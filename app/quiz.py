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


def record_answer(session: Any, qid: str, choice: str) -> None:
    """Store the user's choice for a question in the Flask session."""
    answers: dict[str, str] = session.get("answers", {})
    answers[qid] = choice
    session["answers"] = answers


def score_session(session: Any, questions: list[Question]) -> dict:
    """Compute score from session answers. Returns {correct, total, pct, breakdown}."""
    answers: dict[str, str] = session.get("answers", {})
    breakdown = []
    correct = 0
    for q in questions:
        chosen = answers.get(q.id)
        is_correct = chosen == q.answer
        if is_correct:
            correct += 1
        breakdown.append(
            {
                "question": q,
                "chosen": chosen,
                "correct": is_correct,
            }
        )
    total = len(questions)
    pct = round(correct / total * 100) if total else 0
    return {"correct": correct, "total": total, "pct": pct, "breakdown": breakdown}


def next_unanswered(session: Any, questions: list[Question]) -> Question | None:
    """Return the first question the user hasn't answered yet, or None."""
    answers: dict[str, str] = session.get("answers", {})
    for q in questions:
        if q.id not in answers:
            return q
    return None
