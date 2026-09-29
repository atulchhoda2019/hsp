"""Eval harness smoke test — fixture provider answering with a valid artifact."""

import json

import yaml

from hsp.eval.harness import run_cases
from hsp.provider.fixture import FixtureProvider

GOOD = json.dumps({
    "expression_id": "ca_eval_surcharge",
    "version": 1,
    "jurisdiction": "CA",
    "line": "personal_auto",
    "conditions": [
        {"field": "policy.state", "op": "eq", "value": "CA"},
        {"field": "mvr.major_violations_3y", "op": "ge", "value": 1},
    ],
    "effect": {"type": "surcharge", "factor": 1.25, "applies_to": "base_premium"},
})


def test_harness_metrics(grammar, exemplar_corpus, tmp_path):
    case = {
        "id": "t1",
        "requirement": "CA auto surcharge for major violations",
        "expect": {
            "jurisdiction": "CA", "line": "personal_auto",
            "effect_type": "surcharge",
            "must_have_fields": ["mvr.major_violations_3y"],
            "golden": [{
                "report": {"policy": {"state": "CA"},
                           "mvr": {"major_violations_3y": 3}},
                "matched": True, "effect_factor": 1.25}],
        },
    }
    (tmp_path / "t1.yaml").write_text(yaml.dump(case))
    # canned: any prompt returns the good artifact
    rep = run_cases(tmp_path, plugin=grammar, corpus=exemplar_corpus,
                    provider=FixtureProvider(responses=[GOOD]))
    s = rep.summary()
    assert s["cases"] == 1 and s["validity_rate"] == 1.0
    assert s["first_pass_rate"] == 1.0 and s["golden_rate"] == 1.0
    assert s["structural_match_rate"] == 1.0


def test_harness_records_failures(grammar, exemplar_corpus, tmp_path):
    case = {"id": "bad", "requirement": "x",
            "expect": {"jurisdiction": "CA"}}
    (tmp_path / "bad.yaml").write_text(yaml.dump(case))
    rep = run_cases(tmp_path, plugin=grammar, corpus=exemplar_corpus,
                    provider=FixtureProvider(responses=["{}", "{}", "{}"]))
    c = rep.cases[0]
    assert not c.valid and c.attempts == 3
    assert rep.summary()["validity_rate"] == 0.0
