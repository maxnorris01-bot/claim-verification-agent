"""Minimal structured tracing: one JSON line per LLM/tool call.

Deliberately dependency-free. When a project needs more, swap the body of
`span` for OpenTelemetry (GenAI semantic conventions) without changing callers.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import Config

TRACE_PATH = Path("runs/trace.jsonl")


@contextmanager
def span(
    name: str,
    *,
    config: Config | None = None,
    prompt_version: str | None = None,
    **attrs: Any,
) -> Iterator[dict[str, Any]]:
    """Record a span. Callers may add fields (tokens, cost, output) to the yielded dict."""
    cfg = config or Config.from_env()
    record: dict[str, Any] = {"name": name, "prompt_version": prompt_version, **attrs}
    start = time.perf_counter()
    try:
        yield record
        record["status"] = "ok"
    except Exception as exc:
        record["status"] = "error"
        record["error"] = repr(exc)
        raise
    finally:
        record["duration_s"] = round(time.perf_counter() - start, 4)
        if not cfg.tracing_disabled:
            TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with TRACE_PATH.open("a") as f:
                f.write(json.dumps(record, default=str) + "\n")
