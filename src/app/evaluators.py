"""Stage 2: per-tier evaluators. Only `statistical_data` and `provenance_only` exist in v0.

Both run a web-search research call and return a structured verdict; they differ in prompt and in
the verdict labels they may return. Other tiers get an explicit `not-implemented` Verdict.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app import search
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


def _schema(labels: list[Label], *, compact: bool = False) -> dict[str, Any]:
    """Build the evaluator's output schema.

    `compact=True` is for the tavily backend only (see `_search_evaluator`): a prose request to
    keep evidence/reasoning short (tried first, in `search.RETRIEVED_MODE_NOTE`) was not reliably
    followed - live runs showed evidence counts and reasoning length essentially unchanged.
    `maxLength` on the string fields below is a real, API-enforced constraint. `minItems`/
    `maxItems` on the evidence array is NOT: a live run confirmed the API rejects it outright
    ("For 'array' type, property 'maxItems' is not supported"), so the array stays unbounded -
    the prompt still asks for at most 2 items, it just isn't backstopped by the schema.
    """
    evidence_item: dict[str, Any] = {
        "type": "object",
        "properties": {
            "claim_snippet": {"type": "string", **({"maxLength": 140} if compact else {})},
            "source_url": {"type": "string"},
            "note": {"type": "string", **({"maxLength": 200} if compact else {})},
        },
        "required": ["claim_snippet", "source_url", "note"],
        "additionalProperties": False,
    }
    evidence_schema: dict[str, Any] = {"type": "array", "items": evidence_item}
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": [label.value for label in labels]},
            "confidence": {"type": "string", "enum": [c.value for c in Confidence]},
            "evidence": evidence_schema,
            "origin_trace": {"type": "string", **({"maxLength": 280} if compact else {})},
            "reasoning": {"type": "string", **({"maxLength": 400} if compact else {})},
        },
        "required": ["verdict", "confidence", "evidence", "origin_trace", "reasoning"],
        "additionalProperties": False,
    }


def _search_evaluator(tier: Tier, labels: list[Label]) -> Evaluator:
    schema = _schema(labels)
    compact_schema = _schema(labels, compact=True)

    def evaluate(claim: str, classification: Classification, budget: Budget) -> Verdict:
        prompt = load_prompt(tier.value)
        config = budget.config
        with span(
            f"evaluator.{tier.value}",
            config=config,
            prompt_version=prompt.version,
            prompt_name=prompt.name,
            search_backend=config.search_backend,
        ) as rec:
            fetched_urls: set[str] = set()
            if config.search_backend == "tavily":
                # Retrieval outside the model: parallel searches, then ONE tool-less model call
                # over the snippets. See app/search.py.
                queries = search.build_queries(claim)
                with span("search.tavily", config=config, queries=queries) as search_rec:
                    results = search.search_many(queries, config)
                    budget.add_cost(len(queries) * search.TAVILY_USD_PER_SEARCH)
                    search_rec["n_results"] = len(results)
                fetched_urls = {r.url for r in results}
                completion = complete(
                    span_name=f"evaluator.{tier.value}.research",
                    prompt=replace(prompt, text=prompt.text + search.RETRIEVED_MODE_NOTE),
                    model=config.evaluator_model,
                    user_text=search.format_user_message(claim, results),
                    budget=budget,
                    max_tokens=EVALUATOR_MAX_TOKENS,
                    schema=compact_schema,
                )
            else:
                completion = complete(
                    span_name=f"evaluator.{tier.value}.research",
                    prompt=prompt,
                    model=config.evaluator_model,
                    user_text=claim,
                    budget=budget,
                    max_tokens=EVALUATOR_MAX_TOKENS,
                    schema=schema,
                    tools=[web_search_tool(config.max_searches, config.web_search_tool_type)],
                    effort=config.evaluator_effort,
                    # Search-heavy claims can run long with nothing to show for it until the
                    # whole response is ready; streaming avoids the ~360s APITimeoutError that
                    # caused on the buffered call (see README's Known failures). No-op in mock.
                    stream=True,
                )
            data = parse_json_object(completion.text, what=f"evaluator.{tier.value}")

            # Evidence must point at pages the search really returned; drop anything else
            # (a URL written from memory is worse than no URL).
            grounded_urls = completion.retrieved_urls | fetched_urls
            evidence: list[Evidence] = []
            dropped = 0
            for item in data["evidence"]:
                if item["source_url"] in grounded_urls:
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
        return not_implemented(classification.tier)
    return evaluator(claim, classification, budget)
