"""Stage 2: per-tier evaluators. Only `statistical_data` and `provenance_only` exist in v0.

Both run a web-search research call and return a structured verdict; they differ in prompt and in
the verdict labels they may return. Other tiers get an explicit `not-implemented` Verdict.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.classifier import Classification
from app.llm import Budget, complete, parse_json_object, web_search_tool
from app.prompts import load_prompt
from app.tracing import span
from app.verdict import Confidence, Evidence, Label, Tier, Verdict, not_implemented

Evaluator = Callable[[str, Classification, Budget], Verdict]

# A claim needing several searches (each producing its own code-execution + result content) can
# push output past 6000 tokens before the final JSON verdict; observed live at 6778 on a 4-search
# case, which hit the old cap and raised instead of returning a verdict. 12000 gives headroom.
EVALUATOR_MAX_TOKENS = 12000
EVALUATOR_EFFORT = "medium"


def _schema(labels: list[Label]) -> dict[str, Any]:
    evidence_item = {
        "type": "object",
        "properties": {
            "claim_snippet": {"type": "string"},
            "source_url": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["claim_snippet", "source_url", "note"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": [label.value for label in labels]},
            "confidence": {"type": "string", "enum": [c.value for c in Confidence]},
            "evidence": {"type": "array", "items": evidence_item},
            "origin_trace": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": ["verdict", "confidence", "evidence", "origin_trace", "reasoning"],
        "additionalProperties": False,
    }


def _search_evaluator(tier: Tier, labels: list[Label]) -> Evaluator:
    schema = _schema(labels)

    def evaluate(claim: str, classification: Classification, budget: Budget) -> Verdict:
        prompt = load_prompt(tier.value)
        with span(
            f"evaluator.{tier.value}",
            config=budget.config,
            prompt_version=prompt.version,
            prompt_name=prompt.name,
        ) as rec:
            completion = complete(
                span_name=f"evaluator.{tier.value}.research",
                prompt=prompt,
                model=budget.config.evaluator_model,
                user_text=claim,
                budget=budget,
                max_tokens=EVALUATOR_MAX_TOKENS,
                schema=schema,
                tools=[web_search_tool(budget.config.max_searches)],
                effort=EVALUATOR_EFFORT,
                # Search-heavy claims can run long with nothing to show for it until the whole
                # response is ready; streaming avoids the ~360s APITimeoutError that caused on
                # the buffered call (see README's Known failures). No-op in mock mode.
                stream=True,
            )
            data = parse_json_object(completion.text, what=f"evaluator.{tier.value}")

            # Evidence must point at pages the search tool really returned; drop anything else
            # (a URL written from memory is worse than no URL).
            evidence: list[Evidence] = []
            dropped = 0
            for item in data["evidence"]:
                if item["source_url"] in completion.retrieved_urls:
                    evidence.append(Evidence(**item))
                else:
                    dropped += 1
            verdict = Verdict(
                tier=tier,
                verdict=Label(data["verdict"]),
                confidence=Confidence(data["confidence"]),
                evidence=evidence,
                origin_trace=data["origin_trace"],
                reasoning=data["reasoning"],
            )
            rec.update(
                verdict=verdict.verdict,
                confidence=verdict.confidence,
                evidence_kept=len(evidence),
                evidence_dropped_ungrounded=dropped,
            )
            return verdict

    return evaluate


_CORE = [Label.SUPPORTED, Label.NOT_SUPPORTED, Label.MIXED]

EVALUATORS: dict[Tier, Evaluator] = {
    Tier.STATISTICAL_DATA: _search_evaluator(Tier.STATISTICAL_DATA, _CORE),
    Tier.PROVENANCE_ONLY: _search_evaluator(Tier.PROVENANCE_ONLY, [*_CORE, Label.PROVENANCE_ONLY]),
}


def evaluate(claim: str, classification: Classification, budget: Budget) -> Verdict:
    """Dispatch on tier. Unimplemented tiers degrade to an explicit verdict, never a guess."""
    assert classification.tier is not None
    evaluator = EVALUATORS.get(classification.tier)
    if evaluator is None:
        return not_implemented(classification.tier, classification.reasoning)
    return evaluator(claim, classification, budget)
