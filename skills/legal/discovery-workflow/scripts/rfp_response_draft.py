#!/usr/bin/env python3
"""Slice C1: draft_response for RFPs from an attorney answer brief (synthetic-only).

Does not invent admissions from the record. Objection language is attorney-only.
Live use needs SPEC §9.5 sign-off.
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
WORKFLOW_ROOT = SCRIPT_PATH.parents[1]
LEGAL_ROOT = SCRIPT_PATH.parents[2]
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"
MATTER_SAFETY = LEGAL_ROOT / "scripts" / "matter_safety.py"
LOAD_PACK_SCRIPT = WORKFLOW_ROOT / "jurisdiction" / "load_pack.py"

REQUESTS_REL = Path("02_outputs") / "draft_rfp_requests.jsonl"
BRIEF_REL = Path("02_outputs") / "rfp_answer_brief.jsonl"
ITEMS_REL = Path("02_outputs") / "draft_rfp_response_items.jsonl"
PACKAGE_REL = Path("02_outputs") / "draft_rfp_responses.md"
META_REL = Path("02_outputs") / "draft_rfp_response_meta.json"
DEFAULT_SOURCE = Path("01_discovery_served") / "rfp_set.md"
DEFAULT_BRIEF = Path("01_discovery_proposed") / "rfp_answer_brief.md"
PROFILE_REL = Path("03_attorney") / "matter_profile.yaml"

SCHEMA_VERSION = 1
REQUEST_TYPE = "rfp"
MODE = "draft_response"
CLASSIFICATIONS = {
    "will_produce", "no_documents", "partial", "object_only",
}

RFP_HEADING_RE = re.compile(
    r"^\s*(?:(?:Request\s+for\s+Production|RFP)\s*(?:No\.?|Number)?\s*)"
    r"(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
BRIEF_LINE_RE = re.compile(
    r"^\s*-\s*(?:RFP\s*)?(?P<num>\d+)\s*:\s*(?P<cls>will_produce|no_documents|"
    r"partial|object_only)\s*\|\s*(?P<body>.+)\s*$",
    re.IGNORECASE,
)


class UsageError(RuntimeError):
    """Bad input state."""


def _load_module(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cg = _load_module(CASEGRAPH_SCRIPT, "legal_casegraph_rfp_resp_draft")
_ms = _load_module(MATTER_SAFETY, "matter_safety_rfp_response_draft")
jp = _load_module(LOAD_PACK_SCRIPT, "jurisdiction_load_pack_c1")


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


def load_matter_profile(root: Path) -> dict[str, Any] | None:
    path = root / PROFILE_REL
    if not path.is_file():
        return None
    try:
        import yaml
    except ImportError:
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return None
    pack = str(data.get("jurisdiction_pack") or "").strip()
    if not pack:
        return None
    overlay = data.get("case_overlay")
    return {
        "jurisdiction_pack": pack,
        "case_overlay": str(overlay).strip() if overlay else None,
    }


def parse_served_rfp(text: str) -> list[dict[str, Any]]:
    if re.search(r"Request\s+for\s+Admission", text, re.IGNORECASE) and not re.search(
        r"Request\s+for\s+Production", text, re.IGNORECASE
    ):
        raise UsageError("source looks like RFA set; refuse RFP response drafter")
    if re.search(r"\bInterrogator(?:y|ies)\b", text, re.IGNORECASE) and not re.search(
        r"Request\s+for\s+Production|\bRFP\b", text, re.IGNORECASE
    ):
        raise UsageError("source looks like ROG set; refuse RFP response drafter")
    rows: list[dict[str, Any]] = []
    current: str | None = None
    buf: list[str] = []
    for raw in text.splitlines():
        match = RFP_HEADING_RE.match(raw.rstrip())
        if match:
            if current is not None:
                body = " ".join(buf).strip()
                if not body:
                    raise UsageError(f"RFP No. {current}: empty body")
                rows.append({"served_number": int(current), "text": body})
            current = match.group("num")
            rest = (match.group("rest") or "").strip()
            buf = [rest] if rest else []
            continue
        if current is not None and raw.strip():
            buf.append(raw.strip())
    if current is not None:
        body = " ".join(buf).strip()
        if not body:
            raise UsageError(f"RFP No. {current}: empty body")
        rows.append({"served_number": int(current), "text": body})
    if not rows:
        raise UsageError("zero RFP items parsed")
    return rows


def parse_answer_brief(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        match = BRIEF_LINE_RE.match(line)
        if not match:
            raise UsageError(
                f"brief line {lineno}: expected "
                "'- N: will_produce|no_documents|partial|object_only | narrative'"
            )
        cls = match.group("cls").lower()
        if cls not in CLASSIFICATIONS:
            raise UsageError(f"brief line {lineno}: invalid classification {cls}")
        body = " ".join(match.group("body").split()).strip()
        if not body:
            raise UsageError(f"brief line {lineno}: empty narrative")
        if cls == "object_only" and not re.search(r"ATTORNEY", body, re.I):
            # Force attorney placeholder discipline
            body = f"[attorney: insert objection language] {body}"
        rows.append({
            "served_number": int(match.group("num")),
            "classification": cls,
            "narrative": body,
            "source_line": lineno,
        })
    if not rows:
        raise UsageError("zero answer-brief lines parsed")
    return rows


def _rule_ids(classification: str, available: set[str]) -> list[str]:
    candidates = {
        "will_produce": ["FRCP-34-b-2", "CCP-2031-210", "FRCP-34-a", "CCP-2031-030"],
        "no_documents": ["FRCP-34-b-2", "CCP-2031-210", "FRCP-26-b-1", "CCP-2017-010"],
        "partial": ["FRCP-34-b-2", "CCP-2031-210", "FRCP-34-a"],
        "object_only": ["FRCP-34-b-2", "CCP-2031-210", "FRCP-26-b-1", "CCP-2017-010"],
    }.get(classification, ["FRCP-34-a", "CCP-2031-030"])
    return [rid for rid in candidates if rid in available] or [
        rid for rid in candidates if rid.startswith("FRCP")
    ]


def draft_items(
    requests: list[dict[str, Any]],
    brief: list[dict[str, Any]],
    available: set[str],
) -> list[dict[str, Any]]:
    by_num = {int(b["served_number"]): b for b in brief}
    if len(by_num) != len(brief):
        raise UsageError("duplicate served_number in answer brief")
    missing = [r["served_number"] for r in requests if r["served_number"] not in by_num]
    if missing:
        raise UsageError(f"answer brief missing served numbers: {missing}")
    extra = sorted(set(by_num) - {r["served_number"] for r in requests})
    if extra:
        raise UsageError(f"answer brief has unknown served numbers: {extra}")
    items: list[dict[str, Any]] = []
    for i, req in enumerate(requests, 1):
        b = by_num[int(req["served_number"])]
        cls = b["classification"]
        narrative = b["narrative"]
        if cls == "will_produce":
            response_text = f"Plaintiff will produce: {narrative}"
        elif cls == "no_documents":
            response_text = f"After a reasonable search, plaintiff has no responsive documents. {narrative}"
        elif cls == "partial":
            response_text = f"Plaintiff will produce in part: {narrative}"
        else:
            response_text = narrative
        items.append({
            "item_id": f"DR-RFP-{i}",
            "served_number": req["served_number"],
            "request_text": req["text"],
            "classification": cls,
            "response_text": response_text,
            "rule_ids": _rule_ids(cls, available),
            "objection_draft": None,
            "needs_attorney_decision": True,
            "attorney_review_required": True,
            "request_type": REQUEST_TYPE,
            "mode": MODE,
            "notes": "Draft only — attorney must verify against the record before service.",
        })
    return items


def cmd_parse_served(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_SOURCE)
    if not source.is_file():
        print(f"ERROR: served RFP source not found: {source}", file=sys.stderr)
        return 2
    try:
        rows = parse_served_rfp(read_text(source))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    write_jsonl(output_path(root, REQUESTS_REL), rows)
    write_json(output_path(root, META_REL), {
        "schema_version": SCHEMA_VERSION,
        "request_type": REQUEST_TYPE,
        "mode": MODE,
        "source": {"relpath": source.relative_to(root).as_posix(), "sha256": sha256_file(source)},
        "parsed_at": utcnow(),
        "request_count": len(rows),
    })
    refresh_casegraph_index(root)
    print(f"parsed {len(rows)} served RFPs for response draft -> {root / REQUESTS_REL}")
    return 0


def cmd_parse_brief(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_BRIEF)
    if not source.is_file():
        print(f"ERROR: answer brief not found: {source}", file=sys.stderr)
        return 2
    try:
        rows = parse_answer_brief(read_text(source))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    write_jsonl(output_path(root, BRIEF_REL), rows)
    refresh_casegraph_index(root)
    print(f"parsed {len(rows)} answer-brief lines -> {root / BRIEF_REL}")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    available: set[str] = set()
    profile = load_matter_profile(root)
    if profile:
        try:
            loaded = jp.load_pack(
                profile["jurisdiction_pack"],
                overlay_id=profile.get("case_overlay"),
                allow_stub=bool(args.allow_stub_pack),
            )
            available = set(loaded["rule_ids"])
        except jp.PackError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    try:
        items = draft_items(read_jsonl(root / REQUESTS_REL), read_jsonl(root / BRIEF_REL), available)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    write_jsonl(output_path(root, ITEMS_REL), items)
    meta = {}
    if (root / META_REL).is_file():
        meta = json.loads((root / META_REL).read_text(encoding="utf-8"))
    meta.update({
        "drafted_at": utcnow(),
        "draft_count": len(items),
        "jurisdiction_pack": (profile or {}).get("jurisdiction_pack"),
        "case_overlay": (profile or {}).get("case_overlay"),
    })
    write_json(output_path(root, META_REL), meta)
    refresh_casegraph_index(root)
    print(f"drafted {len(items)} RFP responses -> {root / ITEMS_REL}")
    return 0


def build_package(root: Path, items: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Draft RFP Responses - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {_matter_id(root)}",
        f"**Request type:** {REQUEST_TYPE}",
        f"**Mode:** {MODE}",
        f"**Jurisdiction pack:** {meta.get('jurisdiction_pack') or '—'}",
        "**Single-matter invocation:** confirmed",
        "",
        "> Not a verification or service package. Attorney must edit before serving.",
        "> Objection language is attorney-controlled (`objection_draft` is null).",
        "",
    ]
    for item in items:
        lines.extend([
            f"## Response to Request for Production No. {item['served_number']}",
            "",
            f"**Request:** {item['request_text']}",
            "",
            f"**Classification:** {item['classification']}",
            f"**Rule ids:** {', '.join(item.get('rule_ids') or []) or '—'}",
            "",
            item["response_text"],
            "",
        ])
    lines.extend([
        "## Attorney checklist",
        "",
        "- [ ] Each production stance checked against indexed production",
        "- [ ] Partial/no-documents narratives are accurate",
        "- [ ] No unintended over-commitment to produce",
        "- [ ] Gate commands for Slice C1 exit 0",
        "- [ ] Owner §9.5 sign-off before any live matter use",
        "",
    ])
    return "\n".join(lines)


def cmd_package(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    items = read_jsonl(root / ITEMS_REL)
    if not items:
        print("ERROR: no draft items", file=sys.stderr)
        return 1
    for item in items:
        if item.get("objection_draft") not in (None, ""):
            print(f"ERROR: {item.get('item_id')}: objection_draft must be null", file=sys.stderr)
            return 1
        if item.get("classification") not in CLASSIFICATIONS:
            print(f"ERROR: {item.get('item_id')}: bad classification", file=sys.stderr)
            return 1
    meta = {}
    if (root / META_REL).is_file():
        meta = json.loads((root / META_REL).read_text(encoding="utf-8"))
    path = output_path(root, PACKAGE_REL)
    path.write_text(build_package(root, items, meta), encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote draft RFP responses -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    return subprocess.run(command, text=True, check=False).returncode


def cmd_validate(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    items = read_jsonl(root / ITEMS_REL)
    package = root / PACKAGE_REL
    errors: list[str] = []
    if not items:
        errors.append("no draft items")
    if not package.is_file():
        errors.append(f"missing package: {package}")
    else:
        text = package.read_text(encoding="utf-8")
        if re.search(r"\bRFP-0\d{2,}\b", text):
            errors.append("package contains Bates-colliding RFP-00N tokens")
    for item in items:
        if item.get("mode") != MODE or item.get("request_type") != REQUEST_TYPE:
            errors.append(f"{item.get('item_id')}: wrong type/mode")
        if item.get("objection_draft") not in (None, ""):
            errors.append(f"{item.get('item_id')}: objection_draft must be null")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    gates = [
        [sys.executable, str(CASEGRAPH_SCRIPT), "status", str(root)],
        [sys.executable, str(CASEGRAPH_SCRIPT), "verify-cites", str(root), str(package), "--allow-empty"],
        [sys.executable, str(CASEGRAPH_SCRIPT), "check-isolation", str(root), str(package), "--strict"],
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
    print("PASS: draft RFP response validation")
    return 0


def _create_synthetic_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_served").mkdir(parents=True)
    (root / "01_discovery_proposed").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-18\n", encoding="utf-8",
    )
    (root / PROFILE_REL).write_text(
        f"matter_id: {matter_id}\n"
        "court: synthetic\n"
        "jurisdiction_pack: frcp_generic\n"
        "case_overlay: fela\n"
        "limits_used:\n  rog: 0\n  rfp: null\n  rfa: 0\n",
        encoding="utf-8",
    )
    (root / DEFAULT_SOURCE).write_text(
        "Request for Production No. 1: Produce incident reports for the "
        "June 1, 2024 ladder event.\n\n"
        "Request for Production No. 2: Produce photographs of the ladder.\n\n"
        "Request for Production No. 3: Produce payroll records supporting wage loss.\n",
        encoding="utf-8",
    )
    (root / DEFAULT_BRIEF).write_text(
        "- 1: will_produce | the June 1, 2024 incident report.\n"
        "- 2: no_documents | No responsive ladder photographs after a reasonable search.\n"
        "- 3: partial | wage materials limited to June 2 through July 15, 2024.\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000010\n\n"
        "Incident report dated June 1, 2024. Photograph log of the ladder is indexed.\n",
        encoding="utf-8",
    )
    cg.main(["init", str(root), "--matter-id", matter_id, "--bates-prefix", prefix])
    cg.main(["build", str(root)])


def cmd_selftest(_args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="rfp-response-draft-selftest-") as tmp:
        root = Path(tmp) / "SYN-DRFP"
        _create_synthetic_matter(root, "SYN-DRFP", "THORN-PROD")
        for command in (
            ["parse-served-rfp", str(root)],
            ["parse-answer-brief", str(root)],
            ["draft-rfp-responses", str(root)],
            ["package-rfp-response-draft", str(root)],
            ["validate-rfp-response-draft", str(root)],
        ):
            code = main(command)
            if code != 0:
                print(f"selftest failed: {' '.join(command)}", file=sys.stderr)
                return code
        pkg = (root / PACKAGE_REL).read_text(encoding="utf-8")
        if "will produce" not in pkg.lower() or "no responsive" not in pkg.lower():
            print("selftest failed: expected will_produce/no_documents draft language", file=sys.stderr)
            return 1
        if "RFP-001" in pkg:
            print("selftest failed: Bates-like RFP-001 in package", file=sys.stderr)
            return 1
        print("PASS: rfp-response-draft selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-served-rfp", help="parse served RFP set for drafting")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_served)

    p = sub.add_parser("parse-answer-brief", help="parse attorney answer brief")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_brief)

    p = sub.add_parser("draft-rfp-responses", help="draft responses from brief")
    p.add_argument("matter_dir")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_draft)

    p = sub.add_parser("package-rfp-response-draft", help="write draft responses markdown")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package)

    p = sub.add_parser("validate-rfp-response-draft", help="run Slice C1 validators")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("selftest", help="offline synthetic C1 E2E")
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
