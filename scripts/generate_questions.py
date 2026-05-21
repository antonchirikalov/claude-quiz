#!/usr/bin/env python3
"""
Generate practice questions and append them to data/questions.json.

Workflow:
  1. The script starts the Tavily MCP server (via npx mcp-remote) as a subprocess.
  2. Depending on --strategy, it calls tavily_search (docs), or a two-phase
     discover-then-extract pipeline that trawls Reddit, forums, and community posts.
  3. The gathered content is passed to Claude as context.
  4. Claude generates N validated Question records appended to questions.json.

Usage:
    python scripts/generate_questions.py --domain "Model Capabilities" --count 5
    python scripts/generate_questions.py --domain "Safety & Alignment" --count 10 --strategy community
    python scripts/generate_questions.py --domain "API & Deployment" --count 8 --strategy both

Strategies:
    docs      — search official docs and technical blogs (original behaviour)
    community — search Reddit / forums / LinkedIn for real exam experiences, then
                extract full page content from discovered URLs
    both      — run both strategies and merge context (best quality, slower)

Environment variables:
    TAVILY_MCP_URL  — full Tavily MCP URL including API key
                      e.g. https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-xxx
                      Defaults to the value in .claude/settings.json if found.

    ANTHROPIC_API_KEY — Anthropic API key
"""
import argparse
import asyncio
import json
import os
import pathlib
import re
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_DATA_FILE = _REPO_ROOT / "data" / "questions.json"

# ---------------------------------------------------------------------------
# Docs-oriented queries (official docs, technical blogs, Anthropic content)
# ---------------------------------------------------------------------------
_DOMAIN_QUERIES: dict[str, list[str]] = {
    "Model Capabilities": [
        "Claude context window length tokens capabilities 2024 2025",
        "Claude model comparison Opus Sonnet Haiku benchmark",
        "Anthropic Claude multimodal vision capabilities",
    ],
    "Prompt Engineering": [
        "Claude prompt engineering best practices chain of thought 2024",
        "Anthropic system prompt techniques examples advanced",
        "Claude few-shot prompting XML tags formatting",
    ],
    "Safety & Alignment": [
        "Anthropic Constitutional AI training technique CAI RLHF",
        "Claude safety alignment responsible scaling policy RSP",
        "Anthropic harmlessness helpfulness honesty HHH",
    ],
    "Tool Use / Agentic": [
        "Claude tool use function calling model context protocol MCP",
        "Anthropic agentic AI multi-step tasks best practices",
        "Claude computer use operator user turn tool_result",
    ],
    "API & Deployment": [
        "Anthropic Claude API streaming messages batch prompt caching",
        "Claude API production deployment rate limits tokens",
        "Anthropic Messages API system prompt beta features",
    ],
}
_DEFAULT_QUERIES = ["Claude AI {domain} Anthropic documentation site:docs.anthropic.com"]

# ---------------------------------------------------------------------------
# Community-oriented queries — Reddit, forums, study groups, experience posts
# ---------------------------------------------------------------------------
_COMMUNITY_QUERIES: dict[str, list[str]] = {
    "Model Capabilities": [
        '"Claude certification" OR "Claude certified" exam questions model capabilities reddit',
        'site:reddit.com "anthropic certification" questions answers',
        '"Claude Certified Architect" exam experience model knowledge',
        'Anthropic certification exam "what topics" OR "what was tested" model',
    ],
    "Prompt Engineering": [
        '"Claude certification" exam "prompt engineering" questions reddit forum',
        'site:reddit.com "anthropic certification" prompt techniques exam',
        '"Claude Certified Architect" prompt engineering test questions',
        '"anthropic exam" prompting chain-of-thought questions experience',
    ],
    "Safety & Alignment": [
        '"Claude certification" OR "Claude certified" safety alignment exam reddit',
        'site:reddit.com "anthropic certification" constitutional AI exam questions',
        '"Claude Certified Architect" safety policy exam experience blog',
        '"anthropic exam" "responsible scaling" OR "constitutional AI" questions',
    ],
    "Tool Use / Agentic": [
        '"Claude certification" agentic tool use MCP exam questions reddit forum',
        'site:reddit.com "anthropic certification" "tool use" OR "function calling" exam',
        '"Claude Certified Architect" agentic AI exam experience',
        '"anthropic exam" MCP "model context protocol" test questions',
    ],
    "API & Deployment": [
        '"Claude certification" API deployment exam questions reddit',
        'site:reddit.com "anthropic certification" API exam tips',
        '"Claude Certified Architect" API deployment exam experience blog',
        '"anthropic exam" "prompt caching" OR "batch API" questions experience',
    ],
}
_DEFAULT_COMMUNITY_QUERIES = [
    '"Claude certification" OR "Claude Certified Architect" exam {domain} reddit OR forum',
    '"anthropic certification" exam experience {domain} questions answers',
]

# Generic cross-domain discovery queries to find community posts about the exam
_EXAM_DISCOVERY_QUERIES = [
    '"Claude Certified Architect" exam experience reddit',
    '"Claude certification" passed failed exam questions reddit forum',
    'site:reddit.com "anthropic" "certification" exam study questions',
    '"Claude certified" exam dump practice questions blog',
    '"anthropic certification" exam tips what to study reddit',
    '"Claude Certified Architect" linkedin OR medium exam review questions',
]

_SCHEMA_DESCRIPTION = """\
Return a JSON array of question objects. Each object must have exactly these fields:
- id: str  — lowercase kebab-case slug unique within the file, e.g. "context-window-002"
- domain: str — the exact domain label passed by the caller
- stem: str — question text (1–4 sentences); base it on the reference material provided
- choices: dict — exactly 4 keys A/B/C/D mapping to answer option strings
- answer: str — the correct key (A/B/C/D)
- explanation: str — 2–4 sentence explanation citing specifics from the reference material

Return ONLY the raw JSON array, no prose, no markdown fences.
"""


def _resolve_mcp_url() -> str:
    """Return the Tavily MCP URL from env or from .claude/settings.json."""
    if url := os.environ.get("TAVILY_MCP_URL"):
        return url

    # Try to read from Claude Code project settings
    for settings_path in [
        _REPO_ROOT / ".claude" / "settings.json",
        pathlib.Path.home() / ".claude" / "settings.json",
    ]:
        if not settings_path.exists():
            continue
        try:
            cfg = json.loads(settings_path.read_text(encoding="utf-8"))
            servers = cfg.get("mcpServers", {})
            tavily = servers.get("tavily-remote", {})
            args = tavily.get("args", [])
            # Last arg is the URL: ["-y", "mcp-remote", "<url>"]
            url = next((a for a in reversed(args) if a.startswith("http")), "")
            if url:
                return url
        except Exception:  # noqa: BLE001
            continue

    return ""


def _extract_urls(text: str) -> list[str]:
    """Pull http/https URLs out of a block of text."""
    return list(dict.fromkeys(re.findall(r'https?://[^\s"\'<>)]+', text)))


async def _run_mcp_pipeline(
    queries: list[str],
    mcp_url: str,
    *,
    extract_urls: bool = False,
    max_results: int = 5,
    snippet_limit: int = 3000,
) -> str:
    """Spawn the Tavily MCP server, search all queries, optionally extract URLs.

    When *extract_urls* is True the function collects every URL found in search
    results and calls tavily_extract on them to retrieve full page content —
    ideal for Reddit threads and forum posts where the snippet is too short.
    """
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "mcp-remote", mcp_url],
        env=None,
    )

    snippets: list[str] = []
    discovered_urls: list[str] = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # --- Phase 1: search ---
            for query in queries:
                print(f"  [tavily:search] {query!r}")
                try:
                    result = await session.call_tool(
                        "tavily_search",
                        {
                            "query": query,
                            "search_depth": "advanced",
                            "max_results": max_results,
                            "include_raw_content": False,
                        },
                    )
                    for block in result.content:
                        text = getattr(block, "text", "") or ""
                        if text.strip():
                            snippets.append(text[:snippet_limit])
                            if extract_urls:
                                discovered_urls.extend(_extract_urls(text))
                except Exception as exc:  # noqa: BLE001
                    print(f"  [tavily:search] WARNING: {exc}", file=sys.stderr)

            # --- Phase 2: extract full content from discovered URLs ---
            if extract_urls and discovered_urls:
                # Deduplicate and filter out obviously unhelpful URLs
                _skip_domains = {"docs.anthropic.com", "twitter.com", "x.com", "t.co"}
                urls_to_extract = [
                    u for u in dict.fromkeys(discovered_urls)
                    if not any(d in u for d in _skip_domains)
                ][:12]  # cap at 12 pages to stay within rate limits

                if urls_to_extract:
                    print(f"  [tavily:extract] extracting {len(urls_to_extract)} URLs…")
                    try:
                        result = await session.call_tool(
                            "tavily_extract",
                            {"urls": urls_to_extract},
                        )
                        for block in result.content:
                            text = getattr(block, "text", "") or ""
                            if text.strip():
                                # Full extracted pages can be large; keep top 4000 chars each
                                snippets.append(f"[EXTRACTED PAGE]\n{text[:4000]}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"  [tavily:extract] WARNING: {exc}", file=sys.stderr)

    return "\n\n---\n\n".join(snippets) if snippets else "(no results)"


def _docs_context(domain: str, mcp_url: str) -> str:
    """Gather context from official docs and technical blogs."""
    queries = _DOMAIN_QUERIES.get(domain) or [
        q.format(domain=domain) for q in _DEFAULT_QUERIES
    ]
    return asyncio.run(
        _run_mcp_pipeline(queries, mcp_url, extract_urls=False, max_results=5, snippet_limit=2000)
    )


def _community_context(domain: str, mcp_url: str) -> str:
    """Gather context from Reddit, forums, LinkedIn — real exam experiences.

    Two sub-phases:
      1. Domain-specific community queries.
      2. Generic exam-discovery queries (cross-domain; run once regardless of domain).
    """
    domain_queries = _COMMUNITY_QUERIES.get(domain) or [
        q.format(domain=domain) for q in _DEFAULT_COMMUNITY_QUERIES
    ]
    all_queries = domain_queries + _EXAM_DISCOVERY_QUERIES
    return asyncio.run(
        _run_mcp_pipeline(
            all_queries,
            mcp_url,
            extract_urls=True,   # ← extract full Reddit/forum threads
            max_results=7,
            snippet_limit=3000,
        )
    )


def _search_context(domain: str, mcp_url: str, strategy: str) -> str:
    """Return gathered context according to the chosen strategy."""
    if strategy == "docs":
        print("  [strategy] docs — official docs & technical blogs")
        return _docs_context(domain, mcp_url)
    if strategy == "community":
        print("  [strategy] community — Reddit / forums / exam experiences")
        return _community_context(domain, mcp_url)
    # "both"
    print("  [strategy] both — docs + community (two search passes)")
    docs = _docs_context(domain, mcp_url)
    community = _community_context(domain, mcp_url)
    return f"=== DOCS ===\n{docs}\n\n=== COMMUNITY DISCUSSIONS ===\n{community}"


def _load_existing(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _existing_ids(questions: list[dict]) -> set[str]:
    return {q.get("id", "") for q in questions}


def _generate(
    domain: str,
    count: int,
    existing_ids: set[str],
    context: str,
    strategy: str,
) -> list[dict]:
    client = anthropic.Anthropic()

    community_note = (
        " Pay special attention to questions and topics mentioned in community discussions, "
        "Reddit posts, and exam experience reports — those topics are very likely to appear "
        "on the real exam."
        if strategy in ("community", "both")
        else ""
    )

    system = (
        "You are an expert exam question author for the Claude Certified Architect certification. "
        "Write questions that test deep, practical understanding — not trivia. "
        "Base every question and explanation on the reference material provided."
        + community_note
        + " Write at the level of a senior engineer or solutions architect."
    )
    user = (
        f"Domain: '{domain}'\n"
        f"Questions to generate: {count}\n"
        f"Existing ids to avoid: {sorted(existing_ids) or 'none'}\n\n"
        f"=== Reference material (Tavily search results) ===\n{context}\n"
        f"=== End of reference material ===\n\n"
        + _SCHEMA_DESCRIPTION
    )
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)


_PROMPT_FILE = _REPO_ROOT / "scripts" / "copilot_prompt.txt"
_RESPONSE_FILE = _REPO_ROOT / "scripts" / "copilot_response.json"


def _build_prompt(domain: str, count: int, existing_ids: set[str], context: str) -> str:
    """Assemble the full prompt text to paste into Copilot Chat."""
    community_note = (
        " Pay special attention to questions and topics mentioned in community discussions, "
        "Reddit posts, and exam experience reports — those topics are very likely to appear "
        "on the real exam."
    )
    system_block = (
        "You are an expert exam question author for the Claude Certified Architect certification. "
        "Write questions that test deep, practical understanding — not trivia. "
        "Base every question and explanation on the reference material provided."
        + community_note
        + " Write at the level of a senior engineer or solutions architect."
    )
    return (
        f"{system_block}\n\n"
        f"Domain: '{domain}'\n"
        f"Questions to generate: {count}\n"
        f"Existing ids to avoid: {sorted(existing_ids) or 'none'}\n\n"
        f"=== Reference material (Tavily search results) ===\n{context}\n"
        f"=== End of reference material ===\n\n"
        + _SCHEMA_DESCRIPTION
    )


def _cmd_build_prompt(args: argparse.Namespace) -> None:
    """Run Tavily search, build prompt, save to file."""
    sys.path.insert(0, str(_REPO_ROOT))

    output_path = pathlib.Path(args.output)
    existing = _load_existing(output_path)
    existing_ids = _existing_ids(existing)

    if args.no_search:
        context = "(no search context — generating from model knowledge)"
        print("  [tavily] skipped (--no-search)")
    else:
        mcp_url = _resolve_mcp_url()
        if not mcp_url:
            print(
                "ERROR: Tavily MCP URL not found.\n"
                "Set TAVILY_MCP_URL or add tavily-remote to ~/.claude/settings.json",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"  Searching via Tavily MCP server (strategy: {args.strategy})…")
        context = _search_context(args.domain, mcp_url, args.strategy)
        print(f"  Got {len(context)} chars of context.")

    prompt = _build_prompt(args.domain, args.count, existing_ids, context)
    prompt_path = pathlib.Path(args.prompt_file)
    prompt_path.write_text(prompt, encoding="utf-8")

    print(f"\n✓ Prompt saved to: {prompt_path}")
    print(f"\nNext steps:")
    print(f"  1. Open {prompt_path} and copy all contents")
    print(f"  2. Paste into GitHub Copilot Chat (or any LLM chat)")
    print(f"  3. Copy the returned JSON array and save it to a file")
    print(f"  4. Run: python scripts/generate_questions.py --import <your_file.json>")
    print(f"     (default response file: {_RESPONSE_FILE})")


def _cmd_import(args: argparse.Namespace) -> None:
    """Validate and import a JSON array produced by Copilot into questions.json."""
    sys.path.insert(0, str(_REPO_ROOT))
    from app.errors import SchemaError
    from app.schema import validate_question

    import_path = pathlib.Path(args.import_file)
    if not import_path.exists():
        print(f"ERROR: file not found: {import_path}", file=sys.stderr)
        sys.exit(1)

    try:
        candidates: list[dict] = json.loads(import_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {import_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(candidates, list):
        print("ERROR: JSON must be an array at the top level", file=sys.stderr)
        sys.exit(1)

    output_path = pathlib.Path(args.output)
    existing = _load_existing(output_path)
    existing_ids = _existing_ids(existing)

    print(f"\nImporting {len(candidates)} candidate(s) from {import_path}…")
    added, rejected = 0, 0
    for item in candidates:
        if item.get("id") in existing_ids:
            print(f"  SKIP  duplicate id: {item.get('id')}")
            rejected += 1
            continue
        try:
            validate_question(item)
        except SchemaError as exc:
            print(f"  REJECT {item.get('id', '?')}: {exc}")
            rejected += 1
            continue
        existing.append(item)
        existing_ids.add(item["id"])
        print(f"  ADD   {item['id']}")
        added += 1

    output_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Added {added}, rejected {rejected}. Total: {len(existing)} questions.")


def _cmd_generate(args: argparse.Namespace) -> None:
    """Original flow: Tavily search → Claude API → append to questions.json."""
    sys.path.insert(0, str(_REPO_ROOT))
    from app.errors import SchemaError
    from app.schema import validate_question

    output_path = pathlib.Path(args.output)
    existing = _load_existing(output_path)
    existing_ids = _existing_ids(existing)

    print(f"\nGenerating {args.count} question(s) for domain '{args.domain}'")

    if args.no_search:
        context = "(no search context — generating from model knowledge)"
        strategy = "none"
        print("  [tavily] skipped (--no-search)")
    else:
        mcp_url = _resolve_mcp_url()
        if not mcp_url:
            print(
                "ERROR: Tavily MCP URL not found.\n"
                "Set TAVILY_MCP_URL=https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-...\n"
                "or add tavily-remote to ~/.claude/settings.json mcpServers.\n"
                "Alternatively use --no-search to skip web search.",
                file=sys.stderr,
            )
            sys.exit(1)
        strategy = args.strategy
        print("  Searching via Tavily MCP server…")
        context = _search_context(args.domain, mcp_url, strategy)
        print(f"  Got {len(context)} chars of context.\n")

    print("  Calling Claude to generate questions…")
    try:
        candidates = _generate(args.domain, args.count, existing_ids, context, strategy)
    except (json.JSONDecodeError, IndexError) as exc:
        print(f"ERROR: Could not parse Claude response: {exc}", file=sys.stderr)
        sys.exit(1)

    added, rejected = 0, 0
    for item in candidates:
        if item.get("id") in existing_ids:
            print(f"  SKIP  duplicate id: {item.get('id')}")
            rejected += 1
            continue
        try:
            validate_question(item)
        except SchemaError as exc:
            print(f"  REJECT {item.get('id', '?')}: {exc}")
            rejected += 1
            continue
        existing.append(item)
        existing_ids.add(item["id"])
        print(f"  ADD   {item['id']}")
        added += 1

    output_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Added {added}, rejected {rejected}. Total: {len(existing)} questions.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Claude quiz questions using Tavily MCP.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflows:

  A) Full auto (requires ANTHROPIC_API_KEY):
       python scripts/generate_questions.py --domain "Safety & Alignment" --count 5

  B) Copilot Chat (no API key needed):
     Step 1 — build prompt file:
       python scripts/generate_questions.py --build-prompt --domain "Safety & Alignment" --count 10 --strategy community
     Step 2 — paste prompt into Copilot Chat, save the JSON response to a file
     Step 3 — import the response:
       python scripts/generate_questions.py --import scripts/copilot_response.json
""",
    )
    parser.add_argument("--output", default=str(_DATA_FILE), help="Path to questions.json")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--build-prompt",
        action="store_true",
        help="Run Tavily search, write ready-to-paste prompt to --prompt-file",
    )
    mode.add_argument(
        "--import",
        dest="import_file",
        metavar="FILE",
        help="Import a JSON array (Copilot response) into questions.json",
    )

    parser.add_argument("--domain", help="Exam domain label (required for --build-prompt / default mode)")
    parser.add_argument("--count", type=int, default=5, help="Number of questions to generate")
    parser.add_argument("--no-search", action="store_true", help="Skip Tavily search (--build-prompt only)")
    parser.add_argument(
        "--strategy",
        choices=["docs", "community", "both"],
        default="community",
        help=(
            "'docs' — official docs; "
            "'community' — Reddit/forums/exam posts (default); "
            "'both' — both sources"
        ),
    )
    parser.add_argument(
        "--prompt-file",
        default=str(_PROMPT_FILE),
        help=f"Where to save the generated prompt (default: {_PROMPT_FILE})",
    )
    args = parser.parse_args()

    if args.import_file:
        _cmd_import(args)
    elif args.build_prompt:
        if not args.domain:
            parser.error("--domain is required with --build-prompt")
        _cmd_build_prompt(args)
    else:
        if not args.domain:
            parser.error("--domain is required")
        _cmd_generate(args)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
