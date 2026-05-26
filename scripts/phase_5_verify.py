#!/usr/bin/env python3
"""Phase 5 — Citation Verification.

For each question in questions_raw.jsonl, verifies that the source anchor_value
is present in the page text at the source URL. Uses Tavily Extract to handle SPAs
(e.g. docs.anthropic.com is React-rendered).

Writes anchor_report.json with per-question status: verified / not_found / error / skipped.
Never raises — pipeline continues regardless of outcome.

Usage:
    python scripts/phase_5_verify.py <questions_raw_jsonl> <anchor_report_path>

Requires TAVILY_API_KEY environment variable.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
REQUEST_TIMEOUT = 20  # seconds


def tavily_extract(url: str, api_key: str) -> str | None:
    """Fetch rendered page text via Tavily Extract API. Returns text or None on error."""
    payload = json.dumps({"urls": [url]}).encode()
    req = urllib.request.Request(
        TAVILY_EXTRACT_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            if results:
                return results[0].get("raw_content", "")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass
    return None


def verify_question(q: dict, api_key: str) -> dict:
    qid = q.get("id", "unknown")
    sources: list[dict] = q.get("sources", [])

    if not sources:
        return {"question_id": qid, "status": "skipped", "reason": "no sources"}

    all_verified = True
    unverified: list[str] = []

    for source in sources:
        url = source.get("url", "")
        anchor_value = source.get("anchor_value", "")

        if not url or not anchor_value:
            continue

        page_text = tavily_extract(url, api_key)
        if page_text is None:
            all_verified = False
            unverified.append(f"{url} (fetch error)")
            continue

        if anchor_value not in page_text:
            all_verified = False
            unverified.append(f"{url} (anchor not found: {anchor_value[:60]!r})")

    if not all_verified:
        return {
            "question_id": qid,
            "status": "not_found",
            "unverified_sources": unverified,
        }

    return {"question_id": qid, "status": "verified"}


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: phase_5_verify.py <questions_raw_jsonl> <anchor_report_path>",
            file=sys.stderr,
        )
        sys.exit(1)

    raw_path = Path(sys.argv[1])
    report_path = Path(sys.argv[2])

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        print(
            "WARNING: TAVILY_API_KEY not set — marking all citations as unverified",
            file=sys.stderr,
        )

    questions: list[dict] = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    report: list[dict] = []
    for q in questions:
        if not api_key:
            report.append(
                {"question_id": q.get("id", "unknown"), "status": "skipped", "reason": "no api key"}
            )
        else:
            report.append(verify_question(q, api_key))

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    verified = sum(1 for r in report if r["status"] == "verified")
    not_found = sum(1 for r in report if r["status"] == "not_found")
    skipped = sum(1 for r in report if r["status"] == "skipped")
    print(f"anchor_report.json written: {verified} verified, {not_found} not_found, {skipped} skipped")


if __name__ == "__main__":
    main()
