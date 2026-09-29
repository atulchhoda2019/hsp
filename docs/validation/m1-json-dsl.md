# M1 evidence — JSON decisioning-expression grammar plugin

Date: 2026-09-29. Commit: initial.

## Gate (design.md M1): schema + evaluator unit tests green

```
$ .venv/bin/python -m pytest -q
27 passed in 0.04s

$ .venv/bin/python -m ruff check hsp tests
All checks passed!
```

Coverage:
- tier 1 schema: 10/10 exemplars valid; non-JSON, unknown keys, missing required
  keys, effect semantics (surcharge>1, discount<1, eligibility decision enum),
  bad ops — all rejected
- tier 2 compile: inverted `between`, non-numeric values for numeric ops,
  missing `applies_to` warning
- tier 3 resolve: unknown field, type mismatch, enum/range violations,
  jurisdiction mismatch, line/namespace scope
- evaluator: match/no-match, missing field → false, `any` logic, all 11 ops,
  wrong-type safety; canonical digest stability

Exemplar corpus: 10 artifacts — personal_auto (CA/TX/ALL), homeowners
(FL/CA/NY/ALL), commercial_auto (WA); surcharge/discount/eligibility/pricing_factor.
All synthetic; `metadata.source_refs` use synthetic `req:AZDO-*` / `reg:*` ids.
