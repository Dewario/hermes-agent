"""FABLE5 M20: sync user hooks must not run on the gateway event loop.

A user-authored sync hook doing blocking IO (requests, file writes, sleep)
used to execute inline in HookRegistry.emit/emit_collect — freezing the whole
gateway for every session. Sync handlers now run via asyncio.to_thread; async
handlers are awaited in-loop as before.
"""

from __future__ import annotations

import asyncio
import threading

from gateway.hooks import HookRegistry


def _register(reg: HookRegistry, event: str, fn) -> None:
    # HookRegistry has no public register API (handlers load from hook dirs);
    # tests append into the handler map the same way discover_and_load does.
    reg._handlers.setdefault(event, []).append(fn)


def test_sync_handler_runs_off_loop_thread():
    reg = HookRegistry()
    seen = {}

    def sync_hook(event_type, context):
        seen["tid"] = threading.get_ident()
        seen["event"] = event_type

    _register(reg,"test:evt", sync_hook)

    async def _driver():
        loop_tid = threading.get_ident()
        await reg.emit("test:evt", {"k": "v"})
        return loop_tid

    loop_tid = asyncio.run(_driver())
    assert seen["event"] == "test:evt"
    assert seen["tid"] != loop_tid, (
        "sync hook executed ON the event-loop thread — a blocking hook would "
        "freeze the whole gateway (M20)"
    )


def test_async_handler_still_runs_on_loop():
    reg = HookRegistry()
    seen = {}

    async def async_hook(event_type, context):
        seen["tid"] = threading.get_ident()

    _register(reg,"test:evt", async_hook)

    async def _driver():
        loop_tid = threading.get_ident()
        await reg.emit("test:evt", {})
        return loop_tid

    loop_tid = asyncio.run(_driver())
    assert seen["tid"] == loop_tid, "async hooks should stay on the loop"


def test_emit_collect_gathers_sync_and_async_results():
    reg = HookRegistry()
    _register(reg,"cmd:x", lambda et, ctx: "sync-result")

    async def async_hook(et, ctx):
        return "async-result"

    _register(reg,"cmd:x", async_hook)
    _register(reg,"cmd:x", lambda et, ctx: None)  # None results are dropped

    async def _driver():
        return await reg.emit_collect("cmd:x", {})

    results = asyncio.run(_driver())
    assert results == ["sync-result", "async-result"]


def test_handler_exception_does_not_abort_remaining(capsys):
    reg = HookRegistry()
    calls = []

    def bad(et, ctx):
        raise RuntimeError("hook blew up")

    def good(et, ctx):
        calls.append("good")

    _register(reg,"test:evt", bad)
    _register(reg,"test:evt", good)

    asyncio.run(reg.emit("test:evt", {}))
    assert calls == ["good"]
    assert "hook blew up" in capsys.readouterr().out
