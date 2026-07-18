#!/usr/bin/env python3
"""Audit proposed RFP responses against one synthetic/legal matter record.

Phase A only: parse served RFPs, parse proposed final responses, grade each
record-bound proposition against the same matter's casegraph index, and write a
draft attorney-review audit report. This script never loads two matters at once
and never generates final discovery response language.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
DISCOVERY_RESPONSE_ROOT = SCRIPT_PATH.parents[1]
LEGAL_ROOT = SCRIPT_PATH.parents[2]
REPO_ROOT = SCRIPT_PATH.parents[4]
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"

REQUESTS_REL = Path("02_outputs") / "discovery_requests.json"
PROPOSITIONS_REL = Path("02_outputs") / "proposed_propositions.jsonl"
AUDIT_ITEMS_REL = Path("02_outputs") / "response_audit_items.jsonl"
AUDIT_REPORT_REL = Path("02_outputs") / "response_audit_report.md"

DEFAULT_RFP_SOURCE = Path("01_discovery_served") / "rfp_set.md"
DEFAULT_PROPOSED_SOURCE = Path("01_discovery_proposed") / "proposed_rfp_responses.md"
NON_EVIDENCE_PREFIXES = (
    "01_discovery_proposed/",
    "01_discovery_served/",
    "02_outputs/",
)

SCHEMA_VERSION = 1
STATUS_VALUES = {
    "supported",
    "partially_supported",
    "ambiguous",
    "unsupported",
    "conflicts_with_record",
    "needs_attorney_decision",
}
CITE_TYPES = {"bates", "intake", "transcript", "discovery", "case_file"}

RFP_HEADING_RE = re.compile(
    r"^\s*(?:(?:Request\s+for\s+Production|RFP)\s*(?:No\.?|Number)?\s*)"
    r"(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
NUMBERED_RE = re.compile(r"^\s*(?P<num>\d{1,3})[.)]\s+(?P<rest>.+)$")
RESPONSE_HEADING_RE = re.compile(
    r"^\s*(?:Response\s+to\s+)?(?:(?:Request\s+for\s+Production|RFP)"
    r"\s*(?:No\.?|Number)?\s*)(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
BATES_TEXT_RE = re.compile(
    r"\b([A-Z][A-Z0-9]{1,11}(?:-[A-Z][A-Z0-9]{1,11})*)[-_](0\d{2,7}|\d{5,8})\b"
)
TRANSCRIPT_LINE_RE = re.compile(r"^\s*(?P<page>\d{1,4})[:.](?P<line>\d{1,3})\s+(?P<text>.+)$")

STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "been", "by", "concerning",
    "documents", "document", "for", "from", "has", "have", "in", "is",
    "it", "of", "on", "or", "plaintiff", "produce", "produced", "produces",
    "production", "request", "requested", "responsive", "set", "shall",
    "that", "the", "this", "to", "will", "with",
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
    spec = importlib.util.spec_from_file_location("legal_casegraph", CASEGRAPH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load casegraph script: {CASEGRAPH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_response_rules():
    sys.dont_write_bytecode = True
    path = LEGAL_ROOT / "discovery-workflow" / "scripts" / "response_audit_rules.py"
    spec = importlib.util.spec_from_file_location("response_audit_rules_rfp", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cg = _load_casegraph()
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
    try:
        root.relative_to(REPO_ROOT)
    except ValueError:
        return root
    # Synthetic fixtures may live in-repo; live work must not. The hard live ban
    # is handled by PROVIDER_AUTH/live_preflight and the skill docs.
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
    """Keep casegraph status green after this tool writes audit artifacts."""
    manifest = root / ".casegraph" / "manifest.json"
    if not manifest.is_file():
        return 0
    return cg.main(["build", str(root)])


def evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return indexed rows that can support or contradict response propositions."""
    kept: list[dict[str, Any]] = []
    for row in rows:
        relpath = str(row.get("relpath") or "").replace("\\", "/")
        if relpath.startswith(NON_EVIDENCE_PREFIXES):
            continue
        kept.append(row)
    return kept


def _blocks_by_heading(text: str, heading_re: re.Pattern[str]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = heading_re.match(line)
        if match:
            if current is not None:
                blocks.append(current)
            current = (match.group("num"), [match.group("rest").strip()] if match.group("rest").strip() else [])
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


def parse_rfp_text(text: str) -> list[dict[str, Any]]:
    blocks = _blocks_by_heading(text, RFP_HEADING_RE) or _numbered_blocks(text)
    items: list[dict[str, Any]] = []
    for idx, (number_raw, body) in enumerate(blocks, 1):
        item_id = f"RFP-{idx:03d}"
        normalized = " ".join(body.split())
        items.append({
            "item_id": item_id,
            "number_raw": number_raw,
            "text": normalized,
            "topic_tags": topic_tags(normalized),
            "time_bound": None,
            "custodian_hints": [],
            "parse_warnings": [],
        })
    return items


def topic_tags(text: str) -> list[str]:
    lower = text.lower()
    tags: list[str] = []
    table = [
        ("incident_report", ("incident report", "accident report")),
        ("photographs", ("photograph", "photo", "image")),
        ("medical", ("medical", "doctor", "hospital", "treatment")),
        ("wage_loss", ("wage", "earnings", "income", "payroll")),
        ("testimony", ("deposition", "testimony", "transcript")),
        ("maintenance", ("maintenance", "inspection", "repair")),
        ("policy", ("policy", "rule", "procedure")),
        ("discovery", ("prior response", "discovery response", "request for production")),
    ]
    for tag, needles in table:
        if any(n in lower for n in needles):
            tags.append(tag)
    return tags


def cmd_parse_rfp(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_RFP_SOURCE)
    if not source.is_file():
        print(f"ERROR: served RFP source not found: {source}", file=sys.stderr)
        return 2
    items = parse_rfp_text(read_text(source))
    parse_errors: list[str] = []
    if not items:
        parse_errors.append("zero RFP items parsed")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "matter_id": _matter_id(root),
        "request_type": "rfp",
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
    print(f"parsed {len(items)} RFP items -> {root / REQUESTS_REL}")
    return 0


def _matter_id(root: Path) -> str:
    try:
        return str(cg.load_manifest(root).get("matter_id") or root.name)
    except Exception:
        return root.name


def load_requests(root: Path) -> dict[str, Any]:
    path = root / REQUESTS_REL
    if not path.is_file():
        raise UsageError(f"missing {path}; run parse-rfp first")
    return json.loads(path.read_text(encoding="utf-8"))


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
    out = []
    for part in parts:
        cleaned = part.strip()
        if cleaned:
            out.append(cleaned)
    return out


def proposition_kind(text: str) -> str:
    lower = text.lower()
    if "object" in lower or "objection" in lower:
        return "other_record_bound"
    if re.search(r"\b(no|not any|does not have|do not have|not in possession)\b", lower) and (
        "document" in lower or "responsive" in lower or "photograph" in lower
    ):
        return "no_documents_assertion"
    if re.search(r"\b(already|previously|prior)\b", lower) and "produc" in lower:
        return "already_produced_assertion"
    if "produc" in lower:
        return "production_commitment"
    return "factual_assertion"


def parse_proposed_text(text: str, requests: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = _blocks_by_heading(text, RESPONSE_HEADING_RE) or _numbered_blocks(text)
    number_to_item = {str(item["number_raw"]): item["item_id"] for item in requests.get("items", [])}
    order_items = [item["item_id"] for item in requests.get("items", [])]
    propositions: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    for idx, (number_raw, body) in enumerate(blocks, 1):
        item_id = number_to_item.get(number_raw) or (order_items[idx - 1] if idx - 1 < len(order_items) else f"RFP-{idx:03d}")
        for sentence in _split_sentences(body):
            counters[item_id] = counters.get(item_id, 0) + 1
            prop_id = f"{item_id}-P{counters[item_id]:02d}"
            start = text.find(sentence)
            propositions.append({
                "item_id": item_id,
                "proposition_id": prop_id,
                "text": sentence,
                "kind": proposition_kind(sentence),
                "source_span": {
                    "start_char": start if start >= 0 else None,
                    "end_char": (start + len(sentence)) if start >= 0 else None,
                },
            })
    return propositions


def cmd_parse_proposed(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_PROPOSED_SOURCE)
    if not source.is_file():
        print(f"ERROR: proposed responses source not found: {source}", file=sys.stderr)
        return 2
    requests = load_requests(root)
    propositions = parse_proposed_text(read_text(source), requests)
    if not propositions:
        print("zero propositions parsed", file=sys.stderr)
        return 1
    write_jsonl(output_path(root, PROPOSITIONS_REL), propositions)
    meta = {
        "schema_version": SCHEMA_VERSION,
        "source": {"relpath": source.relative_to(root).as_posix(), "sha256": sha256_file(source)},
        "parsed_at": utcnow(),
        "count": len(propositions),
    }
    write_json(output_path(root, Path("02_outputs") / "proposed_propositions_meta.json"), meta)
    refresh_casegraph_index(root)
    print(f"parsed {len(propositions)} propositions -> {root / PROPOSITIONS_REL}")
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
        return {"type": "bates", "value": f"{row['bates_prefix']}-{int(row['bates_start']):06d}", "quote": text or None}
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


def search_record(root: Path, rows: list[dict[str, Any]], proposition: str) -> list[TextHit]:
    explicit_hits: list[TextHit] = []
    for prefix, number in BATES_TEXT_RE.findall(proposition.upper()):
        row = _row_for_bates(rows, prefix, int(number))
        if row:
            explicit_hits.append(TextHit(row=row, line=1, text="", score=99))
    if explicit_hits:
        return explicit_hits

    terms = _tokenize(proposition)
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
            if score >= 2 or (score >= 1 and any(term in {"incident", "photograph", "wage", "transcript", "maintenance"} for term in terms)):
                hits.append(TextHit(row=row, line=lineno, text=line.strip()[:300], score=score))
    hits.sort(key=lambda h: (h.score, 1 if h.row.get("bates_prefix") else 0), reverse=True)
    return hits[:5]


def audit_proposition(root: Path, rows: list[dict[str, Any]], proposition: dict[str, Any]) -> dict[str, Any]:
    text = proposition["text"]
    kind = proposition["kind"]
    hits = search_record(root, rows, text)
    lower = text.lower()
    cites = [_cite_for_hit(hit.row, hit.line, hit.text) for hit in hits[:3]]

    if kind == "other_record_bound" and ("object" in lower or "privilege" in lower or "work product" in lower):
        return _audit_row(proposition, "needs_attorney_decision", [], [], "Objection/privilege strategy requires attorney review.")

    if kind == "no_documents_assertion":
        if hits:
            return _audit_row(proposition, "conflicts_with_record", [], cites, "Indexed record contains potential responsive material.")
        return _audit_row(proposition, "unsupported", [], [], "No indexed source can prove the absence of responsive documents.")

    if hits:
        note = "Indexed record contains support for this proposition."
        if any(str(hit.row.get("relpath", "")).startswith("01_transcripts/") for hit in hits):
            note = "Indexed testimony contains support for this proposition."
        return _audit_row(proposition, "supported", cites, [], note)

    if "testimony" in lower or "deposition" in lower or "transcript" in lower:
        transcript_rows = [r for r in rows if str(r.get("relpath", "")).startswith("01_transcripts/")]
        status = "unsupported" if transcript_rows else "ambiguous"
        note = "No matching transcript support found." if transcript_rows else "No transcript text is indexed for this matter."
        return _audit_row(proposition, status, [], [], note)

    return _audit_row(proposition, "unsupported", [], [], "No adequate support found in the indexed matter record.")


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
        "status": status,
        "record_cites": record_cites,
        "conflict_cites": conflict_cites,
        "notes": notes,
        "attorney_review_required": status != "supported",
        "request_type": "rfp",
        "mode": "audit_incoming_response",
        "kind": proposition.get("kind"),
    }
    return rar.attach_rule_ids(row, request_type="rfp")


def cmd_audit_existing(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    status = cg.main(["status", str(root)])
    if status != 0:
        print("ERROR: casegraph status is not green; rebuild before audit", file=sys.stderr)
        return 1
    rows = evidence_rows(cg.load_documents(root))
    propositions = read_jsonl(root / PROPOSITIONS_REL)
    audit_rows = [audit_proposition(root, rows, prop) for prop in propositions]
    write_jsonl(output_path(root, AUDIT_ITEMS_REL), audit_rows)
    refresh_casegraph_index(root)
    print(f"audited {len(audit_rows)} propositions -> {root / AUDIT_ITEMS_REL}")
    return 0


def _format_cite(cite: dict[str, Any]) -> str:
    ctype = cite.get("type")
    value = str(cite.get("value") or "")
    if ctype == "transcript":
        return f"{value} {cite.get('page')}:{cite.get('line_start')}-{cite.get('line_end')}"
    if ctype == "bates":
        return value
    return f"{ctype}:{value}"


def _report_excerpt(root: Path, item_id: str, requests: dict[str, Any]) -> str:
    for item in requests.get("items", []):
        if item.get("item_id") == item_id:
            return str(item.get("text") or "")
    return ""


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(1 for row in rows if row.get("status") == status) for status in sorted(STATUS_VALUES)}


def _display_item_id(item_id: str) -> str:
    match = re.fullmatch(r"RFP-(\d{3})", item_id)
    if match:
        return f"Request {int(match.group(1))}"
    return item_id


def _display_proposition_id(proposition_id: str) -> str:
    match = re.fullmatch(r"RFP-(\d{3})-P(\d{2})", proposition_id)
    if match:
        return f"Request {int(match.group(1))}, proposition {int(match.group(2))}"
    return proposition_id


def build_audit_report(root: Path, requests: dict[str, Any], propositions: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> str:
    matter_id = _matter_id(root)
    proposed = root / DEFAULT_PROPOSED_SOURCE
    proposed_sha = sha256_file(proposed) if proposed.is_file() else "unknown"
    counts = _status_counts(audit_rows)
    by_item: dict[str, list[dict[str, Any]]] = {}
    prop_by_id = {p["proposition_id"]: p for p in propositions}
    for row in audit_rows:
        by_item.setdefault(row["item_id"], []).append(row)

    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Discovery Response Audit - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Proposed source sha256:** {proposed_sha}",
        "**Casegraph status:** fresh",
        "**Single-matter invocation:** confirmed",
        "",
        "> Draft for attorney review.",
        "> Not a certification that responses are ready to serve.",
        "> No cross-client facts. No final legal conclusions.",
        "",
        "## Coverage summary",
        "",
        "| Status | Count |",
        "|--------|------:|",
    ]
    for status in ["supported", "partially_supported", "ambiguous", "unsupported", "conflicts_with_record", "needs_attorney_decision"]:
        lines.append(f"| {status} | {counts.get(status, 0)} |")
    lines.extend(["", "## By request", ""])

    for item_id in sorted(by_item):
        lines.extend([f"### {_display_item_id(item_id)}", "", f"**Request (served):** {_report_excerpt(root, item_id, requests)}", ""])
        lines.extend(["| Proposition | Status | Record cites | Notes |", "|-------------|--------|--------------|-------|"])
        for row in by_item[item_id]:
            prop = prop_by_id.get(row["proposition_id"], {})
            cite_text = ", ".join(_format_cite(c) for c in (row.get("record_cites") or row.get("conflict_cites") or [])) or "-"
            note = str(row.get("notes") or "").replace("|", "\\|")
            lines.append(f"| {_display_proposition_id(row['proposition_id'])} | {row['status']} | {cite_text} | {note} |")
            lines.append(f"<!-- proposition: {prop.get('text', row.get('proposition_text', ''))} -->")
        lines.append("")

    flagged = [r for r in audit_rows if r["status"] in {"unsupported", "conflicts_with_record", "needs_attorney_decision", "ambiguous"}]
    lines.extend(["## Conflicts and unsupported (roll-up)", ""])
    if flagged:
        for row in flagged:
            lines.append(f"- {_display_proposition_id(row['proposition_id'])}: {row['status']} - {row['notes']}")
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Attorney checklist",
        "",
        "- [ ] Every conflicts_with_record / unsupported item reviewed",
        "- [ ] Testimony cites checked at page:line against transcript extract",
        "- [ ] No other client's identifiers appear in this report",
        "- [ ] Gate commands in SPEC section 11.3 exit 0",
        "",
    ])
    return "\n".join(lines)


def cmd_package_audit(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = load_requests(root)
    propositions = read_jsonl(root / PROPOSITIONS_REL)
    audit_rows = read_jsonl(root / AUDIT_ITEMS_REL)
    errors = validate_audit_records(requests, propositions, audit_rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report = build_audit_report(root, requests, propositions, audit_rows)
    path = output_path(root, AUDIT_REPORT_REL)
    path.write_text(report, encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote audit report -> {path}")
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


def validate_audit_records(
    requests: dict[str, Any],
    propositions: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    valid_items = {item["item_id"] for item in requests.get("items", [])}
    prop_ids = [p.get("proposition_id") for p in propositions]
    if len(set(prop_ids)) != len(prop_ids):
        errors.append("duplicate proposition IDs")
    prop_set = set(prop_ids)
    audit_ids = [r.get("proposition_id") for r in audit_rows]
    if set(audit_ids) != prop_set or len(audit_ids) != len(prop_ids):
        errors.append("audit rows must match propositions exactly once")
    for prop in propositions:
        if prop.get("item_id") not in valid_items:
            errors.append(f"{prop.get('proposition_id')}: unknown item_id {prop.get('item_id')}")
    for row in audit_rows:
        pid = row.get("proposition_id")
        status = row.get("status")
        if status not in STATUS_VALUES:
            errors.append(f"{pid}: invalid status {status}")
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
        if status in {"unsupported", "ambiguous", "needs_attorney_decision"} and not str(row.get("notes") or "").strip():
            errors.append(f"{pid}: {status} requires notes")
    return errors


def run_command(command: list[str]) -> int:
    completed = subprocess.run(command, text=True, check=False)
    return completed.returncode


def cmd_validate_audit(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = load_requests(root)
    propositions = read_jsonl(root / PROPOSITIONS_REL)
    audit_rows = read_jsonl(root / AUDIT_ITEMS_REL)
    errors = validate_audit_records(requests, propositions, audit_rows)
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
    if not args.skip_live_preflight:
        # Live readiness enforces the OCR queue. Synthetic smoke (`.synthetic`
        # marker or --synthetic) may skip OCR; that path is not live-ready.
        synthetic = bool(args.synthetic) or (root / ".synthetic").is_file()
        preflight = [
            sys.executable,
            str(LIVE_PREFLIGHT_SCRIPT),
            "--matter-dir",
            str(root),
            "--output",
            str(report),
        ]
        if synthetic:
            preflight.append("--skip-ocr-queue")
        gates.append(preflight)
    for command in gates:
        code = run_command(command)
        if code != 0:
            print(f"FAIL: gate exited {code}: {' '.join(command)}")
            return 1
    print("PASS: audit validation")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="discovery-response-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_matter(a, "SYN-A", "THORN-PROD")
        _create_synthetic_matter(b, "SYN-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-rfp", str(matter)],
                ["parse-proposed", str(matter)],
                ["audit-existing", str(matter)],
                ["package-audit", str(matter)],
                ["validate-audit", str(matter)],
            ):
                code = main(command)
                if code != 0:
                    print(f"selftest failed for {matter.name}: {' '.join(command)}", file=sys.stderr)
                    return code
        print("PASS: discovery-response selftest")
        return 0


def _create_synthetic_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_served").mkdir(parents=True)
    (root / "01_discovery_proposed").mkdir(parents=True)
    (root / "01_transcripts").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text("- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8")
    (root / "01_discovery_served" / "rfp_set.md").write_text(
        "Request for Production No. 1: Produce incident reports for the June 1, 2024 event.\n\n"
        "Request for Production No. 2: Produce photographs of the ladder.\n\n"
        "Request for Production No. 3: Produce testimony supporting wage loss.\n",
        encoding="utf-8",
    )
    (root / "01_discovery_proposed" / "proposed_rfp_responses.md").write_text(
        "Response to Request for Production No. 1: Plaintiff will produce the June 1, 2024 incident report.\n\n"
        "Response to Request for Production No. 2: Plaintiff has no responsive photographs of the ladder.\n\n"
        "Response to Request for Production No. 3: Plaintiff's wage loss is supported by deposition testimony.\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000011\n"
        "**Date:** 2024-06-01\n\n"
        "Incident report for the June 1, 2024 event involving the ladder.\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000020.md").write_text(
        f"**Bates Range:** {prefix}-000020 - {prefix}-000020\n\n"
        "Photograph log lists two ladder photographs from the inspection.\n",
        encoding="utf-8",
    )
    (root / "01_transcripts" / "Depo-Wage.txt").write_text(
        "42:3 The worker testified that wage loss began after the injury.\n",
        encoding="utf-8",
    )
    cg.main(["init", str(root), "--matter-id", matter_id, "--bates-prefix", prefix])
    cg.main(["build", str(root)])
    cg.main(["add-entity", str(root), "--name", "June", "--role", "date-term"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-rfp", help="parse served RFPs into discovery_requests.json")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.add_argument("--propounding-party", default="Defendant")
    p.set_defaults(fn=cmd_parse_rfp)

    p = sub.add_parser("parse-proposed", help="parse proposed final responses into propositions")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_proposed)

    p = sub.add_parser("audit-existing", help="audit proposed propositions against casegraph")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_audit_existing)

    p = sub.add_parser("package-audit", help="write response_audit_report.md")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package_audit)

    p = sub.add_parser("validate-audit", help="run Phase A validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true", help="skip live_preflight.py gate")
    p.add_argument(
        "--synthetic",
        action="store_true",
        help="synthetic smoke path: allow live_preflight --skip-ocr-queue (not live-ready)",
    )
    p.set_defaults(fn=cmd_validate_audit)

    p = sub.add_parser("selftest", help="run offline synthetic Phase A audit")
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
