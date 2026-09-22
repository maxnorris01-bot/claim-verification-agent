"""claim -> classify -> route -> retrieve -> evaluate -> Verdict.

`run` is the stable entry point used by the CLI and the eval harness.
"""

from __future__ import annotations

from app.classifier import classify
from app.config import Config
from app.evaluators import evaluate
from app.llm import Budget
from app.tracing import span
from app.verdict import Verdict, invalid_input


def run(claim: str, *, config: Config | None = None, budget: Budget | None = None) -> Verdict:
    """Check one claim. Raises `BudgetExceededError` if the step or cost cap is hit.

    Pass a `budget` to read the steps and cost spent afterwards (the eval harness does).
    """
    cfg = config or (budget.config if budget else Config.from_env())
    budget = budget or Budget(cfg)

    with span("pipeline.run", config=cfg, input_chars=len(claim)) as rec:
        if not claim.strip():
            rec["outcome"] = "empty-input"
            return invalid_input("The input was empty; there is no claim to check.")

        classification = classify(claim.strip(), budget)
        rec["tier"] = classification.tier
        if classification.tier is None:
            return invalid_input(
                f"The input was not a checkable claim. Classifier reasoning: "
                f"{classification.reasoning}"
            )

        verdict = evaluate(claim.strip(), classification, budget)
        rec.update(verdict=verdict.verdict, steps=budget.steps, cost_usd=round(budget.cost_usd, 5))
        return verdict
