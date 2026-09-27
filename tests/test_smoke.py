import pytest

from app.config import DEFAULT_WEB_SEARCH_TOOL, BudgetExceededError, Config, check_budget
from app.llm import web_search_tool
from app.prompts import PROMPTS_DIR, load_prompt


@pytest.mark.parametrize("name", ["classifier", "statistical_data", "provenance_only"])
def test_prompt_loads_with_version(name: str) -> None:
    prompt = load_prompt(name)
    # Any positive integer version is valid. This used to assert `== "1"`, which broke the moment
    # `provenance_only` was bumped to v3 - the number changes every time a prompt is revised.
    assert prompt.version.isdigit() and int(prompt.version) >= 1
    assert prompt.text


def test_every_prompt_file_is_versioned() -> None:
    for path in PROMPTS_DIR.glob("*.md"):
        assert load_prompt(path.stem).version != "unversioned", path.name


def test_search_tool_and_effort_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_WEB_SEARCH_TOOL", raising=False)
    monkeypatch.delenv("APP_EVALUATOR_EFFORT", raising=False)
    cfg = Config.from_env()
    assert cfg.web_search_tool_type == DEFAULT_WEB_SEARCH_TOOL == "web_search_20260209"
    assert cfg.evaluator_effort == "medium"
    assert web_search_tool(cfg.max_searches)["type"] == DEFAULT_WEB_SEARCH_TOOL


def test_search_tool_and_effort_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_WEB_SEARCH_TOOL", "web_search_20250305")
    monkeypatch.setenv("APP_EVALUATOR_EFFORT", "low")
    cfg = Config.from_env()
    assert cfg.web_search_tool_type == "web_search_20250305"
    assert cfg.evaluator_effort == "low"
    tool = web_search_tool(cfg.max_searches, cfg.web_search_tool_type)
    assert tool["type"] == "web_search_20250305"
    assert tool["max_uses"] == cfg.max_searches


def test_budget_caps_enforced() -> None:
    cfg = Config(max_steps=3, max_cost_usd=0.10)
    check_budget(cfg, steps=3, cost_usd=0.10)
    with pytest.raises(BudgetExceededError):
        check_budget(cfg, steps=4, cost_usd=0.0)
    with pytest.raises(BudgetExceededError):
        check_budget(cfg, steps=1, cost_usd=0.11)
