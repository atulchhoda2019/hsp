# Grammar card: decisioning-expression v1.0.0

Emit ONE JSON object — a *decisioning expression*: the conditions under which a
surcharge, discount, eligibility or pricing-factor decision applies.

## Shape

```jsonc
{
  "expression_id": "snake_case_id",       // required
  "version": 1,                            // integer >= 1
  "jurisdiction": "CA",                    // 2-letter state or "ALL"
  "line": "personal_auto",                 // personal_auto | homeowners | renters | commercial_auto
  "condition_logic": "all",                // all | any (default all)
  "conditions": [ { "field": "mvr.major_violations_3y", "op": ">=", "value": 1 } ],
  "effect": { "type": "surcharge", "factor": 1.25, "applies_to": "base_premium" },
  "metadata": { "source_refs": ["req:...", "reg:..."] }
}
```

## Operators

`eq ne lt le gt ge` (scalar value) · `in not_in` (array value) ·
`between` ([lo, hi], inclusive) · `exists not_exists` (no value)

## Effect rules

- `surcharge`: `factor` required and **> 1** (raises premium)
- `discount`: `factor` required and **< 1** (lowers premium)
- `pricing_factor`: `factor` required, **> 0**
- `eligibility`: `decision` required — `ELIGIBLE | INELIGIBLE | REFERRAL`, plus `reason` (UPPER_SNAKE)
- factor effects must set `applies_to`: `base_premium | policy_premium | peril_premium`

## Fields

`conditions[].field` must come from the report registry — dotted paths:
`mvr.* policy.* applicant.* vehicle.* property.* loss_history.*`.
Use only fields valid for the expression's `line`; auto lines may not use
`property.*`, property lines may not use `mvr.*` / `vehicle.*`.

## Rules

- Output the artifact only — no prose, no markdown fences.
- `jurisdiction` must agree with any `policy.state` condition.
- Always include `metadata.source_refs` citing the requirement ids given in the task.
