# F1 Corrections Needed

Branch: `legal-enforcement-levers` (HEAD `185c5b73a`)
Date: 2026-07-20

Actionable corrections from the F1 independent verification pass. These are documented for coordinated merge; they are NOT yet applied on this branch. No live matter use until F1-W1 is resolved.

## F1-W1 - WA deemed-admission refusal is wrong (HIGH, merge-time required)

**Premise failure.** The F1 scaffolder refuses the `deemed_admitted` lever for Washington matters, and the WA motion-to-compel pack entry asserts there is no WA deemed-admission parallel. Both are false.

**Finding.** WA CR 36(a) is a self-executing no-response deemed-admission provision: "The matter is admitted unless, within 30 days after service of the request... the party... serves... a written answer or objection." CR 36(b) makes admitted matters "conclusively established... unless the court... permits withdrawal or amendment." This parallels CA CCP 2033.280 in outcome (deemed admitted on no timely response), though the mechanism differs (WA is self-executing; CA is motion-based with a mandatory grant + mandatory sanction).

**Where it manifests.**
- `skills/legal/discovery-workflow/scripts/enforcement_motion.py` `select_statute()` for `deemed_admitted`: returns refusal "deemed_admitted lever requires Cal. Code Civ. Proc. sec. 2033.280 (CA); Washington has no no-response deemed-admission parallel" when `CCP-2033-280` is absent. This incorrectly denies WA plaintiffs a valid enforcement lever.
- `skills/legal/discovery-workflow/jurisdiction/packs/wa_state.yaml` `WA-CR-37-A` summary: closing sentence "no separate no-response deemed-admission statute parallels CCP 2033.280 in Washington" is false and is rendered into WA motion_to_compel scaffolds.

**Fix (merge-time).**
1. Add a `WA-CR-36-A` rule entry to `wa_state.yaml` with citation "Wash. Super. Ct. Civ. R. 36(a)", source_url the CR 36 PDF, and a summary tracking the self-executing deemed-admission text plus CR 36(b) conclusive establishment and the CR 37(a)(4) expenses path for a sufficiency motion.
2. Update `select_statute()` for `deemed_admitted` to accept WA when `WA-CR-36-A` is available, returning `WA-CR-36-A` as primary (no supporting, no refusal).
3. Remove the "no deemed-admission parallel" sentence from the `WA-CR-37-A` summary; rephrase to note the CR 36(a) self-executing deemed-admission as the RFA-no-response lever and CR 37(a) as the further-response lever.
4. Add tests: WA `deemed_admitted` drafts successfully citing CR 36(a); WA `deemed_admitted` refusal no longer fires for a WA pack; the corrected `WA-CR-37-A` summary no longer contains the false sentence.

**Severity rationale.** The refusal is a false negative (tool produces no scaffold rather than a wrong one), which is the lesser harm. But the `WA-CR-37-A` summary's false "no parallel" statement is affirmative misleading text rendered into WA scaffolds - that is the higher harm. Both must be corrected before merge or any live reliance.

## F1-W2 - WA CR 37(c) citation mismatch (MEDIUM, merge-time recommended)

**Finding.** The pack's `WA-CR-37-C` entry is labeled CR 37(c) but its summary tracks CR 37(a)(4) language (expenses + attorney fees + substantial-justification exception on a motion to compel). CR 37(c) is actually the narrower "Expenses on Failure To Admit" provision (CR 36) with a different exception structure ("unless the court finds that (1) the request was held objectionable, (2) the admission sought was of no substantial importance, or (3) the party failing to admit had reasonable ground to believe..."). The `sanctions_block` prose also cites "(CR 37(c))" for the MTC-expenses language.

**Fix (merge-time).** Either (a) relabel the rule to `WA-CR-37-A-4` (CR 37(a)(4)) for the general MTC-expenses lever and rewrite the summary to track 37(a)(4), or (b) split into two entries (`WA-CR-37-A-4` for MTC expenses; `WA-CR-37-C` for failure-to-admit expenses of proof) and have `select_statute()` for `sanctions` pick `WA-CR-37-A-4` as primary. Update the `sanctions_block` WA citation accordingly. Add a test asserting the WA sanctions scaffold cites the correct rule for the MTC-expenses posture.

**Severity rationale.** MEDIUM because the scaffold is a draft for attorney review and the attorney checklist flags statute verification, but a miscited rule number could propagate into a filed motion if uncaught.

## F1-CA1 - CA sanctions prose "up to $1,000" hedge (LOW, refinement)

**Finding.** `sanctions_block` renders "A monetary sanction up to $1,000 may be imposed absent a showing of substantial justification or other circumstances making an award unjust (section 2023.050)." The statute (2023.050(a)) says "the court shall impose a one-thousand-dollar ($1,000) sanction" - mandatory, subject to the substantial-justification exception. The "up to... may be imposed" framing is a slight hedge.

**Fix (optional).** Rephrase to "A $1,000 sanction applies (mandatory, subject to the substantial-justification exception)..." or "The court shall impose a $1,000 sanction absent substantial justification or circumstances making the award unjust...". Keep the attorney-controlled amount/strategy note.

**Severity rationale.** LOW because the scaffold is explicitly a draft for attorney review and the figure ($1,000) and the exception (substantial justification) are both correct; only the modal framing ("up to/may" vs "shall") is imprecise.

## Merge ordering

1. F1-W1 (required) - fix before merge or any live reliance.
2. F1-W2 (recommended) - fix at merge to avoid miscited rule in filed motions.
3. F1-CA1 (optional) - refinement; can land with or after merge.

After fixes: re-run the F1 selftest, the enforcement_motion test file, and the full legal suite; re-run `git diff --check`; re-verify the corrected WA CR 36(a) and CR 37(a)(4)/(c) entries against the courts.wa.gov PDFs.
