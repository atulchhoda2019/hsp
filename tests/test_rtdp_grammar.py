"""RTDP ruleset grammar plugin tests — schema, CEL compile, resolve, golden."""

import textwrap
from pathlib import Path

import pytest

from hsp.grammars.rtdp_ruleset import RtdpRulesetGrammar

CORPUS = Path(__file__).parent.parent / "corpus" / "exemplars" / "rtdp_ruleset"


@pytest.fixture(scope="session")
def rtdp() -> RtdpRulesetGrammar:
    return RtdpRulesetGrammar()


GOOD = textwrap.dedent("""\
    ruleset_id: tenant_test_gate
    version: 1
    owner_scope: tenant
    requires:
      - signal: claim.fraud_probability
        contract: "1.1.0"
        alias: fraud
        optional: false
    evaluation: all_match
    rules:
      - id: hi_fraud_decline
        when: "signals.fraud.probability >= cfg.decline_p"
        outcome: {decision: DECLINE, reason: HIGH_FRAUD}
        requires_signals: [fraud]
      - id: velocity_review
        when: "features.claimant_claim_count_1h > cfg.vel_max"
        outcome: {decision: REVIEW, reason: VELOCITY}
        requires_signals: []
    default_outcome: APPROVE
    missing_required_signal_outcome: REVIEW
""")


def test_exemplars_valid(rtdp):
    for p in sorted(CORPUS.glob("*.yaml")):
        report = rtdp.validate(p.read_text())
        assert report.ok, f"{p.name}: {[i.message for i in report.issues]}"


def test_good_artifact_all_tiers(rtdp):
    report = rtdp.validate(GOOD)
    assert report.ok, [i.message for i in report.issues]
    assert [t.status.value for t in report.tiers] == ["pass"] * 4


def test_bad_yaml_fails_schema(rtdp):
    report = rtdp.validate("ruleset_id: [unclosed")
    assert not report.ok


def test_bad_cel_fails_compile(rtdp):
    bad = GOOD.replace("signals.fraud.probability >= cfg.decline_p",
                       "signals.fraud.probability =>> cfg.decline_p")
    report = rtdp.validate(bad)
    assert not report.ok
    assert any(i.code in ("cel_parse", "cel_compile")
               for i in report.tiers[1].issues)


def test_non_bool_expr_fails_compile(rtdp):
    bad = GOOD.replace("signals.fraud.probability >= cfg.decline_p",
                       "signals.fraud.probability")
    report = rtdp.validate(bad)
    assert "not_bool" in [i.code for i in report.tiers[1].issues]


def test_unknown_signal_contract(rtdp):
    bad = GOOD.replace('contract: "1.1.0"', 'contract: "9.9.9"')
    report = rtdp.validate(bad)
    assert "unknown_contract" in [i.code for i in report.tiers[2].issues]


def test_unknown_signal_field(rtdp):
    bad = GOOD.replace("signals.fraud.probability", "signals.fraud.score")
    report = rtdp.validate(bad)
    assert "unknown_signal_field" in [i.code for i in report.tiers[2].issues]


def test_unknown_feature(rtdp):
    bad = GOOD.replace("features.claimant_claim_count_1h",
                       "features.bogus_counter")
    report = rtdp.validate(bad)
    assert "unknown_feature" in [i.code for i in report.tiers[2].issues]


def test_signal_read_without_requires_warns(rtdp):
    bad = GOOD.replace("requires_signals: [fraud]", "requires_signals: []")
    report = rtdp.validate(bad)
    assert "signal_read_without_require" in [
        i.code for i in report.tiers[2].warnings]


def test_platform_scope_rejected(rtdp):
    bad = GOOD.replace("owner_scope: tenant", "owner_scope: platform")
    report = rtdp.validate(bad)
    assert "scope_violation" in [i.code for i in report.tiers[3].issues]


def test_golden_eval_mirrors_engine(rtdp):
    case = {"features": {"claimant_claim_count_1h": 3},
            "signals": {"fraud": {"probability": 0.95}},
            "present_signals": ["fraud"],
            "cfg": {"decline_p": 0.9, "vel_max": 10}}
    out = rtdp.evaluate(GOOD, case)
    assert out["decision"] == "DECLINE"
    assert out["fired"][0]["rule_id"] == "hi_fraud_decline"


def test_missing_required_signal_skips_to_review(rtdp):
    case = {"features": {"claimant_claim_count_1h": 3},
            "signals": {}, "present_signals": [],
            "cfg": {"decline_p": 0.9, "vel_max": 10}}
    out = rtdp.evaluate(GOOD, case)
    assert out["decision"] == "REVIEW"
    assert out["skipped"] == ["hi_fraud_decline"]


def test_default_when_nothing_fires(rtdp):
    case = {"features": {"claimant_claim_count_1h": 1},
            "signals": {"fraud": {"probability": 0.1}},
            "present_signals": ["fraud"],
            "cfg": {"decline_p": 0.9, "vel_max": 10}}
    out = rtdp.evaluate(GOOD, case)
    assert out["decision"] == "APPROVE" and out["defaulted"]


def test_yaml_extraction(rtdp):
    assert rtdp.extract_artifact("```yaml\n" + GOOD + "```") is not None
    assert rtdp.extract_artifact("no yaml here") is None
