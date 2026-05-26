#!/usr/bin/env python3
"""Pipeline orchestrator for exam question generation.

Usage:
    python scripts/runner.py --exam "Claude Certified Architect - Fundamentals"
    python scripts/runner.py --exam "Claude Certified Architect - Fundamentals" --questions 120
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

SCRIPTS_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPTS_DIR.parent


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def make_slug(name: str) -> str:
    """Convert an exam name to a lowercase hyphen-separated filesystem slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def run_with_retry(
    cmd: list[str],
    *,
    phase: str,
    label: str,
    max_attempts: int = 3,
) -> subprocess.CompletedProcess | None:
    """Run a subprocess with exponential-backoff retry.

    Returns the completed process on success, or None if all attempts fail.
    """
    for attempt in range(1, max_attempts + 1):
        logger.debug(
            f"subprocess ({phase} {label} attempt {attempt}/{max_attempts}): {' '.join(cmd)}"
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result

        wait = 2**attempt
        if attempt < max_attempts:
            logger.warning(
                f"{phase} {label} attempt {attempt}/{max_attempts} failed "
                f"(exit_code={result.returncode}), retrying in {wait}s"
            )
            if result.stderr:
                logger.debug(f"stderr: {result.stderr[:500]}")
            time.sleep(wait)
        else:
            logger.error(
                f"{phase} {label} all retries exhausted (exit_code={result.returncode})"
            )
            if result.stderr:
                logger.debug(f"stderr: {result.stderr[:500]}")
    return None


def extract_json_from_copilot_output(stdout: str) -> dict:
    """Parse JSON from copilot CLI --output-format json JSONL output.

    Each JSONL line is a JSON object. We look for the last line whose key is
    'assistant.message' (or type == 'assistant.message') and extract a JSON
    block from its text content.
    """
    last_message: str | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "assistant.message":
            # copilot CLI v1.x: content lives at data.content
            content = obj.get("data", {}).get("content") or obj.get("content") or obj.get("message") or ""
            if content:
                last_message = str(content)
        elif "assistant.message" in obj:
            # legacy fallback: {"assistant.message": "..."}
            last_message = str(obj["assistant.message"])

    if last_message is None:
        raise ValueError(
            f"No assistant.message found in copilot output.\nStdout:\n{stdout[:400]}"
        )

    # Try ```json ... ``` fenced block first
    fenced = re.search(r"```json\s*([\s\S]*?)```", last_message)
    if fenced:
        return json.loads(fenced.group(1).strip())

    # Try bare JSON object
    obj_match = re.search(r"\{[\s\S]*\}", last_message)
    if obj_match:
        return json.loads(obj_match.group())

    raise ValueError(
        f"Cannot extract JSON from assistant message:\n{last_message[:400]}"
    )


def stem_words(text: str) -> set[str]:
    """Return set of lowercase words (≥3 chars) from text, used for dedup."""
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


def is_duplicate(
    words: set[str], existing: list[set[str]], threshold: float = 0.7
) -> bool:
    """Return True if Jaccard similarity with any existing stem exceeds threshold."""
    for other in existing:
        if not words or not other:
            continue
        if len(words & other) / len(words | other) > threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_researcher_task(
    exam_name: str,
    questions_target: int | None,
    practice_corpus_path: Path,
) -> str:
    questions_hint = (
        f"Target question count: {questions_target}."
        if questions_target
        else "Determine total_questions from the official exam guide."
    )
    return f"""# Exam Researcher Task

## Objective

Research the following exam and output structured data to stdout as a JSON object.

**Exam:** {exam_name}
**{questions_hint}**

## Steps

1. Search for the official exam guide via Tavily (query: `{exam_name} official exam guide domains weights`).
   Extract: domain names, domain weights (percentages), total_questions.

2. Search exam community forums via Tavily:
   - Reddit, LinkedIn Learning, Medium, community blogs
   - Queries: `{exam_name} exam experience`, `{exam_name} difficult topics`, `{exam_name} misconceptions`
   - For each topic signal: note which domain it belongs to, frequency of mentions, the core insight.

3. From forum misconceptions, derive an anti-pattern (AP) list:
   common wrong approaches that candidates use, which the exam tests against.

4. Collect practice questions from legitimate open practice sites (NOT brain-dump sites).
   Write them directly to: `{practice_corpus_path}`
   Format: JSON array `[{{"stem": "...", "choices": {{}}, "source_site": "..."}}]`
   Do NOT include the practice corpus in stdout.

5. Identify topics mentioned in community discussions that are explicitly in-scope
   or out-of-scope in the official guide.

## Output to stdout

Output ONLY this JSON object (no other text before or after):

```json
{{
  "exam_meta": {{
    "name": "{exam_name}",
    "total_questions": 120,
    "domains": [
      {{"id": "D1", "name": "Domain Name", "weight": 0.25}},
      {{"id": "D2", "name": "Domain Name", "weight": 0.20}}
    ],
    "anti_patterns": [
      {{"id": "AP-D1-01", "label": "Short label", "description": "What candidates get wrong"}}
    ]
  }},
  "signals": [
    {{
      "topic": "topic name",
      "domain_id": "D1",
      "subdomain": "D1.1",
      "signal_strength": 0.85,
      "source_count": 7,
      "insight": "Why candidates struggle with this"
    }}
  ],
  "discovered_subdomains": [
    {{
      "topic": "topic name",
      "in_scope": false,
      "note": "Reason included or excluded"
    }}
  ]
}}
```
"""


def build_writer_task(
    row: dict,
    proposed_id: str,
    output_path: Path,
    anchor: dict,
    today: str,
) -> str:
    stem_hint = f"{anchor.get('stem_words_p10', 34)}–{anchor.get('stem_words_p90', 77)}"
    expl_hint = (
        f"{anchor.get('explanation_words_p10', 42)}–{anchor.get('explanation_words_p90', 119)}"
    )
    num_rate = anchor.get("numerical_specifics_rate", 0.42)
    ap_rate = anchor.get("ap_distractor_rate", 0.50)
    n_choices = anchor.get("choices_count_mode", 4)
    return f"""# Question Writer Task

## Assignment

Write exactly ONE multiple-choice question for a professional certification exam.

| Field | Value |
|---|---|
| Row ID | {row["row_id"]} |
| Domain | {row["domain"]} ({row["domain_id"]}) |
| Subdomain | {row.get("subdomain_id", "")} |
| Topic hint | {row.get("topic_hint", "")} |
| Scenario ID | {row.get("scenario_id", "")} |
| Anti-pattern to embed in a wrong answer | {row.get("anti_pattern_id", "")} |
| Difficulty | {row.get("difficulty", "medium")} |
| Stem format | {row.get("stem_format", "which_approach")} |

## Style targets (measured from gold-standard questions)

| Metric | Target |
|---|---|
| Stem length | {stem_hint} words |
| Number of answer choices | {n_choices} |
| Explanation length | {expl_hint} words |
| Include numerical specifics | ~{num_rate:.0%} of questions (token counts, limits, ratios) |
| AP distractor rate | ~{ap_rate:.0%} — one wrong answer must reflect the assigned anti-pattern |

## Stem format guide

| Format | Pattern |
|---|---|
| `which_approach` | "Which approach…" / "What is the most effective…" |
| `root_cause` | "What is the most likely root cause of…" |
| `evaluate_proposal` | "How should you evaluate this proposal…" |
| `whats_wrong` | "What would NOT improve…" / "What is wrong with this design…" |

Use the assigned format: **{row.get("stem_format", "which_approach")}**

## Cognitive level requirement

Test **APPLICATION or ANALYSIS** (Bloom levels 3–4).
- ✓ Describe a concrete production scenario where the candidate must choose between plausible alternatives.
- ✗ Do NOT write recall questions ("What does X do?", "Which API call performs Y?").

## Steps

1. Search `docs.anthropic.com` via Tavily for: `{row.get("topic_hint", row.get("domain", ""))}`
2. Identify one specific documented fact or quote to use as a source anchor.
3. Write the question. The correct answer must be unambiguously supported by the documentation.
4. Ensure the wrong answers are plausible but clearly wrong on reflection.
5. One wrong answer must reflect anti-pattern: `{row.get("anti_pattern_id", "")}`
6. Write the output JSON to: `{output_path}`

## Question ID

Use exactly this id (do not change it): `{proposed_id}`
Constraint: lowercase, hyphens only, no spaces — enforced by the app schema.

## Output file

Write this JSON object to `{output_path}`:

```json
{{
  "id": "{proposed_id}",
  "domain": "{row["domain"]}",
  "subdomain_id": "{row.get("subdomain_id", "")}",
  "scenario_id": "{row.get("scenario_id", "")}",
  "anti_pattern_in_distractor": "{row.get("anti_pattern_id", "")}",
  "stem": "...",
  "choices": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "answer": "C",
  "explanation": "...",
  "sources": [
    {{
      "url": "https://docs.anthropic.com/...",
      "anchor_kind": "quote",
      "anchor_value": "exact text from the page",
      "supports": "one sentence: what this source proves about the correct answer",
      "retrieved_at": "{today}"
    }}
  ]
}}
```
"""


def build_reviewer_task(q: dict, result_path: Path) -> str:
    choices_fmt = "\n".join(f"  {k}: {v}" for k, v in q.get("choices", {}).items())
    return f"""# Adversarial Reviewer Task

You are a quality reviewer for a certification exam question bank.
Your job: independently answer this question, then evaluate its quality.

## The Question

**ID:** {q["id"]}

**Stem:**
{q.get("stem", "")}

**Answer choices:**
{choices_fmt}

---

## Instructions

### Step 1 — Answer blind

IMPORTANT: answer BEFORE reading the author's answer in Step 2 below.
- Which choice would YOU select?
- Your confidence: 1 (completely uncertain) to 10 (certain)
- Your reasoning in one sentence

### Step 2 — Compare with author

**Author's correct answer:** {q.get("answer", "")}
**Author's explanation:** {q.get("explanation", "")}

Check for these defects:
- Does another choice also seem correct? (distractor ambiguity)
- Does the stem hint at the answer? (stem clue)
- Is this testing recall rather than understanding or application?
- Is the explanation incomplete or incorrect?

### Step 3 — Assign flag

| Flag | Condition |
|---|---|
| `solid` | Your answer agrees with author AND confidence ≥ 7. Question is clean. |
| `ambiguous` | Disagreement OR confidence ≤ 5. Borderline — kept with `quality_tier: "hard"`. |
| `bug` | Disagreement AND confidence ≥ 7. Clear defect — excluded from final set. |

### Step 4 — Write result

Write this JSON to: `{result_path}`

```json
{{
  "question_id": "{q["id"]}",
  "blind_answer": "X",
  "blind_confidence": 8,
  "blind_rationale": "One sentence: why you chose that answer",
  "agreement": true,
  "flag": "solid",
  "issues": []
}}
```

`issues` is an array of strings describing specific defects. Empty array if none.
"""


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


# Hardcoded anchor defaults used when no seed questions are available.
# Derived from the Claude certification question set (May 2026).
_DEFAULT_ANCHOR: dict = {
    "stem_words_p10": 34,
    "stem_words_p90": 77,
    "choices_count_mode": 4,
    "choice_length_ratio_mean": 1.8,
    "choice_length_ratio_p90": 2.6,
    "ap_distractor_rate": 0.50,
    "numerical_specifics_rate": 0.42,
    "explanation_words_p10": 42,
    "explanation_words_p90": 119,
    "opening_pattern_taxonomy": {
        "you_want_have": 0.30,
        "your_pipeline_script": 0.25,
        "production_context": 0.25,
        "other": 0.20,
    },
    "sample_size": 0,
}


def _find_seed_questions(slug: str) -> Path | None:
    """Return a path to seed questions (≥5 items) or None.

    Search order:
      1. exams/<slug>/questions.json
      2. data/questions.json
    """
    candidates = [
        PROJECT_ROOT / "exams" / slug / "questions.json",
        PROJECT_ROOT / "data" / "questions.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                qs = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(qs, list) and len(qs) >= 5:
                    return path
            except (json.JSONDecodeError, OSError):
                continue
    return None


def phase_0(artifacts_dir: Path, practice_corpus_path: Path) -> Path:
    """Run style anchor analysis (Python, no LLM).

    Uses the practice corpus collected by Phase 1 (exam-researcher via Tavily).
    Fallback: built-in defaults if corpus is missing or too small.
    """
    logger.info("Phase 0 start — style anchor")
    anchor_path = artifacts_dir / "style_anchor.json"

    questions_path: Path | None = None
    if practice_corpus_path.exists():
        try:
            corpus = json.loads(practice_corpus_path.read_text(encoding="utf-8"))
            if isinstance(corpus, list) and len(corpus) >= 3:
                questions_path = practice_corpus_path
                logger.info(
                    f"Phase 0: using {len(corpus)} practice questions from Tavily corpus"
                )
            else:
                logger.warning(
                    f"Phase 0: practice corpus has only {len(corpus) if isinstance(corpus, list) else 0} "
                    "questions — using built-in anchor defaults"
                )
        except (json.JSONDecodeError, OSError):
            logger.warning("Phase 0: cannot read practice corpus — using built-in anchor defaults")

    if questions_path is None:
        anchor_path.write_text(
            json.dumps(_DEFAULT_ANCHOR, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Phase 0 done — built-in defaults written to style_anchor.json")
        return anchor_path

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase_0_anchor.py"),
            str(questions_path),
            str(anchor_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning(
            f"Phase 0: phase_0_anchor.py failed ({result.stderr[:200].strip()}) — "
            "falling back to built-in defaults"
        )
        anchor_path.write_text(
            json.dumps(_DEFAULT_ANCHOR, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        logger.info("Phase 0 done — style_anchor.json saved")
    return anchor_path


def phase_1(
    artifacts_dir: Path,
    prompts_dir: Path,
    exam_name: str,
    questions_target: int | None,
) -> tuple[dict, dict]:
    """Run exam-researcher agent. Returns (exam_meta, forum_signals)."""
    logger.info("Phase 1 start — exam-researcher")

    practice_corpus_path = artifacts_dir / "practice_corpus.json"
    task_path = prompts_dir / "researcher_task.md"
    task_path.write_text(
        build_researcher_task(exam_name, questions_target, practice_corpus_path),
        encoding="utf-8",
    )

    result = run_with_retry(
        [
            "copilot",
            "--agent",
            "exam-researcher",
            "-p",
            str(task_path),
            "--allow-all",
            "--no-ask-user",
            "--output-format",
            "json",
        ],
        phase="Phase 1",
        label="exam-researcher",
    )
    if result is None:
        raise SystemExit("Phase 1: exam-researcher failed after all retries")

    data = extract_json_from_copilot_output(result.stdout)
    exam_meta: dict = data["exam_meta"]
    signals: list = data.get("signals", [])
    discovered_subdomains: list = data.get("discovered_subdomains", [])
    forum_signals: dict = {"signals": signals, "discovered_subdomains": discovered_subdomains}

    (artifacts_dir / "exam_meta.json").write_text(
        json.dumps(exam_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (artifacts_dir / "forum_signals.json").write_text(
        json.dumps(forum_signals, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    practice_count = 0
    if practice_corpus_path.exists():
        try:
            corpus = json.loads(practice_corpus_path.read_text(encoding="utf-8"))
            practice_count = len(corpus) if isinstance(corpus, list) else 0
        except json.JSONDecodeError:
            pass

    logger.info(
        f"Phase 1 done — {len(signals)} signals, "
        f"{len(discovered_subdomains)} discovered_subdomains, "
        f"{practice_count} practice questions"
    )
    return exam_meta, forum_signals


def phase_2(artifacts_dir: Path, questions_target: int) -> list[dict]:
    """Run coverage matrix builder (Python, no LLM)."""
    logger.info("Phase 2 start — coverage matrix")
    matrix_path = artifacts_dir / "coverage_matrix.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase_2_coverage.py"),
            str(artifacts_dir / "exam_meta.json"),
            str(artifacts_dir / "forum_signals.json"),
            str(questions_target),
            str(matrix_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"Phase 2 failed:\n{result.stderr}")
        raise SystemExit(1)

    matrix: list[dict] = json.loads(matrix_path.read_text(encoding="utf-8"))
    logger.info(f"Phase 2 done — {len(matrix)} rows in coverage matrix")
    return matrix


def phase_3(
    artifacts_dir: Path,
    prompts_dir: Path,
    matrix: list[dict],
    anchor_path: Path,
) -> Path:
    """Run question-writer agents, one per coverage matrix row."""
    logger.info(f"Phase 3 start — question-writer ({len(matrix)} questions)")

    anchor: dict = json.loads(anchor_path.read_text(encoding="utf-8"))
    # Each agent writes to its own file; runner assembles into JSONL afterwards.
    raw_dir = artifacts_dir / "questions_raw"
    raw_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    skipped = 0
    for row in matrix:
        row_id = row["row_id"]
        output_path = raw_dir / f"q_{row_id}.json"
        task_path = prompts_dir / f"writer_task_{row_id}.md"

        domain_abbr = row["domain_id"].lower().replace("_", "-")
        topic_slug = (
            re.sub(r"[^a-z0-9]+", "-", row.get("topic_hint", row_id).lower())
            .strip("-")[:40]
        )
        proposed_id = f"{domain_abbr}-{topic_slug}"

        task_path.write_text(
            build_writer_task(row, proposed_id, output_path, anchor, today),
            encoding="utf-8",
        )

        result = run_with_retry(
            [
                "copilot",
                "--agent",
                "question-writer",
                "-p",
                str(task_path),
                "--allow-all",
                "--no-ask-user",
                "--output-format",
                "json",
            ],
            phase="Phase 3",
            label=f"row={row_id}",
        )
        if result is None:
            skipped += 1
            continue

        if not output_path.exists():
            logger.warning(
                f"Phase 3 row={row_id}: output file not created by agent, skipping"
            )
            skipped += 1

    # Assemble questions_raw.jsonl
    raw_path = artifacts_dir / "questions_raw.jsonl"
    written = 0
    with raw_path.open("w", encoding="utf-8") as f:
        for q_file in sorted(raw_dir.glob("q_*.json")):
            try:
                q = json.loads(q_file.read_text(encoding="utf-8"))
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
                written += 1
            except json.JSONDecodeError as exc:
                logger.warning(f"Phase 3: cannot parse {q_file.name}: {exc}")

    logger.info(
        f"Phase 3 done — {written} questions in questions_raw.jsonl, {skipped} skipped"
    )
    return raw_path


def phase_4(
    artifacts_dir: Path,
    prompts_dir: Path,
    raw_path: Path,
) -> dict[str, dict]:
    """Run adversarial-reviewer agents, one per question."""
    logger.info("Phase 4 start — adversarial-reviewer")

    adversarial_dir = artifacts_dir / "adversarial_results"
    adversarial_dir.mkdir(exist_ok=True)

    questions: list[dict] = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    skipped = 0
    for q in questions:
        qid = q["id"]
        result_path = adversarial_dir / f"adversarial_result_{qid}.json"
        task_path = prompts_dir / f"reviewer_task_{qid}.md"

        task_path.write_text(build_reviewer_task(q, result_path), encoding="utf-8")

        result = run_with_retry(
            [
                "copilot",
                "--agent",
                "adversarial-reviewer",
                "-p",
                str(task_path),
                "--allow-all",
                "--no-ask-user",
                "--output-format",
                "json",
            ],
            phase="Phase 4",
            label=f"q={qid}",
        )
        if result is None:
            skipped += 1
            continue

        if not result_path.exists():
            logger.warning(f"Phase 4 q={qid}: result file not created by agent")
            skipped += 1

    # Assemble adversarial_report.json from per-question files
    report: list[dict] = []
    for f in sorted(adversarial_dir.glob("adversarial_result_*.json")):
        try:
            report.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            logger.warning(f"Phase 4: cannot parse {f.name}: {exc}")

    report_path = artifacts_dir / "adversarial_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(f"Phase 4 done — {len(report)} reviews assembled, {skipped} skipped")
    return {r["question_id"]: r for r in report}


def phase_5(artifacts_dir: Path) -> dict[str, dict]:
    """Run citation verification (Python + Tavily Extract). Non-blocking on failure."""
    logger.info("Phase 5 start — citation verification")
    anchor_report_path = artifacts_dir / "anchor_report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase_5_verify.py"),
            str(artifacts_dir / "questions_raw.jsonl"),
            str(anchor_report_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning(f"Phase 5 failed (non-blocking): {result.stderr[:300]}")
        return {}

    try:
        report: list[dict] = json.loads(anchor_report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning(f"Phase 5: cannot read anchor_report.json: {exc}")
        return {}

    verified = sum(1 for r in report if r.get("status") == "verified")
    not_found = sum(1 for r in report if r.get("status") == "not_found")
    logger.info(f"Phase 5 done — {verified} verified, {not_found} not_found")
    return {r["question_id"]: r for r in report}


def phase_6(artifacts_dir: Path) -> dict[str, dict]:
    """Run style audit (Python). Non-blocking on failure."""
    logger.info("Phase 6 start — style audit")
    audit_path = artifacts_dir / "style_audit.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "phase_6_style_audit.py"),
            str(artifacts_dir / "questions_raw.jsonl"),
            str(artifacts_dir / "style_anchor.json"),
            str(audit_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning(f"Phase 6 failed (non-blocking): {result.stderr[:300]}")
        return {}

    try:
        audit: list[dict] = json.loads(audit_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning(f"Phase 6: cannot read style_audit.json: {exc}")
        return {}

    style_fail = sum(1 for r in audit if r.get("status") == "style_fail")
    logger.info(f"Phase 6 done — {style_fail} style_fail questions")
    return {r["question_id"]: r for r in audit}


def phase_7(
    artifacts_dir: Path,
    run_dir: Path,
    raw_path: Path,
    adversarial_index: dict[str, dict],
    anchor_index: dict[str, dict],
    style_index: dict[str, dict],
    target_n: int,
) -> Path:
    """Assemble final questions JSON (Phase 7)."""
    logger.info("Phase 7 start — assembly")

    sys.path.insert(0, str(PROJECT_ROOT))
    from app.errors import SchemaError
    from app.schema import validate_question

    questions_raw: list[dict] = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Load practice corpus stems for dedup
    practice_stem_sets: list[set[str]] = []
    practice_path = artifacts_dir / "practice_corpus.json"
    if practice_path.exists():
        try:
            corpus = json.loads(practice_path.read_text(encoding="utf-8"))
            practice_stem_sets = [
                stem_words(q.get("stem", ""))
                for q in corpus
                if isinstance(q, dict)
            ]
        except (json.JSONDecodeError, TypeError):
            pass

    counts = {"bug": 0, "not_found": 0, "style_fail": 0, "dedup": 0, "schema_error": 0}
    accepted: list[dict] = []
    seen_stem_sets: list[set[str]] = []

    for q in questions_raw:
        qid = q.get("id", "unknown")

        # Step 2: filter bugs
        adv = adversarial_index.get(qid, {})
        if adv.get("flag") == "bug":
            counts["bug"] += 1
            logger.debug(f"Rejected {qid}: adversarial flag=bug")
            continue

        # Step 3: add quality_tier
        q["quality_tier"] = "hard" if adv.get("flag") == "ambiguous" else "solid"

        # Step 4: note citation issues (non-blocking)
        if anchor_index.get(qid, {}).get("status") == "not_found":
            counts["not_found"] += 1
            logger.debug(f"Flagged {qid}: citation not_found (keeping)")

        # Step 5: filter style_fail
        if style_index.get(qid, {}).get("status") == "style_fail":
            counts["style_fail"] += 1
            logger.debug(f"Rejected {qid}: style_fail")
            continue

        # Step 6: dedup
        words = stem_words(q.get("stem", ""))
        if is_duplicate(words, seen_stem_sets + practice_stem_sets):
            counts["dedup"] += 1
            logger.debug(f"Rejected {qid}: duplicate stem")
            continue

        # Step 7: validate schema
        try:
            validate_question(q)
        except SchemaError as exc:
            counts["schema_error"] += 1
            logger.warning(f"Rejected {qid}: schema error — {exc}")
            continue

        seen_stem_sets.append(words)
        accepted.append(q)

    passed = len(accepted)
    logger.info(
        f"Phase 7 assembly: raw={len(questions_raw)}, bug={counts['bug']}, "
        f"style_fail={counts['style_fail']}, dedup={counts['dedup']}, "
        f"schema_error={counts['schema_error']}, passed={passed}"
    )

    if passed < target_n * 0.9:
        logger.warning(
            f"Only {passed}/{target_n} questions passed ({passed / target_n:.0%}): "
            f"bug={counts['bug']}, not_found={counts['not_found']}, "
            f"style_fail={counts['style_fail']}, dedup={counts['dedup']}, "
            f"schema_error={counts['schema_error']}. "
            "Recommend rerunning Phase 3 for missing coverage matrix rows."
        )

    # Step 8: save final output
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = run_dir / f"questions-{today}.json"
    output_path.write_text(
        json.dumps(accepted, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Output: {output_path} ({passed} questions)")
    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate exam questions through a multi-phase agent pipeline."
    )
    parser.add_argument(
        "--exam",
        required=True,
        help="Full exam name, e.g. 'Claude Certified Architect - Fundamentals'",
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=None,
        help="Target number of questions (default: determined from exam guide in Phase 1)",
    )
    args = parser.parse_args()

    exam_name: str = args.exam
    questions_target: int | None = args.questions
    slug = make_slug(exam_name)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = (
        PROJECT_ROOT / "exams" / slug / "runs" / f"questions_{slug}_{timestamp}"
    )
    artifacts_dir = run_dir / f"_artifacts_{timestamp}"
    prompts_dir = artifacts_dir / "prompts"

    for d in (run_dir, artifacts_dir, prompts_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Configure loguru: full DEBUG log to file, INFO to stderr
    logger.remove()
    logger.add(
        str(artifacts_dir / "runner.log"),
        level="DEBUG",
        rotation=None,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
    )
    logger.add(
        sys.stderr,
        level="INFO",
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
    )

    logger.info(
        f"Pipeline start: exam={exam_name!r}, "
        f"N={questions_target or 'from Phase 1'}, "
        f"run={run_dir.name}"
    )

    exam_meta, _forum_signals = phase_1(
        artifacts_dir, prompts_dir, exam_name, questions_target
    )

    practice_corpus_path = artifacts_dir / "practice_corpus.json"
    anchor_path = phase_0(artifacts_dir, practice_corpus_path)

    if questions_target is None:
        questions_target = exam_meta.get("total_questions", 120)
        logger.info(f"Target N resolved from exam guide: {questions_target}")

    matrix = phase_2(artifacts_dir, questions_target)
    raw_path = phase_3(artifacts_dir, prompts_dir, matrix, anchor_path)
    adversarial_index = phase_4(artifacts_dir, prompts_dir, raw_path)
    anchor_index = phase_5(artifacts_dir)
    style_index = phase_6(artifacts_dir)

    output_path = phase_7(
        artifacts_dir,
        run_dir,
        raw_path,
        adversarial_index,
        anchor_index,
        style_index,
        questions_target,
    )

    logger.info(
        f"Done. To publish: cp '{output_path}' 'exams/{slug}/questions.json'"
    )


if __name__ == "__main__":
    main()
