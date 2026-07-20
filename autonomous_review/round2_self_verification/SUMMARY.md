# Round 2 — Self-Verification Summary (Hermes independent pass)

**Branch:** `legal-autonomous-ca-wa-experts`
**Pass:** independent, source-bounded re-verification of the load-bearing cites and cross-claim premises in `HANDOFF_CODEX_ROUND2.md`, run in parallel with Codex's own Round-2 pass for mutual cross-checking.
**Discipline:** report only — no edits to merge-critical files (resolvers, packs, expert skill), no edits to `main`, no live `C:\Matters\*` paths, no owner §9.5 boxes.

## Headline result

- **6 of 6 citation clusters CONFIRMED.** Most cites were verified directly against primary/official sources; three items — WA CR 34, WA CR 36, and FRCP 36 — were confirmed by inference / canonical understanding (the packet marks them so), and Codex's independent round-2 review corroborated them against the official PDFs (WA CR 34, WA CR 36) and LII (FRCP 36). Conclusions hold; the phrasing here is intentionally not "all directly fetched."
- **13 of 13 Axis-2 cross-claim premises CONFIRMED.** Zero refuted, zero split. (Claim 13 — King 25-RFA cap — was added 2026-07-20 from this pass's own Cluster 4 finding.)
- **1 nuance** (non-blocking): CA Evid. Code § 801.1 is the product of two bills (SB 652 added, SB 135 scoped). The "SB 652" attribution is correct as originating bill.
- **1 NEW finding** (an addition, not a refutation): King County LCR 26(b)(2)(4) caps RFAs at **25** per party (excluding authenticity RFAs). The current `resolve_rfa_limit` returns `None` for the whole WA family, which is safe-but-conservative; wiring in 25 makes it stricter. **Elevated to merge-time (required), not a follow-up** — see `CORRECTIONS_NEEDED.md`.

## Cluster results

| # | Cluster | Verdict | Report |
|---|---|---|---|
| 1 | CA CCP + Evid. Code | CONFIRMED (1 nuance: § 801.1 dual-bill) | `01_ca_ccp_selfcheck.md` |
| 2 | WA CR + ER | CONFIRMED (secondary-source trap flagged: CR 33 has no statewide cap; 40-cap is King LCR 26) | `02_wa_cr_er_selfcheck.md` |
| 3 | San Bernardino local | CONFIRMED (eFiling mandatory eff. 2025-09-02 via Odyssey; CRC 3.20 preemption) | `03_san_bernardino_selfcheck.md` |
| 4 | King County local | CONFIRMED + **NEW FINDING: RFA cap = 25** (LCR 26(b)(2)(4)) | `04_king_county_selfcheck.md` |
| 5 | Pierce County local | CONFIRMED (2 PARTIAL non-load-bearing items: PCLR 7 "7 court days", PCLR 16 section text) | `05_pierce_county_selfcheck.md` |
| 6 | Expert admissibility case law | CONFIRMED (Sargon 55 Cal.4th 747; People v. Sanchez 63 Cal.4th 665; People v. Kelly 17 Cal.3d 24; State v. Copeland 130 Wn.2d 244; Frye; Daubert; FRE 702 Dec 1 2023 amendment; WA ER 702 unamended) | `06_expert_standards_selfcheck.md` |

## Axis-2 cross-claim verdicts

See `cross_claims_selfcheck.md` for the full table. Roll-up: **13/13 CONFIRMED**. The resolvers and packs are built on premises that all held under independent re-verification. Claim 13 (King 25-RFA cap) is the new premise surfaced by this pass; it has been added to `HANDOFF_CODEX_ROUND2.md` (Cluster 4 + Axis-2 claim 13) so Codex's round-2 verifies it too.

## Corrections needed

One actionable correction, not auto-applied (per round-2 "report, don't auto-apply" discipline). Detail in `CORRECTIONS_NEEDED.md`:

- **C1 — King County RFA cap = 25.** Add a `wa_king_county` branch to `resolve_rfa_limit` returning 25 (excluding authenticity RFAs), update the module comment/docstring, and add resolver + audit tests. Severity: medium (current `None` is safe via attorney override but unnecessarily conservative).
- **Handoff completeness (addressed 2026-07-20):** `HANDOFF_CODEX_ROUND2.md` Cluster 4 now lists the LCR 26(b)(2)(4) 25-RFA cap as a verification target (in addition to the 40 interrogatory cap), and Axis-2 claim 13 has been added so Codex's round-2 verifies it too. Handoff-completeness item, not a legal error.

## What this means for the merge

- The resolver logic (`resolve_rog_limit`, `resolve_rfa_limit`, `resolve_rfp_limit`) and the jurisdiction packs are **sound** — no premise they are built on was refuted.
- The one correction (King RFA = 25) is an **addition**, not a fix to a wrong value, and is now **merge-time (required)**, not a drifting follow-up. The merge already ports `resolve_rfa_limit` (MERGE_PLAN step 1) and pins King County specifics (step 10), so wiring the 25-RFA cap then is zero extra surface. The wiring must respect the LCR 26(b)(2)(4) authenticity-RFA exclusion (25 counts non-authenticity RFAs; do not flag 25 merits RFAs + N authenticity RFAs).
- `HANDOFF_CODEX_ROUND2.md` has been amended (Cluster 4 + Axis-2 claim 13) so Codex's round-2 independently verifies the new finding — the mutual cross-check now covers it.
- Awaiting Codex's `ROUND2_VERIFICATION_REPORT.md` for the mutual cross-check. Any `SPLIT` (disagreement between the two independent passes) will be flagged for human review before merge.

## Source posture

Primary/official sources used: California Legislative Information (leginfo.legislature.ca.gov), Washington State Courts (courts.wa.gov), King County Superior Court (kingcounty.gov), Pierce County Superior Court (piercecountywa.gov), San Bernardino Superior Court (sanbernardino.courts.ca.gov), LII (law.cornell.edu), plus court-published opinions / reliable mirrors (Justia, Caselaw Access Project) for case law with reporter-text confirmation.
