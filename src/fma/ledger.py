"""Append-only, hash-chained provenance ledger (one JSONL file per run).

Each entry commits to the previous entry's hash and to the hash of run.json
after the step, so reordering, deletion, or after-the-fact edits are detectable.
The chain proves internal consistency only: whoever can rewrite the whole file
can forge it. Anchor the head hash outside the apparatus (git commit, a human,
a timestamping service) for anything that has to be trusted.
"""
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(obj) -> str:
    text = obj if isinstance(obj, str) else canonical(obj)
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class Transition:
    """Original minimal transition record; kept for compatibility."""

    transition_id: str
    actor: str
    input_state: str
    action: str
    output_state: str
    question_version: int = 1
    evidence: tuple = ()
    previous_hash: str = ""

    def digest(self) -> str:
        payload = asdict(self)
        payload["evidence"] = list(self.evidence)
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    def head(self) -> str:
        entries = self.entries()
        return entries[-1]["hash"] if entries else GENESIS

    def has(self, action: str) -> bool:
        return any(e["action"] == action for e in self.entries())

    def append(self, *, actor: str, action: str, input_state: str, output_state: str,
               question_version: int = 1, authority: str = "", evidence=(),
               state_hash: str = "", detail: dict | None = None) -> dict:
        entries = self.entries()
        entry = {
            "transition_id": f"T-{len(entries) + 1:04d}",
            "actor": actor,
            "authority": authority,
            "question_version": question_version,
            "input_state": input_state,
            "action": action,
            "output_state": output_state,
            "evidence": list(evidence),
            "detail": detail or {},
            "state_hash": state_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "previous_hash": entries[-1]["hash"] if entries else GENESIS,
        }
        entry["hash"] = sha(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(canonical(entry) + "\n")
        return entry

    def verify(self) -> list[str]:
        """Return a list of problems; empty means the chain is intact."""
        problems = []
        prev = GENESIS
        for i, e in enumerate(self.entries(), 1):
            body = {k: v for k, v in e.items() if k != "hash"}
            if e.get("previous_hash") != prev:
                problems.append(f"entry {i}: previous_hash does not match entry {i - 1}")
            if sha(body) != e.get("hash"):
                problems.append(f"entry {i}: content does not match its hash")
            if e.get("transition_id") != f"T-{i:04d}":
                problems.append(f"entry {i}: transition_id out of sequence")
            prev = e.get("hash")
        return problems
