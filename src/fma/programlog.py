"""Program-level research log: append-only and hash-chained, like a run ledger.

Run ledgers record what happened inside a run. This records everything else:
mistakes, failures, deviations from the plan, decisions, corrections and
observations, including ones made while building the apparatus. Entries are
never edited or removed; a wrong entry is corrected by a later entry.
"""
from pathlib import Path

from .ledger import Ledger

KINDS = ["mistake", "failure", "deviation", "decision", "correction", "observation"]


def _ledger(home) -> Ledger:
    return Ledger(Path(home) / "log" / "program.jsonl")


def add(home, kind: str, text: str, actor: str, run: str = "", ref: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if not text.strip() or not actor.strip():
        raise ValueError("a log entry needs text and an actor")
    return _ledger(home).append(actor=actor, action=kind, input_state="-", output_state="-",
                                detail={"text": text.strip(), "run": run, "ref": ref})


def entries(home) -> list[dict]:
    return _ledger(home).entries()


def verify(home) -> list[str]:
    return _ledger(home).verify()
