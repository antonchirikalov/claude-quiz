import json
import pathlib

import pytest

from app.errors import QuizError, SchemaError
from app.quiz import (
    domain_counts,
    get_answers,
    get_question,
    load_questions,
    nav_groups,
    neighbours,
    next_unanswered,
    record_answer,
    score_session,
)
from app.schema import Question


def make_question(
    qid: str, answers: list[str] | None = None, domain: str = "Test"
) -> Question:
    return Question(
        id=qid,
        domain=domain,
        stem="Stem?",
        choices={"A": "Yes", "B": "No", "C": "Maybe"},
        answers=answers or ["A"],
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


# --- record_answer / get_answers ---

def test_record_answer_stores_list():
    session: dict = {}
    record_answer(session, "q-001", "B")
    assert session["answers"]["q-001"] == ["B"]


def test_record_answer_stores_multiple():
    session: dict = {}
    record_answer(session, "q-001", ["A", "C"])
    assert session["answers"]["q-001"] == ["A", "C"]


def test_record_answer_overwrites():
    session: dict = {"answers": {"q-001": ["A"]}}
    record_answer(session, "q-001", "B")
    assert session["answers"]["q-001"] == ["B"]


def test_get_answers_normalises_legacy_strings():
    session = {"answers": {"q-001": "A", "q-002": ["B", "C"]}}
    assert get_answers(session) == {"q-001": ["A"], "q-002": ["B", "C"]}


def test_get_answers_on_empty_session():
    assert get_answers({}) == {}


# --- score_session ---

def test_score_all_correct():
    qs = [make_question("q-001", ["A"]), make_question("q-002", ["B"])]
    session = {"answers": {"q-001": ["A"], "q-002": ["B"]}}
    result = score_session(session, qs)
    assert result["correct"] == 2
    assert result["total"] == 2
    assert result["pct"] == 100


def test_score_all_wrong():
    qs = [make_question("q-001", ["A"]), make_question("q-002", ["B"])]
    session = {"answers": {"q-001": ["B"], "q-002": ["A"]}}
    result = score_session(session, qs)
    assert result["correct"] == 0
    assert result["pct"] == 0


def test_score_mixed():
    qs = [make_question("q-001", ["A"]), make_question("q-002", ["B"])]
    session = {"answers": {"q-001": ["A"], "q-002": ["A"]}}
    result = score_session(session, qs)
    assert result["correct"] == 1
    assert result["pct"] == 50


def test_score_multi_requires_exact_match():
    qs = [make_question("q-001", ["A", "B"])]
    assert score_session({"answers": {"q-001": ["A", "B"]}}, qs)["correct"] == 1
    assert score_session({"answers": {"q-001": ["B", "A"]}}, qs)["correct"] == 1
    assert score_session({"answers": {"q-001": ["A"]}}, qs)["correct"] == 0
    assert score_session({"answers": {"q-001": ["A", "B", "C"]}}, qs)["correct"] == 0


def test_score_unanswered_counts_as_wrong():
    qs = [make_question("q-001", ["A"]), make_question("q-002", ["B"])]
    result = score_session({"answers": {"q-001": ["A"]}}, qs)
    assert result["correct"] == 1
    assert result["breakdown"][1]["chosen"] == []
    assert result["breakdown"][1]["correct"] is False


def test_score_by_domain():
    qs = [
        make_question("q-001", ["A"], domain="D1"),
        make_question("q-002", ["A"], domain="D1"),
        make_question("q-003", ["A"], domain="D2"),
    ]
    session = {"answers": {"q-001": ["A"], "q-002": ["B"], "q-003": ["A"]}}
    by_domain = score_session(session, qs)["by_domain"]
    assert by_domain["D1"] == {"correct": 1, "total": 2, "pct": 50}
    assert by_domain["D2"] == {"correct": 1, "total": 1, "pct": 100}


def test_score_empty_question_list():
    result = score_session({"answers": {}}, [])
    assert result == {
        "correct": 0,
        "total": 0,
        "pct": 0,
        "breakdown": [],
        "by_domain": {},
    }


# --- domain_counts ---

def test_domain_counts_sorted():
    qs = [
        make_question("q-001", domain="Z"),
        make_question("q-002", domain="A"),
        make_question("q-003", domain="A"),
    ]
    assert domain_counts(qs) == [("A", 2), ("Z", 1)]


# --- next_unanswered ---

def test_next_unanswered_returns_first_unanswered():
    qs = [make_question("q-001"), make_question("q-002")]
    session = {"answers": {"q-001": ["A"]}}
    nxt = next_unanswered(session, qs)
    assert nxt is not None
    assert nxt.id == "q-002"


def test_next_unanswered_returns_none_when_all_done():
    qs = [make_question("q-001"), make_question("q-002")]
    session = {"answers": {"q-001": ["A"], "q-002": ["B"]}}
    assert next_unanswered(session, qs) is None


def test_next_unanswered_returns_first_when_empty_session():
    qs = [make_question("q-001"), make_question("q-002")]
    nxt = next_unanswered({}, qs)
    assert nxt is not None
    assert nxt.id == "q-001"


# --- nav_groups / neighbours ---

def test_nav_groups_flat_when_no_scenario_titles():
    qs = [make_question("q-001"), make_question("q-002")]
    groups = nav_groups(qs, {})
    assert len(groups) == 1
    assert groups[0]["short_label"] is None
    assert [c["number"] for c in groups[0]["cells"]] == [1, 2]


def test_nav_groups_splits_on_scenario_title():
    qs = [make_question("q-001"), make_question("q-002"), make_question("q-003")]
    qs[0].scenario_title = "Scenario 1 · Support Agent"
    qs[1].scenario_title = "Scenario 1 · Support Agent"
    qs[2].scenario_title = "Scenario 2 · Code Generation"
    groups = nav_groups(qs, {})
    assert [g["short_label"] for g in groups] == ["Scenario 1", "Scenario 2"]
    assert [c["number"] for c in groups[0]["cells"]] == [1, 2]
    assert [c["number"] for c in groups[1]["cells"]] == [3]


def test_nav_groups_reports_state_and_current():
    qs = [make_question("q-001", ["A"]), make_question("q-002", ["A"]), make_question("q-003")]
    answers = {"q-001": ["A"], "q-002": ["B"]}
    cells = nav_groups(qs, answers, current_id="q-003")[0]["cells"]
    assert [c["state"] for c in cells] == ["correct", "wrong", "unanswered"]
    assert [c["current"] for c in cells] == [False, False, True]


def test_nav_groups_numbers_are_positional_not_per_group():
    qs = [make_question(f"q-{i:03d}") for i in range(1, 5)]
    for q in qs[:2]:
        q.scenario_title = "Scenario 1 · A"
    for q in qs[2:]:
        q.scenario_title = "Scenario 2 · B"
    groups = nav_groups(qs, {})
    assert [c["number"] for c in groups[1]["cells"]] == [3, 4]


def test_neighbours_at_both_ends():
    qs = [make_question("q-001"), make_question("q-002"), make_question("q-003")]
    assert neighbours(qs, qs[0]) == (None, qs[1])
    assert neighbours(qs, qs[1]) == (qs[0], qs[2])
    assert neighbours(qs, qs[2]) == (qs[1], None)


def test_neighbours_single_question():
    qs = [make_question("q-001")]
    assert neighbours(qs, qs[0]) == (None, None)
