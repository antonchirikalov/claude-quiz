import json
import pathlib

import pytest

from app.errors import QuizError, SchemaError
from app.quiz import (
    get_question,
    load_questions,
    next_unanswered,
    record_answer,
    score_session,
)
from app.schema import Question


def make_question(qid: str, answer: str = "A") -> Question:
    return Question(
        id=qid,
        domain="Test",
        stem="Stem?",
        choices={"A": "Yes", "B": "No"},
        answer=answer,
        explanation="Because A.",
    )


# --- load_questions ---

def test_load_questions_happy(tmp_path: pathlib.Path):
    data = [
        {
            "id": "q-001",
            "domain": "D",
            "stem": "S?",
            "choices": {"A": "a", "B": "b"},
            "answer": "A",
            "explanation": "E.",
        }
    ]
    p = tmp_path / "q.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    qs = load_questions(p)
    assert len(qs) == 1
    assert qs[0].id == "q-001"


def test_load_questions_invalid_json_raises(tmp_path: pathlib.Path):
    p = tmp_path / "q.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(SchemaError, match="not valid JSON"):
        load_questions(p)


def test_load_questions_not_array_raises(tmp_path: pathlib.Path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    with pytest.raises(SchemaError, match="array"):
        load_questions(p)


def test_load_questions_bad_record_raises(tmp_path: pathlib.Path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps([{"id": "BAD ID"}]), encoding="utf-8")
    with pytest.raises(SchemaError):
        load_questions(p)


# --- get_question ---

def test_get_question_found():
    qs = [make_question("q-001"), make_question("q-002")]
    q = get_question("q-002", qs)
    assert q.id == "q-002"


def test_get_question_not_found_raises():
    qs = [make_question("q-001")]
    with pytest.raises(QuizError, match="q-999"):
        get_question("q-999", qs)


# --- record_answer ---

def test_record_answer_stores_in_session():
    session: dict = {}
    record_answer(session, "q-001", "B")
    assert session["answers"]["q-001"] == "B"


def test_record_answer_overwrites():
    session: dict = {"answers": {"q-001": "A"}}
    record_answer(session, "q-001", "B")
    assert session["answers"]["q-001"] == "B"


# --- score_session ---

def test_score_all_correct():
    qs = [make_question("q-001", "A"), make_question("q-002", "B")]
    session = {"answers": {"q-001": "A", "q-002": "B"}}
    result = score_session(session, qs)
    assert result["correct"] == 2
    assert result["total"] == 2
    assert result["pct"] == 100


def test_score_all_wrong():
    qs = [make_question("q-001", "A"), make_question("q-002", "B")]
    session = {"answers": {"q-001": "B", "q-002": "A"}}
    result = score_session(session, qs)
    assert result["correct"] == 0
    assert result["pct"] == 0


def test_score_mixed():
    qs = [make_question("q-001", "A"), make_question("q-002", "B")]
    session = {"answers": {"q-001": "A", "q-002": "A"}}
    result = score_session(session, qs)
    assert result["correct"] == 1
    assert result["pct"] == 50


# --- next_unanswered ---

def test_next_unanswered_returns_first_unanswered():
    qs = [make_question("q-001"), make_question("q-002")]
    session = {"answers": {"q-001": "A"}}
    nxt = next_unanswered(session, qs)
    assert nxt is not None
    assert nxt.id == "q-002"


def test_next_unanswered_returns_none_when_all_done():
    qs = [make_question("q-001"), make_question("q-002")]
    session = {"answers": {"q-001": "A", "q-002": "B"}}
    assert next_unanswered(session, qs) is None


def test_next_unanswered_returns_first_when_empty_session():
    qs = [make_question("q-001"), make_question("q-002")]
    nxt = next_unanswered({}, qs)
    assert nxt is not None
    assert nxt.id == "q-001"
