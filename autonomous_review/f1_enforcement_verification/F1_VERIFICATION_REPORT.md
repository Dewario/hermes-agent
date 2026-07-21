# F1 Enforcement-Lever Verification Report

Branch: `legal-enforcement-levers` (HEAD `185c5b73a`)
Date: 2026-07-20
Verifier: Hermes (autonomous worktree)
Scope: independent verification of the F1 plaintiff enforcement-lever authorities against primary sources, focused on citation accuracy and currentness. No live matter use; synthetic only.

## Method

Each F1 authority was checked against a primary or official source (California Legislative Information for CA CCP; Washington courts.wa.gov rule PDFs for WA CR). Currentness-sensitive amendment claims (SB 235, AB 1521) were checked against the bill history and the "Amended by" line on the code section. WA deemed-admission posture was checked against the CR 36 text plus secondary corroboration.

## F1 authority inventory

The F1 scaffolder (`skills/legal/discovery-workflow/scripts/enforcement_motion.py`) selects a primary statute per lever from the loaded jurisdiction pack. The four levers and their selectable authorities:

| Lever | CA primary | WA primary (current) | WA primary (should be) |
|---|---|---|---|
| `deemed_admitted` | CCP-2033-280 | *refused* | WA-CR-36-A (defect F1-W1) |
| `motion_to_compel` | CCP-2030-300 / CCP-2031-310 / CCP-2033-290 | WA-CR-37-A | WA-CR-37-A (ok) |
| `meet_and_confer_letter` | CCP-2016-040 | WA-CR-26-I | WA-CR-26-I (ok) |
| `sanctions` | CCP-2023-050 (+ CCP-2023-010) | WA-CR-37-C | WA-CR-37-A-4 (defect F1-W2) |

## Cluster results

### Cluster 1 - CA deemed-admitted (CCP 2033.280)

CONFIRMED against leginfo. "If a party to whom requests for admission are directed fails to serve a timely response... (a) waives any objection... (b) The requesting party may move for an order that the genuineness of any documents and the truth of any matters... be deemed admitted, as well as for a monetary sanction... (c) The court shall make this order... It is mandatory that the court impose a monetary sanction." Pack summary matches. Distinction from 2033.290 (further-response motion) is correct.

Source: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.280.

### Cluster 2 - CA motion to compel further responses (CCP 2030.300 / 2031.310 / 2033.290)

CONFIRMED against leginfo for 2030.300 and 2031.310 (freshly fetched); 2033.290 confirmed in prior round and pack citation matches the leginfo URL pattern.

- 2030.300(a): move to compel further ROG response when answer is "evasive or incomplete" or objection is "without merit or too general"; (b)(1) requires a 2016.040 meet-and-confer declaration. Pack summary matches. Distinction from 2030.290 (no-timely-response) is correct.
- 2031.310(a): move to compel further inspection-demand response when "statement of compliance... is incomplete", inability-to-comply representation is "inadequate, incomplete, or evasive", or objection is "without merit or too general"; (b)(2) requires a 2016.040 declaration. Pack summary matches. Distinction from 2031.320 is correct.

Sources:
- https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2030.300.
- https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2031.310.

### Cluster 3 - CA meet-and-confer (CCP 2016.040) and misuse definitions (CCP 2023.010) - AB 1521 currentness

CONFIRMED against leginfo, including the AB 1521 (2025-2026) amendment effective Jan 1, 2026.

- 2016.040(a): meet-and-confer declaration "shall state facts showing a reasonable and good faith attempt, either in person, by telephone, or by videoconference, to informally resolve each issue"; (b) must address retention of a certified shorthand reporter. "Amended by Stats. 2025, Ch. 200, Sec. 12. (AB 1521) Effective January 1, 2026." Pack claim matches.
- 2023.010(i): "Failing to confer or to attempt to confer, in person, by telephone, or by videoconference..." is a listed misuse. AB 1521 amendment effective Jan 1, 2026. Pack claim matches.
- AB 1521 bill history: chaptered 10/01/25 as Chapter 200, Statutes of 2025; approved by the Governor 10/01/25; effective Jan 1, 2026.

Sources:
- https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2016.040.
- https://leginfo.legislature.ca.gov/faces/billHistoryClient.xhtml?bill_id=202520260AB1521

### Cluster 4 - CA sanctions (CCP 2023.050) - SB 235 currentness

CONFIRMED against leginfo, including the SB 235 (2023-2024) amendment effective Jan 1, 2024.

- 2023.050(a): "the court shall impose a one-thousand-dollar ($1,000) sanction, payable to the requesting party" upon the specified findings (failure to respond in good faith to a document request/inspection demand; production within 7 days of a MTC hearing; failure to meet and confer). The exception: "if the court makes written findings that the one subject to the sanction acted with substantial justification or that other circumstances make the imposition of the sanction unjust." "Amended by Stats. 2023, Ch. 284, Sec. 3. (SB 235) Effective January 1, 2024." Pack claim ("Mandatory $1,000 sanction... SB 235 increased the sanction from $250 to $1,000 effective Jan. 1, 2024") matches.
- Low prose nuance: the sanctions_block renders "A monetary sanction up to $1,000 may be imposed absent a showing of substantial justification...". The statute says "shall impose" $1,000 (mandatory, subject to the substantial-justification exception). The "up to... may be imposed" framing is a slight hedge; defensible for a draft but imprecise. See F1-CA1.

Source: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2023.050.

### Cluster 5 - WA CR 26(i) meet-and-confer certification

CONFIRMED against courts.wa.gov CR 26 PDF. "The court will not entertain any motion or objection with respect to rules 26 through 37 unless counsel have conferred... Any motion seeking an order to compel discovery or obtain protection shall include counsel's certification that the conference requirements of this rule have been met." Pack summary matches.

Source: https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_26_00_00.pdf

### Cluster 6 - WA CR 37(a) motion to compel

CONFIRMED against courts.wa.gov CR 37 PDF. "(a) A party, upon reasonable notice... and upon a showing of compliance with rule 26(i), may apply... for an order compelling discovery" covering ROG (rule 33), inspection (rule 34), and admissions. Pack summary matches the procedural text.

BUT the pack summary's closing sentence - "no separate no-response deemed-admission statute parallels CCP 2033.280 in Washington" - is FALSE. See F1-W1.

Source: https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_37_00_00.pdf

### Cluster 7 - WA sanctions / expenses (CR 37(c) vs CR 37(a)(4))

PARTIAL. The pack's `WA-CR-37-C` entry is labeled CR 37(c) but its summary tracks CR 37(a)(4) language ("if a motion to compel is granted, the court may order the failing party to pay the reasonable expenses, including attorney fees, incurred in making the motion, unless the court finds the failure was substantially justified or other circumstances make an award unjust"). CR 37(c) is actually the narrower "Expenses on Failure To Admit" (CR 36) provision with a different exception structure. See F1-W2.

Sources:
- https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_37_00_00.pdf (37(a)(4) and 37(c) text)

### Cluster 8 - WA deemed-admission posture (CR 36) - NEW FINDING

WA CR 36(a) IS a no-response deemed-admission parallel to CCP 2033.280. "The matter is admitted unless, within 30 days after service of the request... the party to whom the request is directed serves upon the party requesting the admission a written answer or objection." CR 36(b): admitted matters are "conclusively established... unless the court... permits withdrawal or amendment." This is self-executing (no motion required to deem admitted, though the requesting party may move to determine sufficiency under CR 36(a) second paragraph, with CR 37(a)(4) expenses). The F1 scaffolder's refusal of `deemed_admitted` for WA is therefore incorrect. See F1-W1.

Sources:
- https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_36_00_00.pdf
- Corroboration: Lexis practice note ("deemed admitted by failure to respond are conclusively established... Wash. CR 36(b)"); vLex ("CR 36 explicitly provides that the failure to answer or respond... automatically results in admission"); Court of Appeals opinion (Schrader, D2 54994-8-II) treating CR 36(a) deemed-admission as operative.

## Roll-up

- 8 clusters checked against primary sources.
- 6 CONFIRMED clean (CA 2033.280, CA 2030.300, CA 2031.310, CA 2016.040/2023.010 + AB 1521, CA 2023.050 + SB 235, WA CR 26(i)).
- 1 PARTIAL (WA CR 37(c) vs 37(a)(4) - F1-W2).
- 1 NEW FINDING / FALSE claim (WA CR 36(a) deemed-admission - F1-W1).
- 1 LOW prose nuance (CA 2023.050 "up to $1,000" - F1-CA1).

Currentness: SB 235 (eff. 2024-01-01) and AB 1521 (eff. 2026-01-01) both confirmed against the bill history and the "Amended by" line on the code sections. As of today (2026-07-20), AB 1521 is in effect.

See CORRECTIONS_NEEDED.md for actionable fixes.
