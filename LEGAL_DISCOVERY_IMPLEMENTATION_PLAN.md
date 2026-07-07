# LEGAL DISCOVERY IMPLEMENTATION PLAN

**Status: HISTORICAL — pre-implementation planning document.**

This plan was written before skill creation. All phases are now complete.
See `LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md` for current status and red-team finding disposition.

## Mission

Finalize plaintiff-side legal discovery intake and review skills for FELA/personal-injury litigation workflows. Skills must be usable, testable, confidential, and locally committed. No client facts, no live config mutation, no push/PR.

## Phase Summary

| Phase | Deliverable | Status |
|-------|------------|--------|
| 0 | Environment verification, working branch | Complete |
| 1 | LEGAL_SKILL_INVENTORY.md | Complete |
| 2 | MODEL_ROUTING_POLICY_LEGAL.md, PROVIDER_TOKEN_INVENTORY_REDACTED.md | Complete |
| 3 | skills/legal/discovery-intake/SKILL.md | Complete |
| 4 | skills/legal/discovery-review/SKILL.md | Complete |
| 5 | Synthetic non-client fixtures (7 files, clearly labeled) | Complete |
| 6 | scripts/validate_legal_discovery_skills.py | Complete (12/12 self-test) |
| 7 | Full verification suite (scanner, validator, privacy audit, git diff) | Complete |
| 8 | Cursor premium QA (max 2 calls, synthetic only) | Skipped — 120s timeout |
| 9 | Patch issues, local commit, LEGAL_DISCOVERY_FINALIZATION_REPORT.md | Complete |

Post-red-team revision: see `LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md`.

## FELA-Specific Requirements

Intake must capture: railroad employer, job craft, crew, terminal/yard/track location, locomotive/consist/equipment, unsafe work method, rule violations, notice/prior incidents, negligent training/supervision, FRA/FRSA/hours-of-service/safety-appliance flags, injury mechanism, lost wages, occupational limits, medical causation facts.

Output: matter profile, parties/witnesses/entities, incident summary, FELA/PI issue checklist, injury/medical-treatment capture, employment/wage-loss capture, liability theory checklist, preservation/spoliation checklist, missing-information list, client interview follow-up questions, initial discovery plan, draft discovery starter sets.

Review output: document inventory, issue coding matrix, chronology/timeline, key fact extraction, witness/entity extraction, production gap analysis, privilege/confidentiality screen, medical/wage/damages extraction, safety-rule/policy/incident-report extraction, deposition outline seeds, follow-up RFP/interrogatory/RFA recommendations, contradiction list, missing-custodian/missing-time-period list, attorney final-review checklist.

Language: "evidence supports/suggests/contradicts/requires attorney review" — never legal conclusions.

## Confidentiality Boundaries

- Skills reference synthetic facts only
- Fixtures labeled SYNTHETIC / NON-CLIENT / TEST ONLY
- No real names, SSNs, DOBs, addresses, phone numbers, payroll data
- No matter scaffolds committed
- No .env references in committed files
- No Windows user paths in committed files — use <USER_HOME> placeholder
- No token values, prefixes, lengths, or account metadata

## Model Routing Policy (Direct-First)

1. Cursor plan / Cursor CLI for implementation and review
2. Direct provider APIs where authorized by owner in current session
3. OpenRouter only as fallback when no direct/plan route exists
4. Local grep, Python, scanner, static tests for mechanical work
5. No OpenRouter credits burned for routine work

## HOLD Items (Must Not Touch)

- Auxiliary/default model config
- Legal native DeepSeek API migration (except documentation/plan)
- Telegram / global messaging
- OpenRouter routing / credits
- Push / PR
- Live config mutation
- Real-client testing
- .env inspection
- Token reads / metadata

## Working Branch

`local/finalize-legal-discovery-skills-20260707` (off `0a768c7f0` on `local/reapply-compat-scanner-on-main-20260707`)

## Implementation Engine

Cursor CLI v3.8.6 available. Use for high-value architecture/legal-risk QA only (max 2 calls). Mechanical work via local tools.

## Post-Completion

- Local commit message: "finalize legal discovery intake and review skills"
- Do NOT stage .codegraph/
- Create LEGAL_DISCOVERY_FINALIZATION_REPORT.md
- No push, no PR
