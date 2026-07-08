"""FABLE5 L8: pin the de-facto public surface of ``gateway.run``.

Several modules reach into ``gateway.run`` for underscore-private symbols via
call-time (late) imports to avoid import cycles::

    def some_handler(...):
        from gateway.run import _AGENT_PENDING_SENTINEL  # late import

Because those imports are lazy, renaming or removing one of the symbols passes
module load, linting, and startup — then throws ``ImportError`` on the first
user invocation in production (the exact latent-break class L8 flags).

This contract test converts that into a CI failure: it AST-scans the known
consumer modules for every private name they import from ``gateway.run`` and
asserts each still resolves. If you intend to rename/remove one of these, this
test is the checklist of consumers that must be migrated in the same change.

The scan is dynamic, so a new private reach-in added to a listed consumer is
covered automatically. A brand-new consumer *file* should be appended to
``_CONSUMER_FILES`` below.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

# External modules that late-import private names from gateway.run.
_CONSUMER_FILES = [
    "gateway/platforms/api_server.py",
    "gateway/slash_commands.py",
    "plugins/platforms/feishu/feishu_comment.py",
    "tools/send_message_tool.py",
    "tui_gateway/server.py",
]


def _reached_in_symbols() -> dict[str, set[str]]:
    """Map each private ``gateway.run`` symbol to the consumer files importing it."""
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


_SYMBOLS = _reached_in_symbols()


def test_discovery_found_the_known_reach_in_surface():
    """Guard the scanner itself: if this drops to near-zero, the consumer list
    or module paths drifted and the contract below is silently vacuous."""
    assert len(_SYMBOLS) >= 10, (
        f"Expected the known private reach-in surface (~14 symbols); found "
        f"{sorted(_SYMBOLS)}. Did a consumer file move?"
    )


@pytest.mark.parametrize("symbol", sorted(_SYMBOLS))
def test_gateway_run_still_exposes_reached_in_symbol(symbol):
    run = importlib.import_module("gateway.run")
    assert hasattr(run, symbol), (
        f"gateway.run.{symbol} is late-imported by "
        f"{sorted(_SYMBOLS[symbol])}. Removing or renaming it passes CI but "
        f"ImportErrors in production on first use — restore it, or migrate "
        f"every listed consumer in the same change."
    )
