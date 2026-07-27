#!/usr/bin/env python3
"""Run scraper, diff against previous data, generate report, send email."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from scraper import run_all, now_iso
from notifier import send_email_digest

DATA_DIR = Path(__file__).resolve().parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"


def load_json(path: Path) -> list[dict]:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def diff_jobs(previous: list[dict], current: list[dict]) -> dict:
    """Compare two job lists; return added, removed, unchanged sets."""
    prev_map = {j["id"]: j for j in previous}
    curr_map = {j["id"]: j for j in current}

    prev_ids = set(prev_map.keys())
    curr_ids = set(curr_map.keys())

    added_ids = curr_ids - prev_ids
    removed_ids = prev_ids - curr_ids
    unchanged_ids = curr_ids & prev_ids

    added = [curr_map[jid] for jid in added_ids]
    removed = [prev_map[jid] for jid in removed_ids]
    unchanged = [curr_map[jid] for jid in unchanged_ids]

    return {
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "total_current": len(current),
        "total_previous": len(previous),
    }


def format_summary(diff: dict) -> str:
    lines = []
    lines.append(f"AI/ML Jobs in Singapore — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Total active listings: {diff['total_current']} (was {diff['total_previous']})")
    lines.append("")

    if diff["added"]:
        lines.append(f"=== NEW ({len(diff['added'])}) ===")
        for j in sorted(diff["added"], key=lambda x: x["company"]):
            lines.append(f"  + [{j['company']}] {j['title']} — {j['location']}")
            lines.append(f"    {j['url']}")
        lines.append("")

    if diff["removed"]:
        lines.append(f"=== REMOVED ({len(diff['removed'])}) ===")
        for j in sorted(diff["removed"], key=lambda x: x["company"]):
            lines.append(f"  - [{j['company']}] {j['title']} — {j['location']}")
        lines.append("")

    if not diff["added"] and not diff["removed"]:
        lines.append("No changes since last run.")

    lines.append("---")
    lines.append(f"Full data: {JOBS_FILE}")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("AI/ML Job Tracker — Singapore")
    print("=" * 60)

    # Load previous data
    previous = load_json(JOBS_FILE)
    print(f"Previous snapshot: {len(previous)} jobs")

    # Run all scrapers
    current = run_all()

    # Save current snapshot
    save_json(JOBS_FILE, current)
    print(f"Saved {len(current)} jobs to {JOBS_FILE}")

    # Diff
    diff = diff_jobs(previous, current)
    summary = format_summary(diff)
    print("\n" + summary)

    # Send email if configured
    send_email = os.environ.get("JOB_TRACKER_SEND_EMAIL", "").lower() == "true"
    if send_email and (diff["added"] or diff["removed"]):
        print("\nSending email digest...")
        try:
            send_email_digest(
                subject=f"AI Jobs SG: {len(diff['added'])} new, {len(diff['removed'])} removed",
                body=summary,
            )
            print("Email sent.")
        except Exception as e:
            print(f"Email failed: {e}")
    elif send_email:
        print("\nNo changes, skipping email.")

    # Write summary to file for git commit message / artifact
    summary_file = DATA_DIR / "summary.txt"
    save_json(DATA_DIR / "diff.json", diff)
    with open(summary_file, "w") as f:
        f.write(summary)
    print(f"\nSummary saved to {summary_file}")

    return diff


if __name__ == "__main__":
    main()
