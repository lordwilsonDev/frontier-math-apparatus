"""Run state machine for the research protocol (docs/PROTOCOL.md, phases A-K).

Phase codes stored in run.json:
  A intake -> B question -> C audit -> D plan -> E attempt -> F verify -> G compare
  G (no match) -> H delta -> I intervene -> E attempt (next cycle) ...
  G -> T transfer (only once an intervention exists) -> K deliverable
  G -> K deliverable

The engine, not the caller, decides the facts that matter for governance:
whether an attempt was reference-blind, whether a verification was
independent, whether a comparison was self-certified, and what a transfer
test showed.
"""
import json
import re
from pathlib import Path

from . import vault
from .compare import MATCHES, Comparison, compare_textual, compare_with_adapter
from .ledger import Ledger, canonical, sha
from .schema import validate

LOCI = ["interpretation", "assumptions", "strategy", "derivation", "calculation",
        "scope", "tooling", "evidence", "reference_disagreement"]
AUDIT_KEYS = ["ambiguities", "losses", "transformations", "inventions", "assumptions"]
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


class ProtocolError(RuntimeError):
    """An action was attempted out of order or without what the protocol requires."""


def list_runs(home) -> list[str]:
    d = Path(home) / "runs"
    return sorted(p.name for p in d.iterdir() if (p / "run.json").exists()) if d.exists() else []


class Run:
    def __init__(self, home, run_id: str):
        self.home = Path(home)
        self.run_id = run_id
        self.dir = self.home / "runs" / run_id
        self.ledger = Ledger(self.dir / "ledger.jsonl")
        path = self.dir / "run.json"
        if not path.exists():
            raise ProtocolError(f"no such run: {run_id}")
        self.state = json.loads(path.read_text())

    # ---------------------------------------------------------------- plumbing

    @property
    def phase(self) -> str:
        return self.state["phase"]

    @property
    def released(self) -> bool:
        return self.ledger.has("REFERENCE_RELEASED")

    def _require(self, action: str, *phases: str) -> None:
        if self.phase not in phases:
            raise ProtocolError(
                f"{action} is not allowed in phase {self.phase}; allowed from: {', '.join(phases)}")

    def _qv(self) -> int:
        return (self.state.get("question") or {}).get("version", 1)

    def _commit(self, action: str, actor: str, new_phase: str, evidence, authority: str = "",
                detail: dict | None = None) -> None:
        if not actor:
            raise ProtocolError("every transition needs an actor")
        old = self.phase
        self.state["phase"] = new_phase
        validate(self.state, "run.schema.json")
        (self.dir / "run.json").write_text(json.dumps(self.state, indent=2, ensure_ascii=False) + "\n")
        self.ledger.append(actor=actor, action=action, input_state=old, output_state=new_phase,
                           question_version=self._qv(), authority=authority,
                           evidence=[sha(evidence)], state_hash=sha(self.state), detail=detail)

    def integrity(self) -> list[str]:
        problems = self.ledger.verify()
        entries = self.ledger.entries()
        if not entries:
            problems.append("ledger is empty")
        elif entries[-1]["state_hash"] != sha(self.state):
            problems.append("run.json does not match the state committed by the last ledger entry")
        return problems

    # ---------------------------------------------------------------- phase A

    @classmethod
    def init(cls, home, run_id: str, problem: dict, reference: dict, actor: str,
             parent_run_id: str | None = None, authority: str = "") -> "Run":
        home = Path(home)
        if not _ID.match(run_id):
            raise ProtocolError("run_id must be alphanumeric with . _ - only")
        run_dir = home / "runs" / run_id
        if run_dir.exists():
            raise ProtocolError(f"run {run_id} already exists; runs are never overwritten")
        problem = dict(problem)
        problem["blind_reference"] = True
        problem["content_hash"] = sha(problem.get("statement", ""))
        validate(problem, "problem.schema.json")
        if not _ID.match(problem["problem_id"]):
            raise ProtocolError("problem_id must be alphanumeric with . _ - only")
        if parent_run_id:
            parent = cls(home, parent_run_id)
            if not parent.state.get("interventions"):
                raise ProtocolError("a transfer run needs a parent run that recorded an intervention")
            for other in list_runs(home):
                if cls(home, other).state["problem"]["content_hash"] == problem["content_hash"]:
                    raise ProtocolError(
                        f"transfer problem is not unseen: run {other} already used this statement")
        commitment = vault.seal(home, problem["problem_id"], reference)
        run_dir.mkdir(parents=True)
        state = {
            "run_id": run_id, "problem": problem, "question": None, "attempts": [],
            "status": "PROPOSED", "phase": "A", "cycle": 1,
            "reference_commitment": commitment, "parent_run_id": parent_run_id,
        }
        (run_dir / "run.json").write_text(json.dumps(state, indent=2) + "\n")
        run = cls(home, run_id)
        run.ledger.append(actor=actor, action="PROBLEM_REGISTERED", input_state="-", output_state="A",
                          authority=authority, evidence=[problem["content_hash"], commitment],
                          state_hash=sha(run.state),
                          detail={"problem_id": problem["problem_id"], "reference_commitment": commitment})
        return run

    # ---------------------------------------------------------------- phases B-D

    def question(self, q: dict, actor: str) -> None:
        self._require("question", "A", "B", "C", "D")
        q = dict(q)
        q["version"] = self._qv() + 1 if self.state.get("question") else 1
        q.setdefault("question_id", f"{self.run_id}-Q")
        validate(q, "question.schema.json")
        if not q["success_conditions"]:
            raise ProtocolError("a canonical question needs at least one success condition")
        self.state["question"] = q
        self._commit("QUESTION_CANONICALIZED", actor, "B", q)

    def audit(self, a: dict, actor: str) -> None:
        self._require("audit", "B")
        record = {}
        for key in AUDIT_KEYS:
            value = a.get(key, [])
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise ProtocolError(f"audit.{key} must be a list of strings")
            record[key] = value
        self.state["audit"] = record
        self._commit("REPRESENTATION_AUDITED", actor, "C", record)

    def plan(self, p: dict, actor: str) -> None:
        self._require("plan", "C")
        hyps = p.get("hypotheses", [])
        for h in hyps:
            validate(h, "hypothesis.schema.json")
        ids = [h["hypothesis_id"] for h in hyps]
        if len(set(ids)) < 2:
            raise ProtocolError("MoIE needs at least two competing hypotheses on record")
        if p.get("selected") not in ids:
            raise ProtocolError("plan.selected must name one of the hypotheses")
        inversions = p.get("inversions", [])
        if not inversions:
            raise ProtocolError("AIL must record at least one inverted assumption")
        self.state["hypotheses"] = hyps
        self.state["plan"] = {"selected": p["selected"], "inversions": inversions,
                              "dissent": p.get("dissent", [])}
        self.state["status"] = "RUNNING"
        self._commit("RESEARCH_PLANNED", actor, "D", p)

    # ---------------------------------------------------------------- phases E-G

    def attempt(self, a: dict, actor: str) -> dict:
        self._require("attempt", "D", "I")
        a = dict(a)
        a["attempt_id"] = f"{self.run_id}-A{len(self.state['attempts']) + 1}"
        a["reference_blind"] = not self.released
        a["actor"] = actor
        a["cycle"] = self.state["cycle"]
        validate(a, "attempt.schema.json")
        self.state["attempts"].append(a)
        self._commit("ATTEMPT_RECORDED", actor, "E", a,
                     detail={"attempt_id": a["attempt_id"], "reference_blind": a["reference_blind"]})
        return a

    def verify(self, v: dict, actor: str) -> dict:
        self._require("verify", "E", "F")
        target = self.state["attempts"][-1]
        checks = v.get("checks", [])
        record = {"attempt_id": target["attempt_id"], "verifier": actor,
                  "independent": actor != target["actor"], "checks": checks}
        outcomes = [c.get("outcome") for c in checks if isinstance(c, dict)]
        record["outcome"] = ("FAIL" if "FAIL" in outcomes
                             else "PASS" if outcomes and all(o == "PASS" for o in outcomes)
                             else "INCONCLUSIVE")
        validate(record, "verification.schema.json")
        self.state.setdefault("verifications", []).append(record)
        self._commit("INTERNALLY_VERIFIED", actor, "F", record,
                     detail={"independent": record["independent"], "outcome": record["outcome"]})
        return record

    def compare(self, actor: str, classification: str | None = None,
                equivalence_basis: str | None = None, adapter: str | None = None,
                delta: str = "") -> dict:
        self._require("compare", "F")
        target = self.state["attempts"][-1]
        if not self.released:
            self.ledger.append(actor=actor, action="REFERENCE_RELEASED", input_state="F",
                               output_state="F", question_version=self._qv(),
                               evidence=[self.state["reference_commitment"]],
                               state_hash=sha(self.state))
        ref = vault.unseal(self.home, self.state["problem"]["problem_id"],
                           self.state["reference_commitment"])
        solver, reference = target["candidate_result"], ref["result"]
        result, basis, method = compare_textual(solver, reference), "", "textual"
        if result is Comparison.EXACT_MATCH:
            basis = "identical after trimming whitespace"
        elif adapter:
            decided = compare_with_adapter(adapter, solver, reference)
            if decided:
                (result, basis), method = decided, f"adapter:{adapter}"
        adjudicated_by = None
        if classification and classification != result.value:
            if classification == Comparison.EXACT_MATCH.value:
                raise ProtocolError("EXACT_MATCH is decided by the comparator, not by adjudication")
            if not (equivalence_basis or "").strip():
                raise ProtocolError("an adjudicated classification needs an explicit basis")
            result, basis, method = Comparison(classification), equivalence_basis, "adjudicated"
            adjudicated_by = actor
        comp = {
            "classification": result.value, "solver_result": solver, "reference_result": reference,
            "equivalence_basis": basis, "delta": delta,
            "reference_provenance": ref.get("provenance", ""),
            "attempt_id": target["attempt_id"], "method": method, "adjudicated_by": adjudicated_by,
            "self_certified": adjudicated_by is not None and adjudicated_by == target["actor"],
        }
        validate(comp, "comparison.schema.json")
        self.state.setdefault("comparisons", []).append(comp)
        self.state["comparison"] = comp
        self.state["status"] = ("MATCH" if result.value in MATCHES
                                else "UNRESOLVED" if result is Comparison.UNRESOLVED else "MISMATCH")
        self._commit("REFERENCE_COMPARED", actor, "G", comp,
                     detail={"classification": result.value, "method": method})
        return comp

    # ---------------------------------------------------------------- phases H-J

    def delta(self, d: dict, actor: str) -> None:
        self._require("delta", "G")
        if self.state["status"] == "MATCH":
            raise ProtocolError("no divergence to localize: the latest comparison is a match")
        validate(d, "delta.schema.json")
        d = dict(d, attempt_id=self.state["attempts"][-1]["attempt_id"])
        self.state.setdefault("deltas", []).append(d)
        self._commit("DELTA_LOCALIZED", actor, "H", d, detail={"locus": d["locus"]})

    def intervene(self, i: dict, actor: str) -> None:
        self._require("intervene", "H")
        i = dict(i)
        i.setdefault("intervention_id", f"{self.run_id}-I{len(self.state.get('interventions', [])) + 1}")
        i.setdefault("failure_class", self.state["deltas"][-1]["locus"])
        validate(i, "intervention.schema.json")
        if not (i.get("controlled_variable") or "").strip():
            raise ProtocolError("an intervention must name the single controlled variable it changes")
        self.state.setdefault("interventions", []).append(i)
        self.state["intervention"] = i
        self.state["cycle"] += 1
        self.state["status"] = "RUNNING"
        self._commit("INTERVENTION_APPLIED", actor, "I", i)

    def transfer(self, child_run_id: str, actor: str) -> dict:
        self._require("transfer", "G")
        if not self.state.get("interventions"):
            raise ProtocolError("nothing to transfer: this run recorded no intervention")
        child = Run(self.home, child_run_id)
        if child.state.get("parent_run_id") != self.run_id:
            raise ProtocolError("transfer run must have been initialised with this run as its parent")
        if child.integrity():
            raise ProtocolError("transfer run failed its ledger integrity check")
        comps = child.state.get("comparisons") or []
        if not comps or not child.state["attempts"][0]["reference_blind"]:
            raise ProtocolError("transfer run needs a blind first attempt that has been compared")
        first = comps[0]["classification"]
        result = ("TRANSFERRED" if first in MATCHES
                  else "DID_NOT_TRANSFER" if first in ("MISMATCH", "PARTIAL_MATCH")
                  else "INCONCLUSIVE")
        record = {"tested": True, "problem_id": child.state["problem"]["problem_id"],
                  "run_id": child_run_id, "result": result,
                  "evidence": f"first comparison of {child_run_id} = {first}; ledger head {child.ledger.head()}"}
        validate(record, "transfer.schema.json")
        self.state["transfer"] = record
        self._commit("TRANSFER_TESTED", actor, "T", record, detail={"result": result})
        return record

    # ---------------------------------------------------------------- phase K

    def deliver(self, d: dict, actor: str) -> dict:
        self._require("deliver", "G", "T")
        d = dict(d)
        last = self.state["attempts"][-1]
        comp = self.state["comparison"]
        d.setdefault("final_result", last["candidate_result"])
        validate(d, "deliverable.schema.json")
        matched = comp["classification"] in MATCHES
        independent_pass = any(
            v["attempt_id"] == last["attempt_id"] and v["independent"] and v["outcome"] == "PASS"
            for v in self.state.get("verifications", []))
        status = d["epistemic_status"]
        if status == "SUPPORTED" and not matched:
            raise ProtocolError("SUPPORTED needs the final comparison to be a match")
        if status in ("VERIFIED", "REPRODUCED"):
            if not matched or comp["self_certified"] or not independent_pass:
                raise ProtocolError(
                    f"{status} needs a matching final comparison that was not self-certified and an "
                    "independent PASS verification of the final attempt; use SUPPORTED, PROPOSED or UNRESOLVED")
        transfer = self.state.get("transfer")
        d["lesson_status"] = ("NOT_APPLICABLE" if not self.state.get("interventions")
                              else "UNTESTED" if not transfer
                              else {"TRANSFERRED": "ACCEPTED", "DID_NOT_TRANSFER": "REJECTED"}.get(
                                  transfer["result"], "INCONCLUSIVE"))
        self.state["deliverable"] = d
        self.state["status"] = "COMPLETED"
        self._commit("DELIVERABLE_ISSUED", actor, "K", d)
        (self.dir / "deliverable.md").write_text(self.render())
        return d

    def render(self) -> str:
        s = self.state

        def block(title, obj):
            body = json.dumps(obj, indent=2, ensure_ascii=False) if obj else "_none recorded_"
            return f"## {title}\n\n```json\n{body}\n```\n" if obj else f"## {title}\n\n{body}\n"

        d = s.get("deliverable", {})
        parts = [
            f"# Run {s['run_id']}\n",
            f"- Final state: **{s['status']}** / epistemic status **{d.get('epistemic_status', '-')}**",
            f"- Final result: `{d.get('final_result', '-')}`",
            f"- Lesson ({d.get('lesson_status', '-')}): {d.get('lesson', '-')}",
            f"- Ledger head: `{self.ledger.head()}` ({len(self.ledger.entries())} transitions)\n",
            block("Problem", s["problem"]),
            block("Canonical question", s.get("question")),
            block("Representation audit", s.get("audit")),
            block("Hypotheses (all preserved)", s.get("hypotheses")),
            block("Plan, inversions, dissent", s.get("plan")),
            block("Attempts", s.get("attempts")),
            block("Verifications", s.get("verifications")),
            block("Reference comparisons", s.get("comparisons")),
            block("Delta analysis", s.get("deltas")),
            block("Interventions", s.get("interventions")),
            block("Transfer", s.get("transfer")),
        ]
        return "\n".join(parts)
