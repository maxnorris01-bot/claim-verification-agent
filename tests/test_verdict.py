import json

from app.verdict import Confidence, Evidence, Label, Tier, Verdict, invalid_input, not_implemented


def test_json_uses_plain_string_values() -> None:
    v = Verdict(
        tier=Tier.STATISTICAL_DATA,
        verdict=Label.NOT_SUPPORTED,
        confidence=Confidence.MEDIUM,
        evidence=[Evidence("a claim", "https://example.org", "a note")],
    )
    raw = v.to_json()
    # The eval harness matches expected_contains against exactly this shape.
    assert '"tier": "statistical_data"' in raw
    assert '"verdict": "not supported"' in raw
    assert json.loads(raw)["evidence"][0]["source_url"] == "https://example.org"


def test_invalid_input_has_null_tier_and_null_confidence() -> None:
    raw = invalid_input("empty").to_json()
    assert '"tier": null' in raw
    assert '"verdict": "invalid-input"' in raw
    assert '"confidence": null' in raw


def test_not_implemented_names_tier_and_has_no_confidence() -> None:
    v = not_implemented(Tier.HISTORICAL_FACTUAL)
    assert v.verdict is Label.NOT_IMPLEMENTED
    assert "historical_factual" in v.reasoning
    assert v.confidence is None
    assert '"confidence": null' in v.to_json()
