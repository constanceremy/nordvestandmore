#!/usr/bin/env python3
"""
FB Queue Scraper
----------------
Processes Notion Events DB entries that were manually created by Constance
(via sharing from Facebook) and have not yet been scraped.

Detection:
  - Created by = Constance Remy
  - Event Link contains facebook.com
  - Scraped checkbox = false

After scraping:
  - The stub entry is updated in place with the first event's fields
  - The Scraped checkbox is ticked
  - If the post yields multiple events (multi-day), additional entries are created

Called from scrape_facebook_events.py at the start of each run.
Can also be run standalone for testing.
"""
import json
import os
import re
import sys
import time
import requests
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_facebook_events as fb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dedup import find_duplicate, get_source_priority, load_fb_to_ig_map
from fix_locations import clean_location
from auto_tag import classify_event, classify_seasonal, is_excluded_location, is_unknown_location
from locations_cache import find_location_coords

NOTION_USER_ID = "9d4906be-31d9-401a-82f4-d69e39a08865"  # Constance Remy
FB_URL_RE = re.compile(r"facebook\.com")


def find_queue_entries() -> list[dict]:
    """Query for unscraped FB stub entries created by Constance."""
    results = []
    cursor = None

    while True:
        payload: dict = {
            "filter": {
                "and": [
                    {
                        "property": "Created by",
                        "created_by": {"contains": NOTION_USER_ID},
                    },
                    {
                        "property": "Scraped",
                        "checkbox": {"equals": False},
                    },
                ]
            },
            "page_size": 100,
        }
        if cursor:
            payload["start_cursor"] = cursor

        r = requests.post(
            f"{fb.NOTION_API}/databases/{fb.NOTION_DB}/query",
            headers=fb.NOTION_HEADERS,
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        for page in data.get("results", []):
            url = page["properties"].get("Event Link", {}).get("url") or ""
            if not url:
                # Notion sometimes puts the pasted URL into the title instead of Event Link
                title_parts = page["properties"].get("Event Name", {}).get("title", [])
                title = title_parts[0]["plain_text"] if title_parts else ""
                if FB_URL_RE.search(title):
                    url = title.strip()
                    # Move URL to Event Link so the rest of the pipeline can use it
                    requests.patch(
                        f"{fb.NOTION_API}/pages/{page['id']}",
                        headers=fb.NOTION_HEADERS,
                        json={
                            "properties": {
                                "Event Link": {"url": url},
                                "Event Name": {"title": []},  # clear the title stub
                            }
                        },
                        timeout=30,
                    )
            if url and FB_URL_RE.search(url):
                results.append({"page_id": page["id"], "url": url})

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return results


def mark_scraped(page_id: str):
    requests.patch(
        f"{fb.NOTION_API}/pages/{page_id}",
        headers=fb.NOTION_HEADERS,
        json={"properties": {"Scraped": {"checkbox": True}}},
        timeout=30,
    )


def parse_fb_event_with_gemini(client, page_text: str, event_url: str) -> list[dict] | None:
    """
    Use Gemini to parse a Facebook event page into event dicts.
    Handles single-day, multi-day, and recurring (next occurrence only).
    Returns None on Gemini API failure (so caller can retry), [] if no events.
    """
    prompt = f"""Extract event information from this Facebook event page.

URL: {event_url}

Page text:
{page_text[:6000]}

Respond ONLY with valid JSON:

{{
  "events": [
    {{
      "event_name": "Name of the event",
      "organizer": "Who is organising (from 'Event by X' line, or page name)",
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM (24h format, or null if unknown)",
      "end_time": "HH:MM (24h format, or null if unknown)",
      "location": "Venue name only — no street address, postal code, or city",
      "description": "Brief summary of what the event is"
    }}
  ]
}}

Rules:
- Today's date is {datetime.now().strftime('%Y-%m-%d')}.
- For a SINGLE-DAY event, return exactly ONE entry.
- For a MULTI-DAY event (different activities on different days), return ONE entry per day/session.
- For a RECURRING event (e.g. every Tuesday), return only the NEXT upcoming occurrence.
- NEVER use a venue/location name as the event_name.
- If the description says "doors" and "show/start", use the show/start time as start_time.
- If location is a full street address, extract only the venue name (e.g. "Lygten Station").
- If NO events can be found, return {{"events": []}}.
- Respond ONLY with the JSON, no extra text."""

    try:
        from google import genai
        from google.genai import types

        fb.gemini_limiter.wait()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=4000),
        )
        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(result_text)
        return result.get("events", [])
    except Exception as e:
        # 503 / transient API failure → return None so caller skips and retries next run
        err = str(e).lower()
        if "503" in err or "unavailable" in err or "overloaded" in err:
            fb.log(f"  ⚠️  Gemini API unavailable — will retry next run: {e}")
            return None
        fb.log(f"  Gemini parse failed: {e}")
        return []


def process_queue(client, existing: dict, all_entries: list, source_mapping: dict):
    """
    Main entry point called by scrape_facebook_events.main().
    Uses the already-initialised client (Gemini) and Notion state.
    """
    fb_to_ig = load_fb_to_ig_map()

    queue = find_queue_entries()
    if not queue:
        return

    print(f"\n📋 FB Queue: {len(queue)} post(s) to process")

    for item in queue:
        page_id = item["page_id"]
        url = item["url"]
        print(f"  📘 Queue: {url}")

        # Fetch the event page text
        page_text = fb.fetch_event_page_text(url)
        if not page_text:
            print(f"  ❌ Could not fetch page — marking done to skip")
            mark_scraped(page_id)
            continue

        # Parse with Gemini
        events = parse_fb_event_with_gemini(client, page_text, url)

        if events is None:
            # Gemini API failure — leave unscraped so next run retries
            print(f"  ⚠️  Gemini failed — will retry next run")
            continue

        if not events:
            print(f"  ℹ️  No events found — marking done")
            mark_scraped(page_id)
            continue

        print(f"  Found {len(events)} event(s)")

        # Extract organiser/source from the first event
        organizer_raw = events[0].get("organizer") or fb.extract_page_name(url) or "facebook"
        # Normalise to a key similar to what scrape_page_entry uses (lowercase, no spaces)
        source = re.sub(r"[^\w]", "", organizer_raw.lower())
        ig_handle = fb_to_ig.get(source)

        # Patch stub title immediately so it's visible in Notion
        first_name = events[0].get("event_name") or ""
        if first_name:
            requests.patch(
                f"{fb.NOTION_API}/pages/{page_id}",
                headers=fb.NOTION_HEADERS,
                json={"properties": {"Event Name": {"title": [{"text": {"content": first_name}}]}}},
                timeout=30,
            )
            print(f"  ✏️  Set stub title: {first_name}")

        first_done = [False]

        for event_data in events:
            ev_name = event_data.get("event_name") or ""
            ev_date = event_data.get("event_date") or ""
            ev_time = event_data.get("start_time") or ""

            # Skip past events
            if ev_date:
                try:
                    if date.fromisoformat(ev_date) < date.today():
                        print(f"  Skipping past: {ev_name} ({ev_date})")
                        continue
                except ValueError:
                    pass

            # Clean location
            location = event_data.get("location")
            if location:
                location = clean_location(location) or location

            ev = {
                "event_name": ev_name,
                "organizer": event_data.get("organizer") or organizer_raw,
                "start_date": ev_date,
                "end_date": ev_date,
                "start_time_disp": fb.to_12h(ev_time),
                "end_time_disp": fb.to_12h(event_data.get("end_time")),
                "location": location,
                "description": event_data.get("description"),
                "source_type": "Facebook",
                "source": source,
                "url": url,
                "ig_handle": ig_handle,
                "start_time": ev_time,
                "tag": classify_event(
                    ev_name,
                    event_data.get("description", ""),
                    event_data.get("organizer", ""),
                ),
            }
            _primary = ev["tag"]
            _seasonal = classify_seasonal(ev_name, event_data.get("description", ""))
            ev["tags_list"] = ([_primary] if _primary else []) + [s for s in _seasonal if s != _primary]

            if is_excluded_location(ev.get("location", "")):
                print(f"  Skipping excluded location: {ev_name} @ {ev.get('location')}")
                continue

            if is_unknown_location(ev.get("location", "")):
                ev["review_notes"] = f"⚠️ Unknown location: {ev['location']}"

            # Cross-platform duplicate check
            dupe = find_duplicate(
                ev_name, ev_date, source, all_entries, source_mapping,
                event_location=ev.get("location", ""),
                event_time=ev_time,
                gemini_fn=fb.make_gemini_dedup_fn(client),
                resolve_coords_fn=lambda loc: find_location_coords(loc, fb.NOTION_TOKEN),
            )
            dedup_key = fb.make_dedup_key(ev)
            dedup_page_id = existing.get(dedup_key)

            merge_only = False
            if dupe and not dedup_page_id:
                current_priority = get_source_priority(url)
                dupe_priority = get_source_priority(dupe.get("url", ""))
                dedup_page_id = dupe["page_id"]
                dupe_date = (dupe.get("start_date") or "")[:10]
                dupe_src = dupe.get("source", "")
                if current_priority > dupe_priority:
                    merge_only = True
                    ev["duplicate_of"] = f"Also at: {dupe_src} ({dupe_date})"
                else:
                    # Carry over IG-specific fields from the existing entry so they aren't lost
                    if not ev.get("ig_handle") and dupe.get("ig_handle"):
                        ev["ig_handle"] = dupe["ig_handle"]
                    if not ev.get("to_tag") and dupe.get("to_tag"):
                        ev["to_tag"] = dupe["to_tag"]
                    ev["duplicate_of"] = f"Also at: {dupe_src} ({dupe_date})"
                ev["possible_duplicate"] = False
            else:
                ev["possible_duplicate"] = False

            if not first_done[0]:
                # First event from this stub — fill the stub in place
                first_done[0] = True
                if dedup_page_id and dedup_page_id != page_id:
                    # Duplicate of an existing entry — update the existing one (merge_only or full)
                    # and fill the stub as a "Possible Duplicate" marker
                    print(f"  ✏️  Filling stub (duplicate): {ev_name} | {ev_date}")
                    fb.notion_update(dedup_page_id, ev, merge_only=merge_only)
                    # Fill stub itself so the row isn't empty, and flag it
                    original = next((e for e in all_entries if e.get("page_id") == dedup_page_id), None)
                    original_name = original.get("name", "") if original else ""
                    ev["duplicate_of"] = f"Duplicate of: {original_name or dedup_page_id}"
                    fb.notion_update(page_id, ev)
                    requests.patch(
                        f"{fb.NOTION_API}/pages/{page_id}",
                        headers=fb.NOTION_HEADERS,
                        json={"properties": {"Possible Duplicate": {"checkbox": True}}},
                        timeout=30,
                    )
                else:
                    # New event — fill the stub
                    print(f"  ✏️  Filling stub: {ev_name} | {ev_date}")
                    fb.notion_update(page_id, ev, merge_only=merge_only)
                    existing[dedup_key] = page_id
                    all_entries.append({
                        "name": ev_name,
                        "start_date": ev_date,
                        "source": source,
                        "page_id": page_id,
                        "url": url,
                        "location": ev.get("location", ""),
                        "start_time": ev_time,
                        "tag": ev.get("tag", ""),
                    })
                # Set tags on stub (notion_update skips it to preserve manual edits)
                if ev.get("tags_list"):
                    requests.patch(
                        f"{fb.NOTION_API}/pages/{page_id}",
                        headers=fb.NOTION_HEADERS,
                        json={"properties": {"Tags": {"multi_select": [{"name": t} for t in ev["tags_list"]]}}},
                        timeout=30,
                    )
            else:
                # Additional events from a multi-day post
                if dedup_page_id:
                    fb.notion_update(dedup_page_id, ev, merge_only=merge_only)
                    print(f"  ✓ Updated existing: {ev_name} | {ev_date}")
                else:
                    r = fb.notion_create(ev)
                    if r.status_code == 429:
                        time.sleep(1.5)
                        r = fb.notion_create(ev)
                    try:
                        r.raise_for_status()
                        nid = r.json().get("id")
                        if nid:
                            existing[dedup_key] = nid
                            all_entries.append({
                                "name": ev_name,
                                "start_date": ev_date,
                                "source": source,
                                "page_id": nid,
                                "url": url,
                                "location": ev.get("location", ""),
                                "start_time": ev_time,
                                "tag": ev.get("tag", ""),
                            })
                        print(f"  ✅ Created: {ev_name} | {ev_date}")
                    except Exception:
                        print(f"  ❌ Create failed: {ev_name}")

            time.sleep(0.3)

        if first_done[0]:
            mark_scraped(page_id)
        else:
            # All events were past/excluded — mark done without filling stub
            print(f"  ℹ️  All events past or excluded — marking done")
            mark_scraped(page_id)

    print()


# ── Standalone entry point ──────────────────────────────────────────────────
def _load_env():
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


if __name__ == "__main__":
    _load_env()
    os.environ.setdefault("DEBUG", "1")

    if not fb.NOTION_TOKEN or not fb.NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not fb.GEMINI_API_KEY:
        sys.exit("Missing GEMINI_API_KEY")

    print("🔍 Checking Notion for queued Facebook posts...")
    queue = find_queue_entries()
    if not queue:
        print("✅ No queued posts found.")
        sys.exit(0)

    from google import genai
    client = genai.Client(api_key=fb.GEMINI_API_KEY)
    existing, all_entries = fb.notion_existing_entries()
    from dedup import load_source_mapping
    source_mapping = load_source_mapping()

    try:
        process_queue(client, existing, all_entries, source_mapping)
    finally:
        pass

    print("✅ Done.")
