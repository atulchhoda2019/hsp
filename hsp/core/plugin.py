"""GrammarPlugin contract.

A grammar plugin gives the agent everything it needs to generate, check and run
artifacts in one DSL: a prompt-facing grammar card, a deterministic multi-tier
validator, an evaluator for golden cases and a canonical digest for pinning.

Validation tiers (see docs/design.md):
  1 schema            artifact parses; closed schema; required fields
  2 compile           conditions/effects form an executable plan
  3 semantic resolve  referenced fields exist; value types compatible
  4 golden-case eval  artifact produces expected decisions on case vectors
  5 policy/guardrail  provenance present; banned constructs absent
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from .report import ValidationReport


class GrammarPlugin(ABC):
    grammar_id: str
    grammar_version: str
    artifact_format: str = "json"   # "json" | "yaml" — bundle file extension
    # dot path for source_refs inside the artifact, or None when the grammar
    # has no metadata channel (refs still land in bundle provenance)
    source_refs_key: str | None = "metadata.source_refs"

    @abstractmethod
    def grammar_card(self) -> str:
        """Compact grammar spec injected into the generator prompt."""

    @abstractmethod
    def validate(self, artifact: str) -> ValidationReport:
        """Run all validation tiers over raw artifact text."""

    @abstractmethod
    def evaluate(self, artifact: str | dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
        """Execute the artifact against one synthetic report/case vector.

        Returns {"matched": bool, "effect": dict | None}.
        """

    def extract_artifact(self, text: str) -> str | None:
        """Pull the artifact document out of raw LLM output. Default: JSON."""
        from hsp.generator.extract import extract_json
        return extract_json(text)

    def digest(self, artifact: str) -> str:
        """Canonical sha256 over the parsed artifact — the pin in manifests."""
        parsed = self.parse(artifact)
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    def parse(self, artifact: str) -> Any:
        """Artifact text → dict. Override for non-JSON grammars."""
        return json.loads(artifact)
