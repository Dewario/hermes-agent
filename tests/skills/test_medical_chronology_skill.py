"""Contract tests for the legal medical chronology skill."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "legal" / "medical-chronology"


def test_skill_frontmatter_description_meets_hermes_standard():
    source = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r'^description: "([^"]+)"$', source, re.MULTILINE)

    assert match, "SKILL.md must declare a quoted description"
    assert len(match.group(1)) <= 60
    assert match.group(1).endswith(".")


def test_template_has_required_chronology_sections():
    template = (SKILL_DIR / "templates" / "medical_chronology_template.md").read_text(
        encoding="utf-8"
    )

    assert "# Medical Chronology" in template
    assert "| Date | Event | Provider | Source (Bates) | Quote |" in template
    assert "## Verification" in template


def test_pin_quotes_accepts_synthetic_chronology():
    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "scripts" / "pin_quotes.py"),
            str(SKILL_DIR / "fixtures" / "SYNTHETIC_medical_chronology.md"),
            str(SKILL_DIR / "fixtures" / "SYNTHETIC_matter"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "All quoted spans verified" in result.stdout
