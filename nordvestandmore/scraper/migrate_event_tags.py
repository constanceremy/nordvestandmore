#!/usr/bin/env python3
"""
One-shot migration: copy Events DB `Tags` values into `Tag List` for any
event where `Tag List` is currently empty.

Non-destructive:
  - Events that already have at least one Tag List value are SKIPPED
  - Events with no `Tags` are left empty (nothing to copy)
  - The old `Tags` property is NOT modified or deleted

The website's getEvents() already reads Tag List first and falls back
to Tags, so events with newly-populated Tag List values pick up
automatically after the script runs.

Usage:
    cd nordvestandmore/scraper
    python3 migrate_event_tags.py            # actually write
    python3 migrate_event_tags.py --dry-run  # show what would change
"""

import os
import sys
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

# Load env from website/.env.local (NOTION_TOKEN, NOTION_EVENTS_DB_ID)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / "website" / ".env.local")
except ImportError:
    env_file = Path(__file__).resolve().parent.parent / "website" / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
EVENTS_DB_ID = os.environ.get("NOTION_EVENTS_DB_ID") or os.environ.get("NOTION_DATABASE_ID", "")

if not NOTION_TOKEN or not EVENTS_DB_ID:
    sys.exit("❌ Missing NOTION_TOKEN or NOTION_EVENTS_DB_ID. Check website/.env.local")

DRY_RUN = "--dry-run" in sys.argv

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type":  "application/json",
    "Notion-Version": "2022-06-28",
}


def _request(url, payload, method, retries=4):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), headers=HEADERS, method=method
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s
            print(f"    ⏳ network blip ({type(e).__name__}); retrying in {wait}s…")
            time.sleep(wait)
    raise last_err  # type: ignore[misc]


def _post(url, payload):
    return _request(url, payload, "POST")


def _patch(url, payload):
    return _request(url, payload, "PATCH")


def fetch_all_event_pages():
    """Page through the Events DB and yield each page object."""
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        data = _post(
            f"https://api.notion.com/v1/databases/{EVENTS_DB_ID}/query",
            payload,
        )
        for page in data.get("results", []):
            yield page
        if not data.get("has_more"):
            return
        cursor = data.get("next_cursor")


def extract_existing_tag_list(props):
    prop = props.get("Tag List", {})
    if prop.get("type") == "multi_select":
        return [opt["name"] for opt in prop.get("multi_select", [])]
    return []


def extract_legacy_tags(props):
    """Read the old `Tags` property, whether it's select or multi_select."""
    prop = props.get("Tags", {})
    t = prop.get("type")
    if t == "multi_select":
        return [opt["name"] for opt in prop.get("multi_select", [])]
    if t == "select":
        s = prop.get("select")
        return [s["name"]] if s else []
    return []


def title_of(props):
    for key in ("Name", "Title", "Event Name"):
        prop = props.get(key)
        if prop and prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    return "(untitled)"


def main():
    print(f"📋 Querying Events DB ({EVENTS_DB_ID})…")
    if DRY_RUN:
        print("   🧪 DRY RUN — no writes will be made\n")

    n_total = 0
    n_skipped_has_list = 0
    n_skipped_no_tags = 0
    n_updated = 0

    for page in fetch_all_event_pages():
        n_total += 1
        props = page.get("properties", {})
        title = title_of(props)

        existing_list = extract_existing_tag_list(props)
        if existing_list:
            n_skipped_has_list += 1
            continue

        legacy = extract_legacy_tags(props)
        if not legacy:
            n_skipped_no_tags += 1
            continue

        print(f"  → {title!r}: copy {legacy} → Tag List")

        if not DRY_RUN:
            try:
                _patch(
                    f"https://api.notion.com/v1/pages/{page['id']}",
                    {
                        "properties": {
                            "Tag List": {
                                "multi_select": [{"name": t} for t in legacy],
                            }
                        }
                    },
                )
                time.sleep(0.35)  # be polite to the Notion rate limit
            except urllib.error.HTTPError as e:
                print(f"    ⚠️  HTTP {e.code}: {e.read().decode()[:200]}")
                continue
        n_updated += 1

    print()
    print(f"📊 Done. Events seen: {n_total}")
    print(f"   ✅ Updated:            {n_updated}")
    print(f"   ⏭️  Already had list:   {n_skipped_has_list}")
    print(f"   ⏭️  No legacy tags:     {n_skipped_no_tags}")
    if DRY_RUN:
        print("\n   (dry run — re-run without --dry-run to apply)")


if __name__ == "__main__":
    main()
