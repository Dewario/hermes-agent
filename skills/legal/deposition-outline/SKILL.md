---
name: legal-deposition-outline
description: "Build source-grounded outlines for witness depositions."
version: 1.0.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, deposition, witness, impeachment, exhibits, casegraph]
    category: legal
    related_skills: [legal-casegraph, legal-discovery-review, legal-discovery-intake]
---

# Legal Deposition Outline Skill

Create a witness-specific deposition outline from an indexed matter record.
The outline organizes factual topics, source support, admissions sought, and
impeachment candidates; it does not provide legal conclusions or replace attorney judgment.

**CONFIDENTIALITY:** Drafts and source data are attorney work product. Keep real
matter data outside this repository and use only SYNTHETIC facts in committed fixtures.

**ATTORNEY REVIEW REQUIRED:** Every outline is a draft. Describe record support
as factual material for attorney review, rather than resolving credibility or legal issues.

## When to Use

- Preparing to examine a fact, corporate, records, or damages witness.
- Turning discovery-review findings into witness-specific questions.
- Organizing prior statements, records, and exhibits for a deposition.
- Identifying factual gaps that require follow-up records or attorney direction.

## Prerequisites

- For a live matter, `<matter>\03_attorney\PROVIDER_AUTH.md` exists, is
  initialed, and authorizes each provider before client text reaches a remote model.
  If it is missing or incomplete, STOP and use
  `skills/legal/templates/PROVIDER_AUTH.template.md`.
- The casegraph index is current: `casegraph status <matter_dir>` exits zero.
  Build or refresh it before drafting when production changed.
- Register the witness in the entity registry before drafting, using
  `casegraph add-entity <matter_dir> --name "<Witness Name>" --role witness`.
- Use one matter directory per session. Synthetic fixtures are exempt from live
  authorization requirements.

## How to Run

Set the casegraph script and matter directory, then query the indexed record
instead of loading production files directly:

```powershell
$cg = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\casegraph\scripts\casegraph.py"
$m = "C:\Matters\<MATTER-ID>"
$fp = Join-Path $env:HERMES_HOME "casegraph\fingerprints.json"

python $cg status $m
python $cg add-entity $m --name "<Witness Name>" --role witness
python $cg query $m --entity "<Witness Name>"
python $cg query $m --grep "<topic, event, or statement>"
```

Copy `templates/deposition_outline_template.md` to
`<matter>\02_outputs\deposition_outline_<witness>.md`, then complete it with
source-backed topics and attorney-review notes.

## Quick Reference

| Need | Casegraph query or outline field |
| --- | --- |
| Witness documents | `query --entity "<Witness Name>"` |
| Topic-specific records | `query --grep "<term>"` |
| Document details | `query --bates <BATES>` |
| Question sequence | topic, objective, questions, source, follow-up |
| Prior-statement test | statement, source/Bates, foundation, fallback |
| Exhibit preparation | Bates range, purpose, authentication/foundation note |

## Procedure

1. **Confirm matter controls.** Verify `PROVIDER_AUTH`, run `status`, and
   resolve one matter directory. If the index is stale, refresh it before
   drafting; do not rely on an old result.
2. **Register and query the witness.** Use `casegraph add-entity` if needed,
   then query `--entity` for witness-specific records and `--grep` for each
   incident, policy, communication, or damages topic. Record exact Bates
   ranges for every material item.
3. **Set examination objectives.** Identify factual objectives such as
   personal knowledge, timeline, notice, training, communications,
   document authenticity, or the witness's prior account. Mark unknowns as
   follow-up records or attorney questions.
4. **Organize topic outlines.** For each topic, state the factual objective,
   source/Bates, foundation questions, primary open questions, follow-up
   questions, and a clean transition. Put personal-knowledge and
   authentication predicates before substantive questions.
5. **Build impeachment candidates.** For each potentially inconsistent prior
   statement, identify the exact source and Bates range, the predicate needed
   to establish the statement, the precise proposition to test, and a
   non-argumentative fallback. Label all candidates “attorney review
   required”; do not decide credibility.
6. **Prepare exhibits.** List each planned exhibit with its Bates range,
   document description, topic, intended factual use, and authentication or
   foundation note. Do not cite unindexed or unreadable documents as verified
   source support.
7. **Review the completed outline.** Ensure every material topic and
   impeachment item has a source, every Bates reference resolves, and
   unresolved gaps are explicit.

## Pitfalls

- Do not state legal conclusions, characterize disputed facts as established,
  or tell the attorney what result the record requires. Use factual wording
  and “requires attorney review” for disputed significance.
- Do not use impeachment as an argument. First establish the witness's
  testimony and foundation; retain a neutral fallback question.
- Do not infer personal knowledge, document authorship, or authenticity from
  a name alone. Ask foundation questions and flag missing support.
- Do not treat a casegraph gate as a factual or legal quality determination;
  it confirms only defined mechanical conditions.
- Do not mix matter records or carry examples between matters.

## Verification

Before attorney handoff, ensure the witness is registered, the index is
current, and each material Bates reference appears in the casegraph. Run:

```powershell
python $cg verify-cites $m <outline.md>
python $cg check-isolation $m <outline.md> --fingerprints $fp --strict
```

Both commands must exit zero. Resolve every strict isolation warning by
registering a legitimate person through `casegraph add-entity`, or investigate
it as possible contamination before handoff. Attorney review remains required.
