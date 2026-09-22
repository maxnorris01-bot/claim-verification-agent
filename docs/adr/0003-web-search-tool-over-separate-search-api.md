# 0003. Use Claude's built-in web search tool instead of a separate search API

- **Status:** accepted
- **Date:** 2026-09-21

## Context

Both evaluators need to run live web searches, read the results, and decide what they show. That
needs a search provider (Google/Bing/SerpAPI/Tavily/etc.) plus code to fetch pages, extract text,
and feed results back to the model - or Claude's server-side web search tool
(`web_search_20260209`), which runs the search and lets Claude read and filter results in the same
API call, no separate key or client-side fetch/parse code.

## Options considered

1. **A separate search API** (e.g. Tavily, SerpAPI, Bing). Pro: provider choice, results
   independent of Anthropic, easier to unit-test with recorded fixtures. Con: another API key and
   `.env` entry for a one-person portfolio project (SPEC.md explicitly says "no separate search API
   key"), plus writing and maintaining fetch/parse/rank code that a server-side tool already does.
2. **Claude's web search tool.** Pro: one credential, no fetch/parse/dedupe code to write or
   maintain, and dynamic filtering (the `_20260209` tool variant) runs on Anthropic's side before
   results reach the context window. Con: search behavior (which queries run, which results get
   read) is inside the model's tool loop, not directly inspectable or swappable, and it ties
   retrieval quality to Anthropic's search backend.

## Decision

Option 2, primarily because it's what SPEC.md specifies ("Claude's built-in web search tool via
the Anthropic API. No separate search API key"), and secondarily because it removes an entire
integration surface (provider client, fetch, HTML/text extraction, error handling for a second
external service) for a two-evaluator v0.

## Consequences

- Every evaluator call's tracing span (`app.tracing.span`) records the queries the model ran and
  how many results came back (`llm._inspect_tool_blocks`), which is the only visibility into what
  was searched - there is no separate search-log to cross-reference.
- Evidence URLs are checked against what the tool actually returned (`evaluators._search_evaluator`
  drops any `source_url` not in that set) since there is no independent fetch step to verify a URL
  is real; this guards against the model citing a URL from memory, not against the tool itself
  returning something unavailable to a human clicking it.
- Search cost is folded into the same per-request budget check as tokens (`llm.estimate_cost`
  adds a flat per-search estimate, since the API does not return a dollar figure), rather than
  tracked as a separate line item against a second provider's bill.
- If search quality becomes a problem, swapping providers means replacing the tool-use loop in
  `src/app/llm.py`, not just an API key - `web_search_tool()` is the only place the tool type is
  named, which keeps that swap to one file.
