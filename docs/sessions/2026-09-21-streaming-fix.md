# 2026-09-21 - streaming fix for evaluator calls

Scoped step: fix the real, reproduced `APITimeoutError` (documented in README's Known failures)
by switching evaluator research calls from a blocking request to streaming. Per the user's
explicit instruction, did **not** touch the two unstable eval cases (`stat-003`/`stat-004`) or run
the full `make eval-fast-live` - only a targeted live sanity check via `scripts/check_claim.py`.

## What changed and why

1. **`app.llm.complete()` gains `stream: bool = False`** (`737917f`). When `True` and the live
   client is in use, a new `_create_message()` helper issues the request via
   `client.messages.stream(...)` + `.get_final_message()` instead of the buffered
   `client.messages.create(...)`. Both return the same `Message` shape, so nothing downstream
   (usage/tool-block inspection, `pause_turn` handling, cost accounting) needed to change. Mock
   mode is completely unaffected: `MockAnthropicClient` only implements `.create()`, and the
   streaming branch requires `config.llm_mode == "live"` - satisfies the user's requirement 2
   exactly (mock/live toggle unchanged; only the live client's request mechanism changes).
2. **`app.evaluators.py` passes `stream=True`** on the evaluator's `complete()` call
   (`0563054`) - both `statistical_data` and `provenance_only` go through the same
   `_search_evaluator`, so one line covers both. The classifier's call is untouched
   (`stream` defaults `False`) - it's short and cheap, nothing to fix there.
3. **A second, unrelated bug found and fixed live** (bundled into `737917f` since it blocked the
   first sanity-check run): `complete()` used to join *every* `text` content block together
   (`"".join(...)`) before parsing JSON. The very first live sanity-check call (see below)
   returned two complete, valid JSON objects in two separate text blocks; joining them produced
   `'{...}{...}'`, which failed to parse (`JSONDecodeError: Extra data`). Every call through this
   function passes a schema, and structured output guarantees the *first* text block is the valid
   JSON - so the fix takes only `response.content`'s first text block. Nothing about this bug is
   streaming-specific as far as I can tell; it was just surfaced by testing the streaming change
   live, since mock-mode's `MockAnthropicClient` only ever emits a single text block and the two
   live eval runs in the prior session happened not to hit this particular shape.

## Live sanity check - 3 hand-picked claims, `APP_LLM_MODE=live`

| # | Claim | Result | Time | Cost | Notes |
|---|-------|--------|------|------|-------|
| 1 | Gallup 5.6% LGBT (`stat-001`) | `supported`, correct | 31.8s | $0.102 | Baseline - typical case, default $0.25 cap, no issue |
| 2 | Nebraska leaf-bag fee (`prov-005` - the case most similar in shape to the prior timeout) | attempt 1: `BudgetExceededError` (not a timeout - see below); attempt 2 (bumped cap): `provenance-only`, correct | attempt 1: 368.8s; attempt 2: 220.5s | attempt 1: $0.319 (over cap); attempt 2: $0.183 | Same claim, two calls - cost varies run to run (consistent with everything else observed this session) |
| 3 | "Women speak 20,000 words/men 7,000" (`stat-006` - the exact case with a **confirmed** prior `APITimeoutError` at 364.4s) | `not supported`, correct (contradicts the actual research) | 51.9s | $0.185 | The direct re-test of the confirmed failure - see below |

**None of the three hit `APITimeoutError`.** Case 3 is the most direct evidence the fix works: the
exact claim that previously failed with a confirmed 364.4s timeout in the live eval report now
completes in well under a minute.

Case 2's first attempt is worth reading carefully: it did **not** time out either - the request
itself completed successfully (`stop_reason: "end_turn"`) in 368.8s, longer than the old ~360s
ceiling that used to trip `APITimeoutError`. It was rejected afterward by the app's own
pre-existing cost cap (`Config.max_cost_usd`, default $0.25 - a single 4-search evaluator call
cost $0.319 on its own). That's the budget-cap contract working exactly as designed
(`BudgetExceededError` rather than silently truncating, per SPEC.md) - not a streaming bug. I
reran both case 2 and case 3 with a diagnostic-only `APP_MAX_COST_USD=1.00` override (not
committed, not written to `.env` - a one-off env var for these two calls) specifically to isolate
"did the timeout fix work" from "does this claim fit the default cost budget," per the sanity
check's actual purpose.

### Usage/cost accounting under streaming - confirmed correct

Checked `runs/trace.jsonl` after each call; `cost_usd` matches `estimate_cost()`'s formula exactly
against the real `usage` fields in every case, e.g. case 3:
`62471 input tokens × $2/1M + 1954 output tokens × $10/1M + 4 searches × $0.01 = $0.18448`,
trace shows `cost_usd: 0.18448`. Token counts, web-search counts, and `stop_reason` all populate
correctly from `stream_ctx.get_final_message()` - no accounting regression from streaming.

**One minor gap found, not fixed:** `request_id` came back `null` in the trace for every streamed
(evaluator) call, where it was a real ID for the non-streamed classifier call in the same run.
`getattr(response, "_request_id", None)` on `get_final_message()`'s returned `Message` apparently
doesn't carry the request ID the same way `.create()`'s return value does - worth a follow-up if
request-id-based debugging of live evaluator failures matters, but it's an observability gap, not
a functional one (the response content, usage, and cost are all correct).

## A side-finding worth flagging (not the streaming fix's job to solve)

With the timeout no longer the binding constraint, the *next* one for a claim needing several
searches is `Config.max_cost_usd` (default $0.25) - case 2 hit it once ($0.319) and stayed under
it once ($0.183) on the identical claim, an artifact of the same run-to-run variance in search
depth/output length documented throughout this project. Streaming didn't cause this; it just
means claims that previously failed via timeout before ever reaching the cost check can now
actually reach it. Worth knowing before running the full `eval-fast-live` (mean cost there was
$0.080-0.084 across both live runs, well under $0.25, but the p95/tail cases are exactly the ones
most likely to bump into this).

## Test / lint / typecheck status

All green throughout, checked before and after every change: `make lint`, `make typecheck`
(mypy strict), `make test` (23/23 pytest, unchanged - all scripted-response tests use
`Config()`'s default `llm_mode="mock"`, so `_create_message`'s streaming branch never activates
for them regardless of `stream=True` being passed). `make eval-fast` (mock) reconfirmed clean
(100% pass rate, ~2-10ms p95, $0.0093 simulated cost) after every change in this step.

## What was deliberately not touched

- `stat-003` / `stat-004`, the two eval cases with reproduced run-to-run verdict instability.
- The full `make eval-fast-live` target - not run this step, per the user's instruction. The 3
  sanity-check results above are encouraging but are 3 hand-picked calls, not a 15-case run.

## Open questions / flag for review

1. **Not yet re-run against the full 15-case live eval.** The sanity check strongly suggests the
   timeout is fixed, but only a full `eval-fast-live` run will show the real pass_rate/p95/cost
   numbers to compare against the two prior live reports.
2. **The cost-cap side-finding above** - worth deciding whether `Config.max_cost_usd`'s default
   ($0.25) needs raising before the next full live run, now that heavy claims can actually reach
   it instead of timing out first.
3. **`request_id` is `null` on streamed responses** - minor observability gap, not fixed.
4. Per the user's instruction, `stat-003`/`stat-004` are still untouched - the LLM verdict
   instability finding from the mock-toggle/v0-implementation steps stands as-is.

## Next command

```bash
git log --oneline -6                         # review this step's 2 commits
make eval-fast-live                          # the real 15-case live run, once you're ready for it
```
