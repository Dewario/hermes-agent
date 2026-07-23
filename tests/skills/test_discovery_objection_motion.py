"""Synthetic tests for Slice F2 plaintiff objection / protective-order drafting."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "objection_motion.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


obj = _load(SCRIPT, "objection_motion")
cg = _load(CASEGRAPH, "casegraph_for_objection_tests")


def _matter(
    tmp_path: Path,
    matter_id: str = "SYN-OBJ-CA",
    pack: str = "ca_ccp",
    court: str = "San Bernardino Superior Court",
) -> Path:
    matter = tmp_path / matter_id
    (matter / "03_attorney").mkdir(parents=True, exist_ok=True)
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (matter / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-19\n", encoding="utf-8",
    )
    profile = [
        f"matter_id: {matter_id}",
        f'court: "{court}"',
        f"jurisdiction_pack: {pack}",
        "case_type: premises liability",
        "limits_used:",
        "  rog: 0",
        "  rfp: null",
        "  rfa: 0",
    ]
    (matter / "03_attorney" / "matter_profile.yaml").write_text(
        "\n".join(profile) + "\n", encoding="utf-8",
    )
    assert cg.main(["init", str(matter), "--matter-id", matter_id, "--bates-prefix", "SYN-PROD"]) == 0
    assert cg.main(["build", str(matter)]) == 0
    return matter


CA_RULES = {
    "CCP-2030-240", "CCP-2031-240", "CCP-2033-230",
    "CCP-2030-090", "CCP-2031-060", "CCP-2033-080", "CCP-2025-420",
    "CCP-2017-020", "CCP-2016-040",
}
WA_RULES = {
    "WA-CR-33-A", "WA-CR-34-B", "WA-CR-36-A", "WA-CR-26-G",
    "WA-CR-26-C", "WA-CR-26-I", "WA-CR-37-A-4",
}


def test_select_statute_ca_objection_by_type():
    assert obj.select_statute("objection", "rog", CA_RULES)[0] == "CCP-2030-240"
    assert obj.select_statute("objection", "rfp", CA_RULES)[0] == "CCP-2031-240"
    assert obj.select_statute("objection", "rfa", CA_RULES)[0] == "CCP-2033-230"


def test_select_statute_wa_objection_by_type():
    assert obj.select_statute("objection", "rog", WA_RULES)[0] == "WA-CR-33-A"
    assert obj.select_statute("objection", "rfp", WA_RULES)[0] == "WA-CR-34-B"
    assert obj.select_statute("objection", "rfa", WA_RULES)[0] == "WA-CR-36-A"
    primary, supporting, refusal = obj.select_statute("objection", "rog", WA_RULES)
    assert supporting == ["WA-CR-26-G"]
    assert refusal is None


def test_select_statute_ca_protective_order_by_type():
    assert obj.select_statute("protective_order", "rog", CA_RULES)[0] == "CCP-2030-090"
    assert obj.select_statute("protective_order", "rfp", CA_RULES)[0] == "CCP-2031-060"
    assert obj.select_statute("protective_order", "rfa", CA_RULES)[0] == "CCP-2033-080"
    primary, supporting, refusal = obj.select_statute("protective_order", "rog", CA_RULES)
    assert "CCP-2017-020" in supporting
    assert "CCP-2016-040" in supporting
    assert refusal is None


def test_select_statute_wa_protective_order_uniform():
    for rt in ("rog", "rfp", "rfa"):
        primary, supporting, refusal = obj.select_statute("protective_order", rt, WA_RULES)
        assert primary == "WA-CR-26-C"
        assert "WA-CR-26-I" in supporting
        assert "WA-CR-37-A-4" in supporting
        assert refusal is None


def test_select_statute_refuses_empty_rules():
    primary, _supporting, refusal = obj.select_statute("objection", "rfa", set())
    assert primary is None
    assert refusal


def test_select_statute_refuses_unknown_lever():
    primary, _supporting, refusal = obj.select_statute("bogus", "rfa", CA_RULES)
    assert primary is None
    assert "unknown lever" in refusal


def _draft_and_validate(matter: Path, lever: str, request_type: str) -> dict:
    assert obj.main(["draft-objection-motion", str(matter), "--lever", lever, "--request-type", request_type]) == 0
    assert obj.main([
        "validate-objection-motion", str(matter), "--lever", lever,
        "--request-type", request_type, "--synthetic",
    ]) == 0
    meta_path = matter / "02_outputs" / obj.META_REL_TEMPLATE.format(lever=lever)
    return json.loads(meta_path.read_text(encoding="utf-8"))


def test_ca_draft_and_validate_all_levers(tmp_path):
    matter = _matter(tmp_path)
    seen = set()
    for lever in ("objection", "protective_order"):
        for rt in ("rog", "rfp", "rfa"):
            meta = _draft_and_validate(matter, lever, rt)
            assert meta["lever"] == lever
            assert meta["request_type"] == rt
            assert meta["mode"] == "objection_motion_draft"
            assert meta["slice_id"] == "F2"
            assert meta["primary_rule_id"]
            assert meta["primary_citation"]
            seen.add(meta["primary_rule_id"])
    assert "CCP-2030-240" in seen
    assert "CCP-2031-240" in seen
    assert "CCP-2033-230" in seen
    assert "CCP-2030-090" in seen
    assert "CCP-2031-060" in seen
    assert "CCP-2033-080" in seen


def test_wa_draft_and_validate_all_levers(tmp_path):
    matter = _matter(tmp_path, matter_id="SYN-OBJ-WA", pack="wa_state", court="King County Superior Court")
    for lever in ("objection", "protective_order"):
        for rt in ("rog", "rfp", "rfa"):
            meta = _draft_and_validate(matter, lever, rt)
            assert meta["primary_rule_id"].startswith("WA-CR-")
    obj_meta = json.loads(
        (matter / "02_outputs" / obj.META_REL_TEMPLATE.format(lever="objection")).read_text(encoding="utf-8")
    )
    assert obj_meta["primary_rule_id"] in {"WA-CR-33-A", "WA-CR-34-B", "WA-CR-36-A"}
    po_meta = json.loads(
        (matter / "02_outputs" / obj.META_REL_TEMPLATE.format(lever="protective_order")).read_text(encoding="utf-8")
    )
    assert po_meta["primary_rule_id"] == "WA-CR-26-C"
    assert "WA-CR-26-I" in po_meta["supporting_rule_ids"]
    assert "WA-CR-37-A-4" in po_meta["supporting_rule_ids"]


def test_ca_objection_uses_correct_statute(tmp_path):
    matter = _matter(tmp_path)
    _draft_and_validate(matter, "objection", "rog")
    pkg = (matter / "02_outputs" / obj.PACKAGE_REL_TEMPLATE.format(lever="objection")).read_text(encoding="utf-8")
    assert "Cal. Code Civ. Proc. sec. 2030.240" in pkg
    assert "2030.240" in pkg


def test_wa_protective_order_uses_cr26c(tmp_path):
    matter = _matter(tmp_path, matter_id="SYN-OBJ-WA2", pack="wa_state", court="Pierce County Superior Court")
    _draft_and_validate(matter, "protective_order", "rfa")
    pkg = (matter / "02_outputs" / obj.PACKAGE_REL_TEMPLATE.format(lever="protective_order")).read_text(encoding="utf-8")
    assert "Wash. Super. Ct. Civ. R. 26(c)" in pkg
    assert "CR 26(c)" in pkg
    assert "CR 37(a)(4)" in pkg


def test_scaffold_does_not_sign_owner_gate(tmp_path):
    matter = _matter(tmp_path)
    _draft_and_validate(matter, "protective_order", "rfa")
    pkg = (matter / "02_outputs" / obj.PACKAGE_REL_TEMPLATE.format(lever="protective_order")).read_text(encoding="utf-8")
    assert "| Field | Value |" in pkg
    assert "| Rule | Citation |" in pkg
    assert "DRAFT FOR ATTORNEY REVIEW" in pkg
    assert "owner_signature" not in pkg.lower()
    assert "9.5" in pkg
    assert "- [x]" not in pkg  # no pre-checked §9.5 boxes


def test_isolation_no_cross_matter_leak(tmp_path):
    a = _matter(tmp_path, "SYN-OBJ-CA", "ca_ccp", "San Bernardino Superior Court")
    b = _matter(tmp_path, "SYN-OBJ-WA", "wa_state", "King County Superior Court")
    _draft_and_validate(a, "protective_order", "rfa")
    _draft_and_validate(b, "protective_order", "rfa")
    a_pkg = (a / "02_outputs" / obj.PACKAGE_REL_TEMPLATE.format(lever="protective_order")).read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / obj.PACKAGE_REL_TEMPLATE.format(lever="protective_order")).read_text(encoding="utf-8")
    assert "SYN-OBJ-WA" not in a_pkg
    assert "SYN-OBJ-CA" not in b_pkg
    assert "2033.080" in a_pkg
    assert "Wash. Super. Ct. Civ. R. 26(c)" in b_pkg


def test_live_mode_enforces_owner_gate(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    assert obj.main([
        "draft-objection-motion", str(matter), "--lever", "protective_order", "--request-type", "rfa",
    ]) == 0
    (matter / ".synthetic").unlink()
    captured: list[list[str]] = []
    original = obj.run_command

    def _capture(command):
        captured.append(list(command))
        if "live_preflight.py" in " ".join(command):
            return 1
        return original(command)

    monkeypatch.setattr(obj, "run_command", _capture)
    code = obj.main([
        "validate-objection-motion", str(matter), "--lever", "protective_order", "--request-type", "rfa",
    ])
    assert code != 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--slice" in preflight
    assert "F2" in preflight
    assert "--mode" in preflight
    assert "objection_motion_draft" in preflight


def test_selftest():
    assert obj.main(["selftest"]) == 0
