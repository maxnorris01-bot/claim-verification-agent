# 2026-09-21 - prep for the full live validation run

Scoped step: three preparatory changes before running `make eval-fast-live` for real, per the
user's explicit instruction. **Nothing in this step touched the live API** - all verification was
via mock-mode `make eval-fast`, unit tests, and static confirmation (a standalone glob test).
`make eval-fast-live` itself was deliberately not run - that's a separate step, pending the user's
go-ahead, since it costs real money.

## What changed and why

### 1. Raised `Config.max_cost_usd`'s default $0.25 -> $0.50 (`5ce8b3b`)

The streaming fix (previous step) let search-heavy evaluator calls actually run to completion
instead of hitting the old ~360s `APITimeoutError` first. The live sanity check from that step hit
$0.319 and $0.183 on the *same* claim across two runs - both over the $0.25 placeholder. $0.50
gives real headroom for a legitimately heavy multi-search claim while remaining a genuine circuit
breaker. Both the dataclass default and `from_env()`'s env-var fallback were updated together (they'd
drifted apart before if I'd only touched one); `.env.example` and README's Security and cost notes
updated to match.

### 2. Moved `stat-003`/`stat-004` to `evals/cases/known-unstable/` (`c53d930`)

First confirmed empirically (not just by reading the code) that `evals/run.py`'s
`load_cases()` glob (`"*.jsonl"`, non-recursive on `evals/cases/`) does not descend into
subdirectories - wrote a standalone test with `Path.glob` against a throwaway directory tree
before touching anything real. `v0.jsonl` now has 13 cases (was 15), confirmed via mock
`eval-fast`'s `n_cases` field before and after.

Both cases showed reproduced run-to-run verdict instability across the two prior live runs
(documented in the v0-implementation and streaming-fix session docs):
- `stat-003` (CDC "1 in 36" autism figure): `mixed` -> `supported`, identical code and input.
- `stat-004` (Gladwell/Ericsson "10,000 hour rule"): `mixed` -> `not supported`, same.

Moved rather than deleted or force-fit to one label - each file keeps a `note` field quoting the
reproduction. `evals/cases/known-unstable/README.md` documents the convention and what retires a
case from there (the v1 gold-set-validated judge SPEC.md already calls for, not a tighter
`expected_contains` string). `evals/README.md`'s "Adding cases" section documents the convention
for future cases that turn out the same way. Main README's Known Failures section updated to match
- and, since I was already editing that section, also corrected the timeout entry from "not fixed
this session" (stale as of the streaming-fix step) to "fixed," with a pointer to that step's
sanity-check evidence, so the README doesn't misrepresent current state.

### 3. Concurrent case scoring (`a31e5f6`, `5db4209`)

Two commits:
- **Prerequisite**: `app.tracing.span`'s file write is now guarded by a module-level
  `threading.Lock`. A single `write()` of a short trace line is usually atomic enough in practice,
  but a line can run to several KB on a verbose search log, and cases now run concurrently - so two
  threads' lines could otherwise interleave into one corrupted line.
- **The actual change**: `evals/run.py`'s `main()` now scores cases via
  `ThreadPoolExecutor(max_workers=5)` (`.map`, which preserves input order in its results
  regardless of completion order, so report ordering stays stable and reproducible) instead of a
  plain list comprehension. Each case is dominated by network wait, so overlapping that wait cuts
  wall-clock time for a run - it does **not** reduce cost; every case still pays for its own calls.

**Verified in mock mode**: ran `make eval-fast` 4 times after the change (13 cases each), 100%
pass rate every time, then checked `runs/trace.jsonl` for corruption across all the runs in this
session combined - 684 lines, 0 malformed. No flakiness observed.

**Assumption made, not tested against live traffic this step** (explicitly out of scope - no live
calls made): `app.llm.get_client`'s cached client instance (both `anthropic.Anthropic` and
`MockAnthropicClient`) is now shared across worker threads by design. Modern HTTP client libraries
built on `httpx` are generally documented as safe for concurrent use from multiple threads, and
`MockAnthropicClient`'s only shared mutable state is an append-only `calls` list used for
diagnostics, not scoring logic - but this hasn't been stress-tested against 5 concurrent *live*
requests yet. Worth watching when `make eval-fast-live` actually runs.

## Test / lint / typecheck / mock eval-fast status

All green throughout, checked after each of the 3 items individually and once more at the end:
`make lint`, `make typecheck` (mypy strict), `make test` (23/23 pytest), `make eval-fast`
(mock - 13 cases, 100% pass rate, ~1-10ms p95, $0.0088 simulated cost, free).

## What was deliberately not touched

- `make eval-fast-live` was not run. That's the next step, pending the user's confirmation, since
  it costs real money.
- No further changes to `stat-003`/`stat-004`'s content beyond moving them (their labels,
  `expected_contains`, and input text are untouched).
- Didn't add a `make eval-standard`/`make eval-nightly` mock/live split - out of scope for this
  step (flagged as a pre-existing gap in the streaming-fix and mock-toggle docs, still open).

## Open questions / flag for review

1. **Ready for the full live run** as far as this step's prep goes: cost cap raised, unstable
   cases parked, concurrency in place. The actual `make eval-fast-live` numbers (pass_rate, p95,
   mean_cost against the 13-case set, with concurrency and the streaming fix both active for the
   first time together) are still unknown until it's actually run.
2. **Concurrency + live client interaction is untested** - see the assumption noted above. If the
   live run shows odd behavior (garbled trace lines despite the lock, unexpected errors under
   concurrent load), `max_workers` in `evals/run.py` is the first thing to turn down.
3. **`max_cost_usd=$0.50` is still per-claim, not per-run.** With 5 workers scoring 13 live cases
   concurrently, the live run's *aggregate* spend across all cases isn't bounded by this number -
   only each individual case's own budget is. Worth knowing before running it, not something this
   step changed (the aggregate was never bounded, even before concurrency).

## Next command

```bash
git log --oneline -8                          # review this step's 5 commits
make eval-fast                                 # re-confirm locally if desired (free, ~instant)
make eval-fast-live                            # the real 13-case live run, once you're ready for it
```
