"""Regression: long MCP / process.wait must heartbeat gateway activity.

Without heartbeats, agent.gateway_timeout kills the agent while a legitimate
long MCP call or background process wait is still in flight — the same class
as the approval heartbeat fix (tests/tools/test_approval_heartbeat.py).
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from unittest.mock import MagicMock, patch


def test_mcp_run_on_mcp_loop_heartbeats_while_waiting():
    from tools import mcp_tool as mod

    touches: list[str] = []

    def fake_touch(state, label):
        touches.append(label)
        state["last_touch"] = state["last_touch"] - 100.0

    future = MagicMock()
    future.result.side_effect = [
        concurrent.futures.TimeoutError(),
        concurrent.futures.TimeoutError(),
        "ok",
    ]

    loop = MagicMock()
    loop.is_running.return_value = True

    with patch.object(mod, "_mcp_loop", loop), \
         patch("agent.async_utils.safe_schedule_threadsafe", return_value=future), \
         patch.object(mod, "_wrap_with_home_override", side_effect=lambda c: c), \
         patch("tools.environments.base.touch_activity_if_due", side_effect=fake_touch), \
         patch("tools.interrupt.is_interrupted", return_value=False):
        out = mod._run_on_mcp_loop(coro_or_factory=object(), timeout=30.0)

    assert out == "ok"
    assert any("mcp" in t for t in touches)


def test_process_wait_does_not_clamp_to_terminal_timeout(monkeypatch):
    monkeypatch.setenv("TERMINAL_TIMEOUT", "2")
    from tools.process_registry import ProcessRegistry

    registry = ProcessRegistry()
    session_id = "wait-clamp-test"
    session = MagicMock()
    session.session_id = session_id
    session.command = "sleep 99"
    session.exited = False
    session.exit_code = None
    session.completion_reason = None
    session.termination_source = None
    session.output_buffer = "still going"
    session._completion_event = threading.Event()

    def flip():
        time.sleep(0.3)
        session.exited = True
        session.exit_code = 0
        session._completion_event.set()

    threading.Thread(target=flip, daemon=True).start()

    registry.get = MagicMock(return_value=session)
    registry._refresh_detached_session = MagicMock(side_effect=lambda s: s)
    registry._reconcile_local_exit = MagicMock()
    registry._completion_consumed = set()

    result = registry.wait(session_id, timeout=5)
    assert result["status"] == "exited"
    assert "clamped" not in (result.get("timeout_note") or "")


def test_process_wait_heartbeats_while_blocking(monkeypatch):
    monkeypatch.setenv("TERMINAL_TIMEOUT", "30")
    from tools.process_registry import ProcessRegistry

    touches: list[str] = []

    def fake_touch(state, label):
        touches.append(label)
        state["last_touch"] = state["last_touch"] - 100.0

    registry = ProcessRegistry()
    session_id = "wait-hb-test"
    session = MagicMock()
    session.session_id = session_id
    session.command = "sleep 99"
    session.exited = False
    session.exit_code = None
    session.completion_reason = None
    session.termination_source = None
    session.output_buffer = ""
    session._completion_event = threading.Event()

    def flip():
        time.sleep(0.35)
        session.exited = True
        session.exit_code = 0
        session._completion_event.set()

    threading.Thread(target=flip, daemon=True).start()

    registry.get = MagicMock(return_value=session)
    registry._refresh_detached_session = MagicMock(side_effect=lambda s: s)
    registry._reconcile_local_exit = MagicMock()
    registry._completion_consumed = set()

    with patch("tools.environments.base.touch_activity_if_due", side_effect=fake_touch):
        result = registry.wait(session_id, timeout=5)

    assert result["status"] == "exited"
    assert any("process wait" in t for t in touches)
