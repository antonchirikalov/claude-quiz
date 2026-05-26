#!/usr/bin/env python3
"""Phase 0 — Style Anchor.

Reads existing gold-standard questions, computes style metrics, writes style_anchor.json.

Usage:
    python scripts/phase_0_anchor.py <questions_path> <anchor_output_path>
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path


def word_count(text: str) -> int:
    return len(text.split())


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = (p / 100) * (len(sorted_vals) - 1)
    lo, hi = int(idx), math.ceil(idx)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)


def detect_opening_pattern(stem: str) -> str:
    s = stem.lower()
    if re.search(r"\byou (want|need|have|are)\b", s):
        return "you_want_have"
    if re.search(r"\b(during|after) (testing|deployment|a run)\b", s):
        return "during_after_testing"
    if re.search(r"\byour (pipeline|script|application|team)\b", s):
        return "your_pipeline_script"
    if re.search(r"\b(production|deployed|live|at scale)\b", s):
        return "production_context"
    return "other"


def choice_length_ratio(choices: dict[str, str]) -> float:
    """Ratio of longest to shortest choice (by word count)."""
    lengths = [word_count(v) for v in choices.values() if v]
    if not lengths or min(lengths) == 0:
        return 1.0
    return max(lengths) / min(lengths)


def has_numerical_specifics(stem: str, explanation: str) -> bool:
    """Return True if stem or explanation contains numbers (token counts, limits, etc.)."""
    combined = stem + " " + explanation
    return bool(re.search(r"\b\d[\d,]*\b", combined))


def compute_anchor(questions: list[dict]) -> dict:
    stem_wc: list[int] = []
    expl_wc: list[int] = []
    choice_ratios: list[float] = []
    choice_counts: list[int] = []
    numerical_flags: list[bool] = []
    opening_patterns: list[str] = []
    ap_distractor_flags: list[bool] = []

    for q in questions:
        stem = q.get("stem", "")
        explanation = q.get("explanation", "")
        choices = q.get("choices", {})

        stem_wc.append(word_count(stem))
        expl_wc.append(word_count(explanation))
        choice_counts.append(len(choices))
        choice_ratios.append(choice_length_ratio(choices))
        numerical_flags.append(has_numerical_specifics(stem, explanation))
        opening_patterns.append(detect_opening_pattern(stem))
        ap_distractor_flags.append(bool(q.get("anti_pattern_in_distractor")))

    pattern_counts = Counter(opening_patterns)
    total = len(opening_patterns) or 1
    taxonomy = {k: round(v / total, 2) for k, v in pattern_counts.items()}

    choices_counter = Counter(choice_counts)
    choices_mode = choices_counter.most_common(1)[0][0] if choices_counter else 4

    return {
        "stem_words_p10": round(percentile(stem_wc, 10)),
        "stem_words_p90": round(percentile(stem_wc, 90)),
        "choices_count_mode": choices_mode,
        "choice_length_ratio_mean": round(sum(choice_ratios) / len(choice_ratios), 2),
        "choice_length_ratio_p90": round(percentile(choice_ratios, 90), 2),
        "ap_distractor_rate": round(sum(ap_distractor_flags) / len(ap_distractor_flags), 2),
        "numerical_specifics_rate": round(sum(numerical_flags) / len(numerical_flags), 2),
        "explanation_words_p10": round(percentile(expl_wc, 10)),
        "explanation_words_p90": round(percentile(expl_wc, 90)),
        "opening_pattern_taxonomy": taxonomy,
        "sample_size": len(questions),
    }


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: phase_0_anchor.py <questions_path> <anchor_output_path>",
            file=sys.stderr,
        )
        sys.exit(1)

    questions_path = Path(sys.argv[1])
    anchor_path = Path(sys.argv[2])

    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    if not isinstance(questions, list):
        print("ERROR: questions file must be a JSON array", file=sys.stderr)
        sys.exit(1)

    if len(questions) < 5:
        print(
            f"ERROR: need at least 5 questions for reliable anchor, got {len(questions)}",
            file=sys.stderr,
        )
        sys.exit(1)

    anchor = compute_anchor(questions)
    anchor_path.write_text(json.dumps(anchor, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"style_anchor.json written ({anchor['sample_size']} questions)")


if __name__ == "__main__":
    main()
