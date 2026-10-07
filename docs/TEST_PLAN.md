# Test Plan — Pilot 0

Written before any run, so the results cannot shape the questions.

## Fixed conditions

- Problems: `calibration/problems/` (30 problems, 5 families, seed 20261007). Answers are single
  integers computed by brute force and sealed in the vault.
- Holdout: `calibration-holdout/problems/` is reserved for transfer tests in Batch 3. Do not run
  it in Batches 1–2.
- Solver: one model, fresh context per run, `web_access: false`, `code_execution: false`.
  These problems are trivial with code; without it they test reasoning and arithmetic.
- Comparison: `bin/fma compare --adapter integer`. Exact text match, else equal/different integers.
  Anything that is not a bare integer stays `UNRESOLVED` and is adjudicated by `judge` with a basis.
- One blind attempt per run. No reruns for a better number.

## Batch 1 — where does it fail? (30 runs)

Every problem once, full pipeline (no `--skip`).
Reads: first-pass accuracy overall and by family (`bin/fma metrics`).
Needed for the later batches: at least 8 first-pass failures. If there are fewer, the bank is too
easy for this solver. Generate a harder set before going on; do not continue on a handful of failures.

## Batch 2 — do the pre-solve stages earn their place? (30 runs)

Same 30 problems, fresh solver context, `--skip question --skip audit --skip ail --skip moie`.
Reads: `first_pass_by_condition`, paired per problem: solved only with the stages, only without,
both, neither.
Honest limit: with 30 pairs only a large effect is distinguishable from noise. Report the four
counts, not a verdict. If the discordant pairs split close to evenly, the stages have not shown
an effect yet.

## Batch 3 — correction and transfer (every Batch 1 failure)

For each failed run: `delta` (one locus), `intervene` (one controlled variable), re-solve.
Then one transfer pair per lesson, on a same-family problem from the holdout set
(`calibration-holdout/problems/`, 20 problems, seed 20261008, never used in Batches 1–2):
`init --parent <run> --arm treatment` (solver is given the lesson) and
`init --parent <run> --arm control` (solver is not), then `bin/fma transfer`.
Reads: correction gain, attempts-to-correction, `transfer_results`.
`TRANSFERRED` is only scored when treatment solves it and control does not.

## What counts as a result

- Report counts with denominators. No percentages on fewer than 20 runs.
- Every governance metric must be clean: reference-blind compliance 1.0, provenance
  completeness 1.0, zero attempts with contamination risk, self-certification rate 0.
  A batch that fails one of these is rerun on new problems, not patched.
- Run `bin/fma check` on each run and commit `runs/` after each batch.
- Every departure from this plan, abandoned run, tool failure or apparatus bug goes in the program
  log (`bin/fma log`) when it happens. Changing this plan after Batch 1 starts is a `deviation`
  entry with the reason; the old text stays in git history.

## After Pilot 0

Only then move to an external reference corpus (see `adapters/openai_math/README.md`), which
needs proof-level comparison that this version does not have.
