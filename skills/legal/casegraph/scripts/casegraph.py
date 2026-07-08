#!/usr/bin/env python3
"""Casegraph — per-matter case file index and verification gates.

The legal-case-file analog of a code index: a persistent, deterministic index of
every document in a matter directory, plus machine-enforced gates that check
agent outputs against that index (citation resolution, cross-matter isolation,
staleness).

Design contract (see SPEC.md):
- The index lives INSIDE the matter directory (``<matter_dir>/.casegraph/``),
  outside this repo, so isolation is physical.
- Deterministic and provenance-first: hashes, structured headers, filename
  patterns. No inference. Unreadable content is flagged, never guessed.
- Contamination checks never read another matter's directory; cross-matter
  detection uses a salted-hash fingerprint store only.
- Gate commands exit non-zero on failure so skills/CI can chain them.

Stdlib-only core; pypdf / python-docx are optional (graceful degradation).
Synthetic data only in this repository. Attorney review required before any
real-matter use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = 1
TOOL_VERSION = "1.0.0"
INDEX_DIRNAME = ".casegraph"
TEXT_CACHE_DIRNAME = "text"

# File types the indexer attempts text extraction for.
_TEXT_EXTS = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".html", ".htm"}
_PDF_EXTS = {".pdf"}
_DOCX_EXTS = {".docx"}
_EML_EXTS = {".eml"}

# Bates identifier: one-or-more uppercase alpha(numeric) prefix segments joined
# by hyphens, then a 3-8 digit number. e.g. TVRR-PROD-000123, ACME000045.
_BATES_TOKEN_RE = re.compile(
    r"\b([A-Z][A-Z0-9]{1,11}(?:-[A-Z][A-Z0-9]{1,11})*)[-_ ]?(\d{3,8})\b"
)

# Structured header fields used by production documents / fixtures:
#   **Bates Range:** TVRR-PROD-000001 - TVRR-PROD-000004
_HEADER_FIELD_RE = re.compile(
    r"^\*\*(?P<key>[A-Za-z /-]+):\*\*\s*(?P<value>.+?)\s*$", re.MULTILINE
)

# Candidate person/org names in outputs: 2-4 capitalized words in sequence
# (allowing initials like "J.T." and connectors). High recall, moderate
# precision — used only for WARN-level findings, never FAIL.
_NAME_CANDIDATE_RE = re.compile(
    r"\b([A-Z][a-zA-Z.]{1,20}(?:\s+(?:of|the|and|for|de|van|von)\s+|\s+)"
    r"[A-Z][a-zA-Z.]{1,20}(?:\s+[A-Z][a-zA-Z.]{1,20}){0,2})\b"
)

_QUOTE_RE = re.compile(r'"([^"\n]{20,300})"')


# ── small utilities ─────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _normalize_identifier(s: str) -> str:
    """Normalize a name/identifier for comparison and fingerprinting.

    NFKC (homoglyph/width defense) -> casefold -> strip punctuation ->
    collapse whitespace. ``J.T.`` and ``J T`` compare equal.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.casefold()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _salted_hash(value: str, salt: str) -> str:
    return hashlib.sha256((salt + "\x1f" + _normalize_identifier(value)).encode("utf-8")).hexdigest()


def _read_text_best_effort(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _index_dir(matter_dir: Path) -> Path:
    return matter_dir / INDEX_DIRNAME


def _manifest_path(matter_dir: Path) -> Path:
    return _index_dir(matter_dir) / "manifest.json"


def _documents_path(matter_dir: Path) -> Path:
    return _index_dir(matter_dir) / "documents.jsonl"


def _entities_path(matter_dir: Path) -> Path:
    return _index_dir(matter_dir) / "entities.json"


def _chronology_path(matter_dir: Path) -> Path:
    return _index_dir(matter_dir) / "chronology.jsonl"


def load_manifest(matter_dir: Path) -> dict:
    p = _manifest_path(matter_dir)
    if not p.exists():
        raise SystemExit(
            f"ERROR: no casegraph index at {p}. Run: casegraph.py init {matter_dir} "
            f"--matter-id <ID> --bates-prefix <PREFIX>"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def save_manifest(matter_dir: Path, manifest: dict) -> None:
    manifest["updated"] = _utcnow()
    p = _manifest_path(matter_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def load_documents(matter_dir: Path) -> List[dict]:
    p = _documents_path(matter_dir)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def save_documents(matter_dir: Path, rows: List[dict]) -> None:
    p = _documents_path(matter_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for row in sorted(rows, key=lambda r: r["relpath"]):
            f.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(tmp, p)


def load_entities(matter_dir: Path) -> dict:
    p = _entities_path(matter_dir)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_entities(matter_dir: Path, entities: dict) -> None:
    p = _entities_path(matter_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entities, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


# ── text extraction (graceful degradation, no inference) ───────────────────

def extract_text(path: Path) -> Tuple[Optional[str], str, Optional[int]]:
    """Return (text, extractable_status, pages).

    extractable_status: "full" | "partial" | "none" | "unsupported".
    Never guesses: a PDF page with no text layer contributes nothing and
    downgrades status to partial/none.
    """
    ext = path.suffix.lower()
    if ext in _TEXT_EXTS:
        return _read_text_best_effort(path), "full", None
    if ext in _PDF_EXTS:
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, "unsupported", None
        try:
            reader = PdfReader(str(path))
            pages = len(reader.pages)
            texts, empty = [], 0
            for pg in reader.pages:
                t = (pg.extract_text() or "").strip()
                if t:
                    texts.append(t)
                else:
                    empty += 1
            if not texts:
                return None, "none", pages
            status = "partial" if empty else "full"
            return "\n\n".join(texts), status, pages
        except Exception:
            return None, "none", None
    if ext in _DOCX_EXTS:
        try:
            import docx  # python-docx
        except ImportError:
            return None, "unsupported", None
        try:
            d = docx.Document(str(path))
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append("\t".join(c.text for c in row.cells))
            text = "\n".join(p for p in parts if p)
            return (text, "full", None) if text.strip() else (None, "none", None)
        except Exception:
            return None, "none", None
    if ext in _EML_EXTS:
        try:
            import email
            from email import policy
            msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
            headers = "\n".join(
                f"{k}: {msg.get(k, '')}" for k in ("From", "To", "Cc", "Date", "Subject")
            )
            body = msg.get_body(preferencelist=("plain", "html"))
            body_text = body.get_content() if body else ""
            return headers + "\n\n" + str(body_text), "full", None
        except Exception:
            return None, "none", None
    return None, "unsupported", None


def parse_header_fields(text: str) -> Dict[str, str]:
    """Parse the ``**Field:** value`` structured header convention."""
    fields = {}
    for m in _HEADER_FIELD_RE.finditer(text[:4000]):
        key = m.group("key").strip().lower().replace(" ", "_").replace("/", "_")
        fields[key] = m.group("value").strip()
    return fields


def parse_bates_range(value: str) -> Optional[Tuple[str, int, int]]:
    """Parse 'TVRR-PROD-000001 - TVRR-PROD-000004' (also 'through', en-dash).

    Returns (prefix, start, end) or None.
    """
    tokens = _BATES_TOKEN_RE.findall(value.upper())
    if not tokens:
        return None
    prefix = tokens[0][0]
    nums = [int(n) for p, n in tokens if p == prefix]
    if not nums:
        return None
    return prefix, min(nums), max(nums)


def bates_from_filename(name: str) -> Optional[Tuple[str, int]]:
    # Underscores are word characters, so "scan_TVRR-PROD-000010.pdf" would
    # otherwise never get a word boundary before TVRR and mis-parse as
    # prefix "PROD". Treat underscores as separators for filename parsing.
    m = _BATES_TOKEN_RE.search(name.upper().replace("_", " "))
    if m:
        return m.group(1), int(m.group(2))
    return None


# ── init / build / status ───────────────────────────────────────────────────

def cmd_init(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    matter_dir.mkdir(parents=True, exist_ok=True)
    mp = _manifest_path(matter_dir)
    if mp.exists() and not args.force:
        print(f"ERROR: index already exists at {mp} (use --force to reinitialize)")
        return 2
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "matter_id": args.matter_id,
        "bates_prefixes": sorted({p.upper() for p in (args.bates_prefix or [])}),
        "created": _utcnow(),
        "counts": {"documents": 0},
    }
    save_manifest(matter_dir, manifest)
    print(f"Initialized casegraph for matter '{args.matter_id}' at {_index_dir(matter_dir)}")
    if not manifest["bates_prefixes"]:
        print("NOTE: no --bates-prefix registered; isolation checks on bates will flag everything.")
    return 0


def _iter_matter_files(matter_dir: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(matter_dir):
        dirs[:] = [d for d in dirs if d != INDEX_DIRNAME and not d.startswith(".")]
        for name in files:
            if name.startswith("."):
                continue
            yield Path(root) / name


def _scan_file(matter_dir: Path, path: Path, no_text_cache: bool) -> dict:
    rel = path.relative_to(matter_dir).as_posix()
    st = path.stat()
    sha = _sha256_file(path)
    row = {
        "relpath": rel,
        "sha256": sha,
        "size": st.st_size,
        "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "ext": path.suffix.lower(),
        "indexed_at": _utcnow(),
        "pages": None,
        "text_extractable": "unsupported",
        "bates_prefix": None,
        "bates_start": None,
        "bates_end": None,
        "doc_date": None,
        "author": None,
        "custodian": None,
        "doc_type": None,
        "title": None,
        "dupes_of": None,
    }
    text, status, pages = extract_text(path)
    row["text_extractable"] = status
    row["pages"] = pages
    if text:
        fields = parse_header_fields(text)
        if "bates_range" in fields:
            parsed = parse_bates_range(fields["bates_range"])
            if parsed:
                row["bates_prefix"], row["bates_start"], row["bates_end"] = parsed
        for src, dst in (
            ("date", "doc_date"), ("author", "author"), ("custodian", "custodian"),
            ("document_type", "doc_type"), ("document_id", "title"),
        ):
            if fields.get(src):
                row[dst] = fields[src]
        if not no_text_cache:
            cache = _index_dir(matter_dir) / TEXT_CACHE_DIRNAME
            cache.mkdir(parents=True, exist_ok=True)
            (cache / f"{sha}.txt").write_text(text, encoding="utf-8", newline="\n")
    if row["bates_start"] is None:
        fb = bates_from_filename(path.name)
        if fb:
            row["bates_prefix"], row["bates_start"] = fb
            row["bates_end"] = fb[1]
    return row


def _harvest_header_entities(matter_dir: Path, rows: List[dict]) -> int:
    """Register Author/Custodian header values as entities (origin=header)."""
    entities = load_entities(matter_dir)
    added = 0
    for row in rows:
        for field, role in (("author", "author"), ("custodian", "custodian")):
            raw = row.get(field)
            if not raw:
                continue
            # Header values like "R.K., Trainmaster, Test Valley Railroad" carry
            # name + role + org; register each comma part as its own entity.
            for part in [p.strip() for p in raw.split(",") if p.strip()]:
                key = _normalize_identifier(part)
                if not key or len(key) < 2:
                    continue
                ent = entities.setdefault(
                    key, {"display": part, "aliases": [], "role": role,
                          "origin": "header", "sources": {}}
                )
                ent["sources"][row["relpath"]] = ent["sources"].get(row["relpath"], 0) + 1
                added += 1
    save_entities(matter_dir, entities)
    return added


def cmd_build(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    manifest = load_manifest(matter_dir)
    old_rows = {r["relpath"]: r for r in load_documents(matter_dir)}
    new_rows: List[dict] = []
    n_new = n_changed = n_same = 0

    for path in _iter_matter_files(matter_dir):
        rel = path.relative_to(matter_dir).as_posix()
        st = path.stat()
        old = old_rows.get(rel)
        if (
            old is not None
            and old["size"] == st.st_size
            and old["mtime_iso"] == datetime.fromtimestamp(
                st.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ):
            new_rows.append(old)
            n_same += 1
            continue
        row = _scan_file(matter_dir, path, args.no_text_cache)
        if old is None:
            n_new += 1
        else:
            n_changed += 1
        new_rows.append(row)

    removed = sorted(set(old_rows) - {r["relpath"] for r in new_rows})

    # Exact-duplicate marking: first relpath (sorted) is canonical.
    by_sha: Dict[str, List[dict]] = {}
    for r in new_rows:
        by_sha.setdefault(r["sha256"], []).append(r)
    n_dupes = 0
    for sha, group in by_sha.items():
        group.sort(key=lambda r: r["relpath"])
        for extra in group[1:]:
            extra["dupes_of"] = group[0]["relpath"]
            n_dupes += 1
        if group[0].get("dupes_of"):
            group[0]["dupes_of"] = None

    save_documents(matter_dir, new_rows)
    n_entities = _harvest_header_entities(matter_dir, new_rows)

    # Bates coverage report (registered prefixes only).
    coverage_notes: List[str] = []
    for prefix in manifest.get("bates_prefixes", []):
        nums: List[Tuple[int, int]] = sorted(
            (r["bates_start"], r["bates_end"])
            for r in new_rows
            if r.get("bates_prefix") == prefix and r.get("bates_start") is not None
        )
        prev_end = None
        for start, end in nums:
            if prev_end is not None and start <= prev_end:
                coverage_notes.append(f"{prefix}: overlap at {start:06d} (prev range ends {prev_end:06d})")
            if prev_end is not None and start > prev_end + 1:
                coverage_notes.append(f"{prefix}: gap {prev_end + 1:06d}-{start - 1:06d}")
            prev_end = max(prev_end or 0, end)

    unreadable = [r["relpath"] for r in new_rows if r["text_extractable"] in ("none",)]
    manifest["counts"] = {
        "documents": len(new_rows),
        "duplicates": n_dupes,
        "unreadable": len(unreadable),
        "entities": len(load_entities(matter_dir)),
    }
    save_manifest(matter_dir, manifest)

    report = {
        "matter_id": manifest["matter_id"],
        "documents": len(new_rows),
        "new": n_new, "changed": n_changed, "unchanged": n_same,
        "removed": removed,
        "duplicates": n_dupes,
        "unreadable": unreadable,
        "bates_coverage_notes": coverage_notes,
        "entity_mentions_registered": n_entities,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Indexed {len(new_rows)} documents for matter '{manifest['matter_id']}' "
              f"({n_new} new, {n_changed} changed, {n_same} unchanged"
              f"{', ' + str(len(removed)) + ' removed' if removed else ''}).")
        if n_dupes:
            print(f"Exact duplicates: {n_dupes} (marked dupes_of canonical copy)")
        if unreadable:
            print(f"UNREADABLE (no text layer — manual/OCR review needed): {len(unreadable)}")
            for u in unreadable[:20]:
                print(f"  - {u}")
        for note in coverage_notes:
            print(f"BATES: {note}")
    return 0


def cmd_status(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    manifest = load_manifest(matter_dir)
    old_rows = {r["relpath"]: r for r in load_documents(matter_dir)}
    added, changed = [], []
    seen = set()
    for path in _iter_matter_files(matter_dir):
        rel = path.relative_to(matter_dir).as_posix()
        seen.add(rel)
        old = old_rows.get(rel)
        if old is None:
            added.append(rel)
            continue
        st = path.stat()
        mt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if old["size"] != st.st_size or old["mtime_iso"] != mt:
            changed.append(rel)
        elif args.deep and _sha256_file(path) != old["sha256"]:
            changed.append(rel)
    removed = sorted(set(old_rows) - seen)
    stale = bool(added or changed or removed)
    report = {
        "matter_id": manifest["matter_id"],
        "stale": stale,
        "added": sorted(added), "changed": sorted(changed), "removed": removed,
        "indexed_documents": len(old_rows),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if stale:
            print(f"STALE index for matter '{manifest['matter_id']}':")
            for label, items in (("added", added), ("changed", changed), ("removed", removed)):
                for it in sorted(items):
                    print(f"  {label}: {it}")
            print("Run `casegraph.py build` before relying on the index.")
        else:
            print(f"Index current: {len(old_rows)} documents, matter '{manifest['matter_id']}'.")
    return 1 if stale else 0


# ── query ────────────────────────────────────────────────────────────────────

def _resolve_bates(rows: List[dict], prefix: str, number: int) -> Optional[dict]:
    for r in rows:
        if (
            r.get("bates_prefix") == prefix
            and r.get("bates_start") is not None
            and r["bates_start"] <= number <= (r.get("bates_end") or r["bates_start"])
        ):
            return r
    return None


def cmd_query(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    load_manifest(matter_dir)
    rows = load_documents(matter_dir)
    results: List[dict] = []

    if args.bates:
        m = _BATES_TOKEN_RE.search(args.bates.upper())
        if not m:
            print(f"ERROR: not a bates identifier: {args.bates}")
            return 2
        hit = _resolve_bates(rows, m.group(1), int(m.group(2)))
        results = [hit] if hit else []
    elif args.doc:
        needle = args.doc.replace("\\", "/").lower()
        results = [r for r in rows if needle in r["relpath"].lower()]
    elif args.entity:
        entities = load_entities(matter_dir)
        key = _normalize_identifier(args.entity)
        ent = entities.get(key)
        if ent is None:
            for k, v in entities.items():
                if key in k or any(key == _normalize_identifier(a) for a in v.get("aliases", [])):
                    ent = v
                    break
        print(json.dumps(ent or {}, indent=2))
        return 0 if ent else 1
    elif args.grep:
        pattern = re.compile(args.grep, re.IGNORECASE)
        cache = _index_dir(matter_dir) / TEXT_CACHE_DIRNAME
        for r in rows:
            fp = cache / f"{r['sha256']}.txt"
            if not fp.exists():
                continue
            for i, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    results.append({"relpath": r["relpath"], "line": i, "text": line.strip()[:240]})
    else:
        results = rows

    print(json.dumps(results, indent=2))
    return 0 if results else 1


# ── verification gates ──────────────────────────────────────────────────────

def _load_allowlist() -> set:
    """Global legal allowlist (courts, statutes, common legal phrases) shipped
    with the skill. Normalized entries."""
    path = Path(__file__).resolve().parent.parent / "data" / "legal_allowlist.txt"
    entries: set = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                entries.add(_normalize_identifier(line))
    return entries


def _extract_citations(text: str) -> List[Tuple[str, int]]:
    out = []
    for m in _BATES_TOKEN_RE.finditer(text.upper()):
        out.append((m.group(1), int(m.group(2))))
    return out


def cmd_verify_cites(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    manifest = load_manifest(matter_dir)
    rows = load_documents(matter_dir)
    output_path = Path(args.output_file)
    if not output_path.exists():
        print(f"ERROR: output file not found: {output_path}")
        return 2
    text = _read_text_best_effort(output_path)

    registered = set(manifest.get("bates_prefixes", []))
    failures: List[str] = []
    checked = 0
    seen: set = set()
    for prefix, number in _extract_citations(text):
        if prefix not in registered:
            continue  # foreign prefixes are the isolation gate's job
        key = (prefix, number)
        if key in seen:
            continue
        seen.add(key)
        checked += 1
        if _resolve_bates(rows, prefix, number) is None:
            failures.append(f"unresolved citation: {prefix}-{number:06d} "
                            f"(no indexed document covers this number)")

    quote_misses: List[str] = []
    quotes_checked = 0
    if args.quotes:
        cache = _index_dir(matter_dir) / TEXT_CACHE_DIRNAME
        corpus: List[str] = []
        for r in rows:
            fp = cache / f"{r['sha256']}.txt"
            if fp.exists():
                corpus.append(_normalize_identifier(fp.read_text(encoding="utf-8")))
        blob = "\n".join(corpus)
        for q in _QUOTE_RE.findall(text):
            quotes_checked += 1
            if _normalize_identifier(q) not in blob:
                quote_misses.append(q[:120])

    report = {
        "output_file": str(output_path),
        "matter_id": manifest["matter_id"],
        "citations_checked": checked,
        "citation_failures": failures,
        "quotes_checked": quotes_checked,
        "quote_misses": quote_misses,
        "pass": not failures and not quote_misses,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"verify-cites: {checked} citations checked against matter "
              f"'{manifest['matter_id']}'.")
        for f_ in failures:
            print(f"  FAIL: {f_}")
        if args.quotes:
            print(f"verify-cites: {quotes_checked} quotes (>=20 chars) checked.")
            for q in quote_misses:
                print(f"  FAIL: quote not found in any indexed document: \"{q}...\"")
        if report["pass"]:
            print("PASS")
    return 0 if report["pass"] else 1


def _fingerprint_store_load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def cmd_export_fingerprint(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    manifest = load_manifest(matter_dir)
    entities = load_entities(matter_dir)
    store_path = Path(args.store)
    store = _fingerprint_store_load(store_path)
    existing = store.get(manifest["matter_id"], {})
    salt = existing.get("salt") or hashlib.sha256(os.urandom(32)).hexdigest()[:32]

    entity_hashes = sorted({
        _salted_hash(k, salt) for k in entities
    } | {
        _salted_hash(a, salt)
        for v in entities.values() for a in v.get("aliases", [])
    })
    prefix_hashes = sorted(_salted_hash(p, salt) for p in manifest.get("bates_prefixes", []))
    store[manifest["matter_id"]] = {
        "salt": salt,
        "bates_prefix_hashes": prefix_hashes,
        "entity_hashes": entity_hashes,
        "exported": _utcnow(),
    }
    store_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = store_path.with_suffix(store_path.suffix + ".tmp")
    tmp.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, store_path)
    print(f"Exported fingerprint for matter '{manifest['matter_id']}' "
          f"({len(entity_hashes)} entity hashes, {len(prefix_hashes)} prefix hashes) "
          f"to {store_path}")
    return 0


def cmd_check_isolation(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    manifest = load_manifest(matter_dir)
    output_path = Path(args.output_file)
    if not output_path.exists():
        print(f"ERROR: output file not found: {output_path}")
        return 2
    text = _read_text_best_effort(output_path)
    matter_id = manifest["matter_id"]
    registered_prefixes = set(manifest.get("bates_prefixes", []))
    allowlist = _load_allowlist()
    entities = load_entities(matter_dir)
    known_keys = set(entities)
    for v in entities.values():
        for a in v.get("aliases", []):
            known_keys.add(_normalize_identifier(a))

    failures: List[str] = []
    warnings: List[str] = []

    # 1) Foreign bates prefixes → FAIL (high-precision cross-matter signal).
    foreign_seen: set = set()
    for prefix, number in _extract_citations(text):
        if prefix in registered_prefixes or prefix in foreign_seen:
            continue
        norm_prefix = _normalize_identifier(prefix)
        if norm_prefix in allowlist:
            continue
        foreign_seen.add(prefix)
        failures.append(
            f"foreign bates prefix '{prefix}' (e.g. {prefix}-{number:06d}) — not "
            f"registered to matter '{matter_id}'"
        )

    # 2) Fingerprint store — identifiers registered to OTHER matters → FAIL.
    fp_hits: List[str] = []
    if args.fingerprints:
        store = _fingerprint_store_load(Path(args.fingerprints))
        candidates = {c for c in _candidate_names(text, subspans=True)}
        candidates |= {p for p, _ in _extract_citations(text)}
        for other_id, entry in store.items():
            if other_id == matter_id:
                continue
            salt = entry.get("salt", "")
            hashes = set(entry.get("entity_hashes", [])) | set(entry.get("bates_prefix_hashes", []))
            for cand in candidates:
                norm = _normalize_identifier(cand)
                if not norm or norm in allowlist or norm in known_keys:
                    continue
                if _salted_hash(cand, salt) in hashes:
                    fp_hits.append(f"'{cand}' matches an identifier registered to matter "
                                   f"'{other_id}'")
        failures.extend(sorted(set(fp_hits)))

    # 3) Unregistered candidate names → WARN (moderate precision; attorney list).
    unknown: List[str] = []
    for cand in sorted(set(_candidate_names(text))):
        norm = _normalize_identifier(cand)
        if not norm or norm in allowlist or norm in known_keys:
            continue
        if any(norm in k or k in norm for k in known_keys):
            continue  # partial alias overlap — treat as known
        unknown.append(cand)
    warnings.extend(f"unregistered name in output: '{u}'" for u in unknown)

    passed = not failures and (not args.strict or not warnings)
    report = {
        "output_file": str(output_path),
        "matter_id": matter_id,
        "failures": failures,
        "warnings": warnings,
        "strict": bool(args.strict),
        "pass": passed,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"check-isolation: matter '{matter_id}', output {output_path.name}")
        for f_ in failures:
            print(f"  FAIL: {f_}")
        for w in warnings:
            print(f"  WARN: {w}")
        print("PASS" if passed else "FAIL" if failures else "FAIL (strict: unresolved WARNs)")
    return 0 if passed else 1


def _candidate_names(text: str, subspans: bool = False) -> Iterable[str]:
    """Yield candidate person/org names from output text.

    With ``subspans=True``, also yield every contiguous 2+-word sub-span of
    each candidate — a maximal span like 'Witness Marcus Ellery' must still
    match a fingerprint registered as 'Marcus Ellery'. Used for the
    fingerprint check (recall matters); WARN reporting uses maximal spans only
    (readability matters).
    """
    # NFKC first: fullwidth/compatibility homoglyphs (e.g. 'Ｍarcus') must
    # fold to ASCII BEFORE the [A-Z]-anchored candidate regex runs, or a
    # homoglyph-spelled name evades extraction entirely (red-team finding).
    text = unicodedata.normalize("NFKC", text)
    # Strip code fences and markdown emphasis to reduce false positives.
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = text.replace("**", " ")
    seen: set = set()
    for m in _NAME_CANDIDATE_RE.finditer(text):
        cand = m.group(1).strip()
        # Skip sentence-initial artifacts: single common word pairs handled by
        # allowlist; here skip candidates that are all-uppercase (headings).
        if cand.isupper():
            continue
        if cand not in seen:
            seen.add(cand)
            yield cand
        if subspans:
            words = cand.split()
            for width in range(2, len(words)):
                for i in range(len(words) - width + 1):
                    sub = " ".join(words[i:i + width])
                    if sub not in seen:
                        seen.add(sub)
                        yield sub


# ── entity management ────────────────────────────────────────────────────────

def cmd_add_entity(args) -> int:
    matter_dir = Path(args.matter_dir).resolve()
    load_manifest(matter_dir)
    entities = load_entities(matter_dir)
    key = _normalize_identifier(args.name)
    ent = entities.setdefault(
        key, {"display": args.name, "aliases": [], "role": args.role or "",
              "origin": "manual", "sources": {}}
    )
    for alias in args.alias or []:
        if alias not in ent["aliases"]:
            ent["aliases"].append(alias)
    if args.role:
        ent["role"] = args.role
    save_entities(matter_dir, entities)
    print(f"Registered entity '{args.name}' ({len(ent['aliases'])} aliases) "
          f"for matter.")
    return 0


# ── selftest ────────────────────────────────────────────────────────────────

def cmd_selftest(args) -> int:
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}: {name}")
        ok = ok and bool(cond)

    print("casegraph selftest")
    # Bates parsing
    check("bates range parse",
          parse_bates_range("TVRR-PROD-000001 - TVRR-PROD-000004") == ("TVRR-PROD", 1, 4))
    check("bates 'through' parse",
          parse_bates_range("ACME-000010 through ACME-000012") == ("ACME", 10, 12))
    check("bates from filename", bates_from_filename("TVRR-PROD-000123.pdf") == ("TVRR-PROD", 123))
    check("normalize homoglyph/case",
          _normalize_identifier("Ｊ.Ｔ.") == _normalize_identifier("j t"))

    with tempfile.TemporaryDirectory(prefix="casegraph_selftest_") as td:
        matter = Path(td) / "matter"
        docs = matter / "production"
        docs.mkdir(parents=True)
        (docs / "TVRR-PROD-000001.md").write_text(
            "**Bates Range:** TVRR-PROD-000001 - TVRR-PROD-000002\n"
            "**Author:** R.K., Trainmaster, Test Valley Railroad\n"
            "**Date:** 2024-11-13\n\nThe conductor reported an unsafe coupling procedure.\n",
            encoding="utf-8")
        ns = argparse.Namespace(matter_dir=str(matter), matter_id="SELFTEST",
                                bates_prefix=["TVRR-PROD"], force=False)
        check("init", cmd_init(ns) == 0)
        nb = argparse.Namespace(matter_dir=str(matter), no_text_cache=False, json=True)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_build(nb)
        check("build", rc == 0)
        rows = load_documents(matter)
        check("bates indexed", rows and rows[0]["bates_prefix"] == "TVRR-PROD")
        good = Path(td) / "out_good.md"
        good.write_text("Fact cited to TVRR-PROD-000002.\n", encoding="utf-8")
        bad = Path(td) / "out_bad.md"
        bad.write_text("Fact cited to TVRR-PROD-000099 and NORF-PROD-000001.\n", encoding="utf-8")
        nv = argparse.Namespace(matter_dir=str(matter), output_file=str(good),
                                quotes=False, json=True)
        with contextlib.redirect_stdout(buf):
            rc_good = cmd_verify_cites(nv)
            nv.output_file = str(bad)
            rc_bad = cmd_verify_cites(nv)
            ni = argparse.Namespace(matter_dir=str(matter), output_file=str(bad),
                                    fingerprints=None, strict=False, json=True)
            rc_iso_bad = cmd_check_isolation(ni)
            ni.output_file = str(good)
            rc_iso_good = cmd_check_isolation(ni)
        check("verify-cites pass", rc_good == 0)
        check("verify-cites fail on out-of-range", rc_bad == 1)
        check("isolation fail on foreign prefix", rc_iso_bad == 1)
        check("isolation pass on clean output", rc_iso_good == 0)
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ── main ────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="casegraph", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="initialize a matter index")
    p.add_argument("matter_dir")
    p.add_argument("--matter-id", required=True)
    p.add_argument("--bates-prefix", action="append", default=[])
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("build", help="incremental scan + index")
    p.add_argument("matter_dir")
    p.add_argument("--no-text-cache", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser("status", help="staleness check (exit 1 if stale)")
    p.add_argument("matter_dir")
    p.add_argument("--deep", action="store_true", help="hash-verify unchanged-looking files")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("query", help="index lookups")
    p.add_argument("matter_dir")
    p.add_argument("--bates")
    p.add_argument("--doc")
    p.add_argument("--entity")
    p.add_argument("--grep")
    p.set_defaults(fn=cmd_query)

    p = sub.add_parser("verify-cites", help="citations in output must resolve (exit 1 on failure)")
    p.add_argument("matter_dir")
    p.add_argument("output_file")
    p.add_argument("--quotes", action="store_true", help="also verify quoted strings appear in corpus")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_verify_cites)

    p = sub.add_parser("check-isolation", help="cross-matter contamination gate (exit 1 on FAIL)")
    p.add_argument("matter_dir")
    p.add_argument("output_file")
    p.add_argument("--fingerprints", help="shared salted-hash fingerprint store")
    p.add_argument("--strict", action="store_true", help="unresolved WARNs also fail")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_check_isolation)

    p = sub.add_parser("add-entity", help="register an entity for the matter")
    p.add_argument("matter_dir")
    p.add_argument("--name", required=True)
    p.add_argument("--alias", action="append", default=[])
    p.add_argument("--role")
    p.set_defaults(fn=cmd_add_entity)

    p = sub.add_parser("export-fingerprint", help="publish salted identifier hashes")
    p.add_argument("matter_dir")
    p.add_argument("--store", required=True)
    p.set_defaults(fn=cmd_export_fingerprint)

    p = sub.add_parser("selftest", help="offline self-test")
    p.set_defaults(fn=cmd_selftest)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
