# M2 evidence — Phase-1 generation pipeline

Date: 2026-09-29.

## Live eval run (Ollama, qwen2.5-coder:3b, temperature 0)

```
$ .venv/bin/python -m hsp.cli eval
PASS ca_mvr_surcharge   attempts=1 golden=3/3
PASS dui_ineligible     attempts=1 golden=2/2
PASS multi_policy_discount attempts=1 golden=2/2
PASS wildfire_surcharge attempts=1 golden=2/2
PASS old_roof_referral  attempts=1 golden=2/2
PASS commercial_mileage attempts=1 golden=2/2

{ "cases": 6, "validity_rate": 1.0, "first_pass_rate": 1.0,
  "mean_attempts": 1.0, "structural_match_rate": 1.0, "golden_rate": 1.0 }
```

## Unit/integration suite

47 tests green (`pytest`), ruff clean. Fixture-provider pipeline tests cover:
first-pass proposal, repair-loop convergence (validation errors echoed back
into the repair prompt), exhaustion → REJECTED bundle, non-JSON responses,
provenance digests.

## Real-world defect found and fixed

First live run REJECTED all 3 attempts: the model emitted `"op": ">"` because
the grammar card's shape example used `>=` while the op enum uses words.
Fix: corrected the card example + added an explicit "ops are words not symbols"
rule; also gave repair rounds temperature 0.2 so a stuck deterministic output
can escape. Same requirement then produced a valid PROPOSED artifact in 1
attempt (digest `sha256:edbd81aa…`).

## Benefits-admin domain (dependent verification + receipts)

Per `Alight_Demo_Use_Cases_and_Devin_Prompts.md`: grammar extended with
`line: benefits_admin` + `document.*`/`dependent.*`/`receipt.*` fields, and a
tier-5 policy rule enforcing the demo thesis — **AI never rejects**
(INELIGIBLE banned for benefits_admin; REFERRAL = human review).

Live eval after extension:

```
9/9 cases — validity 1.0, first_pass 1.0, golden 1.0
(incl. dep_verify_approve, dep_low_confidence_review, receipt_unknown_lines)
```

Iterated failures that produced the fixes:
- model invented field synonyms (`document.parent_name_match` vs registry
  `dependent.parent_match_score`) → added `field_index()` to the prompt
- invented names surfaced only after the tier-2 error was fixed (tiers were
  gated) → tier 3 now always runs when the artifact parses
- `line` misdetected as personal_auto ("auto-approve" substring) → intake now
  scores word-boundary hint matches

## Note on determinism

temperature=0 makes attempt 1 reproducible per model+digest; repair attempts
run at 0.2. Bundle provenance records provider, model, model digest, attempts
and the repair transcript.
