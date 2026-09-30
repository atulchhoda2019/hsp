"""Proposal bundle: the only output form the agent produces.

A bundle is a directory:

  artifact.json     canonical artifact (pretty-printed)
  manifest.json     grammar@version, digests, status=PROPOSED
  provenance.json   requirement, intent, exemplar ids/digests, provider
                    identity, attempt count, repair transcript summary
  validation.json   full tiered validation transcript

Bundles are immutable proposals. Activation is a separate human-gated act;
nothing here carries authority to deploy.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hsp.core.report import Status, ValidationReport


@dataclass
class Provenance:
    requirement: str
    intent: dict
    exemplars: list[dict[str, str]]      # [{id, digest}]
    provider: dict[str, str]
    attempts: int
    repair_transcript: list[str] = field(default_factory=list)  # issue codes per attempt
    created_at: str = ""


@dataclass
class Bundle:
    artifact: dict
    digest: str
    grammar_id: str
    grammar_version: str
    status: str  # PROPOSED | REJECTED
    provenance: Provenance
    validation: ValidationReport
    artifact_format: str = "json"

    def write(self, out_dir: str | Path) -> Path:
        import yaml
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        ext = "yaml" if self.artifact_format == "yaml" else "json"
        text = (yaml.safe_dump(self.artifact, sort_keys=False)
                if ext == "yaml" else json.dumps(self.artifact, indent=2) + "\n")
        (out / f"artifact.{ext}").write_text(text)
        (out / "manifest.json").write_text(json.dumps({
            "artifact_digest": self.digest,
            "grammar": {"id": self.grammar_id, "version": self.grammar_version},
            "status": self.status,
            "note": "proposal only — requires human approval before use",
        }, indent=2) + "\n")
        prov = asdict(self.provenance)
        prov["created_at"] = prov["created_at"] or datetime.now(timezone.utc).isoformat()
        (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
        (out / "validation.json").write_text(json.dumps({
            "grammar_id": self.validation.grammar_id,
            "grammar_version": self.validation.grammar_version,
            "ok": self.validation.ok,
            "tiers": [
                {"tier": t.tier, "name": t.name, "status": t.status.value,
                 "issues": [asdict(i) for i in t.issues]}
                for t in self.validation.tiers
            ],
        }, indent=2) + "\n")
        return out


__all__ = ["Bundle", "Provenance", "Status", "ValidationReport"]
