"""Evaluator tests over synthetic report vectors."""

from hsp.grammars.json_dsl.evaluator import evaluate


def _expr(conditions, logic="all"):
    return {
        "expression_id": "t",
        "version": 1,
        "jurisdiction": "CA",
        "line": "personal_auto",
        "condition_logic": logic,
        "conditions": conditions,
        "effect": {"type": "surcharge", "factor": 1.25, "applies_to": "base_premium"},
    }


def test_match_returns_effect():
    expr = _expr([
        {"field": "policy.state", "op": "eq", "value": "CA"},
        {"field": "mvr.major_violations_3y", "op": "ge", "value": 1},
    ])
    report = {"policy": {"state": "CA"}, "mvr": {"major_violations_3y": 2}}
    out = evaluate(expr, report)
    assert out["matched"] and out["effect"]["factor"] == 1.25


def test_no_match_returns_null_effect():
    expr = _expr([{"field": "mvr.dui_convictions_5y", "op": "ge", "value": 1}])
    out = evaluate(expr, {"mvr": {"dui_convictions_5y": 0}})
    assert not out["matched"] and out["effect"] is None


def test_missing_field_is_false():
    expr = _expr([{"field": "vehicle.safety_rating", "op": "ge", "value": 4}])
    assert not evaluate(expr, {"policy": {"state": "CA"}})["matched"]


def test_any_logic():
    expr = _expr(
        [{"field": "vehicle.use", "op": "eq", "value": "business"},
         {"field": "vehicle.annual_mileage", "op": "gt", "value": 50000}],
        logic="any",
    )
    assert evaluate(expr, {"vehicle": {"use": "commute",
                                       "annual_mileage": 60000}})["matched"]
    assert not evaluate(expr, {"vehicle": {"use": "commute",
                                           "annual_mileage": 9000}})["matched"]


def test_operators():
    report = {"applicant": {"age": 20, "synthetic_score_band": "B"},
              "policy": {"state": "TX"}}
    cases = [
        ({"field": "applicant.age", "op": "between", "value": [16, 25]}, True),
        ({"field": "applicant.age", "op": "between", "value": [25, 30]}, False),
        ({"field": "policy.state", "op": "in", "value": ["CA", "TX"]}, True),
        ({"field": "policy.state", "op": "not_in", "value": ["NY"]}, True),
        ({"field": "applicant.synthetic_score_band", "op": "ne", "value": "A"}, True),
        ({"field": "mvr.dui_convictions_5y", "op": "not_exists"}, True),
        ({"field": "policy.state", "op": "exists"}, True),
    ]
    for cond, expected in cases:
        assert evaluate(_expr([cond]), report)["matched"] is expected, cond


def test_wrong_type_comparison_is_false_not_crash():
    expr = _expr([{"field": "applicant.age", "op": "gt", "value": 25}])
    assert not evaluate(expr, {"applicant": {"age": "twenty"}})["matched"]
