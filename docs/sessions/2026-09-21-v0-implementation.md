# 2026-09-21 - v0 implementation

## What changed and why

Implemented SPEC.md's v0 end to end on branch `feat/v0-pipeline` (not merged, not pushed):

- **Pipeline** (`src/app/pipeline.py`): `run(claim) -> Verdict`. Empty/whitespace input
  short-circuits before any LLM call. Otherwise: classify -> route -> (evaluate | degrade).
- **Classifier** (`src/app/classifier.py`, `prompts/classifier.md`): one structured-output call
  (Haiku 4.5) assigns one of the five spec tiers, or `not_a_claim` for empty/gibberish input - an
  extension beyond the spec's five-tier list, added because the spec didn't say what a non-claim
  should get (see decisions below).
- **Evaluators** (`src/app/evaluators.py`, `prompts/statistical_data.md`,
  `prompts/provenance_only.md`): `statistical_data` and `provenance_only` each run one
  structured-output research call (Sonnet 5 + the `web_search_20260209` tool) and return a
  `Verdict`. Evidence URLs not actually present in the search tool's results are dropped rather
  than trusted from the model's memory. The other three tiers get an explicit `not-implemented`
  Verdict via `evaluate()`'s dispatch, never a guess or a crash.
- **`Verdict`** (`src/app/verdict.py`): dataclass per spec (`tier`, `verdict`, `confidence`,
  `evidence`, `origin_trace`, `reasoning`), plus `Tier`/`Label`/`Confidence` enums and
  `not_implemented()`/`invalid_input()` constructors.
- **`llm.py`**: budgeted (`Budget` against `Config.max_steps`/`max_cost_usd`), traced
  (`app.tracing.span`, tagged with prompt name/version) wrapper around
  `client.messages.create`. Resumes `pause_turn` by resending the assistant content, per the
  web-search tool's documented resume contract. Cost is estimated from `response.usage` (tokens +
  cache multipliers + a flat per-web-search estimate).
- **CLI** (`scripts/check_claim.py`): `claim="..."` or `--claim "..."`, prints the Verdict as JSON.
- **Eval set** (`evals/cases/v0.jsonl`): 15 cases - 6 `statistical_data`, 5 `provenance_only`, 2
  unimplemented-tier, 2 edge (empty, gibberish). `evals/run.py` now serializes the real `Verdict`
  and scores `expected_contains` against it, with real `cost_usd`/`steps` from a `Budget` and
  per-prompt versions in the report.
- **Tests** (`tests/`): 23 tests against a scripted fake Anthropic client (`tests/conftest.py`,
  no network) covering empty/gibberish input, all three unimplemented tiers, both implemented
  tiers end-to-end, per-tier schema differences, evidence-URL grounding, `pause_turn` resumption,
  step/cost cap enforcement, and malformed/refused/truncated model output.
- **2 ADRs** (`docs/adr/0002`, `0003`): why the classifier ships all five tiers ahead of full
  evaluator coverage; why Claude's web search tool over a separate search API.

## Decisions made mid-session (asked, not assumed)

**Before starting**, four spec-ambiguous points, all resolved with the recommended option:
1. `evals/thresholds.yaml`'s 2s `max_latency_p95_s` scaffold default clearly couldn't survive a
   real web-search pipeline -> raise it (to 60s) in its own `eval:` commit before any eval run,
   rather than leave it red or fold the change into other work.
2. What `run()` returns for empty/gibberish input, since the spec's tier list doesn't cover it ->
   add an `invalid-input` verdict with `tier: null`, short-circuiting empty input before any LLM
   call and giving the classifier a `not_a_claim` escape hatch for gibberish.
3. Whether the rubric-based LLM-as-judge is in scope for this session -> deferred to v1, per
   SPEC.md's own "build the judge only after deterministic cases pass"; all v0 cases use
   `expected_contains`.
4. Git workflow -> feature branch (`feat/v0-pipeline`), small Conventional Commits as I went, no
   push, no PR.

**Mid-session**, after the first live `make eval-fast` run surfaced two real threshold misses and
three case failures, asked again rather than unilaterally re-tuning a second time:
5. `stat-003`/`stat-005` had expected labels that looked like my own authoring mistakes, not model
   failures -> fix the two labels in their own `eval:` commit, with the model's actual reasoning
   quoted as justification (commit `7ac91bb`).
6. The 60s latency threshold was an uninformed pre-run guess; live p95 was 240s -> raise it to
   300s in its own commit, same pattern as the first placeholder (commit `a34e351`).

A genuine bug found in the same run (evaluator hit its 6,000-output-token cap on a 4-search case,
correctly raising instead of returning a truncated verdict) was fixed unilaterally
(`EVALUATOR_MAX_TOKENS` 6000 -> 12000, commit `f5828ff`) since it wasn't a judgment call.

## What the second live run revealed (not yet resolved, flagged rather than papered over)

A second `make eval-fast` run - identical code apart from the three fixes above - produced
**worse** numbers than the first, and revealed the earlier "case-authoring mistake" framing was
incomplete:

- `stat-003` and `stat-004`: **the verdict flipped between runs on identical input** (`stat-003`
  mixed -> supported; `stat-004` mixed -> not supported). This is real LLM instability on
  judgment-heavy claims, not a label that needs correcting - `evals/run.py`'s substring match
  against one fixed label is structurally unsuited to these two claims. Did not attempt a third
  label edit; documented instead as exactly the gap SPEC.md defers to a v1 gold-set-validated
  judge.
- `APITimeoutError` fired on two *different* cases across the two runs (`prov-005`, then
  `stat-006`): `client.messages.create` (non-streaming) with a 120s client timeout and default
  retries hits a ~360s hard ceiling on the slowest search-heavy claims, independent of
  `max_steps`/`max_cost_usd`. Not fixed in this session - flagged in README's Known failures and
  What's next as the highest-priority follow-up (switch evaluator research calls to
  `client.messages.stream(...)`).

Given the session was already two full live-API eval runs deep (~40+ minutes, real API spend), a
third automatic rerun chasing these results was judged likely to keep landing below the 90%
pass-rate threshold for the reasons above, not to fix them - so I stopped, reported the real
numbers, and left the fix (streaming) and the judge (v1) as explicit next steps rather than
attempting further threshold or case tuning on my own initiative.

## Eval numbers (both live runs, `evals/reports/`)

| | Run 1 (`fast-20260921-173157.json`) | Run 2 (`fast-20260921-175111.json`, current) |
|---|---|---|
| Pass rate | 80.0% (12/15) | **73.3% (11/15)** |
| Latency p95 | 240.0s | **364.4s** |
| Mean cost | $0.078 | **$0.080** |
| vs. thresholds | latency FAIL (60s, pre-fix) | pass_rate FAIL (90%), latency FAIL (300s) |
| Mean cost threshold ($0.10) | pass | pass |

`evals/thresholds.yaml`'s pass-rate (0.90) and cost ($0.10) thresholds were never touched; only
latency was raised, twice, each in its own commit with the real number that motivated it.

## Test / lint / typecheck status

All green as of the last commit (`f9da63b`): `make lint` (ruff check + format --check), `make
typecheck` (mypy strict), `make test` (23/23 pytest, no network).

## Open questions for review before this merges

1. **`make eval-fast` does not pass `evals/thresholds.yaml`** (73.3% vs. 90% pass rate, 364.4s vs.
   300s p95). SPEC.md's definition of done requires it to pass; it currently doesn't, for the two
   reasons documented above. This needs your decision, not mine: ship v0 as-is with this
   documented, prioritize the streaming fix (real code + a third `make eval-fast` run), or
   something else.
2. `stat-003`/`stat-004` are evidence that 2 of the 11 implemented-tier eval cases may not be
   answerable by a single fixed expected label at all - worth deciding whether v1's LLM-judge work
   should start sooner than planned, or whether those two specific claims should be swapped for
   less contested ones in the eval set (a case-set change, its own commit, not something I did
   unilaterally here).
3. **CLAUDE.md changed on disk mid-session** (added the "Session summary" requirement this file
   satisfies) but the diff also shows what looks like pasted UI chrome from another app
   ("Claude Desktop (macOS), Connected", stray blank lines, "Claude · MD") mixed into the file. I
   did not commit that file or clean it up - it's left as an uncommitted local change for you to
   review, since I don't know how it happened and it's not mine to silently rewrite.
4. This branch was never pushed and no PR was opened, per the git-workflow answer above - it's
   sitting locally on `feat/v0-pipeline`.

## Next command

```bash
git diff main...feat/v0-pipeline --stat   # review the full diff
make eval-fast                            # rerun to see current numbers (~15-20 min, live API cost)
```
