# LEGAL SKILL INVENTORY

Generated: 2026-07-07
Branch: local/finalize-legal-discovery-skills-20260707
Head: 0a768c7f0

## Summary

**Zero legal skills exist in this repository.** The `skills/` directory has no `legal/` subdirectory. No SKILL.md files anywhere in the repo match legal, discovery, intake, FELA, plaintiff, litigation, evidence, or subpoena search terms. This is a greenfield creation.

## Directory Structure to Create

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

## Gap Analysis

| Capability | Status |
|-----------|--------|
| FELA-specific intake fields | Does not exist — to be created |
| Plaintiff-side PI intake workflow | Does not exist — to be created |
| Document inventory generation | Does not exist — to be created |
| Issue coding matrix | Does not exist — to be created |
| Chronology/timeline generation | Does not exist — to be created |
| Privilege/confidentiality screen | Does not exist — to be created |
| Deposition outline seeds | Does not exist — to be created |
| FRA/FRSA/safety-appliance flagging | Does not exist — to be created |
| Medical/wage/damages extraction | Does not exist — to be created |
| Attorney final-review checklist | Does not exist — to be created |
| Synthetic test fixtures | Does not exist — to be created |
| Static validation script | Does not exist — to be created |

## Model/API Dependencies

No custom API integrations. Both skills use the agent's standard toolset:
`read_file`, `write_file`, `terminal`, `search_files`, `vision_analyze` (optional for image/PDF documents).

## Client-Data Risk Assessment

All committed content uses only synthetic facts labeled:
`SYNTHETIC / NON-CLIENT / TEST ONLY`

No real names, SSNs, DOBs, addresses, phone numbers, payroll data, or matter identifiers. Skills instruct agents to use local working directories and include confidentiality warnings. No cloud storage or external service references.

## Test Coverage

- `scripts/validate_legal_discovery_skills.py` — static validator checking required sections, synthetic labels, confidentiality warnings, attorney-review language, path hygiene, and privacy patterns.
- Hermes compat scanner — `skills/software-development/hermes-compat-scanner/scripts/scan_compat.py` — run in full mode on `skills/legal/` and `skills/`.

## Readiness

Greenfield. All dependencies present in standard toolset. FELA-specific knowledge encoded in skill instructions. Ready for creation.
