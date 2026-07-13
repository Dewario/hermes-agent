# LEGAL SKILL INVENTORY

Generated: 2026-07-07  
Revised: 2026-07-12 (six-skill inventory; Batch A closed; live Rickman owner ops)

Branch: `local/finalize-legal-discovery-skills-20260707`

## Summary

Six legal skills exist under `skills/legal/`:

| Skill | Path | Role |
|---|---|---|
| Discovery intake | `discovery-intake/` | Plaintiff FELA/PI intake workflow |
| Discovery review | `discovery-review/` | Document review, chronology, deposition seeds |
| Casegraph | `casegraph/` | Per-matter index + citation/isolation/chronology gates |
| Matter-mail | `matter-mail/` | Correspondence gap scan vs case file (offline CLI) |
| Deposition outline | `deposition-outline/` | Source-grounded witness examination outlines |
| Medical chronology | `medical-chronology/` | Cite-verified treatment chronologies |

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
├── deposition-outline/
│   ├── SKILL.md, fixtures/, templates/
├── discovery-intake/
│   ├── SKILL.md, fixtures/, examples/
├── discovery-review/
│   ├── SKILL.md, fixtures/, templates/, examples/
├── matter-mail/
│   ├── SKILL.md, SPEC.md, fixtures/, references/, scripts/matter_mail.py
├── medical-chronology/
│   ├── SKILL.md, fixtures/, templates/, scripts/
└── scripts/                   # scaffold_matter, live_preflight, validate helpers
```

## Machine gates (handoff profile)

- `validate_legal_discovery_skills.py --strict`
- `pilot/check_outputs.py` (synthetic defaults or `--anchors` for live)
- `casegraph verify-cites` (fail-closed on empty cites; quotes on by default)
- `casegraph verify-chronology --strict`
- `casegraph check-isolation --fingerprints --strict`
- `pilot/eval_faithfulness.py` (synthetic review package vs `discovery-review/fixtures`; required on promote)

Promotion (`pilot/promote_goldens.ps1`) requires full `gates_checked` + package SHA-256 bind + faithfulness pass.

## Readiness

| Batch | Status |
|---|---|
| **A — synthetic goldens** | **Closed** (code + promote gates in tree; faithfulness wired on promote) |
| **B/C/D — tooling** | Implemented (casegraph, matter-mail privacy, live preflight) |
| **E — gateway smoke** | Owner checklist — `pilot/GATEWAY_SMOKE_CHECKLIST.md` |
| **Live Matter 1 (Rickman)** | **Owner ops remaining** — scaffold `C:\Matters\Rickman`, `PROVIDER_AUTH.md`, supervised shakedown per `LIVE_MATTER_RUNBOOK.md` |

- **Synthetic pilot content:** strong (Fable 5 citation audit + faithfulness harness)
- **Code gates:** fail-closed cite/isolation + matter-mail privacy fixes in tree
- **Not ready for unsupervised real-client use** until Rickman supervised shakedown completes
