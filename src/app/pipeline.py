"""PLACEHOLDER pipeline. Replace with the real system under test.

The eval harness calls `run(text)`. Keep that signature stable so evals keep working.
"""

from __future__ import annotations

from app.prompts import load_prompt
from app.tracing import span


def run(text: str) -> str:
    prompt = load_prompt("example")
    with span("pipeline.run", prompt_version=prompt.version, input_chars=len(text)) as rec:
        # TODO: call the model here using `prompt.text`. For now, echo the input.
        output = text
        rec["output_chars"] = len(output)
    return output
