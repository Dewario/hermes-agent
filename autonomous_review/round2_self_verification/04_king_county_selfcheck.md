# 04 — King County Superior Court local rules self-check (Hermes Round 2)

**Source:** King County Superior Court local civil rules (kingcounty.gov official LCR 7 + LCR 26 pages).
**Access date:** 2026-07-20
**Method:** direct fetch of the official LCR 26 and LCR 7 pages (kingcounty.gov is static HTML, fully returned).

## Verdicts

| Item | Claim | Verdict | Notes |
|---|---|---|---|
| LCR 26(b)(2)(B) | 40 interrogatory cap (including discrete subparts) | CONFIRMED | Official LCR 26: "(B) Cases Without Court-Approved Pattern Interrogatories. In cases where a party has not propounded pattern interrogatories pursuant to LCR 33, a party may serve no more than 40 interrogatories, including all discrete subparts." ✓ |
| LCR 26(b)(2)(A) | +15 additional with court-approved pattern | CONFIRMED | Official LCR 26: "(A) Cases With Court-Approved Pattern Interrogatories. In cases where a party has propounded pattern interrogatories pursuant to LCR 33, a party may serve no more than 15 interrogatories, including all discrete subparts, in addition to the pattern interrogatories." ✓ |
| LCR 7(b)(6)(vi) | 4,200-word initial/opposition; 1,750-word reply; 9 judicial days | CONFIRMED | Official LCR 7: "(vi) Word Limits... the initial motion and opposing memorandum shall not exceed 4,200 words; and reply memoranda shall not exceed 1,750 words." Excludes caption, TOC/authorities, signature block; signature block must certify word count. "(A) ... no later than 4:30 p.m. nine judicial days before the date the party wishes the motion to be considered." Reply: "no later than 4:30 p.m. two judicial days before the hearing." ✓ |
| LCR 33 | court-approved pattern-interrogatory set | CONFIRMED (rule structure); **overclaim corrected 2026-07-20** | LCR 26 references "pattern interrogatories pursuant to LCR 33". **Correction (Codex round-2 C4, verified):** the LCR 33 rule page itself shows subsection (a) as "(Reserved)" — the court "will adopt a process for approving Pattern Interrogatories"; (b)/(c) govern use/format. Named pattern sets live on KCSC forms pages, not the rule text. The earlier note here ("pattern sets exist for personal injury, motor vehicle, and general civil") was **not supported by the cited source** and is withdrawn. Verified: King has an approved automobile-tort pattern set (per KCSC forms); broader named sets need separate sourcing. See `ROUND2_RECONCILIATION.md` C4. ✓ |

## NEW FINDING — King County RFA cap = 25 (resolver gap)

**The official King County LCR 26 page states, verbatim:**

> "(4) Requests for Admission. A party may serve no more than 25 requests for admission upon any other party in addition to requests for admission propounded to authenticate documents."

So **King County caps RFAs at 25 per party** (excluding RFAs propounded solely to authenticate documents). This is a real, official-source-confirmed local RFA cap.

**Current resolver behavior:** `resolve_rfa_limit` in `jurisdiction/limits.py` returns `None` for the entire WA family (including `wa_king_county`). The resolver's own comment (lines 88-94) explicitly says: "King LCR 26 references local RFA caps but the specific number is not confirmed in the citation-verification reports, so the resolver returns None there (attorney must supply via override)." The number was left unconfirmed at round-1 time.

**Round-2 has now confirmed it: 25.** This is an actionable correction:
- `resolve_rfa_limit` should return `25` for `wa_king_county` overlay (with the genuineness-authentication exclusion noted in the docstring), falling back to `None` only for `wa_state` base / `wa_pierce_county` (Pierce expressly has no RFA cap per PCLR 3(h)).
- The handoff Cluster 4 listed only the 40 interrogatory cap as a verification target; it should also have listed the LCR 26(b)(2)(4) 25-RFA cap. The handoff is incomplete on this point.

**Severity:** Medium. The resolver is not wrong (it defers to attorney override), but it is now unnecessarily conservative — the number is confirmed and can be wired in. A plaintiff propounding >25 RFAs in King County would currently get no automated flag.

**Disposition:** recorded as a correction; NOT auto-applied during the verification pass (per the round-2 "report, don't auto-apply" discipline). To be folded in during the merge or as a follow-up commit. See `CORRECTIONS_NEEDED.md`.

## Bonus findings (official LCR 26, not in handoff but useful for plaintiff-side)

- **LCR 26(b)(2)(3) Depositions:** "A party may take no more than 10 depositions, with each deposition limited to one day of seven hours; provided, that each party may conduct one deposition that shall be limited to two days and seven hours per day." (Plaintiff-side cap to plan around.)
- **LCR 26(b)(2)(5) Modification:** limits may be increased/decreased by written stipulation or by court order (LCR 7(b) motion) — the stipulation path is the cheap way to exceed 40/25 for plaintiff work.
- **LCR 26(b)(2)(6) Over-limit requests need not be answered:** "the party served with interrogatories or requests for admission in violation of this rule shall be required to respond only to those requests, in numerical order, that comply with LCR 26(b). No motion for protective order is required." (Useful: defense over-service is self-limiting; plaintiff need only answer the compliant ones in numerical order.)
- **LCR 26(b)(2)(7) Applicability:** these limits do NOT apply to family law (LFLR 1) or post-judgment/supplemental proceedings (LCR 69(b)).

## Cross-claim implications (Axis 2)

- Claim 2 (King LCR 26 caps interrogatories at 40): **CONFIRMED.**
- Claim 10 (King uses word-limits 4,200/1,750): **CONFIRMED.**
- **NEW:** King also caps RFAs at 25 (LCR 26(b)(2)(4)) — not currently in the resolver; recorded as a correction.
