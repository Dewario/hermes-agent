# Codex F2 Cross-Check Report

**Branch:** `legal-evidentiary-objections`
**Input commit reviewed:** `7123fa2f90b5cc77fe23043e1dc98a45e414e77a`
**Date:** 2026-07-23

## Verdict

**Passed after corrections.** The F2 design is sound: deterministic
jurisdiction-aware objection / protective-order scaffold selection, no
substantive strategy drafting, strict isolation, live-gated owner approval, and
no live matter paths.

The cross-check found four real defects or drifts in the initial F2 checkpoint.
All four were corrected before this report was committed.

## Source-Verification Summary

| Cluster | Verdict | Source posture |
|---|---|---|
| California objection statutes (`CCP 2030.240`, `2031.240`, `2033.230`) | Confirmed | Official California Legislative Information sections |
| California protective-order statutes (`CCP 2030.090`, `2031.060`, `2033.080`) | Confirmed with correction | Official California Legislative Information sections |
| `CCP 2017.020` as supporting scope-limit / PO authority | Confirmed | Official California Legislative Information |
| `CCP 2025.420` deposition PO scope boundary | Confirmed | Official California Legislative Information; documented but not exposed for F2 `rog`/`rfp`/`rfa` |
| Washington objection statutes (`CR 33(a)`, `34(b)`, `36(a)`, `26(g)`) | Confirmed | Official Washington Courts rule PDFs |
| Washington protective orders (`CR 26(c)`, `26(i)`, `37(a)(4)`) | Confirmed with correction | Official Washington Courts rule PDFs |

## Findings And Fixes

| ID | Severity | Finding | Resolution |
|---|---:|---|---|
| F2-C1 | Medium | `OWNER_LIVE_GATE.md` omitted `enforcement_motion_draft`, `objection_motion_draft`, `F1`, and `F2` even though runtime validation accepts those axes. | Template now lists both modes and slices; owner-gate tests assert F2 gate acceptance. |
| F2-C2 | Medium | SKILL/SPEC described umbrella dispatch too broadly while F1/F2 are intentionally standalone-only. | SKILL/SPEC now say umbrella dispatch/selftest-all covers A/B/C/D/G/E, while F1/F2 use dedicated script selftests; umbrella test encodes that boundary. |
| F2-C3 | Medium | CA RFA protective-order prose said "responding party, or any other party or affected person," but `CCP 2033.080(a)` is responding-party specific. | `protective_order_block()` now uses "responding party" for RFA and preserves the broader ROG/RFP phrase; unit test added. |
| F2-C4 | Low | `WA-CR-37-A-4` pack summary described only granted-motion expenses, omitting denied and partly granted outcomes. | Summary now covers granted, denied, and partly granted/mixed expense outcomes; pack test added. |

## Confirmed Nuance Items

| ID | Result |
|---|---|
| F2-N1 | Confirmed: `CR 34(b)(3)` is a valid RFP response/objection subdivision; `CR 34(b)(3)(B)-(C)` is the tighter pinpoint. |
| F2-N2 | Confirmed: `CCP 2017.020` is correctly supporting-only; per-method PO statutes remain primary. |
| F2-N3 | Confirmed: `CCP 2025.420` is deposition-specific and remains documented in the pack but not exposed by F2's `rog`/`rfp`/`rfa` CLI. |

## Official Sources

- California Legislative Information, `CCP 2030.240`, `2031.240`, `2033.230`,
  `2030.090`, `2031.060`, `2033.080`, `2017.020`, `2016.040`, `2025.420`.
- Washington Courts official PDFs, `CR 26`, `CR 33`, `CR 34`, `CR 36`, `CR 37`.

## Post-Fix Verification

- `python -m py_compile skills\legal\discovery-workflow\scripts\objection_motion.py`
- `python skills\legal\discovery-workflow\scripts\objection_motion.py selftest`
- `python -m pytest -q --basetemp .pytest_tmp_f2_fix tests\skills\test_discovery_objection_motion.py tests\skills\test_matter_safety.py tests\skills\test_live_preflight.py tests\skills\test_discovery_workflow_umbrella.py tests\skills\test_jurisdiction_packs_and_experts.py`
- Result: `84 passed`
- Broad legal/discovery suite: `219 passed`

## Safety Audit

- No live `C:\Matters\<client>` paths created or touched.
- No `OWNER_LIVE_GATE_F2.md` created.
- No owner §9.5 boxes checked by engineering.
- F2 remains packet/scaffold-only and attorney-review-gated.
