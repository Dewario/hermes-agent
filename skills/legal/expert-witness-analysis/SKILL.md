---
name: legal-expert-witness-analysis
description: "Recommend liability and damages experts for plaintiff cases."
version: 0.1.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, expert-witness, plaintiff, liability, damages, trial]
    category: legal
    related_skills: [legal-discovery-workflow, legal-discovery-intake, legal-discovery-review, legal-casegraph]
---

# Legal Expert Witness Analysis Skill

Case-fact and cast-context driven recommendation of (a) **liability** experts and
(b) **damages** experts for plaintiff trial litigation. Synthetic-only until the
owner signs §9.5 for the matter. Does NOT retain experts, draft expert reports,
or render legal conclusions.

**Hard rules:**
- One matter per invocation; never load two clients into one context.
- Recommendations cite the applicable admissibility standard (FRE 702 / Daubert
  federal; Kelly/Frye + Sargon for CA state; Frye + ER 702 for WA state).
- Every recommendation flags `needs_attorney_decision`; the attorney selects and
  retains the expert.
- No expert report drafting; no opinion-on-ultimate-issue drafting.
- No live client files under `hermes-agent/`; matter dirs outside the repo.
- Live use requires owner §9.5 (`OWNER_LIVE_GATE_<slice>.md`) + preflight.

## When to Use

Load this skill after `legal-discovery-intake` and `legal-discovery-review` have
produced the case facts and cast context. Use it to:
- Identify which expert disciplines the plaintiff needs for a strong liability case
- Identify which expert disciplines the plaintiff needs for an exceptional damages case
- Map each recommended expert to the case facts and cast that support the need
- Flag admissibility foundation required (qualification, reliability, fit)
- Surface gaps in the record that an expert would need to fill

## Prerequisites

- `<matter>/01_case_facts/case_facts.md` — chronological factual summary (from intake/review)
- `<matter>/01_case_facts/cast_context.md` — parties, witnesses, entities, custodians
- Intake and trial-gap feeder files are also read when present:
  `00_intake/case_context.md`, `00_intake/intake_package.md`,
  `01_discovery_outgoing/gap_themes.md`, issue briefs, and
  `02_outputs/trial_gap_*`
- `<matter>/03_attorney/matter_profile.yaml` with `jurisdiction_pack` (and optional overlay)
- `legal-casegraph` index for citation/isolation gates on the output

## How to Run

```powershell
$ew = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\expert-witness-analysis\scripts\expert_analysis.py"
$m = "C:\Matters\<MATTER-ID>"

python $ew parse-case-facts $m
python $ew assess-liability-experts $m
python $ew assess-damages-experts $m
python $ew package-expert-analysis $m
python $ew validate-expert-analysis $m
```

Outputs (under `<matter>/02_outputs/`):
- `expert_liability_recommendations.jsonl`
- `expert_damages_recommendations.jsonl`
- `expert_analysis_report.md`

## Quick Reference

| Output Section | Description |
| Liability Expert Recommendations | Discipline, role, case-fact basis, admissibility standard, foundation gaps |
| Damages Expert Recommendations | Discipline, role, case-fact basis, admissibility standard, foundation gaps |
| Cast-Context Mapping | Which witnesses/custodians support each expert's opinions |
| Foundation Gap List | Record gaps an expert would need to fill before forming an opinion |
| Attorney Review Checklist | Retention, disclosure cutoff, and Daubert/Kelly-Frye prep |

## Slices

- **E1** — liability experts (accident reconstruction, human factors, safety/industry
  standards, engineering, regulatory compliance)
- **E2** — damages experts (treating physician/forensic medical, forensic economics,
  vocational rehabilitation, life care planning, neuropsychology where indicated)
- **E3** — cast-context mapping + foundation gaps

## Pitfalls

- DO NOT render legal conclusions — "evidence supports the need for X expert," never
  "the plaintiff must retain X."
- Expert admissibility differs by jurisdiction: CA state court uses Kelly/Frye (not
  Daubert) for novel scientific evidence plus Sargon gatekeeping and Sanchez hearsay-basis
  limits; WA state court applies Frye (State v. Copeland, 130 Wn.2d 244 (1996)) + ER 702
  (State v. Cauthron, 120 Wn.2d 879 (1993)) — ER 702 does NOT track the 2023 FRE 702 amendment.
  Federal uses FRE 702 / Daubert (2023 substantive amendment, not restyling). The skill cites
  the correct standard for the matter's jurisdiction pack. CA medical-causation experts
  should also flag Evid. Code § 801.1 (operative Jan. 1, 2024) — a plaintiff-favorable tool
  to exclude speculative defense "alternative cause" opinions.
- Recommendations are preliminary attorney-review markers; the attorney selects,
  retains, and discloses experts per the scheduling order cutoff.
- No expert report drafting, no opinion-on-ultimate-issue drafting, no "the expert
  will testify that X." The skill identifies the discipline and the foundation need.

## Verification

Before attorney handoff, run the skill validator. It runs casegraph status,
`verify-cites --allow-empty`, check-isolation, and the axis-aware live preflight
gate for the expert-review mode:

```
python skills/legal/expert-witness-analysis/scripts/expert_analysis.py validate-expert-analysis <matter_dir>
```

If `.casegraph/` is missing: STOP — do not hand off.
