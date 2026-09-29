"""LLM provider boundary — same contract as rtdp's slm-service.

Providers are interchangeable (Ollama local now, Bedrock/vLLM later). Every
result carries model identity + digest so provenance never depends on mutable
tags.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResult:
    text: str
    provider: str          # e.g. "ollama", "fixture"
    model: str             # e.g. "qwen2.5-coder:3b"
    model_digest: str      # provider-reported blob digest, or fixture id
    latency_ms: int


class Provider(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, system: str = "",
                 temperature: float = 0.0) -> LLMResult:
        """One-shot generation. temperature defaults to 0 for determinism;
        the repair loop may raise it slightly to escape a stuck output."""

    def identity(self) -> dict[str, str]:
        return {"provider": type(self).__name__}
