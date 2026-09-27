from typing import Any

import pytest

from app import search
from app.config import Config
from app.llm import Budget
from app.pipeline import run
from app.verdict import Label
from tests.conftest import response, text_block

KEPT = "https://example.org/original-report"
INVENTED = "https://example.org/from-memory"


def test_search_backend_defaults_to_anthropic_and_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_SEARCH_BACKEND", raising=False)
    assert Config.from_env().search_backend == "anthropic"
    monkeypatch.setenv("APP_SEARCH_BACKEND", "tavily")
    assert Config.from_env().search_backend == "tavily"
    with pytest.raises(ValueError):
        Config(search_backend="bing")


def test_build_queries_are_two_angles_without_a_model_call() -> None:
    queries = search.build_queries("Gallup found 5.6%")
    assert queries[0] == "Gallup found 5.6%"
    assert len(queries) == 2 and queries[1] != queries[0]


def test_mock_mode_needs_no_key_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    results = search.search_many(["q"], Config(llm_mode="mock"))
    assert [r.url for r in results] == [search.MOCK_URL]


def test_live_mode_without_key_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(search.SearchError, match="TAVILY_API_KEY"):
        search.search_many(["q"], Config(llm_mode="live"))


def test_format_user_message_wraps_claim_and_results() -> None:
    msg = search.format_user_message("c", [search.SearchResult("T", "https://a", "body")])
    assert "<claim>c</claim>" in msg and "<url>https://a</url>" in msg
    assert "<snippet>body</snippet>" in msg


def test_tavily_backend_makes_one_toolless_call_and_grounds_evidence(
    install_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_search(queries: list[str], config: Config) -> list[search.SearchResult]:
        return [search.SearchResult("Report", KEPT, "The rate was 5.6%.")]

    monkeypatch.setattr(search, "search_many", fake_search)
    payload = {
        "verdict": "supported",
        "confidence": "medium",
        "evidence": [
            {"claim_snippet": "5.6%", "source_url": KEPT, "note": "n"},
            {"claim_snippet": "5.6%", "source_url": INVENTED, "note": "n"},
        ],
        "origin_trace": "Report.",
        "reasoning": "Matches.",
    }
    client = install_client(
        [
            response([text_block({"reasoning": "r", "tier": "statistical_data"})]),
            response([text_block(payload)]),
        ]
    )
    budget = Budget(Config(search_backend="tavily"))
    v = run("Gallup found 5.6%", budget=budget)

    assert v.verdict is Label.SUPPORTED
    assert [e.source_url for e in v.evidence] == [KEPT]  # the invented URL is dropped
    _, evaluator_call = client.calls
    assert "tools" not in evaluator_call
    assert KEPT in evaluator_call["messages"][0]["content"]
    assert "Retrieval mode" in evaluator_call["system"]
    assert budget.steps == 2  # classifier + one evaluator call, no search loop
    assert budget.cost_usd >= 2 * search.TAVILY_USD_PER_SEARCH
