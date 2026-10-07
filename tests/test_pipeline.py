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
ENV = {"model": "test-model", "knowledge_cutoff": "2026-06", "web_access": False, "code_execution": False}
PASS = {"checks": [{"name": "recompute", "kind": "computational", "outcome": "PASS", "evidence": "script"}]}


def att(result, **extra):
    return {"candidate_result": result, "environment": ENV, **extra}


def to_plan(home, run_id, pid, parent=None, arm=None):
    r = Run.init(home, run_id, fx("problems", pid), fx("references", pid), "intake", parent, arm=arm)
    r.question(QUESTION, "framer")
    r.audit({"assumptions": ["'or' is inclusive"]}, "framer")
    r.plan(PLAN, "planner")
    return r


def test_full_loop_mismatch_intervention_transfer(tmp_path):
    r = to_plan(tmp_path, "R1", "F-0001")
    a1 = r.attempt(att("2733", strategy="H1", reference_blind=False), "solver")
    assert a1["reference_blind"] is True  # engine stamps blindness; caller's claim is ignored
    v = r.verify(PASS, "solver")
    assert v["independent"] is False
    c1 = r.compare("judge")
    assert c1["classification"] == "UNRESOLVED"  # non-identical text is never auto-called wrong
    r2 = Run(tmp_path, "R1")
    with pytest.raises(ProtocolError):
        r2.attempt(att("2418"), "solver")  # no re-solve without delta + intervention
    r2.delta({"locus": "assumptions", "description": "multiples of 15 counted twice"}, "analyst")
    r2.intervene({"change": "subtract the common multiples", "rationale": "sets overlap",
                  "controlled_variable": "counting method"}, "analyst")
    a2 = r2.attempt(att("2418"), "solver")
    assert a2["reference_blind"] is False  # reference was released before this attempt
    r2.verify(PASS, "verifier")
    assert r2.compare("judge")["classification"] == "EXACT_MATCH"

    for arm, answer in (("treatment", "6834"), ("control", "7000")):
        child = to_plan(tmp_path, f"R1-{arm}", "F-0002", parent="R1", arm=arm)
        a = child.attempt(att(answer), "solver")
        assert a["lesson_applied"] is (arm == "treatment")
        child.verify(PASS, "verifier")
        child.compare("judge", classification=None if arm == "treatment" else "MISMATCH",
                      equivalence_basis="different integer")
    with pytest.raises(ProtocolError):
        Run(tmp_path, "R1").transfer("R1-control", "R1-treatment", "judge")  # arms swapped
    t = Run(tmp_path, "R1").transfer("R1-treatment", "R1-control", "judge")
    assert t["result"] == "TRANSFERRED"

    final = Run(tmp_path, "R1")
    d = final.deliver({"epistemic_status": "VERIFIED", "lesson": "check set overlap before summing"}, "editor")
    assert d["lesson_status"] == "ACCEPTED"
    assert final.state["status"] == "COMPLETED"
    assert final.integrity() == []
    assert (tmp_path / "runs" / "R1" / "deliverable.md").exists()

    m = metrics.compute(tmp_path)
    assert m["primary"]["first_pass_result_accuracy"] == 0.0  # transfer arms are not headline runs
    assert m["primary"]["primary_runs"] == 1
    assert m["primary"]["attempts_to_correction_mean"] == 2
    assert m["primary"]["transfer_rate"] == 1.0
    assert m["governance"]["reference_blind_compliance"] == 1.0
    assert 0 < m["governance"]["self_certification_rate"] < 1


def test_reference_stays_sealed_until_compare(tmp_path):
    r = to_plan(tmp_path, "R2", "F-0001")
    assert "2418" not in (tmp_path / "runs" / "R2" / "run.json").read_text()
    with pytest.raises(ProtocolError):
        r.compare("judge")  # no attempt yet
    r.attempt(att("2418"), "solver")
    with pytest.raises(ProtocolError):
        r.compare("judge")  # no internal verification yet
    assert not r.released


def test_self_certification_blocks_verified(tmp_path):
    r = to_plan(tmp_path, "R3", "F-0001")
    r.attempt(att("2418"), "solver")
    r.verify(PASS, "solver")  # solver checking itself
    r.compare("judge")
    with pytest.raises(ProtocolError):
        r.deliver({"epistemic_status": "VERIFIED", "lesson": "none"}, "editor")
    d = r.deliver({"epistemic_status": "SUPPORTED", "lesson": "none"}, "editor")
    assert d["lesson_status"] == "NOT_APPLICABLE"


def test_adjudication_needs_basis_and_flags_self_certification(tmp_path):
    r = to_plan(tmp_path, "R4", "F-0003")
    r.attempt(att("1 + 2x + x^2"), "solver")
    r.verify(PASS, "verifier")
    with pytest.raises(ProtocolError):
        r.compare("solver", classification="EQUIVALENT_RESULT")
    c = Run(tmp_path, "R4").compare("solver", classification="EQUIVALENT_RESULT", equivalence_basis="reordered")
    assert c["self_certified"] is True


def test_sympy_adapter_confirms_equivalence(tmp_path):
    pytest.importorskip("sympy")
    r = to_plan(tmp_path, "R5", "F-0003")
    r.attempt(att("1 + 2x + x^2"), "solver")
    r.verify(PASS, "verifier")
    c = r.compare("judge", adapter="sympy")
    assert c["classification"] == "EQUIVALENT_RESULT" and c["method"] == "adapter:sympy"


def test_tampering_is_detected(tmp_path):
    r = to_plan(tmp_path, "R6", "F-0001")
    r.attempt(att("2733"), "solver")
    path = tmp_path / "runs" / "R6" / "run.json"
    path.write_text(path.read_text().replace("2733", "2418"))
    assert Run(tmp_path, "R6").integrity()
    ledger = tmp_path / "runs" / "R6" / "ledger.jsonl"
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines[:2] + lines[3:]) + "\n")
    assert any("previous_hash" in p for p in Run(tmp_path, "R6").ledger.verify())


def test_transfer_problem_must_be_unseen(tmp_path):
    r = to_plan(tmp_path, "R7", "F-0001")
    r.attempt(att("2733"), "solver")
    r.verify(PASS, "verifier")
    r.compare("judge")
    r.delta({"locus": "assumptions", "description": "double count"}, "analyst")
    r.intervene({"change": "c", "rationale": "r", "controlled_variable": "counting method"}, "analyst")
    with pytest.raises(ProtocolError):
        Run.init(tmp_path, "R7-T", fx("problems", "F-0001"), fx("references", "F-0001"), "intake", "R7",
                 arm="treatment")


def test_cli_refuses_out_of_order(tmp_path, capsys):
    home = ["--home", str(tmp_path)]
    assert main(home + ["init", "--run", "C1", "--problem", str(FIX / "problems/F-0001.json"),
                        "--reference", str(FIX / "references/F-0001.json"), "--actor", "intake"]) == 0
    assert main(home + ["compare", "--run", "C1", "--actor", "judge"]) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert main(home + ["check", "--run", "C1"]) == 0


def test_control_arm_that_also_solves_makes_transfer_inconclusive(tmp_path):
    r = to_plan(tmp_path, "R8", "F-0001")
    r.attempt(att("2733"), "solver"); r.verify(PASS, "verifier"); r.compare("judge")
    r.delta({"locus": "assumptions", "description": "double count"}, "analyst")
    r.intervene({"change": "c", "rationale": "r", "controlled_variable": "counting method"}, "analyst")
    r.attempt(att("2418"), "solver"); r.verify(PASS, "verifier"); r.compare("judge")
    for arm in ("treatment", "control"):
        c = to_plan(tmp_path, f"R8-{arm}", "F-0002", parent="R8", arm=arm)
        c.attempt(att("6834"), "solver"); c.verify(PASS, "verifier"); c.compare("judge")
    t = Run(tmp_path, "R8").transfer("R8-treatment", "R8-control", "judge")
    assert t["result"] == "INCONCLUSIVE"
    d = Run(tmp_path, "R8").deliver({"epistemic_status": "SUPPORTED", "lesson": "x"}, "editor")
    assert d["lesson_status"] == "INCONCLUSIVE"


def test_ablation_condition_skips_stages_and_is_reported(tmp_path):
    bare = Run.init(tmp_path, "B1", fx("problems", "F-0001"), fx("references", "F-0001"), "intake",
                    skip=["question", "audit", "ail", "moie"])
    with pytest.raises(ProtocolError):
        bare.question(QUESTION, "framer")
    bare.attempt(att("2418"), "solver"); bare.verify(PASS, "verifier"); bare.compare("judge")
    full = to_plan(tmp_path, "B2", "F-0001")
    full.attempt(att("2733"), "solver"); full.verify(PASS, "verifier"); full.compare("judge")
    partial = Run.init(tmp_path, "B3", fx("problems", "F-0001"), fx("references", "F-0001"), "intake",
                       skip=["audit"])
    with pytest.raises(ProtocolError):
        partial.attempt(att("2418"), "solver")  # question and plan are still required
    partial.question(QUESTION, "framer"); partial.plan(PLAN, "planner")
    by = metrics.compute(tmp_path)["first_pass_by_condition"]
    assert by["full"]["first_pass_result_accuracy"] == 0.0
    assert by["skip:ail+audit+moie+question"]["first_pass_result_accuracy"] == 1.0


def test_environment_is_required_and_contamination_is_flagged(tmp_path):
    r = to_plan(tmp_path, "E1", "F-0001")
    with pytest.raises(ProtocolError):
        r.attempt({"candidate_result": "2418"}, "solver")
    a = r.attempt({"candidate_result": "2418", "environment": dict(ENV, web_access=True)}, "solver")
    assert a["contamination_risk"]
    p = dict(fx("problems", "F-0003"), reference_public_since="2026-03-01")
    r2 = Run.init(tmp_path, "E2", p, fx("references", "F-0003"), "intake", skip=["question", "audit", "ail", "moie"])
    assert r2.attempt(att("x"), "solver")["contamination_risk"] == [
        "reference was public before the solver's knowledge cutoff"]


def test_real_problems_need_an_outside_vault(tmp_path, monkeypatch):
    monkeypatch.delenv("FMA_VAULT", raising=False)
    p = dict(fx("problems", "F-0001"), source="calibration")
    with pytest.raises(ProtocolError):
        Run.init(tmp_path / "home", "V1", p, fx("references", "F-0001"), "intake")
    monkeypatch.setenv("FMA_VAULT", str(tmp_path / "outside-vault"))
    Run.init(tmp_path / "home", "V1", p, fx("references", "F-0001"), "intake")
    assert not (tmp_path / "home" / "vault").exists()


def test_calibration_bank_and_preflight(tmp_path, monkeypatch):
    from fma import calibration, preflight
    home = tmp_path / "home"; home.mkdir()
    monkeypatch.delenv("FMA_VAULT", raising=False)
    with pytest.raises(ValueError):
        calibration.generate(home, 5, 1, home / "calibration")
    assert preflight.run(home)[1] is False
    monkeypatch.setenv("FMA_VAULT", str(tmp_path / "v"))
    m = calibration.generate(home, 30, 1, home / "calibration")
    assert len(m) == 30 and len({x["family"] for x in m}) == 5
    again = calibration.generate(tmp_path / "h2", 30, 1, tmp_path / "h2" / "calibration")
    assert [x["statement_hash"] for x in again] == [x["statement_hash"] for x in m]  # seeded
    leaked = [f for f in home.rglob("*.json") if '"result"' in f.read_text()]
    assert not leaked  # no answers anywhere under the apparatus directory
    checks, ready = preflight.run(home)
    assert ready, checks


def test_integer_adapter_calls_distinct_integers_a_mismatch(tmp_path):
    r = to_plan(tmp_path, "I1", "F-0001")
    r.attempt(att("2733"), "solver"); r.verify(PASS, "verifier")
    c = r.compare("judge", adapter="integer")
    assert c["classification"] == "MISMATCH" and c["method"] == "adapter:integer"
    r2 = to_plan(tmp_path, "I2", "F-0001")
    r2.attempt(att("about 2418"), "solver"); r2.verify(PASS, "verifier")
    assert r2.compare("judge", adapter="integer")["classification"] == "UNRESOLVED"


def test_status_next_action_respects_skipped_stages(tmp_path, capsys):
    home = ["--home", str(tmp_path)]
    base = ["--problem", str(FIX / "problems/F-0001.json"), "--reference", str(FIX / "references/F-0001.json"),
            "--actor", "intake"]
    main(home + ["init", "--run", "N1"] + base + ["--skip", "question", "--skip", "audit", "--skip", "ail", "--skip", "moie"])
    main(home + ["init", "--run", "N2"] + base + ["--skip", "question"])
    capsys.readouterr()
    main(home + ["status", "--run", "N1"]); assert json.loads(capsys.readouterr().out)["next"] == "attempt"
    main(home + ["status", "--run", "N2"]); assert json.loads(capsys.readouterr().out)["next"] == "audit"


def test_program_log_is_append_only_and_tamper_evident(tmp_path, capsys):
    from fma import programlog
    home = ["--home", str(tmp_path)]
    assert main(home + ["log", "--kind", "mistake", "--text", "wrong fixture answer", "--actor", "builder"]) == 0
    assert main(home + ["log", "--kind", "correction", "--text", "fixed", "--actor", "builder", "--ref", "T-0001"]) == 0
    assert main(home + ["log", "--text", "no kind"]) == 2
    assert main(home + ["log"]) == 0
    assert "wrong fixture answer" in capsys.readouterr().out
    path = tmp_path / "log" / "program.jsonl"
    path.write_text(path.read_text().replace("wrong fixture answer", "nothing happened"))
    assert programlog.verify(tmp_path)
    assert main(home + ["log"]) == 1
