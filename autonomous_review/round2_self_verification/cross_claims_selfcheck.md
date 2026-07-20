# Axis 2 — Cross-claim stress-test verdict table (Hermes Round 2)

Each premise is load-bearing for a resolver or pack. Verdicts assembled from the per-cluster self-checks (01-06). Verdict key: `CONFIRMED` / `REFUTED` (correction + source) / `SPLIT` (models disagreed — n/a here, single-pass).

| # | Premise | Verdict | Source | Cluster |
|---|---|---|---|---|
| 1 | WA CR 33 has NO statewide interrogatory cap → `resolve_rog_limit(wa_state) = None` | **CONFIRMED** | Official CR 33 PDF (courts.wa.gov) has no numerical cap; the "40 per party" is King County LCR 26(b)(2)(B), not statewide. Secondary source `washingtonlegalservicesauthority.com` incorrectly attributes the 40-cap to CR 33 — a secondary-source trap. | 02 |
| 2 | King LCR 26 caps interrogatories at 40 (incl. discrete subparts) → `resolve_rog_limit(wa_king) = 40` | **CONFIRMED** | Official King County LCR 26(b)(2)(B): "no more than 40 interrogatories, including all discrete subparts." | 04 |
| 3 | Pierce PCLR 3(h) caps = 25/35/35/100 by track (Expedited/Standard/Complex/Dissolution) → `resolve_rog_limit(pierce)` track map | **CONFIRMED** | Official Pierce County PCLR 3(h)(1)-(4): 25 / 35 / 35 / 100. Dissolution 100 (the most-missed) confirmed. Subparts count separately on every track. | 05 |
| 4 | CA CCP § 2033.280 (not § 2033.290) is the no-response deemed-admission statute | **CONFIRMED** | Official leginfo CCP § 2033.280: waiver of objections + deemed-admitted motion + mandatory monetary sanction. | 01 |
| 5 | CA § 2023.050 sanction = $1,000 (not $250) as of Jan 1, 2024 (SB 235) | **CONFIRMED** | Official leginfo CCP § 2023.050: "one-thousand-dollar ($1,000) sanction"; history "SB 235 Effective January 1, 2024." | 01 |
| 6 | CA Evid. Code § 801.1 operative Jan 1, 2024 (SB 652), medical-causation symmetry | **CONFIRMED (nuance)** | Official leginfo Evid. Code § 801.1: added by SB 652 (Stats. 2023, Ch. 75), amended/scoped by SB 135 (Ch. 190), operative Jan 1, 2024. "SB 652" attribution correct as originating bill; the "general civil case" scope is SB 135's. | 01 |
| 7 | Sargon = (2012) 55 Cal.4th 747 (not 53 Cal.4th 1210) | **CONFIRMED** | Quinn Emanuel, Horvitz Levy, evidenceattrial, yokasmith all cite 55 Cal.4th 747 (2012). | 06 |
| 8 | People v. Sanchez = (2016) 63 Cal.4th 665 (not 1 Cal.5th 865; not Sanchez v. Hillerich & Bradsby) | **CONFIRMED** | SDAP, Hanson Bridgett; CA Supreme Court cites its own Sanchez opinion (63 Cal.4th 665) in a 2022 opinion. | 06 |
| 9 | Pierce County cite abbreviation = "PCLR" (not "PCLCR") | **CONFIRMED** | All official Pierce County references use "PCLR" / "PCLGR"; no "PCLCR" appears. | 05 |
| 10 | King uses word-limits (4,200/1,750); Pierce uses page-limits (12/5) | **CONFIRMED** | King LCR 7(b)(6)(vi): 4,200/1,750 words. Pierce PCLR 7(a)(8): 12/5 pages (24/12 for MSJ). | 04, 05 |
| 11 | FRCP 36 has NO numerical cap (unlike FRCP 33's 25) → `resolve_rfa_limit(federal) = None` | **CONFIRMED (canonical)** | FRCP 36 imposes no numerical cap on RFAs (well-established; not independently re-fetched this round). CA caps at 35 (CCP § 2033.030); WA statewide none; Pierce expressly none; **King caps at 25** (see NEW finding). | 01, 04, 05 |
| 12 | FRCP 34 has NO numerical cap → `resolve_rfp_limit = None` in every jurisdiction | **CONFIRMED** | RFP has no numerical cap in any covered jurisdiction: CA CCP no cap; WA CR 34 no statewide cap; Pierce PCLR 3(h) no RFP cap (express); King LCR 26 does not cap RFP count; FRCP 34 no cap. | 01, 02, 04, 05 |
| 13 | King County LCR 26(b)(2)(4) caps RFAs at 25 per party, **excluding** authenticity RFAs → `resolve_rfa_limit(wa_king_county) → 25` | **CONFIRMED** | Official King County LCR 26 page (kingcounty.gov), subsection (b)(2)(4): "Requests for Admission. A party may serve no more than 25 requests for admission upon any other party in addition to requests for admission propounded to authenticate documents." Currently the resolver returns `None` for the whole WA family — safe via attorney override, but unnecessarily conservative. | 04 |

## Verdict roll-up

- **13 of 13 load-bearing premises CONFIRMED.** Zero refuted, zero split. (Claim 13 — King 25-RFA cap — was added 2026-07-20 from this pass's own Cluster 4 finding; it is the new premise the resolver must learn at merge time.)
- **1 nuance** (claim 6): § 801.1's operative text is the product of two bills (SB 652 added, SB 135 scoped). The "SB 652" attribution is correct as originating bill; not a resolver-affecting error.
- **1 NEW finding** (not a refutation of an existing claim, but a gap): King County LCR 26(b)(2)(4) caps RFAs at 25 per party. The current `resolve_rfa_limit` returns None for the whole WA family (including King) because the number was unconfirmed at round-1. Round-2 has confirmed it: **25**. See `CORRECTIONS_NEEDED.md`.

## What this means for the merge

- The resolver logic (`resolve_rog_limit`, `resolve_rfa_limit`, `resolve_rfp_limit`) and the jurisdiction packs are **sound** — no premise that the resolvers are built on is refuted.
- The one actionable correction (King RFA = 25) is now elevated from "merge or follow-up" to **merge-time (required)** — see `CORRECTIONS_NEEDED.md`. The merge already ports `resolve_rfa_limit` (MERGE_PLAN step 1) and pins King County specifics (step 10), so wiring the 25-RFA cap then is zero extra surface and avoids a drifting follow-up. The wiring must respect the LCR 26(b)(2)(4) authenticity-RFA exclusion (the 25 counts non-authenticity RFAs; do not flag a party serving 25 merits RFAs + N authenticity RFAs).
- The handoff doc's Cluster 4 should be amended to list the LCR 26(b)(2)(4) 25-RFA cap as a verification target (currently it lists only the 40 interrogatory cap). This is a handoff-completeness fix, not a legal error.
