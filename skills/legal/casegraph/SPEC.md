# Casegraph — Per-Matter Case File Index (Spec)

**Status:** v1 spec, implemented 2026-07-08 (overnight autonomous build)
**Owner gate:** attorney review required before any real-matter use. Synthetic data only in this repo.

## 1. What this is

Casegraph is the legal-case-file analog of a code index ("codegraph for case files"): a
persistent, deterministic, per-matter index of every document in a discovery/matter
directory, plus machine-enforced verification gates that check agent outputs *against*
that index.

It exists to solve four concrete problems in large-document legal work:

1. **Citation accuracy** — every bates/document reference in an output must resolve to a
   real, hashed, indexed document (the manual 54-row citation audit from the pilot,
   mechanized).
2. **Cross-matter isolation** — facts, names, and bates numbers from one case must never
   appear in another case's work product. Enforced positively (an output may only
   reference identifiers known to the *active* matter) and negatively (a shared
   fingerprint store detects another matter's identifiers without ever exposing them in
   plaintext).
3. **Drift/staleness** — supplemental productions arrive over months. The index is
   hash-keyed and incremental; `status` says exactly what changed since the last build,
   so analysis is never silently based on a stale corpus.
4. **Token efficiency** — the agent queries the index and the extracted-text cache
   instead of re-reading a 10,000-page production every session. Big corpora become
   grep-able.

## 2. What this is NOT (honest usefulness assessment)

- **Not semantic understanding.** Casegraph is deterministic: hashes, metadata, regexes,
  exact text. It verifies that *DOC TVRR-PROD-000123 exists and contains the quoted
  string*; it cannot verify that a paraphrase fairly characterizes the document. Pair:
  LLM does comprehension, casegraph does verification. Neither replaces the other.
- **Not OCR.** If a scanned PDF has no text layer, casegraph indexes it as
  `text_extractable: false` and any citation *to its content* is flagged for manual
  check. It never guesses.
- **Not entity resolution at human quality.** The entity registry starts from structured
  document headers and explicit additions. Name-variant recall is imperfect; the
  isolation gate therefore treats unknown-name findings as WARN (attorney judgment) and
  reserves FAIL for high-precision signals (foreign bates prefixes, fingerprint hits).
- **Not a substitute for attorney review.** It is a *pre-attorney* quality gate that
  makes mechanical errors impossible to miss, so attorney time goes to judgment calls.

**Net assessment:** for ongoing, persistent legal work on large document sets, this is
the single highest-leverage piece of infrastructure available: every downstream skill
(intake, review, chronology, deposition prep) gets verifiable citations, staleness
detection, and isolation enforcement from one index. The failure modes are known and
bounded (OCR, paraphrase, name variants) and each is surfaced rather than hidden.

## 3. Isolation model

- **Physical isolation:** the index lives at `<matter_dir>/.casegraph/`, inside the
  matter directory, outside this repo (e.g. `C:\Matters\<id>\.casegraph\`). Moving or
  archiving the matter moves its index. Nothing matter-specific is ever written into
  the repo or into another matter's directory. (The repo validator's
  `check_matter_scaffolds` gate already enforces "no matter dirs in repo".)
- **One active matter per session:** skills must resolve exactly one matter dir and
  pass it explicitly to every casegraph command. There is no ambient "current matter"
  state that could leak across sessions.
- **Positive gate:** `verify-cites` — every doc/bates citation in an output must
  resolve in the *active* matter's index.
- **Negative gate:** `check-isolation` — (a) any bates-like identifier whose prefix is
  not registered to the active matter → **FAIL**; (b) any candidate person/org name not
  in the active matter's entity registry or the global legal allowlist → **WARN** (list
  for attorney); (c) optional fingerprint store: each matter can export a salted-hash
  fingerprint of its identifiers to a shared local file; a hit from *another* matter's
  fingerprint in this output → **FAIL** ("references an identifier registered to another
  matter") — detected without any cross-matter plaintext ever being read or stored.
- **No cross-matter reads:** contamination checking never opens another matter's
  directory. The fingerprint store contains only salted SHA-256 hashes.

## 4. On-disk layout (schema v1)

```
<matter_dir>/.casegraph/
  manifest.json      # schema_version, matter_id, bates_prefixes[], created, updated,
                     # tool_version, counts
  documents.jsonl    # one per file: relpath, sha256, size, mtime_iso, ext, pages,
                     # text_extractable, bates_start, bates_end, doc_date, author,
                     # custodian, doc_type, title, dupes_of (sha match), indexed_at
  entities.json      # {canonical: {aliases: [], role: "", sources: {relpath: count},
                     #  origin: "header"|"manual"|"agent"}}
  text/<sha256>.txt  # extracted plain text cache (grep target); absent when
                     # text_extractable=false or --no-text-cache
  chronology.jsonl   # optional; {date, event, source_relpath, source_locator, added_by}
```

Shared (optional, still local-only): `%HERMES_HOME%/casegraph/fingerprints.json` —
`{matter_id: {salt, bates_prefix_hashes: [], entity_hashes: []}}`.

## 5. CLI surface

`python skills/legal/casegraph/scripts/casegraph.py <cmd> ...`

| Command | Purpose |
|---|---|
| `init <matter_dir> --matter-id X --bates-prefix P [...]` | create manifest |
| `build <matter_dir>` | incremental scan+index (hash-keyed; unchanged files skipped) |
| `status <matter_dir>` | staleness: added/changed/removed since last build; exit 1 if stale |
| `query <matter_dir> [--bates N|--doc PATH|--entity NAME|--grep REGEX]` | lookups over index + text cache |
| `verify-cites <matter_dir> <output.md>` | every citation resolves; optional quote spot-check; exit 1 on failure |
| `check-isolation <matter_dir> <output.md> [--fingerprints FILE] [--strict]` | contamination gate; exit 1 on FAIL (or on WARN with --strict) |
| `add-entity <matter_dir> --name N [--alias A ...] [--role R]` | registry management |
| `export-fingerprint <matter_dir> --store FILE` | publish salted hashes for cross-matter detection |
| `selftest` | offline self-test on bundled synthetic fixtures |

All commands: deterministic, stdlib-first (pypdf/docx optional, degrade gracefully),
JSON `--json` output for programmatic use, non-zero exit codes for gate failures so
skills and CI can chain them.

## 6. Extraction rules (provenance-first, no inference)

- Metadata comes from three explicit sources only, recorded per-field: (1) the file
  system (size, mtime, hash); (2) the document's own structured header block when
  present (the `**Bates Range:** ...` convention used in productions/fixtures);
  (3) filename patterns (`<PREFIX>-\d{6}` bates in name). Nothing is inferred.
- Bates parsing: normalized to `(prefix, int)`; ranges validated; overlaps and gaps
  reported by `build`.
- Duplicate detection: exact (same sha256) → `dupes_of`; near-dupe detection is out of
  scope for v1 (documented limitation).
- PDF text: pypdf extraction; a page yielding no text marks the doc
  `text_extractable: partial|false`. DOCX via python-docx; EML via stdlib `email`;
  txt/md as-is with encoding detection.

## 7. Skill integration (P5)

- `discovery-review` Step 0 (Production Preflight) gains: "run `casegraph build` +
  `status`; the preflight manifest/bates/dupe checks are the tool's output, verified,
  not re-derived by the model."
- Review/intake Verification sections gain: "run `verify-cites` and `check-isolation`
  on every output file; both must exit 0 (WARNs reviewed) before attorney handoff."
- Existing gates are only ADDED TO — never weakened (standing owner constraint).

## 8. Test plan (P4)

Unit + adversarial pytest on synthetic fixtures only: bates parse edge cases; stale
index detection; dupe hashing; citation misses (unknown bates, out-of-range,
wrong-prefix); quote verification hit/miss; isolation FAIL on foreign prefix; WARN on
unregistered name; fingerprint hit from a second synthetic matter; unicode/homoglyph
normalization in identifiers; unreadable-PDF degradation; `--strict` behavior; exit
codes; no writes outside `<matter_dir>/.casegraph/` and the explicit fingerprint store.
