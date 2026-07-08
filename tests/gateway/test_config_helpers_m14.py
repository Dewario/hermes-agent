"""FABLE5 M14: gateway config must be readable without tripping gateway.run's
import-time bootstrap.

Importing ``gateway.run`` flips the process into gateway mode (HERMES_QUIET /
HERMES_EXEC_ASK) and runs a heavy .env/config bootstrap. Non-gateway callers
(the enroll CLI, the relay client, feishu webhooks) that only need to read a
config value must be able to do so via ``gateway.config_helpers`` without that
side effect.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import yaml


def test_load_raw_gateway_config_reads_yaml(tmp_path):
    from gateway.config_helpers import load_raw_gateway_config

    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"gateway": {"relay_url": "wss://relay.example/x"}})
    )
    cfg = load_raw_gateway_config(tmp_path)
    assert (cfg.get("gateway") or {}).get("relay_url") == "wss://relay.example/x"


def test_missing_config_returns_empty_dict(tmp_path):
    from gateway.config_helpers import load_raw_gateway_config

    assert load_raw_gateway_config(tmp_path) == {}


def test_importing_helper_does_not_enter_gateway_mode():
    """The core M14 guarantee: importing the helper must not import gateway.run
    nor set the mode-flip env vars. Runs in a clean subprocess so it is not
    fooled by another test having already imported gateway.run."""
    code = textwrap.dedent(
        """
        import os, sys
        assert "gateway.run" not in sys.modules
        import gateway.config_helpers  # noqa: F401
        assert "gateway.run" not in sys.modules, "helper must not import gateway.run"
        assert os.environ.get("HERMES_QUIET") != "1", "import must not set HERMES_QUIET"
        assert os.environ.get("HERMES_EXEC_ASK") != "1", "import must not set HERMES_EXEC_ASK"
        assert os.environ.get("_HERMES_GATEWAY") != "1", "import must not mark gateway mode"
        print("OK")
        """
    )
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=str(repo),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "OK" in result.stdout


def test_run_delegates_and_preserves_home_monkeypatch(monkeypatch, tmp_path):
    """gateway.run._load_gateway_config still works (delegates to the helper)
    and honors the gateway.run._hermes_home monkeypatch contract that existing
    tests rely on."""
    import gateway.run as gr

    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"gateway": {"relay_url": "wss://delegated/y"}})
    )
    monkeypatch.setattr(gr, "_hermes_home", tmp_path)
    monkeypatch.setattr(gr, "get_hermes_home_override", lambda: "")

    cfg = gr._load_gateway_config()
    assert (cfg.get("gateway") or {}).get("relay_url") == "wss://delegated/y"


def test_enroll_and_relay_no_longer_import_run_for_config():
    """Guard against regressing the repoint: the enroll and relay modules must
    read config via gateway.config_helpers, not gateway.run."""
    repo = Path(__file__).resolve().parents[2]
    enroll = (repo / "hermes_cli" / "gateway_enroll.py").read_text(encoding="utf-8")
    relay = (repo / "gateway" / "relay" / "__init__.py").read_text(encoding="utf-8")
    for src, name in ((enroll, "gateway_enroll"), (relay, "relay/__init__")):
        assert "from gateway.run import _load_gateway_config" not in src, (
            f"{name} regressed to importing _load_gateway_config from gateway.run"
        )
        assert "gateway.config_helpers" in src, (
            f"{name} should read config via gateway.config_helpers"
        )
