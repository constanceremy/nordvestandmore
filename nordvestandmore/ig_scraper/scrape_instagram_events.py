#!/usr/bin/env python3
"""
Instagram Event Scraper
-----------------------
1. Uses instaloader to pull recent posts (captions + images) from a list of accounts
2. Uses Google Gemini (free) to determine if the post contains events,
   and extracts ALL events (a single post can have multiple events/dates)
3. Pushes results to the unified Notion events database (shared with website scrapers)

Env vars required:
    NOTION_TOKEN            – Notion integration token
    NOTION_DATABASE_ID      – Notion database ID (shared events DB)
    GEMINI_API_KEY          – Google Gemini API key (free tier)
    IG_USERNAME             – Instagram username for login
    IG_PASSWORD             – Instagram password for login
    DAYS_BACK               – How many days back to scrape (default: 7)
"""
import os
import random
import sys
import re
import time
import json
import base64
import tempfile
import shutil
import collections
from datetime import date, datetime, timedelta
from pathlib import Path

import instaloader
from google import genai
from google.genai import types
from PIL import Image
import requests

# Add parent dir to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dedup import load_source_mapping, find_duplicate, similarity
from auto_tag import classify_event, is_not_event, is_deal, should_skip_entirely, is_excluded_location, is_unknown_location
from hours_db import push_to_hours_db
from deals_db import push_to_deals_db
from fix_locations import clean_location

# -------------------- CONFIG --------------------
SLUG = "INSTAGRAM"
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB = os.environ.get("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")
DAYS_BACK = int(os.environ.get("DAYS_BACK", "7"))
ACCOUNTS_FILE = os.environ.get(
    "ACCOUNTS_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.txt"),
)

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

DEBUG = bool(os.environ.get("DEBUG"))

# Gemini free tier: 15 requests per minute
GEMINI_RPM_LIMIT = 14  # stay 1 under to be safe


def log(*a):
    print(f"[{SLUG}]", *a)


class RateLimiter:
    """Simple sliding-window rate limiter. Sleeps if limit would be exceeded."""

    def __init__(self, max_calls: int, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self.timestamps: collections.deque = collections.deque()

    def wait(self):
        now = time.time()
        # Remove timestamps older than the window
        while self.timestamps and self.timestamps[0] <= now - self.period:
            self.timestamps.popleft()
        # If at limit, sleep until the oldest one expires
        if len(self.timestamps) >= self.max_calls:
            sleep_time = self.period - (now - self.timestamps[0]) + 0.5
            if sleep_time > 0:
                log(f"  ⏳ Rate limit: waiting {sleep_time:.1f}s...")
                time.sleep(sleep_time)
        self.timestamps.append(time.time())


gemini_limiter = RateLimiter(max_calls=GEMINI_RPM_LIMIT, period=60.0)


# -------------------- Instagram --------------------
_logged_in = False


def setup_instaloader(login_first: bool = False) -> instaloader.Instaloader:
    """Set up instaloader.

    Args:
        login_first: If True and credentials are available, log in immediately
                     (recommended for CI/cron where rate limits are strict).
    """
    L = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        post_metadata_txt_pattern="",
        max_connection_attempts=1,  # Don't retry on 429 (would block 30 min)
        request_timeout=30,
    )

    if login_first and IG_USERNAME and IG_PASSWORD:
        try_login(L)
    else:
        log("Starting without login (public posts only).")

    return L


def try_login(L: instaloader.Instaloader):
    """Attempt login only when needed (e.g. a private profile)."""
    global _logged_in
    if _logged_in:
        return True
    if not IG_USERNAME or not IG_PASSWORD:
        log("No IG credentials available — cannot log in.")
        return False
    try:
        L.login(IG_USERNAME, IG_PASSWORD)
        log(f"Logged in as {IG_USERNAME}")
        _logged_in = True
        return True
    except Exception as e:
        log(f"Login failed: {e}")
        return False


def load_accounts() -> list[str]:
    """Load Instagram account handles from accounts.txt (one per line, # for comments)."""
    accounts = []
    path = Path(ACCOUNTS_FILE)
    if not path.exists():
        log(f"Accounts file not found: {ACCOUNTS_FILE}")
        return accounts
    for line in path.read_text().splitlines():
        line = line.split("#")[0].strip()  # Strip inline comments
        if line and not line.startswith("#"):
            accounts.append(line.lstrip("@"))
    return accounts


def get_recent_posts(L: instaloader.Instaloader, username: str, days_back: int,
                     auto_login_retry: bool = True):
    """Yield recent posts from an account within the last N days.

    If auto_login_retry=True (default), automatically retries with login when
    the profile can't be loaded or returns 0 posts.
    If False, just yields whatever was found without login and lets the caller
    decide whether to retry later.
    """
    cutoff = datetime.now() - timedelta(days=days_back)

    # Attempt to load profile
    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except Exception as e:
        log(f"Could not load @{username}: {e}")
        if auto_login_retry and not _logged_in:
            if try_login(L):
                try:
                    profile = instaloader.Profile.from_username(L.context, username)
                except Exception as e2:
                    log(f"Still could not load @{username} after login: {e2}")
                    return
            else:
                return
        else:
            return

    total_count = getattr(profile, 'mediacount', '?')
    log(f"Scraping @{username} ({total_count} total posts, last {days_back} days)...")

    # Collect posts (need to buffer to detect 0-post case)
    # Also capture the very first non-pinned post date even if it's outside the window
    # Don't break on the first old post — Instagram feed order isn't always strict.
    # Instead, stop after 3 consecutive old (non-pinned) posts.
    posts = []
    latest_post_date = None
    pinned_count = 0
    consecutive_old = 0
    MAX_CONSECUTIVE_OLD = 3
    for post in profile.get_posts():
        # Skip pinned posts — they appear first but are usually old
        if getattr(post, 'is_pinned', False):
            pinned_count += 1
            continue
        if latest_post_date is None:
            latest_post_date = post.date_utc
        if post.date_utc < cutoff:
            consecutive_old += 1
            if consecutive_old >= MAX_CONSECUTIVE_OLD:
                break
            continue
        consecutive_old = 0  # Reset — we found a recent post
        posts.append(post)
        time.sleep(random.uniform(0.8, 1.5))
    if pinned_count:
        log(f"  Skipped {pinned_count} pinned post{'s' if pinned_count != 1 else ''}")

    # If 0 posts and not logged in, Instagram may be hiding them
    if not posts and not _logged_in and auto_login_retry:
        log(f"  0 posts without login — trying with login...")
        if try_login(L):
            try:
                profile = instaloader.Profile.from_username(L.context, username)
                consecutive_old = 0
                for post in profile.get_posts():
                    if getattr(post, 'is_pinned', False):
                        continue
                    if latest_post_date is None:
                        latest_post_date = post.date_utc
                    if post.date_utc < cutoff:
                        consecutive_old += 1
                        if consecutive_old >= MAX_CONSECUTIVE_OLD:
                            break
                        continue
                    consecutive_old = 0
                    posts.append(post)
                    time.sleep(random.uniform(0.8, 1.5))
            except Exception as e:
                log(f"  Retry after login failed: {e}")

    if posts:
        newest = posts[0].date_utc.strftime("%b %d")
        oldest = posts[-1].date_utc.strftime("%b %d")
        date_range = f" ({newest})" if newest == oldest else f" ({oldest} – {newest})"
    elif latest_post_date:
        date_range = f" (latest: {latest_post_date.strftime('%b %d')})"
    else:
        date_range = ""
    log(f"  Found {len(posts)} recent post{'s' if len(posts) != 1 else ''} from @{username}{date_range}")

    # Attach metadata so callers can inspect it
    get_recent_posts._last_total_count = total_count
    get_recent_posts._last_latest_date = (
        latest_post_date.strftime("%Y-%m-%d") if latest_post_date else None
    )

    yield from posts


def download_first_image(post, tmp_dir: str) -> str | None:
    """Download the first image of a post to a temp directory."""
    try:
        img_url = post.url
        response = requests.get(img_url, timeout=30)
        if response.status_code == 200:
            filepath = os.path.join(tmp_dir, f"{post.shortcode}.jpg")
            with open(filepath, "wb") as f:
                f.write(response.content)
            return filepath
    except Exception as e:
        if DEBUG:
            log(f"  Image download failed for {post.shortcode}: {e}")
    return None


def download_all_images(post, tmp_dir: str) -> list[str]:
    """Download ALL images from a post (including all carousel slides).
    Returns a list of file paths."""
    paths = []
    try:
        if post.typename == "GraphSidecar":
            # Carousel post — download each slide
            for idx, node in enumerate(post.get_sidecar_nodes()):
                if not node.is_video:
                    img_url = node.display_url
                    response = requests.get(img_url, timeout=30)
                    if response.status_code == 200:
                        filepath = os.path.join(tmp_dir, f"{post.shortcode}_{idx}.jpg")
                        with open(filepath, "wb") as f:
                            f.write(response.content)
                        paths.append(filepath)
        else:
            # Single image post
            img_url = post.url
            response = requests.get(img_url, timeout=30)
            if response.status_code == 200:
                filepath = os.path.join(tmp_dir, f"{post.shortcode}.jpg")
                with open(filepath, "wb") as f:
                    f.write(response.content)
                paths.append(filepath)
    except Exception as e:
        if DEBUG:
            log(f"  Image download failed for {post.shortcode}: {e}")
        # Fall back to first image only
        if not paths:
            first = download_first_image(post, tmp_dir)
            if first:
                paths.append(first)
    return paths


# -------------------- AI Analysis (Gemini) --------------------
def setup_gemini():
    """Configure the Gemini API client."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    return client


def analyze_post_with_gemini(
    client, caption: str, image_paths: list[str] | str | None, account: str
) -> list[dict]:
    """
    Send post caption + ALL images to Gemini. Returns a list of event dicts.
    A single post can contain multiple events (different dates, different events).
    Returns empty list if no events found.

    image_paths can be:
      - a list of file paths (carousel slides)
      - a single string path (backward compat)
      - None
    """
    # Normalize image_paths to a list
    if image_paths is None:
        img_list: list[str] = []
    elif isinstance(image_paths, str):
        img_list = [image_paths]
    else:
        img_list = image_paths

    n_images = len(img_list)
    image_note = (
        f"This post has {n_images} image slide(s). Check ALL of them for event details — "
        "event info is often on later slides (e.g. a flyer on slide 2, a schedule on slide 3)."
        if n_images > 1
        else "Check both the caption AND the image for event details."
    )

    prompt = f"""Analyze this Instagram post from @{account}.

Caption: {caption or '(no caption)'}

{image_note}

Your task:
1. Determine if this post announces one or more EVENTS (concert, workshop, exhibition, market, party, talk, screening, opening, festival, dinner, quiz, film screening, book club, lecture, class, pop-up, etc.)
2. If YES, extract ALL events. A single post may contain MULTIPLE events — for example:
   - The same event happening on different dates (e.g. "every Tuesday in March" = 4 separate events)
   - Different events listed in the same post
   - An event with multiple sessions at different times on different days

IMPORTANT: Analyze BOTH the caption text AND the image(s) INDEPENDENTLY.
- If the CAPTION mentions a date, time, or event name → it IS an event, regardless of what the image shows.
- If an IMAGE contains a flyer, poster, or schedule with dates/times → it IS an event, regardless of the caption.
- Event info can be split: name in the caption, date in the image, or vice versa.

Respond ONLY with valid JSON — an array of events:

{{
  "events": [
    {{
      "event_name": "Name of the event",
      "organizer": "Who is organizing/hosting (use @{account} if unclear)",
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM (24h format)" or null,
      "end_time": "HH:MM (24h format)" or null,
      "location": "Venue/place NAME only (e.g. 'Storm B Café', 'Flere Fugle'), do NOT include street address, postal code, or city" or null,
      "description": "One-sentence summary of this specific event",
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
- If the post mentions both "doors" (or "døre åbner") and "show" (or "start") times, use the SHOW/START time as start_time, NOT the doors time.
- Respond ONLY with the JSON, no extra text."""

    try:
        content_parts = []

        # Add ALL images (carousel slides)
        for img_path in img_list:
            if img_path and os.path.exists(img_path):
                img = Image.open(img_path)
                content_parts.append(img)

        content_parts.append(prompt)

        # Respect Gemini free tier: 15 requests/minute
        gemini_limiter.wait()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=content_parts,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2000,
            ),
        )

        text = response.text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        return result.get("events", [])
    except Exception as e:
        log(f"  Gemini analysis failed: {e}")
        return []


def to_12h(time_24: str) -> str | None:
    """Convert 'HH:MM' 24h string to '3:30pm' display format."""
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


# -------------------- Notion --------------------
def notion_existing_entries() -> tuple[dict[str, str], list[dict]]:
    """
    Build dedup index: "URL|StartDate" -> page_id.
    Uses URL + date only (NOT event name) because Gemini may produce
    slightly different names each run, causing false dedup misses.
    Also returns a flat list of entry dicts for cross-platform fuzzy matching.
    """
    key_to_page: dict[str, str] = {}
    all_entries: list[dict] = []
    payload: dict = {"page_size": 100}
    pages_fetched = 0
    while True:
        # Retry on transient network errors (timeouts, connection resets)
        for attempt in range(3):
            try:
                r = requests.post(
                    f"{NOTION_API}/databases/{NOTION_DB}/query",
                    headers=NOTION_HEADERS,
                    json=payload,
                    timeout=60,
                )
                r.raise_for_status()
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < 2:
                    log(f"  Notion API timeout (attempt {attempt + 1}/3), retrying in 10s...")
                    time.sleep(10)
                else:
                    raise
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
            # Dedup key: URL + date (no name — Gemini is non-deterministic)
            key = f"{url_val}|{start_date}"
            if url_val:
                key_to_page[key] = page["id"]
            all_entries.append({
                "name": name,
                "start_date": start_date,
                "source": source.lstrip("@"),
                "page_id": page["id"],
                "url": url_val,
            })
        pages_fetched += 1
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
        if pages_fetched >= 100:
            break
    if DEBUG:
        log("Preloaded Notion entries:", len(key_to_page))
    return key_to_page, all_entries


def build_notion_props(ev: dict, is_update: bool = False) -> dict:
    """Build Notion properties using the unified column schema.

    Args:
        ev: event dict with scraped data
        is_update: if True, skip user-editable fields (Tags, Location,
                   Description) so manual corrections in Notion are preserved.
    """
    props = {}

    # Name (title)
    name = ev.get("event_name") or "Untitled Event"
    props["Event Name"] = {"title": [{"text": {"content": name[:2000]}}]}

    # URL — link to source post
    if ev.get("url"):
        props["Event Link"] = {"url": ev["url"]}

    # Start Date
    if ev.get("start_date"):
        props["Start Date"] = {"date": {"start": ev["start_date"]}}

    # End Date
    if ev.get("end_date"):
        props["End Date"] = {"date": {"start": ev["end_date"]}}

    # Start Time (display format like "7:00pm")
    if ev.get("start_time_disp"):
        props["Start Time"] = {
            "rich_text": [{"text": {"content": ev["start_time_disp"]}}]
        }

    # End Time
    if ev.get("end_time_disp"):
        props["End Time"] = {
            "rich_text": [{"text": {"content": ev["end_time_disp"]}}]
        }

    # Location — only set on create, preserve manual edits on update
    if ev.get("location") and not is_update:
        props["Location"] = {
            "rich_text": [{"text": {"content": ev["location"][:2000]}}]
        }

    # Source (text) — e.g. "@account" or "LYGTEN_STATION"
    if ev.get("source"):
        props["Source"] = {
            "rich_text": [{"text": {"content": ev["source"][:2000]}}]
        }

    # Source Type (select) — "Instagram", "Facebook", "Website"
    if ev.get("source_type"):
        props["Source Type"] = {"select": {"name": ev["source_type"]}}

    # Organizer (text)
    if ev.get("organizer"):
        props["Organizer"] = {
            "rich_text": [{"text": {"content": ev["organizer"][:2000]}}]
        }

    # Description — only set on create, preserve manual edits on update
    if ev.get("description") and not is_update:
        props["Description"] = {
            "rich_text": [{"text": {"content": ev["description"][:2000]}}]
        }

    # Possible Duplicate (checkbox)
    if ev.get("possible_duplicate") is not None:
        props["Possible Duplicate"] = {"checkbox": bool(ev["possible_duplicate"])}

    # Instagramhandle (rich_text) — the source IG handle
    if ev.get("ig_handle"):
        props["Instagramhandle"] = {
            "rich_text": [{"text": {"content": ev["ig_handle"][:2000]}}]
        }

    # To tag (rich_text) — other @mentions from the post
    if ev.get("to_tag"):
        props["To tag"] = {
            "rich_text": [{"text": {"content": ev["to_tag"][:2000]}}]
        }

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
    r = requests.post(
        f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=30
    )
    if r.status_code >= 400:
        try:
            log("CREATE ERROR:", r.status_code, r.json())
        except Exception:
            log("CREATE ERROR RAW:", r.status_code, r.text[:500])
    return r


def notion_update(page_id: str, ev: dict):
    payload = {"properties": build_notion_props(ev, is_update=True)}
    r = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=NOTION_HEADERS,
        json=payload,
        timeout=30,
    )
    if r.status_code >= 400:
        try:
            log("UPDATE ERROR:", r.status_code, r.json())
        except Exception:
            log("UPDATE ERROR RAW:", r.status_code, r.text[:500])
    return r


# -------------------- PER-ACCOUNT FUNCTION (used by runner) --------------------
def scrape_account(account, L, client, existing, all_entries, source_mapping, tmp_dir,
                   auto_login_retry=True):
    """
    Scrape a single Instagram account.
    Mutates `existing` and `all_entries` in-place as new entries are created.
    Returns dict: {created, updated, skipped, flagged_dupes, total_events, total_posts,
                   needs_login (True if 0 posts without login), error (True if crashed)}
    """
    created = updated = skipped = flagged_dupes = total_events = total_posts = 0

    try:
        posts = list(get_recent_posts(L, account, DAYS_BACK,
                                      auto_login_retry=auto_login_retry))
        profile_total = getattr(get_recent_posts, '_last_total_count', '?')
        latest_date = getattr(get_recent_posts, '_last_latest_date', None)
    except Exception as e:
        log(f"  ⚠️ Instagram error for @{account}: {e}")
        log(f"  Skipping @{account} (try again later — Instagram may be rate-limiting).")
        return {
            "created": created, "updated": updated, "skipped": skipped,
            "flagged_dupes": flagged_dupes, "total_events": total_events,
            "total_posts": total_posts, "profile_total": 0,
            "latest_date": None, "error": True,
        }

    for post in posts:
        total_posts += 1
        post_url = f"https://www.instagram.com/p/{post.shortcode}/"
        caption = post.caption or ""

        # Download ALL images for vision analysis (carousel slides)
        image_paths = download_all_images(post, tmp_dir)
        if DEBUG and len(image_paths) > 1:
            log(f"  Downloaded {len(image_paths)} carousel slides for {post_url}")

        # Analyze with Gemini — returns a LIST of events
        events = analyze_post_with_gemini(client, caption, image_paths, account)

        if not events:
            log(f"  Not an event: {post_url}")
            skipped += 1
            continue

        log(f"  Found {len(events)} event(s) in post: {post_url}")
        total_events += len(events)

        past_count = 0
        max_date = date.today() + timedelta(days=180)
        for event_data in events:
            # Skip past events and events too far in the future
            event_date_str = event_data.get("event_date")
            if event_date_str:
                try:
                    ev_date_obj = date.fromisoformat(event_date_str)
                    if ev_date_obj < date.today():
                        past_count += 1
                        log(f"  Skipping past event: {event_data.get('event_name')} ({event_date_str})")
                        continue
                    if ev_date_obj > max_date:
                        log(f"  Skipping too-far-future event: {event_data.get('event_name')} ({event_date_str})")
                        continue
                except ValueError:
                    pass

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

            # Skip retreats from Rört — they're not in Nordvest
            if account.lower() in ("rort.copenhagen",):
                ev_text = f"{event_data.get('event_name', '')} {event_data.get('description', '')}".lower()
                if "retreat" in ev_text or "retræte" in ev_text:
                    log(f"  Skipping Rört retreat: {event_data.get('event_name')}")
                    continue

            # Collect @mentions: from Gemini + from caption directly
            gemini_tags = event_data.get("tagged_accounts") or []
            caption_tags = re.findall(r"@([\w.]+)", caption)
            all_tags = set()
            for t in gemini_tags:
                all_tags.add(t.lstrip("@").lower())
            for t in caption_tags:
                all_tags.add(t.lower())
            # Remove the source account itself
            all_tags.discard(account.lower())
            to_tag = ", ".join(f"@{t}" for t in sorted(all_tags)) if all_tags else None

            # Determine organizer — for @flerefugle, check if the event
            # is actually at one of their sister brands (they cross-post for visibility)
            organizer = event_data.get("organizer")
            ig_handle_val = f"@{account}"
            if account.lower() == "flerefugle":
                _SISTER_BRANDS = {
                    "fovl": ("Fovl NV", "@fovl.nv"),
                    "fovl.nv": ("Fovl NV", "@fovl.nv"),
                    "flok": ("Flok Kantine", "@flok_kantine"),
                    "flok_kantine": ("Flok Kantine", "@flok_kantine"),
                    "bageri": ("Flere Fugle Bageri", "@flerefugle_bageri_og_butik"),
                    "butik": ("Flere Fugle Bageri", "@flerefugle_bageri_og_butik"),
                    "flerefugle_bageri_og_butik": ("Flere Fugle Bageri", "@flerefugle_bageri_og_butik"),
                    "lille_fugl": ("Lille Fugl", "@flerefugle"),
                }
                # Check @mentions and caption for sister brands
                check_text = (caption + " " + (organizer or "") + " " + (event_data.get("location") or "")).lower()
                for key, (brand_name, brand_handle) in _SISTER_BRANDS.items():
                    if key in check_text or f"@{key}" in check_text:
                        organizer = brand_name
                        ig_handle_val = brand_handle
                        break

            # Default location for accounts whose events are always at their own venue
            _DEFAULT_LOCATIONS = {
                "gamma_nv": "Gamma NV",
                "urbancampercph": "Urban Camper",
                "dortheasbar": "Dorthea's Bar",
                "heatharmonydk": "Heat Harmony",
                "haut_scene": "Haut Scene",
                "flok_kantine": "Flok",
                "rabens_saloner": "Rabens Saloner",
                "kima_forfanden": "Kima",
                "cafe.gazou": "Cafe Gazou",
                "lygtenstation": "Lygten Station",
                "dansekapellet": "Dansekapellet",
                "urban13_cph": "Urban 13",
                "grundtvigskirke": "Grundtvigs Kirke",
                "ansgarkirken": "Ansgarkirken",
                "ungdomshuset_d61": "Ungdomshuset",
                "rort.copenhagen": "Rört",
                "tribecabeer.pizzalab": "Tribeca",
                "fofkbh_nordsj": "Aftenskolernes Hus",
                "davescph": "Dave's",
                "goldschmidts_musikakademi": "Goldschmidts Musikakademi",
                "kapernaumskirken": "Kapernaumskirken",
                "makerspacenv": "MakerSpace NV",
                "repaircafenv": "MakerSpace NV",
                "justsaunacph": "Just Sauna",
            }
            location = _DEFAULT_LOCATIONS.get(account.lower()) or event_data.get("location")
            # Normalize full addresses to venue names
            cleaned = clean_location(location) if location else None
            if cleaned:
                location = cleaned

            ev = {
                "event_name": event_data.get("event_name"),
                "organizer": organizer,
                "start_date": event_date_str,
                "end_date": event_date_str,
                "start_time_disp": to_12h(event_data.get("start_time")),
                "end_time_disp": to_12h(event_data.get("end_time")),
                "location": location,
                "description": event_data.get("description"),
                "source_type": "Instagram",
                "source": f"@{account}",
                "url": post_url,
                "ig_handle": ig_handle_val,
                "to_tag": to_tag,
                "tag": classify_event(
                    event_data.get("event_name", ""),
                    event_data.get("description", ""),
                    organizer or "",
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
                ev.get("event_name", ""),
                ev.get("start_date", ""),
                account,
                all_entries,
                source_mapping,
            )
            if dupe:
                ev["possible_duplicate"] = True
                flagged_dupes += 1
                log(f"    ⚠️  Possible duplicate of: {dupe.get('name')} (from {dupe.get('source')})")
            else:
                ev["possible_duplicate"] = False

            dedup_key = make_dedup_key(ev)
            page_id = existing.get(dedup_key)

            # Fallback: if URL-based dedup missed, try name+date fuzzy match
            if not page_id:
                ev_name = ev.get("event_name", "")
                ev_date = ev.get("start_date") or ""
                for entry in all_entries:
                    if not ev_date or (entry.get("start_date") or "")[:10] != ev_date[:10]:
                        continue
                    name_sim = similarity(ev_name, entry.get("name", ""))
                    if name_sim >= 0.80:
                        page_id = entry.get("page_id")
                        if DEBUG:
                            log(f"    🔗 Fuzzy name match ({name_sim:.0%}): '{entry.get('name')}' → updating")
                        break
                if DEBUG and not page_id:
                    log(f"    🔍 Dedup miss: key={dedup_key[:120]}")

            if page_id:
                r = notion_update(page_id, ev)
                if r.status_code == 429:
                    time.sleep(1.5)
                    r = notion_update(page_id, ev)
                try:
                    r.raise_for_status()
                    updated += 1
                except Exception:
                    log(f"  Update failed for {ev.get('event_name')}")
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
                        # Also add to all_entries for subsequent checks
                        all_entries.append({
                            "name": ev.get("event_name", ""),
                            "start_date": ev.get("start_date", ""),
                            "source": account,
                            "page_id": nid,
                            "url": ev.get("url", ""),
                        })
                except Exception:
                    log(f"  Create failed for {ev.get('event_name')}")

            log(
                f"    → {ev.get('event_name')} | {ev.get('start_date')} | {ev.get('location')}"
            )
            time.sleep(0.3)

    # Flag if this account might need login (got 0 posts without being logged in)
    needs_login = (total_posts == 0 and not _logged_in)

    return {
        "created": created, "updated": updated, "skipped": skipped,
        "flagged_dupes": flagged_dupes, "total_events": total_events,
        "total_posts": total_posts, "profile_total": profile_total,
        "latest_date": latest_date, "needs_login": needs_login,
    }


# -------------------- MAIN (standalone) --------------------
def main():
    """
    Usage:
        python3 scrape_instagram_events.py                  # scrape all from accounts.txt
        python3 scrape_instagram_events.py handle1 handle2  # scrape specific accounts
    """
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not GEMINI_API_KEY:
        sys.exit("Missing GEMINI_API_KEY")

    # Accept account names as args, or fall back to accounts.txt
    if len(sys.argv) > 1:
        accounts = [a.lstrip("@").strip() for a in sys.argv[1:] if a.strip()]
    else:
        accounts = load_accounts()
    if not accounts:
        sys.exit(f"No accounts found")

    log(f"Accounts to scrape: {accounts}")
    log(f"Looking back {DAYS_BACK} days")

    L = setup_instaloader()
    client = setup_gemini()
    existing, all_entries = notion_existing_entries()
    source_mapping = load_source_mapping()
    totals = {"created": 0, "updated": 0, "skipped": 0, "flagged_dupes": 0, "total_events": 0}

    tmp_dir = tempfile.mkdtemp(prefix="ig_scraper_")

    try:
        for acct_idx, account in enumerate(accounts, 1):
            log(f"[{acct_idx}/{len(accounts)}] Scraping @{account}...")
            stats = scrape_account(account, L, client, existing, all_entries, source_mapping, tmp_dir)
            for k in totals:
                totals[k] += stats.get(k, 0)
            log(f"  ✅ Done with @{account}")
            time.sleep(2)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    log(f"✅ Done! {totals['total_events']} events found across all posts")
    log(f"   Created {totals['created']}, Updated {totals['updated']}, Skipped {totals['skipped']} posts")
    if totals["flagged_dupes"]:
        log(f"   ⚠️  {totals['flagged_dupes']} flagged as possible duplicates")


if __name__ == "__main__":
    main()
