"""Tests for new jurisdiction packs (wa_state, wa_king_county, wa_pierce_county,
ca_san_bernardino) and the expert-witness-analysis skill."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO / "skills" / "legal" / "discovery-workflow" / "jurisdiction" / "packs"
LOAD_PACK = REPO / "skills" / "legal" / "discovery-workflow" / "jurisdiction" / "load_pack.py"
LIMITS = REPO / "skills" / "legal" / "discovery-workflow" / "jurisdiction" / "limits.py"
EW_SCRIPT = REPO / "skills" / "legal" / "expert-witness-analysis" / "scripts" / "expert_analysis.py"
TAXONOMY = REPO / "skills" / "legal" / "expert-witness-analysis" / "references" / "expert_taxonomy.yaml"


def _load_loader():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("load_pack_test", LOAD_PACK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules["load_pack_test"] = module
    spec.loader.exec_module(module)
    return module


def _load_ew():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("expert_analysis_test", EW_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules["expert_analysis_test"] = module
    spec.loader.exec_module(module)
    return module


def _load_limits():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("limits_test", LIMITS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules["limits_test"] = module
    spec.loader.exec_module(module)
    return module


lp = _load_loader()
limits = _load_limits()
ew = _load_ew()


def test_wa_state_loads_active():
    loaded = lp.load_pack("wa_state")
    assert loaded["base"]["status"] == "active"
    assert loaded["base"]["pack_id"] == "wa_state"
    assert "WA-CR-33-A" in loaded["rule_ids"]
    assert "WA-CR-36-A" in loaded["rule_ids"]


def test_wa_state_rules_cover_all_request_types():
    loaded = lp.load_pack("wa_state")
    for rt in ("rog", "rfp", "rfa"):
        subset = lp.rules_for_type(loaded, rt)
        assert len(subset) >= 1, f"wa_state has no rules for {rt}"


def test_wa_king_county_overlay_requires_wa_state_base():
    loaded = lp.load_pack("wa_state", overlay_id="wa_king_county")
    assert loaded["overlay"]["pack_id"] == "wa_king_county"
    assert any(r["id"].startswith("KING-LCR-") for r in loaded["rules"])


def test_legacy_pack_aliases_resolve_to_canonical_names():
    loaded = lp.load_pack("wa_cr", overlay_id="wa_king_lcr")
    assert loaded["jurisdiction_pack"] == "wa_state"
    assert loaded["case_overlay"] == "wa_king_county"
    loaded = lp.load_pack("ca_ccp", overlay_id="ca_san_bernardino_local")
    assert loaded["case_overlay"] == "ca_san_bernardino"


def test_wa_king_county_refused_as_base():
    with pytest.raises(lp.PackError, match="is an overlay"):
        lp.load_pack("wa_king_county")


def test_wa_king_county_overlay_base_mismatch_rejected():
    with pytest.raises(lp.PackError, match="does not match"):
        lp.load_pack("ca_ccp", overlay_id="wa_king_county")


def test_wa_pierce_county_overlay_loads():
    loaded = lp.load_pack("wa_state", overlay_id="wa_pierce_county")
    assert loaded["overlay"]["pack_id"] == "wa_pierce_county"
    assert any(r["id"].startswith("PIERCE-PCLR-") for r in loaded["rules"])


def test_ca_san_bernardino_overlay_loads_on_ca_ccp():
    loaded = lp.load_pack("ca_ccp", overlay_id="ca_san_bernardino")
    assert loaded["overlay"]["pack_id"] == "ca_san_bernardino"
    assert any(r["id"].startswith("SBC-") for r in loaded["rules"])


def test_ca_san_bernardino_refused_on_wa_state():
    with pytest.raises(lp.PackError, match="does not match"):
        lp.load_pack("wa_state", overlay_id="ca_san_bernardino")


def test_new_packs_are_active_and_source_bound():
    """Verified packs should remain source-bound; uncertainty is rule-specific."""
    for pack_id in ("wa_state", "wa_king_county", "wa_pierce_county", "ca_san_bernardino"):
        loaded = lp.load_pack(pack_id) if pack_id == "wa_state" else lp.load_pack(
            "wa_state" if pack_id.startswith("wa_") else "ca_ccp",
            overlay_id=pack_id,
        )
        assert loaded["base"]["status"] == "active"
        for rule in loaded["rules"]:
            assert rule.get("source_url"), f"{rule['id']} missing source_url"


def test_expert_taxonomy_loads():
    loaded = ew._load_taxonomy()
    assert "liability" in loaded and "damages" in loaded
    assert len(loaded["liability"]) >= 5
    assert len(loaded["damages"]) >= 5


def test_expert_matcher_felrail_scenario():
    text = "train collision at crossing; fra hours of service violation; tbi; wage loss"
    taxonomy = ew._load_taxonomy()
    liab = ew._match_experts(text, taxonomy["liability"])
    dmg = ew._match_experts(text, taxonomy["damages"])
    liab_ids = {m["expert"]["id"] for m in liab}
    dmg_ids = {m["expert"]["id"] for m in dmg}
    assert "EXP-L-ACC-RECON" in liab_ids
    assert "EXP-L-REGULATORY" in liab_ids
    assert "EXP-D-NEUROPSYCH" in dmg_ids
    assert "EXP-D-FORENSIC-ECON" in dmg_ids


def test_expert_standard_for_jurisdiction_packs():
    assert ew._standard_for({"jurisdiction_pack": "frcp_generic"}) == "federal"
    assert ew._standard_for({"jurisdiction_pack": "ca_ccp"}) == "ca"
    assert ew._standard_for({"jurisdiction_pack": "ca_ccp", "case_overlay": "ca_san_bernardino"}) == "ca"
    assert ew._standard_for({"jurisdiction_pack": "wa_state"}) == "wa"
    assert ew._standard_for({"jurisdiction_pack": "wa_state", "case_overlay": "wa_king_county"}) == "wa"


def test_expert_recommendation_includes_admissibility_and_gaps():
    taxonomy = ew._load_taxonomy()
    exp = taxonomy["liability"][0]
    rec = ew._recommendation(exp, "ca", ["collision"], matter_id="SYN-TEST", slice_id="E1")
    assert rec["admissibility_standard"] == "ca"
    assert rec["needs_attorney_decision"] is True
    assert rec["objection_draft"] is None
    assert len(rec["foundation_gaps"]) >= 1
    assert "Kelly" in rec["admissibility_notes"] or "Sargon" in rec["admissibility_notes"]


def test_limit_resolvers_are_jurisdiction_aware():
    ca = lp.load_pack("ca_ccp")
    assert limits.resolve_rog_limit(
        {"jurisdiction_pack": "ca_ccp", "case_overlay": None, "raw": {}},
        set(ca["rule_ids"]),
    ) == 35
    assert limits.resolve_rfa_limit(
        {"jurisdiction_pack": "ca_ccp", "case_overlay": None, "raw": {}},
        set(ca["rule_ids"]),
    ) == 35

    wa = lp.load_pack("wa_state")
    assert limits.resolve_rog_limit(
        {"jurisdiction_pack": "wa_state", "case_overlay": None, "raw": {}},
        set(wa["rule_ids"]),
    ) is None
    assert limits.resolve_rfa_limit(
        {"jurisdiction_pack": "wa_state", "case_overlay": None, "raw": {}},
        set(wa["rule_ids"]),
    ) is None

    king = lp.load_pack("wa_state", overlay_id="wa_king_county")
    assert limits.resolve_rog_limit(
        {"jurisdiction_pack": "wa_state", "case_overlay": "wa_king_county", "raw": {}},
        set(king["rule_ids"]),
    ) == 40
    assert limits.resolve_rfa_limit(
        {"jurisdiction_pack": "wa_state", "case_overlay": "wa_king_county", "raw": {}},
        set(king["rule_ids"]),
    ) == 25

    pierce = lp.load_pack("wa_state", overlay_id="wa_pierce_county")
    assert limits.resolve_rog_limit(
        {
            "jurisdiction_pack": "wa_state",
            "case_overlay": "wa_pierce_county",
            "raw": {"track": "dissolution"},
        },
        set(pierce["rule_ids"]),
    ) == 100
    assert limits.resolve_rfp_limit(
        {"jurisdiction_pack": "wa_state", "case_overlay": "wa_pierce_county", "raw": {}},
        set(pierce["rule_ids"]),
    ) is None


def test_expert_selftest_passes():
    assert ew.selftest() == 0


def test_expert_end_to_end_synthetic(tmp_path):
    matter = tmp_path / "SYN-EXPERT-TEST"
    cf = matter / "01_case_facts"
    cf.mkdir(parents=True)
    (cf / "case_facts.md").write_text(
        "Train collision at grade crossing. Locomotive struck pickup. "
        "FRA Hours of Service violation alleged. Driver suffered TBI and wage loss.",
        encoding="utf-8",
    )
    (cf / "cast_context.md").write_text(
        "Plaintiff: driver. Defendant railroad. Witness: conductor.", encoding="utf-8"
    )
    att = matter / "03_attorney"
    att.mkdir(parents=True)
    (att / "matter_profile.yaml").write_text(
        "matter_id: SYN-EXPERT-TEST\njurisdiction_pack: wa_state\ncase_overlay: wa_king_county\n",
        encoding="utf-8",
    )
    assert ew.parse_case_facts(matter) == 0
    assert ew._assess(matter, "E1") == 0
    assert ew._assess(matter, "E2") == 0
    assert ew.package_analysis(matter) == 0
    report = matter / "02_outputs" / "expert_analysis_report.md"
    assert report.is_file()
    text = report.read_text(encoding="utf-8")
    assert "Jurisdiction standard: `wa`" in text
    assert "Accident Reconstruction" in text
    assert "Forensic Economics" in text
    assert "ATTORNEY REVIEW REQUIRED" in text


def test_expert_analysis_reads_intake_and_gap_feeders(tmp_path):
    matter = tmp_path / "SYN-EXPERT-FEEDERS"
    (matter / "00_intake").mkdir(parents=True)
    (matter / "01_discovery_outgoing").mkdir(parents=True)
    (matter / "03_attorney").mkdir(parents=True)
    (matter / "00_intake" / "case_context.md").write_text(
        "Train collision at a crossing with alleged FRA rules issues. "
        "Plaintiff reports TBI, wage loss, and reduced earning capacity.",
        encoding="utf-8",
    )
    (matter / "01_discovery_outgoing" / "gap_themes.md").write_text(
        "- [liability] visibility, event reconstruction, and FRA compliance gaps\n"
        "- [damages] neuropsychology and forensic economics gaps\n",
        encoding="utf-8",
    )
    (matter / "03_attorney" / "matter_profile.yaml").write_text(
        "matter_id: SYN-EXPERT-FEEDERS\njurisdiction_pack: wa_state\ncase_overlay: wa_king_county\n",
        encoding="utf-8",
    )
    assert ew.parse_case_facts(matter) == 0
    parsed = json.loads((matter / "02_outputs" / "parsed_case_facts.json").read_text(encoding="utf-8"))
    assert "00_intake/case_context.md" in parsed["input_sources"]
    assert "01_discovery_outgoing/gap_themes.md" in parsed["input_sources"]
    assert ew._assess(matter, "E1") == 0
    assert ew._assess(matter, "E2") == 0
    assert ew.package_analysis(matter) == 0
    text = (matter / "02_outputs" / "expert_analysis_report.md").read_text(encoding="utf-8")
    assert "Accident Reconstruction" in text
    assert "Forensic Economics" in text


# --- Invariant tests for verified citation corrections ---
# These assert relationships that must hold (not frozen values), guarding
# against regressions of the premise errors the citation-verification pass
# corrected. See autonomous_review/CROSS_CHECK_REPORT.md.


def _wa_cr33_summary(loaded):
    for r in loaded["rules"]:
        if r["id"] == "WA-CR-33-A":
            return r["summary"]
    return ""


def test_wa_cr33_does_not_claim_statewide_25_limit():
    """WA CR 33 has no statewide numerical limit; the 25 cap is federal FRCP 33(a)(1)."""
    loaded = lp.load_pack("wa_state")
    summary = _wa_cr33_summary(loaded).lower()
    assert "no statewide" in summary, "wa_state must state CR 33 has no statewide limit"
    assert "local" in summary
    # Must not assert a flat 25 cap as WA law
    assert "no more than 25" not in summary


def test_wa_cr26_b1_does_not_use_federal_proportionality():
    """WA CR 26(b)(1) has not adopted the federal 2015 'proportional to the needs' standard.
    The summary must affirmatively disclaim it (the phrase may appear in the negation)."""
    loaded = lp.load_pack("wa_state")
    summary = next(
        r["summary"] for r in loaded["rules"] if r["id"] == "WA-CR-26-SCOPE"
    )
    low = summary.lower()
    assert "relevant to the subject matter" in low
    assert "not adopted" in low or "has not adopted" in low, (
        "wa_state must affirmatively disclaim the federal proportionality standard"
    )


def test_wa_state_has_mandatory_meet_and_confer_cr26i():
    """CR 26(i) is the mandatory pre-motion meet-and-confer (not CR 26(f))."""
    loaded = lp.load_pack("wa_state")
    ids = {r["id"] for r in loaded["rules"]}
    assert "WA-CR-26-I" in ids


def test_wa_cr37_a4_summary_covers_granted_denied_and_mixed_expenses():
    """CR 37(a)(4) covers expense outcomes for granted, denied, and partly granted motions."""
    loaded = lp.load_pack("wa_state")
    summary = next(r["summary"] for r in loaded["rules"] if r["id"] == "WA-CR-37-A-4").lower()
    assert "granted" in summary
    assert "denied" in summary
    assert "partly granted" in summary or "granted in part" in summary
    assert "substantial-justification" in summary


def test_ca_ccp_has_deemed_admission_statute_2033_280():
    """§ 2033.280 is the principal no-timely-response deemed-admission statute."""
    loaded = lp.load_pack("ca_ccp")
    ids = {r["id"] for r in loaded["rules"]}
    assert "CCP-2033-280" in ids
    summary = next(r["summary"] for r in loaded["rules"] if r["id"] == "CCP-2033-280").lower()
    assert "deemed admitted" in summary or "deemed-admission" in summary


def test_ca_ccp_sanction_is_1000_not_250():
    """§ 2023.050 mandatory sanction increased to $1,000 (SB 235, eff. Jan. 1, 2024)."""
    loaded = lp.load_pack("ca_ccp")
    summary = next(r["summary"] for r in loaded["rules"] if r["id"] == "CCP-2023-050")
    assert "$1,000" in summary
    assert "$250" not in summary or "250 to $1,000" in summary  # historical mention ok


def test_ca_ccp_has_objection_particulars_2031_240():
    """§ 2031.240 governs objection/withholding particulars (privilege log)."""
    loaded = lp.load_pack("ca_ccp")
    ids = {r["id"] for r in loaded["rules"]}
    assert "CCP-2031-240" in ids


def test_pierce_county_uses_pclr_not_pclcr():
    """Pierce County official cite is PCLR (PCLR 0.1), not PCLCR."""
    loaded = lp.load_pack("wa_state", overlay_id="wa_pierce_county")
    for r in loaded["rules"]:
        if r["id"].startswith("PIERCE-PCLR"):
            assert "PCLCR" not in r["citation"], f"{r['id']} citation should use PCLR not PCLCR"
            break
    else:
        assert False, "no PIERCE-PCLR rule found"


def test_pierce_county_interrogatory_caps_are_track_based():
    """Pierce interrogatory caps: 25/35/35/100 by track (subparts separate)."""
    loaded = lp.load_pack("wa_state", overlay_id="wa_pierce_county")
    summary = next(
        r["summary"] for r in loaded["rules"] if r["id"] == "PIERCE-PCLR-3-ROG-CAPS"
    )
    low = summary.lower()
    for track_cap in ("expedited 25", "standard 35", "complex 35", "dissolution 100"):
        assert track_cap in low, f"missing track cap {track_cap}"


def test_king_county_interrogatory_limit_is_40():
    """King County LCR 26: 40 interrogatories including discrete subparts."""
    loaded = lp.load_pack("wa_state", overlay_id="wa_king_county")
    summary = next(
        r["summary"] for r in loaded["rules"] if r["id"] == "KING-LCR-26-CAPS"
    )
    assert "40 interrogatories" in summary


def test_expert_taxonomy_no_fictitious_eri_rule():
    """The fictitious 'ERI' WA evidence rule must not appear in any WA admissibility note."""
    taxonomy = ew._load_taxonomy()
    for group in ("liability", "damages"):
        for exp in taxonomy[group]:
            wa_note = exp.get("admissibility_notes", {}).get("wa", "")
            # 'ERI' as a standalone rule reference is forbidden; 'ENGINEERING' is a false positive
            assert " ER 702 + ERI" not in wa_note, (
                f"{exp['id']} wa note still references fictitious ERI rule"
            )
            assert "ERI for" not in wa_note
            assert "Frye/ERI" not in wa_note


def test_expert_taxonomy_has_correct_sargon_cite():
    """Sargon is (2012) 55 Cal.4th 747, not 53 Cal.4th 1210."""
    import yaml
    raw = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    blob = json.dumps(raw)
    assert "55 Cal.4th 747" in blob
    assert "53 Cal.4th 1210" not in blob, "wrong Sargon cite must not appear"


def test_expert_taxonomy_has_correct_sanchez_cite():
    """Sanchez is (2016) 63 Cal.4th 665, not 1 Cal.5th 865."""
    import yaml
    raw = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    blob = json.dumps(raw)
    assert "63 Cal.4th 665" in blob
    assert "1 Cal.5th 865" not in blob, "wrong Sanchez cite must not appear"


def test_expert_taxonomy_includes_ca_801_1():
    """CA Evid. Code § 801.1 (operative Jan. 1, 2024) medical-causation symmetry must be present."""
    import yaml
    raw = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    blob = json.dumps(raw)
    assert "801.1" in blob, "taxonomy must reference CA Evid. Code 801.1"
    assert "Jan. 1, 2024" in blob or "January 1, 2024" in blob


def test_expert_taxonomy_no_copeland_bryant_or_state_v_frye():
    """Fictitious 'Copeland-Bryant' and 'State v. Frye' must not appear; use State v. Copeland (1996)."""
    import yaml
    raw = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    blob = json.dumps(raw)
    assert "Copeland-Bryant" not in blob
    assert "State v. Frye" not in blob
    assert "State v. Copeland" in blob, "must cite State v. Copeland (1996)"
