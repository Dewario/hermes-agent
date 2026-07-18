---
name: legal-discovery-workflow
description: "ROG/RFA audit plus outgoing ROG/RFA drafts."
version: 0.4.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, discovery, audit, rfa, rog, citations, plaintiff]
    category: legal
    related_skills: [legal-casegraph, legal-discovery-response]
---

# Legal Discovery Workflow Skill

Program skill for multi-type discovery (`rog`|`rfp`|`rfa` × audit|draft).
See `SPEC.md` for the full roadmap.

**Implemented here:**
- **A2** — audit proposed final **RFA** responses (`scripts/rfa_audit.py`)
- **A3** — audit proposed final **ROG** answers (`scripts/rog_audit.py`)
- **B1** — draft outgoing **RFAs** with issue tags (`scripts/rfa_outgoing.py`)
- **B2** — draft outgoing **ROGs** with issue tags (`scripts/rog_outgoing.py`)

**RFP audit (Slice A1):** use `legal-discovery-response`, not these modules.

This skill is **not ready for live use** until the relevant slice gates pass and
the owner signs off for that matter × request_type × mode (§9.5).

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

## Slice A3 Procedure (ROG audit)

```powershell
$rog = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rog_audit.py"
$m = "C:\Matters\<MATTER-ID>"

python $rog parse-rog $m
python $rog parse-proposed-rog $m
python $rog audit-rog $m
python $rog package-rog-audit $m
python $rog validate-rog-audit $m
```

Inputs:

- `01_discovery_served/rog_set.md`
- `01_discovery_proposed/proposed_rog_answers.md`

Outputs:

- `02_outputs/rog_requests.json`
- `02_outputs/proposed_rog_propositions.jsonl`
- `02_outputs/rog_audit_items.jsonl`
- `02_outputs/rog_response_audit_report.md`

## Slice B1 Procedure (outgoing RFA draft)

```powershell
$orfa = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rfa_outgoing.py"
$m = "C:\Matters\<MATTER-ID>"

python $orfa parse-issue-brief $m
python $orfa draft-outgoing-rfa $m
python $orfa package-outgoing-rfa $m
python $orfa validate-outgoing-rfa $m
```

Input: `01_discovery_outgoing/rfa_issue_brief.md` (tagged fact lines).
Output: `02_outputs/outgoing_rfa_set.md` (attorney-review draft only).

## Slice B2 Procedure (outgoing ROG draft)

```powershell
$orog = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rog_outgoing.py"
$m = "C:\Matters\<MATTER-ID>"

python $orog parse-issue-brief $m
python $orog draft-outgoing-rog $m
python $orog package-outgoing-rog $m
python $orog validate-outgoing-rog $m
```

Input: `01_discovery_outgoing/rog_issue_brief.md` (tagged interrogatory lines).
Output: `02_outputs/outgoing_rog_set.md` (attorney-review draft only).
Refuses RFA-style `Admit` language — use Slice B1 for admissions.

## Synthetic Self-Test

```powershell
python $rfa selftest
python $rog selftest
python $orfa selftest
python $orog selftest
```
