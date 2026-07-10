---
name: legal-discovery-review
description: "FELA/PI discovery document review and analysis."
version: 1.0.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, discovery, review, fela, personal-injury, plaintiff, document-analysis]
    category: legal
    related_skills: [legal-discovery-intake, legal-casegraph, legal-matter-mail]
---

# Legal Discovery Review Skill

Review and analyze documents produced during discovery in FELA and personal-injury litigation.
Produces a structured review package: document inventory, issue coding, chronology, witness
extraction, production gaps, privilege screening, damages extraction, deposition outlines,
follow-up discovery recommendations, contradiction identification, and attorney review checklist.
Does NOT render legal conclusions or replace attorney judgment.

**CONFIDENTIALITY:** Review outputs are attorney work product. Work in a local directory
isolated from cloud storage. Never transmit produced documents through external APIs without
attorney authorization. This skill uses synthetic facts for development and testing only.

**ATTORNEY REVIEW REQUIRED:** All outputs are drafts for attorney review. No output is a legal
conclusion. Language: "evidence supports / suggests / contradicts / requires attorney review."

## When to Use

Load this skill when an attorney or legal professional needs to:
- Review a production set from the defendant or third parties
- Identify key documents, facts, witnesses, and gaps
- Build an issue coding matrix and fact chronology
- Screen for privilege, confidentiality, or clawback issues
- Extract medical, wage, and damages information
- Generate deposition outlines from produced documents
- Identify contradictions, missing custodians, and follow-up discovery targets

## Prerequisites

- Produced documents in readable format (PDF, text, image) accessible via `read_file`
- Optional: `vision_analyze` for image-based documents
- Review packet: incident reports, medical records, wage records, policies/rules, emails,
  witness statements, production cover letters
- Synthetic test fixtures at `skills/legal/discovery-review/fixtures/` for validation

## How to Run

1. Load the produced document set via `read_file` (text) or `vision_analyze` (images/PDFs).
2. Process documents section by section following the Procedure below.
3. Write each output section to the review package with `write_file`.
4. Run the verification checklist before presenting to the attorney.

## Quick Reference

| Output Section | Description |
|---------------|-------------|
| Document Inventory | Index of all reviewed documents with metadata |
| Issue Coding Matrix | Documents mapped to case issues and liability theories |
| Chronology / Timeline | Date-sorted fact events with source citations |
| Key Fact Extraction | Material facts extracted from each document |
| Witness / Entity Extraction | Persons and entities appearing in the production |
| Production Gap Analysis | Missing documents, custodians, and time periods |
| Privilege / Confidentiality Screen | Documents flagged for privilege or confidentiality |
| Medical / Wage / Damages Extraction | Medical findings, earnings data, and damages evidence |
| Safety Rule / Policy / Incident Report Extraction | Regulatory and safety content |
| Deposition Outline Seeds | Question topics from produced documents |
| Follow-Up RFP / Interrogatory / RFA Recommendations | Additional discovery targets |
| Contradiction List | Inconsistent statements between documents or witnesses |
| Missing-Custodian / Missing-Time-Period List | Gaps requiring further production |
| Attorney Final-Review Checklist | Quality-control checklist before attorney sign-off |

## Procedure


### Step 0: Production Preflight

**Casegraph first (mechanized preflight):** if the `legal-casegraph` skill is
available, run it before any manual preflight — it performs the manifest,
hash, Bates-range, duplicate, and readability checks below deterministically:

```
python skills/legal/casegraph/scripts/casegraph.py build  <matter_dir>
python skills/legal/casegraph/scripts/casegraph.py status <matter_dir>   # must exit 0 (not stale)
```

Use the build report's duplicate, unreadable, and Bates gap/overlap findings as
the preflight results — verified, not re-derived by the model. Query the index
(`query --bates/--grep/--entity`) instead of re-reading documents already
indexed. The manual checklist below remains authoritative for anything the
tool flags as unreadable or cannot parse.

Before processing any document, verify source integrity and citation provenance:

- **Source Manifest:** Confirm all files have stable identifiers (file hash, Bates range, or
  production-native identifier). Never process documents without a traceable citation source.
- **Bates Range Normalization:** Map every document to a normalized Bates range. Flag
  non-sequential ranges, gaps, and overlapping prefixes.
- **OCR / Image Quality:** For scanned or image-based documents, note OCR confidence
  level and whether the text is machine-readable. Flag pages where content is
  illegible or partially extracted. Do not infer facts from unreadable text.
- **Duplicate / Near-Duplicate Detection:** Identify exact duplicates (same hash) and
  near-duplicates (same content, different Bates). Mark the canonical copy and
  note alternates. Do not double-count or double-cite facts from duplicate documents.
- **Production Cover Letter Reconciliation:** Cross-check the document set against
  the production cover letter, privilege log, and any response-to-RFP index.
  Note discrepancies between the cover letter's description and the actual documents.
- **No-Inference Rule:** Documents with illegible, redacted, or corrupted content
  must be flagged as unreadable. Do not fill gaps with assumptions or inferences
  about what the missing content might contain.
- **Attorney Review:** All preflight flags are preliminary — final document identity
  and authenticity determinations require attorney review.

### Step 1: Build Document Inventory

For each document in the production:

```
Document ID: [Bates range or identifier]
Document Type: [incident report, medical record, email, policy, statement, photograph, etc.]
Date: [document date]
Author / Source: [person or entity that created the document]
Custodian: [person or entity that produced the document]
Page Count: [pages]
Confidentiality Marking: [none / confidential / attorney-client / work product]
Summary: [1-3 sentence factual summary]
Relevance: [high / medium / low — with brief rationale]
Issue Tags: [issue codes — see matrix]
Attorney Review Flag: [yes / no — and reason if yes]
```

### Step 2: Create Issue Coding Matrix

Tag each document against case issues. Example issues:

```
FELA-001: Unsafe work method — specific task
FELA-002: Inadequate crew size / help
FELA-003: Failure to inspect workplace
FELA-004: Failure to enforce safety rules
FELA-005: Negligent training / supervision
FELA-006: Defective equipment
FELA-007: Prior similar incidents — notice
FELA-008: Hours of service / fatigue
FELA-009: FRSA retaliation / intimidation
FELA-010: Medical causation
FELA-011: Wage loss / earning capacity
FELA-012: Future medical needs
PI-001: General negligence
PI-002: Premises liability
DAM-001: Medical specials
DAM-002: Lost wages / earning capacity
DAM-003: Pain and suffering
DAM-004: Loss of enjoyment / consortium
PROC-001: Evidentiary foundation
PROC-002: Witness impeachment
```

Produce: document-by-issue grid (documents as rows, issues as columns, relevance markers).

### Step 3: Build Chronology / Timeline

Date-sorted events. Each entry:

```
Date: [YYYY-MM-DD]
Event: [factual description — what happened]
Source: [document ID and Bates page]
Significance: [why this event matters to the case]
Issue Tags: [issue codes]
```

Events span: pre-incident employment history → incident → post-incident medical →
claim reporting → investigation → discovery responses. Gaps in the timeline are noted
explicitly.

### Step 4: Extract Key Facts

For each document, extract material facts:

```
Document ID: [Bates]
Fact: [specific factual statement]
Witness / Source: [person or document making the statement]
Corroboration: [other documents supporting this fact — or "uncorroborated"]
Contradiction: [documents contradicting this fact — or "none identified"]
Attorney Review: [evidence supports / suggests / requires attorney review]
```

### Step 5: Extract Witnesses and Entities

Every person and entity appearing in documents:

```
Name: [synthetic-only for testing]
Role: [plaintiff, defendant employee, witness, medical provider, expert, etc.]
Appears In: [document IDs]
Key Statements / Facts: [summary]
Contact Status: [known / unknown]
Deposition Priority: [high / medium / low — with rationale]
```

### Step 6: Analyze Production Gaps

```
Missing Documents:
- [description of document type not produced but expected]
  Expected Source: [custodian or system]
  Reason Expected: [why it should exist]
  Requested In: [RFP number]
  Status: [not produced / objection / claimed not to exist]

Missing Custodians:
- [name or role]
  Expected Content: [what documents this person likely holds]
  Status: [not searched / no documents / objection]

Missing Time Periods:
- [date range]
  Custodian: [who should have documents for this period]
  Reason Expected: [why this period matters]
  Status: [gap in production]
```

**Correspondence gap scan (optional, additive — when `legal-matter-mail` is
available):** the firm's own mailboxes are a custodian too. Run the **full**
matter-mail pipeline and fold its "missing from case file" and coverage findings
into this section, each item marked "requires attorney review". Do **not** run
`gap` on an empty/stale store.

```
python skills/legal/matter-mail/scripts/matter_mail.py context <matter_dir>
# ATTORNEY CONFIRMS window + participants in .matter_mail/scan_context.json
python skills/legal/matter-mail/scripts/matter_mail.py plan    <matter_dir>
# READ-ONLY fetch per plan (follow @odata.nextLink to exhaustion)
python skills/legal/matter-mail/scripts/matter_mail.py ingest  <matter_dir> --source <export_dir>
python skills/legal/matter-mail/scripts/matter_mail.py status  <matter_dir>   # must show non-zero matched
python skills/legal/matter-mail/scripts/matter_mail.py gap     <matter_dir> --strict
python skills/legal/matter-mail/scripts/matter_mail.py report  <matter_dir>
```

### Step 7: Privilege / Confidentiality Screen

For each document with confidentiality markings or privilege indications:

```
Document ID: [Bates]
Marking: [confidential / attorney-client / work product / other]
Basis: [stated basis for the marking]
Assessment: [marking is facially valid / marking appears overbroad / requires attorney review]
Action: [log for clawback review / request unredacted version / challenge designation]
```

Flag for attorney immediate review:
- Documents marked privileged that appear to contain factual incident information
- Redacted documents where redaction volume or location suggests non-privileged content
- Privilege logs that appear incomplete or conclusory

### Step 8: Extract Medical / Wage / Damages Information

**Medical Extraction:**

```
Provider: [synthetic name only for testing]
Document ID: [Bates]
Date of Service: [date]
Findings: [factual medical findings — no diagnosis unless explicitly stated]
Restrictions: [work restrictions, physical limitations]
Causation Statement: [any statement linking condition to incident]
Attorney Review: [evidence supports / suggests / contradicts causation]
```

**Wage / Damages Extraction:**

```
Document ID: [Bates]
Data Point: [earnings figure, wage rate, time period, benefits]
Amount: [synthetic amount or placeholder]
Period: [date range]
Source Type: [payroll record, W-2, RRB statement, tax return, time slip]
Attorney Review Note: [consistency / gaps / RRTA treatment]
```


All damages calculations and wage-loss figures in this section are preliminary.
All figures require attorney review and are subject to verification by a
qualified economic expert before use in pleadings, discovery responses, or
settlement negotiations.

### Step 9: Extract Safety Rule / Policy / Incident Report Content

For each safety-related document:

```
Document ID: [Bates]
Document Type: [safety rule, operating rule, training manual, incident report]
Key Provisions: [relevant rule text or policy language]
Application to Facts: [how the rule applies to the incident — factual analysis, not legal
  conclusion]
Violation Evidence: [facts suggesting compliance or non-compliance — evidence suggests /
  evidence contradicts / requires investigation]
Defendant's Position: [if stated in document — e.g., claims no violation, blames plaintiff]
```

### Step 10: Generate Deposition Outline Seeds

For each high-priority witness:

```
Witness: [name — synthetic]
Documents to Question On: [document IDs]
Topics:
  1. [topic from this witness's documents]
     Key Documents: [Bates]
     Goal: [what to establish or test]

  2. [topic]
     ...

Impeachment Material: [prior inconsistent statements — document IDs]
Attorney Prep Notes: [potential pitfalls, areas requiring witness's personal knowledge]
```

### Step 11: Recommend Follow-Up RFP, Interrogatory, and RFA

```
Additional RFPs:
- [document type or category]
  Basis: [why needed — gap identified in current production]
  Source: [custodian or system likely to hold it]

Additional Interrogatories:
- [topic]
  Basis: [what we need to know that documents don't reveal]

Additional RFAs:
- [fact to be admitted]
  Basis: [why this fact should be established without dispute]
```

### Step 12: Build Contradiction List

Inconsistencies between documents or between documents and intake facts:

```
Contradiction ID: CONTRA-001
Statement A: [fact] — Source: [Document ID]
Statement B: [contrary fact] — Source: [Document ID]
Analysis: [why these conflict — factual analysis only]
Resolution Clues: [documents or witnesses that might resolve the contradiction]
Attorney Review: [significance of the contradiction to case issues]
```

### Step 13: Missing Custodians and Missing Time Periods

```
Missing Custodians (not searched or no documents produced):
- [name / role]
  Relevance: [why their documents matter]
  Documents Expected: [types of documents they likely hold]

Missing Time Periods (gaps in produced date ranges):
- [date range]
  Custodians: [who should have documents from this period]
  Significance: [why this gap matters]
```

### Step 14: Attorney Final-Review Checklist

Quality-control checklist for the review package:

- [ ] All document IDs referenced in analysis are present in the inventory
- [ ] All issue codes used in the matrix are defined in the issue code legend
- [ ] Chronology entries are date-sorted with no duplicates
- [ ] Every witness in the extraction has at least one supporting document citation
- [ ] Production gaps are tied to specific RFPs or expected custodians
- [ ] Privilege flags include recommended attorney action
- [ ] All extracted facts cite source documents
- [ ] Contradictions are documented with both sources and analysis
- [ ] Deposition outline seeds reference specific documents and Bates ranges
- [ ] Follow-up discovery is specific (document types, custodians, time periods), not generic
- [ ] Medical extraction does not assert causation unless the source document does
- [ ] Wage extraction notes RRTA / FICA methodology
- [ ] Safety-rule extraction links provisions to incident facts
- [ ] Missing-custodian and missing-time-period lists are complete
- [ ] No legal conclusions stated as facts
- [ ] All analysis sections carry "requires attorney review" markers
- [ ] Synthetic data only (development/testing) — no real client facts in committed version

## Verification

Before presenting to the attorney, confirm:
- [ ] Every Bates-numbered reference in analysis sections resolves to a document in the inventory
- [ ] Issue coding matrix is internally consistent (no orphan codes, no uncoded documents)
- [ ] Chronology is complete (no date gaps without explicit notation)
- [ ] All attorney-review-required items are flagged

**Machine gates (mandatory for live matters — missing index = FAIL):** the matter
MUST have a casegraph index before handoff. Run all three on every review output;
all must exit 0, and every WARN must be resolved (register the entity with
`add-entity`, or investigate as possible contamination/hallucination):

```
python skills/legal/casegraph/scripts/casegraph.py verify-cites       <matter_dir> <output.md>
python skills/legal/casegraph/scripts/casegraph.py verify-chronology  <matter_dir> <output.md> --strict
python skills/legal/casegraph/scripts/casegraph.py check-isolation    <matter_dir> <output.md> --fingerprints <store> --strict
```

`verify-cites` defaults to quote checks and fails closed on zero same-matter
citations. If `.casegraph/` is missing: STOP — do not hand off.

These gates supplement — never replace — the checklist above and attorney review.

## Pitfalls

- DO NOT render legal opinions — "evidence supports an inference of X" and "X requires attorney
  review," never state "the defendant is liable for Y" as a conclusion
- Privilege assessment is a preliminary screen — only an attorney can decide whether to
  challenge a privilege claim
- Production gaps are based on what should exist in the ordinary course of the defendant's
  business, not speculation
- Medical causation statements in the extraction cite only what the source document states —
  do not infer causation
- Damages calculations require expert input — mark preliminary figures as subject to expert
  analysis
- FELA featherweight causation is a legal standard — the review outputs describe facts, the
  attorney applies the standard
