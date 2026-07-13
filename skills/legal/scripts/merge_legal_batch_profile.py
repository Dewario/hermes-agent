#!/usr/bin/env python3
"""Merge legal_batch_profile.example.yaml into ~/.hermes/config.yaml (deep merge).

Does not print or modify secrets. Behavior keys only from the example profile.
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required", file=sys.stderr)
    sys.exit(2)

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "skills" / "legal" / "templates" / "legal_batch_profile.example.yaml"
CONFIG = Path.home() / ".hermes" / "config.yaml"


def deep_merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for k, v in overlay.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def main() -> int:
    if not EXAMPLE.is_file():
        print(f"ERROR: missing {EXAMPLE}", file=sys.stderr)
        return 2
    overlay = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8")) or {}
    # Strip comment-only / non-mapping noise
    if not isinstance(overlay, dict):
        print("ERROR: example profile is not a mapping", file=sys.stderr)
        return 2

    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG.is_file():
        existing = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        if not isinstance(existing, dict):
            print("ERROR: existing config.yaml is not a mapping", file=sys.stderr)
            return 2
    else:
        existing = {}

    merged = deep_merge(existing, overlay)
    backup = CONFIG.with_suffix(".yaml.bak-legal-batch")
    if CONFIG.is_file():
        backup.write_bytes(CONFIG.read_bytes())
        print(f"Backup: {backup}")

    CONFIG.write_text(
        yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Merged legal batch profile into {CONFIG}")
    print("Keys applied: " + ", ".join(sorted(overlay.keys())))
    print("Restart the Hermes gateway for timeout/cwd changes to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
