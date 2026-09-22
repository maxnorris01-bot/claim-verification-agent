"""Shared fixtures: a scripted fake Anthropic client so tests never touch the network.

The response-construction primitives (`text_block`, `search_blocks`, `response`) and
`ScriptedClient` live in `app.mock_llm` now, promoted out of this file so the same shapes back
both the unit tests here and `APP_LLM_MODE=mock`'s production client. This file just re-exports
them for the existing tests and wires `install_client` to `app.llm.get_client`'s new
mode-keyed signature.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app import llm, tracing
from app.mock_llm import ScriptedClient, response, search_blocks, text_block

__all__ = ["response", "search_blocks", "text_block", "ScriptedClient", "install_client"]


@pytest.fixture(autouse=True)
def _no_tracing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Belt and suspenders: the env var covers Config.from_env(), and redirecting TRACE_PATH
    # covers tests that construct Config() directly (its tracing_disabled default is False) -
    # either path alone left tests writing fake spans into the real runs/trace.jsonl.
    monkeypatch.setenv("APP_TRACING_DISABLED", "1")
    monkeypatch.setattr(tracing, "TRACE_PATH", tmp_path / "trace.jsonl")


@pytest.fixture
def install_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(responses: list[Any]) -> ScriptedClient:
        client = ScriptedClient(responses)
        monkeypatch.setattr(llm, "get_client", lambda mode: client)
        return client

    return install
