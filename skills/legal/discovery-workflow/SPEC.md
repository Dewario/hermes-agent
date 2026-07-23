# Legal Discovery Workflow — Program Spec

**Status:** Program SPEC active. Implemented synthetic-only slices: **A1**
(RFP audit), **A2** (RFA audit), **A3** (ROG audit), **B1** (outgoing RFA
draft), **B2** (outgoing ROG draft), **B3** (outgoing RFP draft). Counsel-pack
expansion: jurisdiction packs (`frcp_generic`, `fela`, `ca_ccp`,
`ca_san_bernardino`, `wa_state`, `wa_king_county`, `wa_pierce_county`) +
**D1-D3** + **G1** + **E1** + **F1** + **F2** + **C1-C3** `draft_response` (synthetic-only).
See `COUNSEL_PACK_SPEC.md`.
**Not ready for live client use** (owner §9.5 still required per real matter).
**Date:** 2026-07-19 (amended: F2 plaintiff objection / protective-order scaffolds)
**Goal:** One matter-scoped discovery system that covers interrogatories,
RFPs, and RFAs in both **audit** and **outgoing draft** modes — never a
cross-client combined review.

**Hard ban:** Do not run any discovery workflow against Allen, Client A,
Client B, or any live matter until that slice’s synthetic cell is green
**and** the owner signs §9.5 for that matter, request type, mode, and slice. The
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
| Audit proposed final **RFP** responses (A1) | Live client use without §9.5 |
| Audit proposed final **RFA** responses (A2) | Full counsel-pack “ready” marketing |
| Audit proposed final **ROG** answers (A3) | Mixed discovery-set workflow |
| Draft outgoing **RFAs** with issue tags (B1) | |
| Draft outgoing **ROGs** with issue tags (B2) | |
| Draft outgoing **RFPs** with issue tags + production awareness (B3) | |
| Jurisdiction packs + loader (`ca_ccp` active) | |
| Audit defense-served **RFP** requests (D1) | |
| Audit defense-served **RFA** requests (D2) | |
| Audit defense-served **ROG** requests (D3) | |
| Trial gap assessment → brief lines (G1) | |
| Expert-needs assessment for liability and damages (E1) | |
| Draft responses from attorney answer briefs (C1–C3) | |
| Plaintiff enforcement-lever scaffolds (F1) | |
| Plaintiff objection / protective-order scaffolds (F2) | |
| One matter at a time | |
| Synthetic validation + live OCR gate (skip OCR only if synthetic) | |

This SPEC replaces the prior “RFP audit-first, then maybe generate RFPs”
roadmap with a two-axis workflow. Keep Slice A1 code where it is; expand by
new slices, not by stretching RFP parsers to other request types.

---

## 1. Axes (HARD)

Every invocation declares exactly one value on each axis:

| Axis | Values | Meaning |
|------|--------|---------|
| `request_type` | `rog` \| `rfp` \| `rfa` \| `expert` | Interrogatory / request for production / request for admission / expert-needs assessment |
| `mode` | `audit_incoming_response` \| `draft_outgoing_request` \| `audit_incoming_request` (D1-D3) \| `trial_gap_assessment` (G1) \| `expert_needs_assessment` (E1) \| `enforcement_motion_draft` (F1) \| `objection_motion_draft` (F2) \| `draft_response` (C1-C3) | What the tool does |

Definitions:

- **`audit_incoming_response`** — Grade **proposed final answers/responses**
  already drafted for this matter against this matter’s indexed record.
- **`draft_outgoing_request`** — Draft **outgoing** discovery requests this
  party will propound, tied to case issues / jury themes. Materially different
  from audit (issue model required).
- **`audit_incoming_request`** — Grade **defense-served** requests under a
  pinned jurisdiction pack (D1 RFP + D2 RFA + D3 ROG — see
  `COUNSEL_PACK_SPEC.md`).
- **`trial_gap_assessment`** — Recommend additional plaintiff discovery before
  trial; feeds B1–B3 issue briefs (G1).
- **`expert_needs_assessment`** - Identify plaintiff-side liability and damages
  expert categories for attorney review (E1). Does not retain, designate, or
  finally approve any expert.
- **`enforcement_motion_draft`** — Draft non-substantive plaintiff
  enforcement-lever scaffolds (deemed-admitted, motion to compel,
  meet-and-confer, sanctions) with jurisdiction-aware statute selection (F1).
  Does not invent Bates/page:line cites, set a sanction amount, or sign §9.5.
- **`objection_motion_draft`** — Draft non-substantive plaintiff
  objection / protective-order scaffolds against defense-served ROG/RFP/RFA
  with jurisdiction-aware statute selection (F2). CA objection grounds are
  CCP sec. 2030.240 / 2031.240 / 2033.230 by request type; CA protective
  orders are CCP sec. 2030.090 / 2031.060 / 2033.080 by request type (plus
  2025.420 depositions and 2017.020 general scope). WA objections are
  stated in the response under CR 33(a) / 34(b) / 36(a) with CR 26(g) form;
  WA protective orders proceed under CR 26(c) for all request types with
  CR 37(a)(4) expenses. Does not invent substantive objection grounds,
  Bates/page:line cites, or sign §9.5.
- **`draft_response`** — Draft responses to served requests from an attorney
  answer brief (C1 RFP / C2 RFA / C3 ROG). Does not invent admissions;
  `objection_draft` stays null unless attorney opt-in.

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

**Outgoing (`draft_outgoing_request`):** Slice B3 — `scripts/rfp_outgoing.py`.
RFP-specific Produce/Provide drafts with §3.2 issue tags, optional
`| Already: none|gap|Bates` annotations, and keyword overlap checks against
this matter’s casegraph index. Does not reuse response-audit parsers.

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
| **B3** | `rfp` | `draft_outgoing_request` | Implemented (synthetic-only) in `scripts/rfp_outgoing.py` |
| **D1** | `rfp` | `audit_incoming_request` | Implemented (synthetic-only) in `scripts/rfp_request_audit.py` |
| **D2** | `rfa` | `audit_incoming_request` | Implemented (synthetic-only) in `scripts/rfa_request_audit.py` |
| **D3** | `rog` | `audit_incoming_request` | Implemented (synthetic-only) in `scripts/rog_request_audit.py` |
| **G1** | `rog`/`rfp`/`rfa` | `trial_gap_assessment` | Implemented (synthetic-only) in `scripts/trial_gap.py` |
| **E1** | `expert` | `expert_needs_assessment` | Implemented (synthetic-only) in `scripts/expert_needs.py` |
| **F1** | `rog`/`rfp`/`rfa` | `enforcement_motion_draft` | Implemented (synthetic-only) in `scripts/enforcement_motion.py` |
| **F2** | `rog`/`rfp`/`rfa` | `objection_motion_draft` | Implemented (synthetic-only) in `scripts/objection_motion.py` |
| **C1** | `rfp` | `draft_response` | Implemented (synthetic-only) in `scripts/rfp_response_draft.py` |
| **C2** | `rfa` | `draft_response` | Implemented (synthetic-only) in `scripts/rfa_response_draft.py` |
| **C3** | `rog` | `draft_response` | Implemented (synthetic-only) in `scripts/rog_response_draft.py` |

C* drafts are attorney-brief-driven packages only — never serve-ready without
human edit. Live client use still needs owner 9.5 per matter x type x mode x slice.

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
4. draft outgoing RFP *(Slice B3 — exists)*
5. audit RFA response *(Slice A2 — exists)*
6. draft outgoing RFA *(Slice B1 — exists)*
7. audit defense-served RFP request *(Slice D1 - exists)*
8. audit defense-served RFA request *(Slice D2 - exists)*
9. audit defense-served ROG request *(Slice D3 - exists)*
10. trial gap assessment *(Slice G1 - exists)*
11. expert-needs assessment *(Slice E1 - exists)*
12. draft responses to served RFP/RFA/ROG *(Slices C1-C3 - exist)*
13. plaintiff enforcement-lever scaffolds *(Slice F1 - exists)*
14. plaintiff objection / protective-order scaffolds *(Slice F2 - exists)*

Each cell needs parser golden or stable IDs, schema validation, package
template render, and gate path (`validate-*` + synthetic `live_preflight`
skip-OCR allowed). A live dry-run for a single slice requires that slice’s
cell to be green plus full OCR + `casegraph status` + `verify-cites` +
`check-isolation --strict` + `live_preflight` without skip-OCR + attorney
§9.5 sign-off. Full-program use or marketing requires all implemented synthetic cells green.

---

## 8. CLI (umbrella — implemented for A/B/C/D/G/E)

Preferred surface (`scripts/discovery_workflow.py` dispatches to dedicated
slice modules; it does not reimplement parsers). F1 and F2 are intentionally
standalone safety-scaffold slices with dedicated scripts and selftests, not
umbrella-dispatched modes:

```
python skills/legal/discovery-workflow/scripts/discovery_workflow.py \
  --matter-dir <matter> \
  --request-type rfa \
  --mode audit_incoming_response \
  <parse|audit|package|validate|selftest|...>

python skills/legal/discovery-workflow/scripts/discovery_workflow.py selftest-all
```

`selftest-all` covers A1-B3, D1-D3, G1, E1, and C1-C3. Run F1/F2 with their
dedicated script selftests.

Per-slice CLIs remain supported:

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

# Slice B3 — outgoing RFP draft (issue-tagged + production awareness)
python skills/legal/discovery-workflow/scripts/rfp_outgoing.py <cmd>
```

A2 commands: `parse-rfa`, `parse-proposed-rfa`, `audit-rfa`,
`package-rfa-audit`, `validate-rfa-audit`, `selftest`.

A3 commands: `parse-rog`, `parse-proposed-rog`, `audit-rog`,
`package-rog-audit`, `validate-rog-audit`, `selftest`.

B1 commands: `parse-issue-brief`, `draft-outgoing-rfa`, `package-outgoing-rfa`,
`validate-outgoing-rfa`, `selftest`.

B2 commands: `parse-issue-brief`, `draft-outgoing-rog`, `package-outgoing-rog`,
`validate-outgoing-rog`, `selftest`.

B3 commands: `parse-issue-brief`, `draft-outgoing-rfp`, `package-outgoing-rfp`,
`validate-outgoing-rfp`, `selftest`.

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
casegraph verify-cites <matter_dir> <output.md> [--allow-empty for draft/no-Bates-cite slices]
casegraph check-isolation <matter_dir> <output.md> --strict
python skills/legal/scripts/live_preflight.py --matter-dir <matter_dir> \
  --request-type <rog|rfp|rfa|expert> --mode <mode> --slice <slice> \
  [--output <output.md> for cite-bearing audit packages]
```

All exit 0. No `--skip-ocr-queue` on live.

### 9.3 Hygiene

- [ ] Offline pytest only; no client files under `hermes-agent/`.
- [ ] `git diff --check` clean.
- [ ] Skill descriptions ≤ 60 chars when SKILL.md is added/updated.

### 9.4 Program ready for “full discovery” marketing/use

- [x] All implemented Section 7 synthetic cells green.
- [ ] A2 + A3 + A1 audit slices owner-approved for the target matter types
      actually in hand.
- [ ] Outgoing slices used only after their own synthetic cells + owner
      sign-off.

### 9.5 Ready-for-live gate (owner) - per matter x request_type x mode x slice

- [ ] That slice’s §9.1–9.3 green on tip.
- [ ] Explicit written approval naming matter ID + `request_type` + `mode`.
- [ ] Single-matter invocation confirmed.
- [ ] No client files under the repo.

**Verification (2026-07-20 - implemented synthetic matrix):**

| Slice | §9.1–9.3 synthetic | §9.5 owner sign-off | Live dry-run (§9.2) |
|-------|--------------------|---------------------|---------------------|
| A1 `rfp` / `audit_incoming_response` | Green (pytest + selftest) | **Open — not signed** | Not run |
| A2 `rfa` / `audit_incoming_response` | Green (pytest + selftest) | **Open — not signed** | Not run |
| A3 `rog` / `audit_incoming_response` | Green (pytest + selftest) | **Open — not signed** | Not run |
| B1 `rfa` / `draft_outgoing_request` | Green (pytest + selftest) | **Open — not signed** | Not run |
| B2 `rog` / `draft_outgoing_request` | Green (pytest + selftest) | **Open — not signed** | Not run |
| B3 `rfp` / `draft_outgoing_request` | Green (pytest + selftest) | **Open — not signed** | Not run |
| D1 `rfp` / `audit_incoming_request` | Green (pytest + selftest) | **Open - not signed** | Not run |
| D2 `rfa` / `audit_incoming_request` | Green (pytest + selftest) | **Open - not signed** | Not run |
| D3 `rog` / `audit_incoming_request` | Green (pytest + selftest) | **Open - not signed** | Not run |
| G1 multi / `trial_gap_assessment` | Green (pytest + selftest) | **Open - not signed** | Not run |
| E1 `expert` / `expert_needs_assessment` | Green (pytest + selftest) | **Open - not signed** | Not run |
| F1 `rog`/`rfp`/`rfa` / `enforcement_motion_draft` | Green (pytest + selftest) | **Open - not signed** | Not run |
| F2 `rog`/`rfp`/`rfa` / `objection_motion_draft` | Green (pytest + selftest) | **Open - not signed** | Not run |
| C1-C3 / `draft_response` | Green (pytest + selftest) | **Open - not signed** | Not run |

§9.5 is an **owner** gate. Engineering may mark §9.1–9.3 green; it must **not**
check §9.5 boxes or run Allen/live matters until the owner writes approval for
that exact matter ID + request_type + mode + slice.

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
| Slice B3 implementation | `skills/legal/discovery-workflow/scripts/rfp_outgoing.py` |
| Slice D1-D3 implementations | `skills/legal/discovery-workflow/scripts/*_request_audit.py` |
| Slice G1 implementation | `skills/legal/discovery-workflow/scripts/trial_gap.py` |
| Slice E1 implementation | `skills/legal/discovery-workflow/scripts/expert_needs.py` |
| Slice F1 implementation | `skills/legal/discovery-workflow/scripts/enforcement_motion.py` |
| Slice F2 implementation | `skills/legal/discovery-workflow/scripts/objection_motion.py` |
| Slice C1-C3 implementations | `skills/legal/discovery-workflow/scripts/*_response_draft.py` |

When this program SPEC and Slice A1 disagree on roadmap priority, **this file
wins**. When they disagree on RFP-audit schema details already shipped, A1
SPEC wins until a compatibility amend is explicit.

---

## 11. Next actions

Synthetic matrix for A1-B3 + **D1-D3** + **G1** + **E1** + **F1** + **F2** + **C1-C3** is **complete**.
Umbrella `selftest-all` covers A1-B3 + D1-D3 + G1 + E1 + C1-C3; F1/F2 use
their dedicated selftests.
`ca_ccp` pack is **active**. Live-shaped rehearsal (synthetic matter ID only)
lives at `scripts/live_dry_run_rehearsal.py` under `C:\Matters\` — filled
§9.5 gates stay outside the repo.

1. Keep A1-B3 + D1-D3 + G1 + E1 + F1 + F2 + C1-C3 synthetic cells green. **No real clients** without §9.5.
2. One-matter smoke: `discovery_workflow.py smoke` (includes C2).
3. Real-client live dry-run still requires **owner §9.5** (`OWNER_LIVE_GATE.md`).
   Engineering never forges owner approval for a real client matter.

**Do not** use any slice on a real client without owner §9.5 for that matter × type × mode.

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

### B3 acceptance checklist (synthetic)

- [x] Dedicated `rfp_outgoing.py`; issue tags required; refuses Admit / ROG-only / objection voice.
- [x] Production-awareness (`Already:` + index keyword overlap); `outgoing_rfp_set.md`.
- [x] `tests/skills/test_discovery_rfp_outgoing.py` + `selftest`.
- [x] Live `validate-outgoing-rfp` does not skip OCR unless synthetic.

### F1 acceptance checklist (synthetic)

- [x] Dedicated `enforcement_motion.py`; four levers (deemed_admitted,
      motion_to_compel, meet_and_confer_letter, sanctions) with
      jurisdiction-aware statute selection from the loaded pack's available rules.
- [x] `deemed_admitted` is RFA-only: CA selects CCP sec. 2033.280; WA selects
      CR 36(a) with CR 36(b) supporting effect authority; non-rfa request types
      are refused. CA motion-to-compel selects by request type (CCP sec.
      2030.300 / 2031.310 / 2033.290); WA uses CR 37(a) for ROG/RFP and
      CR 36(a) for RFA sufficiency / no-response motions, with CR 37(a)(4)
      supporting expenses. Sanctions select CCP sec. 2023.050 (+ sec. 2023.010
      supporting) or CR 37(a)(4).
- [x] Non-substantive scaffold; no invented Bates/page:line cites; no sanction
      amount; no §9.5 signature. `enforcement_<lever>_scaffold.md` + meta.
- [x] `tests/skills/test_discovery_enforcement_motion.py` + `selftest`.
- [x] Live `validate-enforcement-motion` gates on `live_preflight` with
      `--slice F1 --mode enforcement_motion_draft`; does not skip OCR unless
      synthetic.

### F2 acceptance checklist (synthetic)

- [x] Dedicated `objection_motion.py`; two levers (objection,
      protective_order) with jurisdiction-aware statute selection from the
      loaded pack's available rules across rog/rfp/rfa.
- [x] CA objection grounds select by request type: CCP sec. 2030.240 (ROG),
      2031.240 (RFP, with privilege-log requirement), 2033.230 (RFA). CA
      protective orders select by request type: CCP sec. 2030.090 (ROG),
      2031.060 (RFP), 2033.080 (RFA), with sec. 2017.020 (general scope) and
      sec. 2016.040 (meet-and-confer) supporting; sec. 2025.420 governs
      depositions. WA objections select CR 33(a) (ROG), 34(b) (RFP), 36(a)
      (RFA) with CR 26(g) form supporting; WA protective orders select
      CR 26(c) for all request types with CR 26(i) and CR 37(a)(4) supporting.
- [x] Non-substantive scaffold; no invented Bates/page:line cites; no
      substantive objection grounds or relief; no §9.5 signature.
      `objection_<lever>_scaffold.md` + meta.
- [x] `tests/skills/test_discovery_objection_motion.py` + `selftest`.
- [x] Live `validate-objection-motion` gates on `live_preflight` with
      `--slice F2 --mode objection_motion_draft`; does not skip OCR unless
      synthetic.
