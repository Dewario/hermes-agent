#!/usr/bin/env python3
"""Structural and fixture-grounded checks for legal discovery pilot outputs.

Complements scripts/validate_legal_discovery_skills.py (safety/compliance) with
workflow substance checks: required section headers, synthetic fact anchors,
and attorney-gate phrases.

Usage:
  python pilot/check_outputs.py --phase intake --dir pilot_outputs/intake
  python pilot/check_outputs.py --phase review --dir pilot_outputs/review
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

INTAKE_PACKAGE = "intake_package.md"
REVIEW_PACKAGE = "review_package.md"

INTAKE_HEADER_NEEDLES = [
    "matter profile",
    "parties",
    "incident summary",
    "fela",
    "issue checklist",
    "injury",
    "medical",
    "employment",
    "wage",
    "liability",
    "preservation",
    "spoliation",
    "missing",
    "follow-up",
    "discovery plan",
    "discovery starter",
    "verification",
    "pitfalls",
]

REVIEW_HEADER_NEEDLES = [
    "document inventory",
    "issue coding",
    "chronology",
    "key fact",
    "witness",
    "production gap",
    "privilege",
    "confidentiality",
    "medical",
    "wage",
    "damages",
    "safety rule",
    "deposition",
    "follow-up",
    "contradiction",
    "missing custodian",
    "missing time",
    "attorney final",
    "verification",
    "pitfalls",
]

INTAKE_FACT_ANCHORS = [
    "Test Valley Railroad",
    "TVRR",
    "2024-11-12",
    "Northgate",
    "4721",
    "J.T.",
    "rotator cuff",
    "County General",
]

REVIEW_FACT_ANCHORS = [
    "TVRR",
    "Northgate",
    "IR-2024-11472",
    "TVRR-PROD",
    "2024-11-12",
    "J.T.",
]

INTAKE_PROHIBITED = [
    "SOL Deadline",
    "Legal elements required",
    "if calculable",
    "proves liability",
    "defendant is liable",
    "employer is liable",
    "guarantees recovery",
]

INTAKE_GATE_PHRASES = [
    "sol issue flag",
    "attorney review",
    "requires attorney review",
    "45 u.s.c",
]

REVIEW_GATE_PHRASES = [
    "attorney review",
    "requires attorney review",
    "expert review",
    "preflight",
]

SYNTHETIC_LABEL = "SYNTHETIC / NON-CLIENT / TEST ONLY"


def _find_package(directory: Path, default_name: str) -> Path:
    direct = directory / default_name
    if direct.is_file():
        return direct
    md_files = sorted(directory.glob("*.md"))
    md_files = [p for p in md_files if p.name.upper() not in {"RUN_SUMMARY.MD", "STATUS_NEEDS_OWNER.MD"}]
    if len(md_files) == 1:
        return md_files[0]
    if md_files:
        for p in md_files:
            if "package" in p.name.lower():
                return p
        return md_files[0]
    raise FileNotFoundError(f"No markdown output in {directory}")


def _headers(text: str) -> list[str]:
    return [
        line.lstrip("#").strip().lower()
        for line in text.splitlines()
        if line.startswith("#")
    ]


def _header_covers(needles: list[str], headers: list[str]) -> list[str]:
    missing = []
    for needle in needles:
        if not any(needle in h for h in headers):
            missing.append(needle)
    return missing


def _missing_anchors(text: str, anchors: list[str]) -> list[str]:
    lower = text.lower()
    return [a for a in anchors if a.lower() not in lower]


def _find_prohibited(text: str, phrases: list[str]) -> list[str]:
    hits = []
    for phrase in phrases:
        if phrase.lower() in text.lower():
            hits.append(phrase)
    return hits


def _distinct_gate_phrases(phrases: list[str]) -> list[str]:
    """Collapse overlapping phrases so a pair like 'attorney review' and
    'requires attorney review' counts as ONE gate signal, not two (FABLE5 M12).
    Keeps the shortest representative of each overlap group."""
    kept: list[str] = []
    for p in sorted(phrases, key=len):
        pl = p.lower()
        if any(k in pl or pl in k for k in kept):
            continue
        kept.append(pl)
    return kept


def _missing_gate_phrases(text: str, phrases: list[str], min_count: int = 2) -> bool:
    lower = text.lower()
    # Count DISTINCT gate concepts (FABLE5 M12): overlapping substrings such as
    # 'attorney review' ⊂ 'requires attorney review' must not each add to the
    # tally, or a single phrase would satisfy min_count on its own.
    found = sum(1 for p in _distinct_gate_phrases(phrases) if p in lower)
    return found >= min_count


def _empty_required_sections(text: str, needles: list[str]) -> list[str]:
    """Required headers whose section body is empty (FABLE5 L1).

    A section is 'empty' only when there is NO non-blank content -- not even a
    sub-header -- between its heading and the next heading of equal-or-higher
    level. Sub-headers count as content, so a parent section that immediately
    introduces sub-sections is not flagged. The missing-header case is handled
    separately by ``_header_covers``; this catches header-present/body-empty."""
    lines = text.splitlines()
    empties: list[str] = []
    for needle in needles:
        hdr_idx = None
        hdr_level = 0
        for i, line in enumerate(lines):
            if line.startswith("#") and needle in line.lstrip("#").strip().lower():
                hdr_idx = i
                hdr_level = len(line) - len(line.lstrip("#"))
                break
        if hdr_idx is None:
            continue  # missing entirely -> _header_covers reports it
        body = 0
        for j in range(hdr_idx + 1, len(lines)):
            line = lines[j]
            if line.startswith("#"):
                lvl = len(line) - len(line.lstrip("#"))
                if lvl <= hdr_level:
                    break
                body += 1  # a sub-header is content
                continue
            if line.strip():
                body += 1
        if body == 0:
            empties.append(needle)
    return empties


def _load_anchors(path: Path | None, defaults: list[str]) -> tuple[list[str], str | None]:
    """Load per-matter anchors from JSON, or fall back to synthetic defaults.

    Expected JSON shape::
        {"fact_anchors": ["..."], "bates_regex": "ACME-PROD-\\\\d+",
         "require_synthetic_banner": false}
    """
    if path is None:
        return list(defaults), None
    data = json.loads(path.read_text(encoding="utf-8"))
    anchors = list(data.get("fact_anchors") or defaults)
    bates_re = data.get("bates_regex")
    return anchors, bates_re


def check_intake(
    directory: Path,
    anchors: list[str] | None = None,
    *,
    require_synthetic_banner: bool = True,
) -> list[str]:
    issues: list[str] = []
    try:
        package = _find_package(directory, INTAKE_PACKAGE)
    except FileNotFoundError as exc:
        return [str(exc)]

    text = package.read_text(encoding="utf-8", errors="replace")
    if require_synthetic_banner and SYNTHETIC_LABEL not in text:
        issues.append(f"{package}: missing synthetic label banner")

    headers = _headers(text)
    missing_headers = _header_covers(INTAKE_HEADER_NEEDLES, headers)
    if missing_headers:
        issues.append(
            f"{package}: missing section headers (need ##): {', '.join(missing_headers)}"
        )
    empty_sections = _empty_required_sections(text, INTAKE_HEADER_NEEDLES)
    if empty_sections:
        issues.append(
            f"{package}: sections present but empty (need content): {', '.join(empty_sections)}"
        )

    fact_anchors = anchors if anchors is not None else INTAKE_FACT_ANCHORS
    missing_facts = _missing_anchors(text, fact_anchors)
    if missing_facts:
        issues.append(
            f"{package}: fixture anchors absent (possible hallucination): {', '.join(missing_facts)}"
        )

    prohibited = _find_prohibited(text, INTAKE_PROHIBITED)
    if prohibited:
        issues.append(f"{package}: prohibited phrases: {', '.join(prohibited)}")

    if "sol issue flag" not in text.lower() and "sol issue" not in text.lower():
        issues.append(f"{package}: missing SOL Issue Flag wording")

    if not _missing_gate_phrases(text, INTAKE_GATE_PHRASES, min_count=2):
        issues.append(f"{package}: insufficient attorney-review gate language")

    if "fela" not in text.lower():
        issues.append(f"{package}: missing FELA reference in issue section")

    return issues


def check_review(
    directory: Path,
    anchors: list[str] | None = None,
    *,
    bates_regex: str | None = None,
    require_synthetic_banner: bool = True,
) -> list[str]:
    issues: list[str] = []
    try:
        package = _find_package(directory, REVIEW_PACKAGE)
    except FileNotFoundError as exc:
        return [str(exc)]

    text = package.read_text(encoding="utf-8", errors="replace")
    if require_synthetic_banner and SYNTHETIC_LABEL not in text:
        issues.append(f"{package}: missing synthetic label banner")

    headers = _headers(text)
    missing_headers = _header_covers(REVIEW_HEADER_NEEDLES, headers)
    if missing_headers:
        issues.append(
            f"{package}: missing section headers: {', '.join(missing_headers)}"
        )
    empty_sections = _empty_required_sections(text, REVIEW_HEADER_NEEDLES)
    if empty_sections:
        issues.append(
            f"{package}: sections present but empty (need content): {', '.join(empty_sections)}"
        )

    fact_anchors = anchors if anchors is not None else REVIEW_FACT_ANCHORS
    missing_facts = _missing_anchors(text, fact_anchors)
    if missing_facts:
        issues.append(
            f"{package}: fixture anchors absent: {', '.join(missing_facts)}"
        )

    pattern = bates_regex or r"TVRR-PROD-\d+"
    if not re.search(pattern, text, re.IGNORECASE):
        issues.append(
            f"{package}: no Bates-style Doc ID citations matching /{pattern}/"
        )

    if not _missing_gate_phrases(text, REVIEW_GATE_PHRASES, min_count=2):
        issues.append(f"{package}: insufficient attorney-review / preflight language")

    prohibited = _find_prohibited(text, INTAKE_PROHIBITED)
    if prohibited:
        issues.append(f"{package}: prohibited phrases: {', '.join(prohibited)}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Pilot output structural checks")
    parser.add_argument("--phase", choices=("intake", "review"), required=True)
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="Directory containing intake_package.md or review_package.md",
    )
    parser.add_argument(
        "--anchors",
        type=Path,
        default=None,
        help="Per-matter anchors JSON (fact_anchors, bates_regex, "
             "require_synthetic_banner). Omit for synthetic TVRR defaults.",
    )
    args = parser.parse_args()
    directory = args.dir if args.dir.is_absolute() else REPO_ROOT / args.dir

    if not directory.is_dir():
        print(f"FAIL: directory not found: {directory}")
        return 1

    defaults = INTAKE_FACT_ANCHORS if args.phase == "intake" else REVIEW_FACT_ANCHORS
    anchors_path = args.anchors
    if anchors_path is not None and not anchors_path.is_absolute():
        anchors_path = REPO_ROOT / anchors_path
    fact_anchors, bates_re = _load_anchors(anchors_path, defaults)
    require_banner = True
    if anchors_path is not None:
        cfg = json.loads(anchors_path.read_text(encoding="utf-8"))
        require_banner = bool(cfg.get("require_synthetic_banner", False))

    if args.phase == "intake":
        issues = check_intake(
            directory, fact_anchors, require_synthetic_banner=require_banner,
        )
    else:
        issues = check_review(
            directory,
            fact_anchors,
            bates_regex=bates_re,
            require_synthetic_banner=require_banner,
        )
    if issues:
        print(f"FAIL: {len(issues)} issue(s) for phase={args.phase}")
        for item in issues:
            print(f"  - {item}")
        return 1

    print(f"PASS: phase={args.phase} dir={directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
