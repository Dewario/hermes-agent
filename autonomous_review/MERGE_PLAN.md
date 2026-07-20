# Merge Plan — `legal-autonomous-ca-wa-experts` → `main`

**Source branch:** `legal-autonomous-ca-wa-experts` (worktree `hermes-agent-autonomous`)
**Target:** `main` (primary checkout)
**Status:** Source is clean, verified, merge-ready. Target is NOT ready — it holds Codex's uncommitted work.
**Date:** 2026-07-19
**Decisions LOCKED (2026-07-20):** A1 (pack naming = Hermes uniform `<state>_<county>`), B1 (expert = standalone skill, fold Codex's intake/gap sourcing in).

This plan is for the **coordinated reconciliation** the user decided on. It does not edit `main` directly. It records the two taste calls that are the user's to make, plus the concrete port order, so the merge can execute the moment `main` is clean.

## Preconditions (must hold before any merge)

1. **`main` is clean.** Codex's uncommitted work in the primary checkout must be committed, stashed, or discarded first. Until then, any edit to `main` risks destroying that work. This is Codex's to resolve.
2. **No live matter use.** This is engineering work on skills. No `C:\Matters\*` paths. No owner §9.5 boxes checked by engineering. No forged signatures.
3. **`git diff --check` passes on the source.** Confirmed: exits 0 across `main..legal-autonomous-ca-wa-experts`.
4. **Source tests pass.** Confirmed: 139 passed on the 10-file legal suite (reproducible).
5. **Squash-merge safety.** Before squash-merging, rebase the source onto current `main` so a stale file doesn't silently overwrite recent `main` fixes. Verify with `git diff HEAD~1..HEAD` after merging.

## Decision A — Pack naming convention (USER DECISION)

The two efforts chose different pack file names. One convention must win; the other side's packs get renamed and their references updated.

| Concept | Hermes (this branch) | Codex (main) |
|---|---|---|
| WA state base | `wa_state.yaml` | `wa_cr.yaml` |
| King County overlay | `wa_king_county.yaml` | `wa_king_lcr.yaml` |
| Pierce County overlay | `wa_pierce_county.yaml` | `wa_pierce_pclr.yaml` |
| San Bernardino overlay | `ca_san_bernardino.yaml` | `ca_san_bernardino_local.yaml` |
| CA CCP base | `ca_ccp.yaml` | `ca_ccp.yaml` (same) |

**Option A1 — adopt Hermes' uniform `<state>_<county>` convention.** Rename Codex's packs to `wa_state` / `wa_king_county` / `wa_pierce_county` / `ca_san_bernardino`. Pros: uniform pattern, shorter, no acronym ambiguity. Cons: loses the embedded local-rule acronym (LCR/PCLR).

**Option A2 — adopt Codex's acronym-embedded convention.** Rename Hermes' packs to `wa_cr` / `wa_king_lcr` / `wa_pierce_pclr` / `ca_san_bernardino_local`. Pros: technically precise (embeds the actual local-rule acronym). Cons: less uniform, longer, mixes `_cr` (state) with `_lcr`/`_pclr` (county) patterns.

**Recommendation: A1 (Hermes' uniform convention).** Uniform `<state>_<county>` is easier to reason about and to extend (a future county pack just follows the pattern). The acronym can live in the pack's `description`/frontmatter rather than the filename. But this is a taste call — the user decides.

**DECISION LOCKED: A1** (2026-07-20). Codex's packs will be renamed to `wa_state` / `wa_king_county` / `wa_pierce_county` / `ca_san_bernardino` during the merge (step 13).

**References to update after renaming:** `overlays_allowed` and `base_pack` fields inside each base pack; any `matter_profile.yaml` template or example that names an overlay; the `load_pack.py` registry if it hardcodes names; tests that reference pack IDs by string.

## Decision B — Expert skill architecture (USER DECISION)

| Aspect | Hermes (this branch) | Codex (main) |
|---|---|---|
| Location | `skills/legal/expert-witness-analysis/` (standalone skill) | `skills/legal/discovery-workflow/scripts/expert_needs.py` (single script) |
| Taxonomy | `expert_taxonomy.yaml` — data-driven expert categories | inline in script — intake/gap themes |
| Case-law cites | Sargon (55 Cal.4th 747), Sanchez (63 Cal.4th 665), Copeland, § 801.1 | none (rule IDs only) |
| Admissibility standard | per-jurisdiction (FRE 702/Daubert, CA Kelly/Sargon + § 801.1, WA Frye/Copeland + ER 702) | not modeled |
| Input sourcing | case_facts + cast context | intake/gap-theme brief |

**Option B1 — keep Hermes' standalone skill, fold Codex's intake/gap-theme sourcing in as an additional input path.** Pros: retains the case-law/admissibility layer that is load-bearing for plaintiff-side trial work (a packet that says "consider a medical-causation expert" without naming Sanchez or § 801.1 is materially weaker); Codex's intake/gap sourcing becomes a useful input feeder. Cons: more surface than a single script.

**Option B2 — keep Codex's single script, add the case-law/admissibility layer to it.** Pros: lighter surface, stays inside discovery-workflow. Cons: a single script is a weaker home for a data-driven taxonomy and per-jurisdiction admissibility standards; harder to extend.

**Option B3 — keep both, with the standalone skill as canonical and the script as a thin packet generator that feeds it.** Pros: minimal disruption to either side. Cons: two surfaces for one concern until the script is thinned.

**Recommendation: B1.** For plaintiff-side trial work the case-law cites and per-jurisdiction admissibility standards are the value; the standalone skill is the right home for them. Codex's intake/gap-theme sourcing is a good INPUT path and should be folded in rather than discarded. But this is a taste call — the user decides.

**DECISION LOCKED: B1** (2026-07-20). The standalone `expert-witness-analysis` skill is canonical; Codex's `expert_needs.py` intake/gap-theme sourcing will be folded in as an additional input path during the merge (step 12).

## Port checklist (execute in this order, after preconditions hold)

Each item is a port FROM this branch INTO `main`. "Codex has" means `main` currently lacks it; "Codex retains bug" means `main` has the wrong version.

1. **Port `jurisdiction/limits.py` + the three resolvers** (`resolve_rog_limit`, `resolve_rfa_limit`, `resolve_rfp_limit`). This is the highest-priority correctness fix — it removes Codex's hardcoded federal-25-cap bug on WA ROGs (Codex `rog_request_audit.py:411`) and adds RFA/RFP limit checks that `main` lacks entirely.
2. **Re-wire `rog_request_audit.py`** to use `resolve_rog_limit` (replace the hardcoded `limit = 35 if "CCP-2030-030" in available_rules else DEFAULT_ROG_LIMIT`).
3. **Wire `check_outgoing_rog_limit` into `rog_outgoing.py`** (Codex's version has no outgoing limit check).
4. **Wire `resolve_rfa_limit` into `rfa_request_audit.py` + `rfa_outgoing.py`** (new on `main`).
5. **Wire `resolve_rfp_limit` into `rfp_request_audit.py` + `rfp_outgoing.py`** (new on `main`).
6. **Port `--allow-empty-cites` opt-in into `live_preflight.py`** (Codex added axis args but not this flag; Codex's expert script hardcodes `--allow-empty` locally instead).
7. **Port the CA CCP corrections into Codex's `ca_ccp.yaml`**: §§ 2023.050 ($1,000 sanction), 2033.280 (deemed admission), 2031.240 (objection particulars), 2016.040 (meet-and-confer declaration), 2023.010 (abuse of discovery), unlawful-detainer timing amendments, Evid. Code § 801.1. Codex's pack currently has only the § 2030.030 "plus form" fix.
8. **Port the explicit WA CR 33 no-statewide-cap statement** into Codex's `wa_cr.yaml` (Codex's pack is silent on the cap — the premise that prevents the hardcoded-25 bug from recurring).
9. **Reconcile San Bernardino rule subsets** — carry BOTH the 400-418 series (Codex) and the 520-571 series (Hermes), plus the eFiling rule (Local R. 1800-1860, Odyssey eFileCA) and the CRC 3.20 preemption note. **Round-2 refinements (merge-time):** (C2) cite the civil eFiling requirements page (https://sanbernardino.courts.ca.gov/online-services/efiling/civil-efiling/civil-efiling-requirements) for the Sept. 2, 2025 General Civil mandate date, with 1810.B as the rule framework — not 1810.B alone; (C3) narrow the discovery-code phrasing to "no stand-alone civil local discovery chapter/rule series identified in the July 1, 2026 SBSC civil rules" (avoid the broader "no discovery-related local provisions anywhere" claim).
10. **Pin King County specifics** into the King overlay: the 40 interrogatory cap (LCR 26), the **25-RFA cap** (LCR 26(b)(2)(4), **excluding** authenticity RFAs — new from Hermes round-2 self-verification; wire `resolve_rfa_limit(wa_king_county) → 25` here, do not implement a flat total-RFA-count check), and the 4,200/1,750 word limits (LCR 7). Codex's overlay mentions "local caps" without the numbers. **Round-2 refinement (merge-time, C4):** LCR 33(a) is "(Reserved)"; (b)/(c) govern pattern-interrogatory use/format. Encode only "King has an approved automobile-tort pattern set (per KCSC forms); LCR 33 governs use/format" — do not encode broader named pattern sets unless separately sourced.
11. **Pin Pierce County specifics** into the Pierce overlay: the 25/35/35/100 interrogatory caps by track (incl. Dissolution 100, which Codex misses), the 12/5 page limits (PCLR 7), and the LINX e-filing vendor. Codex's overlay misses Dissolution 100 and the page limits.
12. **Resolve Decision B (expert architecture)** — apply the chosen option.
13. **Resolve Decision A (pack naming)** — apply the chosen convention last, after all content is reconciled, then update `overlays_allowed`/`base_pack` references and tests.

## What this branch has that `main` lacks (do not lose in the merge)

- `resolve_rog_limit` / `resolve_rfa_limit` / `resolve_rfp_limit` + shared `jurisdiction/limits.py`.
- Outgoing ROG/RFA/RFP limit checks (plaintiff-side protection against propounding over-limit discovery).
- `--allow-empty-cites` opt-in in `live_preflight.py` (general, not hardcoded in one script).
- CA CCP enforcement levers (§§ 2023.050, 2033.280, 2031.240, 2016.040, 2023.010, unlawful-detainer timing, § 801.1).
- Explicit WA CR 33 no-statewide-cap statement.
- Pinned King 40 ROG cap + **25-RFA cap (LCR 26(b)(2)(4), excl. authenticity RFAs)** + 4,200/1,750 word limits; Pierce 25/35/35/100 caps + 12/5 page limits + LINX e-filing.
- San Bernardino 520-571 series + eFiling rule + CRC 3.20 preemption note.
- Standalone expert-witness-analysis skill with case-law/admissibility taxonomy.
- 24 new tests (RFA + RFP limit resolvers and wiring) + 14 invariant tests for corrected rules.

## What Codex's `main` has that this branch lacks (do not lose in the merge)

- San Bernardino Local R. 400, 404, 411.2, 412, 415, 416, 418 (case-management / trial-readiness / motions-in-limine / continuance series).
- `SOURCE_PACKET.md` (consolidated source-provenance document).
- King LCR 33 court-approved pattern-interrogatory rule.
- Pierce PCLR 16 pretrial / Joint Statement of Evidence.
- Codex's expert `expert_needs.py` intake/gap-theme sourcing (fold into the standalone skill per Decision B1).

## Hard rules

- No live `C:\Matters\*` paths touched in either checkout.
- No owner §9.5 boxes checked by engineering; no forged signatures.
- `owner_gate_assistant.py` automates the burden of review, never the act of approval.
- Any `needs_attorney_rule_confirm: true` flag requires a licensed attorney before reliance.
- This is engineering work on skills, not a live client matter.
