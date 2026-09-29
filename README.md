# hsp — Underwriting DSL Agent

Agentic generation of validated, production-ready DSL artifacts for insurance
underwriting and pricing rules. All data synthetic. See `docs/design.md`.

## Status

- [x] **M1** — JSON `decisioning-expression` grammar plugin: closed schema,
      deterministic evaluator, 3-tier validation, 10 synthetic exemplars
- [x] **M2** — Phase-1 pipeline live: intake → exemplar retrieval → Ollama
      generation → tiered validation → bounded repair → proposal bundle.
      6/6 eval cases pass at 100% first-pass (qwen2.5-coder:3b)
- [ ] M3 — RTDP ruleset grammar plugin (CEL/YAML)
- [ ] M4 — Phase-2 LangGraph multi-source reconciliation
- [ ] M5 — Eval gates, injection fixtures, evidence

## Quickstart

```bash
uv venv --python 3.11 .venv && uv pip install -e '.[dev]' --python .venv/bin/python
make lint test                                    # ruff + pytest
make validate FILE=corpus/exemplars/json_dsl/ca_auto_mvr_surcharge.json

# live generation (requires `ollama serve` + `ollama pull qwen2.5-coder:3b`)
hsp generate "CA auto surcharge for major MVR violations" --refs req:DEMO-1 --out /tmp/bundle
hsp eval                                          # replay eval/cases through the pipeline
```
