# OCR Farm Cron / Resume

Use durable cron or an owner-run Windows task for long OCR farms; gateway
background messaging is process-local and does not survive a gateway restart.
The OCR helper writes `<matter>/.casegraph/ocr_farm_state.json` after each
successful PDF, so the next invocation skips completed file hashes.

Set `$HermesAgent` to your hermes-agent checkout (example:
`$env:LOCALAPPDATA\hermes\hermes-agent`) and `$Matter` to the matter directory
(example: `C:\Matters\Rickman`).

## Hermes cron

Run five pending PDFs every 15 minutes:

```powershell
$HermesAgent = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$Matter = "C:\Matters\MATTER-ID"
hermes cron add --schedule "every 15m" --workdir $HermesAgent --prompt "Run python skills/legal/scripts/ocr_from_queue.py '$Matter' --run --limit 5. Report only errors; state is persisted under the matter."
```

Cron work is durable across gateway restarts. Configure delivery separately if
you want completion notices; the `.casegraph/ocr_farm_state.json` artifact is
the authoritative resume signal.

## Windows Task Scheduler

```powershell
$HermesAgent = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$Matter = "C:\Matters\MATTER-ID"
$tr = "py `"$HermesAgent\skills\legal\scripts\ocr_from_queue.py`" `"$Matter`" --run --limit 5"
schtasks /create /tn "Hermes OCR MATTER-ID" /sc minute /mo 15 /tr $tr /f
```

## Resume and rebuild

Re-run the chunked command until `casegraph export-ocr-queue <matter>` exits
0. Then run `casegraph build <matter>` to index the OCR text and make it
cite-verifiable. If the queue still contains non-PDF or complex-layout files,
resolve those manually or with the separately installed local
`docling_extract.py` before retrying the queue export.
