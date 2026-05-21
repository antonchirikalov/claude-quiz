# Claude Certified Architect — Practice Quiz

A Flask + Jinja2 web app for studying the **Claude Certified Architect (CCA-F)** exam.

## Features

- Questions across all 5 exam domains with explanations for every answer
- Random question selection on each quiz run
- Results page with a full breakdown of correct and incorrect answers

## Exam Domains

| Domain | Weight |
|--------|--------|
| Agentic Architecture & Claude Code | 27% |
| Claude Code Configuration | 20% |
| Prompt Engineering | 20% |
| Tools & MCP | 18% |
| Context Management | 15% |

## Quick Start

```bash
pip install -r requirements.txt
flask --app app run --debug
```

Open: http://localhost:5000

## Generating Questions

The question bank lives in `data/questions.json`. There are two ways to add more questions.

### Option 1 — Prompt file in VS Code Agent Chat (recommended)

Requirements: **GitHub Copilot** extension + **Tavily MCP** connected.

1. Open VS Code → Agent Chat (`Ctrl+Alt+I`)
2. Click **Attach** → **Prompt...** → select `scripts/generate_questions.prompt.md`
3. The agent searches the web via Tavily and appends new questions to `data/questions.json`

The prompt runs searches for all domains in parallel. The number of questions per domain is controlled by the `count` variable (default: 10).

#### Connecting Tavily MCP

Add the following to your VS Code `settings.json`:

```json
"mcp": {
  "servers": {
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp"],
      "env": {
        "TAVILY_API_KEY": "tvly-your-key-here"
      }
    }
  }
}
```

Get a free API key at [app.tavily.com](https://app.tavily.com).

### Option 2 — CLI script with Anthropic API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/generate_questions.py
```

Requires a valid `ANTHROPIC_API_KEY`.

## Tests

```bash
PYTHONPATH=. pytest -q
```

## Project Structure

```
app/
  __init__.py       — Flask application factory
  quiz.py           — question loading and selection logic
  routes.py         — routes (/, /question, /answer, /results)
  schema.py         — Pydantic question schema
  errors.py         — typed exceptions
data/
  questions.json    — question bank (source of truth)
scripts/
  generate_questions.py          — CLI generator (Anthropic API)
  generate_questions.prompt.md   — agent prompt for VS Code
templates/          — Jinja2 templates
tests/              — pytest test suite
```
