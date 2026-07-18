"""Synthetic tests for Slice A3 ROG audit_incoming_response."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "rog_audit.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rog = _load(SCRIPT, "rog_audit")
cg = _load(CASEGRAPH, "casegraph_for_rog_audit_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-ROG-A", prefix: str = "THORN-PROD") -> Path:
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
    (matter / "01_discovery_served" / "rog_set.md").write_text(
        "Interrogatory No. 1: State the date of the incident involving the ladder.\n\n"
        "Interrogatory No. 2:\n"
        "(a) Identify medical treatment received after the injury.\n"
        "(b) State whether plaintiff claims wage loss.\n\n"
        "Interrogatory No. 3: State all facts supporting any claim of negligence.\n",
        encoding="utf-8",
    )
    (matter / "01_discovery_proposed" / "proposed_rog_answers.md").write_text(
        "Answer to Interrogatory No. 1: The incident occurred on June 1, 2024.\n\n"
        "Answer to Interrogatory No. 2:\n"
        "(a) Plaintiff received medical treatment after the injury.\n"
        "(b) Plaintiff claims wage loss began after the injury.\n\n"
        "Answer to Interrogatory No. 3: Defendant was negligent in failing to train supervisors.\n",
        encoding="utf-8",
    )
    (matter / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000011\n"
        "**Date:** 2024-06-01\n\n"
        "Incident report for the June 1, 2024 event involving the ladder.\n",
        encoding="utf-8",
    )
    (matter / "01_production" / "raw" / f"{prefix}-000030.md").write_text(
        f"**Bates Range:** {prefix}-000030 - {prefix}-000030\n\n"
        "Medical note: treatment after the injury included evaluation for ladder trauma.\n",
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


def test_parse_rog_with_subparts(tmp_path):
    matter = _matter(tmp_path)
    assert rog.main(["parse-rog", str(matter)]) == 0
    payload = json.loads((matter / "02_outputs" / "rog_requests.json").read_text(encoding="utf-8"))
    assert payload["request_type"] == "rog"
    ids = [item["item_id"] for item in payload["items"]]
    assert "ROG-001" in ids
    assert "ROG-002-S01" in ids
    assert "ROG-002-S02" in ids
    assert "ROG-003" in ids


def test_refuses_rfa_source(tmp_path):
    matter = _matter(tmp_path)
    rfa = matter / "01_discovery_served" / "rfa_set.md"
    rfa.write_text("Request for Admission No. 1: Admit the incident date.\n", encoding="utf-8")
    assert rog.main(["parse-rog", str(matter), "--source", str(rfa)]) == 2


def test_audit_flags_unsourced_liability(tmp_path):
    matter = _matter(tmp_path)
    for command in ("parse-rog", "parse-proposed-rog", "audit-rog"):
        assert rog.main([command, str(matter)]) == 0
    rows = _read_jsonl(matter / "02_outputs" / "rog_audit_items.jsonl")
    by_id = {row["proposition_id"]: row for row in rows}
    # Chronology / medical / wage should find support in fixtures.
    chronology = [r for r in rows if r["kind"] == "chronology_assertion"]
    assert chronology and chronology[0]["status"] == "supported"
    medical = [r for r in rows if r["kind"] == "medical_assertion"]
    assert medical and medical[0]["status"] == "supported"
    wage = [r for r in rows if r["kind"] == "wage_assertion"]
    assert wage and wage[0]["status"] == "supported"
    liability = [r for r in rows if r["kind"] == "liability_assertion"]
    assert liability
    assert liability[0]["status"] == "unsupported"
    assert "Unsourced" in liability[0]["notes"]


def test_package_and_validate(tmp_path):
    matter = _matter(tmp_path)
    for command in ("parse-rog", "parse-proposed-rog", "audit-rog", "package-rog-audit"):
        assert rog.main([command, str(matter)]) == 0
    report = (matter / "02_outputs" / "rog_response_audit_report.md").read_text(encoding="utf-8")
    assert "Interrogatory Answer Audit" in report
    assert "Interrogatory 1" in report
    assert "ROG-001" not in report  # Bates-collision-safe display
    assert rog.main(["validate-rog-audit", str(matter)]) == 0


def test_live_mode_enforces_ocr(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    for command in ("parse-rog", "parse-proposed-rog", "audit-rog", "package-rog-audit"):
        assert rog.main([command, str(matter)]) == 0
    (matter / ".synthetic").unlink()
    captured: list[list[str]] = []
    original = rog.run_command

    def _capture(command):
        captured.append(list(command))
        if "live_preflight.py" in " ".join(command):
            return 0
        return original(command)

    monkeypatch.setattr(rog, "run_command", _capture)
    assert rog.main(["validate-rog-audit", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_isolation(tmp_path):
    a = _matter(tmp_path, "SYN-ROG-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-ROG-B", "RIVER-PROD")
    for matter in (a, b):
        for command in ("parse-rog", "parse-proposed-rog", "audit-rog", "package-rog-audit"):
            assert rog.main([command, str(matter)]) == 0
    a_report = (a / "02_outputs" / "rog_response_audit_report.md").read_text(encoding="utf-8")
    b_report = (b / "02_outputs" / "rog_response_audit_report.md").read_text(encoding="utf-8")
    assert "RIVER-PROD" not in a_report
    assert "THORN-PROD" not in b_report


def test_selftest():
    assert rog.main(["selftest"]) == 0
