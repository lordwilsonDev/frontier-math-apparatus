# Metrics

## Primary

- First-Pass Result Accuracy
- Reconstruction Fidelity
- Correction Gain
- Attempts-to-Correction
- Transfer Rate

## Diagnostic

- Question Interpretation Errors
- Communication Losses
- Hidden Assumptions Found
- Strategy Failures
- Derivation Failures
- Calculation Failures
- Reference Disagreements
- MoIE Disagreement Preservation
- Intervention Specificity
- Lesson Recurrence

## Governance

- Reference-Blind Compliance
- Provenance Completeness
- Immutable Transition Coverage
- Self-Certification Rate (target: 0%)
- Independent Verification Coverage

## Reporting rules (v0.2)

- Headline accuracy counts primary runs only; transfer arms are excluded.
- First-pass accuracy is also reported per ablation condition, per problem family, and for
  attempts with no contamination risk.
- Transfer Rate counts a pair as transferred only when the treatment arm solves the unseen problem
  and the control arm does not.
