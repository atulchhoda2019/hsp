"""Deterministic evaluator for decisioning-expression artifacts.

Input is a synthetic report dict keyed by the dotted field paths declared in
fields.yaml, e.g. {"mvr": {"major_violations_3y": 1}, "policy": {"state": "CA"}}.

Semantics:
  - missing field          -> condition is False (except exists/not_exists)
  - type mismatch at eval  -> condition is False; validation tier 3 catches it earlier
  - all conditions pass    -> expression matched; effect applies
"""

from __future__ import annotations

from typing import Any

MISSING = object()


def _lookup(report: dict[str, Any], dotted: str) -> Any:
    node: Any = report
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return MISSING
        node = node[part]
    return node


def _cmp(op: str, actual: Any, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op in ("lt", "le", "gt", "ge", "between"):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False
        if op == "between":
            lo, hi = expected
            return lo <= actual <= hi
        if not isinstance(expected, (int, float)) or isinstance(expected, bool):
            return False
        return {"lt": actual < expected, "le": actual <= expected,
                "gt": actual > expected, "ge": actual >= expected}[op]
    if op == "in":
        return isinstance(expected, list) and actual in expected
    if op == "not_in":
        return isinstance(expected, list) and actual not in expected
    raise ValueError(f"unknown op {op!r}")


def eval_condition(cond: dict[str, Any], report: dict[str, Any]) -> bool:
    actual = _lookup(report, cond["field"])
    op = cond["op"]
    if op == "exists":
        return actual is not MISSING
    if op == "not_exists":
        return actual is MISSING
    if actual is MISSING:
        return False
    return _cmp(op, actual, cond.get("value"))


def evaluate(expression: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Return {"matched": bool, "effect": dict | None} for one report."""
    conditions = expression["conditions"]
    logic = expression.get("condition_logic", "all")
    results = [eval_condition(c, report) for c in conditions]
    matched = all(results) if logic == "all" else any(results)
    return {
        "matched": matched,
        "effect": expression["effect"] if matched else None,
    }
