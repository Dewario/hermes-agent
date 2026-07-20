"""Tests for the owner gate review packet assistant."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "owner_gate_assistant.py"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("owner_gate_assistant", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["owner_gate_assistant"] = module
    spec.loader.exec_module(module)
    return module


asst = _load()


def _write_provider_auth(matter: Path) -> None:
    auth = matter / "03_attorney" / "PROVIDER_AUTH.md"
    auth.parent.mkdir(parents=True, exist_ok=True)
    auth.write_text("- Attorney initials: JD  Date: 2026-07-20\n", encoding="utf-8")


def test_refuses_owner_gate_packet_name(tmp_path):
    bad = tmp_path / "OWNER_LIVE_GATE_DRAFT.md"
    with pytest.raises(SystemExit):
        asst._refuse_matching_owner_gate_filename(bad)


def test_assistant_writes_packet_and_json_without_owner_gate_filename(tmp_path, monkeypatch):
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    monkeypatch.setattr(asst, "REPO_ROOT", fake_repo.resolve())
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    _write_provider_auth(matter)
    package = matter / "02_outputs" / "incoming_rfp_request_audit_report.md"
    package.parent.mkdir(parents=True)
    package.write_text("Review package\n", encoding="utf-8")
    packet = matter / "03_attorney" / "GATE_REVIEW_PACKET_D1.md"
    calls: list[tuple[list[str], Path | None]] = []

    def fake_run(command, *, cwd=None):
        calls.append((command, cwd))
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return asst.CommandResult(0, "9718cc340eb3697222ad0d05f7f37f7b9bfe0c52\n", "")
        return asst.CommandResult(0, "ok\n", "")

    monkeypatch.setattr(asst, "run_command", fake_run)

    code = asst.main([
        "--matter-dir", str(matter),
        "--request-type", "rfp",
        "--mode", "audit_incoming_request",
        "--package-output", str(package),
        "--packet-output", str(packet),
    ])

    assert code == 0
    assert packet.is_file()
    assert not packet.name.startswith("OWNER_LIVE_GATE")
    text = packet.read_text(encoding="utf-8")
    assert "[ ] That slice's 9.1-9.3" in text
    assert "owner_signature:" in text
    data = json.loads(packet.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["ready_for_owner_review"] is True
    assert data["slice"] == "D1"
    assert any(command == ["git", "diff", "--check"] and cwd == fake_repo.resolve() for command, cwd in calls)
    preflight = next(c for c in data["checks"] if c["name"] == "full live preflight")
    assert preflight["status"] == "SKIP"
    assert "--request-type" in preflight["command"]
    assert "--mode" in preflight["command"]
    assert "--slice" in preflight["command"]


def test_assistant_fails_closed_without_provider_auth(tmp_path, monkeypatch):
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    monkeypatch.setattr(asst, "REPO_ROOT", fake_repo.resolve())
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    packet = matter / "03_attorney" / "GATE_REVIEW_PACKET_D1.md"
    commands: list[list[str]] = []

    def fake_run(command, *, cwd=None):
        commands.append(command)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return asst.CommandResult(0, "9718cc340eb3697222ad0d05f7f37f7b9bfe0c52\n", "")
        return asst.CommandResult(0, "ok\n", "")

    monkeypatch.setattr(asst, "run_command", fake_run)

    code = asst.main([
        "--matter-dir", str(matter),
        "--request-type", "rfp",
        "--mode", "audit_incoming_request",
        "--packet-output", str(packet),
    ])

    assert code == 1
    data = json.loads(packet.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["ready_for_owner_review"] is False
    assert any(c["name"] == "provider authorization" and c["status"] == "FAIL" for c in data["checks"])
    assert not any("casegraph.py" in " ".join(command) for command in commands)


def test_assistant_supports_expert_needs_packet(tmp_path, monkeypatch):
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    monkeypatch.setattr(asst, "REPO_ROOT", fake_repo.resolve())
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    _write_provider_auth(matter)
    package = matter / "02_outputs" / "expert_needs_assessment.md"
    package.parent.mkdir(parents=True)
    package.write_text("Expert needs package\n", encoding="utf-8")
    packet = matter / "03_attorney" / "GATE_REVIEW_PACKET_E1.md"

    def fake_run(command, *, cwd=None):
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return asst.CommandResult(0, "9718cc340eb3697222ad0d05f7f37f7b9bfe0c52\n", "")
        return asst.CommandResult(0, "ok\n", "")

    monkeypatch.setattr(asst, "run_command", fake_run)

    code = asst.main([
        "--matter-dir", str(matter),
        "--request-type", "expert",
        "--mode", "expert_needs_assessment",
        "--package-output", str(package),
        "--packet-output", str(packet),
    ])

    assert code == 0
    data = json.loads(packet.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["slice"] == "E1"
    assert data["request_type"] == "expert"
    verify = next(c for c in data["checks"] if c["name"] == "verify cites")
    assert "--allow-empty" in verify["command"]
    preflight = next(c for c in data["checks"] if c["name"] == "full live preflight")
    assert preflight["command"][preflight["command"].index("--slice") + 1] == "E1"
