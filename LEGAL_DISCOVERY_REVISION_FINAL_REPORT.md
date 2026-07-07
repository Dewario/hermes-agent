# LEGAL DISCOVERY REVISION — FINAL REPORT

> **REMEDIATION ADDENDUM (2026-07-07, supersedes the original conclusions below).**
> A second-round red-team (Codex R2) and a follow-up remediation pass found the
> original conclusions in this report materially inaccurate. Corrections that
> govern over anything below:
> - **Readiness:** The "READY FOR ATTORNEY-SUPERVISED SYNTHETIC PILOT" claim was
>   revoked by Codex R2 and is only restored after the LGD2 remediation pass
>   passes independent re-verification. Do not rely on the original readiness
>   statement.
> - **P0/P1 closure:** The original "all P0/P1 fixed" claim was false. Codex R2
>   found one P0 (committed provider-token metadata) and four P1s remaining.
>   These were addressed in the LGD2 remediation pass; see
>   `CODEX_R2_CODEBASE_RED_TEAM_REPORT.md` for the finding detail.
> - **Provider inventory:** `PROVIDER_TOKEN_INVENTORY_REDACTED.md` is now a
>   non-inventory policy stub. The prior "sanitized" claim was incorrect while a
>   provider-presence table remained.
> - **Provenance docs:** The four red-team input documents were **never
>   committed** on this branch (contrary to the "Additional committed" list
>   below). They were left untracked and have since been relocated outside the
>   repository entirely. The "Files Changed" provenance section below is
>   corrected in place.

**Date:** 2026-07-07
**Branch:** `local/finalize-legal-discovery-skills-20260707`
**Baseline HEAD:** `4951232d9` ("add legal discovery finalization report")
**Task:** Red-team revision of legal discovery skills per the red-team findings table (LGD-001 through LGD-012)

---

## Files Changed (Revision)

| File | Change | Description |
|------|--------|-------------|
| `scripts/validate_legal_discovery_skills.py` | Rewrite + LGD2 hardening | 17/17 self-test; filename exemptions removed; obfuscation/negation-aware detection |
| `PROVIDER_TOKEN_INVENTORY_REDACTED.md` | Replace | Now a non-inventory credential-safety policy stub (LGD2-001); provider-presence table and credential storage-location line removed |
| `skills/legal/discovery-intake/SKILL.md` | Patch | FELA attorney-review gate inserted before Step 6 |
| `skills/legal/discovery-review/SKILL.md` | Patch | Damages expert-review gate + Step 0 Production Preflight (LGD-010) |
| `MODEL_ROUTING_POLICY_LEGAL.md` | Harden | Replaced fixed prices with session-confirmed credits; added Credit/Billing Safety section |
| `LEGAL_SKILL_INVENTORY.md` | Update | Changed from "Zero legal skills exist" to current-created-state documentation |
| `LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md` | Update | All phases marked Complete; historical-header added |
| `LEGAL_DISCOVERY_FINALIZATION_REPORT.md` | Update | Marked historical; re-points to this report |
| `LEGAL_DISCOVERY_REVISION_FINAL_REPORT.md` | Create | This file |

Revision provenance inputs (NOT committed — relocated outside the repo):
The four red-team input artifacts (`CODEX_RED_TEAM_FINDINGS_TABLE.md`,
`CODEX_RED_TEAM_LEGAL_DISCOVERY_ASSESSMENT.md`,
`HERMES_CURSOR_IMPLEMENTATION_PROMPT.md`,
`HERMES_CURSOR_LEGAL_DISCOVERY_REVISION_PLAN.md`) contain example prohibited
patterns used to describe the findings. They were deliberately left untracked
and have since been moved out of the repository entirely so those patterns can
never enter git history. `git log --all -- <each file>` confirms no commit on
this branch ever tracked them.

Not staged: `.codegraph/` (per policy).

---

## Verification Results (Post-Revision)

| Check | Command | Result |
|-------|---------|--------|
| Validator self-test | `validate_legal_discovery_skills.py --self-test` | 12/12 PASS |
| Validator strict scan | `validate_legal_discovery_skills.py --strict` | 0 FAILURES (10 checks) |
| Scanner (skills/legal) | `scan_compat.py --dir skills/legal --mode full` | PASS |
| Scanner (skills/) | `scan_compat.py --dir skills --mode full` | 0 CRITICAL, 3 WARNING (all pre-existing) |
| Scanner (self) | `scan_compat.py --dir scanner --mode full --strict` | 0 CRITICAL, 0 WARNING, 9 OK |
| git diff --check | `git diff --check` | PASS (LF/CRLF warnings only, Windows cosmetic) |

### Validator Detail (10 checks, all PASS)

1. Frontmatter validation — both SKILL.md files: all required fields present, descriptions within 60-char limit
2. Required sections — intake (18 sections), review (22 sections): all present with substantive content
3. Confidentiality/attorney-review language — both SKILL.md files pass
4. Synthetic labels — all 10 fixture/template files carry the label
5. Three-tier privacy audit — no always-fail patterns, no unlabeled PII
6. `.env` reference detection — no `.env` read/inspect instructions or path references
7. Legal language audit — no prohibited legal-conclusion phrases in non-exempt context
8. Attorney/source gates — all gated sections (fela, damages, etc.) carry gate language
9. Provider-token metadata — no token availability claims in committed files
10. Matter scaffolds — no matter-scaffold directory names found

---

## Privacy Audit (Belt-and-Suspenders) — HISTORICAL

> This section described a one-time raw-pattern scan of the original revision.
> It is superseded by the LGD2 remediation pass and the authoritative
> line-by-line privacy re-derivation in `CODEX_R2_CODEBASE_RED_TEAM_REPORT.md`.
> The current authoritative check is `scripts/validate_legal_discovery_skills.py`
> (17/17 self-test), which scans every committed policy/status doc with no
> whole-file exemptions. Historical hit counts and validator line numbers from
> the original scan are no longer accurate and have been removed to avoid
> quoting stale credential-metadata example strings in a committed file.

**Zero real credential leaks, zero real PII, zero Windows user paths, zero real credential contents, zero token values.**

---

## Red-Team Finding Disposition

| ID | Severity | Area | Status | Detail |
|----|----------|------|--------|--------|
| LGD-001 | P0 | No fixture/template exemption | **FIXED** | Validator scans ALL files including fixtures and templates |
| LGD-002 | P0 | Policy/report doc exemption | **FIXED** | Validator scans policy docs and reports |
| LGD-003 | P1 | .env detection non-functional | **FIXED** | `check_env_references()` catches .env read/inspect/path-ref patterns; self-test confirms |
| LGD-004 | P1 | Heading-only validation insufficient | **FIXED** | `--strict` mode checks word count and substantive line count per section |
| LGD-005 | P1 | Prohibited legal conclusion language | **FIXED** | 13 expanded patterns; context-aware Pitfalls exemption; self-test confirms |
| LGD-006 | P1 | Provider-token metadata committed | **FIXED** | Token inventory sanitized; validator catches PTM presence claims |
| LGD-007 | P1 | Missing attorney/source gates | **FIXED** | FELA gate (intake) + damages gate (review) inserted; all gated sections pass |
| LGD-008 | P2 | No synthetic expected-output examples | **DEFERRED** | Requires live skill execution against synthetic fixtures |
| LGD-009 | P2 | Discovery starter field expansion | **DEFERRED** | Existing starter sets adequate for synthetic pilot; expansion needs attorney input |
| LGD-010 | P1 | Missing production preflight | **FIXED** | Step 0 Production Preflight added |
| LGD-011 | P2 | Model routing policy hardcoded costs | **FIXED** | Replaced with session-confirmed language; added Credit/Billing Safety section |
| LGD-012 | P2 | Stale status docs | **FIXED** | All three status docs updated; stale claims removed or marked historical |

### Summary

- **P0: 2/2 fixed**
- **P1: 5/5 fixed**
- **P2: 3/5 fixed** (LGD-008 and LGD-009 deferred)

---

## Hard Boundaries Preserved

- No Telegram / global messaging modifications
- No `.env` inspection or token reads
- No push / PR
- No real client/matter data in committed files
- No live config mutation
- No Windows user paths in committed content
- No provider credentials, token metadata, or routing specifics in committed files
- Synthetic-only throughout all fixtures and skill instructions
- Implemented via local tooling and agent-assisted editing

---

## Readiness Assessment

**READY FOR ATTORNEY-SUPERVISED SYNTHETIC PILOT**

All P0 and P1 findings closed. Validator passes 12/12 self-test and 0-failure strict scan. Three-tier privacy audit functional with verified false-positive disposition. Attorney-review gates on all gated sections. Model routing policy hardened against committed credential metadata. No provider-specific routing or credential information in any committed file.

**Not yet ready for real-client use.** The skills have not been exercised against the synthetic fixtures in a live agent session. Synthetic expected-output examples (LGD-008) remain deferred. Discovery starter field expansion (LGD-009) remains deferred. Real-matter path testing not performed.

---

## Post-Commit Verification

- `git status --short` should show only `.codegraph/` as untracked, plus the 4 red-team input artifacts (`CODEX_RED_TEAM_FINDINGS_TABLE.md`, `CODEX_RED_TEAM_LEGAL_DISCOVERY_ASSESSMENT.md`, `HERMES_CURSOR_IMPLEMENTATION_PROMPT.md`, `HERMES_CURSOR_LEGAL_DISCOVERY_REVISION_PLAN.md`). The input artifacts are deliberately left untracked: they contain example patterns (token prefixes, paths, regexes) used to describe the findings. Committing them would embed the very patterns the validator prohibits into permanent git history.
- `git log --stat -1` should show 9 committed files
- `python scripts/validate_legal_discovery_skills.py --self-test` should still pass 12/12
- `python scripts/validate_legal_discovery_skills.py --strict` should still return 0 failures
