---
name: legal-discovery-workflow
description: "Audit RFA responses; RFP via sibling skill."
version: 0.1.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, discovery, audit, rfa, citations, plaintiff]
    category: legal
    related_skills: [legal-casegraph, legal-discovery-response]
---

# Legal Discovery Workflow Skill

Program skill for multi-type discovery (`rog`|`rfp`|`rfa` × audit|draft).
See `SPEC.md` for the full roadmap.

**Implemented here (Slice A2):** audit proposed final **RFA** responses against
one client's indexed matter record.

**RFP audit (Slice A1):** use `legal-discovery-response`, not this module.

This skill is **not ready for live use** until the relevant slice gates pass and
the owner signs off for that matter × request_type × mode.

## Hard Rules

- One matter per session and per command.
- Do not stretch RFA parsers onto RFPs or interrogatories.
- Do not invent Bates or page:line cites.
- Objection language is attorney-controlled (flag only; no final strategy).
- Live validation enforces full OCR preflight; `.synthetic` may skip OCR for
  smoke tests only.

## Slice A2 Procedure (RFA audit)

```powershell
$rfa = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rfa_audit.py"
$m = "C:\Matters\<MATTER-ID>"

python $rfa parse-rfa $m
python $rfa parse-proposed-rfa $m
python $rfa audit-rfa $m
python $rfa package-rfa-audit $m
python $rfa validate-rfa-audit $m
```

Inputs (UTF-8 Markdown extracts):

- `01_discovery_served/rfa_set.md`
- `01_discovery_proposed/proposed_rfa_responses.md`

Outputs:

- `02_outputs/rfa_requests.json`
- `02_outputs/proposed_rfa_responses.jsonl`
- `02_outputs/rfa_audit_items.jsonl`
- `02_outputs/rfa_response_audit_report.md`

## Synthetic Self-Test

```powershell
python $rfa selftest
```
