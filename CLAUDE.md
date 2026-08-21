# claude-quiz

A Flask + Jinja training application that emulates the Claude Certified Architect
practice exam. Question sets live in `exams/<exam>/<file>.json`; `app/schema.py::Question`
is the source of truth for their shape.

## Stack
- Python 3.11, Flask, Jinja2
- Tests: pytest, pytest-flask
- Lint/format: ruff
- Question generation: a CLI script that calls the Tavily MCP server
- Question import: `scripts/import_bank.py` converts a Markdown bank into exam JSON

## Commands
- Install:      pip install -r requirements.txt
- Run app:      flask --app app run --debug
- Run tests:    pytest -q
- Lint:         ruff check .
- Format:       ruff format .
- Import bank:  python scripts/import_bank.py <bank.md> --out exams/<exam>/<file>.json
- Check bank:   python scripts/import_bank.py <bank.md> --check
- Build sims:   python scripts/build_simulations.py <bank.json> --out-dir exams/<exam>

## Conventions
- 4-space indentation, type hints on every function signature
- Routes live in `app/routes.py`, business logic in `app/quiz.py`
- Question records must validate against `app/schema.py::Question`
- Single-answer records use `answer: "B"`; multiple-response use `answers: ["A", "B"]`
  and are scored all-or-nothing, like the real exam
- Question text, choices and explanations are Markdown; render them through the
  `md` / `md_inline` Jinja filters (`app/markdown.py`), never raw
- Never name a dict key `items` in data passed to a template — Jinja resolves
  `obj.items` to the dict method, not the key (see `nav_groups`, which uses `cells`)
- No bare excepts; raise typed errors from `app/errors.py`