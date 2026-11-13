# Prospective validation plan (frozen before first call)

Date: 2026-11-13. Development v3 had 86.2% fewer client tokens but worse raw
verdict accuracy (69/72 baseline,65/72 Meko). This finding stays published.
A deterministic gate derived from development errors reads only Scout fields,
never labels or event names. Retrospective development rescoring is69/72 in
both modes; that is NOT prospective evidence. Unknown prizes remain UNSURE.

Freeze current gate and role prompts, fixed Gemini model,12 new synthetic
held-out cases,3 sequential passes per mode, fresh scoped datapack. Same gate
in both modes. Aggregate accuracy and per-pass token totals, mean and range.
Do not edit code, labels or inputs after calls begin. Report any miss. These
are sequential passes, not independent statistical replications. Gate only
validates extraction consistency, not event authenticity. No total-cost claim.

Outputs go to results/heldout-v4, separate from original development results.
The label field is consumed only by metrics, never passed in model prompts.
Success bar: Meko accuracy >= baseline and fewer client LLM tokens. If the
bar fails, report it and do not declare success by tuning this held-out set.
