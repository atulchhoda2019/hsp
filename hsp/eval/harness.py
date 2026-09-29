"""Eval harness: replay requirement → expected cases through the pipeline.

Each case file (YAML) declares a requirement plus expectations:
  expect: {jurisdiction, line, effect_type, must_have_fields, golden: [{report,
           matched, effect_factor}]}

Metrics per run: validity rate (artifact passed all tiers), first-pass rate,
mean repair depth, structural-match rate, golden-case pass rate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hsp.corpus.store import Corpus
from hsp.core.plugin import GrammarPlugin
from hsp.pipeline import generate
from hsp.provider.base import Provider


@dataclass
class CaseResult:
    case_id: str
    valid: bool
    first_pass: bool
    attempts: int
    structural_match: bool
    golden_pass: int = 0
    golden_total: int = 0
    detail: str = ""


@dataclass
class EvalReport:
    cases: list[CaseResult] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        n = len(self.cases) or 1
        golden_p = sum(c.golden_pass for c in self.cases)
        golden_t = sum(c.golden_total for c in self.cases) or 1
        return {
            "cases": len(self.cases),
            "validity_rate": sum(c.valid for c in self.cases) / n,
            "first_pass_rate": sum(c.first_pass for c in self.cases) / n,
            "mean_attempts": sum(c.attempts for c in self.cases) / n,
            "structural_match_rate": sum(c.structural_match for c in self.cases) / n,
            "golden_rate": golden_p / golden_t,
        }


def run_cases(cases_dir: str | Path, *, plugin: GrammarPlugin, corpus: Corpus,
              provider: Provider) -> EvalReport:
    report = EvalReport()
    for path in sorted(Path(cases_dir).glob("*.yaml")):
        case = yaml.safe_load(path.read_text())
        report.cases.append(_run_case(case, plugin=plugin, corpus=corpus,
                                      provider=provider))
    return report


def _run_case(case: dict, *, plugin, corpus, provider) -> CaseResult:
    res = generate(case["requirement"], plugin=plugin, corpus=corpus,
                   provider=provider, source_refs=case.get("source_refs", []))
    b = res.bundle
    valid = b.status == "PROPOSED"
    first_pass = valid and b.provenance.attempts == 1

    exp = case.get("expect", {})
    art = b.artifact
    structural = valid and all([
        exp.get("jurisdiction") in (None, art.get("jurisdiction")),
        exp.get("line") in (None, art.get("line")),
        exp.get("effect_type") in (None, art.get("effect", {}).get("type")),
        all(f in {c["field"] for c in art.get("conditions", [])}
            for f in exp.get("must_have_fields", [])),
    ])

    golden_pass = golden_total = 0
    if valid:
        for g in exp.get("golden", []):
            golden_total += 1
            out = plugin.evaluate(art, g["report"])
            ok = out["matched"] == g.get("matched", True)
            if ok and "effect_factor" in g and out["effect"]:
                ok = out["effect"].get("factor") == g["effect_factor"]
            golden_pass += ok

    return CaseResult(
        case_id=case["id"],
        valid=valid,
        first_pass=first_pass,
        attempts=b.provenance.attempts,
        structural_match=bool(structural),
        golden_pass=golden_pass,
        golden_total=golden_total,
        detail="" if valid else json.dumps(
            [i.code for i in b.validation.issues])[:200],
    )
