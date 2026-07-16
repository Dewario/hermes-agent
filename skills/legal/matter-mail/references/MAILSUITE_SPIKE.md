# Mailsuite Backend Spike (Future)

**Status:** interface notes only — no Hermes integration, no live runs.  
**Policy:** firm-only mail accounts; read-only transport; synthetic fixtures in-repo.

[mailsuite](https://github.com/seanthegeek/mailsuite) is a candidate future fetch
backend for matter-mail live workflows. Today matter-mail ingests exported artifacts
(`.eml`, Graph JSON, Gmail JSON) via `matter_mail.py`. A mailsuite adapter would sit
**between** firm-approved fetch plans and the existing ingest pipeline — it would not
replace offline ingest, gap analysis, or casegraph handoff.

See also: [LIVE_MAIL_HARDENING.md](LIVE_MAIL_HARDENING.md).

## Design constraints (non-negotiable)

- **Firm-only:** only addresses listed in `$HERMES_HOME/matter_mail_firm.json`
  `mail_accounts` may be queried. Personal mailboxes outside firm config are out of scope.
- **Read-only:** list/search/get message bodies and headers; no send, modify, label, or delete.
- **No credentials in repo:** connection secrets live in profile `.env` or OS keychain;
  matter-mail CLI continues to consume normalized exports, not live sockets.
- **Owner-address rule preserved:** the scanned mailbox owner's address is never a
  qualifying case participant (see `matter-mail/SPEC.md` §3).
- **Matter-scoped output:** fetched payloads land under `<matter_dir>/correspondence/<provider>/`
  for ingest — never under `hermes-agent/`.

## Proposed `MailboxConnection` shape

Typed boundary for a single firm-approved account. Hermes or a thin wrapper would
construct one connection per `mail_accounts` entry at fetch time.

```python
@dataclass(frozen=True)
class MailboxConnection:
    """Read-only handle for one firm-config mail account."""

    label: str              # firm_config mail_accounts[].label (e.g. "work")
    address: str            # canonical mailbox address (lowercase)
    transport: str          # "graph" | "outlook-export" | "gmail-api" | "mailsuite"
    firm_config_path: Path  # resolved matter_mail_firm.json (profile-scoped)
    matter_dir: Path        # active matter; plans + exports scoped here
    read_only: bool = True  # must stay True for legal use

    def search(self, query: str, *, page_token: str | None = None) -> SearchPage: ...
    def get_message(self, message_id: str) -> NormalizedMessage: ...
    def export_page(self, page: SearchPage, dest_dir: Path) -> ExportManifest: ...
```

Supporting types (sketch):

| Type | Role |
|------|------|
| `SearchPage` | `items: list[MessageRef]`, `next_token: str \| None`, `account_label` |
| `MessageRef` | `provider_id`, `internet_message_id`, `received_at`, `subject` (headers only) |
| `NormalizedMessage` | Same fields matter-mail ingest already accepts: Message-ID, From/To/Cc,
  date, subject, body text, `source_transport`, `account_label` |
| `ExportManifest` | JSON sidecar listing exported paths + query window for audit |

`outlook-export` and `gmail-api` remain manual/direct transports; `mailsuite` would
implement `MailboxConnection` for accounts where a unified Python fetch layer is desired.

## Integration seam (future)

```
firm_config mail_accounts[]
        │
        ▼
  plan (matter_mail.py plan)  ──►  per-account query strings
        │
        ▼
  MailboxConnection.search/get  ──►  correspondence/<provider>/*.json|.eml
        │
        ▼
  matter_mail.py ingest ──►  gap report (unchanged)
```

No code path in Hermes should import mailsuite until:

1. H1/H2/H3 checklist in `LIVE_MAIL_HARDENING.md` passes for the target matter.
2. `PROVIDER_AUTH.md` permits remote processing of fetched mail content.
3. Pagination and large pulls use `terminal(background=true, notify_on_complete=true)`.

## Open questions

- Does mailsuite expose stable `internetMessageId` for Graph-backed mailboxes?
- How does it handle Gmail-via-Outlook vs native Graph parity?
- Rate limits and retry policy for multi-account batch plans.
- Whether exports should default to JSON (Graph-shaped) or `.eml` for attorney portability.

## Explicitly out of scope for this spike

- Wiring mailsuite into `matter_mail.py` or core Hermes tools.
- CI or pilot gates against live mailboxes.
- Replacing `tools/microsoft_graph_client.py` or google-workspace skill paths.
