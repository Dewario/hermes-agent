"""Tests for discovery-workflow umbrella dispatcher (SPEC §8)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "discovery_workflow.py"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("discovery_workflow_umbrella", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["discovery_workflow_umbrella"] = module
    spec.loader.exec_module(module)
    return module


dw = _load()


def test_resolve_known_slices():
    assert dw.resolve_slice("rfa", "audit_incoming_response").name == "rfa_audit.py"
    assert dw.resolve_slice("rog", "draft_outgoing_request").name == "rog_outgoing.py"
    assert dw.resolve_slice("rfp", "draft_outgoing_request").name == "rfp_outgoing.py"
    assert dw.resolve_slice("rfp", "audit_incoming_response").name == "discovery_response.py"


def test_draft_response_resolves():
    assert dw.resolve_slice("rfa", "draft_response").name == "rfa_response_draft.py"
    assert dw.resolve_slice("rfp", "draft_response").name == "rfp_response_draft.py"
    assert dw.resolve_slice("rog", "draft_response").name == "rog_response_draft.py"


def test_unknown_pair_rejected():
    try:
        dw.resolve_slice("rfa", "not_a_mode")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "no slice" in str(exc)


def test_missing_axes_errors():
    assert dw.main(["parse-rfa"]) == 2


def test_dispatch_injects_matter_dir(tmp_path, monkeypatch):
    matter = tmp_path / "m"
    matter.mkdir()
    captured: list[list[str]] = []

    def _fake_forward(path, argv):
        captured.append([path.name, *argv])
        return 0

    monkeypatch.setattr(dw, "forward", _fake_forward)
    code = dw.main([
        "--matter-dir", str(matter),
        "--request-type", "rfa",
        "--mode", "audit_incoming_response",
        "parse-rfa",
    ])
    assert code == 0
    assert captured == [["rfa_audit.py", "parse-rfa", str(matter.expanduser())]]


def test_selftest_all_runs_all_slices(monkeypatch):
    calls: list[str] = []

    def _fake_forward(path, argv):
        calls.append(f"{path.name}:{argv[0]}")
        return 0

    monkeypatch.setattr(dw, "forward", _fake_forward)
    assert dw.main(["selftest-all"]) == 0
    assert len(calls) == len(dw.SLICE_SELFTESTS)
    assert all(c.endswith(":selftest") for c in calls)
    assert any("rfp_request_audit.py" in c for c in calls)
    assert any("rfa_request_audit.py" in c for c in calls)
    assert any("rog_request_audit.py" in c for c in calls)
    assert any("trial_gap.py" in c for c in calls)


def test_dispatch_incoming_request_rfp(monkeypatch):
    captured: list[str] = []

    def _fake_forward(path, argv):
        captured.append(path.name)
        return 0

    monkeypatch.setattr(dw, "forward", _fake_forward)
    assert dw.main([
        "--request-type", "rfp",
        "--mode", "audit_incoming_request",
        "selftest",
    ]) == 0
    assert captured == ["rfp_request_audit.py"]


def test_dispatch_incoming_request_rfa(monkeypatch):
    captured: list[str] = []

    def _fake_forward(path, argv):
        captured.append(path.name)
        return 0

    monkeypatch.setattr(dw, "forward", _fake_forward)
    assert dw.main([
        "--request-type", "rfa",
        "--mode", "audit_incoming_request",
        "selftest",
    ]) == 0
    assert captured == ["rfa_request_audit.py"]


def test_dispatch_incoming_request_rog(monkeypatch):
    captured: list[str] = []

    def _fake_forward(path, argv):
        captured.append(path.name)
        return 0

    monkeypatch.setattr(dw, "forward", _fake_forward)
    assert dw.main([
        "--request-type", "rog",
        "--mode", "audit_incoming_request",
        "selftest",
    ]) == 0
    assert captured == ["rog_request_audit.py"]


def test_dispatch_trial_gap(monkeypatch):
    captured: list[str] = []

    def _fake_forward(path, argv):
        captured.append(path.name)
        return 0

    monkeypatch.setattr(dw, "forward", _fake_forward)
    assert dw.main([
        "--mode", "trial_gap_assessment",
        "selftest",
    ]) == 0
    assert captured == ["trial_gap.py"]


def test_smoke_command_forwards(monkeypatch):
    captured: list[list[str]] = []

    def _fake_forward(path, argv):
        captured.append([path.name, *argv])
        return 0

    monkeypatch.setattr(dw, "forward", _fake_forward)
    assert dw.main(["smoke", "--", "--keep-temp"]) == 0
    assert captured == [["smoke_counsel_pack.py", "--keep-temp"]]


def test_skill_description_length():
    skill = (REPO / "skills" / "legal" / "discovery-workflow" / "SKILL.md").read_text(encoding="utf-8")
    for line in skill.splitlines():
        if line.startswith("description:"):
            desc = line.split(":", 1)[1].strip().strip('"')
            assert len(desc) <= 60, len(desc)
            return
    raise AssertionError("missing description")
