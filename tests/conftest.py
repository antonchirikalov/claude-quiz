import json
import pathlib

import pytest

from app import create_app

QUESTIONS = [
    {
        "id": "test-q-001",
        "domain": "Test Domain",
        "stem": "What is 2 + 2?",
        "choices": {"A": "3", "B": "4", "C": "5", "D": "6"},
        "answer": "B",
        "explanation": "Basic arithmetic: 2 + 2 = 4.",
    },
    {
        "id": "test-q-002",
        "domain": "Test Domain",
        "stem": "What is the capital of France?",
        "choices": {"A": "Berlin", "B": "Madrid", "C": "Paris", "D": "Rome"},
        "answer": "C",
        "explanation": "Paris is the capital and largest city of France.",
        "scenario": "You are quizzed on European capitals.",
        "scenario_title": "Scenario 1 · Geography",
        "reference": "TS 9.9",
        "sources": [
            {
                "url": "https://docs.claude.com/en/docs/test-page",
                "quote": "Paris is the capital of France.",
                "note": "Backs the capital claim.",
                "retrieved_at": "2026-08-14",
            }
        ],
    },
    {
        "id": "test-q-004",
        "domain": "Test Domain",
        "stem": "What is the capital of Spain?",
        "choices": {"A": "Berlin", "B": "Madrid", "C": "Paris", "D": "Rome"},
        "answer": "B",
        "explanation": "Madrid is the capital of Spain.",
        "scenario": "You are quizzed on European capitals.",
        "scenario_title": "Scenario 1 · Geography",
    },
    {
        "id": "test-q-003",
        "domain": "Multi Domain",
        "stem": "Which two numbers are even? (Select TWO.)",
        "choices": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "answers": ["B", "D"],
        "explanation": "2 and 4 are even.\n- A: odd.\n- C: odd.",
    },
]


@pytest.fixture()
def app(tmp_path: pathlib.Path):
    questions_file = tmp_path / "questions.json"
    questions_file.write_text(json.dumps(QUESTIONS), encoding="utf-8")

    from app import quiz as quiz_module

    flask_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "QUESTIONS": quiz_module.load_questions(questions_file),
        }
    )
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
