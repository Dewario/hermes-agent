"""Synthetic tests for Slice G1 trial_gap_assessment."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "trial_gap.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = _load(SCRIPT, "trial_gap")
cg = _load(CASEGRAPH, "casegraph_for_trial_gap_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-TG-A", prefix: str = "THORN-PROD") -> Path:
    matter = tmp_path / matter_id
    (matter / "01_discovery_outgoing").mkdir(parents=True)
    (matter / "01_production" / "raw").mkdir(parents=True)
    (matter / "03_attorney").mkdir(parents=True)
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (matter / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    (matter / "03_attorney" / "matter_profile.yaml").write_text(
        f"matter_id: {matter_id}\n"
        "court: synthetic\n"
        "jurisdiction_pack: frcp_generic\n"
        "case_overlay: fela\n"
        "discovery_cutoff: null\n"
        "limits_used:\n"
        "  rog: 0\n"
        "  rfp: null\n"
        "  rfa: 0\n",
        encoding="utf-8",
    )
    (matter / "01_discovery_outgoing" / "gap_themes.md").write_text(
        "- [notice] prior notice of ladder defect | prefer: rfp | "
        "priority: must_before_cutoff | Jury: prior notice\n"
        "- [medical, wage_loss] post-incident treatment and earnings proof | "
        "prefer: rog | priority: should\n"
        "- [authenticity] photograph exhibit authenticity | prefer: rfa | "
        "priority: optional | Jury: exhibit authenticity\n"
        "- [liability] inspection history for the ladder | prefer: rfp | priority: should\n",
        encoding="utf-8",
    )
    (matter / "01_discovery_outgoing" / "rfp_issue_brief.md").write_text(
        "- [liability] Produce all inspection reports for the ladder.\n",
        encoding="utf-8",
    )
    (matter / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000010\n\n"
        "Complaint log notes a written complaint about the ladder on May 1, 2024.\n",
        encoding="utf-8",
    )
    assert cg.main(["init", str(matter), "--matter-id", matter_id, "--bates-prefix", prefix]) == 0
    assert cg.main(["build", str(matter)]) == 0
    return matter


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_assess_flags_and_coverage(tmp_path):
    matter = _matter(tmp_path)
    assert mod.main(["parse-gap-themes", str(matter)]) == 0
    assert mod.main(["assess-trial-gaps", str(matter)]) == 0
    items = _read_jsonl(matter / "02_outputs" / "trial_gap_items.jsonl")
    assert len(items) == 4
    assert all(i["rule_ids"] for i in items)
    assert any(i.get("already_covered") for i in items)
    assert any(
        i.get("priority") == "defer_to_attorney" and "notice" in i["issue_tags"]
        for i in items
    )
    assert any(i["recommended_request_type"] == "rog" for i in items)
    assert any(i["recommended_request_type"] == "rfa" for i in items)
    assert any("FELA-THEME-NOTICE" in (i.get("rule_ids") or []) for i in items)


def test_export_skips_covered(tmp_path):
    matter = _matter(tmp_path)
    for command in ("parse-gap-themes", "assess-trial-gaps", "export-issue-briefs"):
        assert mod.main([command, str(matter)]) == 0
    rfp = (matter / "01_discovery_outgoing" / "gap_suggested_rfp_issue_brief.md").read_text(
        encoding="utf-8"
    )
    assert "prior notice" in rfp
    assert "inspection reports" not in rfp.lower()
    rog = (matter / "01_discovery_outgoing" / "gap_suggested_rog_issue_brief.md").read_text(
        encoding="utf-8"
    )
    assert "medical" in rog or "treatment" in rog or "earnings" in rog


def test_rejects_missing_profile(tmp_path):
    matter = _matter(tmp_path)
    (matter / "03_attorney" / "matter_profile.yaml").unlink()
    assert mod.main(["parse-gap-themes", str(matter)]) == 0
    assert mod.main(["assess-trial-gaps", str(matter)]) == 2


def test_package_and_validate(tmp_path):
    matter = _matter(tmp_path)
    for command in (
        "parse-gap-themes",
        "assess-trial-gaps",
        "export-issue-briefs",
        "package-trial-gap",
        "validate-trial-gap",
    ):
        assert mod.main([command, str(matter)]) == 0
    pkg = (matter / "02_outputs" / "trial_gap_report.md").read_text(encoding="utf-8")
    assert "Trial Gap Assessment" in pkg
    assert "RFP-001" not in pkg
    assert "TG-" in pkg


def test_live_mode_enforces_ocr(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    for command in (
        "parse-gap-themes",
        "assess-trial-gaps",
        "export-issue-briefs",
        "package-trial-gap",
    ):
        assert mod.main([command, str(matter)]) == 0
    (matter / ".synthetic").unlink()
    captured: list[list[str]] = []
    original = mod.run_command

    def _capture(command):
        captured.append(list(command))
        if "live_preflight.py" in " ".join(command):
            return 0
        return original(command)

    monkeypatch.setattr(mod, "run_command", _capture)
    assert mod.main(["validate-trial-gap", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_isolation(tmp_path):
    a = _matter(tmp_path, "SYN-TG-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-TG-B", "RIVER-PROD")
    for matter in (a, b):
        for command in (
            "parse-gap-themes",
            "assess-trial-gaps",
            "export-issue-briefs",
            "package-trial-gap",
        ):
            assert mod.main([command, str(matter)]) == 0
    a_pkg = (a / "02_outputs" / "trial_gap_report.md").read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / "trial_gap_report.md").read_text(encoding="utf-8")
    assert "RIVER-PROD" not in a_pkg
    assert "THORN-PROD" not in b_pkg


def test_selftest():
    assert mod.main(["selftest"]) == 0


def test_skill_description_length():
    skill = (REPO / "skills" / "legal" / "discovery-workflow" / "SKILL.md").read_text(encoding="utf-8")
    for line in skill.splitlines():
        if line.startswith("description:"):
            desc = line.split(":", 1)[1].strip().strip('"')
            assert len(desc) <= 60, len(desc)
            return
    raise AssertionError("missing description")
