# Corrections needed (Hermes Round 2 self-verification)

One actionable correction found. **Elevated to merge-time (required) — not a follow-up.** Per round-2 "report, don't auto-apply" discipline, this is not auto-applied here; it is folded in during the coordinated merge (MERGE_PLAN steps 1 and 10), which already touches `resolve_rfa_limit` and pins King County specifics, so wiring the 25-RFA cap then is zero extra surface and avoids a drifting follow-up.

## C1 — King County RFA cap = 25 (resolver addition)

**Source:** Official King County LCR 26 page (kingcounty.gov), subsection (b)(2)(4), verbatim:
> "Requests for Admission. A party may serve no more than 25 requests for admission upon any other party in addition to requests for admission propounded to authenticate documents."

**Current behavior:** `resolve_rfa_limit` in `skills/legal/discovery-workflow/jurisdiction/limits.py` returns `None` for the entire WA family (including `wa_king_county`). The resolver's own comment (lines 88-94) says the King RFA number was "not confirmed in the citation-verification reports" at round-1, so it deferred to attorney override.

**Round-2 finding:** the number IS confirmed — **25** (excluding RFAs propounded solely to authenticate documents).

**Proposed fix:**
```python
# In resolve_rfa_limit, after the CA CCP branch and before the generic wa_state return:
if pack == "wa_state":
    if profile.get("case_overlay") == "wa_king_county":
        return 25  # LCR 26(b)(2)(4); excludes RFAs propounded solely to authenticate documents
    # wa_state base / wa_pierce_county: Pierce expressly no cap (PCLR 3(h)); wa_state no statewide cap.
    return None
```
Plus update the docstring and the `limits.py` module comment (lines 88-94) to reflect that the King number is now confirmed (25), and add a test in `tests/skills/test_discovery_rfa_request_audit.py` / `test_discovery_rfa_outgoing.py` for `resolve_rfa_limit(wa_king) == 25`.

**Authenticity-RFA exclusion (important for correct wiring):** LCR 26(b)(2)(4) caps "no more than 25 requests for admission ... **in addition to** requests for admission propounded to authenticate documents." The 25 counts **non-authenticity** RFAs. The resolver returns a flat `25` (the cap), but the audit/outgoing checkers must not flag a party that serves 25 merits RFAs + N authenticity RFAs. The cleanest wiring: the resolver returns `25` and the checker treats authenticity RFAs as exempt from the count (or the resolver's docstring makes the exclusion explicit so an attorney reviewing the flag understands it). Do **not** implement a flat "total RFA count > 25 → fail" check for King County.

**Severity:** Medium. The current None is safe (attorney override still honored) but unnecessarily conservative; a plaintiff propounding >25 RFAs in King County currently gets no automated flag.

**Also (handoff completeness — DONE 2026-07-20):** `HANDOFF_CODEX_ROUND2.md` Cluster 4 now lists the LCR 26(b)(2)(4) 25-RFA cap as a verification target, and Axis-2 claim 13 has been added, so Codex's round-2 verifies it too. The handoff header carries an amendment banner noting the supplement.

**No other corrections.** All 13 Axis-2 premises confirmed; all 6 clusters confirmed (with the two PARTIAL items in Cluster 5 — PCLR 7 moving-party filing deadline "7 court days" and PCLR 16 section text — being non-load-bearing and marked for full-section confirmation only if needed).
