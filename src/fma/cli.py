"""Command-line front end. Run `python -m fma -h` (or ./bin/fma -h)."""
import argparse
import json
import os
import sys
from pathlib import Path

from . import calibration, metrics, preflight
from .engine import ProtocolError, Run, list_runs
from .schema import ValidationError

DATA_CMDS = {
    "question": "B  canonical question object (schemas/question.schema.json)",
    "audit": "C  representation audit: ambiguities, losses, transformations, inventions, assumptions",
    "plan": "D  {hypotheses:[>=2], selected, inversions:[>=1], dissent:[]}",
    "attempt": "E  attempt object; blindness is stamped by the engine",
    "verify": "F  {checks:[{name, kind, outcome: PASS|FAIL|INCONCLUSIVE, evidence}]}",
    "delta": "H  {locus, description, evidence}",
    "intervene": "I  {change, rationale, controlled_variable, expected_effect}",
    "deliver": "K  {epistemic_status, lesson, regression_test?}",
}


def _load(path: str):
    return json.load(sys.stdin) if path == "-" else json.loads(Path(path).read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fma", description="Frontier Math Apparatus")
    ap.add_argument("--home", default=os.environ.get("FMA_HOME", "."),
                    help="directory holding runs/ and vault/ (default: FMA_HOME or cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="A  register a problem and quarantine its reference")
    p.add_argument("--run", required=True)
    p.add_argument("--problem", required=True)
    p.add_argument("--reference", required=True)
    p.add_argument("--parent", help="parent run id; makes this a transfer run on an unseen problem")
    p.add_argument("--arm", choices=["treatment", "control"],
                   help="transfer arm: treatment gets the parent's lesson, control does not")
    p.add_argument("--skip", action="append", default=[], choices=["question", "audit", "ail", "moie"],
                   help="ablation: leave this pre-solve stage out (repeatable)")
    p.add_argument("--actor", required=True)

    for name, text in DATA_CMDS.items():
        p = sub.add_parser(name, help=text)
        p.add_argument("--run", required=True)
        p.add_argument("--data", required=True, help="JSON file, or - for stdin")
        p.add_argument("--actor", required=True)

    p = sub.add_parser("compare", help="G  release the reference and classify the latest attempt")
    p.add_argument("--run", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--adapter", choices=["integer", "sympy"])
    p.add_argument("--classification", help="adjudicated class; needs --basis")
    p.add_argument("--basis")
    p.add_argument("--delta", default="")

    p = sub.add_parser("transfer", help="J  score the lesson: treatment vs control run on one unseen problem")
    p.add_argument("--run", required=True)
    p.add_argument("--treatment", required=True)
    p.add_argument("--control", required=True)
    p.add_argument("--actor", required=True)

    for name, text in (("status", "show phase, status and next allowed actions"),
                       ("check", "verify the hash chain and run.json integrity")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--run", required=True)
    p = sub.add_parser("calibrate", help="generate calibration problems; answers go to the vault only")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--out", default=None, help="default: <home>/calibration")
    sub.add_parser("preflight", help="readiness check before real runs")
    sub.add_parser("runs", help="list runs")
    sub.add_parser("metrics", help="compute metrics over all runs")

    a = ap.parse_args(argv)
    try:
        return _dispatch(a)
    except (ProtocolError, ValidationError, ValueError, FileNotFoundError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2


NEXT = {"A": "question", "B": "audit", "C": "plan", "D": "attempt", "E": "verify",
        "F": "verify | compare", "G": "delta | transfer | deliver", "H": "intervene",
        "I": "attempt", "T": "transfer | deliver", "K": "(complete)"}


def _next(r) -> str:
    """Next allowed action, stepping over stages this run's condition skips."""
    skip = set(r.state.get("condition", {}).get("skip", []))
    steps = [("A", "question", {"question"}), ("B", "audit", {"audit"}), ("C", "plan", {"ail", "moie"})]
    if r.phase in "ABC":
        for phase, action, stages in steps:
            if phase >= r.phase and not stages <= skip:
                return action
        return "attempt"
    return NEXT[r.phase]


def _dispatch(a) -> int:
    home = a.home
    if a.cmd == "init":
        run = Run.init(home, a.run, _load(a.problem), _load(a.reference), a.actor, a.parent,
                       skip=a.skip, arm=a.arm)
        print(f"registered {a.run}; reference commitment {run.state['reference_commitment'][:16]}…")
    elif a.cmd in DATA_CMDS:
        out = getattr(Run(home, a.run), a.cmd)(_load(a.data), a.actor)
        print(json.dumps(out, indent=2) if out else f"{a.cmd} recorded")
    elif a.cmd == "compare":
        out = Run(home, a.run).compare(a.actor, a.classification, a.basis, a.adapter, a.delta)
        print(json.dumps(out, indent=2))
    elif a.cmd == "transfer":
        print(json.dumps(Run(home, a.run).transfer(a.treatment, a.control, a.actor), indent=2))
    elif a.cmd == "status":
        r = Run(home, a.run)
        print(json.dumps({"run_id": r.run_id, "phase": r.phase, "status": r.state["status"],
                          "cycle": r.state["cycle"], "attempts": len(r.state["attempts"]),
                          "reference_released": r.released, "next": _next(r),
                          "skipped_stages": r.state.get("condition", {}).get("skip", []),
                          "arm": r.state.get("arm"),
                          "ledger_head": r.ledger.head()}, indent=2))
    elif a.cmd == "check":
        problems = Run(home, a.run).integrity()
        print("OK: ledger chain and run.json are consistent" if not problems else "\n".join(problems))
        return 1 if problems else 0
    elif a.cmd == "calibrate":
        m = calibration.generate(home, a.n, a.seed, a.out or Path(home) / "calibration")
        fams = sorted({x["family"] for x in m})
        print(f"wrote {len(m)} problems across {len(fams)} families ({', '.join(fams)}); "
              f"references sealed in the vault, not printed")
    elif a.cmd == "preflight":
        checks, ready = preflight.run(home)
        for c in checks:
            mark = "ok  " if c["ok"] else ("FAIL" if c["blocking"] else "warn")
            print(f"[{mark}] {c['check']}: {c['detail']}")
        print("\nREADY to start testing" if ready else "\nNOT READY: fix the FAIL lines above")
        return 0 if ready else 1
    elif a.cmd == "runs":
        for r in list_runs(home):
            s = Run(home, r).state
            cond = "+".join(s.get("condition", {}).get("skip", [])) or "full"
            print(f"{r}\tphase {s['phase']}\t{s['status']}\tskip:{cond}\t{s.get('arm') or '-'}")
    elif a.cmd == "metrics":
        print(json.dumps(metrics.compute(home), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
