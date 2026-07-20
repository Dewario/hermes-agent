# Round 2 Mutual Cross-Check Reconciliation (Hermes × Codex)

**Date:** 2026-07-20
**Hermes pass:** `legal-autonomous-ca-wa-experts` @ `d859e6a73` — `autonomous_review/round2_self_verification/`
**Codex pass:** `codex/round2-verification` @ `359377e63` — `autonomous_review/codex_round2_verification/ROUND2_VERIFICATION_REPORT.md` (worktree `hermes-agent-codex-round2`)
**Purpose:** reconcile the two independent round-2 passes before the coordinated merge. Flag any SPLIT for human review.

## Headline

**Mutual cross-check: PASS. No SPLIT.**

- 13/13 Axis-2 cross-claims: both passes CONFIRM, zero refuted, zero split.
- Both passes independently surfaced and agreed on the King County LCR 26(b)(2)(4) 25-RFA cap (with the authenticity-RFA exclusion).
- Codex raised three additional source-precision refinements (C2-C4) that Hermes' pass did not catch; all three were verified against primary sources during this reconciliation and accepted as merge-time items.
- One Hermes overclaim acknowledged (Cluster 4 LCR 33 pattern-set names); corrected.

## Axis-2 cross-claims (13/13)

All 13 premises CONFIRMED by both passes. No SPLIT. (Full table in each pass's own report: `round2_self_verification/cross_claims_selfcheck.md` and Codex's `ROUND2_VERIFICATION_REPORT.md`.) The two passes agree on every load-bearing premise the resolvers and packs are built on.

## Merge-time items (consolidated)

**C1 — King RFA cap = 25 (excluding authenticity RFAs).** Both passes found this. Wire `resolve_rfa_limit(wa_king_county) → 25`; audit/outgoing checkers must exempt RFAs propounded solely to authenticate documents from the count (no flat total-RFA-count check). MERGE_PLAN step 10.

**C2 — San Bernardino eFiling source precision (Codex; verified).** The civil eFiling requirements page states verbatim: "Effective September 2, 2025, by General Order ... and by Local Rules, rule 1810.B., the court adopted mandatory electronic filing and service in General Civil cases ...". Pack text should cite the implementation page (https://sanbernardino.courts.ca.gov/online-services/efiling/civil-efiling/civil-efiling-requirements) for the date/mandate, with 1810.B as the rule framework. MERGE_PLAN step 9.

**C3 — San Bernardino discovery-code phrasing (Codex).** Narrow "no freestanding local discovery code" to "no stand-alone civil local discovery chapter/rule series identified in the July 1, 2026 SBSC civil rules." More defensible; avoids overclaiming "no discovery-related local provisions anywhere." MERGE_PLAN step 9.

**C4 — King LCR 33 pattern-interrogatory precision (Codex; verified).** LCR 33(a) is "(Reserved)"; (b)/(c) govern use/format. Approved pattern set(s) live on KCSC forms pages, not the rule text. Merge text: "King has an approved automobile-tort pattern set (per KCSC forms); LCR 33 governs pattern-interrogatory use/format." Do not encode broader named pattern sets unless separately sourced. MERGE_PLAN step 10. Hermes Cluster 4 overclaim corrected (see below).

**C5 — Case-law source posture (Codex; confirms Hermes).** Some older case text verified via reliable public mirrors (Justia, Caselaw Access Project, SCOCAL) rather than modern official case portals. Citation results unchanged. Matches Hermes' existing source-posture note. No action.

## Hermes overclaim corrected

`round2_self_verification/04_king_county_selfcheck.md` line 14 claimed LCR 33 "pattern sets exist for personal injury, motor vehicle, and general civil." The LCR 33 rule page shows (a) as "(Reserved)" and does not enumerate named sets; that claim was not supported by the cited source. Codex C4 caught it. Corrected in-place with a note pointing to this reconciliation.

## Merge readiness

- Source branch `legal-autonomous-ca-wa-experts`: clean, `git diff --check` clean, 139 tests green.
- Codex round-2 worktree: clean, report committed at `359377e63`.
- Primary `main`: still dirty with Codex's pre-existing reconciliation work — NOT edited by either round-2 pass. Merge precondition 1 (clean main) is Codex's to resolve.
- No SPLIT requiring human legal-source adjudication.

## Next

Execute `MERGE_PLAN.md` in order, with C1-C4 as merge-time items (C5 is a posture note, already reflected). No live matter use until owner §9.5 per matter/request/mode/slice + attorney review.
