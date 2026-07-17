"""Synthetic tests for Slice A2 RFA audit_incoming_response."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "rfa_audit.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"
def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rfa = _load(SCRIPT, "rfa_audit")
cg = _load(CASEGRAPH, "casegraph_for_rfa_audit_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-RFA-A", prefix: str = "THORN-PROD") -> Path:
    matter = tmp_path / matter_id
    (matter / "01_discovery_served").mkdir(parents=True)
    (matter / "01_discovery_proposed").mkdir(parents=True)
    (matter / "01_production" / "raw").mkdir(parents=True)
    (matter / "01_transcripts").mkdir(parents=True)
    (matter / "03_attorney").mkdir(parents=True)
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (matter / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n",
        encoding="utf-8",
    )
    (matter / "01_discovery_served" / "rfa_set.md").write_text(
        "Request for Admission No. 1: Admit that an incident report exists for the June 1, 2024 event.\n\n"
        "Request for Admission No. 2: Admit that plaintiff has no photographs of the ladder.\n\n"
        "Request for Admission No. 3: Admit that wage loss began after the injury.\n",
        encoding="utf-8",
    )
    (matter / "01_discovery_proposed" / "proposed_rfa_responses.md").write_text(
        "Response to Request for Admission No. 1: Admit.\n\n"
        "Response to Request for Admission No. 2: Deny.\n\n"
        "Response to Request for Admission No. 3: Plaintiff lacks information sufficient to admit or deny.\n",
        encoding="utf-8",
    )
    (matter / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000011\n"
        "**Date:** 2024-06-01\n\n"
        "Incident report for the June 1, 2024 event involving the ladder.\n",
        encoding="utf-8",
    )
    (matter / "01_production" / "raw" / f"{prefix}-000020.md").write_text(
        f"**Bates Range:** {prefix}-000020 - {prefix}-000020\n\n"
        "Photograph log lists two ladder photographs from the inspection.\n",
        encoding="utf-8",
    )
    (matter / "01_transcripts" / "Depo-Wage.txt").write_text(
        "42:3 The worker testified that wage loss began after the injury.\n",
        encoding="utf-8",
    )
    assert cg.main(["init", str(matter), "--matter-id", matter_id, "--bates-prefix", prefix]) == 0
    assert cg.main(["build", str(matter)]) == 0
    return matter


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_parse_rfa_stable_ids(tmp_path):
    matter = _matter(tmp_path)
    assert rfa.main(["parse-rfa", str(matter)]) == 0
    first = json.loads((matter / "02_outputs" / "rfa_requests.json").read_text(encoding="utf-8"))
    assert first["request_type"] == "rfa"
    assert first["mode"] == "audit_incoming_response"
    assert [item["item_id"] for item in first["items"]] == ["RFA-001", "RFA-002", "RFA-003"]
    assert rfa.main(["parse-rfa", str(matter)]) == 0
    second = json.loads((matter / "02_outputs" / "rfa_requests.json").read_text(encoding="utf-8"))
    assert [(i["item_id"], i["text"]) for i in first["items"]] == [
        (i["item_id"], i["text"]) for i in second["items"]
    ]


def test_refuses_rfp_source(tmp_path):
    matter = _matter(tmp_path)
    rfp_source = matter / "01_discovery_served" / "rfp_set.md"
    rfp_source.write_text(
        "Request for Production No. 1: Produce the incident report.\n",
        encoding="utf-8",
    )
    assert rfa.main(["parse-rfa", str(matter), "--source", str(rfp_source)]) == 2


def test_classifications_and_audit_statuses(tmp_path):
    matter = _matter(tmp_path)
    assert rfa.main(["parse-rfa", str(matter)]) == 0
    assert rfa.main(["parse-proposed-rfa", str(matter)]) == 0
    assert rfa.main(["audit-rfa", str(matter)]) == 0

    responses = _read_jsonl(matter / "02_outputs" / "proposed_rfa_responses.jsonl")
    by_item = {row["item_id"]: row for row in responses}
    assert by_item["RFA-001"]["classification"] == "admit"
    assert by_item["RFA-002"]["classification"] == "deny"
    assert by_item["RFA-003"]["classification"] == "lack_information"

    audits = _read_jsonl(matter / "02_outputs" / "rfa_audit_items.jsonl")
    by_id = {row["response_id"]: row for row in audits}
    assert by_id["RFA-001-R01"]["status"] == "supported"
    assert by_id["RFA-001-R01"]["record_cites"]
    assert by_id["RFA-002-R01"]["status"] == "supported"
    assert by_id["RFA-002-R01"]["record_cites"][0]["type"] == "bates"
    assert by_id["RFA-003-R01"]["status"] == "needs_attorney_decision"
    assert by_id["RFA-003-R01"]["notes"]


def test_package_and_validate_rfa_audit(tmp_path):
    matter = _matter(tmp_path)
    for command in ("parse-rfa", "parse-proposed-rfa", "audit-rfa", "package-rfa-audit"):
        assert rfa.main([command, str(matter)]) == 0
    report = (matter / "02_outputs" / "rfa_response_audit_report.md").read_text(encoding="utf-8")
    assert "# RFA Response Audit" in report
    assert "lack_information" in report
    assert "THORN-PROD-000010" in report or "THORN-PROD-000020" in report
    assert rfa.main(["validate-rfa-audit", str(matter)]) == 0


def test_validate_live_mode_enforces_ocr_queue(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    for command in ("parse-rfa", "parse-proposed-rfa", "audit-rfa", "package-rfa-audit"):
        assert rfa.main([command, str(matter)]) == 0
    (matter / ".synthetic").unlink()

    captured: list[list[str]] = []
    original = rfa.run_command

    def _capture(command):
        captured.append(list(command))
        if "live_preflight.py" in " ".join(command):
            return 0
        return original(command)

    monkeypatch.setattr(rfa, "run_command", _capture)
    assert rfa.main(["validate-rfa-audit", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_two_matters_remain_isolated(tmp_path):
    a = _matter(tmp_path, "SYN-RFA-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-RFA-B", "RIVER-PROD")
    for matter in (a, b):
        for command in ("parse-rfa", "parse-proposed-rfa", "audit-rfa", "package-rfa-audit"):
            assert rfa.main([command, str(matter)]) == 0
    a_report = (a / "02_outputs" / "rfa_response_audit_report.md").read_text(encoding="utf-8")
    b_report = (b / "02_outputs" / "rfa_response_audit_report.md").read_text(encoding="utf-8")
    assert "RIVER-PROD" not in a_report
    assert "THORN-PROD" not in b_report


def test_selftest_runs_offline():
    assert rfa.main(["selftest"]) == 0


def test_description_length():
    skill = (REPO / "skills" / "legal" / "discovery-workflow" / "SKILL.md").read_text(encoding="utf-8")
    for line in skill.splitlines():
        if line.startswith("description:"):
            desc = line.split(":", 1)[1].strip().strip('"')
            assert len(desc) <= 60, len(desc)
            return
    raise AssertionError("missing description frontmatter")
