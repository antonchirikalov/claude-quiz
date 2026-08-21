"""Convert a Markdown question bank into an exam JSON file the app can serve.

The banks follow a fixed three-part layout:

    # Часть 1 — вопросы
    ## Scenario 1 · Title          (or "## Domain 1 · Title")
    <scenario description paragraph — optional>
    **1.** Stem text
    - A. choice
    ...
    # Часть 2 — ключ и разбор
    **1 · A** · TS 1.1. Why the right answer is right.
    - B: why B is wrong.
    ...
    # Часть 3 — подсчёт и диагностика
    (one-line answer tables + a domain → question numbers table)

Part 1 supplies stems, choices and scenario text; part 2 supplies answers and
explanations; part 3 supplies the domain mapping for scenario-grouped banks and a
second copy of the answer key that this script cross-checks against part 2.

Usage:
    python scripts/import_bank.py ../CCA-F_exam_bank.md --out exams/cca-f/full-bank.json
    python scripts/import_bank.py ../CCA-P_exam_bank.md --out exams/cca-p/full-bank.json
    python scripts/import_bank.py ../CCA-F_exam_bank.md --check
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.errors import SchemaError  # noqa: E402
from app.schema import validate_question  # noqa: E402

PART1 = re.compile(r"^#\s+Часть\s+1\b", re.M)
PART2 = re.compile(r"^#\s+Часть\s+2\b", re.M)
PART3 = re.compile(r"^#\s+Часть\s+3\b", re.M)

GROUP_HEADER = re.compile(
    r"^##\s+(?P<title>(?:Scenario|Domain)\s+(?P<num>\d+)\s*·\s*(?P<name>.+?))\s*$"
)
STEM = re.compile(r"^\*\*(?P<num>\d+)\.\*\*\s+(?P<stem>.+?)\s*$")
CHOICE = re.compile(r"^-\s+(?P<key>[A-F])\.\s+(?P<text>.+?)\s*$")
KEY_HEADER = re.compile(
    r"^\*\*(?P<num>\d+)\s*·\s*(?P<answers>[A-F](?:\s*,\s*[A-F])*)\*\*"
    r"(?:\s*·\s*)?(?P<rest>.*?)\s*$"
)
KEY_BULLET = re.compile(r"^-\s+(?P<text>.+?)\s*$")
# A citation under a key: `Источник: <url> — "quote"` (or `Source:`). The quote is
# optional; both dash styles are accepted because the banks mix them.
KEY_SOURCE = re.compile(
    r"^(?:Источник|Source):\s*(?P<url>https?://\S+)"
    r"(?:\s*[—-]\s*[\"«](?P<quote>.+?)[\"»])?\s*$"
)
REF_STRICT = re.compile(r"^((?:TS|O|PC)\s[\d.]+(?:\s*(?:и|,)\s*[\d.]+)*)\.\s+")
REF_LOOSE = re.compile(r"^((?:TS|O|PC)\s[\d.]+)")
# The domain cell always carries a "·" separator ("5 · Context Management"); requiring it
# keeps this off the one-line answer tables, whose cells are bare number ranges.
DOMAIN_ROW = re.compile(
    r"^\|\s*(?P<domain>[^|]*·[^|]*?)\s*\|\s*(?P<numbers>[\d,\s–\-]+?)\s*\|"
)
RANGE_CELL = re.compile(r"^\d+\s*[–-]\s*\d+$")
SELECT_N = re.compile(r"\(Select\s+(TWO|THREE|FOUR)\.?\)", re.I)

_WORD_TO_N = {"TWO": 2, "THREE": 3, "FOUR": 4}


@dataclass
class RawQuestion:
    number: int
    stem: str
    choices: dict[str, str] = field(default_factory=dict)
    group_title: str | None = None
    scenario: str | None = None


@dataclass
class RawKey:
    number: int
    answers: list[str]
    reference: str | None
    explanation: str
    sources: list[dict] = field(default_factory=list)


def split_parts(text: str) -> tuple[str, str, str]:
    """Split the bank into its three parts. Parts 1 and 2 are required."""
    for name, pattern in (("Часть 1", PART1), ("Часть 2", PART2)):
        if not pattern.search(text):
            raise SystemExit(f"Bank is missing the '# {name}' heading — cannot parse.")
    p1_start = PART1.search(text).end()
    p2_match = PART2.search(text)
    p3_match = PART3.search(text)
    part1 = text[p1_start : p2_match.start()]
    part2_end = p3_match.start() if p3_match else len(text)
    part2 = text[p2_match.end() : part2_end]
    part3 = text[p3_match.end() :] if p3_match else ""
    return part1, part2, part3


def parse_questions(part1: str) -> list[RawQuestion]:
    """Parse stems, choices and per-group scenario text out of part 1."""
    questions: list[RawQuestion] = []
    group_title: str | None = None
    group_intro: list[str] = []
    seen_question_in_group = False
    current: RawQuestion | None = None

    for line in part1.splitlines():
        stripped = line.strip()

        header = GROUP_HEADER.match(stripped)
        if header:
            group_title = header.group("title")
            group_intro = []
            seen_question_in_group = False
            current = None
            continue

        stem = STEM.match(stripped)
        if stem:
            current = RawQuestion(
                number=int(stem.group("num")),
                stem=stem.group("stem"),
                group_title=group_title,
                scenario="\n".join(group_intro) if group_intro else None,
            )
            questions.append(current)
            seen_question_in_group = True
            continue

        choice = CHOICE.match(stripped)
        if choice and current is not None:
            current.choices[choice.group("key")] = choice.group("text")
            continue

        # Free-standing prose before the group's first question is scenario setup.
        if (
            stripped
            and not seen_question_in_group
            and not stripped.startswith(("#", "|", ">", "-", "*", "!", "["))
        ):
            group_intro.append(stripped)

    return questions


def parse_keys(part2: str) -> list[RawKey]:
    """Parse answers, task-statement references and explanations out of part 2."""
    keys: list[RawKey] = []
    current: RawKey | None = None
    bullets: list[str] = []

    def close() -> None:
        if current is not None:
            current.explanation = "\n".join(
                [current.explanation, *[f"- {b}" for b in bullets]]
            ).strip()
            bullets.clear()

    for line in part2.splitlines():
        stripped = line.strip()

        header = KEY_HEADER.match(stripped)
        if header:
            close()
            rest = header.group("rest").strip()
            reference: str | None = None
            strict = REF_STRICT.match(rest)
            if strict:
                reference = re.sub(r"\s+", " ", strict.group(1))
                rest = rest[strict.end() :].strip()
            else:
                loose = REF_LOOSE.match(rest)
                if loose:
                    reference = re.sub(r"\s+", " ", loose.group(1))
            current = RawKey(
                number=int(header.group("num")),
                answers=[a.strip() for a in header.group("answers").split(",")],
                reference=reference,
                explanation=rest,
            )
            keys.append(current)
            continue

        if current is None:
            continue

        source = KEY_SOURCE.match(stripped)
        if source:
            entry = {"url": source.group("url")}
            if source.group("quote"):
                entry["quote"] = source.group("quote")
            current.sources.append(entry)
            continue

        bullet = KEY_BULLET.match(stripped)
        if bullet:
            bullets.append(bullet.group("text"))
        elif stripped.startswith(("#", "|")):
            close()
            current = None

    close()
    return keys


def parse_domain_map(part3: str) -> dict[int, str]:
    """Map question number → domain from the 'Результат по доменам' table."""
    mapping: dict[int, str] = {}
    for line in part3.splitlines():
        row = DOMAIN_ROW.match(line.strip())
        if not row:
            continue
        domain = re.sub(r"\s+", " ", row.group("domain")).strip()
        numbers = row.group("numbers")
        for chunk in numbers.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            span = re.match(r"^(\d+)\s*[–-]\s*(\d+)$", chunk)
            if span:
                for n in range(int(span.group(1)), int(span.group(2)) + 1):
                    mapping[n] = domain
            elif chunk.isdigit():
                mapping[int(chunk)] = domain
    return mapping


def parse_answer_tables(part3: str) -> dict[int, list[str]]:
    """Parse the 'Ответы одной строкой' tables for cross-checking the key."""
    answers: dict[int, list[str]] = {}
    lines = [line.strip() for line in part3.splitlines()]

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip("|").split("|")]

    for i, line in enumerate(lines):
        if not line.startswith("|") or i + 2 >= len(lines):
            continue
        header = cells(line)
        if not header or not all(RANGE_CELL.match(c) for c in header):
            continue
        body = cells(lines[i + 2])
        if len(body) != len(header):
            continue
        for span_cell, tokens_cell in zip(header, body):
            start, end = (int(x) for x in re.split(r"[–-]", span_cell))
            tokens = tokens_cell.split()
            if len(tokens) != end - start + 1:
                continue
            for offset, token in enumerate(tokens):
                answers[start + offset] = sorted(token.replace(",", ""))
    return answers


def build_records(
    questions: list[RawQuestion],
    keys: list[RawKey],
    domain_map: dict[int, str],
    id_prefix: str,
) -> tuple[list[dict], list[str]]:
    """Join part 1 and part 2 by question number into validated JSON records."""
    warnings: list[str] = []
    keys_by_number = {k.number: k for k in keys}
    records: list[dict] = []

    for q in questions:
        key = keys_by_number.get(q.number)
        if key is None:
            warnings.append(f"Q{q.number}: no answer key found in part 2 — skipped.")
            continue
        if len(q.choices) < 2:
            warnings.append(f"Q{q.number}: fewer than 2 choices parsed — skipped.")
            continue

        domain = domain_map.get(q.number)
        if domain is None and q.group_title and q.group_title.startswith("Domain"):
            domain = q.group_title.split("·", 1)[1].strip()
        if domain is None:
            domain = q.group_title or "Uncategorised"
            warnings.append(f"Q{q.number}: no domain mapping found, using '{domain}'.")

        want = SELECT_N.search(q.stem)
        if want and _WORD_TO_N[want.group(1).upper()] != len(key.answers):
            warnings.append(
                f"Q{q.number}: stem says Select {want.group(1).upper()} but the key lists "
                f"{len(key.answers)} answer(s) ({', '.join(key.answers)})."
            )
        if not want and len(key.answers) > 1:
            warnings.append(
                f"Q{q.number}: key lists {len(key.answers)} answers but the stem has no "
                f"'(Select N.)' marker."
            )

        record: dict = {
            "id": f"{id_prefix}-{q.number:02d}",
            "domain": domain,
            "stem": q.stem,
            "choices": q.choices,
            "explanation": key.explanation,
        }
        if len(key.answers) == 1:
            record["answer"] = key.answers[0]
        else:
            record["answers"] = sorted(key.answers)
        if q.scenario:
            record["scenario"] = q.scenario
            record["scenario_title"] = q.group_title
        if key.reference:
            record["reference"] = key.reference
        if key.sources:
            record["sources"] = key.sources

        try:
            validate_question(record)
        except SchemaError as exc:
            warnings.append(f"Q{q.number}: failed schema validation — skipped ({exc}).")
            continue

        records.append(record)

    return records, warnings


def cross_check(records: list[dict], table_answers: dict[int, list[str]]) -> list[str]:
    """Compare the part-2 key against the part-3 one-line answer tables."""
    warnings: list[str] = []
    for record in records:
        number = int(record["id"].rsplit("-", 1)[1])
        expected = table_answers.get(number)
        if expected is None:
            continue
        actual = sorted(record.get("answers", [record.get("answer")]))
        if actual != expected:
            warnings.append(
                f"Q{number}: part 2 says {', '.join(actual)} but the part 3 table says "
                f"{', '.join(expected)} — the bank disagrees with itself."
            )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", type=pathlib.Path, help="Markdown bank to convert")
    parser.add_argument(
        "--out", type=pathlib.Path, help="output JSON path, e.g. exams/cca-f/full-bank.json"
    )
    parser.add_argument(
        "--id-prefix", help="question id prefix (default: derived from the filename)"
    )
    parser.add_argument("--check", action="store_true", help="parse and report only, write nothing")
    args = parser.parse_args()

    if not args.out and not args.check:
        parser.error("either --out or --check is required")

    # Domain names and the report arrow are non-ASCII; a Windows console defaults to
    # cp1252 and would raise UnicodeEncodeError on the first print.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    text = args.source.read_text(encoding="utf-8-sig")
    part1, part2, part3 = split_parts(text)

    id_prefix = args.id_prefix or args.source.stem.split("_")[0].lower().replace("_", "-")

    questions = parse_questions(part1)
    keys = parse_keys(part2)
    domain_map = parse_domain_map(part3)
    records, warnings = build_records(questions, keys, domain_map, id_prefix)
    warnings += cross_check(records, parse_answer_tables(part3))

    print(f"{args.source.name}: {len(questions)} stems, {len(keys)} keys → {len(records)} records")
    multi = [r for r in records if "answers" in r]
    print(f"  multiple-response: {len(multi)}")
    domains: dict[str, int] = {}
    for r in records:
        domains[r["domain"]] = domains.get(r["domain"], 0) + 1
    for name, count in sorted(domains.items()):
        print(f"  {count:>3}  {name}")
    for w in warnings:
        print(f"  WARNING  {w}")

    if args.check:
        return 1 if warnings else 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
