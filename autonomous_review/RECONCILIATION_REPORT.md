# Autonomous Review — Reconciliation Report (Hermes vs Codex)

**Branch:** `legal-autonomous-ca-wa-experts`
**Worktree:** `C:\Users\Prime\AppData\Local\hermes\hermes-agent-autonomous`
**Codex work location:** `main` checkout (`C:\Users\Prime\AppData\Local\hermes\hermes-agent`), uncommitted
**Report date:** 2026-07-19
**Purpose:** Itemize every significant divergence between Hermes' autonomous work and Codex's parallel work, framed by the 14 cross-check questions in `CROSS_CHECK_REPORT.md`. This is engineering work on skills — not a live client matter. No `C:\Matters\*` paths were touched.

## How to read this report

- **Hermes** = work on the isolated `legal-autonomous-ca-wa-experts` branch (this worktree).
- **Codex** = uncommitted changes on `main` in the primary checkout.
- Each divergence is classified: `MATCH` (both agree), `GAP` (Codex missing what Hermes has), `PARTIAL` (Codex has some but not all), `DIVERGENCE` (both have something but they differ), `BUG` (Codex retains a correctness bug Hermes fixed).
- Line numbers cited are from Codex's files in the main checkout unless noted.

## Naming divergence (architectural)

The two efforts chose different pack file names and different expert-skill architecture. This is the single largest structural difference and must be reconciled before any merge.

| Concept | Hermes | Codex |
|---|---|---|
| WA state base pack | `wa_state.yaml` | `wa_cr.yaml` |
| King County overlay | `wa_king_county.yaml` | `wa_king_lcr.yaml` |
| Pierce County overlay | `wa_pierce_county.yaml` | `wa_pierce_pclr.yaml` |
| San Bernardino overlay | `ca_san_bernardino.yaml` | `ca_san_bernardino_local.yaml` |
| Expert skill | `skills/legal/expert-witness-analysis/` (own skill dir, `expert_analysis.py`, `expert_taxonomy.yaml`) | `skills/legal/discovery-workflow/scripts/expert_needs.py` (single script inside discovery-workflow) |

Hermes' expert work is a **standalone skill** with a YAML taxonomy of expert categories and per-jurisdiction admissibility notes (Sargon/Sanchez/Copeland/Cauthron cites, § 801.1). Codex' expert work is a **single script** under discovery-workflow that builds a skeletal packet from intake/gap themes and references rule IDs only — it carries no case-law cites and no per-jurisdiction admissibility standard text.

## WA State pack — `wa_state.yaml` (Hermes) vs `wa_cr.yaml` (Codex)

**Q1 — WA CR 33 interrogatory limit.** `GAP (explicitness)`. Codex's `WA-CR-33-A` (lines 38-43) states only that "Interrogatories may be served without leave at the stated early pleading stage; answers or objections are generally due in 30 days, or 40 days for a defendant." It is **silent** on the numerical cap. It does not repeat the federal "25" error, but it also does **not** affirmatively state "no statewide cap; limits are county-local" the way Hermes' pack does. A reader cannot tell from Codex' pack whether WA has a statewide cap or not. Hermes' pack explicitly states no statewide limit + county-local (King 40, Pierce by track).

**Q2 — CR 26(b)(1) proportionality.** `MATCH`. Codex's `WA-CR-26-SCOPE` (lines 10-15) correctly uses "relevant to the subject matter" and **omits** the federal "proportional to the needs" language. Correct.

**Q3 — fictitious "ERI" rule.** `MATCH`. Codex uses `WA-ER-702` and `WA-ER-703` (lines 101-113) — correct labels, no "ERI" anywhere. Correct.

**CR 26(i) meet-and-confer.** `MATCH`. Codex's `WA-CR-26-I` (lines 31-36) correctly captures the mandatory pre-motion conference + certification. Correct.

**CR 26(g) general objections.** `MATCH`. Codex's `WA-CR-26-G` (lines 24-29) correctly states general objections are not permitted + privilege detail required. Correct.

**CR 26(e) supplementation.** `MATCH`. Codex's `WA-CR-26-E` (lines 17-22) captures the seasonable-supplement duty. Correct.

**Net WA state:** Codex is correct on substance but **less explicit on the CR 33 no-cap point** — the one premise that caused the hardcoded-25 bug in the audit script. Hermes' explicit "no statewide cap" statement is what prevents that bug class from recurring.

## CA CCP pack — `ca_ccp.yaml` (both names match)

**§ 2030.030 interrogatory cap (official-form "plus" framing).** `MATCH`. Codex's `CCP-2030-030` (lines 31-36) correctly states "35 specially prepared interrogatories, **plus** official-form interrogatories." This matches Hermes' fix — official-form interrogatories are additional, not capped at 35. Correct.

**Q6 — § 2023.050 $1,000 sanction.** `GAP`. Codex's `ca_ccp.yaml` has **no § 2023.050** entry at all. The $250→$1,000 sanction increase (SB 235, eff. Jan. 1, 2024) is absent. Hermes' pack carries it.

**Q7 — § 2033.280 deemed-admission.** `GAP`. Codex's RFA rules are § 2033.030, § 2033.060, § 2033.210, § 2033.220 only (lines 73-99). **No § 2033.280** — the principal no-response deemed-admission statute (waiver + motion to deem genuineness/truth admitted + mandatory monetary sanctions). § 2033.290 (further responses) is also absent. Hermes' pack carries § 2033.280 as a distinct rule.

**§ 2031.240 objection particulars.** `GAP`. Codex's RFP rules are § 2031.030, § 2031.210, § 2031.280 (lines 52-71). **No § 2031.240** — the withholding/objection-particulars + privilege-log statute. Hermes' pack carries it as a distinct rule (§ 2031.210 is the response form; § 2031.240 is the particulars).

**§ 2016.040 meet-and-confer declaration.** `GAP`. Codex's `ca_ccp.yaml` has **no § 2016.040** — the meet-and-confer declaration required for discovery motions (amended by AB 1521, eff. Jan. 1, 2026). Hermes' pack carries it.

**§ 2023.010 abuse of discovery.** `GAP`. Codex's `ca_ccp.yaml` has **no § 2023.010** — the abuse-of-discovery definitions amended by AB 1521. Hermes' pack carries it.

**Unlawful-detainer timing (§§ 2030.020/2031.020/2033.020).** `GAP`. Codex's `ca_ccp.yaml` has none of these. The 5→10-day amendments (AB 1521, eff. Jan. 1, 2026) are absent. Hermes' pack notes them.

**§ 1281 removed from discovery context.** `MATCH` (by omission). Codex's `ca_ccp.yaml` does not cite § 1281 in a discovery proposition, so it does not repeat the arbitration-enforcement mis-citation Hermes corrected.

**Net CA CCP:** Codex got exactly **one** of the seven CA CCP corrections (the § 2030.030 "plus" framing). It **misses six**: § 2023.050 ($1,000 sanction), § 2033.280 (deemed admission), § 2031.240 (objection particulars), § 2016.040 (meet-and-confer declaration), § 2023.010 (abuse of discovery), and the unlawful-detainer timing amendments. These are all plaintiff-relevant: § 2033.280 is the primary enforcement lever for deemed admissions against a non-responding defendant; § 2023.050 is the mandatory sanction for document-production misconduct.

## San Bernardino overlay — `ca_san_bernardino.yaml` (Hermes) vs `ca_san_bernardino_local.yaml` (Codex)

**Q8 — San Bernardino rule numbers.** `DIVERGENCE`. The two packs cite **different subsets** of the local rules:

| Hermes rule IDs | Codex rule IDs |
|---|---|
| Local R. 403 (all-purpose judge assignment) | Local R. 400 (civil case-management scope) |
| Local R. 411.1 (Initial Trial Setting Conference) | Local R. 404 (civil action category designation) |
| Local R. 520/521 (reserve hearing date; moving papers + fees) | Local R. 411.1 (Initial Trial Setting Conference) — **shared** |
| Local R. 550 (continuance notice by 4:30 p.m. second court day) | Local R. 411.2 (Trial Readiness Conference) |
| Local R. 560 (meet-and-confer declaration enforcement) | Local R. 412 (complex case guidelines) |
| Local R. 561 (tentative rulings after 3:00 p.m.) | Local R. 415 (motions in limine) |
| Local R. 571 (exhibits filed not lodged) | Local R. 416 (trial-date readiness notice) |
| — | Local R. 418 (continuances per CRC 3.1332) |

Only **Local R. 411.1** overlaps. Both packs are internally consistent with the July 1, 2026 Local Rules PDF, but they cover **different rule chapters**. Hermes focuses on the hearing-reservation/tentative-ruling/meet-and-confer/exhibit rules (520-571 series) most relevant to discovery motion practice; Codex focuses on the case-management/trial-readiness series (400-418). A complete pack would carry **both** subsets.

**eFiling rules (Local R. 1800-1860, Odyssey eFileCA).** `GAP`. Codex's `ca_san_bernardino_local.yaml` has **no e-filing rules** — even though Codex's own subagent citation report reportedly mentioned them. Hermes' pack carries the eFiling rule (Local R. 1800-1860; Odyssey eFileCA; mandatory General Civil eff. Sept. 2, 2025). For a plaintiff-side filer, the e-filing vendor and mandatory-eff date are operationally load-bearing.

**CRC 3.20 preemption note.** `GAP`. Codex's pack does not carry an explicit CRC 3.20 preemption note (the statement that San Bernardino has no freestanding local discovery code; discovery substance comes from CCP/CRC). Hermes' pack carries it.

## King County overlay — `wa_king_county.yaml` (Hermes) vs `wa_king_lcr.yaml` (Codex)

**King interrogatory cap = 40.** `GAP`. Codex's `KING-LCR-26-CAPS` (lines 26-31) says only "Covered civil cases have local caps for interrogatories, depositions, and RFAs; over-limit discovery requires stipulation or court order." It **does not pin the specific 40 interrogatory cap** (LCR 26: 40 including discrete subparts, or 15 additional to court-approved pattern). A plaintiff drafting ROGs in King County cannot read the cap from Codex' pack. Hermes' pack states 40 explicitly.

**Q11 — King word limits (4,200/1,750).** `GAP`. Codex's `KING-LCR-7-MOTION` (lines 54-59) mentions only "local judicial-day deadlines for motion, opposition, and reply papers." It **does not specify the 4,200-word initial/opposition limit or the 1,750-word reply limit**, nor the 9-judicial-day timing. Hermes' pack carries LCR 7(b): 9 judicial days; 4,200 words (initial/opposition), 1,750 reply; no oral argument default.

**LCR 4 case schedule, LCR 26(k) witness, LCR 33 pattern, LCR 37(g) cutoff.** `MATCH`. Codex covers these (lines 12-52) with reasonable substance — CSO milestones, stipulated extension, witness disclosure, pattern interrogatories, discovery cutoff. Hermes covers the same plus the specific caps and word limits.

## Pierce County overlay — `wa_pierce_county.yaml` (Hermes) vs `wa_pierce_pclr.yaml` (Codex)

**Q9 — Pierce cite is "PCLR" not "PCLCR".** `MATCH`. Codex's `pack_id: wa_pierce_pclr` and all citations use "PCLR" correctly (lines 13, 20, 27, 34, 41, 48, 55, 62). Correct.

**Q10 — Pierce interrogatory caps 25/35/35/100 by track.** `PARTIAL`. Codex's `PIERCE-PCLR-3-ROG-CAPS` (lines 26-31) states "expedited uses 25, standard and complex use 35, with subparts counted as separate interrogatories." It **omits the Dissolution-track 100 cap**. Hermes' pack carries all four: Expedited 25, Standard 35, Complex 35, Dissolution 100. For a plaintiff in a Pierce County dissolution matter, the missing 100 cap is a real gap.

**Pierce RFA no limit.** `MATCH`. Codex's `PIERCE-PCLR-3-RFA` (lines 33-38) correctly states no local numerical limit on RFAs for expedited/standard/complex tracks. Correct.

**Q11 — Pierce page limits (12/5) vs King word limits.** `GAP`. Codex's `PIERCE-PCLR-7-MOTION-TIMING` (lines 54-59) mentions only "filing, opposition, reply, working-copy, and confirmation deadlines measured in court days." It **does not specify the 12-page initial/opposition limit or the 5-page reply limit**, nor the assigned-judge-only / Friday 9:00 a.m. docket / 7 court days filing. Hermes' pack carries PCLR 7(a): assigned judge only; Friday 9:00 a.m.; 7 court days; **page** limits 12 initial/opposition, 5 reply — and explicitly contrasts King uses words, Pierce uses pages.

**Pierce track cutoffs (20/26, 45/52, 67/78 weeks).** `GAP`. Codex's `PIERCE-PCLR-3-CUTOFFS` (lines 19-24) mentions "week-based discovery cutoffs and trial intervals" but does not pin the specific week numbers per track. Hermes' pack pins them.

**eFiling vendor (LINX, not Odyssey).** `GAP`. Codex's pack has no e-filing vendor rule. Hermes' pack carries PCLGR 30: e-filing via LINX (not Odyssey), with discovery-not-filed-with-court excluded from mandatory e-Service.

## Expert skill — `expert-witness-analysis/` (Hermes) vs `expert_needs.py` (Codex)

**Architecture.** `DIVERGENCE`. Hermes ships a standalone skill (`skills/legal/expert-witness-analysis/`) with `SKILL.md`, `SPEC.md`, a data-driven `expert_taxonomy.yaml`, and `expert_analysis.py` that resolves the admissibility standard per jurisdiction (federal FRE 702/Daubert, CA Kelly/Sargon + § 801.1, WA Frye/Copeland + ER 702). Codex ships a single script (`discovery-workflow/scripts/expert_needs.py`) that builds a skeletal packet from intake/gap themes and references rule IDs only. Codex' approach is lighter but carries **no per-jurisdiction admissibility standard text and no case-law cites**.

**Q4 — Sargon (55 Cal.4th 747) and Sanchez (63 Cal.4th 665) cites.** `GAP`. Codex' `expert_needs.py` `_rule_ids_for_expert_need` (lines 493-514) references only rule IDs (`EVID-720`, `EVID-801`, `CCP-2034-210`, etc.). It **does not include** the Sargon or Sanchez case citations. A plaintiff attorney using Codex' packet would not see the controlling CA Supreme Court admissibility cases. Hermes' taxonomy folds Sargon (55 Cal.4th 747) into accident-reconstruction/forensic-medical CA notes and Sanchez (63 Cal.4th 665) into medical-causation CA notes.

**Q5 — CA Evid. Code § 801.1 (Jan. 1, 2024 medical-causation symmetry).** `GAP`. Codex' preferred rule-ID list (lines 498-503) includes `EVID-801` (§ 801) but **not `EVID-801-1`** (§ 801.1). The medical-causation symmetry rule — defense alternative-cause experts must opine to reasonable medical probability, a plaintiff-favorable exclusion tool operative since Jan. 1, 2024 (SB 652) — is absent. Hermes' taxonomy folds § 801.1 into treating-physician and forensic-medical CA notes.

**Fictitious "ERI" rule.** `MATCH`. Codex' `expert_needs.py` uses `WA-ER-702`, `WA-ER-703` (line 501) — no "ERI". Correct.

**Fictitious "State v. Frye (1995)" / "Copeland-Bryant (2018)" / "State v. Frye".** `MATCH` (by omission). Codex' script does not cite any WA cases, so it does not repeat the fictitious-case error. Hermes' taxonomy explicitly warns against these non-existent cases.

**Expert validate gates (verify-cites / check-isolation).** `DIVERGENCE (approach)`. Codex' `cmd_validate` (lines 813-817) hardcodes `--allow-empty` on `verify-cites` and `--strict` on `check-isolation` **directly in the expert script's gate list** — so the expert skill passes without citing the record, but the relaxation is local to this one script. Hermes took the **general** route: added an opt-in `--allow-empty-cites` flag to `live_preflight.py` itself, which forwards `--allow-empty` to `verify-cites` **and** relaxes `check-isolation` to non-strict. Hermes' approach serves any future non-record-citing document (intake drafts, expert recommendation reports, gap-theme memos) via one shared flag; Codex' approach works for the expert script only and would need duplication for the next non-record-citing document.

## Script-level bugs — the correctness-critical divergences

These are the two items where Codex' work retains a real bug or gap that Hermes fixed. They are the highest-priority items to reconcile before any merge.

**Q13 — `rog_request_audit.py` ROG numerical limit (HARD CODED BUG).** `BUG`. Codex' `rog_request_audit.py` line 411 still reads:

```python
411:    limit = 35 if "CCP-2030-030" in available_rules else DEFAULT_ROG_LIMIT
```

with `DEFAULT_ROG_LIMIT = 25` at line 42. This means: for any WA matter (no `CCP-2030-030` rule in the WA pack), the audit silently applies the **federal FRCP 33(a)(1) cap of 25** — which is wrong for WA. WA CR 33 has **no statewide cap**; King County LCR 26 = 40; Pierce County PCLR 3(h) = 25/35/35/100 by track. A plaintiff auditing 30 defense-served ROGs in King County under Codex' code would get a false `exceeds_numerical_limit` fail_candidate against a 25 cap that does not apply. Hermes fixed this by extracting `resolve_rog_limit(profile, available_rules)` into a shared `jurisdiction/limits.py` module (CA 35, FRCP 25, WA None with `numerical_limit_county_local` warning, King 40, Pierce by track, attorney-override precedence) and wiring it into `audit_request` + `cmd_audit_incoming_rog`. Codex' audit is **not jurisdiction-aware** for ROG limits.

**Q14 — `rog_outgoing.py` outgoing ROG limit check.** `GAP`. Codex' `rog_outgoing.py` has **no numerical-limit check at all** — grep for `limit|resolve_rog|check_outgoing|numerical` returns zero matches. A plaintiff drafting 50 outgoing ROGs in King County (limit 40) gets no FAIL at validate time under Codex' code. Hermes wired `check_outgoing_rog_limit` into `cmd_validate_outgoing_rog` via the shared `resolve_rog_limit`, so a plaintiff drafting 50 ROGs in King County gets a FAIL at validate time. This is a plaintiff-side protection Codex does not have.

**`live_preflight.py` axis arguments (`--request-type`/`--mode`/`--slice`).** `MATCH`. Codex' `live_preflight.py` (lines 70-92, 205-239) added `--request-type` (with `expert` choice), `--mode` (with `expert_needs_assessment`), and `--slice` — matching Hermes' implementation. Both efforts independently reached the same axis-aware preflight design.

**`live_preflight.py` `--allow-empty-cites` flag.** `GAP`. Codex' `live_preflight.py` has **no `--allow-empty-cites` flag** (grep for `allow-empty|allow_empty` returns no matches). Codex' relaxation is done by hardcoding `--allow-empty` in the expert script's own gate list (see above), not by adding a general opt-in to live_preflight. Hermes added the general flag. The consequence: any **other** non-record-citing document that runs through `live_preflight` (intake drafts, gap-theme memos) will still fail-closed under Codex' live_preflight on zero same-matter cites.

## Scorecard — 14 cross-check questions

| # | Question | Codex result | Classification |
|---|---|---|---|
| 1 | WA CR 33 no statewide limit | Silent (no error, no explicit statement) | GAP (explicitness) |
| 2 | WA CR 26(b)(1) no federal proportionality | Correctly omits | MATCH |
| 3 | No fictitious "ERI" | Uses WA-ER-702/703 | MATCH |
| 4 | Sargon 55 Cal.4th 747 / Sanchez 63 Cal.4th 665 | Not present (rule IDs only) | GAP |
| 5 | CA § 801.1 (Jan. 1, 2024) | Not present (EVID-801 only) | GAP |
| 6 | CA § 2023.050 $1,000 sanction | Not present | GAP |
| 7 | CA § 2033.280 deemed admission | Not present | GAP |
| 8 | San Bernardino rule numbers | Different subset (400-418 vs 403/520-571) | DIVERGENCE |
| 9 | Pierce "PCLR" not "PCLCR" | Uses PCLR | MATCH |
| 10 | Pierce caps 25/35/35/100 by track | 25/35/35 only — missing Dissolution 100 | PARTIAL |
| 11 | King word vs Pierce page limits | Neither pinned | GAP |
| 12 | eFiling vendors (Odyssey/KC Script/LINX) | Not present | GAP |
| 13 | ROG request audit jurisdiction-aware limit | Hardcoded 35/25 bug retained | BUG |
| 14 | Outgoing ROG limit check | No check at all | GAP |

**Totals:** 3 MATCH, 1 PARTIAL, 1 DIVERGENCE, 8 GAP, 1 BUG. Plus the architectural/naming divergence on top.

## What Codex has that Hermes does not

For honesty, this is not a one-directional comparison. Codex' work includes items Hermes' branch does not yet carry:

- **San Bernardino Local R. 400, 404, 411.2, 412, 415, 416, 418** — the case-management / trial-readiness / motions-in-limine / continuance series. Hermes' San Bernardino pack focuses on the hearing-reservation series (520-571) and omits these. A complete pack carries both.
- **`SOURCE_PACKET.md`** — Codex added a provenance document for the jurisdiction packs. Hermes' branch has citation-verification reports but not a single consolidated source-provenance packet.
- **King LCR 33 pattern-interrogatory rule** — Codex' `KING-LCR-33-PATTERN` explicitly flags the court-approved pattern set question. Hermes' King pack covers the 40 cap but not the pattern-set path.
- **Pierce PCLR 16 pretrial / Joint Statement of Evidence** — Codex' `PIERCE-PCLR-16-PRETRIAL` covers dispositive-motion cutoff and the joint evidence statement. Hermes' Pierce pack does not carry PCLR 16.

## Reconciliation recommendation

The two efforts are **complementary, not conflicting** on most points. The recommended merge order, before any live use:

1. **Fix the two script-level bugs first (highest priority).** Port Hermes' `jurisdiction/limits.py` + `resolve_rog_limit` into the main tree and wire it into both `rog_request_audit.py` (replacing the hardcoded line 411) and `rog_outgoing.py` (adding `check_outgoing_rog_limit`). This removes the federal-25-cap false-fail on WA matters and adds the plaintiff-side outgoing-limit protection. These are correctness fixes, not style choices.
2. **Port the `--allow-empty-cites` flag into `live_preflight.py`** so non-record-citing documents get the relaxation generally, then simplify Codex' expert script to use the flag instead of hardcoding `--allow-empty` in its own gate list.
3. **Merge the CA CCP corrections** (§§ 2023.050, 2033.280, 2031.240, 2016.040, 2023.010, unlawful-detainer timing, § 801.1) into Codex' `ca_ccp.yaml`. Codex' pack is missing six plaintiff-relevant corrections.
4. **Merge the explicit WA CR 33 no-statewide-cap statement** into Codex' `wa_cr.yaml` — this is the premise that prevents the hardcoded-25 bug from recurring.
5. **Reconcile the San Bernardino rule subsets** — carry both the 400-418 series (Codex) and the 520-571 series (Hermes), plus the eFiling rule (1800-1860) and the CRC 3.20 preemption note.
6. **Pin the specific King 40 cap, King 4,200/1,750 word limits, Pierce 25/35/35/100 caps (incl. Dissolution 100), and Pierce 12/5 page limits** into Codex' overlays. Codex' summaries mention "local caps" without the numbers a practitioner needs.
7. **Decide the expert-skill architecture.** Codex' single-script approach is lighter and ships inside discovery-workflow; Hermes' standalone-skill approach carries per-jurisdiction admissibility standards and case-law cites (Sargon/Sanchez/Copeland/§ 801.1). For plaintiff-side trial work the case-law cites are load-bearing — a packet that says "consider a medical-causation expert" without naming Sanchez or § 801.1 is materially weaker. Recommend keeping the standalone skill and folding Codex' intake/gap-theme sourcing into it as an additional input path.
8. **Resolve the naming divergence last.** Pick one pack-name convention (`wa_state`/`wa_king_county`/`wa_pierce_county`/`ca_san_bernardino` vs `wa_cr`/`wa_king_lcr`/`wa_pierce_pclr`/`ca_san_bernardino_local`) and rename consistently, including `overlays_allowed` references in the base packs and any matter_profile templates.

## Items still requiring a licensed attorney (not automatable)

- Any `needs_attorney_rule_confirm: true` flag in either set of packs.
- The San Bernardino rule-number divergence (Q8) should be resolved by a licensed attorney confirming which rule chapters govern the specific department/complexity before either pack is relied on.
- Any live matter use requires the owner §9.5 gate (`OWNER_LIVE_GATE_<slice>.md`). The `owner_gate_assistant.py` automates the burden of review but never the act of approval.
- This is engineering work on skills, not a live client matter. No `C:\Matters\*` paths were touched in either worktree.

## Verification evidence

- All Codex file contents cited above were read directly from the main checkout (`C:\Users\Prime\AppData\Local\hermes\hermes-agent`) on 2026-07-19.
- Line numbers refer to Codex' files in the main checkout unless noted.
- Hermes-side corrections are documented in `autonomous_review/CROSS_CHECK_REPORT.md` and backed by `autonomous_review/citation_verification/*.md`.
- Hermes-side tests: `tests/skills/test_jurisdiction_packs_and_experts.py` (14 invariant tests), `tests/skills/test_discovery_rog_request_audit.py` (8 jurisdiction-aware-limit tests), `tests/skills/test_discovery_rog_outgoing.py` (7 outgoing-limit tests) — all passing on the `legal-autonomous-ca-wa-experts` branch.
