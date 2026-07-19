"""Tests for skills/legal/scripts/matter_safety.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "matter_safety.py"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("matter_safety", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["matter_safety"] = module
    spec.loader.exec_module(module)
    return module


ms = _load()


def test_syn_id_rejects_allen_embed():
    assert ms.is_syn_matter_id("SYN-SMOKE-COUNSEL") is True
    assert ms.is_syn_matter_id("SYN-ALLENCASE") is False
    assert ms.is_syn_matter_id("REAL-CLIENT-01") is False


def test_may_skip_ocr_temp_with_marker(tmp_path):
    matter = tmp_path / "SYN-TEMP"
    matter.mkdir()
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    assert ms.may_skip_ocr_queue(matter, synthetic_flag=False) is True


def test_may_skip_ocr_refuses_live_non_syn(tmp_path, monkeypatch):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    monkeypatch.setattr(ms, "is_live_matter_path", lambda _p: True)
    assert ms.may_skip_ocr_queue(matter, synthetic_flag=True) is False


def test_refuse_destructive_non_syn(tmp_path):
    dest = tmp_path / "REAL-CLIENT-01"
    dest.mkdir()
    (dest / "keep.txt").write_text("x\n", encoding="utf-8")
    try:
        ms.refuse_destructive_matter_dir(dest, expected_matter_id="REAL-CLIENT-01")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "SYN" in str(exc)
    assert (dest / "keep.txt").is_file()


def test_owner_gate_rejects_rehearsal_evidence(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    (attorney / "OWNER_LIVE_GATE_D1.md").write_text(
        "# REHEARSAL_EVIDENCE — NOT OWNER APPROVAL\n\n"
        "--- §9.5 ---\n[ ] unchecked\n"
        "owner_signature: VOID — NOT OWNER APPROVAL\n",
        encoding="utf-8",
    )
    ok, detail = ms.owner_live_gate_satisfied(matter)
    assert ok is False
    assert "rehearsal" in detail.lower() or "void" in detail.lower()


def test_refuse_skip_live_preflight_on_live(tmp_path, monkeypatch):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    monkeypatch.setattr(ms, "is_live_matter_path", lambda _p: True)
    try:
        ms.refuse_skip_live_preflight_if_live(matter, skip=True)
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "skip-live-preflight" in str(exc)
