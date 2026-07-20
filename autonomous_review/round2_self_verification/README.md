# Round 2 — Self-Verification (Hermes independent pass)

**Purpose:** an independent, source-bounded re-verification of the load-bearing cites and cross-claim premises in `HANDOFF_CODEX_ROUND2.md`, run by Hermes in parallel with Codex's own Round-2 pass. The user's goal is **mutual cross-checking**: when Codex's `ROUND2_VERIFICATION_REPORT.md` returns, the two independent passes are reconciled, and any `SPLIT` (disagreement) is flagged for human review.

**Method:** each cluster is verified against primary/official sources (statute portals, court rule PDFs, court-published opinions, reliable mirrors). Per-cite verdict: `CONFIRMED` / `DRIFTED` (current text + effective date) / `NOT FOUND`. Cross-claim verdicts: `CONFIRMED` / `REFUTED` (correction + source) / `SPLIT`.

**Non-goals:** no edits to merge-critical files (resolvers, packs, expert skill); no edits to `main`; no live `C:\Matters\*` paths; no owner §9.5 boxes. This is review output only.

**Files:**
- `01_ca_ccp_selfcheck.md` — CA CCP + Evid. Code
- `02_wa_cr_er_selfcheck.md` — WA CR + ER
- `03_san_bernardino_selfcheck.md` — San Bernardino local
- `04_king_county_selfcheck.md` — King County local
- `05_pierce_county_selfcheck.md` — Pierce County local
- `06_expert_standards_selfcheck.md` — expert admissibility case law
- `cross_claims_selfcheck.md` — Axis 2 verdict table
- `SUMMARY.md` — roll-up
