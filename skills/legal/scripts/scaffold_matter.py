#!/usr/bin/env python3
"""Create the standard directory layout for a live legal matter."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LEGAL_ROOT = Path(__file__).resolve().parents[1]
AUTH_TEMPLATE = LEGAL_ROOT / "templates" / "PROVIDER_AUTH.template.md"
ANCHORS_TEMPLATE = REPO_ROOT / "pilot" / "anchors.example.json"

DIRECTORIES = (
    "00_intake",
    "01_production/raw",
    "01_production/text",
    "02_outputs",
    "03_attorney",
    "correspondence",
)


def is_inside_repository(path: Path) -> bool:
    """Return whether a resolved path is contained by this checkout."""
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    return True


def copy_if_missing(source: Path, destination: Path) -> bool:
    """Copy a template only when no matter-specific file exists."""
    if destination.exists():
        return False
    shutil.copyfile(source, destination)
    return True


def cite_check_log_stub(matter_id: str) -> str:
    return (
        "# Cite Check Log\n\n"
        "> **ATTORNEY WORK PRODUCT — fill before live use**\n\n"
        f"- Matter ID: {matter_id}\n"
        "- Reviewer:\n"
        "- Date:\n\n"
        "| Claim / output location | Bates citation verified | Attorney initials | Notes |\n"
        "|---|---|---|---|\n"
    )


def bates_manifest_stub(matter_id: str, prefixes: list[str]) -> str:
    prefix_text = ", ".join(prefixes) if prefixes else "Not yet assigned"
    return (
        "# Bates Manifest\n\n"
        "> **ATTORNEY WORK PRODUCT — fill before live use**\n\n"
        f"- Matter ID: {matter_id}\n"
        f"- Bates prefixes: {prefix_text}\n"
        "- Production date:\n"
        "- Source load files:\n\n"
        "| Prefix | Start | End | Padding | Source | Notes |\n"
        "|---|---:|---:|---:|---|---|\n"
    )


def scaffold_matter(matter_dir: Path, matter_id: str | None, prefixes: list[str]) -> int:
    root = matter_dir.expanduser().resolve()
    if is_inside_repository(root):
        print(
            "ERROR: --matter-dir must be outside the hermes-agent git repository: "
            f"{root}",
            file=sys.stderr,
        )
        return 2

    resolved_id = matter_id or root.name
    for relative in DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)

    attorney_dir = root / "03_attorney"
    copy_if_missing(AUTH_TEMPLATE, attorney_dir / "PROVIDER_AUTH.md")
    copy_if_missing(ANCHORS_TEMPLATE, attorney_dir / "anchors.json")

    cite_log = attorney_dir / "cite_check_log.md"
    if not cite_log.exists():
        cite_log.write_text(cite_check_log_stub(resolved_id), encoding="utf-8")

    manifest = root / "01_production" / "BATES_MANIFEST.md"
    if not manifest.exists():
        manifest.write_text(
            bates_manifest_stub(resolved_id, prefixes), encoding="utf-8"
        )

    print(f"Scaffolded matter: {root}")
    print("Next steps:")
    print("1. sign PROVIDER_AUTH: complete 03_attorney/PROVIDER_AUTH.md.")
    print("2. Drop production files into 01_production/raw/.")
    print(
        "3. Run loadfile_to_manifest for DAT/OPT/LFP productions, if applicable."
    )
    print("4. Run casegraph init with the matter ID and Bates prefix(es).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-dir", required=True, type=Path)
    parser.add_argument(
        "--matter-id", help="Matter identifier (defaults to the directory name)"
    )
    parser.add_argument(
        "--bates-prefix",
        action="append",
        default=[],
        help="Expected Bates prefix; repeat for multiple prefixes",
    )
    args = parser.parse_args(argv)
    return scaffold_matter(args.matter_dir, args.matter_id, args.bates_prefix)


if __name__ == "__main__":
    raise SystemExit(main())
