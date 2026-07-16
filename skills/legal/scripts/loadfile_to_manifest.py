#!/usr/bin/env python3
"""Normalize common e-discovery load files into a casegraph Bates manifest.

This helper is deliberately conservative: it records only Bates identifiers
present in DAT/OPT/LFP inputs and writes only within ``--matter-dir``.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable


BATES_RE = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9_.-]*?)[-_](?P<number>\d{3,})\b"
)
BEGIN_FIELDS = {"begdoc", "begbates", "batesbeg", "batesstart", "startbates"}
END_FIELDS = {"enddoc", "endbates", "batesend", "batesstop", "endbates"}
SINGLE_FIELDS = {"bates", "batesnumber", "docid", "documentid", "begdoc"}


def parse_bates(value: object) -> tuple[str, int, int] | None:
    """Return an explicit Bates identifier's prefix, numeric value, and width."""
    match = BATES_RE.search(str(value).strip())
    if not match:
        return None
    number = match.group("number")
    return match.group("prefix"), int(number), len(number)


def _field_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _dialect_for(text: str) -> csv.Dialect:
    delimiter = "\x14" if "\x14" in text else "\t" if "\t" in text else "|"

    class LoadfileDialect(csv.excel):
        pass

    LoadfileDialect.delimiter = delimiter
    LoadfileDialect.quotechar = "þ" if "þ" in text else '"'
    LoadfileDialect.doublequote = True
    LoadfileDialect.skipinitialspace = False
    return LoadfileDialect


def _records_from_optional_loadfile(path: Path) -> list[dict[str, object]] | None:
    """Use an installed optional parser when it exposes a familiar API."""
    try:
        module = importlib.import_module("loadfile")
    except Exception:
        return None

    for name in ("parse", "read", "load"):
        parser = getattr(module, name, None)
        if not callable(parser):
            continue
        try:
            rows = parser(str(path))
            rows = list(rows)
        except Exception:
            continue
        if rows and all(isinstance(row, dict) for row in rows):
            return [dict(row) for row in rows]
    return None


def read_dat(path: Path) -> tuple[list[dict[str, object]], str]:
    """Read common Concordance DAT dialects without requiring dependencies."""
    optional = _records_from_optional_loadfile(path)
    if optional is not None:
        return optional, "loadfile"

    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rows = list(csv.reader(text.splitlines(), dialect=_dialect_for(text)))
    if not rows:
        return [], "stdlib"
    headers = [_field_name(item) for item in rows[0]]
    return [
        {headers[index] if index < len(headers) else str(index): value
         for index, value in enumerate(row)}
        for row in rows[1:]
        if any(value.strip() for value in row)
    ], "stdlib"


def ranges_from_dat(path: Path) -> tuple[list[dict[str, object]], str]:
    records, parser_name = read_dat(path)
    ranges: list[dict[str, object]] = []
    for index, record in enumerate(records, start=2):
        normalized = {_field_name(key): value for key, value in record.items()}
        begin = next((normalized[key] for key in BEGIN_FIELDS if normalized.get(key)), None)
        end = next((normalized[key] for key in END_FIELDS if normalized.get(key)), None)
        if begin is None:
            begin = next((normalized[key] for key in SINGLE_FIELDS if normalized.get(key)), None)
        first = parse_bates(begin) if begin is not None else None
        last = parse_bates(end) if end is not None else first
        if first and last and first[0] == last[0]:
            ranges.append(_range_record(first, last, path, index))
    return ranges, parser_name


def _range_record(
    first: tuple[str, int, int],
    last: tuple[str, int, int],
    source: Path,
    row: int,
) -> dict[str, object]:
    width = max(first[2], last[2])
    start, end = sorted((first[1], last[1]))
    return {
        "prefix": first[0],
        "start": start,
        "end": end,
        "padding": width,
        "source": source.name,
        "row": row,
    }


def ranges_from_opt(path: Path) -> list[dict[str, object]]:
    """Read OPT/LFP image rows, where the first value is normally the Bates ID."""
    rows: list[dict[str, object]] = []
    for row_number, line in enumerate(
        path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1
    ):
        fields = next(csv.reader([line])) if line.strip() else []
        if not fields:
            continue
        item = parse_bates(fields[0])
        if item:
            rows.append(_range_record(item, item, path, row_number))
    return rows


def collect_loadfiles(values: Iterable[str], suffixes: set[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        candidate = Path(value).expanduser()
        if candidate.is_dir():
            paths.extend(
                item for item in candidate.rglob("*") if item.suffix.lower() in suffixes
            )
        elif candidate.suffix.lower() in suffixes:
            paths.append(candidate)
        else:
            raise ValueError(f"Unsupported load-file input: {candidate}")
    return sorted({path.resolve() for path in paths})


def contained_path(matter_dir: Path, value: str | None, default: Path) -> Path:
    path = (matter_dir / value if value and not Path(value).is_absolute()
            else Path(value) if value else default).resolve()
    try:
        path.relative_to(matter_dir)
    except ValueError as exc:
        raise ValueError(f"Output must stay under matter directory: {path}") from exc
    return path


def normalize_ranges(ranges: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[object, ...]] = set()
    result = []
    for item in sorted(ranges, key=lambda row: (
        str(row["prefix"]), int(row["start"]), int(row["end"]), str(row["source"]), int(row["row"])
    )):
        key = tuple(item[key] for key in ("prefix", "start", "end", "padding", "source", "row"))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def manifest_markdown(ranges: list[dict[str, object]], sources: list[Path]) -> str:
    prefixes = sorted({str(item["prefix"]) for item in ranges})
    lines = [
        "# Bates Manifest",
        "",
        "> Generated from load files. Entries are explicit source identifiers; no Bates were inferred.",
        "",
        f"- Load files: {', '.join(path.name for path in sources) or 'none found'}",
        f"- Bates prefixes: {', '.join(prefixes) or 'none found'}",
        f"- Explicit ranges: {len(ranges)}",
        "",
        "| Prefix | Start | End | Padding | Source | Row |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for item in ranges:
        width = int(item["padding"])
        prefix = str(item["prefix"])
        lines.append(
            f"| {prefix} | {prefix}-{int(item['start']):0{width}d} | "
            f"{prefix}-{int(item['end']):0{width}d} | {width} | "
            f"{item['source']} | {item['row']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-dir", required=True, type=Path)
    parser.add_argument("--dat", action="append", default=[], metavar="PATH")
    parser.add_argument("--opt", action="append", default=[], metavar="PATH")
    parser.add_argument(
        "--production-dir", action="append", default=[], metavar="PATH",
        help="directory to scan recursively for DAT, OPT, and LFP files",
    )
    parser.add_argument("--out", help="manifest output relative to --matter-dir")
    parser.add_argument(
        "--json", nargs="?", const="01_production/BATES_MANIFEST.json", metavar="PATH",
        help="also write JSON (default: 01_production/BATES_MANIFEST.json)",
    )
    parser.add_argument(
        "--print-casegraph-init", action="store_true",
        help="print suggested casegraph init commands for discovered prefixes",
    )
    args = parser.parse_args(argv)

    matter_dir = args.matter_dir.resolve()
    if not matter_dir.is_dir():
        print(f"ERROR: --matter-dir does not exist: {matter_dir}", file=sys.stderr)
        return 2
    try:
        dat_paths = collect_loadfiles(args.dat, {".dat"})
        opt_paths = collect_loadfiles(args.opt, {".opt", ".lfp"})
        for value in args.production_dir:
            root = Path(value).expanduser()
            if not root.is_dir():
                raise ValueError(f"--production-dir must be a directory: {root}")
            dat_paths.extend(item.resolve() for item in root.rglob("*.dat"))
            opt_paths.extend(
                item.resolve() for item in root.rglob("*")
                if item.suffix.lower() in {".opt", ".lfp"}
            )
        dat_paths = sorted(set(dat_paths))
        opt_paths = sorted(set(opt_paths))
        out = contained_path(matter_dir, args.out, matter_dir / "01_production" / "BATES_MANIFEST.md")
        json_out = contained_path(matter_dir, args.json, matter_dir / "01_production" / "BATES_MANIFEST.json") if args.json else None
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    ranges: list[dict[str, object]] = []
    parser_names: dict[str, str] = {}
    try:
        for path in dat_paths:
            found, parser_name = ranges_from_dat(path)
            ranges.extend(found)
            parser_names[path.name] = parser_name
        for path in opt_paths:
            ranges.extend(ranges_from_opt(path))
            parser_names[path.name] = "stdlib"
    except OSError as exc:
        print(f"ERROR: cannot read load file: {exc}", file=sys.stderr)
        return 2

    ranges = normalize_ranges(ranges)
    sources = dat_paths + opt_paths
    payload = {
        "schema_version": 1,
        "sources": [path.name for path in sources],
        "parsers": parser_names,
        "prefixes": sorted({str(item["prefix"]) for item in ranges}),
        "ranges": ranges,
        "warning": "Entries are explicit source identifiers; no Bates were inferred.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(manifest_markdown(ranges, sources), encoding="utf-8")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {out} ({len(ranges)} explicit Bates range(s))")
    if json_out:
        print(f"Wrote {json_out}")
    if args.print_casegraph_init:
        for prefix in payload["prefixes"]:
            print(f'casegraph init "{matter_dir}" --bates-prefix "{prefix}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
