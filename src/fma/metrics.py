"""Metrics computed from recorded runs (docs/METRICS.md).

Only metrics that can be derived from the records are reported. The rest are
listed under `not_implemented` rather than estimated.
"""
from collections import Counter

from .compare import MATCHES
from .engine import Run, list_runs


def _ratio(num: int, den: int):
    return round(num / den, 4) if den else None


def compute(home) -> dict:
    runs = [Run(home, r) for r in list_runs(home)]
    compared = [r for r in runs if r.state.get("comparisons")]
    base = [r for r in compared if not r.state.get("arm")]
    first_ok = [r for r in base if r.state["comparisons"][0]["classification"] in MATCHES]
    final_ok = [r for r in base if r.state["comparisons"][-1]["classification"] in MATCHES]
    corrected = [r for r in final_ok if r not in first_ok]
    attempts_to_fix = [
        next(i for i, c in enumerate(r.state["comparisons"], 1) if c["classification"] in MATCHES)
        for r in corrected]
    transfers = [t for r in runs for t in r.state.get("transfers", [])]
    # Headline accuracy uses primary runs only: no transfer arms.
    primary = [r for r in compared if not r.state.get("arm")]
    clean = [r for r in primary if not r.state["attempts"][0].get("contamination_risk")]

    def first_pass(group):
        return _ratio(sum(r.state["comparisons"][0]["classification"] in MATCHES for r in group), len(group))

    def label(r):
        return "+".join(r.state.get("condition", {}).get("skip", [])) or "full"

    by_condition = {}
    for name in sorted({label(r) for r in primary}):
        group = [r for r in primary if label(r) == name]
        by_condition[f"skip:{name}" if name != "full" else "full"] = {
            "runs": len(group), "first_pass_result_accuracy": first_pass(group)}
    by_family = {}
    for fam in sorted({r.state["problem"].get("family", "-") for r in primary}):
        group = [r for r in primary if r.state["problem"].get("family", "-") == fam]
        by_family[fam] = {"runs": len(group), "first_pass_result_accuracy": first_pass(group)}

    attempts = [(r, a) for r in runs for a in r.state["attempts"]]
    verifs = [v for r in runs for v in r.state.get("verifications", [])]
    comps = [c for r in runs for c in r.state.get("comparisons", [])]
    indep = {v["attempt_id"] for v in verifs if v["independent"]}
    judgments = len(verifs) + sum(1 for c in comps if c["adjudicated_by"])
    self_cert = sum(1 for v in verifs if not v["independent"]) + sum(1 for c in comps if c["self_certified"])

    def blind_ok(r):
        seen_release = False
        for e in r.ledger.entries():
            if e["action"] == "REFERENCE_RELEASED":
                seen_release = True
            if e["action"] == "ATTEMPT_RECORDED":
                return not seen_release and r.state["attempts"][0]["reference_blind"]
        return True

    with_attempts = [r for r in runs if r.state["attempts"]]
    return {
        "runs": len(runs),
        "runs_compared": len(compared),
        "primary": {
            "first_pass_result_accuracy": first_pass(primary),
            "first_pass_result_accuracy_uncontaminated": first_pass(clean),
            "primary_runs": len(primary),
            "final_result_accuracy": _ratio(len(final_ok), len(base)),
            "correction_gain": (None if not base
                                else round((len(final_ok) - len(first_ok)) / len(base), 4)),
            "attempts_to_correction_mean": (round(sum(attempts_to_fix) / len(attempts_to_fix), 2)
                                            if attempts_to_fix else None),
            "transfer_rate": _ratio(sum(t["result"] == "TRANSFERRED" for t in transfers), len(transfers)),
            "transfers_tested": len(transfers),
            "transfer_results": dict(Counter(t["result"] for t in transfers)),
        },
        "first_pass_by_condition": by_condition,
        "first_pass_by_family": by_family,
        "diagnostic": {
            "failure_loci": dict(Counter(d["locus"] for r in runs for d in r.state.get("deltas", []))),
            "comparison_classes": dict(Counter(c["classification"] for c in comps)),
            "hidden_assumptions_found": sum(len((r.state.get("audit") or {}).get("assumptions", []))
                                            for r in runs),
            "communication_losses": sum(len((r.state.get("audit") or {}).get("losses", [])) for r in runs),
            "dissent_preserved_runs": sum(1 for r in runs if (r.state.get("plan") or {}).get("dissent")),
        },
        "governance": {
            "attempts_with_contamination_risk": sum(bool(a.get("contamination_risk")) for _, a in attempts),
            "reference_blind_compliance": _ratio(sum(blind_ok(r) for r in with_attempts), len(with_attempts)),
            "provenance_completeness": _ratio(sum(not r.integrity() for r in runs), len(runs)),
            "self_certification_rate": _ratio(self_cert, judgments),
            "independent_verification_coverage": _ratio(
                sum(a["attempt_id"] in indep for _, a in attempts), len(attempts)),
        },
        "not_implemented": ["reconstruction_fidelity", "intervention_specificity", "lesson_recurrence",
                            "question_interpretation_errors"],
    }
