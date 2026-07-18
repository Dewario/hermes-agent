"""Synthetic tests for C* draft_response slices."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "legal" / "discovery-workflow" / "scripts"


def _load(name: str):
    path = SCRIPTS / name
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name.replace(".", "_")] = module
    spec.loader.exec_module(module)
    return module


def test_c1_selftest():
    assert _load("rfp_response_draft.py").main(["selftest"]) == 0


def test_c2_selftest():
    assert _load("rfa_response_draft.py").main(["selftest"]) == 0


def test_c3_selftest():
    assert _load("rog_response_draft.py").main(["selftest"]) == 0
