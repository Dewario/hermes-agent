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

### Per-matter client authorization (real matters, external providers)

The worker/supervisor tiers route through external, non-US-hosted providers
(DeepSeek, Zhipu/GLM). For any **real** matter whose documents will transit
those APIs, obtain **written, per-matter client authorization before the first
run**. The authorization must:
- name the specific external providers used;
- state that attorney work product (and potentially privileged material) will
  transit those providers' APIs;
- record the data-handling posture relied on (retention, no-training if
  offered);
- be referenced in the matter's `03_attorney/` record.

Absent that authorization, real-matter work stays on a confidentiality-cleared
route (synthetic/pilot work is unaffected). This is a legal/ethical
determination for the confirming attorney, not a technical toggle.

## Credit / Billing Safety

- If any model path returns a billing, credit, overage, or quota warning, downgrade to local/static work for the remainder of the session
- Do not attempt alternate providers to circumvent credit limits
- Spent-credit recovery is not a legal discovery task — stop and report to the owner
- **Bound the reviewer tier.** Moving bulk drafting to the worker tier keeps most
  spend off the reviewer provider, but the reviewer tier still incurs cost —
  set a per-session spend/turn cap on it, and run non-interactive reviews
  through the provider's batch endpoint where one exists to roughly halve that
  cost.

## Model Selection for Legal Tasks

Legal discovery work is routed across three **tiers**. Tiers are the durable
contract; the concrete models below are a **reference mapping** that may be
swapped as models change. The session audit trail records which model filled
each tier for a given run (see Audit Trail).

| Tier | Role | Reference model | Rationale |
|------|------|-----------------|-----------|
| **Worker** | Bulk drafting — intake package, review package, issue matrices, chronologies, extraction, formatting (the token-heavy generation) | DeepSeek V4 Pro (or cheapest competent model) | Highest token volume lives here; run it on the lowest-cost competent tier |
| **Supervisor** | Consistency and gate pre-checks — self-review against the skill's required sections, contradiction/omission sweep, fixture-grounding check before the attorney sees it | GLM 5.2 (or a mid-tier model) | Cross-checks the worker's output at a fraction of reviewer cost |
| **Reviewer** | High-level QA — citation/issue review, adversarial pass, legal-risk framing. **Escalation-only**: sampled sections plus anything flagged UNVERIFIED or high-risk | Opus 4.8 (Fable 5 for hardest-matter escalation only) | Strongest model where legal accuracy is won; kept off the hot path to bound cost |

- **Reviewer is escalation-only.** Reviewing every section on the reviewer tier
  erases the cost separation — sample plus flag-driven review only.
- **Prefer Opus 4.8 over Fable 5 for routine review** (roughly half the per-token
  cost); reserve Fable 5 for genuinely hardest-matter escalation.
- **Never** use any single model's output — worker, supervisor, or reviewer — as
  a legal conclusion without attorney review. The tiers reduce cost and add
  cross-checks; they do not replace the confirming attorney.

## Prompt-Cache Structuring (cost control)

All three reference providers price reused context far below fresh input. Build
each per-matter prompt with a **stable prefix** (skill text, then the matter's
fixtures / production set) and put the **varying instruction last**, so the
resent-context portion of every agentic turn is served from cache. This
compounds with the tiering to cut real-matter cost further.

## Audit Trail

Every legal discovery agent session must record:
- Which model(s) were used for which task
- Whether Cursor CLI, direct API, or OpenRouter was the route
- Approximate token count (if available)
- Attorney review status of outputs

This is logged in the session's final output, not in committed files.
