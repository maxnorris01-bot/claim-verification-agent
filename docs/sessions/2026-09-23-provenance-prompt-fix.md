# 2026-09-23 - provenance_only prompt fix for the not-supported/provenance-only mismatch

Scoped step: fix the `prov-001` verdict mismatch flagged in the previous step's live-validation
run, before doing any further work on this repo. One prompt file changed, no code touched, no eval
cases touched.

## What changed and why

The previous live run (`fast-live-20260923-204027.json`, 12/13 pass) failed on `prov-001`: the
evaluator returned `"not supported"` where the case expects `"provenance-only"`. This was the same
failure *shape* as `prov-005` in an earlier run - the evaluator found a search result that merely
shares a name or keyword with the claim (an unrelated same-titled YouTube video for `prov-001`; a
pre-existing unrelated municipal fee for `prov-005`) without actually addressing the claim's
substance, and treated that tangential hit as grounds for a "not supported" verdict. In both cases
the model's own `reasoning` field explicitly hedged ("cannot definitively prove non-existence,"
"cannot be confirmed or refuted directly") - the verdict it output didn't match its own stated
evidence assessment.

**Fix**: `prompts/provenance_only.md`, bumped `version: 1` -> `2`. Tightened the verdict-label
definitions so contradicting evidence must specifically address the claim's actual subject (not
just share a name/keyword), and added an explicit pre-verdict check: if the model's own reasoning
wouldn't confirm or refute the claim, the verdict must be `provenance-only`, regardless of how
hoax-like the claim otherwise looks. This is a prompt-only change - `src/` untouched.

## Verification (per CLAUDE.md: prompt changes need make eval-fast shown before calling it done)

```
make eval-fast        # mock, free - 13/13 pass, 100%, confirms routing unaffected
make eval-fast-live   # real API cost - the actual test of the fix
```

Live result (`fast-live-20260923-205258.json`):

```json
{
  "tier": "fast", "llm_mode": "live", "n_cases": 13,
  "pass_rate": 1.0, "latency_p95_s": 120.5587, "mean_cost_usd": 0.0708
}
```

13/13 pass. `prov-001` now returns `provenance-only` (matches expected); `prov-005` also correctly
`provenance-only` (no regression). All three thresholds cleared with more margin than the previous
run (latency p95 dropped from 229.6s to 120.6s, mean cost from $0.088 to $0.071 - both plausibly
just this run's mix of how many searches each claim needed, not caused by the prompt change, which
only touches verdict selection, not search behavior). Total run cost: $0.92.

One incidental observation, not something this step fixed: `prov-003`'s raw evaluator output this
run has some garbled trailing text in the `reasoning` field (duplicated phrasing and stray JSON-like
characters after "since small unincorporated places may have limited online footprint"). It didn't
affect scoring (`prov-003` passed - the required substrings matched fine), so it's cosmetic as far
as the eval is concerned, but worth a look if it recurs - could be a structured-output parsing edge
case worth tracing separately.

## What was deliberately not touched

- No eval case content changed. `prov-001`/`prov-005` stay in the gating set, unmoved.
- No code in `src/` touched - this is entirely a prompt wording change.
- Didn't touch the `stat-003`/`stat-004` known-unstable cases or their prompt
  (`statistical_data.md`) - out of scope for this step, which was specifically about the
  `provenance_only` mismatch.

## Test / lint / typecheck / eval status

Lint/typecheck/pytest not rerun this step (no code changed - only a prompt markdown file, which
those don't cover). `make eval-fast` (mock): 13/13, 100%, matches prior baseline exactly - confirms
the prompt edit didn't break routing. `make eval-fast-live`: 13/13, 100% - **all three thresholds
met, first fully clean live run.**

## Open questions / flag for review

1. **One confirming run isn't two.** The `stat-003`/`stat-004` instability only became visible as
   real instability on the *second* live run - a single clean run after this prompt fix doesn't
   prove the same failure mode won't resurface on `prov-001`, `prov-005`, or a different provenance
   case under different search results. Worth treating this as provisionally fixed, watched on the
   next live run, not closed.
2. **`prov-003`'s garbled reasoning text** (see above) - didn't affect this run's outcome, flagged
   for whenever it's convenient to look into, not urgent.
3. Same aggregate-spend note as before still applies: no per-run cost cap in code, Console-level
   $20/month limit is the only backstop.

## Next command

```bash
git status
git diff README.md
git add prompts/provenance_only.md README.md docs/sessions/2026-09-23-provenance-prompt-fix.md
git commit -m "fix: tighten provenance_only prompt so tangential sources don't trigger not-supported"
git push
```
