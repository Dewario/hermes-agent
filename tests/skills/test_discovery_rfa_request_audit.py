"""Synthetic tests for Slice D2 RFA audit_incoming_request."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "rfa_request_audit.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = _load(SCRIPT, "rfa_request_audit")
cg = _load(CASEGRAPH, "casegraph_for_rfa_request_audit_tests")


def _matter(tmp_path: Path, matter_id: str = "SYN-IRFA-A", prefix: str = "THORN-PROD") -> Path:
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
    (matter / "01_discovery_served" / "rfa_set.md").write_text(
        "Request for Admission No. 1: Admit that an incident report exists for the "
        "June 1, 2024 ladder event.\n\n"
        "Request for Admission No. 2: Admit that defendant was negligent AND that "
        "defendant's negligence was the proximate cause of plaintiff's injuries AND "
        "that plaintiff is entitled to judgment as a matter of law.\n\n"
        "Request for Admission No. 3: Admit that counsel's legal advice to plaintiff "
        "concerning settlement was unreasonable.\n",
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
    assert mod.main(["parse-served-rfa", str(matter)]) == 0
    assert mod.main(["audit-incoming-rfa", str(matter)]) == 0
    items = _read_jsonl(matter / "02_outputs" / "incoming_rfa_request_audit_items.jsonl")
    assert len(items) == 3
    assert all(i["rule_ids"] for i in items)
    assert any("not_separately_stated" in (i.get("flags") or []) for i in items)
    assert any("privilege_boundary" in (i.get("flags") or []) for i in items)
    assert any("legal_conclusion" in (i.get("flags") or []) for i in items)
    assert all(i["item_id"].startswith("IR-RFA-") for i in items)
    assert all(i.get("objection_draft") is None for i in items)


def test_rejects_rfp_looking_source(tmp_path):
    matter = _matter(tmp_path)
    (matter / "01_discovery_served" / "rfa_set.md").write_text(
        "Request for Production No. 1: Produce all documents concerning x.\n",
        encoding="utf-8",
    )
    assert mod.main(["parse-served-rfa", str(matter)]) == 2


def test_rejects_missing_profile(tmp_path):
    matter = _matter(tmp_path)
    (matter / "03_attorney" / "matter_profile.yaml").unlink()
    assert mod.main(["parse-served-rfa", str(matter)]) == 0
    assert mod.main(["audit-incoming-rfa", str(matter)]) == 2


def test_king_rfa_limit_excludes_authenticity_requests(tmp_path):
    matter = _matter(tmp_path)
    (matter / "03_attorney" / "matter_profile.yaml").write_text(
        "matter_id: SYN-IRFA-A\n"
        "court: King County Superior Court (synthetic)\n"
        "jurisdiction_pack: wa_state\n"
        "case_overlay: wa_king_county\n"
        "discovery_cutoff: null\n"
        "limits_used:\n"
        "  rog: 0\n"
        "  rfp: null\n"
        "  rfa: 0\n",
        encoding="utf-8",
    )
    merits = [
        f"Request for Admission No. {i}: Admit fact {i} about defendant notice.\n"
        for i in range(1, 26)
    ]
    auth = [
        "Request for Admission No. 26: Admit Exhibit A is a genuine business record.\n",
        "Request for Admission No. 27: Admit Exhibit B is an authentic copy.\n",
    ]
    (matter / "01_discovery_served" / "rfa_set.md").write_text(
        "\n".join(merits + auth),
        encoding="utf-8",
    )
    assert mod.main(["parse-served-rfa", str(matter)]) == 0
    assert mod.main(["audit-incoming-rfa", str(matter)]) == 0
    items = _read_jsonl(matter / "02_outputs" / "incoming_rfa_request_audit_items.jsonl")
    assert len(items) == 27
    assert sum(1 for i in items if not i["authenticity_exempt"]) == 25
    assert sum(1 for i in items if i["authenticity_exempt"]) == 2
    assert not any("exceeds_numerical_limit" in (i.get("flags") or []) for i in items)
    meta = json.loads((matter / "02_outputs" / "incoming_rfa_request_audit_meta.json").read_text(encoding="utf-8"))
    assert meta["rfa_limit"] == 25
    assert meta["rfa_countable_set_total"] == 25


def test_package_and_validate(tmp_path):
    matter = _matter(tmp_path)
    for command in (
        "parse-served-rfa",
        "audit-incoming-rfa",
        "package-incoming-rfa-audit",
        "validate-incoming-rfa-audit",
    ):
        assert mod.main([command, str(matter)]) == 0
    pkg = (matter / "02_outputs" / "incoming_rfa_request_audit_report.md").read_text(encoding="utf-8")
    assert "Incoming Admission Request Audit" in pkg
    assert "Incoming admission request" in pkg
    assert "RFA-001" not in pkg
    assert "FRCP-36" in pkg or "FRCP-26" in pkg


def test_live_mode_enforces_ocr(tmp_path, monkeypatch):
    matter = _matter(tmp_path)
    for command in ("parse-served-rfa", "audit-incoming-rfa", "package-incoming-rfa-audit"):
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
    assert mod.main(["validate-incoming-rfa-audit", str(matter)]) == 0
    preflight = next(cmd for cmd in captured if "live_preflight.py" in " ".join(cmd))
    assert "--skip-ocr-queue" not in preflight


def test_isolation(tmp_path):
    a = _matter(tmp_path, "SYN-IRFA-A", "THORN-PROD")
    b = _matter(tmp_path, "SYN-IRFA-B", "RIVER-PROD")
    for matter in (a, b):
        for command in ("parse-served-rfa", "audit-incoming-rfa", "package-incoming-rfa-audit"):
            assert mod.main([command, str(matter)]) == 0
    a_pkg = (a / "02_outputs" / "incoming_rfa_request_audit_report.md").read_text(encoding="utf-8")
    b_pkg = (b / "02_outputs" / "incoming_rfa_request_audit_report.md").read_text(encoding="utf-8")
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
