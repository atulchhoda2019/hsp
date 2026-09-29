"""Requirement intake: normalize NL text into a structured intent.

The intent steers retrieval and prompt construction — it is advisory, not
authoritative (the LLM still reads the raw requirement). Extraction is
deterministic keyword/state-code matching over synthetic vocabularies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_US_STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
              "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
              "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
              "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
              "VT", "VA", "WA", "WV", "WI", "WY"}

_LINE_HINTS = {
    "personal_auto": ["personal auto", "car", "auto", "vehicle", "driver"],
    "commercial_auto": ["commercial auto", "fleet", "commercial vehicle"],
    "homeowners": ["homeowner", "home", "house", "dwelling", "property"],
    "renters": ["renters", "tenant"],
}

_EFFECT_HINTS = {
    "surcharge": ["surcharge", "increase premium", "penalty"],
    "discount": ["discount", "credit", "reduce premium"],
    "eligibility": ["eligible", "ineligible", "eligibility", "decline", "referral",
                    "refer"],
    "pricing_factor": ["pricing factor", "rate factor"],
}

_FIELD_HINTS = {
    r"\bdui\b": "mvr.dui_convictions_5y",
    r"major violation": "mvr.major_violations_3y",
    r"minor violation": "mvr.minor_violations_3y",
    r"at[- ]fault accident": "mvr.at_fault_accidents_3y",
    r"suspended": "mvr.license_suspended",
    r"\bage\b|young": "applicant.age",
    r"years licensed|inexperienced": "applicant.years_licensed",
    r"roof": "property.roof_age_years",
    r"wildfire": "property.wildfire_score",
    r"coast": "property.distance_to_coast_mi",
    r"protection class": "property.protection_class",
    r"claims?": "loss_history.claims_3y",
    r"mileage": "vehicle.annual_mileage",
    r"safety rating": "vehicle.safety_rating",
    r"multi[- ]policy|bundle": "policy.multi_policy",
    r"prior insurance|lapse": "policy.prior_insurance_months",
    r"term": "policy.term_months",
}


@dataclass
class Intent:
    requirement: str
    jurisdiction: str | None = None        # "CA", "ALL", None
    line: str | None = None
    effect_type: str | None = None
    field_hints: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)


def normalize(requirement: str) -> Intent:
    text = requirement.strip()
    lower = text.lower()
    intent = Intent(requirement=text)

    states = {m.group(0) for m in re.finditer(r"\b[A-Z]{2}\b", text)} & _US_STATES
    states |= {code for name, code in _STATE_NAMES.items() if name in lower}
    if len(states) == 1:
        intent.jurisdiction = states.pop()
    elif len(states) > 1:
        intent.ambiguities.append(f"multiple jurisdictions: {sorted(states)}")

    matches = [line for line, hints in _LINE_HINTS.items()
               if any(h in lower for h in hints)]
    if "commercial_auto" in matches:
        intent.line = "commercial_auto"
    elif matches:
        intent.line = matches[0]
    if intent.line is None:
        intent.ambiguities.append("line of business not detected")

    for effect, hints in _EFFECT_HINTS.items():
        if any(h in lower for h in hints):
            intent.effect_type = effect
            break
    if intent.effect_type is None:
        intent.ambiguities.append("effect type not detected")

    for pat, fname in _FIELD_HINTS.items():
        if re.search(pat, lower) and fname not in intent.field_hints:
            intent.field_hints.append(fname)

    return intent


_STATE_NAMES = {"california": "CA", "texas": "TX", "new york": "NY",
                "florida": "FL", "washington": "WA", "arizona": "AZ",
                "oregon": "OR", "nevada": "NV"}
