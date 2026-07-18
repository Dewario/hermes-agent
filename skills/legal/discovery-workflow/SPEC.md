# Legal Discovery Workflow — Program Spec

**Status:** Program SPEC active. Implemented synthetic-only slices: **A1**
(RFP audit), **A2** (RFA audit), **A3** (ROG audit), **B1** (outgoing RFA
draft), **B2** (outgoing ROG draft). **Not ready for live use.**
**Date:** 2026-07-17 (amended: Slice B2 outgoing ROG draft landed)
**Goal:** One matter-scoped discovery system that covers interrogatories,
RFPs, and RFAs in both **audit** and **outgoing draft** modes — never a
cross-client combined review.

**Hard ban:** Do not run any discovery workflow against Allen, Client A,
Client B, or any live matter until that slice’s synthetic cell is green
**and** the owner signs §9.5 for that matter, request type, and mode. The
current RFP-audit CLI is a foundation only; it is **not** live-use-ready for a
full discovery program (rog + rfp + rfa, audit + draft).

**Depends on:** `legal-casegraph`, `LIVE_MATTER_RUNBOOK.md`,
`live_preflight.py`, `check_provider_auth.py`, and (for Slice A1)
`legal-discovery-response`. Matter dirs under `C:\Matters\<id>\` (outside
repo).

---

## 0. Why this program exists

`legal-discovery-response` Phase A ships only:

| Covered now | Not covered |
|-------------|-------------|
| Audit proposed final **RFP** responses (A1) | RFP outgoing drafting (B3) |
| Audit proposed final **RFA** responses (A2) | Mixed discovery-set workflow |
| Audit proposed final **ROG** answers (A3) | `draft_response` modes |
| Draft outgoing **RFAs** with issue tags (B1) | |
| Draft outgoing **ROGs** with issue tags (B2) | |
| One matter at a time | Full six-cell “ready” marketing |
| Synthetic validation + live OCR gate (skip OCR only if synthetic) | Live use without §9.5 |

This SPEC replaces the prior “RFP audit-first, then maybe generate RFPs”
roadmap with a two-axis workflow. Keep Slice A1 code where it is; expand by
new slices, not by stretching RFP parsers to other request types.

---

## 1. Axes (HARD)

Every invocation declares exactly one value on each axis:

| Axis | Values | Meaning |
|------|--------|---------|
| `request_type` | `rog` \| `rfp` \| `rfa` | Interrogatory / request for production / request for admission |
| `mode` | `audit_incoming_response` \| `draft_outgoing_request` \| `draft_response` (later) | What the tool does |

Definitions:

- **`audit_incoming_response`** — Grade **proposed final answers/responses**
  already drafted for this matter against this matter’s indexed record.
- **`draft_outgoing_request`** — Draft **outgoing** discovery requests this
  party will propound, tied to case issues / jury themes. Materially different
  from audit (issue model required).
- **`draft_response`** — Draft responses to served requests (deferred until
  corresponding audit slice is synthetic-green and owner opens the slice).

CLI / skill entry points MUST take `--request-type` and `--mode` (or
type-specific subcommands that fix both). Parsers, schemas, templates, and
gates are **per (`request_type`, `mode`)** — do not share one parser across
types.

---

## 2. Isolation and privacy (inherits runbook)

Same HARD rules as `discovery-response` SPEC §3 / runbook §8:

- Matter outside repo; signed `PROVIDER_AUTH.md` before remote model sees
  client text.
- One `--matter-dir` per invocation; never load two clients into one context.
- Facts-free multi-matter status index only (matter IDs + timestamps +
  pass/fail — no Bates, quotes, or party facts).
- Live `live_preflight` **without** `--skip-ocr-queue`; synthetic may skip OCR
  only when `.synthetic` or an explicit `--synthetic` flag is set.
- Objection language is attorney-controlled: flag issues or apply **opt-in**
  firm templates only. Never invent final objection strategy for service.

---

## 3. Shared cite and issue models

### 3.1 Cite enum (shared)

Reuse the closed cite types from `discovery-response` SPEC §5:

`bates` | `intake` | `transcript` | `discovery` | `case_file`

`transcript` requires `page` + `line_start` (+ `line_end`). Invalid cites FAIL
validators. Never invent Bates or page:line.

### 3.2 Issue tags (required for outgoing draft modes)

Outgoing drafts MUST tag each request (or subpart) with one or more:

| Tag | Use |
|-----|-----|
| `liability` | Duty / breach / negligence / FELA duty themes |
| `notice` | Actual/constructive notice, prior incidents |
| `causation` | Cause-in-fact / proximate cause |
| `damages` | Non-wage compensatory themes |
| `medical` | Treatment, diagnosis, prognosis, records |
| `wage_loss` | Earnings, disability from work |
| `impeachment` | Credibility / prior inconsistent statements |
| `authenticity` | Foundation for exhibits |
| `admissibility` | Evidence-rule / exclusion themes |
| `jury_theme` | Explicit jury-prep issue (must also name the theme in notes) |

Unknown tags FAIL validation. Audit modes may optionally echo issue tags when
the proposed response implies them; they are mandatory for
`draft_outgoing_request`.

---

## 4. Per-type product requirements

### 4.1 Interrogatories (`rog`)

**Audit (`audit_incoming_response`):**

- Parse served rogs + subparts → stable `ROG-00N` / `ROG-00N-S0K` IDs.
- Parse proposed answers → factual propositions (chronology, medical, wage,
  liability, identity, other record-bound).
- Grade each proposition with the shared status enum
  (`supported` | `partially_supported` | `ambiguous` | `unsupported` |
  `conflicts_with_record` | `needs_attorney_decision`).
- Flag unsourced chronology / medical / wage / liability assertions as
  `unsupported` or `needs_attorney_decision` (never silent pass).

**Outgoing (`draft_outgoing_request`):**

- Draft narrow interrogatories tied to §3.2 issue tags.
- Each request states the issue target and why it is jury-useful (short note).
- No final objection strategy in the draft voice; attorney checklist required.

### 4.2 Requests for production (`rfp`)

**Audit:** Slice A1 — see `skills/legal/discovery-response/SPEC.md` (implemented,
synthetic-only).

**Outgoing (`draft_outgoing_request`):** Not implemented. Must use RFP-specific
templates, issue tags, and Bates/production-awareness (what is already
produced vs sought). Do not reuse response-audit parsers for outgoing RFPs.

### 4.3 Requests for admission (`rfa`)

**Audit (`audit_incoming_response`):**

- Parse served RFAs → stable `RFA-00N` IDs.
- Classify each proposed response as exactly one of:
  `admit` | `deny` | `qualify` | `lack_information` | `object_only` |
  `other_attorney`.
- For `deny` / `qualify`: require record cites or
  `needs_attorney_decision` with notes; verify against casegraph.
- For `admit`: flag if the indexed record appears to contradict the admission.
- For `lack_information`: require notes on what was searched / why incomplete.

**Outgoing (`draft_outgoing_request`):**

- Draft narrow, jury-useful RFAs with §3.2 issue tags.
- Prefer single-fact RFAs; multi-fact RFAs must split or mark
  `needs_attorney_decision`.
- Attorney-review gate before any package is treated as serve-ready.

---

## 5. Templates (per request type × mode)

Ship separate Markdown templates under the implementing skill (paths may live
under `discovery-response/` initially, then move/copy into
`discovery-workflow/` when the umbrella skill lands):

| Artifact | Template role |
|----------|----------------|
| Rog answer audit report | Incoming audit packaging |
| Outgoing rog set | Draft propounded interrogatories |
| RFP response audit report | Slice A1 (exists) |
| Outgoing RFP set | Draft propounded RFPs |
| RFA response audit report | Incoming RFA audit packaging |
| Outgoing RFA set | Draft propounded RFAs |

Each package header MUST include matter ID, source sha256, casegraph freshness,
single-matter confirmation, and **ATTORNEY REVIEW REQUIRED** language.
Synthetic fixtures carry `SYNTHETIC / NON-CLIENT / TEST ONLY`.

---

## 6. Implementation slices (order HARD)

Do not open a later slice’s live gate before earlier synthetic matrices pass.

| Slice | `request_type` | `mode` | Status |
|-------|----------------|--------|--------|
| **A1** | `rfp` | `audit_incoming_response` | Implemented (synthetic-only) in `discovery-response/` |
| **A2** | `rfa` | `audit_incoming_response` | Implemented (synthetic-only) in `scripts/rfa_audit.py` |
| **A3** | `rog` | `audit_incoming_response` | Implemented (synthetic-only) in `scripts/rog_audit.py` |
| **B1** | `rfa` | `draft_outgoing_request` | Implemented (synthetic-only) in `scripts/rfa_outgoing.py` |
| **B2** | `rog` | `draft_outgoing_request` | Implemented (synthetic-only) in `scripts/rog_outgoing.py` |
| **B3** | `rfp` | `draft_outgoing_request` | Next — after B1/B2 stay green |
| **C*** | `rog`\|`rfp`\|`rfa` | `draft_response` | Only after matching audit slice is intentional for live |

\* `draft_response` remains deferred relative to outgoing requests unless the
owner reorders in writing. Default priority for the full program: **audit
coverage first (A2 → A3), then outgoing drafting (B1 → B3).**

Mixed discovery-set workflow (one CLI run over a combined rog+rfp+rfa binder)
is out of scope until A2+A3+A1 are each green on synthetic fixtures. Until
then: one request type per invocation.

---

## 7. Minimum synthetic test matrix

Offline fixtures only (two synthetic matters for isolation where audit cites
are involved):

1. audit rog response *(Slice A3 — exists)*
2. draft outgoing rog *(Slice B2 — exists)*
3. audit RFP response *(Slice A1 — exists)*
4. draft outgoing RFP
5. audit RFA response *(Slice A2 — exists)*
6. draft outgoing RFA *(Slice B1 — exists)*

Each cell needs parser golden or stable IDs, schema validation, package
template render, and gate path (`validate-*` + synthetic `live_preflight`
skip-OCR allowed). A live dry-run for a single slice requires that slice’s
cell to be green plus full OCR + `casegraph status` + `verify-cites` +
`check-isolation --strict` + `live_preflight` without skip-OCR + attorney
§9.5 sign-off. Full-program use or marketing requires all six cells green.

---

## 8. CLI sketch (umbrella — not implemented yet)

Preferred long-term surface:

```
python skills/legal/discovery-workflow/scripts/discovery_workflow.py \
  --matter-dir <matter> \
  --request-type rfa \
  --mode audit_incoming_response \
  <parse|audit|package|validate|selftest|...>
```

Until the umbrella lands:

```
# Slice A1 — RFP audit
python skills/legal/discovery-response/scripts/discovery_response.py <cmd>

# Slice A2 — RFA audit (dedicated module; refuses RFP/rog-looking sources)
python skills/legal/discovery-workflow/scripts/rfa_audit.py <cmd>

# Slice A3 — ROG audit (dedicated module; refuses RFP/rfa-looking sources)
python skills/legal/discovery-workflow/scripts/rog_audit.py <cmd>

# Slice B1 — outgoing RFA draft (issue-tagged; not audit parsers)
python skills/legal/discovery-workflow/scripts/rfa_outgoing.py <cmd>

# Slice B2 — outgoing ROG draft (issue-tagged; refuses Admit / audit parsers)
python skills/legal/discovery-workflow/scripts/rog_outgoing.py <cmd>
```

A2 commands: `parse-rfa`, `parse-proposed-rfa`, `audit-rfa`,
`package-rfa-audit`, `validate-rfa-audit`, `selftest`.

A3 commands: `parse-rog`, `parse-proposed-rog`, `audit-rog`,
`package-rog-audit`, `validate-rog-audit`, `selftest`.

B1 commands: `parse-issue-brief`, `draft-outgoing-rfa`, `package-outgoing-rfa`,
`validate-outgoing-rfa`, `selftest`.

B2 commands: `parse-issue-brief`, `draft-outgoing-rog`, `package-outgoing-rog`,
`validate-outgoing-rog`, `selftest`.

---

## 9. Acceptance criteria (program)

### 9.1 Per-slice (every new slice)

- [ ] Dedicated parser; refuses wrong `request_type` input.
- [ ] Dedicated output schema + template.
- [ ] Validators: cite enum, status/classification enum, isolation, no
      invented locators.
- [ ] Synthetic selftest cell in §7 matrix green.
- [ ] Objection boundary respected (flag / opt-in template only).

### 9.2 Live dry-run (per matter × slice)

```
casegraph status <matter_dir>
casegraph verify-cites <matter_dir> <output.md>
casegraph check-isolation <matter_dir> <output.md> --strict
python skills/legal/scripts/live_preflight.py --matter-dir <matter_dir> \
  --output <output.md>
```

All exit 0. No `--skip-ocr-queue` on live.

### 9.3 Hygiene

- [ ] Offline pytest only; no client files under `hermes-agent/`.
- [ ] `git diff --check` clean.
- [ ] Skill descriptions ≤ 60 chars when SKILL.md is added/updated.

### 9.4 Program ready for “full discovery” marketing/use

- [ ] All six §7 synthetic cells green.
- [ ] A2 + A3 + A1 audit slices owner-approved for the target matter types
      actually in hand.
- [ ] Outgoing slices used only after their own synthetic cells + owner
      sign-off.

### 9.5 Ready-for-live gate (owner) — per matter × slice

- [ ] That slice’s §9.1–9.3 green on tip.
- [ ] Explicit written approval naming matter ID + `request_type` + `mode`.
- [ ] Single-matter invocation confirmed.
- [ ] No client files under the repo.

**Verification (2026-07-17 — A1+A2 synthetic tip):**

| Slice | §9.1–9.3 synthetic | §9.5 owner sign-off | Live dry-run (§9.2) |
|-------|--------------------|---------------------|---------------------|
| A1 `rfp` / `audit_incoming_response` | Green (pytest + selftest) | **Open — not signed** | Not run |
| A2 `rfa` / `audit_incoming_response` | Green (pytest + selftest) | **Open — not signed** | Not run |
| A3 `rog` / `audit_incoming_response` | Green (pytest + selftest) | **Open — not signed** | Not run |
| B1 `rfa` / `draft_outgoing_request` | Green (pytest + selftest) | **Open — not signed** | Not run |
| B2 `rog` / `draft_outgoing_request` | Green (pytest + selftest) | **Open — not signed** | Not run |

§9.5 is an **owner** gate. Engineering may mark §9.1–9.3 green; it must **not**
check §9.5 boxes or run Allen/live matters until the owner writes approval for
that exact matter ID + request_type + mode.

---

## 10. Relationship to `legal-discovery-response`

| Item | Location |
|------|----------|
| Program roadmap + axes | **This file** |
| Slice A1 detail (RFP audit schemas, CLI, §11 gates) | `skills/legal/discovery-response/SPEC.md` |
| Slice A1 skill procedure | `skills/legal/discovery-response/SKILL.md` |
| Slice A1 implementation | `skills/legal/discovery-response/scripts/discovery_response.py` |
| Slice A2/A3 skill procedure | `skills/legal/discovery-workflow/SKILL.md` |
| Slice A2 implementation | `skills/legal/discovery-workflow/scripts/rfa_audit.py` |
| Slice A3 implementation | `skills/legal/discovery-workflow/scripts/rog_audit.py` |
| Slice B1 implementation | `skills/legal/discovery-workflow/scripts/rfa_outgoing.py` |
| Slice B2 implementation | `skills/legal/discovery-workflow/scripts/rog_outgoing.py` |

When this program SPEC and Slice A1 disagree on roadmap priority, **this file
wins**. When they disagree on RFP-audit schema details already shipped, A1
SPEC wins until a compatibility amend is explicit.

---

## 11. Next actions

1. Keep A1–A3 + B1 + B2 synthetic cells green. **No live clients** without §9.5.
2. Implement **B3** outgoing RFP.
3. Live dry-run per matter only after the relevant slice’s §9.5 sign-off.

**Do not** use A1/A2/A3/B1/B2 live without owner §9.5 for that matter × type × mode.

### A2 acceptance checklist (synthetic)

- [x] Dedicated `rfa_audit.py` parser; refuses RFP/rog-looking sources.
- [x] Classification enum + audit statuses + `rfa_response_audit_report.md`.
- [x] `tests/skills/test_discovery_rfa_audit.py` + `selftest`.
- [x] Live `validate-rfa-audit` does not skip OCR unless synthetic.

### A3 acceptance checklist (synthetic)

- [x] Dedicated `rog_audit.py` parser; subparts; refuses RFP/rfa-looking sources.
- [x] Proposition kinds + unsourced sensitive-kind hard fail + report template.
- [x] `tests/skills/test_discovery_rog_audit.py` + `selftest`.
- [x] Live `validate-rog-audit` does not skip OCR unless synthetic.

### B1 acceptance checklist (synthetic)

- [x] Dedicated `rfa_outgoing.py`; issue tags required; rejects objection voice.
- [x] Multi-fact AND-split; `outgoing_rfa_set.md` attorney-review package.
- [x] `tests/skills/test_discovery_rfa_outgoing.py` + `selftest`.
- [x] Live `validate-outgoing-rfa` does not skip OCR unless synthetic.

### B2 acceptance checklist (synthetic)

- [x] Dedicated `rog_outgoing.py`; issue tags required; refuses Admit / objection voice.
- [x] Multi-topic AND-split; `outgoing_rog_set.md` attorney-review package.
- [x] `tests/skills/test_discovery_rog_outgoing.py` + `selftest`.
- [x] Live `validate-outgoing-rog` does not skip OCR unless synthetic.
