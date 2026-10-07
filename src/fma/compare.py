import re
from enum import Enum


class Comparison(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    EQUIVALENT_RESULT = "EQUIVALENT_RESULT"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    DIFFERENT_FORM = "DIFFERENT_FORM"
    CONDITIONAL_MATCH = "CONDITIONAL_MATCH"
    MISMATCH = "MISMATCH"
    UNRESOLVED = "UNRESOLVED"


_INT = re.compile(r"^[+-]?\d+$")
MATCHES = {Comparison.EXACT_MATCH.value, Comparison.EQUIVALENT_RESULT.value}


def compare_textual(solver_result: str, reference_result: str) -> Comparison:
    """Conservative baseline comparator; semantic equivalence requires a domain adapter."""
    if solver_result.strip() == reference_result.strip():
        return Comparison.EXACT_MATCH
    return Comparison.UNRESOLVED


def compare_with_adapter(name: str, solver_result: str, reference_result: str):
    """Return (Comparison, basis) from a named equivalence adapter, or None if it cannot decide."""
    if name == "integer":
        # Two bare integers are either the same number or a genuine mismatch.
        a, b = solver_result.strip(), reference_result.strip()
        if _INT.match(a) and _INT.match(b):
            if int(a) == int(b):
                return Comparison.EQUIVALENT_RESULT, "integer: equal as integers"
            return Comparison.MISMATCH, "integer: both results are bare integers and they differ"
        return None
    if name == "sympy":
        from .adapters import sympy_equiv
        return sympy_equiv.equivalent(solver_result, reference_result)
    raise ValueError(f"unknown comparison adapter: {name}")
