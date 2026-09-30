"""Tier-1 schema tests: exemplars validate; malformed artifacts fail."""

import pytest

from tests.conftest import dumps


def test_all_exemplars_pass_tier1(grammar, exemplars):
    assert len(exemplars) == 14
    for name, text in exemplars.items():
        report = grammar.validate(text)
        assert report.tiers[0].status.value == "pass", f"{name}: {report.tiers[0].issues}"


def test_exemplars_fully_valid(grammar, exemplars):
    for name, text in exemplars.items():
        report = grammar.validate(text)
        assert report.ok, f"{name}: {[i.message for i in report.issues]}"


def test_rejects_non_json(grammar):
    report = grammar.validate("{not json")
    assert not report.ok
    assert report.tiers[0].issues[0].code == "invalid_json"
    assert report.tiers[1].status.value == "skip"


def test_rejects_unknown_top_level_key(grammar, artifact):
    artifact["surprise"] = True
    assert not grammar.validate(dumps(artifact)).ok


def test_rejects_missing_required_key(grammar, artifact):
    del artifact["effect"]
    assert not grammar.validate(dumps(artifact)).ok


@pytest.mark.parametrize("effect,why", [
    ({"type": "surcharge", "factor": 0.9, "applies_to": "base_premium"},
     "surcharge factor must be > 1"),
    ({"type": "discount", "factor": 1.1, "applies_to": "base_premium"},
     "discount factor must be < 1"),
    ({"type": "surcharge"}, "surcharge requires factor"),
    ({"type": "eligibility", "factor": 1.2}, "eligibility requires decision"),
    ({"type": "eligibility", "decision": "MAYBE"}, "decision enum"),
])
def test_effect_semantics(grammar, artifact, effect, why):
    artifact["effect"] = effect
    report = grammar.validate(dumps(artifact))
    assert not report.ok, why


def test_bad_op_and_missing_value(grammar, artifact):
    artifact["conditions"][0]["op"] = "approximately"
    assert not grammar.validate(dumps(artifact)).ok
    artifact["conditions"][0]["op"] = "gt"
    del artifact["conditions"][0]["value"]
    assert not grammar.validate(dumps(artifact)).ok
