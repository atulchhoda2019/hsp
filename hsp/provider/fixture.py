"""Deterministic fixture provider for tests and offline eval.

Two modes:
  - canned: {requirement-substring -> artifact text} lookup
  - repair-loop simulation: a queue of responses consumed in order, so tests
    can assert the repair loop converges.
"""

from __future__ import annotations

from collections.abc import Sequence

from .base import LLMResult, Provider


class FixtureProvider(Provider):
    def __init__(self, responses: Sequence[str] | None = None,
                 canned: dict[str, str] | None = None) -> None:
        self._queue = list(responses or [])
        self._canned = canned or {}
        self.prompts: list[str] = []  # captured for assertions

    def generate(self, prompt: str, *, system: str = "",
                 temperature: float = 0.0) -> LLMResult:
        self.prompts.append(prompt)
        if self._queue:
            text = self._queue.pop(0)
        else:
            text = next(
                (v for k, v in self._canned.items() if k in prompt),
                "{}",
            )
        return LLMResult(
            text=text,
            provider="fixture",
            model="fixture@1",
            model_digest="sha256:fixture",
            latency_ms=0,
        )

    def identity(self) -> dict[str, str]:
        return {"provider": "fixture"}
