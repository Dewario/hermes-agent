# Matter-Mail — Correspondence Gap Scanner (Spec)

**Status:** v1.1 spec, implemented 2026-07-08 (autonomous build; revised same day for
the Outlook-first topology + adversarial review findings)
**Owner gate:** attorney review required before any real-matter use. Synthetic data only in this repo.
**Depends on:** `legal-casegraph` (matter index); for live fetch:
`tools/microsoft_graph_client.py` (Microsoft Graph, primary) and optionally
`productivity/google-workspace` (Gmail API fallback, read-only).

## 1. What this is

Matter-mail answers one question per matter: **"Which case-relevant emails exist in the
attorney's mailboxes but never made it into the server case file?"** Not every
correspondence gets filed; during provider outages whole months of case email can live
only in a secondary mailbox.

**Mail topology (Outlook-first):** both the work mailbox (M365) and any personal
account (e.g. Gmail) are assumed to be accessed through Microsoft Outlook. Each
scanned mailbox is a `mail_accounts` entry in the firm config with a per-account
fetch **transport**:

- `graph` — Microsoft Graph API (the M365 work mailbox; full fidelity: Graph message
  JSON carries `internetMessageId`).
- `outlook-export` — manual export from the Outlook client (.eml/.msg drag-export,
  or .pst converted to .eml/.mbox). The right path for third-party accounts added to
  Outlook, which Graph generally cannot query.
- `gmail-api` — direct Gmail API via the google-workspace skill (readonly), as a
  fallback when fetching the Gmail account directly is preferable.

The pipeline:

1. **Context derivation** — the scan window and participant list come from the matter
   itself (casegraph chronology + entity registry + firm config), not from memory or
   hardcoded values. The agent proposes; the attorney confirms.
2. **Batched, per-account scanning** — matter-mail emits per-account query plans
   (Graph KQL, Gmail search operators, or export instructions). The fetch itself is
   performed by existing, already-authorized tooling. Matter-mail never holds mail
   credentials.
3. **Deterministic ingest + gap analysis** — fetched messages are normalized, deduped
   (Message-ID, then provider id, then content hash), owner-aware participant-filtered
   and window-filtered BEFORE persistence, privilege-screened, and diffed against the
   casegraph index. Output is an attorney-review gap report with exit-code gates.

## 2. What this is NOT (honest usefulness assessment)

- **Not a mail client and not a fetcher.** The core CLI is offline and stdlib-only
  (`extract_msg` optional for .msg). It consumes exported artifacts so every stage is
  testable without OAuth, and live use adds zero new auth surface.
- **Not semantic relevance ranking.** Participant + window matching is deterministic.
  A message from an unknown address will be missed in participant mode; exhaustive
  mode (priority windows) exists for high-risk spans and triages by headers.
- **Not an auto-filer.** Matter-mail stages copies under `<matter_dir>/correspondence/`
  and reports. Filing is an attorney decision.
- **Not privilege review.** The privilege screen is a keyword/participant flagger that
  routes items to attorney review; it renders no conclusions.

## 3. Isolation and privacy model

- **Physical isolation:** all state lives at `<matter_dir>/.matter_mail/` and
  `<matter_dir>/correspondence/`, inside the matter directory, outside this repo —
  identical to casegraph's model.
- **Mailbox-owner rule (the personal-mailbox problem):** every message in a mailbox
  involves its owner, so the owner's own address carries no case signal. Addresses in
  `mail_accounts` (plus `ingest --owner`) are excluded from participant matching AND
  from plan query targets: a message qualifies only when a **non-owner** case
  participant appears in From/To/Cc. Non-qualifying mail is counted
  (`excluded_non_matter`) and its content discarded — never written anywhere.
- **Window enforcement (cross-matter leakage):** ingest drops messages dated outside
  the confirmed scan window (±1 day tolerance; `excluded_out_of_window` count;
  `--allow-out-of-window` to override). Firm contacts appear in *every* matter's
  correspondence, so an over-broad export must not leak other matters' mail into this
  matter's record. Undated messages are kept (over-report, never silently under-report).
- **Firm config, not hardcoded people:** staff addresses, mail accounts, outage
  windows, margins live in `$HERMES_HOME/matter_mail_firm.json` (or `--firm-config`).
  The repo ships only a synthetic example. `window_margin_days` in config is honored;
  CLI `--margin-days` wins.
- **Read-only mail access:** Graph GET / `gmail search|get` (readonly) only.
  Send/modify/label operations are prohibited in the skill text and unused by the CLI.
- **One active matter per invocation:** every command takes an explicit `matter_dir`.
  `--provider` (a staging path segment) is validated against `[a-z0-9_-]{1,32}`.

## 4. Data model

`<matter_dir>/.matter_mail/`: `scan_context.json` (window/participants/accounts with
provenance), `messages.jsonl` (normalized rows), `gap_report.json`,
`participants.json` (manual additions).

`<matter_dir>/correspondence/<provider>/` — staged copies of MATCHED messages only,
named `YYYY-MM-DD_<msgid_hash12>` (collisions uniquify, never overwrite; writes are
atomic): `.eml`/`.msg` sources verbatim; JSON sources as the original provider object
(body included — the staged copy is what the attorney reviews and what casegraph
indexes). Header-only triage rows and excluded mail are never staged.

Normalized row highlights (see code for full shape): `msgid` (canonical Message-ID),
`msgid_hash` (dedup key: Message-ID > provider message id > content fallback
including recipients and body hash, so same-day same-subject replies never collapse),
`provenance` (`full` | `graph_json` | `reduced`), `has_attachments_unfetched` (Graph
`hasAttachments` without an expanded attachment list), `privilege_flags`,
`participants_matched`, `staged_relpath`.

Dedup fidelity upgrade: a body-bearing copy of an already-ingested message (e.g.
gmail `get` after `search`) replaces the body-less row in place; a duplicate whose
staged file has gone missing re-stages it.

## 5. Commands (CLI: `scripts/matter_mail.py`)

All commands support `--json`. Gate-style commands exit non-zero on actionable findings.

- `context <matter_dir> [--firm-config PATH] [--window-start] [--window-end]
  [--margin-days N]` — derive scan context: participants (firm contacts +
  client-role casegraph entities + manual), mail accounts, window (incident-date
  anchor − margin → today, chronology/doc-date fallbacks, every value with
  provenance), priority windows clamped to the scan window. Fails with guidance when
  no window is derivable.
- `add-participant <matter_dir> --name NAME [--email ADDR ...] [--role ROLE]` —
  register an ad-hoc participant (keys use casegraph-compatible normalization).
- `plan <matter_dir>` — per-account query plans: Graph KQL participant chunks
  (`participants:<addr>` + `received` range), Gmail operator queries
  (`after:`/`before:`+1d exclusive), or Outlook export instructions. Owner addresses
  are excluded from all query targets. Priority windows emit exhaustive rows on the
  configured account's transport (headers-only triage at ingest via
  `--allow-unmatched`).
- `ingest <matter_dir> --source PATH [--provider TAG] [--owner ADDR ...]
  [--allow-unmatched] [--allow-out-of-window]` — normalize `.eml`, `.mbox`
  (Takeout / converted .pst), `.msg` (optional extract_msg), Microsoft Graph JSON
  (single message, array, or `{"value": [...]}` collection), and google-workspace
  JSON. Order of filters: dedup → window → owner-aware participant match →
  privilege flags → stage. Malformed/unreadable files are counted, never fatal.
- `gap <matter_dir> [--strict]` — diff against the case file:
  1. **Filed check** — Message-ID match against `.eml` files in the matter (outside
     `correspondence/`), body-hash verified: hash match → `filed_exact`
     (`body_verified: true`); mismatch → `filed_conflicts` (HARD — altered/truncated
     filed copy or spoofed id); hash unavailable on either side → `filed_unverified`
     (WARN — never reported as verified). Duplicate filed ids accumulate all body
     hashes. Filed .eml parsing skips attachment decoding (perf).
  2. **Probable check** — normalized subject (≥8 chars AND ≥2 tokens) found in an
     indexed doc's text together with a boundary-anchored date variant (±1 day) →
     `probable_filed` (WARN: verify).
  3. **Attachment gaps** — checked for EVERY matched message (including filed ones —
     a filed email body does not file its attachments): sha256 match → ok; name-only
     → probable; else missing (HARD). Graph rows with `hasAttachments` and no list →
     `unfetched_verify` (WARN).
  4. **Thread gaps** — referenced Message-IDs existing nowhere (HARD).
  5. **Window coverage** — spans ≥ N days with no matched mail (WARN).
  Exit 1 on HARD findings; `--strict` also fails WARN-level findings.
- `report <matter_dir> [--output PATH]` — attorney-review markdown: banners, per-item
  provenance and privilege flags, filed-conflict/unverified sections, verification
  checklist.
- `status <matter_dir>` — state consistency gate: context present, staged copies on
  disk, gap report not older than the message store.
- `selftest` — offline end-to-end self-test.

## 6. Live-fetch procedure (SKILL.md, not CLI)

1. `casegraph.py status` → `matter_mail.py context` → attorney confirms window,
   participants, and accounts → `matter_mail.py plan`.
2. Per plan row: Graph rows via `tools/microsoft_graph_client.py`
   (`GET /me/messages` with `$search` KQL and `$select=internetMessageId,subject,from,
   toRecipients,ccRecipients,receivedDateTime,conversationId,hasAttachments,body`),
   saving JSON to a scratch dir; gmail rows via `google_api.py gmail search/get`
   (readonly); outlook-export rows are manual export instructions. Sequential, with
   backoff on 429.
3. `matter_mail.py ingest` → `gap` → `report`; then `casegraph.py build` and the
   casegraph gates on the report.
4. Attorney reviews; filing decisions are human.

## 7. Failure modes (surfaced, not hidden)

- **Reduced-provenance rows** (gmail JSON: no Message-ID/Cc/attachments) match by
  subject+date only; each such item is labeled and the report says exactly what could
  not be checked. Graph JSON removes this for the work mailbox (`internetMessageId`),
  but its attachments still need an expansion fetch (`unfetched_verify`).
- **Cross-format body comparison** (Graph HTML vs filed .eml plain text) can
  false-conflict on rendering differences — a conflict is a review flag, never a
  conclusion; over-report, never silent under-report.
- **Unknown-address relevant mail** outside priority windows: missed by design in
  participant mode; the report's coverage section states the participant set used.
- **Clock/timezone skew:** all dates normalize to UTC dates (ISO offsets honored);
  matching uses ±1-day tolerance; window edges get the same tolerance at ingest.
- **.msg without extract_msg:** counted and reported with guidance (re-export as
  .eml), never silently dropped.

## 8. Gates and repo hygiene

- Validator: SKILL.md frontmatter, confidentiality + attorney-review language,
  synthetic-labeled fixtures, no matter scaffolds in-repo. Real matter state lives
  outside the repo per §3.
- Tests: `tests/skills/test_matter_mail.py` — full pipeline offline, including
  red-team regressions for the adversarial review findings (owner-addressed personal
  mail, same-day reply hash collisions, empty-body Message-ID spoofing, name-boundary
  over-capture, out-of-window leakage, `--provider` path traversal).
- Casegraph interplay is additive: matter-mail reads casegraph state read-only;
  staged correspondence enters the index only via the normal `casegraph build`.
