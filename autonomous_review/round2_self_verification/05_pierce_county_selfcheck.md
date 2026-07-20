# 05 — Pierce County Superior Court local rules self-check (Hermes Round 2)

**Source:** Pierce County Superior Court local rules (courts.wa.gov official PDF + piercecountywa.gov official PCLR 3, PCLR 7, E-Filing pages).
**Access date:** 2026-07-20
**Method:** official Pierce County rule PDF + official county pages (PCLR 3, PCLR 7, E-Filing). Full PDF body fetched to local file; key subsections confirmed via official page extracts.

## Verdicts

| Item | Claim | Verdict | Notes |
|---|---|---|---|
| PCLR 3(h)(1) Expedited | 25 interrogatories; subparts count separately; no RFA limit | CONFIRMED | Official PCLR 3(h)(1): "Interrogatories shall be limited to twenty-five (25) in number and each subpart of an interrogatory shall be counted as a separate interrogatory... There shall be no limit on requests for admissions." Discovery cutoff 20 weeks, trial 26 weeks. ✓ |
| PCLR 3(h)(2) Standard | 35 interrogatories; subparts count separately; no RFA limit | CONFIRMED | Official PCLR 3(h)(2): "Interrogatories shall be limited to thirty-five (35) in number and each subpart... counted as a separate interrogatory... There shall be no limit on requests for admissions." Personal injury / breach of contract / title to land / construction / discrimination presumptively standard. ✓ |
| PCLR 3(h)(3) Complex | 35 interrogatories; subparts count separately; no RFA limit | CONFIRMED | Official PCLR 3(h)(3): 35 interrogatories; "There shall be no limit on requests for admission." Medical/professional malpractice, product liability, class action presumptively complex. ✓ |
| PCLR 3(h)(4) Dissolution | 100 interrogatories; subparts count separately; no RFA limit | CONFIRMED | Official PCLR 3(h)(4): "Interrogatories shall be limited to one hundred (100) in number and each subpart... counted as a separate interrogatory... There shall be no limit on requests for admissions." Dissolution presumptively family-law track at filing; moves to dissolution track if not resolved within 122 days. **The Dissolution 100 cap — the most commonly missed — is confirmed.** ✓ |
| PCLR 7(a)(8) page limits | 12-page initial/opposition; 5-page reply | CONFIRMED | Official PCLR 7(a)(8): "The initial motion and opposing memorandum shall not exceed twelve (12) pages... reply memoranda shall not exceed five (5) pages without authorization of the court." **Bonus:** MSJ under CR 56 is 24 pages initial/opposition, 12 pages reply (not in handoff). ✓ |
| PCLR 7(a)(1) when heard | Friday 9:00 a.m.; assigned judicial department only | CONFIRMED | Official PCLR 7(a)(1): "Motions are heard on Friday mornings at 9:00 a.m., unless specially set by the assigned judicial department." "All contested motions to change venue and all discovery motions shall be heard before the assigned judicial department." If Friday is a non-judicial day, heard on the judicial day immediately preceding. ✓ |
| PCLR 7(a) timing | 7 court days (moving party) | PARTIAL | Opposition: "12:00 noon three (3) court days before" (a)(5); reply: "12:00 noon two (2) court days before" (a)(6) — both CONFIRMED. The moving party's filing deadline (the "7 court days" figure in the handoff) was not in the fetched PCLR 7 snippet; it likely sits in PCLR 7(a)(3)-(4). Mark for full-section confirmation. |
| LINX e-filing | e-filing via LINX (not Odyssey) | CONFIRMED | Official Pierce County E-Filing page: "A FREE LINX account is required in order to access electronic services (including e-filing, e-service...)"; login at linxonline.co.pierce.wa.us. Pierce uses LINX, distinct from San Bernardino's Odyssey eFileCA. ✓ |
| "PCLR" abbreviation | Pierce County Local Rule = "PCLR" (not "PCLCR") | CONFIRMED | All official Pierce County references use "PCLR" (PCLR 3, PCLR 7, PCLR 40, etc.) and "PCLGR" for general rules. No "PCLCR" appears. ✓ |
| PCLR 16 | pretrial / Joint Statement of Evidence | PARTIAL | "Joint Statement of Evidence" is confirmed to exist in the Pierce rules — referenced in PCLR 3(g)(2) and PCLR 40(e)(4) (which list "Joint Statement of Evidence, Pretrial Conference, and Trial date"). The specific PCLR 16 section text was not in the fetched snippet; mark for full-section confirmation. |

## Findings

- **No drift on the load-bearing caps.** PCLR 3(h) track caps 25/35/35/100 are all confirmed verbatim from the official Pierce County PDF, including the Dissolution 100 cap (Axis 2 claim 3). Subparts-count-separately is explicit on every track.
- **Pierce expressly has NO RFA cap on any track.** Each PCLR 3(h) subdivision states "There shall be no limit on requests for admissions." This confirms `resolve_rfa_limit` returning None for `wa_pierce_county` is correct, and confirms the King County RFA=25 finding (Cluster 4) is King-specific, not a WA-wide rule. The two counties genuinely diverge on RFAs: King caps at 25, Pierce caps at none.
- **Pierce uses page-limits (12/5; 24/12 for MSJ); King uses word-limits (4,200/1,750).** Axis 2 claim 10 confirmed. The word-vs-page contrast is real and jurisdiction-specific.
- **LINX vs Odyssey:** Pierce = LINX; San Bernardino = Odyssey eFileCA. The e-filing vendor divergence is confirmed.
- **Two PARTIAL items** (PCLR 7 moving-party filing deadline "7 court days"; PCLR 16 section text) — the existence/structure is confirmed but the exact subsection text wasn't in the fetched snippets. Both are non-load-bearing for the resolvers; mark for full-section confirmation if needed.

## Cross-claim implications (Axis 2)

- Claim 3 (Pierce PCLR 3(h) caps = 25/35/35/100 by track; Dissolution 100 the hardest): **CONFIRMED.**
- Claim 9 (Pierce cite abbreviation = "PCLR" not "PCLCR"): **CONFIRMED.**
- Claim 10 (King word-limits vs Pierce page-limits): **CONFIRMED.**
- **Corroboration:** Pierce's express "no limit on requests for admissions" on every track confirms `resolve_rfa_limit(wa_pierce_county) = None` is correct, and isolates the King RFA=25 finding to King County alone.
