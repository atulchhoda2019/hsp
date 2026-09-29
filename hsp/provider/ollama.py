"""Ollama provider — POST /api/generate with deterministic sampling."""

from __future__ import annotations

import json
import os
import time
import urllib.request

from .base import LLMResult, Provider

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:3b"


class OllamaProvider(Provider):
    def __init__(self, model: str | None = None, host: str | None = None,
                 timeout_s: float = 120) -> None:
        self.model = model or os.environ.get("HSP_MODEL", DEFAULT_MODEL)
        self.host = (host or os.environ.get("HSP_OLLAMA_HOST", DEFAULT_HOST)).rstrip("/")
        self.timeout_s = timeout_s

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            self.host + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read())

    def generate(self, prompt: str, *, system: str = "",
                 temperature: float = 0.0) -> LLMResult:
        started = time.monotonic()
        body = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature, "top_p": 1.0},
        }
        out = self._post("/api/generate", body)
        return LLMResult(
            text=out.get("response", ""),
            provider="ollama",
            model=self.model,
            model_digest=self._model_digest(),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    def _model_digest(self) -> str:
        try:
            info = self._post("/api/show", {"model": self.model})
            details = info.get("model_info") or {}
            return "sha256:" + str(info.get("digest") or details.get("digest", "unknown"))
        except Exception:
            return "unknown"

    def identity(self) -> dict[str, str]:
        return {"provider": "ollama", "host": self.host, "model": self.model}
