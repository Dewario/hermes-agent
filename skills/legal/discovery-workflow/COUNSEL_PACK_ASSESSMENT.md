# Counsel pack — skeptical assessment

**Date:** 2026-07-17  
**Lens:** AGENTS.md footprint ladder, prompt-cache, isolation, hallucination.

## 1. Footprint ladder

**Fit: skill + scripts only.** Jurisdiction YAML + D1/G1 CLIs under
`skills/legal/discovery-workflow/`. Do **not** add Hermes core tools, new
`HERMES_*` behavioral env vars, or speculative plugin hooks. Matter profile
belongs in the matter dir / `config` bridge later if needed — not `.env`.

## 2. Prompt-cache / isolation

| Risk | Mitigation |
|------|------------|
| Swapping `jurisdiction_pack` mid-conversation mutates system context | Pin pack on matter profile at session start; deferred invalidation (`--now` only if we add a slash command later) |
| Cross-matter Bates in gap reports | Keep casegraph `check-isolation --strict`; G1/B3 patterns for display IDs |
| Pack text bloating every turn | Load pack in tool/CLI process; inject **findings** into outputs, not full FRCP text into system prompt |

## 3. Hallucination / jurisdictional risk

| Risk | Mitigation |
|------|------------|
| Model invents “local rule” | Require `rule_ids` from loaded pack or `needs_attorney_rule_confirm` |
| Stub `ca_ccp` used live | `status: stub` → live validate FAIL |
| Overlay without base | Loader requires `base_pack` match |
| Auto-objection sounds serve-ready | `objection_draft` null by default; attorney-controlled |

## 4. Overlap with discovery-intake / review

| Keep | Do not duplicate |
|------|------------------|
| Intake FELA checklists as **overlay hints** | Second prose intake inside G1 |
| Review Section 11 follow-ups as **optional input** to G1 | Parallel unstructured “recommendations” skill with no schema |

Bridge: review/intake → structured `trial_gap_item` / issue-brief lines → B1–B3.

## 5. What NOT to build in v1

- Mixed rog+rfp+rfa binder CLI
- Auto-objection / meet-and-confer letter generator
- `draft_response` (C*)
- District-specific local-rule packs without a named court owner
- Core-agent toolset growth

## 6. Engineering sequence

| Step | Effort | Depends |
|------|--------|---------|
| Pack loader + unit tests | S | packs shipped |
| Matter profile template + scaffold hook | S | schema |
| **D1** RFP `audit_incoming_request` | M | loader, fixtures — done |
| **D2** RFA `audit_incoming_request` | M | D1 patterns — done |
| **D3** ROG `audit_incoming_request` | M | D1/D2 patterns — done |
| **G1** trial_gap_assessment | L | themes + packs + B\* brief format — done |
| A\* rule_id deepening | S–M | packs |
| Umbrella mode wiring | S | each slice |

## 7. Test strategy

- Offline pytest only; unique Windows `--basetemp`
- Pack schema tests (active vs stub)
- D1/D2/D3 refuse wrong-type sources; each has dedicated parser
- Isolation selftest two synthetic matters
- No client files under repo

## 8. Open questions for owner

1. Default pack for first live matter: `frcp_generic`+`fela`, or wait for `ca_ccp`?
2. First D* dry-run court / district (for future local pack — not required for FRCP)?

## Top 5 risks

1. **Jurisdictional hallucination** if checkers don’t enforce `rule_ids`
2. **Stub pack leakage** into live preflight
3. **Cache breaks** from mid-session pack swaps
4. **Scope creep** into auto-objections / C* before G1 green
5. **Prose duplication** with discovery-review instead of a schema bridge
