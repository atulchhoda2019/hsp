# Grammar card: decisioning-expression v1.0.0

Emit ONE JSON object — a *decisioning expression*: the conditions under which a
surcharge, discount, eligibility or pricing-factor decision applies.

## Shape

```jsonc
{
  "expression_id": "snake_case_id",       // required
  "version": 1,                            // integer >= 1
  "jurisdiction": "CA",                    // 2-letter state or "ALL"
  "line": "personal_auto",                 // personal_auto | homeowners | renters | commercial_auto | benefits_admin
  "condition_logic": "all",                // all | any (default all)
  "conditions": [ { "field": "mvr.major_violations_3y", "op": "ge", "value": 1 } ],
  "effect": { "type": "surcharge", "factor": 1.25, "applies_to": "base_premium" },
  "metadata": { "source_refs": ["req:...", "reg:..."] }
}
```

## Operators

IMPORTANT: ops are lowercase words, never symbols — `ge` not `>=`, `eq` not `==`.

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
`mvr.* policy.* applicant.* vehicle.* property.* loss_history.*` for insurance
lines; `document.* dependent.* receipt.*` for `benefits_admin`.
Use only fields valid for the expression's `line`; auto lines may not use
`property.*`, property lines may not use `mvr.*` / `vehicle.*`,
benefits_admin may not use bureau/vehicle/property fields.

## benefits_admin guardrail

For `line: benefits_admin`, the effect is `eligibility` with
`decision: ELIGIBLE` (auto-approve) or `REFERRAL` (human review).
`INELIGIBLE` is banned — the system never auto-rejects.

## Rules

- Output the artifact only — no prose, no markdown fences.
- `jurisdiction` must agree with any `policy.state` condition.
- Always include `metadata.source_refs` citing the requirement ids given in the task.
