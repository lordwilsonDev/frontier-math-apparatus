# Frontier Math Apparatus — session handoff

You are picking up a research apparatus owned by Wilson (Black Swan Labs). Read this file, then
`README.md` and `docs/PROTOCOL.md`. Design rules 1–10 in the README are binding.

## What exists (v0.1, built 2026-10-07)

A working, tested governance core. It does not solve mathematics; it controls and records the
process around a solver.

| Piece | File | What it enforces |
|---|---|---|
| Run state machine, phases A–K | `src/fma/engine.py` | Order of phases; no re-solve without a delta and an intervention |
| Hash-chained ledger | `src/fma/ledger.py` | Every transition recorded; edits to `run.json` or the ledger are detectable |
| Reference quarantine | `src/fma/vault.py` | Only a SHA-256 commitment enters the run until Phase G |
| Comparator + sympy adapter | `src/fma/compare.py`, `src/fma/adapters/` | Non-identical text is `UNRESOLVED`, never auto-`MISMATCH` |
| Metrics | `src/fma/metrics.py` | Primary, diagnostic, governance numbers from recorded runs |
| CLI | `bin/fma` | One command per phase |
| Slash command | `.claude/commands/fma-run.md` | `/fma-run <problem.json> <reference.json>` drives one full run |

Facts the engine decides itself (callers cannot assert them): whether an attempt was
reference-blind, whether a verification was independent, whether a comparison was self-certified,
and the outcome of a transfer test. `VERIFIED` is refused unless the final attempt has an
independent PASS and a match that was not self-certified.

```
python3 -m pytest -q          # 10 tests, all on fixtures
bin/fma -h
bin/fma status --run <id>     # shows phase and the next allowed action
bin/fma check --run <id>      # ledger + run.json integrity
bin/fma metrics
```

No third-party packages are required. `sympy` is optional (equivalence adapter), `pytest` for tests.

## Start here: Pilot 0

Do these in order. Stop and ask Wilson where marked.

1. Run the tests. If they are not green, fix that first.
2. **Confirm the reference terrain.** The docs name "OpenAI/math". The build session could not
   reach `github.com/openai/math` from its sandbox (blocked, not confirmed missing). A web search
   suggested OpenAI published ten mathematical results with Lean proofs in 2026; that was not
   verified. Find the actual source, its licence, and how results are organised. **Ask Wilson** to
   confirm it is the corpus he means before ingesting anything.
3. Write `adapters/openai_math/ingest.py` to the contract in `adapters/openai_math/README.md`.
   It must emit problem files and reference files separately, with references going straight to
   the vault.
4. **Ask Wilson** where the vault lives. Set `FMA_VAULT` to a directory outside this repository
   that the solving agent is not given. The in-repo default is for fixtures only.
5. Calibration batch: 5–10 problems Wilson picks at L1–L2, each via `/fma-run`. Purpose is to
   exercise the protocol and get first metrics, not to claim results.
6. Review `bin/fma metrics` with Wilson, then fix the highest-value gap below before scaling up.

## Roles for a run

Use separate agents with separate actor names; the governance metrics depend on it.

- `solver` — blind. No vault access, no web search, no reference corpus. Give it only the problem
  statement and the plan.
- `verifier` — did not produce the attempt. Checks it before the reference is released.
- `judge` — runs `compare`, adjudicates equivalence with a stated basis.
- `analyst` — delta and intervention.

Actor names are self-declared strings. The ledger records who claimed to act, not who did.

## Known gaps (be honest about these in any write-up)

1. **Blindness is procedural.** Anything that can read the vault directory can read the reference.
   Also, a public corpus may be in a model's training data or reachable by search. Record the
   solver model, its knowledge cutoff, and tool access in `attempt.environment`.
2. **Transfer has no control arm.** A child run matching on first attempt is scored `TRANSFERRED`
   even if the solver would have solved it without the lesson. Needed: solve the unseen problem
   with and without the lesson and compare. Until then, transfer rate is an upper bound.
3. **AIL, MoIE, FCVE are recorded, not implemented.** The engine requires their outputs (inverted
   assumptions, at least two hypotheses with dissent kept, verification checks) but the reasoning
   comes from whoever fills them in. Wilson's own implementations should plug in here.
4. **Comparison is result-string based.** Fine for closed-form answers. For theorem-and-proof
   references it is the wrong shape; that needs a proof-level comparison design (statement
   equivalence, proof-strategy delta, Lean check as an FCVE adapter).
5. **The ledger is not externally anchored.** Commit after each run, or record the head hash
   somewhere the apparatus cannot write, to satisfy rule 9.
6. Four metrics in `docs/METRICS.md` are not computed yet; `metrics` lists them under
   `not_implemented`.
7. `LICENSE` (MIT) and `CITATION.cff` were filled in from Wilson's stated defaults; he should
   confirm the wording.

## Conventions

- Runs are append-only. Never edit `runs/*/run.json` or `ledger.jsonl` by hand, never reuse a run id.
- A wrong first attempt is data. Do not rerun a blind attempt to get a better number.
- Commit `runs/` after every completed run.
- Fixture references sit in the open under `fixtures/references/`; fixtures test plumbing only.
