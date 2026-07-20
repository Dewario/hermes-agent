# Autonomous Review — CA/WA Trial Court Discovery + Expert Witness Expansion

**Branch:** `legal-autonomous-ca-wa-experts`
**Worktree:** `C:\Users\Prime\AppData\Local\hermes\hermes-agent-autonomous`
**Started:** 2026-07-19 (UTC-7)
**Base tip:** `9718cc340` (`fix(legal): harden matter path safety and stop forging §9.5`)
**Owner of this file set:** Hermes Agent (GLM 5.2) — separate from Cursor's parallel work on `feat/plaintiff-jurisdiction-expert-packs`.

## Purpose

Engineering expansion of the plaintiff discovery skills for multi-jurisdictional trial litigation, almost exclusively plaintiff-side. **Synthetic only.** No live client matter; no owner §9.5 forged; no client files in repo. This is skill/pack/code work, not a live matter run.

## Scope (this branch)

1. **Citation verification** — confirm CA CCP, WA Civil Rules, San Bernardino / King / Pierce local rules are temporally current and accurate as of 2026.
2. **New jurisdiction packs** — `ca_san_bernardino`, `wa_state`, `wa_king_county`, `wa_pierce_county` (overlays on `ca_ccp` / `wa_state`).
3. **Expert witness skill** — `legal-expert-witness-analysis`: case-fact and cast-context driven selection of (a) liability experts and (b) damages experts.
4. **Tests** — pack loader, citation currency, expert skill.
5. **Cross-check report** — `autonomous_review/CROSS_CHECK_REPORT.md` for the user to compare against Cursor's work before merging either.

## Directory layout (this branch)

```
autonomous_review/
  MANIFEST.md                       (this file)
  CROSS_CHECK_REPORT.md             (filled at end of pass)
  citation_verification/
    ca_ccp.md                      (CA CCP discovery citations, 2026 currency)
    wa_civil_rules.md               (WA CR 26/33/34/36, 2026 currency)
    san_bernardino_local.md         (San Bernardino Superior Court local civil rules)
    king_county_local.md            (King County Superior Court local civil rules)
    pierce_county_local.md          (Pierce County Superior Court local civil rules)
    expert_standards.md             (CA + WA expert witness standards)
  jurisdiction_packs/              (canonical copies also under skills/.../packs/)
  expert_witness_skill/            (canonical copy also under skills/legal/expert-witness-analysis/)
  tests/                           (test notes)
```

## Hard rules followed

- No owner §9.5 boxes checked by engineering.
- No `OWNER_LIVE_GATE_*.md` written; no forged signatures.
- No live/Allen client files under `hermes-agent/`.
- New packs ship `status: active` but live use still requires owner §9.5 + preflight.
- One matter per invocation; no cross-client context.
- Objection language stays attorney-controlled.
- Citations must resolve to a real, current rule; unverified rules use `needs_attorney_rule_confirm`.

## How to cross-check against Cursor

1. Cursor's work: branch `feat/plaintiff-jurisdiction-expert-packs`, worktree `.worktrees/plaintiff-jur-expert`.
2. This work: branch `legal-autonomous-ca-wa-experts`, worktree `hermes-agent-autonomous`.
3. Compare `autonomous_review/citation_verification/` against Cursor's equivalent.
4. Compare jurisdiction pack rule_id sets for overlap/conflict.
5. Compare expert skill scope.
6. Reconcile before promoting either into `main`.

## Status (end of autonomous pass — 2026-07-19)

- **Citation verification:** COMPLETE. 6 reports in `citation_verification/` (ca_ccp, wa_civil_rules, san_bernardino_local, king_county_local, pierce_county_local, expert_standards).
- **Jurisdiction packs:** COMPLETE + CORRECTED. All 4 new packs built; ca_ccp also corrected (4 rules added, 2 summaries fixed). Citations verified against primary sources.
- **Expert witness skill:** COMPLETE + CORRECTED. SKILL.md, taxonomy, expert_analysis.py built. Fictitious "ERI" WA rule removed (9 entries); Sargon/Sanchez cites corrected; CA § 801.1 added.
- **Tests:** COMPLETE. `test_jurisdiction_packs_and_experts.py` — 15 tests passing. No regressions in existing pack tests (19 total passing).
- **Cross-check report:** COMPLETE. `CROSS_CHECK_REPORT.md` written with 14 cross-check questions for Cursor comparison.
- **Reconciliation report:** COMPLETE. `RECONCILIATION_REPORT.md` written — itemizes every divergence between Hermes' work and Codex' parallel uncommitted work on `main`, framed by the 14 cross-check questions. Scorecard: 3 MATCH, 1 PARTIAL, 1 DIVERGENCE, 8 GAP, 1 BUG. Two correctness-critical items flagged for priority merge: (a) Codex' `rog_request_audit.py` line 411 still hardcodes the federal 25 cap for WA (BUG); (b) Codex' `rog_outgoing.py` has no outgoing-limit check (GAP).
- **Commits:** `49a5db52a` (feat: WA + San Bernardino packs and expert skill) + a follow-up commit folding citation corrections + a follow-up committing the reconciliation report + RFA/RFP numerical-limit commits + a whitespace-fix commit from Codex cross-check.

## Codex cross-check response (2026-07-19)

Codex reviewed the reconciliation report and the branch. Its substantive legal findings (WA ROG hardcoded-limit bug, missing CA CCP enforcement rules, incomplete local overlays, expert-skill architecture divergence) all **confirm** the reconciliation report — they are not in dispute. One concrete defect in this branch's own work was caught and is now fixed:

- **Whitespace:** `git diff --check main..legal-autonomous-ca-wa-experts` had been failing on trailing whitespace in `pierce_county_local.md` / `san_bernardino_local.md` and blank-line-at-EOF in `RECONCILIATION_REPORT.md` / `king_county_local.md` / `limits.py`. Fixed in `29823c2ab`; `git diff --check` now exits 0 across the full branch diff.
- **Test count:** the full 10-file legal suite is **139 passed** (reproducible across two runs). Codex's "91 passed" is a narrower test selection, not a contradiction; the "107" Codex referenced was not a number quoted in this branch's reports.
- **Primary checkout:** Codex's own uncommitted work sits in the primary `main` checkout (Codex finding #2). That is a precondition for any merge and is Codex's to clean up — this branch should NOT edit the primary checkout while that work is uncommitted.

**Assessment of Codex's "Done Decision":** Fair. The "no follow-up actions needed" phrasing (about the background test task) was ambiguous and read as "all clear." There IS follow-up: the reconciliation/merge work the report itself recommends.

**Merge readiness:** this branch is clean, `git diff --check` passes, 139 tests pass, all six citation reports are committed. The remaining reconciliation (port WA-aware resolvers, CA CCP enforcement rules, pinned local overlays, and the pack-name / expert-architecture decision into `main`) requires Codex to first clean the primary checkout, then a coordinated merge. No live matter use.

## Critical corrections surfaced (highest-impact)

1. WA CR 33 has NO statewide 25-interrogatory limit (that's federal FRCP 33(a)(1)); WA limits are county-local.
2. WA CR 26(b)(1) has NOT adopted the federal 2015 "proportional to the needs" standard.
3. WA has NO mandatory initial disclosures (CR 26(a) is "Discovery Methods").
4. WA mandatory meet-and-confer is CR 26(i), not CR 26(f) (discretionary).
5. "ERI" is NOT a Washington evidence rule (taxonomy had it on 9 entries — removed).
6. Sargon is (2012) 55 Cal.4th 747 (not 53 Cal.4th 1210); Sanchez is (2016) 63 Cal.4th 665 (not 1 Cal.5th 865).
7. CA § 801.1 (operative Jan. 1, 2024) medical-causation symmetry — plaintiff-favorable exclusion tool, added to taxonomy.
8. CA § 2023.050 sanction increased $250 → $1,000 (SB 235, eff. Jan. 1, 2024).
9. CA § 2033.280 is the no-response deemed-admission statute (not § 2033.290).
10. Pierce County cite is "PCLR" (not "PCLCR"); interrogatory caps 25/35/35/100 by track.
11. King uses word-limits (4,200/1,750); Pierce uses page-limits (12/5).
12. eFiling: San Bernardino=Odyssey eFileCA, King=KC Script Portal, Pierce=LINX.
