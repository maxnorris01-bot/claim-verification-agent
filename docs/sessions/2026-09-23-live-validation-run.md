# 2026-09-23 - the full live validation run

Scoped step: run `make eval-fast-live` for real (the step the previous session's prep work was
building toward), read the result against `evals/thresholds.yaml`, and update the README to match.
No code or eval-case changes this step - this is a validation run and a docs update only.

## What changed and why

### The live run itself

Run from the repo directly (`maxs-MacBook-Pro:claim-verification-agent`), not from this session -
this Claude session has no shell access to Max's machine, only file read/write through the device
bridge, so the run itself had to happen locally:

```
git log --oneline -8          # confirmed HEAD at afbfbdf, the 5 prep commits present
make eval-fast                 # mock sanity check first - 100% pass, matches prep-step numbers
make eval-fast-live             # the real run
```

Before the run, Max set a **$20/month spend limit on the Anthropic Console workspace** - the
account-level backstop the prep step had flagged as still missing (nothing in the repo itself
bounds a run's aggregate spend; `max_cost_usd` is per-case only). Total spend for this run came in
at **$1.15** across 13 cases, well inside both the Console cap and the $1.50-3.50 estimate from the
prep step.

### What the numbers say

```json
{
  "tier": "fast", "llm_mode": "live", "n_cases": 13,
  "pass_rate": 0.9231, "latency_p95_s": 229.5986, "mean_cost_usd": 0.0883
}
```

vs. `evals/thresholds.yaml` (`min_pass_rate: 0.90`, `max_latency_p95_s: 300.0`,
`max_mean_cost_usd: 0.10`): **all three thresholds met.** This is the first `make eval-fast-live`
run to pass since the project started - the first two 15-case runs failed on both pass rate
(73.3%) and latency (364.4s). Full report:
`evals/reports/fast-live-20260923-204027.json`.

This run is the first to combine three things that were each verified separately before but never
together at full scale: the streaming fix (no more `APITimeoutError`), the known-unstable cases
moved out of the gating set (`stat-003`/`stat-004`), and concurrent case scoring (5 workers). All
13 cases completed cleanly with no crashes, no timeouts, and no thread-safety symptoms (no garbled
trace lines) - the assumptions flagged as untested in the prep step held up under real concurrent
live traffic.

**One case still failed**: `prov-001` (a fictional-sounding claim about eels in a Montana water
treatment plant) returned `"not supported"` where the case expects `"provenance-only"`. This
doesn't affect the run's pass/fail status (92.3% still clears the 90% floor), but it's the same
shape of mismatch that `prov-005` hit in the second 15-case run: the evaluator finds a real but
irrelevant search result (here, an unrelated same-named viral video) and treats that weak signal as
grounds for "not supported" instead of the more honest "provenance-only." `prov-005` itself passed
cleanly this run. Documented in the README's Known Failures rather than fixed - it's only shown on
two different cases so far, not the same case twice, so it's not yet confirmed as run-to-run
instability the way `stat-003`/`stat-004` are; it could also be a systematic prompt issue. Left in
the gating set, per this repo's rule against editing eval cases to paper over a failure.

### README updated to match

- **Results table**: replaced the stale 15-case, both-thresholds-failing numbers with this run's
  13-case, all-thresholds-passing numbers. Updated the report link and the headline paragraph
  (`make eval-fast-live` now meets its own thresholds for the first time).
- **Known failures**: the timeout-ceiling entry now says "confirmed at full scale," citing this
  run's clean 13/13 completion. Added a new entry for the `provenance_only`
  not-supported-vs-provenance-only pattern, consolidating the `prov-005` (run 2) and `prov-001`
  (this run) instances - the old truncation-bullet's stale reference to `prov-005`'s mismatch now
  points at the new consolidated entry instead of re-explaining it.
- **Security and cost notes**: added a line noting `max_cost_usd` is still per-case, not
  per-run, and that the $20/month Console limit is now the backstop for aggregate spend.
- **What's next**: marked the "confirm streaming fix at full scale" item done, added a new item for
  investigating the `provenance_only` mismatch pattern before the next live run.

## What was deliberately not touched

- No eval case content, labels, or `expected_contains` changed - `prov-001` stays as-is, in the
  gating set, documented as a known failure rather than moved or relabeled.
- No prompt changes. The `provenance_only` mismatch pattern is flagged for a future step, not fixed
  here - fixing it needs either a prompt tweak (out of scope for a validation-and-docs step) or more
  data on whether it's run-to-run instability.
- The plaintext `github token.txt` sitting in `~/Desktop/Projects/` (outside the repo, so not
  committed) was noticed while browsing the folder but not touched - worth moving somewhere safer
  or deleting once keychain/SSH auth is in place, per `Local_Environment_Setup.md`, but that's
  Max's call, not something to action unasked.

## Test / lint / typecheck / eval status

No code changed this step, so lint/test/typecheck weren't rerun - last known-green state is from
the prep step (`make lint`, `make typecheck`, `make test` 23/23, all clean). `make eval-fast` (mock)
was rerun as a pre-flight sanity check: 13/13 cases, 100% pass, matching the prep step's numbers
exactly, confirming nothing broke between then and now. `make eval-fast-live`: see numbers above -
**meets thresholds** (first time).

## Open questions / flag for review

1. **`prov-001`'s verdict mismatch** - is it isolated noise, or does it belong in
   `known-unstable/` alongside `stat-003`/`stat-004`? One data point on this specific case isn't
   enough to tell; the pattern (weak tangential source → over-confident "not supported") has now
   shown on two different provenance cases, which is more suggestive of a systematic prompt issue
   than pure flakiness, but that's a hypothesis, not confirmed. Needs either a rerun to see if
   `prov-001` itself flips, or a look at the `provenance_only` prompt's negative-evidence bar.
2. **No aggregate spend cap in code, still.** The Console-level $20/month limit set before this run
   is an account-wide backstop, not scoped to this project's key specifically (per the
   `portfolio-projects` workspace convention in `Local_Environment_Setup.md`, other projects share
   it). Worth deciding whether that's precise enough or whether a per-run cost cap belongs in
   `evals/run.py` itself.
3. **The plaintext GitHub token file** noted above - not urgent, but flagged for whenever it's
   convenient to clean up.

## Next command

```bash
git status                                     # review the README diff
git diff README.md
git add README.md docs/sessions/2026-09-23-live-validation-run.md
git commit -m "docs: update README and session log with the first passing eval-fast-live run"
```
