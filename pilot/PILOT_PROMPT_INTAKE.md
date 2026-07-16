# LONG-RUN CONTROL BLOCK — Synthetic Intake Pilot

## Scope

- Work only on the files listed under TASK SCOPE.
- Task input documents are **read-only evidence**. Do not stage, commit, move,
  or rewrite them.
- Do not implement unrelated refactors.

## Spend / runtime boundary

- Tool calls MUST NOT spawn paid subagent API runs beyond this session's model.
- Hard iteration budget: **40 tool-calling turns maximum** for this task.
- On ANY payment, credit, quota, overage, or billing signal: **STOP** immediately.
  Write `pilot_outputs/STATUS_NEEDS_OWNER.md` with the signal. Do not continue
  on another paid backend.

## Stop conditions

- Iteration budget reached.
- Billing/credit/quota signal.
- Same command class fails twice — stop and write diagnosis.
- Privacy or provenance uncertainty.

## Post-completion lock

- After writing outputs, do NOT amend git history or commit.
- Do not modify source skills or validator scripts.

---

## TASK SCOPE

**Read (fixtures only — synthetic):**

- `skills/legal/discovery-intake/fixtures/intake_facts_synthetic.md`
- `skills/legal/discovery-intake/fixtures/intake_questionnaire_synthetic.md`
- `skills/legal/discovery-intake/SKILL.md` (procedure and Quick Reference)

**Write:**

- `pilot_outputs/intake/intake_package.md` — **single markdown file** with `##`
  headers, one section per Quick Reference row (see OUTPUT CONTRACT below).

**COMMIT_INPUTS_ALLOWED:** NONE

**OWNER_HOLD:** real client data, git commit/push, credential files, `.env`,
Telegram/messaging, provider config changes, any file outside TASK SCOPE.

---

## OUTPUT CONTRACT

Produce exactly **one file**: `pilot_outputs/intake/intake_package.md`

Use `##` headers matching these sections (in order):

1. `## Matter Profile`
2. `## Parties / Witnesses / Entities`
3. `## Incident Summary`
4. `## FELA / PI Issue Checklist`
5. `## Injury / Medical-Treatment Capture`
6. `## Employment / Wage-Loss Capture`
7. `## Liability Theory Checklist`
8. `## Preservation / Spoliation Checklist`
9. `## Missing-Information List`
10. `## Client Interview Follow-Up Questions`
11. `## Initial Discovery Plan`
12. `## Draft Discovery Starter Sets`
13. `## Verification`
14. `## Pitfalls`

**Required language rules:**

- Use **SOL Issue Flag** (or equivalent issue flag) — **never** calculate or
  state a statute-of-limitations deadline as a date.
- Use **Elements for attorney to verify against governing authority** — never
  "Legal elements required" or agent-driven element conclusions.
- Before Step 6 substantive FELA/PI issue content, include an explicit
  **FELA / PI attorney-review gate** paragraph naming attorney review against
  45 U.S.C. §§ 51–60 (FELA) or state tort law for PI flags.
- Mark analysis sections with **requires attorney review** or equivalent.
- Use only facts from the synthetic fixtures (TVRR / Northgate / J.T. matter).
- **No legal conclusions** — use "evidence supports / suggests / requires
  attorney review" language only.
- Top of file: `**SYNTHETIC / NON-CLIENT / TEST ONLY**`

---

## Acceptance (machine-checkable)

Before finishing:

1. Confirm `pilot_outputs/intake/intake_package.md` exists and all 14 sections
   are present.
2. Run: `python scripts/validate_legal_discovery_skills.py --dir pilot_outputs/intake --strict`
3. Run: `python pilot/check_outputs.py --phase intake --dir pilot_outputs/intake`
4. Append a short `pilot_outputs/intake/RUN_SUMMARY.md` with pass/fail of steps 2–3.

If any check fails, fix the output and re-run checks once. If still failing,
stop and document blockers in `pilot_outputs/STATUS_NEEDS_OWNER.md`.

---

## Procedure

1. Load the legal-discovery-intake skill behavior from SKILL.md.
2. Read both synthetic fixture files with `read_file`.
3. Build the intake package per Procedure steps, respecting attorney gates.
4. Write `pilot_outputs/intake/intake_package.md`.
5. Run acceptance commands and write RUN_SUMMARY.md.

Begin.
