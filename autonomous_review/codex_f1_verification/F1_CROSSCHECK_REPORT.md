# Codex F1 Cross-Check Report

Date: 2026-07-22
Branch: `legal-enforcement-levers`
Scope: F1 plaintiff enforcement-lever slice after `742375fb8`, with
cross-check follow-up fixes applied before merge.

## Headline

**PASS after fixes.** The independent Codex cross-check confirmed the original
F1-W1, F1-W2, and F1-CA1 fixes, then found two additional implementation /
source-precision issues. Those follow-up issues are now fixed on this branch:

- **F1-W3:** WA RFA motion-to-compel primary authority now selects CR 36(a),
  with CR 37(a)(4) supporting expenses; CR 37(a) remains ROG/RFP-only.
- **F1-T1:** F1 reference templates now mirror the table-based generated
  scaffold contract, and tests lock that contract.

No live `C:\Matters\<client>` path was touched. No owner sec. 9.5 checkbox or
signature was filled.

## Source Packet

| Cluster | Source | Cross-check result |
|---|---|---|
| CA deemed-admitted | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.280. | CONFIRMED: no timely RFA response supports a deemed-admitted motion and mandatory monetary sanctions. |
| CA ROG further responses | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2030.300. | CONFIRMED: ROG further-response motion, 2016.040 declaration, sanctions framework. |
| CA RFP further responses | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2031.310. | CONFIRMED: RFP further-response motion, good cause, 2016.040 declaration, sanctions framework. |
| CA RFA further responses | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.290. | CONFIRMED: RFA further-response motion, 2016.040 declaration, sanctions framework. |
| CA meet-and-confer | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2016.040. | CONFIRMED: declaration must show reasonable good-faith effort; AB 1521 amendment effective Jan. 1, 2026. |
| CA misuse definitions | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2023.010. | CONFIRMED: includes failure to respond, evasive responses, unsuccessful unjustified motions, and failure to confer; AB 1521 effective Jan. 1, 2026. |
| CA $1,000 sanctions | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2023.050. | CONFIRMED: mandatory $1,000 structure when statutory findings are made, subject to written findings of substantial justification / unjust circumstances. |
| WA CR 26(i) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_26_00_00.pdf | CONFIRMED: court will not entertain motions/objections under CR 26-37 without counsel conference and certification. |
| WA CR 36(a)/(b) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_36_00_00.pdf | CONFIRMED: unanswered RFAs are admitted unless timely answered or objected to; admitted matters are conclusive absent withdrawal/amendment. |
| WA CR 37(a)/(a)(4)/(c) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_37_00_00.pdf | CONFIRMED: CR 37(a) covers ROG/RFP motion-to-compel posture; CR 37(a)(4) covers motion expenses; CR 37(c) is the distinct failure-to-admit proof-expense rule. |

## Defect Verdicts

| Finding | Verdict | Implementation check |
|---|---|---|
| F1-W1 WA deemed-admission refusal | FIXED | `select_statute()` returns `WA-CR-36-A` + `WA-CR-36-B` for WA RFA deemed-admitted; WA pack carries CR 36(a)/(b); tests assert the path. |
| F1-W2 WA CR 37(c) mismatch | FIXED | WA sanctions authority is `WA-CR-37-A-4`; generated scaffolds cite CR 37(a)(4); only historical / negative-guard `WA-CR-37-C` references remain. |
| F1-CA1 CA sanctions hedge | FIXED | Live prose and sanctions template state the mandatory $1,000 structure subject to statutory exceptions. |
| F1-W3 WA RFA motion primary | FIXED | WA `motion_to_compel` selects CR 37(a) for ROG/RFP and CR 36(a) + CR 37(a)(4) for RFA. |
| F1-T1 template/table contract | FIXED | Enforcement templates use the same metadata/supporting-authority table shape emitted by `enforcement_motion.py`; tests assert no stale bold metadata or caption section. |

## Cross-Claim Verdicts

| # | Premise | Verdict |
|---|---|---|
| 1 | CA `deemed_admitted` is RFA-only and cites CCP sec. 2033.280; ROG/RFP refused. | CONFIRMED |
| 2 | WA has a self-executing CR 36(a) RFA admission posture, not CA's motion-plus-mandatory-sanction mechanism. | CONFIRMED |
| 3 | CA `motion_to_compel` selects CCP secs. 2030.300 / 2031.310 / 2033.290 by request type. | CONFIRMED |
| 4 | WA `motion_to_compel` selects CR 37(a) for ROG/RFP and CR 36(a) for RFA sufficiency / no-response motions. | CONFIRMED |
| 5 | CA `meet_and_confer_letter` cites CCP sec. 2016.040; WA cites CR 26(i). | CONFIRMED |
| 6 | CA `sanctions` cites CCP sec. 2023.050 with sec. 2023.010 supporting; WA `sanctions` cites CR 37(a)(4). | CONFIRMED |
| 7 | CCP sec. 2023.050's $1,000 figure and exception posture are current as of 2026-07-22. | CONFIRMED |
| 8 | AB 1521 amendments to CCP secs. 2016.040 and 2023.010 are effective Jan. 1, 2026 and in force as of 2026-07-22. | CONFIRMED |
| 9 | F1 scaffolds do not sign owner gates or pre-check sec. 9.5 boxes. | CONFIRMED |
| 10 | F1 scaffold metadata and supporting authority render as markdown tables for isolation stability. | CONFIRMED |
| 11 | King 25-RFA cap is outside F1 and was not rewired. | CONFIRMED |
| 12 | F1 tests and selftests use synthetic paths; no live client path is touched. | CONFIRMED |

Roll-up: **12/12 cross-claims confirmed, zero SPLIT, zero NOT FIXED after the
cross-check follow-up patch.**

## Verification

- `python -m py_compile skills\legal\discovery-workflow\scripts\enforcement_motion.py`
- `python -m pytest -q --basetemp .pytest_tmp tests\skills\test_discovery_enforcement_motion.py` -> `17 passed`
- Broad legal/discovery suite -> `200 passed`

Note: the broad run used global `python -m pytest --basetemp .pytest_tmp`
because local temp defaults remain permission-sensitive on this Windows host.
