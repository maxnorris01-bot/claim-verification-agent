# To-do - Claim Verification Agent

A running checklist, not a narrative. Check items off as they're done and add a short note (what
happened, any surprises) rather than deleting the line - that note is often more useful later than
the checkmark itself. Add new items as they come up; don't wait for a session's end. This is
*not* where decisions and reasoning go - that's `docs/working-notes-and-decisions.md`. This is just
"what's next."

## Up next (in priority order)

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
- [ ] Implement output formatting (not yet started). Observations from the walkthrough to cover:
      (1) for `not-implemented` verdicts, `reasoning` mixes the system's "not evaluated" message
      with the classifier's own take on the claim, which reads close to a verdict - consider a
      plain user-facing message plus a separate classifier-reasoning field, or hiding it;
      (2) `confidence: "low"` on a non-evaluation is ambiguous - consider null/n-a; (3) output is
      raw JSON, fine as an API response but not human-facing.

## v1 (after v0 closes out)

- [ ] Remaining 3 of 5 v0 tiers (2 of 5 implemented so far).
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
      built.

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
