# Jurisdiction packs

Machine-readable discovery **rule packs** for the counsel-pack expansion
(`COUNSEL_PACK_SPEC.md`). Skill/CLI only — not Hermes core tools.

## Load order

1. Read matter profile: `jurisdiction_pack`, optional `case_overlay`.
2. Load `packs/<jurisdiction_pack>.yaml`.
3. If overlay set, load `packs/<case_overlay>.yaml` and require
   `base_pack == jurisdiction_pack`.
4. Merge rules by `id` (overlay wins on conflict).
5. Filter by `applies_to` for the current `request_type`.

## Shipped packs

| pack_id | status | Role |
|---------|--------|------|
| `frcp_generic` | active | Default federal discovery rules (26/33/34/36/e) |
| `fela` | active | FELA/railroad theme checks on top of FRCP (`fela.yaml`) |
| `ca_ccp` | stub | California CCP placeholders — not for live |

## Checker contract

See `SCHEMA.md`. Implementation lives in future D1/G1 scripts; this directory
is the source of truth for rule ids.
