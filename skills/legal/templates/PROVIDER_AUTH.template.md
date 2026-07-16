<!-- SYNTHETIC / NON-CLIENT / TEST ONLY — template; copy to <matter_dir>\03_attorney\PROVIDER_AUTH.md (outside the repo) and complete. -->

# Provider Authorization — Matter ____________

**CONFIDENTIALITY:** Attorney work product. This authorization lives in the
matter directory, outside any repository. **ATTORNEY REVIEW REQUIRED:** only
the responsible attorney may complete and sign this record.

Per firm policy (MODEL_ROUTING_POLICY_LEGAL.md) and the LIVE_MATTER_RUNBOOK,
no client/matter text may be transmitted to an external model provider
without this record completed, initialed, and dated. Written client
authorization is additionally required for non-US providers.

## 1. Matter

- Matter ID / path: `C:\Matters\____________`
- Client: ____________
- Client written authorization on file (required for DeepSeek/GLM): [ ] yes — location: ____________

## 2. Providers authorized to receive matter text (check all that apply)

| Tier | Provider / model | Data location | Authorized? | Scope limits |
|---|---|---|---|---|
| Worker | DeepSeek V4 Pro (API) | non-US | [ ] | e.g. drafting only, no medical records |
| Supervisor | GLM 5.2 (API) | non-US | [ ] | |
| Reviewer | Anthropic Opus 4.8 / Fable 5 (API) | US | [ ] | |
| Local only | (no external provider) | on-machine | [ ] | casegraph/matter-mail tooling only |

- Retention/training: provider retention of prompts acceptable? [ ] no (required answer unless client authorized otherwise)
- Prohibited content regardless of provider: [ ] SSNs/financial acct numbers [ ] unredacted medical [ ] other: ____________

## 3. Production format for this matter (matter-mail / casegraph intake note)

- [ ] Text PDFs  [ ] Scanned/image PDFs (OCR needed — casegraph flags as unreadable)  [ ] Load file (type: ______)  [ ] Native email (.pst/.eml/.msg)

## 4. Attestation

I authorize the providers checked above to receive text from this matter
subject to the scope limits stated, and I have verified client authorization
where required.

- Attorney initials: ______  Date: ____________
