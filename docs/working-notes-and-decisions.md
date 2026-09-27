# Working notes and decisions log - Claim Verification Agent

This is a different kind of record from `docs/sessions/*.md`. Session docs narrate what changed in
one sitting and are written for someone with zero context picking up the diff. This file is the
opposite shape: short, durable entries - a decision plus *why*, or an open item worth remembering -
meant to be skimmed months later when the reasoning behind something has otherwise been forgotten.
Append to it whenever a real decision gets made, not just at the end of a session. If something is
already fully documented elsewhere (a technical fix in a session doc, a known failure in the
README, a design tradeoff in an ADR), point to it here rather than duplicating it.

## Decisions

**2026-09-26 - v0 merged to `main` as a regular merge commit, not a squash.** Merge commit
`23ae2e6` brings in all 45 branch commits. Chose a regular merge because the README and session
docs cite specific commit hashes (e.g. `7ac91bb`, `737917f`, `0563054`, `f5828ff`); a squash merge
would have collapsed those into one new commit and left the cited hashes reachable only through the
old branch. Merged locally (`git merge --no-ff`) rather than via a PR because `gh` isn't installed
and Homebrew isn't on this Mac - a PR would have left a GitHub-side record but not changed the
result. Reasons it was ready to merge: live eval 13/13 with all thresholds met, lint/typecheck/tests
green, reports and docs current. What "v0 shipped" does and doesn't mean: two of five tiers work
and are eval-backed; the walkthrough was deliberately thin, and output formatting is still open.

**2026-09-26 - Aggregate spend check ported; `max_total_cost_usd` set to $2.50.** The template's
optional run-total check now exists in this repo's `evals/run.py`, with `max_total_cost_usd: 2.50`
in `evals/thresholds.yaml` (added in its own `eval:` commit, per the rule that thresholds change
separately). $2.50 is sized for the 13-case fast tier: the last two live runs cost about $1.08, so
it leaves room for a heavier run and still catches a runaway one. It's one number for all tiers,
so `eval-standard`'s ~50 cases would trip it - deliberate for now, since that tier is unused (see
the `eval-standard`/`eval-nightly` decision). Also found while verifying: `tests/test_smoke.py`
hardcoded prompt version `"1"` and had been failing since the 2026-09-24 prompt v3 bump, uncaught
because unit tests weren't rerun that session. Fixed to accept any positive integer version.

**2026-09-24 - v0 walkthrough kept short on purpose.** Max ran two live claims by hand (an
unimplemented-tier one and a well-supported statistical one) and stopped there, judging that more
hands-on testing is better done once the actual site/tool is up rather than through the CLI. Both
behaved correctly. Findings (trailing-character bug, `not-implemented` output wording) went into
`docs/todo.md`. Consequence: the close-out was based on a thin sample, so nothing here proves the
search-based tiers read well on nuanced claims - the eval runs cover verdict correctness, not
output readability.

**2026-09-24 - Eval reports: ignored by default, force-add only the ones the README cites.**
`.gitignore` ignores `evals/reports/*.json` (every run writes a timestamped file - tracking all of
them, including the many mock-mode ones, would be noise), and until now that meant the README's
report links were all broken on GitHub. Chose to keep ignoring by default but `git add -f` the six
reports the README actually cites (about 150KB total), so the results table is verifiable by
clicking through, including the failing 11/13 run that shows the v2 regression. Consequence: when a
future run gets cited in the README, it needs `git add -f` too - a plain `git add` will silently
skip it.

**2026-09-24 - Portfolio hosting: one site, per-project tabs.** All three portfolio projects will
live on a single website: a homepage explaining each project, some navigation, each project on its
own tab/section. Not decided yet: the actual stack/hosting provider. Consequence worth keeping in
mind: a public site that takes live user input and calls a paid API per request needs its own
backend regardless of anything else (rate limiting, abuse prevention, keeping `ANTHROPIC_API_KEY`
server-side, never shipped to the browser) - this isn't optional infrastructure that only
self-grading would need.

**2026-09-24 - "User testing" for v0 close-out, scoped down.** Means Max personally running
through the site and checking it looks right and behaves as expected - not a broader beta or
outside testers. Revisit this scope if/when the project is further along and outside eyes would
actually help.

**2026-09-24 - Self-grading: not committed to v1, not dropped either.** The portfolio plan doc
names the self-grading accuracy tracker as this project's actual differentiator versus existing
competitors, so it shouldn't quietly disappear from scope - but it's also the one piece that adds
real infrastructure (persistent storage, a scheduled recheck job). Given the hosting decision
above already implies a backend for other reasons, the marginal cost of adding self-grading once
that backend exists is smaller than it looks in isolation. Leaning toward: ship v1 without it,
add it once the backend exists anyway. Not fully decided.

**2026-09-24 - `eval-standard` / `eval-nightly` tiers: deliberately left unused.** They exist as
Makefile targets and code paths (in both this repo and the template) but nobody's written the
50+/100+ case sets they're meant for, and nothing schedules `nightly` to actually run. For a solo
portfolio project without real production traffic, investing in them isn't worth it right now.
Revisit if the case count grows past ~15 or there's an actual reason to want a scheduled,
more-thorough-but-less-frequent check.

**2026-09-24 - Provenance_only prompt: v2 did NOT hold; v3 provisionally does.** The caution in the
2026-09-23 entry below was right. The second live run under v2 (`fast-live-20260924-210331.json`)
failed 11/13: `prov-005` regressed to `not supported`, using unrelated municipal and state fees as
"contradicting" evidence while its own `origin_trace` said no origin was found. Chose to write a
tighter prompt (v3: explicit list of what does not count as contradicting evidence, plus a required
final reasoning-vs-verdict check) rather than just rerun v2 again, since a repeat run of unchanged
code adds a noisy sample and no fix. Tested `prov-005` in isolation 4x (all `provenance-only`), then
one full live run at 13/13 (`fast-live-20260924-212213.json`). Still a small sample; watch it on
future live runs. Details: `docs/sessions/2026-09-24-provenance-prompt-v3.md`.

**2026-09-24 - `stat-005` failed once (`mixed` vs expected `not supported`), then passed; not moved
to `known-unstable/` yet.** Same code and prompt both times, so it is model instability, same shape
as `stat-003`/`stat-004`. Decided not to move a case off one failure in four runs; if it flips
again, move it in its own `eval:` commit. Never edit the expected label to make it pass.

**2026-09-24 - Eval runner prints per-case progress to stderr.** `evals/run.py` now emits
`[start]`/`[done N/M]` lines, because a multi-minute live run with a silent terminal is hard to tell
apart from a hang. Output-only change; scoring, reports and thresholds unchanged. For ad hoc loops
of `scripts/check_claim.py`, prefer `echo` status lines plus `tee` over redirecting to a file.

**2026-09-23 - Provenance_only prompt fix, confirmed once, not twice.** `prov-001` and `prov-005`
were returning `not supported` when they should have returned `provenance-only` (evaluator treated
a tangential, irrelevant search hit as a negative signal). Fixed via a prompt-only change
(`prompts/provenance_only.md` v2). One live run since the fix passed 13/13 clean. Important
caveat: the `stat-003`/`stat-004` instability (see README's Known Failures) only became visible as
*real* instability on a *second* identical live run - so one clean run here doesn't yet prove this
won't resurface. Treat as provisionally fixed until a second live run confirms it.

**2026-09-23 - Template gaps applied back to `portfolio-project-template`.** Mock/live LLM toggle,
concurrent eval scoring, thread-safe tracing, real per-case cost wiring, a new aggregate
`max_total_cost_usd` run-level check (something this repo itself still doesn't have), realistic
threshold defaults, and the known-unstable case convention - all ported from what this repo built
from scratch, generalized where they were domain-specific. Verified clean (lint/typecheck/test/
eval-fast) before committing. Full detail in the template's own `docs/lessons-learned.md`.

**2026-09-21 - Aggregate live-run spend has no in-repo cap; a $20/month Console limit is the
backstop.** `Config.max_cost_usd` bounds one case/invocation, not a whole run's total. Rather than
build that into this repo's own `evals/run.py` mid-v0, set a $20/month spend limit on the
Anthropic Console workspace as the actual guardrail. (Update 2026-09-26: the template's optional
`max_total_cost_usd` check has since been ported into this repo - see the 2026-09-26 entry above.
The Console limit remains the account-level guard.)

**2026-09-24 - `github token.txt` in `~/Desktop/Projects/` is intentional, not a finding.**
Sits outside any repo folder, kept there on purpose for reference. Noting this here so it doesn't
get re-flagged as a surprise security issue in a future session.

## Open items / parking lot

- Keep watching the `provenance_only` fix (v3) on future live runs - one full clean run plus 4/4 on
  `prov-005` isolated, not yet a long track record (see 2026-09-24 decision above).
- Stray quote/trailing characters in evaluator free-text fields: investigated 2026-09-26 and
  deliberately left as a documented cosmetic quirk (see `docs/todo.md`). Model-side, not our
  parsing; roughly 1 run in 5 on the Gallup claim; revisit only if formatting makes it visible.
- Output formatting: the walkthrough noted `not-implemented` verdicts mix the system message with the
  classifier's own take in `reasoning`, and `confidence: "low"` on a non-evaluation is ambiguous.
  See `docs/todo.md`.
- Adversarial prompt-injection eval cases - named in the README's "What's next," never built.

## See also

- `docs/sessions/*.md` - what changed and why, per work session.
- `README.md`'s Known Failures section - the detailed, evidence-quoted record of real bugs found
  and their status.
- `docs/adr/` - specific architectural decisions with fuller reasoning than fits here.
