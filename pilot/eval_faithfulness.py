#!/usr/bin/env python3
"""Offline faithfulness / claim-grounding harness for SYNTHETIC legal goldens.

Reads a review or intake package markdown plus a fixture text corpus directory.
Extracts Bates-cited claim-like sentences and checks quoted spans or normalized
tokens against cited document text.

SYNTHETIC / CI ONLY — never point this at live matter data in CI pipelines.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CASEGRAPH_PATH = REPO_ROOT / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"
SYNTHETIC_BANNER = "SYNTHETIC / NON-CLIENT / TEST ONLY"

# Boilerplate excluded from token-overlap scoring (normalized form).
_STOPWORDS = frozenset(
    {
        "attorney",
        "review",
        "requires",
        "required",
        "evidence",
        "suggests",
        "supports",
        "document",
        "documents",
        "source",
        "section",
        "package",
        "pilot",
        "synthetic",
        "fixture",
        "fixtures",
        "matter",
        "analysis",
        "preliminary",
        "determination",
        "determinations",
    }
)

# Pure citation / inventory rows — not factual claims.
_META_LINE_RE = re.compile(
    r"^\|?\s*(doc id|document id|type|date|author|pages?|bates|source|significance|"
    r"issue tags?|atty review|appears in|contact|depo priority)\b",
    re.IGNORECASE,
)

# Gap / missing-production prose (extends casegraph _GAP_MARKER_RE).
_LOCAL_GAP_RE = re.compile(
    r"not provided in (?:this )?pilot|not in pilot|not included in the fixture|"
    r"not included in this pilot|pending their availability|listed as produced at|"
    r"documents referenced but not|missing documents|not reviewed|"
    r"not located|not yet available|not produced|withheld as privileged|"
    r"referenc(?:e|ed) but not",
    re.IGNORECASE,
)

_GAP_SECTION_NEEDLES = (
    "documents referenced but not",
    "missing documents",
    "production gap",
    "documents withheld",
    "documents claimed not",
    "follow-up discovery",
    "missing custodians",
    "missing time period",
    "additional rfps",
    "additional interrogator",
    "additional rfas",
    "document inventory",
    "deposition outline",
    "attorney final-review checklist",
    "verification",
    "pitfalls",
    "production preflight",
    "issue code legend",
    "issue coding matrix",
    "witness / entity extraction",
    "privilege / confidentiality",
    "production cover letter reconciliation",
    "duplicate / near-duplicate",
    "bates range normalization",
)

# Sections where Bates-cited sentences are treated as checkable factual claims.
_CLAIM_SECTION_NEEDLES = (
    "key fact",
    "chronology",
    "timeline",
    "contradiction",
    "medical extraction",
    "wage / damages",
    "wage extraction",
    "safety rule",
    "policy / incident report extraction",
)


def _in_gap_section(section: str) -> bool:
    lower = section.lower()
    return any(needle in lower for needle in _GAP_SECTION_NEEDLES)


def _in_claim_section(section: str) -> bool:
    lower = section.lower()
    return any(needle in lower for needle in _CLAIM_SECTION_NEEDLES)


def _line_gap_context(line: str, section: str, cg) -> bool:
    if _in_gap_section(section):
        return True
    if cg._GAP_MARKER_RE.search(line):
        return True
    if _LOCAL_GAP_RE.search(line):
        return True
    # Bulleted missing-document inventory under preflight (synthetic pilot).
    if re.match(
        r"^-\s+.+\(TVRR-PROD-\d{6}\s+through\s+000\d{3}",
        line.strip(),
        re.IGNORECASE,
    ):
        return True
    return False


def _load_casegraph():
    if not CASEGRAPH_PATH.is_file():
        raise FileNotFoundError(f"casegraph helper missing: {CASEGRAPH_PATH}")
    spec = importlib.util.spec_from_file_location("casegraph_faithfulness", CASEGRAPH_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _header_fields(text: str, cg) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in cg._HEADER_FIELD_RE.finditer(text):
        out[m.group("key").strip().lower()] = m.group("value").strip()
    return out


def _register_range(
    index: dict[tuple[str, int], tuple[str, int]],
    text: str,
    value: str,
    parse_bates_range,
) -> None:
    parsed = parse_bates_range(value)
    if not parsed:
        return
    prefix, start, end = parsed
    span = end - start + 1
    for number in range(start, end + 1):
        key = (prefix, number)
        existing = index.get(key)
        if existing is not None and existing[1] <= span:
            continue
        index[key] = (text, span)


def index_corpus(corpus_dir: Path, cg) -> dict[tuple[str, int], str]:
    """Map (bates_prefix, page_number) -> full document text."""
    raw: dict[tuple[str, int], tuple[str, int]] = {}
    for path in sorted(corpus_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fields = _header_fields(text, cg)
        bates_value = fields.get("bates range", "").strip()
        if bates_value and not bates_value.upper().startswith("N/A"):
            _register_range(raw, text, bates_value, cg.parse_bates_range)
        elif not bates_value and fields.get("document id"):
            _register_range(raw, text, fields["document id"], cg.parse_bates_range)
        fb = cg.bates_from_filename(path.name)
        if fb is not None:
            prefix, number = fb
            raw.setdefault((prefix, number), (text, 1))
    return {key: text for key, (text, _span) in raw.items()}


def _claim_text_from_table_line(line: str) -> str | None:
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if not cells:
        return None
    substantive = [c for c in cells if len(c) >= 12]
    if not substantive:
        return None
    return max(substantive, key=len)


def _is_claim_candidate(
    line: str,
    cites: list[tuple[str, int]],
    cg,
    *,
    section: str,
) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if not cites:
        return False
    if not _in_claim_section(section):
        return False
    if _line_gap_context(stripped, section, cg):
        return False
    if _META_CLAIM_RE.search(stripped):
        return False
    if _META_LINE_RE.search(stripped):
        return False
    # Skip markdown table separator rows.
    if re.fullmatch(r"[|\s:\-]+", stripped):
        return False
    # Require some prose beyond bare citations.
    without_cites = cg._BATES_TEXT_RE.sub("", stripped.upper())
    without_cites = re.sub(r"[|*_\-]", " ", without_cites)
    return len(without_cites.strip()) >= 20


def extract_claims(
    package_text: str,
    cg,
    *,
    registered_prefixes: set[str],
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    section = ""
    for raw_line in package_text.splitlines():
        if raw_line.startswith("#"):
            section = raw_line.lstrip("#").strip()
        line = raw_line.rstrip()
        cites = [
            (p, n)
            for p, n in cg._extract_citations(line)
            if p in registered_prefixes
        ]
        if not _is_claim_candidate(line, cites, cg, section=section):
            continue
        claim_text = _claim_text_from_table_line(line) or line.strip()
        key = claim_text.lower()
        if key in seen:
            continue
        seen.add(key)
        claims.append(
            {
                "text": claim_text,
                "citations": [{"prefix": p, "number": n} for p, n in cites],
                "line": line.strip(),
            }
        )
    return claims


def _significant_tokens(normalized_text: str) -> set[str]:
    tokens = set()
    for tok in normalized_text.split():
        if len(tok) < 3:
            continue
        if tok in _STOPWORDS:
            continue
        if tok.isdigit():
            continue
        tokens.add(tok)
    return tokens


def _token_found(token: str, doc_norm: str, doc_tokens: set[str]) -> bool:
    if token in doc_tokens:
        return True
    if len(token) >= 4 and token in doc_norm:
        return True
    return False


_META_CLAIM_RE = re.compile(
    r"direct contradiction|requires attorney review for impeachment|"
    r"resolution may require|three possibilities|conclusion column",
    re.IGNORECASE,
)


def _strip_citations(text: str, cg) -> str:
    out = cg._BATES_TEXT_RE.sub(" ", text)
    return cg._normalize_identifier(out)


def _check_claim(
    claim: dict[str, Any],
    corpus: dict[tuple[str, int], str],
    cg,
    *,
    min_overlap: float,
    min_tokens: int,
    corpus_norm: str = "",
) -> dict[str, Any]:
    cites = claim["citations"]
    doc_texts: list[str] = []
    unresolved: list[str] = []
    for cite in cites:
        key = (cite["prefix"], cite["number"])
        doc = corpus.get(key)
        if doc is None:
            unresolved.append(f"{cite['prefix']}-{cite['number']:06d}")
        else:
            doc_texts.append(doc)

    result: dict[str, Any] = {
        "text": claim["text"],
        "line": claim["line"],
        "citations": cites,
        "unresolved_citations": unresolved,
        "quote_misses": [],
        "token_overlap": 0.0,
        "grounded": False,
        "reason": "",
    }

    if unresolved:
        # Mixed citations: require grounding against resolved docs only.
        if doc_texts:
            cites = [c for c in cites if (c["prefix"], c["number"]) in corpus]
        else:
            result["reason"] = f"unresolved citations: {', '.join(unresolved)}"
            return result

    merged_doc_norm = cg._normalize_identifier("\n".join(doc_texts))
    doc_tokens = _significant_tokens(merged_doc_norm)

    quote_misses: list[str] = []
    for quote in cg._iter_quoted_spans(claim["text"]):
        q = quote.strip().strip(".… ").strip()
        if len(q) < 12:
            continue
        if cg._META_QUOTE_RE.match(q) and len(q) < 60:
            continue
        qn = cg._normalize_identifier(q)
        if qn and qn not in merged_doc_norm:
            # Allow minor typographic drift (straight vs curly apostrophe, etc.).
            q_compact = qn.replace(" ", "")
            if q_compact not in merged_doc_norm.replace(" ", ""):
                quote_misses.append(q[:120])
    if quote_misses and corpus_norm:
        still_missing: list[str] = []
        for q in quote_misses:
            qn = cg._normalize_identifier(q.strip().strip(".… ").strip())
            if qn in corpus_norm or qn.replace(" ", "") in corpus_norm.replace(" ", ""):
                continue
            still_missing.append(q)
        quote_misses = still_missing
    result["quote_misses"] = quote_misses
    if quote_misses:
        result["reason"] = "quoted span not found in cited document(s)"
        return result

    claim_norm = _strip_citations(claim["text"], cg)
    claim_tokens = _significant_tokens(claim_norm)
    if not claim_tokens:
        result["grounded"] = True
        result["reason"] = "citation-only row (no content tokens to verify)"
        return result

    overlap = {t for t in claim_tokens if _token_found(t, merged_doc_norm, doc_tokens)}
    overlap_ratio = len(overlap) / len(claim_tokens)
    result["token_overlap"] = round(overlap_ratio, 3)
    if len(overlap) >= min_tokens and overlap_ratio >= min_overlap:
        result["grounded"] = True
        result["reason"] = "token overlap satisfied"
        return result

    result["reason"] = (
        f"insufficient token overlap ({overlap_ratio:.0%}, "
        f"{len(overlap)}/{len(claim_tokens)} tokens)"
    )
    return result


def evaluate(
    package_path: Path,
    corpus_dir: Path,
    *,
    require_synthetic: bool = True,
    min_overlap: float = 0.15,
    min_tokens: int = 1,
    max_failures: int | None = None,
) -> dict[str, Any]:
    cg = _load_casegraph()
    package_text = package_path.read_text(encoding="utf-8", errors="replace")
    if require_synthetic and SYNTHETIC_BANNER not in package_text:
        return {
            "package": str(package_path),
            "corpus_dir": str(corpus_dir),
            "pass": False,
            "error": f"missing synthetic banner ({SYNTHETIC_BANNER!r})",
            "claims_checked": 0,
            "failures": [],
        }

    corpus = index_corpus(corpus_dir, cg)
    if not corpus:
        return {
            "package": str(package_path),
            "corpus_dir": str(corpus_dir),
            "pass": False,
            "error": "corpus directory contains no indexed Bates documents",
            "claims_checked": 0,
            "failures": [],
        }

    registered_prefixes = {prefix for prefix, _ in corpus}
    claims = extract_claims(package_text, cg, registered_prefixes=registered_prefixes)
    corpus_norm = cg._normalize_identifier("\n".join(corpus.values()))
    failures: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    for claim in claims:
        outcome = _check_claim(
            claim,
            corpus,
            cg,
            min_overlap=min_overlap,
            min_tokens=min_tokens,
            corpus_norm=corpus_norm,
        )
        checked.append(outcome)
        if not outcome["grounded"]:
            failures.append(outcome)
            if max_failures is not None and len(failures) >= max_failures:
                break

    return {
        "package": str(package_path),
        "corpus_dir": str(corpus_dir),
        "corpus_documents": len({id(v) for v in corpus.values()}),
        "corpus_bates_pages": len(corpus),
        "claims_checked": len(checked),
        "claims_extracted": len(claims),
        "failures": failures,
        "pass": not failures and bool(claims),
        "vacuous": not claims,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic legal golden faithfulness / claim-grounding check",
    )
    parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Path to review_package.md or intake_package.md",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Directory of fixture markdown documents (Bates-indexed)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report on stdout")
    parser.add_argument(
        "--no-require-synthetic",
        action="store_true",
        help="Do not require the SYNTHETIC banner (local debugging only)",
    )
    parser.add_argument(
        "--min-overlap",
        type=float,
        default=0.15,
        help="Minimum fraction of significant claim tokens found in cited doc(s)",
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=1,
        help="Minimum overlapping significant tokens required",
    )
    parser.add_argument(
        "--allow-vacuous",
        action="store_true",
        help="Pass when zero Bates-cited claims are extracted (draft packages)",
    )
    args = parser.parse_args(argv)

    package = args.package if args.package.is_absolute() else REPO_ROOT / args.package
    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus

    if not package.is_file():
        print(f"FAIL: package not found: {package}", file=sys.stderr)
        return 1
    if not corpus.is_dir():
        print(f"FAIL: corpus directory not found: {corpus}", file=sys.stderr)
        return 1

    report = evaluate(
        package,
        corpus,
        require_synthetic=not args.no_require_synthetic,
        min_overlap=args.min_overlap,
        min_tokens=args.min_tokens,
    )

    if report.get("vacuous") and not args.allow_vacuous:
        report["pass"] = False
        report["error"] = (
            "no Bates-cited claims extracted (vacuous PASS refused; "
            "use --allow-vacuous only for drafts)"
        )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report.get("error"):
            print(f"FAIL: {report['error']}")
        elif report["pass"]:
            print(
                f"PASS: {report['claims_checked']} claim(s) grounded against "
                f"{report['corpus_documents']} fixture document(s)"
            )
        else:
            print(f"FAIL: {len(report['failures'])} ungrounded claim(s)")
            for item in report["failures"][:20]:
                print(f"  - {item['reason']}: {item['text'][:120]}...")
            if len(report["failures"]) > 20:
                print(f"  ... and {len(report['failures']) - 20} more")

    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    sys.exit(main())
