# hsp — Underwriting DSL Agent

Agentic generation of validated, production-ready DSL artifacts for insurance
underwriting and pricing rules. All data synthetic. See `docs/design.md`.

## Status

- [x] **M1** — JSON `decisioning-expression` grammar plugin: closed schema,
      deterministic evaluator, 3-tier validation, 10 synthetic exemplars
- [ ] M2 — Phase-1 generation pipeline (retrieval → generate → validate → repair → bundle) via Ollama
- [ ] M3 — RTDP ruleset grammar plugin (CEL/YAML)
- [ ] M4 — Phase-2 LangGraph multi-source reconciliation
- [ ] M5 — Eval gates, injection fixtures, evidence

## Quickstart

```bash
uv venv --python 3.11 .venv && uv pip install -e '.[dev]' --python .venv/bin/python
make lint test                                    # ruff + pytest
make validate FILE=corpus/exemplars/json_dsl/ca_auto_mvr_surcharge.json
```
