# 2026-09-24 - second live run, v2 regression, provenance_only prompt v3

Picked up the top open item: a second live `make eval-fast-live` to check whether the
`provenance_only` v2 fix (2026-09-23) actually held. It did not. Wrote a v3 prompt, tested it, and
added progress output to the eval runner. One prompt file and one runner file changed; no eval
cases or thresholds touched.

## What changed and why

**1. The second live run under v2 failed 11/13** (`evals/reports/fast-live-20260924-210331.json`,
pass rate 84.6% against the 90% threshold; latency p95 123.6s and mean cost $0.079 both fine).
Two failures:

- `prov-005` (Nebraska leaf-bag fee): returned `not supported` (medium confidence) against
  expected `provenance-only` - the same failure shape v2 was meant to fix. The model cited real
  but unrelated fees (Omaha and Lincoln municipal yard-waste bag fees, the state's business litter
  fee) as contradicting evidence, while its own `origin_trace` said "No origin found". So v2 held
  once (13/13) and then regressed on the next run with identical code.
- `stat-005` (Mehrabian "93% nonverbal"): returned `mixed` (high confidence) against expected
  `not supported`. The `statistical_data` prompt and code were unchanged from runs where it passed,
  so this is run-to-run model instability on a claim that straddles the line (real figure from real
  1967 studies, stretched far beyond their scope) - same shape as `stat-003`/`stat-004`. Not
  touched: no re-labeling, no move to `known-unstable/` off a single failure.

**2. `prompts/provenance_only.md` v2 -> v3.** Rather than rerun unchanged v2 (another noisy sample,
no fix), tightened the prompt: an explicit "what does NOT count as contradicting evidence" list
(a similar-but-different thing such as another city's or another state fee; a record that merely
fails to mention the claim; resemblance to a hoax), a required final check that each cited
contradicting source must discuss the claim's exact event and say it is wrong, and an explicit
rule that when reasoning and verdict disagree, the reasoning wins. A source about the claim's own
event that contradicts it still yields `not supported`, so real debunks are not blocked. Evidence
`note` fields must also say whether a source addresses the claim's subject or only something
adjacent.

**3. `evals/run.py` now prints per-case progress to stderr** (`[start] <id>` and
`[done N/M] <id> PASS|FAIL <latency> <cost>`), because a multi-minute live run with a silent
terminal is indistinguishable from a hang. Output only: scoring, reports, and thresholds are
unchanged, and the JSON summary on stdout is unaffected.

## Choices made mid-session

- Test v3 on `prov-005` in isolation (4 runs via `scripts/check_claim.py`, about $0.70) before a
  full run (about $1.08), rather than full run first. `evals/run.py` has no single-case option.
- Hold `stat-005` in the gating set for now; move it to `evals/cases/known-unstable/` in its own
  `eval:` commit only if it flips again.

## Eval numbers

Prompt v3, `fast-live-20260924-212213.json`: tier fast, live, 13 cases, pass rate 100% (13/13),
latency p95 125.7s (threshold 300s), mean cost $0.0828 (threshold $0.10), total about $1.08.
All three thresholds met. `prov-001` through `prov-005` all `provenance-only`; `stat-005` passed
(`not supported`); `stat-006` was slowest at about 120s along with the search-heavy provenance
cases. `prov-003` reasoning text was clean (the garbled text from 2026-09-23 did not recur).

Isolated `prov-005` runs under v3: 4/4 `provenance-only`, costs $0.13 to $0.23.

Mock `make eval-fast`: 13/13, 100%, prompt versions show `provenance_only: 3`.

## Test / lint / typecheck status

`make lint`: clean. `make typecheck`: clean (13 source files). `make eval-fast` (mock): passes.
Unit tests were not rerun this session (runner change is output-only).

## Open questions and flags

1. **v3 is a small sample.** One full clean run plus 4 isolated ones. v2 also passed cleanly once
   before regressing, so keep watching it on future live runs.
2. **`stat-005`** may belong in `known-unstable/`. One failure in four live runs so far.
3. Aggregate-spend backstop is still only the $20/month Console limit; porting the template's
   `max_total_cost_usd` check into `evals/run.py` remains open.

## Suggested commits (separate, per the repo's one-logical-change rule)

```bash
git add evals/run.py
git commit -m "feat: print per-case progress during eval runs"
git add prompts/provenance_only.md evals/reports/fast-live-20260924-210331.json evals/reports/fast-live-20260924-212213.json README.md docs/working-notes-and-decisions.md docs/todo.md docs/sessions/2026-09-24-provenance-prompt-v3.md
git commit -m "fix: tighten provenance_only prompt (v3) after v2 regressed on prov-005"
git push
```
