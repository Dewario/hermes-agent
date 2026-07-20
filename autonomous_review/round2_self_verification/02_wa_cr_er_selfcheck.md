# 02 — WA CR + ER self-check (Hermes Round 2)

**Source:** Washington State Courts (courts.wa.gov) official rule PDFs + WSBA clean-copy CR 26 + corroboration.
**Access date:** 2026-07-20
**Method:** official CR 33 / CR 26 PDF text via WebSearch extraction; WSBA CR 26 clean copy; secondary corroboration for CR 34/36.

## Verdicts

| Cite | Claim | Verdict | Notes |
|---|---|---|---|
| CR 26(b)(1) | scope is "relevant to the subject matter"; does NOT adopt the federal 2015 "proportional to the needs" language | CONFIRMED | Official CR 26 PDF: "(1) In General. Parties may obtain discovery regarding any matter, not privileged, which is relevant to the subject matter involved in the pending action..." — this is the pre-2015 federal phrasing. The federal "proportional to the needs of the case" sentence (FRCP 26(b)(1), eff. Dec 1 2015) is absent. **Nuance:** CR 26(b)(1) DOES have a factor-based limitation in the "frequency or extent" paragraph — "unduly burdensome or expensive, taking into account the needs of the case, the amount in controversy, limitations on the parties, resources, and the importance of the issues" — which is functionally proportionality-adjacent, but it is a court-limitation mechanism, not part of the scope sentence. The handoff claim (no federal 2015 proportionality language in the scope sentence) holds. |
| CR 26(i) | mandatory pre-motion meet-and-confer + certification (not CR 26(f), which is discretionary) | CONFIRMED | Official CR 26 PDF + WSBA clean copy: "(i) Motions; Conference of Counsel Required. The court will not entertain any motion or objection with respect to rules 26 through 37 unless counsel have conferred... Any motion seeking an order to compel discovery or obtain protection shall include counsel's certification that the conference requirements of this rule have been met." Case law: "mandatory" and "literal compliance required" (Case v. Dundom, 115 Wn.App. 199 (2002); Rudolph v. Empirical Research Sys., 107 Wn.App. 861 (2001)). CR 26(f) is the court-ordered discovery conference ("the court may direct") — discretionary. The (i) vs (f) distinction in the handoff is correct. |
| CR 33 | NO statewide numerical interrogatory cap | CONFIRMED | Official CR 33 PDF text contains no numerical limit — only availability, scope (incorporates CR 26(b)), and the 30/40-day response timing. The "40 per party" cap that appears in some secondary sources is actually **King County LCR 26(b)(2)(A)**, not statewide CR 33. See **secondary-source trap** below. |
| CR 34 | no statewide numerical RFP cap | CONFIRMED (by inference) | Not independently PDF-fetched. Inference basis: (a) CR 33 official text has no cap; (b) Genesis Law Firm states the statewide default is "no limitations unless the county's local rules say otherwise"; (c) the resolver returns None for RFP in every jurisdiction. Mark for independent confirmation if a RFP-cap question ever arises, but no evidence of a statewide CR 34 cap exists. |
| CR 36 | no statewide numerical RFA cap | CONFIRMED (by inference) | Same inference basis as CR 34. The resolver returns None for RFA in wa_state. No evidence of a statewide CR 36 cap. |
| ER 702 / ER 703 | rule text governs expert admissibility; no "ERI" rule | CONFIRMED | ER 702 text (via Cundy v. BNSF, No. 40095-6-III, filed Mar 5 2026): "If scientific, technical, or other specialized knowledge will assist the trier of fact... a witness qualified as an expert by knowledge, skill, experience, training, or education, may testify thereto in the form of an opinion or otherwise." ER 703 governs reliability of underlying methods. Expert Institute synthesis: "There is no nonexistent rule" — i.e., "ERI" is not a Washington evidence rule. The fictitious "ERI" label that had crept into an earlier taxonomy is correctly absent from current skill files. |
| Frye (State v. Copeland) | WA retained Frye for novel scientific evidence | CONFIRMED | Cundy v. BNSF (Mar 5 2026): "novel scientific evidence must satisfy both Frye and ER 702"; where methodology is long-accepted and not novel, Frye does not apply and ER 702 alone governs. This corroborates the expert_standards citation report's reference to a March 5 2026 opinion. |

## Secondary-source trap (important)

A secondary source (`washingtonlegalservicesauthority.com`) states: "Interrogatories are capped at 40 per party under CR 33 unless the court permits more." **This is incorrect.** The 40-per-party cap is **King County LCR 26(b)(2)(A)** (per `smartrules.com` and `genesislawfirm.com`: "King County limits the number of interrogatories; Snohomish County does not. You can assume there are no limitations unless the county's local rules say otherwise."). The official statewide CR 33 PDF contains no numerical cap.

**Implication for the resolver:** `resolve_rog_limit(wa_state) → None` (statewide, no cap) and `resolve_rog_limit(wa_king_county) → 40` (local cap) are both **correct**. A naive verifier relying on the secondary source would wrongly conclude CR 33 caps at 40 statewide and break the WA-state resolver. This is exactly the kind of secondary-source error the round-2 source-bounded verification is meant to catch.

## Cross-claim implications (Axis 2)

- Claim 1 (WA CR 33 has NO statewide interrogatory cap → resolve_rog_limit(wa_state) = None): **CONFIRMED.**
- Claim 2 (King LCR 26 caps interrogatories at 40): to be confirmed in the King County cluster (04), but the secondary-source evidence here already points to LCR 26(b)(2)(A) as the 40-cap source.
- Claim 11/12 (FRCP 36 / FRCP 34 no cap): federal, not WA; covered in the expert/federal notes. WA CR 34/36 have no statewide cap (inference above).
