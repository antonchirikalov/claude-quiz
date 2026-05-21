import pytest

from app.errors import SchemaError
from app.schema import Question, validate_question

VALID = {
    "id": "valid-q-001",
    "domain": "Model Capabilities",
    "stem": "A valid question stem?",
    "choices": {"A": "Option A", "B": "Option B"},
    "answer": "A",
    "explanation": "A is correct because it is option A.",
}


def test_valid_record_returns_question():
    q = validate_question(VALID)
    assert isinstance(q, Question)
    assert q.id == "valid-q-001"
    assert q.answer == "A"


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
