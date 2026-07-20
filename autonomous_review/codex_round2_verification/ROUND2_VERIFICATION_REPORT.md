# Codex Round 2 Verification Report

**Date:** 2026-07-20
**Worktree:** `C:\Users\Prime\AppData\Local\hermes\hermes-agent-codex-round2`
**Branch:** `codex/round2-verification`
**Base checked out:** `main` at `9718cc340`
**Compared against:** `legal-autonomous-ca-wa-experts` at `d859e6a73`
**Scope:** source-bounded verification of `autonomous_review/HANDOFF_CODEX_ROUND2.md`,
`round2_self_verification`, and merge-readiness claims.

## Discipline

- Report only. No code, pack, resolver, skill, or template edits were made.
- No edits to the primary `main` checkout.
- No live `C:\Matters\*` paths touched.
- No owner section 9.5 boxes checked, drafted, or signed.
- This is legal-source verification and engineering merge review, not case advice.

## Method

The pass combined targeted subagent verification with local retrieval and source
inspection:

- Cluster 1: California CCP and Evidence Code, against California Legislative
  Information.
- Cluster 2: Washington CR and ER, against Washington Courts official rule PDFs
  and rule index.
- Cluster 3: San Bernardino Superior Court local rules, eFiling pages, and CRC
  3.20.
- Clusters 4 and 5: King and Pierce local civil rules, current 2025 rule sets,
  and posted 2026 proposed-rule materials where relevant.
- Cluster 6: expert-admissibility case law and federal evidence/civil rules,
  using court resources, Justia/case-law mirrors, U.S. Courts rule pages, and
  LII for current readable rule text.

## Headline Verdict

**Passed with exceptions.** The legal premises are substantially confirmed and
the merge plan remains executable. There are no refuted load-bearing premises.
The exceptions are merge-time clarifications, not blockers to the coordinated
merge:

1. King County RFA cap must be wired at merge time: 25 non-authenticity RFAs
   under LCR 26(b)(2)(4), with authenticity RFAs excluded from the count.
2. San Bernardino eFiling date/source language should cite the civil eFiling
   requirements page for mandatory General Civil effective September 2, 2025;
   Local Rule 1810.B alone is only the designated-cases framework.
3. San Bernardino "no local discovery code" language should be narrowed to
   "no stand-alone civil local discovery chapter/rule series identified in the
   July 1, 2026 SBSC civil rules."
4. King LCR 33 should be treated as partial but usable: LCR 33 governs use and
   format of pattern interrogatories, and King official forms pages confirm an
   approved automobile-tort pattern set, but the current rule page itself shows
   subsection (a) as reserved. Do not encode broader pattern-set names unless
   separately sourced.

## Cluster Results

| # | Cluster | Verdict | Notes |
|---|---|---|---|
| 1 | CA CCP + Evidence Code | CONFIRMED with nuance | CCP Secs. 2030.030, 2023.050, 2033.280, 2033.290, 2031.240, 2031.210, 2016.040, 2023.010, 2030.020, 2031.020, 2033.020, and Evid. Code Sec. 801.1 all held against LegInfo. Nuance: Evid. Code Sec. 801.1 was added by SB 652 and scoped/amended by SB 135. |
| 2 | WA CR + ER | CONFIRMED | CR 26(b)(1), CR 26(i), CR 33, CR 34, CR 36, ER 702, ER 703, and no "ERI" rule all held against Washington Courts sources. CR 33/34/36 have no statewide numerical caps. |
| 3 | San Bernardino local | CONFIRMED with narrowing | Local Rules 400, 403, 404, 411.1, 411.2, 412, 415, 416, 418, 520, 521, 550, 560, 561, 571, and 1800-1860 were found in the current local-rules PDF. The eFiling implementation date should be sourced to the civil eFiling requirements page. |
| 4 | King County local | CONFIRMED with one partial item | LCR 26 40-ROG cap, LCR 26(b)(2)(4) 25-RFA cap excluding authentication RFAs, and LCR 7 4,200/1,750 word limits are confirmed. LCR 33 pattern-interrogatory support is partial as described above. |
| 5 | Pierce County local | CONFIRMED | PCLR abbreviation, PCLR 3(h) 25/35/35/100 ROG caps by track, no RFA cap, PCLR 7 timing/page limits, PCLR 16 Joint Statement, and PCLGR 30/LINX points are confirmed. 2026 proposals do not disturb the checked provisions as of this pass. |
| 6 | Expert standards | CONFIRMED | Sargon, People v. Sanchez, People v. Kelly, State v. Copeland, Frye, Daubert, FRE 702, WA ER 702/703 all held. No source support was found for the fictitious "State v. Frye (1995)" or "Copeland-Bryant (2018)" labels. |

## Axis 2 Cross-Claim Verdict Table

| # | Premise | Codex Round 2 verdict | Merge impact |
|---|---|---|---|
| 1 | WA CR 33 has no statewide interrogatory cap. | CONFIRMED | Keep `resolve_rog_limit(wa_state) = None`; county overlays handle local caps. |
| 2 | King LCR 26 caps interrogatories at 40 without pattern interrogatories. | CONFIRMED | Keep/wire King ROG cap. Clarify that pattern scenario is pattern set plus 15, not 40 plus 15. |
| 3 | Pierce PCLR 3(h) caps ROGs at 25/35/35/100 by track. | CONFIRMED | Keep/wire track-aware Pierce ROG cap, including Dissolution 100. |
| 4 | CA CCP Sec. 2033.280 is the no-response deemed-admission statute. | CONFIRMED | Use Sec. 2033.280 for no-response deemed admissions; Sec. 2033.290 is further responses. |
| 5 | CA CCP Sec. 2023.050 sanction is $1,000 as of Jan. 1, 2024. | CONFIRMED | Keep CA pack correction. |
| 6 | Evid. Code Sec. 801.1 is operative Jan. 1, 2024 and covers medical-causation symmetry. | CONFIRMED with nuance | Attribute origin to SB 652 and current scoped text to SB 135 amendment. |
| 7 | Sargon is 55 Cal.4th 747 (2012). | CONFIRMED | Keep anti-conflation note; do not cite 53 Cal.4th 1210. |
| 8 | People v. Sanchez is 63 Cal.4th 665 (2016). | CONFIRMED | Keep anti-conflation note; do not conflate with Sanchez v. Hillerich & Bradsby. |
| 9 | Pierce local civil rule abbreviation is PCLR, not PCLCR. | CONFIRMED | Keep PCLR/PCLGR naming. |
| 10 | King uses word limits; Pierce uses page limits. | CONFIRMED | Keep King LCR 7 word limits and Pierce PCLR 7 page limits. |
| 11 | FRCP 36 has no numerical RFA cap. | CONFIRMED | `resolve_rfa_limit(federal) = None` remains correct. |
| 12 | FRCP 34 has no numerical RFP cap. | CONFIRMED | `resolve_rfp_limit(federal) = None` remains correct. |
| 13 | King LCR 26(b)(2)(4) caps RFAs at 25, excluding authenticity RFAs. | CONFIRMED | Merge-time required resolver/checker wiring. Do not count authenticity RFAs toward 25. |

Roll-up: 13 of 13 cross-claims confirmed. Zero refuted. Zero split.

## Corrections and Merge-Time Requirements

### C1 - King County RFA cap

Confirmed. During the coordinated merge, wire `wa_king_county` into
`resolve_rfa_limit` as `25`, but ensure the audit/outgoing checkers exempt RFAs
propounded solely to authenticate documents from the count. A flat "total RFAs
over 25" check would be wrong.

### C2 - San Bernardino eFiling source precision

Confirmed. Rule 1810.B establishes mandatory eFiling/service for designated
cases, but the September 2, 2025 General Civil implementation detail is sourced
to the San Bernardino civil eFiling requirements page. Pack text should cite the
implementation page for that date.

### C3 - San Bernardino discovery-code phrasing

Confirmed as a phrasing issue. Use the narrow statement: no stand-alone civil
local discovery chapter/rule series was identified in the July 1, 2026 SBSC
civil local rules. Avoid broader claims that San Bernardino has no
discovery-related local provisions anywhere.

### C4 - King LCR 33 pattern interrogatory precision

Confirmed as partial but usable. Current LCR 33 has reserved subsection (a), and
subsections (b)/(c) govern use and format. King official forms pages confirm an
approved automobile-tort pattern-interrogatory set located through KCBA. Merge
text can say King has an approved automobile-tort pattern set and LCR 33
governs pattern-interrogatory use/format. It should not claim multiple named
pattern sets unless those names are separately verified.

### C5 - Case-law source posture

Confirmed. The expert taxonomy cites are correct, but the source posture should
stay honest: some older case text was verified through reliable public mirrors
or court-resource mirrors rather than modern official case portals. That does
not change the citation result.

## Source Packet

### California

- California Legislative Information, CCP Sec. 2030.030:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2030.030.
- California Legislative Information, CCP Sec. 2023.050:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2023.050.
- California Legislative Information, CCP Sec. 2033.280:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.280.
- California Legislative Information, CCP Sec. 2033.290:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.290.
- California Legislative Information, CCP Sec. 2031.240:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2031.240.
- California Legislative Information, CCP Sec. 2031.210:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2031.210.
- California Legislative Information, CCP Sec. 2016.040:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2016.040.
- California Legislative Information, CCP Sec. 2023.010:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2023.010.
- California Legislative Information, CCP Sec. 2030.020:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2030.020.
- California Legislative Information, CCP Sec. 2031.020:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2031.020.
- California Legislative Information, CCP Sec. 2033.020:
  https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.020.
- California Legislative Information, Evidence Code group including Sec. 801.1:
  https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?article=1.&chapter=1.&division=7.&lawCode=EVID&part=&title=
- SB 235:
  https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB235
- AB 1521:
  https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260AB1521
- SB 652:
  https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB652
- SB 135:
  https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB135

### Washington Statewide

- CR 26:
  https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_26_00_00.pdf
- CR 33:
  https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_33_00_00.pdf
- CR 34:
  https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_34_00_00.pdf
- CR 36:
  https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_36_00_00.pdf
- ER 702:
  https://www.courts.wa.gov/court_rules/pdf/ER/GA_ER_07_02_00.pdf
- ER 703:
  https://www.courts.wa.gov/court_rules/pdf/ER/GA_ER_07_03_00.pdf
- Washington ER index:
  https://www.courts.wa.gov/court_rules/?fa=court_rules.list&group=ga&set=ER

### San Bernardino

- Local rules PDF:
  https://sanbernardino.courts.ca.gov/system/files/local-rules/rulesofcourt.pdf
- Civil eFiling requirements:
  https://sanbernardino.courts.ca.gov/online-services/efiling/civil-efiling/civil-efiling-requirements
- Civil eFiling FAQ:
  https://sanbernardino.courts.ca.gov/online-services/efiling/civil-efiling/civil-efiling-faq
- eFiling page:
  https://sanbernardino.courts.ca.gov/online-services/efiling
- CRC 3.20:
  https://courts.ca.gov/cms/rules/index/three/rule3_20

### King County

- LCR 26:
  https://kingcounty.gov/en/dept/dja/courts-jails-legal-system/superior-court-local-rules/local-civil-rules/lcr-26
- LCR 7:
  https://kingcounty.gov/en/dept/dja/courts-jails-legal-system/superior-court-local-rules/local-civil-rules/lcr-7
- LCR 33:
  https://kingcounty.gov/en/dept/dja/courts-jails-legal-system/superior-court-local-rules/local-civil-rules/lcr-33
- Current local rules PDF:
  https://cdn.kingcounty.gov/-/media/king-county/depts/dja/local-rules/2025-kc-superior-court-local-rules.pdf?hash=85BD23E05FADCA06CD03343F609DB396&rev=f1b0abeb39314b659efe6beec9ed982b
- Civil forms:
  https://kingcounty.gov/en/court/superior-court/courts-jails-legal-system/civil/forms
- Local rules comment period:
  https://kingcounty.gov/en/dept/dja/courts-jails-legal-system/superior-court-local-rules/local-rules-comment-period
- 2026 proposed amendments:
  https://cdn.kingcounty.gov/-/media/king-county/depts/dja/local-rules/2026-lrc-proposed-amendments.pdf?hash=F8098F83B4246011DBFC9296E33100E8&rev=9f088ef125394d5b97039dd1e75de7fe

### Pierce County

- Local rules page:
  https://www.piercecountywa.gov/1195/Local-Rules
- 2025 local rules PDF:
  https://www.piercecountywa.gov/DocumentCenter/View/150861/2025-Local-Rules---Pierce-County
- 2026 proposed PCLR 3:
  https://www.piercecountywa.gov/DocumentCenter/View/156931/Amended-PCLR-3-Commencement-of-Action---Case-Schedule-2026
- 2026 proposed PCLR 7:
  https://www.piercecountywa.gov/DocumentCenter/View/156933/Amended-PCLR-7-Motions-Judges-and-Commissioners-2026
- 2026 proposed PCLR 16:
  https://www.piercecountywa.gov/DocumentCenter/View/156935/Amended-PCLR-16-Pretrial-and-settlement-Procedures-2026
- PCLGR 30 public request:
  https://www.piercecountywa.gov/DocumentCenter/View/157484/Request-to-Update-PCLGR-30---Fields

### Expert And Federal Sources

- Sargon v. University of Southern California, 55 Cal.4th 747:
  https://scocal.stanford.edu/opinion/sargon-v-univ-southern-cal-34179
- People v. Sanchez, 63 Cal.4th 665:
  https://law.justia.com/cases/california/supreme-court/2016/s216681.html
- People v. Kelly, 17 Cal.3d 24:
  https://scocal.stanford.edu/opinion/people-v-kelly-23058
- State v. Copeland, 130 Wn.2d 244, 922 P.2d 1304:
  https://law.justia.com/cases/washington/supreme-court/1996/62417-8-1.html
- Frye v. United States, 293 F. 1013:
  https://law.justia.com/cases/district-of-columbia/court-of-appeals/1923/no-3968.html
- Daubert v. Merrell Dow Pharmaceuticals, Inc., 509 U.S. 579:
  https://supreme.justia.com/cases/federal/us/509/579/
- U.S. Courts, Federal Rules of Civil Procedure:
  https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/federal-rules-civil-procedure
- U.S. Courts, Federal Rules of Evidence:
  https://www.uscourts.gov/forms-rules/current-rules-practice-procedure/federal-rules-evidence
- LII, FRE 702 readable rule text:
  https://www.law.cornell.edu/rules/fre/rule_702
- LII, FRCP 34 readable rule text:
  https://www.law.cornell.edu/rules/frcp/rule_34
- LII, FRCP 36 readable rule text:
  https://www.law.cornell.edu/rules/frcp/rule_36

## Integration Readiness

Ready to reconcile, subject to the existing preconditions:

1. Clean or preserve Codex's uncommitted primary-checkout work before any edit to
   `main`.
2. Execute `MERGE_PLAN.md` in order.
3. Treat C1 through C4 above as merge-time requirements, not later follow-ups.
4. Re-run the full legal test selection after integration and `git diff --check`.
5. Keep live use gated by owner section 9.5 per matter, request type, mode, and
   slice, plus attorney review for any flagged legal reliance.

## Done Decision

**Passed with exceptions.** The branch's self-verification is corroborated on
the merits. No `SPLIT` requiring human legal-source adjudication was found. The
exceptions should be incorporated during merge so they do not drift into later
cleanup.
