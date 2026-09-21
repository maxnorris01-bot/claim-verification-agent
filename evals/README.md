# Evals

## Tiers

| Tier | Runs | Cases |
|------|------|-------|
| fast | every PR | first 15 |
| standard | merges to main | first 50 |
| nightly | scheduled | all |

Case order matters: put the highest-signal, most representative cases first.

## Adding cases

Append to `cases/*.jsonl`. Each line: `id`, `category`, `input`, and either `expected_contains` (deterministic) or a `rubric` name (LLM-as-judge). When you find a real failure in the wild, add it here as a regression case.

## Rules

- Case and threshold changes go in their own commits, never bundled with the change they'd excuse.
- A judge is trusted only after it agrees with a human-labeled gold set (`gold/`). Record its agreement rate in the README results table.
- Reports in `reports/` include prompt versions so results are attributable.
- Thresholds in `thresholds.yaml` are starting points; tune per project.
