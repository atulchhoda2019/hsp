# M3 evidence — RTDP ruleset grammar plugin

Date: 2026-09-29.

## What

`hsp.grammars.rtdp_ruleset` — second grammar plugin: YAML rulesets with CEL
`when` expressions, mirroring `rtdp/internal/ruleseng/engine.go` semantics
(skip rules on absent required signals; precedence DECLINE > REVIEW > APPROVE;
missing-signal outcome; default outcome).

- Contracts snapshot: `hsp/grammars/rtdp_ruleset/contracts_snapshot/`
  (4 signal contracts + 4 feature definitions copied from rtdp, with
  `SNAPSHOT.sha256` pin manifest).
- Validation tiers: 1 schema (closed keys, enums) → 2 compile (celpy parse +
  zero-activation smoke eval → must yield bool) → 3 resolve (contract@version,
  alias scoping, signal-field paths vs value_schema, feature registry,
  requires_signals coverage warnings) → 5 policy (owner_scope=tenant enforced,
  ≤50 rules).
- Golden eval: `evaluate()` runs real CEL via celpy with identical
  fired/skipped/defaulted semantics.

## Live run (Ollama qwen2.5-coder:3b)

```
$ hsp eval --grammar rtdp-ruleset
PASS fraud_triage attempts=1 golden=4/4   # DECLINE/REVIEW/APPROVE/missing-signal
PASS uw_gate      attempts=1 golden=3/3

validity 1.0 · first_pass 1.0 · golden 1.0
```

Direct generate also passed first attempt:
`digest=sha256:2548efe5…`, correct cfg.* tunables, alias hygiene, ordered rules.

## Defect found and fixed

Generation initially returned REJECTED: model added `metadata.source_refs`
(prompt instruction) but the rtdp spec is closed — `unknown_key` failed schema.
Fix: `source_refs_key` is now a plugin attribute; rtdp sets it `None` so refs
live only in bundle provenance, and the prompt omits the requirement.

## Suite

61 tests green; ruff clean. New coverage: CEL parse/compile negatives,
non-bool rejection, unknown contract/feature/signal-field, alias scoping,
platform-scope rejection, golden eval (fired/skipped/defaulted), YAML extraction.
