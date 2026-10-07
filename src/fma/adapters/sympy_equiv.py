"""Optional symbolic-equivalence adapter (needs `pip install sympy`).

Handles closed-form expressions and `lhs = rhs` equations only. It can confirm
equivalence; it never declares a mismatch, because failing to simplify a
difference to zero is not evidence that two results differ.
"""
import re

from ..compare import Comparison

# sympy's parser evaluates its input, so only plain math text gets through.
_SAFE = re.compile(r"^[0-9A-Za-z_+\-*/^().,= \t]{1,400}$")


def _parse(text: str):
    from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application,
                                            parse_expr, standard_transformations)
    if not _SAFE.match(text) or "__" in text:
        return None
    transforms = standard_transformations + (implicit_multiplication_application, convert_xor)
    parts = text.split("=")
    if len(parts) > 2:
        return None
    try:
        exprs = [parse_expr(p.strip(), transformations=transforms) for p in parts]
    except Exception:
        return None
    return exprs[0] - exprs[1] if len(exprs) == 2 else exprs[0]


def equivalent(solver_result: str, reference_result: str):
    from sympy import simplify
    a, b = _parse(solver_result), _parse(reference_result)
    if a is None or b is None:
        return None
    is_equation = "=" in solver_result or "=" in reference_result
    if is_equation and not ("=" in solver_result and "=" in reference_result):
        return None
    try:
        if simplify(a - b) == 0:
            return Comparison.EQUIVALENT_RESULT, "sympy: simplify(solver - reference) == 0"
        if is_equation and simplify(a + b) == 0:
            return Comparison.EQUIVALENT_RESULT, "sympy: equations agree up to swapping sides"
    except Exception:
        return None
    return None
