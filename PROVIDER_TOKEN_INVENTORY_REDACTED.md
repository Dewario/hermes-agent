# PROVIDER TOKEN INVENTORY — REDACTED

Generated: 2026-07-07
Classification: INTERNAL — do not commit token values, prefixes, or metadata
Policy: Filename + presence only. No contents, no sizes, no validation.

## Token Directory

Path: <USER_HOME>/Documents/API_TOKENS/

## Inventory (filename only, no contents inspected)

| Provider | Filename | Presence |
|----------|----------|----------|
| Anthropic | (present) | Yes |
| DeepSeek | (present) | Yes |
| Gemini | (present, JPG format) | Yes |
| LangChain | (present) | Yes |
| MiniMax | (present) | Yes |
| OpenAI | (present) | Yes |
| OpenRouter | (present) | Yes |
| Perplexity | (present) | Yes |
| (unknown) | (present) | Yes |
| (unknown) | (present) | Yes |

## Hermes Environment Configuration

A Hermes environment configuration file exists at the standard Hermes
application-data location. Path and contents are not inspected per mission
boundaries.

## Usage Notes

- Token values, prefixes, lengths, expiration dates, and account metadata have NOT been read and MUST NOT be read during this mission.
- Skills must reference tokens only via provider configuration or environment variables, never inline.
- No committed file may contain token values, token prefixes (e.g., sk-), or API key patterns.
- The validator script enforces this via pattern checks.

## Provider Authorization

Provider authorization for legal discovery work is governed solely by
MODEL_ROUTING_POLICY_LEGAL.md. This document does not enumerate token
availability, direct-API-route status, or per-provider credential presence
beyond the filename-only inventory above. Individual provider credential
details, access status, and endpoint configuration are managed outside
version control and are never committed.
