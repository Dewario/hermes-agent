"""Contract tests for the legal deposition-outline skill."""

from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "legal" / "deposition-outline"
SKILL = SKILL_DIR / "SKILL.md"
TEMPLATE = SKILL_DIR / "templates" / "deposition_outline_template.md"
FIXTURE = SKILL_DIR / "fixtures" / "synthetic_witness_statement.md"


def _frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    return match.group(1)


def test_frontmatter_meets_hermes_skill_standards():
    frontmatter = _frontmatter(SKILL.read_text(encoding="utf-8"))

    assert "name: legal-deposition-outline" in frontmatter
    assert "author: ahfullerjd (with Hermes Agent)" in frontmatter
    description = re.search(r'^description: "?(.*?)"?$', frontmatter, re.MULTILINE)
    assert description
    assert len(description.group(1)) <= 60
    assert description.group(1).endswith(".")


def test_skill_contains_required_safety_and_casegraph_guidance():
    text = SKILL.read_text(encoding="utf-8")

    for heading in (
        "## When to Use",
        "## Prerequisites",
        "## How to Run",
        "## Quick Reference",
        "## Procedure",
        "## Pitfalls",
        "## Verification",
    ):
        assert heading in text

    for required_text in (
        "PROVIDER_AUTH",
        "casegraph add-entity",
        "--entity",
        "--grep",
        "verify-cites",
        "check-isolation",
        "--strict",
    ):
        assert required_text in text


def test_template_has_deposition_output_headings():
    text = TEMPLATE.read_text(encoding="utf-8")

    for heading in (
        "# Deposition Outline",
        "## Objectives",
        "## Topic Outlines",
        "## Key Admissions Sought",
        "## Impeachment Points",
        "## Exhibits to Mark / Use",
    ):
        assert heading in text


def test_skill_avoids_prohibited_legal_conclusions():
    text = SKILL.read_text(encoding="utf-8").lower()

    for prohibited_phrase in (
        "proves liability",
        "guarantees recovery",
        "defendant is liable",
        "establishes negligence",
    ):
        assert prohibited_phrase not in text


def test_fixture_is_explicitly_synthetic():
    assert "SYNTHETIC" in FIXTURE.read_text(encoding="utf-8")
