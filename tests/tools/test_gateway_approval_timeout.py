"""Tests for approvals.get_gateway_approval_timeout()."""

from __future__ import annotations

from tools import approval as mod


def test_get_gateway_approval_timeout_reads_config(monkeypatch):
    monkeypatch.setattr(
        mod,
        "_get_approval_config",
        lambda: {"gateway_timeout": 2400},
    )
    assert mod.get_gateway_approval_timeout() == 2400


def test_get_gateway_approval_timeout_defaults_to_1800(monkeypatch):
    monkeypatch.setattr(mod, "_get_approval_config", lambda: {})
    assert mod.get_gateway_approval_timeout() == 1800
