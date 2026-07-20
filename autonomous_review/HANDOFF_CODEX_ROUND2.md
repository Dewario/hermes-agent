# Handoff — Codex Round 2 (Citation Re-Verification + Cross-Claim Stress-Test)

**From:** Hermes Agent (branch `legal-autonomous-ca-wa-experts`)
**To:** Codex (primary `main` checkout)
**Date:** 2026-07-20
**Round:** 2 of 2 before the coordinated merge
**Scope:** (1) citation currency re-verification + (3) cross-claim stress-testing. **NOT** free-form expansion.

> **Amendment 2026-07-20 (post self-verification):** Hermes' independent round-2 self-verification pass (committed at `ca407b069`, see `autonomous_review/round2_self_verification/`) confirmed all original targets and surfaced one new finding — **King County LCR 26(b)(2)(4) caps RFAs at 25** (excluding authenticity RFAs). This amendment adds that cap as a Cluster 4 target and as Axis-2 claim 13, so the mutual cross-check covers it. If your round-2 has already started, verify claim 13 / the new Cluster 4 bullet as an addendum and flag it in your report.

## Context

The reconciliation (`RECONCILIATION_REPORT.md`) and merge plan (`MERGE_PLAN.md`) are complete. Decisions are locked:
- **A1** — pack naming = Hermes' uniform `<state>_<county>`.
- **B1** — expert skill = standalone `expert-witness-analysis/`, with Codex's `expert_needs.py` intake/gap sourcing folded in as an input path.

Before the merge, the user wants one bounded verification round to catch citation drift and premise errors cheaply. This document gives Codex a divided, non-overlapping checklist so a multi-agent / multi-model parallel run does not duplicate work or diverge further.

## How to run this round (multi-agent, multi-model, parallel)

Dispatch agents in parallel along two axes. Use multiple models per axis for independent confirmation (single-model error on a legal cite is the failure mode this round exists to catch).

- **Axis 1 — Citation currency (6 jurisdiction clusters).** One agent per cluster. Each agent opens the official source URL(s) for its cluster, confirms each cited rule is current as of the source's stated effective date, and reports per-cite: `CONFIRMED` / `DRIFTED` (current text + effective date) / `NOT FOUND`.
- **Axis 2 — Cross-claim stress-test (13 load-bearing premises).** One agent per claim (or a small group per agent). Each agent independently verifies the premise against primary sources and reports: `CONFIRMED` / `REFUTED` (with the correction and the source). These are the premises the resolvers and packs are built on — if any is wrong, the logic changes. Claim 13 (King 25-RFA cap) was added 2026-07-20 from Hermes round-2 self-verification.

Recommended model diversity: run each axis with at least two different models and flag any disagreement as a `SPLIT` verdict for human review. Do not auto-apply corrections — report them. Corrections get folded in during the merge (step 7-11 of `MERGE_PLAN.md`).

## Preconditions and hard rules

- **Do not edit `main`.** It holds your uncommitted work. Run this round in a worktree or on a branch; output reports only.
- **No free-form expansion / new features.** This is verification, not development. If you find a gap, log it — do not build it.
- **No live `C:\Matters\*` paths.** No owner §9.5 boxes checked by engineering. No forged signatures.
- **Do not drop Hermes' unique work.** See the "do not lose" lists in `MERGE_PLAN.md`.
- **Authoritative source list:** the six reports under `autonomous_review/citation_verification/` (ca_ccp, wa_civil_rules, san_bernardino_local, king_county_local, pierce_county_local, expert_standards) hold the full cite list with URLs — use them as the canonical index. The clusters below summarize the load-bearing cites with their source links inline so each agent is self-contained. Clusters 1-5 link official portals (leginfo, courts.wa.gov, court/county rule PDFs). Cluster 6 is case law, which has no single official portal, so it links court-published opinions and reliable free mirrors (Justia, Caselaw Access Project `cite.case.law`, LII); confirm each cite and holding against the official reporter text, falling back to Google Scholar / CourtListener if a link 404s.

## Axis 1 — Citation currency clusters (one agent each)

### Cluster 1: CA CCP + Evid. Code
Official source: https://leginfo.legislature.ca.gov/faces/codes.xhtml (CCP = `lawCode=CCP`; Evid = `lawCode=EVID`)
- CCP § 2030.030 — 35 specially prepared interrogatories **plus** official-form (not capped at 35).
- CCP § 2023.050 — monetary sanction floor; confirm it is **$1,000** (SB 235, eff. Jan 1, 2024), not the prior $250.
- CCP § 2033.280 — no-response deemed-admission statute (deemed genuineness/truth + mandatory monetary sanctions).
- CCP § 2031.240 — withholding/objection particulars + privilege log (distinct from § 2031.210 response form).
- CCP § 2016.040 — meet-and-confer declaration required for discovery motions (AB 1521, eff. Jan 1, 2026).
- CCP § 2023.010 — abuse-of-discovery definitions (AB 1521, eff. Jan 1, 2026).
- CCP §§ 2030.020 / 2031.020 / 2033.020 — unlawful-detainer timing (5→10 days, AB 1521, eff. Jan 1, 2026).
- Evid. Code § 801.1 — medical-causation symmetry, operative Jan 1, 2024 (SB 652). Confirm the bill text: https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB652

### Cluster 2: WA CR + ER
Official source: https://www.courts.wa.gov/court_rules/?fa=court_rules.list&group=sup&set=cr (CR) and `&set=er` (ER)
- CR 26(b)(1) — confirm scope is "relevant to the subject matter" and does **NOT** adopt the federal 2015 "proportional to the needs" language.
- CR 26(i) — mandatory pre-motion meet-and-confer + certification (not CR 26(f), which is discretionary).
- CR 33 — confirm **no statewide numerical interrogatory cap** (the federal 25-cap is FRCP 33(a)(1), not WA).
- CR 34 — confirm no statewide numerical RFP cap.
- CR 36 — confirm no statewide numerical RFA cap.
- ER 702 / ER 703 — confirm rule text; confirm there is **no "ERI"** rule (a fictitious label that had crept into an earlier taxonomy).

### Cluster 3: San Bernardino Superior Court local rules
Official source: https://sanbernardino.courts.ca.gov/system/files/local-rules/rulesofcourt.pdf (eff. July 1, 2026)
- Hermes set: Local R. 403, 411.1, 520, 521, 550, 560, 561, 571.
- Codex set: Local R. 400, 404, 411.2, 412, 415, 416, 418.
- eFiling: Local R. 1800-1860 (Odyssey eFileCA; mandatory General Civil eff. Sept. 2, 2025).
- CRC 3.20 preemption — confirm San Bernardino has no freestanding local discovery code (substance is CCP/CRC).
- Confirm both rule subsets exist in the July 1, 2026 PDF and reconcile any renumbering.

### Cluster 4: King County Superior Court local rules
Official source: https://kingcounty.gov/en/dept/dja/courts-jails-legal-system/superior-court-local-rules/local-civil-rules
- LCR 26 — confirm the **40 interrogatory cap** (including discrete subparts; +15 additional to court-approved pattern).
- LCR 26(b)(2)(4) — confirm the **25-RFA cap** per party, **excluding** requests for admission propounded to authenticate documents. Premise for `resolve_rfa_limit(wa_king_county) → 25`. Source: https://kingcounty.gov/en/dept/dja/courts-jails-legal-system/superior-court-local-rules/local-civil-rules/lcr-26 _(Added 2026-07-20 from Hermes round-2 self-verification; not in the original Cluster 4 target list.)_
- LCR 7(b) — confirm **4,200-word** initial/opposition limit and **1,750-word** reply limit; 9 judicial days.
- LCR 33 — confirm the court-approved pattern-interrogatory set.
- Note any current comment-period changes that alter the caps or word limits.

### Cluster 5: Pierce County Superior Court local rules
Official source: https://www.courts.wa.gov/court_rules/pdf/LCR/27/SUP/LCR_Pierce_SUP.pdf (eff. as amended Sept. 1, 2025)
- PCLR 3(h) — confirm interrogatory caps by track: **Expedited 25 / Standard 35 / Complex 35 / Dissolution 100** (the Dissolution 100 cap is the one most often missed).
- PCLR 7(a) — confirm **12-page** initial/opposition and **5-page** reply limits; 7 court days; Friday 9:00 a.m.; assigned judge only.
- PCLR 16 — confirm pretrial / Joint Statement of Evidence.
- PCLGR 30 — confirm e-filing via **LINX** (not Odyssey); confirm discovery-not-filed-with-court is excluded from mandatory e-Service.
- Confirm the cite abbreviation is **"PCLR"** (not "PCLCR").

### Cluster 6: Expert admissibility standards (case law)
Case law has no single official portal; links below are court-published opinions or reliable free mirrors. Confirm each cite and holding against the official reporter text; fall back to Google Scholar / CourtListener if a link 404s.
- Sargon v. USC (2012) **55 Cal.4th 747** — CA admissibility gatekeeper standard. Confirm citation (a common error is 53 Cal.4th 1210). Source: https://law.justia.com/cases/california/supreme-court/2012/s191550.html (also on courts.ca.gov opinions).
- People v. Sanchez (2016) **63 Cal.4th 665** — CA case-specific opinion basis (expert may not relate case-specific hearsay to the jury as independent proof of the facts). Confirm citation (a common error is 1 Cal.5th 865; also do not conflate with Sanchez v. Hillerich & Bradsby (2002) 97 Cal.App.4th 503, a different Court-of-Appeal products case). Source: https://law.justia.com/cases/california/supreme-court/2016/s216681.html (also on courts.ca.gov opinions).
- People v. Kelly (1976) 17 Cal.3d 24 — CA standard for novel scientific evidence. Source: https://cite.case.law/cal3d/17/24/ (Caselaw Access Project; fallback Google Scholar).
- State v. Copeland, 130 Wn.2d 244, 922 P.2d 1304 (1996) — WA Frye standard. Confirm citation (the page is 244, not 24; include the parallel P.2d cite). Source: https://law.justia.com/cases/washington/supreme-court/1996/62417-8-1.html (also on courts.wa.gov opinions).
- Frye v. United States, 293 F. 1013 (D.C. Cir. 1923) — WA's adopted standard. Source: https://cite.case.law/f/293/1013/ (Caselaw Access Project; fallback Google Scholar).
- Daubert v. Merrell Dow, 509 U.S. 579 (1993) — federal admissibility standard. Source: https://cite.case.law/us/509/579/ (Caselaw Access Project). FRE 702 current text: https://www.law.cornell.edu/rules/fre/rule_702 (LII).
- Confirm there is **no "State v. Frye (1995)"** and **no "Copeland-Bryant (2018)"** — both are fictitious cites that had crept into an earlier taxonomy.

## Axis 2 — Cross-claim stress-test (one agent per claim, or group)

Each premise below is load-bearing: a resolver or pack is built on it. If any is refuted, the logic must change before merge. Verify each against primary sources and report `CONFIRMED` / `REFUTED` (with correction + source).

1. **WA CR 33 has NO statewide interrogatory cap.** Premise for `resolve_rog_limit(wa_state) → None`. (If a statewide cap exists, the resolver must return it, not None.)
2. **King County LCR 26 caps interrogatories at 40** (including discrete subparts). Premise for `resolve_rog_limit(wa_king_county) → 40`.
3. **Pierce County PCLR 3(h) caps = 25 / 35 / 35 / 100** by track (Expedited / Standard / Complex / Dissolution). Premise for `resolve_rog_limit(wa_pierce_county)` track map. The **Dissolution 100** cap is the one to verify hardest — it is the most commonly missed.
4. **CA CCP § 2033.280** (not § 2033.290) is the no-response deemed-admission statute. Premise for the deemed-admission enforcement lever.
5. **CA § 2023.050 sanction = $1,000** (not $250) as of Jan 1, 2024 (SB 235). Premise for the sanction-amount correction.
6. **CA Evid. Code § 801.1** is operative Jan 1, 2024 (SB 652) and establishes medical-causation symmetry (defense alternative-cause experts must opine to reasonable medical probability). Premise for the plaintiff-favorable exclusion tool.
7. **Sargon = (2012) 55 Cal.4th 747** (not 53 Cal.4th 1210). Premise for the CA admissibility cite.
8. **People v. Sanchez = (2016) 63 Cal.4th 665** (not 1 Cal.5th 865; and not Sanchez v. Hillerich & Bradsby (2002) 97 Cal.App.4th 503, a different case). Premise for the CA case-specific-opinion cite.
9. **Pierce County cite abbreviation = "PCLR"** (not "PCLCR"). Premise for all Pierce rule IDs.
10. **King uses word-limits (4,200 / 1,750); Pierce uses page-limits (12 / 5).** Premise for the motion-limit notes and the explicit word-vs-page contrast.
11. **FRCP 36 has NO numerical cap** (unlike FRCP 33's 25). Premise for `resolve_rfa_limit(federal) → None`. (If FRCP 36 caps RFAs, the federal default must change.)
12. **FRCP 34 has NO numerical cap.** Premise for `resolve_rfp_limit → None` in every jurisdiction. (If any jurisdiction caps RFP count, the resolver must learn it.)
13. **King County LCR 26(b)(2)(4) caps RFAs at 25** per party, **excluding** requests for admission propounded solely to authenticate documents. Premise for `resolve_rfa_limit(wa_king_county) → 25` (currently the resolver returns `None` for the whole WA family — safe via attorney override, but unnecessarily conservative). Source: https://kingcounty.gov/en/dept/dja/courts-jails-legal-system/superior-court-local-rules/local-civil-rules/lcr-26. _(Added 2026-07-20 from Hermes round-2 self-verification; this is the new finding, so Round-2 must verify it independently for the mutual cross-check to cover it.)_

## Deliverables from Codex (output only — no edits to `main`)

1. **Per-cluster verification report** (6 reports, one per Axis-1 cluster): for each cite, `CONFIRMED` / `DRIFTED` (current text + effective date) / `NOT FOUND`, with the source URL and access date. For clusters 1-5 the source URL is an official portal; for cluster 6 (case law) it is a court-published opinion or a reliable mirror (Justia / Caselaw Access Project / LII) plus confirmation of the cite against the official reporter text — not "official portal only."
2. **Cross-claim verdict table** (13 rows, one per Axis-2 claim): claim → `CONFIRMED` / `REFUTED` (correction + source) / `SPLIT` (models disagreed).
3. **Corrections list**: any `DRIFTED` / `REFUTED` item, with the exact fix and which merge-plan step it maps to (steps 7-11).
4. **A short confidence summary**: how many cites confirmed vs. drifted, how many cross-claims confirmed vs. refuted, and any jurisdiction where the source was inaccessible.

Write these to a single `ROUND2_VERIFICATION_REPORT.md` in your own review directory (do not commit into the shared tree until the coordinated merge).

## What NOT to do

- No free-form expansion or new features — verification only.
- No editing `main` (it's dirty with your uncommitted work — clean it first or work in a worktree/branch).
- No auto-applying corrections — report them; they get folded in during the merge.
- No live `C:\Matters\*` paths; no owner §9.5 boxes checked by engineering; no forged signatures.
- Do not drop Hermes' unique work (resolvers, CA CCP enforcement levers, pinned local details, expert taxonomy) — see "do not lose" in `MERGE_PLAN.md`.

## After this round

When the verification report is in, the coordinated merge executes per `MERGE_PLAN.md`:
1. Clean `main` (commit/stash Codex's uncommitted work).
2. Port resolvers + re-wire (steps 1-6).
3. Fold any Round-2 corrections into the CA CCP / WA / local packs (steps 7-11).
4. Apply B1 (fold Codex's expert sourcing into the standalone skill) (step 12).
5. Apply A1 (rename packs to the uniform convention; update references) (step 13).
6. Re-run the full legal suite; confirm `git diff --check` passes; confirm 139+ tests green.

No live matter use until owner §9.5 per matter/request/mode/slice + attorney review.
