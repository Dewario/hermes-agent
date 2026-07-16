#!/usr/bin/env python3
"""Verify chronology-table quotations against a matter's local text."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TEXT_SUFFIXES = {".txt", ".md", ".eml", ".csv", ".json", ".xml"}


def normalize(value: str) -> str:
    """Make whitespace differences immaterial without changing words."""
    return re.sub(r"\s+", " ", value).strip()


def quote_cells(chronology: Path) -> list[tuple[int, str]]:
    """Return non-empty Quote cells from Markdown tables with a Quote header."""
    quotes: list[tuple[int, str]] = []
    quote_column: int | None = None

    for line_number, raw_line in enumerate(
        chronology.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.lstrip().startswith("|"):
            quote_column = None
            continue

        cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
        if "Quote" in cells:
            quote_column = cells.index("Quote")
            continue
        if quote_column is None or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if quote_column >= len(cells):
            continue

        quote = cells[quote_column].strip().strip("`").strip()
        if len(quote) >= 2 and quote[0] == quote[-1] and quote[0] in {"'", '"'}:
            quote = quote[1:-1]
        if quote:
            quotes.append((line_number, quote))
    return quotes


def source_files(matter_dir: Path) -> list[Path]:
    """Prefer casegraph cache, then known production text, then text-like files."""
    candidates: list[Path] = []
    for directory in (
        matter_dir / ".casegraph" / "text",
        matter_dir / "01_production" / "text",
    ):
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*") if path.is_file())

    if not candidates:
        candidates.extend(
            path
            for path in matter_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in TEXT_SUFFIXES
            and ".casegraph" not in path.parts
        )
    return candidates


def source_text(matter_dir: Path) -> str:
    """Concatenate local source text, ignoring unreadable files."""
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in source_files(matter_dir)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Markdown chronology Quote cells against matter text."
    )
    parser.add_argument("chronology", type=Path)
    parser.add_argument("matter_dir", type=Path)
    args = parser.parse_args()

    if not args.chronology.is_file():
        parser.error(f"chronology does not exist: {args.chronology}")
    if not args.matter_dir.is_dir():
        parser.error(f"matter directory does not exist: {args.matter_dir}")

    quotes = quote_cells(args.chronology)
    corpus = normalize(source_text(args.matter_dir))
    if not corpus:
        print("No readable source text found.", file=sys.stderr)
        return 1

    misses = [
        (line_number, quote)
        for line_number, quote in quotes
        if normalize(quote) not in corpus
    ]
    if misses:
        for line_number, quote in misses:
            print(f"Missing quote at chronology line {line_number}: {quote!r}", file=sys.stderr)
        return 1

    print(f"All quoted spans verified ({len(quotes)} quote(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
