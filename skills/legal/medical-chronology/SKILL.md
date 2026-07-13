---
name: legal-medical-chronology
description: "Build cite-verified medical treatment chronologies."
version: 1.0.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, medical, chronology, bates, citations, personal-injury]
    category: legal
    related_skills: [legal-discovery-review, legal-casegraph]
---

# Legal Medical Chronology Skill

Create a date-sorted, source-grounded treatment chronology from a single matter's
medical records. It reports record-supported medical facts; it does not diagnose,
state legal causation, or replace attorney review.

**CONFIDENTIALITY:** Real matter data stays outside this repository. Before any
remote model receives live matter text, `03_attorney/PROVIDER_AUTH.md` must exist,
be initialed, and list the provider in use. If it is missing or incomplete, stop
and use `skills/legal/templates/PROVIDER_AUTH.template.md`. Synthetic fixtures are
the only exception.

## When to Use

- Preparing a provider-by-provider treatment history for a FELA or personal-injury matter.
- Reconciling dates, findings, restrictions, referrals, imaging, and follow-up care.
- Identifying explicit gaps, conflicting entries, or missing records for attorney review.

## Prerequisites

- One matter directory, handled in isolation, with readable medical-record text and Bates identifiers.
- For live matters, completed `03_attorney/PROVIDER_AUTH.md` before any client text reaches a remote provider.
- The `legal-casegraph` skill and its script available locally.
- Use `read_file` only for targeted source review; use `terminal` for casegraph commands and the helper.

## How to Run

1. For a live matter, verify `PROVIDER_AUTH.md` before reading or transmitting matter text.
2. Build and check the index before extracting facts; do not begin chronology work on an absent or stale index:

   ```powershell
   python skills/legal/casegraph/scripts/casegraph.py build <matter_dir>
   python skills/legal/casegraph/scripts/casegraph.py status <matter_dir>
   ```

3. Start from `templates/medical_chronology_template.md`. Query the casegraph by Bates, provider, and date; inspect the cited source text before recording a fact.
4. Add one dated row per supported event. Every dated event must include its `Source (Bates)` value and a verbatim `Quote`.
5. State missing dates, unreadable records, and conflicts explicitly as attorney-review items; never infer them.
6. Before handoff, run:

   ```powershell
   python skills/legal/medical-chronology/scripts/pin_quotes.py <chronology.md> <matter_dir>
   python skills/legal/casegraph/scripts/casegraph.py verify-chronology <matter_dir> <chronology.md> --strict
   python skills/legal/casegraph/scripts/casegraph.py verify-cites <matter_dir> <chronology.md>
   ```

## Quick Reference

| Row element | Requirement |
| --- | --- |
| Date | Record-supported date in `YYYY-MM-DD`; state uncertainty rather than guessing. |
| Event | Neutral, source-limited medical fact. |
| Provider | Named facility or clinician exactly as supported. |
| Source (Bates) | Bates page/range for every dated event. |
| Quote | Verbatim supporting span from source text. |

## Procedure

1. Keep one matter per session and run casegraph `build` then `status` first.
2. Sort records by service date, then record date when the service date is absent; label the distinction.
3. Extract only what the record says: symptoms, examination findings, diagnoses explicitly stated by the provider, tests, treatment, restrictions, referrals, and planned follow-up.
4. Pin each medical factual assertion to a verbatim source quote. Do not paraphrase a medical fact without retaining the supporting quote in the row.
5. Include Bates Sources per dated event, even when several events arise from the same record.
6. Use the helper for a local exact-normalized span check. For chronicle-style sliding-window quote matching, use casegraph quote checks through `verify-cites`; it can match source text across normalized windows.
7. Mark contradictions, unclear dates, and non-text-verifiable scans as `requires attorney review`.

## Pitfalls

- Do not treat a billed procedure, scheduling note, or problem-list entry as a performed treatment unless the record says it occurred.
- Do not infer causation, prognosis, diagnosis, or work restrictions from context.
- Do not omit a Bates source or replace it with a filename.
- Do not use a paraphrase where a medical fact is claimed; quote the source text verbatim.
- A passing machine gate verifies traceability, not medical or legal accuracy; attorney review remains required.

## Verification

- [ ] Casegraph `status` passes after the final source set is indexed.
- [ ] Every dated event has Provider, Source (Bates), and a verbatim Quote.
- [ ] `pin_quotes.py` reports every quoted span verified.
- [ ] `casegraph verify-chronology <matter_dir> <chronology.md> --strict` exits 0.
- [ ] `casegraph verify-cites <matter_dir> <chronology.md>` exits 0.
- [ ] Attorney reviews all gaps, conflicts, unreadable records, and medical interpretations.
