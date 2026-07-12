---
name: legal-matter-mail
description: "Find case emails missing from the matter file."
version: 1.0.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, correspondence, email, gap-analysis, discovery, plaintiff]
    category: legal
    related_skills: [legal-casegraph, legal-discovery-review, legal-discovery-intake]
---

# Matter-Mail — Correspondence Gap Scanner

Scan attorney mailboxes for case-relevant email in a matter-derived time window, then
diff the results against the casegraph-indexed matter file. Assumes an Outlook-first
topology: both the work mailbox (M365, fetched via Microsoft Graph) and any personal
account added to Outlook (e.g. Gmail — fetched via Outlook client export, or the
google-workspace skill as a gmail-api fallback) are configured as `mail_accounts` in
the firm config, each with its own fetch transport. Output is an attorney-review gap
report: which correspondence exists only in a mailbox and never made it into the
server case file, which attachments are unfiled, and where email threads reference
messages that exist nowhere.

**CONFIDENTIALITY:** Mailbox contents and gap reports are confidential attorney work
product. All state lives inside the matter directory, outside this repo. Never
transmit mailbox content through external APIs beyond the read-only fetch itself
without attorney authorization. This skill uses synthetic fixtures for development
and testing only.

**ATTORNEY REVIEW REQUIRED:** All outputs are drafts for attorney review. The scanner
stages copies and reports gaps; it never files documents, never renders legal
conclusions, and never decides privilege. Language: "evidence supports / suggests /
requires attorney review."

**PROVIDER_AUTH (live matters):** Before any remote model sees mailbox/matter text, verify
`<matter>\03_attorney\PROVIDER_AUTH.md` is complete. If missing: **STOP**. Synthetic
fixtures are exempt.

**Long-running fetches:** Graph/Gmail exhaust-to-nextLink and large `gap` runs must use
`terminal(background=true, notify_on_complete=true)` — foreground defaults time out at 180s.

**READ-ONLY MAIL ACCESS:** Only `gmail search` / `gmail get` (readonly scope) and
Microsoft Graph GET requests are permitted. Never send, reply, forward, modify,
label, or delete mailbox content from this skill.

## When to Use

- A matter's file may be missing correspondence (not everything gets filed).
- A provider outage or account switch pushed case email into a secondary mailbox
  (e.g. personal Gmail) for a span of the case.
- Before discovery responses, mediation, or a file audit, to confirm the server
  file reflects all client/firm correspondence in the relevant window.

## Prerequisites

- `legal-casegraph` index built for the matter (`casegraph.py build`) — supplies the
  chronology anchors (incident date, first contact), entity registry, and the
  document index the gap check diffs against.
- Firm config outside the repo (`$HERMES_HOME/matter_mail_firm.json`): firm contact
  addresses, `mail_accounts` (label, owner address, transport: graph /
  outlook-export / gmail-api), provider outage priority windows, privilege keywords.
  Example shape: `fixtures/firm_config_example.json`.
- For live fetch: Microsoft Graph credentials (`tools/microsoft_graph_client.py`) for
  the M365 mailbox; the Outlook client itself for accounts Graph cannot query
  (export path); optionally the google-workspace skill (Gmail readonly scope) for
  the gmail-api transport.

## How to Run

All commands: `python skills/legal/matter-mail/scripts/matter_mail.py <cmd> <matter_dir>`

1. **Preflight.** `casegraph.py status <matter_dir>` must report the index current;
   rebuild if stale.
2. **Context.** `matter_mail.py context <matter_dir>` derives the scan window
   (incident date minus margin, through today) and the participant set (client
   entities + firm contacts). Every derived value carries provenance (source
   citation to the chronology entry or config key). **Present the window and
   participants to the attorney and get confirmation before scanning** — override
   with `--window-start/--window-end` or `add-participant` as directed.
3. **Plan.** `matter_mail.py plan <matter_dir> --json` emits batched, read-only
   provider queries. Priority windows (e.g. a provider outage span from firm config)
   add exhaustive-mode rows for the fallback mailbox.
4. **Fetch (read-only).** For each plan row, run the matching tooling and save the
   results to a scratch directory:
   - `graph` rows: `GET /me/messages` via `tools/microsoft_graph_client.py` with the
     row's KQL in `$search` and `$select=internetMessageId,subject,from,toRecipients,
     ccRecipients,receivedDateTime,conversationId,hasAttachments,body` — save the
     JSON responses (`{"value": [...]}` collections ingest natively).
   - `outlook-export` rows: follow the row's instructions — export the window from
     the Outlook client as `.eml`/`.msg` (drag-export) or `.pst` converted to
     `.eml`/`.mbox`; a Google Takeout `.mbox` of the Gmail account is an equivalent
     bulk source.
   - `gmail` rows: `google_api.py gmail search "<query>" --max 100`, then
     `gmail get <id>` per hit (readonly; reduced fidelity — no Message-ID/Cc/
     attachments — so prefer Graph or client export when possible).
   Run rows sequentially; back off on HTTP 429.
5. **Ingest.** `matter_mail.py ingest <matter_dir> --source <scratch_dir>`. Filters
   run before persistence: the mailbox owner's own address never qualifies a message
   (at least one non-owner case participant must appear in From/To/Cc), messages
   dated outside the confirmed window are dropped, and non-qualifying content is
   counted then discarded — it never touches the matter directory. For
   exhaustive/outage rows, add `--allow-unmatched` to keep header-only triage rows.
6. **Gap + report.** `matter_mail.py gap <matter_dir>` (exit 1 = gaps found), then
   `matter_mail.py report <matter_dir>`. Re-run `casegraph.py build` so staged
   correspondence enters the index, and run the casegraph gates on the report file.
7. **Attorney review.** Walk the report's verification checklist with the attorney.
   Filing decisions are the attorney's; matter-mail stages copies only.

## Output Sections (gap_report.md)

| Section | Description |
|---|---|
| Summary | Counts per check, scan window + anchors with provenance |
| Missing From Case File | Matched mail with no filed counterpart — attorney review required |
| Filed Conflicts | Message-ID matches a filed copy but the body differs — review required |
| Filed But Body Unverified | Message-ID matched but a body hash was unavailable — confirm |
| Probably Filed — Verify | Subject+date matched an indexed document; confirm before relying |
| Attachment Gaps | Mail attachments whose hash/name match no indexed file; Graph attachments not yet fetched |
| Thread Gaps | Referenced Message-IDs that exist nowhere (mailbox or file) |
| Coverage Gaps | Spans in the window with no matched mail — confirm nothing occurred |
| Unmatched Triage | Header-only candidates from exhaustive-mode ingest |
| Verification Checklist | Attorney sign-off steps |

## Privilege

The privilege screen only *flags* (`firm_internal`, `counsel_keyword`) to route items
for attorney review — it renders no privilege conclusions and must not be treated as
a privilege log. Any onward use of flagged correspondence requires attorney review of
each item against the source document.

## Verification

- `matter_mail.py selftest` — offline end-to-end self-test (must PASS).
- `pytest tests/skills/test_matter_mail.py` — fixture-based pipeline tests.
- Casegraph gates (`verify-cites`, `check-isolation`) run on the gap report like on
  any other output; every anchor in the report carries a source citation.

## Pitfalls

- **Do not hardcode timeframes or people.** The scan window comes from the matter
  chronology with attorney confirmation; staff addresses and mail accounts come from
  the firm config. Outage spans are `priority_windows` config entries, not code.
- **Configure `mail_accounts` with owner addresses.** Without them the owner's own
  address counts as a participant and the scan would stage the entire personal
  mailbox — the owner rule is the central privacy control.
- **Third-party accounts in Outlook are usually NOT Graph-queryable.** Use the
  `outlook-export` transport (client export) or `gmail-api` for the Gmail account;
  do not assume the work-account Graph token can see it.
- **Reduced-fidelity JSON**: google-workspace output lacks Message-ID/Cc/attachments;
  a "missing" verdict from reduced rows may be a fidelity artifact — re-fetch via
  Graph or as `.eml` before relying on it. The report labels provenance per item.
- **Graph attachments need an expansion fetch** — `hasAttachments` rows appear as
  "unfetched — verify" until the attachments endpoint is fetched.
- **Participant-mode misses unknown addresses** by design (privacy of mixed personal
  mailboxes). Use exhaustive mode for high-risk windows and review triage rows.
- **Never write real mailbox exports into this repo** — scratch dirs and matter
  directories only. Fixtures here are synthetic only.
- **No legal conclusions**: the report states what was found and what requires
  attorney review; it never asserts that a gap is spoliation or that correspondence
  is privileged.
