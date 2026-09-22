"""Tiered eval runner.

    python -m evals.run --tier fast|standard|nightly

Exits non-zero if thresholds in evals/thresholds.yaml are missed, so CI can gate on it.

Scoring depends on `Config.llm_mode` (`APP_LLM_MODE`, default "mock"):
  * live: deterministic - `expected_contains` substrings matched (case-insensitively) against the
    compact JSON of the returned Verdict, e.g. `"verdict": "mixed"`. This is a real quality check
    and costs real API money (`make eval-fast-live`).
  * mock: structural only - the returned `tier` must match the case's `category` (or, for
    `category: edge`, the verdict must be `invalid-input`). The mock client
    (`app.mock_llm.MockAnthropicClient`) has no real-world knowledge, so verdict *labels*
    (supported/mixed/...) are never checked in this mode - a 100% mock pass rate is a plumbing
    signal, not a quality signal. This is the default (`make eval-fast`), costs nothing, and
    needs no API key.

Add LLM-as-judge scorers in evals/judges.py and validate them against a human-labeled gold set
before trusting them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from app.config import Config, load_env
from app.llm import Budget
from app.pipeline import run as system_under_test
from app.prompts import PROMPTS_DIR, load_prompt
from app.verdict import Label, Tier, Verdict

EVALS_DIR = Path(__file__).resolve().parent
TIER_SIZES: dict[str, int | None] = {"fast": 15, "standard": 50, "nightly": None}


def load_cases(tier: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted((EVALS_DIR / "cases").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                cases.append(json.loads(line))
    limit = TIER_SIZES[tier]
    return cases if limit is None else cases[:limit]


def prompt_versions() -> dict[str, str]:
    return {p.stem: load_prompt(p.stem).version for p in sorted(PROMPTS_DIR.glob("*.md"))}


def _passed(case: dict[str, Any], verdict: Verdict, output: str, config: Config) -> bool:
    if config.llm_mode == "live":
        expected = case.get("expected_contains", [])
        return all(e.lower() in output.lower() for e in expected)
    # Mock mode: only structural routing is meaningful (see module docstring) - the mock has no
    # real-world knowledge, so verdict labels are never checked here.
    category = case.get("category", "")
    if category == "edge":
        return verdict.verdict == Label.INVALID_INPUT
    try:
        expected_tier = Tier(category)
    except ValueError:
        return False  # unknown category - can't structurally verify, don't silently pass it
    return verdict.tier == expected_tier


def score_case(case: dict[str, Any], config: Config) -> dict[str, Any]:
    budget = Budget(config)
    start = time.perf_counter()
    verdict: Verdict | None = None
    error: str | None = None
    try:
        verdict = system_under_test(case["input"], budget=budget)
    except Exception as exc:  # a crash is a failed case, not a crashed eval run
        error = repr(exc)
    latency = time.perf_counter() - start
    output = verdict.to_json() if verdict is not None else ""
    passed = error is None and verdict is not None and _passed(case, verdict, output, config)
    return {
        "id": case["id"],
        "category": case.get("category", "default"),
        "passed": passed,
        "latency_s": latency,
        "cost_usd": budget.cost_usd,
        "steps": budget.steps,
        "error": error,
        "output": output,
    }


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=list(TIER_SIZES), default="fast")
    args = parser.parse_args()
    load_env()
    config = Config.from_env()
    mode_note = (
        "real API cost, quality-checked"
        if config.llm_mode == "live"
        else "free, structural routing check only - not a quality signal"
    )
    print(f"llm_mode={config.llm_mode} ({mode_note})", file=sys.stderr)

    thresholds = yaml.safe_load((EVALS_DIR / "thresholds.yaml").read_text())
    cases = load_cases(args.tier)
    if not cases:
        print("No eval cases found.", file=sys.stderr)
        return 1

    results = [score_case(c, config) for c in cases]
    pass_rate = sum(r["passed"] for r in results) / len(results)
    latency_p95 = p95([r["latency_s"] for r in results])
    mean_cost = sum(r["cost_usd"] for r in results) / len(results)

    summary = {
        "tier": args.tier,
        "llm_mode": config.llm_mode,
        "prompt_versions": prompt_versions(),
        "n_cases": len(results),
        "pass_rate": round(pass_rate, 4),
        "latency_p95_s": round(latency_p95, 4),
        "mean_cost_usd": round(mean_cost, 4),
    }

    failures = []
    if pass_rate < thresholds["min_pass_rate"]:
        failures.append(f"pass_rate {pass_rate:.2%} < {thresholds['min_pass_rate']:.2%}")
    if latency_p95 > thresholds["max_latency_p95_s"]:
        failures.append(f"latency_p95 {latency_p95:.2f}s > {thresholds['max_latency_p95_s']}s")
    if mean_cost > thresholds["max_mean_cost_usd"]:
        failures.append(f"mean_cost ${mean_cost:.3f} > ${thresholds['max_mean_cost_usd']}")

    report_dir = EVALS_DIR / "reports"
    report_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (report_dir / f"{args.tier}-{config.llm_mode}-{stamp}.json").write_text(
        json.dumps({"summary": summary, "failures": failures, "results": results}, indent=2)
    )

    print(json.dumps(summary, indent=2))
    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
