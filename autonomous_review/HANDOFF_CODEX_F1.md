# HANDOFF - Codex F1 Enforcement-Lever Cross-Check

Dispatch-ready checklist for Codex to perform a multi-agent, multi-model parallel cross-check of the F1 plaintiff enforcement-lever slice. This is a verification handoff, not an implementation handoff. Do not merge; do not edit core legal files. Produce a report.

## Context (locked)

- Branch under review: `legal-enforcement-levers` (HEAD `185c5b73a`).
- Parent / main: `7462dc4cc` (clean). `7462dc4cc` is an ancestor of `legal-enforcement-levers`.
- Locked decisions from prior reconciliation (unchanged): A1 (uniform pack naming `<state>_<county>`), B1 (standalone expert skill, fold intake/gap sourcing in).
- King County 25-RFA cap (LCR 26(b)(2)(4), excluding authenticity RFAs) is already wired into `resolve_rfa_limit` on `main`; do NOT re-wire it.
- Live boundary unchanged: no real `C:\Matters\<client>` use until owner sec. 9.5 sign-off outside the repo, per matter / request type / mode / slice.

## Scope

F1 adds deterministic, jurisdiction-aware scaffolding for four plaintiff enforcement levers across CA and WA trial courts. The scaffolder is `skills/legal/discovery-workflow/scripts/enforcement_motion.py`; authorities live in `skills/legal/discovery-workflow/jurisdiction/packs/ca_ccp.yaml` and `wa_state.yaml`. Hermes independently verified the F1 authorities and documented findings in `autonomous_review/f1_enforcement_verification/`. Codex's job is to cross-check that verification: confirm or refute each cluster, and independently assess the three defects Hermes raised.

## Verification targets (per cluster)

For each cluster, confirm the citation, the summary's substantive accuracy, and currentness against a primary or official source. Append a source URL per cluster (court-published opinion, official code text, or reliable mirror with reporter-text confirmation).

1. CA deemed-admitted - CCP 2033.280. Source: leginfo.legislature.ca.gov.
2. CA ROG motion to compel further responses - CCP 2030.300. Source: leginfo.
3. CA RFP motion to compel further responses - CCP 2031.310. Source: leginfo.
4. CA RFA motion to compel further responses - CCP 2033.290. Source: leginfo.
5. CA meet-and-confer declaration - CCP 2016.040, including AB 1521 (2025-2026) effective 2026-01-01. Source: leginfo + bill history.
6. CA discovery-misuse definitions - CCP 2023.010, including AB 1521 effective 2026-01-01. Source: leginfo + bill history.
7. CA sanctions - CCP 2023.050, including SB 235 (2023-2024) increase from $250 to $1,000 effective 2024-01-01. Source: leginfo + bill compare.
8. WA CR 26(i) meet-and-confer certification. Source: courts.wa.gov CR 26 PDF.
9. WA CR 37(a) motion to compel. Source: courts.wa.gov CR 37 PDF.
10. WA sanctions / expenses - the rule labeled `WA-CR-37-C` in the pack. Confirm whether the summary tracks CR 37(a)(4) (MTC expenses + substantial justification) or CR 37(c) (expenses on failure to admit, CR 36). Source: courts.wa.gov CR 37 PDF.
11. WA deemed-admission posture - CR 36(a). Confirm whether WA has a self-executing no-response deemed-admission (matter admitted unless response within 30 days) and whether CR 36(b) makes it conclusive. Source: courts.wa.gov CR 36 PDF.

## Defects Hermes raised - Codex to confirm or refute

Hermes claims three defects. For each, independently verify against primary sources and mark CONFIRMED, REFUTED, or SPLIT (with the precise text that supports the call).

- F1-W1 (HIGH, Hermes says merge-time required): the F1 scaffolder refuses `deemed_admitted` for WA, and the `WA-CR-37-A` pack summary states "no separate no-response deemed-admission statute parallels CCP 2033.280 in Washington." Hermes says both are false because WA CR 36(a) is a self-executing deemed-admission parallel. Confirm or refute by reading CR 36(a)/(b) text.
- F1-W2 (MEDIUM): the `WA-CR-37-C` pack entry is labeled CR 37(c) but its summary tracks CR 37(a)(4) language. Confirm which subsection the summary text actually tracks.
- F1-CA1 (LOW): the `sanctions_block` CA prose says "up to $1,000 may be imposed" where 2023.050(a) says "shall impose" $1,000. Confirm the modal framing mismatch.

## Cross-claims (plaintiff enforcement posture)

For each premise, mark CONFIRMED / REFUTED / SPLIT with the controlling source.

1. CA `deemed_admitted` is RFA-only and cites 2033.280; the scaffolder refuses it for ROG/RFP. (Premise: 2033.280 is RFA-scoped.)
2. WA has no motion-based deemed-admission that mirrors 2033.280's motion-plus-mandatory-sanction mechanism; WA's is self-executing under CR 36(a). (Premise: mechanism differs, outcome parallels.)
3. CA `motion_to_compel` selects 2030.300 (ROG) / 2031.310 (RFP) / 2033.290 (RFA) by request type; each requires a 2016.040 meet-and-confer declaration.
4. WA `motion_to_compel` selects CR 37(a) for all three request types and requires a CR 26(i) certification.
5. CA `meet_and_confer_letter` cites 2016.040; WA cites CR 26(i).
6. CA `sanctions` cites 2023.050 with 2023.010 supporting; WA `sanctions` cites the rule labeled `WA-CR-37-C`.
7. The $1,000 figure and "substantial justification" exception in 2023.050 are current as of 2026-07-20 (SB 235 eff. 2024-01-01; no later amendment identified).
8. The AB 1521 amendments to 2016.040 and 2023.010 are effective 2026-01-01 and are in force as of 2026-07-20.
9. The F1 scaffolds never sign an owner gate and never pre-check sec. 9.5 boxes (matter_safety + live_preflight enforce this).
10. The F1 scaffolds render metadata and supporting authority as markdown tables and use candidate-free prose so casegraph check-isolation --strict stays clean without local allowlist edits.
11. The King 25-RFA cap is already wired on main and is NOT in scope for F1 (do not re-wire).
12. No live `C:\Matters\<client>` path is touched by F1; all F1 tests are synthetic.

## Deliverables from Codex

- A single report: `autonomous_review/codex_f1_verification/F1_CROSSCHECK_REPORT.md` on the Codex worktree.
- Per-cluster verdict (CONFIRMED / REFUTED / SPLIT) with one source URL each. For case law (none expected in F1), source URL means court-published opinion or reliable mirror plus reporter-text confirmation, not "official portal only."
- A verdict on each of F1-W1 / F1-W2 / F1-CA1 (CONFIRMED / REFUTED / SPLIT) with the controlling text.
- A roll-up: N/N cross-claims confirmed, plus any new defects Codex finds that Hermes missed.
- Any new source-precision refinements (merge-time clarifications) classified as required / recommended / optional.
- Commit the report on the Codex worktree; do not edit `main` or the Hermes worktree.

## Out of scope

- Do not merge F1 into `main`.
- Do not fix the defects on the Hermes branch; document them in the Codex report only.
- Do not re-wire the King 25-RFA cap.
- Do not touch live matter paths or owner-gate boxes.
- Do not add new core tools; F1 is skill-local.

## Source policy

Primary / official sources first (leginfo.legislature.ca.gov for CA CCP; courts.wa.gov rule PDFs for WA CR). Reliable mirrors (Justia, Caselaw Access Project, LII) acceptable for corroboration with reporter-text confirmation. Note any source that is JS-rendered and required a search fallback.
