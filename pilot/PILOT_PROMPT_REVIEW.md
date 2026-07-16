# LONG-RUN CONTROL BLOCK — Synthetic Review Pilot (Mode A)

## Scope

- Work only on the files listed under TASK SCOPE.
- Input fixtures are **read-only evidence**. Do not commit or move them.
- Mode A: review **production fixtures only** — do not require intake output.

## Spend / runtime boundary

- Hard iteration budget: **50 tool-calling turns maximum**.
- On ANY billing/credit/quota signal: **STOP** and write
  `pilot_outputs/STATUS_NEEDS_OWNER.md`.

## Stop conditions

- Iteration budget, billing signal, repeated command failure, privacy uncertainty.

## Post-completion lock

- No git commits. Do not modify source skills or validators.

---

## TASK SCOPE

**Read (synthetic production set):**

- `skills/legal/discovery-review/fixtures/review_incident_report.md`
- `skills/legal/discovery-review/fixtures/review_medical_note.md`
- `skills/legal/discovery-review/fixtures/review_wage_loss_note.md`
- `skills/legal/discovery-review/fixtures/review_railroad_rule_excerpt.md`
- `skills/legal/discovery-review/fixtures/review_supervisor_email.md`
- `skills/legal/discovery-review/fixtures/review_witness_statement.md`
- `skills/legal/discovery-review/fixtures/review_production_cover_letter.md`
- `skills/legal/discovery-review/templates/review_output_template.md`
- `skills/legal/discovery-review/SKILL.md` (Procedure + Step 0 Production Preflight)

**Write:**

- `pilot_outputs/review/review_package.md` — **single markdown file** with `##`
  headers per OUTPUT CONTRACT.

**COMMIT_INPUTS_ALLOWED:** NONE

**OWNER_HOLD:** real client data, git commit/push, credentials, `.env`, messaging.

---

## OUTPUT CONTRACT

Produce exactly **one file**: `pilot_outputs/review/review_package.md`

Complete **Step 0: Production Preflight** content first (source integrity,
Bates/citation provenance) as the opening subsection under Document Inventory
or a dedicated `## Production Preflight` before Section 1.

Then use `##` headers aligned to the review template:

1. `## Section 1: Document Inventory` (or `## Document Inventory`)
2. `## Section 2: Issue Coding Matrix`
3. `## Section 3: Chronology / Timeline`
4. `## Section 4: Key Fact Extraction`
5. `## Section 5: Witness / Entity Extraction`
6. `## Section 6: Production Gap Analysis`
7. `## Section 7: Privilege / Confidentiality Screen`
8. `## Section 8: Medical / Wage / Damages Extraction`
9. `## Section 9: Safety Rule / Policy / Incident Report Extraction`
10. `## Section 10: Deposition Outline Seeds`
11. `## Section 11: Follow-Up Discovery Recommendations`
12. `## Section 12: Contradiction List`
13. `## Section 13: Missing-Custodian / Missing-Time-Period List`
14. `## Section 14: Attorney Final-Review Checklist`
15. `## Verification`
16. `## Pitfalls`

**Required language rules:**

- Complete **damages expert-review gate** language before substantive damages
  conclusions (flag for attorney/expert review).
- Cite source documents by Doc ID / Bates from fixtures (e.g. TVRR-PROD-*).
- **No legal conclusions** as facts.
- Mark analysis with attorney-review requirements.
- Top of file: `**SYNTHETIC / NON-CLIENT / TEST ONLY**`

---

## Acceptance (machine-checkable)

1. Confirm `pilot_outputs/review/review_package.md` exists with all sections.
2. Run: `python scripts/validate_legal_discovery_skills.py --dir pilot_outputs/review --strict`
3. Run: `python pilot/check_outputs.py --phase review --dir pilot_outputs/review`
4. Write `pilot_outputs/review/RUN_SUMMARY.md` with check results.

If checks fail, fix once and re-run. If still failing, stop with STATUS doc.

---

## Procedure

1. Load legal-discovery-review skill from SKILL.md.
2. Run Step 0 Production Preflight on the fixture set.
3. Read each fixture with `read_file` (and `vision_analyze` only if needed for
   images — fixtures are markdown text).
4. Build the review package following the template structure.
5. Run acceptance commands.

Begin.
