"""Extract the artifact JSON from raw LLM output.

Tolerates markdown fences and leading/trailing prose — strictness belongs to
the validator, not to parsing the response envelope.
"""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json(text: str) -> str | None:
    text = text.strip()
    m = _FENCE.search(text)
    if m:
        return m.group(1)
    start = text.find("{")
    if start == -1:
        return None
    depth, end = 0, -1
    in_str = esc = False
    for i, ch in enumerate(text[start:], start):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    if end == -1:
        return None
    candidate = text[start:end]
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        return None
