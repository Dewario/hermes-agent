#!/usr/bin/env python3
"""Slice A3: audit proposed interrogatory answers against one matter record.

Dedicated ROG parsers and schemas — does not reuse RFP/RFA parsers.
Synthetic-only until discovery-workflow SPEC §9.5 sign-off per matter.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
LEGAL_ROOT = SCRIPT_PATH.parents[2]
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"
MATTER_SAFETY = LEGAL_ROOT / "scripts" / "matter_safety.py"

REQUESTS_REL = Path("02_outputs") / "rog_requests.json"
PROPOSITIONS_REL = Path("02_outputs") / "proposed_rog_propositions.jsonl"
PROPOSITIONS_META_REL = Path("02_outputs") / "proposed_rog_propositions_meta.json"
AUDIT_ITEMS_REL = Path("02_outputs") / "rog_audit_items.jsonl"
AUDIT_REPORT_REL = Path("02_outputs") / "rog_response_audit_report.md"

DEFAULT_ROG_SOURCE = Path("01_discovery_served") / "rog_set.md"
DEFAULT_PROPOSED_SOURCE = Path("01_discovery_proposed") / "proposed_rog_answers.md"
NON_EVIDENCE_PREFIXES = (
    "01_discovery_proposed/",
    "01_discovery_served/",
    "02_outputs/",
)

SCHEMA_VERSION = 1
REQUEST_TYPE = "rog"
MODE = "audit_incoming_response"

PROPOSITION_KINDS = {
    "chronology_assertion",
    "medical_assertion",
    "wage_assertion",
    "liability_assertion",
    "identity_assertion",
    "other_record_bound",
}
SENSITIVE_KINDS = {
    "chronology_assertion",
    "medical_assertion",
    "wage_assertion",
    "liability_assertion",
}
STATUS_VALUES = {
    "supported",
    "partially_supported",
    "ambiguous",
    "unsupported",
    "conflicts_with_record",
    "needs_attorney_decision",
}
CITE_TYPES = {"bates", "intake", "transcript", "discovery", "case_file"}

ROG_HEADING_RE = re.compile(
    r"^\s*(?:(?:Interrogator(?:y|ies)|ROG)\s*(?:No\.?|Number)?\s*)"
    r"(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
RFP_HEADING_RE = re.compile(r"^\s*(?:Request\s+for\s+Production|RFP)\b", re.IGNORECASE)
RFA_HEADING_RE = re.compile(r"^\s*(?:Request\s+for\s+Admission|RFA)\b", re.IGNORECASE)
NUMBERED_RE = re.compile(r"^\s*(?P<num>\d{1,3})[.)]\s+(?P<rest>.+)$")
RESPONSE_HEADING_RE = re.compile(
    r"^\s*(?:(?:Answer|Response)\s+to\s+)?(?:(?:Interrogator(?:y|ies)|ROG)"
    r"\s*(?:No\.?|Number)?\s*)(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
SUBPART_RE = re.compile(
    r"^\s*\((?P<label>[a-z]|[A-Z]|\d{1,2})\)\s+(?P<rest>.+)$"
)
BATES_TEXT_RE = re.compile(
    r"\b([A-Z][A-Z0-9]{1,11}(?:-[A-Z][A-Z0-9]{1,11})*)[-_](0\d{2,7}|\d{5,8})\b"
)
TRANSCRIPT_LINE_RE = re.compile(r"^\s*(?P<page>\d{1,4})[:.](?P<line>\d{1,3})\s+(?P<text>.+)$")

STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "been", "by", "for", "from", "has",
    "have", "in", "is", "it", "of", "on", "or", "plaintiff", "request",
    "that", "the", "this", "to", "will", "with", "answer", "state", "identify",
    "describe", "interrogatory",
}


class UsageError(RuntimeError):
    """Bad input state; caller should return exit code 1 or 2."""


@dataclass(frozen=True)
class TextHit:
    row: dict[str, Any]
    line: int
    text: str
    score: int


def _load_casegraph():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("legal_casegraph_rog", CASEGRAPH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load casegraph script: {CASEGRAPH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_response_rules():
    sys.dont_write_bytecode = True
    path = SCRIPT_PATH.parent / "response_audit_rules.py"
    spec = importlib.util.spec_from_file_location("response_audit_rules_rog", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cg = _load_casegraph()

def _load_matter_safety():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("matter_safety_rog_audit", MATTER_SAFETY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load matter_safety: {MATTER_SAFETY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ms = _load_matter_safety()
rar = _load_response_rules()


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeError:
            continue
    return data.decode("utf-8", errors="replace")


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise UsageError(f"missing JSONL file: {path}")
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise UsageError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def matter_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise UsageError(f"matter directory not found: {root}")
    return root


def contained(root: Path, rel_or_abs: str | Path) -> Path:
    path = Path(rel_or_abs)
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UsageError(f"path escapes matter dir: {resolved}") from exc
    return resolved


def output_path(root: Path, rel: Path) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def refresh_casegraph_index(root: Path) -> int:
    manifest = root / ".casegraph" / "manifest.json"
    if not manifest.is_file():
        return 0
    return cg.main(["build", str(root)])


def evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in rows:
        relpath = str(row.get("relpath") or "").replace("\\", "/")
        if relpath.startswith(NON_EVIDENCE_PREFIXES):
            continue
        kept.append(row)
    return kept


def _refuse_wrong_request_type(text: str) -> None:
    has_rog = any(ROG_HEADING_RE.match(line) for line in text.splitlines())
    has_rfp = any(RFP_HEADING_RE.match(line) for line in text.splitlines())
    has_rfa = any(RFA_HEADING_RE.match(line) for line in text.splitlines())
    if has_rfp and not has_rog:
        raise UsageError("source looks like RFPs; use discovery_response.py (Slice A1)")
    if has_rfa and not has_rog:
        raise UsageError("source looks like RFAs; use rfa_audit.py (Slice A2)")


def _blocks_by_heading(text: str, heading_re: re.Pattern[str]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = heading_re.match(line)
        if match:
            if current is not None:
                blocks.append(current)
            rest = match.group("rest").strip()
            current = (match.group("num"), [rest] if rest else [])
            continue
        if current is not None:
            current[1].append(line)
    if current is not None:
        blocks.append(current)
    return [(num, "\n".join(lines).strip()) for num, lines in blocks if "\n".join(lines).strip()]


def _numbered_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = NUMBERED_RE.match(line)
        if match:
            if current is not None:
                blocks.append(current)
            current = (match.group("num"), [match.group("rest").strip()])
            continue
        if current is not None:
            current[1].append(line)
    if current is not None:
        blocks.append(current)
    return [(num, "\n".join(lines).strip()) for num, lines in blocks if "\n".join(lines).strip()]


def _split_subparts(body: str) -> list[tuple[str | None, str]]:
    """Return (subpart_label_or_None, text) chunks for one interrogatory body."""
    lines = body.splitlines()
    chunks: list[tuple[str | None, list[str]]] = []
    current: tuple[str | None, list[str]] | None = None
    preamble: list[str] = []
    saw_subpart = False
    for raw in lines:
        match = SUBPART_RE.match(raw)
        if match:
            saw_subpart = True
            if current is not None:
                chunks.append(current)
            elif preamble:
                chunks.append((None, preamble))
                preamble = []
            current = (match.group("label").lower(), [match.group("rest").strip()])
            continue
        if current is not None:
            current[1].append(raw)
        else:
            preamble.append(raw)
    if current is not None:
        chunks.append(current)
    elif preamble:
        chunks.append((None, preamble))
    if not saw_subpart:
        text = " ".join(" ".join(preamble).split())
        return [(None, text)] if text else []
    out: list[tuple[str | None, str]] = []
    for label, parts in chunks:
        text = " ".join(" ".join(parts).split())
        if text:
            out.append((label, text))
    return out


def parse_rog_text(text: str) -> list[dict[str, Any]]:
    _refuse_wrong_request_type(text)
    blocks = _blocks_by_heading(text, ROG_HEADING_RE) or _numbered_blocks(text)
    items: list[dict[str, Any]] = []
    for idx, (number_raw, body) in enumerate(blocks, 1):
        parent_id = f"ROG-{idx:03d}"
        subparts = _split_subparts(body)
        if len(subparts) == 1 and subparts[0][0] is None:
            items.append({
                "item_id": parent_id,
                "parent_id": parent_id,
                "subpart": None,
                "number_raw": number_raw,
                "text": subparts[0][1],
                "parse_warnings": [],
            })
            continue
        for sub_idx, (label, sub_text) in enumerate(subparts, 1):
            items.append({
                "item_id": f"{parent_id}-S{sub_idx:02d}",
                "parent_id": parent_id,
                "subpart": label or str(sub_idx),
                "number_raw": number_raw,
                "text": sub_text,
                "parse_warnings": [],
            })
    return items


def proposition_kind(text: str) -> str:
    lower = text.lower()
    # Wage before medical: "wage loss … after the injury" must not become medical.
    if any(n in lower for n in ("wage", "earnings", "income", "payroll", "lost wages")):
        return "wage_assertion"
    if any(n in lower for n in ("medical", "doctor", "hospital", "treatment", "diagnosis")):
        return "medical_assertion"
    if "injury" in lower and any(n in lower for n in ("treat", "care", "hospital", "doctor")):
        return "medical_assertion"
    if any(n in lower for n in ("negligen", "liable", "liability", "duty", "breach", "fault")):
        return "liability_assertion"
    if any(n in lower for n in ("on or about", "june", "dated", "occurred", "happened on", "2024", "2025")):
        return "chronology_assertion"
    if any(n in lower for n in ("name is", "reside", "address", "date of birth", "ssn")):
        return "identity_assertion"
    return "other_record_bound"


def _split_sentences(block: str) -> list[str]:
    lines = []
    for raw in block.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if re.match(r"(?i)^(response|answer|request)\s*[:#-]?$", stripped):
            continue
        lines.append(stripped.lstrip("-* ").strip())
    text = " ".join(lines)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [part.strip() for part in parts if part.strip()]


def parse_proposed_rog_text(text: str, requests: dict[str, Any]) -> list[dict[str, Any]]:
    _refuse_wrong_request_type(text)
    if requests.get("request_type") != REQUEST_TYPE:
        raise UsageError(
            f"rog_requests.json request_type must be {REQUEST_TYPE!r}, "
            f"got {requests.get('request_type')!r}"
        )
    blocks = _blocks_by_heading(text, RESPONSE_HEADING_RE) or _numbered_blocks(text)
    # Map number_raw -> parent items (and flat items without subparts)
    by_number: dict[str, list[dict[str, Any]]] = {}
    for item in requests.get("items", []):
        by_number.setdefault(str(item["number_raw"]), []).append(item)
    order_parents = sorted({item["parent_id"] for item in requests.get("items", [])})

    propositions: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    for idx, (number_raw, body) in enumerate(blocks, 1):
        candidates = by_number.get(number_raw) or []
        if not candidates and idx - 1 < len(order_parents):
            parent = order_parents[idx - 1]
            candidates = [i for i in requests.get("items", []) if i["parent_id"] == parent]
        if not candidates:
            item_id = f"ROG-{idx:03d}"
            target_ids = [item_id]
        elif len(candidates) == 1:
            target_ids = [candidates[0]["item_id"]]
        else:
            # Answer may address parent; attach propositions to each subpart text overlap,
            # else to parent-first subpart only once via parent_id aggregate item.
            target_ids = [candidates[0]["parent_id"]]
            # Prefer a synthetic parent bucket: use first subpart's parent_id as item_id
            # only if no parent-level item exists.
            parent_id = candidates[0]["parent_id"]
            if not any(i["item_id"] == parent_id for i in candidates):
                target_ids = [candidates[0]["item_id"]]

        answer_chunks = _split_subparts(body)
        if len(answer_chunks) > 1 and len(candidates) > 1:
            label_to_item = {
                str(i.get("subpart") or "").lower(): i["item_id"] for i in candidates
            }
            for label, chunk in answer_chunks:
                item_id = label_to_item.get((label or "").lower()) or candidates[0]["item_id"]
                for sentence in _split_sentences(chunk):
                    counters[item_id] = counters.get(item_id, 0) + 1
                    prop_id = f"{item_id}-P{counters[item_id]:02d}"
                    propositions.append({
                        "item_id": item_id,
                        "proposition_id": prop_id,
                        "text": sentence,
                        "kind": proposition_kind(sentence),
                    })
            continue

        item_id = target_ids[0]
        for sentence in _split_sentences(body):
            counters[item_id] = counters.get(item_id, 0) + 1
            prop_id = f"{item_id}-P{counters[item_id]:02d}"
            propositions.append({
                "item_id": item_id,
                "proposition_id": prop_id,
                "text": sentence,
                "kind": proposition_kind(sentence),
            })
    return propositions


def _matter_id(root: Path) -> str:
    try:
        return str(cg.load_manifest(root).get("matter_id") or root.name)
    except Exception:
        return root.name


def load_requests(root: Path) -> dict[str, Any]:
    path = root / REQUESTS_REL
    if not path.is_file():
        raise UsageError(f"missing {path}; run parse-rog first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("request_type") != REQUEST_TYPE:
        raise UsageError(
            f"{path} is not a ROG request set (request_type={payload.get('request_type')!r})"
        )
    return payload


def cmd_parse_rog(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_ROG_SOURCE)
    if not source.is_file():
        print(f"ERROR: served ROG source not found: {source}", file=sys.stderr)
        return 2
    try:
        items = parse_rog_text(read_text(source))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    parse_errors: list[str] = []
    if not items:
        parse_errors.append("zero ROG items parsed")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "matter_id": _matter_id(root),
        "request_type": REQUEST_TYPE,
        "mode": MODE,
        "source": {
            "relpath": source.relative_to(root).as_posix(),
            "sha256": sha256_file(source),
            "served_date": None,
            "propounding_party": args.propounding_party,
        },
        "parsed_at": utcnow(),
        "items": items,
        "parse_errors": parse_errors,
    }
    write_json(output_path(root, REQUESTS_REL), payload)
    if parse_errors:
        print("; ".join(parse_errors), file=sys.stderr)
        return 1
    refresh_casegraph_index(root)
    print(f"parsed {len(items)} ROG items -> {root / REQUESTS_REL}")
    return 0


def cmd_parse_proposed_rog(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_PROPOSED_SOURCE)
    if not source.is_file():
        print(f"ERROR: proposed ROG answers source not found: {source}", file=sys.stderr)
        return 2
    requests = load_requests(root)
    try:
        rows = parse_proposed_rog_text(read_text(source), requests)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print("zero proposed ROG propositions parsed", file=sys.stderr)
        return 1
    write_jsonl(output_path(root, PROPOSITIONS_REL), rows)
    write_json(
        output_path(root, PROPOSITIONS_META_REL),
        {
            "schema_version": SCHEMA_VERSION,
            "request_type": REQUEST_TYPE,
            "mode": MODE,
            "source": {
                "relpath": source.relative_to(root).as_posix(),
                "sha256": sha256_file(source),
            },
            "parsed_at": utcnow(),
            "count": len(rows),
        },
    )
    refresh_casegraph_index(root)
    print(f"parsed {len(rows)} proposed ROG propositions -> {root / PROPOSITIONS_REL}")
    return 0


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    out: list[str] = []
    for word in words:
        if word in STOPWORDS:
            continue
        if word.endswith("s") and len(word) > 4:
            word = word[:-1]
        if word not in out:
            out.append(word)
    return out


def _text_cache(root: Path) -> Path:
    return root / ".casegraph" / "text"


def _read_cached_doc(root: Path, row: dict[str, Any]) -> str:
    cache = _text_cache(root) / f"{row.get('sha256')}.txt"
    if cache.is_file():
        return read_text(cache)
    path = root / str(row.get("relpath", ""))
    return read_text(path) if path.is_file() else ""


def _row_for_bates(rows: list[dict[str, Any]], prefix: str, number: int) -> dict[str, Any] | None:
    try:
        return cg._resolve_bates(rows, prefix, number)
    except Exception:
        for row in rows:
            if row.get("bates_prefix") == prefix and row.get("bates_start") is not None:
                if int(row["bates_start"]) <= number <= int(row.get("bates_end") or row["bates_start"]):
                    return row
    return None


def _cite_for_hit(row: dict[str, Any], line: int | None = None, text: str | None = None) -> dict[str, Any]:
    relpath = str(row.get("relpath") or "").replace("\\", "/")
    if row.get("bates_prefix") and row.get("bates_start") is not None:
        return {
            "type": "bates",
            "value": f"{row['bates_prefix']}-{int(row['bates_start']):06d}",
            "quote": text or None,
        }
    if relpath.startswith("00_intake/"):
        return {"type": "intake", "value": relpath, "quote": text or None}
    if relpath.startswith("01_transcripts/"):
        page, line_start, line_end = _transcript_locator(text or "", line)
        return {
            "type": "transcript",
            "value": Path(relpath).stem,
            "page": page,
            "line_start": line_start,
            "line_end": line_end,
            "quote": _strip_transcript_prefix(text or "") or None,
        }
    if relpath.startswith("01_discovery"):
        return {"type": "discovery", "value": relpath, "quote": text or None}
    return {"type": "case_file", "value": relpath, "quote": text or None}


def _transcript_locator(text: str, fallback_line: int | None) -> tuple[int, int, int]:
    match = TRANSCRIPT_LINE_RE.match(text or "")
    if match:
        page = int(match.group("page"))
        line = int(match.group("line"))
        return page, line, line
    line = int(fallback_line or 1)
    return 1, line, line


def _strip_transcript_prefix(text: str) -> str:
    match = TRANSCRIPT_LINE_RE.match(text or "")
    return match.group("text").strip() if match else text.strip()


def search_record(root: Path, rows: list[dict[str, Any]], query: str) -> list[TextHit]:
    explicit_hits: list[TextHit] = []
    for prefix, number in BATES_TEXT_RE.findall(query.upper()):
        row = _row_for_bates(rows, prefix, int(number))
        if row:
            explicit_hits.append(TextHit(row=row, line=1, text="", score=99))
    if explicit_hits:
        return explicit_hits

    terms = _tokenize(query)
    if not terms:
        return []
    hits: list[TextHit] = []
    for row in rows:
        text = _read_cached_doc(root, row)
        if not text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            lower = line.lower()
            score = sum(1 for term in terms if term in lower)
            if score >= 2 or (score >= 1 and any(
                term in {"incident", "ladder", "wage", "june", "injury", "medical", "negligen"}
                for term in terms
            )):
                hits.append(TextHit(row=row, line=lineno, text=line.strip()[:300], score=score))
    hits.sort(key=lambda h: (h.score, 1 if h.row.get("bates_prefix") else 0), reverse=True)
    return hits[:5]


def _audit_row(
    proposition: dict[str, Any],
    status: str,
    record_cites: list[dict[str, Any]],
    conflict_cites: list[dict[str, Any]],
    notes: str,
) -> dict[str, Any]:
    row = {
        "item_id": proposition["item_id"],
        "proposition_id": proposition["proposition_id"],
        "proposition_text": proposition["text"],
        "kind": proposition["kind"],
        "status": status,
        "record_cites": record_cites,
        "conflict_cites": conflict_cites,
        "notes": notes,
        "attorney_review_required": status != "supported",
        "request_type": REQUEST_TYPE,
        "mode": MODE,
    }
    return rar.attach_rule_ids(row, request_type=REQUEST_TYPE)


def audit_rog_proposition(
    root: Path,
    rows: list[dict[str, Any]],
    proposition: dict[str, Any],
) -> dict[str, Any]:
    text = proposition["text"]
    kind = proposition["kind"]
    hits = search_record(root, rows, text)
    cites = [_cite_for_hit(hit.row, hit.line, hit.text) for hit in hits[:3]]
    lower = text.lower()

    if "object" in lower or "privilege" in lower or "work product" in lower:
        return _audit_row(
            proposition, "needs_attorney_decision", [], [],
            "Objection/privilege strategy requires attorney review.",
        )

    if hits:
        note = "Indexed record contains support for this proposition."
        if any(str(hit.row.get("relpath", "")).startswith("01_transcripts/") for hit in hits):
            note = "Indexed testimony contains support for this proposition."
        return _audit_row(proposition, "supported", cites, [], note)

    if kind in SENSITIVE_KINDS:
        return _audit_row(
            proposition, "unsupported", [], [],
            f"Unsourced {kind.replace('_', ' ')}; cannot silent-pass without record cites.",
        )

    return _audit_row(
        proposition, "unsupported", [], [],
        "No adequate support found in the indexed matter record.",
    )


def cmd_audit_rog(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    status = cg.main(["status", str(root)])
    if status != 0:
        print("ERROR: casegraph status is not green; rebuild before audit", file=sys.stderr)
        return 1
    load_requests(root)
    rows = evidence_rows(cg.load_documents(root))
    propositions = read_jsonl(root / PROPOSITIONS_REL)
    audit_rows = [audit_rog_proposition(root, rows, prop) for prop in propositions]
    write_jsonl(output_path(root, AUDIT_ITEMS_REL), audit_rows)
    refresh_casegraph_index(root)
    print(f"audited {len(audit_rows)} ROG propositions -> {root / AUDIT_ITEMS_REL}")
    return 0


def validate_cite(cite: dict[str, Any]) -> str | None:
    ctype = cite.get("type")
    if ctype not in CITE_TYPES:
        return f"invalid cite type: {ctype}"
    if not str(cite.get("value") or "").strip():
        return "cite value is empty"
    if ctype == "transcript":
        if cite.get("page") is None or cite.get("line_start") is None:
            return "transcript cite missing page/line_start"
    return None


def validate_rog_audit_records(
    requests: dict[str, Any],
    propositions: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if requests.get("request_type") != REQUEST_TYPE:
        errors.append("requests request_type must be rog")
    valid_items = {item["item_id"] for item in requests.get("items", [])}
    # Allow propositions keyed to parent_id when answers are not subpart-split.
    valid_items |= {item["parent_id"] for item in requests.get("items", [])}
    prop_ids = [p.get("proposition_id") for p in propositions]
    if len(set(prop_ids)) != len(prop_ids):
        errors.append("duplicate proposition IDs")
    audit_ids = [r.get("proposition_id") for r in audit_rows]
    if set(audit_ids) != set(prop_ids) or len(audit_ids) != len(prop_ids):
        errors.append("audit rows must match propositions exactly once")
    for prop in propositions:
        if prop.get("item_id") not in valid_items:
            errors.append(f"{prop.get('proposition_id')}: unknown item_id {prop.get('item_id')}")
        if prop.get("kind") not in PROPOSITION_KINDS:
            errors.append(f"{prop.get('proposition_id')}: invalid kind {prop.get('kind')}")
    for row in audit_rows:
        pid = row.get("proposition_id")
        status = row.get("status")
        kind = row.get("kind")
        if status not in STATUS_VALUES:
            errors.append(f"{pid}: invalid status {status}")
        if kind not in PROPOSITION_KINDS:
            errors.append(f"{pid}: invalid kind {kind}")
        record_cites = row.get("record_cites") or []
        conflict_cites = row.get("conflict_cites") or []
        for cite in [*record_cites, *conflict_cites]:
            issue = validate_cite(cite)
            if issue:
                errors.append(f"{pid}: {issue}")
        if status in {"supported", "partially_supported"} and not record_cites:
            errors.append(f"{pid}: {status} requires record_cites")
        if status == "conflicts_with_record" and not conflict_cites:
            errors.append(f"{pid}: conflicts_with_record requires conflict_cites")
        if status in {"unsupported", "ambiguous", "needs_attorney_decision"} and not str(
            row.get("notes") or ""
        ).strip():
            errors.append(f"{pid}: {status} requires notes")
        if (
            kind in SENSITIVE_KINDS
            and status == "supported"
            and not record_cites
        ):
            errors.append(f"{pid}: sensitive kind {kind} cannot be supported without cites")
    return errors


def _format_cite(cite: dict[str, Any]) -> str:
    ctype = cite.get("type")
    value = str(cite.get("value") or "")
    if ctype == "transcript":
        return f"{value} {cite.get('page')}:{cite.get('line_start')}-{cite.get('line_end')}"
    if ctype == "bates":
        return value
    return f"{ctype}:{value}"


def _display_item_id(item_id: str) -> str:
    match = re.fullmatch(r"ROG-(\d{3})(?:-S(\d{2}))?", item_id)
    if not match:
        return item_id
    base = f"Interrogatory {int(match.group(1))}"
    if match.group(2):
        return f"{base}, subpart {int(match.group(2))}"
    return base


def _display_proposition_id(proposition_id: str) -> str:
    match = re.fullmatch(r"ROG-(\d{3})(?:-S(\d{2}))?-P(\d{2})", proposition_id)
    if not match:
        return proposition_id
    base = f"Interrogatory {int(match.group(1))}"
    if match.group(2):
        base = f"{base}, subpart {int(match.group(2))}"
    return f"{base}, proposition {int(match.group(3))}"


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(1 for row in rows if row.get("status") == status) for status in sorted(STATUS_VALUES)}


def build_rog_audit_report(
    root: Path,
    requests: dict[str, Any],
    audit_rows: list[dict[str, Any]],
) -> str:
    matter_id = _matter_id(root)
    proposed = root / DEFAULT_PROPOSED_SOURCE
    proposed_sha = sha256_file(proposed) if proposed.is_file() else "unknown"
    status_counts = _status_counts(audit_rows)
    by_item: dict[str, list[dict[str, Any]]] = {}
    for row in audit_rows:
        by_item.setdefault(row["item_id"], []).append(row)
    request_map = {item["item_id"]: item for item in requests.get("items", [])}

    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Interrogatory Answer Audit - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Request type:** {REQUEST_TYPE}",
        f"**Mode:** {MODE}",
        f"**Proposed source sha256:** {proposed_sha}",
        "**Casegraph status:** fresh",
        "**Single-matter invocation:** confirmed",
        "",
        "> Draft for attorney review.",
        "> Not a certification that interrogatory answers are ready to serve.",
        "> No cross-client facts. No final objection strategy.",
        "",
        "## Status summary",
        "",
        "| Status | Count |",
        "|--------|------:|",
    ]
    for status in [
        "supported", "partially_supported", "ambiguous", "unsupported",
        "conflicts_with_record", "needs_attorney_decision",
    ]:
        lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    lines.extend(["", "## By request", ""])

    for item_id in sorted(by_item):
        req = request_map.get(item_id) or next(
            (i for i in requests.get("items", []) if i["parent_id"] == item_id),
            {},
        )
        lines.extend([
            f"### {_display_item_id(item_id)}",
            "",
            f"**Request (served):** {req.get('text', '')}",
            "",
            "| proposition | Kind | Status | Cites | Notes |",
            "|-------------|------|--------|-------|-------|",
        ])
        for row in by_item[item_id]:
            cite_text = ", ".join(
                _format_cite(c) for c in (row.get("record_cites") or row.get("conflict_cites") or [])
            ) or "-"
            note = str(row.get("notes") or "").replace("|", "\\|")
            lines.append(
                f"| {_display_proposition_id(row['proposition_id'])} | {row['kind']} | "
                f"{row['status']} | {cite_text} | {note} |"
            )
            lines.append(f"<!-- proposition: {row.get('proposition_text', '')} -->")
        lines.append("")

    flagged = [
        r for r in audit_rows
        if r["status"] in {
            "unsupported", "conflicts_with_record", "needs_attorney_decision", "ambiguous",
        }
    ]
    lines.extend(["## Conflicts and open items (roll-up)", ""])
    if flagged:
        for row in flagged:
            lines.append(
                f"- {_display_proposition_id(row['proposition_id'])}: "
                f"{row['kind']}/{row['status']} - {row['notes']}"
            )
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Attorney checklist",
        "",
        "- [ ] Every unsourced chronology/medical/wage/liability assertion reviewed",
        "- [ ] Testimony cites checked at page:line against transcript extract",
        "- [ ] No other client's identifiers appear in this report",
        "- [ ] Gate commands for Slice A3 exit 0",
        "",
    ])
    return "\n".join(lines)


def cmd_package_rog_audit(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = load_requests(root)
    propositions = read_jsonl(root / PROPOSITIONS_REL)
    audit_rows = read_jsonl(root / AUDIT_ITEMS_REL)
    errors = validate_rog_audit_records(requests, propositions, audit_rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report = build_rog_audit_report(root, requests, audit_rows)
    path = output_path(root, AUDIT_REPORT_REL)
    path.write_text(report, encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote ROG audit report -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    completed = subprocess.run(command, text=True, check=False)
    return completed.returncode


def cmd_validate_rog_audit(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = load_requests(root)
    propositions = read_jsonl(root / PROPOSITIONS_REL)
    audit_rows = read_jsonl(root / AUDIT_ITEMS_REL)
    errors = validate_rog_audit_records(requests, propositions, audit_rows)
    report = root / AUDIT_REPORT_REL
    if not report.is_file():
        errors.append(f"missing audit report: {report}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    gates = [
        [sys.executable, str(CASEGRAPH_SCRIPT), "status", str(root)],
        [sys.executable, str(CASEGRAPH_SCRIPT), "verify-cites", str(root), str(report), "--allow-empty"],
        [sys.executable, str(CASEGRAPH_SCRIPT), "check-isolation", str(root), str(report), "--strict"],
    ]
    _ms.append_live_preflight_gate(
        gates,
        root,
        live_preflight_script=LIVE_PREFLIGHT_SCRIPT,
        skip_live_preflight=bool(args.skip_live_preflight),
        synthetic_flag=bool(getattr(args, 'synthetic', False)),
        request_type=REQUEST_TYPE,
        mode=MODE,
        slice_id="A3",
    )
    for command in gates:
        code = run_command(command)
        if code != 0:
            print(f"FAIL: gate exited {code}: {' '.join(command)}")
            return 1
    print("PASS: ROG audit validation")
    return 0


def _create_synthetic_rog_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_served").mkdir(parents=True)
    (root / "01_discovery_proposed").mkdir(parents=True)
    (root / "01_transcripts").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    (root / "01_discovery_served" / "rog_set.md").write_text(
        "Interrogatory No. 1: State the date of the incident involving the ladder.\n\n"
        "Interrogatory No. 2:\n"
        "(a) Identify medical treatment received after the injury.\n"
        "(b) State whether plaintiff claims wage loss.\n\n"
        "Interrogatory No. 3: State all facts supporting any claim of negligence.\n",
        encoding="utf-8",
    )
    (root / "01_discovery_proposed" / "proposed_rog_answers.md").write_text(
        "Answer to Interrogatory No. 1: The incident occurred on June 1, 2024.\n\n"
        "Answer to Interrogatory No. 2:\n"
        "(a) Plaintiff received medical treatment after the injury.\n"
        "(b) Plaintiff claims wage loss began after the injury.\n\n"
        "Answer to Interrogatory No. 3: Defendant was negligent in failing to train supervisors.\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000011\n"
        "**Date:** 2024-06-01\n\n"
        "Incident report for the June 1, 2024 event involving the ladder.\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000030.md").write_text(
        f"**Bates Range:** {prefix}-000030 - {prefix}-000030\n\n"
        "Medical note: treatment after the injury included evaluation for ladder trauma.\n",
        encoding="utf-8",
    )
    (root / "01_transcripts" / "Depo-Wage.txt").write_text(
        "42:3 The worker testified that wage loss began after the injury.\n",
        encoding="utf-8",
    )
    cg.main(["init", str(root), "--matter-id", matter_id, "--bates-prefix", prefix])
    cg.main(["build", str(root)])
    cg.main(["add-entity", str(root), "--name", "June", "--role", "date-term"])


def cmd_selftest(_args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="rog-audit-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_rog_matter(a, "SYN-ROG-A", "THORN-PROD")
        _create_synthetic_rog_matter(b, "SYN-ROG-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-rog", str(matter)],
                ["parse-proposed-rog", str(matter)],
                ["audit-rog", str(matter)],
                ["package-rog-audit", str(matter)],
                ["validate-rog-audit", str(matter)],
            ):
                code = main(command)
                if code != 0:
                    print(f"selftest failed for {matter.name}: {' '.join(command)}", file=sys.stderr)
                    return code
        a_report = (a / AUDIT_REPORT_REL).read_text(encoding="utf-8")
        b_report = (b / AUDIT_REPORT_REL).read_text(encoding="utf-8")
        if "RIVER-PROD" in a_report or "THORN-PROD" in b_report:
            print("selftest failed: cross-matter Bates leaked into report", file=sys.stderr)
            return 1
        print("PASS: rog-audit selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-rog", help="parse served interrogatories into rog_requests.json")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.add_argument("--propounding-party", default="Defendant")
    p.set_defaults(fn=cmd_parse_rog)

    p = sub.add_parser("parse-proposed-rog", help="parse proposed ROG answers into propositions")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_proposed_rog)

    p = sub.add_parser("audit-rog", help="audit proposed ROG propositions against casegraph")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_audit_rog)

    p = sub.add_parser("package-rog-audit", help="write rog_response_audit_report.md")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package_rog_audit)

    p = sub.add_parser("validate-rog-audit", help="run Slice A3 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(fn=cmd_validate_rog_audit)

    p = sub.add_parser("selftest", help="run offline synthetic ROG audit E2E")
    p.set_defaults(fn=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
