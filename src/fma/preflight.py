"""Readiness check before real runs: `fma preflight`.

Runs a complete fixture loop in a temporary directory (so it needs no test
framework), then checks the things that make real results trustworthy.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import programlog, schema, vault
from .engine import ProtocolError, Run, list_runs

ROOT = Path(__file__).resolve().parents[2]
ENV = {"model": "selftest", "knowledge_cutoff": "0000-00", "web_access": False, "code_execution": False}
Q = {"referent": "integers", "proposition": "sum equals S", "scope": "exact",
     "success_conditions": ["one integer"]}
PLAN = {"hypotheses": [
    {"hypothesis_id": "H1", "statement": "add both progressions", "assumptions": ["disjoint"],
     "discriminating_test": "small N"},
    {"hypothesis_id": "H2", "statement": "inclusion-exclusion", "assumptions": [],
     "discriminating_test": "small N"}],
    "selected": "H1", "inversions": ["sets overlap"], "dissent": ["H1 double counts"]}
PASS = {"checks": [{"name": "recompute", "kind": "computational", "outcome": "PASS"}]}


def _fx(kind, pid):
    return json.loads((ROOT / "fixtures" / kind / f"{pid}.json").read_text())


def _solve(run, answer, verifier="verifier"):
    run.attempt({"candidate_result": answer, "environment": ENV}, "solver")
    run.verify(PASS, verifier)
    return run.compare("judge", adapter="integer")


def selftest() -> str:
    """Mismatch -> delta -> intervention -> match -> treatment/control transfer -> deliverable."""
    saved = os.environ.pop("FMA_VAULT", None)  # fixtures use a throwaway vault, never the real one
    try:
        return _selftest()
    finally:
        if saved is not None:
            os.environ["FMA_VAULT"] = saved


def _selftest() -> str:
    with tempfile.TemporaryDirectory() as home:
        r = Run.init(home, "S", _fx("problems", "F-0001"), _fx("references", "F-0001"), "intake")
        try:
            r.compare("judge")
            return "compare was allowed before any attempt"
        except ProtocolError:
            pass
        r.question(Q, "framer"); r.audit({}, "framer"); r.plan(PLAN, "planner")
        if _solve(r, "2733")["classification"] != "MISMATCH":
            return "wrong integer answer was not classified as a mismatch"
        r.delta({"locus": "assumptions", "description": "double count"}, "analyst")
        r.intervene({"change": "subtract overlap", "rationale": "sets overlap",
                     "controlled_variable": "counting method"}, "analyst")
        if _solve(r, "2418")["classification"] != "EXACT_MATCH":
            return "corrected attempt did not match"
        for arm, answer in (("treatment", "6834"), ("control", "7000")):
            c = Run.init(home, f"S-{arm}", _fx("problems", "F-0002"), _fx("references", "F-0002"),
                         "intake", parent_run_id="S", arm=arm, skip=["question", "audit", "ail", "moie"])
            _solve(c, answer)
        if Run(home, "S").transfer("S-treatment", "S-control", "judge")["result"] != "TRANSFERRED":
            return "treatment/control transfer was scored wrongly"
        final = Run(home, "S")
        d = final.deliver({"epistemic_status": "VERIFIED", "lesson": "check overlap"}, "editor")
        if d["lesson_status"] != "ACCEPTED" or final.integrity():
            return "deliverable or ledger integrity is wrong"
        path = Path(home) / "runs" / "S" / "run.json"
        path.write_text(path.read_text().replace("2733", "2418"))
        if not Run(home, "S").integrity():
            return "tampering with run.json went undetected"
    return ""


def run(home) -> tuple[list[dict], bool]:
    home = Path(home)
    checks = []

    def add(name, ok, detail, blocking=True):
        checks.append({"check": name, "ok": bool(ok), "blocking": blocking, "detail": detail})

    add("python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0])
    try:
        names = sorted(p.name for p in schema.SCHEMA_DIR.glob("*.json"))
        for n in names:
            schema.load(n)
        add("schemas load", len(names) >= 12, f"{len(names)} schema files")
    except Exception as e:
        add("schemas load", False, str(e))
    try:
        problem = selftest()
        add("end-to-end self-test", not problem, problem or "full loop incl. control-arm transfer and tamper detection")
    except Exception as e:
        add("end-to-end self-test", False, f"{type(e).__name__}: {e}")

    v, h = vault.vault_dir(home).resolve(), home.resolve()
    outside = bool(os.environ.get("FMA_VAULT")) and v != h and h not in v.parents
    add("vault outside the apparatus", outside,
        str(v) if outside else "set FMA_VAULT to a directory outside this repo, e.g. export FMA_VAULT=~/.fma-vault")
    bad = [r for r in list_runs(home) if Run(home, r).integrity()]
    add("existing runs intact", not bad, f"{len(list_runs(home))} run(s)" if not bad else f"failed: {bad}")

    bad_log = programlog.verify(home)
    add("program log intact", not bad_log,
        f"{len(programlog.entries(home))} entries" if not bad_log else "; ".join(bad_log))

    cal = list((home / "calibration" / "problems").glob("*.json"))
    missing = [p.stem for p in cal if not (v / f"{p.stem}.json").exists()]
    add("calibration set present", bool(cal) and not missing,
        f"{len(cal)} problems, all with sealed references" if cal and not missing
        else "run: bin/fma calibrate --n 30 --seed <int>" if not cal
        else f"{len(missing)} problem(s) have no reference in the vault")
    try:
        import sympy  # noqa: F401
        add("sympy adapter", True, "available", blocking=False)
    except ImportError:
        add("sympy adapter", False, "optional; pip install sympy for closed-form equivalence", blocking=False)
    try:
        dirty = subprocess.run(["git", "-C", str(home), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=20)
        add("git clean", dirty.returncode == 0 and not dirty.stdout.strip(),
            "not a git repository" if dirty.returncode else
            "clean" if not dirty.stdout.strip() else "uncommitted changes; commit before a batch",
            blocking=False)
    except Exception as e:
        add("git clean", False, str(e), blocking=False)
    return checks, all(c["ok"] for c in checks if c["blocking"])
