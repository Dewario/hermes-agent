# F1 Authority Fix Verification

Branch: `legal-enforcement-levers`
Date: 2026-07-22

Purpose: record the post-fix verification target for the F1-W1, F1-W2, and
F1-CA1 corrections. This supplements the original F1 verification report
without deleting the historical defect record.

## Source Packet

| Issue | Primary source | Verification use |
|---|---|---|
| F1-W1 | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_36_00_00.pdf | CR 36(a) admits an unanswered RFA unless a timely answer or objection is served; CR 36(b) supplies conclusive effect unless withdrawal or amendment is allowed. |
| F1-W2 | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_37_00_00.pdf | CR 37(a)(4) is the motion-to-compel expense rule; CR 37(c) is the distinct expenses-on-failure-to-admit rule. |
| F1-CA1 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2023.050. | CCP sec. 2023.050 requires a $1,000 sanction when statutory findings are made, subject to the statutory substantial-justification / unjust-circumstances exception. |

## Expected Corrected Behavior

| Check | Expected result |
|---|---|
| `select_statute("deemed_admitted", "rfa", wa_state rules)` | Primary `WA-CR-36-A`; supporting `WA-CR-36-B`; no refusal. |
| WA deemed-admitted scaffold | Drafts and validates for RFA; cites `Wash. Super. Ct. Civ. R. 36(a)`; supporting table includes `WA-CR-36-B`. |
| `WA-CR-37-A` summary | No statement that Washington lacks a no-response deemed-admission parallel; points RFA no-response admissions to CR 36(a). |
| WA sanctions authority | Primary `WA-CR-37-A-4`; generated scaffold cites `Wash. Super. Ct. Civ. R. 37(a)(4)`. |
| CA sanctions prose | Does not use "up to $1,000" / "may be imposed" framing; states the mandatory $1,000 structure subject to statutory exceptions. |

## Live Boundary

This verification remains synthetic / engineering-only. No live
`C:\Matters\<client>` paths are touched, and no owner sec. 9.5 checkbox or
signature is filled by engineering.
