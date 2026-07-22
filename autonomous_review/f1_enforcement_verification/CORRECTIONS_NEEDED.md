# F1 Corrections Needed

Branch: `legal-enforcement-levers`
Date: 2026-07-20

Actionable corrections from the F1 independent verification pass. They were unresolved when first documented at `a4313948f`.

Status as of the F1 fix commit: F1-W1, F1-W2, and F1-CA1 are applied on this branch and ready for independent cross-check. No live matter use remains allowed without owner sec. 9.5.

## F1-W1 - WA deemed-admission refusal is wrong (HIGH, RESOLVED)

**Premise failure.** The F1 scaffolder refuses the `deemed_admitted` lever for Washington matters, and the WA motion-to-compel pack entry asserts there is no WA deemed-admission parallel. Both are false.

**Finding.** WA CR 36(a) is a self-executing no-response deemed-admission provision: "The matter is admitted unless, within 30 days after service of the request... the party... serves... a written answer or objection." CR 36(b) makes admitted matters "conclusively established... unless the court... permits withdrawal or amendment." This parallels CA CCP 2033.280 in outcome (deemed admitted on no timely response), though the mechanism differs (WA is self-executing; CA is motion-based with a mandatory grant + mandatory sanction).

**Where it manifests.**
- `skills/legal/discovery-workflow/scripts/enforcement_motion.py` `select_statute()` for `deemed_admitted`: returns refusal "deemed_admitted lever requires Cal. Code Civ. Proc. sec. 2033.280 (CA); Washington has no no-response deemed-admission parallel" when `CCP-2033-280` is absent. This incorrectly denies WA plaintiffs a valid enforcement lever.
- `skills/legal/discovery-workflow/jurisdiction/packs/wa_state.yaml` `WA-CR-37-A` summary: closing sentence "no separate no-response deemed-admission statute parallels CCP 2033.280 in Washington" is false and is rendered into WA motion_to_compel scaffolds.

**Fix applied.**
1. `wa_state.yaml` carries `WA-CR-36-A` and `WA-CR-36-B` with source URLs to the CR 36 PDF.
2. `select_statute()` accepts WA when `WA-CR-36-A` is available, returning `WA-CR-36-A` as primary with `WA-CR-36-B` supporting when present.
3. Remove the "no deemed-admission parallel" sentence from the `WA-CR-37-A` summary; rephrase to note the CR 36(a) self-executing deemed-admission as the RFA-no-response lever and CR 37(a) as the further-response lever.
4. Add tests: WA `deemed_admitted` drafts successfully citing CR 36(a); WA `deemed_admitted` refusal no longer fires for a WA pack; the corrected `WA-CR-37-A` summary no longer contains the false sentence.

**Severity rationale.** The refusal is a false negative (tool produces no scaffold rather than a wrong one), which is the lesser harm. But the `WA-CR-37-A` summary's false "no parallel" statement is affirmative misleading text rendered into WA scaffolds - that is the higher harm. Both must be corrected before merge or any live reliance.

## F1-W2 - WA CR 37(c) citation mismatch (MEDIUM, RESOLVED)

**Finding.** The pack's `WA-CR-37-C` entry is labeled CR 37(c) but its summary tracks CR 37(a)(4) language (expenses + attorney fees + substantial-justification exception on a motion to compel). CR 37(c) is actually the narrower "Expenses on Failure To Admit" provision (CR 36) with a different exception structure ("unless the court finds that (1) the request was held objectionable, (2) the admission sought was of no substantial importance, or (3) the party failing to admit had reasonable ground to believe..."). The `sanctions_block` prose also cites "(CR 37(c))" for the MTC-expenses language.

**Fix applied.** Relabeled the general motion-expense sanctions rule to `WA-CR-37-A-4`, rewrote the summary to track CR 37(a)(4), changed `select_statute()` and `sanctions_block()` to use CR 37(a)(4), and added regression coverage for the generated WA sanctions scaffold.

**Severity rationale.** MEDIUM because the scaffold is a draft for attorney review and the attorney checklist flags statute verification, but a miscited rule number could propagate into a filed motion if uncaught.

## F1-CA1 - CA sanctions prose "up to $1,000" hedge (LOW, RESOLVED)

**Finding.** `sanctions_block` renders "A monetary sanction up to $1,000 may be imposed absent a showing of substantial justification or other circumstances making an award unjust (section 2023.050)." The statute (2023.050(a)) says "the court shall impose a one-thousand-dollar ($1,000) sanction" - mandatory, subject to the substantial-justification exception. The "up to... may be imposed" framing is a slight hedge.

**Fix applied.** Rephrased `sanctions_block()` and the reference template to state that section 2023.050 requires a $1,000 monetary sanction when statutory findings are made, subject to written findings of substantial justification or other circumstances making the sanction unjust. The attorney-controlled amount/strategy note remains.

**Severity rationale.** LOW because the scaffold is explicitly a draft for attorney review and the figure ($1,000) and the exception (substantial justification) are both correct; only the modal framing ("up to/may" vs "shall") is imprecise.

## Merge ordering

1. F1-W1 fixed before merge or any live reliance.
2. F1-W2 fixed with F1-W1 to avoid miscited WA sanctions authority.
3. F1-CA1 fixed with the same patch.

After fixes: re-run the F1 selftest, the enforcement_motion test file, and the full legal suite; re-run `git diff --check`; re-verify the corrected WA CR 36(a) and CR 37(a)(4) entries against the courts.wa.gov PDFs.
