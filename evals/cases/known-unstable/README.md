# Known-unstable cases

Cases here are **not** loaded by `evals/run.py::load_cases` - it globs `evals/cases/*.jsonl`
non-recursively, which does not descend into this subdirectory (confirmed empirically before
moving anything here; not just assumed from reading the code). They don't count toward pass_rate,
don't gate CI, and aren't part of any tier's case set.

## What lives here and why

`stat-003.jsonl` and `stat-004.jsonl` moved out of `evals/cases/v0.jsonl` on 2026-09-21 after two
live `make eval-fast-live` runs against identical code (same prompts, same model, same input)
returned **different verdicts on the same claim**:

- `stat-003` (CDC "1 in 36" autism figure): `mixed` in run 1, `supported` in run 2.
- `stat-004` (Gladwell/Ericsson "10,000 hour rule"): `mixed` in run 1, `not supported` in run 2.

Both claims genuinely straddle a line - a real figure from a real study, popularized with dropped
caveats - and the evaluator's `mixed` vs. `supported`/`not supported` call on them isn't stable run
to run. `evals/run.py`'s live-mode scoring is a single fixed-string `expected_contains` match; it
cannot express "any of {mixed, not supported} is acceptable, {supported} is not," which is what
these two claims would actually need. Gating CI on a coin flip isn't a useful signal, so they're
parked here instead of either being force-fit to one label or silently dropped.

Full quoted evidence: README.md's Known Failures section (repo root) and
`docs/sessions/2026-09-21-v0-implementation.md` / `2026-09-21-streaming-fix.md`.

## What retires a case from here

The v1 rubric-based, gold-set-validated LLM-as-judge SPEC.md calls for (`evals/README.md`'s "a
judge is trusted only after it agrees with a human-labeled gold set" rule) - not a tighter
`expected_contains` string. Once that judge exists and is validated, move a case's file back up
into `evals/cases/` (or wire this directory into a dedicated judged-case loader) rather than
gating it on exact-string matching again.
