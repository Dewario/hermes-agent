# F2 Corrections Needed

**Branch:** `legal-evidentiary-objections`
**Date:** 2026-07-23

## Blocking corrections (merge-time)

**None.** All F2 anchor statutes are confirmed against primary sources and
the implementation matches. The slice is synthetic-only and live-gated.

## Low-severity precision items (Codex independent verification)

These are subdivision-level citation precision points for Codex to confirm
against the primary rule text. They do not block merge and do not change
runtime statute selection (the primary statutes are correct).

### F2-N1 (LOW) — WA RFP objection subdivision

- **Where:** `objection_motion.py` `objection_block` WA/rfp prose cites
  "CR 34(b)(3)" as the subdivision requiring a specific objection with
  reasons.
- **Pack entry:** `WA-CR-34-B` is cited as "Wash. Super. Ct. Civ. R. 34(b)"
  broadly.
- **Proposed check:** confirm CR 34(b)(3) is the response/objection
  subdivision (vs. (b)(1) form, (b)(2) time).
- **Source:** https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_34_00_00.pdf
- **If wrong:** narrow the prose to "CR 34(b)" and drop the "(3)" specificity;
  no pack change needed.

### F2-N2 (LOW) — CA general protective-order vehicle

- **Where:** `select_statute` `protective_order`/CA supporting list includes
  `CCP-2017-020` for all request types.
- **Proposed check:** confirm § 2017.020 is the correct general scope-limit
  protective-order vehicle (the per-method statutes § 2030.090 / 2031.060 /
  § 2033.080 remain primary).
- **Source:** https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2017.020.
- **If wrong:** drop `CCP-2017-020` from the supporting list; keep
  `CCP-2016-040` (meet-and-confer) supporting.

### F2-N3 (LOW) — Deposition PO scope boundary

- **Where:** `CCP-2025.420` (deposition protective order) is in the pack but
  not an exposed F2 lever (F2 request types are rog/rfp/rfa only).
- **Proposed check:** confirm this scope boundary is intentional (deposition
  PO is documented authority, not a Slice F2 lever).
- **If a deposition PO lever is wanted:** that is a separate slice, not F2.

## Status

No HIGH or MEDIUM defects identified during the independent verification
pass. The three LOW items are precision/confirmation points for the Codex
cross-check, not actionable code changes unless Codex finds a primary-source
contradiction.
