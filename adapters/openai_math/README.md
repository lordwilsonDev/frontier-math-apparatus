# OpenAI/math reference adapter (not yet implemented)

Status: contract only. The source corpus has not been confirmed; see `CLAUDE.md`, Pilot 0 step 2.

## Contract

`ingest.py <source-dir> --problems <dir> --vault <dir>` should write, per result:

- `<problems>/<problem_id>.json` — `problem_id`, `statement`, `source` (URL + commit),
  `terrain`, `difficulty` (a hypothesis, see `docs/LEVELS.md`). **No reference content.**
- `<vault>/<problem_id>.json` — `result` (string), `provenance` (URL, commit, manuscript or
  result-family id, formalization state). Written in the canonical form `fma.vault.seal` uses.

Rules: the statement must be checked by a human or a separate agent for leaked answer content;
ingestion runs in a session that never also acts as `solver`.
