"""Synthetic tests for legal-discovery-response Phase A audit."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-response" / "scripts" / "discovery_response.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dr = _load(SCRIPT, "discovery_response")
cg = _load(CASEGRAPH, "casegraph_for_discovery_response_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-A", prefix: str = "THORN-PROD") -> Path:
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
    (matter / "01_discovery_served" / "rfp_set.md").write_text(
        "Request for Production No. 1: Produce incident reports for the June 1, 2024 event.\n\n"
        "Request for Production No. 2: Produce photographs of the ladder.\n\n"
        "Request for Production No. 3: Produce testimony supporting wage loss.\n",
        encoding="utf-8",
    )
    (matter / "01_discovery_proposed" / "proposed_rfp_responses.md").write_text(
        "Response to Request for Production No. 1: Plaintiff will produce the June 1, 2024 incident report.\n\n"
        "Response to Request for Production No. 2: Plaintiff has no responsive photographs of the ladder.\n\n"
        "Response to Request for Production No. 3: Plaintiff's wage loss is supported by deposition testimony.\n",
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


def test_parse_rfp_stable_ids_and_canonical_reparse(tmp_path):
    matter = _matter(tmp_path)

    assert dr.main(["parse-rfp", str(matter)]) == 0
    first = json.loads((matter / "02_outputs" / "discovery_requests.json").read_text(encoding="utf-8"))
    assert [item["item_id"] for item in first["items"]] == ["RFP-001", "RFP-002", "RFP-003"]

    assert dr.main(["parse-rfp", str(matter)]) == 0
    second = json.loads((matter / "02_outputs" / "discovery_requests.json").read_text(encoding="utf-8"))
    # Ignore parse timestamp; stable source hash gives identical id/text mapping.
    first_pairs = [(item["item_id"], item["text"]) for item in first["items"]]
    second_pairs = [(item["item_id"], item["text"]) for item in second["items"]]
    assert first_pairs == second_pairs
    assert first["source"]["sha256"] == second["source"]["sha256"]


def test_phase_a_audit_outputs_supported_conflict_and_transcript_cite(tmp_path):
    matter = _matter(tmp_path)

    assert dr.main(["parse-rfp", str(matter)]) == 0
    assert dr.main(["parse-proposed", str(matter)]) == 0
    assert dr.main(["audit-existing", str(matter)]) == 0

    rows = _read_jsonl(matter / "02_outputs" / "response_audit_items.jsonl")
    by_id = {row["proposition_id"]: row for row in rows}
    assert by_id["RFP-001-P01"]["status"] == "supported"
    assert by_id["RFP-001-P01"]["record_cites"][0]["type"] == "bates"
    assert by_id["RFP-002-P01"]["status"] == "conflicts_with_record"
    assert by_id["RFP-002-P01"]["conflict_cites"][0]["type"] == "bates"
    assert by_id["RFP-003-P01"]["status"] == "supported"
    transcript = by_id["RFP-003-P01"]["record_cites"][0]
    assert transcript["type"] == "transcript"
    assert transcript["page"] == 42
    assert transcript["line_start"] == 3


def test_package_and_validate_audit(tmp_path):
    matter = _matter(tmp_path)

    for command in ("parse-rfp", "parse-proposed", "audit-existing", "package-audit"):
        assert dr.main([command, str(matter)]) == 0

    report = matter / "02_outputs" / "response_audit_report.md"
    text = report.read_text(encoding="utf-8")
    assert "# Discovery Response Audit" in text
    assert "conflicts_with_record" in text
    assert "THORN-PROD-000010" in text
    assert "Depo-Wage 42:3-3" in text
    assert dr.main(["validate-audit", str(matter)]) == 0


def test_validate_audit_live_mode_enforces_ocr_queue(tmp_path, monkeypatch):
    """Live matters must not pass --skip-ocr-queue to live_preflight."""
    matter = _matter(tmp_path)
    for command in ("parse-rfp", "parse-proposed", "audit-existing", "package-audit"):
        assert dr.main([command, str(matter)]) == 0
    (matter / ".synthetic").unlink()

    captured: list[list[str]] = []
    original = dr.run_command

    def _capture(command):
        captured.append(list(command))
        if "live_preflight.py" in " ".join(command):
            return 0
        return original(command)

    monkeypatch.setattr(dr, "run_command", _capture)
    assert dr.main(["validate-audit", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_validate_rejects_invalid_transcript_cite(tmp_path):
    matter = _matter(tmp_path)
    for command in ("parse-rfp", "parse-proposed", "audit-existing"):
        assert dr.main([command, str(matter)]) == 0

    rows = _read_jsonl(matter / "02_outputs" / "response_audit_items.jsonl")
    for row in rows:
        if row["proposition_id"] == "RFP-003-P01":
            row["record_cites"] = [{"type": "transcript", "value": "Depo-Wage"}]
    dr.write_jsonl(matter / "02_outputs" / "response_audit_items.jsonl", rows)
    assert dr.main(["package-audit", str(matter)]) == 1


def test_two_synthetic_matters_remain_isolated(tmp_path):
    a = _matter(tmp_path, "SYN-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-B", "RIVER-PROD")

    for matter in (a, b):
        for command in ("parse-rfp", "parse-proposed", "audit-existing", "package-audit"):
            assert dr.main([command, str(matter)]) == 0

    a_report = (a / "02_outputs" / "response_audit_report.md").read_text(encoding="utf-8")
    b_report = (b / "02_outputs" / "response_audit_report.md").read_text(encoding="utf-8")
    assert "RIVER-PROD" not in a_report
    assert "THORN-PROD" not in b_report


def test_selftest_runs_offline():
    assert dr.main(["selftest"]) == 0
