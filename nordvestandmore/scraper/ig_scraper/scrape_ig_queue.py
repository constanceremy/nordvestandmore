#!/usr/bin/env python3
"""
IG Queue Scraper
----------------
Processes Notion Events DB entries that were manually created by Constance
(via sharing from Instagram) and have not yet been scraped.

Detection:
  - Created by = Constance Remy
  - Event Link contains instagram.com/p/
  - Scraped checkbox = false

After scraping:
  - The stub entry is updated in place with the first event's fields
  - The Scraped checkbox is ticked
  - If the post yields multiple events, additional entries are created

Called from drip_scrape.py at the start of each batch run.
Can also be run standalone for testing.
"""
import os
import re
import sys
import tempfile
import shutil
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_instagram_events as ig
from locations_cache import find_location_coords

NOTION_USER_ID = "9d4906be-31d9-401a-82f4-d69e39a08865"  # Constance Remy
IG_POST_RE = re.compile(r"instagram\.com/p/([A-Za-z0-9_-]+)")


def find_queue_entries() -> list[dict]:
    """Query for unscraped IG stub entries created by Constance."""
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
            f"{ig.NOTION_API}/databases/{ig.NOTION_DB}/query",
            headers=ig.NOTION_HEADERS,
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        for page in data.get("results", []):
            url = page["properties"].get("Event Link", {}).get("url") or ""
            if IG_POST_RE.search(url):
                results.append({"page_id": page["id"], "url": url})

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return results


def mark_scraped(page_id: str):
    requests.patch(
        f"{ig.NOTION_API}/pages/{page_id}",
        headers=ig.NOTION_HEADERS,
        json={"properties": {"Scraped": {"checkbox": True}}},
        timeout=30,
    )


def process_queue(L, client, existing, all_entries, source_mapping, tmp_dir):
    """
    Main entry point called by drip_scrape.py.
    Uses already-initialised L (instaloader), client (Gemini), and Notion state.
    """
    import instaloader as _instaloader

    queue = find_queue_entries()
    if not queue:
        return

    print(f"\n📋 IG Queue: {len(queue)} post(s) to process")

    for item in queue:
        page_id = item["page_id"]
        url = item["url"]
        m = IG_POST_RE.search(url)
        if not m:
            continue
        shortcode = m.group(1)
        print(f"  📸 Queue: {url}")

        try:
            post = _instaloader.Post.from_shortcode(L.context, shortcode)
        except Exception as e:
            print(f"  ❌ Could not fetch post: {e} — marking done to skip")
            mark_scraped(page_id)
            continue

        account = post.owner_username
        image_paths = ig.download_all_images(post, tmp_dir)
        events = ig.analyze_post_with_gemini(
            client, post.caption or "", image_paths, account,
            post_date=post.date_utc.date()
        )

        if events is None:
            # Gemini API failure (503 etc) — leave unscraped so next run retries
            print(f"  ⚠️  Gemini failed — will retry next run")
            continue

        if not events:
            print(f"  ℹ️  No events found — marking done")
            mark_scraped(page_id)
            continue

        print(f"  Found {len(events)} event(s)")

        # Always overwrite the stub with the first event's data from Gemini.
        # We do this unconditionally — even if the event is already in Notion
        # via a different entry (dedup case), the stub's title/fields should
        # reflect what Gemini extracted, not the raw Instagram caption.
        # We patch just the title here; scrape_account fills the rest.
        first_name = events[0].get("event_name") or ""
        if first_name:
            requests.patch(
                f"{ig.NOTION_API}/pages/{page_id}",
                headers=ig.NOTION_HEADERS,
                json={"properties": {"Event Name": {"title": [{"text": {"content": first_name}}]}}},
                timeout=30,
            )
            print(f"  ✏️  Set stub title: {first_name}")

        # Monkey-patch get_recent_posts to process only this post
        def _just_this_post(L_, acct_, days_, **kwargs):
            _just_this_post._last_total_count = 1
            _just_this_post._last_latest_date = post.date_utc.date()
            return iter([post])

        original_get = ig.get_recent_posts
        ig.get_recent_posts = _just_this_post

        # Intercept first notion_create → update stub in place instead of
        # creating a new entry. This handles new events (not yet in Notion).
        first_done = [False]
        original_create = ig.notion_create

        def _update_stub_first(ev: dict):
            if not first_done[0]:
                first_done[0] = True
                print(f"  ✏️  Filling stub fields: {ev.get('event_name')} | {ev.get('start_date')}")
                ig.notion_update(page_id, ev)
                # Set tag separately — notion_update skips it to preserve manual edits,
                # but stubs are new and have no tag yet
                if ev.get("tags_list"):
                    requests.patch(
                        f"{ig.NOTION_API}/pages/{page_id}",
                        headers=ig.NOTION_HEADERS,
                        json={"properties": {"Tags": {"multi_select": [{"name": t} for t in ev["tags_list"]]}}},
                        timeout=30,
                    )
                key = ig.make_dedup_key(ev)
                existing[key] = page_id
                # Return a mock response that satisfies raise_for_status() and .json()
                class _FakeResp:
                    status_code = 200
                    def raise_for_status(self): pass
                    def json(self): return {"id": page_id}
                return _FakeResp()
            return original_create(ev)

        ig.notion_create = _update_stub_first

        try:
            ig.scrape_account(
                account, L, client, existing, all_entries, source_mapping, tmp_dir,
                auto_login_retry=False,
            )
        finally:
            ig.get_recent_posts = original_get
            ig.notion_create = original_create

        if first_done[0]:
            # Stub was filled in — mark as scraped
            mark_scraped(page_id)
        else:
            # notion_create was never called = event already existed in Notion via dedup.
            # Fill the stub in place with the first event's data so the row is complete,
            # set Possible Duplicate so it's visually flagged, then mark scraped.
            # No new row is created.
            print(f"  ✏️  Event already in Notion — filling stub in place and marking done")

            # Find the original entry: try URL-based key first, then cross-platform
            dedup_key = ig.make_dedup_key(events[0])
            original_page_id = existing.get(dedup_key)

            if not original_page_id:
                # Cross-platform: event may exist from a different source (website, FB)
                xdupe = ig.find_duplicate(
                    events[0].get("event_name", ""),
                    events[0].get("start_date", ""),
                    account,
                    all_entries,
                    source_mapping,
                    events[0].get("location", ""),
                    events[0].get("start_time", ""),
                    resolve_coords_fn=lambda loc: find_location_coords(loc, ig.NOTION_TOKEN),
                )
                if xdupe:
                    original_page_id = xdupe.get("page_id")

            if original_page_id:
                original = next((e for e in all_entries if e.get("page_id") == original_page_id), None)
                original_name = original.get("name", "") if original else ""
                events[0]["duplicate_of"] = f"Duplicate of: {original_name or original_page_id}"

            # Compute tags if not already set (events[0] is raw Gemini output)
            if "tags_list" not in events[0]:
                from auto_tag import classify_event, classify_seasonal
                _primary = classify_event(
                    events[0].get("event_name", ""),
                    events[0].get("description", ""),
                    account,
                )
                _seasonal = classify_seasonal(events[0].get("event_name", ""), events[0].get("description", ""))
                events[0]["tags_list"] = ([_primary] if _primary else []) + [s for s in _seasonal if s != _primary]

            ig.notion_update(page_id, events[0])

            # Set Possible Duplicate checkbox so the row is visually flagged in Notion
            requests.patch(
                f"{ig.NOTION_API}/pages/{page_id}",
                headers=ig.NOTION_HEADERS,
                json={"properties": {"Possible Duplicate": {"checkbox": True}}},
                timeout=30,
            )
            if events[0].get("tags_list"):
                requests.patch(
                    f"{ig.NOTION_API}/pages/{page_id}",
                    headers=ig.NOTION_HEADERS,
                    json={"properties": {"Tags": {"multi_select": [{"name": t} for t in events[0]["tags_list"]]}}},
                    timeout=30,
                )
            mark_scraped(page_id)

    print()


# ── Standalone entry point ──────────────────────────────────────────────────
def _load_env():
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
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

    if not ig.NOTION_TOKEN or not ig.NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not ig.GEMINI_API_KEY:
        sys.exit("Missing GEMINI_API_KEY")

    print("🔍 Checking Notion for queued Instagram posts...")
    queue = find_queue_entries()
    if not queue:
        print("✅ No queued posts found.")
        sys.exit(0)

    L = ig.setup_instaloader()
    ig_username = os.environ.get("IG_USERNAME", "nvandmore_events")
    session_file = Path.home() / ".config" / "instaloader" / f"session-{ig_username}"
    if session_file.exists():
        try:
            L.load_session_from_file(ig_username, str(session_file))
            print(f"✅ Session loaded for @{ig_username}")
        except Exception as e:
            print(f"⚠️  Session load failed: {e}")

    client = ig.setup_gemini()
    existing, all_entries = ig.notion_existing_entries()
    source_mapping = ig.load_source_mapping()
    tmp_dir = tempfile.mkdtemp(prefix="ig_queue_")

    try:
        process_queue(L, client, existing, all_entries, source_mapping, tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("✅ Done.")
