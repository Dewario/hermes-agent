# Batched plan: merge custom work → one `main` → retire local branches

**Goal:** One local `main` = current `origin/main` + full custom functionality (legal skills, pilot, compat scanner, FABLE5/gateway hardening), then delete obsolete local branches and debris folders — **no loss of function, efficiency, or consistency**.

**Strategy:** extract-skills-first (Batch A–C), then sequenced core cherry-picks (Batch D), then retire branches (Batch E). **Do not** `git rebase` the 42-commit feature tip onto main. **Do not** use `hermes update` as the merge tool (it can `reset --hard origin/main`).

| Ref | SHA / tip |
|-----|-----------|
| Feature (source of truth today) | `local/finalize-legal-discovery-skills-20260707` @ `3ea7bd224` |
| Upstream | `origin/main` (fetch at start of each batch; ~1153 ahead of stale local main) |
| Stale local `main` | `830165473` — will be overwritten in Batch B |
| `local/reapply-compat-scanner-on-main-20260707` | Ancestor of feature — **no unique commits** |
| `local/promote-devlab-compat-scanner-20260706` | Duplicate scanner patch (different SHA) — **skip** |

**Defaults baked into this plan** (override before Batch B if needed):

1. Root process docs → `pilot/docs/` on final main (not repo root clutter).
2. Backup = local annotated tags (optional private remote later).
3. Phase 2 core = full sequenced cherry-pick (not “drop unless repro”).
4. Approval timeout: **keep 1800s** legal/messaging helper when that pick lands (document the intentional diverge from main’s ~60s canonical).

---

## Batch map

```
A  Freeze & sanitize     → nothing deleted yet; WIP + tags safe
B  Fresh main + transplant skills/pilot/scanner (+ parked docs)
C  Verify legal surface  → must be green before any core picks
D  Core cherry-picks     → 9 ordered clusters; preserve long-job efficiency
E  Cutover & retire      → only main + backup tags remain
```

Each batch has: **inputs → steps → done when → rollback**. Do not start the next batch until “done when” is true.

---

## Batch A — Freeze & sanitize (≈15 min)

**Inputs:** Feature branch checked out; hermes/desktop/gateway **stopped**.

### Steps

1. Stop concurrent Hermes processes (Windows locks).
2. On feature branch, commit dirty WIP (must not be lost):
   - `skills/legal/casegraph/scripts/casegraph.py`
   - `pilot/eval_faithfulness.py`
   - `tests/skills/test_casegraph.py`
3. Leave untracked debris **uncommitted**:
   - `.cache/`, `.tmp-pytest/`
   - `CODEX_*.md`, `MATTER_MAIL_*.md`
4. Optionally delete debris folders from disk after confirming they are not needed (they are regenerable / reports).
5. Commit this plan file if you want it on the backup tip (`BRANCH_MERGE_BATCH_PLAN.md`, `implementation-plan.md`) — or keep them only locally until Batch B.
6. Create immutable backups:

```powershell
cd C:\Users\Prime\AppData\Local\hermes\hermes-agent
git fetch origin main
git tag -a backup/pre-merge-feature-20260716 -m "Full custom tip before main cutover" HEAD
git branch backup/branch-pre-merge-feature-20260716 HEAD   # distinct from tag name (avoids ambiguous ref)
git branch backup/stale-main-830165473 main
```
**Batch A status (2026-07-16):** complete @ `c036d7b5f` — WIP + plans committed; tag
`backup/pre-merge-feature-20260716` and branch `backup/branch-pre-merge-feature-20260716`
point at that tip; stale main saved; debris deleted from disk.

**Red-team (pre-B):** GO-WITH-FIXES — do **not** blind-checkout `.gitignore` in Batch B
(merge legal/pilot ignore lines onto `origin/main` base). Fix incremental Bates
header-vs-filename widen in `cmd_build` before trusting live matter indexes (can
land as Batch B+ hotfix or before Batch C). See panel notes in chat 2026-07-16.

### Done when

- [ ] `git status` shows clean tracked tree (or only intentional untracked debris).
- [ ] Tag `backup/pre-merge-feature-20260716` exists and points at feature tip (incl. WIP commit).
- [ ] No hermes.exe holding the venv.

### Rollback

`git reset --hard backup/pre-merge-feature-20260716` on the feature branch.

### Branch disposition this batch

None deleted.

---

## Batch B — Build integration tip (transplant, no core yet)

**Inputs:** Batch A complete. Working from a new branch off `origin/main`.

### Steps

```powershell
git fetch origin main
git checkout -B integrate/custom-main origin/main
$src = "refs/tags/backup/pre-merge-feature-20260716"

# Product surface from frozen tip — NEVER blind-checkout .gitignore
git checkout $src -- `
  skills/legal `
  skills/software-development/hermes-compat-scanner `
  tests/skills `
  pilot `
  tests/pilot `
  scripts/validate_legal_discovery_skills.py

# Surgical ignore merge: keep origin/main base, append legal/pilot lines only
Add-Content -Path .gitignore -Value @"

# Legal discovery pilot ephemeral outputs
pilot_outputs/
pilot/COMMAND_LEDGER.jsonl
.pytest_tmp/
# Local codegraph / Shadow index cache (not source)
.codegraph/
# LGD2-008 goldens under legal discovery skills (exception to examples/ ignore)
!skills/legal/discovery-intake/examples/
!skills/legal/discovery-intake/examples/**
!skills/legal/discovery-review/examples/
!skills/legal/discovery-review/examples/**
"@

# Park process docs under pilot/docs/
git checkout $src -- `
  LEGAL_DISCOVERY_FINALIZATION_REPORT.md `
  LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md `
  LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md `
  LEGAL_SKILL_INVENTORY.md `
  MODEL_ROUTING_POLICY_LEGAL.md `
  PROVIDER_TOKEN_INVENTORY_REDACTED.md `
  BRANCH_MERGE_BATCH_PLAN.md `
  implementation-plan.md

New-Item -ItemType Directory -Force pilot/docs | Out-Null
foreach ($f in @(
  "LEGAL_DISCOVERY_FINALIZATION_REPORT.md",
  "LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md",
  "LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md",
  "LEGAL_SKILL_INVENTORY.md",
  "MODEL_ROUTING_POLICY_LEGAL.md",
  "PROVIDER_TOKEN_INVENTORY_REDACTED.md",
  "BRANCH_MERGE_BATCH_PLAN.md",
  "implementation-plan.md"
)) { git mv -f $f "pilot/docs/$f" }

git add -A
git status --short
# assert: no LEGAL_*.md / PROVIDER_* at repo root; mcp oauth skill test still present
git commit -m "feat(custom): import legal skills, pilot harness, compat scanner"
```

**Do not** checkout `gateway/`, `agent/`, `tools/`, `run_agent.py`, or wholesale `.gitignore` in this batch.

### Done when

- [ ] `integrate/custom-main` = `origin/main` + one (or few) transplant commit(s).
- [ ] `skills/legal/**` and `hermes-compat-scanner` present.
- [ ] Root has no `LEGAL_*.md` / token inventory (they live under `pilot/docs/` or were intentionally omitted).
- [ ] No CODEX_/cache files staged.

### Rollback

```powershell
git checkout local/finalize-legal-discovery-skills-20260707
git branch -D integrate/custom-main
```

Feature tip untouched via backup tag.

### Functionality preserved so far

Legal/pilot/scanner **files** present. Runtime long-job/gateway efficiency patches **not yet** — that is Batch D (required before declaring “complete”).

---

## Batch C — Legal / pilot consistency gate (must pass)

**Inputs:** On `integrate/custom-main`.

### Steps

```powershell
scripts/run_tests.sh `
  tests/skills/test_casegraph.py `
  tests/skills/test_matter_mail.py `
  tests/skills/test_legal_discovery_validator.py `
  tests/skills/test_eval_faithfulness.py `
  tests/skills/test_scaffold_matter.py `
  tests/skills/test_live_preflight.py `
  tests/skills/test_ocr_from_queue.py `
  tests/skills/test_loadfile_to_manifest.py `
  tests/skills/test_medical_chronology_skill.py `
  tests/skills/test_deposition_outline_skill.py `
  tests/skills/test_check_provider_auth.py `
  tests/skills/test_docling_extract.py `
  tests/pilot/ -q
```

Fix any upstream API drift **in skill/test/pilot code only** (commit on `integrate/custom-main`). Do not “fix” by pulling old `gateway/run.py` yet.

Optional smoke: `hermes chat` once from this checkout — legal skills should list; banner should be ~0 behind if HEAD tracks origin tip + transplant only.

### Done when

- [x] Above test list green.
- [x] No skill frontmatter regressions introduced (descriptions already ≤60 chars).

**Batch C status (2026-07-17):** GREEN on `integrate/custom-main` @ `3bb391f1a` —
191 passed, 2 skipped (Windows venv pytest; WSL `run_tests.sh` could not see venv).
One test fix landed: OCR `recommended_action` assertion matches extract status.
Note: branch is ahead 2 / behind ~47 vs `origin/main` — rebase/merge before or during Batch D/E.

### Rollback

Revert fix commits on `integrate/custom-main`, or reset integrate to post–Batch B commit.

---

## Batch D — Core hardening (efficiency + consistency) — sequenced

**Why this batch is required for “no loss”:** Panel audit found FABLE5/gateway/agent patches **still absent** on `origin/main` (long-job survival, MCP late-refresh lifetime gate, public run.py surface, /steer merge, aux identity, skills_guard bypasses, etc.). Skills alone would lose long-job efficiency and several consistency invariants.

**Inputs:** Batch C green. Still on `integrate/custom-main`. Budget several focused sessions (not one mega-rebase).

**Batch D1 status (2026-07-17):** GREEN @ `032613cfe` / tag `batch-d1-green` — cherry-picked `d708841b9` (resolved `gateway/relay/__init__.py`; also migrated new main IdP config path off `gateway.run`). Tests: 41 passed (`test_config_helpers_m14` + relay policy/self-provision).

**Batch D2 status (2026-07-17):** GREEN @ tag `batch-d2-green` — cherry-picked `dc6c6a02d` + `168f84ba5` (slash_commands conflict: kept main multiplex/reasoning/fast-picker; used L8 public APIs). Follow-up: public `profile_runtime_scope` wrapper + consumers (`api_server`, `slash_commands`) off privates. Tests: 41 passed (`test_run_public_surface_l8` + `test_config_helpers_m14`).

**Batch D3 status (2026-07-17):** GREEN @ tag `batch-d3-green` — cherry-picked `888b1e5f8`. Conflicts: kept main `_deliver_completion_notification` + routing metadata; set `tried_agent_notify` and fall through to user send on inject `False` (no silent drop); kept `approvals.gateway_timeout` 1800s (not CLI `timeout` 60s). Also landed process.wait no-clamp + activity heartbeats, head+tail tool previews, MCP late-refresh test file (D4 may be partial/no-op). Tests: 123 passed (long-job heartbeats, background notifications, tool_result_storage, L8).

Cherry-pick **from** `backup/pre-merge-feature-20260716` **onto** `integrate/custom-main`, one cluster at a time. After each cluster: run the matching tests listed.

| Cluster | Commits (primary) | Tests after pick | Invariant to keep |
|--------:|-------------------|------------------|-------------------|
| D1 | `d708841b9` (+ env pieces of `168f84ba5` if needed) | `tests/gateway/test_config_helpers_m14.py` | Side-effect-free config read |
| D2 | rest of `168f84ba5`, `dc6c6a02d` | `tests/gateway/test_run_public_surface_l8.py` | Public gateway surface / deferred process env |
| D3 | `888b1e5f8` | `tests/tools/test_long_job_heartbeats.py`, `tests/gateway/test_background_process_notifications.py`, related tool_result/process_registry tests | Long jobs don’t silently drop |
| D4 | `cc21de3af` | `tests/gateway/test_mcp_late_refresh.py` | No mid-session toolset mutation (prompt cache) |
| D5 | `17e9e9717` | `tests/gateway/test_hooks_offloop_m20.py`, `tests/run_agent/test_persist_failure_notice_l7.py` | Off-loop hooks / failure surfacing |
| D6 | `291fefe95`, `2f3406af9`, `d7619f848`, `e65f6819d`, `dc64bcd79`, `4a8273c31`, `50717be7b`, `e36a74506` | `tests/agent/`, `tests/run_agent/` targeted | Aux identity + stream/fallback integrity |
| D7 | `f7076925f` | `tests/tools/test_skills_guard.py`, `tests/agent/test_file_safety.py` | Skill-install / shell-rc gap closed |
| D8 | `0698696b5` | `tests/gateway/test_steer_command.py` | /steer merges pending, doesn’t clobber |
| D9 | approval/timeout slice from `6051d9ee0` (and any qqbot bits still required) | `tests/tools/test_gateway_approval_timeout.py`, `tests/tools/test_mcp_elicitation.py` | **Keep 1800s** for legal long jobs (document diverge) |

### Conflict rules (consistency)

- Prefer **semantic merge**: keep main’s new multiplex/delegation paths; re-apply *your* invariant (lifetime counter, take-queued-completion, config_helpers, etc.).
- Do **not** drop a cluster because main has a thematic cousin (`to_thread`, busy-queue FIFO, TUI MCP refresh, durable delegation).
- If a cherry-pick is empty/already present: record “no-op” and continue.
- Squash only **within** a cluster after it is green — never squash D1–D9 into one blob before conflicts are resolved.

### Done when

- [ ] All D1–D9 clusters applied or explicitly waived with written reason in `pilot/docs/`.
- [ ] Targeted gateway/agent/tools tests for applied clusters green.
- [ ] Prompt-cache invariant: MCP late-refresh does not mutate tools mid-session (D4).
- [ ] Long-job path: heartbeats / notify path still works (D3).

### Rollback

```powershell
git reset --hard <sha-after-Batch-C>
# or reset to last green cluster tag you created, e.g.:
# git tag batch-d3-green
```

Recommend: `git tag batch-dN-green` after each green cluster.

---

## Batch E — Cut over `main`, retire branches & folders

**Inputs:** Batch D complete (or Batch C only if you consciously defer D — **not** “no loss”; only do that if you accept parking core on the backup tag).

### E1 — Cut over local main

```powershell
git checkout -B main integrate/custom-main
git tag -a backup/custom-main-cutover-20260716 -m "Post-merge custom main" HEAD
```

Verify:

```powershell
git rev-list --count HEAD..origin/main   # expect 0 (not behind)
git rev-list --count origin/main..HEAD   # expect small = your theme/cherry commits
hermes chat   # banner: not 1150+ behind; legal skills present
```

Dep sync **after** cutover, carefully:

- Prefer manual venv sync from this checkout, **or**
- `hermes update` only when you understand it may reset if histories diverge — with tags in place first.

### E2 — Retire local branches (only after E1 smoke OK)

| Branch | Action |
|--------|--------|
| `integrate/custom-main` | Delete after FF into `main` (`git branch -d`) |
| `local/finalize-legal-discovery-skills-20260707` | Delete after tag verified (`-D` only if tip == backup tag) |
| `local/reapply-compat-scanner-on-main-20260707` | Delete (ancestor; fully contained) |
| `local/promote-devlab-compat-scanner-20260706` | Delete (duplicate scanner; tip already has files) |
| `backup/stale-main-830165473` | Delete after cutover confidence (optional keep 7 days) |
| `backup/pre-merge-feature-20260716` **branch** | Optional delete; **keep the annotated tag** |
| Tags `backup/pre-merge-feature-20260716`, `backup/custom-main-cutover-20260716` | **KEEP** |

```powershell
git branch -d integrate/custom-main
git branch -D local/finalize-legal-discovery-skills-20260707
git branch -D local/reapply-compat-scanner-on-main-20260707
git branch -D local/promote-devlab-compat-scanner-20260706
# after a few good days:
git branch -D backup/stale-main-830165473
git branch -D backup/pre-merge-feature-20260716   # tag remains
```

### E3 — Clean local folders (disk, not git)

Safe to delete anytime (not part of the product):

```powershell
Remove-Item -Recurse -Force .cache, .tmp-pytest -ErrorAction SilentlyContinue
Remove-Item -Force CODEX_*.md, MATTER_MAIL_*.md -ErrorAction SilentlyContinue
```

Do **not** delete `pilot/`, `skills/legal/`, or `pilot/docs/`.

### Done when

- [ ] Only meaningful local branch: `main` (+ optional short-lived backups).
- [ ] Backup tags exist and `git show backup/pre-merge-feature-20260716` works.
- [ ] Working tree free of cache/report debris.
- [ ] Banner healthy; legal skills + long-job behavior verified once.

### Rollback (nuclear)

```powershell
git checkout -B main backup/pre-merge-feature-20260716
```

Restores pre-cutover custom tip (again behind upstream).

---

## What “no loss” means (acceptance checklist)

| Concern | Ensured by |
|---------|------------|
| Legal product (casegraph, matter-mail, intake/review, med chron, depo) | Batch B + C |
| Compat scanner | Batch B (from feature tip; promote branch skipped as duplicate) |
| Pilot / promote goldens / faithfulness | Batch B + C |
| Long-job efficiency (no silent drops, heartbeats, result storage) | Batch D3 |
| Prompt-cache / toolset stability (MCP late refresh) | Batch D4 |
| Gateway import side effects / public surface | Batch D1–D2 |
| Steer/pending consistency | Batch D8 |
| Skill install security gaps | Batch D7 |
| Aux/fallback/stream integrity | Batch D6 |
| Process docs retained | Batch B → `pilot/docs/` |
| Branch/folder clutter gone | Batch E |

---

## Explicit non-goals

- Opening an upstream PR to Nous (optional later; this plan is **local main** cleanup).
- Replaying all 42 commits via rebase.
- Keeping `local/*` branches after cutover.
- Committing `.cache`, `.tmp-pytest`, or CODEX/MATTER_MAIL review dumps.

---

## Suggested calendar

| Day | Batch |
|-----|-------|
| Day 1 | A → B → C (stop if tests red) |
| Day 2 | D1–D4 (gateway/long-job/MCP — highest legal runtime value) |
| Day 3 | D5–D9 + E cutover + branch delete |

---

## Approval gate

Reply with **“execute Batch A”** (or A–C / full A–E) to begin. Until then this file is plan-only — no branch deletes, no resets.
