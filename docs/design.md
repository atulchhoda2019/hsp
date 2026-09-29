# Underwriting DSL Agent — Design v0.1

Status: draft for approval. Scope: design/plan only — no code until approved.

## Problem

Insurance decisioning platforms encode underwriting and pricing logic as structured
DSL artifacts (rulesets, thresholds, product bindings). Authoring them by hand is slow,
error-prone, and requires scarce domain + grammar expertise. This project builds an
agentic system that takes natural-language rule descriptions and produces **validated,
production-ready DSL artifacts** — mirroring the two-phase approach in the reference
architecture:

- **Phase 1 (MVP):** single-source agent — NL requirement + retrieved code exemplars →
  generated artifact → deterministic validation → bounded repair loop → proposal bundle.
- **Phase 2:** autonomous multi-source agent (LangGraph) that reconciles regulatory
  sources (DOI bulletins/statutes) with business requirements (Azure DevOps work items
  or equivalent docs) and generates DSL without human authoring, still behind a
  human-approval gate.

Differentiator vs generic RAG: retrieval returns **structured code exemplars**, and
output is checked against a **proprietary grammar** with a real evaluator — not
prose answers.

## Non-negotiables (carried from RTDP AGENTS.md)

- All data synthetic: tenants, rules, regulations, requirements, models, identities.
- The agent **proposes**; it never activates. Generated artifacts are proposal bundles
  requiring human approval — the agent identity holds no activation/approval/dispatch
  authority (ADR-011 analogue, enforced in packaging, not convention).
- Deterministic validation is authoritative. The LLM may propose; only the validator
  may approve. Validation failures feed a bounded repair loop, never get papered over.
- Provenance is mandatory: every artifact records source requirement refs, exemplar
  ids, model/provider identity + digest, and the full validation transcript.
- No mutable `latest` anywhere: exemplar corpus, grammar versions, and generated
  artifacts are all digest-pinned.
- Evidence in `docs/validation/`; secrets only as references; pinned deps/images.

## Architecture

```
            ┌──────────────┐     ┌────────────────────┐
  NL req ──▶│ intake/normal│────▶│ exemplar retriever │ (structured-code RAG)
            │  -izer       │     │ corpus: versioned, │
            └──────────────┘     │ digest-pinned      │
                                 └─────────┬──────────┘
                                           │ top-k exemplars + grammar card
                                           ▼
                                 ┌────────────────────┐     ┌───────────────┐
            ┌───────────────────▶│ generator (LLM via │────▶│ repair loop   │◀─┐
            │  bounded iters     │ provider boundary) │     │ (bounded)     │  │
            │                    └────────────────────┘     └──────┬────────┘  │
            │                                                      │ failures  │
            │                    ┌────────────────────┐            │           │
            └────────────────────│ validation tiers   │────────────┘           │
                                 │ 1 schema           │                        │
                                 │ 2 grammar compile  │                        │
                                 │ 3 semantic resolve │                        │
                                 │ 4 golden-case eval │                        │
                                 │ 5 policy/guardrail │                        │
                                 └─────────┬──────────┘                        │
                                           │ pass                              ▼
                                           ▼                              human gate
                                 ┌────────────────────┐
                                 │ proposal bundle    │──▶ human approve ──▶
                                 │ artifact + manifest│    hand off to target
                                 │ + provenance       │    platform (rtdp) or
                                 └────────────────────┘    standalone registry
```

### Components

| Component | Responsibility |
|---|---|
| `intake` | Normalize NL requirement → structured intent (product, jurisdiction, rule type, fields referenced, outcome class). Reject underspecified intents with targeted questions rather than guessing. |
| `corpus` | Versioned exemplar store of real grammar artifacts (synthetic here). Entries carry grammar version, product, jurisdiction, tags, digest. Retrieval = embedding similarity + hard filters (grammar version, rule type) + near-miss diversity. |
| `provider` | LLM boundary — same pattern as rtdp `slm-service`: Ollama locally now; Bedrock/vLLM/SageMaker later behind one interface. Model identity + digest recorded in provenance. |
| `generator` | Prompt = intent + grammar card (compact spec) + top-k exemplars + output contract. Constrained to emit a single artifact document. |
| `validator` | Grammar-plugin driven, 5 tiers (below). Fully deterministic; same artifact → same verdict. |
| `repair` | Feeds structured validation errors back to generator. Bounded (default 3 iters); escalating error detail each round; exhaust → fail with diagnostics, never ship unvalidated output. |
| `packager` | Emits proposal bundle: artifact, manifest (grammar@version, digests), provenance, validation transcript, golden-case results. |
| `eval` | Offline harness: replay suite of (requirement → expected artifact/behavior) cases; measures validity rate, first-pass rate, repair depth, semantic-diff vs expected. Gate for prompt/grammar/corpus changes. |

### Validation tiers (per grammar plugin)

1. **Schema** — artifact parses; required fields; no unknown fields (closed schema).
2. **Compile** — expressions compile under the grammar's evaluator (CEL for rtdp;
   expression engine for JSON DSL).
3. **Semantic resolution** — every referenced feature exists (`feature@version`),
   every signal resolves to a registered contract (`signal@semver`), every `cfg.*`
   key exists in the product's thresholds, outcome enums are legal.
4. **Golden-case eval** — artifact executes against synthetic case vectors and
   produces expected decisions; also adversarial fixtures (missing signal →
   `missing_required_signal_outcome`, etc.).
5. **Policy/guardrail** — no live-action authority references, required provenance
   fields, banned constructs (e.g. unbounded literals where thresholds exist),
   deterministic-ordering checks.

## Grammar plugins

Core is grammar-agnostic. A plugin provides: `schema`, `compile()`, `resolve_symbols()`,
`evaluator` (for golden cases), `exemplar_index` tags, `grammar_card` (prompt text),
`package()`.

### Plugin A — RTDP ruleset DSL (YAML + CEL) — first-class

Targets the existing rtdp artifact surface so generated rules actually execute in
the rules-service under pinned bundle digests:

```yaml
ruleset_id: uw_surcharge_ca
version: 1
owner_scope: tenant            # agent output is tenant-scoped draft, never platform
requires:
  - signal: underwriting.eligibility_probability
    contract: "1.0.0"
    alias: elig
    optional: false
evaluation: all_match
rules:
  - id: mvr_major_violation_surcharge
    when: "features.mvr_major_violations_3y >= cfg.surcharge_threshold"
    outcome: {decision: REVIEW, reason: MVR_SURCHARGE_REVIEW}
    requires_signals: []
default_outcome: APPROVE
missing_required_signal_outcome: REVIEW
```

Plugin also validates companions when requested: product YAML updates
(`required_features`, `signals`, `thresholds`, `ruleset: id@version`), signal
`requires` against `contracts/signal_contracts/*`, bindings only by reference —
the agent may *reference* bindings, never create model identities.

### Plugin B — standalone JSON "decisioning expressions" DSL

hsp-native grammar modeled on the reference doc: each expression = conditions under
which a pricing factor / surcharge / discount / eligibility applies — report fields
to read, operators/thresholds, action. hsp owns its JSON Schema, expression evaluator,
and exemplar corpus. Useful for demoing the agent independent of the rtdp stack.

```jsonc
{
  "expression_id": "ca_auto_mvr_surcharge",
  "version": 1,
  "jurisdiction": "CA",
  "line": "personal_auto",
  "effect": { "type": "surcharge", "factor": 1.25 },
  "conditions": [
    { "field": "mvr.major_violations_3y", "op": ">=", "value": 1 },
    { "field": "policy.state", "op": "==", "value": "CA" }
  ]
}
```

## Phase 2 — multi-source reconciliation agent (LangGraph)

Adds a graph that generates from **conflicting** sources, not a single NL prompt:

```
sources: [DOI bulletin/statute docs]  +  [business requirement docs/work items]
   │                                        │
   ▼                                        ▼
extract constraints (hard: legal)    extract constraints (soft: business)
   └────────────┬───────────────────────────┘
                ▼
        reconcile: detect conflicts (e.g. reg caps surcharge ≤ 15%,
        req asks 25%) → resolution = regulation wins; log conflict fact
                ▼
        synthesize intent set → per-rule Phase-1 pipeline → merged proposal
                ▼
        coverage check: every hard constraint mapped to ≥1 generated rule
        or explicit waiver; unconstrained rules flagged
                ▼
        proposal bundle + reconciliation report → human gate
```

Source docs are synthetic corpora in hsp (`corpus/regulations/`, `corpus/reqs/`).
Phase 2 output is still a proposal — human approval unchanged.

## Repo layout (planned)

```
hsp/
  docs/design.md                  # this file
  docs/validation/                # evidence, eval runs
  hsp/                            # python package
    intake/  corpus/  provider/   # pipeline stages
    generator/  validator/  repair/  packager/
    grammars/rtdp/                # plugin A (cel/yaml via rtdp schemas)
    grammars/json_dsl/            # plugin B (native schema+evaluator)
    phase2/graph.py               # LangGraph reconciliation
    cli.py                        # hsp generate / validate / eval
  corpus/exemplars/               # versioned artifact exemplars (synthetic)
  corpus/regulations/  corpus/reqs/   # synthetic Phase-2 source docs
  eval/cases/                     # requirement → expected cases
  tests/  Makefile  pyproject.toml
```

Stack: Python 3.12, LangGraph (phase 2), Ollama provider via HTTP (reusing rtdp
local stack), pyyaml/jsonschema, cel-python or delegation to rtdp validator for
plugin A compile+eval. Vector index: sqlite-vec or pgvector — decide at build time,
keep dependency light.

## Build milestones

| # | Deliverable | Exit gate |
|---|---|---|
| M1 | Grammar plugin B: JSON DSL schema + evaluator + 10 exemplars + validator tiers 1–2 | schema+eval unit tests green |
| M2 | Phase-1 pipeline end-to-end on plugin B (intake→retrieve→generate→validate→repair→bundle) via Ollama | `hsp eval` on 10 synthetic cases ≥ target validity rate; proposal bundles with provenance |
| M3 | Plugin A: rtdp ruleset grammar (tiers 1–5 incl. CEL compile + signal/feature/cfg resolution + golden eval against rules-service semantics) | generated ruleset loads in local rtdp `make e2e` |
| M4 | Phase-2 LangGraph: synthetic regulation + req corpora, conflict reconcile, coverage check | conflict fixture resolved correctly; coverage report complete |
| M5 | Hardening: eval gates in CI, prompt-injection fixtures, evidence docs | full suite green; docs/validation populated |

## Open questions for approval

1. LLM for generation: local Ollama model (free, reproducible) vs API model for
   quality — recommend Ollama `qwen2.5-coder`-class for Phase 1, pluggable either way.
2. Corpus size target: ~30-50 synthetic exemplars across 2 jurisdictions/lines enough
   for credible demo; larger corpora are Phase-2 work.
3. Whether plugin A should validate by importing rtdp schemas (tighter, but couples
   hsp to rtdp repo path) vs a copied snapshot of schemas (decoupled, can drift) —
   recommend copied snapshot + digest check.
