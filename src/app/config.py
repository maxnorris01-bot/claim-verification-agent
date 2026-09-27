"""Runtime configuration, read from environment variables.

Every agent loop must respect `max_steps` and `max_cost_usd`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

LLM_MODES = ("mock", "live")
SEARCH_BACKENDS = ("anthropic", "tavily")
# Dynamic filtering (the model writes code to filter search results before reading them); needs
# Sonnet 4.6+/Opus 4.6+. Configurable (APP_WEB_SEARCH_TOOL) so it can be compared against the older
# `web_search_20250305` tool for latency/cost - see docs/working-notes-and-decisions.md.
DEFAULT_WEB_SEARCH_TOOL = "web_search_20260209"


@dataclass(frozen=True)
class Config:
    max_steps: int = 12
    # $0.25 (the original placeholder) was too tight once the streaming fix (llm.py) let
    # search-heavy evaluator calls actually run to completion instead of hitting the old
    # ~360s APITimeoutError first: the live sanity check hit $0.319 and $0.183 on the *same*
    # claim across two runs, both over $0.25. $0.50 gives real headroom for a legitimately
    # heavy multi-search claim while remaining a genuine circuit breaker, not a rubber stamp.
    max_cost_usd: float = 0.50
    tracing_disabled: bool = False
    classifier_model: str = "claude-haiku-4-5"
    evaluator_model: str = "claude-sonnet-5"
    max_searches: int = 4
    web_search_tool_type: str = DEFAULT_WEB_SEARCH_TOOL
    evaluator_effort: str = "medium"
    # "anthropic" (default): the model drives Anthropic's server-side web search tool.
    # "tavily": we run the searches ourselves (app.search) and make one tool-less model call.
    search_backend: str = "anthropic"
    # "mock" (default): app.llm.get_client returns app.mock_llm.MockAnthropicClient - zero API
    # calls, zero cost, no key required. "live": the real Anthropic client, real cost. Never
    # defaults to "live" - every entry point (CLI, eval harness) is free unless explicitly opted
    # in via APP_LLM_MODE=live, e.g. `make eval-fast-live`.
    llm_mode: str = "mock"

    def __post_init__(self) -> None:
        if self.llm_mode not in LLM_MODES:
            raise ValueError(f"APP_LLM_MODE must be one of {LLM_MODES}, got {self.llm_mode!r}")
        if self.search_backend not in SEARCH_BACKENDS:
            raise ValueError(
                f"APP_SEARCH_BACKEND must be one of {SEARCH_BACKENDS}, got {self.search_backend!r}"
            )

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            max_steps=int(os.environ.get("APP_MAX_STEPS", "12")),
            max_cost_usd=float(os.environ.get("APP_MAX_COST_USD", "0.50")),
            tracing_disabled=os.environ.get("APP_TRACING_DISABLED", "0") == "1",
            classifier_model=os.environ.get("APP_CLASSIFIER_MODEL", "claude-haiku-4-5"),
            evaluator_model=os.environ.get("APP_EVALUATOR_MODEL", "claude-sonnet-5"),
            max_searches=int(os.environ.get("APP_MAX_SEARCHES", "4")),
            web_search_tool_type=os.environ.get("APP_WEB_SEARCH_TOOL", DEFAULT_WEB_SEARCH_TOOL),
            evaluator_effort=os.environ.get("APP_EVALUATOR_EFFORT", "medium"),
            search_backend=os.environ.get("APP_SEARCH_BACKEND", "anthropic"),
            llm_mode=os.environ.get("APP_LLM_MODE", "mock"),
        )


def load_env() -> None:
    """Load `.env` from the working directory (entry points call this once; never overrides)."""
    load_dotenv(find_dotenv(usecwd=True))


class BudgetExceededError(RuntimeError):
    """Raised when an agent run exceeds its step or cost cap."""


def check_budget(config: Config, steps: int, cost_usd: float) -> None:
    if steps > config.max_steps:
        raise BudgetExceededError(f"step cap exceeded: {steps} > {config.max_steps}")
    if cost_usd > config.max_cost_usd:
        raise BudgetExceededError(
            f"cost cap exceeded: ${cost_usd:.3f} > ${config.max_cost_usd:.3f}"
        )
