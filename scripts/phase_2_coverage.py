#!/usr/bin/env python3
"""Phase 2 — Coverage Matrix.

Distributes N questions across domains and subdomains according to exam guide weights
and forum signal boosts. Assigns difficulty, stem_format, scenario_id, and anti_pattern_id
to each row deterministically.

Usage:
    python scripts/phase_2_coverage.py <exam_meta_path> <forum_signals_path> <n> <output_path>
"""

import json
import math
import random
import sys
from pathlib import Path

# Stem format distribution (from 12 official sample analysis)
STEM_FORMATS = ["which_approach"] * 70 + ["root_cause"] * 15 + ["evaluate_proposal"] * 10 + ["whats_wrong"] * 5
# Difficulty distribution: easy 25%, medium 50%, hard 25%
DIFFICULTY_POOL = ["easy"] * 25 + ["medium"] * 50 + ["hard"] * 25


def distribute_n(total: int, weights: list[float]) -> list[int]:
    """Distribute total across buckets by weight, ensuring sum == total."""
    raw = [total * w for w in weights]
    floored = [math.floor(v) for v in raw]
    remainder = total - sum(floored)
    # Distribute remainder to buckets with largest fractional parts
    fractions = [(raw[i] - floored[i], i) for i in range(len(weights))]
    fractions.sort(reverse=True)
    for i in range(remainder):
        floored[fractions[i][1]] += 1
    return floored


def boost_signals(
    domain_rows: list[dict],
    signals: list[dict],
    domain_id: str,
) -> list[dict]:
    """Attach signal metadata (signal_strength, insight) to rows for high-signal topics."""
    high_signals = [
        s for s in signals
        if s.get("domain_id") == domain_id and s.get("signal_strength", 0) >= 0.6
    ]
    # Sort rows so high-signal topics appear near the front
    signal_topics = {s["topic"].lower(): s for s in high_signals}
    for row in domain_rows:
        hint = row.get("topic_hint", "").lower()
        for topic, sig in signal_topics.items():
            if any(word in hint for word in topic.split() if len(word) > 3):
                row["signal_strength"] = sig["signal_strength"]
                row["insight"] = sig.get("insight", "")
                break
    return sorted(domain_rows, key=lambda r: -r.get("signal_strength", 0))


def build_matrix(
    exam_meta: dict,
    forum_signals: dict,
    n: int,
    rng: random.Random,
) -> list[dict]:
    domains: list[dict] = exam_meta.get("domains", [])
    anti_patterns: list[dict] = exam_meta.get("anti_patterns", [])
    signals: list[dict] = forum_signals.get("signals", [])
    discovered: list[dict] = forum_signals.get("discovered_subdomains", [])

    if not domains:
        raise ValueError("exam_meta has no domains")

    # Step 1: distribute N by domain weight
    weights = [d.get("weight", 1 / len(domains)) for d in domains]
    total_weight = sum(weights)
    normalized = [w / total_weight for w in weights]
    counts = distribute_n(n, normalized)

    # Step 6: add extra rows for in-scope discovered subdomains
    extra_topics = [d for d in discovered if d.get("in_scope") is True]
    for extra in extra_topics:
        # Assign extra question to the most relevant domain (D1 fallback)
        domain_id = extra.get("domain_id", domains[0]["id"])
        idx = next((i for i, d in enumerate(domains) if d["id"] == domain_id), 0)
        counts[idx] += 1
        n += 1

    stem_format_pool = rng.sample(STEM_FORMATS * math.ceil(n / len(STEM_FORMATS)), n)
    difficulty_pool = rng.sample(
        DIFFICULTY_POOL * math.ceil(n / len(DIFFICULTY_POOL)), n
    )

    ap_cycle = anti_patterns if anti_patterns else [{"id": "", "label": ""}]
    matrix: list[dict] = []
    row_counter = 0

    for domain_idx, domain in enumerate(domains):
        domain_id = domain["id"]
        domain_name = domain["name"]
        domain_count = counts[domain_idx]

        # Build subdomain list from signals for this domain
        domain_signals = [s for s in signals if s.get("domain_id") == domain_id]
        subdomains = list({s.get("subdomain", f"{domain_id}.1") for s in domain_signals})
        if not subdomains:
            subdomains = [f"{domain_id}.1"]

        domain_rows: list[dict] = []
        for i in range(domain_count):
            subdomain_id = subdomains[i % len(subdomains)]
            ap = ap_cycle[(row_counter) % len(ap_cycle)]
            sig = domain_signals[i % len(domain_signals)] if domain_signals else {}

            # High-signal topics get higher hard% (proportional boost)
            strength = sig.get("signal_strength", 0)
            if strength >= 0.8:
                diff = rng.choices(["easy", "medium", "hard"], weights=[15, 45, 40])[0]
            else:
                diff = difficulty_pool[row_counter % len(difficulty_pool)]

            domain_rows.append({
                "row_id": f"{row_counter + 1:03d}",
                "domain": domain_name,
                "domain_id": domain_id,
                "subdomain_id": subdomain_id,
                "scenario_id": f"S{(i % 5) + 1}",
                "anti_pattern_id": ap.get("id", ""),
                "anti_pattern_label": ap.get("label", ""),
                "topic_hint": sig.get("topic", f"{domain_name} concepts"),
                "difficulty": diff,
                "stem_format": stem_format_pool[row_counter % len(stem_format_pool)],
                "priority": "high" if strength >= 0.7 else "normal",
            })
            row_counter += 1

        domain_rows = boost_signals(domain_rows, signals, domain_id)
        matrix.extend(domain_rows)

    # Re-number rows in final order
    for i, row in enumerate(matrix):
        row["row_id"] = f"{i + 1:03d}"

    return matrix


def main() -> None:
    if len(sys.argv) != 5:
        print(
            "Usage: phase_2_coverage.py <exam_meta_path> <forum_signals_path> <n> <output_path>",
            file=sys.stderr,
        )
        sys.exit(1)

    exam_meta_path = Path(sys.argv[1])
    forum_signals_path = Path(sys.argv[2])
    n = int(sys.argv[3])
    output_path = Path(sys.argv[4])

    exam_meta: dict = json.loads(exam_meta_path.read_text(encoding="utf-8"))
    forum_signals: dict = json.loads(forum_signals_path.read_text(encoding="utf-8"))

    # Fixed seed for reproducible matrix (same inputs → same matrix)
    rng = random.Random(42)
    matrix = build_matrix(exam_meta, forum_signals, n, rng)

    output_path.write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"coverage_matrix.json written ({len(matrix)} rows)")


if __name__ == "__main__":
    main()
