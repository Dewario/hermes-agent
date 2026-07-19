# Discovery counsel — surface inventory

**Source:** multi-agent research pass, 2026-07-17.  
**Purpose:** Anchor counsel-pack expansion. Not a live-readiness claim.

## Implemented (synthetic-green; §9.5 open)

| Slice | Mode | Script |
|-------|------|--------|
| A1 | rfp / audit_incoming_response | `discovery-response/scripts/discovery_response.py` |
| A2 | rfa / audit_incoming_response | `scripts/rfa_audit.py` |
| A3 | rog / audit_incoming_response | `scripts/rog_audit.py` |
| B1 | rfa / draft_outgoing_request | `scripts/rfa_outgoing.py` |
| B2 | rog / draft_outgoing_request | `scripts/rog_outgoing.py` |
| B3 | rfp / draft_outgoing_request | `scripts/rfp_outgoing.py` |

Umbrella: `scripts/discovery_workflow.py` (+ `selftest-all`).

## Adjacent prose skills (not machine-gated counsel loop)

| Skill | Useful for counsel pack | Gap |
|-------|-------------------------|-----|
| `discovery-intake` | Matter profile, FELA checklists, sample starter sets | Not record-driven; no jurisdiction pack |
| `discovery-review` | Gaps, follow-up discovery recommendations (prose) | No CLI bridge to B1–B3 issue briefs |
| `casegraph` | Cite/isolation/OCR gates | Shared foundation — keep |
| `deposition-outline` | Admissions/impeachment themes | Downstream of gap work |

## Gaps vs plaintiff discovery counsel target

| Target | Status |
|--------|--------|
| Audit **defense-served requests** (overbreadth, limits, rule cites) | **Synthetic-green offline** — D1–D3; live needs owner §9.5 |
| Audit **plaintiff proposed responses** | **Synthetic-green offline** — A1–A3; live needs §9.5 |
| **Trial-gap / additional discovery** before trial | **Synthetic-green offline** — G1 themes → brief exports; attorney edit before B* |
| **Jurisdiction / rule packs** | **Loader + frcp_generic/fela + active ca_ccp** — used by D*/G1/C* |
| `draft_response` (C*) | **Synthetic-green offline** — C1–C3 answer-brief drafts; attorney edit before serve |

## Shared enums to reuse (do not fork)

- Cite types: `bates` \| `intake` \| `transcript` \| `discovery` \| `case_file`
- Audit status: `supported` \| `partially_supported` \| `ambiguous` \| `unsupported` \| `conflicts_with_record` \| `needs_attorney_decision`
- Outgoing issue tags: `liability` \| `notice` \| `causation` \| `damages` \| `medical` \| `wage_loss` \| `impeachment` \| `authenticity` \| `admissibility` \| `jury_theme`

Bridge later: review codes `FELA-00x` → workflow issue tags (`references/issue_tag_map.yaml`).
