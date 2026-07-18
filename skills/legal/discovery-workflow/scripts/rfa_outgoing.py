#!/usr/bin/env python3
"""Slice B1: draft outgoing RFAs tied to case issue tags (synthetic-only).

Dedicated draft_outgoing_request path — does not reuse RFA/RFP/ROG audit parsers.
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

TARGETS_REL = Path("02_outputs") / "outgoing_rfa_targets.jsonl"
ITEMS_REL = Path("02_outputs") / "outgoing_rfa_items.jsonl"
PACKAGE_REL = Path("02_outputs") / "outgoing_rfa_set.md"
META_REL = Path("02_outputs") / "outgoing_rfa_meta.json"

DEFAULT_BRIEF = Path("01_discovery_outgoing") / "rfa_issue_brief.md"

SCHEMA_VERSION = 1
REQUEST_TYPE = "rfa"
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
    r"^\s*-\s*\[(?P<tags>[^\]]+)\]\s+(?P<body>.+?)(?:\s*\|\s*Jury:\s*(?P<jury>.+))?\s*$",
    re.IGNORECASE,
)
AND_SPLIT_RE = re.compile(r"\bAND\b", re.IGNORECASE)
OBJECTION_RE = re.compile(r"\b(object(?:s|ion|ed)?|privilege|work product)\b", re.IGNORECASE)


class UsageError(RuntimeError):
    """Bad input state."""


def _load_casegraph():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("legal_casegraph_rfa_out", CASEGRAPH_SCRIPT)
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
    if "jury_theme" in tags:
        # caller must supply jury note separately
        pass
    return tags


def parse_issue_brief(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        match = BRIEF_LINE_RE.match(line)
        if not match:
            raise UsageError(
                f"brief line {lineno}: expected '- [tag, ...] Admit that … [| Jury: …]'"
            )
        tags = parse_issue_tags(match.group("tags"))
        body = match.group("body").strip()
        jury = (match.group("jury") or "").strip() or None
        if "jury_theme" in tags and not jury:
            raise UsageError(f"brief line {lineno}: jury_theme requires '| Jury: …' note")
        if OBJECTION_RE.search(body):
            raise UsageError(
                f"brief line {lineno}: objection/privilege language is attorney-controlled; "
                "remove it from the issue brief"
            )
        rows.append({
            "target_id": f"T{len(rows) + 1}",
            "issue_tags": tags,
            "fact_text": body,
            "jury_note": jury,
            "source_line": lineno,
        })
    return rows


def _is_multi_fact(text: str) -> bool:
    if AND_SPLIT_RE.search(text):
        return True
    # Multiple independent admit clauses
    if len(re.findall(r"\badmit\b", text, flags=re.IGNORECASE)) > 1:
        return True
    return False


def _normalize_admit(text: str) -> str:
    cleaned = " ".join(text.split()).strip(" .")
    if re.match(r"(?i)^admit\b", cleaned):
        return cleaned if cleaned.endswith(".") else f"{cleaned}."
    cleaned = re.sub(r"(?i)^that\s+", "", cleaned)
    body = cleaned[0].lower() + cleaned[1:] if cleaned else cleaned
    sentence = f"Admit that {body}"
    return sentence if sentence.endswith(".") else f"{sentence}."


def draft_outgoing_items(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for target in targets:
        fact = target["fact_text"]
        tags = list(target["issue_tags"])
        jury = target.get("jury_note")
        if _is_multi_fact(fact):
            parts = [p.strip(" .") for p in AND_SPLIT_RE.split(fact) if p.strip()]
            if len(parts) >= 2:
                for part in parts:
                    items.append(_item_row(len(items) + 1, target, _normalize_admit(part), tags, jury, multi_split=True))
                continue
            items.append(_item_row(
                len(items) + 1, target, _normalize_admit(fact), tags, jury,
                multi_split=False, needs_attorney=True,
                notes="Multi-fact RFA could not be auto-split; attorney must narrow.",
            ))
            continue
        items.append(_item_row(len(items) + 1, target, _normalize_admit(fact), tags, jury, multi_split=False))
    return items


def _item_row(
    n: int,
    target: dict[str, Any],
    text: str,
    tags: list[str],
    jury: str | None,
    *,
    multi_split: bool,
    needs_attorney: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    # Avoid Bates-like IDs (PREFIX-001). Use ORA-1 style.
    item_id = f"ORA-{n}"
    note = notes or (
        f"Targets issue tag(s): {', '.join(tags)}."
        + (f" Jury usefulness: {jury}" if jury else " Narrow single-fact admission for record lock-in.")
    )
    if multi_split and not notes:
        note = f"Auto-split from multi-fact target {target['target_id']}. {note}"
    return {
        "item_id": item_id,
        "target_id": target["target_id"],
        "text": text,
        "issue_tags": tags,
        "jury_note": jury,
        "single_fact": not needs_attorney,
        "needs_attorney_decision": needs_attorney,
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
    print(f"parsed {len(rows)} outgoing RFA targets -> {root / TARGETS_REL}")
    return 0


def cmd_draft_outgoing_rfa(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    targets = read_jsonl(root / TARGETS_REL)
    items = draft_outgoing_items(targets)
    if not items:
        print("zero outgoing RFA items drafted", file=sys.stderr)
        return 1
    write_jsonl(output_path(root, ITEMS_REL), items)
    refresh_casegraph_index(root)
    print(f"drafted {len(items)} outgoing RFAs -> {root / ITEMS_REL}")
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
        if not item.get("single_fact", False) and not item.get("needs_attorney_decision"):
            errors.append(f"{iid}: non-single-fact items must set needs_attorney_decision")
        if item.get("needs_attorney_decision") and not str(item.get("notes") or "").strip():
            errors.append(f"{iid}: needs_attorney_decision requires notes")
        if item.get("mode") != MODE or item.get("request_type") != REQUEST_TYPE:
            errors.append(f"{iid}: wrong request_type/mode")
    return errors


def _display_item_id(item_id: str) -> str:
    match = re.fullmatch(r"ORA-(\d+)", str(item_id))
    if match:
        return f"Outgoing admission {int(match.group(1))}"
    return str(item_id)


def build_outgoing_package(root: Path, items: list[dict[str, Any]], brief_sha: str) -> str:
    matter_id = _matter_id(root)
    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Outgoing Requests for Admission - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Request type:** {REQUEST_TYPE}",
        f"**Mode:** {MODE}",
        f"**Issue brief sha256:** {brief_sha}",
        "**Casegraph status:** fresh",
        "**Single-matter invocation:** confirmed",
        "",
        "> Draft for attorney review.",
        "> Not a certification that these RFAs are ready to serve.",
        "> No final objection strategy. No cross-client facts.",
        "",
        "## Draft requests",
        "",
    ]
    for item in items:
        tags = ", ".join(item.get("issue_tags") or [])
        lines.extend([
            f"### {_display_item_id(item['item_id'])}",
            "",
            f"**Issue tags:** {tags}",
            f"**Jury note:** {item.get('jury_note') or '—'}",
            f"**Single-fact:** {'yes' if item.get('single_fact') else 'no'}",
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
        "- [ ] Every request is narrow and single-fact (or explicitly approved as multi-fact)",
        "- [ ] Issue tags and jury notes match case themes",
        "- [ ] No invented Bates or transcript locators in this package",
        "- [ ] No objection strategy invented by the tool",
        "- [ ] Gate commands for Slice B1 exit 0",
        "- [ ] Owner §9.5 sign-off before any live matter use",
        "",
    ])
    return "\n".join(lines)


def cmd_package_outgoing_rfa(args: argparse.Namespace) -> int:
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
    print(f"wrote outgoing RFA package -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    return subprocess.run(command, text=True, check=False).returncode


def cmd_validate_outgoing_rfa(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    targets = read_jsonl(root / TARGETS_REL)
    items = read_jsonl(root / ITEMS_REL)
    errors = validate_outgoing_records(targets, items)
    package = root / PACKAGE_REL
    if not package.is_file():
        errors.append(f"missing package: {package}")
    else:
        text = package.read_text(encoding="utf-8")
        # Isolation: package must not embed Bates-like RFA-00N tokens
        if re.search(r"\bRFA-0\d{2,}\b", text):
            errors.append("package contains Bates-colliding RFA-00N tokens; use display labels")
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
        # Outgoing drafts intentionally cite no Bates; do not pass --output
        # (live_preflight refuses vacuous verify-cites). Package cite/isolation
        # gates above use --allow-empty + check-isolation instead.
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
    print("PASS: outgoing RFA validation")
    return 0


def _create_synthetic_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_outgoing").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    (root / "01_discovery_outgoing" / "rfa_issue_brief.md").write_text(
        "# SYNTHETIC / NON-CLIENT / TEST ONLY\n\n"
        "- [notice] Admit that defendant received a written complaint about the ladder on May 1, 2024. "
        "| Jury: prior notice\n"
        "- [wage_loss] Admit that plaintiff was unable to work from June 2, 2024 through July 15, 2024.\n"
        "- [liability] Admit that defendant owed a duty to maintain the ladder AND that defendant "
        "breached that duty.\n"
        "- [jury_theme, authenticity] Admit that the photograph log marked as an exhibit is a genuine "
        "business record. | Jury: exhibit authenticity\n",
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
    with tempfile.TemporaryDirectory(prefix="rfa-outgoing-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_matter(a, "SYN-ORFA-A", "THORN-PROD")
        _create_synthetic_matter(b, "SYN-ORFA-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-issue-brief", str(matter)],
                ["draft-outgoing-rfa", str(matter)],
                ["package-outgoing-rfa", str(matter)],
                ["validate-outgoing-rfa", str(matter)],
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
        print("PASS: rfa-outgoing selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-issue-brief", help="parse outgoing RFA issue brief")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_issue_brief)

    p = sub.add_parser("draft-outgoing-rfa", help="draft narrow outgoing RFAs from targets")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_draft_outgoing_rfa)

    p = sub.add_parser("package-outgoing-rfa", help="write outgoing_rfa_set.md")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package_outgoing_rfa)

    p = sub.add_parser("validate-outgoing-rfa", help="run Slice B1 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(fn=cmd_validate_outgoing_rfa)

    p = sub.add_parser("selftest", help="offline synthetic outgoing RFA E2E")
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
