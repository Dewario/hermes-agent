---
name: hermes-compat-scanner
description: Scan custom skills and scripts for 0.18.0 compatibility issues — deprecated model aliases, removed tools, removed providers. Survives future Hermes updates.
version: 1.0.0
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [compatibility, scanner, deprecation, 0.18.0, migration]
---

# Hermes Compatibility Scanner

Scan custom Hermes skills, scripts, and configs for 0.18.0+ compatibility issues. Detect deprecated model aliases, removed tools (`send_message`), removed providers (`google-gemini-cli`, `google-antigravity`), and other drift patterns.

## Trigger

- Hermes has been updated to a new version
- Pre-commit / pre-promotion check on custom skills
- Periodic deprecation audit
- Custom-skill authoring — verify no deprecated patterns before shipping

## Usage

```bash
# Full scan (all patterns) against a skill directory
python scripts/scan_compat.py --dir /path/to/skills --mode full

# Model aliases only
python scripts/scan_compat.py --dir /path/to/skills --mode hermes-aliases

# Removed tools only
python scripts/scan_compat.py --dir /path/to/skills --mode removed-tools

# Strict mode: exit non-zero on WARNING findings too
python scripts/scan_compat.py --dir /path/to/skills --mode full --strict

# JSON output for machine consumption
python scripts/scan_compat.py --dir /path/to/skills --mode full --format json
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No CRITICAL findings; WARNING findings are allowed unless `--strict` is used |
| 1 | CRITICAL findings present (requires action) |
| 2 | WARNING findings present (requires review; only with `--strict`) |

Without `--strict`, exit code 0 means zero CRITICAL findings (WARNING only = pass).

## Classification

| Level | Meaning |
|-------|---------|
| CRITICAL | Active code or config that will break or is broken — needs immediate fix |
| WARNING | Pattern found but context is ambiguous — needs human review to decide |
| OK | Pattern found but is documentation-about-removal — no action needed |

See `references/deprecated-patterns.md` for the full pattern table and classification rules.

## Self-Check

The scanner over its own directory:

```bash
python scripts/scan_compat.py --dir . --mode full
# Exit: 0 (no CRITICAL findings in the scanner's own code)

python scripts/scan_compat.py --dir . --mode full --strict
# Exit: 2 (WARNINGs in the reference table require review under --strict)
```

For a fully clean self-check excluding the reference table:
```bash
python scripts/scan_compat.py --dir . --mode full --strict --exclude references/
# Exit: 0 (no CRITICAL or WARNING findings)
```

## Supported Deprecations (0.18.0)

- `send_message` tool removal → replaced by cron deliver / hermes send / final response
- `deepseek-chat` alias retirement (2026-07-24) → `deepseek-v4-flash`
- `deepseek-reasoner` alias retirement (2026-07-24) → `deepseek-v4-pro`
- `google-gemini-cli` provider removal → no replacement
- `google-antigravity` provider removal → no replacement
- `prompt_caching.enabled` removal → no replacement

## Notes

- Stdlib only. No pip install needed. Runs on Python 3.11+.
- Skips `.git`, `node_modules`, `__pycache__`, `*.pyc` directories.
- Output paths are relative to the scan root, and finding context masks local user paths, Telegram identifiers, and token-like values before printing.
- `compat-scanner:allow` is honored only inside this scanner's own script so scanned project files cannot silence deprecated usage with an inline marker.
- Native API calls (e.g., direct `requests.post` to `api.deepseek.com`) are flagged as WARNING, not CRITICAL — the model identifier may be DeepSeek's own API model name, not a Hermes alias. Owner must verify.
- This scanner does NOT modify files. It is read-only.
