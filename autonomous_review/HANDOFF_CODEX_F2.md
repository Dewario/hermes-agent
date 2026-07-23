# Handoff — Codex F2 Cross-Check (objection / protective-order scaffolds)

**Dispatch date:** 2026-07-23
**Source branch:** `legal-evidentiary-objections` (autonomous worktree at
`C:\Users\Prime\AppData\Local\hermes\hermes-agent-autonomous`)
**Base:** `ae538c895` (main tip: F1 + OCR retry hardening)
**Slice:** F2 — `objection_motion_draft` mode; levers `objection`, `protective_order`
**Hermes verification packet:** `autonomous_review/f2_objection_verification/F2_VERIFICATION_REPORT.md`

## 1. Objective

Codex performs an independent, multi-agent / multi-model parallel cross-check
of the F2 plaintiff objection / protective-order scaffolds before any merge
or live use. Two axes:

1. **Citation currency + correctness** — re-verify every F2 anchor statute
   against primary sources (CA leginfo; WA courts PDFs) and confirm the
   implementation's `select_statute` picks match.
2. **Plaintiff objection posture** — confirm the scaffolds are
   non-substantive, do not invent objection grounds or Bates/page:line cites,
   and that the per-request-type statute mapping is correct for a plaintiff
   responding to defense-served ROG/RFP/RFA and moving for protective orders.

## 2. Locked constraints (do not violate)

- **Synthetic only.** No live `C:\Matters\<client>` path. No owner §9.5
  sign-off. No `OWNER_LIVE_GATE_F2*.md` creation or signing.
- **Non-substantive.** The scaffolds name the controlling statute and
  attorney-controlled posture only. Codex must flag any invented substantive
  objection grounds, relief, or sanction amount as a defect.
- **No core edits.** F2 is a skill/script slice; do not grow the core toolset.
- **No allowlist changes.** Scaffolds pass `check-isolation --strict` via
  table-rendered metadata + candidate-free prose. If Codex finds an
  isolation leak, report it; do not paper over it with allowlist entries.

## 3. Verification targets

### Cluster 1 — CA CCP objection grounds (primary: leginfo.legislature.ca.gov)

| Rule id | Citation | Source URL |
|---|---|---|
| CCP-2030-240 | Cal. Code Civ. Proc. sec. 2030.240 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2030.240. |
| CCP-2031-240 | Cal. Code Civ. Proc. sec. 2031.240 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2031.240. |
| CCP-2033-230 | Cal. Code Civ. Proc. sec. 2033.230 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.230. |

Confirm: specific-ground requirement; privilege/work-product assertion;
partial-objection remainder answered; RFP privilege-log facts.

### Cluster 2 — CA CCP protective orders (primary: leginfo)

| Rule id | Citation | Source URL |
|---|---|---|
| CCP-2030-090 | Cal. Code Civ. Proc. sec. 2030.090 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2030.090. |
| CCP-2031-060 | Cal. Code Civ. Proc. sec. 2031.060 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2031.060. |
| CCP-2033-080 | Cal. Code Civ. Proc. sec. 2033.080 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2033.080. |
| CCP-2025-420 | Cal. Code Civ. Proc. sec. 2025.420 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2025.420. |
| CCP-2017-020 | Cal. Code Civ. Proc. sec. 2017.020 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2017.020. |
| CCP-2016-040 | Cal. Code Civ. Proc. sec. 2016.040 | https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum=2016.040. |

Confirm: prompt-move right; meet-and-confer declaration prerequisite; good
cause; "any order justice requires" standard; § 2017.020 general scope limit
is the correct supporting vehicle.

### Cluster 3 — WA CR objections (primary: courts.wa.gov PDFs)

| Rule id | Citation | Source URL |
|---|---|---|
| WA-CR-33-A | Wash. Super. Ct. Civ. R. 33(a) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_33_00_00.pdf |
| WA-CR-34-B | Wash. Super. Ct. Civ. R. 34(b) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_34_00_00.pdf |
| WA-CR-36-A | Wash. Super. Ct. Civ. R. 36(a) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_36_00_00.pdf |
| WA-CR-26-G | Wash. Super. Ct. Civ. R. 26(g) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_26_00_00.pdf |

Confirm: answer-or-objection-with-reasons form; no general objections; CR
26(g) signing/specificity. **Precision item F2-N1:** confirm CR 34(b)(3) is
the response/objection subdivision (the prose cites (b)(3); the pack cites
(b) broadly).

### Cluster 4 — WA CR protective orders (primary: courts.wa.gov PDFs)

| Rule id | Citation | Source URL |
|---|---|---|
| WA-CR-26-C | Wash. Super. Ct. Civ. R. 26(c) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_26_00_00.pdf |
| WA-CR-26-I | Wash. Super. Ct. Civ. R. 26(i) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_26_00_00.pdf |
| WA-CR-37-A-4 | Wash. Super. Ct. Civ. R. 37(a)(4) | https://www.courts.wa.gov/court_rules/pdf/CR/SUP_CR_37_00_00.pdf |

Confirm: good cause; "any order justice requires"; 8 enumerated directions;
CR 26(i) certification; CR 37(a)(4) expenses on the motion.

### Cluster 5 — Implementation mapping (code, not citation)

Confirm `select_statute` in `scripts/objection_motion.py` produces:

- objection/CA: rog→CCP-2030-240, rfp→CCP-2031-240, rfa→CCP-2033-230
- objection/WA: rog→WA-CR-33-A(+WA-CR-26-G), rfp→WA-CR-34-B(+WA-CR-26-G), rfa→WA-CR-36-A(+WA-CR-26-G)
- protective_order/CA: rog→CCP-2030-090, rfp→CCP-2031-060, rfa→CCP-2033-080 (+CCP-2017-020, CCP-2016-040)
- protective_order/WA: all→WA-CR-26-C (+WA-CR-26-I, WA-CR-37-A-4)
- refusal when the controlling statute is absent from the loaded pack.

### Cluster 6 — Scope boundary (precision item F2-N3)

Confirm F2 request types are rog/rfp/rfa only and that `CCP-2025.420`
(deposition PO) is documented authority but **not** an exposed F2 lever. A
deposition PO lever would be a separate slice.

## 4. Deliverables from Codex

A single `F2_CROSSCHECK_REPORT.md` committed to the Codex worktree under
`autonomous_review/codex_f2_verification/`, containing:

- Per-cluster verdict (CONFIRMED / DIVERGENCE / DEFECT) with the primary
  source URL used and a one-line basis.
- For each of F2-N1, F2-N2, F2-N3: a CONFIRMED / CORRECTION verdict with the
  exact subdivision text quoted from the primary source.
- Any new defects found, classified HIGH / MEDIUM / LOW with the exact file
  and line where the defect manifests and a proposed fix.
- A final roll-up: merge-ready / merge-with-corrections / blocked.

**Source URL policy:** for statutory clusters (1-4), cite the primary
government source (leginfo section page; courts.wa.gov rule PDF). For any
case law Codex introduces, cite a court-published opinion or reliable mirror
plus reporter-text confirmation — not an "official portal only" claim.

## 5. Reproduction commands (Codex worktree)

```powershell
# Selftest (12 lever x type combos, CA + WA)
python skills/legal/discovery-workflow/scripts/objection_motion.py selftest

# Dedicated pytest file
python -m pytest tests/skills/test_discovery_objection_motion.py --basetemp .pytest_tmp -q

# Whitespace / hygiene
git diff --check
```

## 6. Out of scope

- F1 (enforcement levers) — already merged to main; do not re-litigate.
- Live matter runs; owner §9.5; `OWNER_LIVE_GATE_F2*.md` signing.
- Core toolset changes; umbrella `discovery_workflow.py` DISPATCH wiring
  (F1 was deliberately shipped without umbrella wiring; F2 mirrors that).
