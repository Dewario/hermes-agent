# Legal Discovery Synthetic Pilot

Attorney-supervised synthetic pilot for `legal-discovery-intake` and
`legal-discovery-review`. **Synthetic fixtures only.**

## Policy (non-negotiable)

- **Never** place real-client documents under `pilot/`, `pilot_outputs/`, or
  `skills/legal/*/fixtures/`.
- **Never** commit `pilot_outputs/` (unapproved drafts).
- Promote to `skills/legal/*/examples/` only after `approval.json` records
  attorney sign-off.
- Hermes sends prompts to your configured provider — synthetic data only for
  this pilot.

## Layout

| Path | Purpose |
|------|---------|
| `PILOT_PROMPT_INTAKE.md` | Control block + intake task (Mode A) |
| `PILOT_PROMPT_REVIEW.md` | Control block + review task (fixtures only) |
| `run_pilot.ps1` | Wall-clock guard, ledger, Hermes invoke, auto gates |
| `invoke_hermes.py` | Reliable multiline prompt delivery to `hermes chat -q` |
| `check_outputs.py` | Structural + fixture-grounded checks |
| `eval_faithfulness.py` | Bates-cited claim grounding vs fixture corpus (synthetic/CI only) |
| `approval.schema.json` | JSON Schema for attorney sign-off |
| `approval.template.json` | Copy to `pilot_outputs/approval.json` after review |
| `promote_goldens.ps1` | Copy approved outputs → `examples/` (LGD2-008) |
| `geval_rubric.sample.yaml` | Optional DeepEval rubrics (phase 2) |

Outputs land in `pilot_outputs/` (gitignored).

## Quick start

```powershell
cd $env:LOCALAPPDATA\hermes\hermes-agent

# Dry run: validators + check script only (no Hermes spend)
.\pilot\run_pilot.ps1 -Phase intake -DryRun

# Intake pass (Hermes API spend — supervised or budget-capped)
.\pilot\run_pilot.ps1 -Phase intake -MaxTurns 40 -TimeoutMinutes 90

# Review pass (Mode A — review fixtures only)
.\pilot\run_pilot.ps1 -Phase review -MaxTurns 50 -TimeoutMinutes 120

# Both passes sequentially
.\pilot\run_pilot.ps1 -Phase all -MaxTurns 40 -TimeoutMinutes 90
```

After Hermes finishes and auto gates pass:

1. Attorney reviews `pilot_outputs/intake/` and `pilot_outputs/review/`.
2. Fill `pilot_outputs/approval.json` from `approval.template.json`.
3. `.\pilot\promote_goldens.ps1`

## Auto gates (machine)

1. `validate_legal_discovery_skills.py --dir pilot_outputs/.../<package>.md --strict`
   (package file only — excludes Hermes transcript logs)
2. `check_outputs.py --phase intake|review`
3. `pytest tests/pilot/` (structural tests for check_outputs)
4. `python pilot/eval_faithfulness.py --package <review_package.md> --corpus skills/legal/discovery-review/fixtures --json` (optional during pilot runs; **required** on `promote_goldens.ps1`)

**Faithfulness harness (`eval_faithfulness.py`):** SYNTHETIC / CI only. Point it at
`skills/legal/*/fixtures` and committed `examples/` goldens — never at live matter
directories or attorney production sets in CI. `promote_goldens.ps1` runs it after
casegraph gates on `pilot_outputs/review/review_package.md` and aborts promotion on
non-zero exit.

## Attorney gate (human)

Required before goldens commit. See `approval.template.json` and
`ATTORNEY_REVIEW_PENDING.md` in `pilot_outputs/` after a run.
