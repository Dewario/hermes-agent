"""Synthetic tests for Slice B3 RFP draft_outgoing_request."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "rfp_outgoing.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


out = _load(SCRIPT, "rfp_outgoing")
cg = _load(CASEGRAPH, "casegraph_for_rfp_outgoing_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-ORFP-A", prefix: str = "THORN-PROD") -> Path:
    matter = tmp_path / matter_id
    (matter / "01_discovery_outgoing").mkdir(parents=True)
    (matter / "01_production" / "raw").mkdir(parents=True)
    (matter / "03_attorney").mkdir(parents=True)
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (matter / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    (matter / "01_discovery_outgoing" / "rfp_issue_brief.md").write_text(
        "- [notice] Produce all written complaints about the ladder received on or before "
        "May 1, 2024. | Jury: prior notice\n"
        "- [wage_loss] Produce all payroll records for plaintiff from June 2, 2024 through "
        "July 15, 2024. | Already: none\n"
        "- [liability] Produce all inspection reports for the ladder AND produce all "
        "maintenance policies for ladders.\n"
        "- [jury_theme, authenticity] Produce the photograph log and chain-of-custody "
        "records for that exhibit. | Jury: exhibit authenticity\n",
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


def test_parse_and_draft_splits_and_flags_overlap(tmp_path):
    matter = _matter(tmp_path)
    assert out.main(["parse-issue-brief", str(matter)]) == 0
    assert out.main(["draft-outgoing-rfp", str(matter)]) == 0
    items = _read_jsonl(matter / "02_outputs" / "outgoing_rfp_items.jsonl")
    assert len(items) >= 4
    assert all(item["issue_tags"] for item in items)
    liability = [i for i in items if "liability" in i["issue_tags"]]
    assert len(liability) >= 2  # AND-split
    assert all(i["item_id"].startswith("ORP-") for i in items)
    assert any(i.get("production_status") == "possible_overlap" for i in items)
    assert any(i.get("production_status") == "gap_or_none_declared" for i in items)


def test_rejects_unknown_tag(tmp_path):
    matter = _matter(tmp_path)
    brief = matter / "01_discovery_outgoing" / "rfp_issue_brief.md"
    brief.write_text("- [not_a_tag] Produce all documents concerning x.\n", encoding="utf-8")
    assert out.main(["parse-issue-brief", str(matter)]) == 2


def test_rejects_objection_language(tmp_path):
    matter = _matter(tmp_path)
    brief = matter / "01_discovery_outgoing" / "rfp_issue_brief.md"
    brief.write_text(
        "- [notice] Produce all documents concerning x, subject to plaintiff's objection.\n",
        encoding="utf-8",
    )
    assert out.main(["parse-issue-brief", str(matter)]) == 2


def test_rejects_rfa_admit_language(tmp_path):
    matter = _matter(tmp_path)
    brief = matter / "01_discovery_outgoing" / "rfp_issue_brief.md"
    brief.write_text(
        "- [notice] Admit that defendant received a written complaint about the ladder.\n",
        encoding="utf-8",
    )
    assert out.main(["parse-issue-brief", str(matter)]) == 2


def test_rejects_rog_only_language(tmp_path):
    matter = _matter(tmp_path)
    brief = matter / "01_discovery_outgoing" / "rfp_issue_brief.md"
    brief.write_text(
        "- [notice] State all facts concerning defendant's receipt of complaints.\n",
        encoding="utf-8",
    )
    assert out.main(["parse-issue-brief", str(matter)]) == 2


def test_package_and_validate(tmp_path):
    matter = _matter(tmp_path)
    for command in (
        "parse-issue-brief", "draft-outgoing-rfp", "package-outgoing-rfp", "validate-outgoing-rfp",
    ):
        assert out.main([command, str(matter)]) == 0
    pkg = (matter / "02_outputs" / "outgoing_rfp_set.md").read_text(encoding="utf-8")
    assert "Outgoing Requests for Production" in pkg
    assert "Outgoing production request" in pkg
    assert "RFP-001" not in pkg
    assert "Production status" in pkg


def test_live_mode_enforces_ocr(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    for command in ("parse-issue-brief", "draft-outgoing-rfp", "package-outgoing-rfp"):
        assert out.main([command, str(matter)]) == 0
    (matter / ".synthetic").unlink()
    captured: list[list[str]] = []
    original = out.run_command

    def _capture(command):
        captured.append(list(command))
        if "live_preflight.py" in " ".join(command):
            return 0
        return original(command)

    monkeypatch.setattr(out, "run_command", _capture)
    assert out.main(["validate-outgoing-rfp", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_isolation(tmp_path):
    a = _matter(tmp_path, "SYN-ORFP-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-ORFP-B", "RIVER-PROD")
    for matter in (a, b):
        for command in ("parse-issue-brief", "draft-outgoing-rfp", "package-outgoing-rfp"):
            assert out.main([command, str(matter)]) == 0
    a_pkg = (a / "02_outputs" / "outgoing_rfp_set.md").read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / "outgoing_rfp_set.md").read_text(encoding="utf-8")
    assert "RIVER-PROD" not in a_pkg
    assert "THORN-PROD" not in b_pkg


def test_selftest():
    assert out.main(["selftest"]) == 0


def test_skill_description_length():
    skill = (REPO / "skills" / "legal" / "discovery-workflow" / "SKILL.md").read_text(encoding="utf-8")
    for line in skill.splitlines():
        if line.startswith("description:"):
            desc = line.split(":", 1)[1].strip().strip('"')
            assert len(desc) <= 60, len(desc)
            return
    raise AssertionError("missing description")
