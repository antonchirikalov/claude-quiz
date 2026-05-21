# claude-quiz

A Flask + Jinja training application that emulates the Claude Certified Architect
practice exam. Source of truth for the question schema is `data/questions.json`.

## Stack
- Python 3.11, Flask, Jinja2
- Tests: pytest, pytest-flask
- Lint/format: ruff
- Question generation: a CLI script that calls the Tavily MCP server

## Commands
- Install:    pip install -r requirements.txt
- Run app:    flask --app app run --debug
- Run tests:  pytest -q
- Lint:       ruff check .
- Format:     ruff format .

## Conventions
- 4-space indentation, type hints on every function signature
- Routes live in `app/routes.py`, business logic in `app/quiz.py`
- Question records must validate against `app/schema.py::Question`
- No bare excepts; raise typed errors from `app/errors.py`