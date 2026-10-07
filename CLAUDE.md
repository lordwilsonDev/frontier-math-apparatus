# Frontier Math Apparatus — session handoff

You are picking up a research apparatus owned by Wilson (Black Swan Labs). Read this file, then
`README.md` and `docs/PROTOCOL.md`. Design rules 1–10 in the README are binding.

## What exists (v0.2, 2026-10-07)

A working, tested governance core. It does not solve mathematics; it controls and records the
process around a solver.

| Piece | File | What it enforces |
|---|---|---|
| Run state machine, phases A–K | `src/fma/engine.py` | Order of phases; no re-solve without a delta and an intervention |
| Hash-chained ledger | `src/fma/ledger.py` | Every transition recorded; edits to `run.json` or the ledger are detectable |
| Reference quarantine | `src/fma/vault.py` | Only a SHA-256 commitment enters the run until Phase G; real problems are refused unless the vault is outside this directory |
| Comparators | `src/fma/compare.py`, `src/fma/adapters/` | Non-identical text is `UNRESOLVED`; `integer` and `sympy` adapters decide what they can prove |
| Transfer with a control arm | `engine.transfer` | A lesson only counts as transferred when the treatment run solves the unseen problem and the control run does not |
| Stage ablation | `init --skip` | Runs can leave out question, audit, ail, moie; metrics report first-pass accuracy per condition |
| Solver environment | `engine.attempt` | Model, knowledge cutoff, web access, code execution are required; contamination risk is flagged |
| Calibration bank | `src/fma/calibration.py` | Seeded problems with brute-force answers written to the vault only |
| Program research log | `bin/fma log` | Append-only, hash-chained record of mistakes, failures, deviations and decisions outside runs |
| Preflight | `bin/fma preflight` | End-to-end self-test plus readiness checks; exits non-zero if not ready |
| Metrics | `src/fma/metrics.py` | Primary, per-condition, per-family, diagnostic, governance |
| Slash command | `.claude/commands/fma-run.md` | `/fma-run <problem.json> [run-id] [skip...]` drives one full run |

Facts the engine decides itself (callers cannot assert them): whether an attempt was
reference-blind, whether a verification was independent, whether a comparison was self-certified,
whether an attempt carried the lesson, and the outcome of a transfer test. `VERIFIED` is refused
unless the final attempt has an independent PASS and a match that was not self-certified.

```
bin/fma preflight             # must print READY before any batch
python3 -m pytest -q          # 18 tests (needs pytest; preflight covers the core loop without it)
bin/fma status --run <id>     # phase and next allowed action
bin/fma check --run <id>      # ledger + run.json integrity
bin/fma metrics
```

No third-party packages are required. `sympy` is optional, `pytest` is for the test suite.

## Start here

The calibration set (30 problems, seed 20261007) is in `calibration/problems/`, with a 20-problem
transfer holdout (seed 20261008) in `calibration-holdout/problems/`; its answers are in
the vault at `../.fma-vault`, which `bin/fma` picks up automatically. **Never read the vault.**

1. `bin/fma preflight`. Do not start until it prints READY.
2. Read `docs/TEST_PLAN.md`. It is fixed in advance; follow it as written.
3. Ask Wilson which model is the solver for Pilot 0, then run Batch 1: one `/fma-run` per
   calibration problem. Commit `runs/` when the batch is done.
4. Show Wilson `bin/fma metrics`. Continue to Batch 2 and 3 only if Batch 1 met the failure
   count the plan requires.
5. The external corpus comes after Pilot 0. The docs name "OpenAI/math"; the build session could
   not reach `github.com/openai/math` (blocked, not confirmed missing), and a web search suggesting
   OpenAI published ten results with Lean proofs in 2026 was not verified. Confirm the source with
   Wilson before ingesting anything.

## Roles for a run

Use separate agents with separate actor names; the governance metrics depend on it.

- `solver` — blind. No vault access, no web search, no reference corpus. Give it only the problem
  statement and the plan.
- `verifier` — did not produce the attempt. Checks it before the reference is released.
- `judge` — runs `compare`, adjudicates equivalence with a stated basis.
- `analyst` — delta and intervention.

Actor names are self-declared strings. The ledger records who claimed to act, not who did.

## Known gaps (be honest about these in any write-up)

1. **Blindness is still procedural.** The vault sits outside the repo and the engine refuses an
   in-repo vault for real problems, but any process on this machine can read it. Solver agents
   must be told not to, and that instruction is the only barrier.
2. **Roles and environment are self-declared.** The ledger records the actor names and the
   solver environment it was given. It cannot verify them.
3. **AIL, MoIE, FCVE are recorded, not implemented.** The engine requires their outputs; the
   reasoning comes from whoever fills them in. Batch 2 of the test plan measures whether they help.
4. **Comparison is result-string based.** Right for the calibration bank. Wrong shape for
   theorem-and-proof references; that needs statement equivalence and a proof checker adapter.
5. **One transfer pair is one data point.** The control arm removes the worst confound; it does
   not make a single pair significant.
6. **The ledger is not externally anchored.** Committing `runs/` after each batch is the anchor.
7. Four metrics in `docs/METRICS.md` are not computed; `metrics` lists them under `not_implemented`.
8. `LICENSE` (MIT) and `CITATION.cff` were filled in from Wilson's stated defaults; he should confirm.

## Everything is recorded

This is a research program. Failures, mistakes, deviations and dead ends are data, and they are
recorded with the same care as results. Wilson's standing rule: everything is recorded.

- Inside a run, the ledger does it. Record the attempt you got, not the one you wanted.
- Outside a run, use the program log: `bin/fma log --kind <kind> --text "..." --actor <you>`.
  Kinds: `mistake`, `failure`, `deviation`, `decision`, `correction`, `observation`.
  Log it when it happens, not at the end. `bin/fma log` with no arguments shows the log.
- Log at least: every bug found in the apparatus, every departure from `docs/TEST_PLAN.md`, every
  run abandoned and why, every instruction you interpreted rather than confirmed, every tool or
  environment failure, and anything you could not verify.
- The log is append-only and hash-chained (`log/program.jsonl`). Never edit or delete an entry.
  A wrong entry is corrected by a new `correction` entry that names it.
- A fix does not erase the mistake. Log the mistake, then the correction.
- Commit `log/` with every commit.

## Conventions

- Runs are append-only. Never edit `runs/*/run.json` or `ledger.jsonl` by hand, never reuse a run id.
- A wrong first attempt is data. Do not rerun a blind attempt to get a better number.
- Commit `runs/` after every completed run.
- Fixture references sit in the open under `fixtures/references/`; fixtures test plumbing only.
- To add calibration problems: `bin/fma calibrate --n <N> --seed <new int>`. Wilson runs this, not a solving session.
