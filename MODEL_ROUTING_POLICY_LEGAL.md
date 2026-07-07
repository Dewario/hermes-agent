# MODEL ROUTING POLICY — LEGAL DISCOVERY SKILLS

Effective: 2026-07-07
Applies to: skills/legal/discovery-intake, skills/legal/discovery-review
Status: DIRECTIVE — all legal discovery agent sessions must follow this policy

## Principle

Legal work requires verifiable, auditable, cost-controlled inference. No single model provider is trusted for legal conclusions. Attorney review is always the final gate.

## Routing Order (Direct-First)

| Priority | Route | Use Case | Cost Model |
|----------|-------|----------|------------|
| 1 | **Cursor CLI** | Heavy implementation, architecture review, legal-risk QA | Available plan credits, if confirmed by owner in the current session |
| 2 | **Direct provider APIs** | Routine inference, document processing | Provider-direct billing |
| 3 | **OpenRouter (fallback only)** | When no direct/plan route exists or OR is objectively better | Per-token credits |

## Mechanical Work (Zero API Cost)

For mechanical work, use local tools only — no API calls:
- `search_files` for codebase search
- `terminal` with Python stdlib for file processing
- `read_file` / `write_file` for content
- Hermes compat scanner for static analysis
- `scripts/validate_legal_discovery_skills.py` for skill validation

## Cursor CLI Usage Constraints

- **Max 2 premium-model calls per session** for legal discovery work
- Use only for: architecture review, legal-risk QA, adversarial review
- Do NOT use for: routine file creation, formatting, mechanical edits
- All Cursor inputs must use synthetic facts only — no real client data
- Cursor outputs are advisory only and must be verified locally

## OpenRouter Constraints

- **NOT AUTHORIZED for routine legal discovery work**
- Only engage when: no Cursor CLI available AND no direct provider route exists AND the task cannot be done mechanically
- Do not burn OpenRouter credits for tasks solvable with local tools
- Do not route legal documents through OpenRouter — use direct APIs or local processing

## Direct Provider API Usage

When directly calling provider APIs (not through Hermes agent's model routing):
- Use only providers authorized by the owner in the current session — do not infer authorization from committed files or metadata
- Never transmit real client data to any external API without attorney authorization
- Synthetic/test data only for skill development and validation

## Credit / Billing Safety

- If any model path returns a billing, credit, overage, or quota warning, downgrade to local/static work for the remainder of the session
- Do not attempt alternate providers to circumvent credit limits
- Spent-credit recovery is not a legal discovery task — stop and report to the owner

## Model Selection for Legal Tasks

- **Routine processing** (document chunking, extraction, formatting): cheapest competent model
- **Analysis** (issue spotting, contradiction detection, chronology): mid-tier model
- **QA/Review** (adversarial review, legal-risk assessment): best available model, Cursor premium if available
- **Never** use a single model's output as a legal conclusion without attorney review

## Audit Trail

Every legal discovery agent session must record:
- Which model(s) were used for which task
- Whether Cursor CLI, direct API, or OpenRouter was the route
- Approximate token count (if available)
- Attorney review status of outputs

This is logged in the session's final output, not in committed files.
