"""Reference quarantine.

At intake the reference is written to the vault and only its SHA-256
commitment enters the run. The engine opens the vault once, at Phase G, after
a blind attempt and an internal verification are already on the ledger.

This is a procedural barrier, not a cryptographic one: any process that can
read the vault directory can read the reference. For real blindness, point
FMA_VAULT at a location the solving agent cannot read (different user,
different machine, or a human holding the file).
"""
import json
import os
from pathlib import Path

from .ledger import canonical, sha


def vault_dir(home) -> Path:
    return Path(os.environ.get("FMA_VAULT") or Path(home) / "vault")


def seal(home, problem_id: str, reference: dict) -> str:
    if not isinstance(reference, dict) or not isinstance(reference.get("result"), str):
        raise ValueError("reference must be an object with a string 'result'")
    d = vault_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{problem_id}.json"
    text = canonical(reference)
    if path.exists() and path.read_text() != text:
        raise ValueError(f"vault already holds a different reference for {problem_id}")
    path.write_text(text)
    return sha(text)


def unseal(home, problem_id: str, commitment: str) -> dict:
    path = vault_dir(home) / f"{problem_id}.json"
    text = path.read_text()
    if sha(text) != commitment:
        raise ValueError(f"reference for {problem_id} does not match its intake commitment")
    return json.loads(text)
