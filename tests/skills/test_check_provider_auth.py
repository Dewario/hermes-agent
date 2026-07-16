"""Tests for skills/legal/scripts/check_provider_auth.py (P0-1 gate)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "check_provider_auth.py"
TEMPLATE = REPO / "skills" / "legal" / "templates" / "PROVIDER_AUTH.template.md"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("check_provider_auth", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


auth = _load()


def _write_auth(matter: Path, body: str) -> Path:
    path = matter / "03_attorney" / "PROVIDER_AUTH.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


COMPLETE = """# Provider Authorization — Matter SYN-TEST

## 4. Attestation

- Attorney initials: JD  Date: 2026-07-12
"""


def test_attorney_initials_rejects_template_blanks():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert auth.attorney_initials_complete(text) is False
    assert auth.attorney_initials_complete("") is False
    assert auth.attorney_initials_complete(
        "- Attorney initials: ______  Date: ____________\n"
    ) is False


def test_attorney_initials_accepts_filled_line():
    assert auth.attorney_initials_complete(COMPLETE) is True
    assert auth.attorney_initials_complete(
        "Attorney initials: A.B.  Date: 2026-01-01\n"
    ) is True
    assert auth.attorney_initials_complete("Signed /s/ JD on behalf of firm\n") is True


def test_live_matters_path_detection(tmp_path):
    # Strict: only drive:\Matters\... or /Matters/... — nested pytest dirs do not count.
    nested = tmp_path / "Matters" / "case1"
    nested.mkdir(parents=True)
    assert auth.is_live_matter_path(nested) is False
    assert auth.is_live_matter_path(tmp_path / "other") is False
    # Synthetic POSIX-style /Matters/client when the resolved root segment is Matters.
    # On Windows this is rare in tests; env/force cover enforcement instead.


def test_synthetic_fixture_path_exempt():
    fixture = REPO / "skills" / "legal" / "matter-mail" / "fixtures"
    assert auth.is_synthetic_matter_path(fixture) is True


def test_gate_fails_on_live_without_auth(tmp_path, monkeypatch):
    matter = tmp_path / "LiveCase"
    matter.mkdir(parents=True)
    monkeypatch.delenv("HERMES_REQUIRE_PROVIDER_AUTH", raising=False)
    code, msg = auth.check_provider_auth(matter, force=True)
    assert code == 1
    assert "PROVIDER_AUTH" in msg


def test_gate_passes_when_initialed(tmp_path, monkeypatch):
    matter = tmp_path / "LiveCase"
    matter.mkdir(parents=True)
    _write_auth(matter, COMPLETE)
    monkeypatch.delenv("HERMES_REQUIRE_PROVIDER_AUTH", raising=False)
    code, msg = auth.check_provider_auth(matter, force=True)
    assert code == 0
    assert msg == "ok"


def test_gate_env_force_on_non_matters_path(tmp_path, monkeypatch):
    matter = tmp_path / "scratch_matter"
    matter.mkdir()
    monkeypatch.setenv("HERMES_REQUIRE_PROVIDER_AUTH", "1")
    code, _ = auth.check_provider_auth(matter)
    assert code == 1
    _write_auth(matter, COMPLETE)
    code, _ = auth.check_provider_auth(matter)
    assert code == 0


def test_gate_allow_unsigned_and_synthetic_banner(tmp_path, monkeypatch):
    matter = tmp_path / "PilotSyn"
    matter.mkdir(parents=True)
    monkeypatch.delenv("HERMES_REQUIRE_PROVIDER_AUTH", raising=False)
    code, _ = auth.check_provider_auth(matter, force=True, allow_unsigned=True)
    assert code == 0
    (matter / "README.md").write_text(
        "**SYNTHETIC / NON-CLIENT / TEST ONLY**\n", encoding="utf-8")
    code, msg = auth.check_provider_auth(matter, force=True)
    assert code == 0
    assert "exempt" in msg


def test_cli_exit_codes(tmp_path, monkeypatch):
    matter = tmp_path / "CliCase"
    matter.mkdir(parents=True)
    monkeypatch.delenv("HERMES_REQUIRE_PROVIDER_AUTH", raising=False)
    assert auth.main([str(matter), "--force"]) == 1
    _write_auth(matter, COMPLETE)
    assert auth.main([str(matter), "--force"]) == 0
    assert auth.main([str(matter), "--allow-unsigned-provider-auth"]) == 0
