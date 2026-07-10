<!-- SYNTHETIC / NON-CLIENT / TEST ONLY -->

**SYNTHETIC / NON-CLIENT / TEST ONLY**

# Matter-Mail Fixtures

Synthetic test data for the matter-mail correspondence gap scanner. All names,
addresses (`.synthetic` TLD), dates, and facts are invented and belong to the
same Test Valley Railroad (TVRR) universe as the discovery-skill fixtures.
Nothing here is client data; nothing here may be treated as confidential facts.

| Path | Purpose |
|---|---|
| `firm_config_example.json` | Example firm config: contacts, `mail_accounts` (Outlook-first topology: work mailbox via Graph, Gmail-in-Outlook via client export), provider outage priority window, privilege keywords. Real configs live OUTSIDE the repo (`$HERMES_HOME/matter_mail_firm.json`). |
| `mailbox_export/` | Synthetic `.eml` export simulating a mixed personal/work mailbox: one already-filed email, one missing email with an attachment, one reply exposing a thread gap, one privileged-flagged email, one personal email that the participant filter must exclude. |
| `graph_export/` | Synthetic Microsoft Graph `GET /me/messages` collection JSON (primary transport; carries `internetMessageId` for exact filed matching, plus a `hasAttachments` row exercising the unfetched-attachment surfacing). |
| `gmail_export/` | Synthetic google-workspace `gmail search`/`gmail get` JSON (fallback transport; reduced fidelity: no Message-ID / Cc / attachments) exercising the probable-match path. |

Tests build the matter directory itself (casegraph index, filed documents,
chronology) in a temp dir at run time — no matter scaffolds are committed to
the repo, matching the casegraph isolation model.

**ATTORNEY REVIEW REQUIRED — fixtures are for validation only; outputs from
fixtures are not legal work product.**
