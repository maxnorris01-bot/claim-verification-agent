from typing import Any

import pytest

from app.config import BudgetExceededError, Config
from app.llm import Budget, LLMOutputError
from app.pipeline import run
from app.verdict import Confidence, Label, Tier
from tests.conftest import response, search_blocks, text_block

URL = "https://example.org/original-report"


def classifier_reply(tier: str) -> Any:
    return response([text_block({"reasoning": "because", "tier": tier})])


def evaluator_reply(verdict: str, urls: list[str], **kwargs: Any) -> Any:
    payload = {
        "verdict": verdict,
        "confidence": "medium",
        "evidence": [{"claim_snippet": "5.6%", "source_url": u, "note": "n"} for u in urls],
        "origin_trace": "Original report, 2021.",
        "reasoning": "The figure matches.",
    }
    return response([*search_blocks("q", [URL]), text_block(payload)], searches=1, **kwargs)


def test_empty_input_short_circuits_without_calling_the_model(install_client: Any) -> None:
    client = install_client([])
    for text in ["", "   \n"]:
        v = run(text)
        assert v.verdict is Label.INVALID_INPUT
        assert v.tier is None
    assert client.calls == []


def test_not_a_claim_is_invalid_input(install_client: Any) -> None:
    client = install_client([classifier_reply("not_a_claim")])
    v = run("asdkj qwpo zzxv")
    assert v.verdict is Label.INVALID_INPUT and v.tier is None
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "tier", ["scientific_empirical", "historical_factual", "contested_unfalsifiable"]
)
def test_unimplemented_tiers_degrade_gracefully(install_client: Any, tier: str) -> None:
    client = install_client([classifier_reply(tier)])
    v = run("some claim")
    assert v.verdict is Label.NOT_IMPLEMENTED
    assert v.tier == Tier(tier)
    assert len(client.calls) == 1  # classifier only; no evaluator, no search


def test_statistical_tier_end_to_end(install_client: Any) -> None:
    client = install_client(
        [classifier_reply("statistical_data"), evaluator_reply("supported", [URL])]
    )
    budget = Budget(Config())
    v = run("According to Gallup, 5.6% ...", budget=budget)
    assert v.tier is Tier.STATISTICAL_DATA
    assert v.verdict is Label.SUPPORTED
    assert v.confidence is Confidence.MEDIUM
    assert [e.source_url for e in v.evidence] == [URL]
    assert budget.steps == 2
    assert budget.cost_usd > 0.01  # tokens plus one web search
    classifier_call, evaluator_call = client.calls
    assert classifier_call["model"] == "claude-haiku-4-5"
    assert "tools" not in classifier_call
    assert evaluator_call["tools"][0]["name"] == "web_search"
    assert evaluator_call["tools"][0]["max_uses"] == Config().max_searches


def test_provenance_tier_can_return_provenance_only(install_client: Any) -> None:
    install_client([classifier_reply("provenance_only"), evaluator_reply("provenance-only", [])])
    v = run("a chain message says ...")
    assert v.tier is Tier.PROVENANCE_ONLY
    assert v.verdict is Label.PROVENANCE_ONLY
    assert v.evidence == []


def test_statistical_schema_does_not_offer_provenance_only(install_client: Any) -> None:
    client = install_client([classifier_reply("statistical_data"), evaluator_reply("mixed", [URL])])
    run("a stat")
    enum = client.calls[1]["output_config"]["format"]["schema"]["properties"]["verdict"]["enum"]
    assert "provenance-only" not in enum


def test_evidence_urls_not_returned_by_search_are_dropped(install_client: Any) -> None:
    install_client(
        [
            classifier_reply("statistical_data"),
            evaluator_reply("supported", [URL, "https://made-up.example/from-memory"]),
        ]
    )
    v = run("a stat")
    assert [e.source_url for e in v.evidence] == [URL]


def test_pause_turn_is_resumed_and_counts_as_a_step(install_client: Any) -> None:
    paused = response(search_blocks("q", [URL]), stop_reason="pause_turn", searches=1)
    client = install_client(
        [classifier_reply("statistical_data"), paused, evaluator_reply("supported", [URL])]
    )
    budget = Budget(Config())
    v = run("a stat", budget=budget)
    assert v.verdict is Label.SUPPORTED
    assert budget.steps == 3
    resumed = client.calls[2]["messages"]
    assert resumed[-1]["role"] == "assistant"  # paused turn re-sent, no synthetic "continue"
    assert URL in {
        u.url
        for b in resumed[-1]["content"]
        if b.type == "web_search_tool_result"
        for u in b.content
    }


def test_step_cap_raises_before_the_extra_request(install_client: Any) -> None:
    client = install_client(
        [classifier_reply("statistical_data"), evaluator_reply("supported", [URL])]
    )
    with pytest.raises(BudgetExceededError, match="step cap"):
        run("a stat", config=Config(max_steps=1))
    assert len(client.calls) == 1  # the evaluator request was never sent


def test_cost_cap_raises_rather_than_returning_a_verdict(install_client: Any) -> None:
    install_client(
        [
            classifier_reply("statistical_data"),
            evaluator_reply("supported", [URL], input_tokens=50_000),
        ]
    )
    with pytest.raises(BudgetExceededError, match="cost cap"):
        run("a stat", config=Config(max_cost_usd=0.05))


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_unusable_responses_raise_instead_of_guessing(
    install_client: Any, stop_reason: str
) -> None:
    install_client([response([text_block("{")], stop_reason=stop_reason)])
    with pytest.raises(LLMOutputError):
        run("a stat")


def test_malformed_json_raises(install_client: Any) -> None:
    install_client([response([text_block("not json")])])
    with pytest.raises(LLMOutputError, match="valid JSON"):
        run("a stat")
