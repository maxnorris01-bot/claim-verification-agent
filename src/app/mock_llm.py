"""A mock Anthropic client, so the pipeline runs end-to-end with zero API calls.

Two things live here:

  * The response-construction primitives (`text_block`, `search_blocks`, `response`) and
    `ScriptedClient`, which replays pre-built responses in order. These were originally written
    for `tests/conftest.py` and are promoted here so the same shapes are available to both the
    unit tests (which need exact control over specific scenarios: `pause_turn`, malformed output,
    budget-cap trips) and anything else that wants to script an exact conversation.
  * `MockAnthropicClient`, which auto-generates a schema-valid response for *any* classifier or
    evaluator request by inspecting the request's `output_config.format.schema` - no scripting
    needed. This is what `APP_LLM_MODE=mock` (the default - see `Config.llm_mode`) wires into
    `app.llm.get_client`, so `make eval-fast`, `scripts/check_claim.py`, and any other entry point
    run for free by default, with zero real API calls.

`MockAnthropicClient`'s claim routing uses simple, documented keyword heuristics - good enough to
route every v0 eval case to the tier its `category` claims, so `make eval-fast` can structurally
exercise routing, evaluator schema shape, evidence-URL grounding, tracing, and budget accounting.
It is deliberately NOT a stand-in for real model quality: verdict labels (`supported` / `mixed` /
...) are picked arbitrarily from the schema's allowed set, not reasoned about from evidence. Only
`make eval-fast-live` (the real API) tests whether verdicts are actually correct - see
`evals/run.py`'s mode-aware scoring.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

# ---- Response-construction primitives ------------------------------------------------------
# Shared by ScriptedClient and MockAnthropicClient below, and imported directly by
# tests/conftest.py for exact scenario control.


def text_block(payload: dict[str, Any] | str) -> SimpleNamespace:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(type="text", text=text)


def search_blocks(query: str, urls: list[str]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(type="server_tool_use", name="web_search", input={"query": query}),
        SimpleNamespace(
            type="web_search_tool_result", content=[SimpleNamespace(url=u) for u in urls]
        ),
    ]


def response(
    content: list[SimpleNamespace],
    *,
    stop_reason: str = "end_turn",
    input_tokens: int = 100,
    output_tokens: int = 50,
    searches: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            server_tool_use=SimpleNamespace(web_search_requests=searches),
        ),
        _request_id="req_mock",
    )


class ScriptedClient:
    """Returns scripted responses in order and records every request. Unit-test use only.

    Unlike `MockAnthropicClient`, this has no logic of its own - it exists to let a test pin down
    an exact sequence of responses (a malformed one, a `pause_turn`, a truncated one) that
    `MockAnthropicClient`'s always-succeeds happy path can't express.
    """

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self._responses.pop(0)


# ---- Heuristic claim router (MockAnthropicClient's classifier stand-in only) -----------------
# Order matters: checked top to bottom, first match wins.

_GIBBERISH_STOPWORDS = (
    " a ", " the ", " is ", " of ", " in ", " to ", " and ", " that ", " was ", " were ",
)  # fmt: skip
_STAT_KEYWORDS = ("%", "study", "poll", "survey", "research", "found that", "showed", "estimate")
_PROV_KEYWORDS = (
    "anonymous", "forum", "chain message", "chain text", "leaked", "unnamed source",
    "neighbor", "friend who", "blog", "insider",
)  # fmt: skip
_MORAL_KEYWORDS = ("moral", "unjustifiable", "should be", "ethic")
_HEALTH_KEYWORDS = ("exercise", "blood pressure", "health", "medical", "disease", "symptom")


def guess_tier(claim: str) -> str:
    """Route a claim to a tier name (or "not_a_claim"), using simple keyword heuristics.

    Good enough to correctly route every case in `evals/cases/v0.jsonl` - this is a plumbing
    stand-in, not a real classifier. Real routing quality is what `classifier.classify` (live
    mode) is for; see the module docstring.
    """
    text = f" {claim.lower()} "
    if not any(w in text for w in _GIBBERISH_STOPWORDS):
        return "not_a_claim"
    # Provenance signals checked first: a hearsay claim can still contain an incidental "%" or
    # "study" in its fabricated details (e.g. "a leaked memo says sales dropped 4%"), and the
    # hearsay framing is the more determinative signal when both are present.
    if any(k in text for k in _PROV_KEYWORDS):
        return "provenance_only"
    if any(k in text for k in _STAT_KEYWORDS):
        return "statistical_data"
    if any(k in text for k in _MORAL_KEYWORDS):
        return "contested_unfalsifiable"
    if any(k in text for k in _HEALTH_KEYWORDS):
        return "scientific_empirical"
    return "historical_factual"


class MockAnthropicClient:
    """Auto-generates schema-valid responses for any classifier or evaluator request.

    Wired in by `app.llm.get_client` when `Config.llm_mode == "mock"` (the default). Tells a
    classifier call from an evaluator call by inspecting the request's
    `output_config.format.schema` properties (classifier schemas have a `tier` property;
    evaluator schemas have a `verdict` property) - `app.llm.complete` doesn't need to change to
    support this.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        schema = kwargs.get("output_config", {}).get("format", {}).get("schema", {})
        properties = schema.get("properties", {})

        if "tier" in properties:
            return self._classifier_response(_last_user_text(kwargs["messages"]))
        if "verdict" in properties:
            return self._evaluator_response(schema)
        raise AssertionError(
            "MockAnthropicClient got a request whose schema has neither 'tier' nor 'verdict' - "
            "it only knows how to answer classifier and evaluator calls."
        )

    def _classifier_response(self, claim: str) -> SimpleNamespace:
        payload = {
            "reasoning": "Mock classifier: routed by keyword heuristic, not real reasoning.",
            "tier": guess_tier(claim),
        }
        return response([text_block(payload)], input_tokens=200, output_tokens=60)

    def _evaluator_response(self, schema: dict[str, Any]) -> SimpleNamespace:
        url = "https://mock.example/source"
        labels: list[str] = schema["properties"]["verdict"]["enum"]
        payload = {
            "verdict": labels[0],  # arbitrary - mock mode doesn't check verdict labels, see above
            "confidence": "medium",
            "evidence": [
                {
                    "claim_snippet": "mock",
                    "source_url": url,
                    "note": "Mock evidence for pipeline testing, not a real source.",
                }
            ],
            "origin_trace": "Mock origin trace - not a real source lookup.",
            "reasoning": "Mock evaluator: schema-valid placeholder, not a real assessment.",
        }
        content = [*search_blocks("mock query", [url]), text_block(payload)]
        return response(content, input_tokens=300, output_tokens=150, searches=1)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg["role"] == "user":
            content = msg["content"]
            return content if isinstance(content, str) else ""
    return ""
