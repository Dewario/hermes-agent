#!/usr/bin/env python3
"""Validate legal discovery skills for content, labels, privacy, and legal-risk guardrails.

Checks:
  1. Required sections with substantive content (not just headings)
  2. SYNTHETIC / NON-CLIENT / TEST ONLY labels in all fixture files
  3. Confidentiality and attorney-review language
  4. Attorney/source gates in legal-standard sections
  5. Three-tier privacy audit (always-fail, synthetic-gated, self-exclusion)
  6. .env reference detection (clause-scoped: read/inspect/copy instructions,
     bare/standalone and prose references; boundary text exempted per-clause)
  7. Prohibited legal-conclusion language (obfuscation-normalized; exempts only
     quoted or directly-negated references, across line wraps)
  8. Provider-token-metadata detection (LGD-006)
  9. Frontmatter validation
 10. Matter scaffold detection

There are NO whole-file exemptions: every scanned file is subject to every
check. Legitimate boundary text and quoted examples are handled by
clause/phrase-scoped logic in the individual checks, not by exempting a
filename (Codex R2 finding LGD2-002). Independent regression coverage lives in
tests/skills/test_legal_discovery_validator.py.

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
import html
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

# -- Configuration -------------------------------------------------

SKILLS_DIR = Path("skills/legal")
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Committed status/policy docs that are scanned in full. The four red-team
# input documents (CODEX_RED_TEAM_*, HERMES_CURSOR_*) are deliberately NOT in
# this list: they live outside the repo (relocated to keep prohibited example
# patterns out of git history) and are not scanned here.
#
# There are NO whole-file exemptions. Every scanned file is subject to every
# check. Legitimate boundary text and quoted examples are handled by
# line-scoped / phrase-scoped logic in the individual checks, not by exempting
# a filename. (Removing the old filename-exemption sets closed LGD2-002: the
# hole that let a file pass privacy/env checks purely because of its name, and
# the same mechanism the post-run amend exploited via LEGAL_SCAN_EXEMPT_DOCS.)
POLICY_DOCS = [
    "MODEL_ROUTING_POLICY_LEGAL.md",
    "PROVIDER_TOKEN_INVENTORY_REDACTED.md",
    "LEGAL_DISCOVERY_FINALIZATION_REPORT.md",
    "LEGAL_SKILL_INVENTORY.md",
    "LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md",
    "LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md",
]

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

# .env detection (LGD-003) -- action instructions, path refs, and bare/prose forms.
# Boundary/prohibition text is exempted per-clause (not per-line) in the check.
_ENV_REFERENCE_RAW = [
    (r"(?i)(?:read|inspect|print|cat|copy|open|load|source|access|dump|show)XBSXs+[^.]*XBSX.env", ".env read/inspect instruction"),
    (r"(?i)(?:/|XBSX|~/)XBSX.envXBSXb", ".env file path reference"),
    (r"(?i)^XBSXs*XBSX.envXBSXs*$", "standalone .env reference"),
    (r"(?i)environmentXBSXs+file[^.]*secret", "environment/secrets file prose reference"),
]

# Provider-token-metadata detection (LGD-006; standalone-claim patterns added
# per Codex R3 residual on LGD2-001)
_PTM_RAW = [
    (r"(?i)tokenXBSXs+(?:available|present|found|exists)", "token availability claim"),
    (r"(?i)(?:anthropic|openai|deepseek|gemini|minimax|openrouter|perplexity|langchain).*(?:token|apiXBSXs+key).*(?:present|available|yes)", "provider-token presence row"),
    (r"(?i)directXBSXs+apiXBSXs+routeXBSXs*XBSX|", "Direct API Route column"),
    (r"(?i)providerXBSXs*XBSX|XBSXs*tokenXBSXs*XBSX|XBSXs*(?:filename|presence|available)", "provider token inventory header"),
    (r"(?i)TokenXBSXs+AvailableXBSXs+.*(?:Yes|Available)", "Token Available cell"),
    (r"(?i)(?:token|credential|key)s?[XBSXs-]+director", "credential-directory location"),
    (r"(?i)environmentXBSXs+config(?:uration)?(?:XBSXs+file)?XBSXs+(?:exists|isXBSXs+present|present|located|found)", "environment-config existence claim"),
    (r"(?i)existenceXBSXs+of[^.;]{0,60}environmentXBSXs+config", "environment-config existence claim (noun form)"),
    # Structural table-shape patterns (Codex R3 round-2 residual): an
    # inventory-shaped table is metadata even with no token-specific wording.
    # A "Provider" column alone is ambiguous in this domain (medical provider
    # tables are legitimate legal content) -- it is inventory-shaped only when
    # the same header row also carries credential-ish columns.
    (r"(?i)XBSX|XBSXs*providers?XBSXs*XBSX|[^XBSXn]{0,120}XBSXb(?:filename|presence|token|apiXBSXs+key|available|configured|credential)XBSXb", "provider column header (inventory table shape)"),
    (r"(?i)XBSX|XBSXs*(?:anthropic|openai|deepseek|gemini|minimax|openrouter|perplexity|langchain|mistral|cohere|groq|xai)[^|XBSXn]{0,20}XBSX|[^XBSXn]{0,60}XBSXb(?:yes|present|available|configured|true)XBSXb", "provider presence row (table shape)"),
]

# Legal-conclusion patterns (LGD-005)
_PROHIBITED_LEGAL_RAW = [
    (r"XBSXbprove(?:s|d)?XBSXs+(?:theXBSXs+)?(?:liability|fault|negligence|causation|cause)XBSXb", "proves liability/fault/negligence"),
    (r"XBSXbestablish(?:es|ed)?XBSXs+(?:theXBSXs+)?(?:liability|negligence|causation|cause|fault)XBSXb", "establishes liability/negligence"),
    (r"XBSXbdemonstrate(?:s|d)?XBSXs+(?:theXBSXs+)?(?:liability|negligence|causation|cause)XBSXb", "demonstrates liability/negligence"),
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


# Tokens that signal a prohibited phrase is being *discussed or prohibited*
# rather than asserted. Deliberately excludes bare "no"/"not" (too broad).
_NEGATION_TOKENS = (
    "do not", "don't", "do n't", "does not", "doesn't", "never", "avoid",
    "no need", "cannot", "can't", "must not", "may not", "shall not",
    "should not", "will not", "won't", "without", "instead of",
    "rather than",
)

# Homoglyph fold table: common Greek/Cyrillic lookalikes -> ASCII, plus
# zero-width/invisible characters stripped. Built with chr() to honor the
# no-literal-backslash invariant (unicode escapes contain backslashes).
_CONFUSABLES = {
    # Greek lowercase / uppercase lookalikes
    chr(0x03B1): "a", chr(0x03B5): "e", chr(0x03B9): "i", chr(0x03BA): "k",
    chr(0x03BD): "v", chr(0x03BF): "o", chr(0x03C1): "p", chr(0x03C4): "t",
    chr(0x03C5): "u", chr(0x03C7): "x",
    chr(0x0391): "A", chr(0x0392): "B", chr(0x0395): "E", chr(0x0396): "Z",
    chr(0x0397): "H", chr(0x0399): "I", chr(0x039A): "K", chr(0x039C): "M",
    chr(0x039D): "N", chr(0x039F): "O", chr(0x03A1): "P", chr(0x03A4): "T",
    chr(0x03A5): "Y", chr(0x03A7): "X",
    # Cyrillic lowercase / uppercase lookalikes
    chr(0x0430): "a", chr(0x0435): "e", chr(0x043E): "o", chr(0x0440): "p",
    chr(0x0441): "c", chr(0x0443): "y", chr(0x0445): "x", chr(0x0455): "s",
    chr(0x0456): "i", chr(0x0501): "d",
    chr(0x0410): "A", chr(0x0412): "B", chr(0x0415): "E", chr(0x041A): "K",
    chr(0x041C): "M", chr(0x041D): "H", chr(0x041E): "O", chr(0x0420): "P",
    chr(0x0421): "C", chr(0x0422): "T", chr(0x0423): "Y", chr(0x0425): "X",
    # Zero-width / invisible characters removed entirely
    chr(0x200B): "", chr(0x200C): "", chr(0x200D): "", chr(0x2060): "",
    chr(0xFEFF): "", chr(0x00AD): "",
}


def _strip_html_comments(text):
    """Remove HTML comments, replacing each with the same number of newlines it
    spanned so downstream line-number counting stays aligned (FABLE5 H7)."""
    return re.sub(
        sentinel(r"<!--.*?-->"),
        lambda m: chr(10) * m.group(0).count(chr(10)),
        text,
        flags=re.DOTALL,
    )


def _decode_html_entities(text):
    """Decode HTML entities (numeric & named) so '&#112;roves' / 'pro&lt;'
    can't hide a trigger phrase (FABLE5 H7). Any newline/CR a decode would
    introduce is folded to a space so line offsets are preserved."""
    def _dec(m):
        s = html.unescape(m.group(0))
        return s.replace(chr(13), " ").replace(chr(10), " ")
    return re.sub(sentinel(r"&#?XBSXw+;"), _dec, text)


def _normalize_md(text):
    """Normalize obfuscation before pattern scanning (LGD2-004, R3 homoglyph
    residual, FABLE5 H7): NFKC unicode normalization, Greek/Cyrillic homoglyph
    folding, zero-width-character stripping, markdown-escape/emphasis removal,
    HTML-comment stripping, and HTML-entity decoding, so 'pro\\*ves',
    'pr<omicron>ves', 'pro<!--x-->ves', '&#112;roves', and zero-width-split
    words all normalize to 'proves'. Newlines are never introduced or removed,
    so line numbers stay aligned."""
    out = unicodedata.normalize("NFKC", text)
    out = _strip_html_comments(out)      # before backslash/emphasis strip
    out = _decode_html_entities(out)     # reveal entity-hidden letters
    out = out.replace(chr(92), "")  # drop backslashes (markdown escapes)
    for ch in ("*", "_", "`"):
        out = out.replace(ch, "")
    for src, dst in _CONFUSABLES.items():
        if src in out:
            out = out.replace(src, dst)
    return out


def _clauses(text):
    """Split a line into clauses on ';', ':' and sentence-ending period+space.
    A period immediately followed by a non-space (as in '.env') does NOT split,
    so '.env' stays intact. Splitting on ':' means a prohibition prefix cannot
    shield an action clause after it ("Do not skip this: read .env ...")."""
    parts = re.split(sentinel(r"[;:]|XBSX.XBSXs+"), text)
    return [p for p in parts if p.strip()]


def _logical_blocks(content):
    """Yield (start_lineno_0based, text) logical blocks: a heading line, a
    list item (with its wrapped continuation lines joined), or a prose
    paragraph (wrapped lines joined). Scanning blocks instead of physical
    lines means a sentence that wraps ("It does not enumerate ...\\n... is
    present.") keeps its negation attached to its trigger phrase."""
    lines = content.split(chr(10))
    block_start = None
    block_lines = []
    starter = re.compile(sentinel(r"^XBSXs*(?:#{1,6}XBSXs|[-*+]XBSXs|XBSXd+XBSX.XBSXs|XBSX|)"))

    def flush():
        nonlocal block_start, block_lines
        if block_lines:
            yield_val = (block_start, " ".join(l.strip() for l in block_lines))
            block_start, block_lines = None, []
            return yield_val
        block_start, block_lines = None, []
        return None

    for i, line in enumerate(lines):
        if not line.strip():
            out = flush()
            if out:
                yield out
            continue
        if starter.match(line) and block_lines:
            out = flush()
            if out:
                yield out
        if not block_lines:
            block_start = i
        block_lines.append(line)
    out = flush()
    if out:
        yield out


def _is_prohibition_clause(clause):
    """True when a clause is prohibition/boundary text (derived from the single
    _NEGATION_TOKENS source of truth, so the token sets cannot drift apart)."""
    cl = clause.lower()
    for tok in _NEGATION_TOKENS:
        if re.search(sentinel(r"XBSXb") + re.escape(tok) + sentinel(r"XBSXb"), cl):
            return True
    # Leading "no <noun>" boundary text, e.g. "No .env references belong..."
    # or "- No committed file may enumerate..." (optional list-marker prefix).
    return bool(re.match(sentinel(r"^XBSXs*(?:[-*+]XBSXs+|XBSXd+XBSX.XBSXs+)?noXBSXs+XBSXS"), cl))


def _clause_boundary_governs(clause, match_start):
    """True when a clause is boundary/prohibition text that actually GOVERNS a
    trigger located at ``match_start`` (FABLE5 M8).

    Unlike :func:`_is_prohibition_clause` (which fires on a negation token
    *anywhere* in the clause, so "you can read .env without approval" wrongly
    exempts a real read instruction), this requires the negation to precede the
    trigger -- a negation token in the clause prefix before ``match_start``, or a
    leading "no <noun>" boundary. A negation that only appears AFTER the trigger
    does not exempt."""
    prefix = clause[:match_start].lower()
    for tok in _NEGATION_TOKENS:
        if re.search(sentinel(r"XBSXb") + re.escape(tok) + sentinel(r"XBSXb"), prefix):
            return True
    return bool(re.match(
        sentinel(r"^XBSXs*(?:[-*+]XBSXs+|XBSXd+XBSX.XBSXs+)?noXBSXs+XBSXS"),
        clause.lower(),
    ))


# Instructional verbs that legitimately introduce a prohibited phrase as an
# example to avoid, e.g. "do not use 'proves liability'", "never say ...".
_INSTRUCTIONAL_VERBS = (
    "use", "say", "state", "write", "draft", "render", "conclude",
    "claim", "assert", "allege", "declare", "call", "label", "term",
    "phrase", "word", "describe",
)


def _legal_match_is_referenced(content, start, end):
    """True when a prohibited-phrase match is being *referenced* (quoted or
    directly negated) rather than *asserted*. Cross-line-wrap safe.

    Referenced if EITHER:
      - the phrase is quoted within its enclosing sentence (e.g.
        never say 'defendant is liable'), OR
      - a negation token *directly governs* the phrase -- it appears within a
        short window immediately before the match, optionally followed by one
        instructional verb (e.g. "no need to prove negligence",
        "do not use 'proves liability'").

    A negation that sits earlier in the sentence but is separated by other
    content ("do not ignore that this report proves liability") does NOT
    exempt: that is an asserted conclusion wrapped in a double negative.
    """
    nl = chr(10)
    # Enclosing-sentence prefix for the quote test.
    window_start = start - 200 if start > 200 else 0
    pre_sentence = content[window_start:start]
    for boundary in (nl + nl, ". ", "! ", "? "):
        idx = pre_sentence.rfind(boundary)
        if idx != -1:
            pre_sentence = pre_sentence[idx + len(boundary):]
    collapsed_sentence = re.sub(sentinel(r"XBSXs+"), " ", pre_sentence.lower())
    post_line = content[end:end + 120].split(nl, 1)[0]

    # Quoted phrase (referenced, not asserted).
    # Double quotes: the odd-count-in-prefix + present-in-suffix heuristic is
    # safe. Apostrophes are NOT (FABLE5 M7): contractions/possessives
    # ("the plaintiff's evidence proves liability and it's undisputed") produce
    # odd counts and would falsely exempt an asserted conclusion. For the
    # apostrophe we instead require the match to be quote-*bracketed* -- an
    # apostrophe within a couple of chars before the match AND after it -- which
    # is what an actual quoted reference ('proves liability') looks like.
    if collapsed_sentence.count('"') % 2 == 1 and '"' in post_line:
        return True
    pre_adj = content[max(0, start - 2):start]
    post_adj = content[end:end + 2]
    if "'" in pre_adj and "'" in post_adj:
        return True

    # Direct negation: negation token within a short collapsed window
    # immediately before the match, allowing one optional instructional verb
    # and small filler ("to", "the", "a") between the token and the phrase.
    near = re.sub(sentinel(r"XBSXs+"), " ", content[max(0, start - 40):start].lower())
    quote_cls = "[" + "'" + chr(34) + "]?"
    ws = sentinel(r"XBSXs+")
    verbs = "|".join(_INSTRUCTIONAL_VERBS)
    for tok in _NEGATION_TOKENS:
        pat = (re.escape(tok)
               + sentinel(r"XBSXs*(?:to" + "XBSXs+)?")
               + "(?:(?:" + verbs + ")" + ws + ")?"
               + "(?:(?:the|a|an|any)" + ws + ")?"
               + quote_cls + "$")
        if re.search(pat, near):
            return True
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
            else:
                # Anti-filler (LGD2-006): reject sections whose body is padded
                # with repeated identical lines or a tiny vocabulary. Real
                # workflow content is lexically varied; filler is not.
                normalized = [re.sub(sentinel(r"XBSXs+"), " ", l.strip().lower())
                              for l in body_lines]
                distinct_lines = len(set(normalized))
                tokens = [w for w in re.findall(sentinel(r"[a-z]+"),
                                                section_body.lower())]
                distinct_tokens = len(set(tokens))
                if distinct_lines < 3:
                    issues.append(
                        f"{filepath}: section '{section}' appears to be filler "
                        f"({distinct_lines} distinct lines among {len(body_lines)})"
                    )
                elif tokens and distinct_tokens / len(tokens) < 0.4:
                    issues.append(
                        f"{filepath}: section '{section}' appears to be filler "
                        f"(low lexical diversity: {distinct_tokens}/{len(tokens)} "
                        f"distinct tokens)"
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

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    lines = content.split(chr(10))
    is_synthetic = has_synthetic_label(content)

    # FABLE5 H6: privacy patterns are scanned against BOTH the raw line and a
    # normalized copy. The raw line preserves backslashes so the Windows-path
    # pattern (which needs a real path separator) still fires; the normalized
    # copy strips zero-width chars / folds homoglyphs / decodes HTML entities /
    # removes markdown escapes so an obfuscated secret ('TELEGRAM\_BOT_TOKEN=',
    # a zero-width-split key, an entity-encoded token) cannot slip past. Matches
    # are deduped by (line, pattern-name) so the union never double-reports.
    def _scan(pattern):
        return pattern.search(line) or pattern.search(_normalize_md(line))

    for lineno, line in enumerate(lines):
        for pattern, name in ALWAYS_FAIL_PATTERNS:
            if _scan(pattern):
                issues.append(
                    f"{filepath}:{lineno + 1}: PRIVACY FAIL ({name}): "
                    f"{line.strip()[:120]}"
                )

        for pattern, name in SYNTHETIC_GATED_PATTERNS:
            if _scan(pattern):
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

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    lines = content.split(chr(10))
    # Patterns 0-1 are strong (an explicit read/copy instruction or a real
    # file path); these are flagged even inside a heading. Patterns 2+ are
    # soft filename/prose mentions; a heading that merely names ".env" as a
    # policy topic (e.g. "# .env Policy") is not an access instruction.
    for lineno, raw_line in enumerate(lines):
        line = _normalize_md(raw_line)
        is_heading = bool(re.match(sentinel(r"^XBSXs*#"), line))
        for clause in _clauses(line):
            for idx, (pattern, name) in enumerate(ENV_REFERENCE_PATTERNS):
                if is_heading and idx >= 2:
                    continue
                m = pattern.search(clause)
                if not m:
                    continue
                # Exempt only when a negation actually GOVERNS this trigger --
                # a negation before the match, or a leading "no <noun>" boundary.
                # A negation later in the clause ("read .env without approval")
                # does not exempt a real action clause (LGD2-003 + FABLE5 M8).
                if _clause_boundary_governs(clause, m.start()):
                    break
                issues.append(
                    f"{filepath}:{lineno + 1}: .ENV REFERENCE ({name}): "
                    f"{clause.strip()[:120]}"
                )
                break
    return issues


def check_legal_language(filepath):
    """Check for prohibited legal conclusion language with context awareness."""
    issues = []
    path_str = str(filepath)

    if is_privacy_scan_excluded(path_str):
        return issues

    try:
        raw = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    # Normalize markdown-escape / emphasis obfuscation (backslash, * _ `) so
    # split-with-punctuation phrases still match. _normalize_md preserves line
    # structure, so offsets stay aligned with the original line numbers.
    content = _normalize_md(raw)
    nl = chr(10)

    for pattern, pattern_name in PROHIBITED_LEGAL_PATTERNS:
        for match in pattern.finditer(content):
            start = match.start()
            match_lineno = content.count(nl, 0, start)
            match_text = match.group(0)

            # Exempt only when the phrase is referenced (quoted) or negated
            # (instructional) within its enclosing sentence -- spanning line
            # wraps. An asserted conclusion is always flagged. A negation
            # elsewhere in a *different* sentence does not exempt (LGD2-004).
            if _legal_match_is_referenced(content, start, match.end()):
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

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{filepath}: cannot read: {e}"]

    # Scan logical blocks (paragraphs/list items with wrapped lines joined),
    # then clause-scope within each block: prohibition/boundary clauses
    # ("It does not enumerate...", "No committed file may record...") are
    # exempt; any other clause carrying metadata wording is flagged. Block
    # joining keeps a wrapped sentence's negation attached to its trigger.
    for start_lineno, block in _logical_blocks(content):
        text = _normalize_md(block)
        for clause in _clauses(text):
            for pattern, name in PROVIDER_TOKEN_METADATA_PATTERNS:
                m = pattern.search(clause)
                if not m:
                    continue
                # Exempt only when a negation governs THIS trigger (before it),
                # not merely appears somewhere in the clause (FABLE5 M8).
                if _clause_boundary_governs(clause, m.start()):
                    break
                issues.append(
                    f"{filepath}:{start_lineno + 1}: PROVIDER-TOKEN METADATA ({name}): "
                    f"{clause.strip()[:120]}"
                )
                break
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

        # Test 13: .env exemption-abuse -- negation + real action on one line (LGD2-003)
        t("mixed negation+action .env line caught",
          lambda: _t(tmpdir, "t13.md",
                     chr(10).join(["# Setup", "",
                                   "Do not skip this: read .env and copy it to output.", ""]),
                     lambda f: len(check_env_references(f)) > 0))

        # Test 14: bare .env filename / prose reference caught (LGD2-003)
        t("bare and prose .env references caught",
          lambda: _t(tmpdir, "t14.md",
                     chr(10).join(["# Notes", "", "Path: .env",
                                   "Open the environment file for local secrets.", ""]),
                     lambda f: len(check_env_references(f)) >= 1))

        # Test 15: markdown-escape obfuscated legal conclusion caught (LGD2-004)
        t("markdown-escape obfuscated conclusion caught",
          lambda: _t(tmpdir, "t15.md",
                     "".join(["# Analysis", chr(10), chr(10),
                              "The finding pro", chr(92), "*ves liability here.", chr(10)]),
                     lambda f: len(check_legal_language(f)) > 0))

        # Test 16: conclusion in a heading / 'do not ignore' abuse caught (LGD2-004)
        t("heading and do-not-ignore conclusions caught",
          lambda: _t(tmpdir, "t16.md",
                     chr(10).join(["# This Proves Liability", "",
                                   "Do not ignore that this establishes negligence.", ""]),
                     lambda f: len(check_legal_language(f)) >= 2))

        # Test 17: strict filler section rejected (LGD2-006)
        t("repeated-filler strict section rejected",
          lambda: _t(tmpdir, "t17.md",
                     chr(10).join(["# S", "", "## Matter Profile", "",
                                   "attorney review required source citation",
                                   "attorney review required source citation",
                                   "attorney review required source citation",
                                   "attorney review required source citation", ""]),
                     lambda f: len(check_required_sections(
                         f, ["matter profile"], strict=True)) > 0))

        # Test 18: unicode homoglyph obfuscated conclusion caught (R3 residual)
        t("unicode homoglyph obfuscated conclusion caught",
          lambda: _t(tmpdir, "t18.md",
                     chr(10).join(["# Analysis", "",
                                   "The finding pr" + chr(0x03BF) + "ves liability here.",
                                   ""]),
                     lambda f: len(check_legal_language(f)) > 0))

        # Test 19: standalone credential-directory wording caught (R3 residual)
        t("standalone credential-directory wording caught",
          lambda: _t(tmpdir, "t19.md",
                     chr(10).join(["# Inventory", "",
                                   "Token directory: /synthetic/path", ""]),
                     lambda f: len(check_provider_token_metadata(f)) > 0))

        # Test 20: standalone environment-config existence claim caught (R3 residual)
        t("standalone environment-config existence claim caught",
          lambda: _t(tmpdir, "t20.md",
                     chr(10).join(["# Inventory", "",
                                   "Environment configuration exists for this synthetic check.",
                                   ""]),
                     lambda f: len(check_provider_token_metadata(f)) > 0))

        # Test 21: PTM prohibition/boundary wording exempted
        t("PTM prohibition boundary wording exempted",
          lambda: _t(tmpdir, "t21.md",
                     chr(10).join(["# Policy", "",
                                   "It does not enumerate whether any environment configuration is present.",
                                   "No committed file may record the existence of any environment configuration.",
                                   ""]),
                     lambda f: len(check_provider_token_metadata(f)) == 0))

        # Test 22: provider presence table WITHOUT token wording caught (R3 round 2)
        t("provider presence table without token wording caught",
          lambda: _t(tmpdir, "t22.md",
                     chr(10).join(["# Inventory", "",
                                   "| Provider | Filename | Presence |",
                                   "|----------|----------|----------|",
                                   "| Anthropic | (present) | Yes |", ""]),
                     lambda f: len(check_provider_token_metadata(f)) > 0))

        # Test 23: legitimate routing table row NOT flagged
        t("routing-policy provider row not flagged",
          lambda: _t(tmpdir, "t23.md",
                     chr(10).join(["# Routing", "",
                                   "| Priority | Route | Use Case | Cost Model |",
                                   "|---|---|---|---|",
                                   "| 3 | OpenRouter (fallback only) | When no direct route exists | Per-token credits |",
                                   ""]),
                     lambda f: len(check_provider_token_metadata(f)) == 0))

        # Test 24 (FABLE5 H6): markdown-escaped secret caught by privacy tier
        t("markdown-escaped secret caught in privacy tier",
          lambda: _t(tmpdir, "t24.md",
                     chr(10).join(["# Config", "",
                                   "Set TELEGRAM" + chr(92) + "_BOT" + chr(92) + "_TOKEN=123456:ABCdefGhIJKlmno",
                                   ""]),
                     lambda f: any("PRIVACY FAIL" in i for i in check_privacy(f))))

        # Test 25 (FABLE5 H6): zero-width-split secret caught by privacy tier
        t("zero-width-split secret caught in privacy tier",
          lambda: _t(tmpdir, "t25.md",
                     chr(10).join(["# Config", "",
                                   "TELEGRAM" + chr(0x200B) + "_BOT_TOKEN=123456:ABCdefGhIJKlmno",
                                   ""]),
                     lambda f: any("PRIVACY FAIL" in i for i in check_privacy(f))))

        # Test 26 (FABLE5 H6): Windows path still caught (raw-line pass intact)
        t("windows path still caught after H6 union scan",
          lambda: _t(tmpdir, "t26.md",
                     chr(10).join(["# Notes", "",
                                   "See C:" + chr(92) + "Users" + chr(92) + "alice" + chr(92) + "secret.txt",
                                   ""]),
                     lambda f: any("Windows user path" in i for i in check_privacy(f))))

        # Test 27 (FABLE5 H7): HTML-comment-split legal conclusion caught
        t("html-comment-split conclusion caught",
          lambda: _t(tmpdir, "t27.md",
                     chr(10).join(["# Case", "",
                                   "The report pro<!--x-->ves liability of the railroad.",
                                   ""]),
                     lambda f: len(check_legal_language(f)) > 0))

        # Test 28 (FABLE5 H7): HTML-entity-encoded conclusion caught
        t("html-entity-encoded conclusion caught",
          lambda: _t(tmpdir, "t28.md",
                     chr(10).join(["# Case", "",
                                   "The report &#112;roves liability of the railroad.",
                                   ""]),
                     lambda f: len(check_legal_language(f)) > 0))

        # Test 29 (FABLE5 M8): trailing-negation .env instruction NOT exempted
        t("trailing-negation env instruction still caught",
          lambda: _t(tmpdir, "t29.md",
                     chr(10).join(["# Setup", "",
                                   "You can read .env without approval.", ""]),
                     lambda f: len(check_env_references(f)) > 0))

        # Test 30 (FABLE5 M7): apostrophe/possessive does not exempt an assertion
        t("possessive apostrophe does not exempt asserted conclusion",
          lambda: _t(tmpdir, "t30.md",
                     chr(10).join(["# Case", "",
                                   "The plaintiff's evidence proves liability and it's undisputed.",
                                   ""]),
                     lambda f: len(check_legal_language(f)) > 0))

        # Test 31 (FABLE5 M8): leading negation boundary still exempted (no regression)
        t("leading-negation env boundary still exempted",
          lambda: _t(tmpdir, "t31.md",
                     chr(10).join(["# Policy", "",
                                   "Never read .env files in this workflow.", ""]),
                     lambda f: len(check_env_references(f)) == 0))

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

    # FABLE5 M11: a mistargeted --dir (an empty directory, or one with no
    # readable files) must not silently PASS. Count what the scan TARGET
    # contributed -- excluding policy docs, which are always appended -- and
    # fail when an explicit --dir yielded nothing to scan.
    if args.dir:
        policy_paths = {(REPO_ROOT / d).resolve() for d in POLICY_DOCS}
        scan_contributed = [f for f in all_files if f.resolve() not in policy_paths]
        if not scan_contributed:
            print(f"\nERROR: no files found to scan under {scan_dir.absolute()} "
                  f"(--dir target is empty or contains no readable files).")
            sys.exit(1)

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
