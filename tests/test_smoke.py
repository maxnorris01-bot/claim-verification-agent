import pytest

from app.config import BudgetExceededError, Config, check_budget
from app.prompts import PROMPTS_DIR, load_prompt


@pytest.mark.parametrize("name", ["classifier", "statistical_data", "provenance_only"])
def test_prompt_loads_with_version(name: str) -> None:
    prompt = load_prompt(name)
    assert prompt.version == "1"
    assert prompt.text


def test_every_prompt_file_is_versioned() -> None:
    for path in PROMPTS_DIR.glob("*.md"):
        assert load_prompt(path.stem).version != "unversioned", path.name


def test_budget_caps_enforced() -> None:
    cfg = Config(max_steps=3, max_cost_usd=0.10)
    check_budget(cfg, steps=3, cost_usd=0.10)
    with pytest.raises(BudgetExceededError):
        check_budget(cfg, steps=4, cost_usd=0.0)
    with pytest.raises(BudgetExceededError):
        check_budget(cfg, steps=1, cost_usd=0.11)
