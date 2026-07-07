# LEGAL SKILL INVENTORY

Generated: 2026-07-07
Revised: 2026-07-07 (post red-team findings, Codex review)
Branch: local/finalize-legal-discovery-skills-20260707
Head at creation: 0a768c7f0
Revision baseline: d5726f572

## Summary

Two legal discovery skills exist and are validated:
- `skills/legal/discovery-intake/` — Plaintiff FELA/PI discovery intake workflow
- `skills/legal/discovery-review/` — FELA/PI discovery document review and analysis

Both skills are synthetic-only (no real client data) and carry attorney-review gates on all analysis sections. See `LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md` for the current revision status and red-team finding disposition.

This document is the pre-implementation inventory. It is preserved for historical context. The current post-revision state is documented in the final report.

## Directory Structure (Created)

```
skills/legal/
├── discovery-intake/
│   ├── SKILL.md
│   └── fixtures/
│       ├── intake_facts_synthetic.md
│       └── intake_questionnaire_synthetic.md
└── discovery-review/
    ├── SKILL.md
    ├── fixtures/
    │   ├── review_incident_report.md
    │   ├── review_medical_note.md
    │   ├── review_wage_loss_note.md
    │   ├── review_railroad_rule_excerpt.md
    │   ├── review_supervisor_email.md
    │   ├── review_witness_statement.md
    │   └── review_production_cover_letter.md
    └── templates/
        └── review_output_template.md
```

## Gap Analysis (All Closed)

All capabilities listed below were created during the pre-implementation phase and subsequently hardened per red-team findings.

| Capability | Status |
|-----------|--------|
| FELA-specific intake fields | Created and validated |
| Plaintiff-side PI intake workflow | Created and validated |
| Document inventory generation | Created and validated |
| Issue coding matrix | Created and validated |
| Chronology/timeline generation | Created and validated |
| Privilege/confidentiality screen | Created and validated |
| Deposition outline seeds | Created and validated |
| FRA/FRSA/safety-appliance flagging | Created and validated |
| Medical/wage/damages extraction | Created and validated |
| Attorney final-review checklist | Created and validated |
| Synthetic test fixtures | Created (9 fixtures + 1 template) |
| Static validation script | Created (12/12 self-test) |
| Production preflight (LGD-010) | Added per red-team review |

## Model/API Dependencies

No custom API integrations. Both skills use the agent's standard toolset:
`read_file`, `write_file`, `terminal`, `search_files`, `vision_analyze` (optional for image/PDF documents).

## Client-Data Risk Assessment

All committed content uses only synthetic facts labeled:
`SYNTHETIC / NON-CLIENT / TEST ONLY`

No real names, SSNs, DOBs, addresses, phone numbers, payroll data, or matter identifiers. Skills instruct agents to use local working directories and include confidentiality warnings. No cloud storage or external service references.

## Test Coverage

- `scripts/validate_legal_discovery_skills.py` — 12/12 self-test, 10-check comprehensive static validator
- Hermes compat scanner — `skills/software-development/hermes-compat-scanner/scripts/scan_compat.py`

## Current Status

Synthetic-only. Validated at 0 failures in --strict mode. Attorney-review gates present on all gated sections. Provider token inventory sanitized. Model routing policy hardened against committed credential metadata. Ready for attorney-supervised synthetic pilot testing.
