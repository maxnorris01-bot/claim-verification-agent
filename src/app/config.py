"""Runtime configuration, read from environment variables.

Every agent loop must respect `max_steps` and `max_cost_usd`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


@dataclass(frozen=True)
class Config:
    max_steps: int = 12
    max_cost_usd: float = 0.25
    tracing_disabled: bool = False
    classifier_model: str = "claude-haiku-4-5"
    evaluator_model: str = "claude-sonnet-5"
    max_searches: int = 4

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            max_steps=int(os.environ.get("APP_MAX_STEPS", "12")),
            max_cost_usd=float(os.environ.get("APP_MAX_COST_USD", "0.25")),
            tracing_disabled=os.environ.get("APP_TRACING_DISABLED", "0") == "1",
            classifier_model=os.environ.get("APP_CLASSIFIER_MODEL", "claude-haiku-4-5"),
            evaluator_model=os.environ.get("APP_EVALUATOR_MODEL", "claude-sonnet-5"),
            max_searches=int(os.environ.get("APP_MAX_SEARCHES", "4")),
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
