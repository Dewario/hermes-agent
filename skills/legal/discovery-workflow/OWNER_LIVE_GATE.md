# Owner Live Gate — Discovery Workflow §9.5 Approval

**This is the ONLY document that authorizes a live matter for a discovery
slice.** It exists so the owner (attorney) — never engineering — records the
§9.5 sign-off required by
[`SPEC.md`](SPEC.md) before any `rog`/`rfp`/`rfa` audit or outgoing-draft slice
touches a real matter.

> **Engineering boundary (HARD):** Engineering may mark SPEC §9.1–9.3 green
> (synthetic cells, live dry-run mechanics, hygiene). Engineering **must NOT**
> check any §9.5 box, fill in the approval line, or run a live/Allen matter.
> A §9.5 box checked by anyone other than the owner is void.

One filled copy of this template is required **per matter × request_type ×
mode**. Do not batch matters or slices into a single approval. Store the filled
copy **outside this repo** with the matter (e.g.
`C:\Matters\<MATTER-ID>\03_attorney\`), never under `hermes-agent/`.

---

## How to use

1. Copy the block below into the matter's attorney folder (outside the repo).
2. The owner confirms each §9.1–9.5 item, fills matter ID / request_type /
   mode, and pins the exact **tip commit SHA** the slice was validated on.
3. The owner signs and dates. Only then may the live dry-run in
   [`../LIVE_MATTER_RUNBOOK.md`](../LIVE_MATTER_RUNBOOK.md) §8 run **without**
   `--skip-ocr-queue`.

---

## Copy-paste template

```
# §9.5 Owner Live Gate — <MATTER-ID>

matter_id:      ______________________________
request_type:   [ ] rog   [ ] rfp   [ ] rfa      (choose exactly one)
mode:           [ ] audit_incoming_response
                [ ] draft_outgoing_request
                [ ] draft_response            (choose exactly one)
tip_commit_sha: ______________________________   (git rev-parse HEAD, validated tip)
slice:          ____   (A1 rfp-audit | A2 rfa-audit | A3 rog-audit |
                        B1 rfa-draft | B2 rog-draft | B3 rfp-draft)

--- §9.1 Per-slice synthetic (engineering may confirm; owner verifies) ---
[ ] Dedicated parser; refuses wrong request_type input.
[ ] Dedicated output schema + template.
[ ] Validators: cite enum, status/classification enum, isolation, no invented locators.
[ ] This slice's §7 synthetic cell is green (pytest + selftest) on the tip SHA above.
[ ] Objection boundary respected (flag / opt-in template only).

--- §9.2 Live dry-run (per matter × slice) — run WITHOUT --skip-ocr-queue ---
[ ] casegraph status <matter_dir>                         → exit 0
[ ] casegraph verify-cites <matter_dir> <output.md> [--allow-empty for outgoing drafts] → exit 0
[ ] casegraph check-isolation <matter_dir> <output.md> --strict → exit 0
[ ] live_preflight.py --matter-dir <matter_dir>
      audit slices: add --output <output.md>
      outgoing drafts (B1/B2/B3): omit --output (no Bates cites; vacuous cite check fails)
      NEVER pass --skip-ocr-queue on live → exit 0
[ ] OCR queue empty (casegraph export-ocr-queue <matter_dir> → exit 0)

--- §9.3 Hygiene ---
[ ] Offline pytest only; no client files under hermes-agent/.
[ ] git diff --check clean.
[ ] Skill descriptions ≤ 60 chars.

--- §9.4 Program-ready (informational; not required for a single-slice live gate) ---
[ ] All six §7 synthetic cells green (see SPEC §9.4).

--- §9.5 Ready-for-live (OWNER ONLY — engineering must NOT check these) ---
[ ] That slice's §9.1–9.3 are green on the tip_commit_sha above.
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
  (matter, request_type, mode). A second slice on the same matter needs its own
  filled copy.
- **Tip SHA is load-bearing.** The §9.1/§9.2 confirmations are only valid for
  the commit named in `tip_commit_sha`. If the tree advances, re-verify before
  the live run.
- **No live results in the repo.** This template ships blank. Do not commit a
  filled copy, real matter IDs, or dry-run output into `hermes-agent/`.
- **Current status:** as of the SPEC §9.5 table, all six slices are
  synthetic-green with **§9.5 Open — not signed**. No live dry-run has been run.
