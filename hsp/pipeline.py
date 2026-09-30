"""Phase-1 pipeline: intake → retrieve → generate → validate → repair → bundle.

The loop is deterministic in structure: at most `max_attempts` LLM calls, each
round's validation errors are appended verbatim to the next prompt. Exhaustion
produces a REJECTED bundle — never an unvalidated artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from hsp.corpus.store import Corpus
from hsp.core.plugin import GrammarPlugin

from hsp.generator.prompt import SYSTEM, build_prompt, build_repair_prompt
from hsp.intake.intent import normalize
from hsp.packager.bundle import Bundle, Provenance
from hsp.provider.base import Provider


@dataclass
class GenerationResult:
    bundle: Bundle
    bundle_dir: Path | None


def generate(requirement: str, *, plugin: GrammarPlugin, corpus: Corpus,
             provider: Provider, source_refs: list[str] | None = None,
             max_attempts: int = 3, exemplar_k: int = 3,
             out_dir: str | Path | None = None) -> GenerationResult:
    intent = normalize(requirement)
    exemplars = corpus.retrieve(intent, k=exemplar_k)
    refs = source_refs or []
    prompt = build_prompt(intent, exemplars, plugin.grammar_card(), refs,
                          refs_key=plugin.source_refs_key,
                          field_index=plugin.field_index())

    repair_notes: list[str] = []
    report = None
    artifact: dict | None = None
    provider_meta = provider.identity()
    attempts = 0

    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        result = provider.generate(prompt, system=SYSTEM,
                                   temperature=0.0 if attempt == 1 else 0.2)
        provider_meta = {**provider_meta, "provider": result.provider,
                         "model": result.model, "model_digest": result.model_digest}
        raw = plugin.extract_artifact(result.text)
        if raw is None:
            repair_notes.append(f"attempt {attempt}: no JSON object in response")
            report = None
            prompt = build_repair_prompt(
                prompt, result.text[:2000],
                _empty_report(plugin, "no_json_object"))
            continue
        try:
            artifact = plugin.parse(raw)
        except Exception:
            report = None
            repair_notes.append(f"attempt {attempt}: unparsable artifact")
            continue
        report = plugin.validate(raw)
        if report.ok:
            break
        repair_notes.append(
            f"attempt {attempt}: " + "; ".join(
                f"t{t.tier}:{i.code}" for t in report.tiers for i in t.errors
            ) or "failed")
        prompt = build_repair_prompt(prompt, raw, report)

    ok = report is not None and report.ok and artifact is not None
    if report is None:
        report = _empty_report(plugin, "exhausted_without_artifact")

    bundle = Bundle(
        artifact=artifact or {},
        digest=plugin.digest(raw) if ok else "",
        grammar_id=plugin.grammar_id,
        grammar_version=plugin.grammar_version,
        status="PROPOSED" if ok else "REJECTED",
        provenance=Provenance(
            requirement=requirement,
            intent={"jurisdiction": intent.jurisdiction, "line": intent.line,
                    "effect_type": intent.effect_type,
                    "field_hints": intent.field_hints,
                    "ambiguities": intent.ambiguities},
            exemplars=[{"id": e.id, "digest": e.digest} for e in exemplars],
            provider=provider_meta,
            attempts=attempts,
            repair_transcript=repair_notes,
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
        validation=report,
        artifact_format=plugin.artifact_format,
    )
    bundle_dir = bundle.write(out_dir) if out_dir else None
    return GenerationResult(bundle=bundle, bundle_dir=bundle_dir)


def _empty_report(plugin: GrammarPlugin, code: str):
    from hsp.core.report import Issue, Status, TierResult, ValidationReport
    r = ValidationReport(plugin.grammar_id, plugin.grammar_version)
    r.tiers.append(TierResult(0, "extract", Status.FAIL, [Issue(code, code)]))
    return r
