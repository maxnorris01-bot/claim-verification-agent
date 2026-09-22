"""Check one claim from the command line.

    uv run python scripts/check_claim.py claim="According to Gallup, 5.6% of U.S. adults ..."
    uv run python scripts/check_claim.py --claim "..."

Prints the Verdict as JSON on stdout; steps and cost go to stderr.
"""

from __future__ import annotations

import argparse
import sys

from app.config import BudgetExceededError, Config, load_env
from app.llm import Budget
from app.pipeline import run


def parse_claim(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("claim", nargs="?", help='the claim, as `claim="..."` or a bare string')
    parser.add_argument("--claim", dest="claim_flag", help="the claim (alternative form)")
    args = parser.parse_args(argv)
    value: str | None = args.claim_flag if args.claim_flag is not None else args.claim
    if value is None:
        parser.error('provide a claim: claim="..."')
    return value.removeprefix("claim=") if value.startswith("claim=") else value


def main(argv: list[str] | None = None) -> int:
    load_env()
    claim = parse_claim(sys.argv[1:] if argv is None else argv)
    budget = Budget(Config.from_env())
    try:
        verdict = run(claim, budget=budget)
    except BudgetExceededError as exc:
        print(f"Budget exceeded: {exc}", file=sys.stderr)
        return 2
    print(verdict.to_json(indent=2))
    print(f"steps={budget.steps} cost=${budget.cost_usd:.4f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
