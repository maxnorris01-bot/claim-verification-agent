# Working notes and decisions log - Claim Verification Agent

This is a different kind of record from `docs/sessions/*.md`. Session docs narrate what changed in
one sitting and are written for someone with zero context picking up the diff. This file is the
opposite shape: short, durable entries - a decision plus *why*, or an open item worth remembering -
meant to be skimmed months later when the reasoning behind something has otherwise been forgotten.
Append to it whenever a real decision gets made, not just at the end of a session. If something is
already fully documented elsewhere (a technical fix in a session doc, a known failure in the
README, a design tradeoff in an ADR), point to it here rather than duplicating it.

## Decisions

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
Anthropic Console workspace as the actual guardrail. (The template now has an optional
`max_total_cost_usd` check in `evals/run.py` - worth porting back into this repo at some point,
not done yet.)

**2026-09-24 - `github token.txt` in `~/Desktop/Projects/` is intentional, not a finding.**
Sits outside any repo folder, kept there on purpose for reference. Noting this here so it doesn't
get re-flagged as a surprise security issue in a future session.

## Open items / parking lot

- Merge `feat/v0-pipeline` into `main` - pushed to GitHub, PR link generated, never opened or
  merged. Decide: merge now to mark v0 "shipped," or keep developing on the branch a while longer.
- A second live run to confirm the `provenance_only` fix holds (see decision above) - not urgent,
  but do it before fully trusting this as closed.
- `prov-003`'s raw `reasoning` output had duplicated phrasing and stray trailing characters in the
  2026-09-23 live report - didn't fail the case (the required substrings still matched), never
  investigated. Worth a look if it recurs; not investigated as of this writing.
- Adversarial prompt-injection eval cases - named in the README's "What's next," never built.
- Port the template's `max_total_cost_usd` aggregate-spend check back into this repo's own
  `evals/run.py` (see the 2026-09-21 decision above) - the template now has this, this repo
  doesn't yet.

## See also

- `docs/sessions/*.md` - what changed and why, per work session.
- `README.md`'s Known Failures section - the detailed, evidence-quoted record of real bugs found
  and their status.
- `docs/adr/` - specific architectural decisions with fuller reasoning than fits here.
