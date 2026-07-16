#!/usr/bin/env python3
"""Hermes 0.18.0 compatibility scanner.

Scans custom skills/scripts/configs for deprecated patterns:
- Removed send_message tool  # compat-scanner:allow
- Deprecated model aliases (deepseek-chat, deepseek-reasoner)  # compat-scanner:allow
- Removed providers (google-gemini-cli, google-antigravity)  # compat-scanner:allow
- Removed prompt_caching.enabled config  # compat-scanner:allow

Stdlib only. Read-only. Classifies hits by context: CRITICAL, WARNING, OK.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ── Pattern definitions ──────────────────────────────────────────
# Lines containing IGNORE_MARKER are skipped during scanning.
# Pattern definition strings below use it to prevent self-flagging.
IGNORE_MARKER = "compat-scanner:allow"

PATTERNS = [
    {
        "id": "deepseek-chat",  # compat-scanner:allow
        "pattern": re.compile(r"deepseek-chat"),  # compat-scanner:allow
        "severity": "CRITICAL",
        "retirement": "2026-07-24",
        "replacement": "deepseek-v4-flash",
        "is_model_alias": True,
    },
    {
        "id": "deepseek-reasoner",  # compat-scanner:allow
        "pattern": re.compile(r"deepseek-reasoner"),  # compat-scanner:allow
        "severity": "CRITICAL",
        "retirement": "2026-07-24",
        "replacement": "deepseek-v4-pro",
        "is_model_alias": True,
    },
    {
        "id": "google-gemini-cli",  # compat-scanner:allow
        "pattern": re.compile(r"google-gemini-cli"),  # compat-scanner:allow
        "severity": "CRITICAL",
        "retirement": "0.18.0",
        "replacement": "(removed)",
        "is_provider_removal": True,
    },
    {
        "id": "google-antigravity",  # compat-scanner:allow
        "pattern": re.compile(r"google-antigravity"),  # compat-scanner:allow
        "severity": "CRITICAL",
        "retirement": "0.18.0",
        "replacement": "(removed)",
        "is_provider_removal": True,
    },
    {
        "id": "send_message",  # compat-scanner:allow
        "pattern": re.compile(r"send_message"),  # compat-scanner:allow
        "severity": "WARNING",
        "retirement": "0.18.0",
        "replacement": "cron deliver / hermes send / final response",
        "is_tool_removal": True,
    },
    {
        "id": "prompt_caching.enabled",  # compat-scanner:allow
        "pattern": re.compile(r"prompt_caching\.enabled"),  # compat-scanner:allow
        "severity": "WARNING",
        "retirement": "0.18.0",
        "replacement": "(removed)",
        "is_config_removal": True,
    },
]

# Keywords that indicate a hit is documentation-about-removal
DEPRECATION_ACKNOWLEDGMENT = [
    "no longer", "removed", "removal", "replacement", "instead",
    "deprecated", "retired", "retirement", "cron deliver", "hermes send",
    "final response", "unaffected", "fills that gap", "no longer has",
    "fills this gap", "agent no longer",
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".hermes_history"}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".dll", ".exe", ".so", ".dylib"}
DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}

CONTEXT_WINDOW = 100
NATIVE_API_WINDOW = 500
WIN_USER_PATH = r"[Cc]:\\[U]sers\\[^\s\"'<>)]*"
WIN_FWD_USER_PATH = r"[Cc]:/[U]sers/[^\s\"'<>)]*"
MSYS_USER_PATH = r"/c/[U]sers/[^\s\"'<>)]*"
TELEGRAM_BOT_URL = r"api\.telegram\.org/" + r"bot"
TELEGRAM_TOKEN_NAME = "TELEGRAM" + "_BOT_TOKEN"
TELEGRAM_CHANNEL_NAME = "TELEGRAM" + "_HOME_CHANNEL"
OPENROUTER_KEY_NAME = "OPENROUTER" + "_API_KEY"
OPENAI_KEY_NAME = "OPENAI" + "_API_KEY"
SECRET_PREFIX = "s" + "k-"
CHAT_ID_PREFIX = "-" + "100"

SENSITIVE_REDACTIONS = [
    (re.compile(WIN_USER_PATH, re.IGNORECASE), "<USER_HOME>"),
    (re.compile(WIN_FWD_USER_PATH, re.IGNORECASE), "<USER_HOME>"),
    (re.compile(MSYS_USER_PATH, re.IGNORECASE), "<USER_HOME>"),
    (re.compile(CHAT_ID_PREFIX + r"\d{6,}"), "<REDACTED_CHAT_ID>"),
    (
        re.compile(TELEGRAM_BOT_URL + r"[A-Za-z0-9:_-]+",
                   re.IGNORECASE),
        "<TELEGRAM_API_ENDPOINT><" + TELEGRAM_TOKEN_NAME + ">",
    ),
    (
        re.compile(r"(" + TELEGRAM_TOKEN_NAME +
                   r"\s*[:=]\s*[\"']?)[^\s\"'#]+([\"']?)"),
        r"\1<" + TELEGRAM_TOKEN_NAME + r">\2",
    ),
    (
        re.compile(r"(" + TELEGRAM_CHANNEL_NAME +
                   r"\s*[:=]\s*[\"']?)[^\s\"'#]+([\"']?)"),
        r"\1<" + TELEGRAM_CHANNEL_NAME + r">\2",
    ),
    (
        re.compile(r"(" + OPENROUTER_KEY_NAME +
                   r"\s*[:=]\s*[\"']?)[^\s\"'#]+([\"']?)",
                   re.IGNORECASE),
        r"\1<REDACTED_API_KEY>\2",
    ),
    (
        re.compile(r"(" + OPENAI_KEY_NAME +
                   r"\s*[:=]\s*[\"']?)[^\s\"'#]+([\"']?)",
                   re.IGNORECASE),
        r"\1<REDACTED_API_KEY>\2",
    ),
    (
        re.compile(r"([A-Za-z0-9_]*API_KEY\s*[:=]\s*[\"']?)"
                   r"[^\s\"'#]+([\"']?)",
                   re.IGNORECASE),
        r"\1<REDACTED_API_KEY>\2",
    ),
    (
        re.compile(SECRET_PREFIX + r"[A-Za-z0-9_-]+", re.IGNORECASE),
        "<REDACTED_API_KEY>",
    ),
]


def mask_sensitive(text: str) -> str:
    """Mask local paths and token-like values before printing findings."""
    for pattern, replacement in SENSITIVE_REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def display_path(filepath: Path, root_dir: Path) -> str:
    """Return a privacy-preserving path for output."""
    try:
        path = filepath.resolve().relative_to(root_dir.resolve())
    except ValueError:
        path = filepath
    return mask_sensitive(str(path))


def is_documentation_file(filepath: Path) -> bool:
    """Check whether deprecation language should downgrade a hit to OK."""
    if filepath.name.upper() in {"README", "CHANGELOG", "LICENSE"}:
        return True
    return filepath.suffix.lower() in DOC_EXTENSIONS


def skip_file(filepath: Path, exclude_dirs: list, root_dir: Path) -> bool:
    """Check if file should be skipped."""
    parts = filepath.parts
    for skip_dir in SKIP_DIRS:
        if skip_dir in parts:
            return True
    for exclude_dir in exclude_dirs:
        # Resolve relative exclude paths against root_dir
        resolved = (
            (root_dir / exclude_dir).resolve()
            if not Path(exclude_dir).is_absolute()
            else Path(exclude_dir).resolve()
        )
        try:
            filepath.resolve().relative_to(resolved)
            return True
        except ValueError:
            pass
    if filepath.suffix in SKIP_EXTENSIONS:
        return True
    return False


def line_has_marker(content: str, line_num: int, filepath: Path) -> bool:
    """Check if a specific line contains the ignore marker."""
    lines = content.split("\n")
    if line_num - 1 < len(lines):
        line = lines[line_num - 1]
        if IGNORE_MARKER not in line:
            return False

        # The marker only prevents this exact scanner file's literal pattern
        # definitions from self-flagging. Scanned project files must not be
        # able to hide active deprecated usage by adding the marker.
        try:
            return filepath.resolve() == Path(__file__).resolve()
        except OSError:
            return False
    return False


def is_native_api_context(content: str, match_start: int) -> bool:
    """Check if a model-alias hit is in a native API call context."""
    window_start = max(0, match_start - NATIVE_API_WINDOW)
    window_end = min(len(content), match_start + NATIVE_API_WINDOW)
    window = content[window_start:window_end]
    return "api.deepseek.com" in window


def is_deprecated_in_context(content: str, match_start: int) -> bool:
    """Check if a hit is surrounded by deprecation acknowledgment language."""
    window_start = max(0, match_start - CONTEXT_WINDOW)
    window_end = min(len(content), match_start + CONTEXT_WINDOW)
    window = content[window_start:window_end].lower()
    for keyword in DEPRECATION_ACKNOWLEDGMENT:
        if keyword.lower() in window:
            return True
    return False


def classify_hit(pattern_def: dict, content: str, match_start: int,
                 filepath: Path) -> str:
    """Classify a pattern hit as CRITICAL, WARNING, or OK."""
    pid = pattern_def["id"]
    doc_file = is_documentation_file(filepath)
    has_deprecation_context = is_deprecated_in_context(content, match_start)

    # Deprecation context only proves documentation intent in docs. In active
    # code/config, a nearby "deprecated" comment must not hide a live usage.
    if doc_file and has_deprecation_context:
        return "OK"
    if doc_file:
        return "WARNING"

    # Provider removals: CRITICAL if not covered by deprecation context above
    if pattern_def.get("is_provider_removal"):
        return "CRITICAL"

    # Config removals: WARNING in non-upstream files
    if pattern_def.get("is_config_removal"):
        return "WARNING"

    if pid == "send_message":  # compat-scanner:allow
        return "WARNING"

    # Model aliases: check for native API context
    if pattern_def.get("is_model_alias"):
        if is_native_api_context(content, match_start):
            return "WARNING"
        return "CRITICAL"

    return pattern_def["severity"]


def scan_directory(root_dir: Path, mode: str, exclude_dirs: list) -> list:
    """Scan a directory for deprecated patterns. Returns list of findings."""
    raw_findings = []

    for filepath in root_dir.rglob("*"):
        if not filepath.is_file():
            continue
        if skip_file(filepath, exclude_dirs, root_dir):
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        lines = content.splitlines()

        for pat in PATTERNS:
            if mode == "hermes-aliases" and not pat.get("is_model_alias"):
                continue
            if mode == "removed-tools" and not pat.get("is_tool_removal"):
                continue

            for m in pat["pattern"].finditer(content):
                line_num = content[:m.start()].count("\n") + 1

                # Skip lines with the ignore marker
                if line_has_marker(content, line_num, filepath):
                    continue

                line_text = (
                    lines[line_num - 1].strip()
                    if line_num - 1 < len(lines)
                    else ""
                )
                classification = classify_hit(
                    pat, content, m.start(), filepath
                )

                masked_context = mask_sensitive(line_text)

                raw_findings.append({
                    "pattern": pat["id"],
                    "severity": pat["severity"],
                    "classification": classification,
                    "file": display_path(filepath, root_dir),
                    "line": line_num,
                    "context": masked_context[:120],
                    "retirement": pat.get("retirement", ""),
                    "replacement": pat.get("replacement", ""),
                })

    # Dedup by (file, line, pattern): keep most severe classification
    severity_order = {"CRITICAL": 3, "WARNING": 2, "OK": 1}
    deduped = {}
    for f in raw_findings:
        key = (f["file"], f["line"], f["pattern"])
        if key not in deduped:
            deduped[key] = f
        elif severity_order.get(f["classification"], 0) > \
                severity_order.get(deduped[key]["classification"], 0):
            deduped[key] = f

    return sorted(deduped.values(), key=lambda f: (
        -severity_order.get(f["classification"], 0),
        f["file"],
        f["line"],
    ))


def format_text(findings: list) -> str:
    """Format findings as human-readable text."""
    if not findings:
        return "PASS: No deprecated patterns found.\n"

    critical = [f for f in findings if f["classification"] == "CRITICAL"]
    warnings = [f for f in findings if f["classification"] == "WARNING"]
    ok_hits = [f for f in findings if f["classification"] == "OK"]

    lines = []
    lines.append(f"Results: {len(critical)} CRITICAL, "
                 f"{len(warnings)} WARNING, {len(ok_hits)} OK\n")

    if critical:
        lines.append("=== CRITICAL ===")
        for f in critical:
            lines.append(
                f"  {f['file']}:{f['line']}  [{f['pattern']}]"
            )
            lines.append(
                f"    Retires: {f['retirement']}  "
                f"Replace: {f['replacement']}"
            )
            lines.append(f"    {f['context']}")
            lines.append("")

    if warnings:
        lines.append("=== WARNING ===")
        for f in warnings:
            lines.append(
                f"  {f['file']}:{f['line']}  [{f['pattern']}]"
            )
            lines.append(
                f"    Retires: {f['retirement']}  "
                f"Replace: {f['replacement']}"
            )
            lines.append(f"    {f['context']}")
            lines.append("")

    if ok_hits:
        lines.append("=== OK (documentation-only, no action needed) ===")
        for f in ok_hits:
            lines.append(
                f"  {f['file']}:{f['line']}  [{f['pattern']}]"
            )
            lines.append(f"    {f['context']}")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Hermes 0.18.0 compatibility scanner"
    )
    parser.add_argument(
        "--dir", required=True,
        help="Directory to scan (use C:/-style paths on Windows)"
    )
    parser.add_argument(
        "--mode", choices=["hermes-aliases", "removed-tools", "full"],
        default="full",
        help="Scan mode (default: full)"
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit non-zero on WARNING findings too"
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--exclude", action="append", default=[],
        help="Exclude directory (repeatable, e.g. --exclude ./node_modules)"
    )
    args = parser.parse_args()

    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"Error: {args.dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    findings = scan_directory(root, args.mode, args.exclude)

    if args.format == "json":
        print(json.dumps(findings, indent=2))
    else:
        print(format_text(findings))

    # Exit codes
    has_critical = any(f["classification"] == "CRITICAL" for f in findings)
    has_warning = any(f["classification"] == "WARNING" for f in findings)

    if has_critical:
        sys.exit(1)
    if args.strict and has_warning:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
