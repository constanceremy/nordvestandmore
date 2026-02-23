#!/usr/bin/env python3
"""
One-off script to retag all existing events in the Notion database.
Reads every entry, runs auto_tag.classify_event() on its name + description,
and updates the Tags property if a tag is found.

Usage:
    python retag_all.py              # dry run (show what would change)
    python retag_all.py --apply      # actually update Notion
"""
import os
import sys
import time
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Load .env
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

from auto_tag import classify_event

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB = os.environ.get("NOTION_DATABASE_ID", "")
NOTION_API = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def fetch_all_entries() -> list[dict]:
    """Fetch all entries from the Notion database."""
    entries = []
    payload: dict = {"page_size": 100}
    pages_fetched = 0

    while True:
        r = requests.post(
            f"{NOTION_API}/databases/{NOTION_DB}/query",
            headers=HEADERS, json=payload, timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        for page in data.get("results", []):
            props = page.get("properties", {})

            name_parts = props.get("Event Name", {}).get("title", [])
            name = name_parts[0]["text"]["content"] if name_parts else ""

            desc_parts = props.get("Description", {}).get("rich_text", [])
            description = desc_parts[0]["text"]["content"] if desc_parts else ""

            org_parts = props.get("Organizer", {}).get("rich_text", [])
            organizer = org_parts[0]["text"]["content"] if org_parts else ""

            # Current tag
            tag_prop = props.get("Tags", {}).get("select")
            current_tag = tag_prop["name"] if tag_prop else None

            entries.append({
                "page_id": page["id"],
                "name": name,
                "description": description,
                "organizer": organizer,
                "current_tag": current_tag,
            })

        pages_fetched += 1
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
        if pages_fetched >= 200:
            break

    return entries


def update_tag(page_id: str, tag: str) -> bool:
    """Update the Tags select property on a Notion page."""
    payload = {
        "properties": {
            "Tags": {"select": {"name": tag}},
        }
    }
    resp = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=HEADERS, json=payload, timeout=30,
    )
    if resp.status_code == 429:
        time.sleep(1.5)
        resp = requests.patch(
            f"{NOTION_API}/pages/{page_id}",
            headers=HEADERS, json=payload, timeout=30,
        )
    return resp.status_code < 400


def main():
    apply = "--apply" in sys.argv
    mode = "APPLYING" if apply else "DRY RUN"

    print(f"🏷️  Retag All Events ({mode})")
    print("=" * 50)
    print()

    print("📥 Fetching all entries from Notion...")
    entries = fetch_all_entries()
    print(f"   Found {len(entries)} entries")
    print()

    would_tag = 0
    would_change = 0
    already_correct = 0
    no_tag = 0
    errors = 0

    for i, entry in enumerate(entries):
        new_tag = classify_event(
            entry["name"],
            entry["description"],
            entry["organizer"],
        )

        if not new_tag:
            no_tag += 1
            continue

        if entry["current_tag"] == new_tag:
            already_correct += 1
            continue

        if entry["current_tag"]:
            action = f"CHANGE {entry['current_tag']} → {new_tag}"
            would_change += 1
        else:
            action = f"TAG → {new_tag}"
            would_tag += 1

        print(f"  {action}: {entry['name'][:60]}")

        if apply:
            ok = update_tag(entry["page_id"], new_tag)
            if not ok:
                print(f"    ❌ Failed to update!")
                errors += 1
            time.sleep(0.3)  # Rate limiting

    print()
    print("=" * 50)
    print(f"  Total entries:     {len(entries)}")
    print(f"  Already correct:   {already_correct}")
    print(f"  Would tag (new):   {would_tag}")
    print(f"  Would change:      {would_change}")
    print(f"  No tag matched:    {no_tag}")
    if errors:
        print(f"  ❌ Errors:         {errors}")
    print("=" * 50)

    if not apply and (would_tag + would_change) > 0:
        print()
        print("👆 This was a dry run. To apply changes, run:")
        print("   python retag_all.py --apply")


if __name__ == "__main__":
    main()
