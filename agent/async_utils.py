"""Async/sync bridging helpers.

The codebase has ~30 sites that schedule a coroutine onto an event loop from a
worker thread via :func:`asyncio.run_coroutine_threadsafe`.  That function can
raise :class:`RuntimeError` (e.g. the loop was closed during a shutdown race),
and when it does the coroutine object is never awaited and never closed —
which triggers a ``"coroutine '<name>' was never awaited"`` RuntimeWarning and
leaks the coroutine's frame until GC.

:func:`safe_schedule_threadsafe` wraps the call, closes the coroutine on
scheduling failure, and returns ``None`` (instead of a half-formed future) so
callers can branch cleanly:

    fut = safe_schedule_threadsafe(coro, loop)
    if fut is None:
        return  # or fallback behavior
    fut.result(timeout=5)

The helper deliberately does NOT also handle ``future.result()`` failures —
that is a separate concern.  Once the loop has accepted the coroutine, its
lifecycle belongs to the loop, not the scheduling thread.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future
from typing import Any, Coroutine, Optional


_DEFAULT_LOGGER = logging.getLogger(__name__)


def safe_schedule_threadsafe(
    coro: Coroutine[Any, Any, Any],
    loop: Optional[asyncio.AbstractEventLoop],
    *,
    logger: Optional[logging.Logger] = None,
    log_message: str = "Failed to schedule coroutine on loop",
    log_level: int = logging.DEBUG,
) -> Optional[Future]:
    """Schedule ``coro`` on ``loop`` from a sync context, leak-safe.

    Returns the :class:`concurrent.futures.Future` on success, or ``None`` if
    the loop is missing or :func:`asyncio.run_coroutine_threadsafe` raised
    (e.g. the loop was closed during a shutdown race).  In all failure paths
    the coroutine is :meth:`close`-d so it does not trigger
    ``"coroutine was never awaited"`` warnings or leak its frame.

    Callers retain full control over what to do with the returned future
    (call ``.result(timeout=...)``, attach ``add_done_callback``, ignore it
    fire-and-forget, etc.).
    """
    log = logger if logger is not None else _DEFAULT_LOGGER

    if loop is None:
        if asyncio.iscoroutine(coro):
            coro.close()
        log.log(log_level, "%s: loop is None", log_message)
        return None

    try:
        return asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception as exc:
        if asyncio.iscoroutine(coro):
            coro.close()
        log.log(log_level, "%s: %s", log_message, exc)
        return None


def run_coroutine_sync(coro: Coroutine[Any, Any, Any], *, timeout: Optional[float] = None) -> Any:
    """Run ``coro`` to completion from synchronous code, safe on any thread.

    ``asyncio.run()`` raises ``RuntimeError`` when the calling thread already
    has a running event loop (e.g. agent methods invoked directly from an
    async frontend instead of via an executor) — and callers that wrap it in
    a broad ``except`` silently lose the feature (FABLE5 L7). This helper
    handles both cases:

    - No running loop on this thread → plain ``asyncio.run`` (fast path; this
      is the normal worker-thread case).
    - Running loop on this thread → execute the coroutine on a short-lived
      worker thread with its own loop and block for the result. This still
      stalls the loop for the duration (callers on a loop thread should
      really ``await``), but it returns the correct result instead of
      raising — degraded, not broken.

    ``timeout`` (seconds) applies to the coroutine itself via
    ``asyncio.wait_for`` in both paths.
    """
    if timeout is not None:
        coro = asyncio.wait_for(coro, timeout)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import threading
    outcome: dict = {}

    def _worker() -> None:
        try:
            outcome["value"] = asyncio.run(coro)
        except BaseException as exc:  # propagate faithfully, incl. CancelledError
            outcome["error"] = exc

    t = threading.Thread(target=_worker, name="run_coroutine_sync", daemon=True)
    t.start()
    t.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")
