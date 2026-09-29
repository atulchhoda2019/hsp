"""Pipeline tests with the fixture provider — deterministic, no LLM needed."""

import json

from hsp.pipeline import generate
from hsp.provider.fixture import FixtureProvider

GOOD = json.dumps({
    "expression_id": "ca_test_surcharge",
    "version": 1,
    "jurisdiction": "CA",
    "line": "personal_auto",
    "conditions": [
        {"field": "policy.state", "op": "eq", "value": "CA"},
        {"field": "mvr.major_violations_3y", "op": "ge", "value": 1},
    ],
    "effect": {"type": "surcharge", "factor": 1.25, "applies_to": "base_premium",
               "reason": "MVR_MAJOR_VIOLATION"},
    "metadata": {"author": "hsp-agent", "source_refs": ["req:T-1"]},
})

BAD_THEN_GOOD = [json.dumps({
    "expression_id": "ca_test_surcharge",
    "version": 1,
    "jurisdiction": "CA",
    "line": "personal_auto",
    "conditions": [{"field": "mvr.bogus_field", "op": "ge", "value": 1}],
    "effect": {"type": "surcharge", "factor": 1.5, "applies_to": "base_premium"},
}), GOOD]

REQ = "California auto surcharge for major violations"


def test_first_pass_proposal(grammar, exemplar_corpus, tmp_path):
    res = generate(REQ, plugin=grammar, corpus=exemplar_corpus,
                   provider=FixtureProvider(responses=[GOOD]),
                   source_refs=["req:T-1"], out_dir=tmp_path)
    b = res.bundle
    assert b.status == "PROPOSED"
    assert b.provenance.attempts == 1
    assert b.digest.startswith("sha256:")
    for name in ("artifact.json", "manifest.json", "provenance.json",
                 "validation.json"):
        assert (res.bundle_dir / name).exists()
    manifest = json.loads((res.bundle_dir / "manifest.json").read_text())
    assert manifest["status"] == "PROPOSED"


def test_repair_loop_converges(grammar, exemplar_corpus):
    provider = FixtureProvider(responses=BAD_THEN_GOOD)
    res = generate(REQ, plugin=grammar, corpus=exemplar_corpus,
                   provider=provider)
    b = res.bundle
    assert b.status == "PROPOSED"
    assert b.provenance.attempts == 2
    assert "unknown_field" in b.provenance.repair_transcript[0]
    # repair prompt carried the validation errors back to the model
    assert "unknown_field" in provider.prompts[1]


def test_exhaustion_yields_rejected_bundle(grammar, exemplar_corpus, tmp_path):
    bad = BAD_THEN_GOOD[0]
    res = generate(REQ, plugin=grammar, corpus=exemplar_corpus,
                   provider=FixtureProvider(responses=[bad, bad, bad]),
                   max_attempts=3, out_dir=tmp_path)
    b = res.bundle
    assert b.status == "REJECTED"
    assert b.provenance.attempts == 3
    manifest = json.loads((res.bundle_dir / "manifest.json").read_text())
    assert manifest["status"] == "REJECTED"


def test_no_json_in_response_retries(grammar, exemplar_corpus):
    res = generate(REQ, plugin=grammar, corpus=exemplar_corpus,
                   provider=FixtureProvider(responses=["sorry, cannot", GOOD]))
    assert res.bundle.status == "PROPOSED"
    assert res.bundle.provenance.attempts == 2


def test_provenance_records_exemplar_digests(grammar, exemplar_corpus):
    res = generate(REQ, plugin=grammar, corpus=exemplar_corpus,
                   provider=FixtureProvider(responses=[GOOD]))
    prov = res.bundle.provenance
    assert all(e["digest"].startswith("sha256:") for e in prov.exemplars)
    assert prov.provider["provider"] == "fixture"
