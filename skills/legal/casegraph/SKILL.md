---
name: legal-casegraph
description: "Per-matter case file index and verification gates."
version: 1.0.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, discovery, index, verification, isolation, citations, fela, personal-injury]
    category: legal
    related_skills: [legal-discovery-intake, legal-discovery-review]
---

# Legal Casegraph Skill

Build and query a persistent, deterministic index of every document in a matter
directory, and run machine-enforced verification gates on work product: citation
resolution, cross-matter isolation, and index staleness. This is the case-file
analog of a code index. See `SPEC.md` for architecture and the honest
usefulness assessment (including what this tool cannot do).

**CONFIDENTIALITY:** The index lives inside the matter directory
(`<matter_dir>/.casegraph/`) and contains document hashes, extracted text, and
entity names — it is attorney work product, exactly as sensitive as the matter
documents themselves. Keep matter directories outside this repository and
outside cloud-synced folders unless the attorney has approved the storage
location. Never commit an index, a fingerprint store, or any matter content to
this repository. This skill uses synthetic facts for development and testing only.

**ATTORNEY REVIEW REQUIRED:** Gate results are mechanical checks, not legal
judgment. A PASS means citations resolve and no cross-matter identifiers were
detected — it does not mean the analysis is correct or complete. All outputs
remain drafts requiring attorney review.

## When to Use

- At the start of any discovery-review or intake session: build/refresh the
  matter index and confirm it is not stale.
- Before handing ANY work product to the attorney: run `verify-cites` and
  `check-isolation` on the output file.
- When a supplemental production arrives: `build` incrementally re-indexes.
- To locate documents by bates number, entity, or text without re-reading the
  corpus (token efficiency: query the index, do not re-read documents you can
  grep).

## Prerequisites

- A matter directory OUTSIDE this repository (e.g. `C:\Matters\<id>\`) holding
  the produced documents (PDF, DOCX, EML, text/markdown).
- Python 3.10+; `pypdf` and `python-docx` optional (PDF/DOCX text extraction
  degrades gracefully to "unreadable — manual review" without them).

## How to Run

```
# one-time per matter
python skills/legal/casegraph/scripts/casegraph.py init  C:\Matters\M1 --matter-id M1 --bates-prefix TVRR-PROD

# every session / after new productions
python skills/legal/casegraph/scripts/casegraph.py build  C:\Matters\M1
python skills/legal/casegraph/scripts/casegraph.py status C:\Matters\M1   # exit 1 = stale

# queries (token-efficient corpus access)
python skills/legal/casegraph/scripts/casegraph.py query C:\Matters\M1 --bates TVRR-PROD-000123
python skills/legal/casegraph/scripts/casegraph.py query C:\Matters\M1 --grep "coupling"
python skills/legal/casegraph/scripts/casegraph.py query C:\Matters\M1 --entity "R.K."

# gates — run on every output before attorney handoff (exit 0 required)
python skills/legal/casegraph/scripts/casegraph.py verify-cites    C:\Matters\M1 review_package.md --quotes
python skills/legal/casegraph/scripts/casegraph.py check-isolation C:\Matters\M1 review_package.md --fingerprints %HERMES_HOME%\casegraph\fingerprints.json

# registry maintenance
python skills/legal/casegraph/scripts/casegraph.py add-entity C:\Matters\M1 --name "Northgate Yard" --role location
python skills/legal/casegraph/scripts/casegraph.py export-fingerprint C:\Matters\M1 --store %HERMES_HOME%\casegraph\fingerprints.json
```

## Gate Semantics

| Gate | FAIL (exit 1) | WARN (listed, exit 0 unless --strict) |
|---|---|---|
| `status` | index stale (files added/changed/removed) | — |
| `verify-cites` | a cited bates number resolves to no indexed document; `--quotes`: a quoted string (≥20 chars) appears in no indexed document | — |
| `verify-chronology` | a chronology entry's Source citation does not resolve | entry's date (any common rendering) not found in the cited document's text; cited document unreadable/unverifiable |
| `check-isolation` | bates prefix not registered to this matter; identifier matching ANOTHER matter's fingerprint | capitalized name not in this matter's entity registry or the global legal allowlist |

WARNs are an attorney-review list, not noise: a legitimate new name should be
registered with `add-entity` (which also documents who the person is); a name
you cannot place may be contamination or hallucination — investigate before
handoff.

## Isolation Rules (mandatory)

1. One matter per session. Resolve the matter directory once, explicitly, and
   pass it to every command. Never operate on two matters in one session.
2. Never copy text between matter directories, even as "an example."
3. `check-isolation` must pass on every output before attorney handoff. Run it
   with `--fingerprints` when more than one matter exists on this machine.
4. After building/updating a matter's entity registry, re-run
   `export-fingerprint` so other matters can detect leakage OF this matter.
   The store holds salted hashes only — no plaintext crosses matters.

## Pitfalls

- A stale index silently invalidates every downstream check — run `status`
  first, every session.
- `text_extractable: none` documents (scans without OCR) are indexed by
  filename/bates only; facts "cited" to them cannot be text-verified. The
  build output lists them — they need manual review or OCR before reliance.
- Quote verification is exact after normalization: paraphrases are NOT checked.
  A passing `verify-cites` does not certify that paraphrased characterizations
  are fair — that requires attorney review.
- The entity WARN check is recall-limited (regex candidates). It reduces, but
  does not eliminate, the need for human review of names.
