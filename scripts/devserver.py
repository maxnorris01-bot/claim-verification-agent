"""Local dev server for hands-on latency/cost feel-testing before the go/no-go call.

Not a production surface - no auth, single-user, binds to localhost only. Type a claim into a
browser, run it through the real pipeline (mock or live, whatever APP_LLM_MODE /
APP_SEARCH_BACKEND / APP_EVALUATOR_MODEL are set to), and see the wall-clock time, cost, and full
Verdict - the same numbers `make eval-fast-live` reports in aggregate, felt one claim at a time.

    APP_LLM_MODE=live APP_SEARCH_BACKEND=tavily APP_EVALUATOR_MODEL=claude-haiku-4-5 \\
        uv run python scripts/devserver.py

Then open http://127.0.0.1:8000. Every submission in live mode costs real API money - the page
shows a running session total so that's never a surprise. Leaving APP_LLM_MODE unset (or "mock")
runs instantly against the mock client and is free, but doesn't tell you anything about latency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from flask import Flask, render_template_string, request

from app.config import BudgetExceededError, Config, load_env
from app.llm import Budget, LLMOutputError
from app.pipeline import run
from app.verdict import Verdict

load_env()
app = Flask(__name__)


@dataclass
class CheckResult:
    latency_s: float
    cost_usd: float = 0.0
    steps: int = 0
    verdict: Verdict | None = None
    error: str | None = None


@dataclass
class SessionStats:
    n_checks: int = 0
    total_cost_usd: float = 0.0
    total_latency_s: float = 0.0

    @property
    def avg_latency_s(self) -> float:
        return self.total_latency_s / self.n_checks if self.n_checks else 0.0


STATS = SessionStats()

PAGE = """
<!doctype html>
<title>Claim Verification - dev server</title>
<style>
  body {
    font-family: -apple-system, sans-serif; max-width: 720px; margin: 40px auto;
    padding: 0 16px; color: #1a1a1a;
  }
  textarea { width: 100%; height: 80px; font-size: 15px; padding: 8px; box-sizing: border-box; }
  button { font-size: 15px; padding: 8px 20px; margin-top: 8px; cursor: pointer; }
  .banner { padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
  .banner.mock { background: #fff3cd; border: 1px solid #ffe69c; }
  .banner.live { background: #e7f5ea; border: 1px solid #b7e0c0; }
  .stats { color: #666; font-size: 13px; margin-top: 4px; }
  #status { display: none; margin-top: 12px; color: #555; }
  .result { margin-top: 24px; padding: 16px; border: 1px solid #ddd; border-radius: 8px; }
  .verdict { font-size: 20px; font-weight: 600; }
  .meta { color: #666; font-size: 13px; margin: 4px 0 16px; }
  .field { margin-bottom: 12px; }
  .field-label {
    font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: #888;
  }
  .evidence-item { margin: 6px 0; padding-left: 12px; border-left: 2px solid #ddd; }
  .error { color: #a00; }
  a { color: #06c; }
</style>

<h2>Claim Verification - dev server</h2>

{% if is_live %}
<div class="banner live">
  <strong>Live mode.</strong> Backend: <code>{{ backend }}</code>
  &middot; Evaluator: <code>{{ evaluator_model }}</code>
  &middot; Every submission below costs real API money.
</div>
{% else %}
<div class="banner mock">
  <strong>Mock mode.</strong> Responses are fake and instant - set <code>APP_LLM_MODE=live</code>
  before starting this server to test for real.
</div>
{% endif %}

<form method="post" action="/check" onsubmit="onCheckSubmit()">
  <textarea name="claim" placeholder="Enter a claim to check..." required>{{ claim }}</textarea>
  <br>
  <button id="go" type="submit">Check claim</button>
  <div id="status">Checking your claim - this can take up to ~20s for a fresh, live claim.</div>
</form>

<script>
  function onCheckSubmit() {
    document.getElementById('status').style.display = 'block';
    var btn = document.getElementById('go');
    btn.disabled = true;
    btn.innerText = 'Checking…';
  }
</script>

<div class="stats">
  Session: {{ stats_line }}
</div>

{% if result %}
<div class="result">
  {% if result.error %}
    <div class="error"><strong>Error:</strong> {{ result.error }}</div>
  {% else %}
    <div class="verdict">
      {{ result.verdict.verdict }}{% if confidence_label %} ({{ confidence_label }}){% endif %}
    </div>
    <div class="meta">{{ meta_line }}</div>

    <div class="field">
      <div class="field-label">Reasoning</div>
      {{ result.verdict.reasoning }}
    </div>

    <div class="field">
      <div class="field-label">Origin trace</div>
      {{ result.verdict.origin_trace }}
    </div>

    {% if result.verdict.evidence %}
    <div class="field">
      <div class="field-label">Evidence</div>
      {% for e in result.verdict.evidence %}
      <div class="evidence-item">
        "{{ e.claim_snippet }}" &mdash;
        <a href="{{ e.source_url }}" target="_blank" rel="noopener">{{ e.source_url }}</a>
        <br>{{ e.note }}
      </div>
      {% endfor %}
    </div>
    {% endif %}
  {% endif %}
</div>
{% endif %}
"""


def _run_claim(claim: str) -> CheckResult:
    config = Config.from_env()
    budget = Budget(config)
    start = time.monotonic()
    try:
        verdict = run(claim, budget=budget)
    except (BudgetExceededError, LLMOutputError) as exc:
        return CheckResult(latency_s=time.monotonic() - start, error=str(exc))
    latency_s = time.monotonic() - start
    STATS.n_checks += 1
    STATS.total_cost_usd += budget.cost_usd
    STATS.total_latency_s += latency_s
    return CheckResult(
        latency_s=latency_s, cost_usd=budget.cost_usd, steps=budget.steps, verdict=verdict
    )


def _render(result: CheckResult | None, claim: str) -> str:
    config = Config.from_env()
    stats_line = f"{STATS.n_checks} checked · ${STATS.total_cost_usd:.4f} total"
    if STATS.n_checks:
        stats_line += f" · {STATS.avg_latency_s:.1f}s avg"
    meta_line = confidence_label = ""
    if result and result.verdict:
        tier = result.verdict.tier or "n/a"
        meta_line = f"tier: {tier} · {result.latency_s:.2f}s · ${result.cost_usd:.4f}"
        meta_line += f" · {result.steps} step(s)"
        if result.verdict.confidence:
            confidence_label = f"{result.verdict.confidence} confidence"
    return render_template_string(
        PAGE,
        is_live=config.llm_mode == "live",
        backend=config.search_backend,
        evaluator_model=config.evaluator_model,
        claim=claim,
        stats_line=stats_line,
        result=result,
        meta_line=meta_line,
        confidence_label=confidence_label,
    )


@app.get("/")
def index() -> str:
    return _render(result=None, claim="")


@app.post("/check")
def check() -> str:
    claim = request.form.get("claim", "")
    return _render(result=_run_claim(claim), claim=claim)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
