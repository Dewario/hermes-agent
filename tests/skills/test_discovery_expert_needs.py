"""Synthetic tests for Slice E1 expert_needs_assessment."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "expert_needs.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = _load(SCRIPT, "expert_needs")
cg = _load(CASEGRAPH, "casegraph_for_expert_needs_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-EXP-A", prefix: str = "EXPERT-PROD") -> Path:
    matter = tmp_path / matter_id
    (matter / "00_intake").mkdir(parents=True)
    (matter / "01_discovery_outgoing").mkdir(parents=True)
    (matter / "01_production" / "raw").mkdir(parents=True)
    (matter / "03_attorney").mkdir(parents=True)
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (matter / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-20\n",
        encoding="utf-8",
    )
    (matter / "03_attorney" / "matter_profile.yaml").write_text(
        f"matter_id: {matter_id}\n"
        "court: \"San Bernardino Superior Court (synthetic)\"\n"
        "jurisdiction_pack: ca_ccp\n"
        "case_overlay: ca_san_bernardino\n"
        "case_type: premises liability\n"
        "liability_theory: prior notice of unsafe ladder and missed inspection\n"
        "injuries: lumbar surgery, permanent restrictions, chronic pain\n"
        "damages_theory: future care, wage loss, and earning capacity\n"
        "discovery_cutoff: null\n"
        "expert_cutoff: null\n"
        "limits_used:\n"
        "  rog: 0\n"
        "  rfp: null\n"
        "  rfa: 0\n",
        encoding="utf-8",
    )
    (matter / "00_intake" / "case_context.md").write_text(
        "# Synthetic case context\n\n"
        "Plaintiff fell from a defective ladder after prior notice and a missed inspection.\n"
        "The incident caused lumbar surgery, chronic pain, future care needs, and permanent work restrictions.\n"
        "The damages claim includes wage loss and reduced earning capacity.\n",
        encoding="utf-8",
    )
    (matter / "01_discovery_outgoing" / "gap_themes.md").write_text(
        "- [notice] prior notice of ladder defect | prefer: rfp | priority: must_before_cutoff\n"
        "- [medical, wage_loss] future care, surgery, work restrictions, and earning capacity\n",
        encoding="utf-8",
    )
    (matter / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000010\n\n"
        "Complaint log notes a ladder complaint before the fall.\n",
        encoding="utf-8",
    )
    assert cg.main(["init", str(matter), "--matter-id", matter_id, "--bates-prefix", prefix]) == 0
    assert cg.main(["build", str(matter)]) == 0
    return matter


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_assess_builds_liability_and_damages_candidates(tmp_path):
    matter = _matter(tmp_path)
    assert mod.main(["assess-expert-needs", str(matter)]) == 0
    items = _read_jsonl(matter / "02_outputs" / "expert_needs_items.jsonl")
    assert any(i["track"] == "liability" for i in items)
    assert any(i["track"] == "damages" for i in items)
    assert any(i["expert_type"] == "premises_safety" for i in items)
    assert any(i["expert_type"] == "medical_causation_and_prognosis" for i in items)
    assert all(i["needs_attorney_decision"] is True for i in items)
    assert all(i["source_anchors"] for i in items)
    assert all(i["rule_ids"] for i in items)


def test_package_and_validate(tmp_path):
    matter = _matter(tmp_path)
    for command in (
        "assess-expert-needs",
        "package-expert-needs",
        "validate-expert-needs",
    ):
        assert mod.main([command, str(matter)]) == 0
    pkg = (matter / "02_outputs" / "expert_needs_assessment.md").read_text(encoding="utf-8")
    assert "Expert Needs Assessment" in pkg
    assert "Liability Experts" in pkg
    assert "Damages Experts" in pkg
    assert "retain Dr." not in pkg


def test_rejects_missing_profile(tmp_path):
    matter = _matter(tmp_path)
    (matter / "03_attorney" / "matter_profile.yaml").unlink()
    assert mod.main(["assess-expert-needs", str(matter)]) == 2


def test_validate_threads_e1_live_preflight(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    assert mod.main(["assess-expert-needs", str(matter)]) == 0
    assert mod.main(["package-expert-needs", str(matter)]) == 0
    captured: list[list[str]] = []

    def _capture(command):
        captured.append(list(command))
        return 0

    monkeypatch.setattr(mod, "run_command", _capture)
    assert mod.main(["validate-expert-needs", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert preflight[preflight.index("--request-type") + 1] == "expert"
    assert preflight[preflight.index("--mode") + 1] == "expert_needs_assessment"
    assert preflight[preflight.index("--slice") + 1] == "E1"


def test_isolation(tmp_path):
    a = _matter(tmp_path, "SYN-EXP-A", "EXPERTA-PROD")
    b = _matter(tmp_path, "SYN-EXP-B", "EXPERTB-PROD")
    for matter in (a, b):
        assert mod.main(["assess-expert-needs", str(matter)]) == 0
        assert mod.main(["package-expert-needs", str(matter)]) == 0
    a_pkg = (a / "02_outputs" / "expert_needs_assessment.md").read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / "expert_needs_assessment.md").read_text(encoding="utf-8")
    assert "EXPERTB-PROD" not in a_pkg
    assert "EXPERTA-PROD" not in b_pkg


def test_selftest():
    assert mod.main(["selftest"]) == 0
