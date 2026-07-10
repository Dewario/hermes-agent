# LEGAL SKILL INVENTORY

Generated: 2026-07-07  
Revised: 2026-07-09 (post live-readiness red team — Batches B/C/D tooling)

Branch: `local/finalize-legal-discovery-skills-20260707`

## Summary

Four legal skills exist under `skills/legal/`:

| Skill | Path | Role |
|---|---|---|
| Discovery intake | `discovery-intake/` | Plaintiff FELA/PI intake workflow |
| Discovery review | `discovery-review/` | Document review, chronology, deposition seeds |
| Casegraph | `casegraph/` | Per-matter index + citation/isolation/chronology gates |
| Matter-mail | `matter-mail/` | Correspondence gap scan vs case file (offline CLI) |

Supporting: `scripts/validate_legal_discovery_skills.py`, `pilot/`, `LIVE_MATTER_RUNBOOK.md`.

All committed content is synthetic-only. Attorney-review gates on analysis sections. Real matters live outside the repo.

## Directory structure

```
skills/legal/
├── LIVE_MATTER_RUNBOOK.md
├── casegraph/
│   ├── SKILL.md, SPEC.md
│   ├── data/legal_allowlist.txt
│   └── scripts/casegraph.py
├── discovery-intake/
│   ├── SKILL.md, fixtures/, examples/
├── discovery-review/
│   ├── SKILL.md, fixtures/, templates/, examples/
└── matter-mail/
    ├── SKILL.md, SPEC.md, fixtures/, scripts/matter_mail.py
```

## Machine gates (handoff profile)

- `validate_legal_discovery_skills.py --strict`
- `pilot/check_outputs.py` (synthetic defaults or `--anchors` for live)
- `casegraph verify-cites` (fail-closed on empty cites; quotes on by default)
- `casegraph verify-chronology --strict`
- `casegraph check-isolation --fingerprints --strict`

Promotion (`pilot/promote_goldens.ps1`) requires full `gates_checked` + package SHA-256 bind.

## Readiness

- **Synthetic pilot content:** strong (Fable 5 citation audit)
- **Code gates (Batches B/C):** fail-closed cite/isolation + matter-mail privacy fixes in tree
- **Owner Batch A:** sign `approval.json`, promote goldens, provider auth — see `pilot/OWNER_CHECKLIST_BATCH_A.md`
- **Not ready for unsupervised real-client use** until Batch A + supervised Matter 1 shakedown
