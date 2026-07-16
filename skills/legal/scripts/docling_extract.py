#!/usr/bin/env python3
"""Extract local matter files with an optionally installed Docling."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def contained_path(matter_dir: Path, value: Path) -> Path:
    """Resolve a source or output path and require it to remain in the matter."""
    path = value.resolve()
    try:
        path.relative_to(matter_dir)
    except ValueError as exc:
        raise ValueError(f"Path must stay under matter directory: {path}") from exc
    return path


def source_path(matter_dir: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    return contained_path(matter_dir, candidate if candidate.is_absolute() else matter_dir / candidate)


def source_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(path for path in source.rglob("*") if path.is_file())
    raise ValueError(f"--src does not exist: {source}")


def load_converter():
    try:
        module = importlib.import_module("docling.document_converter")
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install it locally with: pip install docling"
        ) from exc
    return module.DocumentConverter()


def markdown_from_result(result: object) -> str:
    document = result.document
    export_markdown = getattr(document, "export_to_markdown", None)
    if callable(export_markdown):
        return export_markdown()
    export_text = getattr(document, "export_to_text", None)
    if callable(export_text):
        return export_text()
    raise RuntimeError("Installed Docling result cannot export markdown or text")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-dir", required=True, type=Path)
    parser.add_argument("--src", required=True, help="file or directory under --matter-dir")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("01_production/text"),
        help="output directory relative to --matter-dir (default: 01_production/text)",
    )
    args = parser.parse_args(argv)

    matter_dir = args.matter_dir.resolve()
    if not matter_dir.is_dir():
        print(f"ERROR: --matter-dir does not exist: {matter_dir}", file=sys.stderr)
        return 2
    try:
        src = source_path(matter_dir, args.src)
        out_dir = contained_path(
            matter_dir,
            args.out_dir if args.out_dir.is_absolute() else matter_dir / args.out_dir,
        )
        files = source_files(src)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not files:
        print(f"ERROR: no files found under --src: {src}", file=sys.stderr)
        return 2
    try:
        converter = load_converter()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    failures = 0
    for source in files:
        relative = source.relative_to(matter_dir)
        output = out_dir / relative.with_suffix(".md")
        try:
            output = contained_path(matter_dir, output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(markdown_from_result(converter.convert(str(source))), encoding="utf-8")
            print(f"Wrote {output}")
        except (OSError, RuntimeError) as exc:
            print(f"FAIL {relative}: {exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
