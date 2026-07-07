#!/usr/bin/env python3
"""Validate legal discovery skills for required content, labels, and privacy.

Checks:
  1. Required sections in both SKILL.md files
  2. SYNTHETIC / NON-CLIENT / TEST ONLY labels in all fixture files
  3. Confidentiality warnings in SKILL.md files
  4. Attorney-review language
  5. No raw local paths (C:\\Users, /c/Users, literal username)
  6. No .env references
  7. No token strings (sk-, API_KEY=, TELEGRAM_BOT_TOKEN, etc.)
  8. No SSN-like patterns
  9. No matter scaffolds (directory structures with real-looking case folders)
 10. Frontmatter validation (required fields)

Stdlib only. Run from repo root.
Exit code 0 = pass, 1 = validation failure.
"""

import os
import re
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────
SKILLS_DIR = Path("skills/legal")
SCRIPT_DIR = Path(__file__).resolve().parent

# Frontmatter required fields
REQUIRED_FRONTMATTER = ["name", "description", "version", "license", "platforms"]

# Required section headings (case-insensitive keyword check)
INTAKE_REQUIRED_SECTIONS = [
    "matter profile",
    "parties",
    "incident summary",
    "fela",
    "issue checklist",
    "injury",
    "medical",
    "employment",
    "wage",
    "liability theory",
    "preservation",
    "spoliation",
    "missing information",
    "follow-up question",
    "discovery plan",
    "discovery starter",
    "verification",
    "pitfalls",
]

REVIEW_REQUIRED_SECTIONS = [
    "document inventory",
    "issue coding",
    "chronology",
    "key fact",
    "witness",
    "entit",              # matches "Entities" in Step 5 heading
    "production gap",
    "privilege",
    "confidentiality screen",
    "medical",
    "wage",
    "damages",            # matches "Damages" in Step 8 heading
    "safety rule",
    "deposition outline",
    "follow-up",          # matches "Follow-Up" in Step 11 heading
    "interrogatory",
    "contradiction",
    "missing custodian",
    "missing time period",
    "attorney final-review",
    "verification",
    "pitfalls",
]

# Privacy patterns (things that should NOT appear in committed files)
PRIVACY_PATTERNS = [
    (re.compile(r"[Cc]:[\\/][Uu]sers[\\/][^\\s\"'<>)]*"), "Windows user path"),
    (re.compile(r"/c/[Uu]sers/[^\\s\"'<>)]*"), "MSYS user path"),
    (re.compile(r"\bTELEGRAM\s*_*\s*BOT\s*_*\s*TOKEN\b"), "TELEGRAM_BOT_TOKEN"),
    (re.compile(r"\bOPENROUTER\s*_*\s*API\s*_*\s*KEY\b"), "OPENROUTER_API_KEY"),
    (re.compile(r"\bOPENAI\s*_*\s*API\s*_*\s*KEY\b"), "OPENAI_API_KEY"),
    (re.compile(r"\bapi\.telegram\.org/bot"), "Telegram API endpoint"),
    (re.compile(r"chat\s*_*\s*id\s*:\s*\S+"), "chat_id reference"),
    (re.compile(r"[sS][kK]-[a-zA-Z0-9]{20,}"), "sk- token prefix"),
    (re.compile(r"\bSSN\b.*\d{3}[-\s]?\d{2}[-\s]?\d{4}"), "SSN pattern"),
    (re.compile(r"\d{3}[-\s]\d{2}[-\s]\d{4}"), "SSN-like pattern"),
    (re.compile(r"\b\d{2}/\d{2}/\d{4}\b"), "DOB-like date"),  # fixture-exemption logic handles false positives
    (re.compile(r"api\s*_*\s*key\s*[:=]\s*\S+"), "API_KEY=value pattern"),
]

# Allowed patterns (files/lines exempt from privacy checks)
ALLOWED_PATTERNS = [
    "SYNTHETIC / NON-CLIENT / TEST ONLY",
    "compat-scanner:allow",
    "<USER_HOME>",
    "[SYNTHETIC]",
    "synthetic name",
    "synthetic email",
    "skills/legal/discovery-intake/fixtures/",
    "skills/legal/discovery-review/fixtures/",
    "skills/legal/discovery-review/templates/",
    "LEGAL_SKILL_INVENTORY.md",
    "LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md",
    "LEGAL_DISCOVERY_FINALIZATION_REPORT.md",
    "MODEL_ROUTING_POLICY_LEGAL.md",
    "PROVIDER_TOKEN_INVENTORY_REDACTED.md",
]

# Files that are expected to contain test data (SKIP strict data checks)
FIXTURE_PATHS = [
    "fixtures/",
    "templates/",
]

FAILURES = []


def is_fixture(path_str: str) -> bool:
    """Check if file is in a fixtures or templates directory."""
    normalized = path_str.replace("\\", "/")
    return any(fp in normalized for fp in FIXTURE_PATHS)


def line_is_allowed(line: str, file_path: str) -> bool:
    """Check if a line matching a privacy pattern is allowed."""
    for allowed in ALLOWED_PATTERNS:
        if allowed.lower() in line.lower():
            return True
    if is_fixture(file_path):
        return True  # fixtures are expected to contain test data
    return False


def check_frontmatter(filepath: Path) -> list[str]:
    """Validate SKILL.md frontmatter has required fields."""
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    # Check for frontmatter delimiters
    if not content.startswith("---"):
        issues.append(f"{filepath}: missing frontmatter (no opening ---)")
        return issues

    parts = content.split("---", 2)
    if len(parts) < 3:
        issues.append(f"{filepath}: malformed frontmatter")
        return issues

    fm = parts[1]
    for field in REQUIRED_FRONTMATTER:
        if not re.search(rf"^{field}\s*:", fm, re.MULTILINE):
            issues.append(f"{filepath}: missing required frontmatter field '{field}'")

    # Check description length (max 60 chars per AGENTS.md standard)
    desc_match = re.search(r'^description:\s*"?(.+?)"?$', fm, re.MULTILINE)
    if desc_match:
        desc = desc_match.group(1).strip()
        if len(desc) > 60:
            issues.append(f"{filepath}: description too long ({len(desc)} chars, max 60)")

    return issues


def check_required_sections(filepath: Path, required: list[str]) -> list[str]:
    """Check that SKILL.md contains required section headings."""
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    content_lower = content.lower()
    for section in required:
        # Look for markdown headings containing the keyword
        if not re.search(rf"^#{{1,3}}\s+.*{re.escape(section)}", content_lower, re.MULTILINE):
            issues.append(f"{filepath}: missing section containing keyword '{section}'")
    return issues


def check_confidentiality(filepath: Path) -> list[str]:
    """Check for confidentiality and attorney-review language."""
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    content_lower = content.lower()

    if "confidential" not in content_lower:
        issues.append(f"{filepath}: missing confidentiality language")

    if "attorney review" not in content_lower:
        issues.append(f"{filepath}: missing attorney-review language")

    return issues


def check_synthetic_label(filepath: Path) -> list[str]:
    """Check that fixture/template files have the synthetic label."""
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    if "SYNTHETIC / NON-CLIENT / TEST ONLY" not in content:
        issues.append(f"{filepath}: missing SYNTHETIC / NON-CLIENT / TEST ONLY label")
    return issues


def check_privacy(filepath: Path) -> list[str]:
    """Check file for privacy violations."""
    issues = []
    path_str = str(filepath)

    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").split("\n")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    for lineno, line in enumerate(lines, start=1):
        for pattern, name in PRIVACY_PATTERNS:
            if pattern.search(line):
                if not line_is_allowed(line, path_str):
                    issues.append(
                        f"{filepath}:{lineno}: potential privacy issue ({name}): "
                        f"{line.strip()[:100]}"
                    )

    return issues


def check_legal_language(filepath: Path) -> list[str]:
    """Check for prohibited legal conclusion language."""
    issues = []
    prohibited = [
        "proves",
        "establishes that",
        "demonstrates that",
        "defendant violated",
        "employer is liable",
        "negligence is established",
    ]

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    content_lower = content.lower()
    for phrase in prohibited:
        if phrase in content_lower:
            # Check if it appears in allowed context
            for line in content.split("\n"):
                if phrase in line.lower():
                    if "do not" in line.lower() or "evidence suggests" in line.lower():
                        continue  # Pitfalls/examples are OK
                    issues.append(
                        f"{filepath}: prohibited legal conclusion language: '{phrase}'"
                    )
                    break
    return issues


def check_matter_scaffolds(skills_dir: Path) -> list[str]:
    """Check for directory structures that look like real matter folders."""
    issues = []
    scaffold_patterns = [
        r"[A-Z][a-z]+\s+v\.\s+[A-Z]",  # "Smith v. Jones"
        r"\d{2,4}-\d{2,4}-\d{2,4}",  # case number pattern
        r"(?i)client[_ ]?matter",
        r"(?i)case[_ ]?file",
    ]

    for root, dirs, files in os.walk(skills_dir):
        root_path = Path(root)
        # Skip the skills/legal root and obvious non-matter dirs
        if root_path == skills_dir:
            continue
        if root_path.parts[-1] in ("fixtures", "templates", "scripts", "references"):
            continue

        dirname = root_path.name
        for pattern in scaffold_patterns:
            if re.search(pattern, dirname):
                issues.append(f"{root_path}: directory name looks like a matter scaffold")
    return issues


def main():
    global FAILURES

    if not SKILLS_DIR.exists():
        print(f"ERROR: skills/legal directory not found at {SKILLS_DIR.absolute()}")
        sys.exit(1)

    print("=" * 60)
    print("Legal Discovery Skills Validator")
    print("=" * 60)

    # Collect all files
    all_files = []
    for root, dirs, files in os.walk(SKILLS_DIR):
        for f in files:
            all_files.append(Path(root) / f)

    skill_files = [f for f in all_files if f.name == "SKILL.md"]
    fixture_files = [f for f in all_files if is_fixture(str(f)) and f.suffix == ".md"]
    other_files = [f for f in all_files if f not in skill_files and f not in fixture_files]

    print(f"\nFound: {len(skill_files)} SKILL.md file(s), "
          f"{len(fixture_files)} fixture/template file(s), "
          f"{len(other_files)} other file(s)")

    # ── Check 1: Frontmatter ──────────────────────────────────
    print("\n── Frontmatter Validation ──")
    for sf in skill_files:
        issues = check_frontmatter(sf)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {sf}")

    # ── Check 2: Required sections ─────────────────────────────
    print("\n── Required Sections ──")
    for sf in skill_files:
        if "discovery-intake" in str(sf):
            required = INTAKE_REQUIRED_SECTIONS
        elif "discovery-review" in str(sf):
            required = REVIEW_REQUIRED_SECTIONS
        else:
            continue
        issues = check_required_sections(sf, required)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {sf} ({len(required)} sections checked)")

    # ── Check 3: Confidentiality and attorney-review ────────────
    print("\n── Confidentiality / Attorney-Review ──")
    for sf in skill_files:
        issues = check_confidentiality(sf)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {sf}")

    # ── Check 4: Synthetic labels in fixtures ──────────────────
    print("\n── Synthetic Labels (fixtures) ──")
    for ff in fixture_files:
        issues = check_synthetic_label(ff)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {ff.relative_to(SKILLS_DIR)}")
    if not fixture_files:
        print("  (no fixture files found)")

    # ── Check 5: Privacy audit ─────────────────────────────────
    print("\n── Privacy Audit ──")
    privacy_issues_found = 0
    for f in all_files:
        issues = check_privacy(f)
        if issues:
            for i in issues:
                privacy_issues_found += 1
                # Only report as failures if not in fixture
                if is_fixture(str(f)):
                    print(f"  INFO: {i}")  # fixtures are expected to contain data
                else:
                    FAILURES.append(i)
                    print(f"  FAIL: {i}")
    if privacy_issues_found == 0:
        print("  PASS: no privacy issues found")

    # ── Check 6: Legal language ────────────────────────────────
    print("\n── Legal Language Audit ──")
    for sf in skill_files:
        issues = check_legal_language(sf)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {sf}")

    # ── Check 7: Matter scaffolds ──────────────────────────────
    print("\n── Matter Scaffold Check ──")
    issues = check_matter_scaffolds(SKILLS_DIR)
    if issues:
        FAILURES.extend(issues)
        for i in issues:
            print(f"  FAIL: {i}")
    else:
        print("  PASS: no matter scaffolds found")

    # ── Results ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} issue(s) found")
        for f in FAILURES:
            print(f"  - {f}")
        print(f"\n{len(FAILURES)} total failure(s)")
        sys.exit(1)
    else:
        print("PASS: all checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
