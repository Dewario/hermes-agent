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

## Hermes .env

Path: <USER_HOME>/AppData/Local/hermes/.env
Status: Present (contents NOT inspected per mission boundaries)

## Usage Notes

- Token values, prefixes, lengths, expiration dates, and account metadata have NOT been read and MUST NOT be read during this mission
- Skills must reference tokens only via provider configuration or environment variables, never inline
- No committed file may contain token values, token prefixes (e.g., sk-), or API key patterns
- The validator script enforces this via pattern checks

## Provider Availability Summary

| Provider | Token Available | Direct API Route |
|----------|----------------|-----------------|
| Anthropic | Yes | Available |
| DeepSeek | Yes | Available |
| Google (Gemini) | Yes (JPG format) | Check format |
| MiniMax | Yes | Available |
| OpenAI | Yes | Available |
| OpenRouter | Yes | Available |
| Perplexity | Yes | Available |

Note: Token availability does not imply authorization to use for legal discovery work. See MODEL_ROUTING_POLICY_LEGAL.md for routing rules.
