import json
import pathlib
from typing import Any

from app.errors import QuizError, SchemaError
from app.schema import Question, validate_question

_DATA_PATH = pathlib.Path(__file__).parent.parent / "data" / "questions.json"
_EXAMS_DIR = pathlib.Path(__file__).parent.parent / "exams"


def list_exams() -> list[str]:
    """Return sorted list of exam folder names under exams/."""
    if not _EXAMS_DIR.exists():
        return []
    return sorted(p.name for p in _EXAMS_DIR.iterdir() if p.is_dir())


def list_question_files(exam: str) -> list[str]:
    """Return sorted list of .json filenames in an exam folder."""
    exam_dir = _EXAMS_DIR / exam
    if not exam_dir.exists():
        return []
    return sorted(p.name for p in exam_dir.glob("*.json"))


def questions_path(exam: str, filename: str) -> pathlib.Path:
    """Return the absolute path for a given exam/filename pair."""
    return _EXAMS_DIR / exam / filename


def load_questions(path: pathlib.Path = _DATA_PATH) -> list[Question]:
    """Load and validate all questions from the JSON data file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"questions.json is not valid JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise SchemaError("questions.json must contain a JSON array at the top level")
    questions: list[Question] = []
    for i, item in enumerate(raw):
        try:
            questions.append(validate_question(item))
        except SchemaError as exc:
            raise SchemaError(f"Question at index {i} is invalid: {exc}") from exc
    return questions


def get_question(qid: str, questions: list[Question]) -> Question:
    """Return the Question with the given id; raise QuizError if not found."""
    for q in questions:
        if q.id == qid:
            return q
    raise QuizError(f"Unknown question id: '{qid}'")


def nav_groups(
    questions: list[Question], answers: dict[str, list[str]], current_id: str | None = None
) -> list[dict]:
    """Build the question-number navigator, one group per scenario block.

    Banks grouped by domain carry no scenario title, so they collapse into a
    single unlabelled group. Each item reports its answered state so the grid
    can show at a glance what is still open.
    """
    groups: list[dict] = []
    for number, q in enumerate(questions, start=1):
        label = q.scenario_title
        if not groups or groups[-1]["label"] != label:
            # "Scenario 3 · Multi-Agent Research System" → "Scenario 3"
            short = label.split("·", 1)[0].strip() if label else None
            # Key is "cells", not "items": in Jinja `group.items` resolves to the dict
            # method, not the key.
            groups.append({"label": label, "short_label": short, "cells": []})

        chosen = answers.get(q.id)
        if chosen is None:
            state = "unanswered"
        else:
            state = "correct" if q.is_correct(chosen) else "wrong"
        groups[-1]["cells"].append(
            {
                "number": number,
                "id": q.id,
                "state": state,
                "current": q.id == current_id,
                "multi": q.is_multi,
            }
        )
    return groups


def neighbours(
    questions: list[Question], question: Question
) -> tuple[Question | None, Question | None]:
    """Return the questions before and after this one in bank order."""
    index = questions.index(question)
    previous = questions[index - 1] if index > 0 else None
    following = questions[index + 1] if index + 1 < len(questions) else None
    return previous, following


def domain_counts(questions: list[Question]) -> list[tuple[str, int]]:
    """Return (domain, question count) pairs, sorted by domain name."""
    counts: dict[str, int] = {}
    for q in questions:
        counts[q.domain] = counts.get(q.domain, 0) + 1
    return sorted(counts.items())


def get_answers(session: Any) -> dict[str, list[str]]:
    """Return the session's answer map, normalising legacy single-string values."""
    raw: dict[str, Any] = session.get("answers", {}) or {}
    return {qid: ([v] if isinstance(v, str) else list(v)) for qid, v in raw.items()}


def record_answer(session: Any, qid: str, choice: str | list[str]) -> None:
    """Store the user's selected choice key(s) for a question in the Flask session."""
    chosen = [choice] if isinstance(choice, str) else list(choice)
    answers = get_answers(session)
    answers[qid] = chosen
    session["answers"] = answers


def score_session(session: Any, questions: list[Question]) -> dict:
    """Compute score from session answers.

    Returns {correct, total, pct, breakdown, by_domain}. Multiple-response
    questions count as correct only on an exact match — no partial credit,
    matching how the real exam scores them.
    """
    answers = get_answers(session)
    breakdown = []
    by_domain: dict[str, dict[str, int]] = {}
    correct = 0
    for q in questions:
        chosen = answers.get(q.id)
        is_correct = q.is_correct(chosen)
        if is_correct:
            correct += 1
        breakdown.append(
            {
                "question": q,
                "chosen": chosen or [],
                "correct": is_correct,
            }
        )
        stats = by_domain.setdefault(q.domain, {"correct": 0, "total": 0})
        stats["total"] += 1
        stats["correct"] += 1 if is_correct else 0

    for stats in by_domain.values():
        stats["pct"] = round(stats["correct"] / stats["total"] * 100) if stats["total"] else 0

    total = len(questions)
    pct = round(correct / total * 100) if total else 0
    return {
        "correct": correct,
        "total": total,
        "pct": pct,
        "breakdown": breakdown,
        "by_domain": dict(sorted(by_domain.items())),
    }


def next_unanswered(session: Any, questions: list[Question]) -> Question | None:
    """Return the first question the user hasn't answered yet, or None."""
    answers = get_answers(session)
    for q in questions:
        if q.id not in answers:
            return q
    return None
