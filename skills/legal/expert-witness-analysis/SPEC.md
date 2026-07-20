# Legal Expert Witness Analysis — Spec

**Status:** Slices E1-E3 implemented, synthetic-only; **not ready for live use.**
**Date:** 2026-07-19
**Skill:** `legal-expert-witness-analysis` (see `SKILL.md` for operational usage)
**Primary use:** Case-fact and cast-context driven recommendation of (a) liability
experts and (b) damages experts for **plaintiff** trial litigation — one matter
(one client) at a time.

**Hard ban:** Do not run against any live matter until §9.5 acceptance criteria
pass on **synthetic** fixtures and the owner signs off **for this slice**. No
expert reports; no ultimate-issue opinions; no "the plaintiff must retain X."

---

## 1. What this skill is

A deterministic recommender (not a model-based reasoner) that:

1. Parses `case_facts.md` + `cast_context.md`, plus intake and trial-gap
   feeder artifacts when present, into a case-fact text blob.
2. Matches the blob against a data-driven expert taxonomy
   (`references/expert_taxonomy.yaml`) using keyword triggers.
3. Resolves the admissibility standard from the matter's `jurisdiction_pack`
   (and optional `case_overlay`).
4. Emits per-expert recommendations with case-fact basis, admissibility notes,
   and foundation gaps — each flagged `needs_attorney_decision`.

The taxonomy and the admissibility-standard resolution are **data-driven and
testable**; the script stays deterministic so recommendations are reproducible.

---

## 2. Slices

| Slice | Scope | Status |
|-------|-------|--------|
| **E1** | Liability experts (accident reconstruction, human factors, safety/industry standards, engineering, regulatory compliance, toxicology, fire origin, premises security) | Implemented — synthetic-only |
| **E2** | Damages experts (treating physician, forensic medical, forensic economics, vocational rehabilitation, life care planning, neuropsychology, forensic accounting) | Implemented — synthetic-only |
| **E3** | Cast-context mapping + foundation gaps (cross-expert linkage to witnesses/custodians and record gaps) | Implemented — synthetic-only |

---

## 3. Admissibility standard resolution (`_standard_for`)

The standard is resolved from the matter profile, not hardcoded per expert:

| `jurisdiction_pack` | `case_overlay` | Standard |
|----------------------|----------------|----------|
| `frcp_generic` | (any) | `federal` (FRE 702 / Daubert; 2023 substantive amendment) |
| `ca_ccp` | `ca_san_bernardino` | `ca` (Kelly/Frye + Sargon + Sanchez + § 801.1) |
| `wa_state` | `wa_king_county` / `wa_pierce_county` | `wa` (Frye + ER 702) |

**Per-jurisdiction gates (critical — see `autonomous_review/citation_verification/expert_standards.md`):**

- **Federal:** FRE 702 (Dec. 1, 2023 substantive amendment — "more likely than not" preponderance stem; rewrote (d)) + Daubert/Kumho/Joiner.
- **CA state:** Kelly/Frye (People v. Kelly (1976) 17 Cal.3d 24) for novel scientific techniques; Sargon (Sargon Enterprises v. USC (2012) 55 Cal.4th 747) anti-speculation gatekeeping under Evid. Code 801(b)/802; Sanchez (People v. Sanchez (2016) 63 Cal.4th 665) case-specific hearsay limits; **§ 801.1** (operative Jan. 1, 2024) medical-causation symmetry — plaintiff-favorable exclusion of speculative defense alternative-cause opinions. CA does NOT follow Daubert.
- **WA state:** Frye (Frye v. United States, 293 F. 1013 (D.C. Cir. 1923); retained in State v. Copeland, 130 Wn.2d 244 (1996)) for novel scientific evidence + ER 702 (State v. Cauthron, 120 Wn.2d 879 (1993)) two-part test. **ER 702 does NOT track the 2023 FRE 702 amendment** — remains 1979 text. "ERI" is NOT a Washington evidence rule.

---

## 4. Data flow

```
case_facts.md + cast_context.md + intake/gap feeders
  -> parse_case_facts (text blob)
  -> _match_experts(blob, taxonomy["liability"])   -> E1
  -> _match_experts(blob, taxonomy["damages"])      -> E2
  -> _recommendation(expert, standard, triggers)    -> per-expert rec
  -> package_analysis (markdown report + jsonl)
  -> validate_analysis (casegraph verify-cites --allow-empty + check-isolation + live_preflight)
```

---

## 5. Hard invariants (enforced by tests)

- Every recommendation sets `needs_attorney_decision: true`.
- `objection_draft` is always `None` (no opinion drafting).
- The taxonomy must NOT reference the fictitious "ERI" WA rule.
- Sargon cite = `55 Cal.4th 747` (not `53 Cal.4th 1210`).
- Sanchez cite = `63 Cal.4th 665` (not `1 Cal.5th 865`).
- No "Copeland-Bryant" or "State v. Frye"; use `State v. Copeland` (1996).
- CA medical-causation experts reference § 801.1 (operative Jan. 1, 2024).
- WA CR 33 has no statewide interrogatory cap (county-local) — this skill does
  not impose a numerical cap on expert count.

---

## 6. Acceptance criteria (synthetic, before any live use)

1. `expert_analysis.py selftest` exits 0.
2. `parse-case-facts` + `assess-liability-experts` + `assess-damages-experts`
   + `package-expert-analysis` + `validate-expert-analysis` all exit 0 on a
   synthetic matter.
3. The report contains "ATTORNEY REVIEW REQUIRED" and the resolved
   jurisdiction standard.
4. casegraph `verify-cites --allow-empty` and `check-isolation` exit 0 on the
   output report.
5. `live_preflight.py` exits 0 (synthetic mode skips §9.5).
6. Owner signs `OWNER_LIVE_GATE_<slice>.md` for the specific slice before any
   live matter run — the `owner_gate_assistant.py` may automate the burden of
   review but NEVER the act of approval.

---

## 7. Out of scope (HARD)

- Retaining or vetting experts.
- Drafting expert reports, declarations, or any opinion text.
- Opinion-on-ultimate-issue drafting.
- Determining expert fees or budgets.
- Any legal conclusion ("the plaintiff must retain X"). Recommendations say
  "evidence supports the need for X expert," never the imperative.
- Live client files under `hermes-agent/`; matter dirs live outside the repo.
