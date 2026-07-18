#!/usr/bin/env python3
"""Slice D2: audit defense-served RFAs under a pinned jurisdiction pack (synthetic-only).

Mode: audit_incoming_request / request_type: rfa.
Does not reuse response-audit or outgoing-draft parsers.
Not live-ready; attorney review required. Live use needs SPEC §9.5 sign-off.
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
LOAD_PACK_SCRIPT = WORKFLOW_ROOT / "jurisdiction" / "load_pack.py"

REQUESTS_REL = Path("02_outputs") / "incoming_rfa_requests.jsonl"
ITEMS_REL = Path("02_outputs") / "incoming_rfa_request_audit_items.jsonl"
PACKAGE_REL = Path("02_outputs") / "incoming_rfa_request_audit_report.md"
META_REL = Path("02_outputs") / "incoming_rfa_request_audit_meta.json"
DEFAULT_SOURCE = Path("01_discovery_served") / "rfa_set.md"
PROFILE_REL = Path("03_attorney") / "matter_profile.yaml"

SCHEMA_VERSION = 1
REQUEST_TYPE = "rfa"
MODE = "audit_incoming_request"

RFA_HEADING_RE = re.compile(
    r"^\s*(?:(?:Request\s+for\s+Admission|RFA)\s*(?:No\.?|Number)?\s*)"
    r"(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
NUMBERED_RE = re.compile(r"^\s*(?P<num>\d{1,3})[.)]\s+(?P<rest>.+)$")
ADMIT_RE = re.compile(r"\badmit\b", re.IGNORECASE)
ROG_ONLY_RE = re.compile(
    r"^(state|identify|describe|list|explain|set forth)\b",
    re.IGNORECASE,
)
PRODUCE_WORD_RE = re.compile(r"\b(produce|production)\b", re.IGNORECASE)
AND_SPLIT_RE = re.compile(r"\bAND\b")
COMPOUND_ADMIT_RE = re.compile(r"\badmit\b.+\band\b.+\b(?:that|whether)\b", re.IGNORECASE)
LEGAL_CONCLUSION_RE = re.compile(
    r"\b(liable|negligen(?:ce|t)|breach(?:ed)?\s+(?:of\s+)?duty|proximate cause|"
    r"as a matter of law|entitled to judgment)\b",
    re.IGNORECASE,
)
PRIVILEGE_FISH_RE = re.compile(
    r"\b(communications?\s+with\s+(?:counsel|attorneys?)|attorney[- ]client|"
    r"work[- ]product|legal advice)\b",
    re.IGNORECASE,
)
VAGUE_RE = re.compile(
    r"\b(any and all|all facts|everything concerning|whatsoever|"
    r"including but not limited to)\b",
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


cg = _load_module(CASEGRAPH_SCRIPT, "legal_casegraph_rfa_req_audit")
jp = _load_module(LOAD_PACK_SCRIPT, "jurisdiction_load_pack_d2")


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


def load_matter_profile(root: Path) -> dict[str, Any]:
    path = root / PROFILE_REL
    if not path.is_file():
        raise UsageError(
            f"missing {PROFILE_REL.as_posix()} — required for audit_incoming_request "
            "(jurisdiction_pack, optional case_overlay)"
        )
    try:
        import yaml
    except ImportError as exc:
        raise UsageError("PyYAML required to read matter_profile.yaml") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise UsageError(f"invalid matter_profile.yaml: {exc}") from exc
    if not isinstance(data, dict):
        raise UsageError("matter_profile.yaml must be a mapping")
    pack = str(data.get("jurisdiction_pack") or "").strip()
    if not pack:
        raise UsageError("matter_profile.yaml must set jurisdiction_pack")
    overlay = data.get("case_overlay")
    overlay_id = str(overlay).strip() if overlay else None
    return {
        "matter_id": data.get("matter_id") or _matter_id(root),
        "court": data.get("court"),
        "jurisdiction_pack": pack,
        "case_overlay": overlay_id or None,
        "discovery_cutoff": data.get("discovery_cutoff"),
        "expert_cutoff": data.get("expert_cutoff"),
        "limits_used": data.get("limits_used") or {},
        "raw": data,
    }


def _blocks_by_heading(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    current_num: str | None = None
    buf: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        match = RFA_HEADING_RE.match(line)
        if match:
            if current_num is not None:
                blocks.append((current_num, " ".join(buf).strip()))
            current_num = match.group("num")
            rest = (match.group("rest") or "").strip()
            buf = [rest] if rest else []
            continue
        if current_num is not None and line.strip():
            buf.append(line.strip())
    if current_num is not None:
        blocks.append((current_num, " ".join(buf).strip()))
    return blocks


def _numbered_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for raw in text.splitlines():
        match = NUMBERED_RE.match(raw.strip())
        if match:
            blocks.append((match.group("num"), match.group("rest").strip()))
    return blocks


def parse_served_rfa(text: str) -> list[dict[str, Any]]:
    """Parse defense-served RFAs. Refuses RFP/ROG-looking sets."""
    if re.search(r"Request\s+for\s+Production", text, re.IGNORECASE) and not re.search(
        r"Request\s+for\s+Admission", text, re.IGNORECASE
    ):
        raise UsageError("source looks like RFP set; use D1 (rfp_request_audit)")
    if re.search(r"\bInterrogator(?:y|ies)\b", text, re.IGNORECASE) and not re.search(
        r"Request\s+for\s+Admission|\bRFA\b", text, re.IGNORECASE
    ):
        raise UsageError("source looks like ROG set; use D3 (not implemented) / refuse RFA auditor")

    blocks = _blocks_by_heading(text) or _numbered_blocks(text)
    if not blocks:
        raise UsageError("zero RFA items parsed — expected 'Request for Admission No. N:' headings")

    rows: list[dict[str, Any]] = []
    for num, body in blocks:
        body = " ".join(body.split()).strip()
        if not body:
            raise UsageError(f"RFA No. {num}: empty body")
        if PRODUCE_WORD_RE.search(body) and not ADMIT_RE.search(body):
            raise UsageError(
                f"RFA No. {num}: production-style language refused; this auditor is RFA-only"
            )
        if ROG_ONLY_RE.match(body) and not ADMIT_RE.search(body):
            raise UsageError(
                f"RFA No. {num}: interrogatory-style language refused; this auditor is RFA-only"
            )
        rows.append({
            "served_number": int(num),
            "text": body,
            "request_type": REQUEST_TYPE,
            "mode": MODE,
        })
    return rows


def _ensure_rule(rule_ids: set[str], available: set[str], candidate: str) -> str | None:
    if candidate in available:
        rule_ids.add(candidate)
        return candidate
    return None


def audit_request(
    req: dict[str, Any],
    *,
    available_rules: set[str],
    index: int,
) -> dict[str, Any]:
    text = str(req.get("text") or "")
    flags: list[str] = []
    rule_ids: set[str] = set()
    notes: list[str] = []
    severity = "info"
    needs_attorney = False

    def add(flag: str, rules: list[str], note: str, sev: str = "warn") -> None:
        nonlocal severity, needs_attorney
        flags.append(flag)
        notes.append(note)
        for rid in rules:
            if _ensure_rule(rule_ids, available_rules, rid) is None:
                needs_attorney = True
                notes.append(f"Rule {rid} not in pinned pack — needs_attorney_rule_confirm.")
        if sev == "fail_candidate":
            severity = "fail_candidate"
            needs_attorney = True
        elif sev == "warn" and severity != "fail_candidate":
            severity = "warn"
            needs_attorney = True

    # Compound / not separately stated (FRCP 36(a)(2))
    and_parts = [p for p in AND_SPLIT_RE.split(text) if p.strip()]
    if len(and_parts) >= 2 or COMPOUND_ADMIT_RE.search(text) or len(re.findall(r"\badmit\b", text, re.I)) > 1:
        add(
            "not_separately_stated",
            ["FRCP-36-a-2", "FRCP-26-b-1"],
            "Compound or multi-fact admission — FRCP 36 expects each matter separately stated.",
            "warn",
        )
    if VAGUE_RE.search(text):
        add(
            "vague_or_overbroad",
            ["FRCP-36-a-1", "FRCP-26-b-1"],
            "Vague/overbroad admission language may be improper under Rule 36 scope.",
            "warn",
        )
    if LEGAL_CONCLUSION_RE.search(text):
        add(
            "legal_conclusion",
            ["FRCP-36-a-1", "FRCP-26-b-1"],
            "May call for a pure legal conclusion — attorney must decide answer/objection posture.",
            "warn",
        )
    if PRIVILEGE_FISH_RE.search(text):
        add(
            "privilege_boundary",
            ["FRCP-26-b-1", "FRCP-36-a-5"],
            "Language may reach privileged attorney communications — attorney must decide objection posture.",
            "fail_candidate",
        )

    if not flags:
        _ensure_rule(rule_ids, available_rules, "FRCP-36-a-1")
        _ensure_rule(rule_ids, available_rules, "FRCP-26-b-1")
        notes.append("No automated compound/privilege flags; attorney response strategy still required.")

    if not rule_ids:
        needs_attorney = True
        notes.append("No pack rule_ids resolved — needs_attorney_rule_confirm.")

    item_id = f"IR-RFA-{index}"
    return {
        "item_id": item_id,
        "served_number": req.get("served_number"),
        "request_type": REQUEST_TYPE,
        "mode": MODE,
        "source_request_label": f"Served admission request {req.get('served_number')}",
        "text": text,
        "flags": sorted(set(flags)),
        "rule_ids": sorted(rule_ids),
        "severity": severity if flags else "info",
        "notes": " ".join(notes),
        "needs_attorney_decision": needs_attorney or bool(flags),
        "needs_attorney_rule_confirm": any("needs_attorney_rule_confirm" in n for n in notes),
        "objection_draft": None,
        "attorney_review_required": True,
    }


def cmd_parse_served_rfa(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_SOURCE)
    if not source.is_file():
        print(f"ERROR: served RFA source not found: {source}", file=sys.stderr)
        return 2
    try:
        rows = parse_served_rfa(read_text(source))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    write_jsonl(output_path(root, REQUESTS_REL), rows)
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
            "request_count": len(rows),
        },
    )
    refresh_casegraph_index(root)
    print(f"parsed {len(rows)} served RFAs -> {root / REQUESTS_REL}")
    return 0


def cmd_audit_incoming_rfa(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    try:
        profile = load_matter_profile(root)
        loaded = jp.load_pack(
            profile["jurisdiction_pack"],
            overlay_id=profile.get("case_overlay"),
            allow_stub=bool(args.allow_stub_pack),
        )
    except (UsageError, jp.PackError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    available = set(loaded["rule_ids"])
    requests = read_jsonl(root / REQUESTS_REL)
    items = [
        audit_request(req, available_rules=available, index=i)
        for i, req in enumerate(requests, 1)
    ]
    write_jsonl(output_path(root, ITEMS_REL), items)
    meta_path = root / META_REL
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    meta.update({
        "audited_at": utcnow(),
        "jurisdiction_pack": profile["jurisdiction_pack"],
        "case_overlay": profile.get("case_overlay"),
        "pack_rule_count": len(available),
        "audit_item_count": len(items),
    })
    write_json(output_path(root, META_REL), meta)
    refresh_casegraph_index(root)
    print(f"audited {len(items)} incoming RFAs -> {root / ITEMS_REL}")
    return 0


def validate_records(requests: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not items:
        errors.append("no audit items")
    ids = [i.get("item_id") for i in items]
    if len(set(ids)) != len(ids):
        errors.append("duplicate item_ids")
    if len(items) != len(requests):
        errors.append("audit item count != served request count")
    for item in items:
        iid = item.get("item_id")
        if item.get("mode") != MODE or item.get("request_type") != REQUEST_TYPE:
            errors.append(f"{iid}: wrong request_type/mode")
        if not item.get("rule_ids") and not item.get("needs_attorney_rule_confirm"):
            errors.append(f"{iid}: must have rule_ids or needs_attorney_rule_confirm")
        if item.get("objection_draft") not in (None, ""):
            errors.append(f"{iid}: objection_draft must be null unless firm template opt-in")
        if item.get("severity") not in {"info", "warn", "fail_candidate"}:
            errors.append(f"{iid}: invalid severity")
    return errors


def _display_item_id(item_id: str) -> str:
    match = re.fullmatch(r"IR-RFA-(\d+)", str(item_id))
    if match:
        return f"Incoming admission request {int(match.group(1))}"
    return str(item_id)


def build_package(root: Path, items: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    matter_id = _matter_id(root)
    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Incoming Admission Request Audit - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Request type:** {REQUEST_TYPE}",
        f"**Mode:** {MODE}",
        f"**Jurisdiction pack:** {meta.get('jurisdiction_pack') or '—'}",
        f"**Case overlay:** {meta.get('case_overlay') or '—'}",
        f"**Source sha256:** {(meta.get('source') or {}).get('sha256') or '—'}",
        "**Casegraph status:** fresh",
        "**Single-matter invocation:** confirmed",
        "",
        "> Draft for attorney review. Not a certification of objections or responses.",
        "> No final objection strategy. No cross-client facts.",
        "> Every finding cites pack rule ids or needs attorney rule confirmation.",
        "",
        "## Findings",
        "",
    ]
    for item in items:
        flags = ", ".join(item.get("flags") or []) or "—"
        rules = ", ".join(item.get("rule_ids") or []) or "—"
        lines.extend([
            f"### {_display_item_id(item['item_id'])}",
            "",
            f"**Served No.:** {item.get('served_number')}",
            f"**Severity:** {item.get('severity')}",
            f"**Flags:** {flags}",
            f"**Rule ids:** {rules}",
            f"**Attorney decision:** {'required' if item.get('needs_attorney_decision') else 'review still required'}",
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
            lines.append(
                f"- {_display_item_id(item['item_id'])} ({item.get('severity')}): {item.get('notes')}"
            )
    else:
        lines.append("- None flagged (full attorney review of response strategy still required).")

    lines.extend([
        "",
        "## Attorney checklist",
        "",
        "- [ ] Compound / separately-stated flags reviewed against Rule 36",
        "- [ ] Privilege-boundary and legal-conclusion items decided by attorney",
        "- [ ] No invented Bates or transcript locators in this package",
        "- [ ] Gate commands for Slice D2 exit 0",
        "- [ ] Owner §9.5 sign-off before any live matter use",
        "",
    ])
    return "\n".join(lines)


def cmd_package(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = read_jsonl(root / REQUESTS_REL)
    items = read_jsonl(root / ITEMS_REL)
    errors = validate_records(requests, items)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    meta = {}
    if (root / META_REL).is_file():
        meta = json.loads((root / META_REL).read_text(encoding="utf-8"))
    path = output_path(root, PACKAGE_REL)
    path.write_text(build_package(root, items, meta), encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote incoming RFA request audit package -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    return subprocess.run(command, text=True, check=False).returncode


def cmd_validate(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    requests = read_jsonl(root / REQUESTS_REL)
    items = read_jsonl(root / ITEMS_REL)
    errors = validate_records(requests, items)
    package = root / PACKAGE_REL
    if not package.is_file():
        errors.append(f"missing package: {package}")
    else:
        text = package.read_text(encoding="utf-8")
        if re.search(r"\bRFA-0\d{2,}\b", text):
            errors.append("package contains Bates-colliding RFA-00N tokens; use display labels")
    try:
        profile = load_matter_profile(root)
        jp.load_pack(
            profile["jurisdiction_pack"],
            overlay_id=profile.get("case_overlay"),
            allow_stub=bool(args.allow_stub_pack),
        )
    except (UsageError, jp.PackError) as exc:
        errors.append(str(exc))
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
    print("PASS: incoming RFA request audit validation")
    return 0


def _write_profile(root: Path, matter_id: str) -> None:
    (root / "03_attorney").mkdir(parents=True, exist_ok=True)
    (root / PROFILE_REL).write_text(
        f"matter_id: {matter_id}\n"
        "court: \"U.S. District Court (synthetic)\"\n"
        "jurisdiction_pack: frcp_generic\n"
        "case_overlay: fela\n"
        "discovery_cutoff: null\n"
        "expert_cutoff: null\n"
        "limits_used:\n"
        "  rog: 0\n"
        "  rfp: null\n"
        "  rfa: 0\n",
        encoding="utf-8",
    )


def _create_synthetic_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_served").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    _write_profile(root, matter_id)
    (root / DEFAULT_SOURCE).write_text(
        "<!-- SYNTHETIC / NON-CLIENT / TEST ONLY -->\n\n"
        "Request for Admission No. 1: Admit that an incident report exists for the "
        "June 1, 2024 ladder event.\n\n"
        "Request for Admission No. 2: Admit that defendant was negligent AND that "
        "defendant's negligence was the proximate cause of plaintiff's injuries AND "
        "that plaintiff is entitled to judgment as a matter of law.\n\n"
        "Request for Admission No. 3: Admit that counsel's legal advice to plaintiff "
        "concerning settlement was unreasonable.\n",
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
    with tempfile.TemporaryDirectory(prefix="rfa-request-audit-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_matter(a, "SYN-IRFA-A", "THORN-PROD")
        _create_synthetic_matter(b, "SYN-IRFA-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-served-rfa", str(matter)],
                ["audit-incoming-rfa", str(matter)],
                ["package-incoming-rfa-audit", str(matter)],
                ["validate-incoming-rfa-audit", str(matter)],
            ):
                code = main(command)
                if code != 0:
                    print(f"selftest failed for {matter.name}: {' '.join(command)}", file=sys.stderr)
                    return code
        a_items = read_jsonl(a / ITEMS_REL)
        if not any("not_separately_stated" in (i.get("flags") or []) for i in a_items):
            print("selftest failed: expected compound flag", file=sys.stderr)
            return 1
        if not any("privilege_boundary" in (i.get("flags") or []) for i in a_items):
            print("selftest failed: expected privilege_boundary flag", file=sys.stderr)
            return 1
        if not all(i.get("rule_ids") for i in a_items):
            print("selftest failed: every item needs rule_ids", file=sys.stderr)
            return 1
        a_pkg = (a / PACKAGE_REL).read_text(encoding="utf-8")
        b_pkg = (b / PACKAGE_REL).read_text(encoding="utf-8")
        if "RIVER-PROD" in a_pkg or "THORN-PROD" in b_pkg:
            print("selftest failed: cross-matter Bates leaked", file=sys.stderr)
            return 1
        if "RFA-001" in a_pkg:
            print("selftest failed: Bates-like RFA-001 in package", file=sys.stderr)
            return 1
        print("PASS: rfa-request-audit selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-served-rfa", help="parse defense-served RFA set")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_served_rfa)

    p = sub.add_parser("audit-incoming-rfa", help="audit served RFAs against jurisdiction pack")
    p.add_argument("matter_dir")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_audit_incoming_rfa)

    p = sub.add_parser("package-incoming-rfa-audit", help="write audit report markdown")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package)

    p = sub.add_parser("validate-incoming-rfa-audit", help="run Slice D2 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("selftest", help="offline synthetic D2 E2E")
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
