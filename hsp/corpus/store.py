"""Exemplar corpus: load, pin, retrieve.

Retrieval is deterministic lexical scoring — token overlap between the
requirement/intent and each exemplar's description + referenced fields,
with hard filters on grammar-fit dimensions (line, jurisdiction). With a
corpus of tens of exemplars this is transparent and testable; swap in
embeddings later without changing the interface.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from hsp.intake.intent import Intent

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass
class Exemplar:
    id: str
    artifact: dict
    digest: str
    tokens: set[str]

    @property
    def text(self) -> str:
        return json.dumps(self.artifact, indent=2)


def _digest(artifact: dict) -> str:
    canon = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canon.encode()).hexdigest()


class Corpus:
    def __init__(self, exemplars: list[Exemplar]) -> None:
        self.exemplars = exemplars

    @classmethod
    def load(cls, directory: str | Path) -> "Corpus":
        items = []
        for path in sorted(Path(directory).glob("*.json")):
            art = json.loads(path.read_text())
            hay = json.dumps(art) + " " + art.get("description", "")
            items.append(Exemplar(
                id=art.get("expression_id", path.stem),
                artifact=art,
                digest=_digest(art),
                tokens=set(_TOKEN.findall(hay.lower())),
            ))
        return cls(items)

    def retrieve(self, intent: Intent, k: int = 3) -> list[Exemplar]:
        query = set(_TOKEN.findall(intent.requirement.lower()))
        query |= {t for f in intent.field_hints for t in _TOKEN.findall(f)}

        scored = []
        for ex in self.exemplars:
            if intent.line and ex.artifact.get("line") != intent.line:
                continue
            jur = ex.artifact.get("jurisdiction")
            if intent.jurisdiction and jur not in (intent.jurisdiction, "ALL"):
                continue
            score = len(query & ex.tokens)
            if ex.artifact.get("effect", {}).get("type") == intent.effect_type:
                score += 3
            scored.append((score, ex))

        scored.sort(key=lambda s: (-s[0], s[1].id))
        chosen = [ex for s, ex in scored[:k] if s > 0] or [ex for _, ex in scored[:k]]
        return chosen
