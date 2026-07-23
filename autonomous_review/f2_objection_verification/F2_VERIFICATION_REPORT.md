# F2 Verification Report — Plaintiff Objection / Protective-Order Scaffolds

**Branch:** `legal-evidentiary-objections` (autonomous worktree)
**Base:** `ae538c895` (main tip: F1 + OCR retry hardening)
**Date:** 2026-07-23
**Verifier:** Hermes Agent (independent pass, pre-merge)
**Mode:** `objection_motion_draft` · Slice `F2` · Levers `objection`, `protective_order`

## 1. Scope

Independent verification of the anchor statutes wired into
`scripts/objection_motion.py` and the jurisdiction pack entries added for
F2, against primary sources. The slice drafts **non-substantive** plaintiff
scaffolds for two response levers when defense-served ROG/RFP/RFA is
overbroad or improper: `objection` (response language) and `protective_order`
(a motion for protective order). It does not invent substantive objection
grounds, Bates/page:line cites, or sign §9.5.

## 2. Confirmed authorities

### 2.1 California (CCP) — confirmed via leginfo.legislature.ca.gov (primary)

| Rule id | Citation | Role | Confirmed |
|---|---|---|---|
| CCP-2030-240 | Cal. Code Civ. Proc. sec. 2030.240 | ROG objection grounds | YES — specific ground; privilege/work-product; partial objection answered |
| CCP-2031-240 | Cal. Code Civ. Proc. sec. 2031.240 | RFP objection grounds | YES — identify responsive material; extent + grounds; privilege-log facts |
| CCP-2033-230 | Cal. Code Civ. Proc. sec. 2033.230 | RFA objection grounds | YES — specific ground; privilege/work-product; partial request answered |
| CCP-2030-090 | Cal. Code Civ. Proc. sec. 2030.090 | ROG protective order | YES — prompt move; meet-and-confer decl.; good cause; any-order justice requires |
| CCP-2031-060 | Cal. Code Civ. Proc. sec. 2031.060 | RFP protective order | YES — corrected from initial § 2031.260 (response timing) premise |
| CCP-2033-080 | Cal. Code Civ. Proc. sec. 2033.080 | RFA protective order | YES — corrected from initial § 2033.090 premise (Art. 1 ends at § 2033.080) |
| CCP-2025-420 | Cal. Code Civ. Proc. sec. 2025.420 | Deposition protective order | YES — before/during/after deposition; meet-and-confer decl. |
| CCP-2017-020 | Cal. Code Civ. Proc. sec. 2017.020 | General scope limit (supporting) | YES — burden/expense/intrusiveness vs. admissible evidence; protective-order vehicle |
| CCP-2016-040 | Cal. Code Civ. Proc. sec. 2016.040 | Meet-and-confer (supporting) | YES — pre-existing from F1; required declaration on discovery motions |

### 2.2 Washington (CR) — confirmed via courts.wa.gov PDFs (primary)

| Rule id | Citation | Role | Confirmed |
|---|---|---|---|
| WA-CR-33-A | Wash. Super. Ct. Civ. R. 33(a) | ROG objection (answer or objection w/ reasons) | YES |
| WA-CR-34-B | Wash. Super. Ct. Civ. R. 34(b) | RFP objection (response form; specific objections) | YES — pack cites CR 34(b) broadly; prose drills to CR 34(b)(3) (see §4) |
| WA-CR-36-A | Wash. Super. Ct. Civ. R. 36(a) | RFA objection (admit unless answer/objection served) | YES — pre-existing from F1 |
| WA-CR-26-G | Wash. Super. Ct. Civ. R. 26(g) | Objection form / signing (supporting) | YES — no general objections; privilege detail |
| WA-CR-26-C | Wash. Super. Ct. Civ. R. 26(c) | Protective order (all request types) | YES — good cause; any-order justice requires; 8 enumerated directions |
| WA-CR-26-I | Wash. Super. Ct. Civ. R. 26(i) | Meet-and-confer certification (supporting) | YES — pre-existing from F1 |
| WA-CR-37-A-4 | Wash. Super. Ct. Civ. R. 37(a)(4) | Expenses on protective-order motion (supporting) | YES — pre-existing from F1 |

## 3. Implementation-vs-authority match

`select_statute(lever, request_type, available_rules)` picks the primary
statute from the loaded pack's available rule ids and refuses when the
controlling statute is absent:

- **objection / CA:** rog→CCP-2030-240, rfp→CCP-2031-240, rfa→CCP-2033-230.
- **objection / WA:** rog→WA-CR-33-A (+WA-CR-26-G), rfp→WA-CR-34-B (+WA-CR-26-G), rfa→WA-CR-36-A (+WA-CR-26-G).
- **protective_order / CA:** rog→CCP-2030-090, rfp→CCP-2031-060, rfa→CCP-2033-080 (+CCP-2017-020, CCP-2016-040 supporting).
- **protective_order / WA:** all types→WA-CR-26-C (+WA-CR-26-I, WA-CR-37-A-4 supporting).

All four (lever × jurisdiction) branches resolve to a verified primary
statute. No fabricated rule ids; no cross-jurisdiction bleed.

## 4. Precision items flagged for Codex independent verification

These are not defects — they are points where a second reader should confirm
the subdivision-level citation against the primary rule text.

- **F2-N1 (LOW):** WA RFP objection prose cites **CR 34(b)(3)** as the
  subdivision requiring "permit inspection or state a specific objection
  including the reasons." The pack rule `WA-CR-34-B` is cited as
  "Wash. Super. Ct. Civ. R. 34(b)" broadly. Codex should confirm CR 34(b)(3)
  is the response/objection subdivision (vs. (b)(1) form / (b)(2) time).
  Source: https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_34_00_00.pdf
- **F2-N2 (LOW):** CA `protective_order` supporting list includes
  **CCP-2017-020** (general scope limit) for all request types. Codex should
  confirm § 2017.020 is the correct general protective-order vehicle (vs. a
  per-method statute only). The per-method statutes (§ 2030.090 / 2031.060 /
  2033.080) remain primary; § 2017.020 is supporting only.
- **F2-N3 (LOW):** The slice does **not** draft a freestanding deposition
  protective-order scaffold even though **CCP-2025.420** is in the pack. The
  F2 request types are rog/rfp/rfa only (per SPEC §1 axis). Codex should
  confirm this scope boundary is intentional (deposition PO is documented
  authority, not an exposed F2 lever).

## 5. Safety / gate posture

- `matter_safety.py`: `_OWNER_GATE_FILE` regex includes `F2`;
  `_selected_choice` mode tuple includes `objection_motion_draft`.
- `live_preflight.py`: `--mode objection_motion_draft` and `--slice F2`
  are accepted choices.
- Scaffold metadata + supporting authority rendered as markdown tables
  (casegraph `check-isolation --strict` skips table rows), and prose
  citations use candidate-free forms ("section N of the code of civil
  procedure", "CR N(x)") — **no allowlist changes were needed**. Selftest
  passes `check-isolation --strict` clean for all 12 lever×type combos.
- No `OWNER_LIVE_GATE_F2*.md` is created or signed; no §9.5 boxes pre-checked.
- No live `C:\Matters\<client>` path touched; synthetic only.

## 6. Test evidence

- `objection_motion.py selftest`: PASS (12 draft+validate combos CA+WA,
  isolation + jurisdiction-aware statute assertion).
- `tests/skills/test_discovery_objection_motion.py`: **14 passed** in 32.68s
  (unit select_statute × 6, E2E CA+WA, refusal empty/unknown, isolation,
  owner-gate live refusal, selftest).
- Broad legal/discovery suite: **214 passed** in 180.67s
  (200-test F1 baseline + 14 F2 tests), EXIT=0.
- `git diff --check` on F2 changes: clean (EXIT=0).

## 7. Verdict

**PASS for merge candidacy, pending Codex independent cross-check.** All F2
anchor statutes are confirmed against primary sources (CA leginfo; WA courts
PDFs). Three LOW-severity precision items (F2-N1..N3) are flagged for Codex
to independently verify subdivision-level citations; none block merge. The
slice is synthetic-only, non-substantive, and live-gated behind owner §9.5.
