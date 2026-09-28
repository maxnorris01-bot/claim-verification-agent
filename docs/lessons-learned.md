# Lessons learned — Claim Verification Agent (project retrospective)

Written 2026-09-27, the day the project moved to reserved/backup status (see
`working-notes-and-decisions.md`, 2026-09-27 entry, for the decision itself). This doc is the
capstone summary for anyone picking the project back up, or starting the next one and wanting to
avoid repeating what didn't work here. It doesn't replace `docs/sessions/*.md` or
`working-notes-and-decisions.md` — it's the "what would we do differently" rollup, written once,
at the point the project stopped being actively developed.

## Why this project was shelved

Cost target met (mean $0.017/claim vs. the 2c MVP target), quality held (92-100% pass across live
runs), but latency stayed stuck at 10-17s per live claim with no remaining, confirmed lever from a
full session of trying (JSON Schema `maxItems`/`maxLength` don't work as bounds; a prose "be
concise" instruction was never cleanly tested). The only paths left are a genuinely different
architecture or leaning on a not-yet-built verdict store. That's a real wall, not a tuning gap, and
the full record is in `docs/sessions/2026-09-26-tavily-search-spike.md` and the
2026-09-26 entries in `working-notes-and-decisions.md`.

## Approach

- **The full 5-tier agentic pipeline was built before its unit economics were ever checked.**
  Performance targets (5s / 2 cents per live claim) were only set formally at v0 close-out
  (2026-09-26), after the whole classifier + 5-tier evaluator architecture already existed. The
  performance wall wasn't discovered until the very end of the build, not the start. Next time:
  run a one-claim, one-tier spike through the real API call pattern the product will actually make,
  and check it against a performance target, *before* laying out the full architecture.
- **The named differentiator was deferred for the entire project and never built.** The portfolio
  plan calls the self-grading / accuracy-tracker mechanic this project's actual competitive edge
  over existing fact-checking tools - it was pushed to "v1, maybe" from day one and never
  implemented. A differentiator that never ships doesn't differentiate anything. Next time: treat
  the named differentiator as core scope, not polish, or don't claim it as the differentiator.
- **Scope (5 evaluation tiers) was ambitious for a solo project.** Only 2 of 5 tiers ever got
  built out. A narrower initial scope (2-3 tiers, chosen to still be a complete, honest product)
  would have reached a demonstrable finished state faster, with performance and differentiator work
  layered on top of something whole rather than raced against an ever-expanding tier list.

## Implementation

**Worth reusing as-is:**
- Prompt versioning via frontmatter (`version: N`) plus `prompt_versions` recorded in every eval
  report - made prompt fixes directly attributable to specific reports.
- The eval harness convention that cases/thresholds only change in dedicated commits, never
  bundled with the change they'd excuse - held up as a real guardrail every time, not just a rule
  on paper.
- The ADR log for non-obvious decisions, and the two-tier `docs/sessions/*.md` +
  `working-notes-and-decisions.md` record (session docs for full reconstruction, the decisions log
  for a fast "what's next" answer without re-reading every session).
- `scripts/devserver.py` / `make devserver` - building a manual, one-claim-at-a-time feel-test tool
  before making a go/no-go call was worth it; a JSON summary of pass rates doesn't tell you whether
  10 seconds *feels* slow to a real user.
- Mock/live LLM toggle and the known-unstable case convention for run-to-run model instability.

**Change next time:**
- Wire budget/cost tracing (`Budget`, `src/app/tracing.py`) in from the very first prototype, not
  after a pipeline already exists. It's what made the performance investigation possible at all
  here - doing it from session one would have surfaced the cost/latency problem sooner, closer to
  when the architecture could still cheaply change.
- A structured-output evaluator prompt with multiple verdict labels needs an explicit
  "reasoning and verdict must agree" instruction from the start, not after a live-run mismatch
  finds it. (Found here via the `prov-001`/`prov-005` verdict mismatch - see the 2026-09-23
  decisions entry.) Likely to recur in Purchase Decision Agent's buy/wait/skip verdict.

**API capability limits discovered (worth remembering for any future prompt/schema work):**
- Anthropic's structured output (`output_config.format.schema`) rejects `maxItems` on array fields
  outright (a 400 error) and silently accepts-but-ignores `maxLength` on string fields (live output
  ran to 786 characters against a 400-char cap, no error). Don't rely on JSON Schema length/count
  keywords to bound model output length or cost.
- A model-driven web-search tool loop is inherently multi-turn (decide a query, read results,
  answer), and its cost/latency track the search content fed back into context - tunable
  (search count, effort, tool version) up to a plateau, not past it.
- Moving retrieval outside the model (a dedicated search API run in parallel, one tool-less model
  call over the snippets) reliably cuts cost, but doesn't by itself fix output-generation latency -
  that's driven by the model's own generation length, which the schema bounds above can't currently
  constrain.

## Template repo fixes contributed back

Seven gaps found while building this project were generalized and applied to
`portfolio-project-template` on 2026-09-23: a mock/live LLM client toggle, concurrent eval scoring,
thread-safe tracing, real per-case cost wiring, an aggregate run-level cost cap, more realistic
default thresholds, and a known-unstable case convention. Full detail already lives in the
template's own `docs/lessons-learned.md` - not duplicated here. Still open in the template, not yet
generalized: mock-forced/live-forced eval-standard/nightly variants, an adversarial/
prompt-injection eval pattern, and a self-grading/outcome-tracking pattern (needs a persistence
layer the template has no opinion on yet - worth building once a project actually needs it).

## Working cadence and structure (Cowork + device-bridge collaboration)

- **Device-bridge writes need explicit post-write verification.** `device_commit_files` reported
  success at least three times this project while the file on Max's machine silently kept its old
  content - caught only by re-staging and diffing checksums afterward, and it cost at least one
  wasted live-eval run before being caught. Now standard practice (and documented in
  `Chat_Instructions.md`): always re-stage and compare after any source-file commit; if a same-path
  re-commit doesn't take effect, write to a new filename and commit with `force: true`, which
  consistently worked when a same-path retry didn't.
- **Protected files need manual handoff, and heredocs need real tabs.** `Makefile` and
  `.github/workflows/ci.yml` can't be written directly through the bridge - always hand over full
  file content for Max to paste. A heredoc with `Makefile` recipe tabs needs `TAB=$(printf '\t')`
  and an unquoted heredoc; a quoted one silently converts leading tabs to spaces in transit and
  breaks `make` with "missing separator."
- **Terminal commands always get handed off, split by repo/terminal.** No `device_bash` in this
  session type - every `git`/`make`/`uv` command goes to Max verbatim, and since he runs one
  terminal per repo, commands are split by which repo's terminal they run in. Held up well all
  project.
- **No AI attribution lines in commits or PRs** - a standing preference that slipped through once
  (2026-09-26) before being caught and documented in both this repo's decisions log and the
  project's `Chat_Instructions.md`. Worth a deliberate check at the start of any future session,
  before drafting a first commit message.
- **Eval cases/thresholds only change in dedicated commits** - repeated from Engineering Standards
  here because it held up as a real guardrail in practice, not just a rule that sounded good on
  paper.

## Biggest lesson for the next project

Run a tiny, cheap spike through the real cost/latency-driving code path, and check it against the
project's actual performance target, before committing to the project's full scope - not as a gate
discovered 90% of the way through a fully built v0. That's exactly the reasoning behind the
portfolio's new roadmap (see `Applied_AI_Portfolio_Plan.md`, 2026-09-27 update): the next projects
start as a no-AI-call MVP that proves out the product's core data/logic and shipping cadence for
free, with the agentic/LLM layer added later as its own deliberate, separately evaluated upgrade -
rather than building the full agentic design first and finding out only at the end whether it's
economically viable.

## See also

- `docs/sessions/*.md` - what changed and why, per work session.
- `docs/working-notes-and-decisions.md` - the full decision log, including the 2026-09-26
  performance investigation and the 2026-09-27 shelving decision.
- `README.md`'s Known Failures section - the detailed, evidence-quoted record of real bugs found.
- `docs/adr/` - specific architectural decisions with fuller reasoning than fits here.
