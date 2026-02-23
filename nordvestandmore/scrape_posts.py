#!/usr/bin/env python3
"""
Manual Instagram Post Scraper
------------------------------
Give it one or more Instagram post URLs, and it will:
1. Log in with Instaloader (using IG_USERNAME / IG_PASSWORD)
2. Download all images (including carousel slides)
3. Use Gemini to extract event details
4. Push to Notion

Usage:
    python3 scrape_posts.py <url1> [url2] [url3] ...
    python3 scrape_posts.py   # interactive mode — paste URLs one per line, blank line to start

Env vars required (same as ig_scraper):
    NOTION_TOKEN, NOTION_DATABASE_ID, GEMINI_API_KEY,
    IG_USERNAME, IG_PASSWORD
"""
import getpass
import logging
import os
import re
import sys
import time
import json
import tempfile
import shutil
from datetime import date, datetime

import instaloader
from google import genai
from google.genai import types
from PIL import Image
import requests

# Suppress noisy instaloader warnings (403 high-quality image fetch)
logging.getLogger("instaloader").setLevel(logging.ERROR)

# Add parent dir for shared modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedup import load_source_mapping, find_duplicate
from auto_tag import classify_event, is_not_event, is_deal, should_skip_entirely, is_excluded_location, is_unknown_location
from hours_db import push_to_hours_db
from deals_db import push_to_deals_db
from fix_locations import clean_location

# -------------------- CONFIG --------------------
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB = os.environ.get("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = None  # prompted at runtime

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# -------------------- HELPERS --------------------

def log(*a):
    print("[SCRAPE_POSTS]", *a)


def extract_shortcode(url: str) -> str | None:
    """Extract the shortcode from an Instagram post/reel URL."""
    m = re.search(r"instagram\.com/(?:p|reel|reels)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def extract_username_from_post(post) -> str:
    """Get the username of the post author."""
    try:
        return post.owner_username
    except Exception:
        return "unknown"


# -------------------- INSTALOADER --------------------

def setup_instaloader() -> instaloader.Instaloader:
    """Set up instaloader WITH login (prompts for password)."""
    global IG_PASSWORD

    L = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        post_metadata_txt_pattern="",
    )

    username = IG_USERNAME or input("Instagram username: ").strip()
    if username:
        IG_PASSWORD = getpass.getpass(f"Instagram password for {username}: ")
        try:
            L.login(username, IG_PASSWORD)
            log(f"✅ Logged in as {username}")
        except Exception as e:
            log(f"⚠️  Login failed: {e}")
            log("Continuing without login (some posts may not be accessible)")
    else:
        log("⚠️  No username provided — running without login")

    return L


def load_post_by_shortcode(L: instaloader.Instaloader, shortcode: str):
    """Load a single post by its shortcode."""
    return instaloader.Post.from_shortcode(L.context, shortcode)


class _SuppressStderr:
    """Context manager to suppress stderr (instaloader 403 noise)."""
    def __enter__(self):
        self._orig = sys.stderr
        sys.stderr = open(os.devnull, "w")
        return self
    def __exit__(self, *args):
        sys.stderr.close()
        sys.stderr = self._orig


def download_all_images(post, tmp_dir: str) -> list[str]:
    """Download ALL images from a post (including carousel slides)."""
    paths = []
    try:
        with _SuppressStderr():
            if post.typename == "GraphSidecar":
                for idx, node in enumerate(post.get_sidecar_nodes()):
                    if not node.is_video:
                        img_url = node.display_url
                        r = requests.get(img_url, timeout=30)
                        if r.status_code == 200:
                            filepath = os.path.join(tmp_dir, f"{post.shortcode}_{idx}.jpg")
                            with open(filepath, "wb") as f:
                                f.write(r.content)
                            paths.append(filepath)
            else:
                img_url = post.url
                r = requests.get(img_url, timeout=30)
                if r.status_code == 200:
                    filepath = os.path.join(tmp_dir, f"{post.shortcode}.jpg")
                    with open(filepath, "wb") as f:
                        f.write(r.content)
                    paths.append(filepath)
    except Exception as e:
        log(f"  Image download error: {e}")
    return paths


# -------------------- GEMINI --------------------

def setup_gemini():
    return genai.Client(api_key=GEMINI_API_KEY)


def analyze_post_with_gemini(client, caption: str, image_paths: list[str], account: str) -> list[dict]:
    """Use Gemini to extract event details from a post."""
    img_list = image_paths if isinstance(image_paths, list) else ([image_paths] if image_paths else [])

    prompt = f"""You are an event-extraction assistant. The post is from Instagram account @{account}.

Caption:
\"\"\"
{caption}
\"\"\"

Extract ALL events from this post. Return JSON:
{{
  "events": [
    {{
      "event_name": "...",
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM" or null,
      "end_time": "HH:MM" or null,
      "location": "Venue/place NAME only (e.g. 'Storm B Café', 'Flere Fugle'), do NOT include street address, postal code, or city" or null,
      "description": "short summary, max 200 chars",
      "organizer": "who is hosting" or null,
      "tagged_accounts": ["@handle1", "@handle2"]
    }}
  ]
}}

Rules:
- The current date is {datetime.now().strftime('%Y-%m-%d')}. If no year is mentioned, assume the next upcoming occurrence.
- If the same event repeats on multiple dates, create a SEPARATE entry for EACH date.
- If NO events are found, return {{"events": []}}
- ALWAYS include events even if the date is in the past — we filter past events separately.
- Read ALL images carefully — event details (dates, times, locations) are often only in later slides of the carousel.
- A caption like "Fredag d. 20. februar kl. 10" IS an event — don't skip it just because the image looks generic.
- For tagged_accounts: extract ALL @mentions from the caption (not @{account} itself). Include collaborators, performers, DJs, venues, etc. If none found, return an empty list.
- Respond ONLY with the JSON, no extra text."""

    content_parts = []
    for img_path in img_list:
        if img_path and os.path.exists(img_path):
            img = Image.open(img_path)
            content_parts.append(img)
    content_parts.append(prompt)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=content_parts,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=16000,
                ),
            )

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(text)
            return result.get("events", [])
        except json.JSONDecodeError as e:
            log(f"  ⚠️  Gemini returned invalid JSON (attempt {attempt+1}/3): {e}")
            log(f"  Raw response: {response.text[:500] if response else 'None'}")
            if attempt < 2:
                time.sleep(2)
        except Exception as e:
            log(f"  Gemini analysis failed: {e}")
            return []

    log("  ❌ Gemini failed after 3 attempts")
    return []


def to_12h(time_24: str) -> str | None:
    """Convert 'HH:MM' to '3:30pm' display format."""
    if not time_24:
        return None
    try:
        parts = time_24.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        suffix = "am" if hh < 12 else "pm"
        h12 = hh % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{mm:02d}{suffix}"
    except Exception:
        return time_24


# -------------------- NOTION --------------------

def _notion_request(method, url, retries=3, **kwargs):
    """Make a Notion API request with retry logic for timeouts."""
    kwargs.setdefault("timeout", 60)
    kwargs.setdefault("headers", NOTION_HEADERS)
    for attempt in range(retries):
        try:
            r = getattr(requests, method)(url, **kwargs)
            return r
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                log(f"  ⚠️  Notion timeout (attempt {attempt+1}/{retries}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def notion_existing_entries() -> tuple[dict[str, str], list[dict]]:
    """Build dedup index from Notion DB."""
    log("Loading existing Notion entries for dedup...")
    key_to_page: dict[str, str] = {}
    all_entries: list[dict] = []
    payload: dict = {"page_size": 100}
    pages_fetched = 0
    while True:
        r = _notion_request(
            "post",
            f"{NOTION_API}/databases/{NOTION_DB}/query",
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            url_val = props.get("Event Link", {}).get("url", "")
            name_parts = props.get("Event Name", {}).get("title", [])
            name = name_parts[0]["text"]["content"] if name_parts else ""
            date_obj = props.get("Start Date", {}).get("date")
            start_date = date_obj["start"] if date_obj else ""
            source_parts = props.get("Source", {}).get("rich_text", [])
            source = source_parts[0]["text"]["content"] if source_parts else ""
            key = f"{url_val}|{start_date}"
            if url_val:
                key_to_page[key] = page["id"]
            all_entries.append({
                "name": name, "start_date": start_date,
                "source": source.lstrip("@"), "page_id": page["id"], "url": url_val,
            })
        pages_fetched += 1
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
        if pages_fetched >= 100:
            break
    log(f"  Loaded {len(all_entries)} existing entries.")
    return key_to_page, all_entries


def build_notion_props(ev: dict, is_update: bool = False) -> dict:
    """Build Notion properties using the unified column schema.

    Args:
        ev: event dict with scraped data
        is_update: if True, skip user-editable fields (Tags, Location,
                   Description) so manual corrections in Notion are preserved.
    """
    props = {}

    name = ev.get("event_name") or "Untitled Event"
    props["Event Name"] = {"title": [{"text": {"content": name[:2000]}}]}

    if ev.get("url"):
        props["Event Link"] = {"url": ev["url"]}
    if ev.get("start_date"):
        props["Start Date"] = {"date": {"start": ev["start_date"]}}
    if ev.get("end_date"):
        props["End Date"] = {"date": {"start": ev["end_date"]}}
    if ev.get("start_time_disp"):
        props["Start Time"] = {"rich_text": [{"text": {"content": ev["start_time_disp"]}}]}
    if ev.get("end_time_disp"):
        props["End Time"] = {"rich_text": [{"text": {"content": ev["end_time_disp"]}}]}
    # Location — only set on create, preserve manual edits on update
    if ev.get("location") and not is_update:
        props["Location"] = {"rich_text": [{"text": {"content": ev["location"][:2000]}}]}
    if ev.get("source"):
        props["Source"] = {"rich_text": [{"text": {"content": ev["source"][:2000]}}]}
    if ev.get("source_type"):
        props["Source Type"] = {"select": {"name": ev["source_type"]}}
    if ev.get("organizer"):
        props["Organizer"] = {"rich_text": [{"text": {"content": ev["organizer"][:2000]}}]}
    # Description — only set on create, preserve manual edits on update
    if ev.get("description") and not is_update:
        props["Description"] = {"rich_text": [{"text": {"content": ev["description"][:2000]}}]}
    if ev.get("possible_duplicate") is not None:
        props["Possible Duplicate"] = {"checkbox": bool(ev["possible_duplicate"])}
    if ev.get("ig_handle"):
        props["Instagramhandle"] = {"rich_text": [{"text": {"content": ev["ig_handle"][:2000]}}]}
    if ev.get("to_tag"):
        props["To tag"] = {"rich_text": [{"text": {"content": ev["to_tag"][:2000]}}]}

    # Tag (select) — only set on create, preserve manual edits on update
    if ev.get("tag") and not is_update:
        props["Tags"] = {"select": {"name": ev["tag"]}}

    # Review Notes (rich_text) — flagged for manual review (e.g. unknown location)
    if ev.get("review_notes"):
        props["Review Notes"] = {
            "rich_text": [{"text": {"content": ev["review_notes"][:2000]}}]
        }

    return props


def make_dedup_key(ev: dict) -> str:
    """Build a deduplication key: URL + date (no name — Gemini is non-deterministic)."""
    return f"{ev.get('url', '')}|{ev.get('start_date', '')}"


def notion_create(ev: dict):
    payload = {
        "parent": {"database_id": NOTION_DB},
        "properties": build_notion_props(ev),
    }
    r = _notion_request("post", f"{NOTION_API}/pages", json=payload)
    if r.status_code >= 400:
        try:
            log("CREATE ERROR:", r.status_code, r.json())
        except Exception:
            log("CREATE ERROR RAW:", r.status_code, r.text[:500])
    return r


def notion_update(page_id: str, ev: dict):
    payload = {"properties": build_notion_props(ev, is_update=True)}
    r = _notion_request("patch", f"{NOTION_API}/pages/{page_id}", json=payload)
    if r.status_code >= 400:
        try:
            log("UPDATE ERROR:", r.status_code, r.json())
        except Exception:
            log("UPDATE ERROR RAW:", r.status_code, r.text[:500])
    return r


# -------------------- PROCESS A SINGLE POST --------------------

def process_post(L, client, shortcode: str, post_url: str,
                 existing: dict, all_entries: list, source_mapping: dict, tmp_dir: str):
    """Scrape one post and push events to Notion."""
    try:
        with _SuppressStderr():
            post = load_post_by_shortcode(L, shortcode)
            # Pre-fetch attributes that may trigger 403 warnings
            _ = post.owner_username
            _ = post.caption
            _ = post.typename
    except Exception as e:
        log(f"❌ Could not load post {post_url}: {e}")
        return

    account = extract_username_from_post(post)
    caption = post.caption or ""

    log(f"📸 Post by @{account}: {post_url}")
    log(f"   Caption: {caption[:120]}{'...' if len(caption) > 120 else ''}")

    # Download images
    image_paths = download_all_images(post, tmp_dir)
    log(f"   Downloaded {len(image_paths)} image(s)")

    # Analyze with Gemini
    events = analyze_post_with_gemini(client, caption, image_paths, account)

    if not events:
        log(f"   ℹ️  No events detected in this post.")
        return

    log(f"   🎯 Found {len(events)} event(s)!")

    created = updated = 0
    for event_data in events:
        event_date_str = event_data.get("event_date")

        # Collect @mentions
        gemini_tags = event_data.get("tagged_accounts") or []
        caption_tags = re.findall(r"@([\w.]+)", caption)
        all_tags = set()
        for t in gemini_tags:
            all_tags.add(t.lstrip("@").lower())
        for t in caption_tags:
            all_tags.add(t.lower())
        all_tags.discard(account.lower())
        to_tag = ", ".join(f"@{t}" for t in sorted(all_tags)) if all_tags else None

        # Skip non-events entirely (deadlines, etc.)
        if should_skip_entirely(event_data.get("event_name", ""), event_data.get("description", "")):
            log(f"  Skipping non-event: {event_data.get('event_name')}")
            continue

        # Route hours/closure announcements to separate DB
        if is_not_event(event_data.get("event_name", "")):
            push_to_hours_db({
                "event_name": event_data.get("event_name"),
                "source": f"@{account}",
                "location": event_data.get("location"),
                "description": event_data.get("description"),
                "url": post_url,
                "source_type": "Instagram",
                "ig_handle": f"@{account}",
                "date": post.date_utc.date().isoformat(),
            }, log_fn=log)
            continue

        # Route deals/special-price announcements to Deals DB
        if is_deal(event_data.get("event_name", ""), event_data.get("description", "")):
            push_to_deals_db({
                "event_name": event_data.get("event_name"),
                "place": event_data.get("location"),
                "source": f"@{account}",
                "description": event_data.get("description"),
                "url": post_url,
                "source_type": "Instagram",
                "ig_handle": f"@{account}",
                "date": post.date_utc.date().isoformat(),
            }, log_fn=log)
            continue

        ev = {
            "event_name": event_data.get("event_name"),
            "organizer": event_data.get("organizer"),
            "start_date": event_date_str,
            "end_date": event_date_str,
            "start_time_disp": to_12h(event_data.get("start_time")),
            "end_time_disp": to_12h(event_data.get("end_time")),
            "location": clean_location(event_data.get("location")) or event_data.get("location"),
            "description": event_data.get("description"),
            "source_type": "Instagram",
            "source": f"@{account}",
            "url": post_url,
            "ig_handle": f"@{account}",
            "to_tag": to_tag,
            "tag": classify_event(
                event_data.get("event_name", ""),
                event_data.get("description", ""),
                event_data.get("organizer", ""),
            ),
        }

        # Skip events at excluded locations (not in Nordvest)
        if is_excluded_location(ev.get("location", "")):
            log(f"  Skipping excluded location: {ev.get('event_name')} @ {ev.get('location')}")
            continue

        # Flag unknown locations for manual review
        if is_unknown_location(ev.get("location", "")):
            ev["review_notes"] = f"⚠️ Unknown location: {ev['location']}"
            log(f"  ⚠️ Unknown location flagged for review: {ev.get('event_name')} @ {ev.get('location')}")

        # Check for cross-platform duplicate
        dupe = find_duplicate(
            ev.get("event_name", ""), ev.get("start_date", ""),
            account, all_entries, source_mapping,
        )
        if dupe:
            ev["possible_duplicate"] = True
            log(f"   ⚠️  Possible duplicate of: {dupe.get('name')} (from {dupe.get('source')})")
        else:
            ev["possible_duplicate"] = False

        dedup_key = make_dedup_key(ev)
        page_id = existing.get(dedup_key)

        if page_id:
            r = notion_update(page_id, ev)
            if r.status_code == 429:
                time.sleep(1.5)
                r = notion_update(page_id, ev)
            try:
                r.raise_for_status()
                updated += 1
            except Exception:
                log(f"   ❌ Update failed for {ev.get('event_name')}")
        else:
            r = notion_create(ev)
            if r.status_code == 429:
                time.sleep(1.5)
                r = notion_create(ev)
            try:
                r.raise_for_status()
                created += 1
                nid = r.json().get("id")
                if nid:
                    existing[dedup_key] = nid
                    all_entries.append({
                        "name": ev.get("event_name", ""),
                        "start_date": ev.get("start_date", ""),
                        "source": account,
                        "page_id": nid,
                        "url": ev.get("url", ""),
                    })
            except Exception:
                log(f"   ❌ Create failed for {ev.get('event_name')}")

        log(f"   → {ev.get('event_name')} | {ev.get('start_date')} | {ev.get('location')}")
        time.sleep(0.3)

    log(f"   ✅ Done: {created} created, {updated} updated")


# -------------------- MAIN --------------------

def main():
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit("❌ Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not GEMINI_API_KEY:
        sys.exit("❌ Missing GEMINI_API_KEY")

    # Collect URLs from args or interactive input
    urls = []
    if len(sys.argv) > 1:
        urls = sys.argv[1:]
    else:
        print("📋 Paste Instagram post URLs (one per line). Empty line to start scraping:")
        print()
        while True:
            try:
                line = input("  URL> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            urls.append(line)

    if not urls:
        sys.exit("No URLs provided.")

    # Validate & extract shortcodes
    posts_to_scrape = []
    for url in urls:
        sc = extract_shortcode(url)
        if sc:
            post_url = f"https://www.instagram.com/p/{sc}/"
            posts_to_scrape.append((sc, post_url))
        else:
            log(f"⚠️  Skipping invalid URL: {url}")

    if not posts_to_scrape:
        sys.exit("No valid Instagram post URLs found.")

    log(f"🚀 Scraping {len(posts_to_scrape)} post(s)...")
    print()

    # Setup
    L = setup_instaloader()
    client = setup_gemini()
    existing, all_entries = notion_existing_entries()
    source_mapping = load_source_mapping()
    tmp_dir = tempfile.mkdtemp(prefix="ig_manual_")

    try:
        for i, (shortcode, post_url) in enumerate(posts_to_scrape, 1):
            log(f"[{i}/{len(posts_to_scrape)}] {post_url}")
            process_post(L, client, shortcode, post_url, existing, all_entries, source_mapping, tmp_dir)
            print()
            if i < len(posts_to_scrape):
                time.sleep(2)  # Rate limit between posts
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    log("🎉 All done!")


if __name__ == "__main__":
    main()
