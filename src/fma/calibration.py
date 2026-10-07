"""Calibration problem bank: parametric problems whose answers are computed by brute force.

Purpose: a pool of problems with certain answers, large enough to produce
failures and same-family pairs for transfer tests, before any external
reference corpus is involved. Every problem asks for a single integer, so the
exact-match comparator is sufficient.

Answers are trivially computable by code. They only measure reasoning when the
solver runs with code_execution = false; record that honestly in the attempt.
"""
import json
import random
from math import gcd
from pathlib import Path

from . import vault
from .ledger import sha

TAIL = " Give the answer as a single integer."


def _incl_excl(rng, level):
    n = rng.choice([100, 200, 500][: level + 1]) * rng.randint(1, 4)
    ks = rng.sample([3, 4, 5, 6, 7, 9, 10, 11, 14, 15], 2 + (level >= 2))
    text = " or ".join(map(str, ks))
    ans = sum(i for i in range(1, n + 1) if any(i % k == 0 for k in ks))
    return f"Find the sum of all positive integers n <= {n} that are divisible by {text}.", ans


def _modpow(rng, level):
    a, b = rng.randint(2, 30 * level), rng.randint(20, 200 * level)
    m = rng.choice([7, 11, 13, 100, 1000][: 2 + level])
    return f"Find the remainder when {a}^{b} is divided by {m}.", pow(a, b, m)


def _lattice(rng, level):
    w, h = rng.randint(3, 3 + 2 * level), rng.randint(3, 3 + 2 * level)
    cells = [(x, y) for x in range(w + 1) for y in range(h + 1) if (x, y) not in ((0, 0), (w, h))]
    blocked = sorted(rng.sample(cells, level))
    ways = {}
    for x in range(w + 1):
        for y in range(h + 1):
            if (x, y) in blocked:
                ways[x, y] = 0
            elif (x, y) == (0, 0):
                ways[x, y] = 1
            else:
                ways[x, y] = ways.get((x - 1, y), 0) + ways.get((x, y - 1), 0)
    pts = ", ".join(f"({x},{y})" for x, y in blocked)
    return (f"A path moves from (0,0) to ({w},{h}) using unit steps right or up. "
            f"How many such paths avoid the point(s) {pts}?"), ways[w, h]


def _coprime(rng, level):
    n = rng.randint(200, 400) * level
    m = rng.choice([30, 42, 66, 70, 105, 210])
    k = rng.choice([3, 4, 5, 7])
    r = rng.randrange(k)
    ans = sum(1 for i in range(1, n + 1) if gcd(i, m) == 1 and i % k == r)
    return (f"How many positive integers n <= {n} satisfy both gcd(n, {m}) = 1 and "
            f"n leaves remainder {r} when divided by {k}?"), ans


def _digits(rng, level):
    n = rng.randint(300, 999) * 10 ** (level - 1)
    d = rng.choice([3, 4, 5, 7, 9])
    ans = sum(1 for i in range(1, n + 1) if sum(map(int, str(i))) % d == 0)
    return f"How many integers from 1 to {n} inclusive have a digit sum divisible by {d}?", ans


FAMILIES = {"incl_excl": _incl_excl, "modpow": _modpow, "lattice": _lattice,
            "coprime": _coprime, "digits": _digits}


def generate(home, n: int, seed: int, out_dir) -> list[dict]:
    """Write n problems to out_dir and their references to the vault. Returns the manifest."""
    v, h = vault.vault_dir(home).resolve(), Path(home).resolve()
    if v == h or h in v.parents:
        raise ValueError("set FMA_VAULT to a directory outside the apparatus before generating references")
    rng = random.Random(seed)
    out = Path(out_dir)
    (out / "problems").mkdir(parents=True, exist_ok=True)
    manifest, seen, names = [], set(), list(FAMILIES)
    while len(manifest) < n:
        i = len(manifest)
        family, level = names[i % len(names)], 1 + (i // len(names)) % 3
        statement, answer = FAMILIES[family](rng, level)
        if statement in seen:
            continue
        seen.add(statement)
        pid = f"CAL-{seed}-{i + 1:03d}-{family}"
        problem = {"problem_id": pid, "statement": statement + TAIL, "source": "calibration",
                   "family": family, "terrain": "T-calibration", "difficulty": f"L{min(level, 2)}",
                   "blind_reference": True}
        (out / "problems" / f"{pid}.json").write_text(json.dumps(problem, indent=2) + "\n")
        commitment = vault.seal(home, pid, {
            "result": str(answer),
            "provenance": f"fma.calibration brute force, seed {seed}, family {family}, level {level}"})
        manifest.append({"problem_id": pid, "family": family, "level": level,
                         "statement_hash": sha(problem["statement"]), "reference_commitment": commitment})
    (out / f"manifest-{seed}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
