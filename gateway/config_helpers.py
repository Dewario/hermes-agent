"""Side-effect-free gateway config helpers.

Importing ``gateway.run`` runs a heavy module-level bootstrap: it loads
``~/.hermes/.env``, bridges ``config.yaml`` scalars into ``os.environ``, adds
to ``sys.path``/``SSL_CERT_FILE``, and — most consequentially — flips the
process into *gateway mode* by setting ``HERMES_QUIET=1`` and
``HERMES_EXEC_ASK=1`` (output suppressed, exec-approval toggled).

Non-gateway callers that merely need to *read* gateway config — the ``hermes
gateway enroll`` CLI, the relay client, feishu webhooks — must not pay that
cost or be silently switched into gateway mode just to look up a value
(FABLE5 M14). This module carries the pure read so they can import it without
tripping ``gateway.run``'s side effects.

``gateway.run._load_gateway_config`` now delegates here, so the two stay in
lockstep and the ``gateway.run._hermes_home`` test-monkeypatch contract is
preserved (run.py passes its resolved home in explicitly).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def gateway_config_home() -> Path:
    """Resolve the Hermes home gateway config reads should use (override-first).

    Side-effect-free: reads only the ``HERMES_HOME`` override and the default
    home resolver, never importing ``gateway.run``.
    """
    from hermes_constants import get_hermes_home, get_hermes_home_override
    override = get_hermes_home_override()
    if override:
        return Path(override)
    return get_hermes_home()


def load_raw_gateway_config(home: Optional[Path] = None) -> dict:
    """Load and parse ``<home>/config.yaml`` into a raw dict, ``{}`` on error.

    ``home`` defaults to :func:`gateway_config_home` when omitted, so external
    callers (relay, enroll) can invoke it with no arguments. ``gateway.run``
    passes its own resolved home explicitly to preserve the
    ``gateway.run._hermes_home`` test-monkeypatch contract.

    Named distinctly from ``gateway.config.load_gateway_config`` (which builds
    the ``GatewayConfig`` dataclass) — this one returns the normalized raw
    mapping, mirroring ``gateway.run._load_gateway_config``.

    Mirrors ``gateway.run._load_gateway_config`` exactly:

    * reuses the mtime-keyed raw-yaml cache from
      ``hermes_cli.config.read_raw_config`` when *home* matches the canonical
      config path (otherwise a direct read, so monkeypatched-home fixtures
      still work),
    * overlays managed scope so administrator-pinned values are honored,
    * replays the root-model-key normalization ``load_config`` applies
      (#34500).

    Fail-open throughout — a broken/missing config yields ``{}`` rather than
    raising into the caller.
    """
    if home is None:
        home = gateway_config_home()
    config_path = Path(home) / 'config.yaml'
    raw: dict = {}
    used_canonical = False
    try:
        from hermes_cli.config import get_config_path, read_raw_config
        if config_path == get_config_path():
            raw = read_raw_config()
            used_canonical = True
    except Exception:
        pass

    if not used_canonical:
        try:
            if config_path.exists():
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    raw = yaml.safe_load(f) or {}
        except Exception:
            logger.debug("Could not load gateway config from %s", config_path)
            raw = {}

    try:
        from hermes_cli import managed_scope
        raw = managed_scope.apply_managed_overlay(raw if isinstance(raw, dict) else {})
    except Exception:
        pass
    if not isinstance(raw, dict):
        return {}
    try:
        from hermes_cli.config import _normalize_root_model_keys
        raw = _normalize_root_model_keys(raw)
    except Exception:
        pass
    return raw
