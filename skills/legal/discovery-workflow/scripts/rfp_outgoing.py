#!/usr/bin/env python3
"""Slice B3: draft outgoing RFPs tied to case issue tags (synthetic-only).

Dedicated draft_outgoing_request path — does not reuse RFA/RFP/ROG audit parsers.
Includes production-awareness against the matter casegraph index.
Not serve-ready; attorney review required. Live use needs SPEC §9.5 sign-off.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
LEGAL_ROOT = SCRIPT_PATH.parents[2]
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"

TARGETS_REL = Path("02_outputs") / "outgoing_rfp_targets.jsonl"
ITEMS_REL = Path("02_outputs") / "outgoing_rfp_items.jsonl"
PACKAGE_REL = Path("02_outputs") / "outgoing_rfp_set.md"
META_REL = Path("02_outputs") / "outgoing_rfp_meta.json"

DEFAULT_BRIEF = Path("01_discovery_outgoing") / "rfp_issue_brief.md"

SCHEMA_VERSION = 1
REQUEST_TYPE = "rfp"
MODE = "draft_outgoing_request"

ISSUE_TAGS = {
    "liability",
    "notice",
    "causation",
    "damages",
    "medical",
    "wage_loss",
    "impeachment",
    "authenticity",
    "admissibility",
    "jury_theme",
}

BRIEF_LINE_RE = re.compile(
    r"^\s*-\s*\[(?P<tags>[^\]]+)\]\s+(?P<body>.+?)"
    r"(?:\s*\|\s*Jury:\s*(?P<jury>[^|]+))?"
    r"(?:\s*\|\s*Already:\s*(?P<already>.+))?\s*$",
    re.IGNORECASE,
)
AND_SPLIT_RE = re.compile(r"\bAND\b", re.IGNORECASE)
OBJECTION_RE = re.compile(r"\b(object(?:s|ion|ed)?|privilege|work product)\b", re.IGNORECASE)
ADMIT_RE = re.compile(r"\badmit\b", re.IGNORECASE)
ROG_ONLY_RE = re.compile(
    r"^(state|identify|describe|list|explain|set forth)\b",
    re.IGNORECASE,
)
PRODUCE_STEM_RE = re.compile(
    r"^(produce|provide)\b",
    re.IGNORECASE,
)
PRODUCE_WORD_RE = re.compile(r"\b(produce|production|documents?|records?)\b", re.IGNORECASE)
BATES_RE = re.compile(r"\b([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+)-(\d{4,})\b")
STOPWORDS = {
    "about", "after", "before", "concerning", "during", "documents", "document",
    "produce", "produced", "production", "provide", "records", "record",
    "regarding", "their", "these", "those", "through", "which", "would",
    "could", "shall", "every", "each", "from", "with", "that", "this",
    "written", "copies", "copy", "all", "any", "and", "the", "for",
}


class UsageError(RuntimeError):
    """Bad input state."""


def _load_casegraph():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("legal_casegraph_rfp_out", CASEGRAPH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load casegraph script: {CASEGRAPH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cg = _load_casegraph()


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
    if not (root / ".casegraph" / "manifest.json").is_file():
        return 0
    return cg.main(["build", str(root)])


def _matter_id(root: Path) -> str:
    try:
        return str(cg.load_manifest(root).get("matter_id") or root.name)
    except Exception:
        return root.name


def parse_issue_tags(raw: str) -> list[str]:
    tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
    unknown = [t for t in tags if t not in ISSUE_TAGS]
    if unknown:
        raise UsageError(f"unknown issue tag(s): {', '.join(unknown)}")
    if not tags:
        raise UsageError("each brief line needs at least one issue tag")
    return tags


def _parse_already(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def parse_issue_brief(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        match = BRIEF_LINE_RE.match(line)
        if not match:
            raise UsageError(
                f"brief line {lineno}: expected "
                "'- [tag, ...] Produce … [| Jury: …] [| Already: none|gap|Bates]'"
            )
        tags = parse_issue_tags(match.group("tags"))
        body = match.group("body").strip()
        jury = (match.group("jury") or "").strip() or None
        already = _parse_already(match.group("already"))
        if "jury_theme" in tags and not jury:
            raise UsageError(f"brief line {lineno}: jury_theme requires '| Jury: …' note")
        if OBJECTION_RE.search(body):
            raise UsageError(
                f"brief line {lineno}: objection/privilege language is attorney-controlled; "
                "remove it from the issue brief"
            )
        if ADMIT_RE.search(body):
            raise UsageError(
                f"brief line {lineno}: RFA-style 'Admit' language refused; "
                "use Slice B1 (rfa_outgoing) for admissions"
            )
        if ROG_ONLY_RE.match(body) and not PRODUCE_WORD_RE.search(body):
            raise UsageError(
                f"brief line {lineno}: interrogatory-style language refused; "
                "use Slice B2 (rog_outgoing) for ROGs, or start with Produce/Provide"
            )
        rows.append({
            "target_id": f"T{len(rows) + 1}",
            "issue_tags": tags,
            "fact_text": body,
            "jury_note": jury,
            "already_note": already,
            "source_line": lineno,
        })
    return rows


def _is_multi_topic(text: str) -> bool:
    if AND_SPLIT_RE.search(text):
        return True
    stems = list(PRODUCE_STEM_RE.finditer(text))
    return len(stems) > 1


def _normalize_produce(text: str) -> str:
    cleaned = " ".join(text.split()).strip(" .")
    if PRODUCE_STEM_RE.match(cleaned):
        body = cleaned[0].upper() + cleaned[1:] if cleaned else cleaned
        return body if body.endswith(".") else f"{body}."
    cleaned = re.sub(r"(?i)^(all\s+)?(documents?|records?)\s+(concerning|regarding|about|for)\s+", "", cleaned)
    sentence = f"Produce all documents concerning {cleaned}"
    return sentence if sentence.endswith(".") else f"{sentence}."


def _bates_label(row: dict[str, Any]) -> str | None:
    prefix = row.get("bates_prefix")
    start = row.get("bates_start")
    end = row.get("bates_end")
    if not prefix or start is None:
        return None
    if end is None or end == start:
        return f"{prefix}-{int(start):06d}"
    return f"{prefix}-{int(start):06d}–{prefix}-{int(end):06d}"


def load_indexed_docs(root: Path) -> list[dict[str, Any]]:
    path = root / ".casegraph" / "documents.jsonl"
    if not path.is_file():
        return []
    docs: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        rel = row.get("relpath") or row.get("path") or ""
        text = ""
        if rel:
            candidate = root / rel
            if candidate.is_file():
                try:
                    text = read_text(candidate)
                except OSError:
                    text = ""
        docs.append({
            "relpath": rel,
            "bates": _bates_label(row),
            "text": text,
            "name": Path(str(rel)).name.lower(),
        })
    return docs


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{5,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def find_production_overlaps(text: str, docs: list[dict[str, Any]]) -> list[str]:
    keys = _keywords(text)
    if not keys:
        return []
    hits: list[str] = []
    for doc in docs:
        hay = f"{doc.get('name', '')} {doc.get('text', '')}".lower()
        score = sum(1 for k in keys if k in hay)
        if score >= 2:
            label = doc.get("bates") or doc.get("relpath") or "indexed document"
            if label not in hits:
                hits.append(str(label))
    return hits[:8]


def _resolve_already(
    already: str | None,
    text: str,
    docs: list[dict[str, Any]],
) -> tuple[str, list[str], bool, str]:
    """Return production_status, overlap labels, needs_attorney, note fragment."""
    if already:
        lowered = already.strip().lower()
        if lowered in {"none", "gap", "unknown"}:
            return "gap_or_none_declared", [], False, f"Attorney marked Already: {already.strip()}."
        bates_hits = [f"{m.group(1)}-{int(m.group(2)):06d}" for m in BATES_RE.finditer(already.upper())]
        if not bates_hits:
            return (
                "attorney_declared",
                [],
                True,
                f"Already note not parseable as Bates or none/gap: {already.strip()}",
            )
        indexed = {d.get("bates") for d in docs if d.get("bates")}
        missing = [b for b in bates_hits if b not in indexed]
        if missing:
            return (
                "declared_missing_from_index",
                bates_hits,
                True,
                f"Already Bates not in this matter index: {', '.join(missing)}.",
            )
        return "already_indexed", bates_hits, False, f"Attorney marked already indexed: {', '.join(bates_hits)}."

    overlaps = find_production_overlaps(text, docs)
    if overlaps:
        return (
            "possible_overlap",
            overlaps,
            True,
            "Possible indexed overlap — attorney must confirm whether to narrow or withdraw.",
        )
    return "no_indexed_overlap", [], False, "No keyword overlap found in this matter's index."


def draft_outgoing_items(
    targets: list[dict[str, Any]],
    docs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    docs = docs or []
    items: list[dict[str, Any]] = []
    for target in targets:
        fact = target["fact_text"]
        tags = list(target["issue_tags"])
        jury = target.get("jury_note")
        already = target.get("already_note")
        if _is_multi_topic(fact):
            parts = [p.strip(" .") for p in AND_SPLIT_RE.split(fact) if p.strip()]
            if len(parts) >= 2:
                for part in parts:
                    items.append(
                        _item_row(
                            len(items) + 1, target, _normalize_produce(part),
                            tags, jury, already, docs, multi_split=True,
                        )
                    )
                continue
            items.append(_item_row(
                len(items) + 1, target, _normalize_produce(fact), tags, jury, already, docs,
                multi_split=False, needs_attorney=True,
                notes="Multi-topic production request could not be auto-split; attorney must narrow.",
            ))
            continue
        items.append(
            _item_row(
                len(items) + 1, target, _normalize_produce(fact),
                tags, jury, already, docs, multi_split=False,
            )
        )
    return items


def _item_row(
    n: int,
    target: dict[str, Any],
    text: str,
    tags: list[str],
    jury: str | None,
    already: str | None,
    docs: list[dict[str, Any]],
    *,
    multi_split: bool,
    needs_attorney: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    # Avoid Bates-like IDs (PREFIX-001). Use ORP-1 style (Outgoing Request for Production).
    item_id = f"ORP-{n}"
    status, overlaps, prod_needs, prod_note = _resolve_already(already, text, docs)
    needs = needs_attorney or prod_needs
    note = notes or (
        f"Targets issue tag(s): {', '.join(tags)}. {prod_note}"
        + (f" Jury usefulness: {jury}" if jury else "")
    )
    if multi_split and not notes:
        note = f"Auto-split from multi-topic target {target['target_id']}. {note}"
    if needs and not notes and "attorney" not in note.lower():
        note = f"{note} Attorney decision required on scope/production overlap."
    return {
        "item_id": item_id,
        "target_id": target["target_id"],
        "text": text,
        "issue_tags": tags,
        "jury_note": jury,
        "already_note": already,
        "production_status": status,
        "production_overlaps": overlaps,
        "single_fact": not needs,
        "needs_attorney_decision": needs,
        "notes": note,
        "request_type": REQUEST_TYPE,
        "mode": MODE,
        "attorney_review_required": True,
    }


def cmd_parse_issue_brief(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_BRIEF)
    if not source.is_file():
        print(f"ERROR: issue brief not found: {source}", file=sys.stderr)
        return 2
    try:
        rows = parse_issue_brief(read_text(source))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print("zero issue targets parsed", file=sys.stderr)
        return 1
    write_jsonl(output_path(root, TARGETS_REL), rows)
    write_json(
        output_path(root, META_REL),
        {
            "schema_version": SCHEMA_VERSION,
            "request_type": REQUEST_TYPE,
            "mode": MODE,
            "source": {
                "relpath": source.relative_to(root).as_posix(),
                "sha256": sha256_file(source),
            },
            "parsed_at": utcnow(),
            "target_count": len(rows),
        },
    )
    refresh_casegraph_index(root)
    print(f"parsed {len(rows)} outgoing RFP targets -> {root / TARGETS_REL}")
    return 0


def cmd_draft_outgoing_rfp(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    targets = read_jsonl(root / TARGETS_REL)
    refresh_casegraph_index(root)
    docs = load_indexed_docs(root)
    items = draft_outgoing_items(targets, docs)
    if not items:
        print("zero outgoing RFP items drafted", file=sys.stderr)
        return 1
    write_jsonl(output_path(root, ITEMS_REL), items)
    refresh_casegraph_index(root)
    print(f"drafted {len(items)} outgoing RFPs -> {root / ITEMS_REL}")
    return 0


def validate_outgoing_records(targets: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    target_ids = {t.get("target_id") for t in targets}
    item_ids = [i.get("item_id") for i in items]
    if len(set(item_ids)) != len(item_ids):
        errors.append("duplicate outgoing item IDs")
    if not items:
        errors.append("no outgoing items")
    for item in items:
        iid = item.get("item_id")
        tags = item.get("issue_tags") or []
        if item.get("target_id") not in target_ids:
            errors.append(f"{iid}: unknown target_id")
        if not tags:
            errors.append(f"{iid}: issue_tags required")
        unknown = [t for t in tags if t not in ISSUE_TAGS]
        if unknown:
            errors.append(f"{iid}: unknown tags {unknown}")
        if "jury_theme" in tags and not str(item.get("jury_note") or "").strip():
            errors.append(f"{iid}: jury_theme requires jury_note")
        text = str(item.get("text") or "")
        if not text.strip():
            errors.append(f"{iid}: empty text")
        if OBJECTION_RE.search(text):
            errors.append(f"{iid}: objection language forbidden in draft voice")
        if ADMIT_RE.search(text):
            errors.append(f"{iid}: RFA-style Admit language forbidden in RFP draft")
        if not item.get("production_status"):
            errors.append(f"{iid}: production_status required")
        if not item.get("single_fact", False) and not item.get("needs_attorney_decision"):
            errors.append(f"{iid}: non-single-topic items must set needs_attorney_decision")
        if item.get("needs_attorney_decision") and not str(item.get("notes") or "").strip():
            errors.append(f"{iid}: needs_attorney_decision requires notes")
        if item.get("mode") != MODE or item.get("request_type") != REQUEST_TYPE:
            errors.append(f"{iid}: wrong request_type/mode")
    return errors


def _display_item_id(item_id: str) -> str:
    match = re.fullmatch(r"ORP-(\d+)", str(item_id))
    if match:
        return f"Outgoing production request {int(match.group(1))}"
    return str(item_id)


def build_outgoing_package(root: Path, items: list[dict[str, Any]], brief_sha: str) -> str:
    matter_id = _matter_id(root)
    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Outgoing Requests for Production - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Request type:** {REQUEST_TYPE}",
        f"**Mode:** {MODE}",
        f"**Issue brief sha256:** {brief_sha}",
        "**Casegraph status:** fresh",
        "**Single-matter invocation:** confirmed",
        "",
        "> Draft for attorney review.",
        "> Not a certification that these production requests are ready to serve.",
        "> No final objection strategy. No cross-client facts.",
        "> Production-awareness notes are heuristics against this matter index only.",
        "",
        "## Draft requests",
        "",
    ]
    for item in items:
        tags = ", ".join(item.get("issue_tags") or [])
        overlaps = item.get("production_overlaps") or []
        overlap_txt = ", ".join(overlaps) if overlaps else "—"
        lines.extend([
            f"### {_display_item_id(item['item_id'])}",
            "",
            f"**Issue tags:** {tags}",
            f"**Jury note:** {item.get('jury_note') or '—'}",
            f"**Production status:** {item.get('production_status') or '—'}",
            f"**Indexed overlaps (this matter only):** {overlap_txt}",
            f"**Single-topic:** {'yes' if item.get('single_fact') else 'no'}",
            f"**Attorney decision:** {'required' if item.get('needs_attorney_decision') else 'review still required before serve'}",
            "",
            str(item.get("text") or ""),
            "",
            f"_Notes:_ {item.get('notes') or '—'}",
            "",
        ])

    flagged = [i for i in items if i.get("needs_attorney_decision")]
    lines.extend(["## Open attorney items", ""])
    if flagged:
        for item in flagged:
            lines.append(f"- {_display_item_id(item['item_id'])}: {item.get('notes')}")
    else:
        lines.append("- None marked needs_attorney_decision (full attorney serve review still required).")

    lines.extend([
        "",
        "## Attorney checklist",
        "",
        "- [ ] Every production request is narrow and single-topic (or explicitly approved as multi-topic)",
        "- [ ] Production overlaps reviewed (narrow, withdraw, or confirm still needed)",
        "- [ ] Issue tags and jury notes match case themes",
        "- [ ] No invented Bates or transcript locators beyond this matter's index",
        "- [ ] No objection strategy invented by the tool",
        "- [ ] Gate commands for Slice B3 exit 0",
        "- [ ] Owner §9.5 sign-off before any live matter use",
        "",
    ])
    return "\n".join(lines)


def cmd_package_outgoing_rfp(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    targets = read_jsonl(root / TARGETS_REL)
    items = read_jsonl(root / ITEMS_REL)
    errors = validate_outgoing_records(targets, items)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    brief = root / DEFAULT_BRIEF
    brief_sha = sha256_file(brief) if brief.is_file() else "unknown"
    path = output_path(root, PACKAGE_REL)
    path.write_text(build_outgoing_package(root, items, brief_sha), encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote outgoing RFP package -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    return subprocess.run(command, text=True, check=False).returncode


def cmd_validate_outgoing_rfp(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    targets = read_jsonl(root / TARGETS_REL)
    items = read_jsonl(root / ITEMS_REL)
    errors = validate_outgoing_records(targets, items)
    package = root / PACKAGE_REL
    if not package.is_file():
        errors.append(f"missing package: {package}")
    else:
        text = package.read_text(encoding="utf-8")
        # Isolation: package must not embed Bates-colliding RFP-00N request IDs
        if re.search(r"\bRFP-0\d{2,}\b", text):
            errors.append("package contains Bates-colliding RFP-00N tokens; use display labels")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    gates = [
        [sys.executable, str(CASEGRAPH_SCRIPT), "status", str(root)],
        [sys.executable, str(CASEGRAPH_SCRIPT), "verify-cites", str(root), str(package), "--allow-empty"],
        [sys.executable, str(CASEGRAPH_SCRIPT), "check-isolation", str(root), str(package), "--strict"],
    ]
    if not args.skip_live_preflight:
        # Outgoing drafts may mention this-matter Bates only as production notes.
        # Do not pass --output to live_preflight (vacuous/cite coupling).
        synthetic = bool(args.synthetic) or (root / ".synthetic").is_file()
        preflight = [
            sys.executable, str(LIVE_PREFLIGHT_SCRIPT),
            "--matter-dir", str(root),
        ]
        if synthetic:
            preflight.append("--skip-ocr-queue")
        gates.append(preflight)
    for command in gates:
        code = run_command(command)
        if code != 0:
            print(f"FAIL: gate exited {code}: {' '.join(command)}")
            return 1
    print("PASS: outgoing RFP validation")
    return 0


def _create_synthetic_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_outgoing").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    (root / "01_discovery_outgoing" / "rfp_issue_brief.md").write_text(
        "# SYNTHETIC / NON-CLIENT / TEST ONLY\n\n"
        "- [notice] Produce all written complaints about the ladder received on or before "
        "May 1, 2024. | Jury: prior notice\n"
        "- [wage_loss] Produce all payroll records for plaintiff from June 2, 2024 through "
        "July 15, 2024. | Already: none\n"
        "- [liability] Produce all inspection reports for the ladder AND produce all "
        "maintenance policies for ladders.\n"
        "- [jury_theme, authenticity] Produce the photograph log and chain-of-custody "
        "records for that exhibit. | Jury: exhibit authenticity\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000010\n\n"
        "Complaint log notes a written complaint about the ladder on May 1, 2024.\n",
        encoding="utf-8",
    )
    cg.main(["init", str(root), "--matter-id", matter_id, "--bates-prefix", prefix])
    cg.main(["build", str(root)])


def cmd_selftest(_args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="rfp-outgoing-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_matter(a, "SYN-ORFP-A", "THORN-PROD")
        _create_synthetic_matter(b, "SYN-ORFP-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-issue-brief", str(matter)],
                ["draft-outgoing-rfp", str(matter)],
                ["package-outgoing-rfp", str(matter)],
                ["validate-outgoing-rfp", str(matter)],
            ):
                code = main(command)
                if code != 0:
                    print(f"selftest failed for {matter.name}: {' '.join(command)}", file=sys.stderr)
                    return code
        a_pkg = (a / PACKAGE_REL).read_text(encoding="utf-8")
        b_pkg = (b / PACKAGE_REL).read_text(encoding="utf-8")
        if "RIVER-PROD" in a_pkg or "THORN-PROD" in b_pkg:
            print("selftest failed: cross-matter Bates leaked", file=sys.stderr)
            return 1
        a_items = read_jsonl(a / ITEMS_REL)
        if not any(i.get("production_status") == "possible_overlap" for i in a_items):
            print("selftest failed: expected production overlap on complaint/ladder docs", file=sys.stderr)
            return 1
        if not any(i.get("production_status") == "gap_or_none_declared" for i in a_items):
            print("selftest failed: expected Already: none status", file=sys.stderr)
            return 1
        print("PASS: rfp-outgoing selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-issue-brief", help="parse outgoing RFP issue brief")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_issue_brief)

    p = sub.add_parser("draft-outgoing-rfp", help="draft narrow outgoing RFPs from targets")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_draft_outgoing_rfp)

    p = sub.add_parser("package-outgoing-rfp", help="write outgoing_rfp_set.md")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package_outgoing_rfp)

    p = sub.add_parser("validate-outgoing-rfp", help="run Slice B3 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(fn=cmd_validate_outgoing_rfp)

    p = sub.add_parser("selftest", help="offline synthetic outgoing RFP E2E")
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
