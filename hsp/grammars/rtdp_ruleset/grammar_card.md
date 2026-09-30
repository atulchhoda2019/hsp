# Grammar card: rtdp-ruleset v1.0.0

Emit ONE YAML object — an RTDP ruleset: ordered CEL rules evaluated against
`features`, `signals`, `cfg`, `input`, `actor` maps, aggregated by decision
precedence (DECLINE > REVIEW > APPROVE).

## Shape

```yaml
ruleset_id: tenant_my_rules        # snake_case, tenant prefix for agent output
version: 1
owner_scope: tenant                # agent artifacts are ALWAYS tenant scope
requires:                          # semantic signal deps — never model names
  - signal: claim.fraud_probability
    contract: "1.1.0"              # exact contract semver
    alias: fraud
    optional: false
evaluation: all_match
rules:
  - id: model_decline
    when: "signals.fraud.probability >= cfg.decline_probability"
    outcome: {decision: DECLINE, reason: MODEL_HIGH_RISK}
    requires_signals: [fraud]
default_outcome: APPROVE
missing_required_signal_outcome: REVIEW
```

## CEL expressions (`when`)

- Real CEL: `&&`, `||`, `!`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, ternary `?:`.
- Must evaluate to **bool**. Max 4096 bytes.
- Available roots: `features.<name>`, `signals.<alias>.<field>`, `cfg.<key>`,
  `input.<field>`, `actor.<field>`.
- `signals.<alias>` paths must use an alias declared in `requires`; the field
  must exist in that contract's value_schema.
- `features.<name>` must be a registered feature definition.
- `cfg.<key>` reads product thresholds — invent keys only when the requirement
  names a tunable knob.
- A rule reading `signals.<alias>` must list the alias in `requires_signals`
  so the engine skips it (never zero-values) when the signal is absent.

## Outcomes

`decision` ∈ APPROVE | REVIEW | DECLINE. `reason` ∈ UPPER_SNAKE. Higher-severity
outcomes win aggregation; `default_outcome` applies when no rule fires;
`missing_required_signal_outcome` applies when a fired rule needed an absent
required signal.

## Rules

- YAML only — no prose, no fences.
- Rules are ordered; prefer most-severe checks first (DECLINE, then REVIEW,
  then default APPROVE).
- Reference bindings/signals by contract name — never invent provider
  endpoints, model names, or activation fields.
