"""Build exam-shaped simulation sets from an imported bank.

The real CCAR-F exam draws 4 scenarios at random from the official bank of 6, so a
straight run through every scenario is not what exam day looks like. This script
writes fixed 4-scenario simulations from the imported bank; three of them, arranged
so every scenario appears in exactly two, which lets you sit a fresh-feeling exam
three times without meeting the same scenario twice in a row.

Scenario 7 (prompt caching) is excluded: it sits outside the five scored domains.

Usage:
    python scripts/build_simulations.py exams/cca-f/full-bank-70.json --out-dir exams/cca-f
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.quiz import load_questions  # noqa: E402

# Each simulation names the official scenario numbers it draws from. The combinations
# are chosen so every simulation still touches all five scored domains — a random
# 4-of-6 draw can miss one entirely (e.g. scenarios 1-4 contain no Domain 4 questions).
SIMULATIONS = {
    "a": (1, 3, 5, 6),
    "b": (2, 4, 5, 6),
    "c": (1, 2, 4, 5),
}
SCENARIO_NUMBER = re.compile(r"Scenario\s+(\d+)")


def scenario_number(record: dict) -> int | None:
    """Official scenario number from the record's scenario title, if any."""
    match = SCENARIO_NUMBER.search(record.get("scenario_title") or "")
    return int(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=pathlib.Path, help="imported bank JSON")
    parser.add_argument("--out-dir", type=pathlib.Path, required=True)
    args = parser.parse_args()

    records = json.loads(args.source.read_text(encoding="utf-8"))
    by_scenario: dict[int, list[dict]] = {}
    for record in records:
        number = scenario_number(record)
        if number is not None:
            by_scenario.setdefault(number, []).append(record)

    available = sorted(by_scenario)
    print(f"{args.source.name}: {len(records)} records, scenarios {available}")

    for name, wanted in SIMULATIONS.items():
        missing = [n for n in wanted if n not in by_scenario]
        if missing:
            print(f"  SKIP sim {name.upper()} — bank has no scenario(s) {missing}")
            continue

        selected = [r for n in wanted for r in by_scenario[n]]
        out = args.out_dir / f"exam-sim-{name}.json"
        out.write_text(
            json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        questions = load_questions(out)  # fails loudly if a record is malformed
        domains: dict[str, int] = {}
        for q in questions:
            domains[q.domain] = domains.get(q.domain, 0) + 1
        spread = ", ".join(f"{d.split(' · ')[0]}:{c}" for d, c in sorted(domains.items()))
        print(f"  sim {name.upper()}: scenarios {wanted} → {len(questions)} questions ({spread})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
