"""Tests for the messaging gateway's late MCP tool-snapshot refresh.

When an MCP server connects slower than the bounded wait at agent build
(``wait_for_mcp_discovery`` / ``mcp_discovery_timeout``), the agent is built
without its tools. ``GatewayRunner._schedule_mcp_late_refresh`` waits for
discovery to land, then rebuilds the snapshot — but only while the agent has
not yet made an API call, so it never invalidates a cached prompt prefix.

Mirrors ``tests/test_tui_mcp_late_refresh.py`` with a bare GatewayRunner
(same fixture style as ``test_mcp_reload_refreshes_cached_agents.py``).
"""

from __future__ import annotations

import threading
import time
import types
from collections import OrderedDict

import model_tools
from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.run import GatewayRunner


def _make_fake_agent(initial_tools, *, api_calls=0):
    agent = types.SimpleNamespace()
    agent.tools = list(initial_tools)
    agent.valid_tool_names = {t["function"]["name"] for t in initial_tools}
    agent.enabled_toolsets = None
    agent.disabled_toolsets = None
    agent._api_call_count = api_calls
    agent._user_turn_count = 0
    return agent


def _tool(name):
    return {
        "type": "function",
        "function": {"name": name, "description": "", "parameters": {}},
    }


def _drain_refresh_threads(timeout=5.0):
    deadline = time.time() + timeout
    for th in list(threading.enumerate()):
        if th.name.startswith("gateway-mcp-late-refresh-"):
            th.join(timeout=max(0.0, deadline - time.time()))


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner._agent_cache = OrderedDict()
    runner._agent_cache_lock = threading.Lock()
    return runner


def _install(monkeypatch, *, in_flight, join_result, new_defs):
    """Wire mcp_startup discovery accessors + get_tool_definitions."""
    import hermes_cli.mcp_startup as startup

    monkeypatch.setattr(startup, "mcp_discovery_in_flight", lambda: in_flight)
    monkeypatch.setattr(startup, "join_mcp_discovery", lambda timeout=None: join_result)
    monkeypatch.setattr(model_tools, "get_tool_definitions", lambda **kw: list(new_defs))


def test_late_refresh_adds_tools_when_pre_first_api_call(monkeypatch):
    base = [_tool("read_file"), _tool("write_file")]
    full = base + [_tool("mcp__nous_support__a")]
    agent = _make_fake_agent(base)
    runner = _make_runner()
    session_key = "agent:telegram:dm:u1"
    runner._agent_cache[session_key] = (agent, "sig")

    _install(monkeypatch, in_flight=True, join_result=True, new_defs=full)
    runner._schedule_mcp_late_refresh(session_key, agent)
    _drain_refresh_threads()

    assert len(agent.tools) == 3
    assert "mcp__nous_support__a" in agent.valid_tool_names


def test_no_refresh_when_discovery_not_in_flight(monkeypatch):
    base = [_tool("read_file")]
    agent = _make_fake_agent(base)
    runner = _make_runner()
    session_key = "agent:telegram:dm:u2"
    runner._agent_cache[session_key] = (agent, "sig")

    _install(
        monkeypatch,
        in_flight=False,
        join_result=True,
        new_defs=base + [_tool("x")],
    )
    runner._schedule_mcp_late_refresh(session_key, agent)
    _drain_refresh_threads()

    assert len(agent.tools) == 1


def test_no_refresh_once_api_call_started(monkeypatch):
    """Cache safety: never rebuild the tool list after the first API call."""
    base = [_tool("read_file")]
    full = base + [_tool("mcp__late__b")]
    agent = _make_fake_agent(base, api_calls=1)
    runner = _make_runner()
    session_key = "agent:telegram:dm:u3"
    runner._agent_cache[session_key] = (agent, "sig")

    _install(monkeypatch, in_flight=True, join_result=True, new_defs=full)
    runner._schedule_mcp_late_refresh(session_key, agent)
    _drain_refresh_threads()

    assert len(agent.tools) == 1


def test_no_refresh_when_join_times_out(monkeypatch):
    base = [_tool("read_file")]
    full = base + [_tool("mcp__slow__c")]
    agent = _make_fake_agent(base)
    runner = _make_runner()
    session_key = "agent:telegram:dm:u4"
    runner._agent_cache[session_key] = (agent, "sig")

    _install(monkeypatch, in_flight=True, join_result=False, new_defs=full)
    runner._schedule_mcp_late_refresh(session_key, agent)
    _drain_refresh_threads()

    assert len(agent.tools) == 1


def test_no_refresh_when_cached_agent_replaced(monkeypatch):
    """If the cache entry was swapped while we waited, bail."""
    base = [_tool("read_file")]
    full = base + [_tool("mcp__late__d")]
    agent = _make_fake_agent(base)
    other_agent = _make_fake_agent(base)
    runner = _make_runner()
    session_key = "agent:telegram:dm:u5"
    runner._agent_cache[session_key] = (agent, "sig")

    import hermes_cli.mcp_startup as startup

    monkeypatch.setattr(startup, "mcp_discovery_in_flight", lambda: True)
    monkeypatch.setattr(model_tools, "get_tool_definitions", lambda **kw: list(full))

    def _swap_join(timeout=None):
        runner._agent_cache[session_key] = (other_agent, "sig")
        return True

    monkeypatch.setattr(startup, "join_mcp_discovery", _swap_join)
    runner._schedule_mcp_late_refresh(session_key, agent)
    _drain_refresh_threads()

    assert len(agent.tools) == 1
    assert len(other_agent.tools) == 1


def test_refresh_allowed_when_user_turn_started_but_no_api_yet(monkeypatch):
    """Gateway starts the turn immediately; gate on API calls, not turn count."""
    base = [_tool("read_file")]
    full = base + [_tool("mcp__first_turn__e")]
    agent = _make_fake_agent(base)
    agent._user_turn_count = 1  # turn prologue already ran
    runner = _make_runner()
    session_key = "agent:telegram:dm:u6"
    runner._agent_cache[session_key] = (agent, "sig")

    _install(monkeypatch, in_flight=True, join_result=True, new_defs=full)
    runner._schedule_mcp_late_refresh(session_key, agent)
    _drain_refresh_threads()

    assert "mcp__first_turn__e" in agent.valid_tool_names
