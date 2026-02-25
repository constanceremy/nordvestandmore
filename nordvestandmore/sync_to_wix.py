#!/usr/bin/env python3
"""
Notion → Wix CMS Sync
─────────────────────
Reads events from the Notion database and pushes them to a Wix CMS collection.
Notion is the source of truth — edit/review events there, then sync to Wix.

Usage:
    python sync_to_wix.py              # full sync (all non-deleted, non-duplicate events)
    python sync_to_wix.py --dry-run    # preview what would be synced without pushing
    python sync_to_wix.py --clear      # remove all items from Wix collection first

Environment variables (set in .env or GitHub Secrets):
    NOTION_TOKEN          - Notion integration token
    NOTION_DATABASE_ID    - Notion database ID
    WIX_API_KEY           - Wix API key
    WIX_SITE_ID           - Wix site ID
    WIX_COLLECTION_ID     - Wix CMS collection ID (default: events_nordvest)
"""

import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime, date

# ────────────────── Load .env ──────────────────

ENV_FILE = Path(__file__).resolve().parent / ".env"

def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

load_env()

# ────────────────── Config ──────────────────

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB = os.environ.get("NOTION_DATABASE_ID", "")
NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

WIX_API_KEY = os.environ.get("WIX_API_KEY", "")
WIX_SITE_ID = os.environ.get("WIX_SITE_ID", "")
WIX_COLLECTION_ID = os.environ.get("WIX_COLLECTION_ID", "Import1")
WIX_API = "https://www.wixapis.com/wix-data/v2"
WIX_HEADERS = {
    "Authorization": WIX_API_KEY,
    "wix-site-id": WIX_SITE_ID,
    "Content-Type": "application/json",
}


def log(msg: str):
    print(f"[WIX-SYNC] {msg}")


# ────────────────── Notion: read events ──────────────────

def _extract_text(prop: dict, prop_type: str) -> str:
    """Extract text from a Notion property."""
    if prop_type == "title":
        parts = prop.get("title", [])
        return parts[0]["text"]["content"] if parts else ""
    elif prop_type == "rich_text":
        parts = prop.get("rich_text", [])
        return parts[0]["text"]["content"] if parts else ""
    elif prop_type == "select":
        sel = prop.get("select")
        return sel["name"] if sel else ""
    elif prop_type == "url":
        return prop.get("url") or ""
    elif prop_type == "date":
        d = prop.get("date")
        return d["start"] if d else ""
    elif prop_type == "checkbox":
        return prop.get("checkbox", False)
    return ""


def read_notion_events() -> list[dict]:
    """Read all publishable events from Notion (not deleted, not duplicates)."""
    events = []
    payload = {
        "page_size": 100,
        "filter": {
            "and": [
                {"property": "Deleted", "checkbox": {"equals": False}},
                {"property": "Possible Duplicate", "checkbox": {"equals": False}},
            ]
        },
        "sorts": [
            {"property": "Start Date", "direction": "ascending"},
        ],
    }

    pages_fetched = 0
    while True:
        r = requests.post(
            f"{NOTION_API}/databases/{NOTION_DB}/query",
            headers=NOTION_HEADERS, json=payload, timeout=30,
        )
        if r.status_code != 200:
            log(f"Notion query error: {r.status_code} {r.text[:200]}")
            break

        data = r.json()
        pages_fetched += 1

        for page in data.get("results", []):
            props = page.get("properties", {})
            notion_id = page["id"]

            event_name = _extract_text(props.get("Event Name", {}), "title")
            start_date = _extract_text(props.get("Start Date", {}), "date")
            end_date = ""
            date_prop = props.get("Start Date", {}).get("date")
            if date_prop and date_prop.get("end"):
                end_date = date_prop["end"]
            # Also check explicit End Date property
            if not end_date:
                end_date_prop = props.get("End Date", {})
                if end_date_prop.get("date"):
                    end_date = end_date_prop["date"].get("start", "")

            start_time = _extract_text(props.get("Start Time", {}), "rich_text")
            end_time = _extract_text(props.get("End Time", {}), "rich_text")
            location = _extract_text(props.get("Location", {}), "rich_text")
            description = _extract_text(props.get("Description", {}), "rich_text")
            tags = _extract_text(props.get("Tags", {}), "select")
            source = _extract_text(props.get("Source", {}), "rich_text")
            source_type = _extract_text(props.get("Source Type", {}), "select")
            event_link = _extract_text(props.get("Event Link", {}), "url")
            missing_fields = _extract_text(props.get("Missing fields", {}), "rich_text")
            review_notes = _extract_text(props.get("Review Notes", {}), "rich_text")
            reviewed = _extract_text(props.get("Reviewed Missing Fields", {}), "checkbox")

            # Skip events with no name or no date
            if not event_name or not start_date:
                continue

            # Skip events with missing fields or review notes unless reviewed
            if (missing_fields or review_notes) and not reviewed:
                continue

            # Skip past events (before today)
            try:
                event_date = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
                if event_date < date.today():
                    continue
            except (ValueError, TypeError):
                pass

            events.append({
                "notion_id": notion_id,
                "event_name": event_name,
                "start_date": start_date,
                "end_date": end_date,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "description": description,
                "tags": tags,
                "source": source,
                "source_type": source_type,
                "event_link": event_link,
            })

        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    log(f"Read {len(events)} publishable events from Notion ({pages_fetched} pages)")

    # Deduplicate: same event name + same date + same time = keep first only
    seen: set[tuple] = set()
    unique_events = []
    dupes_removed = 0
    for ev in events:
        key = (
            ev["event_name"].strip().lower(),
            ev["start_date"][:10],
            (ev.get("start_time") or "").strip(),
        )
        if key in seen:
            dupes_removed += 1
            continue
        seen.add(key)
        unique_events.append(ev)
    if dupes_removed:
        log(f"  Removed {dupes_removed} duplicate event(s) (same name + date + time)")
    return unique_events


# ────────────────── Wix: data operations ──────────────────

def _notion_to_wix(ev: dict) -> dict:
    """Map a Notion event dict to a Wix CMS data item."""
    wix = {
        "title": ev["event_name"],
        "eventName": ev["event_name"],
        "startDate": ev["start_date"][:10] if ev["start_date"] else "",
        "startTime": ev["start_time"],
        "endTime": ev["end_time"],
        "location": ev["location"],
        "tags": ev["tags"],
        "eventLink": ev["event_link"],
        "source": ev["source"],
        "sourceType": ev["source_type"],
        "description": ev["description"],
    }

    # Parse start date for formatted fields
    if ev["start_date"]:
        try:
            dt = datetime.strptime(ev["start_date"][:10], "%Y-%m-%d")
            # Human-readable date: "May 27, 2026"
            readable_date = dt.strftime("%B %d, %Y").replace(" 0", " ")
            wix["startDate"] = readable_date
            # Wix DATETIME format — include time for proper sorting
            time_str = (ev["start_time"] or "").strip()
            time_24h = "00:00"
            if time_str:
                # Parse time to 24h format for sorting (handles "18:00", "6:00pm", etc.)
                for fmt in ("%H:%M", "%H.%M", "%I:%M%p", "%I:%M %p", "%I%p", "%I %p"):
                    try:
                        t = datetime.strptime(time_str.lower().replace(".", ":"), fmt)
                        time_24h = t.strftime("%H:%M")
                        break
                    except ValueError:
                        continue
            wix["dateForWix"] = {"$date": dt.strftime(f"%Y-%m-%dT{time_24h}:00Z")}
            wix["startDateForWix"] = {"$date": dt.strftime(f"%Y-%m-%dT{time_24h}:00Z")}
            # Sort field: ISO format for correct chronological ordering
            wix["sortByDate"] = f"{dt.strftime('%Y-%m-%d')} {time_24h}"
            # Human-readable date+time for display
            wix["dateAndTime"] = f"{readable_date} {time_str}".strip()
        except ValueError:
            pass

    # End date
    if ev["end_date"]:
        try:
            dt = datetime.strptime(ev["end_date"][:10], "%Y-%m-%d")
            readable_end = dt.strftime("%B %d, %Y").replace(" 0", " ")
            wix["endDateForBlog"] = readable_end
            wix["endDate"] = {"$date": dt.strftime("%Y-%m-%dT00:00:00Z")}
        except ValueError:
            pass

    return wix


def wix_get_all_items() -> list[dict]:
    """Fetch all existing items from the Wix collection."""
    items = []
    offset = 0
    limit = 50

    while True:
        payload = {
            "query": {
                "filter": {},
                "paging": {"limit": limit, "offset": offset},
            }
        }
        r = requests.post(
            f"{WIX_API}/items/query",
            headers=WIX_HEADERS,
            json={"dataCollectionId": WIX_COLLECTION_ID, **payload},
            timeout=30,
        )
        if r.status_code != 200:
            log(f"Wix query error: {r.status_code} {r.text[:200]}")
            break

        data = r.json()
        batch = data.get("dataItems", [])
        items.extend(batch)

        total = data.get("pagingMetadata", {}).get("total", 0)
        offset += limit
        if offset >= total or not batch:
            break

    return items


def wix_insert_item(data_item: dict) -> bool:
    """Insert a single item into the Wix collection."""
    payload = {
        "dataCollectionId": WIX_COLLECTION_ID,
        "dataItem": {
            "data": data_item,
        },
    }
    r = requests.post(
        f"{WIX_API}/items",
        headers=WIX_HEADERS, json=payload, timeout=30,
    )
    if r.status_code >= 400:
        log(f"  Insert failed: {r.status_code} {r.text[:200]}")
        return False
    return True


def wix_remove_item(item_id: str) -> bool:
    """Remove an item from the Wix collection."""
    r = requests.delete(
        f"{WIX_API}/items/{item_id}",
        headers=WIX_HEADERS,
        params={"dataCollectionId": WIX_COLLECTION_ID},
        timeout=30,
    )
    if r.status_code >= 400:
        log(f"  Remove failed: {r.status_code} {r.text[:200]}")
        return False
    return True


def wix_bulk_remove(item_ids: list[str]) -> int:
    """Remove items in bulk from the Wix collection."""
    payload = {
        "dataCollectionId": WIX_COLLECTION_ID,
        "dataItemIds": item_ids,
    }
    r = requests.post(
        f"{WIX_API}/items/bulk-remove",
        headers=WIX_HEADERS, json=payload, timeout=60,
    )
    if r.status_code >= 400:
        log(f"  Bulk remove failed ({r.status_code}), falling back to individual deletes...")
        removed = 0
        for item_id in item_ids:
            if wix_remove_item(item_id):
                removed += 1
            time.sleep(0.1)
        return removed
    return len(item_ids)


def wix_clear_collection():
    """Remove ALL items from the Wix collection (loops until empty)."""
    total_removed = 0
    pass_num = 0

    while True:
        pass_num += 1
        # Always fetch from offset 0 since we're deleting
        payload = {
            "query": {
                "filter": {},
                "paging": {"limit": 100, "offset": 0},
            }
        }
        r = requests.post(
            f"{WIX_API}/items/query",
            headers=WIX_HEADERS,
            json={"dataCollectionId": WIX_COLLECTION_ID, **payload},
            timeout=30,
        )
        if r.status_code != 200:
            log(f"  Query error during clear: {r.status_code}")
            break

        data = r.json()
        batch = data.get("dataItems", [])
        remaining = data.get("pagingMetadata", {}).get("total", 0)

        if not batch:
            break

        log(f"  Pass {pass_num}: removing {len(batch)} items ({remaining} remaining)...")
        ids = [item.get("id") or item.get("_id") for item in batch if item.get("id") or item.get("_id")]
        removed = wix_bulk_remove(ids)
        total_removed += removed
        time.sleep(0.5)  # brief pause between passes

    log(f"Cleared {total_removed} items from Wix collection")


# ────────────────── Sync logic ──────────────────

def sync(dry_run: bool = False):
    """
    Full-replace sync: clear Wix collection, then insert all current events.
    Always syncs events from today onwards. No duplicates possible.
    """
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not WIX_API_KEY or not WIX_SITE_ID:
        sys.exit("Missing WIX_API_KEY or WIX_SITE_ID")

    # 1. Read from Notion (today onwards, not deleted, not duplicates)
    notion_events = read_notion_events()
    if not notion_events:
        log("No events to sync")
        return

    # 2. Clear everything in Wix
    if dry_run:
        wix_items = wix_get_all_items()
        log(f"[DRY-RUN] Would clear {len(wix_items)} existing items from Wix")
        log(f"[DRY-RUN] Would insert {len(notion_events)} events")
        for ev in notion_events[:10]:
            log(f"  [DRY-RUN] {ev['event_name']} ({ev['start_date']})")
        if len(notion_events) > 10:
            log(f"  [DRY-RUN] ... and {len(notion_events) - 10} more")
        return

    wix_clear_collection()

    # 3. Insert all events
    log(f"Inserting {len(notion_events)} events into Wix...")
    inserted = 0
    for i, ev in enumerate(notion_events, start=1):
        wix_data = _notion_to_wix(ev)
        wix_data["sortByDate"] = str(i).zfill(5)
        if wix_insert_item(wix_data):
            inserted += 1
        if i % 50 == 0:
            log(f"  Progress: {i}/{len(notion_events)}")
        time.sleep(0.15)

    log(f"✅ Sync complete: {inserted} events pushed to Wix")


def _extract_wix_item_date(item_data: dict) -> date | None:
    """Try to extract a date from a Wix item, checking multiple possible field names."""
    import re as _re

    # Try various date field names (Wix may camelCase or snake_case them)
    for field in ("dateForWix", "date_for_wix", "startDateForWix", "start_date_for_wix"):
        val = item_data.get(field)
        if isinstance(val, dict):
            raw = val.get("$date", "")
            if raw and len(raw) >= 10:
                try:
                    return date.fromisoformat(raw[:10])
                except ValueError:
                    pass
        elif isinstance(val, str) and len(val) >= 10:
            try:
                return date.fromisoformat(val[:10])
            except ValueError:
                pass

    # Try readable startDate: "February 25, 2026"
    for field in ("startDate", "start_date"):
        val = item_data.get(field, "")
        if not val or not isinstance(val, str):
            continue
        # Try "Month Day, Year" format
        try:
            return datetime.strptime(val, "%B %d, %Y").date()
        except (ValueError, TypeError):
            pass
        # Try ISO format
        try:
            return date.fromisoformat(val[:10])
        except (ValueError, TypeError):
            pass

    # Last resort: scan all values for ISO date patterns
    for key, val in item_data.items():
        if isinstance(val, dict) and "$date" in val:
            raw = val["$date"]
            if raw and len(raw) >= 10:
                try:
                    return date.fromisoformat(raw[:10])
                except ValueError:
                    pass

    return None


def sync_today(dry_run: bool = False):
    """
    Quick sync: only replace today's events in Wix.
    1. Reads today's events from Notion
    2. Deletes only today's events from Wix
    3. Re-inserts today's events from Notion
    Much faster than a full sync — useful for quick corrections.
    """
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not WIX_API_KEY or not WIX_SITE_ID:
        sys.exit("Missing WIX_API_KEY or WIX_SITE_ID")

    today_obj = date.today()
    today_str = today_obj.isoformat()
    log(f"⚡ Quick sync: today's events only ({today_str})")

    # 1. Read today's events from Notion
    all_events = read_notion_events()
    today_events = [
        ev for ev in all_events
        if ev.get("start_date", "")[:10] == today_str
    ]
    log(f"Found {len(today_events)} event(s) for today in Notion")

    # 2. Find and remove today's events + any past events from Wix
    wix_items = wix_get_all_items()
    log(f"Fetched {len(wix_items)} total item(s) from Wix")

    # Build a set of today's event names for fallback matching
    today_event_names = {
        ev["event_name"].strip().lower()
        for ev in today_events
        if ev.get("event_name")
    }

    remove_ids = []
    past_count = 0
    today_count = 0
    name_match_count = 0
    for item in wix_items:
        item_data = item.get("data", {})
        item_id = item.get("id") or item.get("_id")
        if not item_id:
            continue

        item_date = _extract_wix_item_date(item_data)

        if item_date is not None:
            if item_date < today_obj:
                remove_ids.append(item_id)
                past_count += 1
                continue
            elif item_date == today_obj:
                remove_ids.append(item_id)
                today_count += 1
                continue

        # Fallback: match by event name (catches items where date parsing failed)
        item_name = (item_data.get("eventName") or item_data.get("title") or "").strip().lower()
        if item_name and item_name in today_event_names and item_id not in remove_ids:
            remove_ids.append(item_id)
            name_match_count += 1

    log(f"Found {today_count} today's + {past_count} past + {name_match_count} name-matched item(s) to remove from Wix")

    if dry_run:
        log(f"[DRY-RUN] Would remove {len(remove_ids)} item(s) from Wix ({today_count} today + {past_count} past + {name_match_count} name-matched)")
        log(f"[DRY-RUN] Would insert {len(today_events)} today's event(s)")
        for ev in today_events:
            log(f"  [DRY-RUN] {ev['event_name']} ({ev['start_time'] or '?'})")
        return

    if remove_ids:
        log(f"Removing {len(remove_ids)} item(s) from Wix ({today_count} today + {past_count} past + {name_match_count} name-matched)...")
        removed = wix_bulk_remove(remove_ids)
        log(f"  Removed {removed} item(s)")
        time.sleep(0.5)
    else:
        log("No items to remove from Wix")

    # 3. Insert today's events
    if not today_events:
        log("No events for today to insert")
        return

    # Figure out the sort position — today's events should come first
    # Use "00001", "00002", etc. since they're the earliest date
    log(f"Inserting {len(today_events)} today's event(s) into Wix...")
    inserted = 0
    for i, ev in enumerate(today_events, start=1):
        wix_data = _notion_to_wix(ev)
        wix_data["sortByDate"] = str(i).zfill(5)
        if wix_insert_item(wix_data):
            inserted += 1
        time.sleep(0.15)

    log(f"⚡ Quick sync done: {inserted} today's event(s) pushed to Wix")


# ────────────────── CLI ──────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    today_only = "--today" in sys.argv

    if dry_run:
        log("Dry-run mode — no changes will be made to Wix")

    if today_only:
        sync_today(dry_run=dry_run)
    else:
        sync(dry_run=dry_run)


if __name__ == "__main__":
    main()
