# Jurisdiction pack YAML schema

Packs are **data**. Checkers load them; models must not invent rule text beyond
what the pack contains. Missing coverage → `needs_attorney_rule_confirm`.

## Pack document

```yaml
pack_id: frcp_generic          # stable id
version: 1
status: active                 # active | stub | deprecated
title: "Federal Rules of Civil Procedure (generic)"
jurisdiction_kind: federal     # federal | state | local
overlays_allowed: [fela]       # optional overlay pack_ids
rules:                         # list of rule entries
  - id: FRCP-33-a-1
    citation: "Fed. R. Civ. P. 33(a)(1)"
    summary: "..."
    applies_to: [rog]          # rog | rfp | rfa | all
    check_hints:               # machine-usable tokens
      - numerical_limit
      - interrogatory
```

## Overlay document

Same schema plus:

```yaml
base_pack: frcp_generic        # required — overlays never stand alone for live
overlay: true
```

## Hard rules for consumers

1. Pin `jurisdiction_pack` (+ optional `case_overlay`) on the **matter profile**
   at session start. Do not swap packs mid-conversation (prompt-cache).
2. Every machine finding in `audit_incoming_request` / rule-deepened audits /
   `trial_gap_assessment` MUST include `rule_ids: []` from loaded packs, or
   `needs_attorney_rule_confirm: true` with notes.
3. `status: stub` packs **FAIL** live validation; synthetic tests may load stubs
   only when `--allow-stub-pack` is set.
4. Objection language remains attorney-controlled. Packs flag; they do not draft
   final serve-ready objections.
