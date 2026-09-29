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

## Note on determinism

temperature=0 makes attempt 1 reproducible per model+digest; repair attempts
run at 0.2. Bundle provenance records provider, model, model digest, attempts
and the repair transcript.
