# Autonomous Review — Cross-Check Report (Hermes vs Cursor)

**Branch:** `legal-autonomous-ca-wa-experts`
**Worktree:** `C:\Users\Prime\AppData\Local\hermes\hermes-agent-autonomous`
**Base tip (main):** `9711cc340` (fix(legal): harden matter path safety and stop forging §9.5)
**Report date:** 2026-07-19
**Purpose:** Standalone review file set so the owner can cross-check Hermes' autonomous work against Cursor's parallel work before proceeding. This is engineering work on skills — not a live client matter.

## How to use this report

1. Cursor is working in parallel on the main checkout (`hermes-agent`).
2. This report lives in the isolated worktree so the two do not collide.
3. Compare the corrections and citations below against Cursor's output. Any divergence should be reconciled by the owner (the human attorney) before any live use.
4. **All legal citations here are research support, not legal advice.** Citations flagged `needs_attorney_rule_confirm` require a licensed attorney to confirm before reliance.

## Work completed this autonomous pass

| Area | Deliverable | Status |
|------|-------------|--------|
| Jurisdiction packs | `ca_san_bernardino`, `wa_state`, `wa_king_county`, `wa_pierce_county` | Built + corrected against citation reports |
| Expert skill | `skills/legal/expert-witness-analysis/` (SKILL.md, taxonomy, expert_analysis.py) | Built + corrected against expert-standards report |
| Citation verification | 6 reports in `autonomous_review/citation_verification/` | Completed by parallel multi-model agents |
| Tests | `tests/skills/test_jurisdiction_packs_and_experts.py` (15 tests) | Passing |
| Pack corrections | ca_ccp, wa_state, ca_san_bernardino, wa_king_county, wa_pierce_county | Folded confirmed corrections |
| Taxonomy corrections | Removed fictitious "ERI" WA rule; corrected Sargon/Sanchez cites; added §801.1 | Folded |

## Critical corrections folded into packs (verify against Cursor)

These are the high-impact corrections the citation-verification agents surfaced. Each was folded into the corresponding pack. Cursor should be checked for the same corrections.

### CA CCP (ca_ccp.yaml) — 4 rules added, 2 summaries corrected

1. **§ 2030.030 interrogatory cap** — CORRECTED. The pack implied a 35 cap on official-form interrogatories. The report confirms: only specially prepared interrogatories are capped at 35; official-form interrogatories are additional and NOT capped at 35 by § 2030.030. Additional special interrogatories need the § 2030.040-.050 declaration.
2. **§ 2031.210 / § 2031.240** — CORRECTED. § 2031.210 is the response form (compliance/unable/objection); the withholding/objection particulars belong in § 2031.240 (privilege log, particularity). Added § 2031.240 as a new rule.
3. **§ 2033.280 ADDED** — The principal deemed-admission statute for no timely response (waiver + motion to deem genuineness/truth admitted + mandatory monetary sanctions). § 2033.290 governs further responses, NOT no-response deemed admission.
4. **§ 2016.040 ADDED** — Meet-and-confer declaration required for discovery motions. Amended by AB 1521 (Stats. 2025, ch. 200), eff. Jan. 1, 2026.
5. **§ 2023.050 ADDED** — Mandatory $1,000 sanction for specified document-production and meet-and-confer misconduct. Increased from $250 to $1,000 by SB 235 (Stats. 2023, ch. 284), eff. Jan. 1, 2024.
6. **§ 1281 REMOVED from discovery context** — § 1281 et seq. is arbitration enforcement, NOT general discovery motion-to-compel authority. The report flagged this as a wrong citation for a discovery proposition.
7. **AB 1521 (Stats. 2025, ch. 200)** eff. Jan. 1, 2026 amended § 2016.040, § 2023.010, and §§ 2030.020/2031.020/2033.020 (unlawful-detainer timing 5→10 days). Noted in pack summaries.

### WA State (wa_state.yaml) — 3 critical premise corrections, 3 rules added

1. **CR 33 interrogatory limit — CRITICAL CORRECTION.** The pack said "no more than 25 written interrogatories including discrete subparts." This is WRONG — that is the federal FRCP 33(a)(1) cap, NOT WA. WA CR 33 imposes NO statewide numerical limit; limits are county-local (King LCR 26: 40; Pierce ~25/35 by track). Corrected to state no statewide limit + county-local.
2. **CR 26(b)(1) scope — CRITICAL CORRECTION.** The pack said "proportional to the needs of the case." This is WRONG — WA has NOT adopted the federal 2015 proportionality standard. WA uses "relevant to the subject matter" scope with (b)(1)(A)-(C) pre-2015-style factors. Corrected.
3. **CR 26(a) — CORRECTED.** The pack said "Required disclosures — confirm whether WA mandates initial disclosures." Confirmed: WA has NO mandatory initial disclosures (no FRCP 26(a)(1) analog). CR 26(a) is "Discovery Methods" listing devices.
4. **CR 26(i) ADDED** — The MANDATORY meet-and-confer before any CR 26-37 motion/objection (with certification). This is the WA pre-motion confer rule — NOT CR 26(f), which is a discretionary discovery conference.
5. **CR 26(g) ADDED** — General objections now expressly PROHIBITED; privilege log required for every privilege assertion. Amended eff. Oct. 1, 2024.
6. **CR 26(e) UPDATED** — Now a self-executing duty to seasonably supplement/correct all discovery responses (post-Oct. 1, 2024 amendment).
7. **CR 30 UPDATED** — Amended eff. Oct. 1, 2024: remote depositions without leave; 3-day objection window; audible/visible; no coaching.
8. **CR 45 UPDATED** — Amended eff. July 9, 2024 for remote-means testimony; 5-day pre-service notice on parties; 14-day objection window.
9. **CR 36(a) deemed-admission UPDATED** — Confirmed 30 days (40 for defendant). Last amended eff. Sept. 1, 2015.
10. **Label is "CR" not "SCR"** — confirmed.

### San Bernardino (ca_san_bernardino.yaml) — rewritten with confirmed rule numbers

The pack had placeholder "confirm current rule number" entries. All replaced with confirmed rules from the July 1, 2026 Local Rules:

1. **CRC 3.20 preemption ADDED** — San Bernardino has no freestanding local discovery code; discovery substance comes from CCP/CRC; local rules regulate calendaring/filing/meet-and-confer/tentative rulings.
2. **Local R. 403** — all-purpose judge assignment at filing (replaces placeholder).
3. **Local R. 411.1** — Initial Trial Setting Conference in lieu of CMC; on or before 26th week.
4. **Local R. 520/521** — reserve hearing date first; moving papers + fees within 5 court days.
5. **Local R. 550** — continuance notice by 4:30 p.m. second court day before hearing.
6. **Local R. 560** — meet-and-confer declaration enforcement (court may take off calendar).
7. **Local R. 561** — tentative rulings after 3:00 p.m. court day before.
8. **Local R. 571** — exhibits filed (not lodged) unless authorized.
9. **Discovery cutoff CONFIRMED** — NO countywide standing cutoff; CCP § 2024.020 et seq. governs + case-specific TSC/CMO.
10. **Expert disclosure CONFIRMED** — NO local civil expert rule; CCP §§ 2034.210-2034.310 governs.
11. **IDC CONFIRMED** — NOT a countywide Local Rule; department/complex-driven (Local R. 412 for complex). S26 = before filing; S33 = after filing/before opposition (they differ).
12. **eFiling** — Local R. 1800-1860; Odyssey eFileCA; mandatory General Civil eff. Sept. 2, 2025.

### King County (wa_king_county.yaml) — rewritten with confirmed rule numbers

1. **LCR 4 / LCR 40(a)** — CSO standard form: T-22 primary witness, T-16 additional witness, T-8 discovery cutoff, T-3 witness/exhibit exchange.
2. **LCR 37(g)** — discovery completion 56 calendar days before trial (matches T-8).
3. **LCR 26 interrogatories** — 40 including discrete subparts, or 15 additional to court-approved pattern.
4. **LCR 26(b)(3)** — 10 depositions, 7 hours/day; one 2-day deposition.
5. **LCR 26(k)** — expert disclosure: name/address/phone + summary opinions + basis + qualifications. Failure → witness exclusion.
6. **LCR 37(e)-(f)** — incorporates CR 26(i) conference/certificate. No general joint-stipulation requirement.
7. **LCR 7(b)** — 9 judicial days; 4,200 word limit (initial/opposition), 1,750 reply; no oral argument default.
8. **LCAR 2.1** — mandatory arbitration ≤ $100,000 (post-Sept 1, 2019); CSO stricken on transfer; LCAR 4.2 arbitrator discovery.
9. **LGR 30** — mandatory e-filing via KC Script Portal for attorneys.

### Pierce County (wa_pierce_county.yaml) — rewritten with confirmed rule numbers

1. **Cite is "PCLR" not "PCLCR"** — CORRECTED (PCLR 0.1).
2. **PCLR 3(c)/(h)/(i)** — Form A + track-based deadlines. Interrogatory caps by track (subparts separate): Expedited 25, Standard 35, Complex 35, Dissolution 100. No RFA limit.
3. **PCLR 3(i) cutoffs** — Expedited 20/26, Standard 45/52, Complex 67/78 weeks (discovery/trial).
4. **PCLR 7(a)** — assigned judge only; commissioners do NOT hear discovery motions; Friday 9:00 a.m. docket; 7 court days filing.
5. **PCLR 7(a)(8)** — PAGE limits (12 initial/opposition, 5 reply) — Pierce uses pages, King uses words.
6. **PCLR 7(a)(9)** — confirmation required 5-3 court days (LINX).
7. **PCLR 26** — expert disclosure: opinions + basis + qualifications/CV; treating physicians = expert AND fact.
8. **PCLR 27-37 Reserved** — no local CR 37; CR 26(i)/CR 37(a) apply statewide.
9. **PCLSCCAR 1.1/1.2** — mandatory arbitration $100,000 NET claim (not $50,000).
10. **PCLGR 30** — e-filing via LINX (NOT Odyssey); discovery not filed with court excluded from mandatory e-service.

### Expert taxonomy (expert_taxonomy.yaml + SKILL.md) — fictitious rule removed, cites corrected

1. **"ERI" REMOVED — CRITICAL.** The taxonomy had "Frye / ER 702 + ERI" for WA on 9 expert entries. The report confirms "ERI" is NOT a recognized Washington evidence rule (GR 37 is jury-selection, not expert evidence). All 9 entries corrected to "Frye (State v. Copeland, 130 Wn.2d 244 (1996)) + ER 702 (State v. Cauthron, 120 Wn.2d 879 (1993)); ER 702 does not track the 2023 FRE 702 amendment."
2. **Sargon cite CORRECTED** — The request had "53 Cal.4th 1210" (wrong). Correct cite: **Sargon Enterprises, Inc. v. USC (2012) 55 Cal.4th 747**. Folded into accident reconstruction and forensic medical CA notes.
3. **Sanchez cite CORRECTED** — The request had "1 Cal.5th 865" (wrong). Correct cite: **People v. Sanchez (2016) 63 Cal.4th 665**. Folded into medical-causation CA notes.
4. **"State v. Frye (1995)" / "Copeland-Bryant (2018)" — DO NOT USE.** No such WA cases. Frye comes from Frye v. United States, 293 F. 1013 (D.C. Cir. 1923); WA retained it in State v. Copeland, 130 Wn.2d 244 (1996).
5. **CA Evid. Code § 801.1 ADDED** — Operative Jan. 1, 2024 (SB 652 / Stats. 2023, chs. 75 & 190). Medical-causation symmetry: defense alternative-cause experts must opine to reasonable medical probability. Plaintiff-favorable exclusion tool. Folded into treating physician and forensic medical CA notes.
6. **FRE 702 (2023) — substantive amendment, NOT restyling.** Added "more likely than not" preponderance stem; rewrote (d). Noted in SKILL.md pitfalls.
7. **WA ER 702 does NOT track 2023 FRE 702 amendment** — remains 1979 text. Noted in SKILL.md pitfalls.

## Cross-check questions for Cursor

When comparing this work against Cursor's parallel output, the owner should verify:

1. **WA CR 33 limit** — Does Cursor's wa_state pack correctly say NO statewide limit (county-local), or does it repeat the federal "25" error?
2. **WA CR 26(b)(1) proportionality** — Does Cursor's pack correctly omit the federal "proportional to the needs" language?
3. **WA "ERI"** — Does Cursor's expert/taxonomy work avoid the fictitious "ERI" rule?
4. **Sargon/Sanchez cites** — Does Cursor use 55 Cal.4th 747 and 63 Cal.4th 665 (not the wrong cites)?
5. **CA § 801.1** — Does Cursor's expert skill include the Jan. 1, 2024 medical-causation symmetry rule?
6. **CA § 2023.050** — Does Cursor's ca_ccp pack reflect the $1,000 sanction (not $250)?
7. **CA § 2033.280** — Does Cursor's pack distinguish the no-response deemed-admission statute from § 2033.290 (further responses)?
8. **San Bernardino rule numbers** — Does Cursor use Local R. 403/411.1/520/521/560/561 (not placeholders)?
9. **Pierce cite** — Does Cursor use "PCLR" (not "PCLCR")?
10. **Pierce interrogatory caps** — Does Cursor show 25/35/35/100 by track (subparts separate)?
11. **King vs Pierce motion limits** — Does Cursor correctly distinguish King word-limits (4,200/1,750) from Pierce page-limits (12/5)?
12. **eFiling vendors** — Does Cursor correctly show San Bernardino=Odyssey eFileCA, King=KC Script Portal, Pierce=LINX?
13. **ROG/RFA numerical limit handling** — Does Cursor's ROG/RFA request audit correctly handle WA's no-statewide-limit and King/Pierce local caps, or does it use a hardcoded federal 25 default? (Hermes fixed `rog_request_audit.py` to be jurisdiction-aware via `resolve_rog_limit`, now in a shared `jurisdiction/limits.py` module.)
14. **Outgoing ROG limit check** — Does Cursor's `rog_outgoing.py` validate the propounded interrogatory count against the jurisdiction cap (so a plaintiff drafting 50 ROGs in King County gets a FAIL)? (Hermes wired `check_outgoing_rog_limit` into `cmd_validate_outgoing_rog`.)

## ROG request audit — jurisdiction-aware numerical limit (NEW FIX)

The `rog_request_audit.py` hardcoded the interrogatory limit to 35 (CA) or 25 (federal default). This was wrong for WA: CR 33 has NO statewide cap (the 25 cap is federal FRCP 33(a)(1)); King County LCR 26 = 40; Pierce County PCLR 3(h) = 25/35/35/100 by track. Fix: `resolve_rog_limit(profile, available_rules)` with attorney-override precedence; emits `numerical_limit_county_local` warning when no determinable limit exists instead of fail-closing.

## Follow-up gaps (NOT regressions — flagged for a future pass)

These are gaps surfaced during the plaintiff-side review that are out of scope for this autonomous pass but should be addressed before relying on the outgoing/audit skills for live WA plaintiff work:

1. **RFA numerical limit checking.** `rfa_request_audit.py` does not perform any numerical-limit check. CA caps RFAs at 35 (§ 2033.030) unless stipulated; WA has no statewide RFA cap (PCLR 3(h) confirms no RFA limit on any track). A future pass should add `resolve_rfa_limit` mirroring the ROG resolver (CA 35, WA None, attorney override). **ADDRESSED (2026-07-19):** `resolve_rfa_limit` now lives in `jurisdiction/limits.py` (CA 35, WA None, King None-unconfirmed, Pierce None, FRCP None since FRCP 36 has no cap, attorney override wins) and is wired into both `rfa_request_audit.py` (emits `numerical_limit_county_local` warn when no determinable cap, `exceeds_numerical_limit` fail_candidate when projected count exceeds the cap) and `rfa_outgoing.py` (`check_outgoing_rfa_limit` fails validation when the plaintiff propounds over the cap; county-local/none notes are warnings). 13 new tests cover the resolver + both wiring points.
2. **RFP numerical limit checking.** `rfp_request_audit.py` does not perform numerical-limit checking. RFP typically has no numerical cap in CA or WA, but the audit should still confirm "no cap applies" explicitly rather than silently, so the attorney sees the jurisdiction posture. **ADDRESSED (2026-07-19):** `resolve_rfp_limit` now lives in `jurisdiction/limits.py` (always None — RFP has no numerical cap in CA, WA, or federal; attorney override honored) and is wired into both `rfp_request_audit.py` (emits `numerical_limit_none` info note confirming the no-cap posture) and `rfp_outgoing.py` (`check_outgoing_rfp_limit` emits the no-cap warning; an attorney override that is exceeded fails validation). 11 new tests cover the resolver + both wiring points. **The numerical-limit story is now complete across all three request types (ROG/RFA/RFP).**
3. **Outgoing drafting limit checks.** `rog_outgoing.py` checks numerical limits via the shared `resolve_rog_limit`; `rfa_outgoing.py` checks via `resolve_rfa_limit`; `rfp_outgoing.py` confirms the no-cap posture via `resolve_rfp_limit`. A plaintiff drafting 50 ROGs in King County (limit 40), or 36 RFAs in CA (limit 35), gets a FAIL at validate time; RFP always emits a no-cap informational note. **All three outgoing drafting paths now confirm the jurisdiction numerical-limit posture.**
4. **Pierce County track in matter_profile.** The `resolve_rog_limit` Pierce path reads `track` from `matter_profile.yaml`. The matter-profile schema should document `track` as an optional field for Pierce County matters (Expedited/Standard/Complex/Dissolution) so the limit resolves without an attorney override. **Note:** `resolve_rfa_limit` does not need `track` because Pierce has no RFA cap on any track.

These are enhancement candidates, not bugs introduced by this pass. The ROG request-audit fix is the one correctness fix landed here; the RFA/RFP/outgoing items are net-new checks that should be designed together (shared `resolve_*_limit` helpers) in a focused follow-up.

## Verification evidence

- `tests/skills/test_jurisdiction_packs_and_experts.py` — 15 tests passing (pack loading, overlay behavior, expert matching, admissibility, end-to-end synthetic).
- `tests/skills/test_discovery_jurisdiction_packs.py` — 4 tests passing (no regressions in existing pack tests).
- `tests/skills/test_discovery_prepare_ladder.py` + `test_discovery_smoke_counsel_pack.py` — 9 E2E tests passing (after copying gitignored `legal_allowlist.txt` data file into the worktree).
- `expert_analysis.py selftest` — PASS.
- All 5 modified packs load cleanly via `yaml.safe_load`.
- `python -m py_compile` on touched scripts — PASS.

## Items still requiring a licensed attorney (not automatable)

- Any `needs_attorney_rule_confirm: true` flag in the packs (e.g., Pierce Form A dates, San Bernardino department IDC orders, Sanchez 2024-2026 progeny, WA ER 703/704/705 verbatim text).
- Any live matter use requires the owner §9.5 gate (`OWNER_LIVE_GATE_<slice>.md`) — the `owner_gate_assistant.py` automates the burden of review but never the act of approval.
- This is engineering work on skills, not a live client matter. No `C:\Matters\*` paths were touched.

## Citation verification reports (full text)

The full per-jurisdiction citation reports live in `autonomous_review/citation_verification/`:
- `ca_ccp.md` — CA Code of Civil Procedure discovery provisions
- `wa_civil_rules.md` — WA Superior Court Civil Rules (CR)
- `san_bernardino_local.md` — San Bernardino County local rules
- `king_county_local.md` — King County local rules
- `pierce_county_local.md` — Pierce County local rules
- `expert_standards.md` — Expert admissibility standards (FRE 702/Daubert, Kelly/Frye/Sargon/Sanchez, Frye/ER 702)

These are the source-bounded research memos that back every correction above.
