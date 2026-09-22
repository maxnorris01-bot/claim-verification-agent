"""Shared fixtures: a scripted fake Anthropic client so tests never touch the network."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app import llm, tracing


@pytest.fixture(autouse=True)
def _no_tracing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Belt and suspenders: the env var covers Config.from_env(), and redirecting TRACE_PATH
    # covers tests that construct Config() directly (its tracing_disabled default is False) -
    # either path alone left tests writing fake spans into the real runs/trace.jsonl.
    monkeypatch.setenv("APP_TRACING_DISABLED", "1")
    monkeypatch.setattr(tracing, "TRACE_PATH", tmp_path / "trace.jsonl")


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
        _request_id="req_test",
    )


class FakeClient:
    """Returns scripted responses in order and records every request."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self._responses.pop(0)


@pytest.fixture
def install_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(responses: list[SimpleNamespace]) -> FakeClient:
        client = FakeClient(responses)
        monkeypatch.setattr(llm, "get_client", lambda: client)
        return client

    return install
