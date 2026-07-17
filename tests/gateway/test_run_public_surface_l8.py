"""FABLE5 L8: gateway.run public-surface contract.

History: five modules (api_server, slash_commands, feishu_comment,
send_message_tool, tui_gateway) late-imported ~15 underscore-private symbols
from gateway.run. Because those imports were lazy, renaming a private passed
CI and ImportError'd in production on first user invocation.

End-state (this contract): gateway.run exposes a documented public surface
(late-binding wrappers, so tests may keep monkeypatching the privates), all
production consumers import ONLY public names, and the wrappers' backing
privates still exist. A regression on any leg fails here, not in production.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

# Production modules that late-import from gateway.run. Tests are exempt
# (white-box by design).
_CONSUMER_FILES = [
    "gateway/platforms/api_server.py",
    "gateway/slash_commands.py",
    "plugins/platforms/feishu/feishu_comment.py",
    "tools/send_message_tool.py",
    "tui_gateway/server.py",
]

# The stable public surface external code may rely on.
_PUBLIC_SURFACE = [
    "AGENT_PENDING_SENTINEL",
    "INTERRUPT_REASON_STOP",
    "gateway_home",
    "get_gateway_config",
    "resolve_gateway_model",
    "platform_config_key",
    "get_gateway_runner",
    "profile_runtime_scope",
    "telegramize_command_mentions",
    "redact_approval_command",
    "resolve_runtime_agent_kwargs",
    "resolve_runtime_agent_kwargs_for_provider",
    "resolve_hermes_bin",
    "home_target_env_var",
    "home_thread_env_var",
    "current_max_iterations",
]

# Backing privates the wrappers late-bind to (and that existing tests
# monkeypatch). Removing one breaks the wrapper AND dozens of test patches.
_BACKING_PRIVATES = [
    "_AGENT_PENDING_SENTINEL",
    "_INTERRUPT_REASON_STOP",
    "_hermes_home",
    "_load_gateway_config",
    "_resolve_gateway_model",
    "_platform_config_key",
    "_gateway_runner_ref",
    "_profile_runtime_scope",
    "_telegramize_command_mentions",
    "_redact_approval_command",
    "_resolve_runtime_agent_kwargs",
    "_resolve_runtime_agent_kwargs_for_provider",
    "_resolve_hermes_bin",
    "_home_target_env_var",
    "_home_thread_env_var",
    "_current_max_iterations",
]


def _private_imports_from_gateway_run() -> dict[str, set[str]]:
    """Map each private gateway.run symbol to the consumer files importing it."""
    found: dict[str, set[str]] = {}
    for rel in _CONSUMER_FILES:
        path = _REPO / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "gateway.run":
                for alias in node.names:
                    if alias.name.startswith("_"):
                        found.setdefault(alias.name, set()).add(rel)
    return found


def test_no_production_consumer_imports_privates():
    """The L8 latent-break class: a private import that passes CI and
    ImportErrors in production after a rename. Must stay at zero."""
    offenders = _private_imports_from_gateway_run()
    assert not offenders, (
        f"Private gateway.run imports crept back into production code: "
        f"{ {k: sorted(v) for k, v in offenders.items()} }. Import the public "
        f"surface instead (see the L8 block in gateway/run.py)."
    )


def test_consumers_actually_use_gateway_run():
    """Guard the scanner: if no consumer imports gateway.run at all, the
    contract above is vacuous (paths drifted / module renamed)."""
    uses = 0
    for rel in _CONSUMER_FILES:
        path = _REPO / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "gateway.run":
                uses += 1
    assert uses >= 10, (
        f"Expected the known consumer surface (~26 gateway.run import sites); "
        f"found {uses}. Did a consumer file move?"
    )


@pytest.mark.parametrize("symbol", _PUBLIC_SURFACE)
def test_public_surface_exists(symbol):
    run = importlib.import_module("gateway.run")
    assert hasattr(run, symbol), (
        f"gateway.run.{symbol} is part of the documented public surface "
        f"consumers now import — removing it ImportErrors them in production."
    )


@pytest.mark.parametrize("symbol", _BACKING_PRIVATES)
def test_backing_private_exists(symbol):
    run = importlib.import_module("gateway.run")
    assert hasattr(run, symbol), (
        f"gateway.run.{symbol} backs a public wrapper (late-binding) and is "
        f"monkeypatched by existing tests — do not remove without migrating "
        f"the wrapper and every test patch."
    )


def test_wrappers_late_bind(monkeypatch):
    """Monkeypatching a private must still affect consumers that call the
    public wrapper — this is what makes the migration test-transparent."""
    import gateway.run as run

    monkeypatch.setattr(run, "_resolve_gateway_model", lambda config=None: "patched-model")
    assert run.resolve_gateway_model() == "patched-model"

    monkeypatch.setattr(run, "_hermes_home", Path("C:/patched-home"))
    assert run.gateway_home() == Path("C:/patched-home")

    class _Runner:
        pass

    _r = _Runner()
    monkeypatch.setattr(run, "_gateway_runner_ref", lambda: _r)
    assert run.get_gateway_runner() is _r
