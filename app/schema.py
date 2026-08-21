from __future__ import annotations

from dataclasses import dataclass, field

from app.errors import SchemaError

_REQUIRED = ("id", "domain", "stem", "choices", "explanation")


def _take_until_bullet(lines: list[str]):
    """Yield lines up to the first per-distractor bullet."""
    for line in lines:
        if line.strip().startswith(("- ", "* ")):
            return
        yield line


def _parse_sources(data: dict, qid: str) -> list[Source]:
    """Read the optional 'sources' list.

    Accepts both this app's field names and the ones the original generated bank
    used (anchor_value / supports), so older files keep loading.
    """
    raw = data.get("sources") or []
    if not isinstance(raw, list):
        raise SchemaError(f"Question '{qid}': 'sources' must be a list when present")

    sources: list[Source] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SchemaError(f"Question '{qid}': every source must be an object")
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise SchemaError(f"Question '{qid}': source needs an http(s) 'url', got {url!r}")
        sources.append(
            Source(
                url=url,
                quote=item.get("quote") or item.get("anchor_value"),
                note=item.get("note") or item.get("supports"),
                retrieved_at=item.get("retrieved_at"),
            )
        )
    return sources


@dataclass
class Source:
    """A citation backing an explanation — ideally official documentation."""

    url: str
    quote: str | None = None
    note: str | None = None
    retrieved_at: str | None = None


@dataclass
class Question:
    id: str
    domain: str
    stem: str
    choices: dict[str, str]
    answers: list[str]
    explanation: str
    scenario: str | None = None
    scenario_title: str | None = None
    reference: str | None = None
    tags: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)

    @property
    def explanation_lead(self) -> str:
        """The part of the explanation before the per-distractor bullets."""
        lines = self.explanation.splitlines()
        head = [ln for ln in _take_until_bullet(lines)]
        return "\n".join(head).strip()

    @property
    def explanation_points(self) -> list[str]:
        """The per-distractor bullets, without their leading marker."""
        points = []
        for line in self.explanation.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- ", "* ")):
                points.append(stripped[2:])
        return points

    @property
    def answer(self) -> str:
        """Correct answer key(s) as a display string: 'B' or 'A, B'."""
        return ", ".join(self.answers)

    @property
    def is_multi(self) -> bool:
        """True for multiple-response questions (Select TWO / Select THREE)."""
        return len(self.answers) > 1

    def is_correct(self, chosen: list[str] | None) -> bool:
        """True only on an exact match — partial selections score zero."""
        return bool(chosen) and set(chosen) == set(self.answers)


def _parse_answers(data: dict, qid: str, choices: dict) -> list[str]:
    """Read either 'answer' (single) or 'answers' (multiple-response)."""
    has_single = "answer" in data
    has_multi = "answers" in data
    if has_single and has_multi:
        raise SchemaError(f"Question '{qid}': define either 'answer' or 'answers', not both")
    if not has_single and not has_multi:
        raise SchemaError(f"Question '{qid}': missing required field: 'answer' or 'answers'")

    raw = data["answers"] if has_multi else [data["answer"]]
    if not isinstance(raw, list) or not raw:
        raise SchemaError(f"Question '{qid}': 'answers' must be a non-empty list of choice keys")
    if len(set(raw)) != len(raw):
        raise SchemaError(f"Question '{qid}': 'answers' contains duplicate keys: {raw}")
    for key in raw:
        if key not in choices:
            raise SchemaError(f"Question '{qid}': answer key '{key}' not found in choices")
    if len(raw) >= len(choices):
        raise SchemaError(f"Question '{qid}': every choice cannot be a correct answer")
    return sorted(raw)


def validate_question(data: dict) -> Question:
    """Parse and validate a raw dict into a Question; raise SchemaError on failure."""
    for name in _REQUIRED:
        if name not in data:
            raise SchemaError(f"Question missing required field: '{name}'")

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

    answers = _parse_answers(data, qid, choices)

    explanation: str = data["explanation"]
    if not isinstance(explanation, str) or not explanation.strip():
        raise SchemaError(f"Question '{qid}': 'explanation' must be a non-empty string")

    scenario = data.get("scenario")
    if scenario is not None and not isinstance(scenario, str):
        raise SchemaError(f"Question '{qid}': 'scenario' must be a string when present")

    return Question(
        id=qid,
        domain=data["domain"],
        stem=data["stem"],
        choices=choices,
        answers=answers,
        explanation=explanation,
        scenario=scenario or None,
        scenario_title=data.get("scenario_title") or None,
        reference=data.get("reference"),
        tags=list(data.get("tags", [])),
        sources=_parse_sources(data, qid),
    )
