# Verification adapters

FCVE plugs in here. A verification adapter takes an attempt and returns checks in the shape
`schemas/verification.schema.json` expects:

`{"name": ..., "kind": formal|semantic|computational|adversarial|evidence|governance,
  "outcome": PASS|FAIL|INCONCLUSIVE, "evidence": ...}`

Recorded with `bin/fma verify`. The verifier's actor must differ from the solver's for the check
to count as independent. Nothing is implemented here yet.
