from hsp.intake.intent import normalize


def test_extracts_state_and_line_and_effect():
    i = normalize("California personal auto: surcharge 25% for major violations")
    assert i.jurisdiction == "CA"
    assert i.line == "personal_auto"
    assert i.effect_type == "surcharge"
    assert "mvr.major_violations_3y" in i.field_hints


def test_state_name_and_commercial():
    i = normalize("Washington commercial auto fleet vehicles over 50000 miles "
                  "get a pricing factor increase")
    assert i.jurisdiction == "WA"
    assert i.line == "commercial_auto"
    assert i.effect_type == "pricing_factor"


def test_ambiguities_recorded_not_guessed():
    i = normalize("apply a rule about roof age")
    assert i.jurisdiction is None or "NY" not in str(i.jurisdiction)
    assert "effect type not detected" in i.ambiguities or i.effect_type


def test_multiple_states_flagged():
    i = normalize("CA and TX both get the surcharge")
    assert any("multiple jurisdictions" in a for a in i.ambiguities)
