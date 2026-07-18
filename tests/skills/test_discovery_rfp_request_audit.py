"""Synthetic tests for Slice D1 RFP audit_incoming_request."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "rfp_request_audit.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = _load(SCRIPT, "rfp_request_audit")
cg = _load(CASEGRAPH, "casegraph_for_rfp_request_audit_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-IRFP-A", prefix: str = "THORN-PROD") -> Path:
    matter = tmp_path / matter_id
    (matter / "01_discovery_served").mkdir(parents=True)
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
    (matter / "01_discovery_served" / "rfp_set.md").write_text(
        "Request for Production No. 1: Produce all incident reports concerning the "
        "June 1, 2024 ladder event, limited to January 1, 2023 through June 30, 2024.\n\n"
        "Request for Production No. 2: Produce any and all documents whatsoever relating "
        "to the incident from the beginning of time, including but not limited to emails, "
        "ESI, and each and every communication with counsel.\n\n"
        "Request for Production No. 3: Produce photographs of the ladder taken on or about "
        "June 1, 2024.\n",
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


def test_parse_and_audit_flags(tmp_path):
    matter = _matter(tmp_path)
    assert mod.main(["parse-served-rfp", str(matter)]) == 0
    assert mod.main(["audit-incoming-rfp", str(matter)]) == 0
    items = _read_jsonl(matter / "02_outputs" / "incoming_rfp_request_audit_items.jsonl")
    assert len(items) == 3
    assert all(i["rule_ids"] for i in items)
    assert any("lacks_particularity" in (i.get("flags") or []) for i in items)
    assert any("privilege_boundary" in (i.get("flags") or []) for i in items)
    assert all(i["item_id"].startswith("IR-RFP-") for i in items)
    assert all(i.get("objection_draft") is None for i in items)


def test_rejects_rfa_looking_source(tmp_path):
    matter = _matter(tmp_path)
    (matter / "01_discovery_served" / "rfp_set.md").write_text(
        "Request for Admission No. 1: Admit that x.\n",
        encoding="utf-8",
    )
    assert mod.main(["parse-served-rfp", str(matter)]) == 2


def test_rejects_missing_profile(tmp_path):
    matter = _matter(tmp_path)
    (matter / "03_attorney" / "matter_profile.yaml").unlink()
    assert mod.main(["parse-served-rfp", str(matter)]) == 0
    assert mod.main(["audit-incoming-rfp", str(matter)]) == 2


def test_package_and_validate(tmp_path):
    matter = _matter(tmp_path)
    for command in (
        "parse-served-rfp",
        "audit-incoming-rfp",
        "package-incoming-rfp-audit",
        "validate-incoming-rfp-audit",
    ):
        assert mod.main([command, str(matter)]) == 0
    pkg = (matter / "02_outputs" / "incoming_rfp_request_audit_report.md").read_text(encoding="utf-8")
    assert "Incoming Production Request Audit" in pkg
    assert "Incoming production request" in pkg
    assert "RFP-001" not in pkg
    assert "FRCP-34" in pkg or "FRCP-26" in pkg


def test_live_mode_enforces_ocr(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    for command in ("parse-served-rfp", "audit-incoming-rfp", "package-incoming-rfp-audit"):
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
    assert mod.main(["validate-incoming-rfp-audit", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_isolation(tmp_path):
    a = _matter(tmp_path, "SYN-IRFP-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-IRFP-B", "RIVER-PROD")
    for matter in (a, b):
        for command in ("parse-served-rfp", "audit-incoming-rfp", "package-incoming-rfp-audit"):
            assert mod.main([command, str(matter)]) == 0
    a_pkg = (a / "02_outputs" / "incoming_rfp_request_audit_report.md").read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / "incoming_rfp_request_audit_report.md").read_text(encoding="utf-8")
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
