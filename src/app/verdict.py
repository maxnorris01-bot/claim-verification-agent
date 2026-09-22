"""The `Verdict` returned by `pipeline.run`, plus the tier/label vocabularies.

Dataclasses are used throughout (matching `Config` and `Prompt`); `to_dict`/`to_json` give the
serialized form that the eval harness matches `expected_contains` against.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Tier(StrEnum):
    SCIENTIFIC_EMPIRICAL = "scientific_empirical"
    HISTORICAL_FACTUAL = "historical_factual"
    STATISTICAL_DATA = "statistical_data"
    PROVENANCE_ONLY = "provenance_only"
    CONTESTED_UNFALSIFIABLE = "contested_unfalsifiable"


class Label(StrEnum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not supported"
    MIXED = "mixed"
    PROVENANCE_ONLY = "provenance-only"
    NOT_IMPLEMENTED = "not-implemented"
    INVALID_INPUT = "invalid-input"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Evidence:
    claim_snippet: str
    source_url: str
    note: str


@dataclass(frozen=True)
class Verdict:
    tier: Tier | None  # None only for invalid-input (no claim to route)
    verdict: Label
    confidence: Confidence
    evidence: list[Evidence] = field(default_factory=list)
    origin_trace: str = ""
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def not_implemented(tier: Tier, reasoning: str) -> Verdict:
    return Verdict(
        tier=tier,
        verdict=Label.NOT_IMPLEMENTED,
        confidence=Confidence.LOW,
        origin_trace="Not attempted: no evaluator exists for this tier yet.",
        reasoning=(
            f"The '{tier}' tier is not yet implemented in v0, so the claim was routed but not "
            f"evaluated. Classifier reasoning: {reasoning}"
        ),
    )


def invalid_input(reasoning: str) -> Verdict:
    return Verdict(
        tier=None,
        verdict=Label.INVALID_INPUT,
        confidence=Confidence.LOW,
        origin_trace="Not attempted: input is not a checkable claim.",
        reasoning=reasoning,
    )
