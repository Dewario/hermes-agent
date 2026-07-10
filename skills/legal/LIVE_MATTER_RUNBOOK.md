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

Never place real client files under `hermes-agent/`.

## 2. Provider authorization checklist (owner)

Before the first Hermes session on a real matter, write `03_attorney/PROVIDER_AUTH.md`:

- [ ] Provider name (e.g. Anthropic / DeepSeek / Zhipu / local)
- [ ] Retention / training opt-out confirmed acceptable for work product
- [ ] Client / engagement permits this processing
- [ ] Session budget (max tool turns) recorded
- [ ] Authorization date + attorney initials

Without this file: **do not** send matter text to any remote model API.

## 3. OCR / text extraction path

| Production type | Path |
|---|---|
| Text-layer PDF | `read_file` on the PDF; copy extract to `01_production/text/` |
| Scanned PDF / TIFF | Local OCR via `terminal` (`ocrmypdf` / Tesseract) **or** page-wise `vision_analyze`; flag low-confidence pages in Step 0 |
| Load file (DAT/OPT/LFP) | Normalize to Bates manifest with a small Python script via `terminal`; do not invent Bates |
| Native email (.eml) | Prefer matter-mail ingest; casegraph indexes staged copies |

Casegraph marks docs without text as `text_extractable: none|partial` — citations to those pages require manual attorney check.

## 4. Session order

1. `casegraph init` + `build` + `status`
2. Intake **or** review (never both in one session)
3. Machine gates: validator (file-scoped) → `check_outputs --anchors` → casegraph verify-cites / chronology / isolation `--strict`
4. Owner cite-check ≥10 claims; record in `03_attorney/cite_check_log.md`

## 5. Per-matter `check_outputs` anchors

```json
{
  "fact_anchors": ["Client Last", "Employer Name", "Incident City"],
  "bates_regex": "ACME-PROD-\\d+",
  "require_synthetic_banner": false
}
```

```
python pilot/check_outputs.py --phase review --dir C:\Matters\M1\02_outputs --anchors C:\Matters\M1\03_attorney\anchors.json
```

## 6. Matter-mail (optional)

Requires `$HERMES_HOME/matter_mail_firm.json` with `mail_accounts[].address` set.
Full pipeline only — see discovery-review Step 6. Never run against a personal mailbox until MM-H1/H2/H3 fixes are in the tree you are running.
