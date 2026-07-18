#!/usr/bin/env python3
"""Slice D3: audit defense-served ROGs under a pinned jurisdiction pack (synthetic-only).

Mode: audit_incoming_request / request_type: rog.
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

REQUESTS_REL = Path("02_outputs") / "incoming_rog_requests.jsonl"
ITEMS_REL = Path("02_outputs") / "incoming_rog_request_audit_items.jsonl"
PACKAGE_REL = Path("02_outputs") / "incoming_rog_request_audit_report.md"
META_REL = Path("02_outputs") / "incoming_rog_request_audit_meta.json"
DEFAULT_SOURCE = Path("01_discovery_served") / "rog_set.md"
PROFILE_REL = Path("03_attorney") / "matter_profile.yaml"

SCHEMA_VERSION = 1
REQUEST_TYPE = "rog"
MODE = "audit_incoming_request"
DEFAULT_ROG_LIMIT = 25

ROG_HEADING_RE = re.compile(
    r"^\s*(?:(?:Interrogator(?:y|ies)|ROG)\s*(?:No\.?|Number)?\s*)"
    r"(?P<num>\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
NUMBERED_RE = re.compile(r"^\s*(?P<num>\d{1,3})[.)]\s+(?P<rest>.+)$")
SUBPART_RE = re.compile(r"^\s*\((?P<label>[a-zA-Z]|\d{1,2})\)\s+(?P<rest>.+)$")
ADMIT_RE = re.compile(r"\badmit\b", re.IGNORECASE)
PRODUCE_WORD_RE = re.compile(r"\b(produce|production)\b", re.IGNORECASE)
VAGUE_RE = re.compile(
    r"\b(any and all|all facts|everything concerning|whatsoever|"
    r"including but not limited to)\b",
    re.IGNORECASE,
)
CONTENTION_RE = re.compile(
    r"\b(all facts supporting|facts? (?:and contentions? )?supporting|"
    r"contend(?:s|ing)? that|basis for (?:each|any) claim|"
    r"each and every fact)\b",
    re.IGNORECASE,
)
PRIVILEGE_FISH_RE = re.compile(
    r"\b(communications?\s+with\s+(?:counsel|attorneys?)|attorney[- ]client|"
    r"work[- ]product|legal advice)\b",
    re.IGNORECASE,
)
LEGAL_CONCLUSION_RE = re.compile(
    r"\b(liable|negligen(?:ce|t)|breach(?:ed)?\s+(?:of\s+)?duty|proximate cause|"
    r"as a matter of law)\b",
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


cg = _load_module(CASEGRAPH_SCRIPT, "legal_casegraph_rog_req_audit")
jp = _load_module(LOAD_PACK_SCRIPT, "jurisdiction_load_pack_d3")


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
    limits = data.get("limits_used") or {}
    if not isinstance(limits, dict):
        limits = {}
    rog_used = limits.get("rog", 0)
    try:
        rog_used_n = int(rog_used) if rog_used is not None else 0
    except (TypeError, ValueError):
        rog_used_n = 0
    return {
        "matter_id": data.get("matter_id") or _matter_id(root),
        "court": data.get("court"),
        "jurisdiction_pack": pack,
        "case_overlay": overlay_id or None,
        "discovery_cutoff": data.get("discovery_cutoff"),
        "expert_cutoff": data.get("expert_cutoff"),
        "limits_used": limits,
        "rog_used": rog_used_n,
        "raw": data,
    }


def _blocks_by_heading(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, list[str]]] = []
    current_num: str | None = None
    buf: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        match = ROG_HEADING_RE.match(line)
        if match:
            if current_num is not None:
                blocks.append((current_num, buf))
            current_num = match.group("num")
            rest = (match.group("rest") or "").strip()
            buf = [rest] if rest else []
            continue
        if current_num is not None:
            buf.append(line)
    if current_num is not None:
        blocks.append((current_num, buf))
    return [(num, "\n".join(lines).strip()) for num, lines in blocks if "\n".join(lines).strip()]


def _numbered_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for raw in text.splitlines():
        match = NUMBERED_RE.match(raw.strip())
        if match:
            blocks.append((match.group("num"), match.group("rest").strip()))
    return blocks


def _split_subparts(body: str) -> list[tuple[str | None, str]]:
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


def parse_served_rog(text: str) -> list[dict[str, Any]]:
    """Parse defense-served interrogatories. Refuses RFP/RFA-looking sets."""
    if re.search(r"Request\s+for\s+Production", text, re.IGNORECASE) and not re.search(
        r"\bInterrogator(?:y|ies)\b", text, re.IGNORECASE
    ):
        raise UsageError("source looks like RFP set; use D1 (rfp_request_audit)")
    if re.search(r"Request\s+for\s+Admission", text, re.IGNORECASE) and not re.search(
        r"\bInterrogator(?:y|ies)\b", text, re.IGNORECASE
    ):
        raise UsageError("source looks like RFA set; use D2 (rfa_request_audit)")

    blocks = _blocks_by_heading(text) or _numbered_blocks(text)
    if not blocks:
        raise UsageError("zero ROG items parsed — expected 'Interrogatory No. N:' headings")

    rows: list[dict[str, Any]] = []
    for num, body in blocks:
        subparts = _split_subparts(body)
        if not subparts:
            raise UsageError(f"Interrogatory No. {num}: empty body")
        for _label, part_text in subparts:
            if PRODUCE_WORD_RE.search(part_text) and not re.search(
                r"\b(state|identify|describe|list|explain)\b", part_text, re.I
            ):
                raise UsageError(
                    f"Interrogatory No. {num}: production-style language refused; "
                    "this auditor is ROG-only"
                )
            if ADMIT_RE.search(part_text) and not re.search(
                r"\b(state|identify|describe|list|explain|whether)\b", part_text, re.I
            ):
                raise UsageError(
                    f"Interrogatory No. {num}: admission-style language refused; "
                    "this auditor is ROG-only"
                )
        flat_text = " ".join(t for _, t in subparts)
        labeled = [{"label": lab, "text": txt} for lab, txt in subparts if lab is not None]
        discrete = len(subparts) if any(lab is not None for lab, _ in subparts) else 1
        rows.append({
            "served_number": int(num),
            "text": flat_text,
            "subparts": labeled,
            "discrete_subpart_count": discrete,
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
    rog_used: int,
    set_discrete_total: int,
) -> dict[str, Any]:
    text = str(req.get("text") or "")
    discrete = int(req.get("discrete_subpart_count") or 1)
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
                notes.append(
                    f"rule_id {rid} not in pinned pack — needs_attorney_rule_confirm."
                )
        if sev == "fail_candidate":
            severity = "fail_candidate"
            needs_attorney = True
        elif sev == "warn" and severity != "fail_candidate":
            severity = "warn"
            needs_attorney = True

    if discrete >= 2:
        add(
            "discrete_subparts",
            ["FRCP-33-a-1", "CCP-2030-030", "FRCP-26-b-1", "CCP-2017-010"],
            f"Interrogatory has {discrete} discrete subparts — each counts toward the Rule 33 limit.",
            "warn",
        )
    if VAGUE_RE.search(text):
        add(
            "vague_or_overbroad",
            ["FRCP-33-a-2", "CCP-2030-060", "FRCP-26-b-1", "CCP-2017-010"],
            "Vague/overbroad interrogatory language may exceed Rule 26(b) scope.",
            "warn",
        )
    if CONTENTION_RE.search(text) or (
        LEGAL_CONCLUSION_RE.search(text) and re.search(r"\ball facts\b", text, re.I)
    ):
        add(
            "contention_interrogatory",
            ["FRCP-33-a-2", "CCP-2030-060", "FRCP-26-b-1", "CCP-2017-010"],
            "Contention / all-facts interrogatory — timing and scope are attorney-controlled under Rule 33(a)(2).",
            "warn",
        )
    if PRIVILEGE_FISH_RE.search(text):
        add(
            "privilege_boundary",
            ["FRCP-26-b-1", "FRCP-33-b", "CCP-2017-010", "CCP-2030-210"],
            "Language may reach privileged attorney communications — attorney must decide objection posture.",
            "fail_candidate",
        )

    limit = 35 if "CCP-2030-030" in available_rules else DEFAULT_ROG_LIMIT
    projected = rog_used + set_discrete_total
    if projected > limit:
        add(
            "exceeds_numerical_limit",
            ["FRCP-33-a-1", "CCP-2030-030"],
            f"Projected interrogatory count (used {rog_used} + this set {set_discrete_total} "
            f"= {projected}) exceeds default limit of {limit} "
            "(absent stipulation/order).",
            "fail_candidate",
        )

    if not flags:
        for rid in ("FRCP-33-a-1", "CCP-2030-030", "FRCP-26-b-1", "CCP-2017-010"):
            _ensure_rule(rule_ids, available_rules, rid)
        notes.append("No automated subpart/privilege flags; attorney response strategy still required.")

    if not rule_ids:
        needs_attorney = True
        notes.append("No pack rule_ids resolved — needs_attorney_rule_confirm.")

    item_id = f"IR-ROG-{index}"
    return {
        "item_id": item_id,
        "served_number": req.get("served_number"),
        "request_type": REQUEST_TYPE,
        "mode": MODE,
        "source_request_label": f"Served interrogatory request {req.get('served_number')}",
        "text": text,
        "discrete_subpart_count": discrete,
        "subparts": req.get("subparts") or [],
        "flags": sorted(set(flags)),
        "rule_ids": sorted(rule_ids),
        "severity": severity if flags else "info",
        "notes": " ".join(notes),
        "needs_attorney_decision": needs_attorney or bool(flags),
        "needs_attorney_rule_confirm": any("needs_attorney_rule_confirm" in n for n in notes),
        "objection_draft": None,
        "attorney_review_required": True,
    }


def cmd_parse_served_rog(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or DEFAULT_SOURCE)
    if not source.is_file():
        print(f"ERROR: served ROG source not found: {source}", file=sys.stderr)
        return 2
    try:
        rows = parse_served_rog(read_text(source))
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
            "discrete_subpart_total": sum(int(r.get("discrete_subpart_count") or 1) for r in rows),
        },
    )
    refresh_casegraph_index(root)
    print(f"parsed {len(rows)} served ROGs -> {root / REQUESTS_REL}")
    return 0


def cmd_audit_incoming_rog(args: argparse.Namespace) -> int:
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
    set_discrete_total = sum(int(r.get("discrete_subpart_count") or 1) for r in requests)
    items = [
        audit_request(
            req,
            available_rules=available,
            index=i,
            rog_used=int(profile.get("rog_used") or 0),
            set_discrete_total=set_discrete_total,
        )
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
        "rog_used": profile.get("rog_used"),
        "discrete_subpart_total": set_discrete_total,
    })
    write_json(output_path(root, META_REL), meta)
    refresh_casegraph_index(root)
    print(f"audited {len(items)} incoming ROGs -> {root / ITEMS_REL}")
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
    match = re.fullmatch(r"IR-ROG-(\d+)", str(item_id))
    if match:
        return f"Incoming interrogatory request {int(match.group(1))}"
    return str(item_id)


def build_package(root: Path, items: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    matter_id = _matter_id(root)
    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Incoming Interrogatory Request Audit - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Request type:** {REQUEST_TYPE}",
        f"**Mode:** {MODE}",
        f"**Jurisdiction pack:** {meta.get('jurisdiction_pack') or '—'}",
        f"**Case overlay:** {meta.get('case_overlay') or '—'}",
        f"**Source sha256:** {(meta.get('source') or {}).get('sha256') or '—'}",
        f"**Discrete subpart total (this set):** {meta.get('discrete_subpart_total') or '—'}",
        f"**Prior interrogatories used (profile):** {meta.get('rog_used') if meta.get('rog_used') is not None else '—'}",
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
        subs = item.get("subparts") or []
        sub_note = (
            ", ".join(f"({s.get('label')})" for s in subs if s.get("label"))
            if subs
            else "—"
        )
        lines.extend([
            f"### {_display_item_id(item['item_id'])}",
            "",
            f"**Served No.:** {item.get('served_number')}",
            f"**Discrete subparts:** {item.get('discrete_subpart_count') or 1} ({sub_note})",
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
        "- [ ] Discrete-subpart / Rule 33 numerical-limit flags reviewed",
        "- [ ] Contention and privilege-boundary items decided by attorney",
        "- [ ] No invented Bates or transcript locators in this package",
        "- [ ] Gate commands for Slice D3 exit 0",
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
    print(f"wrote incoming ROG request audit package -> {path}")
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
        if re.search(r"\bROG-0\d{2,}\b", text):
            errors.append("package contains Bates-colliding ROG-00N tokens; use display labels")
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
    print("PASS: incoming ROG request audit validation")
    return 0


def _write_profile(root: Path, matter_id: str, *, rog_used: int = 0) -> None:
    (root / "03_attorney").mkdir(parents=True, exist_ok=True)
    (root / PROFILE_REL).write_text(
        f"matter_id: {matter_id}\n"
        "court: \"U.S. District Court (synthetic)\"\n"
        "jurisdiction_pack: frcp_generic\n"
        "case_overlay: fela\n"
        "discovery_cutoff: null\n"
        "expert_cutoff: null\n"
        "limits_used:\n"
        f"  rog: {rog_used}\n"
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
        "Interrogatory No. 1: State the date of the incident involving the ladder.\n\n"
        "Interrogatory No. 2:\n"
        "(a) Identify medical treatment received after the injury.\n"
        "(b) State whether plaintiff claims wage loss.\n\n"
        "Interrogatory No. 3: State all facts supporting any claim of negligence.\n\n"
        "Interrogatory No. 4: Identify communications with counsel concerning settlement strategy.\n",
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
    with tempfile.TemporaryDirectory(prefix="rog-request-audit-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_matter(a, "SYN-IROG-A", "THORN-PROD")
        _create_synthetic_matter(b, "SYN-IROG-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-served-rog", str(matter)],
                ["audit-incoming-rog", str(matter)],
                ["package-incoming-rog-audit", str(matter)],
                ["validate-incoming-rog-audit", str(matter)],
            ):
                code = main(command)
                if code != 0:
                    print(f"selftest failed for {matter.name}: {' '.join(command)}", file=sys.stderr)
                    return code
        a_items = read_jsonl(a / ITEMS_REL)
        if not any("discrete_subparts" in (i.get("flags") or []) for i in a_items):
            print("selftest failed: expected discrete_subparts flag", file=sys.stderr)
            return 1
        if not any("contention_interrogatory" in (i.get("flags") or []) for i in a_items):
            print("selftest failed: expected contention_interrogatory flag", file=sys.stderr)
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
        if "ROG-001" in a_pkg:
            print("selftest failed: Bates-like ROG-001 in package", file=sys.stderr)
            return 1
        print("PASS: rog-request-audit selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-served-rog", help="parse defense-served ROG set")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_served_rog)

    p = sub.add_parser("audit-incoming-rog", help="audit served ROGs against jurisdiction pack")
    p.add_argument("matter_dir")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_audit_incoming_rog)

    p = sub.add_parser("package-incoming-rog-audit", help="write audit report markdown")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package)

    p = sub.add_parser("validate-incoming-rog-audit", help="run Slice D3 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("selftest", help="offline synthetic D3 E2E")
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
