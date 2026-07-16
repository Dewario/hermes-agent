<!-- SYNTHETIC / NON-CLIENT / TEST ONLY -->

Golden expected-output packages live here after attorney-approved synthetic
pilot runs (LGD2-008).

## How goldens are created

1. Run `pilot/run_pilot.ps1` (intake phase).
2. Attorney reviews `pilot_outputs/intake/intake_package.md`.
3. Record sign-off in `pilot_outputs/approval.json`.
4. Run `pilot/promote_goldens.ps1` — copies approved output to
   `examples/<pilot_id>/`.

## Rules

- Synthetic data only — no real client matter content.
- Every golden must have a sibling `approval.json` copy from the pilot.
- Regress with:
  `python pilot/check_outputs.py --phase intake --dir examples/<pilot_id>`
