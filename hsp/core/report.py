"""Validation result types shared by all grammar plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class Issue:
    """One validation finding. `path` locates it inside the artifact when known."""

    code: str
    message: str
    path: str | None = None
    severity: str = "error"  # error | warning


@dataclass
class TierResult:
    tier: int
    name: str
    status: Status
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]


@dataclass
class ValidationReport:
    grammar_id: str
    grammar_version: str
    tiers: list[TierResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(t.status != Status.FAIL for t in self.tiers)

    @property
    def issues(self) -> list[Issue]:
        return [i for t in self.tiers for i in t.issues]

    def failed_tier(self) -> TierResult | None:
        for t in self.tiers:
            if t.status == Status.FAIL:
                return t
        return None
