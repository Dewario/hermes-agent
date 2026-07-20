# Jurisdiction packs

Machine-readable discovery rule packs for the counsel-pack expansion
(`COUNSEL_PACK_SPEC.md`). Skill/CLI only; not Hermes core tools.

## Load order

1. Read matter profile: `jurisdiction_pack`, optional `case_overlay`.
2. Load `packs/<jurisdiction_pack>.yaml`.
3. If overlay is set, load `packs/<case_overlay>.yaml` and require
   `base_pack == jurisdiction_pack`.
4. Merge rules by `id` (overlay wins on conflict).
5. Filter by `applies_to` for the current `request_type`
   (`rog`, `rfp`, `rfa`, `expert`, or `all`).

## Shipped packs

| pack_id | status | Role |
|---------|--------|------|
| `frcp_generic` | active | Default federal discovery rules (26/33/34/36/e) |
| `fela` | active | FELA/railroad theme checks on top of FRCP (`fela.yaml`) |
| `ca_ccp` | active | California CCP/Evidence Code baselines for discovery and expert planning |
| `ca_san_bernardino_local` | active overlay | San Bernardino Superior Court local civil overlay for `ca_ccp` |
| `wa_cr` | active | Washington Superior Court Civil Rules and Evidence Rule expert baselines |
| `wa_king_lcr` | active overlay | King County Superior Court local civil overlay for `wa_cr` |
| `wa_pierce_pclr` | active overlay | Pierce County Superior Court local civil overlay for `wa_cr` |

## Checker contract

See `SCHEMA.md`. This directory is the source of truth for rule ids used by
D1-D3, G1, C1-C3, and E1.
