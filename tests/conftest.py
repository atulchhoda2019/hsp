import json
from pathlib import Path

import pytest

from hsp.grammars.json_dsl import JsonDslGrammar

EXEMPLARS = Path(__file__).parent.parent / "corpus" / "exemplars" / "json_dsl"


@pytest.fixture(scope="session")
def grammar() -> JsonDslGrammar:
    return JsonDslGrammar()


@pytest.fixture(scope="session")
def exemplars() -> dict[str, str]:
    return {p.stem: p.read_text() for p in sorted(EXEMPLARS.glob("*.json"))}


@pytest.fixture
def artifact() -> dict:
    return {
        "expression_id": "test_expr",
        "version": 1,
        "jurisdiction": "CA",
        "line": "personal_auto",
        "conditions": [
            {"field": "policy.state", "op": "eq", "value": "CA"},
            {"field": "mvr.major_violations_3y", "op": "ge", "value": 1},
        ],
        "effect": {"type": "surcharge", "factor": 1.25, "applies_to": "base_premium"},
    }


def dumps(obj: dict) -> str:
    return json.dumps(obj)
