# 0.18.0 Deprecated Patterns Reference

Machine-readable table of deprecated patterns in Hermes Agent 0.18.0. Used by `scan_compat.py` to detect drift in custom skills, scripts, and configs. Updated as new deprecations are announced.

| Pattern | Retirement | Replacement | Severity | Regex | Context-Rule |
|---------|------------|-------------|----------|-------|--------------|
| `deepseek-chat` | 2026-07-24 | `deepseek-v4-flash` | CRITICAL | `deepseek-chat` | CRITICAL in OpenRouter slug format (`provider/deepseek-chat`); WARNING in native API calls adjacent to `api.deepseek.com`; OK if surrounded by deprecation documentation |
| `deepseek-reasoner` | 2026-07-24 | `deepseek-v4-pro` | CRITICAL | `deepseek-reasoner` | Same rules as `deepseek-chat` |
| `google-gemini-cli` | 0.18.0 | (removed) | CRITICAL | `google-gemini-cli` | CRITICAL in active code/config; OK in documentation that explicitly describes the removal |
| `google-antigravity` | 0.18.0 | (removed) | CRITICAL | `google-antigravity` | CRITICAL in active code/config; OK in documentation that explicitly describes the removal |
| `send_message` | 0.18.0 | cron deliver / hermes send / final response | WARNING | `send_message` | OK if deprecation/removal/replacement language within 100 chars; WARNING otherwise |
| `prompt_caching.enabled` | 0.18.0 | (removed) | WARNING | `prompt_caching\\.enabled` | WARNING in any non-upstream file |

## Context Classification Rules

### CRITICAL
The pattern appears in active code, routing configuration, or provider slug format and is NOT surrounded by deprecation/removal acknowledgment. A CRITICAL finding means the code will break or already is broken.

### WARNING
The pattern appears but there is some mitigating context: it's in a native API call (not Hermes-routed), it's in a reference document that doesn't explicitly note the removal, or the context is ambiguous. A WARNING finding requires human review.

### OK
The pattern appears in documentation that explicitly describes the deprecation/removal, or the surrounding text contains replacement instructions. No action needed.

## Deprecation Acknowledgment Keywords

Words and phrases that, when found within 100 characters of a match, indicate the hit is documentation-about-removal rather than active usage:

- "no longer"
- "removed"
- "removal"
- "replacement"
- "instead"
- "deprecated"
- "retired"
- "retirement"
- "cron deliver"
- "hermes send"
- "final response"
- "unaffected"
- "fills that gap"
- "no longer has"

## Native API Detection

A `deepseek-chat` or `deepseek-reasoner` hit is classified as WARNING (not CRITICAL) when the surrounding code (within 500 chars) uses `api.deepseek.com`. This indicates the model identifier may be DeepSeek's native API model name, not a Hermes provider alias. The owner must verify what model names `api.deepseek.com` accepts before changing those calls.
