from dataclasses import dataclass

from app.errors import SchemaError

_REQUIRED = ("id", "domain", "stem", "choices", "answer", "explanation")


@dataclass
class Question:
    id: str
    domain: str
    stem: str
    choices: dict[str, str]
    answer: str
    explanation: str


def validate_question(data: dict) -> Question:
    """Parse and validate a raw dict into a Question; raise SchemaError on failure."""
    for field in _REQUIRED:
        if field not in data:
            raise SchemaError(f"Question missing required field: '{field}'")

    qid: str = data["id"]
    if not isinstance(qid, str) or not qid:
        raise SchemaError("Question 'id' must be a non-empty string")
    if qid != qid.lower() or " " in qid:
        raise SchemaError(f"Question 'id' must be lowercase with no spaces, got: '{qid}'")

    choices: dict = data["choices"]
    if not isinstance(choices, dict) or len(choices) < 2 or len(choices) > 6:
        raise SchemaError(
            f"Question '{qid}': 'choices' must be a dict with 2–6 entries, "
            f"got {len(choices) if isinstance(choices, dict) else type(choices).__name__}"
        )

    answer: str = data["answer"]
    if answer not in choices:
        raise SchemaError(
            f"Question '{qid}': 'answer' key '{answer}' not found in choices"
        )

    explanation: str = data["explanation"]
    if not isinstance(explanation, str) or not explanation.strip():
        raise SchemaError(f"Question '{qid}': 'explanation' must be a non-empty string")

    return Question(
        id=qid,
        domain=data["domain"],
        stem=data["stem"],
        choices=choices,
        answer=answer,
        explanation=explanation,
    )
