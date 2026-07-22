"""Synthetic tests for Slice F1 plaintiff enforcement-lever drafting."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "enforcement_motion.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


enf = _load(SCRIPT, "enforcement_motion")
cg = _load(CASEGRAPH, "casegraph_for_enforcement_tests")


def _matter(
    tmp_path: Path,
    matter_id: str = "SYN-ENF-CA",
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
    "CCP-2033-280", "CCP-2033-290", "CCP-2030-300", "CCP-2031-310",
    "CCP-2016-040", "CCP-2023-010", "CCP-2023-050",
}
WA_RULES = {"WA-CR-36-A", "WA-CR-36-B", "WA-CR-37-A", "WA-CR-37-A-4", "WA-CR-26-I"}


def test_select_statute_ca_deemed_admitted_rfa_only():
    primary, supporting, refusal = enf.select_statute("deemed_admitted", "rfa", CA_RULES)
    assert primary == "CCP-2033-280"
    assert supporting == []
    assert refusal is None


def test_select_statute_deemed_admitted_refuses_non_rfa():
    primary, _supporting, refusal = enf.select_statute("deemed_admitted", "rog", CA_RULES)
    assert primary is None
    assert "RFA-only" in refusal


def test_select_statute_deemed_admitted_accepts_wa():
    primary, supporting, refusal = enf.select_statute("deemed_admitted", "rfa", WA_RULES)
    assert primary == "WA-CR-36-A"
    assert supporting == ["WA-CR-36-B"]
    assert refusal is None


def test_select_statute_ca_motion_to_compel_by_type():
    assert enf.select_statute("motion_to_compel", "rog", CA_RULES)[0] == "CCP-2030-300"
    assert enf.select_statute("motion_to_compel", "rfp", CA_RULES)[0] == "CCP-2031-310"
    assert enf.select_statute("motion_to_compel", "rfa", CA_RULES)[0] == "CCP-2033-290"


def test_select_statute_wa_motion_to_compel_by_type():
    for rt in ("rog", "rfp"):
        assert enf.select_statute("motion_to_compel", rt, WA_RULES)[0] == "WA-CR-37-A"
    primary, supporting, refusal = enf.select_statute("motion_to_compel", "rfa", WA_RULES)
    assert primary == "WA-CR-36-A"
    assert supporting == ["WA-CR-37-A-4"]
    assert refusal is None


def test_select_statute_meet_and_confer_jurisdiction_aware():
    assert enf.select_statute("meet_and_confer_letter", "rfa", CA_RULES)[0] == "CCP-2016-040"
    assert enf.select_statute("meet_and_confer_letter", "rfa", WA_RULES)[0] == "WA-CR-26-I"


def test_select_statute_sanctions_jurisdiction_aware():
    primary, supporting, refusal = enf.select_statute("sanctions", "rfa", CA_RULES)
    assert primary == "CCP-2023-050"
    assert "CCP-2023-010" in supporting
    assert enf.select_statute("sanctions", "rfa", WA_RULES)[0] == "WA-CR-37-A-4"
    assert refusal is None


def test_select_statute_refuses_empty_rules():
    primary, _supporting, refusal = enf.select_statute("motion_to_compel", "rfa", set())
    assert primary is None
    assert refusal


def _draft_and_validate(matter: Path, lever: str, request_type: str) -> dict:
    assert enf.main(["draft-enforcement-motion", str(matter), "--lever", lever, "--request-type", request_type]) == 0
    assert enf.main([
        "validate-enforcement-motion", str(matter), "--lever", lever,
        "--request-type", request_type, "--synthetic",
    ]) == 0
    meta_path = matter / "02_outputs" / enf.META_REL_TEMPLATE.format(lever=lever)
    return json.loads(meta_path.read_text(encoding="utf-8"))


def test_ca_draft_and_validate_all_levers(tmp_path):
    matter = _matter(tmp_path)
    cases = [
        ("deemed_admitted", "rfa"),
        ("motion_to_compel", "rog"),
        ("motion_to_compel", "rfp"),
        ("motion_to_compel", "rfa"),
        ("meet_and_confer_letter", "rfa"),
        ("sanctions", "rfa"),
    ]
    seen_statutes = set()
    for lever, rt in cases:
        meta = _draft_and_validate(matter, lever, rt)
        assert meta["lever"] == lever
        assert meta["request_type"] == rt
        assert meta["mode"] == "enforcement_motion_draft"
        assert meta["slice_id"] == "F1"
        assert meta["primary_rule_id"]
        assert meta["primary_citation"]
        seen_statutes.add(meta["primary_rule_id"])
    assert "CCP-2033-280" in seen_statutes
    assert "CCP-2030-300" in seen_statutes
    assert "CCP-2031-310" in seen_statutes
    assert "CCP-2033-290" in seen_statutes
    assert "CCP-2016-040" in seen_statutes
    assert "CCP-2023-050" in seen_statutes


def test_wa_draft_and_validate_all_rfa_levers(tmp_path):
    matter = _matter(tmp_path, matter_id="SYN-ENF-WA", pack="wa_state", court="King County Superior Court")
    for lever in ("deemed_admitted", "motion_to_compel", "meet_and_confer_letter", "sanctions"):
        meta = _draft_and_validate(matter, lever, "rfa")
        assert meta["primary_rule_id"].startswith("WA-CR-")
    mtc_meta = json.loads(
        (matter / "02_outputs" / enf.META_REL_TEMPLATE.format(lever="motion_to_compel")).read_text(
            encoding="utf-8"
        )
    )
    assert mtc_meta["primary_rule_id"] == "WA-CR-36-A"
    assert mtc_meta["supporting_rule_ids"] == ["WA-CR-37-A-4"]
    deemed_meta = json.loads(
        (matter / "02_outputs" / enf.META_REL_TEMPLATE.format(lever="deemed_admitted")).read_text(encoding="utf-8")
    )
    assert deemed_meta["primary_rule_id"] == "WA-CR-36-A"
    assert deemed_meta["supporting_rule_ids"] == ["WA-CR-36-B"]
    sanctions_meta = json.loads(
        (matter / "02_outputs" / enf.META_REL_TEMPLATE.format(lever="sanctions")).read_text(encoding="utf-8")
    )
    assert sanctions_meta["primary_rule_id"] == "WA-CR-37-A-4"


def test_wa_deemed_admitted_uses_cr36(tmp_path):
    matter = _matter(tmp_path, matter_id="SYN-ENF-WA2", pack="wa_state", court="Pierce County Superior Court")
    meta = _draft_and_validate(matter, "deemed_admitted", "rfa")
    assert meta["primary_rule_id"] == "WA-CR-36-A"
    pkg = (matter / "02_outputs" / enf.PACKAGE_REL_TEMPLATE.format(lever="deemed_admitted")).read_text(
        encoding="utf-8"
    )
    assert "Wash. Super. Ct. Civ. R. 36(a)" in pkg
    assert "WA-CR-36-B" in pkg


def test_wa_pack_no_false_deemed_admission_caveat():
    loaded = enf.jp.load_pack("wa_state")
    rules = {rule["id"]: rule for rule in loaded["rules"]}
    assert "WA-CR-37-A-4" in rules
    assert "WA-CR-37-C" not in rules
    assert "no-response deemed-admission statute parallels" not in rules["WA-CR-37-A"]["summary"]


def test_ca_deemed_admitted_refuses_non_rfa(tmp_path):
    matter = _matter(tmp_path)
    code = enf.main([
        "draft-enforcement-motion", str(matter), "--lever", "deemed_admitted", "--request-type", "rog",
    ])
    assert code != 0


def test_scaffold_does_not_sign_owner_gate(tmp_path):
    matter = _matter(tmp_path)
    _draft_and_validate(matter, "sanctions", "rfa")
    pkg = (matter / "02_outputs" / enf.PACKAGE_REL_TEMPLATE.format(lever="sanctions")).read_text(encoding="utf-8")
    assert "| Field | Value |" in pkg
    assert "| Rule | Citation |" in pkg
    assert "**Matter ID:**" not in pkg
    assert "## Caption" not in pkg
    assert "DRAFT FOR ATTORNEY REVIEW" in pkg
    assert "owner_signature" not in pkg.lower()
    assert "sec. 9.5" in pkg.lower() or "§9.5" in pkg.lower() or "9.5" in pkg
    assert "- [x]" not in pkg  # no pre-checked §9.5 boxes


def test_isolation_no_cross_matter_leak(tmp_path):
    a = _matter(tmp_path, "SYN-ENF-CA", "ca_ccp", "San Bernardino Superior Court")
    b = _matter(tmp_path, "SYN-ENF-WA", "wa_state", "King County Superior Court")
    _draft_and_validate(a, "sanctions", "rfa")
    _draft_and_validate(b, "sanctions", "rfa")
    a_pkg = (a / "02_outputs" / enf.PACKAGE_REL_TEMPLATE.format(lever="sanctions")).read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / enf.PACKAGE_REL_TEMPLATE.format(lever="sanctions")).read_text(encoding="utf-8")
    assert "SYN-ENF-WA" not in a_pkg
    assert "SYN-ENF-CA" not in b_pkg
    assert "Wash. Super. Ct. Civ. R. 37(a)(4)" in b_pkg
    assert "2023.050" in a_pkg


def test_live_mode_enforces_owner_gate(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    assert enf.main([
        "draft-enforcement-motion", str(matter), "--lever", "sanctions", "--request-type", "rfa",
    ]) == 0
    (matter / ".synthetic").unlink()
    captured: list[list[str]] = []
    original = enf.run_command

    def _capture(command):
        captured.append(list(command))
        # Simulate the live preflight refusing a live matter without an owner gate.
        if "live_preflight.py" in " ".join(command):
            return 1
        return original(command)

    monkeypatch.setattr(enf, "run_command", _capture)
    code = enf.main([
        "validate-enforcement-motion", str(matter), "--lever", "sanctions", "--request-type", "rfa",
    ])
    assert code != 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--slice" in preflight
    assert "F1" in preflight
    assert "--mode" in preflight
    assert "enforcement_motion_draft" in preflight


def test_selftest():
    assert enf.main(["selftest"]) == 0
