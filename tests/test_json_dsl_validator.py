"""Validator tiers 2-3: compile plan + semantic resolution."""

from tests.conftest import dumps


def _errors(report, tier):
    return [i.code for i in report.tiers[tier - 1].errors]


def _warnings(report, tier):
    return [i.code for i in report.tiers[tier - 1].warnings]


def test_clean_artifact_passes_all_tiers(grammar, artifact):
    report = grammar.validate(dumps(artifact))
    assert report.ok
    assert [t.status.value for t in report.tiers] == ["pass", "pass", "pass"]


def test_tier2_between_inverted(grammar, artifact):
    artifact["conditions"][1] = {"field": "applicant.age", "op": "between",
                                 "value": [30, 18]}
    report = grammar.validate(dumps(artifact))
    assert "between_inverted" in _errors(report, 2)


def test_tier2_numeric_op_rejects_string(grammar, artifact):
    artifact["conditions"][1] = {"field": "applicant.age", "op": "gt",
                                 "value": "old"}
    report = grammar.validate(dumps(artifact))
    assert "value_not_numeric" in _errors(report, 2)


def test_tier2_factor_without_applies_to_warns(grammar, artifact):
    del artifact["effect"]["applies_to"]
    report = grammar.validate(dumps(artifact))
    assert report.ok
    assert "factor_no_base" in _warnings(report, 2)


def test_tier3_unknown_field(grammar, artifact):
    artifact["conditions"][1] = {"field": "bureau.real_score", "op": "gt", "value": 700}
    report = grammar.validate(dumps(artifact))
    assert "unknown_field" in _errors(report, 3)


def test_tier3_type_mismatch(grammar, artifact):
    artifact["conditions"][1] = {"field": "applicant.age", "op": "eq",
                                 "value": "thirty"}
    report = grammar.validate(dumps(artifact))
    assert "type_mismatch" in _errors(report, 3)


def test_tier3_enum_and_range(grammar, artifact):
    artifact["conditions"][1] = {"field": "vehicle.safety_rating", "op": "eq", "value": 9}
    report = grammar.validate(dumps(artifact))
    assert "range_violation" in _errors(report, 3)


def test_tier3_jurisdiction_mismatch(grammar, artifact):
    artifact["conditions"][0]["value"] = "TX"
    report = grammar.validate(dumps(artifact))
    assert "jurisdiction_mismatch" in _errors(report, 3)


def test_tier3_line_field_scope(grammar, artifact):
    artifact["conditions"][1] = {"field": "property.wildfire_score", "op": "gt",
                                 "value": 60}
    report = grammar.validate(dumps(artifact))
    assert "field_not_in_line" in _errors(report, 3)


def test_digest_is_stable_and_canonical(grammar, artifact):
    a = dumps(artifact)
    reordered = dumps(dict(reversed(list(artifact.items()))))
    assert grammar.digest(a) == grammar.digest(reordered)
