---
name: legal-discovery-response
description: "Audit proposed discovery responses."
version: 0.1.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, discovery, audit, rfp, citations, plaintiff]
    category: legal
    related_skills: [legal-casegraph, legal-discovery-review]
---

# Legal Discovery Response Skill

Slice A1 only: audit proposed final **RFP** responses against one client's
indexed matter record. Interrogatories, RFAs, and outgoing drafting are **out
of scope** — see `../discovery-workflow/SPEC.md`. This skill is **not**
live-use-ready for a full discovery program; even RFP audit needs `SPEC.md`
§11 + owner §11.5 per matter.

## Hard Rules

- One matter per session and per command. Never load two clients' records into
  one context.
- Do not generate served response language in Phase A.
- Do not rewrite final objections; flag objection/privilege strategy as
  attorney review.
- Every support finding must cite the same matter's casegraph record.
- Run only against matter directories outside the repo for live work.

## Phase A Procedure

Set the script path:

```powershell
$dr = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-response\scripts\discovery_response.py"
$m = "C:\Matters\<MATTER-ID>"
```

Run:

```powershell
python $dr parse-rfp $m
python $dr parse-proposed $m
python $dr audit-existing $m
python $dr package-audit $m
python $dr validate-audit $m
```

Live `validate-audit` enforces full `live_preflight` including the OCR queue.
Synthetic fixtures (`.synthetic` marker) or `validate-audit --synthetic` may
skip OCR for smoke tests only — that is not live readiness.

Outputs:

- `02_outputs/proposed_propositions.jsonl`
- `02_outputs/response_audit_items.jsonl`
- `02_outputs/response_audit_report.md`

Before any live matter, confirm `03_attorney/PROVIDER_AUTH.md` is signed,
casegraph is fresh, and the owner has approved Phase A for that matter.

## Synthetic Self-Test

```powershell
python $dr selftest
```
