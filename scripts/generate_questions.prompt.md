---
mode: agent
description: Search the web for Claude Certified Architect exam questions across ALL domains and save to data/questions.json
tools:
  - tavily_search
  - tavily_extract
  - read_file
  - replace_string_in_file
variables:
  - name: count
    description: "Questions per domain"
    default: "10"
---

You are an expert exam question author for the **Claude Certified Architect** certification.

Target domains (process ALL of them):
- Safety & Alignment
- Model Capabilities
- Prompt Engineering
- Tool Use / Agentic
- API & Deployment

## Step 1 — Parallel web search for ALL domains

Fire ALL of these `tavily_search` calls **simultaneously** (`search_depth: advanced`, `max_results: 7`):

**Cross-domain discovery (run once):**
- `"Claude Certified Architect" exam experience reddit forum questions answers`
- `site:reddit.com "anthropic certification" exam questions study tips`
- `"Claude certification" passed exam experience blog medium linkedin`
- `"anthropic exam" practice questions dump experience 2024 2025`

**Per-domain community queries (all in parallel):**
- `"Claude certification" exam "Safety & Alignment" constitutional AI questions reddit`
- `"Claude certification" exam "Model Capabilities" context window questions reddit`
- `"Claude certification" exam "Prompt Engineering" chain-of-thought questions reddit`
- `"Claude certification" exam "Tool Use" MCP agentic questions reddit`
- `"Claude certification" exam "API" deployment questions reddit`

**Per-domain docs queries (all in parallel):**
- `Claude safety alignment constitutional AI responsible scaling Anthropic documentation`
- `Claude model capabilities context window Opus Sonnet Haiku Anthropic docs`
- `Claude prompt engineering best practices XML tags system prompt Anthropic`
- `Claude tool use function calling MCP agentic Anthropic documentation`
- `Claude API streaming batch prompt caching messages Anthropic documentation`

Then collect all URLs from results and call `tavily_extract` on up to 15 Reddit/Medium/blog URLs (skip docs.anthropic.com) to get full thread content.

## Step 2 — Read questions.json

Read `data/questions.json` and collect all existing `id` values. Never generate duplicates.

## Step 3 — Generate questions for ALL domains

For **each** of the 5 domains generate exactly **${count}** questions using the gathered context.

Rules:
- Prioritise topics that appeared in community discussions — those are most likely on the real exam
- Test deep practical understanding, not trivia
- `id` must be lowercase-kebab, unique across the whole file

Schema for each question object:
```
{
  "id": "lowercase-kebab-slug",
  "domain": "<exact domain name>",
  "stem": "Question text (1-4 sentences)",
  "choices": { "A": "...", "B": "...", "C": "...", "D": "..." },
  "answer": "A|B|C|D",
  "explanation": "3-6 sentences citing specifics from reference material"
}
```

## Step 4 — Save to data/questions.json

Read `data/questions.json` one more time (latest state), append ALL new questions, write the full updated array back.

Print a final summary: questions added per domain and new total.
