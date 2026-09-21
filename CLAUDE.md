# CLAUDE.md

## Commands
- Install: `make install`
- Lint + format check: `make lint`
- Tests: `make test` (single test: `uv run pytest tests/test_x.py::test_name`)
- Fast evals: `make eval-fast` (run after ANY change to prompts or agent logic)

## Rules
- IMPORTANT: Prompts live in `prompts/` as versioned files. Never inline prompt strings in code.
- Any change to a prompt or agent logic must be followed by `make eval-fast`. Show the output before calling the work done.
- Eval cases and thresholds (`evals/`) change only through explicit, separate commits. Never edit them to make a failing eval pass.
- Never commit secrets. Config comes from environment variables; `.env.example` lists what's needed.
- Every agent loop must have a step cap and a cost cap, both set in `src/app/config.py`.
- Log every LLM/tool call through `src/app/tracing.py` so runs are inspectable.
- Record non-obvious design decisions as a short ADR in `docs/adr/`.

## Definition of done
Lint clean, tests pass, `make eval-fast` meets `evals/thresholds.yaml`, README results table updated if numbers changed.

## Conventions
- Conventional Commits (`feat:`, `fix:`, `eval:`, `docs:`, `chore:`).
- One logical change per commit; small PRs.
