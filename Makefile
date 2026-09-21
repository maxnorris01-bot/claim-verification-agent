.PHONY: install lint format typecheck test eval-fast eval-standard eval-nightly

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

test:
	uv run pytest

eval-fast:
	uv run python -m evals.run --tier fast

eval-standard:
	uv run python -m evals.run --tier standard

eval-nightly:
	uv run python -m evals.run --tier nightly
