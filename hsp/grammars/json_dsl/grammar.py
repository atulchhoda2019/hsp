"""JSON decisioning-expression grammar plugin.

Validates artifacts in five tiers; tiers 1-3 are implemented in M1, tiers 4-5
run once the eval harness (M2) and policy rules (M5) land. A `skip` tier result
means the tier is not configured, never that it passed.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

import jsonschema
import yaml

from hsp.core.plugin import GrammarPlugin
from hsp.core.report import Issue, Status, TierResult, ValidationReport

from .evaluator import evaluate as _evaluate

_PKG = "hsp.grammars.json_dsl"

_NUMERIC_OPS = {"lt", "le", "gt", "ge", "between"}


def _load_resource(name: str) -> Any:
    return resources.files(_PKG).joinpath(name).read_text()


class JsonDslGrammar(GrammarPlugin):
    grammar_id = "decisioning-expression"
    grammar_version = "1.0.0"

    def __init__(self) -> None:
        self._schema = json.loads(_load_resource("schema.json"))
        registry = yaml.safe_load(_load_resource("fields.yaml"))
        self._fields: dict[str, dict[str, Any]] = registry["fields"]

    def grammar_card(self) -> str:
        return _load_resource("grammar_card.md")

    def evaluate(self, artifact: str | dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
        expr = json.loads(artifact) if isinstance(artifact, str) else artifact
        return _evaluate(expr, case)

    def validate(self, artifact: str) -> ValidationReport:
        report = ValidationReport(self.grammar_id, self.grammar_version)
        parsed, tier1 = self._tier_schema(artifact)
        report.tiers.append(tier1)
        if parsed is None:
            report.tiers.append(TierResult(2, "compile", Status.SKIP))
            report.tiers.append(TierResult(3, "resolve", Status.SKIP))
            return report
        plan, tier2 = self._tier_compile(parsed)
        report.tiers.append(tier2)
        report.tiers.append(
            self._tier_resolve(parsed) if plan else TierResult(3, "resolve", Status.SKIP)
        )
        return report

    # --- tier 1: schema -----------------------------------------------------
    def _tier_schema(self, artifact: str) -> tuple[dict[str, Any] | None, TierResult]:
        try:
            parsed = json.loads(artifact)
        except json.JSONDecodeError as e:
            return None, TierResult(1, "schema", Status.FAIL, [
                Issue("invalid_json", f"artifact is not JSON: {e}")
            ])
        if not isinstance(parsed, dict):
            return None, TierResult(1, "schema", Status.FAIL, [
                Issue("not_object", "top-level artifact must be a JSON object")
            ])
        issues = [
            Issue("schema", e.message, path=".".join(str(p) for p in e.absolute_path))
            for e in jsonschema.Draft202012Validator(self._schema).iter_errors(parsed)
        ]
        return (parsed if not issues else None), TierResult(
            1, "schema", Status.PASS if not issues else Status.FAIL, issues
        )

    # --- tier 2: compile (build an executable plan) -------------------------
    def _tier_compile(self, expr: dict[str, Any]) -> tuple[bool, TierResult]:
        issues: list[Issue] = []
        for i, cond in enumerate(expr.get("conditions", [])):
            path = f"conditions.{i}"
            op, value = cond["op"], cond.get("value")
            if op == "between":
                lo, hi = value
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                           for v in (lo, hi)):
                    issues.append(Issue("between_not_numeric",
                                        "between bounds must be numbers", path))
                elif lo > hi:
                    issues.append(Issue("between_inverted",
                                        f"between lower bound {lo} > upper {hi}", path))
            elif op in _NUMERIC_OPS:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    issues.append(Issue("value_not_numeric",
                                        f"op {op} requires a numeric value", path))
        effect = expr["effect"]
        if "factor" in effect and "applies_to" not in effect:
            issues.append(Issue("factor_no_base",
                                "factor effects must declare applies_to",
                                "effect", severity="warning"))
        return not issues or all(i.severity != "error" for i in issues), TierResult(
            2, "compile",
            Status.FAIL if any(i.severity == "error" for i in issues) else Status.PASS,
            issues,
        )

    # --- tier 3: semantic resolution ----------------------------------------
    def _tier_resolve(self, expr: dict[str, Any]) -> TierResult:
        issues: list[Issue] = []
        jur, line = expr["jurisdiction"], expr["line"]
        for i, cond in enumerate(expr.get("conditions", [])):
            path = f"conditions.{i}"
            spec = self._fields.get(cond["field"])
            if spec is None:
                issues.append(Issue("unknown_field",
                                    f"field {cond['field']!r} not in report registry",
                                    path))
                continue
            issues += self._check_value(cond, spec, path)
            issues += self._check_jurisdiction(cond, jur, path)
            issues += self._check_line(cond, line, path)
        return TierResult(3, "resolve",
                          Status.FAIL if issues and any(
                              i.severity == "error" for i in issues) else Status.PASS,
                          issues)

    def _check_value(self, cond: dict[str, Any], spec: dict[str, Any], path: str) -> list[Issue]:
        op, value = cond["op"], cond.get("value")
        ftype = spec["type"]
        if op in ("exists", "not_exists"):
            return []
        values = value if op in ("in", "not_in", "between") else [value]

        def compatible(v: Any) -> bool:
            if ftype == "boolean":
                return isinstance(v, bool)
            if ftype == "string":
                return isinstance(v, str)
            return isinstance(v, (int, float)) and not isinstance(v, bool)

        issues: list[Issue] = []
        for v in values:
            if not compatible(v):
                issues.append(Issue("type_mismatch",
                                    f"value {v!r} incompatible with field type {ftype}",
                                    path))
                continue
            if "enum" in spec and v not in spec["enum"]:
                issues.append(Issue("enum_violation",
                                    f"{v!r} not in {spec['enum']}", path))
            if "minimum" in spec and isinstance(v, (int, float)) and v < spec["minimum"]:
                issues.append(Issue("range_violation",
                                    f"{v} below field minimum {spec['minimum']}", path))
            if "maximum" in spec and isinstance(v, (int, float)) and v > spec["maximum"]:
                issues.append(Issue("range_violation",
                                    f"{v} above field maximum {spec['maximum']}", path))
        return issues

    @staticmethod
    def _check_jurisdiction(cond: dict[str, Any], jur: str, path: str) -> list[Issue]:
        if cond["field"] != "policy.state":
            return []
        if cond["op"] == "eq" and jur != "ALL" and cond.get("value") != jur:
            return [Issue("jurisdiction_mismatch",
                          f"expression jurisdiction {jur} but condition requires "
                          f"state {cond['value']}", path)]
        if cond["op"] == "not_in" and jur != "ALL" and jur in (cond.get("value") or []):
            return [Issue("jurisdiction_excluded",
                          f"expression jurisdiction {jur} is excluded by condition",
                          path)]
        return []

    _LINE_FIELDS = {
        "personal_auto": ("mvr.", "vehicle.", "policy.", "applicant.", "loss_history."),
        "commercial_auto": ("mvr.", "vehicle.", "policy.", "applicant.", "loss_history."),
        "homeowners": ("property.", "policy.", "applicant.", "loss_history."),
        "renters": ("property.", "policy.", "applicant.", "loss_history."),
    }

    def _check_line(self, cond: dict[str, Any], line: str, path: str) -> list[Issue]:
        if not cond["field"].startswith(self._LINE_FIELDS[line]):
            return [Issue("field_not_in_line",
                          f"field {cond['field']!r} has no namespace in line {line!r}",
                          path)]
        return []
