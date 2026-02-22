#!/usr/bin/env python3
"""
Cleanup exact duplicates: same name + same date + same URL + same source.
Keeps the oldest entry, deletes the rest.

Usage:
    python cleanup_duplicates.py            # dry run
    python cleanup_duplicates.py --delete   # actually delete
"""
import json
import os
import sys
import time
import requests
from collections import defaultdict
from pathlib import Path

# Load .env
env_file = Path(__file__).resolve().parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB = os.environ.get("NOTION_DATABASE_ID", "")
NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def fetch_all_entries() -> list[dict]:
    entries = []
    payload: dict = {"page_size": 100}
    pages_fetched = 0
    while True:
        r = requests.post(
            f"{NOTION_API}/databases/{NOTION_DB}/query",
            headers=NOTION_HEADERS, json=payload, timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            name_parts = props.get("Name", {}).get("title", [])
            name = name_parts[0]["text"]["content"] if name_parts else ""
            date_obj = props.get("Start Date", {}).get("date")
            start_date = date_obj["start"] if date_obj else ""
            url_val = props.get("URL", {}).get("url", "") or ""
            source_parts = props.get("Source", {}).get("rich_text", [])
            source = source_parts[0]["text"]["content"] if source_parts else ""
            entries.append({
                "page_id": page["id"],
                "name": name,
                "start_date": start_date,
                "url": url_val,
                "source": source,
                "created_time": page.get("created_time", ""),
            })
        pages_fetched += 1
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
        if pages_fetched >= 200:
            break
    return entries


def find_exact_duplicates(entries: list[dict]) -> list[dict]:
    """Find entries with identical (name, start_date, url, source). Keep oldest."""
    groups: dict[tuple, list] = defaultdict(list)
    for entry in entries:
        key = (
            entry["name"].strip().lower(),
            entry["start_date"],
            entry["url"].strip().rstrip("/"),
            entry["source"].strip().lower(),
        )
        if key[0] and key[1]:
            groups[key].append(entry)

    to_delete = []
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        group.sort(key=lambda e: e["created_time"])
        # Keep first (oldest), delete the rest
        to_delete.extend(group[1:])
    return to_delete


def delete_page(page_id: str) -> bool:
    r = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"archived": True},
        timeout=30,
    )
    return r.status_code < 400


def main():
    dry_run = "--delete" not in sys.argv
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID in .env")

    print("📥 Fetching all Notion entries...")
    entries = fetch_all_entries()
    print(f"   Found {len(entries)} total entries")

    print("🔍 Finding exact duplicates (same name + date + URL + source)...")
    to_delete = find_exact_duplicates(entries)

    if not to_delete:
        print("   ✅ No exact duplicates found!")
        return

    print(f"   Found {len(to_delete)} exact duplicate(s) to remove\n")

    for d in to_delete[:20]:
        print(f"   🗑️  {d['name'][:50]:<50} | {d['start_date']} | {d['source']}")
    if len(to_delete) > 20:
        print(f"   ... and {len(to_delete) - 20} more")

    if dry_run:
        print(f"\n⚠️  DRY RUN — run with --delete to remove {len(to_delete)} duplicate(s)")
    else:
        print(f"\n🗑️  Deleting {len(to_delete)} duplicate(s)...")
        deleted = 0
        for i, d in enumerate(to_delete, 1):
            if delete_page(d["page_id"]):
                deleted += 1
            else:
                print(f"   ⚠️  Failed: {d['name']} ({d['start_date']})")
            if i % 50 == 0:
                print(f"   ... {i}/{len(to_delete)}")
            time.sleep(0.3)
        print(f"   ✅ Deleted {deleted}/{len(to_delete)} duplicates")


if __name__ == "__main__":
    main()
