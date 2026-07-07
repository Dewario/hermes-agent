# PROVIDER CREDENTIAL SAFETY POLICY

Effective: 2026-07-07
Applies to: skills/legal/discovery-intake, skills/legal/discovery-review
Supersedes: the former provider-token inventory (removed 2026-07-07, LGD2-001)

## Purpose

This document states the credential-handling rules for legal discovery work.
It is intentionally a **policy stub**, not an inventory. It does not enumerate
which providers are configured, which credential files exist, where they are
stored, or whether any environment configuration is present. That information
is credential metadata and must never be committed to version control.

## Rules

- Credential values, prefixes, lengths, expirations, and account metadata are
  never read and never recorded during legal discovery work.
- No committed file may enumerate configured providers, credential-file
  presence, credential-file locations, or the existence of any environment
  configuration.
- Skills reference model access only through the agent's configured provider
  routing or environment variables — never inline, never by file path.
- Provider authorization is governed solely by `MODEL_ROUTING_POLICY_LEGAL.md`
  and is confirmed by the owner in the active session, not inferred from any
  committed file.
- `scripts/validate_legal_discovery_skills.py` enforces the no-metadata rule:
  it fails if provider-token presence metadata appears in any scanned file,
  including this one.

## Rationale

The prior version of this file enumerated providers along with per-provider
credential presence and the filesystem location where credentials are stored.
A red-team review (LGD-006 / LGD2-001) found that a filename-and-presence
inventory is itself credential metadata, regardless of whether any secret
values appear. It was removed. This stub records the policy without
reintroducing the metadata.
