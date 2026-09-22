# Claim Verification Agent — v0 Spec

## Goal
A working, evaluated slice of the claim classifier + two tiers, proving the full pipeline shape (classify -> route -> retrieve -> evaluate -> verdict) before adding scope. Portfolio project for an applied AI / data analytics job search — the README and eval report are part of the deliverable, not an afterthought.

## In scope
- **Entry point:** `src/app/pipeline.py::run(claim: str) -> Verdict`, callable from a CLI script (`scripts/check_claim.py claim="..."`). No web UI in v0.
- **Classifier:** one LLM call that assigns the claim to exactly one of five tiers: `scientific_empirical`, `historical_factual`, `statistical_data`, `provenance_only`, `contested_unfalsifiable`. Always returns a tier plus its own brief reasoning.
- **Evaluators implemented for two tiers only:**
  - `statistical_data`: trace the claim back toward its original study/poll/source using web search; check for framing drift between the source and the claim as stated.
  - `provenance_only`: attempt corroboration via web search; if none is found beyond a single low-credibility source, label it honestly as provenance-only rather than forcing a true/false verdict.
- **Unimplemented tiers** (`scientific_empirical`, `historical_factual`, `contested_unfalsifiable`): the classifier still routes to them, but the evaluator returns a clear "tier not yet implemented" `Verdict` rather than crashing or guessing. This is intentional, not a bug — note it in the README's "known limitations."
- **Verdict output** (dataclass or typed dict — pick one and use it consistently):
  - `tier`, `verdict` (e.g. supported / not supported / mixed / provenance-only / not-implemented), `confidence` (low/medium/high), `evidence` (list of {claim_snippet, source_url, note}), `origin_trace` (best-effort earliest source found, with a hedge if incomplete), `reasoning`.
- **Retrieval:** Claude's built-in web search tool via the Anthropic API. No separate search API key.
- **Tracing:** every classifier call and every evaluator call goes through `app.tracing.span`, tagged with the prompt version.
- **Budget:** the whole `run()` call for one claim respects `Config.max_steps` / `max_cost_usd` from `app/config.py`. Raise `BudgetExceededError` rather than silently truncating.

## Eval set (`evals/cases/`)
10-15 cases total:
- 5-6 `statistical_data` claims with a known, checkable source (mix of accurately-repeated and drifted-framing claims)
- 5-6 `provenance_only` claims (things traceable only to a single low-credibility source, or outright fabricated-sounding claims)
- 1-2 claims that should route to an unimplemented tier, to confirm graceful degradation
- 1-2 edge cases: empty string input, non-claim gibberish input

Each case: `id`, `category` (tier name), `input`, and either `expected_contains` for simple checks or a rubric reference for judged cases (see `evals/rubrics/`). Build the rubric-based judge only after the deterministic cases pass — don't build both at once.

## Out of scope for v0 — do not implement
- Trending-claims homepage feed / Reddit / Google Trends ingestion
- Self-grading / accuracy track record (needs real verdicts to sit for a while before it can check outcomes — v1+ milestone)
- `scientific_empirical` and `historical_factual` evaluators (different retrieval strategies — literature quality weighting, primary-record verification — deliberately deferred)
- `contested_unfalsifiable` evaluator
- Any web/app UI

## Definition of done
- `make lint`, `make typecheck`, `make test` all pass
- `make eval-fast` passes `evals/thresholds.yaml`
- README results table filled in with real numbers from an eval report (not placeholders)
- At least one real observed failure documented in the README's "Known failures" section
- One ADR recorded for: (a) why the classifier ships ahead of full evaluator coverage, (b) why Claude's web search tool over a separate search API

## Explicit non-goals for this session
Don't scaffold the trending feed, don't stub self-grading data models, don't touch the other three tiers beyond making sure the classifier can name them and the pipeline handles them gracefully. If something outside this spec looks tempting to add "while we're in there," don't — note it instead as a follow-up.
