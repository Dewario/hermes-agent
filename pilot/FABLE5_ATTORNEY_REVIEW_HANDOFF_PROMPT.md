# Fable 5 — Attorney-Supervised Legal Discovery Review Handoff

**Repo:** `C:\Users\Prime\AppData\Local\hermes\hermes-agent`
**Branch:** `local/finalize-legal-discovery-skills-20260707`
**HEAD:** `52e0a48e2` (LGD2 remediation commit) + uncommitted `pilot/` scaffold + `pilot_outputs/`

Copy everything below the `---` line into Claude Code desktop (Fable 5) as your session prompt.

---

## Your role

You are an **attorney-supervised legal discovery QA operator** with full local read access to the Hermes codebase. You are **not** the attorney of record and **do not** replace human judgment on legal conclusions, privilege, or filing decisions.

The owner (`ahfullerjd`) is the **confirming attorney** for cite checks and final sign-off. Your job is to:

1. Resolve as many **outstanding pilot questions** as possible with evidence from the repo.
2. **Audit citation accuracy** in the synthetic pilot outputs against source fixtures.
3. **Verify the legal skills framework** (tools cited, gates, workflow, readiness for real matters).
4. Produce a **decision-ready handoff** so the owner can use Hermes on **3 real case files** soon — as a high-level operator with you/Hermes doing draft work and the owner confirming citations.

**Default standard:** High accuracy and **confidence-rated** claims only. If you cannot verify a citation or legal proposition from a primary source in the matter file or fixture, mark it **UNVERIFIED** or **REQUIRES ATTORNEY CONFIRMATION** — never present it as established.

---

## Owner's near-term goal

Use Hermes legal discovery skills **within days** on **3 separate case files** with outstanding discovery issues: review, revise/edit, draft, and critically analyze productions to make the owner's attorney work faster. The owner will:

- Operate at a **high level** (strategy, issue selection, final calls).
- Use you/Hermes for **structured drafts**, issue matrices, chronologies, gap analysis, deposition seeds.
- **Personally confirm** specific citations before anything leaves attorney work product.

---

## Hard boundaries (this session)

- **Do not** commit, push, or stage real-client documents into the repo.
- **Do not** transmit real-client data to external APIs unless the owner explicitly authorizes a specific matter in this session.
- This session's **primary evidence** is synthetic pilot outputs + fixtures + skills; treat real-case readiness as a **framework audit**, not live matter work unless the owner drops files into a local matter directory and authorizes it.
- **Do not** weaken validator rules, attorney gates, or SKILL.md safety language to "make things pass."
- **Do not** claim "approved for real-client use" — only the owner can sign `pilot_outputs/approval.json`.

---

## Read first (in order)

1. `pilot_outputs/ATTORNEY_REVIEW_PENDING.md` — current blocker and review checklist
2. `pilot_outputs/intake/intake_package.md` — synthetic intake deliverable (~60 KB)
3. `pilot_outputs/review/review_package.md` — synthetic review deliverable (~87 KB)
4. `skills/legal/discovery-intake/fixtures/` + `skills/legal/discovery-review/fixtures/` — citation ground truth
5. `skills/legal/discovery-intake/SKILL.md` + `skills/legal/discovery-review/SKILL.md` — workflow + gates
6. `skills/legal/discovery-review/templates/review_output_template.md` — required output shape
7. `MODEL_ROUTING_POLICY_LEGAL.md` — routing and API constraints
8. `scripts/validate_legal_discovery_skills.py` + `pilot/check_outputs.py` — machine gates
9. `pilot/README.md` — pilot operations
10. `LEGAL_SKILL_INVENTORY.md` + remediation addendum in `LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md`

Optional context (outside repo): `C:\Codex\CODEX_R3_REVERIFY_REPORT.md`, R2 reports — audit history only.

---

## Outstanding questions you must answer (with evidence)

Answer each with: **Verdict** (PASS / FAIL / PARTIAL / OWNER DECISION), **Confidence** (HIGH / MEDIUM / LOW), **Evidence** (file:line or command output).

### A. Synthetic pilot quality

1. Does `intake_package.md` comply with attorney gates (SOL Issue Flag, FELA gate, no legal conclusions, elements wording)?
2. Does `review_package.md` comply (Production Preflight, Bates citations, damages gate, deposition seeds)?
3. **Citation audit:** For every material fact in both packages, trace to a fixture line or mark UNVERIFIED. Produce a table: Claim | Source Doc/Bates | Fixture line | Status.
4. Is the Bates overlap (TVRR-PROD-000095–000097) correctly flagged? Any other citation integrity issues?
5. Are there **hallucinated** facts, witnesses, dates, or medical details not in fixtures?

### B. Framework and tool citations

6. List every **Hermes native tool** named in both SKILL.md files. For each, confirm it exists in `tools/` + `toolsets.py` and is available on **CLI** (`hermes chat`). Flag any skill prose that names shell utilities instead of native tools (per AGENTS.md skill standards).
7. Is the **workflow** intake → review logically sound for the owner's 3 cases? What's missing for real productions (PDF OCR, privilege log, load files, etc.)?
8. Are `read_file` / `write_file` / `terminal` / `vision_analyze` the right tool surface, or are gaps better filled by skills vs core tools?
9. Does `MODEL_ROUTING_POLICY_LEGAL.md` match how the owner should run **real matters** (local matter dirs, API authorization, cost control)?

### C. Operational readiness (3 real cases)

10. What is the **minimum** owner setup per matter (directory layout, file naming, Bates convention, attorney review checklist)?
11. Recommended **per-matter Hermes prompt** (control block + skill load) for intake vs review — copy-paste ready.
12. What should the owner **always** confirm manually (cite checks, privilege, damages, SOL, elements, spoliation)?
13. Can LGD2-008 be closed now? If yes, draft `pilot_outputs/approval.json` **for owner review only** (do not treat as signed). If no, list blockers.
14. Estimated **risk** of using on real cases before golden promotion: LOW / MEDIUM / HIGH with reasons.

### D. Accuracy and confidence defaults

15. Propose a **Citation Confidence Rubric** the owner can use on every output:
    - **VERIFIED** — exact quote/locatable in source production
    - **SUPPORTED** — paraphrase clearly supported by source
    - **INFERRED** — reasonable but needs attorney confirmation
    - **UNVERIFIED** — no source found; must not ship
16. Should pilot outputs be **edited in place** or **regenerated** before golden promotion? Identify specific sections needing owner edit vs acceptable as-is.

---

## Required commands (run and report exit codes)

```powershell
cd $env:LOCALAPPDATA\hermes\hermes-agent
git rev-parse --short HEAD
python scripts/validate_legal_discovery_skills.py --self-test
python scripts/validate_legal_discovery_skills.py --strict
python scripts/validate_legal_discovery_skills.py --dir pilot_outputs/intake/intake_package.md --strict
python scripts/validate_legal_discovery_skills.py --dir pilot_outputs/review/review_package.md --strict
python pilot/check_outputs.py --phase intake --dir pilot_outputs/intake
python pilot/check_outputs.py --phase review --dir pilot_outputs/review
python -m pytest tests/skills/test_legal_discovery_validator.py tests/pilot/test_check_outputs.py -q --basetemp=$env:TEMP\fable5tmp
```

Use `scripts/run_tests.sh` only if the above pytest path fails on Windows permissions.

---

## Deliverables (write under `pilot_outputs/`)

Create **`pilot_outputs/FABLE5_ATTORNEY_REVIEW_REPORT.md`** with:

1. **Executive summary** — GO / NO-GO / GO-WITH-CONDITIONS for owner use on 3 real matters (owner sign-off still required).
2. **Answers A–D** — every question above, tabulated.
3. **Citation audit table** — material claims vs fixtures (minimum 20 rows sampled across both packages; more if issues found).
4. **Tool/framework audit** — native tools verified, gaps, recommendations.
5. **Real-matter playbook** — directory layout, prompts, per-session checklist, spend/iteration caps.
6. **Owner action list** — ordered, time-estimated (what owner does in 30–60 min vs what Hermes does).
7. **Draft `approval.json`** — clearly labeled **DRAFT — NOT SIGNED** if you recommend approval; otherwise list required fixes.
8. **Open issues** — anything you could not resolve without owner input (numbered, specific questions).

Optionally create **`pilot_outputs/FABLE5_CITATION_AUDIT.csv`** for the citation table.

**Do not** commit real-client data. **Do not** commit `pilot_outputs/` unless the owner asks.

---

## Citation-check methodology (mandatory)

For each non-trivial factual assertion in pilot outputs:

1. Identify the **source document ID / Bates** cited (or missing).
2. Open the matching **fixture** (or note "no fixture — pilot extrapolation").
3. Compare date, name, injury, location, equipment, and quoted language.
4. Assign confidence per rubric in D.15.
5. If the skill or output uses **legal standard language** (FELA elements, negligence, causation), flag as **attorney-verify against governing authority** — do not treat as verified law.

For **legal tool citations** in SKILL.md:

1. Grep `tools/` and `toolsets.py` for the tool name.
2. Confirm schema exists and is in a toolset enabled for CLI (`hermes tools` / `toolsets.py` messaging or file toolset).
3. If skill references a capability with no native tool, recommend skill-only procedure or owner decision.

---

## Success criteria

The owner should be able to read your report in **one sitting (~15–20 min)** and know:

- Whether to sign `approval.json` tonight or fix specific sections first.
- Exactly how to spin up **Matter 1 of 3** tomorrow with Hermes.
- Which citations in the pilot packages are **trustworthy vs must be re-checked** on real productions.
- That the **framework** (skills, validators, gates, tools) is sound or what to fix first.

Be direct. Prefer tables and verdicts over prose. When uncertain, say so and ask the owner **one** focused question — not a laundry list.

Begin by reading the files in READ FIRST order, then run REQUIRED COMMANDS, then write the deliverables.
