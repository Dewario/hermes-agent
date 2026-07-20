# Owner Live Gate - Discovery Workflow Section 9.5 Approval

**This is the ONLY document that authorizes a live matter for a discovery
slice.** It exists so the owner (attorney), never engineering, records the
Section 9.5 sign-off required by [`SPEC.md`](SPEC.md) before any
`rog`/`rfp`/`rfa`/`expert` review, drafting, or assessment slice touches a
real matter.

> **Engineering boundary (HARD):** Engineering may mark SPEC Sections 9.1-9.3
> green (synthetic cells, live dry-run mechanics, hygiene). Engineering must
> NOT check any Section 9.5 box, fill in the approval line, or run a live
> client matter. A Section 9.5 box checked by anyone other than the owner is
> void.

One filled copy of this template is required per matter x request_type x mode x
slice. Do not batch matters or slices into a single approval. Store the filled
copy outside this repo with the matter using the canonical filename
`C:\Matters\<MATTER-ID>\03_attorney\OWNER_LIVE_GATE_<slice>.md`
(for example, `OWNER_LIVE_GATE_D1.md`), never under `hermes-agent/`.

---

## How to use

Optional review aid before owner approval:

```powershell
python skills/legal/scripts/owner_gate_assistant.py `
  --matter-dir C:\Matters\<MATTER-ID> `
  --request-type rfp `
  --mode audit_incoming_request `
  --package-output C:\Matters\<MATTER-ID>\02_outputs\<package>.md
```

The assistant writes `GATE_REVIEW_PACKET_*.md` plus JSON only. It does not
approve, sign, or create an `OWNER_LIVE_GATE_*.md` file.

1. Copy the block below into the matter's attorney folder outside the repo as
   `OWNER_LIVE_GATE_<slice>.md`.
2. The owner confirms each Section 9.1-9.5 item, fills matter ID,
   request_type, mode, slice, and pins the exact tip commit SHA the slice was
   validated on.
3. The owner signs and dates. Only then may the live dry-run in
   [`../LIVE_MATTER_RUNBOOK.md`](../LIVE_MATTER_RUNBOOK.md) Section 8 run
   without `--skip-ocr-queue`.

---

## Copy-paste template

```text
# Section 9.5 Owner Live Gate - <MATTER-ID>

file_name:      OWNER_LIVE_GATE_<slice>.md
matter_id:      ______________________________
request_type:   [ ] rog   [ ] rfp   [ ] rfa   [ ] expert      (choose exactly one)
mode:           [ ] audit_incoming_response
                [ ] draft_outgoing_request
                [ ] audit_incoming_request
                [ ] trial_gap_assessment
                [ ] expert_needs_assessment
                [ ] draft_response            (choose exactly one)
tip_commit_sha: ______________________________   (git rev-parse HEAD, validated tip)
slice:          ____   (A1 rfp-audit | A2 rfa-audit | A3 rog-audit |
                        B1 rfa-draft | B2 rog-draft | B3 rfp-draft |
                        D1 rfp-request-audit | D2 rfa-request-audit |
                        D3 rog-request-audit | G1 trial-gap |
                        E1 expert-needs |
                        C1 rfp-response-draft | C2 rfa-response-draft |
                        C3 rog-response-draft)

--- Section 9.1 Per-slice synthetic (engineering may confirm; owner verifies) ---
[ ] Dedicated parser; refuses wrong request_type input.
[ ] Dedicated output schema + template.
[ ] Validators: cite enum, status/classification enum, isolation, no invented locators.
[ ] This slice's Section 7 synthetic cell is green (pytest + selftest) on the tip SHA above.
[ ] Objection boundary respected (flag / opt-in template only).

--- Section 9.2 Live dry-run (per matter x slice) - run WITHOUT --skip-ocr-queue ---
[ ] casegraph status <matter_dir> -> exit 0
[ ] casegraph verify-cites <matter_dir> <output.md> [--allow-empty for outgoing drafts / E1] -> exit 0
[ ] casegraph check-isolation <matter_dir> <output.md> --strict -> exit 0
[ ] live_preflight.py --matter-dir <matter_dir> --request-type <rog|rfp|rfa|expert> --mode <mode> --slice <slice>
      audit slices: add --output <output.md>
      draft/no-Bates-cite slices (B1/B2/B3/C1/C2/C3/E1): omit --output
      NEVER pass --skip-ocr-queue on live -> exit 0
[ ] OCR queue empty (casegraph export-ocr-queue <matter_dir> -> exit 0)

--- Section 9.3 Hygiene ---
[ ] Offline pytest only; no client files under hermes-agent/.
[ ] git diff --check clean.
[ ] Skill descriptions <= 60 chars.

--- Section 9.4 Program-ready (informational; not required for a single-slice live gate) ---
[ ] All Section 7 synthetic cells green (see SPEC Section 9.4).

--- 9.5 Ready-for-live (OWNER ONLY - engineering must NOT check these) ---
[ ] That slice's 9.1-9.3 are green on the tip_commit_sha above.
[ ] Explicit written approval naming this matter_id + request_type + mode (this document).
[ ] Single-matter invocation confirmed (one --matter-dir; no cross-client context).
[ ] No client files under the repo.

owner_name:      ______________________________
owner_signature: ______________________________
date:            ______________________________
```

---

## Notes

- **Scope is one cell.** This gate authorizes exactly one
  (matter, request_type, mode, slice). A second slice on the same matter needs
  its own filled copy.
- **Filename is load-bearing.** Live preflight accepts only canonical
  `OWNER_LIVE_GATE_<slice>.md` files. Drafts, assistant packets, review
  packets, and rehearsal evidence are ignored.
- **Tip SHA is load-bearing.** The Section 9.1/9.2 confirmations are only
  valid for the commit named in `tip_commit_sha`. If the tree advances,
  re-verify before the live run.
- **No live results in the repo.** This template ships blank. Do not commit a
  filled copy, real matter IDs, or dry-run output into `hermes-agent/`.
- **Current status:** A1-B3, D1-D3, G1, C1-C3, and E1 are synthetic-green when
  the matching focused tests and selftests pass on the current tip. Section 9.5
  remains open and unsigned for every real client matter.
