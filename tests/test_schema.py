import pytest

from app.errors import SchemaError
from app.schema import Question, validate_question

VALID = {
    "id": "valid-q-001",
    "domain": "Model Capabilities",
    "stem": "A valid question stem?",
    "choices": {"A": "Option A", "B": "Option B", "C": "Option C"},
    "answer": "A",
    "explanation": "A is correct because it is option A.",
}

VALID_MULTI = {
    **VALID,
    "id": "valid-q-002",
    "choices": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
    "answers": ["B", "D"],
}
del VALID_MULTI["answer"]


def test_valid_record_returns_question():
    q = validate_question(VALID)
    assert isinstance(q, Question)
    assert q.id == "valid-q-001"
    assert q.answers == ["A"]
    assert q.answer == "A"
    assert q.is_multi is False


def test_missing_required_field_raises():
    for field in ("id", "domain", "stem", "choices", "answer", "explanation"):
        data = {k: v for k, v in VALID.items() if k != field}
        with pytest.raises(SchemaError, match=field):
            validate_question(data)


def test_id_with_uppercase_raises():
    data = {**VALID, "id": "Invalid-ID"}
    with pytest.raises(SchemaError, match="lowercase"):
        validate_question(data)


def test_id_with_space_raises():
    data = {**VALID, "id": "bad id"}
    with pytest.raises(SchemaError, match="no spaces"):
        validate_question(data)


def test_too_few_choices_raises():
    data = {**VALID, "choices": {"A": "Only one"}}
    with pytest.raises(SchemaError, match="2"):
        validate_question(data)


def test_too_many_choices_raises():
    data = {**VALID, "choices": {k: k for k in "ABCDEFG"}}
    with pytest.raises(SchemaError):
        validate_question(data)


def test_answer_not_in_choices_raises():
    data = {**VALID, "answer": "Z"}
    with pytest.raises(SchemaError, match="not found in choices"):
        validate_question(data)


def test_empty_explanation_raises():
    data = {**VALID, "explanation": "   "}
    with pytest.raises(SchemaError, match="explanation"):
        validate_question(data)


# --- multiple response ---

def test_valid_multi_record():
    q = validate_question(VALID_MULTI)
    assert q.answers == ["B", "D"]
    assert q.answer == "B, D"
    assert q.is_multi is True


def test_multi_answers_are_sorted():
    q = validate_question({**VALID_MULTI, "answers": ["D", "B"]})
    assert q.answers == ["B", "D"]


def test_both_answer_and_answers_raises():
    data = {**VALID_MULTI, "answer": "A"}
    with pytest.raises(SchemaError, match="not both"):
        validate_question(data)


def test_duplicate_answers_raise():
    data = {**VALID_MULTI, "answers": ["B", "B"]}
    with pytest.raises(SchemaError, match="duplicate"):
        validate_question(data)


def test_answers_covering_every_choice_raises():
    data = {**VALID_MULTI, "answers": ["A", "B", "C", "D"]}
    with pytest.raises(SchemaError, match="every choice"):
        validate_question(data)


def test_empty_answers_list_raises():
    data = {**VALID_MULTI, "answers": []}
    with pytest.raises(SchemaError, match="answer"):
        validate_question(data)


def test_multi_answer_key_not_in_choices_raises():
    data = {**VALID_MULTI, "answers": ["B", "Z"]}
    with pytest.raises(SchemaError, match="not found in choices"):
        validate_question(data)


# --- optional fields ---

def test_scenario_and_reference_are_kept():
    q = validate_question(
        {
            **VALID,
            "scenario": "Some setup.",
            "scenario_title": "Scenario 1 · Setup",
            "reference": "TS 1.1",
        }
    )
    assert q.scenario == "Some setup."
    assert q.scenario_title == "Scenario 1 · Setup"
    assert q.reference == "TS 1.1"


def test_scenario_title_defaults_to_none():
    q = validate_question({**VALID, "scenario": "Some setup."})
    assert q.scenario_title is None


def test_blank_scenario_becomes_none():
    q = validate_question({**VALID, "scenario": ""})
    assert q.scenario is None


def test_non_string_scenario_raises():
    with pytest.raises(SchemaError, match="scenario"):
        validate_question({**VALID, "scenario": 42})


# --- is_correct ---

def test_is_correct_exact_match_only():
    q = validate_question(VALID_MULTI)
    assert q.is_correct(["B", "D"]) is True
    assert q.is_correct(["D", "B"]) is True
    assert q.is_correct(["B"]) is False
    assert q.is_correct(["B", "D", "A"]) is False
    assert q.is_correct([]) is False
    assert q.is_correct(None) is False


# --- sources ---

def test_sources_are_parsed():
    q = validate_question({
        **VALID,
        "sources": [{
            "url": "https://docs.claude.com/en/docs/x",
            "quote": "verbatim",
            "note": "why it matters",
            "retrieved_at": "2026-08-14",
        }],
    })
    assert len(q.sources) == 1
    assert q.sources[0].url == "https://docs.claude.com/en/docs/x"
    assert q.sources[0].quote == "verbatim"
    assert q.sources[0].note == "why it matters"


def test_sources_accept_legacy_field_names():
    q = validate_question({
        **VALID,
        "sources": [{
            "url": "https://docs.claude.com/en/docs/x",
            "anchor_value": "stop_reason",
            "supports": "the loop signal",
        }],
    })
    assert q.sources[0].quote == "stop_reason"
    assert q.sources[0].note == "the loop signal"


def test_sources_default_to_empty():
    assert validate_question(VALID).sources == []


def test_source_without_http_url_raises():
    with pytest.raises(SchemaError, match="http"):
        validate_question({**VALID, "sources": [{"url": "docs.claude.com/x"}]})


def test_sources_not_a_list_raises():
    with pytest.raises(SchemaError, match="list"):
        validate_question({**VALID, "sources": {"url": "https://x.dev"}})


# --- explanation split ---

def test_explanation_splits_into_lead_and_points():
    q = validate_question({
        **VALID,
        "explanation": "Lead sentence.\nSecond lead line.\n- B: wrong because.\n- C: also wrong.",
    })
    assert q.explanation_lead == "Lead sentence.\nSecond lead line."
    assert q.explanation_points == ["B: wrong because.", "C: also wrong."]


def test_explanation_without_bullets_has_no_points():
    q = validate_question({**VALID, "explanation": "Just the lead."})
    assert q.explanation_lead == "Just the lead."
    assert q.explanation_points == []
