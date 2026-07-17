# Custom Hermes Main — Cleanup & Merge Plan

**Date:** 2026-07-16
**Target:** one local `main` = current `origin/main` + kept custom delta
**Source tip:** `local/finalize-legal-discovery-skills-20260707` @ `3ea7bd224`
**Upstream tip:** `origin/main` @ `bd37ff913`
**Divergence:** +42 / −1152 commits · 144 files · +21,050 / −452 lines
**Merge-base:** `830165473` (2026-07-06)

> Panel note: Opus / GPT-Sol / Fable / GLM / Terra seats hit API limits (empty).
> **Composer** — conflict risk **8/10**, merge-tree **22** overlaps, NO-GO rebase.
> **Grok overlap** — high-value FABLE5/gateway/agent patches are **still needed**
> (not superseded); related main work is only thematic. Confirms
> **extract-skills-first**, then a **sequenced Phase-2 cherry-pick campaign**
> for core (do not rebase-all).

---

## Scope and impacted surfaces

| Bucket | Paths | Role in final main |
|--------|--------|--------------------|
| Legal product | `skills/legal/**` (casegraph, matter-mail, discovery-intake/review, medical-chronology, deposition-outline, scripts, templates) | **KEEP** — primary customization |
| Legal tests | `tests/skills/test_*.py` for those skills | **KEEP** |
| Pilot harness | `pilot/**`, `tests/pilot/**`, `scripts/validate_legal_discovery_skills.py` | **KEEP** (local ops; not upstream-bound) |
| Compat scanner | `skills/software-development/hermes-compat-scanner/**` | **KEEP** (already on feature tip) |
| Core hardening | `gateway/run.py`, `run_agent.py`, `agent/*`, `tools/*`, `hermes_cli/config.py` | **DO NOT blind-rebase** — extract/re-validate selectively |
| Root process docs | `LEGAL_*.md`, `MODEL_ROUTING_POLICY_LEGAL.md`, `PROVIDER_TOKEN_INVENTORY_REDACTED.md` | **PARK** out of git or move under `pilot/docs/` |
| Debris | `CODEX_*.md`, `MATTER_MAIL_*.md`, `.cache/`, `.tmp-pytest/` | **NEVER merge** |
| Dirty WIP | `casegraph.py`, `eval_faithfulness.py`, `test_casegraph.py` | **Commit or stash before any rewrite** |

### Other local branches

| Branch | Disposition |
|--------|-------------|
| `main` @ `830165473` | Stale; will be replaced by new final main |
| `local/reapply-compat-scanner-on-main-20260707` | Ancestor of feature; no unique work |
| `local/promote-devlab-compat-scanner-20260706` | 1 unique commit; tip already has scanner files — ignore unless diff proves extras |
| Feature branch | Retain as immutable backup tag after cutover |

---

## Verdict (recommended strategy)

**Extract-skills-first, then selective core cherry-picks — not rebase-all.**

Why:

1. `gateway/run.py` has **71** upstream commits since merge-base; `run_agent.py` **28**; `agent/conversation_loop.py` **29**. Replaying local gateway/agent patches across that churn is high conflict and high regression risk.
2. Composer panel: `git merge-tree` predicts **22 “changed in both”** files on a rebase attempt — including every hot path. Immediate rebase is **NO-GO** until WIP is clean and a multi-hour conflict budget exists; even then, extract-skills-first avoids replaying ~16 gateway/agent commits through that churn.
3. Worst expected manual merges if you did rebase: `agent/auxiliary_client.py`, `agent/chat_completion_helpers.py` (main rewrote aux routing; feature rewrote same call sites).
4. ~62 of 144 changed paths are under `skills/` — the real product delta is skill-shaped and AGENTS.md-aligned (capability at the edges).
5. Several “core” commits exist to keep long legal jobs alive (MCP late refresh, heartbeats, timeouts). Upstream may have partial equivalents; each must be re-proven on new main, not assumed.
6. `hermes update` alone will hard-reset to stock main and **drop** the running custom tip from HEAD (branch tip preserved only if you keep the feature branch/tag).

**If you insist on rebase later:** stash `-u` → backup branch → `git rebase origin/main` → resolve per commit → squash **after** clean rebase (not before). Prefer the extract path in §Ordered cleanup steps instead.

---

## Keep / Rebase / Drop matrix

| Item | Decision | Notes |
|------|----------|-------|
| Legal skills + scripts + tests | **KEEP → transplant** | Cherry-pick/copy onto fresh main |
| Pilot harness + validators | **KEEP → transplant** | Local ops tooling |
| hermes-compat-scanner | **KEEP** | Already in feature tip |
| Root `LEGAL_*.md` / token inventory | **PARK** | Process artifacts; don’t clutter main root (token inventory especially) |
| Dirty WIP on casegraph / faithfulness | **COMMIT first** | Then include in transplant |
| Untracked CODEX_/MATTER_MAIL_ reports | **DROP** | Exclude from all commits |
| Gateway long-job / MCP late-refresh (`888b1e5f8`, `cc21de3af`) | **PHASE 2 KEEP** | Symbols absent on main; TUI has partial late-refresh only |
| Public run.py surface + config_helpers (L8/M14) | **PHASE 2 KEEP** | `apply_gateway_process_env` / `config_helpers.py` absent on main |
| Event-loop / silent failure (M20/L7), /steer merge (M15) | **PHASE 2 KEEP** | Thematic cousins on main; invariants not replaced |
| Aux identity / stream / fallback stack (L4, M2/M6, M16/M17, H9–H11) | **PHASE 2 KEEP** | Highest conflict; cherry-pick after gateway surface stabilizes |
| skills_guard scan bypasses (`f7076925f`) | **PHASE 2 KEEP** | Related provenance work on main ≠ this bypass fix |
| Approval timeout 1800 vs main ~60 (`6051d9ee0` slice) | **PHASE 2 DESIGN CALL** | Not a clean upstream; decide intentionally |
| Sibling compat-scanner promote branch | **DROP** | Duplicate of tip content |

---

## Recommended final branch topology

```
origin/main (bd37ff91…)
    └── main                      ← FINAL local production tip (FF to origin/main, then custom commits)
         └── (theme commits)
              1. legal-skills
              2. legal-tests + pilot
              3. optional core patches (only if still needed)
backup/legal-finalize-3ea7bd224   ← annotated tag of today’s feature tip (immutable)
local/finalize-…                  ← leave untouched until cutover verified
```

**Name:** keep calling production branch `main` (matches `hermes update`).
**History style:** prefer **2–4 thematic commits** on top of upstream, not a 42-commit rebase replay.
**Do not** squash away the backup tag.

---

## Ordered cleanup steps

### 0. Preconditions (rollback: none needed)

1. Quit all `hermes` / gateway / desktop processes (Windows file locks).
2. Commit or stash dirty WIP on the feature branch.
3. Ensure `.gitignore` already covers caches (feature has a commit for this); do not add CODEX reports.

### 1. Freeze backups (rollback: delete tags only)

```powershell
cd C:\Users\Prime\AppData\Local\hermes\hermes-agent
git fetch origin main
git tag -a backup/legal-finalize-3ea7bd224 -m "Pre-cutover feature tip" 3ea7bd224
git branch backup/pre-cutover-main main
```

### 2. Build a clean integration branch from upstream

```powershell
git checkout -B main origin/main
git checkout -b integrate/custom-legal-main
```

### 3. Transplant product surface (skills-first)

Preferred mechanical path (lowest conflict):

```powershell
# From feature tip, export keepers into the integration branch
git checkout backup/legal-finalize-3ea7bd224 -- `
  skills/legal `
  skills/software-development/hermes-compat-scanner `
  tests/skills `
  pilot `
  tests/pilot `
  scripts/validate_legal_discovery_skills.py `
  .gitignore

# Optionally relocate process docs instead of root clutter:
# git checkout backup/legal-finalize-3ea7bd224 -- LEGAL_*.md MODEL_ROUTING_POLICY_LEGAL.md
# then git mv into pilot/docs/

git commit -m "feat(legal): import customized legal discovery skill surface"
```

Alternative if you want commit attribution: `git cherry-pick` only the legal-themed SHAs (skip gateway/agent SHAs). Expect conflicts on any commit that touched both legal + gateway (e.g. `6051d9ee0`).

### 4. Run legal verification on new base

```powershell
scripts/run_tests.sh tests/skills/test_casegraph.py tests/skills/test_matter_mail.py `
  tests/skills/test_legal_discovery_validator.py tests/skills/test_eval_faithfulness.py `
  tests/skills/test_scaffold_matter.py tests/skills/test_live_preflight.py `
  tests/skills/test_ocr_from_queue.py tests/skills/test_loadfile_to_manifest.py `
  tests/skills/test_medical_chronology_skill.py tests/skills/test_deposition_outline_skill.py `
  tests/pilot/ -q
```

Fix skill/test breakages from upstream API drift **before** any core cherry-picks.

### 5. Phase 2 — sequenced core cherry-picks (separate campaign)

Grok audit: these patches are **still needed** on current main (not superseded).
Do **not** rebase-all. After Phase 1 (skills/pilot) is green, cherry-pick in this
dependency order — one cluster at a time, with tests after each:

1. M14 `gateway/config_helpers.py` + env deferral (`d708841b9` / pieces of `168f84ba5`)
2. L8 public aliases + reach-in tests (`168f84ba5`, `dc6c6a02d`)
3. Long-job / completion / process_registry / tool_result_storage (`888b1e5f8`)
4. MCP late-refresh + lifetime gate (`cc21de3af`)
5. M20 hooks + L7 persist notice (`17e9e9717`)
6. Aux L4/M2/M6 + stream/fallback H9–H11/M16/M17 (`291fefe95` … `4a8273c31`)
7. Security `skills_guard` (`f7076925f`)
8. M15 `/steer` merge last (`0698696b5`) — after busy-queue settles
9. **Design call:** approval timeout 1800 vs main’s canonical ~60 (`6051d9ee0` slice)

Before each cluster: note the invariant you are preserving. Main’s
`to_thread` / busy-queue / TUI MCP refresh / durable delegation are **cousins**,
not substitutes — do not drop a pick solely because a thematic cousin exists.

### 6. Cut over local `main`

```powershell
git checkout main
git merge --ff-only integrate/custom-legal-main
# optional: delete integrate branch after success
```

### 7. Refresh install without destroying custom main

Prefer:

```powershell
git pull --ff-only origin main   # only if you also push; else skip
# sync deps from the checkout you are on:
hermes update
```

**Caution:** if `hermes update` finds divergence it may `reset --hard origin/main` and wipe unpushed custom commits from `main`. Before running it, either:

- ensure custom commits are pushed to a remote you control, **or**
- run update only when `main` is a fast-forward of `origin/main` plus your commits (ff-only pull of origin into main will fail safely if you haven’t merged yet — but reset path is dangerous), **or**
- temporarily update via manual `git merge origin/main` + dep sync while staying on your tip.

Safest post-cutover habit: **never let `hermes update` run while `main` has unique commits unless those commits are pushed/backed up.**

### 8. Retire stale branches (after 1–2 good days)

- Keep tag `backup/legal-finalize-3ea7bd224`
- Delete obsolete locals: `local/finalize-…`, `local/promote-…`, `local/reapply-…`, `backup/pre-cutover-main` when confident

---

## Verification plan

| Gate | Command / check |
|------|-----------------|
| Banner health | `hermes chat` shows near-0 commits behind; carried count = your theme commits only |
| Legal unit | `scripts/run_tests.sh` list in step 4 |
| Skills load | Banner lists legal skills; `/skills` or skill scan sees casegraph/matter-mail |
| Long job smoke | One background OCR/build with `notify_on_complete` on Windows |
| No debris | `git status` clean of CODEX_/cache artifacts |
| Core invariant | Prompt-cache / toolset mid-session mutation: if you kept MCP patch, run `tests/gateway/test_mcp_late_refresh.py` |

---

## Risks and rollback

| Risk | Mitigation |
|------|------------|
| Rebase-all destroys hours in `gateway/run.py` conflicts | Use extract-skills-first |
| `hermes update` hard-reset drops custom main | Tag + branch backup; avoid update until tip is saved |
| Windows venv locks mid-update | Close hermes/desktop/gateway first; use `--force` only if you accept risk |
| Silent loss of dirty WIP | Commit/stash before checkout |
| Token inventory in git | Keep redacted file out of shared remotes; prefer local-only |
| Upstream skill sync overwriting legal skills | Legal skills are custom — confirm `sync_skills` treats them as user/bundled correctly; pin/user-modified if needed |
| Core patches “feel important” but are obsolete | Require failing repro on new main before cherry-pick |

**Rollback:** `git checkout -B main backup/legal-finalize-3ea7bd224` (returns to pre-cutover tip; you will be behind upstream again).

---

## Questions for you (before execution)

1. Should root process docs (`LEGAL_*.md`, routing/token inventories) live on `main` under `pilot/docs/`, or stay only on the backup tag?
2. Do you want a **private remote** backup of the final custom `main`, or local tags only?
3. Phase 2 timing: run core cherry-picks **immediately after** skills transplant, or park them on `backup/…` and schedule a dedicated FABLE5 port day?
4. Approval timeout: keep legal long-job **1800s** helper, or adopt main’s canonical ~60s and compensate another way?

---

## Execution readiness

- **Plan status:** ready to execute Phase 1 after answers (defaults: park docs under `pilot/docs/`, local tag backup, Phase 2 core port as a dedicated follow-up day).
- **Do not run** `hermes update` as the cutover mechanism for this customization.
- **Next command when approved:** step 0–1 (quit hermes, commit WIP, create backup tag).
- **Panel complete:** Composer + Grok seats landed; other multi-model seats API-limited.
