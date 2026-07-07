#!/usr/bin/env python3
"""Validate legal discovery skills for content, labels, privacy, and legal-risk guardrails.

Checks:
  1. Required sections with substantive content (not just headings)
  2. SYNTHETIC / NON-CLIENT / TEST ONLY labels in all fixture files
  3. Confidentiality and attorney-review language
  4. Attorney/source gates in legal-standard sections
  5. Three-tier privacy audit (always-fail, synthetic-gated, self-exclusion)
  6. .env reference detection (read/inspect/copy instructions only)
  7. Prohibited legal-conclusion language (expanded, context-aware)
  8. Provider-token-metadata detection (LGD-006)
  9. Frontmatter validation
 10. Matter scaffold detection

Stdlib only. Run from repo root.
Exit code 0 = pass, 1 = validation failure.

Usage:
  python scripts/validate_legal_discovery_skills.py
  python scripts/validate_legal_discovery_skills.py --strict
  python scripts/validate_legal_discovery_skills.py --self-test
  python scripts/validate_legal_discovery_skills.py --dir <path>
  python scripts/validate_legal_discovery_skills.py --no-policy-docs

NOTE: Zero literal backslash characters exist in this source. All regex patterns
use XBSX sentinels that _compile_patterns() replaces with chr(92) at module load.
Backslashes in runtime code use chr(92) exclusively.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

# -- Configuration -------------------------------------------------

SKILLS_DIR = Path("skills/legal")
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

POLICY_DOCS = [
    "MODEL_ROUTING_POLICY_LEGAL.md",
    "PROVIDER_TOKEN_INVENTORY_REDACTED.md",
    "LEGAL_DISCOVERY_FINALIZATION_REPORT.md",
    "LEGAL_SKILL_INVENTORY.md",
    "LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md",
    "CODEX_RED_TEAM_LEGAL_DISCOVERY_ASSESSMENT.md",
    "CODEX_RED_TEAM_FINDINGS_TABLE.md",
    "HERMES_CURSOR_LEGAL_DISCOVERY_REVISION_PLAN.md",
    "HERMES_CURSOR_IMPLEMENTATION_PROMPT.md",
]

# Red-team docs whose finding descriptions quote prohibited phrases
LEGAL_SCAN_EXEMPT_DOCS = {
    "CODEX_RED_TEAM_FINDINGS_TABLE.md",
    "CODEX_RED_TEAM_LEGAL_DISCOVERY_ASSESSMENT.md",
    "HERMES_CURSOR_LEGAL_DISCOVERY_REVISION_PLAN.md",
    "HERMES_CURSOR_IMPLEMENTATION_PROMPT.md",
}

# Docs exempt from privacy and .env scans -- they discuss findings, contain boundary language
PRIVACY_AND_ENV_EXEMPT_DOCS = LEGAL_SCAN_EXEMPT_DOCS | {
    "LEGAL_DISCOVERY_FINALIZATION_REPORT.md",
    "LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md",
    "LEGAL_SKILL_INVENTORY.md",
}

# Docs exempt from provider-token-metadata scan (they discuss the finding)
# NOTE: PROVIDER_TOKEN_INVENTORY_REDACTED.md is NOT here -- it IS the LGD-006 target
PTM_SCAN_EXEMPT_DOCS = LEGAL_SCAN_EXEMPT_DOCS | {
    "MODEL_ROUTING_POLICY_LEGAL.md",
}

REQUIRED_FRONTMATTER = ["name", "description", "version", "license", "platforms"]

INTAKE_REQUIRED_SECTIONS = [
    "matter profile", "parties", "incident summary", "fela",
    "issue checklist", "injury", "medical", "employment", "wage",
    "liability theory", "preservation", "spoliation", "missing information",
    "follow-up question", "discovery plan", "discovery starter",
    "verification", "pitfalls",
]

REVIEW_REQUIRED_SECTIONS = [
    "document inventory", "issue coding", "chronology", "key fact",
    "witness", "entit", "production gap", "privilege", "confidentiality screen",
    "medical", "wage", "damages", "safety rule", "deposition outline",
    "follow-up", "interrogatory", "contradiction", "missing custodian",
    "missing time period", "attorney final-review", "verification", "pitfalls",
]

SYNTHETIC_LABEL = "SYNTHETIC / NON-CLIENT / TEST ONLY"

# -- Pattern Definitions (all use XBSX for backslash) ---------------

# Tier 1: Always-fail -- forbidden everywhere, including labeled synthetic fixtures
_ALWAYS_FAIL_RAW = [
    (r"[Cc]:[XBSXXBSX/]+[Uu]sers[XBSXXBSX/]+[^XBSXsXBSX<>)]*", "Windows user path"),
    (r"/c/[Uu]sers/[^XBSXsXBSX<>)]*", "MSYS user path (/c/Users/...)"),
    (r"XBSXbapiXBSX.telegramXBSX.org/bot", "Telegram API endpoint"),
    (r"XBSXbchatXBSXs*_*XBSXs*idXBSXs*:XBSXs*XBSXS+", "chat_id reference"),
    (r"(?i)(?:TELEGRAM|OPENROUTER|OPENAI|ANTHROPIC|DEEPSEEK|GEMINI|MINIMAX|PERPLEXITY|LANGCHAIN)XBSXs*_*XBSXs*(?:API|BOT)XBSXs*_*XBSXs*(?:KEY|TOKEN)XBSXs*[:=]", "API/BOT key assignment"),
    (r"apiXBSXs*_*XBSXs*keyXBSXs*[:=]XBSXs*[A-Za-z0-9_XBSX-]{8,}", "API_KEY=value pattern"),
    (r"SECRETXBSXs*_*XBSXs*[:=]XBSXs*XBSXS+", "SECRET=value pattern"),
    (r"TOKENXBSXs*[:=]XBSXs*[A-Za-z0-9_XBSX-]{8,}", "TOKEN=value pattern"),
    (r"[sS][kK]-[a-zA-Z0-9]{20,}", "sk- token prefix"),
    (r"xox[baprs]-[a-zA-Z0-9-]{10,}", "Slack bot/xox token"),
    (r"ghp_[A-Za-z0-9]{36,}", "GitHub personal access token"),
]

# Tier 2: Synthetic-context-gated -- PII shapes allowed only in synthetic-labeled files
_SYNTHETIC_GATED_RAW = [
    (r"XBSXbSSNXBSXb.*XBSXd{3}[-XBSXs]?XBSXd{2}[-XBSXs]?XBSXd{4}", "SSN pattern"),
    (r"(?<![XBSXd#])XBSXd{3}[-XBSXs]XBSXd{2}[-XBSXs]XBSXd{4}", "SSN-like pattern"),
    (r"XBSXbXBSXd{2}/XBSXd{2}/XBSXd{4}XBSXb", "DOB-like date"),
    (r"XBSXbXBSX(?XBSXd{3}XBSX)?[XBSXs.-]XBSXd{3}[XBSXs.-]XBSXd{4}XBSXb", "phone-like pattern"),
    (r"XBSXbXBSXd+[-XBSXs]+[A-Za-z]+XBSXs+(Street|Avenue|Road|Drive|Lane|Blvd|Way|Court|Place|Circle|Highway|Hwy)XBSXb", "address-like pattern"),
    (r"(MedicalXBSXs+Record|MRN|MedicalXBSXs+RecordXBSXs+Number)XBSXs*[:#]XBSXs*XBSXd", "medical record number"),
]

# .env detection (LGD-003) -- tightened: path-ref requires slash/tilde prefix
_ENV_REFERENCE_RAW = [
    (r"(?i)(?:read|inspect|print|cat|copy|open|load|source)XBSXs+.*XBSX.env", ".env read/inspect instruction"),
    (r"(?i)(?:/|XBSX|~/)XBSX.envXBSXb", ".env file path reference"),
]

# Provider-token-metadata detection (LGD-006)
_PTM_RAW = [
    (r"(?i)tokenXBSXs+(?:available|present|found|exists)", "token availability claim"),
    (r"(?i)(?:anthropic|openai|deepseek|gemini|minimax|openrouter|perplexity|langchain).*(?:token|apiXBSXs+key).*(?:present|available|yes)", "provider-token presence row"),
    (r"(?i)directXBSXs+apiXBSXs+routeXBSXs*XBSX|", "Direct API Route column"),
    (r"(?i)providerXBSXs*XBSX|XBSXs*tokenXBSXs*XBSX|XBSXs*(?:filename|presence|available)", "provider token inventory header"),
    (r"(?i)TokenXBSXs+AvailableXBSXs+.*(?:Yes|Available)", "Token Available cell"),
]

# Legal-conclusion patterns (LGD-005)
_PROHIBITED_LEGAL_RAW = [
    (r"XBSXbproves?XBSXs+(?:theXBSXs+)?(?:liability|fault|negligence|causation|cause)XBSXb", "proves liability/fault/negligence"),
    (r"XBSXbestablishes?XBSXs+(?:theXBSXs+)?(?:liability|negligence|causation|cause|fault)XBSXb", "establishes liability/negligence"),
    (r"XBSXbdemonstrates?XBSXs+(?:theXBSXs+)?(?:liability|negligence|causation|cause)XBSXb", "demonstrates liability/negligence"),
    (r"XBSXblegallyXBSXs+sufficientXBSXb", "legally sufficient"),
    (r"XBSXbguarante(?:e|es)XBSXs+(?:dXBSXs+)?recoveryXBSXb", "guarantees/guaranteed recovery"),
    (r"XBSXbdefinitiveXBSXs+(?:medicalXBSXs+)?causationXBSXb", "definitive causation"),
    (r"XBSXbdefendantXBSXs+isXBSXs+liableXBSXb", "defendant is liable"),
    (r"XBSXbemployerXBSXs+isXBSXs+liableXBSXb", "employer is liable"),
    (r"XBSXbplaintiffXBSXs+isXBSXs+entitledXBSXb", "plaintiff is entitled"),
    (r"XBSXbnegligenceXBSXs+isXBSXs+establishedXBSXb", "negligence is established"),
    (r"XBSXbclientXBSXs+shouldXBSXs+(?:file|settle|accept|reject|demand|claim|sue|sign)XBSXb", "client should [action]"),
    (r"XBSXbmustXBSXs+(?:file|settle|accept|reject)XBSXb", "must file/settle/accept"),
    (r"XBSXbconclusivelyXBSXs+shows?XBSXb", "conclusively shows"),
]

# Attorney/source gate patterns
_ATTORNEY_GATE_RAW = [
    (r"attorney[XBSXs-]review", "attorney-review"),
    (r"attorney[XBSXs-]provided", "attorney-provided"),
    (r"requires?XBSXs+attorney", "requires attorney"),
    (r"sourceXBSXs*(?:citation|verification|check)", "source citation/verification"),
    (r"XBSXbXBSXd+XBSXs+UXBSX.?SXBSX.?CXBSX.?", "USC citation"),
    (r"XBSXbXBSXd+XBSXs+UXBSX.?SXBSX.XBSXs+XBSXd+", "US Reports citation"),
]

# Sections that MUST contain attorney/source gate language
GATED_SECTIONS = [
    "statute of limitations", "sol deadline", "sol issue flag",
    "legal standard", "legal elements", "causation", "liability",
    "privilege", "damages", "fela",
]

# -- Sentinel Compilation (runs at import) -------------------------

ALWAYS_FAIL_PATTERNS = []
SYNTHETIC_GATED_PATTERNS = []
ENV_REFERENCE_PATTERNS = []
PROVIDER_TOKEN_METADATA_PATTERNS = []
PROHIBITED_LEGAL_PATTERNS = []
ATTORNEY_GATE_PATTERNS = []

FAILURES = []
WARNINGS = []

_PATTERN_COMPILE_ERRORS = []


def _compile_patterns():
    """Compile all XBSX-sentinel pattern lists into re.Pattern objects.
    Records any compilation errors in _PATTERN_COMPILE_ERRORS so --self-test can report them."""
    BS = chr(92)

    def sub(s):
        return s.replace("XBSX", BS)

    for name, raw_list, flags_default in [
        ("ALWAYS_FAIL_PATTERNS", _ALWAYS_FAIL_RAW, 0),
        ("SYNTHETIC_GATED_PATTERNS", _SYNTHETIC_GATED_RAW, 0),
        ("ENV_REFERENCE_PATTERNS", _ENV_REFERENCE_RAW, re.IGNORECASE),
        ("PROVIDER_TOKEN_METADATA_PATTERNS", _PTM_RAW, re.IGNORECASE),
        ("PROHIBITED_LEGAL_PATTERNS", _PROHIBITED_LEGAL_RAW, re.IGNORECASE),
        ("ATTORNEY_GATE_PATTERNS", _ATTORNEY_GATE_RAW, 0),
    ]:
        lst = globals()[name]
        for i, (pat_str, label) in enumerate(raw_list):
            try:
                compiled = re.compile(sub(pat_str), flags_default)
                lst.append((compiled, sub(label)))
            except re.error as e:
                _PATTERN_COMPILE_ERRORS.append(f"{name}[{i}] ({label}): {e}")


_compile_patterns()


def _check_all_patterns_compiled():
    """Verify all pattern lists contain only re.Pattern tuples. Returns list of failures."""
    issues = []
    for name in ["ALWAYS_FAIL_PATTERNS", "SYNTHETIC_GATED_PATTERNS",
                 "ENV_REFERENCE_PATTERNS", "PROVIDER_TOKEN_METADATA_PATTERNS",
                 "PROHIBITED_LEGAL_PATTERNS", "ATTORNEY_GATE_PATTERNS"]:
        lst = globals()[name]
        for i, item in enumerate(lst):
            if not (isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], re.Pattern)):
                issues.append(f"{name}[{i}]: not a compiled (re.Pattern, str) tuple")
    if _PATTERN_COMPILE_ERRORS:
        issues.extend(_PATTERN_COMPILE_ERRORS)
    return issues


# -- Sentinel Helpers (no backslash literals) -----------------------

def sentinel(s):
    """Return s with XBSX replaced by actual backslash. For runtime regex construction."""
    return s.replace("XBSX", chr(92))


# -- Utility Functions ---------------------------------------------

def has_synthetic_label(content):
    return SYNTHETIC_LABEL in content


def is_privacy_scan_excluded(file_path):
    normalized = Path(file_path).as_posix()
    return "scripts/validate_legal_discovery_skills.py" in normalized


def is_fixture_path(path_str):
    normalized = Path(path_str).as_posix()
    return "/fixtures/" in normalized or "/templates/" in normalized


def is_legal_scan_exempt(file_path):
    normalized = Path(file_path).as_posix()
    for exempt in LEGAL_SCAN_EXEMPT_DOCS:
        if normalized.endswith(exempt):
            return True
    return False


def is_privacy_env_exempt(file_path):
    normalized = Path(file_path).as_posix()
    for exempt in PRIVACY_AND_ENV_EXEMPT_DOCS:
        if normalized.endswith(exempt):
            return True
    return False


def is_ptm_scan_exempt(file_path):
    normalized = Path(file_path).as_posix()
    for exempt in PTM_SCAN_EXEMPT_DOCS:
        if normalized.endswith(exempt):
            return True
    return False


def get_section_content(content, section_keyword):
    """Extract content under a heading matching section_keyword (case-insensitive)."""
    lines = content.split(chr(10))
    heading_idx = None
    keyword_lower = section_keyword.lower()

    for i, line in enumerate(lines):
        if re.match(sentinel(r"^#{1,3}XBSXs+.*") + re.escape(keyword_lower), line, re.IGNORECASE):
            heading_idx = i
            break

    if heading_idx is None:
        return ""

    body_lines = []
    for j in range(heading_idx + 1, len(lines)):
        if re.match(sentinel(r"^#{1,3}XBSXs+"), lines[j]):
            break
        body_lines.append(lines[j])

    return chr(10).join(body_lines)


def is_in_exempt_context(line, content, match_pos):
    """Determine if a match is in an exempt context (pitfalls, DO NOT).
    Uses section-scoped detection: looks backward to find the enclosing section heading."""
    line_lower = line.lower()

    if re.match(sentinel(r"^XBSXs*(?:do not|never|avoid|#)"), line_lower):
        return True

    if re.search(sentinel(r"XBSXb(do not|never|avoid)XBSXb"), line_lower):
        return True

    lines_before = content[:match_pos].split(chr(10))
    for l in reversed(lines_before):
        ll = l.lower()
        if re.match(sentinel(r"^#{1,3}XBSXs+"), l):
            if "pitfall" in ll or "prohibited" in ll:
                return True
            break

    return False


# -- Check Functions -----------------------------------------------

def check_frontmatter(filepath):
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    if not content.startswith("---"):
        issues.append(f"{filepath}: missing frontmatter (no opening ---)")
        return issues

    parts = content.split("---", 2)
    if len(parts) < 3:
        issues.append(f"{filepath}: malformed frontmatter")
        return issues

    fm = parts[1]
    for field in REQUIRED_FRONTMATTER:
        if not re.search(sentinel(rf"^{field}XBSXs*:"), fm, re.MULTILINE):
            issues.append(f"{filepath}: missing required frontmatter field '{field}'")

    desc_match = re.search(sentinel(r'^description:XBSXs*"?(.+?)"?$'), fm, re.MULTILINE)
    if desc_match:
        desc = desc_match.group(1).strip()
        if len(desc) > 60:
            issues.append(f"{filepath}: description too long ({len(desc)} chars, max 60)")

    return issues


def check_required_sections(filepath, required, strict=False):
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    content_lower = content.lower()
    for section in required:
        if not re.search(sentinel(rf"^#{{1,3}}XBSXs+.*") + re.escape(section),
                         content_lower, re.MULTILINE):
            issues.append(f"{filepath}: missing section containing keyword '{section}'")
        elif strict:
            section_body = get_section_content(content, section)
            body_lines = [l for l in section_body.split(chr(10))
                          if l.strip() and not re.match(sentinel(r"^XBSXs*#"), l)]
            word_count = len(section_body.split())

            if len(body_lines) < 3:
                issues.append(
                    f"{filepath}: section '{section}' has insufficient content "
                    f"({len(body_lines)} substantive lines, minimum 3)"
                )
            elif word_count < 20:
                issues.append(
                    f"{filepath}: section '{section}' has insufficient content "
                    f"({word_count} words, minimum 20)"
                )
    return issues


def check_confidentiality(filepath):
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


def check_synthetic_label(filepath):
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]
    if SYNTHETIC_LABEL not in content:
        issues.append(f"{filepath}: missing {SYNTHETIC_LABEL} label")
    return issues


def check_privacy(filepath, strict=False):
    """Three-tier privacy check. Scans ALL files including fixtures and templates."""
    issues = []
    path_str = str(filepath)

    if is_privacy_scan_excluded(path_str):
        return issues

    if is_privacy_env_exempt(path_str):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    lines = content.split(chr(10))
    is_synthetic = has_synthetic_label(content)

    for lineno, line in enumerate(lines):
        for pattern, name in ALWAYS_FAIL_PATTERNS:
            if pattern.search(line):
                issues.append(
                    f"{filepath}:{lineno + 1}: PRIVACY FAIL ({name}): "
                    f"{line.strip()[:120]}"
                )

        for pattern, name in SYNTHETIC_GATED_PATTERNS:
            if pattern.search(line):
                if not is_synthetic:
                    issues.append(
                        f"{filepath}:{lineno + 1}: PRIVACY FAIL ({name}) -- "
                        f"file lacks synthetic label: {line.strip()[:120]}"
                    )
                elif strict:
                    issues.append(
                        f"{filepath}:{lineno + 1}: PRIVACY WARNING ({name}) -- "
                        f"present in synthetic file: {line.strip()[:120]}"
                    )

    return issues


def check_env_references(filepath):
    """Check for .env file reference instructions in .md files."""
    issues = []
    path_str = str(filepath)

    if is_privacy_scan_excluded(path_str):
        return issues

    if filepath.suffix.lower() not in (".md",):
        return issues

    if is_privacy_env_exempt(path_str):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    lines = content.split(chr(10))
    for lineno, line in enumerate(lines):
        for pattern, name in ENV_REFERENCE_PATTERNS:
            if pattern.search(line):
                ll = line.lower()
                if ".env" in ll:
                    if any(w in ll for w in ("not performed", "not inspected",
                           "not touched", "not read", "must not", "do not",
                           "never", "don't", "no .env", "not inspect")):
                        continue
                issues.append(
                    f"{filepath}:{lineno + 1}: .ENV REFERENCE ({name}): "
                    f"{line.strip()[:120]}"
                )
    return issues


def check_legal_language(filepath):
    """Check for prohibited legal conclusion language with context awareness."""
    issues = []
    path_str = str(filepath)

    if is_privacy_scan_excluded(path_str):
        return issues

    if is_legal_scan_exempt(path_str):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    lines = content.split(chr(10))
    for pattern, pattern_name in PROHIBITED_LEGAL_PATTERNS:
        for match in pattern.finditer(content):
            match_lineno = content[:match.start()].count(chr(10))
            match_line = lines[match_lineno] if match_lineno < len(lines) else ""
            match_text = match.group(0)

            if is_in_exempt_context(match_line, content, match.start()):
                continue

            issues.append(
                f"{filepath}:{match_lineno + 1}: prohibited legal conclusion language "
                f"('{pattern_name}'): {match_text}"
            )
    return issues


def check_attorney_gates(filepath):
    """Check that legal-standard sections have attorney-review or source-citation gates."""
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    for section in GATED_SECTIONS:
        section_body = get_section_content(content, section)
        if not section_body or len(section_body.strip()) < 10:
            continue

        has_gate = False
        for gate_pattern, __ in ATTORNEY_GATE_PATTERNS:
            if gate_pattern.search(section_body):
                has_gate = True
                break

        if not has_gate:
            issues.append(
                f"{filepath}: section '{section}' lacks attorney-review or "
                f"source-citation gate language"
            )

    return issues


def check_provider_token_metadata(filepath):
    """Check for committed provider-token presence metadata (LGD-006)."""
    issues = []
    path_str = str(filepath)

    if is_privacy_scan_excluded(path_str):
        return issues

    # NOTE: PROVIDER_TOKEN_INVENTORY_REDACTED.md is NOT exempt -- it IS the target
    if is_ptm_scan_exempt(path_str):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    lines = content.split(chr(10))
    for lineno, line in enumerate(lines):
        for pattern, name in PROVIDER_TOKEN_METADATA_PATTERNS:
            if pattern.search(line):
                issues.append(
                    f"{filepath}:{lineno + 1}: PROVIDER-TOKEN METADATA ({name}): "
                    f"{line.strip()[:120]}"
                )
    return issues


def check_matter_scaffolds(scan_dir):
    issues = []
    scaffold_patterns = [
        sentinel(r"[A-Z][a-z]+XBSXs+vXBSX.XBSXs+[A-Z]"),
        sentinel(r"XBSXd{2,4}-XBSXd{2,4}-XBSXd{2,4}"),
        r"(?i)client[_ ]?matter",
        r"(?i)case[_ ]?file",
    ]

    for root, dirs, files in os.walk(scan_dir):
        root_path = Path(root)
        if root_path == scan_dir:
            continue
        last_part = root_path.parts[-1] if len(root_path.parts) > len(scan_dir.parts) else ""
        if last_part in ("fixtures", "templates", "scripts", "references", "examples"):
            continue

        dirname = root_path.name
        for pattern in scaffold_patterns:
            if re.search(pattern, dirname):
                issues.append(f"{root_path}: directory name looks like a matter scaffold")
    return issues


# -- Self-Test -----------------------------------------------------

def run_self_test():
    """Run negative-control self-test and pattern-compilation assertion.
    Returns 0 if all pass, 1 if any fail."""
    print("=" * 60)
    print("Validator Self-Test")
    print("=" * 60)

    # Pre-check: pattern compilation
    compile_issues = _check_all_patterns_compiled()
    if compile_issues:
        print("\nPATTERN COMPILATION FAILURES:")
        for ci in compile_issues:
            print(f"  FAIL: {ci}")
        print("\nSelf-test ABORTED: patterns did not compile")
        return 1
    print("\nPattern compilation: PASS")

    # Negative-control tests
    print("\nNegative Controls:")
    tmpdir = tempfile.mkdtemp(prefix="legal_validator_selftest_")
    try:
        passed = 0
        total = 0

        def t(name, fn):
            nonlocal passed, total
            total += 1
            try:
                ok = fn()
                if ok:
                    print(f"  PASS: Test {total} -- {name}")
                    passed += 1
                else:
                    print(f"  FAIL: Test {total} -- {name}")
            except Exception as e:
                print(f"  FAIL: Test {total} -- {name} (exception: {e})")

        # Test 1: TELEGRAM_BOT_TOKEN= in labeled fixture (always-fail tier)
        t("TELEGRAM_BOT_TOKEN= caught in labeled fixture",
          lambda: _t(tmpdir, "fixtures/t1.md",
                     chr(10).join(["SYNTHETIC / NON-CLIENT / TEST ONLY", "", "# Test", "",
                                   "TELEGRAM_BOT_TOKEN=123456:ABCdef", ""]),
                     lambda f: any("TELEGRAM" in i for i in check_privacy(f))))

        # Test 2: SSN in unlabeled file
        t("SSN in unlabeled file caught",
          lambda: _t(tmpdir, "fixtures/t2.md",
                     chr(10).join(["# Unlabeled", "", "Patient SSN: 123-45-6789", ""]),
                     lambda f: any("SSN" in i for i in check_privacy(f))))

        # Test 3: Labeled fixture with phone (PASS -- synthetic-gated)
        t("synthetic-gated phone passes in labeled fixture",
          lambda: _t(tmpdir, "fixtures/t3.md",
                     chr(10).join(["SYNTHETIC / NON-CLIENT / TEST ONLY", "", "# Phone", "",
                                   "Emergency Contact: 555-123-4567", ""]),
                     lambda f: len(check_privacy(f)) == 0))

        # Test 4: .env read instruction caught
        t(".env read instruction caught",
          lambda: _t(tmpdir, "t4.md",
                     chr(10).join(["# Setup", "",
                                   "First read your .env file to get API keys.",
                                   "Then cat ~/.hermes/.env to see tokens.", ""]),
                     lambda f: len(check_env_references(f)) > 0))

        # Test 5: .env prohibition text exempted (boundary language)
        t(".env boundary language exempted",
          lambda: _t(tmpdir, "t5.md",
                     chr(10).join(["# .env Policy", "",
                                   "Do not read .env files. Never inspect .env.",
                                   "No .env references in committed files.", ""]),
                     lambda f: len(check_env_references(f)) == 0))

        # Test 6: "proves liability" outside exemption
        t("proves liability caught",
          lambda: _t(tmpdir, "t6.md",
                     chr(10).join(["# Case", "",
                                   "The report proves liability of the railroad.",
                                   "This guarantees recovery for the plaintiff.", ""]),
                     lambda f: len(check_legal_language(f)) > 0))

        # Test 7: Pitfalls section with prohibited phrases exempted
        t("prohibited phrases exempted in Pitfalls",
          lambda: _t(tmpdir, "t7.md",
                     chr(10).join(["# Skill", "", "## Pitfalls", "",
                                   "DO NOT use 'proves liability' or 'guarantees recovery' in output.",
                                   "Never say 'defendant is liable' as a conclusion.", ""]),
                     lambda f: len(check_legal_language(f)) == 0))

        # Test 8: Sparse heading-only SKILL.md in strict mode
        t("sparse section caught in strict mode",
          lambda: _t(tmpdir, "t8.md",
                     chr(10).join(["---", "name: test", "description: Test skill.",
                                   "version: 1.0", "license: MIT", "platforms: [linux]",
                                   "---", "", "# Test", "", "## Matter Profile", "",
                                   "Case: pending.", "", "## Incident Summary", "", "", ""]),
                     lambda f: len(check_required_sections(
                         f, ["matter profile", "incident summary"], strict=True)) > 0))

        # Test 9: Windows user path (constructed with chr(92) to avoid doubling)
        t("raw Windows user path caught",
          lambda: _t(tmpdir, "t9.md",
                     "".join(["# Path Leak", chr(10), chr(10),
                              "The file is at C:", chr(92), "Users", chr(92),
                              "TestUser", chr(92), "Documents", chr(92), "case.md", chr(10)]),
                     lambda f: any("Windows user path" in i for i in check_privacy(f))))

        # Test 10: api.telegram.org endpoint
        t("api.telegram.org endpoint caught",
          lambda: _t(tmpdir, "t10.md",
                     chr(10).join(["# Config", "", "Use https://api.telegram.org/bot for sending.", ""]),
                     lambda f: any("Telegram API endpoint" in i for i in check_privacy(f))))

        # Test 11: Provider-token metadata prose (LGD-006)
        t("provider-token metadata caught",
          lambda: _t(tmpdir, "t11.md",
                     chr(10).join(["# Token Inventory", "",
                                   "| Provider | Token Available |",
                                   "| Anthropic | Yes |", "| OpenAI | Yes |",
                                   "Direct API Route | Available |",
                                   "Token file: anthropic_key.txt (present)", ""]),
                     lambda f: len(check_provider_token_metadata(f)) > 0))

        # Test 12: Pattern-compilation self-check
        t("all patterns compiled as re.Pattern objects",
          lambda: len(_check_all_patterns_compiled()) == 0)

        print(f"\nSelf-test results: {passed}/{total} passed")
        if passed == total:
            print("ALL self-tests passed")
            return 0
        else:
            print(f"{total - passed} test(s) FAILED")
            return 1

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _t(tmpdir, rel_path, content, fn):
    f = Path(tmpdir) / rel_path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    return fn(f)


# -- File Collection -----------------------------------------------

def collect_all_files(scan_dir, include_policy=True):
    all_files = []
    scan_dir = scan_dir.resolve()

    if scan_dir.exists() and scan_dir.is_dir():
        for root, dirs, files in os.walk(scan_dir):
            for f in files:
                all_files.append(Path(root) / f)
    elif scan_dir.is_file():
        all_files.append(scan_dir)

    if include_policy:
        for doc in POLICY_DOCS:
            doc_path = REPO_ROOT / doc
            if doc_path.exists():
                all_files.append(doc_path)

    return all_files


# -- Main ----------------------------------------------------------

def main():
    global FAILURES, WARNINGS, REPO_ROOT, POLICY_DOCS

    parser = argparse.ArgumentParser(description="Validate legal discovery skills.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--dir", type=str, default=None)
    parser.add_argument("--no-policy-docs", action="store_true")
    parser.add_argument("--root", type=str, default=None)
    args = parser.parse_args()

    if args.root:
        REPO_ROOT = Path(args.root).resolve()
        POLICY_DOCS = [d for d in POLICY_DOCS if (REPO_ROOT / d).exists()]

    scan_dir = Path(args.dir) if args.dir else SKILLS_DIR
    include_policy_docs = not args.no_policy_docs

    if args.self_test:
        sys.exit(run_self_test())

    if not scan_dir.exists():
        print(f"ERROR: scan directory not found at {scan_dir.absolute()}")
        sys.exit(1)

    print("=" * 60)
    print("Legal Discovery Skills Validator")
    print(f"Scan directory: {scan_dir}")
    if include_policy_docs:
        print("Policy docs: included")
    if args.strict:
        print("Mode: STRICT")
    print("=" * 60)

    all_files = collect_all_files(scan_dir, include_policy=include_policy_docs)

    skill_files = [f for f in all_files if f.name == "SKILL.md"]
    fixture_files = [f for f in all_files if is_fixture_path(str(f)) and f.suffix == ".md"]
    other_files = [f for f in all_files if f not in skill_files and f not in fixture_files]

    print(f"\nFound: {len(skill_files)} SKILL.md file(s), "
          f"{len(fixture_files)} fixture/template file(s), "
          f"{len(other_files)} other file(s)")

    # 1. Frontmatter
    print("\n-- Frontmatter Validation --")
    for sf in skill_files:
        issues = check_frontmatter(sf)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {sf}")

    # 2. Required sections
    print("\n-- Required Sections --")
    for sf in skill_files:
        if "discovery-intake" in str(sf):
            required = INTAKE_REQUIRED_SECTIONS
        elif "discovery-review" in str(sf):
            required = REVIEW_REQUIRED_SECTIONS
        else:
            continue
        issues = check_required_sections(sf, required, strict=args.strict)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {sf} ({len(required)} sections checked)")

    # 3. Confidentiality / attorney-review
    print("\n-- Confidentiality / Attorney-Review --")
    for sf in skill_files:
        issues = check_confidentiality(sf)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            print(f"  PASS: {sf}")

    # 4. Synthetic labels
    print("\n-- Synthetic Labels (fixtures) --")
    for ff in fixture_files:
        issues = check_synthetic_label(ff)
        if issues:
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
        else:
            rel = ff.relative_to(scan_dir) if scan_dir in ff.parents else ff
            print(f"  PASS: {rel}")
    if not fixture_files:
        print("  (no fixture files found)")

    # 5. Privacy audit
    print("\n-- Privacy Audit (three-tier) --")
    privacy_count = 0
    for f in all_files:
        issues = check_privacy(f, strict=args.strict)
        if issues:
            privacy_count += len(issues)
            for i in issues:
                if "WARNING" in i and not args.strict:
                    print(f"  INFO: {i}")
                else:
                    FAILURES.append(i)
                    print(f"  FAIL: {i}")
    if privacy_count == 0:
        print("  PASS: no privacy issues found")

    # 6. .env references
    print("\n-- .env Reference Detection --")
    env_count = 0
    for f in all_files:
        issues = check_env_references(f)
        if issues:
            env_count += len(issues)
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
    if env_count == 0:
        print("  PASS: no .env references found")

    # 7. Legal language
    print("\n-- Legal Language Audit --")
    legal_count = 0
    for f in all_files:
        issues = check_legal_language(f)
        if issues:
            legal_count += len(issues)
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
    if legal_count == 0:
        print("  PASS: no prohibited legal conclusion language")

    # 8. Attorney/source gates
    print("\n-- Attorney/Source Gates --")
    gate_count = 0
    for sf in skill_files:
        issues = check_attorney_gates(sf)
        if issues:
            gate_count += len(issues)
            if args.strict:
                FAILURES.extend(issues)
                for i in issues:
                    print(f"  FAIL: {i}")
            else:
                WARNINGS.extend(issues)
                for i in issues:
                    print(f"  WARN: {i}")
    if gate_count == 0:
        print("  PASS: all gated sections have attorney/source language")

    # 9. Provider-token metadata
    print("\n-- Provider-Token Metadata --")
    ptm_count = 0
    for f in all_files:
        issues = check_provider_token_metadata(f)
        if issues:
            ptm_count += len(issues)
            FAILURES.extend(issues)
            for i in issues:
                print(f"  FAIL: {i}")
    if ptm_count == 0:
        print("  PASS: no provider-token metadata found")

    # 10. Matter scaffolds
    print("\n-- Matter Scaffold Check --")
    scaffold_issues = check_matter_scaffolds(scan_dir)
    if scaffold_issues:
        FAILURES.extend(scaffold_issues)
        for i in scaffold_issues:
            print(f"  FAIL: {i}")
    else:
        print("  PASS: no matter scaffolds found")

    # Results
    print("\n" + "=" * 60)
    if WARNINGS:
        print(f"WARNINGS: {len(WARNINGS)}")
        for w in WARNINGS:
            print(f"  - {w}")

    if FAILURES:
        print(f"\nFAIL: {len(FAILURES)} issue(s) found")
        for f_issue in FAILURES:
            print(f"  - {f_issue}")
        print(f"\n{len(FAILURES)} total failure(s)")
        sys.exit(1)
    else:
        print("PASS: all checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
