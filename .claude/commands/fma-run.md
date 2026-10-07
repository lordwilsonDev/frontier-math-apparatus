---
description: Drive one Frontier Math Apparatus run through phases A–K
argument-hint: <problem.json> <reference.json> [run-id]
---

Run the full research protocol (`docs/PROTOCOL.md`) for the problem in `$1` with the quarantined
reference in `$2`. Run id: `$3`, or derive one from the problem id plus today's date.

You are the orchestrator. You must not open `$2`, the vault, or any reference corpus yourself.
Pass the reference path to `bin/fma init` without reading it.

Write each phase's JSON to `runs/<run-id>/inputs/` and pass it with `--data`. After every command,
`bin/fma status --run <run-id>` tells you the next allowed action. A `REFUSED` message means the
protocol was violated; fix the cause, do not work around it.

1. **A** `bin/fma init --run <id> --problem $1 --reference $2 --actor intake`
2. **B** Write the canonical question (all fields in `schemas/question.schema.json`). `question`, actor `framer`.
3. **C** Record ambiguities, losses, transformations, inventions, assumptions. `audit`, actor `framer`.
4. **D** Invert the load-bearing assumptions (AIL). Produce at least two genuinely different
   strategies (MoIE), each with a discriminating test. Select one; keep the dissent verbatim. `plan`, actor `planner`.
5. **E** Spawn a subagent as `solver`. Give it only the problem statement, canonical question and
   selected plan. Tell it: no web search, no reading `vault/`, `fixtures/references/`, or `$2`.
   It returns derivation, intermediate claims, tools, failures, candidate result. Record model
   name, knowledge cutoff and tool access under `environment`. `attempt`, actor `solver`.
   Record whatever it returns, including a failure. Do not rerun for a better answer.
6. **F** Spawn a different subagent as `verifier` with the attempt but not the reference. It
   recomputes, attacks the weakest step, checks the answer against the success conditions.
   `verify`, actor `verifier`.
7. **G** `bin/fma compare --run <id> --actor judge` (add `--adapter sympy` for closed forms).
   If the result is `UNRESOLVED` and the two results are in fact equivalent or in fact different,
   adjudicate with `--classification ... --basis "..."`; the basis must be checkable.
8. If the comparison is a match, go to step 11.
9. **H, I** Localise the divergence to one locus. Change one control variable. `delta`, then
   `intervene`, actor `analyst`.
10. **E–G again** Re-solve with the intervention applied, verify, compare. Repeat 9–10 at most
    three cycles; after that deliver as `UNRESOLVED`.
11. **J** If an intervention was recorded: pick an unseen problem with the same hypothesised
    failure structure, run it as its own run with `init --parent <id>`, applying the lesson, through
    step 7. Then `bin/fma transfer --run <id> --child <child-id> --actor judge`. If no suitable
    unseen problem exists, skip this; the lesson is then recorded as `UNTESTED`.
12. **K** `deliver` with the epistemic status the evidence supports and the reusable lesson.
    Then `bin/fma check --run <id>` and commit `runs/`.

Report to the user: the first-pass classification, the failure locus if any, the intervention,
the transfer result, the final epistemic status, and the path to `deliverable.md`.
