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
| Load file (DAT/OPT/LFP) | Normalize to Bates manifest with a small Python script via `terminal`; do not invent Bates |
| Native email (.eml) | Prefer matter-mail ingest; casegraph indexes staged copies |

Casegraph marks docs without text as `text_extractable: none|partial|unsupported`,
continues indexing, and writes `.casegraph/needs_ocr.json` on every `build`.
Agents should: (1) `export-ocr-queue` or
`python skills/legal/scripts/ocr_from_queue.py <matter>` (plan; add `--run` if
`ocrmypdf` is installed), (2) OCR via OCRmyPDF/Tesseract into `01_production/text/`
(or searchable PDF) in background, (3) `casegraph build` again so previously
skipped text becomes cite-verifiable. Citations to unreadables still require
attorney check until the queue is empty.

## 5. Session order

1. Confirm `03_attorney/PROVIDER_AUTH.md` is complete
2. `casegraph init` + `build` (background if large) + `status` + `export-ocr-queue`
   — if queue non-empty, OCR then rebuild before review cites
3. Intake **or** review (never both in one session)
4. Machine gates: validator (file-scoped) → `check_outputs --anchors` → casegraph verify-cites / chronology / isolation `--strict`
5. Owner cite-check ≥10 claims; record in `03_attorney/cite_check_log.md`

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
