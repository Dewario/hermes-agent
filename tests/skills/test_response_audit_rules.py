"""Unit tests for A* response-audit rule_id baselines."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "response_audit_rules.py"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("response_audit_rules_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["response_audit_rules_test"] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def test_baselines_per_type():
    rfa = mod.baseline_rule_ids("rfa", status="supported", classification="admit")
    assert "FRCP-36-a-1" in rfa
    rog = mod.baseline_rule_ids("rog", status="unsupported", kind="medical")
    assert "FRCP-33-a-1" in rog
    rfp = mod.baseline_rule_ids("rfp", status="supported")
    assert "FRCP-34-a" in rfp


def test_attach_and_intersect():
    row = mod.attach_rule_ids(
        {"status": "supported", "classification": "admit", "notes": "ok"},
        request_type="rfa",
        available={"FRCP-36-a-1", "FRCP-36-a-4", "FRCP-26-b-1"},
    )
    assert row["rule_ids"]
    assert row["needs_attorney_rule_confirm"] is False
    missing = mod.attach_rule_ids(
        {"status": "supported", "classification": "admit", "notes": "ok"},
        request_type="rfa",
        available={"FRCP-99-fake"},
    )
    assert missing["needs_attorney_rule_confirm"] is True
