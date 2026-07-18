# Plaintiff Discovery Counsel Pack — Expansion SPEC

**Status:** SPEC only — **not implemented**. Synthetic A1–B3 remain the only
green cells. **Not ready for live use.**
**Date:** 2026-07-17  
**Parent program:** `SPEC.md` (A1–B3 details win there until merged)  
**This file wins** on counsel-pack roadmap, new modes, and jurisdiction axis.

**Hard ban:** No Allen/live matter runs; engineering never checks §9.5. Owner
gate: `OWNER_LIVE_GATE.md` per matter × request_type × **mode** (including new
modes below).

---

## 0. Product goal

A jurisdictionally disciplined plaintiff discovery counsel loop:

| Leg | Mode | Question |
|-----|------|----------|
| 1 | `audit_incoming_request` | Are **defense-served** ROGs/RFPs/RFAs proper under the pinned rule pack? |
| 2 | `audit_incoming_response` | Do **plaintiff proposed responses** match the record and rule duties? (A1–A3 exist; deepen with `rule_ids`) |
| 3 | `trial_gap_assessment` | What **additional** discovery should plaintiff issue before trial? → feeds B1–B3 |
| Rule layer | `jurisdiction_pack` (+ optional `case_overlay`) | Every finding cites pack `rule_id`s or `needs_attorney_rule_confirm` |

---

## 1. Axes (HARD)

| Axis | Values |
|------|--------|
| `request_type` | `rog` \| `rfp` \| `rfa` (N/A for pure G1 orchestrator runs that emit multi-type recommendations) |
| `mode` | `audit_incoming_response` \| `draft_outgoing_request` \| `audit_incoming_request` \| `trial_gap_assessment` \| `draft_response` (later) |
| `jurisdiction_pack` | Required for D\* and G1 (e.g. `frcp_generic`). Stub packs fail live. |
| `case_overlay` | Optional (e.g. `fela`). Must declare `base_pack`. |

One `--matter-dir` per invocation. Packs pinned from matter profile at start —
do not swap mid-session (prompt-cache).

---

## 2. Non-goals (v1)

- Inventing local rules or uncited doctrine
- Serve-ready objection drafting / auto-serve packages
- Mixed multi-matter or mixed-type binder CLI
- New Hermes **core** model tools (skill + scripts only)
- `draft_response` (C*) before D\* synthetic-green and owner intentional use
- Replacing attorney judgment on trial strategy

---

## 3. Matter profile fields (new)

Store under matter (outside repo), e.g. `03_attorney/matter_profile.yaml`:

```yaml
matter_id: ...
court: ...
jurisdiction_pack: frcp_generic
case_overlay: fela          # optional
discovery_cutoff: null      # ISO date or null → cutoff checks need_attorney
expert_cutoff: null
limits_used:
  rog: 0
  rfp: null                 # FRCP 34 has no default numerical cap
  rfa: 0
```

Scaffold may create a blank template later; D1 refuses live without pack id.

---

## 4. Slice order (HARD)

| Slice | Mode | request_type | Deliverable |
|-------|------|--------------|-------------|
| **D1** | `audit_incoming_request` | `rfp` | First implementation |
| **D2** | `audit_incoming_request` | `rfa` | After D1 green |
| **D3** | `audit_incoming_request` | `rog` | After D2 green |
| **G1** | `trial_gap_assessment` | (multi recommend) | After D1 + A\* available |
| A\* deepen | `audit_incoming_response` | per type | Add `rule_ids[]` to audit items |
| C\* | `draft_response` | per type | Only after matching audit intentional for live |

Do not open G1 live before D1 synthetic-green. B1–B3 remain the **draft**
engines; G1 emits issue-brief lines + priorities into `01_discovery_outgoing/`.

---

## 5. Schemas (outline)

### 5.1 `incoming_request_audit_item`

```json
{
  "item_id": "IR-RFP-1",
  "request_type": "rfp",
  "mode": "audit_incoming_request",
  "source_request_label": "Outgoing production request display or served heading",
  "flags": ["overbroad", "lacks_particularity"],
  "rule_ids": ["FRCP-34-b-1", "FRCP-26-b-1"],
  "severity": "warn",
  "notes": "...",
  "needs_attorney_decision": true,
  "objection_draft": null
}
```

`severity`: `info` \| `warn` \| `fail_candidate` (never auto-serve).  
`objection_draft` always null unless opt-in firm template id supplied.

### 5.2 `trial_gap_item`

```json
{
  "gap_id": "TG-1",
  "issue_tags": ["notice", "liability"],
  "element_or_theme": "prior notice of ladder defect",
  "recommended_request_type": "rfp",
  "priority": "must_before_cutoff",
  "rule_ids": ["FRCP-34-a", "FELA-THEME-NOTICE"],
  "already_covered": false,
  "suggested_brief_line": "- [notice] Produce all ... | Jury: prior notice",
  "needs_attorney_decision": true,
  "notes": "..."
}
```

`priority`: `must_before_cutoff` \| `should` \| `optional` \| `defer_to_attorney`.

### 5.3 Display IDs

Avoid Bates-like `RFP-001` in packages — use `IR-*` / `TG-*` / existing
`ORP-*`/`ORA-*`/`ORI-*` for outgoing.

---

## 6. Synthetic matrix additions

| Cell | Slice | Gate |
|------|-------|------|
| 7 | D1 rfp request audit | pytest + selftest |
| 8 | D2 rfa request audit | pytest + selftest |
| 9 | D3 rog request audit | pytest + selftest |
| 10 | G1 trial gap | pytest + selftest; exports brief lines without foreign Bates |

Jurisdiction unit tests: load `frcp_generic`+`fela`; refuse `ca_ccp` without
`--allow-stub-pack`; refuse unknown `rule_id` references in fixtures.

---

## 7. Relationship to other skills

| Skill | Role |
|-------|------|
| `discovery-workflow` A1–B3 | Keep; deepen; do not stretch parsers |
| `discovery-review` / `discovery-intake` | Prose inputs to G1 — bridge, don’t duplicate |
| `casegraph` | Unchanged gate layer |
| `jurisdiction/` | Pack data for D\*/G1 |

---

## 8. Acceptance (per new slice)

Same as parent SPEC §9.1–9.3 + pack pinning + rule_id discipline.  
§9.5 remains **owner-only**.

### D1 acceptance checklist (not started)

- [ ] Dedicated RFP incoming-request auditor; refuses response-audit parsers
- [ ] Loads `frcp_generic` (+ optional overlay); stub packs blocked on live
- [ ] Template + synthetic fixture + pytest/selftest
- [ ] Umbrella dispatch for `audit_incoming_request`
