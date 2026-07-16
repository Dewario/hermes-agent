# Gateway smoke checklist — Batch E (Telegram)

Owner-run only. No secrets in this file. Use when legal work will flow through
the messaging gateway (optional — CLI-only supervised runs do not require this).

**Prereq:** gateway running with Telegram adapter configured in your profile
(`~/.hermes/config.yaml`); bot token in `~/.hermes/.env` (never commit).

## Smoke steps (~15 min)

| # | Action | Pass criteria |
|---|--------|---------------|
| 1 | `/new` | Fresh session starts; prior transcript does not leak into the new turn. |
| 2 | Send a prompt that invokes a visible tool (e.g. `read_file` on a small repo file) | Tool progress appears in chat (`display.tool_progress_command` or default feed). |
| 3 | `terminal` with `background=true`, `notify_on_complete=true` (short `sleep` or `echo`) | Running output or completion notify arrives without blocking the session indefinitely. |
| 4 | Trigger a command that requires approval (or use a gated tool your profile blocks) | Approval prompt appears; session shows wait/heartbeat until `/approve` or `/deny`. |

## Config knobs to verify

- `display.background_process_notifications` — `all` or `result` for legal long jobs.
- `display.tool_progress_command` — enabled if you expect inline tool status in Telegram.
- `terminal.cwd` — points at matter directory when doing live legal work (e.g. `C:\Matters\Rickman`).

## Fail / stop

- Bot silent after `/new` → check `gateway.log`, Telegram token lock (single profile per bot).
- No tool progress → confirm toolset enabled via `hermes tools` for the gateway platform.
- Background job never notifies → confirm `notify_on_complete=true` and notification mode not `off`.
- Approval hangs with no heartbeat → gateway runner must receive `/approve`/`/deny` while agent blocked (see AGENTS.md gateway guards).

## Not in scope

- Provider auth for live matter text (`03_attorney/PROVIDER_AUTH.md`) — Batch A / live runbook.
- H3 aux 429 / payment taxonomy — see `OWNER_CHECKLIST_BATCH_A.md` deferred items.
- Full legal skill regression — use `LIVE_MATTER_RUNBOOK.md` supervised shakedown instead.

Record pass/fail in your matter notes; no repo commit required.
