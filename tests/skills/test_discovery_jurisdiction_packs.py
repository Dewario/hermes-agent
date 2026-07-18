"""Unit tests for jurisdiction pack loader (counsel-pack foundation)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "jurisdiction" / "load_pack.py"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("jurisdiction_load_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["jurisdiction_load_pack"] = module
    spec.loader.exec_module(module)
    return module


jp = _load()


def test_load_frcp_with_fela_overlay():
    loaded = jp.load_pack("frcp_generic", overlay_id="fela")
    assert "FRCP-34-b-1" in loaded["rule_ids"]
    assert "FELA-THEME-NOTICE" in loaded["rule_ids"]
    rfp_rules = jp.rules_for_type(loaded, "rfp")
    assert any(r["id"] == "FRCP-34-a" for r in rfp_rules)
    assert any(r["id"] == "FELA-THEME-RAIL-DOCS" for r in rfp_rules)


def test_stub_pack_refused_by_default():
    try:
        jp.load_pack("ca_ccp")
        raise AssertionError("expected PackError")
    except jp.PackError as exc:
        assert "stub" in str(exc).lower()


def test_stub_pack_allowed_explicitly():
    loaded = jp.load_pack("ca_ccp", allow_stub=True)
    assert loaded["base"]["status"] == "stub"
    assert loaded["rule_ids"]


def test_overlay_base_mismatch_fails():
    # fela requires frcp_generic
    try:
        jp.load_pack("ca_ccp", overlay_id="fela", allow_stub=True)
        raise AssertionError("expected PackError")
    except jp.PackError as exc:
        assert "base_pack" in str(exc)


def test_cli_lists_rules():
    assert jp.main(["frcp_generic", "--overlay", "fela", "--request-type", "rfa"]) == 0
