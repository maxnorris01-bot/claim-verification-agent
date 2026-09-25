# To-do - Claim Verification Agent

A running checklist, not a narrative. Check items off as they're done and add a short note (what
happened, any surprises) rather than deleting the line - that note is often more useful later than
the checkmark itself. Add new items as they come up; don't wait for a session's end. This is
*not* where decisions and reasoning go - that's `docs/working-notes-and-decisions.md`. This is just
"what's next."

## Up next (in priority order)

- [ ] Second live eval run (`make eval-fast-live`) to confirm the `provenance_only` prompt fix
      (v2) holds. One clean run so far (13/13); the `stat-003`/`stat-004` instability only became
      visible as *real* instability on a second identical live run, so don't treat this fix as
      fully proven until it's been repeated. See working-notes-and-decisions.md, 2026-09-23 entry.
- [ ] Decide: merge `feat/v0-pipeline` into `main`, or keep developing on the branch. Pushed to
      GitHub, PR link generated, never opened/merged.
- [ ] v0 close-out walkthrough: personally run through the tool's behavior end-to-end and confirm
      it looks and behaves as expected. (Scoped to Max only, not outside testers - see
      working-notes-and-decisions.md, 2026-09-24 entry.)
- [ ] Implement output formatting (not yet started).
- [ ] Port the template's `max_total_cost_usd` aggregate run-level spend check back into this
      repo's own `evals/run.py` - the template has it now, this repo still relies solely on the
      $20/month Anthropic Console limit as a backstop.

## v1 (after v0 closes out)

- [ ] Remaining 3 of 5 v0 tiers (2 of 5 implemented so far).
- [ ] Self-grading / accuracy tracker - named in the portfolio plan as this project's actual
      differentiator, but not committed to v1's scope yet. Leaning toward shipping v1 without it
      and adding it once a real backend exists anyway (site hosting will need one regardless).
      Still not fully decided - see working-notes-and-decisions.md, 2026-09-24 entry.

## Lower priority / opportunistic

- [ ] `prov-003`'s raw `reasoning` output had duplicated phrasing and stray trailing characters in
      the 2026-09-23 live report. Didn't fail the case, never investigated. Worth a look if it
      recurs.
- [ ] Adversarial / prompt-injection eval cases - named in the README's "What's next," never
      built.

## Completed (most recent first)

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
