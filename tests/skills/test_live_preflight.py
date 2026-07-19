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
