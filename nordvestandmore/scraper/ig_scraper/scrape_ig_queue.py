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

        if not events:
            print(f"  ℹ️  No events found — marking done")
            mark_scraped(page_id)
            continue

        print(f"  Found {len(events)} event(s)")

        # Monkey-patch get_recent_posts to process only this post
        def _just_this_post(L_, acct_, days_, **kwargs):
            _just_this_post._last_total_count = 1
            _just_this_post._last_latest_date = post.date_utc.date()
            return iter([post])

        original_get = ig.get_recent_posts
        ig.get_recent_posts = _just_this_post

        # Intercept first notion_create → update stub in place
        first_done = [False]
        original_create = ig.notion_create

        def _update_stub_first(ev: dict):
            if not first_done[0]:
                first_done[0] = True
                print(f"  ✏️  Filling stub: {ev.get('event_name')} | {ev.get('start_date')}")
                ig.notion_update(page_id, ev)
                key = ig.make_dedup_key(ev)
                existing[key] = page_id
                return type("R", (), {"status_code": 200})()
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
