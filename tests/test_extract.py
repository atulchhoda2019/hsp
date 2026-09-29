import json

from hsp.generator.extract import extract_json


def test_plain_json():
    assert json.loads(extract_json('{"a": 1}')) == {"a": 1}


def test_fenced():
    out = extract_json('Here you go:\n```json\n{"a": {"b": 2}}\n```\nDone.')
    assert json.loads(out) == {"a": {"b": 2}}


def test_prose_wrapped():
    out = extract_json('Sure! {"a": "x{y}z"} thanks')
    assert json.loads(out) == {"a": "x{y}z"}


def test_no_json():
    assert extract_json("no object here") is None


def test_unbalanced():
    assert extract_json('{"a": ') is None
