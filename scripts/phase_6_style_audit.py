#!/usr/bin/env python3
"""Phase 6 — Style Audit.

Compares each question in questions_raw.jsonl against the style_anchor.json metrics.
Questions outside tolerance are flagged as style_fail.

Tolerance rules (configurable below):
  - stem word count outside [p10 * 0.7, p90 * 1.4]  → style_fail
  - explanation word count outside [p10 * 0.5, p90 * 1.5] → style_fail

Writes style_audit.json with per-question status: pass / style_fail.

Usage:
    python scripts/phase_6_style_audit.py <questions_raw_jsonl> <style_anchor_path> <audit_output_path>
"""

import json
import sys
from pathlib import Path


def word_count(text: str) -> int:
    return len(text.split())


def audit_question(q: dict, anchor: dict) -> dict:
    qid = q.get("id", "unknown")
    issues: list[str] = []

    stem_wc = word_count(q.get("stem", ""))
    stem_lo = anchor.get("stem_words_p10", 34) * 0.7
    stem_hi = anchor.get("stem_words_p90", 77) * 1.4
    if stem_wc < stem_lo or stem_wc > stem_hi:
        issues.append(
            f"stem length {stem_wc} words outside expected range "
            f"[{stem_lo:.0f}–{stem_hi:.0f}]"
        )

    expl_wc = word_count(q.get("explanation", ""))
    expl_lo = anchor.get("explanation_words_p10", 42) * 0.5
    expl_hi = anchor.get("explanation_words_p90", 119) * 1.5
    if expl_wc < expl_lo or expl_wc > expl_hi:
        issues.append(
            f"explanation length {expl_wc} words outside expected range "
            f"[{expl_lo:.0f}–{expl_hi:.0f}]"
        )

    if issues:
        return {"question_id": qid, "status": "style_fail", "issues": issues}
    return {"question_id": qid, "status": "pass"}


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: phase_6_style_audit.py <questions_raw_jsonl> <style_anchor_path> <audit_output_path>",
            file=sys.stderr,
        )
        sys.exit(1)

    raw_path = Path(sys.argv[1])
    anchor_path = Path(sys.argv[2])
    audit_path = Path(sys.argv[3])

    anchor: dict = json.loads(anchor_path.read_text(encoding="utf-8"))
    questions: list[dict] = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    audit = [audit_question(q, anchor) for q in questions]

    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    fails = sum(1 for r in audit if r["status"] == "style_fail")
    passed = len(audit) - fails
    print(f"style_audit.json written: {passed} pass, {fails} style_fail")


if __name__ == "__main__":
    main()
