"""Synthetic preparation ladder — refuses live paths; L3 isolation green."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO / "skills" / "legal" / "discovery-workflow" / "scripts"
    / "prepare_synthetic_ladder.py"
)


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("prepare_synthetic_ladder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["prepare_synthetic_ladder"] = module
    spec.loader.exec_module(module)
    return module


def test_refuse_allen_path(tmp_path):
    mod = _load()
    try:
        mod.refuse_live_path(tmp_path / "Allen_matter", allow_matters_synth=False)
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "refused" in str(exc).lower()


def test_refuse_matters_non_synth():
    mod = _load()
    try:
        mod.refuse_live_path(Path(r"C:\Matters\REAL-CLIENT-01"), allow_matters_synth=True)
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "SYN" in str(exc)


def test_l3_isolation_level(tmp_path):
    mod = _load()
    result = mod.level3_isolation(tmp_path)
    assert result["ok"] is True, result


def test_ladder_l3_only(tmp_path):
    mod = _load()
    code = mod.main([
        "--workspace", str(tmp_path / "ws"),
        "--levels", "L3",
        "--report", str(tmp_path / "report.md"),
    ])
    assert code == 0
    assert (tmp_path / "report.md").is_file()
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "PASS" in text
    assert "none" in text.lower() or "Live client files engaged:** none" in text
