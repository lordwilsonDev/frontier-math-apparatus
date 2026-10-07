"""Dependency-free validator for the subset of JSON Schema used in schemas/."""
import json
import os
from pathlib import Path

SCHEMA_DIR = Path(os.environ.get("FMA_SCHEMAS") or Path(__file__).resolve().parents[2] / "schemas")

_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


class ValidationError(ValueError):
    pass


def load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def validate(obj, schema, path: str = "$") -> None:
    """Raise ValidationError listing every violation. `schema` is a dict or a schema file name."""
    if isinstance(schema, str):
        schema = load(schema)
    errs: list[str] = []
    _check(obj, schema, path, errs)
    if errs:
        raise ValidationError("; ".join(errs))


def _check(o, s: dict, p: str, errs: list) -> None:
    if "$ref" in s:
        s = load(s["$ref"])
    t = s.get("type")
    if t:
        ok = isinstance(o, _TYPES[t])
        if t in ("integer", "number") and isinstance(o, bool):
            ok = False
        if not ok:
            errs.append(f"{p}: expected {t}, got {type(o).__name__}")
            return
    if "enum" in s and o not in s["enum"]:
        errs.append(f"{p}: {o!r} not in {s['enum']}")
    if "const" in s and o != s["const"]:
        errs.append(f"{p}: must equal {s['const']!r}")
    if "minimum" in s and isinstance(o, (int, float)) and o < s["minimum"]:
        errs.append(f"{p}: below minimum {s['minimum']}")
    if "minLength" in s and isinstance(o, str) and len(o.strip()) < s["minLength"]:
        errs.append(f"{p}: shorter than {s['minLength']} characters")
    if "minItems" in s and isinstance(o, list) and len(o) < s["minItems"]:
        errs.append(f"{p}: needs at least {s['minItems']} item(s)")
    if isinstance(o, dict):
        for k in s.get("required", []):
            if k not in o:
                errs.append(f"{p}: missing required '{k}'")
        for k, sub in s.get("properties", {}).items():
            if k in o:
                _check(o[k], sub, f"{p}.{k}", errs)
    if isinstance(o, list) and "items" in s:
        for i, item in enumerate(o):
            _check(item, s["items"], f"{p}[{i}]", errs)
