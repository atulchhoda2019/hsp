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

    @staticmethod
    def digest(artifact: str) -> str:
        """Canonical sha256 over normalized JSON — the pin used in manifests."""
        canonical = json.dumps(
            json.loads(artifact), sort_keys=True, separators=(",", ":")
        )
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
