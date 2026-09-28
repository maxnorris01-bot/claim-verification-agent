# To-do - Claim Verification Agent

A running checklist, not a narrative. Check items off as they're done and add a short note (what
happened, any surprises) rather than deleting the line - that note is often more useful later than
the checkmark itself. Add new items as they come up; don't wait for a session's end. This is
*not* where decisions and reasoning go - that's `docs/working-notes-and-decisions.md`. This is just
"what's next."

## Project status: reserved / backup (2026-09-27)

Not actively being developed. The PERFORMANCE gate below never resolved - latency stuck at 10-17s
per live claim with no confirmed lever left to try short of a bigger architecture change - so the
project was moved to reserve status alongside City Livability and Satellite Conjunction rather than
pushed to production as-is. See `working-notes-and-decisions.md` (2026-09-27 entry) for the full
reasoning and `docs/lessons-learned.md` for the project retrospective. Everything below is left as
it stood when work paused, not deleted, so the state is reconstructable if this gets reactivated.

## Up next (in priority order) — as of when work paused

- [ ] Keep watching the `provenance_only` v3 fix on future live runs. (Second live run on
      2026-09-24 showed v2 did not hold - 11/13, `prov-005` regressed - so v3 was written; v3 is 13/13
      once plus 4/4 on `prov-005` isolated.) Move `stat-005` to `known-unstable/` in its own `eval:`
      commit only if it flips again.
- [x] v0 close-out walkthrough (`2026-09-24`, deliberately short): ran two claims live via
      `scripts/check_claim.py` - an unimplemented-tier one (intermittent fasting) and a
      well-supported statistical one (Gallup 5.6%). Both behaved correctly. Stopped there on
      purpose; more hands-on testing happens once the actual site/tool is up. Observations
      feeding the formatting item below. (Scoped to Max only - see
      working-notes-and-decisions.md, 2026-09-24 entry.)
- [ ] **PERFORMANCE - gates production.** MVP target per live claim: 5s or less and 2 cents or
      less; stretch 2s and 1 cent; if MVP isn't met, the project doesn't ship to production (see
      working-notes-and-decisions.md, 2026-09-26). Baseline: p95 125.7s, mean $0.083.
      (a) [x] env-var experiments on the model-driven search path: older tool + `max_searches=2`
      plateaus at p95 16.5s / mean $0.043 (13/13); `evaluator_effort=low` on top made no
      difference. Still 3x/2x over target - tuning alone isn't enough.
      (b) [x] Tavily retrieval-outside-the-model spike (`APP_SEARCH_BACKEND=tavily`, not the
      default): meets the cost target (mean $0.017) and quality holds (92-100% across four live
      runs), but latency is stuck at ~15-17s p95. Two confirmed findings on why: JSON Schema
      `maxItems` is rejected by the API, `maxLength` is accepted but not enforced. A third attempt
      (a prose "be concise" instruction) looked ineffective but was actually never deployed to the
      test run due to a bridge file-sync bug - retracted as inconclusive, not a real finding. Full
      (corrected) detail: `docs/sessions/2026-09-26-tavily-search-spike.md`.
      (c) [x] Built `scripts/devserver.py` / `make devserver` - a local page for feeling out
      latency claim-by-claim to inform the go/no-go call. First real claim (CDC opioid stat) came
      back correctly in 10s and felt slow.
      (d) [ ] hard timeout and fallback for API-side tail latency - not started.
      (e) [ ] tighten `evals/thresholds.yaml` in its own commit, once a design actually hits target.
      **Open decision, not yet made:** keep chasing live-path latency (e.g. a smaller fixed schema,
      dropping free-form fields), or accept 10-17s as the live (cache-miss) path and lean on the
      verdict store so it's the rare exception, not the default. Needs Max's hands-on read via
      `make devserver` - pick up next session.
- [ ] Verdict store with live fallback (see working-notes-and-decisions.md, 2026-09-26): schema
      (canonical claim, aliases, verdict, checked-on date, prompt/model version), semantic matching
      with a conservative threshold, a review-then-publish seeding pipeline, and where the seed
      claims come from (check source licenses).
- [ ] Decide which tiers must exist before launch. The seed myths will mostly be scientific or
      historical, both currently `not-implemented`.
- [ ] Site: stack and hosting decision, visual design and navigation (final product look), backend
      (API key server-side, rate limiting, abuse prevention, timeout fallback).
- [ ] Prompt-injection eval cases before the site takes public input (moved up from "Lower
      priority").
- [ ] CI cleanup: `ci.yml` is the untouched template and runs a daily mock `eval-nightly` and
      `eval-standard` on every push (all runs green as of 2026-09-26) - decide whether to keep or
      remove; fix the README's `OWNER/REPO` placeholders (badge and clone URL) and empty demo
      comment.
- [~] Output formatting: the data cleanups are done (2026-09-26, branch `feat/output-formatting`):
      `not-implemented` now returns only a plain "tier not implemented" message (no classifier
      opinion) and `not-implemented` / `invalid-input` return `confidence: null`. What remains is
      the final-product design (what the site looks like, how users navigate it) - see the Site
      item above.

## v1 (after v0 closes out)

- [ ] Remaining 3 of 5 v0 tiers (2 of 5 implemented so far). Fine to defer for personal testing, but
      likely needed before launch - a seed corpus of common myths is mostly scientific/historical.
- [ ] Self-grading / accuracy tracker - named in the portfolio plan as this project's actual
      differentiator, but not committed to v1's scope yet. Leaning toward shipping v1 without it
      and adding it once a real backend exists anyway (site hosting will need one regardless).
      Still not fully decided - see working-notes-and-decisions.md, 2026-09-24 entry.

## Lower priority / opportunistic

- [ ] Stray quote/trailing characters in evaluator free-text fields - investigated 2026-09-26,
      deliberately not fixed, revisit only if the formatting layer makes it visible. Seen on
      `prov-003` (2026-09-23, with duplicated phrasing) and as a stray `'` at the end of `reasoning`
      on the Gallup 5.6% claim (2026-09-24). Findings: not our parsing (`llm.parse_json_object`
      uses strict `json.loads` and nothing modifies `reasoning` afterward, so the characters are
      inside the string the model wrote). A 5-run repeat of the Gallup claim showed `reasoning` and
      `origin_trace` clean 5/5, but 2 evidence notes in 1 of 5 runs ended in `.'"` (possibly
      legitimate nested quotes - unconfirmed). Roughly 1 run in 5, cosmetic, never affected a
      verdict or pass/fail. Options not taken: a prompt line requiring plain-prose text fields
      (needs many paid runs to verify at this rate); an opt-in raw-output field in the trace
      (small `llm.py` change, would make the next occurrence diagnosable); trimming quotes in code
      (risks eating legitimate ones).
- [ ] Adversarial / prompt-injection eval cases - named in the README's "What's next," never
      built. (Moved up: now tracked under "Up next" as a gate before public input.)

## Completed (most recent first)

- [x] `2026-09-26` - Merged `feat/v0-pipeline` into `main` (merge commit `23ae2e6`, a regular merge
      not a squash so the commit hashes cited in the README and session docs stay reachable). No
      PR was opened: `gh` isn't installed, so it was merged locally with `git merge --no-ff` and
      pushed. `main` had no commits the branch lacked, so no conflicts. v0 is shipped on `main`;
      further work goes on new branches.

- [x] `2026-09-26` - Ported the template's `max_total_cost_usd` aggregate spend check into
      `evals/run.py` (code commit) and added `max_total_cost_usd: 2.50` to `evals/thresholds.yaml`
      (separate `eval:` commit). Reports now include `total_cost_usd`. Surprise: `make test` had
      been failing since the 2026-09-24 prompt v3 bump (`tests/test_smoke.py` hardcoded prompt
      version `"1"`) - never caught because that session didn't rerun the unit tests. Fixed to accept
      any positive integer version. Lesson: run the whole lint/typecheck/test/eval-fast chain after a
      prompt bump, not just `make eval-fast`.

- [x] `2026-09-24` - `provenance_only` prompt v3 written and tested after the second live run
      failed 11/13 under v2 (`prov-005` regressed, `stat-005` flipped). v3: 4/4 on `prov-005`
      isolated, then full live run 13/13 (`fast-live-20260924-212213.json`). Also added per-case
      progress output to `evals/run.py`. See `docs/sessions/2026-09-24-provenance-prompt-v3.md`.

- [x] `2026-09-23` - Working notes and decisions log convention set up (this repo + template +
      both CLAUDE.md files).
- [x] `2026-09-23` - `portfolio-project-template` gaps closed (mock/live LLM toggle, concurrent
      eval scoring, thread-safe tracing, real cost wiring, aggregate spend cap, realistic
      thresholds, known-unstable case convention) and verified clean. Full detail in the
      template's `docs/lessons-learned.md`.
- [x] `2026-09-23` - `provenance_only` prompt fixed (v2) after `prov-001`/`prov-005` verdict
      mismatch found in a live run. One live run since confirmed 13/13 - second run still needed
      (see "Up next" above).
- [x] `2026-09-21` - Template repo built; this repo cloned from it; v0 started (2 of 5 tiers).
