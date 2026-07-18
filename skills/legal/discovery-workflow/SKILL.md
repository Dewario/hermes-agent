---
name: legal-discovery-workflow
description: "Audit and draft ROG/RFP/RFA discovery sets."
version: 0.11.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, discovery, audit, rfa, rog, rfp, citations, plaintiff]
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
- **B3** — draft outgoing **RFPs** with issue tags + production awareness
  (`scripts/rfp_outgoing.py`)
- **D1** — audit defense-served **RFP** requests under jurisdiction packs
  (`scripts/rfp_request_audit.py`)
- **D2** — audit defense-served **RFA** requests under jurisdiction packs
  (`scripts/rfa_request_audit.py`)
- **D3** — audit defense-served **ROG** requests under jurisdiction packs
  (`scripts/rog_request_audit.py`)
- **G1** — trial gap assessment → suggested B1–B3 issue-brief lines
  (`scripts/trial_gap.py`)

**RFP response audit (Slice A1):** use `legal-discovery-response`, not D1.

This skill is **not ready for live use** until the relevant slice gates pass and
the owner signs off for that matter × request_type × mode (§9.5). Use
`OWNER_LIVE_GATE.md` for that approval (owner only).

**Umbrella (optional):** `scripts/discovery_workflow.py` dispatches by
`--request-type` + `--mode` to the slice scripts below, or run
`selftest-all` for the synthetic matrix.

**Counsel-pack:** D1–D3 + G1 implemented (synthetic-only). C* / live still
blocked on owner §9.5 — see `COUNSEL_PACK_SPEC.md` and `jurisdiction/`.

## Hard Rules

- One matter per session and per command.
- Do not stretch parsers across request types.
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

## Slice B3 Procedure (outgoing RFP draft)

```powershell
$orfp = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rfp_outgoing.py"
$m = "C:\Matters\<MATTER-ID>"

python $orfp parse-issue-brief $m
python $orfp draft-outgoing-rfp $m
python $orfp package-outgoing-rfp $m
python $orfp validate-outgoing-rfp $m
```

Input: `01_discovery_outgoing/rfp_issue_brief.md` (tagged Produce lines;
optional `| Already: none|gap|Bates`).
Output: `02_outputs/outgoing_rfp_set.md` (attorney-review draft only).
Flags keyword overlaps against this matter's casegraph index. Refuses Admit
and interrogatory-only stems.

## Slice D1 Procedure (incoming RFP request audit)

Requires `<matter>/03_attorney/matter_profile.yaml` with `jurisdiction_pack`
(see `templates/matter_profile.template.yaml`).

```powershell
$d1 = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rfp_request_audit.py"
$m = "C:\Matters\<MATTER-ID>"

python $d1 parse-served-rfp $m
python $d1 audit-incoming-rfp $m
python $d1 package-incoming-rfp-audit $m
python $d1 validate-incoming-rfp-audit $m
```

Input: `01_discovery_served/rfp_set.md`  
Output: `02_outputs/incoming_rfp_request_audit_report.md`  
Does **not** draft objections (`objection_draft` is always null).

## Slice D2 Procedure (incoming RFA request audit)

Requires `<matter>/03_attorney/matter_profile.yaml` with `jurisdiction_pack`
(see `templates/matter_profile.template.yaml`).

```powershell
$d2 = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rfa_request_audit.py"
$m = "C:\Matters\<MATTER-ID>"

python $d2 parse-served-rfa $m
python $d2 audit-incoming-rfa $m
python $d2 package-incoming-rfa-audit $m
python $d2 validate-incoming-rfa-audit $m
```

Input: `01_discovery_served/rfa_set.md`  
Output: `02_outputs/incoming_rfa_request_audit_report.md`  
Does **not** draft objections (`objection_draft` is always null).
Refuses RFP/ROG-looking sources — use D1 or D3 respectively.

## Slice D3 Procedure (incoming ROG request audit)

Requires `<matter>/03_attorney/matter_profile.yaml` with `jurisdiction_pack`
(see `templates/matter_profile.template.yaml`).

```powershell
$d3 = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\rog_request_audit.py"
$m = "C:\Matters\<MATTER-ID>"

python $d3 parse-served-rog $m
python $d3 audit-incoming-rog $m
python $d3 package-incoming-rog-audit $m
python $d3 validate-incoming-rog-audit $m
```

Input: `01_discovery_served/rog_set.md`  
Output: `02_outputs/incoming_rog_request_audit_report.md`  
Does **not** draft objections (`objection_draft` is always null).
Counts discrete subparts toward Rule 33; refuses RFP/RFA-looking sources.

## Slice G1 Procedure (trial gap assessment)

Requires `<matter>/03_attorney/matter_profile.yaml` with `jurisdiction_pack`.
Attorney-authored themes: `01_discovery_outgoing/gap_themes.md`.

```powershell
$g1 = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\trial_gap.py"
$m = "C:\Matters\<MATTER-ID>"

python $g1 parse-gap-themes $m
python $g1 assess-trial-gaps $m
python $g1 export-issue-briefs $m
python $g1 package-trial-gap $m
python $g1 validate-trial-gap $m
```

Outputs:
- `02_outputs/trial_gap_report.md`
- `01_discovery_outgoing/gap_suggested_{rfp,rog,rfa}_issue_brief.md`

Edit suggested lines, then run B1–B3. Does **not** serve discovery.

## Synthetic Self-Test

```powershell
$dw = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\discovery_workflow.py"
python $dw selftest-all
# or per slice:
python $rfa selftest
python $rog selftest
python $orfa selftest
python $orog selftest
python $orfp selftest
python $d1 selftest
python $d2 selftest
python $d3 selftest
python $g1 selftest
```
