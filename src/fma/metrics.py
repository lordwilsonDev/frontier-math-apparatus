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
    first_ok = [r for r in compared if r.state["comparisons"][0]["classification"] in MATCHES]
    final_ok = [r for r in compared if r.state["comparisons"][-1]["classification"] in MATCHES]
    corrected = [r for r in final_ok if r not in first_ok]
    attempts_to_fix = [
        next(i for i, c in enumerate(r.state["comparisons"], 1) if c["classification"] in MATCHES)
        for r in corrected]
    transfers = [r.state["transfer"] for r in runs if r.state.get("transfer")]

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
            "first_pass_result_accuracy": _ratio(len(first_ok), len(compared)),
            "final_result_accuracy": _ratio(len(final_ok), len(compared)),
            "correction_gain": (None if not compared
                                else round((len(final_ok) - len(first_ok)) / len(compared), 4)),
            "attempts_to_correction_mean": (round(sum(attempts_to_fix) / len(attempts_to_fix), 2)
                                            if attempts_to_fix else None),
            "transfer_rate": _ratio(sum(t["result"] == "TRANSFERRED" for t in transfers), len(transfers)),
            "transfers_tested": len(transfers),
        },
        "diagnostic": {
            "failure_loci": dict(Counter(d["locus"] for r in runs for d in r.state.get("deltas", []))),
            "comparison_classes": dict(Counter(c["classification"] for c in comps)),
            "hidden_assumptions_found": sum(len((r.state.get("audit") or {}).get("assumptions", []))
                                            for r in runs),
            "communication_losses": sum(len((r.state.get("audit") or {}).get("losses", [])) for r in runs),
            "dissent_preserved_runs": sum(1 for r in runs if (r.state.get("plan") or {}).get("dissent")),
        },
        "governance": {
            "reference_blind_compliance": _ratio(sum(blind_ok(r) for r in with_attempts), len(with_attempts)),
            "provenance_completeness": _ratio(sum(not r.integrity() for r in runs), len(runs)),
            "self_certification_rate": _ratio(self_cert, judgments),
            "independent_verification_coverage": _ratio(
                sum(a["attempt_id"] in indep for _, a in attempts), len(attempts)),
        },
        "not_implemented": ["reconstruction_fidelity", "intervention_specificity", "lesson_recurrence",
                            "question_interpretation_errors"],
    }
