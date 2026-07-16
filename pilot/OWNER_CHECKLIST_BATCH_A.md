# Owner checklist — unblock live Matter 1

Autonomous Batches **B / C / D(tooling)** are implemented in the working tree.
The items below **require your responsive input** and cannot be completed by the agent.

## Batch A (~25–40 min)

1. Edit three review-package self-audit slips in `pilot_outputs/review/review_package.md`:
   - chronology “one year” → “~6 months”
   - “21 dated entries” → “19”
   - span start “August 8, 2024” → “2023-01-01” (or match the table)
2. Compute SHA-256 of both packages and fill `pilot_outputs/approval.json` from `pilot/approval.template.json`:
   - `approved: true` for intake + review
   - real `reviewed_at` ISO-8601
   - `artifacts.*.sha256` matching disk files
   - keep the full `gates_checked` list (11 items)
3. Run `.\pilot\promote_goldens.ps1`
4. Create `C:\Matters\<M1>\` per `skills/legal/LIVE_MATTER_RUNBOOK.md`
5. Write `03_attorney/PROVIDER_AUTH.md` (provider + retention decision)
6. Optional hygiene: delete `pilot_outputs/**/hermes_*.txt`

## Still deferred (Batch E — your call)

- **H3** aux 429 / payment taxonomy (needs real Vertex/Gemini error captures + decision vs #26803)
- Gateway messaging smoke if you will run legal work through the gateway (not required for supervised CLI)

## After A

Supervised Matter 1 shakedown using Fable 5 §6 prompts + LIVE_MATTER_RUNBOOK.md.
Do **not** treat unsigned goldens or vacuous pre-fix gates as live approval — those holes are closed in code; process sign-off is still yours.
