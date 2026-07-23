"""Tests for the live legal matter preflight helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "live_preflight.py"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("live_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


preflight = _load()


def _complete_auth(matter: Path) -> None:
    auth = matter / "03_attorney" / "PROVIDER_AUTH.md"
    auth.parent.mkdir(parents=True)
    auth.write_text("- Attorney initials: JD  Date: 2026-07-12\n", encoding="utf-8")


def _owner_gate(
    matter: Path,
    *,
    request_type: str = "rfp",
    mode: str = "audit_incoming_request",
    slice_id: str = "D1",
) -> None:
    request_choices = {
        "rog": "[x] rog   [ ] rfp   [ ] rfa   [ ] expert",
        "rfp": "[ ] rog   [x] rfp   [ ] rfa   [ ] expert",
        "rfa": "[ ] rog   [ ] rfp   [x] rfa   [ ] expert",
        "expert": "[ ] rog   [ ] rfp   [ ] rfa   [x] expert",
    }[request_type]
    modes = [
        "audit_incoming_response",
        "draft_outgoing_request",
        "audit_incoming_request",
        "trial_gap_assessment",
        "draft_response",
        "expert_needs_assessment",
        "enforcement_motion_draft",
        "objection_motion_draft",
    ]
    choices = "\n                ".join(
        f"[{'x' if item == mode else ' '}] {item}" for item in modes
    )
    path = matter / "03_attorney" / f"OWNER_LIVE_GATE_{slice_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# 9.5 Owner Live Gate - {matter.name}

matter_id:      {matter.name}
request_type:   {request_choices}
mode:           {choices}
tip_commit_sha: 9718cc340eb3697222ad0d05f7f37f7b9bfe0c52
slice:          {slice_id}

--- 9.5 Ready-for-live (OWNER ONLY) ---
[x] That slice's 9.1-9.3 are green on the tip_commit_sha above.
[x] Explicit written approval naming this matter_id + request_type + mode.
[x] Single-matter invocation confirmed.
[x] No client files under the repo.

owner_name:      Responsible Attorney
owner_signature: Responsible Attorney
date:            2026-07-20
""",
        encoding="utf-8",
    )


def test_preflight_stops_after_provider_auth_failure(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "matter"
    matter.mkdir()
    calls = []

    def fake_run(command):
        calls.append(command)
        return preflight.CommandResult(1, "", "authorization missing")

    monkeypatch.setattr(preflight, "run_command", fake_run)

    assert preflight.main(["--matter-dir", str(matter)]) == 1
    assert len(calls) == 1
    assert "FAIL" in capsys.readouterr().out


def test_preflight_runs_all_gates_and_optional_fingerprint(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "matter"
    matter.mkdir()
    _complete_auth(matter)
    (matter / ".casegraph").mkdir()
    output = matter / "02_outputs" / "review.md"
    output.parent.mkdir()
    output.write_text("Review", encoding="utf-8")
    home = tmp_path / "hermes-home"
    fingerprints = home / "casegraph" / "fingerprints.json"
    fingerprints.parent.mkdir(parents=True)
    fingerprints.write_text("{}\n", encoding="utf-8")
    commands = []

    def fake_run(command):
        commands.append(command)
        return preflight.CommandResult(0, "ok", "")

    monkeypatch.setattr(preflight, "run_command", fake_run)
    monkeypatch.setenv("HERMES_HOME", str(home))

    assert preflight.main(["--matter-dir", str(matter), "--output", str(output)]) == 0

    actions = [next(
        action for action in (
            "status", "export-ocr-queue", "verify-cites",
            "verify-chronology", "check-isolation",
        ) if action in command
    ) for command in commands[1:]]
    assert actions == [
        "status", "export-ocr-queue", "verify-cites",
        "verify-chronology", "check-isolation",
    ]
    isolation = commands[-1]
    assert "--strict" in isolation
    assert isolation[isolation.index("--fingerprints") + 1] == str(fingerprints)
    assert "PASS" in capsys.readouterr().out


def test_preflight_warns_and_exits_one_for_ocr_queue(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "matter"
    matter.mkdir()
    _complete_auth(matter)
    (matter / ".casegraph").mkdir()

    def fake_run(command):
        if "export-ocr-queue" in command:
            return preflight.CommandResult(1, "OCR queue: 2", "")
        return preflight.CommandResult(0, "ok", "")

    monkeypatch.setattr(preflight, "run_command", fake_run)

    assert preflight.main(["--matter-dir", str(matter)]) == 1
    assert "WARN" in capsys.readouterr().out


def test_preflight_skip_ocr_queue_and_emit_json(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "matter"
    matter.mkdir()
    _complete_auth(matter)
    (matter / ".casegraph").mkdir()
    commands = []

    def fake_run(command):
        commands.append(command)
        return preflight.CommandResult(0, "ok", "")

    monkeypatch.setattr(preflight, "run_command", fake_run)

    assert preflight.main([
        "--matter-dir", str(matter), "--skip-ocr-queue", "--json",
    ]) == 0
    assert not any("export-ocr-queue" in command for command in commands)
    assert '"status": "PASS"' in capsys.readouterr().out


def test_preflight_refuses_skip_ocr_on_live_non_syn(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    _complete_auth(matter)
    monkeypatch.setattr(preflight._ms, "is_live_matter_path", lambda _p: True)
    monkeypatch.setattr(preflight._ms, "is_syn_matter_id", lambda _m: False)

    assert preflight.main([
        "--matter-dir", str(matter), "--skip-ocr-queue",
    ]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "OCR skip" in out or "skip-ocr" in out.lower()


def test_preflight_rejects_owner_gate_for_wrong_axis(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    _complete_auth(matter)
    _owner_gate(matter, mode="audit_incoming_request")
    monkeypatch.setattr(preflight._ms, "is_live_matter_path", lambda _p: True)
    monkeypatch.setattr(preflight._ms, "is_syn_matter_id", lambda _m: False)

    assert preflight.main([
        "--matter-dir", str(matter),
        "--request-type", "rfp",
        "--mode", "draft_outgoing_request",
        "--slice", "D1",
    ]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "mode mismatch" in out


def test_preflight_accepts_f2_owner_gate_axis(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    _complete_auth(matter)
    _owner_gate(
        matter,
        request_type="rfa",
        mode="objection_motion_draft",
        slice_id="F2",
    )
    monkeypatch.setattr(preflight._ms, "is_live_matter_path", lambda _p: True)
    monkeypatch.setattr(preflight._ms, "is_syn_matter_id", lambda _m: False)
    monkeypatch.setattr(preflight, "run_command", lambda _command: preflight.CommandResult(0, "ok", ""))

    assert preflight.main([
        "--matter-dir", str(matter),
        "--request-type", "rfa",
        "--mode", "objection_motion_draft",
        "--slice", "F2",
    ]) == 0
    assert "PASS" in capsys.readouterr().out
