# Live Matter-Mail Hardening

Real mailbox work is firm-only: use firm-managed `mail_accounts` and the
active profile's `$HERMES_HOME/matter_mail_firm.json`. Do not scan a personal
mailbox or add an unapproved account to a live matter workflow.

Before any remote model receives mailbox or matter text, confirm
`03_attorney/PROVIDER_AUTH.md` is complete. If it is absent or incomplete,
stop; synthetic fixtures are the only exception.

Run Graph/Gmail pagination, large ingest jobs, and `matter_mail.py gap` with
`terminal(background=true, notify_on_complete=true)`. Keep reports and
scratch exports in the matter directory, never this repository.

## H1/H2/H3 readiness checklist

- [ ] **H1 — firm-only scope:** firm config names each approved account, owner,
  and read-only transport; owner-only messages do not qualify.
- [ ] **H2 — provider authorization:** `PROVIDER_AUTH.md` permits the planned
  handling before remote processing of live content.
- [ ] **H3 — resilient execution:** long fetch, ingest, and gap commands run
  background+notify and preserve progress artifacts under the matter directory.

`mailsuite` (https://github.com/seanthegeek/mailsuite) is a future backend
spike only. Do not integrate it into Hermes or use it for current live runs.
