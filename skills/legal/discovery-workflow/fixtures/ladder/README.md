<!-- SYNTHETIC / NON-CLIENT / TEST ONLY -->

# Synthetic preparation ladder

Graduated offline matters used to pressure-test the counsel pack **without**
touching any live client directory.

| Level | Matter ID | Purpose |
|-------|-----------|---------|
| **L1** | `SYN-SMOKE-COUNSEL` | Baseline — full counsel-pack smoke (`fixtures/smoke_matter/seed/`) |
| **L2** | `SYN-LADDER-STRESS` | Stress — denser served sets, `ca_ccp` pack, C\* briefs, OCR-cleared TEMP rehearsal |
| **L3** | `SYN-LADDER-ISO-A` / `SYN-LADDER-ISO-B` | Isolation — two matters; packages must not cross-bleed Bates prefixes |

Run (TEMP only; never Allen / never real clients):

```powershell
$prep = "$env:LOCALAPPDATA\hermes\hermes-agent\skills\legal\discovery-workflow\scripts\prepare_synthetic_ladder.py"
python $prep
# or:
python discovery_workflow.py prepare
```

Hard rules:

- Every matter carries `.synthetic` and a `SYN-*` matter ID.
- Default output is under `%TEMP%`; `--keep` preserves it for inspection.
- Refuse paths / IDs that look like live client matters.
- Do **not** copy ladder outputs into a real matter folder.
