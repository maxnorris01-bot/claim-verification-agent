"""Stage 1: one LLM call that assigns a claim to exactly one tier (or to 'not a claim')."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.llm import Budget, complete, parse_json_object
from app.prompts import load_prompt
from app.verdict import Tier

NOT_A_CLAIM = "not_a_claim"

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        # reasoning is declared first so the model explains itself before committing to a tier
        "reasoning": {"type": "string"},
        "tier": {"type": "string", "enum": [*(t.value for t in Tier), NOT_A_CLAIM]},
    },
    "required": ["reasoning", "tier"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Classification:
    tier: Tier | None  # None means the input was not a checkable claim
    reasoning: str


def classify(claim: str, budget: Budget) -> Classification:
    prompt = load_prompt("classifier")
    completion = complete(
        span_name="classifier.classify",
        prompt=prompt,
        model=budget.config.classifier_model,
        user_text=claim,
        budget=budget,
        max_tokens=512,
        schema=_SCHEMA,
    )
    data = parse_json_object(completion.text, what="classifier")
    raw_tier = data["tier"]
    tier = None if raw_tier == NOT_A_CLAIM else Tier(raw_tier)
    return Classification(tier=tier, reasoning=str(data["reasoning"]))
