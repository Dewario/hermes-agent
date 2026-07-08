"""FABLE5 L7: run_coroutine_sync — safe sync→async bridge on any thread.

asyncio.run() raises RuntimeError when the calling thread already has a
running event loop; callers that wrapped it in a broad except silently lost
the feature (e.g. the Anthropic vision fallback degrading to "Image analysis
failed"). run_coroutine_sync must work in both threading situations and
propagate results/exceptions faithfully.
"""

from __future__ import annotations

import asyncio

import pytest

from agent.async_utils import run_coroutine_sync


async def _double(x):
    await asyncio.sleep(0)
    return x * 2


async def _boom():
    await asyncio.sleep(0)
    raise ValueError("kaboom")


def test_no_running_loop_fast_path():
    assert run_coroutine_sync(_double(21)) == 42


def test_exception_propagates():
    with pytest.raises(ValueError, match="kaboom"):
        run_coroutine_sync(_boom())


def test_works_from_thread_with_running_loop():
    """The case that used to raise: sync code invoked ON a loop thread."""
    async def _driver():
        # We're on the loop thread; calling the sync bridge here must still
        # produce the result (via the worker-thread path), not raise
        # "asyncio.run() cannot be called from a running event loop".
        return run_coroutine_sync(_double(5))

    assert asyncio.run(_driver()) == 10


def test_timeout_enforced():
    async def _sleepy():
        await asyncio.sleep(30)

    with pytest.raises(Exception) as exc_info:
        run_coroutine_sync(_sleepy(), timeout=0.05)
    assert isinstance(exc_info.value, (asyncio.TimeoutError, TimeoutError))
