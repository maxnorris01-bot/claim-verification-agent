# 0002. Ship the five-tier classifier ahead of full evaluator coverage

- **Status:** accepted
- **Date:** 2026-09-21

## Context

SPEC.md scopes v0 to two of five tiers (`statistical_data`, `provenance_only`) having a real
evaluator; the other three (`scientific_empirical`, `historical_factual`,
`contested_unfalsifiable`) still need a tier assignment, since the classifier is a single call that
always picks one of the five. The alternative would be to ship a classifier limited to the two
implemented tiers plus a catch-all "other," and add the remaining three tiers only once their
evaluators exist.

## Options considered

1. **Classifier only knows the two implemented tiers**, everything else falls into one catch-all
   bucket. Pro: no need to define a `not-implemented` verdict shape. Con: the catch-all can't be
   distinguished from a genuinely ambiguous claim, and the classifier's taxonomy has to be redone
   (not just extended) when each new evaluator ships, since "other" would need to be split back
   into named tiers later.
2. **Classifier names all five tiers now; unimplemented tiers return a `not-implemented` Verdict.**
   Pro: the routing decision and the evaluation decision are separated cleanly, the tier taxonomy
   never changes shape as evaluators are added, and the eval set can already exercise "does the
   pipeline degrade gracefully" (the spec asks for 1-2 such cases). Con: `Verdict.verdict` needs a
   `not-implemented` label from day one, and the five-tier design has to be right before any
   evaluator besides the first two is built.

## Decision

Option 2. The classifier is the pipeline's routing contract: given the full five-tier taxonomy is
already fixed in SPEC.md, defining it once and having unimplemented tiers degrade explicitly is
simpler than growing the taxonomy in lockstep with evaluator coverage, and it proves the
classify -> route -> (evaluate | decline) shape end to end before more evaluators are added.

## Consequences

Adding `scientific_empirical` or `historical_factual` in v1 is registering a new evaluator in
`EVALUATORS` (`src/app/evaluators.py`) and writing its prompt - no classifier or `Verdict` schema
change. The cost is that the classifier's tier boundaries (especially provenance_only vs.
statistical_data, and the not_a_claim escape hatch for invalid input) have to be gotten right now,
since they are load-bearing before three of the five tiers have any way to be exercised
end-to-end; `evals/cases/v0.jsonl`'s two "unimplemented tier" cases are the only check on this
until v1.
