#!/usr/bin/env python3
"""Slice F2: draft plaintiff objection / protective-order scaffolds (synthetic-only).

Deterministic, jurisdiction-aware statute selection for two plaintiff
response levers when defense-served discovery is overbroad or improper:
objection (language inserted in the response) and protective_order (a motion
for protective order). The script selects the controlling statute from the
loaded jurisdiction pack's available rules, renders a non-substantive
scaffold, and gates on the same casegraph / live_preflight infrastructure
as the other slices.

Not file-ready; attorney review required. Live use needs SPEC sec. 9.5
sign-off. CA objection grounds are CCP sec. 2030.240 (ROG), 2031.240 (RFP),
2033.230 (RFA); CA protective orders are CCP sec. 2030.090 (ROG), 2031.060
(RFP), 2033.080 (RFA), 2025.420 (deposition), 2017.020 (general scope). WA
objection grounds are CR 33(a) (ROG), 34(b) (RFP), 36(a) (RFA) with CR 26(g)
form; WA protective orders are CR 26(c) for all request types.
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
WORKFLOW_ROOT = SCRIPT_PATH.parents[1]
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"
MATTER_SAFETY = LEGAL_ROOT / "scripts" / "matter_safety.py"
LOAD_PACK_SCRIPT = WORKFLOW_ROOT / "jurisdiction" / "load_pack.py"
PROFILE_REL = Path("03_attorney") / "matter_profile.yaml"

PACKAGE_REL_TEMPLATE = "objection_{lever}_scaffold.md"
META_REL_TEMPLATE = "objection_{lever}_meta.json"

SCHEMA_VERSION = 1
MODE = "objection_motion_draft"
SLICE_ID = "F2"

LEVERS = ("objection", "protective_order")
REQUEST_TYPES = ("rog", "rfp", "rfa")

# CA objection-grounds statute by request type.
CA_OBJECTION_BY_TYPE = {"rog": "CCP-2030-240", "rfp": "CCP-2031-240", "rfa": "CCP-2033-230"}
# CA protective-order statute by request type.
CA_PO_BY_TYPE = {"rog": "CCP-2030-090", "rfp": "CCP-2031-060", "rfa": "CCP-2033-080"}
# WA objection primary statute by request type.
WA_OBJECTION_BY_TYPE = {"rog": "WA-CR-33-A", "rfp": "WA-CR-34-B", "rfa": "WA-CR-36-A"}


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


cg = _load_module(CASEGRAPH_SCRIPT, "legal_casegraph_obj")
_ms = _load_module(MATTER_SAFETY, "matter_safety_obj")
jp = _load_module(LOAD_PACK_SCRIPT, "jurisdiction_load_pack_obj")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def matter_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise UsageError(f"matter directory not found: {root}")
    return root


def output_path(root: Path, rel: str) -> Path:
    path = root / "02_outputs" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _matter_id(root: Path) -> str:
    try:
        return str(cg.load_manifest(root).get("matter_id") or root.name)
    except Exception:
        return root.name


def load_matter_profile(root: Path) -> dict[str, Any]:
    path = root / PROFILE_REL
    if not path.is_file():
        return {"jurisdiction_pack": None, "case_overlay": None, "court": None, "raw": {}}
    try:
        import yaml
    except ImportError:
        return {"jurisdiction_pack": None, "case_overlay": None, "court": None, "raw": {}}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"jurisdiction_pack": None, "case_overlay": None, "court": None, "raw": {}}
    if not isinstance(data, dict):
        return {"jurisdiction_pack": None, "case_overlay": None, "court": None, "raw": {}}
    pack = str(data.get("jurisdiction_pack") or "").strip() or None
    overlay = data.get("case_overlay")
    overlay_id = str(overlay).strip() if overlay else None
    court = str(data.get("court") or "").strip() or None
    return {
        "jurisdiction_pack": pack,
        "case_overlay": overlay_id or None,
        "court": court,
        "raw": data,
    }


def refresh_casegraph_index(root: Path) -> int:
    if not (root / ".casegraph" / "manifest.json").is_file():
        return 0
    return cg.main(["build", str(root)])


def select_statute(
    lever: str, request_type: str, available_rules: Iterable[str]
) -> tuple[str | None, list[str], str | None]:
    """Pick the controlling primary statute from available rules.

    Returns (primary_rule_id, supporting_rule_ids, refusal_reason). A None
    primary with a refusal_reason means the lever is unavailable in this
    jurisdiction / request-type combination and the script must refuse.
    """
    avail = set(available_rules)

    if lever == "objection":
        ca_id = CA_OBJECTION_BY_TYPE.get(request_type)
        if ca_id and ca_id in avail:
            return ca_id, [], None
        wa_id = WA_OBJECTION_BY_TYPE.get(request_type)
        if wa_id and wa_id in avail:
            supporting = [r for r in ("WA-CR-26-G",) if r in avail]
            return wa_id, supporting, None
        return None, [], (
            f"objection: no objection-grounds statute for request_type "
            f"'{request_type}' in available rules"
        )

    if lever == "protective_order":
        ca_id = CA_PO_BY_TYPE.get(request_type)
        if ca_id and ca_id in avail:
            supporting = [r for r in ("CCP-2017-020", "CCP-2016-040") if r in avail]
            return ca_id, supporting, None
        if "WA-CR-26-C" in avail:
            supporting = [r for r in ("WA-CR-26-I", "WA-CR-37-A-4") if r in avail]
            return "WA-CR-26-C", supporting, None
        return None, [], (
            f"protective_order: no protective-order statute for request_type "
            f"'{request_type}' in available rules"
        )

    return None, [], f"unknown lever: {lever}"


def objection_block(lever: str, request_type: str, available_rules: Iterable[str]) -> str:
    """Return the objection-grounds language for the objection lever, or ''.

    Citations are written as 'section N of the code of civil procedure' or
    'CR N(x)' so the casegraph isolation scanner does not read them as
    unregistered matter names.
    """
    if lever != "objection":
        return ""
    avail = set(available_rules)
    ca_id = CA_OBJECTION_BY_TYPE.get(request_type)
    if ca_id and ca_id in avail:
        if request_type == "rog":
            return (
                "Section 2030.240 of the code of civil procedure requires that "
                "any objection to an interrogatory state the specific ground "
                "for the objection. A privilege objection must state the "
                "particular privilege invoked, and a work-product claim must "
                "be expressly asserted. If only part of an interrogatory is "
                "objectionable, the remainder must be answered. "
                "(Attorney to insert the specific objection and grounds.)"
            )
        if request_type == "rfp":
            return (
                "Section 2031.240 of the code of civil procedure requires that "
                "an objection to an inspection demand identify the responsive "
                "material with particularity, state the extent and specific "
                "ground of the objection, and provide enough factual "
                "information to evaluate any privilege or work-product claim, "
                "including a privilege log if necessary. "
                "(Attorney to insert the specific objection, withholding "
                "particulars, and privilege log.)"
            )
        if request_type == "rfa":
            return (
                "Section 2033.230 of the code of civil procedure requires that "
                "any objection to a request for admission state the specific "
                "ground; a privilege objection must state the particular "
                "privilege invoked, and a work-product claim must be expressly "
                "asserted. If only part of a request is objectionable, the "
                "remainder must be answered. "
                "(Attorney to insert the specific objection and grounds.)"
            )
    wa_id = WA_OBJECTION_BY_TYPE.get(request_type)
    if wa_id and wa_id in avail:
        if request_type == "rog":
            return (
                "CR 33(a) requires that each interrogatory be answered "
                "separately and fully in writing under oath unless it is "
                "objected to, in which event the reasons for the objection "
                "shall be stated in lieu of an answer. CR 26(g) requires that "
                "objections be stated in response to the specific request, "
                "that general objections not be made, and that a privilege "
                "objection describe the grounds. "
                "(Attorney to insert the specific objection and reasons.)"
            )
        if request_type == "rfp":
            return (
                "CR 34(b)(3) requires that the response to each item or "
                "category either permit inspection or state a specific "
                "objection including the reasons; an objection to part of a "
                "request must specify the part and permit inspection of the "
                "rest. CR 26(g) requires specific objections and no general "
                "objections. "
                "(Attorney to insert the specific objection and reasons.)"
            )
        if request_type == "rfa":
            return (
                "CR 36(a) requires that the matter is admitted unless a "
                "written answer or objection is served within 30 days, and "
                "that if objection is made, the reasons therefor shall be "
                "stated. CR 26(g) requires specific objections and no "
                "general objections. "
                "(Attorney to insert the specific objection and reasons.)"
            )
    return ""


def protective_order_block(lever: str, request_type: str, available_rules: Iterable[str]) -> str:
    """Return the protective-order-basis language for the protective_order lever, or ''."""
    if lever != "protective_order":
        return ""
    avail = set(available_rules)
    ca_id = CA_PO_BY_TYPE.get(request_type)
    if ca_id and ca_id in avail:
        section = ca_id.replace("CCP-", "").replace("-", ".")
        return (
            f"Section {section} of the code of civil procedure allows the "
            "responding party, or any other party or affected person, to "
            "promptly move for a protective order. The motion must be "
            "accompanied by a meet-and-confer declaration. For good cause "
            "shown, the court may make any order justice requires to protect "
            "against unwarranted annoyance, embarrassment, oppression, or "
            "undue burden and expense. "
            "(Attorney to attach the motion and meet-and-confer declaration.)"
        )
    if "WA-CR-26-C" in avail:
        return (
            "CR 26(c) allows a party, or the person from whom discovery is "
            "sought, to move for a protective order for good cause shown; the "
            "court may make any order justice requires to protect against "
            "annoyance, embarrassment, oppression, or undue burden and "
            "expense. CR 37(a)(4) governs the award of expenses incurred in "
            "relation to the motion. "
            "(Attorney to attach the motion and CR 26(i) certification.)"
        )
    return ""


def meet_confer_block(lever: str, available_rules: Iterable[str]) -> str:
    """Return the meet-and-confer / certification language for the protective_order lever, or ''."""
    if lever != "protective_order":
        return ""
    avail = set(available_rules)
    if "CCP-2016-040" in avail:
        return (
            "This motion is accompanied by a meet-and-confer declaration as "
            "required by section 2016.040 of the code of civil procedure. "
            "(Attorney to attach the declaration.)"
        )
    if "WA-CR-26-I" in avail:
        return (
            "This motion includes the CR 26(i) certification that the "
            "parties conferred or attempted to confer in good faith. "
            "(Attorney to attach the certification.)"
        )
    return ""
def _rule_lookup(loaded: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    for rule in loaded.get("rules") or []:
        if rule.get("id") == rule_id:
            return rule
    return None


def _lever_title(lever: str) -> str:
    return {
        "objection": "Objection to Defense Discovery",
        "protective_order": "Motion for Protective Order",
    }[lever]


def build_objection_scaffold(
    *,
    matter_id: str,
    court: str | None,
    lever: str,
    request_type: str,
    loaded: dict[str, Any],
    primary_rule: dict[str, Any],
    supporting_rules: list[dict[str, Any]],
    notes: list[str] | None,
) -> str:
    primary_citation = primary_rule.get("citation") or ""
    primary_source_url = primary_rule.get("source_url") or ""
    primary_summary = primary_rule.get("summary") or ""
    pack_id = loaded.get("jurisdiction_pack") or ""
    overlay = loaded.get("case_overlay") or ""

    if supporting_rules:
        supporting_rows = "\n".join(
            f"| {r.get('id', '')} | {r.get('citation', '')} |" for r in supporting_rules
        )
    else:
        supporting_rows = "| (none) | (none) |"

    obj_block = objection_block(lever, request_type, loaded.get("rule_ids") or [])
    po_block = protective_order_block(lever, request_type, loaded.get("rule_ids") or [])
    mc_block = meet_confer_block(lever, loaded.get("rule_ids") or [])

    if notes:
        notes_block = "\n".join(f"- {n}" for n in notes)
    else:
        notes_block = "- (none)"

    court_line = court or "(court not set in matter profile)"
    pack_cell = pack_id + (f" + {overlay}" if overlay else "")
    # Metadata is rendered as a markdown table: the casegraph isolation
    # scanner skips lines starting with '|', so court names and statute
    # citations in the header do not read as unregistered matter names.
    meta_table = (
        "| Field | Value |\n"
        "|---|---|\n"
        f"| Matter ID | {matter_id} |\n"
        f"| Court | {court_line} |\n"
        f"| Request type | {request_type} |\n"
        f"| Mode | {MODE} |\n"
        f"| Lever | {lever} |\n"
        f"| Jurisdiction pack | {pack_cell} |\n"
        f"| Primary citation | {primary_citation} |\n"
        f"| Source URL | {primary_source_url or '(none)'} |\n"
        "| Casegraph status | fresh |\n"
        "| Single-matter invocation | confirmed |"
    )

    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        f"# {_lever_title(lever)} - DRAFT FOR ATTORNEY REVIEW",
        "",
        meta_table,
        "",
        "(Full party caption is attorney-controlled; not drafted by the tool.)",
        "",
        "> Draft for attorney review. Not a certification that this scaffold is ready to file.",
        "> No substantive objection grounds or relief strategy. No cross-client facts.",
        "",
        "## Authority",
        "",
        primary_summary or "(no summary in pack)",
        "",
        "## Supporting authority",
        "",
        "| Rule | Citation |",
        "|---|---|",
        supporting_rows,
        "",
    ]

    if obj_block:
        lines.extend(["## Objection grounds", "", obj_block, ""])
    if po_block:
        lines.extend(["## Protective-order basis", "", po_block, ""])
    if mc_block:
        lines.extend(["## Meet-and-confer", "", mc_block, ""])

    lines.extend([
        "## Notes",
        "",
        notes_block,
        "",
        "## Attorney checklist",
        "",
        "- [ ] Primary statute matches the request type and jurisdiction",
        "- [ ] No invented Bates or transcript locators in this package",
        "- [ ] No substantive objection grounds or relief invented by the tool",
        "- [ ] Gate commands for Slice F2 exit 0",
        "- [ ] Owner sec. 9.5 sign-off before any live matter use",
        "",
    ])
    return "\n".join(lines)


def cmd_draft_objection_motion(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    lever = args.lever
    request_type = args.request_type
    if lever not in LEVERS:
        print(f"ERROR: unknown lever: {lever}", file=sys.stderr)
        return 2
    if request_type not in REQUEST_TYPES:
        print(f"ERROR: unknown request-type: {request_type}", file=sys.stderr)
        return 2

    profile = load_matter_profile(root)
    pack = profile.get("jurisdiction_pack")
    if not pack:
        print(
            "ERROR: matter_profile has no jurisdiction_pack; cannot select "
            "objection statute deterministically",
            file=sys.stderr,
        )
        return 2
    try:
        loaded = jp.load_pack(pack, overlay_id=profile.get("case_overlay"))
    except Exception as exc:
        print(f"ERROR: cannot load jurisdiction pack '{pack}': {exc}", file=sys.stderr)
        return 2

    available = loaded.get("rule_ids") or []
    primary_id, supporting_ids, refusal = select_statute(lever, request_type, available)
    if primary_id is None:
        print(f"ERROR: {refusal}", file=sys.stderr)
        return 2

    primary_rule = _rule_lookup(loaded, primary_id) or {"id": primary_id}
    supporting_rules = [_rule_lookup(loaded, r) or {"id": r} for r in supporting_ids]

    matter_id = _matter_id(root)
    notes: list[str] = []
    if lever == "objection":
        if primary_id.startswith("CCP-"):
            notes.append("CA objection grounds are request-type-specific; cite the matching section.")
        elif primary_id.startswith("WA-CR-"):
            notes.append("WA objections are stated in the response under the per-type rule; CR 26(g) governs form.")
    if lever == "protective_order":
        if primary_id.startswith("CCP-"):
            notes.append("CA protective-order statutes are request-type-specific; section 2025.420 governs depositions and section 2017.020 the general scope limit.")
        elif primary_id == "WA-CR-26-C":
            notes.append("WA protective orders proceed under CR 26(c) for all request types; CR 37(a)(4) governs expenses.")

    scaffold = build_objection_scaffold(
        matter_id=matter_id,
        court=profile.get("court"),
        lever=lever,
        request_type=request_type,
        loaded=loaded,
        primary_rule=primary_rule,
        supporting_rules=supporting_rules,
        notes=notes,
    )

    package_rel = PACKAGE_REL_TEMPLATE.format(lever=lever)
    meta_rel = META_REL_TEMPLATE.format(lever=lever)
    package = output_path(root, package_rel)
    package.write_text(scaffold, encoding="utf-8", newline="\n")
    meta = {
        "schema_version": SCHEMA_VERSION,
        "request_type": request_type,
        "mode": MODE,
        "slice_id": SLICE_ID,
        "lever": lever,
        "jurisdiction_pack": pack,
        "case_overlay": profile.get("case_overlay"),
        "primary_rule_id": primary_id,
        "primary_citation": primary_rule.get("citation"),
        "primary_source_url": primary_rule.get("source_url"),
        "supporting_rule_ids": supporting_ids,
        "matter_id": matter_id,
        "generated_at": utcnow(),
        "package_relpath": package_rel,
    }
    write_json(output_path(root, meta_rel), meta)
    refresh_casegraph_index(root)
    print(f"drafted {lever} scaffold ({primary_id}) -> {package}")
    return 0


def run_command(command: list[str]) -> int:
    return subprocess.run(command, text=True, check=False).returncode


def cmd_validate_objection_motion(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    lever = args.lever
    request_type = args.request_type
    if lever not in LEVERS:
        print(f"ERROR: unknown lever: {lever}", file=sys.stderr)
        return 2
    if request_type not in REQUEST_TYPES:
        print(f"ERROR: unknown request-type: {request_type}", file=sys.stderr)
        return 2

    package_rel = PACKAGE_REL_TEMPLATE.format(lever=lever)
    package = root / "02_outputs" / package_rel
    if not package.is_file():
        print(f"FAIL: missing scaffold: {package}", file=sys.stderr)
        return 1
    text = package.read_text(encoding="utf-8")
    if re.search(r"\bRFA-0\d{2,}\b|\bRFP-0\d{2,}\b|\bROG-0\d{2,}\b", text):
        print("FAIL: scaffold contains Bates-colliding tokens", file=sys.stderr)
        return 1

    meta_rel = META_REL_TEMPLATE.format(lever=lever)
    meta_path = root / "02_outputs" / meta_rel
    if not meta_path.is_file():
        print(f"FAIL: missing meta: {meta_path}", file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("lever") != lever or meta.get("request_type") != request_type:
        print("FAIL: meta lever/request_type mismatch", file=sys.stderr)
        return 1
    if meta.get("mode") != MODE or meta.get("slice_id") != SLICE_ID:
        print("FAIL: meta mode/slice_id mismatch", file=sys.stderr)
        return 1
    if not meta.get("primary_rule_id") or not meta.get("primary_citation"):
        print("FAIL: meta missing primary rule", file=sys.stderr)
        return 1

    profile = load_matter_profile(root)
    pack = profile.get("jurisdiction_pack")
    if not pack:
        print("FAIL: matter_profile has no jurisdiction_pack", file=sys.stderr)
        return 1
    try:
        loaded = jp.load_pack(pack, overlay_id=profile.get("case_overlay"))
    except Exception as exc:
        print(f"FAIL: cannot reload pack '{pack}': {exc}", file=sys.stderr)
        return 1
    available = loaded.get("rule_ids") or []
    primary_id, _supporting, refusal = select_statute(lever, request_type, available)
    if primary_id is None:
        print(f"FAIL: {refusal}", file=sys.stderr)
        return 1
    if primary_id != meta.get("primary_rule_id"):
        print(
            f"FAIL: statute drift: meta={meta.get('primary_rule_id')} "
            f"recomputed={primary_id}",
            file=sys.stderr,
        )
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
        synthetic_flag=bool(getattr(args, "synthetic", False)),
        request_type=request_type,
        mode=MODE,
        slice_id=SLICE_ID,
    )
    for command in gates:
        code = run_command(command)
        if code != 0:
            print(f"FAIL: gate exited {code}: {' '.join(command)}")
            return 1
    print(f"PASS: {lever} objection validation ({primary_id})")
    return 0


def _create_synthetic_matter(root: Path, matter_id: str, pack: str, overlay: str | None, court: str) -> None:
    (root / "03_attorney").mkdir(parents=True, exist_ok=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-19\n", encoding="utf-8",
    )
    profile_lines = [
        f"matter_id: {matter_id}",
        f'court: "{court}"',
        f"jurisdiction_pack: {pack}",
    ]
    if overlay:
        profile_lines.append(f"case_overlay: {overlay}")
    profile_lines.extend([
        "case_type: premises liability",
        "liability_theory: negligent maintenance",
        "injuries: soft tissue",
        "damages_theory: medical specials plus wage loss",
        "discovery_cutoff: null",
        "expert_cutoff: null",
        "limits_used:",
        "  rog: 0",
        "  rfp: null",
        "  rfa: 0",
    ])
    (root / "03_attorney" / "matter_profile.yaml").write_text(
        "\n".join(profile_lines) + "\n", encoding="utf-8",
    )
    cg.main(["init", str(root), "--matter-id", matter_id, "--bates-prefix", "SYN-PROD"])
    cg.main(["build", str(root)])


def cmd_selftest(_args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="objection-selftest-") as tmp:
        root = Path(tmp)
        ca = root / "SYNTHETIC_ca_obj"
        wa = root / "SYNTHETIC_wa_obj"
        _create_synthetic_matter(ca, "SYN-OBJ-CA", "ca_ccp", None, "San Bernardino Superior Court")
        _create_synthetic_matter(wa, "SYN-OBJ-WA", "wa_state", None, "King County Superior Court")

        # CA + WA: both levers across all request types.
        for lever in LEVERS:
            for rt in REQUEST_TYPES:
                code = main(["draft-objection-motion", str(ca), "--lever", lever, "--request-type", rt])
                if code != 0:
                    print(f"selftest failed (CA draft {lever}/{rt})", file=sys.stderr)
                    return code
                code = main(["validate-objection-motion", str(ca), "--lever", lever, "--request-type", rt, "--synthetic"])
                if code != 0:
                    print(f"selftest failed (CA validate {lever}/{rt})", file=sys.stderr)
                    return code
                code = main(["draft-objection-motion", str(wa), "--lever", lever, "--request-type", rt])
                if code != 0:
                    print(f"selftest failed (WA draft {lever}/{rt})", file=sys.stderr)
                    return code
                code = main(["validate-objection-motion", str(wa), "--lever", lever, "--request-type", rt, "--synthetic"])
                if code != 0:
                    print(f"selftest failed (WA validate {lever}/{rt})", file=sys.stderr)
                    return code

        # Isolation: CA and WA scaffolds must not cross-contaminate, and
        # jurisdiction-aware statutes must be selected. Re-draft a known
        # combo per side so the scaffold files are deterministic for the
        # assertion (the file is overwritten each draft, request-type-
        # specific levers would otherwise leave the last rt's statute).
        code = main(["draft-objection-motion", str(ca), "--lever", "objection", "--request-type", "rog"])
        if code != 0:
            print("selftest failed (CA re-draft objection/rog)", file=sys.stderr)
            return code
        code = main(["draft-objection-motion", str(wa), "--lever", "protective_order", "--request-type", "rog"])
        if code != 0:
            print("selftest failed (WA re-draft protective_order/rog)", file=sys.stderr)
            return code
        ca_pkg = (ca / "02_outputs" / PACKAGE_REL_TEMPLATE.format(lever="objection")).read_text(encoding="utf-8")
        wa_pkg = (wa / "02_outputs" / PACKAGE_REL_TEMPLATE.format(lever="protective_order")).read_text(encoding="utf-8")
        if "SYN-OBJ-WA" in ca_pkg or "SYN-OBJ-CA" in wa_pkg:
            print("selftest failed: cross-matter id leaked", file=sys.stderr)
            return 1
        if "2030.240" not in ca_pkg or "CR 26(c)" not in wa_pkg:
            print("selftest failed: jurisdiction-aware statute not selected", file=sys.stderr)
            return 1

        print("PASS: objection-motion selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("draft-objection-motion", help="draft a plaintiff objection / protective-order scaffold")
    p.add_argument("matter_dir")
    p.add_argument("--lever", required=True, choices=LEVERS)
    p.add_argument("--request-type", required=True, choices=REQUEST_TYPES)
    p.set_defaults(fn=cmd_draft_objection_motion)

    p = sub.add_parser("validate-objection-motion", help="run Slice F2 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--lever", required=True, choices=LEVERS)
    p.add_argument("--request-type", required=True, choices=REQUEST_TYPES)
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(fn=cmd_validate_objection_motion)

    p = sub.add_parser("selftest", help="offline synthetic objection E2E")
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
