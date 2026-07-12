#!/usr/bin/env python3
"""Matter-mail — correspondence gap scanner for legal matters.

Answers one question per matter: which case-relevant emails exist in the
attorney's mailboxes but never made it into the server case file?

Design contract (see SPEC.md):
- Offline core: this CLI consumes exported artifacts (.eml/.mbox/.msg files,
  Microsoft Graph JSON, google-workspace JSON). It never holds mail
  credentials and never fetches.
- Outlook-first topology: both the work mailbox and any personal (e.g. Gmail)
  account are assumed to be accessed through Microsoft Outlook. Fetch
  transports are per-account config (`mail_accounts`): "graph" (Microsoft
  Graph API), "outlook-export" (manual export from the Outlook client), or
  "gmail-api" (direct Gmail API fallback).
- All state lives INSIDE the matter directory (``<matter_dir>/.matter_mail/``
  and ``<matter_dir>/correspondence/``), outside this repo.
- Participant filter runs BEFORE persistence: personal mail with no case
  participant is counted and discarded — its content never touches disk.
  The scanned mailbox owner's own address is NOT a qualifying participant
  (every message in a mailbox involves its owner); at least one non-owner
  participant must appear in From/To/Cc.
- Messages outside the confirmed scan window are excluded at ingest (count
  only) so other matters' correspondence cannot leak into this matter's
  record via an over-broad export.
- Deterministic: Message-ID dedup, hash matching, boundary-anchored date
  variants. No inference. Reduced-fidelity inputs are labeled, never
  upgraded silently; a Message-ID match without a verifiable body is
  reported as filed-UNVERIFIED, never as verified.
- Gate commands exit non-zero on actionable findings so skills/CI can chain.

Stdlib-only core (extract_msg optional for .msg). Synthetic data only in this
repository. Attorney review required before any real-matter use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from email import message_from_bytes, policy
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

SCHEMA_VERSION = 2
TOOL_VERSION = "1.1.0"

STATE_DIRNAME = ".matter_mail"
CORR_DIRNAME = "correspondence"
CASEGRAPH_DIRNAME = ".casegraph"

DEFAULT_MARGIN_DAYS = 30
DEFAULT_COVERAGE_GAP_DAYS = 14
ADDR_CHUNK = 6  # addresses per provider query (query-length headroom)
MIN_NAME_MATCH_LEN = 4  # normalized display-name length required to match
DATE_TOLERANCE_DAYS = 1  # subject+date probable matching tolerance
MIN_SUBJECT_MATCH_LEN = 8
MIN_SUBJECT_MATCH_TOKENS = 2
_PROVIDER_TAG_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
VALID_TRANSPORTS = ("graph", "outlook-export", "gmail-api")

CLIENT_ROLE_HINTS = ("client", "plaintiff", "claimant")
INCIDENT_EVENT_RE = re.compile(
    r"injur|incident|accident|collision|derail|fall|struck|amputat", re.IGNORECASE
)
FIRST_CONTACT_EVENT_RE = re.compile(
    r"first contact|initial (?:contact|consult)|intake|retain|engagement", re.IGNORECASE
)

DEFAULT_PRIVILEGE_KEYWORDS = [
    "attorney-client",
    "attorney client",
    "work product",
    "privileged",
    "legal advice",
    "litigation hold",
]

_SUBJECT_TAG_RE = re.compile(r"^\s*(?:\[[^\]]{1,40}\]\s*|(?:re|fw|fwd|aw|sv)\s*[:\]]\s*)+",
                             re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


# ── small utilities ─────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_identifier(s: str) -> str:
    """Text normalization for subject/body/keyword matching.

    NFKC -> casefold -> strip punctuation except @ and . (kept so email
    addresses inside subjects/bodies survive) -> collapse whitespace.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.casefold()
    s = re.sub(r"[^\w\s@.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_name(s: str) -> str:
    """Name/entity-key normalization: NFKC -> casefold -> strip ALL
    punctuation -> collapse whitespace. Identical contract to casegraph's
    _normalize_identifier, so participant keys interoperate with casegraph
    entity keys ('J.T.' -> 'j t')."""
    s = unicodedata.normalize("NFKC", s)
    s = s.casefold()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _normalize_subject(subject: str) -> str:
    """Strip reply/forward/bracket-tag prefixes, then normalize."""
    s = subject or ""
    prev = None
    while prev != s:
        prev = s
        s = _SUBJECT_TAG_RE.sub("", s)
    return _normalize_identifier(s)


def _normalize_body_text(text: str) -> str:
    text = _HTML_TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def _canonical_msgid(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = raw.strip().strip("<>").strip()
    return m or None


def _parse_date_any(value: Optional[str]) -> Optional[date]:
    """Parse RFC 2822, ISO 8601 (offset-aware, converted to UTC), or common
    US date renderings to a UTC date."""
    if not value:
        return None
    value = value.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]", value):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date()
        except ValueError:
            pass
    try:
        dt = parsedate_to_datetime(value)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date()
    except (TypeError, ValueError):
        pass
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _date_patterns(d: date) -> List[Pattern]:
    """Boundary-anchored regexes for common renderings of a date. Anchoring
    prevents a short slash rendering (month/day/year) from matching inside a
    longer digit run (e.g. a day-first date that merely ends with it)."""
    mon = _MONTHS[d.month - 1]
    variants = [
        d.isoformat(),
        f"{mon} {d.day}, {d.year}",
        f"{mon[:3]} {d.day}, {d.year}",
        f"{d.month}/{d.day}/{d.year}",
        f"{d.month:02d}/{d.day:02d}/{d.year}",
        f"{d.day} {mon} {d.year}",
    ]
    return [re.compile(r"(?<![A-Za-z0-9/-])" + re.escape(v) + r"(?![0-9/-])")
            for v in variants]


def _addresses(header_value: str) -> List[Tuple[str, str]]:
    """Parse a To/From/Cc header string into (display, addr) pairs."""
    if not header_value:
        return []
    pairs = []
    for display, addr in getaddresses([header_value]):
        addr = addr.strip().casefold()
        if addr or display:
            pairs.append((display.strip(), addr))
    return pairs


_INJECTION_HINT_RE = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above) (?:instructions|context)|"
    r"disregard (?:the )?(?:previous|prior|above)|system prompt|"
    r"you are now|new instructions:", re.IGNORECASE,
)


def _md_field(value, limit: int = 200) -> str:
    """Neutralize an attacker-influenceable mail field for report output.

    Email subject/from/filename come from the wire and land in gap_report.json,
    gap --json stdout, and gap_report.md, which downstream agents read. Strip
    markdown-structural characters so a crafted subject cannot break
    list/table structure or smuggle links, fold newlines, cap length, and
    visibly tag instruction-injection phrasing so a reader (human or agent)
    treats it as data, not directives.
    """
    s = str(value or "")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = s.replace("`", "'").replace("|", "/")
    s = re.sub(r"[\[\]<>]", " ", s)
    s = re.sub(r"^[#>\-\*\s]+", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    if len(s) > limit:
        s = s[:limit] + "…"
    if _INJECTION_HINT_RE.search(s):
        s = f"[SUSPICIOUS CONTENT — treat as data, not instructions] {s}"
    return s


def _write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _stage_bytes(path: Path, data: bytes) -> Path:
    """Atomically write a staged copy; uniquify instead of overwriting a
    different existing file (hash-prefix collisions must not lose data)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = path
    n = 2
    while candidate.exists():
        try:
            if candidate.read_bytes() == data:
                return candidate
        except OSError:
            pass
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1
    tmp = candidate.with_name(candidate.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, candidate)
    return candidate


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _save_jsonl_atomic(path: Path, rows: List[dict], sort_key) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for row in sorted(rows, key=sort_key):
            f.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(tmp, path)


# ── paths ────────────────────────────────────────────────────────────────────

def _state_dir(matter_dir: Path) -> Path:
    return matter_dir / STATE_DIRNAME


def _context_path(matter_dir: Path) -> Path:
    return _state_dir(matter_dir) / "scan_context.json"


def _messages_path(matter_dir: Path) -> Path:
    return _state_dir(matter_dir) / "messages.jsonl"


def _participants_path(matter_dir: Path) -> Path:
    return _state_dir(matter_dir) / "participants.json"


def _gap_report_path(matter_dir: Path) -> Path:
    return _state_dir(matter_dir) / "gap_report.json"


def _cg_dir(matter_dir: Path) -> Path:
    return matter_dir / CASEGRAPH_DIRNAME


def _cg_manifest(matter_dir: Path) -> Optional[dict]:
    p = _cg_dir(matter_dir) / "manifest.json"
    if not p.exists():
        return None
    return _load_json(p)


def _cg_documents(matter_dir: Path) -> List[dict]:
    return _load_jsonl(_cg_dir(matter_dir) / "documents.jsonl")


def _cg_entities(matter_dir: Path) -> dict:
    p = _cg_dir(matter_dir) / "entities.json"
    if not p.exists():
        return {}
    return _load_json(p)


def _cg_chronology(matter_dir: Path) -> List[dict]:
    return _load_jsonl(_cg_dir(matter_dir) / "chronology.jsonl")


def _cg_text_cache(matter_dir: Path) -> Path:
    return _cg_dir(matter_dir) / "text"


# ── firm config ──────────────────────────────────────────────────────────────

def load_firm_config(explicit: Optional[str]) -> Tuple[dict, str]:
    """Load firm config: --firm-config > $MATTER_MAIL_FIRM_CONFIG >
    $HERMES_HOME/matter_mail_firm.json > ~/.hermes/matter_mail_firm.json.

    Returns (config, source_description). Missing config is not an error —
    participants can still come from casegraph entities and add-participant.
    """
    candidates: List[Tuple[Path, str]] = []
    if explicit:
        candidates.append((Path(explicit), "--firm-config"))
    env = os.environ.get("MATTER_MAIL_FIRM_CONFIG")
    if env:
        candidates.append((Path(env), "$MATTER_MAIL_FIRM_CONFIG"))
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        candidates.append((Path(hermes_home) / "matter_mail_firm.json", "$HERMES_HOME"))
    else:
        # Profile-safe: only the active HERMES_HOME. Never fall back to
        # Path.home()/".hermes" — that crosses profile boundaries when a
        # profile is missing its firm config (red-team finding B2).
        try:
            from hermes_constants import get_hermes_home
            candidates.append(
                (get_hermes_home() / "matter_mail_firm.json", "get_hermes_home()")
            )
        except Exception:
            pass

    for path, label in candidates:
        if path.exists():
            try:
                cfg = _load_json(path)
            except (json.JSONDecodeError, OSError) as e:
                raise SystemExit(f"ERROR: firm config at {path} is unreadable: {e}")
            return cfg, f"{label}:{path.name}"
        if label == "--firm-config":
            raise SystemExit(f"ERROR: firm config not found: {path}")
    return {}, "none"


def _mail_accounts(firm_cfg: dict, notes: List[str]) -> List[dict]:
    """Mailboxes to scan (Outlook-first topology). Each: label, address
    (the mailbox owner's address — excluded from participant matching),
    transport (graph | outlook-export | gmail-api)."""
    accounts = []
    for acct in firm_cfg.get("mail_accounts", []):
        transport = (acct.get("transport") or "graph").casefold()
        if transport not in VALID_TRANSPORTS:
            notes.append(f"WARNING: account '{acct.get('label')}' has unknown "
                         f"transport '{transport}' — treated as outlook-export")
            transport = "outlook-export"
        accounts.append({
            "label": acct.get("label") or transport,
            "address": (acct.get("address") or "").casefold() or None,
            "transport": transport,
        })
    if not accounts:
        notes.append("no mail_accounts configured — refusing default anonymous "
                     "account (privacy fail-closed). Set firm config "
                     "mail_accounts with label, address, and transport.")
    for acct in accounts:
        if not acct.get("address"):
            notes.append(f"ERROR: mail account '{acct.get('label')}' is missing "
                         f"address — owner exclusion cannot run")
    return accounts


def _require_owner_addresses(accounts: List[dict], cmd: str) -> Optional[str]:
    """Return an error message if owner addresses are incomplete (H2)."""
    if not accounts:
        return (f"ERROR: {cmd} requires firm config mail_accounts with an "
                f"address on every account (owner exclusion is mandatory)")
    missing = [a.get("label") or "?" for a in accounts if not a.get("address")]
    if missing:
        return (f"ERROR: {cmd} refuses to proceed — mail_accounts missing "
                f"address for: {', '.join(missing)}")
    return None


# ── participants ─────────────────────────────────────────────────────────────

def _derive_participants(matter_dir: Path, firm_cfg: dict) -> List[dict]:
    """Participants = firm contacts + client-role casegraph entities +
    manual add-participant entries. Every entry carries provenance."""
    participants: Dict[str, dict] = {}

    for contact in firm_cfg.get("firm_contacts", []):
        name = contact.get("name", "")
        key = _normalize_name(name) or ",".join(contact.get("emails", []))
        if not key:
            continue
        participants[key] = {
            "key": key,
            "display": name,
            "emails": sorted({e.strip().casefold() for e in contact.get("emails", []) if e}),
            "role": contact.get("role", "firm"),
            "origin": "firm_config",
        }

    entities = _cg_entities(matter_dir)
    for key, ent in entities.items():
        role = (ent.get("role") or "").casefold()
        if not any(h in role for h in CLIENT_ROLE_HINTS):
            continue
        emails = sorted({
            a.strip().casefold()
            for a in ent.get("aliases", [])
            if "@" in a
        })
        participants.setdefault(key, {
            "key": key,
            "display": ent.get("display", key),
            "emails": emails,
            "role": ent.get("role", ""),
            "origin": "casegraph_entity",
        })

    pp = _participants_path(matter_dir)
    if pp.exists():
        for key, row in _load_json(pp).items():
            participants[key] = row

    return sorted(participants.values(), key=lambda r: r["key"])


class ParticipantMatcher:
    """Deterministic membership test for a message's address headers.

    Emails match exactly (casefold). Display names match as whole-token
    sequences (never substrings — 'Anna' must not match 'Susanna') and only
    when the normalized name is >= MIN_NAME_MATCH_LEN chars (initials like
    'J T' are too short by design, to keep personal mail out of the matter
    record).

    Owner identity is a *person*, not a single string: exact owner addresses,
    plus-address / local-part variants of those addresses, and display-name
    tokens that match an owner identity never qualify a message. Every message
    in a mailbox involves its owner, so owner hits carry no case signal."""

    def __init__(
        self,
        participants: List[dict],
        owner_emails: Iterable[str] = (),
        owner_names: Iterable[str] = (),
    ):
        self.owner_emails = {e.casefold() for e in owner_emails if e}
        self.owner_local_parts = {
            e.split("@", 1)[0].split("+", 1)[0].casefold()
            for e in self.owner_emails if "@" in e
        }
        self.owner_name_norms = {
            _normalize_name(n) for n in owner_names
            if n and len(_normalize_name(n)) >= MIN_NAME_MATCH_LEN
        }
        # Also treat firm_config participants whose email is an owner address
        # as owner identities for display-name exclusion.
        self.email_to_key: Dict[str, str] = {}
        self.name_keys: List[Tuple[str, str]] = []
        for p in participants:
            emails = [e.casefold() for e in p.get("emails", []) if e]
            is_owner_person = any(e in self.owner_emails for e in emails)
            if is_owner_person:
                norm = _normalize_name(p.get("display", ""))
                if len(norm) >= MIN_NAME_MATCH_LEN:
                    self.owner_name_norms.add(norm)
                continue  # never register owner as a case participant key
            for e in emails:
                self.email_to_key[e] = p["key"]
            norm = _normalize_name(p.get("display", ""))
            if len(norm) >= MIN_NAME_MATCH_LEN:
                self.name_keys.append((norm, p["key"]))

    def _is_owner_addr(self, addr: str) -> bool:
        if not addr:
            return False
        a = addr.casefold()
        if a in self.owner_emails:
            return True
        if "@" not in a:
            return False
        local, _, domain = a.partition("@")
        base_local = local.split("+", 1)[0]
        # Plus-address / alias on a known owner domain+local base.
        for oe in self.owner_emails:
            if "@" not in oe:
                continue
            o_local, _, o_domain = oe.partition("@")
            o_base = o_local.split("+", 1)[0]
            if domain == o_domain and base_local == o_base:
                return True
        return base_local in self.owner_local_parts and any(
            oe.endswith("@" + domain) for oe in self.owner_emails
        )

    def _is_owner_display(self, display: str) -> bool:
        if not display or not self.owner_name_norms:
            return False
        padded = f" {_normalize_name(display)} "
        return any(f" {n} " in padded for n in self.owner_name_norms)

    def match(self, header_pairs: Iterable[Tuple[str, str]]) -> List[str]:
        hits = set()
        for display, addr in header_pairs:
            if self._is_owner_addr(addr) or self._is_owner_display(display):
                continue
            if addr and addr.casefold() in self.email_to_key:
                hits.add(self.email_to_key[addr.casefold()])
                continue
            padded = f" {_normalize_name(f'{display} {addr}')} "
            for name, key in self.name_keys:
                if f" {name} " in padded:
                    hits.add(key)
        return sorted(hits)


# ── message normalization ───────────────────────────────────────────────────

def _msgid_hash(msgid: Optional[str], provider: str = "", provider_id: Optional[str] = None,
                from_: str = "", date_iso: Optional[str] = None, subject_norm: str = "",
                to: Iterable[str] = (), body_sha: Optional[str] = None) -> str:
    """Stable dedup key. Priority: Message-ID > provider message id >
    content fallback. The fallback includes recipients and the body hash so
    two same-day replies with identical normalized subjects ('Re: X' and
    'Re: Re: X') never collapse into one row (silent message loss)."""
    if msgid:
        return _sha256_bytes(("msgid\x1f" + msgid).encode("utf-8"))
    if provider_id:
        return _sha256_bytes(f"pid\x1f{provider}\x1f{provider_id}".encode("utf-8"))
    basis = "\x1f".join([
        "fallback", from_.casefold(), date_iso or "", subject_norm,
        ",".join(sorted(t.casefold() for t in to)), body_sha or "",
    ])
    return _sha256_bytes(basis.encode("utf-8"))


def normalize_eml(raw: bytes, include_attachments: bool = True) -> Optional[dict]:
    """Parse an RFC 822 message into the normalized row (full provenance)."""
    try:
        msg = message_from_bytes(raw, policy=policy.default)
    except Exception:
        return None

    def hdr(name: str) -> str:
        try:
            return str(msg.get(name, "") or "")
        except Exception:
            return ""

    body_text = ""
    try:
        body = msg.get_body(preferencelist=("plain", "html"))
        if body is not None:
            body_text = _normalize_body_text(str(body.get_content()))
    except Exception:
        body_text = ""

    attachments = []
    if include_attachments:
        try:
            for part in msg.iter_attachments():
                try:
                    payload = part.get_payload(decode=True) or b""
                except Exception:
                    payload = b""
                attachments.append({
                    "filename": part.get_filename() or "(unnamed)",
                    "size": len(payload),
                    "sha256": _sha256_bytes(payload) if payload else None,
                })
        except Exception:
            pass

    msgid = _canonical_msgid(hdr("Message-ID"))
    d = _parse_date_any(hdr("Date"))
    subject = hdr("Subject")
    subject_norm = _normalize_subject(subject)
    from_ = hdr("From")
    to = [f"{disp} <{addr}>".strip() if disp else addr
          for disp, addr in _addresses(hdr("To"))]
    refs = [r for r in (
        _canonical_msgid(tok) for tok in re.split(r"\s+", hdr("References")) if tok
    ) if r]
    in_reply_to = _canonical_msgid(hdr("In-Reply-To"))
    body_sha = _sha256_bytes(body_text.encode("utf-8")) if body_text else None

    return {
        "msgid": msgid,
        "msgid_hash": _msgid_hash(msgid, provider="eml", provider_id=None,
                                  from_=from_, date_iso=d.isoformat() if d else None,
                                  subject_norm=subject_norm, to=to, body_sha=body_sha),
        "provider": "eml",
        "provenance": "full",
        "provider_id": None,
        "thread_id": None,
        "date_iso": d.isoformat() if d else None,
        "from": from_,
        "to": to,
        "cc": [f"{disp} <{addr}>".strip() if disp else addr
               for disp, addr in _addresses(hdr("Cc"))],
        "subject": subject,
        "subject_norm": subject_norm,
        "participants_matched": [],
        "in_reply_to": in_reply_to,
        "references": refs,
        "attachments": attachments,
        "has_attachments_unfetched": False,
        "body_sha256": body_sha,
        "body_text": body_text,  # dropped before persistence
        "privilege_flags": [],
        "staged_relpath": None,
    }


def normalize_graph_json(obj: dict) -> Optional[dict]:
    """Normalize a Microsoft Graph message resource (the primary transport in
    the Outlook-first topology). Graph JSON carries internetMessageId, so
    Message-ID matching works at full fidelity; attachments are NOT expanded
    in a standard messages fetch — hasAttachments is surfaced so the gap
    report can demand a follow-up fetch instead of silently skipping them."""
    if not isinstance(obj, dict):
        return None
    if "internetMessageId" not in obj and "receivedDateTime" not in obj:
        return None

    def addr_list(key: str) -> List[str]:
        out = []
        for r in obj.get(key) or []:
            ea = (r or {}).get("emailAddress") or {}
            name = (ea.get("name") or "").strip()
            addr = (ea.get("address") or "").strip().casefold()
            if name and addr:
                out.append(f"{name} <{addr}>")
            elif addr or name:
                out.append(addr or name)
        return out

    fr = ((obj.get("from") or {}).get("emailAddress")) or {}
    from_ = ""
    if fr:
        name = (fr.get("name") or "").strip()
        addr = (fr.get("address") or "").strip().casefold()
        from_ = f"{name} <{addr}>".strip() if name else addr

    msgid = _canonical_msgid(obj.get("internetMessageId"))
    d = _parse_date_any(obj.get("receivedDateTime") or obj.get("sentDateTime"))
    subject = obj.get("subject", "") or ""
    subject_norm = _normalize_subject(subject)
    body_content = ((obj.get("body") or {}).get("content")) or obj.get("bodyPreview", "") or ""
    body_text = _normalize_body_text(body_content)
    body_sha = _sha256_bytes(body_text.encode("utf-8")) if body_text else None
    to = addr_list("toRecipients")

    return {
        "msgid": msgid,
        "msgid_hash": _msgid_hash(msgid, provider="graph", provider_id=obj.get("id"),
                                  from_=from_, date_iso=d.isoformat() if d else None,
                                  subject_norm=subject_norm, to=to, body_sha=body_sha),
        "provider": "graph",
        "provenance": "graph_json",
        "provider_id": obj.get("id"),
        "thread_id": obj.get("conversationId"),
        "date_iso": d.isoformat() if d else None,
        "from": from_,
        "to": to,
        "cc": addr_list("ccRecipients"),
        "subject": subject,
        "subject_norm": subject_norm,
        "participants_matched": [],
        "in_reply_to": None,
        "references": [],
        "attachments": [],
        "has_attachments_unfetched": bool(obj.get("hasAttachments")),
        "body_sha256": body_sha,
        "body_text": body_text,
        "privilege_flags": [],
        "staged_relpath": None,
    }


def normalize_gmail_json(obj: dict) -> Optional[dict]:
    """Normalize a google-workspace gmail search/get row (fallback transport;
    reduced provenance: no Message-ID, no Cc, no attachments — matching falls
    back to subject+date). Dedup keys on the stable gmail message id, so a
    search row and a get row for the same message collapse to one row."""
    if not isinstance(obj, dict) or "id" not in obj:
        return None
    d = _parse_date_any(obj.get("date", ""))
    subject = obj.get("subject", "") or ""
    subject_norm = _normalize_subject(subject)
    from_ = obj.get("from", "") or ""
    body_text = _normalize_body_text(obj.get("body", "") or "")
    to = [a for _, a in _addresses(obj.get("to", "") or "")] or \
         ([obj.get("to")] if obj.get("to") else [])
    return {
        "msgid": None,
        "msgid_hash": _msgid_hash(None, provider="gmail", provider_id=obj.get("id")),
        "provider": "gmail",
        "provenance": "reduced",
        "provider_id": obj.get("id"),
        "thread_id": obj.get("threadId"),
        "date_iso": d.isoformat() if d else None,
        "from": from_,
        "to": to,
        "cc": [],
        "subject": subject,
        "subject_norm": subject_norm,
        "participants_matched": [],
        "in_reply_to": None,
        "references": [],
        "attachments": [],
        "has_attachments_unfetched": False,
        "body_sha256": _sha256_bytes(body_text.encode("utf-8")) if body_text else None,
        "body_text": body_text,
        "privilege_flags": [],
        "staged_relpath": None,
    }


def normalize_msg_bytes(raw: bytes, path_name: str) -> Optional[dict]:
    """Normalize an Outlook .msg file (drag-export from the Outlook client).
    Requires the optional ``extract_msg`` package; returns None when the
    package is unavailable or the file is unreadable (callers count it)."""
    try:
        import extract_msg  # optional dependency
    except ImportError:
        return None
    try:
        import io
        m = extract_msg.Message(io.BytesIO(raw))
        msgid = _canonical_msgid(getattr(m, "messageId", None) or "")
        d = _parse_date_any(str(getattr(m, "date", "") or ""))
        subject = getattr(m, "subject", "") or ""
        subject_norm = _normalize_subject(subject)
        from_ = getattr(m, "sender", "") or ""
        to = [t.strip() for t in (getattr(m, "to", "") or "").split(";") if t.strip()]
        cc = [t.strip() for t in (getattr(m, "cc", "") or "").split(";") if t.strip()]
        body_text = _normalize_body_text(getattr(m, "body", "") or "")
        body_sha = _sha256_bytes(body_text.encode("utf-8")) if body_text else None
        attachments = []
        for att in getattr(m, "attachments", []) or []:
            data = getattr(att, "data", None)
            data = data if isinstance(data, (bytes, bytearray)) else b""
            attachments.append({
                "filename": getattr(att, "longFilename", None)
                            or getattr(att, "shortFilename", None) or "(unnamed)",
                "size": len(data),
                "sha256": _sha256_bytes(bytes(data)) if data else None,
            })
        return {
            "msgid": msgid,
            "msgid_hash": _msgid_hash(msgid, provider="msg", provider_id=None,
                                      from_=from_, date_iso=d.isoformat() if d else None,
                                      subject_norm=subject_norm, to=to, body_sha=body_sha),
            "provider": "msg",
            "provenance": "full" if msgid else "reduced",
            "provider_id": None,
            "thread_id": None,
            "date_iso": d.isoformat() if d else None,
            "from": from_, "to": to, "cc": cc,
            "subject": subject, "subject_norm": subject_norm,
            "participants_matched": [],
            "in_reply_to": None, "references": [],
            "attachments": attachments,
            "has_attachments_unfetched": False,
            "body_sha256": body_sha,
            "body_text": body_text,
            "privilege_flags": [],
            "staged_relpath": None,
        }
    except Exception:
        return None


def _privilege_flags(row: dict, firm_emails: set, keywords: List[str]) -> List[str]:
    flags = []
    all_addrs = {a for _, a in _addresses(row.get("from", ""))}
    for field in ("to", "cc"):
        for entry in row.get(field, []):
            for _, a in _addresses(entry):
                all_addrs.add(a)
    all_addrs.discard("")
    if all_addrs and firm_emails and all_addrs <= firm_emails:
        flags.append("firm_internal")
    haystack = " ".join([row.get("subject_norm", ""),
                         _normalize_identifier(row.get("body_text", "") or "")])
    for kw in keywords:
        if _normalize_identifier(kw) in haystack:
            flags.append("counsel_keyword")
            break
    return flags


# ── commands ────────────────────────────────────────────────────────────────

def cmd_context(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    if not matter_dir.exists():
        print(f"ERROR: matter directory not found: {matter_dir}")
        return 2
    firm_cfg, cfg_source = load_firm_config(args.firm_config)
    manifest = _cg_manifest(matter_dir)
    notes: List[str] = [f"firm_config: {cfg_source}"]
    accounts = _mail_accounts(firm_cfg, notes)
    owner_err = _require_owner_addresses(accounts, "context")
    if owner_err:
        print(owner_err)
        return 2

    # Anchors from the casegraph chronology (injury/incident, first contact).
    chronology = _cg_chronology(matter_dir)
    dated = [(r, _parse_date_any(r.get("date"))) for r in chronology]
    dated = [(r, d) for r, d in dated if d is not None]
    dated.sort(key=lambda t: t[1])
    incident_date = first_contact_date = None
    for r, d in dated:
        event = r.get("event", "")
        if incident_date is None and INCIDENT_EVENT_RE.search(event):
            incident_date = d
        if first_contact_date is None and FIRST_CONTACT_EVENT_RE.search(event):
            first_contact_date = d

    margin_days = args.margin_days if args.margin_days is not None else \
        int(firm_cfg.get("window_margin_days", DEFAULT_MARGIN_DAYS))
    margin = timedelta(days=margin_days)
    if args.window_start:
        start = _parse_date_any(args.window_start)
        if start is None:
            print(f"ERROR: cannot parse --window-start: {args.window_start}")
            return 2
        start_prov = "explicit"
    elif incident_date is not None:
        start = incident_date - margin
        start_prov = f"incident_date {incident_date.isoformat()} - {margin_days}d margin"
    elif dated:
        start = dated[0][1] - margin
        start_prov = (f"earliest chronology entry {dated[0][1].isoformat()} "
                      f"- {margin_days}d margin")
    else:
        doc_dates = [_parse_date_any(r.get("doc_date"))
                     for r in _cg_documents(matter_dir)]
        doc_dates = [d for d in doc_dates if d is not None]
        if doc_dates:
            start = min(doc_dates) - margin
            start_prov = (f"earliest indexed doc_date {min(doc_dates).isoformat()} "
                          f"- {margin_days}d margin")
        else:
            print("ERROR: no casegraph chronology or dated documents to derive a "
                  "scan window from. Provide --window-start YYYY-MM-DD explicitly "
                  "(and confirm it with the attorney).")
            return 2

    if args.window_end:
        end = _parse_date_any(args.window_end)
        if end is None:
            print(f"ERROR: cannot parse --window-end: {args.window_end}")
            return 2
        end_prov = "explicit"
    else:
        end = _today()
        end_prov = "today"

    if end < start:
        print(f"ERROR: window end {end.isoformat()} precedes start {start.isoformat()}")
        return 2

    participants = _derive_participants(matter_dir, firm_cfg)
    if not participants:
        notes.append("WARNING: no participants derived — configure firm contacts or "
                     "run add-participant before scanning; participant filter would "
                     "exclude everything.")

    priority_windows = []
    for w in firm_cfg.get("priority_windows", []):
        ws, we = _parse_date_any(w.get("start")), _parse_date_any(w.get("end"))
        if ws is None or we is None:
            notes.append(f"WARNING: unparseable priority window skipped: {w}")
            continue
        lo, hi = max(ws, start), min(we, end)
        if lo <= hi:
            priority_windows.append({
                "start": lo.isoformat(), "end": hi.isoformat(),
                "account": w.get("account") or w.get("provider", ""),
                "mode": w.get("mode", "exhaustive"),
                "reason": w.get("reason", ""),
            })

    context = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "generated": _utcnow(),
        "matter_id": (manifest or {}).get("matter_id"),
        "window": {
            "start": start.isoformat(), "start_provenance": start_prov,
            "end": end.isoformat(), "end_provenance": end_prov,
        },
        "anchors": {
            "incident_date": incident_date.isoformat() if incident_date else None,
            "first_contact_date": (first_contact_date.isoformat()
                                   if first_contact_date else None),
        },
        "participants": participants,
        "mail_accounts": accounts,
        "priority_windows": priority_windows,
        "coverage_gap_days": firm_cfg.get("coverage_gap_days",
                                          DEFAULT_COVERAGE_GAP_DAYS),
        "privilege_keywords": firm_cfg.get("privilege_keywords",
                                           DEFAULT_PRIVILEGE_KEYWORDS),
        "notes": notes,
    }
    _write_json_atomic(_context_path(matter_dir), context)

    if args.json:
        print(json.dumps(context, indent=2))
    else:
        print(f"Scan context for matter '{context['matter_id']}' written to "
              f"{_context_path(matter_dir)}")
        print(f"  window: {start.isoformat()} .. {end.isoformat()}  "
              f"(start: {start_prov}; end: {end_prov})")
        if incident_date:
            print(f"  incident anchor: {incident_date.isoformat()}")
        if first_contact_date:
            print(f"  first-contact anchor: {first_contact_date.isoformat()}")
        print(f"  participants: {len(participants)}  mail accounts: {len(accounts)}  "
              f"priority windows: {len(priority_windows)}")
        for n in notes:
            print(f"  NOTE: {n}")
    return 0


def cmd_add_participant(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    if not matter_dir.exists():
        print(f"ERROR: matter directory not found: {matter_dir}")
        return 2
    pp = _participants_path(matter_dir)
    existing = _load_json(pp) if pp.exists() else {}
    key = _normalize_name(args.name)
    if not key:
        print(f"ERROR: unusable participant name: {args.name!r}")
        return 2
    row = existing.get(key, {
        "key": key, "display": args.name, "emails": [],
        "role": args.role or "", "origin": "manual",
    })
    emails = set(row.get("emails", []))
    emails.update(e.strip().casefold() for e in (args.email or []) if e.strip())
    row["emails"] = sorted(emails)
    if args.role:
        row["role"] = args.role
    existing[key] = row
    _write_json_atomic(pp, existing)
    print(f"Registered participant '{args.name}' ({len(row['emails'])} address(es)).")
    return 0


def _chunk(seq: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _gmail_dates(lo: date, hi: date) -> str:
    # gmail 'before:' is exclusive; use end+1 day
    return (f"after:{lo.strftime('%Y/%m/%d')} "
            f"before:{(hi + timedelta(days=1)).strftime('%Y/%m/%d')}")


def cmd_plan(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    cp = _context_path(matter_dir)
    if not cp.exists():
        print(f"ERROR: no scan context at {cp}. Run: matter_mail.py context {matter_dir}")
        return 2
    ctx = _load_json(cp)
    start = _parse_date_any(ctx["window"]["start"])
    end = _parse_date_any(ctx["window"]["end"])
    accounts = ctx.get("mail_accounts") or [{"label": "outlook", "address": None,
                                             "transport": "graph"}]
    owner_addrs = {a["address"] for a in accounts if a.get("address")}

    # Participant addresses to query for — the mailbox owner's own address
    # carries no signal inside its own mailbox and is excluded.
    addrs = sorted({e for p in ctx["participants"] for e in p.get("emails", [])}
                   - owner_addrs)
    plans: List[dict] = []
    warnings: List[str] = []

    def rows_for(account: dict, lo: date, hi: date, mode: str, reason: str) -> None:
        transport = account["transport"]
        label = account["label"]
        if transport == "graph":
            if mode == "exhaustive":
                plans.append({
                    "provider": "graph", "account": label, "mode": mode,
                    "window": {"start": lo.isoformat(), "end": hi.isoformat()},
                    "query": (f"received>={lo.isoformat()} AND "
                              f"received<={hi.isoformat()}"),
                    "reason": reason,
                })
                return
            for chunk in _chunk(addrs, ADDR_CHUNK):
                kql = " OR ".join(f"participants:{a}" for a in chunk)
                plans.append({
                    "provider": "graph", "account": label, "mode": mode,
                    "window": {"start": lo.isoformat(), "end": hi.isoformat()},
                    "query": (f"({kql}) AND received>={lo.isoformat()} "
                              f"AND received<={hi.isoformat()}"),
                    "reason": f"{reason} — addresses {chunk[0]} .. {chunk[-1]}",
                })
        elif transport == "gmail-api":
            if mode == "exhaustive":
                plans.append({
                    "provider": "gmail", "account": label, "mode": mode,
                    "window": {"start": lo.isoformat(), "end": hi.isoformat()},
                    "query": _gmail_dates(lo, hi),
                    "reason": reason,
                })
                return
            for chunk in _chunk(addrs, ADDR_CHUNK):
                ors = " OR ".join(f"from:{a} OR to:{a} OR cc:{a}" for a in chunk)
                plans.append({
                    "provider": "gmail", "account": label, "mode": mode,
                    "window": {"start": lo.isoformat(), "end": hi.isoformat()},
                    "query": f"{_gmail_dates(lo, hi)} ({ors})",
                    "reason": f"{reason} — addresses {chunk[0]} .. {chunk[-1]}",
                })
        else:  # outlook-export
            plans.append({
                "provider": "outlook-export", "account": label, "mode": mode,
                "window": {"start": lo.isoformat(), "end": hi.isoformat()},
                "query": (f"Export mailbox '{label}' for {lo.isoformat()}.."
                          f"{hi.isoformat()} from the Outlook client to a scratch "
                          f"directory (.eml / .msg drag-export, or .pst converted "
                          f"to .eml/.mbox); then matter_mail.py ingest filters to "
                          f"case participants"),
                "reason": reason,
            })

    for account in accounts:
        rows_for(account, start, end, "participants",
                 f"account '{account['label']}' ({account['transport']})")

    by_label = {a["label"]: a for a in accounts}
    for w in ctx.get("priority_windows", []):
        lo, hi = _parse_date_any(w["start"]), _parse_date_any(w["end"])
        target = by_label.get(w.get("account"))
        reason = (f"priority window ({w.get('reason', 'configured')}): list ALL "
                  f"messages, ingest with --allow-unmatched for header triage")
        if target is None:
            # Back-compat: treat the account value as a transport hint.
            hint = (w.get("account") or "").casefold()
            transport = hint if hint in VALID_TRANSPORTS else \
                ("gmail-api" if hint == "gmail" else "outlook-export")
            target = {"label": w.get("account") or "unconfigured",
                      "transport": transport}
            warnings.append(f"priority window references account "
                            f"'{w.get('account')}' not present in mail_accounts — "
                            f"emitted a generic {transport} row; configure the "
                            f"account for owner-address exclusion")
        rows_for(target, lo, hi, "exhaustive", reason)

    if not addrs:
        warnings.append("no participant email addresses configured (after owner-"
                        "address exclusion) — participant-mode queries were not "
                        "generated; add firm contacts or add-participant --email "
                        "before fetching")

    plan = {
        "generated": _utcnow(),
        "matter_id": ctx.get("matter_id"),
        "mail_accounts": accounts,
        "participant_names_without_email": [
            p["display"] for p in ctx["participants"] if not p.get("emails")
        ],
        "warnings": warnings,
        "fetch_notes": [
            "READ-ONLY fetch only: Microsoft Graph GET (messages endpoint) or "
            "gmail search/get (readonly scope). Never send, reply, modify, or label.",
            "Graph transport: request $select=internetMessageId,subject,from,"
            "toRecipients,ccRecipients,receivedDateTime,conversationId,"
            "hasAttachments,body — internetMessageId enables exact filed matching. "
            "tools/microsoft_graph_client.py in this repo is the reference client.",
            "MANDATORY pagination: follow every @odata.nextLink (or use "
            "microsoft_graph_client.iterate_pages / collect_paginated) until "
            "exhausted. Saving page 1 only is a silent under-scan — treat as FAIL.",
            "When hasAttachments is true, emit a follow-up plan row for the "
            "message attachments endpoint before treating the message as complete.",
            "google-workspace JSON is reduced fidelity (no Message-ID/Cc/attachments); "
            "prefer Graph or raw .eml export to upgrade matching.",
            "Outlook client exports: .eml or .msg drag-export per message; bulk via "
            ".pst export converted to .eml/.mbox (ingest reads .eml/.mbox/.msg/.json).",
            "Run queries sequentially; on HTTP 429 back off and resume.",
        ],
        "queries": plans,
    }
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(f"{len(plans)} planned queries for matter '{ctx.get('matter_id')}':")
        for p in plans:
            print(f"  [{p['provider']}/{p['account']}/{p['mode']}] {p['query']}")
        for w in warnings:
            print(f"  WARNING: {w}")
        for name in plan["participant_names_without_email"]:
            print(f"  NOTE: participant '{name}' has no known address — "
                  f"name matching applies only at ingest; consider add-participant "
                  f"--email once an address is learned.")
    return 0


def _iter_source_files(source: Path) -> Iterable[Path]:
    if source.is_file():
        yield source
        return
    for root, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in sorted(files):
            if not name.startswith("."):
                yield Path(root) / name


def _json_objs(loaded) -> List[dict]:
    """Accept a bare object, a list, or a Graph collection ({"value": [...]})."""
    if isinstance(loaded, dict) and isinstance(loaded.get("value"), list):
        return [o for o in loaded["value"] if isinstance(o, dict)]
    if isinstance(loaded, list):
        return [o for o in loaded if isinstance(o, dict)]
    if isinstance(loaded, dict):
        return [loaded]
    return []


def cmd_ingest(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    cp = _context_path(matter_dir)
    if not cp.exists():
        print(f"ERROR: no scan context at {cp}. Run: matter_mail.py context {matter_dir}")
        return 2
    ctx = _load_json(cp)
    source = Path(args.source).resolve()
    if not source.exists():
        print(f"ERROR: source not found: {source}")
        return 2
    if args.provider and not _PROVIDER_TAG_RE.fullmatch(args.provider):
        print(f"ERROR: --provider must match [a-z0-9_-]{{1,32}}, got: {args.provider!r}")
        return 2

    owner_emails = {a["address"] for a in ctx.get("mail_accounts", [])
                    if a.get("address")}
    for o in args.owner or []:
        owner_emails.add(o.strip().casefold())
    if not owner_emails:
        print("ERROR: ingest refuses empty owner_emails — re-run context with "
              "mail_accounts.address set, or pass --owner")
        return 2
    owner_names = [
        p.get("display", "") for p in ctx.get("participants", [])
        if p.get("origin") == "firm_config" and any(
            (e or "").casefold() in owner_emails for e in p.get("emails", [])
        )
    ]
    matcher = ParticipantMatcher(
        ctx["participants"], owner_emails=owner_emails, owner_names=owner_names,
    )
    firm_emails = {e for p in ctx["participants"] if p.get("origin") == "firm_config"
                   for e in p.get("emails", [])}
    firm_keys = {
        p["key"] for p in ctx["participants"] if p.get("origin") == "firm_config"
    }
    keywords = ctx.get("privilege_keywords", DEFAULT_PRIVILEGE_KEYWORDS)
    win_start = _parse_date_any(ctx["window"]["start"])
    win_end = _parse_date_any(ctx["window"]["end"])
    tol = timedelta(days=DATE_TOLERANCE_DAYS)

    existing = {r["msgid_hash"]: r for r in _load_jsonl(_messages_path(matter_dir))}
    n_new = n_dup = n_excluded = n_unmatched_kept = n_unparseable = 0
    n_out_of_window = n_upgraded = n_restaged = n_msg_unsupported = 0
    n_firm_only = 0

    def _header_pairs_for(row: dict) -> List[Tuple[str, str]]:
        header_pairs = list(_addresses(row["from"]))
        for field in ("to", "cc", "bcc"):
            for entry in row.get(field) or []:
                header_pairs.extend(_addresses(entry))
        return header_pairs

    def _qualifies(matched: List[str]) -> bool:
        """H3: firm-only threads (no client/opponent/manual participant) do not
        stage by default — they are cross-matter leakage within the window."""
        if not matched:
            return False
        if getattr(args, "allow_firm_internal", False):
            return True
        return any(k not in firm_keys for k in matched)

    def stage(row: dict, raw: Optional[bytes], source_obj: Optional[dict]) -> None:
        """Persist a staged copy under correspondence/ (full source content —
        matched messages ARE case correspondence; the staged copy is what the
        attorney reviews and what casegraph indexes)."""
        corr = matter_dir / CORR_DIRNAME / row["provider"]
        stem = f"{row['date_iso'] or 'undated'}_{row['msgid_hash'][:12]}"
        if raw is not None:
            ext = ".msg" if row["provider"] == "msg" else ".eml"
            staged = _stage_bytes(corr / f"{stem}{ext}", raw)
        else:
            payload = json.dumps(source_obj if source_obj is not None else
                                 {k: v for k, v in row.items() if k != "body_text"},
                                 indent=2, sort_keys=True).encode("utf-8")
            staged = _stage_bytes(corr / f"{stem}.json", payload)
        row["staged_relpath"] = staged.relative_to(matter_dir).as_posix()

    def _unstage_prior(prior_row: dict) -> None:
        """Delete any staged correspondence copy for a prior row."""
        rel = prior_row.get("staged_relpath")
        if not rel:
            return
        try:
            (matter_dir / rel).unlink(missing_ok=True)
        except OSError:
            pass

    def _drop_prior(prior_row: dict, msgid_hash: str) -> None:
        """Remove a previously-active message from the store + disk."""
        _unstage_prior(prior_row)
        existing.pop(msgid_hash, None)

    def _redact_unmatched_triage(target: dict) -> None:
        """Header-only triage row: no body/attachments, privacy-redacted."""
        target["attachment_count"] = len(target.get("attachments", []))
        target["attachments"] = []
        target["body_sha256"] = None
        target["subject"] = "[redacted-unmatched]"
        target["subject_norm"] = ""
        target["from"] = "[redacted-unmatched]"
        target["staged_relpath"] = None
        target["participants_matched"] = []
        target.pop("body_text", None)

    for path in _iter_source_files(source):
        # (row, raw_bytes, original_json_obj) triples
        rows: List[Tuple[dict, Optional[bytes], Optional[dict]]] = []
        suffix = path.suffix.lower()
        try:
            if suffix == ".eml":
                raw = path.read_bytes()
                row = normalize_eml(raw)
                if row is None:
                    n_unparseable += 1
                    continue
                rows.append((row, raw, None))
            elif suffix == ".msg":
                raw = path.read_bytes()
                row = normalize_msg_bytes(raw, path.name)
                if row is None:
                    n_msg_unsupported += 1
                    continue
                rows.append((row, raw, None))
            elif suffix == ".mbox":
                # Bulk mailbox export (Google Takeout, or .pst converted via
                # readpst). Each message keeps full .eml fidelity.
                import mailbox
                try:
                    box = mailbox.mbox(str(path))
                except Exception:
                    n_unparseable += 1
                    continue
                for key in box.iterkeys():
                    try:
                        raw = box.get_bytes(key)
                    except Exception:
                        n_unparseable += 1
                        continue
                    row = normalize_eml(raw)
                    if row is None:
                        n_unparseable += 1
                        continue
                    row["provider"] = "mbox"
                    rows.append((row, raw, None))
                box.close()
            elif suffix in (".json", ".jsonl"):
                try:
                    if suffix == ".jsonl":
                        objs = _load_jsonl(path)
                    else:
                        objs = _json_objs(_load_json(path))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    n_unparseable += 1
                    continue
                for obj in objs:
                    # Graph shape first (Graph rows also carry an "id").
                    row = normalize_graph_json(obj) or normalize_gmail_json(obj)
                    if row is None:
                        n_unparseable += 1
                        continue
                    rows.append((row, None, obj))
            else:
                continue
        except OSError:
            n_unparseable += 1
            continue

        for row, raw, source_obj in rows:
            if args.provider:
                row["provider"] = args.provider

            prior = existing.get(row["msgid_hash"])
            if prior is not None:
                n_dup += 1
                # P0-2: always re-qualify against CURRENT context/config.
                # A tightened window, removed participant, or withdrawn
                # --allow-firm-internal must unstage prior active rows.
                d = _parse_date_any(row.get("date_iso") or prior.get("date_iso"))
                if (d is not None and win_start and win_end
                        and not (win_start - tol <= d <= win_end + tol)
                        and not args.allow_out_of_window):
                    _drop_prior(prior, row["msgid_hash"])
                    n_out_of_window += 1
                    continue

                matched = matcher.match(_header_pairs_for(row))
                if not matched:
                    if not args.allow_unmatched:
                        _drop_prior(prior, row["msgid_hash"])
                        n_excluded += 1
                        continue
                    # Demote to header-only triage; drop any staged body copy.
                    _unstage_prior(prior)
                    triage = dict(prior)
                    triage.update({
                        "msgid_hash": row["msgid_hash"],
                        "date_iso": row.get("date_iso") or prior.get("date_iso"),
                    })
                    _redact_unmatched_triage(triage)
                    existing[row["msgid_hash"]] = triage
                    n_unmatched_kept += 1
                    continue

                if not _qualifies(matched):
                    _drop_prior(prior, row["msgid_hash"])
                    n_firm_only += 1
                    continue

                # Still qualifies — preserve fidelity upgrade / restage paths.
                if (row.get("body_sha256") and not prior.get("body_sha256")
                        and row["msgid_hash"] == prior["msgid_hash"]):
                    row["participants_matched"] = matched
                    row["privilege_flags"] = _privilege_flags(
                        row, firm_emails, keywords)
                    stage(row, raw, source_obj)
                    row.pop("body_text", None)
                    existing[row["msgid_hash"]] = row
                    n_upgraded += 1
                elif (prior.get("staged_relpath")
                      and not (matter_dir / prior["staged_relpath"]).exists()):
                    if (row.get("body_sha256") and prior.get("body_sha256")
                            and row["body_sha256"] != prior["body_sha256"]):
                        _drop_prior(prior, row["msgid_hash"])
                        n_excluded += 1  # refuse restage of divergent bytes
                    else:
                        prior["participants_matched"] = matched
                        stage(prior, raw, source_obj)
                        existing[row["msgid_hash"]] = prior
                        n_restaged += 1
                else:
                    # Idempotent keep; refresh match list if context grew/shrunk
                    # but still qualifies.
                    if prior.get("participants_matched") != matched:
                        prior["participants_matched"] = matched
                        existing[row["msgid_hash"]] = prior
                continue

            # Window enforcement: an over-broad export must not leak other
            # matters' correspondence into this matter's record.
            d = _parse_date_any(row.get("date_iso"))
            if (d is not None and win_start and win_end
                    and not (win_start - tol <= d <= win_end + tol)
                    and not args.allow_out_of_window):
                n_out_of_window += 1
                continue

            matched = matcher.match(_header_pairs_for(row))
            row["participants_matched"] = matched

            if not matched:
                if not args.allow_unmatched:
                    # Personal / non-matter mail: count it, drop ALL content.
                    n_excluded += 1
                    continue
                # Header-only triage: redact subject/from (privacy); keep date + hash.
                _redact_unmatched_triage(row)
                existing[row["msgid_hash"]] = row
                n_unmatched_kept += 1
                continue

            if not _qualifies(matched):
                n_firm_only += 1
                continue

            row["privilege_flags"] = _privilege_flags(row, firm_emails, keywords)
            stage(row, raw, source_obj)
            row.pop("body_text", None)
            existing[row["msgid_hash"]] = row
            n_new += 1

    _save_jsonl_atomic(_messages_path(matter_dir), list(existing.values()),
                       sort_key=lambda r: (r.get("date_iso") or "", r["msgid_hash"]))

    report = {
        "ingested_new": n_new,
        "duplicates_skipped": n_dup,
        "fidelity_upgraded": n_upgraded,
        "restaged": n_restaged,
        "excluded_non_matter": n_excluded,
        "excluded_firm_only": n_firm_only,
        "excluded_out_of_window": n_out_of_window,
        "unmatched_kept_for_triage": n_unmatched_kept,
        "unparseable": n_unparseable,
        "msg_unsupported": n_msg_unsupported,
        "total_messages": len(existing),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Ingested {n_new} new message(s); {n_dup} duplicate(s) "
              f"({n_upgraded} fidelity-upgraded, {n_restaged} re-staged); "
              f"{n_excluded} excluded (no non-owner case participant — content "
              f"discarded); {n_firm_only} excluded (firm-only — use "
              f"--allow-firm-internal to stage); {n_out_of_window} excluded "
              f"(outside scan window); {n_unmatched_kept} kept header-only "
              f"for triage; {n_unparseable} unparseable.")
        if n_msg_unsupported:
            print(f"NOTE: {n_msg_unsupported} .msg file(s) skipped — install the "
                  f"optional 'extract-msg' package or re-export as .eml.")
        print(f"Store: {len(existing)} total at {_messages_path(matter_dir)}")
    return 0


# ── gap analysis ─────────────────────────────────────────────────────────────

def _filed_msgids(matter_dir: Path) -> Dict[str, dict]:
    """Message-IDs of .eml files already in the matter, outside correspondence/
    and state dirs, with every filed copy's body hash so a Message-ID match is
    content-verified (matching id + different body = conflict; matching id +
    unverifiable body = unverified, never 'verified'). Duplicate filed ids
    accumulate all body hashes. Attachments are not decoded here (headers +
    body only — this walk runs on every gap invocation)."""
    out: Dict[str, dict] = {}
    skip = {STATE_DIRNAME, CASEGRAPH_DIRNAME, CORR_DIRNAME}
    for root, dirs, files in os.walk(matter_dir):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        for name in files:
            if not name.lower().endswith(".eml"):
                continue
            path = Path(root) / name
            try:
                row = normalize_eml(path.read_bytes(), include_attachments=False)
            except OSError:
                continue
            if row is None or not row.get("msgid"):
                continue
            entry = out.setdefault(row["msgid"], {"relpaths": [], "body_hashes": []})
            entry["relpaths"].append(path.relative_to(matter_dir).as_posix())
            if row.get("body_sha256"):
                entry["body_hashes"].append(row["body_sha256"])
    return out


def _indexed_text_docs(matter_dir: Path) -> List[Tuple[dict, Path]]:
    cache = _cg_text_cache(matter_dir)
    docs = []
    for row in _cg_documents(matter_dir):
        if row["relpath"].startswith(f"{CORR_DIRNAME}/"):
            continue
        fp = cache / f"{row['sha256']}.txt"
        if fp.exists():
            docs.append((row, fp))
    return docs


def cmd_gap(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    manifest = _cg_manifest(matter_dir)
    if manifest is None:
        print(f"ERROR: no casegraph index at {_cg_dir(matter_dir)}. The gap check "
              f"diffs mail against the indexed case file — run casegraph init/build "
              f"first.")
        return 2
    cp = _context_path(matter_dir)
    if not cp.exists():
        print(f"ERROR: no scan context. Run: matter_mail.py context {matter_dir}")
        return 2
    ctx = _load_json(cp)
    messages = _load_jsonl(_messages_path(matter_dir))
    if not messages:
        print("ERROR: no ingested messages. Run: matter_mail.py ingest first.")
        return 2

    filed = _filed_msgids(matter_dir)
    filed_ids = set(filed)
    text_docs = _indexed_text_docs(matter_dir)
    # Normalize each doc text once — probable matching is O(msgs x docs).
    doc_texts: List[Tuple[dict, str, str]] = []
    for row, fp in text_docs:
        text = fp.read_text(encoding="utf-8", errors="replace")
        doc_texts.append((row, text, _normalize_identifier(text)))
    indexed_shas = {row["sha256"] for row in _cg_documents(matter_dir)}
    indexed_basenames = {Path(row["relpath"]).name.casefold()
                         for row in _cg_documents(matter_dir)
                         if not row["relpath"].startswith(f"{CORR_DIRNAME}/")}

    matched = [m for m in messages if m.get("participants_matched")]
    triage = [m for m in messages if not m.get("participants_matched")]

    missing: List[dict] = []
    probable: List[dict] = []
    filed_exact: List[dict] = []
    filed_unverified: List[dict] = []
    filed_conflicts: List[dict] = []
    attachment_gaps: List[dict] = []

    for m in matched:
        label = {
            "msgid_hash": m["msgid_hash"], "date": m.get("date_iso"),
            "from": _md_field(m.get("from")), "subject": _md_field(m.get("subject")),
            "provenance": m.get("provenance"),
            "staged_relpath": m.get("staged_relpath"),
            "privilege_flags": m.get("privilege_flags", []),
        }

        # Attachment verification runs for every matched message — including
        # ones whose body is filed: a filed email whose attachment was never
        # separately filed is still an attachment gap.
        for att in m.get("attachments", []):
            if att.get("sha256") and att["sha256"] in indexed_shas:
                continue
            name_hit = (att.get("filename", "").casefold() in indexed_basenames)
            attachment_gaps.append({
                "message": label, "filename": _md_field(att.get("filename")),
                "size": att.get("size"),
                "status": "probable_name_match" if name_hit else "missing",
            })
        if m.get("has_attachments_unfetched"):
            attachment_gaps.append({
                "message": label, "filename": "(attachments not fetched — Graph "
                "hasAttachments=true; fetch the attachments endpoint to verify)",
                "size": None, "status": "unfetched_verify",
            })

        if m.get("msgid") and m["msgid"] in filed_ids:
            entry = filed[m["msgid"]]
            filed_as = entry["relpaths"][0] if entry["relpaths"] else None
            if m.get("body_sha256") and entry["body_hashes"]:
                if m["body_sha256"] in entry["body_hashes"]:
                    filed_exact.append({**label, "filed_as": filed_as,
                                        "body_verified": True})
                else:
                    filed_conflicts.append({
                        **label, "filed_as": filed_as,
                        "conflict": "Message-ID matches a filed copy but the body "
                                    "differs — filed copy may be altered/truncated "
                                    "or the id spoofed; attorney review required",
                    })
            else:
                filed_unverified.append({
                    **label, "filed_as": filed_as,
                    "verify": "Message-ID matches a filed copy but a body hash is "
                              "unavailable on one side — open both copies and "
                              "confirm they are the same correspondence",
                })
            continue

        hit_doc = None
        d = _parse_date_any(m.get("date_iso"))
        subject_norm = m.get("subject_norm") or ""
        if (d is not None and len(subject_norm) >= MIN_SUBJECT_MATCH_LEN
                and len(subject_norm.split()) >= MIN_SUBJECT_MATCH_TOKENS):
            patterns: List[Pattern] = []
            for delta in range(-DATE_TOLERANCE_DAYS, DATE_TOLERANCE_DAYS + 1):
                patterns.extend(_date_patterns(d + timedelta(days=delta)))
            for row, text, norm_text in doc_texts:
                if subject_norm in norm_text and any(p.search(text) for p in patterns):
                    hit_doc = row["relpath"]
                    break
        if hit_doc:
            probable.append({**label, "probable_match": hit_doc,
                             "verify": "subject+date matched document text — confirm "
                                       "this is the same correspondence"})
        else:
            missing.append(label)

    known_ids = filed_ids | {m["msgid"] for m in messages if m.get("msgid")}
    thread_gaps: List[dict] = []
    seen_refs = set()
    for m in matched:
        refs = list(m.get("references", []))
        if m.get("in_reply_to"):
            refs.append(m["in_reply_to"])
        for ref in refs:
            if ref and ref not in known_ids and ref not in seen_refs:
                seen_refs.add(ref)
                thread_gaps.append({
                    "missing_msgid": ref,
                    "cited_by": {"date": m.get("date_iso"),
                                 "subject": _md_field(m.get("subject")),
                                 "msgid_hash": m["msgid_hash"]},
                })

    # Window coverage: spans inside the scan window with no matched messages.
    start = _parse_date_any(ctx["window"]["start"])
    end = _parse_date_any(ctx["window"]["end"])
    gap_days = int(ctx.get("coverage_gap_days", DEFAULT_COVERAGE_GAP_DAYS))
    msg_dates = sorted({_parse_date_any(m["date_iso"]) for m in matched
                        if m.get("date_iso")})
    coverage_gaps: List[dict] = []
    points = [start] + [d for d in msg_dates if d and start <= d <= end] + [end]
    for a, b in zip(points, points[1:]):
        span = (b - a).days
        if span >= gap_days:
            coverage_gaps.append({"start": a.isoformat(), "end": b.isoformat(),
                                  "days": span})

    n_att_missing = len([a for a in attachment_gaps if a["status"] == "missing"])
    n_att_probable = len([a for a in attachment_gaps
                          if a["status"] == "probable_name_match"])
    n_att_unfetched = len([a for a in attachment_gaps
                           if a["status"] == "unfetched_verify"])

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated": _utcnow(),
        "matter_id": manifest.get("matter_id"),
        "window": ctx["window"],
        "anchors": ctx.get("anchors", {}),
        "counts": {
            "messages_matched": len(matched),
            "messages_triage_unmatched": len(triage),
            "filed_exact": len(filed_exact),
            "filed_unverified": len(filed_unverified),
            "filed_conflicts": len(filed_conflicts),
            "probable_filed": len(probable),
            "missing_from_file": len(missing),
            "attachment_gaps": n_att_missing,
            "attachment_probable": n_att_probable,
            "attachment_unfetched": n_att_unfetched,
            "thread_gaps": len(thread_gaps),
            "coverage_gaps": len(coverage_gaps),
        },
        "missing_from_file": missing,
        "probable_filed": probable,
        "filed_exact": filed_exact,
        "filed_unverified": filed_unverified,
        "filed_conflicts": filed_conflicts,
        "attachment_gaps": attachment_gaps,
        "thread_gaps": thread_gaps,
        "coverage_gaps": coverage_gaps,
        "triage_unmatched": [
            {"date": m.get("date_iso"), "from": _md_field(m.get("from")),
             "subject": _md_field(m.get("subject")), "provider": m.get("provider")}
            for m in triage
        ],
    }
    _write_json_atomic(_gap_report_path(matter_dir), report)

    hard = bool(missing or thread_gaps or filed_conflicts or n_att_missing)
    soft = bool(probable or coverage_gaps or filed_unverified
                or n_att_probable or n_att_unfetched)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        c = report["counts"]
        print(f"Gap analysis for matter '{report['matter_id']}' "
              f"({c['messages_matched']} matched messages):")
        print(f"  filed exact (body verified): {c['filed_exact']}   "
              f"filed UNVERIFIED: {c['filed_unverified']}   "
              f"FILED CONFLICTS: {c['filed_conflicts']}")
        print(f"  probable filed (verify): {c['probable_filed']}")
        print(f"  MISSING FROM FILE: {c['missing_from_file']}")
        print(f"  attachment gaps: {c['attachment_gaps']} "
              f"(+{c['attachment_probable']} name-only, "
              f"+{c['attachment_unfetched']} unfetched to verify)")
        print(f"  thread gaps (earlier messages missing everywhere): "
              f"{c['thread_gaps']}")
        print(f"  coverage gaps >= {gap_days}d: {c['coverage_gaps']}")
        print(f"  unmatched triage rows: {c['messages_triage_unmatched']}")
        print(f"Report: {_gap_report_path(matter_dir)}")
    if hard:
        return 1
    if soft and args.strict:
        return 1
    return 0


def cmd_report(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    gp = _gap_report_path(matter_dir)
    if not gp.exists():
        print(f"ERROR: no gap report at {gp}. Run: matter_mail.py gap {matter_dir}")
        return 2
    r = _load_json(gp)
    out = Path(args.output) if args.output else _state_dir(matter_dir) / "gap_report.md"
    out = out if out.is_absolute() else (Path.cwd() / out).resolve()
    # Write containment: default and --output must stay under the matter dir
    # unless the attorney explicitly opts out with --force-external.
    try:
        out.relative_to(matter_dir)
        contained = True
    except ValueError:
        contained = False
    if not contained and not getattr(args, "force_external", False):
        print(f"ERROR: report --output must resolve under the matter directory "
              f"({matter_dir}); got {out}. Pass --force-external to override.")
        return 2
    c = r["counts"]

    lines: List[str] = []
    lines.append("**CONFIDENTIAL — ATTORNEY WORK PRODUCT**")
    lines.append("")
    lines.append("**ATTORNEY REVIEW REQUIRED — DRAFT ONLY — NO LEGAL CONCLUSIONS**")
    lines.append("")
    lines.append(f"# Correspondence Gap Report — Matter {r.get('matter_id')}")
    lines.append("")
    lines.append(f"Generated: {r['generated']}  |  Tool: matter-mail {TOOL_VERSION}")
    lines.append("")
    w = r["window"]
    lines.append(f"**Scan window:** {w['start']} .. {w['end']}  ")
    lines.append(f"(start: {w['start_provenance']}; end: {w['end_provenance']})")
    a = r.get("anchors", {})
    if a.get("incident_date"):
        lines.append(f"**Incident anchor:** {a['incident_date']}")
    if a.get("first_contact_date"):
        lines.append(f"**First-contact anchor:** {a['first_contact_date']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Check | Count |")
    lines.append("|---|---|")
    lines.append(f"| Messages matched to case participants | {c['messages_matched']} |")
    lines.append(f"| Filed (Message-ID + body verified) | {c['filed_exact']} |")
    lines.append(f"| Filed but body UNVERIFIED — check | "
                 f"{c.get('filed_unverified', 0)} |")
    lines.append(f"| **Filed conflicts (body differs)** | "
                 f"**{c.get('filed_conflicts', 0)}** |")
    lines.append(f"| Probably filed — verify | {c['probable_filed']} |")
    lines.append(f"| **Missing from case file** | **{c['missing_from_file']}** |")
    lines.append(f"| Attachment gaps | {c['attachment_gaps']} |")
    lines.append(f"| Attachments unfetched (Graph) — verify | "
                 f"{c.get('attachment_unfetched', 0)} |")
    lines.append(f"| Thread gaps (missing earlier messages) | {c['thread_gaps']} |")
    lines.append(f"| Coverage gaps in window | {c['coverage_gaps']} |")
    lines.append(f"| Unmatched header-only triage rows | "
                 f"{c['messages_triage_unmatched']} |")
    lines.append("")

    def section(title: str, rows: List[dict], render) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not rows:
            lines.append("None found.")
            lines.append("")
            return
        for row in rows:
            lines.append(render(row))
        lines.append("")

    def _priv(m):
        flags = m.get("privilege_flags") or []
        return f" — **PRIVILEGE FLAGS: {', '.join(flags)}**" if flags else ""

    section(
        "Missing From Case File (attorney review required)",
        r["missing_from_file"],
        lambda m: (f"- {m.get('date') or 'undated'} — **{_md_field(m.get('subject')) or '(no subject)'}** — "
                   f"from {_md_field(m.get('from'))} — staged: `{m.get('staged_relpath')}` "
                   f"(source fidelity: {m.get('provenance')}){_priv(m)}"),
    )
    section(
        "Filed Conflicts — Filed Copy Differs From Mailbox Copy",
        r.get("filed_conflicts", []),
        lambda m: (f"- {m.get('date')} — **{_md_field(m.get('subject'))}** — filed as "
                   f"`{m.get('filed_as')}` — {m.get('conflict')}"),
    )
    section(
        "Filed But Body Unverified — Confirm Same Correspondence",
        r.get("filed_unverified", []),
        lambda m: (f"- {m.get('date')} — {_md_field(m.get('subject'))} — filed as "
                   f"`{m.get('filed_as')}` — {m.get('verify')}"),
    )
    section(
        "Probably Filed — Verify Before Relying",
        r["probable_filed"],
        lambda m: (f"- {m.get('date')} — {_md_field(m.get('subject'))} — probable match: "
                   f"`{m.get('probable_match')}` — {m.get('verify')}"),
    )
    section(
        "Attachment Gaps",
        r["attachment_gaps"],
        lambda g: (f"- `{_md_field(g.get('filename'))}` ({g.get('size')} bytes, {g['status']}) on "
                   f"message {g['message'].get('date')} — "
                   f"{_md_field(g['message'].get('subject'))}"),
    )
    section(
        "Thread Gaps — Earlier Messages Missing Everywhere",
        r["thread_gaps"],
        lambda g: (f"- missing `<{g['missing_msgid']}>` cited by "
                   f"{g['cited_by'].get('date')} — {_md_field(g['cited_by'].get('subject'))}"),
    )
    section(
        "Coverage Gaps (no matched mail in span — confirm nothing occurred)",
        r["coverage_gaps"],
        lambda g: f"- {g['start']} .. {g['end']} ({g['days']} days)",
    )
    section(
        "Unmatched Triage Candidates (headers only; exhaustive-mode ingest)",
        r["triage_unmatched"],
        lambda m: (f"- {m.get('date') or 'undated'} — {m.get('subject') or '(no subject)'} "
                   f"— from {m.get('from')} [{m.get('provider')}]"),
    )

    lines.append("## Verification Checklist (attorney)")
    lines.append("")
    lines.append("- [ ] Scan window and participant set match the matter "
                 "(see provenance above); source citation for each anchor reviewed.")
    lines.append("- [ ] Each 'missing from file' item reviewed; filing decision made "
                 "by attorney — matter-mail stages copies but never files.")
    lines.append("- [ ] Filed-unverified and probable matches opened and confirmed "
                 "against the staged copy.")
    lines.append("- [ ] Privilege flags reviewed before any onward production.")
    lines.append("- [ ] Reduced-fidelity items re-fetched via Graph or as .eml where "
                 "confirmation is needed (source citation: gap_report.json "
                 "provenance fields); Graph 'attachments unfetched' items expanded.")
    lines.append("- [ ] `casegraph.py build` re-run so staged correspondence enters "
                 "the index; casegraph gates PASS on this report.")
    lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Attorney-review report written: {out}")
    return 0


def cmd_status(args) -> int:
    """Consistency check on matter-mail state (exit 1 if attention needed):
    scan context present, staged copies all on disk, gap report not older
    than the message store."""
    matter_dir = Path(args.matter_dir).resolve()
    issues: List[str] = []
    cp = _context_path(matter_dir)
    mp = _messages_path(matter_dir)
    gp = _gap_report_path(matter_dir)

    if not cp.exists():
        issues.append("no scan context — run: matter_mail.py context")
    messages = _load_jsonl(mp)
    dangling = [m["staged_relpath"] for m in messages
                if m.get("staged_relpath")
                and not (matter_dir / m["staged_relpath"]).exists()]
    for rel in dangling:
        issues.append(f"staged copy missing on disk: {rel} "
                      f"(re-run ingest against the original source to re-stage)")
    if messages and not gp.exists():
        issues.append("messages ingested but no gap analysis — run: matter_mail.py gap")
    elif messages and gp.exists() and mp.exists() \
            and gp.stat().st_mtime < mp.stat().st_mtime:
        issues.append("gap report is older than the message store — re-run: "
                      "matter_mail.py gap")

    report = {
        "matter_dir": str(matter_dir),
        "context": cp.exists(),
        "messages": len(messages),
        "staged_missing": len(dangling),
        "issues": issues,
        "ok": not issues,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if issues:
            print(f"matter-mail status: ATTENTION ({len(messages)} messages)")
            for i in issues:
                print(f"  - {i}")
        else:
            print(f"matter-mail status: OK ({len(messages)} messages ingested, "
                  f"all staged copies present)")
    return 1 if issues else 0


# ── selftest ────────────────────────────────────────────────────────────────

def _selftest_eml(msgid: str, from_: str, to: str, date_hdr: str, subject: str,
                  body: str, refs: str = "", attachment: Optional[Tuple[str, bytes]] = None) -> bytes:
    lines = [
        f"Message-ID: <{msgid}>",
        f"From: {from_}",
        f"To: {to}",
        f"Date: {date_hdr}",
        f"Subject: {subject}",
    ]
    if refs:
        lines.append(f"References: <{refs}>")
    if attachment is None:
        lines += ["Content-Type: text/plain; charset=utf-8", "", body]
        return ("\r\n".join(lines)).encode("utf-8")
    name, payload = attachment
    import base64
    b64 = base64.b64encode(payload).decode("ascii")
    lines += [
        'Content-Type: multipart/mixed; boundary="XBOUND"', "",
        "--XBOUND", "Content-Type: text/plain; charset=utf-8", "", body, "",
        "--XBOUND", f'Content-Type: application/octet-stream; name="{name}"',
        "Content-Transfer-Encoding: base64",
        f'Content-Disposition: attachment; filename="{name}"', "",
        b64, "--XBOUND--", "",
    ]
    return ("\r\n".join(lines)).encode("utf-8")


def cmd_selftest(args) -> int:
    import contextlib
    import io
    import tempfile

    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}: {name}")
        ok = ok and bool(cond)

    print("matter-mail selftest")
    check("subject normalization strips Re:/Fwd:/tags",
          _normalize_subject("RE: Fwd: [External] Claim status") ==
          _normalize_subject("Claim status"))
    check("date parse rfc2822",
          _parse_date_any("Tue, 10 Mar 2026 09:15:00 -0500") == date(2026, 3, 10))
    check("date parse iso offset -> UTC",
          _parse_date_any("2026-03-11T02:00:00+05:00") == date(2026, 3, 10))
    check("msgid canonicalization", _canonical_msgid(" <abc@x> ") == "abc@x")
    check("fallback hash distinguishes same-day same-subject replies",
          _msgid_hash(None, from_="a@x", date_iso="2026-03-10",
                      subject_norm="re claim", body_sha="h1") !=
          _msgid_hash(None, from_="a@x", date_iso="2026-03-10",
                      subject_norm="re claim", body_sha="h2"))
    slash_date = "/".join(("12", "3", "2026"))  # m/d/y rendering of Dec 3
    check("date pattern boundary-anchored",
          not _date_patterns(date(2026, 12, 3))[3].search("1" + slash_date)
          and bool(_date_patterns(date(2026, 12, 3))[3].search(f"on {slash_date} x")))
    graph_row = normalize_graph_json({
        "id": "AAMk1", "internetMessageId": "<g-1@mail.synthetic>",
        "receivedDateTime": "2026-03-12T15:00:00Z",
        "subject": "Claim status", "hasAttachments": True,
        "from": {"emailAddress": {"name": "C Test", "address": "C@Personal.SYNTHETIC"}},
        "toRecipients": [{"emailAddress": {"name": "A Counsel",
                                           "address": "ac@firm.synthetic"}}],
        "body": {"contentType": "html", "content": "<p>Hello  there</p>"},
    })
    check("graph json normalized (msgid, date, addr casefold, hasAttachments)",
          graph_row is not None
          and graph_row["msgid"] == "g-1@mail.synthetic"
          and graph_row["date_iso"] == "2026-03-12"
          and graph_row["from"] == "C Test <c@personal.synthetic>"
          and graph_row["has_attachments_unfetched"] is True
          and graph_row["body_sha256"] is not None)

    with tempfile.TemporaryDirectory(prefix="matter_mail_selftest_") as td:
        tmp = Path(td)
        matter = tmp / "matter"
        (matter / "production").mkdir(parents=True)

        # Minimal synthetic casegraph state (matter-mail reads it read-only).
        cg = matter / CASEGRAPH_DIRNAME
        (cg / "text").mkdir(parents=True)
        _write_json_atomic(cg / "manifest.json", {
            "schema_version": 1, "tool_version": "selftest",
            "matter_id": "SELFTEST", "bates_prefixes": ["TVRR-PROD"],
            "created": _utcnow(), "counts": {"documents": 1},
        })
        filed_doc_text = ("**Date:** 2026-03-12\n\nEmail re Claim status update "
                          "for conductor J.T. received March 12, 2026.")
        doc_sha = _sha256_bytes(filed_doc_text.encode("utf-8"))
        (cg / "text" / f"{doc_sha}.txt").write_text(filed_doc_text, encoding="utf-8")
        with open(cg / "documents.jsonl", "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({
                "relpath": "production/claim_status_memo.md", "sha256": doc_sha,
                "size": len(filed_doc_text), "mtime_iso": _utcnow(),
                "ext": ".md", "indexed_at": _utcnow(), "pages": None,
                "text_extractable": "full", "bates_prefix": "TVRR-PROD",
                "bates_start": 1, "bates_end": 1, "doc_date": "2026-03-12",
                "author": None, "custodian": None, "doc_type": None,
                "title": None, "dupes_of": None,
            }) + "\n")
        with open(cg / "chronology.jsonl", "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"date": "2026-02-20", "event": "Client injury at "
                                "Northgate Yard (synthetic)", "source_relpath":
                                "production/claim_status_memo.md"}) + "\n")
            f.write(json.dumps({"date": "2026-02-27", "event": "First contact / "
                                "intake call with firm (synthetic)",
                                "source_relpath": "production/claim_status_memo.md"}) + "\n")

        # A filed .eml already in the matter.
        filed_eml = _selftest_eml(
            "filed-001@mail.synthetic", "Client C. Test <client@personal.synthetic>",
            "Alex Counsel <acounsel@firm.synthetic>",
            "Thu, 12 Mar 2026 10:00:00 -0500", "Claim status",
            "Filed copy of the claim status email.")
        (matter / "production" / "filed_claim_status.eml").write_bytes(filed_eml)

        firm_cfg_path = tmp / "firm.json"
        _write_json_atomic(firm_cfg_path, {
            "firm_contacts": [
                {"name": "Alex Counsel", "emails": ["acounsel@firm.synthetic"],
                 "role": "attorney"},
                {"name": "Pat Paralegal", "emails": ["pparalegal@firm.synthetic"],
                 "role": "paralegal"},
            ],
            "mail_accounts": [
                {"label": "work", "address": "acounsel@firm.synthetic",
                 "transport": "graph"},
                {"label": "gmail_outlook",
                 "address": "acounsel.overflow@personal.synthetic",
                 "transport": "outlook-export"},
            ],
            "priority_windows": [
                {"start": "2026-03-04", "end": "2026-05-16",
                 "account": "gmail_outlook", "mode": "exhaustive",
                 "reason": "primary provider outage (synthetic)"},
            ],
        })

        buf = io.StringIO()
        ns = argparse.Namespace(matter_dir=str(matter), firm_config=str(firm_cfg_path),
                                window_start=None, window_end="2026-06-30",
                                margin_days=None, json=False)
        with contextlib.redirect_stdout(buf):
            rc = cmd_context(ns)
        check("context derives window from chronology", rc == 0)
        ctx = _load_json(_context_path(matter))
        check("window start = incident - margin",
              ctx["window"]["start"] == "2026-01-21")
        check("incident + first-contact anchors found",
              ctx["anchors"]["incident_date"] == "2026-02-20"
              and ctx["anchors"]["first_contact_date"] == "2026-02-27")
        check("mail accounts + priority window clamped",
              len(ctx["mail_accounts"]) == 2
              and ctx["priority_windows"][0]["start"] == "2026-03-04")

        na = argparse.Namespace(matter_dir=str(matter), name="Client C. Test",
                                email=["client@personal.synthetic"], role="client")
        with contextlib.redirect_stdout(buf):
            rc_add = cmd_add_participant(na)
            rc_ctx2 = cmd_context(ns)
        check("add-participant", rc_add == 0)
        check("context rebuild picks up participant", rc_ctx2 == 0)
        ctx = _load_json(_context_path(matter))
        check("participants include client + firm",
              len(ctx["participants"]) == 3)

        np_ = argparse.Namespace(matter_dir=str(matter), json=True)
        with contextlib.redirect_stdout(io.StringIO()) as pbuf:
            rc_plan = cmd_plan(np_)
        check("plan", rc_plan == 0)
        plan = json.loads(pbuf.getvalue())
        check("plan: graph participants + outlook-export + exhaustive rows",
              any(q["provider"] == "graph" and q["mode"] == "participants"
                  for q in plan["queries"])
              and any(q["provider"] == "outlook-export" for q in plan["queries"])
              and any(q["mode"] == "exhaustive" for q in plan["queries"]))
        check("plan excludes owner address from query targets",
              not any("acounsel.overflow@personal.synthetic" in q["query"]
                      for q in plan["queries"] if q["mode"] == "participants"))

        # Source mailbox export: filed copy, a missing email w/ attachment,
        # a reply citing an unknown earlier message, personal mail addressed
        # to the mailbox owner (must be excluded: owner is not a participant).
        src = tmp / "export"
        src.mkdir()
        (src / "m1_filed.eml").write_bytes(filed_eml)
        (src / "m2_missing.eml").write_bytes(_selftest_eml(
            "missing-002@mail.synthetic", "Client C. Test <client@personal.synthetic>",
            "Alex Counsel <acounsel@firm.synthetic>",
            "Fri, 20 Mar 2026 09:00:00 -0500", "Wage statement attached",
            "Attaching my wage statement per your request.",
            attachment=("wage_statement.pdf", b"%PDF-1.4 synthetic wage data")))
        (src / "m3_reply.eml").write_bytes(_selftest_eml(
            "reply-003@mail.synthetic", "Alex Counsel <acounsel@firm.synthetic>",
            "Client C. Test <client@personal.synthetic>",
            "Sat, 21 Mar 2026 09:00:00 -0500", "Re: Treatment plan",
            "Following up on the earlier note.", refs="unknown-000@mail.synthetic"))
        (src / "m4_personal.eml").write_bytes(_selftest_eml(
            "personal-004@mail.synthetic", "Family Member <fam@personal.synthetic>",
            "Alex Counsel <acounsel.overflow@personal.synthetic>",
            "Sun, 22 Mar 2026 09:00:00 -0500",
            "Dinner plans", "Personal note that must never enter the matter."))
        (src / "m5_outside_window.eml").write_bytes(_selftest_eml(
            "old-005@mail.synthetic", "Client C. Test <client@personal.synthetic>",
            "Alex Counsel <acounsel@firm.synthetic>",
            "Mon, 05 Jan 2015 09:00:00 -0500", "Old unrelated matter thread",
            "Correspondence from another era that must not leak into this matter."))

        ni = argparse.Namespace(matter_dir=str(matter), source=str(src),
                                provider=None, allow_unmatched=False,
                                allow_out_of_window=False, allow_firm_internal=False,
                                owner=[], json=True)
        with contextlib.redirect_stdout(io.StringIO()) as ibuf:
            rc_ing = cmd_ingest(ni)
        check("ingest", rc_ing == 0)
        ing = json.loads(ibuf.getvalue())
        check("ingest counts (3 matter, 1 owner-personal excluded, 1 out-of-window)",
              ing["ingested_new"] == 3 and ing["excluded_non_matter"] == 1
              and ing["excluded_out_of_window"] == 1)
        matter_blob = "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in matter.rglob("*") if p.is_file())
        check("excluded content absent from matter dir",
              "Dinner" not in matter_blob and "another era" not in matter_blob)
        with contextlib.redirect_stdout(io.StringIO()):
            rc_reing = cmd_ingest(ni)
        check("re-ingest idempotent", rc_reing == 0)
        rows = _load_jsonl(_messages_path(matter))
        check("no duplicate rows after re-ingest", len(rows) == 3)

        ng = argparse.Namespace(matter_dir=str(matter), strict=False, json=True)
        with contextlib.redirect_stdout(io.StringIO()) as gbuf:
            rc_gap = cmd_gap(ng)
        gap = json.loads(gbuf.getvalue())
        check("gap exits 1 on missing mail", rc_gap == 1)
        check("filed copy matched + body verified",
              gap["counts"]["filed_exact"] == 1
              and gap["filed_exact"][0]["body_verified"] is True)
        check("missing mail detected", gap["counts"]["missing_from_file"] == 2)
        check("attachment gap detected", gap["counts"]["attachment_gaps"] == 1)
        check("thread gap detected", gap["counts"]["thread_gaps"] == 1)

        nr = argparse.Namespace(matter_dir=str(matter), output=None,
                                force_external=False)
        with contextlib.redirect_stdout(io.StringIO()):
            rc_rep = cmd_report(nr)
        check("report", rc_rep == 0)
        report_md = (_state_dir(matter) / "gap_report.md").read_text(encoding="utf-8")
        check("report carries work-product + attorney banners",
              "ATTORNEY WORK PRODUCT" in report_md
              and "ATTORNEY REVIEW REQUIRED" in report_md)

    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ── main ────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="matter_mail", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("context", help="derive scan window + participants from the matter")
    p.add_argument("matter_dir")
    p.add_argument("--firm-config")
    p.add_argument("--window-start")
    p.add_argument("--window-end")
    p.add_argument("--margin-days", type=int, default=None,
                   help=f"window margin (default: firm config "
                        f"window_margin_days or {DEFAULT_MARGIN_DAYS})")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_context)

    p = sub.add_parser("add-participant", help="register an ad-hoc scan participant")
    p.add_argument("matter_dir")
    p.add_argument("--name", required=True)
    p.add_argument("--email", action="append", default=[])
    p.add_argument("--role")
    p.set_defaults(fn=cmd_add_participant)

    p = sub.add_parser("plan", help="emit per-account provider query plans "
                                    "(graph / outlook-export / gmail)")
    p.add_argument("matter_dir")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("ingest", help="normalize exported mail "
                                      "(.eml / .mbox / .msg / Graph or gmail JSON)")
    p.add_argument("matter_dir")
    p.add_argument("--source", required=True)
    p.add_argument("--provider", help="override provider tag "
                                      "(lowercase [a-z0-9_-], default: inferred)")
    p.add_argument("--owner", action="append", default=[],
                   help="additional mailbox-owner address(es) excluded from "
                        "participant matching (mail_accounts addresses are "
                        "always excluded)")
    p.add_argument("--allow-unmatched",
                   action="store_true",
                   help="keep header-only triage rows for non-participant mail "
                        "(exhaustive/outage windows); bodies are still discarded")
    p.add_argument("--allow-out-of-window", action="store_true",
                   help="ingest messages dated outside the scan window "
                        "(default: excluded and counted)")
    p.add_argument("--allow-firm-internal", action="store_true",
                   help="stage firm-only threads (no client/opponent participant); "
                        "default excludes them to prevent cross-matter leakage")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("gap", help="diff ingested mail vs the case file (exit 1 on gaps)")
    p.add_argument("matter_dir")
    p.add_argument("--strict", action="store_true",
                   help="probable/coverage/unverified findings also fail")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_gap)

    p = sub.add_parser("report", help="render attorney-review markdown report")
    p.add_argument("matter_dir")
    p.add_argument("--output")
    p.add_argument("--force-external", action="store_true",
                   help="allow --output outside the matter directory")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("status", help="state consistency check (exit 1 if attention needed)")
    p.add_argument("matter_dir")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("selftest", help="offline self-test")
    p.set_defaults(fn=cmd_selftest)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
