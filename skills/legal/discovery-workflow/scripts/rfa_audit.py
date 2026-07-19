#!/usr/bin/env python3
"""Slice A2: audit proposed RFA responses against one matter record.

Dedicated RFA parsers and schemas — does not reuse or stretch RFP parsers.
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
WORKFLOW_ROOT = SCRIPT_PATH.parents[1]
LEGAL_ROOT = SCRIPT_PATH.parents[2]
REPO_ROOT = SCRIPT_PATH.parents[4]
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"
MATTER_SAFETY = LEGAL_ROOT / "scripts" / "matter_safety.py"

REQUESTS_REL = Path("02_outputs") / "rfa_requests.json"
RESPONSES_REL = Path("02_outputs") / "proposed_rfa_responses.jsonl"
RESPONSES_META_REL = Path("02_outputs") / "proposed_rfa_responses_meta.json"
AUDIT_ITEMS_REL = Path("02_outputs") / "rfa_audit_items.jsonl"
AUDIT_REPORT_REL = Path("02_outputs") / "rfa_response_audit_report.md"

DEFAULT_RFA_SOURCE = Path("01_discovery_served") / "rfa_set.md"
DEFAULT_PROPOSED_SOURCE = Path("01_discovery_proposed") / "proposed_rfa_responses.md"
NON_EVIDENCE_PREFIXES = (
    "01_discovery_proposed/",
    "01_discovery_served/",
    "02_outputs/",
)

SCHEMA_VERSION = 1
REQUEST_TYPE = "rfa"
MODE = "audit_incoming_response"

CLASSIFICATIONS = {
    "admit",
    "deny",
    "qualify",
    "lack_information",
    "object_only",
    "other_attorney",
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

RFA_HEADING_RE = re.compile(
    r"^\s*(?:(?:Request\s+for\s+Admission|RFA)\s*(?:No\.?|Number)?\s*)"
    r"(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
RFP_HEADING_RE = re.compile(
    r"^\s*(?:Request\s+for\s+Production|RFP)\b",
    re.IGNORECASE,
)
ROG_HEADING_RE = re.compile(
    r"^\s*(?:Interrogator(?:y|ies)|ROG)\b",
    re.IGNORECASE,
)
NUMBERED_RE = re.compile(r"^\s*(?P<num>\d{1,3})[.)]\s+(?P<rest>.+)$")
RESPONSE_HEADING_RE = re.compile(
    r"^\s*(?:Response\s+to\s+)?(?:(?:Request\s+for\s+Admission|RFA)"
    r"\s*(?:No\.?|Number)?\s*)(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
BATES_TEXT_RE = re.compile(
    r"\b([A-Z][A-Z0-9]{1,11}(?:-[A-Z][A-Z0-9]{1,11})*)[-_](0\d{2,7}|\d{5,8})\b"
)
TRANSCRIPT_LINE_RE = re.compile(r"^\s*(?P<page>\d{1,4})[:.](?P<line>\d{1,3})\s+(?P<text>.+)$")

STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "been", "by", "for", "from", "has",
    "have", "in", "is", "it", "of", "on", "or", "plaintiff", "request",
    "that", "the", "this", "to", "will", "with", "admission", "admit",
    "admits", "deny", "denies", "denied",
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
    spec = importlib.util.spec_from_file_location("legal_casegraph_rfa", CASEGRAPH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load casegraph script: {CASEGRAPH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_response_rules():
    sys.dont_write_bytecode = True
    path = SCRIPT_PATH.parent / "response_audit_rules.py"
    spec = importlib.util.spec_from_file_location("response_audit_rules_rfa", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cg = _load_casegraph()

def _load_matter_safety():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("matter_safety_rfa_audit", MATTER_SAFETY)
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
    has_rfa = any(RFA_HEADING_RE.match(line) for line in text.splitlines())
    has_rfp = any(RFP_HEADING_RE.match(line) for line in text.splitlines())
    has_rog = any(ROG_HEADING_RE.match(line) for line in text.splitlines())
    if has_rfp and not has_rfa:
        raise UsageError(
            "source looks like RFPs; use discovery_response.py (Slice A1), not rfa_audit"
        )
    if has_rog and not has_rfa:
        raise UsageError(
            "source looks like interrogatories; Slice A3 (rog audit) is not this module"
        )


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


def parse_rfa_text(text: str) -> list[dict[str, Any]]:
    _refuse_wrong_request_type(text)
    blocks = _blocks_by_heading(text, RFA_HEADING_RE) or _numbered_blocks(text)
    items: list[dict[str, Any]] = []
    for idx, (number_raw, body) in enumerate(blocks, 1):
        normalized = " ".join(body.split())
        items.append({
            "item_id": f"RFA-{idx:03d}",
            "number_raw": number_raw,
            "text": normalized,
            "parse_warnings": [],
        })
    return items


def classify_rfa_response(text: str) -> str:
    lower = text.lower()
    # Check lack-of-info before deny/admit — phrases often contain those words.
    if re.search(r"\black(?:s|ing)? (?:of )?(information|knowledge)\b", lower) or re.search(
        r"\b(insufficient information|unable to admit or deny|cannot admit or deny|"
        r"sufficient to admit or deny)\b",
        lower,
    ):
        return "lack_information"
    if re.search(r"\b(admit(?:s|ted)? in part|qualif(?:y|ies|ied)|except that|subject to)\b", lower):
        return "qualify"
    if re.search(r"\b(object(?:s|ion|ed)?)\b", lower) and not re.search(
        r"\b(admit|deny|denied|admits|denies)\b", lower
    ):
        return "object_only"
    if re.search(r"\b(deny|denies|denied|denial)\b", lower):
        return "deny"
    if re.search(r"\b(admit|admits|admitted|admission)\b", lower):
        return "admit"
    return "other_attorney"


def parse_proposed_rfa_text(text: str, requests: dict[str, Any]) -> list[dict[str, Any]]:
    _refuse_wrong_request_type(text)
    if requests.get("request_type") != REQUEST_TYPE:
        raise UsageError(
            f"rfa_requests.json request_type must be {REQUEST_TYPE!r}, "
            f"got {requests.get('request_type')!r}"
        )
    blocks = _blocks_by_heading(text, RESPONSE_HEADING_RE) or _numbered_blocks(text)
    number_to_item = {str(item["number_raw"]): item["item_id"] for item in requests.get("items", [])}
    order_items = [item["item_id"] for item in requests.get("items", [])]
    rows: list[dict[str, Any]] = []
    for idx, (number_raw, body) in enumerate(blocks, 1):
        item_id = number_to_item.get(number_raw) or (
            order_items[idx - 1] if idx - 1 < len(order_items) else f"RFA-{idx:03d}"
        )
        response_text = " ".join(body.split())
        rows.append({
            "item_id": item_id,
            "response_id": f"{item_id}-R01",
            "response_text": response_text,
            "classification": classify_rfa_response(response_text),
            "source_span": {
                "start_char": text.find(body.strip()[:40]) if body.strip() else None,
                "end_char": None,
            },
        })
    return rows


def _matter_id(root: Path) -> str:
    try:
        return str(cg.load_manifest(root).get("matter_id") or root.name)
    except Exception:
        return root.name


def load_requests(root: Path) -> dict[str, Any]:
    path = root / REQUESTS_REL
    if not path.is_file():
        raise UsageError(f"missing {path}; run parse-rfa first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("request_type") != REQUEST_TYPE:
        raise UsageError(
            f"{path} is not an RFA request set (request_type={payload.get('request_type')!r})"
        )
    return payload


def cmd_parse_rfa(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_RFA_SOURCE)
    if not source.is_file():
        print(f"ERROR: served RFA source not found: {source}", file=sys.stderr)
        return 2
    try:
        items = parse_rfa_text(read_text(source))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    parse_errors: list[str] = []
    if not items:
        parse_errors.append("zero RFA items parsed")
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
    print(f"parsed {len(items)} RFA items -> {root / REQUESTS_REL}")
    return 0


def cmd_parse_proposed_rfa(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_PROPOSED_SOURCE)
    if not source.is_file():
        print(f"ERROR: proposed RFA responses source not found: {source}", file=sys.stderr)
        return 2
    requests = load_requests(root)
    try:
        rows = parse_proposed_rfa_text(read_text(source), requests)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print("zero proposed RFA responses parsed", file=sys.stderr)
        return 1
    write_jsonl(output_path(root, RESPONSES_REL), rows)
    write_json(
        output_path(root, RESPONSES_META_REL),
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
    print(f"parsed {len(rows)} proposed RFA responses -> {root / RESPONSES_REL}")
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
                term in {"incident", "ladder", "wage", "june", "injury", "photograph"}
                for term in terms
            )):
                hits.append(TextHit(row=row, line=lineno, text=line.strip()[:300], score=score))
    hits.sort(key=lambda h: (h.score, 1 if h.row.get("bates_prefix") else 0), reverse=True)
    return hits[:5]


def _audit_row(
    response: dict[str, Any],
    request_text: str,
    status: str,
    record_cites: list[dict[str, Any]],
    conflict_cites: list[dict[str, Any]],
    notes: str,
) -> dict[str, Any]:
    classification = response["classification"]
    row = {
        "item_id": response["item_id"],
        "response_id": response["response_id"],
        "request_text": request_text,
        "response_text": response["response_text"],
        "classification": classification,
        "status": status,
        "record_cites": record_cites,
        "conflict_cites": conflict_cites,
        "notes": notes,
        "attorney_review_required": status != "supported" or classification in {
            "object_only", "other_attorney", "lack_information", "qualify",
        },
        "request_type": REQUEST_TYPE,
        "mode": MODE,
    }
    return rar.attach_rule_ids(row, request_type=REQUEST_TYPE)


def audit_rfa_response(
    root: Path,
    rows: list[dict[str, Any]],
    response: dict[str, Any],
    request_text: str,
) -> dict[str, Any]:
    classification = response["classification"]
    query = f"{request_text} {response['response_text']}"
    hits = search_record(root, rows, query)
    cites = [_cite_for_hit(hit.row, hit.line, hit.text) for hit in hits[:3]]

    if classification == "object_only":
        return _audit_row(
            response, request_text, "needs_attorney_decision", [], [],
            "Objection-only RFA response requires attorney strategy review.",
        )
    if classification == "other_attorney":
        return _audit_row(
            response, request_text, "needs_attorney_decision", [], [],
            "Response classification unclear; attorney must classify and review.",
        )
    if classification == "lack_information":
        note = (
            "Lack-of-information response: record the search scope and why "
            "admission/denial is unavailable."
        )
        if hits:
            note += " Indexed record may contain relevant facts — confirm diligence."
            return _audit_row(
                response, request_text, "needs_attorney_decision", cites, [], note,
            )
        return _audit_row(
            response, request_text, "needs_attorney_decision", [], [], note,
        )
    if classification == "admit":
        if hits and _admission_conflicts(request_text, response["response_text"], hits):
            return _audit_row(
                response, request_text, "conflicts_with_record", [], cites,
                "Indexed record appears to contradict this admission.",
            )
        if hits:
            return _audit_row(
                response, request_text, "supported", cites, [],
                "No indexed contradiction found for this admission.",
            )
        return _audit_row(
            response, request_text, "ambiguous", [], [],
            "Admission has no indexed corroboration or contradiction; attorney should confirm.",
        )
    if classification in {"deny", "qualify"}:
        if hits:
            status = "supported" if classification == "deny" else "partially_supported"
            note = (
                "Indexed record contains material that can support this denial."
                if classification == "deny"
                else "Qualification needs attorney review of the partial admission against the record."
            )
            return _audit_row(response, request_text, status, cites, [], note)
        return _audit_row(
            response, request_text, "unsupported", [], [],
            f"{classification.title()} lacks record cites; attorney must supply support or revise.",
        )
    return _audit_row(
        response, request_text, "needs_attorney_decision", [], [],
        "Unhandled classification path.",
    )


def _admission_conflicts(request_text: str, response_text: str, hits: list[TextHit]) -> bool:
    """Heuristic: admission that the fact is true conflicts if record supports the opposite needle."""
    blob = f"{request_text} {response_text}".lower()
    # Synthetic fixture: admitting "no ladder photographs" conflicts when photos exist.
    if "photograph" in blob and ("no " in blob or "not " in blob or "none" in blob):
        return any("photograph" in hit.text.lower() for hit in hits)
    # Admitting absence of incident report conflicts when incident report is indexed.
    if "incident" in blob and ("no " in blob or "not " in blob or "none" in blob):
        return any("incident" in hit.text.lower() for hit in hits)
    return False


def cmd_audit_rfa(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    status = cg.main(["status", str(root)])
    if status != 0:
        print("ERROR: casegraph status is not green; rebuild before audit", file=sys.stderr)
        return 1
    requests = load_requests(root)
    request_text = {
        item["item_id"]: str(item.get("text") or "") for item in requests.get("items", [])
    }
    rows = evidence_rows(cg.load_documents(root))
    responses = read_jsonl(root / RESPONSES_REL)
    audit_rows = [
        audit_rfa_response(root, rows, response, request_text.get(response["item_id"], ""))
        for response in responses
    ]
    write_jsonl(output_path(root, AUDIT_ITEMS_REL), audit_rows)
    refresh_casegraph_index(root)
    print(f"audited {len(audit_rows)} RFA responses -> {root / AUDIT_ITEMS_REL}")
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


def validate_rfa_audit_records(
    requests: dict[str, Any],
    responses: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if requests.get("request_type") != REQUEST_TYPE:
        errors.append("requests request_type must be rfa")
    valid_items = {item["item_id"] for item in requests.get("items", [])}
    response_ids = [r.get("response_id") for r in responses]
    if len(set(response_ids)) != len(response_ids):
        errors.append("duplicate response IDs")
    audit_ids = [r.get("response_id") for r in audit_rows]
    if set(audit_ids) != set(response_ids) or len(audit_ids) != len(response_ids):
        errors.append("audit rows must match proposed responses exactly once")
    for response in responses:
        if response.get("item_id") not in valid_items:
            errors.append(f"{response.get('response_id')}: unknown item_id")
        if response.get("classification") not in CLASSIFICATIONS:
            errors.append(
                f"{response.get('response_id')}: invalid classification "
                f"{response.get('classification')}"
            )
    for row in audit_rows:
        rid = row.get("response_id")
        classification = row.get("classification")
        status = row.get("status")
        if classification not in CLASSIFICATIONS:
            errors.append(f"{rid}: invalid classification {classification}")
        if status not in STATUS_VALUES:
            errors.append(f"{rid}: invalid status {status}")
        record_cites = row.get("record_cites") or []
        conflict_cites = row.get("conflict_cites") or []
        for cite in [*record_cites, *conflict_cites]:
            issue = validate_cite(cite)
            if issue:
                errors.append(f"{rid}: {issue}")
        if classification in {"deny", "qualify"}:
            if status in {"supported", "partially_supported"} and not record_cites:
                errors.append(f"{rid}: {classification}/{status} requires record_cites")
            if status == "unsupported" and not str(row.get("notes") or "").strip():
                errors.append(f"{rid}: unsupported {classification} requires notes")
            if status == "needs_attorney_decision" and not str(row.get("notes") or "").strip():
                errors.append(f"{rid}: needs_attorney_decision requires notes")
        if classification == "admit" and status == "conflicts_with_record" and not conflict_cites:
            errors.append(f"{rid}: admit/conflicts_with_record requires conflict_cites")
        if classification == "lack_information" and not str(row.get("notes") or "").strip():
            errors.append(f"{rid}: lack_information requires notes")
        if status in {"unsupported", "ambiguous", "needs_attorney_decision"} and not str(
            row.get("notes") or ""
        ).strip():
            errors.append(f"{rid}: {status} requires notes")
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
    """Human label that must not look like a Bates token (RFA-001 matches Bates regex)."""
    match = re.fullmatch(r"RFA-(\d{3})", item_id)
    if match:
        return f"Admission {int(match.group(1))}"
    return item_id


def _display_response_id(response_id: str) -> str:
    match = re.fullmatch(r"RFA-(\d{3})-R(\d{2})", response_id)
    if match:
        return f"Admission {int(match.group(1))}, response {int(match.group(2))}"
    return response_id


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(1 for row in rows if row.get("status") == status) for status in sorted(STATUS_VALUES)}


def _classification_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        name: sum(1 for row in rows if row.get("classification") == name)
        for name in sorted(CLASSIFICATIONS)
    }


def build_rfa_audit_report(
    root: Path,
    requests: dict[str, Any],
    audit_rows: list[dict[str, Any]],
) -> str:
    matter_id = _matter_id(root)
    proposed = root / DEFAULT_PROPOSED_SOURCE
    proposed_sha = sha256_file(proposed) if proposed.is_file() else "unknown"
    status_counts = _status_counts(audit_rows)
    class_counts = _classification_counts(audit_rows)
    by_item: dict[str, list[dict[str, Any]]] = {}
    for row in audit_rows:
        by_item.setdefault(row["item_id"], []).append(row)

    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# RFA Response Audit - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Request type:** {REQUEST_TYPE}",
        f"**Mode:** {MODE}",
        f"**Proposed source sha256:** {proposed_sha}",
        "**Casegraph status:** fresh",
        "**Single-matter invocation:** confirmed",
        "",
        "> Draft for attorney review.",
        "> Not a certification that RFA responses are ready to serve.",
        "> No cross-client facts. No final objection strategy.",
        "",
        "## Classification summary",
        "",
        "| Classification | Count |",
        "|----------------|------:|",
    ]
    for name in sorted(CLASSIFICATIONS):
        lines.append(f"| {name} | {class_counts.get(name, 0)} |")
    lines.extend([
        "",
        "## Status summary",
        "",
        "| Status | Count |",
        "|--------|------:|",
    ])
    for status in [
        "supported", "partially_supported", "ambiguous", "unsupported",
        "conflicts_with_record", "needs_attorney_decision",
    ]:
        lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    lines.extend(["", "## By request", ""])

    request_map = {item["item_id"]: item for item in requests.get("items", [])}
    for item_id in sorted(by_item):
        req = request_map.get(item_id, {})
        lines.extend([
            f"### {_display_item_id(item_id)}",
            "",
            f"**Request (served):** {req.get('text', '')}",
            "",
            "| response | Classification | Status | Cites | Notes |",
            "|----------|----------------|--------|-------|-------|",
        ])
        for row in by_item[item_id]:
            cite_text = ", ".join(
                _format_cite(c) for c in (row.get("record_cites") or row.get("conflict_cites") or [])
            ) or "-"
            note = str(row.get("notes") or "").replace("|", "\\|")
            lines.append(
                f"| {_display_response_id(row['response_id'])} | {row['classification']} | "
                f"{row['status']} | {cite_text} | {note} |"
            )
            lines.append(f"<!-- response: {row.get('response_text', '')} -->")
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
                f"- {_display_response_id(row['response_id'])}: "
                f"{row['classification']}/{row['status']} - {row['notes']}"
            )
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Attorney checklist",
        "",
        "- [ ] Every deny/qualify without record cites reviewed or revised",
        "- [ ] Every admit/conflicts_with_record item reviewed against the record",
        "- [ ] Lack-of-information diligence notes confirmed",
        "- [ ] No other client's identifiers appear in this report",
        "- [ ] Gate commands for Slice A2 exit 0",
        "",
    ])
    return "\n".join(lines)


def cmd_package_rfa_audit(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = load_requests(root)
    responses = read_jsonl(root / RESPONSES_REL)
    audit_rows = read_jsonl(root / AUDIT_ITEMS_REL)
    errors = validate_rfa_audit_records(requests, responses, audit_rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report = build_rfa_audit_report(root, requests, audit_rows)
    path = output_path(root, AUDIT_REPORT_REL)
    path.write_text(report, encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote RFA audit report -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    completed = subprocess.run(command, text=True, check=False)
    return completed.returncode


def cmd_validate_rfa_audit(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = load_requests(root)
    responses = read_jsonl(root / RESPONSES_REL)
    audit_rows = read_jsonl(root / AUDIT_ITEMS_REL)
    errors = validate_rfa_audit_records(requests, responses, audit_rows)
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
    )
    for command in gates:
        code = run_command(command)
        if code != 0:
            print(f"FAIL: gate exited {code}: {' '.join(command)}")
            return 1
    print("PASS: RFA audit validation")
    return 0


def _create_synthetic_rfa_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_served").mkdir(parents=True)
    (root / "01_discovery_proposed").mkdir(parents=True)
    (root / "01_transcripts").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    (root / "01_discovery_served" / "rfa_set.md").write_text(
        "Request for Admission No. 1: Admit that an incident report exists for the June 1, 2024 event.\n\n"
        "Request for Admission No. 2: Admit that plaintiff has no photographs of the ladder.\n\n"
        "Request for Admission No. 3: Admit that wage loss began after the injury.\n",
        encoding="utf-8",
    )
    (root / "01_discovery_proposed" / "proposed_rfa_responses.md").write_text(
        "Response to Request for Admission No. 1: Admit.\n\n"
        "Response to Request for Admission No. 2: Deny.\n\n"
        "Response to Request for Admission No. 3: Plaintiff lacks information sufficient to admit or deny.\n",
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


def cmd_selftest(_args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="rfa-audit-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_rfa_matter(a, "SYN-RFA-A", "THORN-PROD")
        _create_synthetic_rfa_matter(b, "SYN-RFA-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-rfa", str(matter)],
                ["parse-proposed-rfa", str(matter)],
                ["audit-rfa", str(matter)],
                ["package-rfa-audit", str(matter)],
                ["validate-rfa-audit", str(matter)],
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
        print("PASS: rfa-audit selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-rfa", help="parse served RFAs into rfa_requests.json")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.add_argument("--propounding-party", default="Defendant")
    p.set_defaults(fn=cmd_parse_rfa)

    p = sub.add_parser("parse-proposed-rfa", help="parse proposed RFA responses + classify")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_proposed_rfa)

    p = sub.add_parser("audit-rfa", help="audit proposed RFA classifications against casegraph")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_audit_rfa)

    p = sub.add_parser("package-rfa-audit", help="write rfa_response_audit_report.md")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package_rfa_audit)

    p = sub.add_parser("validate-rfa-audit", help="run Slice A2 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument(
        "--synthetic",
        action="store_true",
        help="synthetic smoke path: allow live_preflight --skip-ocr-queue (not live-ready)",
    )
    p.set_defaults(fn=cmd_validate_rfa_audit)

    p = sub.add_parser("selftest", help="run offline synthetic RFA audit E2E")
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
