"""End-to-end protocol tests on fixtures. These test the machinery, not any solver."""
import json
from pathlib import Path

import pytest

from fma import metrics
from fma.cli import main
from fma.engine import ProtocolError, Run

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def fx(kind, pid):
    return json.loads((FIX / kind / f"{pid}.json").read_text())


QUESTION = {"referent": "integers 1..N", "proposition": "the sum equals S", "scope": "exact integer",
            "success_conditions": ["a single integer is stated"]}
PLAN = {
    "hypotheses": [
        {"hypothesis_id": "H1", "statement": "sum the two progressions", "assumptions": ["sets are disjoint"],
         "discriminating_test": "brute-force check for small N"},
        {"hypothesis_id": "H2", "statement": "inclusion-exclusion", "assumptions": [],
         "discriminating_test": "brute-force check for small N"},
    ],
    "selected": "H1",
    "inversions": ["what if the two sets overlap?"],
    "dissent": ["H2 holder: H1 double counts common multiples"],
}
PASS = {"checks": [{"name": "recompute", "kind": "computational", "outcome": "PASS", "evidence": "script"}]}


def to_plan(home, run_id, pid, parent=None):
    r = Run.init(home, run_id, fx("problems", pid), fx("references", pid), "intake", parent)
    r.question(QUESTION, "framer")
    r.audit({"assumptions": ["'or' is inclusive"]}, "framer")
    r.plan(PLAN, "planner")
    return r


def test_full_loop_mismatch_intervention_transfer(tmp_path):
    r = to_plan(tmp_path, "R1", "F-0001")
    a1 = r.attempt({"candidate_result": "2733", "strategy": "H1", "reference_blind": False}, "solver")
    assert a1["reference_blind"] is True  # engine stamps blindness; caller's claim is ignored
    v = r.verify(PASS, "solver")
    assert v["independent"] is False
    c1 = r.compare("judge")
    assert c1["classification"] == "UNRESOLVED"  # non-identical text is never auto-called wrong
    r2 = Run(tmp_path, "R1")
    with pytest.raises(ProtocolError):
        r2.attempt({"candidate_result": "2418"}, "solver")  # no re-solve without delta + intervention
    r2.delta({"locus": "assumptions", "description": "multiples of 15 counted twice"}, "analyst")
    r2.intervene({"change": "subtract the common multiples", "rationale": "sets overlap",
                  "controlled_variable": "counting method"}, "analyst")
    a2 = r2.attempt({"candidate_result": "2418"}, "solver")
    assert a2["reference_blind"] is False  # reference was released before this attempt
    r2.verify(PASS, "verifier")
    assert r2.compare("judge")["classification"] == "EXACT_MATCH"

    child = to_plan(tmp_path, "R1-T", "F-0002", parent="R1")
    child.attempt({"candidate_result": "6834"}, "solver")
    child.verify(PASS, "verifier")
    child.compare("judge")
    t = Run(tmp_path, "R1").transfer("R1-T", "judge")
    assert t["result"] == "TRANSFERRED"

    final = Run(tmp_path, "R1")
    d = final.deliver({"epistemic_status": "VERIFIED", "lesson": "check set overlap before summing"}, "editor")
    assert d["lesson_status"] == "ACCEPTED"
    assert final.state["status"] == "COMPLETED"
    assert final.integrity() == []
    assert (tmp_path / "runs" / "R1" / "deliverable.md").exists()

    m = metrics.compute(tmp_path)
    assert m["primary"]["first_pass_result_accuracy"] == 0.5
    assert m["primary"]["attempts_to_correction_mean"] == 2
    assert m["primary"]["transfer_rate"] == 1.0
    assert m["governance"]["reference_blind_compliance"] == 1.0
    assert 0 < m["governance"]["self_certification_rate"] < 1


def test_reference_stays_sealed_until_compare(tmp_path):
    r = to_plan(tmp_path, "R2", "F-0001")
    assert "2418" not in (tmp_path / "runs" / "R2" / "run.json").read_text()
    with pytest.raises(ProtocolError):
        r.compare("judge")  # no attempt yet
    r.attempt({"candidate_result": "2418"}, "solver")
    with pytest.raises(ProtocolError):
        r.compare("judge")  # no internal verification yet
    assert not r.released


def test_self_certification_blocks_verified(tmp_path):
    r = to_plan(tmp_path, "R3", "F-0001")
    r.attempt({"candidate_result": "2418"}, "solver")
    r.verify(PASS, "solver")  # solver checking itself
    r.compare("judge")
    with pytest.raises(ProtocolError):
        r.deliver({"epistemic_status": "VERIFIED", "lesson": "none"}, "editor")
    d = r.deliver({"epistemic_status": "SUPPORTED", "lesson": "none"}, "editor")
    assert d["lesson_status"] == "NOT_APPLICABLE"


def test_adjudication_needs_basis_and_flags_self_certification(tmp_path):
    r = to_plan(tmp_path, "R4", "F-0003")
    r.attempt({"candidate_result": "1 + 2x + x^2"}, "solver")
    r.verify(PASS, "verifier")
    with pytest.raises(ProtocolError):
        r.compare("solver", classification="EQUIVALENT_RESULT")
    c = Run(tmp_path, "R4").compare("solver", classification="EQUIVALENT_RESULT", equivalence_basis="reordered")
    assert c["self_certified"] is True


def test_sympy_adapter_confirms_equivalence(tmp_path):
    pytest.importorskip("sympy")
    r = to_plan(tmp_path, "R5", "F-0003")
    r.attempt({"candidate_result": "1 + 2x + x^2"}, "solver")
    r.verify(PASS, "verifier")
    c = r.compare("judge", adapter="sympy")
    assert c["classification"] == "EQUIVALENT_RESULT" and c["method"] == "adapter:sympy"


def test_tampering_is_detected(tmp_path):
    r = to_plan(tmp_path, "R6", "F-0001")
    r.attempt({"candidate_result": "2733"}, "solver")
    path = tmp_path / "runs" / "R6" / "run.json"
    path.write_text(path.read_text().replace("2733", "2418"))
    assert Run(tmp_path, "R6").integrity()
    ledger = tmp_path / "runs" / "R6" / "ledger.jsonl"
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines[:2] + lines[3:]) + "\n")
    assert any("previous_hash" in p for p in Run(tmp_path, "R6").ledger.verify())


def test_transfer_problem_must_be_unseen(tmp_path):
    r = to_plan(tmp_path, "R7", "F-0001")
    r.attempt({"candidate_result": "2733"}, "solver")
    r.verify(PASS, "verifier")
    r.compare("judge")
    r.delta({"locus": "assumptions", "description": "double count"}, "analyst")
    r.intervene({"change": "c", "rationale": "r", "controlled_variable": "counting method"}, "analyst")
    with pytest.raises(ProtocolError):
        Run.init(tmp_path, "R7-T", fx("problems", "F-0001"), fx("references", "F-0001"), "intake", "R7")


def test_cli_refuses_out_of_order(tmp_path, capsys):
    home = ["--home", str(tmp_path)]
    assert main(home + ["init", "--run", "C1", "--problem", str(FIX / "problems/F-0001.json"),
                        "--reference", str(FIX / "references/F-0001.json"), "--actor", "intake"]) == 0
    assert main(home + ["compare", "--run", "C1", "--actor", "judge"]) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert main(home + ["check", "--run", "C1"]) == 0
