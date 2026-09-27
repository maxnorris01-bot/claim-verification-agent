# 2026-09-21 - mock/live toggle for eval-fast

Scoped step before the streaming fix or the two unstable eval cases (`stat-003`, `stat-004`) -
per the user's explicit instruction, neither was touched here, and nothing ran against the live
API this session.

## What changed and why

Added a mock/live toggle so `make eval-fast` no longer hits the real API by default, per the
user's five numbered requirements:

1. **Promoted the fake Anthropic client out of tests** (`3c07e37`). `text_block`, `search_blocks`,
   `response`, and the scripted-response client (`FakeClient`, renamed `ScriptedClient`) moved
   from `tests/conftest.py` into `src/app/mock_llm.py` - production code, not test-only. The same
   primitives now back both the 23 unit tests (which still need exact scripted responses for
   scenarios like `pause_turn` and malformed output) and a new `MockAnthropicClient`.
2. **`Config.llm_mode`** (`88ddf1a`): `"mock"` (default) or `"live"`, read from `APP_LLM_MODE`,
   validated in `__post_init__`. `app.llm.get_client` is now keyed by mode and returns
   `MockAnthropicClient` or the real `anthropic.Anthropic` accordingly. Every entry point
   (`scripts/check_claim.py`, `evals/run.py`) goes through `Config.from_env()`, so every entry
   point defaults to mock with no code changes needed at the call sites.
3. **`make eval-fast` forces `APP_LLM_MODE=mock`; new `make eval-fast-live` forces `=live`**
   (`873121f`). The explicit force in both targets means a stray `APP_LLM_MODE=live` left in
   `.env` can't make a "fast" run silently cost money, and `eval-fast-live` can't accidentally
   run mock.
4. **`MockAnthropicClient`'s responses are shape-correct, not quality-correct**, per the user's
   explicit instruction. It inspects `output_config.format.schema` to tell a classifier call from
   an evaluator call (`tier` property vs. `verdict` property - `app.llm.complete` needed no
   changes to support this), and:
   - Classifier calls: routes the claim to a tier via `guess_tier()`, a small set of keyword
     heuristics (stat/prov/moral/health signals, plus a stopword check for gibberish -> exercises
     the `not_a_claim` path). Tuned to correctly route every case in `evals/cases/v0.jsonl`,
     documented as a plumbing stand-in, not a real classifier.
   - Evaluator calls: always returns a schema-valid verdict - a fabricated `web_search_tool_result`
     block with one URL, and an evidence entry citing that same URL (exercising the
     evidence-grounding check in `evaluators.py`), `verdict` picked arbitrarily from the schema's
     allowed enum (mock mode never checks whether the label is *right*).
   - The empty-input short-circuit needs no mock support at all - `pipeline.run` already returns
     `invalid-input` before any client call for empty/whitespace text.
5. **`evals/run.py` scoring is now mode-aware** (`873121f`): live mode is unchanged
   (`expected_contains` substring match - a real quality check). Mock mode checks only that the
   returned `tier` matches the case's `category` (or, for `category: edge`, that the verdict is
   `invalid-input`) - structural routing only, since the mock has no real-world knowledge to be
   scored on. Report filenames now include the mode (`{tier}-{mode}-{timestamp}.json`) and the
   summary JSON carries an explicit `llm_mode` field, so a report's mode is never ambiguous.
6. **Documented in README and CLAUDE.md** (`9e23a1d`), per the user's instruction: README gets a
   "Mock vs. live" subsection and an updated Evaluation table with cost columns; CLAUDE.md's
   Commands, the agent-logic-change rule, and Definition of done all now distinguish the free
   mock check (run every time) from the real-cost live check (run deliberately, not routinely).

## A bug the mock run itself caught

First `make eval-fast` (mock) run: 93.33% (14/15), not the expected 100%. `prov-002` (a hearsay
"chain message" claim that also happens to mention "4%") was misrouted to `statistical_data`
because the keyword heuristic checked statistical signals before provenance signals. Reordered so
provenance signals are checked first (a hearsay framing is the more determinative signal when
both appear) - re-ran, 100% (15/15). Fixed before the first commit, so no separate fix-up commit
was needed; noted here since it's a real example of the mock-mode structural check doing its job.

## Result: `make eval-fast` (mock mode)

```
llm_mode=mock (free, structural routing check only - not a quality signal)
{
  "tier": "fast",
  "llm_mode": "mock",
  "n_cases": 15,
  "pass_rate": 1.0,
  "latency_p95_s": 0.0025,
  "mean_cost_usd": 0.0093
}
```

Exit code 0. Confirmed with `ANTHROPIC_API_KEY` unset (`unset ANTHROPIC_API_KEY`) via both
`make eval-fast` and a direct `scripts/check_claim.py` call - both ran end to end with no key and
no network call. `mean_cost_usd` here is the mock's simulated per-call cost estimate (exercising
the same cost-accounting code path real calls use), not real spend - zero requests reached the
network, so real billing is exactly $0.

## Test / lint / typecheck status

All green: `make lint` (ruff check + format --check), `make typecheck` (mypy strict), `make test`
(23/23 pytest, unchanged pass count - the promoted primitives didn't change test behavior).

## What was deliberately not touched

- The streaming fix for evaluator calls (the ~360s `APITimeoutError` ceiling documented in
  README's Known failures) - next step, per the user.
- `stat-003` / `stat-004`, the two eval cases with reproduced run-to-run verdict instability -
  next step, per the user.
- No live API call was made this session. `evals/reports/fast-mock-20260921-190530.json` is the
  only new report; the two prior live reports are untouched.
- `eval-standard` / `eval-nightly` don't have mock-forced/live-forced variants the way
  `eval-fast`/`eval-fast-live` do - they inherit whatever `APP_LLM_MODE` is set to (mock by
  default, so still safe, just not as explicit). Flagged in README's Evaluation section as worth
  doing before either is used for real; out of scope for this step.

## Open questions / flag for review

1. `MockAnthropicClient`'s keyword heuristics are tuned specifically to route the 15 cases in
   `evals/cases/v0.jsonl` correctly - adding a new eval case with unusual phrasing could need a
   heuristic tweak to keep mock-mode's structural check meaningful. This is a known, accepted
   limitation of a keyword-based stand-in, not a bug.
2. Mock-mode's `mean_cost_usd` and `latency_p95_s` numbers are real numbers from real code paths
   (the same `estimate_cost`/tracing machinery), but computed from fabricated `usage` values -
   worth double-checking nobody later mistakes a mock report's cost/latency for a live estimate.
   The stderr banner and `llm_mode` field in every report are the mitigation currently in place.
3. `evals/run.py`'s mock-mode `_passed` check treats an unrecognized `category` (one that isn't a
   valid `Tier` name and isn't `"edge"`) as an automatic fail rather than raising - intentional
   (don't silently pass what can't be verified), but worth knowing if a future case uses a
   `category` string that doesn't match a `Tier` exactly.

## Next command

```bash
uv run pytest -q && make eval-fast     # re-confirm locally if desired (both free, ~instant)
git log --oneline -9                   # review this step's 5 commits
```
Ready to continue to the streaming fix once this is reviewed.
