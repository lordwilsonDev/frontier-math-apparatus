# Frontier Math Apparatus (FMA)

A reproducible laboratory for blind mathematical problem solving, reference comparison, failure localization, controlled intervention, and transfer testing.

## Core question

Can a governed research apparatus independently reconstruct mathematical results, measure where reasoning diverges from a reference corpus, intervene on the failure, and determine whether the correction transfers to unseen problems?

## Pipeline

`Problem → Question Engineering → Linguistic Normalization → Communication Audit → AIL → MoIE → Research Plan → Blind Solve → Internal Verification → Reference Comparison → Delta Analysis → Intervention → Re-solve → Transfer → Deliverable`

## Design rules

1. The first solve is reference-blind.
2. OpenAI/math is a reference terrain, not the architecture.
3. A reference match is evidence of agreement, not proof of the solver's process.
4. Different-looking answers are not automatically mismatches; semantic equivalence must be considered.
5. Disagreement is preserved; MoIE is not majority voting.
6. Every material transition is recorded as provenance.
7. Corrections should be controlled interventions, not arbitrary prompt churn.
8. A lesson is not accepted as transferable until tested on unseen terrain.
9. The apparatus cannot be its own final authority.
10. Every run ends in a durable research deliverable.

## Status (v0.1)

The governance core is implemented and tested: phase state machine, hash-chained ledger,
reference quarantine, comparator, metrics, CLI. Mathematical execution, reference ingestion,
and FCVE verification are adapters and are not implemented yet. See `CLAUDE.md` for the
current state, known gaps, and the next steps.

## Quick start

```
python3 -m pytest -q
bin/fma init --run demo --problem fixtures/problems/F-0001.json \
             --reference fixtures/references/F-0001.json --actor intake
bin/fma status --run demo      # prints the next allowed action
```

One command per phase: `init question audit plan attempt verify compare delta intervene
transfer deliver`, plus `status check runs metrics`. In Claude Code, `/fma-run` drives a whole run.
