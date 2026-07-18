"""Synthetic tests for Slice B1 RFA draft_outgoing_request."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "rfa_outgoing.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


out = _load(SCRIPT, "rfa_outgoing")
cg = _load(CASEGRAPH, "casegraph_for_rfa_outgoing_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-ORFA-A", prefix: str = "THORN-PROD") -> Path:
    matter = tmp_path / matter_id
    (matter / "01_discovery_outgoing").mkdir(parents=True)
    (matter / "01_production" / "raw").mkdir(parents=True)
    (matter / "03_attorney").mkdir(parents=True)
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (matter / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    (matter / "01_discovery_outgoing" / "rfa_issue_brief.md").write_text(
        "- [notice] Admit that defendant received a written complaint about the ladder on May 1, 2024. "
        "| Jury: prior notice\n"
        "- [wage_loss] Admit that plaintiff was unable to work from June 2, 2024 through July 15, 2024.\n"
        "- [liability] Admit that defendant owed a duty to maintain the ladder AND that defendant "
        "breached that duty.\n"
        "- [jury_theme, authenticity] Admit that the photograph log marked as an exhibit is a genuine "
        "business record. | Jury: exhibit authenticity\n",
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


def test_parse_and_draft_splits_multi_fact(tmp_path):
    matter = _matter(tmp_path)
    assert out.main(["parse-issue-brief", str(matter)]) == 0
    assert out.main(["draft-outgoing-rfa", str(matter)]) == 0
    items = _read_jsonl(matter / "02_outputs" / "outgoing_rfa_items.jsonl")
    assert len(items) >= 4
    assert all(item["issue_tags"] for item in items)
    liability = [i for i in items if "liability" in i["issue_tags"]]
    assert len(liability) >= 2  # AND-split
    assert all(i["single_fact"] for i in liability)
    assert all(i["item_id"].startswith("ORA-") for i in items)


def test_rejects_unknown_tag(tmp_path):
    matter = _matter(tmp_path)
    brief = matter / "01_discovery_outgoing" / "rfa_issue_brief.md"
    brief.write_text("- [not_a_tag] Admit that x.\n", encoding="utf-8")
    assert out.main(["parse-issue-brief", str(matter)]) == 2


def test_rejects_objection_language(tmp_path):
    matter = _matter(tmp_path)
    brief = matter / "01_discovery_outgoing" / "rfa_issue_brief.md"
    brief.write_text(
        "- [notice] Admit that x, subject to plaintiff's objection on privilege grounds.\n",
        encoding="utf-8",
    )
    assert out.main(["parse-issue-brief", str(matter)]) == 2


def test_package_and_validate(tmp_path):
    matter = _matter(tmp_path)
    for command in (
        "parse-issue-brief", "draft-outgoing-rfa", "package-outgoing-rfa", "validate-outgoing-rfa",
    ):
        assert out.main([command, str(matter)]) == 0
    pkg = (matter / "02_outputs" / "outgoing_rfa_set.md").read_text(encoding="utf-8")
    assert "Outgoing Requests for Admission" in pkg
    assert "Outgoing admission" in pkg
    assert "RFA-001" not in pkg
    assert "issue tags" in pkg.lower() or "Issue tags" in pkg


def test_live_mode_enforces_ocr(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    for command in ("parse-issue-brief", "draft-outgoing-rfa", "package-outgoing-rfa"):
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
    assert out.main(["validate-outgoing-rfa", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_isolation(tmp_path):
    a = _matter(tmp_path, "SYN-ORFA-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-ORFA-B", "RIVER-PROD")
    for matter in (a, b):
        for command in ("parse-issue-brief", "draft-outgoing-rfa", "package-outgoing-rfa"):
            assert out.main([command, str(matter)]) == 0
    a_pkg = (a / "02_outputs" / "outgoing_rfa_set.md").read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / "outgoing_rfa_set.md").read_text(encoding="utf-8")
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
