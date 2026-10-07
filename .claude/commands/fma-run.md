---
description: Drive one Frontier Math Apparatus run through phases A–K
argument-hint: <problem.json> [run-id] [skip stages...]
---

Run the research protocol (`docs/PROTOCOL.md`) for the problem in `$1`. Run id: `$2`, or derive
one from the problem id. Any further arguments name stages to skip (question, audit, ail, moie).

You are the orchestrator. You must not read the vault (`$FMA_VAULT`, `../.fma-vault`), any
reference file, or any reference corpus, and you must not compute the answer yourself.

The reference: for calibration problems it is already sealed in the vault under the problem id;
pass `--reference` the vault file path **without opening it** (`init` verifies and re-seals the
identical content). For other problems the user supplies the path.

Write each phase's JSON to `runs/<run-id>/inputs/` and pass it with `--data`. After every command,
`bin/fma status --run <run-id>` tells you the next allowed action. A `REFUSED` message means the
protocol was violated; fix the cause, do not work around it.

1. **A** `bin/fma init --run <id> --problem $1 --reference <path> --actor intake` plus one
   `--skip <stage>` per skipped stage. Skipped stages are left out below; `status` shows what is next.
2. **B** Write the canonical question (all fields in `schemas/question.schema.json`). `question`, actor `framer`.
3. **C** Record ambiguities, losses, transformations, inventions, assumptions. `audit`, actor `framer`.
4. **D** Invert the load-bearing assumptions (AIL). Produce at least two genuinely different
   strategies (MoIE), each with a discriminating test. Select one; keep the dissent verbatim. `plan`, actor `planner`.
5. **E** Spawn a subagent as `solver`. Give it only the problem statement, canonical question and
   selected plan. Tell it: no web search, no code execution unless the test plan allows it, no reading
   the vault or any reference. It returns derivation, intermediate claims, tools, failures and a
   candidate result in the format the problem asks for. `environment` is required:
   `{"model", "knowledge_cutoff" (YYYY-MM), "web_access", "code_execution"}`, stated truthfully. `attempt`, actor `solver`.
   Record whatever it returns, including a failure. Do not rerun for a better answer.
6. **F** Spawn a different subagent as `verifier` with the attempt but not the reference. It
   recomputes, attacks the weakest step, checks the answer against the success conditions.
   `verify`, actor `verifier`.
7. **G** `bin/fma compare --run <id> --actor judge` (add `--adapter integer` for integer answers, `--adapter sympy` for closed forms).
   If the result is `UNRESOLVED` and the two results are in fact equivalent or in fact different,
   adjudicate with `--classification ... --basis "..."`; the basis must be checkable.
8. If the comparison is a match, go to step 11.
9. **H, I** Localise the divergence to one locus. Change one control variable. `delta`, then
   `intervene`, actor `analyst`.
10. **E–G again** Re-solve with the intervention applied, verify, compare. Repeat 9–10 at most
    three cycles; after that deliver as `UNRESOLVED`.
11. **J** If an intervention was recorded: pick an unused same-family problem (for calibration: from `calibration-holdout/problems/`) and run
    it twice as separate runs, both through step 7 with fresh solver agents:
    `init --parent <id> --arm treatment` (the solver is given the lesson) and
    `init --parent <id> --arm control` (the solver is not). Then
    `bin/fma transfer --run <id> --treatment <t-id> --control <c-id> --actor judge`.
    If no unused same-family problem exists, skip this; the lesson is recorded as `UNTESTED`.
12. **K** `deliver` with the epistemic status the evidence supports and the reusable lesson.
    Then `bin/fma check --run <id>` and commit `runs/`.

Report to the user: the first-pass classification, the failure locus if any, the intervention,
the transfer result, the final epistemic status, and the path to `deliverable.md`.
