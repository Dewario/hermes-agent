#!/usr/bin/env python3
"""Load and merge jurisdiction packs for discovery counsel checkers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - stdlib fallback not attempted
    yaml = None  # type: ignore


PACKS_DIR = Path(__file__).resolve().parent / "packs"


class PackError(RuntimeError):
    """Invalid or disallowed pack configuration."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise PackError("PyYAML is required to load jurisdiction packs")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PackError(f"pack root must be a mapping: {path}")
    return data


def load_pack(
    pack_id: str,
    *,
    overlay_id: str | None = None,
    allow_stub: bool = False,
    packs_dir: Path | None = None,
) -> dict[str, Any]:
    root = packs_dir or PACKS_DIR
    base_path = root / f"{pack_id}.yaml"
    if not base_path.is_file():
        raise PackError(f"unknown jurisdiction_pack: {pack_id}")
    base = _load_yaml(base_path)
    if base.get("overlay"):
        raise PackError(f"{pack_id} is an overlay; set it as case_overlay, not jurisdiction_pack")
    status = str(base.get("status") or "")
    if status == "stub" and not allow_stub:
        raise PackError(f"pack {pack_id} is stub; refuse without allow_stub")
    if status == "deprecated":
        raise PackError(f"pack {pack_id} is deprecated")

    rules: dict[str, dict[str, Any]] = {}
    for rule in base.get("rules") or []:
        rid = rule.get("id")
        if not rid:
            raise PackError(f"{pack_id}: rule missing id")
        rules[str(rid)] = dict(rule)

    overlay_meta = None
    if overlay_id:
        overlay_path = root / f"{overlay_id}.yaml"
        if not overlay_path.is_file():
            raise PackError(f"unknown case_overlay: {overlay_id}")
        overlay = _load_yaml(overlay_path)
        if not overlay.get("overlay"):
            raise PackError(f"{overlay_id} is not an overlay pack")
        if overlay.get("base_pack") != pack_id:
            raise PackError(
                f"overlay {overlay_id} base_pack={overlay.get('base_pack')!r} "
                f"does not match jurisdiction_pack={pack_id!r}"
            )
        ostatus = str(overlay.get("status") or "")
        if ostatus == "stub" and not allow_stub:
            raise PackError(f"overlay {overlay_id} is stub; refuse without allow_stub")
        for rule in overlay.get("rules") or []:
            rid = rule.get("id")
            if not rid:
                raise PackError(f"{overlay_id}: rule missing id")
            rules[str(rid)] = dict(rule)
        overlay_meta = {
            "pack_id": overlay.get("pack_id"),
            "version": overlay.get("version"),
            "status": overlay.get("status"),
        }

    return {
        "jurisdiction_pack": pack_id,
        "case_overlay": overlay_id,
        "base": {
            "pack_id": base.get("pack_id"),
            "version": base.get("version"),
            "status": base.get("status"),
            "title": base.get("title"),
        },
        "overlay": overlay_meta,
        "rules": list(rules.values()),
        "rule_ids": sorted(rules.keys()),
    }


def rules_for_type(loaded: dict[str, Any], request_type: str) -> list[dict[str, Any]]:
    rt = request_type.lower()
    out: list[dict[str, Any]] = []
    for rule in loaded.get("rules") or []:
        applies = [str(x).lower() for x in (rule.get("applies_to") or [])]
        if "all" in applies or rt in applies:
            out.append(rule)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack_id")
    parser.add_argument("--overlay")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--request-type", choices=("rog", "rfp", "rfa", "expert"))
    args = parser.parse_args(argv)
    try:
        loaded = load_pack(args.pack_id, overlay_id=args.overlay, allow_stub=args.allow_stub)
    except PackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.request_type:
        subset = rules_for_type(loaded, args.request_type)
        print(f"{len(subset)} rules for {args.request_type}")
        for rule in subset:
            print(f"  {rule['id']}: {rule.get('citation')}")
    else:
        print(
            f"loaded {loaded['jurisdiction_pack']}"
            + (f"+{loaded['case_overlay']}" if loaded["case_overlay"] else "")
            + f" → {len(loaded['rule_ids'])} rules"
        )
        for rid in loaded["rule_ids"]:
            print(f"  {rid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
