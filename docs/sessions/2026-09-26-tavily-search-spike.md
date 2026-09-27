# Session: performance tuning and the Tavily search-backend spike

Continuation of the PERFORMANCE gate opened earlier the same day (see
`working-notes-and-decisions.md`, 2026-09-26). Goal: get a live claim under the MVP target (5s,
2 cents) or find out it can't be done with this design. Nothing in this session is committed to
`main` or merged into `feat/output-formatting` - it's all new, uncommitted work, landing in its own
commit(s) alongside this doc. No go/no-go decision was made; see "Where this leaves things" below.

## Part 1: tuning the existing (model-driven search) path

Three env-var experiments on the 13-case `fast` tier, live, no code changes:

| Config | Pass rate | p95 latency | Mean cost | Report |
|---|---|---|---|---|
| Baseline (default search tool) | 13/13 | 125.7s | $0.083 | pre-existing |
| `APP_WEB_SEARCH_TOOL=web_search_20250305` (older tool) | 13/13 | 22.3s | $0.054 | pre-existing |
| + `APP_MAX_SEARCHES=2` | 13/13 | 16.5s | $0.043 | `fast-live-20260926-221308.json` |
| + `APP_EVALUATOR_EFFORT=low` | 13/13 | 17.3s | $0.044 | `fast-live-20260926-221502.json` |

Effort made no measurable difference (17.3s vs 16.5s is noise). This is a large improvement over
baseline (about 7x on latency, 2x on cost) but still 3x over on latency and 2x over on cost, with
diminishing returns from further tuning. One run in between these (`fast-live-20260926-220908.json`)
failed outright - not a code or design problem, the Anthropic account hit its monthly API usage
cap. Confirmed from the response body (`"You have reached your specified API usage limits"`) and
resolved by raising the Console limit; noted here only so a future zero-cost/zero-latency failure
isn't mistaken for a bug again.

Conclusion: tuning the model-driven search loop cannot reach the target. The loop is at least two
sequential model turns per claim (decide a query, then read results and answer), and the search
content fed back into context is what the cost and latency actually track.

## Part 2: the Tavily spike (retrieval outside the model)

Built behind `APP_SEARCH_BACKEND=tavily` (default remains `"anthropic"` - nothing changes unless
explicitly opted in). Design: two parallel Tavily queries per claim (the claim as written, and the
claim plus "original source"), no model involved in searching, then one tool-less model call over
the returned snippets. New: `src/app/search.py`, plus a `search_backend` dispatch in
`src/app/evaluators.py` and `src/app/config.py`.

First attempt used `urllib` for the Tavily HTTP calls and failed everywhere:
`fast-live-20260926-222559.json` shows every search-tier case erroring with
`CERTIFICATE_VERIFY_FAILED` - a known class of issue on macOS Python installs whose system
certificate store isn't wired into `urllib`'s default SSL context. Fixed by switching to `httpx`
(already an indirect dependency via `anthropic`), which carries its own bundled CA store. Added
`httpx>=0.23` as an explicit dependency.

With that fixed, the backend works:

| Attempt | Pass rate | p95 latency | Mean cost | Report |
|---|---|---|---|---|
| Tavily, first working run | 12/13 (`stat-006` failed) | 15.6s | $0.0165 | `fast-live-20260926-222917.json` |
| prose "be concise" instruction added (see caveat below) | 12/13 (`prov-004` failed) | 17.6s | $0.0169 | `fast-live-20260926-223413.json` |
| unrelated to the above - a schema edit silently didn't deploy (bridge sync bug, see below) | 12/13 (`stat-005` failed) | 15.8s | $0.0167 | `fast-live-20260926-223755.json` |
| + schema `maxItems` (rejected by API) | 4/13 - void, not a quality result | 7.0s | $0.0121 | `fast-live-20260926-224026.json` |
| + schema `maxLength` only | 13/13 | 17.4s | $0.0168 | `fast-live-20260926-224309.json` |

**Cost target: met, comfortably.** $0.0165-0.0169 mean is well under the 2c MVP target, mostly
because Tavily's flat per-search fee ($0.008 x 2 = $0.016) replaced the old design's expensive
multi-turn token cost. Tavily's own fee is now the largest single line item in the new, much
smaller total - not because it's expensive, but because everything else got cheap around it.

**Quality: holds, but not with a wide margin.** 92-100% pass rate across four live runs, with
three different cases (`stat-006`, `prov-004`, `stat-005`) each failing exactly once. That reads as
the same near-the-margin model instability already flagged for `stat-005` elsewhere (README's Known
Failures), not a new Tavily-specific problem - `stat-006`'s one failure was a defensible "mixed" vs
expected "not supported" labeling call, where the model had actually found the correct contradicting
data.

**Latency: did not move**, staying in the 15-17s p95 range across every attempt to change it below.
This is the target still unmet.

### Why latency didn't move, and what was tried

Live traces show a sequential path: classifier (~2s) -> Tavily search, two parallel queries
(~1.5-3.7s) -> evaluator generation (~7-10s, the largest piece by a wide margin, scaling with
*output* length rather than input). Parallelizing the classifier with the search was considered and
rejected without being tried live: since Tavily search must run for every claim to be overlapped
with the classifier, but roughly a third of eval cases don't need search at all (`not-implemented`/
`invalid-input`), firing it speculatively would add a full search's cost ($0.016) to those cases,
projected to push mean cost from $0.017 toward $0.02 - right at or over the 2c ceiling, to save
about 2 seconds. Not attempted.

Three attempts were made to shorten the evaluator's generation (the actual dominant cost), but only
two are confirmed - see the correction below.

1. **A prose instruction** appended to the prompt only for this backend ("use at most 2 evidence
   items, keep reasoning to one or two sentences"). The live run made right after adding it
   (`fast-live-20260926-223413.json`) showed no change in output length - but a later audit (done
   while preparing this doc, comparing file checksums on both sides of the bridge) found that this
   specific edit to `src/app/search.py` never actually reached Max's machine: the commit tool
   reported success, but the deployed file still lacked the instruction. So that run silently
   tested the *unmodified* prompt, not the concise version - the "no change" result is real, but it
   doesn't tell us whether Haiku would have followed the instruction, only that the instruction was
   never actually in front of it. Left unresolved rather than re-tested, since the schema-level
   finding below (`maxLength`, confirmed deployed via checksum) already answers the practical
   question - whether prose-only instructions could ever be trusted to bound output without a
   verified deployment either way, they're not what we'd rely on for a real constraint.
2. **A hard `maxItems` bound** on the evidence array, added to the JSON Schema passed as
   `output_config.format.schema`. The API rejects this outright:
   `"output_config.format.schema: For 'array' type, property 'maxItems' is not supported"` (a real
   400 error, confirmed live in `fast-live-20260926-224026.json` - all 9 search-tier cases failed
   before any generation happened, which is why that run's cost and latency both look artificially
   low). This is a hard capability limit of the API today, not a bug in this code.
3. **A hard `maxLength` bound** on the string fields (`reasoning`, `origin_trace`, and the evidence
   item's `note`/`claim_snippet`). This one is *accepted* by the API - no error - but not actually
   enforced: `fast-live-20260926-224309.json` shows `reasoning` running 336-786 characters against a
   400-character cap. It's a silent no-op, not a working constraint.

Net finding, the two confirmed ones: structured output on this API enforces `enum` values and
object shape, but neither of the two length-bounding JSON Schema keywords tried here. Whether a
prose request alone could ever be trusted as a real constraint remains untested (see above). Either
way, there is currently no *confirmed* lever in this design that reliably controls the evaluator's
generation time, which is the thing actually driving latency.

There was also a real, separate bug worth recording, and worth being blunt about: a
`device_commit_files` write reported success but the file on Max's machine didn't change, at least
three times across this session (once each for `search.py`'s prose edit, `evaluators.py`'s schema
edit, and `search.py` again - caught only during a final pre-commit audit, not in the moment).
That means at least one documented "finding" above (the prose instruction) was actually a false
read caused by this bug, not a real result - corrected above rather than left standing. Going
forward, every write to a Python source file on Max's machine is verified by re-staging and
comparing checksums immediately after the commit, not by trusting the tool's own success report,
and a plain re-commit that doesn't take effect is retried by writing to a new source path.

## Part 3: `scripts/devserver.py` / `make devserver`

A local, single-user web page (`http://127.0.0.1:8000`, no auth) for feeling out latency and
reading full verdicts claim-by-claim, rather than reading them off a JSON summary. Shows: a mock/
live banner (with the active search backend and evaluator model), a form to submit any claim, and
per-request latency, cost, and the full `Verdict` (reasoning, origin trace, evidence with clickable
source URLs), plus a running session cost total. `flask` added as a dev-only dependency (not used
by the app, the eval harness, or CI). Not built to any particular design polish - it exists to
answer one question: does the current latency feel acceptable to a real user.

First hands-on result: a real claim (the CDC opioid-overdose statistic) came back correctly
supported in 10s - and felt slow. That's on the fast end of the measured 10-17s range for a
search-tier claim, which is a meaningful data point: most live claims will feel at least this slow,
some noticeably more.

## Where this leaves things

Cost target: met. Quality: holds, without a wide margin. Latency: stuck at 10-17s per live claim,
felt as "long" even at the fast end of that range, with no remaining lever from this session's list
that reliably shortens it. No go/no-go call was made. The live options going into next session:

- Lean on the verdict store (already on the roadmap, see the 2026-09-26 "Design direction" decision)
  so live search becomes the rare exception rather than the default interaction, and accept 10-17s
  there.
- Or attempt a more invasive redesign - for example dropping the free-form evidence/reasoning
  fields for a smaller, fixed schema - before deciding anything.

Continue via `make devserver` (env vars documented in the script's own docstring).
