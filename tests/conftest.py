import json
import pathlib

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path: pathlib.Path):
    questions_file = tmp_path / "questions.json"
    questions_file.write_text(
        json.dumps(
            [
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
                },
            ]
        ),
        encoding="utf-8",
    )

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
