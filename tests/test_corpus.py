from hsp.intake.intent import normalize


def test_loads_and_digests(exemplar_corpus):
    assert len(exemplar_corpus.exemplars) == 14
    assert all(e.digest.startswith("sha256:") for e in exemplar_corpus.exemplars)


def test_retrieval_prefers_matching_line_and_effect(exemplar_corpus):
    intent = normalize("CA auto surcharge for major MVR violations")
    top = exemplar_corpus.retrieve(intent, k=2)
    assert top[0].artifact["line"] == "personal_auto"
    assert any(e.id == "ca_auto_mvr_surcharge" for e in top)


def test_retrieval_respects_line_filter(exemplar_corpus):
    intent = normalize("California homeowners wildfire surcharge")
    top = exemplar_corpus.retrieve(intent, k=5)
    assert all(e.artifact["line"] == "homeowners" for e in top)


def test_retrieval_admits_all_jurisdiction(exemplar_corpus):
    intent = normalize("NY auto discount")
    ids = [e.id for e in exemplar_corpus.retrieve(intent, k=10)]
    assert "all_auto_multi_policy_discount" in ids or "all_auto_safety_rating_discount" in ids
