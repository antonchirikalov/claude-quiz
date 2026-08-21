# Claude Certified Architect — Practice Quiz

A Flask + Jinja2 web app for studying the **Claude Certified Architect (CCA-F)** exam.

## Features

- Pick an exam and a question set, then work through it one question at a time
- Question-number navigator on every question and answer page: jump straight to any
  number, step back and forth by position, and see at a glance which questions are
  still open, correct or wrong. Scenario-grouped banks get one row per scenario
- Every answer is followed by a breakdown: why the correct option is correct, why each
  distractor fails, and the task statement it maps to
- Explanations can carry citations — a link to the documentation page plus the verbatim
  sentence the answer rests on, so a claim can be checked rather than trusted
- Scenario text opens on the first question of its block and stays collapsed on the
  rest, so the same paragraph isn't re-read fifteen times
- Single-answer and multiple-response questions (`Select TWO` / `Select THREE`), the
  latter scored all-or-nothing. Note: the observed CCA-F is single-answer throughout —
  multiple-response support exists because one line of the exam guide mentions it
- Results page with a per-domain score table, the way the real exam report reads

## Exam Domains

| # | Domain | Weight |
|---|--------|--------|
| 1 | Agentic Architecture & Orchestration | 27% |
| 2 | Tool Design & MCP Integration | 18% |
| 3 | Claude Code & Developer Workflow | 20% |
| 4 | Prompt Engineering & Structured Output | 20% |
| 5 | Context Management & Reliability | 15% |

The exam presents 4 scenarios of 15 questions each, drawn from an official set of 6.

## Quick Start

```bash
pip install -r requirements.txt
flask --app app run --debug
```

Open: http://localhost:5000

## How the Questions Are Written

The banks are not generated in one pass and shipped. Each question goes through the
same construction and verification steps, and the rules below exist because earlier
drafts broke them.

### Source hierarchy

On conflict, the higher source wins:

1. **The official exam guide** — domains, weights, 30 task statements, out-of-scope
   list. This decides *what* is asked.
2. **Current documentation** (`code.claude.com`, `platform.claude.com`). This decides
   *which answer is correct*.
3. **The 12 official sample questions** — the source of form: stem length, question
   type, how distractors are built.
4. **Candidate reports** from forums and repos — what actually turns up, and where
   people lose points.

### Shape

Questions come in blocks of 15, each block one scenario describing a production system.
The domain mix per block is chosen so that the finished bank matches the blueprint
weights, rather than covering whatever was easiest to write.

### Stem rules

- Describes a production situation; the operative question is the **last sentence**, as
  it is in every official sample
- Asks what to **do**, never what a source **says**. A stem whose correct answer is
  "the sources disagree" cannot appear on the real exam
- Carries eliminating facts, so the question is solved by reasoning rather than by
  recognising a keyword

### Distractor types

Four kinds, mixed deliberately:

- **Valid, but not the first step** — something the documentation genuinely recommends,
  which is nonetheless the wrong response to the stated symptom
- **Invented configuration** — a field or setting that sounds real and does not exist
- **A real detail in the wrong place** — a genuine mechanism applied where it does not
  govern
- **Inverted mapping** — two correct concepts swapped

### Verification

The explanation is written **after** loading the documentation, never before. Every
citation carries the verbatim sentence it rests on. Where a task statement has no
documentation page, the explanation says so rather than citing a near-miss page.

Divergences between the exam guide and the current product are flagged in the
explanation and are **never** the subject of a question — the item would have no
defensible answer. Prefill no longer being supported, and MCP tool schemas now being
deferred rather than loaded upfront, are the two that matter most.

### Anti-gaming checks

A bank that can be solved without reading it is worthless. Measured per block:

- **"the longest answer is correct"** — rewritten down toward the 25% a coin flip
  gives, and no option may exceed every other by a visible margin
- **answer positions** spread across A–D
- the importer cross-checks the answer key against the scoring tables, so a
  transcription slip fails the build rather than reaching the app

## Question Sets

The banks ship with the app — clone, run, and there are questions to answer. Authored
Markdown sources live in `banks/`, and the JSON the app serves lives in
`exams/<exam>/<name>.json`:

| Set | Questions | What it is |
|-----|-----------|------------|
| `exams/cca-f/bank-v2.json` | 75 | The main CCA-F bank: 5 scenario blocks of 15, built to the blueprint's domain weights |
| `exams/cca-f/sourced-set-12.json` | 12 | A short set where every item carries documentation citations |
| `exams/cca-p/full-bank-63.json` | 63 | CCA-P, from the earlier generator — it has **not** been through the verification pass below |

The items are original: written from the public exam guide's task statements, the
public documentation and community reports. They are not reproductions of exam
questions. The study guides those task statements come from are third-party material
and are deliberately not included here.

### Importing a Markdown bank

Banks are authored in a three-part Markdown layout — part 1 questions, part 2 answer
key and explanations, part 3 scoring tables — and converted with
`scripts/import_bank.py`:

```bash
python scripts/import_bank.py banks/CCA-F_bank_v2.md --out exams/cca-f/bank-v2.json
```

It joins stems and choices (part 1) with answers and explanations (part 2), takes the
domain mapping from part 3, and validates two things a bank gets wrong on its own:

- the part-2 key against the one-line answer tables in part 3
- `(Select TWO.)` / `(Select THREE.)` markers against the number of answers in the key

Add `--check` to parse and report without writing anything. It exits non-zero if
anything is off, which makes it usable as a pre-commit check on the bank.

### Exam simulations

The real exam draws 4 scenarios of 6, so a run through every scenario is not what exam
day looks like. `scripts/build_simulations.py` slices an imported bank into
4-scenario sets:

```bash
python scripts/build_simulations.py exams/cca-f/bank-v2.json --out-dir exams/cca-f
```

The combinations are fixed rather than random, and chosen so each one covers all five
scored domains — an arbitrary 4-of-6 draw can miss one entirely.

### Question record format

```json
{
  "id": "cca-f-01",
  "domain": "1 · Agentic Architecture & Orchestration",
  "stem": "How should loop termination be controlled?",
  "choices": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "answer": "A",
  "explanation": "Why A is right.\n- B: why B is wrong.",
  "scenario": "You are building...",
  "scenario_title": "Scenario 1 · Support Agent",
  "reference": "TS 1.1",
  "sources": [
    {
      "url": "https://code.claude.com/docs/en/sub-agents",
      "quote": "Each subagent starts with a fresh, isolated context window.",
      "retrieved_at": "2026-08-20"
    }
  ]
}
```

`answer` holds a single key; multiple-response questions use `answers: ["A", "B"]`
instead. `scenario`, `scenario_title`, `reference` and `sources` are optional. Stems,
choices, scenarios and explanations are Markdown — `inline code`, **bold** and `- `
bullet lists render.

## Generating New Questions

Two paths exist for drafting additional questions. Both produce drafts that still need
the verification pass described above — neither replaces it.

### Option 1 — Prompt file in VS Code Agent Chat

Requirements: **GitHub Copilot** extension + **Tavily MCP** connected.

1. Open VS Code → Agent Chat (`Ctrl+Alt+I`)
2. Click **Attach** → **Prompt...** → select `scripts/generate_questions.prompt.md`
3. The agent searches the web via Tavily and appends new questions to the target JSON

The prompt runs searches for all domains in parallel. Questions per domain is
controlled by the `count` variable (default: 10).

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

## Tests

```bash
PYTHONPATH=. pytest -q
ruff check .
```

## Project Structure

```
app/
  __init__.py       — Flask application factory, Jinja filters
  quiz.py           — question loading, navigation groups, scoring, session state
  routes.py         — routes (/, /select, /question, /answer, /results)
  schema.py         — question schema and validation, including citations
  markdown.py       — the small Markdown subset used in question text
  errors.py         — typed exceptions
banks/
  *.md              — authored Markdown banks (the source the importer reads)
exams/
  <exam>/<set>.json — question sets the app serves
scripts/
  import_bank.py                 — Markdown bank → exam JSON converter
  build_simulations.py           — bank JSON → 4-scenario exam simulations
  generate_questions.py          — CLI generator (Anthropic API)
  generate_questions.prompt.md   — agent prompt for VS Code
templates/
  _nav.html         — question-number navigator
  ...               — Jinja2 templates
tests/              — pytest test suite
```
