# Legal Discovery Response — Spec (Slice A1: RFP Response Audit)

**Status:** Slice A1 implemented, synthetic-only; **not ready for live use.**
**Program roadmap:** `skills/legal/discovery-workflow/SPEC.md` (rog|rfp|rfa ×
audit|draft axes). This file is **only** RFP `audit_incoming_response`.
**Date:** 2026-07-17 (amended: program pointer + multi-type roadmap)
**Primary use of this slice:** Critically **review proposed final RFP
responses** against that client's documents, testimony (where relevant), and
case-file / discovery corpus — **one matter (one client) at a time**.

**RFP-only (HARD for this slice):** Parsers and fixtures target served RFPs /
proposed RFP responses (`request_type: "rfp"`). Do **not** stretch these
parsers to interrogatories or RFAs — those are separate slices in the program
SPEC (A2 RFA audit, A3 rog audit, then outgoing drafting).
**Depends on:** `legal-casegraph`, `LIVE_MATTER_RUNBOOK.md`, `live_preflight.py`,
`check_provider_auth.py`. Matter dirs under `C:\Matters\<id>\` (outside repo).

**Hard ban:** Do not run against Allen, Client A, Client B, or any live matter
until §11 acceptance criteria pass on **synthetic** fixtures and the owner
signs off **for this slice**. This tool is **not** live-use-ready for a full
discovery program (rog/rfa/outgoing). Program-level drafting and other request
types follow `discovery-workflow/SPEC.md`, not the deferred Phase B sketch
below.

---

## 0. Implementation priority (HARD)

| Slice | Scope | Status / when |
|-------|-------|---------------|
| **A1 (this skill)** | RFP `audit_incoming_response` | Implemented — synthetic-only |
| **A2+** | RFA/rog audit, outgoing drafts, `draft_response` | See `discovery-workflow/SPEC.md` — **not** this file |

Historical “Phase B RFP generation” notes in §10 are superseded by the program
SPEC’s `draft_outgoing_request` / `draft_response` slices. Do not implement
generation from this file alone.

---

## 1. What Phase A is

A skill + CLI that takes:

1. a **proposed final discovery response set** (already drafted — Word/PDF/MD
   extract placed in the matter dir), and
2. that **same client's** indexed case file (casegraph: productions, intake,
   transcripts, prior discovery, memos),

and emits a **proposition-level audit**: each material claim in the proposed
responses graded against the record with strict locators — never a combined
multi-client review.

## 2. What this is NOT

- **Not a substitute for attorney judgment.** Audit statuses are machine-assisted
  draft findings for attorney review.
- **Not a cross-client comparator.** Two clients ⇒ two matter dirs ⇒ two
  invocations. See §3.1.
- **Not automatic "serve / don't serve" approval.**
- **Not objection strategy advice** beyond flagging unsupported assertions or
  record conflicts for attorney decision.
- **Not Phase B generation** until §0 says so.
- **Not a core Hermes model tool.** Footprint: skill + scripts under `skills/legal/`.

## 3. Isolation and privacy

| Rule | Requirement |
|------|-------------|
| Matter location | Outside repo (`C:\Matters\<MATTER-ID>\` via `scaffold_matter.py`) |
| Auth | Signed `03_attorney/PROVIDER_AUTH.md` before any remote model sees client text |
| Synthetic in-repo | Fixtures/goldens only; banner `SYNTHETIC / NON-CLIENT / TEST ONLY` |
| One matter | Every invocation takes exactly one `--matter-dir` |
| Gates | `casegraph status`, `verify-cites`, `check-isolation --strict`, `live_preflight.py` (full OCR queue for live; synthetic may skip OCR) |

### 3.1 Multi-client ban (HARD)

When auditing **two clients** (e.g. Client A and Client B):

1. Run `audit-existing` **separately** for each matter dir.
2. **Never** load both clients' proposed responses, transcripts, or productions
   into one agent context or one CLI invocation.
3. The only allowed joint artifact is an optional **top-level status index**
   outside both matters (e.g. owner spreadsheet or
   `C:\Matters\_audit_status\index.md`) that lists matter IDs, audit timestamps,
   and pass/fail of gates — **no facts, no quotes, no names beyond matter IDs,
   no Bates, no transcript lines**.
4. `check-isolation --strict` must FAIL if another matter's Bates prefix or
   fingerprint appears in an audit report.

---

## 4. Phase A inputs

### 4.1 Matter layout additions

```
<matter_dir>/
  00_intake/
  01_production/{raw,text}/ + BATES_MANIFEST.md
  01_discovery_served/              # propounded requests (for item alignment)
    rfp_set.md
  01_discovery_proposed/            # NEW — proposed FINAL responses to audit
    proposed_rfp_responses.md       # attorney-placed extract (required for audit)
    # optional: proposed_rfp_responses.docx → export to .md offline first
  01_transcripts/                   # optional; indexed via casegraph when present
    *.txt | *.md                    # page/line-preserving text extracts
  02_outputs/                       # audit writes here
  03_attorney/PROVIDER_AUTH.md
  .casegraph/
```

### 4.2 Required machine inputs (audit)

| Artifact | Source |
|----------|--------|
| Proposed final responses | `01_discovery_proposed/proposed_rfp_responses.md` |
| Served RFP set (for item IDs) | `01_discovery_served/rfp_set.md` |
| Casegraph index | `status` exit 0 (productions + any transcripts/case-file docs indexed) |
| Anchors | `03_attorney/anchors.json` |

### 4.3 Explicit non-inputs

- Another client's matter directory or exports.
- Unindexed PDFs/transcripts (OCR/index first).
- Attorney mental notes not on disk.

---

## 5. Cite model (shared Phase A / later Phase B)

### 5.1 Closed `cite.type` enum

| `type` | Required locator fields | Notes |
|--------|-------------------------|-------|
| `bates` | `value` (Bates or range) | Production docs |
| `intake` | `value` (stable intake doc id or relpath) | Client questionnaire / intake package |
| `transcript` | `value` (witness or depo id), `page`, `line_start`, `line_end` | Page:line testimony; `line_end` may equal `line_start` |
| `discovery` | `value` (e.g. `RFP-012` or prior response id), optional `party` | Prior or companion discovery request/response IDs |
| `case_file` | `value` (relpath under matter dir or registered doc id) | Memos, pleadings, correspondence staged in matter |

Optional on all types: `quote` (`string` or `null`).

**Invalid:** `type` outside the enum; `transcript` without `page` + `line_start`;
empty `value`.

### 5.2 Example cite objects

```json
{"type": "bates", "value": "THORN-PROD-000010", "quote": null}
{"type": "intake", "value": "00_intake/intake_package.md#wage-loss", "quote": null}
{"type": "transcript", "value": "Depo-Smith", "page": 42, "line_start": 3, "line_end": 11, "quote": null}
{"type": "discovery", "value": "RFP-003", "party": "plaintiff_prior", "quote": null}
{"type": "case_file", "value": "00_intake/engagement_notes.md", "quote": null}
```

---

## 6. Phase A — audit schemas and outputs

### 6.1 Parse proposed responses → propositions

CLI: `parse-proposed <matter_dir>`

Aligns proposed answer text to stable request IDs (`RFP-00N` from served set
when possible). Emits propositions (atomic factual or commitment claims) for
audit — not legal conclusions.

Path: `<matter_dir>/02_outputs/proposed_propositions.jsonl`

```json
{
  "item_id": "RFP-001",
  "proposition_id": "RFP-001-P01",
  "text": "Plaintiff will produce the June 1, 2024 incident report.",
  "kind": "production_commitment",
  "source_span": {"start_char": 120, "end_char": 188}
}
```

`kind` closed enum (v1): `production_commitment` | `factual_assertion` |
`already_produced_assertion` | `no_documents_assertion` | `other_record_bound`.

### 6.2 Audit item record

Path: `<matter_dir>/02_outputs/response_audit_items.jsonl`

```json
{
  "item_id": "RFP-001",
  "proposition_id": "RFP-001-P01",
  "proposition_text": "Plaintiff will produce the June 1, 2024 incident report.",
  "status": "supported",
  "record_cites": [
    {"type": "bates", "value": "THORN-PROD-000010", "quote": null}
  ],
  "conflict_cites": [],
  "notes": "Incident report present in production text cache.",
  "attorney_review_required": false
}
```

### 6.3 Proposition-level `status` enum (HARD)

| Status | Meaning |
|--------|---------|
| `supported` | Record cites adequately support the proposition |
| `partially_supported` | Some support; material gaps remain |
| `ambiguous` | Record unclear / incomplete OCR / competing readings |
| `unsupported` | No adequate support found in indexed record |
| `conflicts_with_record` | One or more record cites contradict the proposition |
| `needs_attorney_decision` | Privilege, strategy, or judgment call — stop |

Every audit item MUST use exactly one of these statuses.

### 6.4 Audit report template

Path: `<matter_dir>/02_outputs/response_audit_report.md`

````markdown
<!-- SYNTHETIC / NON-CLIENT / TEST ONLY -->

# Discovery Response Audit — DRAFT FOR ATTORNEY REVIEW

**Matter ID:** […]
**Proposed source sha256:** […]
**Casegraph status:** fresh | stale
**Single-matter invocation:** confirmed

> **ATTORNEY REVIEW REQUIRED — AUDIT DRAFT ONLY**
> Not a certification that responses are ready to serve.
> No cross-client facts. No final legal conclusions.

## Coverage summary

| Status | Count |
|--------|------:|
| supported | |
| partially_supported | |
| ambiguous | |
| unsupported | |
| conflicts_with_record | |
| needs_attorney_decision | |

## By request

### RFP-001

**Request (served):** […]

**Proposed response excerpt:** […]

| proposition_id | Status | Record cites | Notes |
|----------------|--------|--------------|-------|
| RFP-001-P01 | supported | Bates THORN-PROD-000010 | … |

## Conflicts and unsupported (roll-up)

- …

## Attorney checklist

- [ ] Every conflicts_with_record / unsupported item reviewed
- [ ] Testimony cites checked at page:line against transcript extract
- [ ] No other client's identifiers appear in this report
- [ ] Gate commands in §11.3 exit 0
````

---

## 7. Phase A CLI

`python skills/legal/discovery-response/scripts/discovery_response.py <cmd>`

| Command | Purpose | Exit |
|---------|---------|------|
| `parse-rfp <matter_dir>` | Served RFP → `discovery_requests.json` (shared) | 1 if zero items |
| `parse-proposed <matter_dir>` | Proposed finals → `proposed_propositions.jsonl` | 1 if empty |
| `audit-existing <matter_dir>` | Grade propositions vs casegraph/transcripts → `response_audit_items.jsonl` | 1 if casegraph stale |
| `package-audit <matter_dir>` | Write `response_audit_report.md` | 1 if coverage incomplete |
| `validate-audit <matter_dir>` | §11 Phase A gates | 1 on FAIL |
| `selftest` | Offline synthetic audit E2E | 1 on failure |

Agent workflow (SKILL.md, later): one matter → parse-rfp → parse-proposed →
audit-existing → package-audit → validate-audit →
`live_preflight.py --output …/response_audit_report.md`.

---

## 8. Phase A retrieval / grading loop

For each proposition:

1. Restrict all queries to `--matter-dir` index only.
2. Search productions (`bates` / grep), intake, transcripts (`transcript` locators),
   prior discovery IDs, case_file paths as applicable.
3. Assign exactly one §6.3 status; attach `record_cites` / `conflict_cites`.
4. Never invent Bates or page:line. Missing transcript text ⇒ `ambiguous` or
   `unsupported`, not guessed support.
5. Privilege-tinged or strategy-bound items ⇒ `needs_attorney_decision`.

---

## 9. Objection boundary (applies if audit comments on objections)

Audit may flag that proposed objection language is unsupported by the record or
inconsistent with produced documents. It **MUST NOT** rewrite final objection
prose for service. Generation-time objection rules (flag-only default, firm
template opt-in) live in Phase B (§13) and do not apply to Phase A except:

- No naked final-objection voice presented as attorney-approved in the audit
  report without `needs_attorney_decision` or explicit attorney checklist.

---

## 10. Phase B (deferred) — generation sketch

Do **not** implement until Phase A §11 is green. When built, generation reuses
§5 cite enum, served `discovery_requests.json`, and adds draft package outputs
(`rfp_response_items.jsonl`, `rfp_response_package.md`) with:

- `cited_claims[]` (each claim ≥1 cite; no multi-fact / single-cite pass)
- `--enable-template-objections` opt-in (no silent firm-template prose)
- `forbid_naked_objections` / `require_cited_claims` validators

Full generation CLI and templates remain postponed; prior draft sections are
superseded by this §10 pointer until Phase B is specified in a follow-up amend.

---

## 11. Machine-checkable acceptance criteria (Phase A)

All must pass before any live matter:

### 11.1 Parser / propositions

- [ ] `parse-rfp` stable `RFP-00N` IDs (golden re-parse).
- [ ] `parse-proposed` emits ≥1 proposition; every proposition maps to an `item_id`.
- [ ] Re-parse same source sha256 ⇒ identical proposition IDs/text (golden).

### 11.2 Audit integrity

- [ ] Every proposition appears exactly once in `response_audit_items.jsonl`.
- [ ] Every item has a valid §6.3 `status`.
- [ ] `supported` / `partially_supported` / `conflicts_with_record` items have
      ≥1 well-formed cite (§5.1); `transcript` cites include page + line_start.
- [ ] `unsupported` / `ambiguous` / `needs_attorney_decision` may have empty
      `record_cites` but must have non-empty `notes`.
- [ ] Validator `forbid_cross_matter_identifiers` — foreign Bates prefix or
      other-matter fingerprint ⇒ FAIL.

### 11.3 Casegraph / live gates

**Live readiness** (no `.synthetic` marker; OCR queue must be clear):

```
python skills/legal/discovery-response/scripts/discovery_response.py \
  validate-audit <matter_dir>
# equivalent live_preflight (OCR enforced — do NOT pass --skip-ocr-queue):
python skills/legal/scripts/live_preflight.py --matter-dir <matter_dir> \
  --output <matter_dir>/02_outputs/response_audit_report.md
```

Underlying casegraph gates (also run by `validate-audit`):

```
python skills/legal/casegraph/scripts/casegraph.py status <matter_dir>
python skills/legal/casegraph/scripts/casegraph.py verify-cites <matter_dir> \
  <matter_dir>/02_outputs/response_audit_report.md
python skills/legal/casegraph/scripts/casegraph.py check-isolation <matter_dir> \
  <matter_dir>/02_outputs/response_audit_report.md --strict
```

**Synthetic smoke** only (fixture / selftest matters with `.synthetic`, or
`validate-audit --synthetic`): `live_preflight` may use `--skip-ocr-queue`.
That path proves packaging and isolation — it does **not** satisfy live OCR
readiness. All listed live commands must exit 0 before §11.5.

### 11.4 Tests / hygiene

- [ ] `tests/skills/test_discovery_response_audit.py` — offline synthetic only.
- [ ] Two synthetic matters in selftest prove isolation (no cross cites).
- [ ] Skill frontmatter (when added): description ≤ 60 chars; confidentiality +
      attorney-review language; platforms include windows.
- [ ] `git diff --check` clean on new files (no trailing whitespace).

### 11.5 Ready-for-live gate (owner)

- [ ] §11.1–11.4 green on tip.
- [ ] Explicit written approval per matter (Client A, Client B, Allen, …).
- [ ] Each live client audited in its own matter dir only.
- [ ] No client files under `hermes-agent/`.

---

## 12. Implementation order

1. Fixtures: two synthetic matters + proposed response extracts + minimal
   transcripts/productions.
2. `parse-rfp` + `parse-proposed` + goldens.
3. Deterministic stub `audit-existing` (no model) wiring statuses + cites.
4. `package-audit` + `validate-audit` (including isolation).
5. SKILL.md Phase A procedure (one matter per session).
6. Model-assisted audit behind the same validators.
7. **Owner approval** → live Client A audit; separately Client B.
8. **Only then** open Phase B generation spec/implement.

---

## 13. Synthetic fixture plan (repo)

```
skills/legal/discovery-response/
  SPEC.md
  SKILL.md                         # later (Phase A first)
  scripts/discovery_response.py    # later
  fixtures/
    SYNTHETIC_client_a/
    SYNTHETIC_client_b/
    SYNTHETIC_rfp_set.md
    SYNTHETIC_proposed_rfp_responses.md
  templates/
    response_audit_report_template.md
```

---

## 14. Alignment with latest review

| Finding | Spec response |
|---------|----------------|
| First use is audit, not generate | §0 Phase A first; Phase B deferred |
| Cite types too narrow | §5 `bates\|intake\|transcript\|discovery\|case_file` |
| Two clients | §3.1 separate matters; status index facts-free |
| Audit outputs / statuses | §6 `response_audit_items.jsonl` + report + enum |
| Trailing whitespace | Strip before commit; §11.4 requires clean check |
| Live ban | Intro + runbook §8 |

---

## 15. Next action after this slice

1. Keep A1 synthetic gates green; no live use without §11.5.
2. Follow `discovery-workflow/SPEC.md` for A2 (RFA audit) next — do not stretch
   A1 parsers.
3. Full six-cell synthetic matrix + per-matter §9.5 before any live dry-run of
   the broader program.
