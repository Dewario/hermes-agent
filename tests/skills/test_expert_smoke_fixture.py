"""E2E smoke for the expert-witness-analysis synthetic smoke fixture."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "expert-witness-analysis" / "scripts" / "expert_analysis.py"
SEED = REPO / "skills" / "legal" / "expert-witness-analysis" / "fixtures" / "smoke_matter" / "seed"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"

REQUIRED_SEED = [
    ".synthetic",
    "01_case_facts/case_facts.md",
    "01_case_facts/cast_context.md",
    "03_attorney/matter_profile.yaml",
    "03_attorney/PROVIDER_AUTH.md",
]


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ew = _load(SCRIPT, "expert_analysis_smoke")
cg = _load(CASEGRAPH, "casegraph_for_expert_smoke")


def test_seed_complete():
    assert SEED.is_dir()
    for rel in REQUIRED_SEED:
        assert (SEED / rel).is_file(), f"missing seed file: {rel}"


def test_seed_is_synthetic():
    marker = (SEED / ".synthetic").read_text(encoding="utf-8")
    assert "SYNTHETIC" in marker.upper()


def test_expert_smoke_e2e(tmp_path):
    """Materialize the seed and run the full expert pipeline end-to-end."""
    matter = tmp_path / "SYN-SMOKE-EXPERT"
    shutil.copytree(SEED, matter)
    assert cg.main(["init", str(matter), "--matter-id", "SYN-SMOKE-EXPERT", "--bates-prefix", "SMOKE-PROD"]) == 0
    assert cg.main(["build", str(matter)]) == 0

    assert ew.parse_case_facts(matter) == 0
    assert ew._assess(matter, "E1") == 0
    assert ew._assess(matter, "E2") == 0
    assert ew.package_analysis(matter) == 0

    report = matter / "02_outputs" / "expert_analysis_report.md"
    assert report.is_file()
    text = report.read_text(encoding="utf-8")
    # WA standard resolved from wa_state + wa_king_county overlay
    assert "Jurisdiction standard: `wa`" in text
    # FELA/railroad scenario should surface reconstruction + regulatory + econ + neuropsych
    assert "Accident Reconstruction" in text
    assert "Forensic Economics" in text
    assert "ATTORNEY REVIEW REQUIRED" in text
    # No opinion drafting
    assert "objection_draft" not in text.lower() or "objection_draft: None" in text

    # JSONL outputs exist
    assert (matter / "02_outputs" / "expert_liability_recommendations.jsonl").is_file()
    assert (matter / "02_outputs" / "expert_damages_recommendations.jsonl").is_file()


def test_expert_smoke_validate(tmp_path):
    """The packaged report must pass casegraph verify-cites and check-isolation."""
    matter = tmp_path / "SYN-SMOKE-EXPERT"
    shutil.copytree(SEED, matter)
    assert cg.main(["init", str(matter), "--matter-id", "SYN-SMOKE-EXPERT", "--bates-prefix", "SMOKE-PROD"]) == 0
    assert cg.main(["build", str(matter)]) == 0
    assert ew.parse_case_facts(matter) == 0
    assert ew._assess(matter, "E1") == 0
    assert ew._assess(matter, "E2") == 0
    assert ew.package_analysis(matter) == 0
    assert ew.validate_analysis(matter) == 0
