# Live Matter Runbook — Layout, Auth, OCR

**CONFIDENTIAL — ATTORNEY WORK PRODUCT when filled with real matter data.**
Synthetic examples only in this repository. Real matters live **outside** the repo.

## 1. Matter directory layout (create once per matter)

```
C:\Matters\<MATTER-ID>\
├── 00_intake\                 # client notes, questionnaire, engagement docs
├── 01_production\
│   ├── raw\                   # as-received PDFs/load files — READ-ONLY
│   ├── text\                  # extracted/OCR text, one file per Bates range
│   └── BATES_MANIFEST.md      # prefix, padding, production date
├── 02_outputs\                # Hermes packages (intake_package.md, review_*)
├── 03_attorney\
│   ├── PROVIDER_AUTH.md       # required before any API call with client text
│   └── cite_check_log.md
├── correspondence\            # matter-mail staged copies (tool-managed)
├── .casegraph\                # casegraph index (tool-managed)
└── .matter_mail\              # matter-mail state (tool-managed)
```

Never place real client files under `hermes-agent/`. Example live matter: `C:\Matters\Rickman\`.
Create the layout with:

```
python skills/legal/scripts/scaffold_matter.py --matter-dir C:\Matters\Rickman --matter-id Rickman --bates-prefix RICKMAN-PROD
```

The scaffold refuses a matter path inside this repository and preserves any
existing attorney authorization or anchors files.

## 2. Provider authorization checklist (owner)

Before the first Hermes session on a real matter, write `03_attorney/PROVIDER_AUTH.md`
(copy from `skills/legal/templates/PROVIDER_AUTH.template.md`):

- [ ] Provider name (e.g. Anthropic / DeepSeek / Zhipu / local)
- [ ] Retention / training opt-out confirmed acceptable for work product
- [ ] Client / engagement permits this processing
- [ ] Session budget (max tool turns) recorded
- [ ] Authorization date + attorney initials

Without this file: **STOP — do not** send matter text to any remote model API.
Skills must verify this file exists and is initialed before the first client-text turn.

## 3. Long-running tools (timeouts / batch)

Hermes foreground `terminal` defaults to **180s** and hard-caps at **600s**.
Live OCR, `casegraph build`, and matter-mail fetches often exceed that.

| Job class | Required pattern |
|---|---|
| Short query / status / one cite gate | Foreground `terminal` OK |
| OCR, first `casegraph build`, multi-hour mail ingest, large scripts | `terminal(background=true, notify_on_complete=true)` — do **not** block the chat loop |
| Must survive gateway restart | Prefer owner-run offline or `cron` — not `delegate_task(background=true)` |

Write progress artifacts under the matter dir (e.g. `.casegraph/`, `.matter_mail/`) so a killed session can resume. Prefer absolute script paths under the hermes-agent checkout; on PowerShell use `$env:HERMES_HOME` (not `%HERMES_HOME%`).

## 4. OCR / text extraction path

| Production type | Path |
|---|---|
| Text-layer PDF | `read_file` on the PDF; copy extract to `01_production/text/` |
| Scanned PDF / TIFF | Local OCR via `terminal(background=true, notify_on_complete=true)` (`ocrmypdf` / Tesseract) **or** page-wise `vision_analyze`; flag low-confidence pages in Step 0. Prefer owner-run offline OCR into `01_production/text/` before the session when the set is large. |
| Load file (DAT/OPT/LFP) | Normalize explicit Bates values with `python skills/legal/scripts/loadfile_to_manifest.py --matter-dir <matter> --production-dir <folder> --json`; it writes `01_production/BATES_MANIFEST.md` (and optional JSON), never invents Bates, and can print suggested `casegraph init --bates-prefix` flags |
| Native email (.eml) | Prefer matter-mail ingest; casegraph indexes staged copies |

Casegraph marks docs without text as `text_extractable: none|partial|unsupported`,
continues indexing, and writes `.casegraph/needs_ocr.json` on every `build`.
Agents should: (1) `export-ocr-queue` or
`python skills/legal/scripts/ocr_from_queue.py <matter>` (plan; add `--run` if
`ocrmypdf` is installed), (2) OCR via OCRmyPDF/Tesseract into `01_production/text/`
(or searchable PDF) in background, (3) `casegraph build` again so previously
skipped text becomes cite-verifiable. Citations to unreadables still require
attorney check until the queue is empty.

For large farms, use `ocr_from_queue.py <matter> --run --limit 5`. It records
each completed PDF SHA-256 in `.casegraph/ocr_farm_state.json`, so restarts
skip completed work. Use durable cron or Windows Task Scheduler rather than
gateway messaging when the job must survive a gateway restart; see
[`references/OCR_FARM_CRON.md`](references/OCR_FARM_CRON.md). Re-run chunks
until `casegraph export-ocr-queue <matter>` exits 0, then run `casegraph build`.

## 5. Session order

1. Create the layout with `scaffold_matter.py`, then sign `03_attorney/PROVIDER_AUTH.md`
2. `casegraph init` + `build` (background if large) + `status` + `export-ocr-queue`
   — if queue non-empty, OCR then rebuild before review cites
3. Intake **or** review (never both in one session)
4. Machine gates: validator (file-scoped) → `check_outputs --anchors` → casegraph verify-cites / chronology / isolation `--strict`
5. Owner cite-check ≥10 claims; record in `03_attorney/cite_check_log.md`

Before sending a completed package to attorney handoff, run:

```
python skills/legal/scripts/live_preflight.py --matter-dir C:\Matters\Rickman --output C:\Matters\Rickman\02_outputs\review_package.md
```

This stops on unsigned provider authorization, stale casegraph indexes, or
failed output gates. A non-empty OCR queue is a warning with exit code 1;
use `--skip-ocr-queue` only when the attorney has accepted the remaining OCR work.

For a deposition outline, confirm the witness is registered with `casegraph add-entity`, then run `verify-cites` and `check-isolation --strict` on the completed outline before attorney handoff.

## 6. Per-matter `check_outputs` anchors

```json
{
  "fact_anchors": ["Client Last", "Employer Name", "Incident City"],
  "bates_regex": "ACME-PROD-\\d+",
  "require_synthetic_banner": false
}
```

```
python pilot/check_outputs.py --phase review --dir C:\Matters\Rickman\02_outputs --anchors C:\Matters\Rickman\03_attorney\anchors.json
```

## 7. Matter-mail (optional)

Requires `$HERMES_HOME/matter_mail_firm.json` with `mail_accounts[].address` set.
Full pipeline only — see discovery-review Step 6. Never run against a personal mailbox until MM-H1/H2/H3 fixes are in the tree you are running.

For medical-record timelines after review, use `skills/legal/medical-chronology/SKILL.md`.

## 8. Discovery workflows — not ready for live use

Program roadmap: `skills/legal/discovery-workflow/SPEC.md` (`rog`|`rfp`|`rfa`
× audit|draft). Implemented synthetic-only today: **A1** RFP audit
(`discovery-response/`) and **A2** RFA audit
(`discovery-workflow/scripts/rfa_audit.py`). Do **not** use Hermes for Allen
or any live matter’s interrogatories, outgoing sets, or even RFP/RFA audit
until the relevant slice’s acceptance criteria are green and the owner
approves **that matter × request_type × mode**. Never combine two clients’
records in one review context.
