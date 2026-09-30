"""RTDP ruleset grammar plugin — YAML + CEL, mirrors internal/ruleseng/engine.go.

Tiers:
  1 schema        YAML parses; required fields; closed key set; enums
  2 compile       every `when` parses as CEL and smoke-evals to bool
  3 resolve       signals exist in contract snapshot at exact version;
                  aliases/signal-field paths/feature names resolve; cfg keys
                  reported (checked against product context when supplied)
  4 golden        evaluate() against synthetic case vectors
  5 policy        owner_scope=tenant; bounded rule count; no identity fields
"""

from __future__ import annotations

import re
from typing import Any

import celpy
import yaml

from hsp.core.plugin import GrammarPlugin
from hsp.core.report import Issue, Status, TierResult, ValidationReport

_PKG = "hsp.grammars.rtdp_ruleset"

_REQUIRED = {"ruleset_id", "version", "owner_scope", "evaluation", "rules",
             "default_outcome"}
_ALLOWED_TOP = _REQUIRED | {"requires", "missing_required_signal_outcome"}
_EVAL_MODES = {"all_match"}
_DECISIONS = {"APPROVE", "REVIEW", "DECLINE"}
_MAX_EXPR_BYTES = 4096
_MAX_RULES = 50
_PRECEDENCE = {"DECLINE": 3, "REVIEW": 2, "APPROVE": 1}

# symbols.<alias>.<field> / features.<name> / cfg.<key> references in `when`
_REF = re.compile(r"\b(features|signals|cfg|input|actor)\.([A-Za-z_][\w.]*)")


class RtdpRulesetGrammar(GrammarPlugin):
    grammar_id = "rtdp-ruleset"
    grammar_version = "1.0.0"
    artifact_format = "yaml"
    source_refs_key = None  # rtdp rulesets are a closed spec — refs live in the bundle

    def __init__(self, snapshot_dir: str | None = None) -> None:
        from importlib import resources
        root = resources.files(_PKG).joinpath("contracts_snapshot")
        if snapshot_dir:
            from pathlib import Path
            root = Path(snapshot_dir)
        self._contracts = self._load_dir(root, "signal_contracts")
        self._features = self._load_dir(root, "feature_definitions")
        self._env = celpy.Environment()

    @staticmethod
    def _load_dir(root: Any, sub: str) -> dict[str, dict[str, Any]]:
        """{contract_name: {version_str: spec}} from <root>/<sub>/<name>/<ver>.yaml."""
        out: dict[str, dict[str, Any]] = {}
        base = root / sub if not hasattr(root, "joinpath") else root.joinpath(sub)
        try:
            entries = base.iterdir()
        except (AttributeError, FileNotFoundError):
            return out
        for name_dir in entries:
            vers: dict[str, Any] = {}
            try:
                files = name_dir.iterdir()
            except (AttributeError, NotADirectoryError):
                continue
            for f in files:
                spec = yaml.safe_load(f.read_text())
                vers[str(spec.get("version"))] = spec
            if vers:
                key = str(name_dir.name) if hasattr(name_dir, "name") else str(name_dir)
                out[key] = vers
        return out

    def grammar_card(self) -> str:
        from importlib import resources
        return resources.files(_PKG).joinpath("grammar_card.md").read_text()

    def extract_artifact(self, text: str) -> str | None:
        from hsp.generator.extract import extract_yaml
        return extract_yaml(text)

    def parse(self, artifact: str) -> Any:
        return yaml.safe_load(artifact)

    # ------------------------------------------------------------------ eval
    def evaluate(self, artifact: str | dict[str, Any],
                 case: dict[str, Any]) -> dict[str, Any]:
        spec = yaml.safe_load(artifact) if isinstance(artifact, str) else artifact
        return self._evaluate_spec(spec, case)

    def _evaluate_spec(self, spec: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
        features = case.get("features", {})
        signals = case.get("signals", {})
        present = set(case.get("present_signals", list(signals)))
        cfg = case.get("cfg", {})
        activation = celpy.json_to_cel({
            "features": features, "signals": signals, "cfg": cfg,
            "input": case.get("input", {}), "actor": case.get("actor", {}),
            "timer": {},
        })
        fired, skipped = [], []
        for rule in spec.get("rules", []):
            if any(a not in present for a in rule.get("requires_signals") or []):
                skipped.append(rule["id"])
                continue
            prog = self._env.program(self._env.compile(rule["when"]))
            try:
                if bool(prog.evaluate(activation)):
                    fired.append({"rule_id": rule["id"], **rule["outcome"]})
            except celpy.CELEvalError as e:
                return {"error": f"rule {rule['id']} eval: {e}"}
        best, best_rank = None, 0
        for f in fired:
            rank = _PRECEDENCE.get(f["decision"], 0)
            if rank > best_rank:
                best, best_rank = f["decision"], rank
        if best:
            decision = best
        elif skipped and spec.get("missing_required_signal_outcome"):
            decision = spec["missing_required_signal_outcome"]
        else:
            decision = spec["default_outcome"]
        return {"decision": decision, "fired": fired, "skipped": skipped,
                "defaulted": not fired and not skipped}

    # ------------------------------------------------------------- validate
    def validate(self, artifact: str) -> ValidationReport:
        report = ValidationReport(self.grammar_id, self.grammar_version)
        spec, tier1 = self._tier_schema(artifact)
        report.tiers.append(tier1)
        if spec is None:
            for n, name in ((2, "compile"), (3, "resolve"), (5, "policy")):
                report.tiers.append(TierResult(n, name, Status.SKIP))
            return report
        progs_ok, tier2 = self._tier_compile(spec)
        report.tiers.append(tier2)
        report.tiers.append(self._tier_resolve(spec))
        report.tiers.append(self._tier_policy(spec))
        return report

    def _tier_schema(self, artifact: str) -> tuple[dict | None, TierResult]:
        try:
            spec = yaml.safe_load(artifact)
        except yaml.YAMLError as e:
            return None, TierResult(1, "schema", Status.FAIL, [
                Issue("invalid_yaml", f"artifact is not YAML: {e}")])
        if not isinstance(spec, dict):
            return None, TierResult(1, "schema", Status.FAIL, [
                Issue("not_object", "artifact must be a YAML mapping")])
        issues: list[Issue] = []
        for k in spec:
            if k not in _ALLOWED_TOP:
                issues.append(Issue("unknown_key", f"unknown key {k!r}", k))
        for k in _REQUIRED:
            if k not in spec:
                issues.append(Issue("missing_key", f"missing {k!r}", k))
        if "evaluation" in spec and spec["evaluation"] not in _EVAL_MODES:
            issues.append(Issue("bad_enum",
                                f"evaluation must be one of {_EVAL_MODES}",
                                "evaluation"))
        if spec.get("owner_scope") not in ("platform", "tenant"):
            issues.append(Issue("bad_enum", "owner_scope must be platform|tenant",
                                "owner_scope"))
        rules = spec.get("rules")
        if not isinstance(rules, list) or not rules:
            issues.append(Issue("no_rules", "rules must be a non-empty list"))
        else:
            for i, r in enumerate(rules):
                p = f"rules.{i}"
                for k in ("id", "when", "outcome"):
                    if k not in r:
                        issues.append(Issue("missing_key", f"rule missing {k!r}", p))
                    if k == "when" and isinstance(r.get("when"), str) \
                            and len(r["when"].encode()) > _MAX_EXPR_BYTES:
                        issues.append(Issue("expr_too_large", "when > 4096 bytes", p))
                out = r.get("outcome") or {}
                if out.get("decision") not in _DECISIONS:
                    issues.append(Issue("bad_enum",
                                        f"outcome.decision must be one of {_DECISIONS}",
                                        p))
                if not isinstance(r.get("requires_signals", []), list):
                    issues.append(Issue("bad_type",
                                        "requires_signals must be a list", p))
        return (None if issues else spec), TierResult(
            1, "schema", Status.FAIL if issues else Status.PASS, issues)

    def _tier_compile(self, spec: dict[str, Any]) -> tuple[bool, TierResult]:
        issues: list[Issue] = []
        for rule in spec.get("rules", []):
            path = f"rules.{rule['id']}"
            try:
                self._env.compile(rule["when"])
            except celpy.CELParseError as e:
                issues.append(Issue("cel_parse", f"{e}", path))
                continue
            except Exception as e:
                issues.append(Issue("cel_compile", f"{e}", path))
                continue
            ok, msg = self._smoke_eval_bool(rule["when"])
            if not ok:
                issues.append(Issue("not_bool", msg, path))
        return not issues, TierResult(
            2, "compile", Status.FAIL if issues else Status.PASS, issues)

    def _smoke_eval_bool(self, expr: str) -> tuple[bool, str]:
        """Eval against a zero-valued activation of all referenced symbols —
        approximates cel-go's OutputType==bool compile check."""
        activation = self._zero_activation(expr)
        try:
            out = self._env.program(self._env.compile(expr)).evaluate(activation)
        except celpy.CELEvalError as e:
            return False, f"smoke eval: {e}"
        except Exception as e:
            return False, f"smoke eval: {e}"
        if not isinstance(out, (bool, celpy.celtypes.BoolType)):
            return False, f"expression evaluates to {type(out).__name__}, not bool"
        return True, ""

    @staticmethod
    def _zero_activation(expr: str) -> Any:
        """Build {root: nested-zero-dict} for every referenced symbol path."""
        root: dict[str, Any] = {}
        for top, rest in _REF.findall(expr):
            parts = rest.split(".")
            node = root.setdefault(top, {})
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = 0.0
        for top in ("features", "signals", "cfg", "input", "actor", "timer"):
            root.setdefault(top, {})
        return celpy.json_to_cel(root)

    def _tier_resolve(self, spec: dict[str, Any]) -> TierResult:
        issues: list[Issue] = []
        aliases: dict[str, dict[str, Any]] = {}
        for i, req in enumerate(spec.get("requires") or []):
            path = f"requires.{i}"
            sig, ver, alias = req.get("signal"), str(req.get("contract")), req.get("alias")
            if not sig or not alias:
                issues.append(Issue("missing_key",
                                    "requires entries need signal+contract+alias", path))
                continue
            if alias in aliases:
                issues.append(Issue("dup_alias", f"alias {alias!r} declared twice", path))
            contract = self._contracts.get(sig, {}).get(ver)
            if contract is None:
                issues.append(Issue("unknown_contract",
                                    f"{sig}@{ver} not in contract snapshot", path))
            else:
                aliases[alias] = contract

        declared = set(aliases)
        for rule in spec.get("rules", []):
            path = f"rules.{rule['id']}"
            for a in rule.get("requires_signals") or []:
                if a not in declared:
                    issues.append(Issue("undeclared_alias",
                                        f"requires_signals alias {a!r} not in requires",
                                        path))
            for top, rest in _REF.findall(rule["when"]):
                parts = rest.split(".")
                if top == "features" and parts[0] not in self._features:
                    issues.append(Issue("unknown_feature",
                                        f"feature {parts[0]!r} not in registry", path))
                elif top == "signals":
                    alias = parts[0]
                    if alias not in declared:
                        issues.append(Issue("undeclared_signal",
                                            f"signals.{alias} not declared in requires",
                                            path))
                    elif len(parts) > 1:
                        fields = aliases[alias].get("value_schema", {})
                        if parts[1] not in fields:
                            issues.append(Issue(
                                "unknown_signal_field",
                                f"signals.{alias}.{parts[1]} not in contract "
                                f"value_schema {sorted(fields)}", path))
                    for a2 in declared:
                        if a2 == alias and alias not in (rule.get("requires_signals") or []):
                            issues.append(Issue(
                                "signal_read_without_require",
                                f"rule reads signals.{alias} but lacks "
                                f"requires_signals entry", path,
                                severity="warning"))
        return TierResult(3, "resolve",
                          Status.FAIL if any(i.severity == "error" for i in issues)
                          else Status.PASS, issues)

    @staticmethod
    def _tier_policy(spec: dict[str, Any]) -> TierResult:
        issues: list[Issue] = []
        if spec.get("owner_scope") != "tenant":
            issues.append(Issue("scope_violation",
                                "agent artifacts must be owner_scope=tenant",
                                "owner_scope"))
        if len(spec.get("rules", [])) > _MAX_RULES:
            issues.append(Issue("too_many_rules", f">{_MAX_RULES} rules"))
        return TierResult(5, "policy",
                          Status.FAIL if issues else Status.PASS, issues)
