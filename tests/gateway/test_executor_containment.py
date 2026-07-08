"""FABLE5 H9: gateway executor abandoned-worker containment.

An inactivity timeout can abandon a worker thread wedged in an uninterruptible
call (cancelling the asyncio wrapper does not free the OS thread). Without
containment, ~10 such hangs exhaust the fixed 10-worker pool and every session
blocks forever. The runner tracks simultaneously-abandoned workers and recycles
the pool once they approach capacity; a worker that later frees itself
decrements the wedged count so a subsequent timeout doesn't recycle prematurely.
"""

from __future__ import annotations

import threading

from gateway.run import GatewayRunner


class _FakeExecutor:
    def __init__(self):
        self.shutdown_called = False

    def shutdown(self, *args, **kwargs):
        self.shutdown_called = True


class _Fake:
    """Minimal stand-in binding the real GatewayRunner guard methods."""

    _EXECUTOR_MAX_WORKERS = GatewayRunner._EXECUTOR_MAX_WORKERS
    _executor_lock_ref = GatewayRunner._executor_lock_ref
    _note_executor_worker_abandoned = GatewayRunner._note_executor_worker_abandoned
    _note_executor_worker_recovered = GatewayRunner._note_executor_worker_recovered
    _recycle_executor = GatewayRunner._recycle_executor

    def __init__(self):
        self._executor_lock = threading.Lock()
        self._executor = _FakeExecutor()
        self._executor_abandoned = 0


def test_recycles_pool_when_workers_wedge():
    f = _Fake()
    old = f._executor
    # Abandon up to just below the recycle threshold — no recycle yet.
    for _ in range(f._EXECUTOR_MAX_WORKERS - 3):
        f._note_executor_worker_abandoned()
    assert f._executor is old
    assert not old.shutdown_called
    # One more crosses the threshold (max_workers - 2) -> recycle.
    f._note_executor_worker_abandoned()
    assert old.shutdown_called, "old executor must be shut down on recycle"
    assert f._executor is None, "executor nulled so _get_executor builds a fresh pool"
    assert f._executor_abandoned == 0, "wedged count reset after recycle"


def test_recovered_worker_decrements_count():
    f = _Fake()
    f._note_executor_worker_abandoned()
    f._note_executor_worker_abandoned()
    assert f._executor_abandoned == 2
    f._note_executor_worker_recovered()
    assert f._executor_abandoned == 1
    # Never goes negative.
    f._note_executor_worker_recovered()
    f._note_executor_worker_recovered()
    assert f._executor_abandoned == 0


def test_recovery_prevents_premature_recycle():
    """Workers that free themselves must not accumulate toward the threshold."""
    f = _Fake()
    old = f._executor
    # A steady state where each abandonment is soon followed by recovery.
    for _ in range(f._EXECUTOR_MAX_WORKERS * 3):
        f._note_executor_worker_abandoned()
        f._note_executor_worker_recovered()
    assert f._executor is old
    assert not old.shutdown_called
