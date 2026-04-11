#!/usr/bin/env python3
"""
Facebook Event Scraper
-----------------------
1. Uses Playwright (headless Chromium) to load Facebook /events pages
2. Extracts event cards (title, date, location, link)
3. Optionally uses Gemini to enrich/clarify extracted data
4. Pushes results to the unified Notion events database

Env vars required:
    NOTION_TOKEN            – Notion integration token
    NOTION_DATABASE_ID      – Notion database ID (shared events DB)
    GEMINI_API_KEY          – Google Gemini API key (free tier)
    FB_ACCOUNTS_FILE        – Path to file listing Facebook page URLs (default: fb_accounts.txt)
"""
import os
import sys
import re
import time
import json
import collections
from datetime import datetime, date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
import requests

# Add parent dir to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dedup import load_source_mapping, find_duplicate, load_fb_to_ig_map, _extract_fb_id, similarity, are_sources_related, get_source_priority
from auto_tag import classify_event, classify_seasonal, is_not_event, is_deal, should_skip_entirely, is_excluded_location, is_unknown_location
from hours_db import push_to_hours_db
from deals_db import push_to_deals_db
from fix_locations import clean_location
from locations_cache import find_location_id, find_location_coords

# -------------------- CONFIG --------------------
SLUG = "FACEBOOK"
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB = os.environ.get("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

FB_ACCOUNTS_FILE = os.environ.get(
    "FB_ACCOUNTS_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_accounts.txt"),
)
FB_COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_cookies.json")

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

DEBUG = bool(os.environ.get("DEBUG"))

# Gemini rate limiter (shared with IG scraper concept)
GEMINI_RPM_LIMIT = 14


def log(*a):
    print(f"[{SLUG}]", *a)


class RateLimiter:
    """Simple sliding-window rate limiter."""

    def __init__(self, max_calls: int, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self.timestamps: collections.deque = collections.deque()

    def wait(self):
        now = time.time()
        while self.timestamps and self.timestamps[0] <= now - self.period:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.max_calls:
            sleep_time = self.period - (now - self.timestamps[0]) + 0.5
            if sleep_time > 0:
                log(f"  ⏳ Rate limit: waiting {sleep_time:.1f}s...")
                time.sleep(sleep_time)
        self.timestamps.append(time.time())


gemini_limiter = RateLimiter(max_calls=GEMINI_RPM_LIMIT, period=60.0)


def make_gemini_dedup_fn(client):
    """Return a gemini_fn callable for find_duplicate() borderline checks."""
    if not client:
        return None
    def _check(ev_a: dict, ev_b: dict) -> bool | None:
        try:
            from google.genai import types as _types
            from dedup import build_dedup_prompt
            gemini_limiter.wait()
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=build_dedup_prompt(ev_a, ev_b),
                config=_types.GenerateContentConfig(temperature=0.0, max_output_tokens=5),
            )
            answer = resp.text.strip().lower()
            result = answer.startswith("yes")
            log(f"    🤖 Gemini dedup: '{ev_a['name']}' vs '{ev_b['name']}' → {'duplicate' if result else 'different'}")
            return result
        except Exception as e:
            log(f"    🤖 Gemini dedup failed: {e}")
            return None
    return _check


# -------------------- Facebook scraping --------------------
def load_fb_pages() -> list[dict]:
    """
    Load Facebook page event URLs from fb_accounts.txt.
    Supports optional filters:  URL |filter:text  #comment
    Example: https://facebook.com/fofkbh/events |filter:Birkedommervej
    """
    pages = []
    path = Path(FB_ACCOUNTS_FILE)
    if not path.exists():
        log(f"Accounts file not found: {FB_ACCOUNTS_FILE}")
        return pages
    for line in path.read_text().splitlines():
        line = line.split("#")[0].strip()  # Strip inline comments
        if not line:
            continue

        # Extract |filter: and |exclude: if present (order-independent)
        location_filter = None
        exclude_filter = None
        # Process |exclude: first so it doesn't interfere with |filter:
        if "|exclude:" in line:
            parts = line.split("|exclude:", 1)
            line = parts[0].strip()
            exclude_filter = parts[1].strip()
        if "|filter:" in line:
            parts = line.split("|filter:", 1)
            line = parts[0].strip()
            location_filter = parts[1].strip()

        # Handle profile.php?id=...&sk=events format
        if "sk=events" in line or "/events" in line:
            pass  # Already points to events
        elif "profile.php" in line:
            sep = "&" if "?" in line else "?"
            line = line + sep + "sk=events"
        else:
            line = line.rstrip("/") + "/events"

        pages.append({"url": line, "filter": location_filter, "exclude": exclude_filter})
    return pages


def extract_page_name(url: str) -> str:
    """Extract page name from a Facebook URL."""
    # Handle profile.php?id=DIGITS format
    id_match = re.search(r"[?&]id=(\d+)", url)
    if id_match:
        return f"fb-{id_match.group(1)}"
    # Handle facebook.com/PageName/events format
    parts = url.rstrip("/").split("/")
    for i, part in enumerate(parts):
        if part == "events" and i > 0:
            return parts[i - 1]
    return parts[-1] if parts else "unknown"


def scrape_facebook_events(page_url: str) -> list[dict]:
    """
    Use Playwright to load a Facebook /events page and extract event data.
    Returns a list of event dicts with: title, date_text, location, url, page_name.
    """
    page_name = extract_page_name(page_url)
    events = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Use saved cookies if available (from fb_login.py)
        context_opts = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 900},
            "locale": "en-US",
        }
        if os.path.exists(FB_COOKIES_FILE):
            context_opts["storage_state"] = FB_COOKIES_FILE
            if DEBUG:
                log("  Using saved Facebook cookies")
        else:
            if DEBUG:
                log("  No cookies found — scraping as logged-out user")

        context = browser.new_context(**context_opts)
        page = context.new_page()

        try:
            log(f"  Loading {page_url} ...")
            page.goto(page_url, wait_until="domcontentloaded", timeout=30000)

            # Wait a bit for JS to render content
            time.sleep(3)

            # Try to dismiss cookie/login popups
            for selector in [
                'div[aria-label="Close"]',
                'button:has-text("Decline optional cookies")',
                'button:has-text("Not now")',
                'div[role="button"]:has-text("Close")',
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        time.sleep(0.5)
                except Exception:
                    pass

            # ── Detect Past-only pages ──
            # Facebook shows tabs like "Upcoming" and "Past".
            # If the page only has a "Past" heading/tab selected with no
            # "Upcoming" section, there are no future events — skip entirely.
            page_text_full = page.evaluate("() => document.body.innerText") or ""
            has_upcoming = bool(re.search(r"\bUpcoming\b", page_text_full))
            has_past_only = (
                bool(re.search(r"\bPast\b", page_text_full)) and not has_upcoming
            )
            if has_past_only:
                log(f"  ⏭️  Only past events found on this page — skipping")
                browser.close()
                return events  # empty list

            # If there's both Upcoming and Past, try clicking "Upcoming" tab
            if has_upcoming:
                try:
                    upcoming_tab = page.query_selector(
                        'a:has-text("Upcoming"), '
                        'div[role="tab"]:has-text("Upcoming"), '
                        'span:has-text("Upcoming")'
                    )
                    if upcoming_tab:
                        upcoming_tab.click()
                        time.sleep(2)
                        if DEBUG:
                            log("  Clicked 'Upcoming' tab")
                except Exception:
                    pass  # If click fails, continue with current view

            # Scroll down to load more events
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)

            # Extract the full page text and all links for Gemini to parse
            # Also try to find structured event cards
            event_links = []

            # Strategy 1: Find links that look like facebook.com/events/DIGITS
            all_links = page.query_selector_all("a[href]")
            for link in all_links:
                try:
                    href = link.get_attribute("href") or ""
                    if "/events/" in href and re.search(r"/events/\d+", href):
                        # Get the surrounding text (parent container)
                        parent = link
                        text = ""
                        # Walk up a few levels to get context
                        for _ in range(5):
                            parent = parent.evaluate_handle(
                                "el => el.parentElement"
                            )
                            text = parent.evaluate("el => el.innerText") or ""
                            if len(text) > 20:
                                break

                        # Normalize the URL — preserve event_time_id for recurring events
                        event_id_match = re.search(r"/events/(\d+)", href)
                        if event_id_match:
                            event_url = f"https://www.facebook.com/events/{event_id_match.group(1)}/"
                            # Recurring events have ?event_time_id=... to distinguish dates
                            time_id_match = re.search(r"event_time_id=(\d+)", href)
                            if time_id_match:
                                event_url += f"?event_time_id={time_id_match.group(1)}"
                            event_links.append({
                                "url": event_url,
                                "text": text.strip(),
                                "page_name": page_name,
                            })
                except Exception as e:
                    if DEBUG:
                        log(f"  Link extraction error: {e}")

            # Deduplicate by event URL.
            # For recurring events: if we have event_time_id versions,
            # skip the base URL (it's redundant / just shows the next date).
            seen_urls = set()
            base_event_ids_with_time_ids = set()
            for ev in event_links:
                if "event_time_id" in ev["url"]:
                    eid = re.search(r"/events/(\d+)/", ev["url"])
                    if eid:
                        base_event_ids_with_time_ids.add(eid.group(1))
            for ev in event_links:
                if ev["url"] in seen_urls:
                    continue
                # Skip base URL if event_time_id versions exist
                eid = re.search(r"/events/(\d+)/", ev["url"])
                if (eid and eid.group(1) in base_event_ids_with_time_ids
                        and "event_time_id" not in ev["url"]):
                    continue
                seen_urls.add(ev["url"])
                events.append(ev)

            # If no structured links found, fall back to full page text for Gemini
            if not events:
                page_text = page.evaluate("() => document.body.innerText") or ""
                if page_text.strip():
                    events.append({
                        "url": page_url,
                        "text": page_text[:5000],  # Limit text size
                        "page_name": page_name,
                        "is_full_page": True,
                    })

        except PwTimeout:
            log(f"  ⚠️ Timeout loading {page_url}")
        except Exception as e:
            log(f"  ❌ Error scraping {page_url}: {e}")
        finally:
            browser.close()

    return events


def fetch_event_name_from_page(event_url: str) -> str | None:
    """
    Visit an individual Facebook event page and extract the event name.
    Used as a fallback when the events listing card doesn't include the name.
    Returns the event name or None.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_opts = {
                "user_agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1280, "height": 900},
                "locale": "en-US",
            }
            if os.path.exists(FB_COOKIES_FILE):
                context_opts["storage_state"] = FB_COOKIES_FILE

            context = browser.new_context(**context_opts)
            page = context.new_page()
            page.goto(event_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            # Dismiss popups
            for selector in [
                'div[aria-label="Close"]',
                'button:has-text("Decline optional cookies")',
                'button:has-text("Not now")',
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        time.sleep(0.3)
                except Exception:
                    pass

            # Try multiple strategies to find the event name
            # Strategy 1: og:title meta tag
            og_title = page.evaluate(
                '() => document.querySelector(\'meta[property="og:title"]\')?.content'
            )
            if og_title and og_title.strip() and "Facebook" not in og_title:
                browser.close()
                return og_title.strip()

            # Strategy 2: page title (often "Event Name | Facebook")
            title = page.title() or ""
            if " | Facebook" in title:
                name = title.replace(" | Facebook", "").strip()
                if name and len(name) > 3:
                    browser.close()
                    return name

            # Strategy 3: first large heading on the page
            heading = page.evaluate("""
                () => {
                    const h = document.querySelector('h1, h2, [role="heading"]');
                    return h ? h.innerText : null;
                }
            """)
            if heading and heading.strip() and len(heading.strip()) > 3:
                browser.close()
                return heading.strip()

            browser.close()
    except Exception as e:
        if DEBUG:
            log(f"  Could not fetch event page title: {e}")
    return None


def is_multi_day_event(text: str) -> bool:
    """
    Detect if card text indicates a multi-day event.
    Facebook shows multi-day events like:
      "FRI, MAR 27 AT 8 AM – SUN, MAR 29 AT 3 PM"
      "MAR 27 – MAR 29"
      "FEBRUARY 28 – MARCH 2"
      "FEB 28 - MAR 2"
    """
    # Pattern 1: two abbreviated dates separated by – or -
    date_pat = r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?\s+\d{1,2}"
    multi = re.search(
        date_pat + r".*?[–\-]\s*(?:(?:MON|TUE|WED|THU|FRI|SAT|SUN)[A-Z]*,?\s+)?" + date_pat,
        text, re.IGNORECASE,
    )
    if multi:
        return True

    # Pattern 2: full month names "February 28 – March 2"
    full_date_pat = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}"
    multi2 = re.search(
        full_date_pat + r".*?[–\-]\s*" + full_date_pat,
        text, re.IGNORECASE,
    )
    if multi2:
        return True

    # Pattern 3: "3 days" or "X-day event" or "weekend" hints
    if re.search(r"\b\d+\s*days?\b", text, re.IGNORECASE):
        return True

    return False


def fetch_event_page_text(event_url: str) -> str | None:
    """
    Visit an individual Facebook event page and extract the full visible text.
    Used for multi-day events to get the description with per-day schedules.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_opts = {
                "user_agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1280, "height": 900},
                "locale": "en-US",
            }
            if os.path.exists(FB_COOKIES_FILE):
                context_opts["storage_state"] = FB_COOKIES_FILE

            context = browser.new_context(**context_opts)
            page = context.new_page()
            page.goto(event_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)

            # Dismiss popups
            for selector in [
                'div[aria-label="Close"]',
                'button:has-text("Decline optional cookies")',
                'button:has-text("Not now")',
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        time.sleep(0.3)
                except Exception:
                    pass

            # Try clicking "See more" to expand the description
            try:
                see_more = page.query_selector('div[role="button"]:has-text("See more")')
                if see_more:
                    see_more.click()
                    time.sleep(0.5)
            except Exception:
                pass

            page_text = page.evaluate("() => document.body.innerText") or ""
            browser.close()
            return page_text[:8000] if page_text.strip() else None
    except Exception as e:
        if DEBUG:
            log(f"  Could not fetch event page text: {e}")
    return None


def parse_multi_day_with_gemini(client, page_text: str, event_url: str,
                                page_name: str) -> list[dict]:
    """
    Use Gemini to parse a multi-day Facebook event page into per-day entries.
    Returns a list of event dicts, one per day.
    """
    prompt = f"""This is a multi-day Facebook event from "{page_name}".

Full page text:
{page_text[:6000]}

Your task:
1. This event spans MULTIPLE days. You MUST create a SEPARATE entry for EACH day/session.
2. READ THE DESCRIPTION CAREFULLY — it often contains a detailed schedule with specific
   dates, times, and activities for each day. Use those to create per-day entries.
3. If the description lists specific sessions (e.g. "Friday 17:00-20:00 Workshop A",
   "Saturday 10:00-16:00 Workshop B"), create one event per session with those times.
4. If no per-day breakdown is in the description, create one entry per day the event runs.

Respond ONLY with valid JSON:

{{
  "events": [
    {{
      "event_name": "Name of the event (optionally with day-specific suffix like 'Event Name - Day 1')",
      "organizer": "Who is organizing (use '{page_name}' if unclear)",
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM (24h format)" or null,
      "end_time": "HH:MM (24h format)" or null,
      "location": "Venue name only (no street address, postal code, or city)" or null,
      "description": "What happens on THIS specific day/session (from the description)"
    }}
  ]
}}

Rules:
- The current date is {datetime.now().strftime('%Y-%m-%d')}.
- You MUST create MULTIPLE entries — one per day or session. A single entry is WRONG for a multi-day event.
- Pay special attention to the event DESCRIPTION — it often has the per-day schedule.
- If per-day times are listed in the description, use those specific times for each day.
- If the description does NOT mention specific times for each day, set start_time and end_time to null.
  Do NOT invent times or use the overall event date-range start/end as individual day times.
- NEVER use a venue/location name as the event_name.
- If the description mentions both "doors" (or "døre åbner") and "show" (or "start") times, use the SHOW/START time as start_time, NOT the doors time.
- If NO events are found, return {{"events": []}}
- Respond ONLY with the JSON, no extra text."""

    try:
        from google import genai
        from google.genai import types

        gemini_limiter.wait()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4000,
            ),
        )

        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(result_text)
        return result.get("events", [])
    except Exception as e:
        log(f"  Gemini multi-day parse failed: {e}")
        return []


def fetch_recurring_dates(event_url: str) -> list[dict] | None:
    """
    Visit a Facebook event page and check if it's a recurring event.
    If so, extract all upcoming dates.
    Returns a list of dicts [{event_date, start_time, event_time_url}, ...] or None.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_opts = {
                "user_agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1280, "height": 900},
                "locale": "en-US",
            }
            if os.path.exists(FB_COOKIES_FILE):
                context_opts["storage_state"] = FB_COOKIES_FILE

            context = browser.new_context(**context_opts)
            page = context.new_page()
            page.goto(event_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            # Dismiss popups
            for selector in [
                'div[aria-label="Close"]',
                'button:has-text("Decline optional cookies")',
                'button:has-text("Not now")',
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        time.sleep(0.3)
                except Exception:
                    pass

            page_text = page.evaluate("() => document.body.innerText") or ""

            # Check if this is a recurring event — look for multiple date lines
            # Facebook recurring events show upcoming dates with links like
            # /events/ID/?event_time_id=XXX
            recurring_links = []
            all_links = page.query_selector_all("a[href]")
            for link in all_links:
                try:
                    href = link.get_attribute("href") or ""
                    if "event_time_id" in href:
                        # Get the text around this link (the date)
                        link_text = link.evaluate("el => el.innerText") or ""
                        # Also check parent for more context
                        parent_text = link.evaluate(
                            "el => el.parentElement ? el.parentElement.innerText : ''"
                        ) or ""
                        text_to_parse = parent_text if len(parent_text) > len(link_text) else link_text

                        time_id_match = re.search(r"event_time_id=(\d+)", href)
                        event_id_match = re.search(r"/events/(\d+)", href)
                        if time_id_match and event_id_match:
                            time_url = (
                                f"https://www.facebook.com/events/"
                                f"{event_id_match.group(1)}/"
                                f"?event_time_id={time_id_match.group(1)}"
                            )
                            parsed = try_parse_date_from_text(text_to_parse)
                            if parsed and parsed.get("event_date"):
                                recurring_links.append({
                                    "event_date": parsed["event_date"],
                                    "start_time": parsed.get("start_time"),
                                    "event_time_url": time_url,
                                })
                except Exception:
                    pass

            browser.close()

            # Deduplicate by date + time_url
            if recurring_links:
                seen = set()
                deduped = []
                for rl in recurring_links:
                    key = rl["event_time_url"]
                    if key not in seen:
                        seen.add(key)
                        deduped.append(rl)
                # Only treat as recurring if we found 2+ dates
                if len(deduped) >= 2:
                    # Filter out past dates
                    today = date.today()
                    future = [
                        d for d in deduped
                        if date.fromisoformat(d["event_date"]) >= today
                    ]
                    if future:
                        if DEBUG:
                            log(f"  🔄 Recurring event with {len(future)} upcoming date(s)")
                        return future

    except Exception as e:
        if DEBUG:
            log(f"  Could not check recurring dates: {e}")
    return None


# -------------------- AI Analysis (Gemini) --------------------
def parse_event_with_gemini(client, raw_event: dict) -> list[dict]:
    """
    Use Gemini to parse raw event text into structured event data.
    Returns a list of event dicts.
    """
    text = raw_event.get("text", "")
    page_name = raw_event.get("page_name", "unknown")
    event_url = raw_event.get("url", "")
    is_full_page = raw_event.get("is_full_page", False)

    if not text:
        return []

    if is_full_page:
        task = "Extract ALL events from this Facebook events page"
    else:
        task = "Parse this Facebook event card"

    prompt = f"""{task} for the page "{page_name}".

Raw text:
{text[:3000]}

Your task:
1. Extract ALL events you can find. Each event should have a name, date, time, and location.
2. If the same event happens on multiple dates, create a SEPARATE entry for each date.

Respond ONLY with valid JSON:

{{
  "events": [
    {{
      "event_name": "Name of the event",
      "organizer": "Who is organizing (use '{page_name}' if unclear)",
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM (24h format)" or null,
      "end_time": "HH:MM (24h format)" or null,
      "location": "Venue/place NAME only (e.g. 'Storm B Café', 'Flere Fugle'), do NOT include street address, postal code, or city" or null,
      "description": "One-sentence summary"
    }}
  ]
}}

Rules:
- The current date is {datetime.now().strftime('%Y-%m-%d')}. If no year is mentioned, assume the next upcoming occurrence.
- NEVER use a venue/location name as the event_name. The event_name should be the actual name of the event (e.g. "Sunday Deep" not "Rört").
- If the text mentions both "doors" (or "døre åbner") and "show" (or "start") times, use the SHOW/START time as start_time, NOT the doors time.
- If NO events are found, return {{"events": []}}
- Respond ONLY with the JSON, no extra text."""

    try:
        from google import genai
        from google.genai import types

        gemini_limiter.wait()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4000,
            ),
        )

        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(result_text)
        return result.get("events", [])
    except Exception as e:
        log(f"  Gemini analysis failed: {e}")
        return []


def try_parse_date_from_text(text: str) -> dict | None:
    """
    Attempt to parse event info directly from text without Gemini.
    Handles: "SAT, FEB 22 AT 7 PM", "Today at 7 PM", "Tomorrow at 3 PM"
    """
    from datetime import timedelta
    result = {}

    # Check for "Today" / "Tomorrow" first
    today_match = re.search(r"\bToday\b", text, re.IGNORECASE)
    tomorrow_match = re.search(r"\bTomorrow\b", text, re.IGNORECASE)

    if today_match:
        result["event_date"] = date.today().isoformat()
    elif tomorrow_match:
        result["event_date"] = (date.today() + timedelta(days=1)).isoformat()
    else:
        # Try standard date: "SAT, FEB 22 AT 7 PM" or "Saturday, February 22, 2026"
        date_match = re.search(
            r"(?:MON|TUE|WED|THU|FRI|SAT|SUN)[A-Z]*,?\s+"
            r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+(\d{1,2})"
            r"(?:,?\s*(\d{4}))?",
            text, re.IGNORECASE,
        )
        if date_match:
            month_str, day_str, year_str = date_match.groups()
            month_map = {
                "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
            }
            month = month_map.get(month_str[:3].upper())
            if month:
                year = int(year_str) if year_str else datetime.now().year
                try:
                    d = date(year, month, int(day_str))
                    # No year given → use current year. If it's in the past,
                    # the date filter downstream will skip it.
                    result["event_date"] = d.isoformat()
                except ValueError:
                    pass

    # Try to find time
    time_match = re.search(
        r"(?:AT\s+)?(\d{1,2})(?::(\d{2}))?\s*(AM|PM)",
        text, re.IGNORECASE,
    )
    if time_match:
        h, m, ampm = time_match.groups()
        h = int(h)
        m = int(m) if m else 0
        if ampm.upper() == "PM" and h != 12:
            h += 12
        elif ampm.upper() == "AM" and h == 12:
            h = 0
        result["start_time"] = f"{h:02d}:{m:02d}"

    return result if result else None


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
    """Build dedup index: URL -> page_id. Also returns flat list for fuzzy matching."""
    url_to_page: dict[str, str] = {}
    all_entries: list[dict] = []
    payload: dict = {"page_size": 100}
    pages_fetched = 0
    while True:
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
                    log(f"  Notion API error (attempt {attempt + 1}/3), retrying in 10s… ({e})")
                    time.sleep(10)
                else:
                    raise
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code >= 500 and attempt < 2:
                    log(f"  Notion API {e.response.status_code} (attempt {attempt + 1}/3), retrying in 10s…")
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
            location_parts = props.get("Location", {}).get("rich_text", [])
            location = location_parts[0]["text"]["content"] if location_parts else ""
            time_parts = props.get("Start Time", {}).get("rich_text", [])
            start_time = time_parts[0]["text"]["content"] if time_parts else ""
            if url_val:
                url_to_page[url_val] = page["id"]
            all_entries.append({
                "name": name,
                "start_date": start_date,
                "source": source.lstrip("@"),
                "page_id": page["id"],
                "url": url_val,
                "location": location,
                "start_time": start_time,
            })
        pages_fetched += 1
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
        if pages_fetched >= 100:
            break
    if DEBUG:
        log("Preloaded Notion entries:", len(url_to_page))
    return url_to_page, all_entries


def build_notion_props(ev: dict, is_update: bool = False, merge_only: bool = False) -> dict:
    """Build Notion properties using the unified column schema.

    Args:
        ev: event dict with scraped data
        is_update: if True, skip user-editable fields (Tags, Location,
                   Description) so manual corrections in Notion are preserved.
        merge_only: if True, only patch IG-specific additive fields (ig_handle, to_tag)
                   and duplicate_of. Used when merging a lower-priority source into an
                   existing higher-priority entry.
    """
    # Merge-only mode: add metadata + enrich name/description if this source has more info
    if merge_only:
        props = {}
        if ev.get("ig_handle"):
            props["Instagramhandle"] = {"rich_text": [{"text": {"content": ev["ig_handle"][:2000]}}]}
        if ev.get("to_tag"):
            props["To tag"] = {"rich_text": [{"text": {"content": ev["to_tag"][:2000]}}]}
        if ev.get("duplicate_of"):
            props["Duplicate of"] = {"rich_text": [{"text": {"content": ev["duplicate_of"][:2000]}}]}
        if ev.get("name_is_richer"):
            name = ev.get("event_name") or ""
            if name:
                props["Event Name"] = {"title": [{"text": {"content": name[:2000]}}]}
        if ev.get("description_is_richer"):
            desc = ev.get("description") or ""
            if desc:
                props["Description"] = {"rich_text": [{"text": {"content": desc[:2000]}}]}
        if ev.get("location"):
            loc_id = find_location_id(ev["location"], NOTION_TOKEN)
            if loc_id:
                props["Locations"] = {"relation": [{"id": loc_id}]}
        return props

    props = {}

    # Name (title) — set on create, or on update only if incoming name is richer
    if not is_update or ev.get("name_is_richer"):
        name = ev.get("event_name") or "Untitled Event"
        props["Event Name"] = {"title": [{"text": {"content": name[:2000]}}]}

    if ev.get("url"):
        props["Event Link"] = {"url": ev["url"]}

    if ev.get("start_date"):
        props["Start Date"] = {"date": {"start": ev["start_date"]}}

    if ev.get("end_date"):
        props["End Date"] = {"date": {"start": ev["end_date"]}}

    if ev.get("start_time_disp"):
        props["Start Time"] = {
            "rich_text": [{"text": {"content": ev["start_time_disp"]}}]
        }

    if ev.get("end_time_disp"):
        props["End Time"] = {
            "rich_text": [{"text": {"content": ev["end_time_disp"]}}]
        }

    # Location text — only set on create, preserve manual edits on update
    if ev.get("location") and not is_update:
        props["Location"] = {
            "rich_text": [{"text": {"content": ev["location"][:2000]}}]
        }
    # Locations relation — always set when resolvable (derived data, not user-editable)
    if ev.get("location"):
        loc_id = find_location_id(ev["location"], NOTION_TOKEN)
        if loc_id:
            props["Locations"] = {"relation": [{"id": loc_id}]}

    if ev.get("source"):
        props["Source"] = {
            "rich_text": [{"text": {"content": ev["source"][:2000]}}]
        }

    if ev.get("source_type"):
        props["Source Type"] = {"select": {"name": ev["source_type"]}}

    if ev.get("organizer"):
        props["Organizer"] = {
            "rich_text": [{"text": {"content": ev["organizer"][:2000]}}]
        }

    # Description — set on create, or on update only if incoming is richer
    if ev.get("description") and (not is_update or ev.get("description_is_richer")):
        props["Description"] = {
            "rich_text": [{"text": {"content": ev["description"][:2000]}}]
        }

    # Possible Duplicate (checkbox) — only set on create, preserve manual review on update
    if ev.get("possible_duplicate") is not None and not is_update:
        props["Possible Duplicate"] = {"checkbox": bool(ev["possible_duplicate"])}

    # Instagramhandle (rich_text) — filled from source_mapping.csv if available
    if ev.get("ig_handle"):
        props["Instagramhandle"] = {
            "rich_text": [{"text": {"content": ev["ig_handle"][:2000]}}]
        }

    # To tag (rich_text) — not typically available from FB
    if ev.get("to_tag"):
        props["To tag"] = {
            "rich_text": [{"text": {"content": ev["to_tag"][:2000]}}]
        }

    # Tags (multi_select) — set on create, or on update if the existing entry had no tag
    if ev.get("tags_list") and (not is_update or ev.get("set_tag_on_update")):
        props["Tags"] = {"multi_select": [{"name": t} for t in ev["tags_list"]]}

    # Review Notes (rich_text) — flagged for manual review (e.g. unknown location)
    if ev.get("review_notes"):
        props["Review Notes"] = {
            "rich_text": [{"text": {"content": ev["review_notes"][:2000]}}]
        }

    # Duplicate of (rich_text) — cross-platform merge note (e.g. "Also at: @handle")
    if ev.get("duplicate_of"):
        props["Duplicate of"] = {
            "rich_text": [{"text": {"content": ev["duplicate_of"][:2000]}}]
        }

    return props


def make_dedup_key(ev: dict) -> str:
    """For Facebook, the event URL alone is the unique key."""
    return ev.get("url", "")


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


def notion_update(page_id: str, ev: dict, merge_only: bool = False):
    payload = {"properties": build_notion_props(ev, is_update=True, merge_only=merge_only)}
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


# -------------------- PER-PAGE FUNCTION (used by runner) --------------------
def scrape_page_entry(page_entry, client, existing, all_entries, source_mapping, fb_to_ig):
    """
    Scrape a single Facebook page for events.
    Mutates `existing` and `all_entries` in-place as new entries are created.
    Returns dict: {created, updated, skipped, flagged_dupes, total_events}
    """
    created = updated = skipped = flagged_dupes = total_events = 0

    page_url = page_entry["url"]
    location_filter = page_entry.get("filter")
    exclude_filter = page_entry.get("exclude")
    page_name = extract_page_name(page_url)

    raw_events = scrape_facebook_events(page_url)
    log(f"  Found {len(raw_events)} raw event card(s)")

    for raw_ev in raw_events:
        event_url = raw_ev.get("url", page_url)
        text = raw_ev.get("text", "")

        # Apply include location filter if set.
        # Supports semicolon-separated OR terms, e.g. "Utterslev Mose;NV"
        if location_filter:
            terms = [t.strip().lower() for t in location_filter.split(";") if t.strip()]
            text_lower = text.lower()
            if not any(t in text_lower for t in terms):
                if DEBUG:
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    title = lines[1] if len(lines) > 1 else lines[0] if lines else "?"
                    log(f"  Filtered out (no '{location_filter}'): {title[:80]}")
                continue

        # Apply exclude location filter if set
        if exclude_filter and exclude_filter.lower() in text.lower():
            if DEBUG:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                title = lines[1] if len(lines) > 1 else lines[0] if lines else "?"
                log(f"  Filtered out (contains '{exclude_filter}'): {title[:80]}")
            continue

        parsed_events = []

        # Parse event text with regex (Facebook events are structured enough)
        if text:
            fallback = try_parse_date_from_text(text)
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            date_pattern = re.compile(
                r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)", re.IGNORECASE
            )
            skip_patterns = re.compile(
                r"^(Event by|Interested|Going|·|Log In|Forgot)", re.IGNORECASE
            )
            # Address-like lines: "Street 42, 2400" or "Street 42, 2400 City"
            address_pattern = re.compile(
                r"^[A-Za-zÆØÅæøå\s]+\d+.*,\s*\d{4}\b"
            )
            title = "Facebook Event"
            location = None
            organizer = page_name
            for i, line in enumerate(lines):
                if date_pattern.match(line) or skip_patterns.match(line):
                    continue
                # If line looks like an address, save as location and keep looking for title
                if address_pattern.match(line):
                    if not location:
                        location = line.strip()
                    continue
                title = line[:200]
                # Look at next lines for location / organizer
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j]
                    if skip_patterns.match(next_line) or date_pattern.match(next_line):
                        continue
                    if "·" in next_line:
                        location = next_line.replace("·", "").strip()
                    elif address_pattern.match(next_line):
                        location = next_line.strip()
                    elif not location:
                        location = next_line.strip()
                    break
                for line in lines:
                    if line.lower().startswith("event by "):
                        organizer = line[9:].strip()
                        break
                break

            # If title is still the default or looks like the venue name,
            # try fetching the real event name from the event page
            title_is_bad = (
                title == "Facebook Event"
                or title.lower().strip() == page_name.lower().strip()
                or title.lower().strip() in (location or "").lower()
            )
            if title_is_bad and event_url and event_url != page_url:
                fetched_name = fetch_event_name_from_page(event_url)
                if fetched_name:
                    title = fetched_name[:200]
                    log(f"  Fetched event name from page: {title}")

            if fallback:
                parsed_events = [{
                    "event_name": title,
                    "organizer": organizer,
                    "event_date": fallback.get("event_date"),
                    "start_time": fallback.get("start_time"),
                    "end_time": None,
                    "location": location,
                    "description": text[:200],
                }]

            # ── Check for multi-day event: visit event page for per-day details ──
            _is_multi = is_multi_day_event(text)
            if (_is_multi and client
                    and event_url and event_url != page_url):
                log(f"  🗓️  Multi-day event detected — fetching event page for details...")
                page_text = fetch_event_page_text(event_url)
                if page_text:
                    multi_events = parse_multi_day_with_gemini(
                        client, page_text, event_url, page_name
                    )
                    if multi_events and len(multi_events) > 1:
                        log(f"  🗓️  Parsed {len(multi_events)} day(s) from multi-day event")
                        parsed_events = multi_events
                    elif multi_events:
                        log(f"  🗓️  Gemini returned only 1 entry for multi-day event — keeping it")
                        parsed_events = multi_events
                    else:
                        log(f"  🗓️  Multi-day parsing returned no results — keeping fallback")
                else:
                    log(f"  🗓️  Could not fetch event page text")

            # ── Check for recurring event: visit event page to find all dates ──
            # Only do this if the listing page didn't already give us event_time_id links
            if (len(parsed_events) == 1
                    and event_url and event_url != page_url
                    and "event_time_id" not in event_url):
                recurring = fetch_recurring_dates(event_url)
                if recurring:
                    base = parsed_events[0]
                    parsed_events = []
                    for rd in recurring:
                        entry = dict(base)
                        entry["event_date"] = rd["event_date"]
                        entry["start_time"] = rd.get("start_time") or base.get("start_time")
                        entry["_event_time_url"] = rd.get("event_time_url")
                        parsed_events.append(entry)

        if not parsed_events:
            if DEBUG:
                log(f"  No events parsed from: {event_url}")
            skipped += 1
            continue

        log(f"  Parsed {len(parsed_events)} event(s) from: {event_url}")
        total_events += len(parsed_events)

        max_date = date.today() + timedelta(days=180)
        for event_data in parsed_events:
            event_date_str = event_data.get("event_date")
            if event_date_str:
                try:
                    ev_date_obj = date.fromisoformat(event_date_str)
                    if ev_date_obj < date.today():
                        if DEBUG:
                            log(f"  Skipping past event: {event_data.get('event_name')} ({event_date_str})")
                        continue
                    if ev_date_obj > max_date:
                        if DEBUG:
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
                    "source": page_name,
                    "location": event_data.get("location"),
                    "description": event_data.get("description"),
                    "url": event_url,
                    "source_type": "Facebook",
                    "ig_handle": fb_to_ig.get(_extract_fb_id(page_url).lower()),
                    "date": date.today().isoformat(),
                }, log_fn=log)
                continue

            # Route deals/special-price announcements to Deals DB
            if is_deal(event_data.get("event_name", ""), event_data.get("description", "")):
                push_to_deals_db({
                    "event_name": event_data.get("event_name"),
                    "place": event_data.get("location"),
                    "source": page_name,
                    "description": event_data.get("description"),
                    "url": event_url,
                    "source_type": "Facebook",
                    "ig_handle": fb_to_ig.get(_extract_fb_id(page_url).lower()),
                    "date": date.today().isoformat(),
                }, log_fn=log)
                continue

            # Skip retreats from Rört — they're not in Nordvest
            if page_name.lower() in ("rortcph", "rort copenhagen"):
                ev_text = f"{event_data.get('event_name', '')} {event_data.get('description', '')}".lower()
                if "retreat" in ev_text or "retræte" in ev_text:
                    log(f"  Skipping Rört retreat: {event_data.get('event_name')}")
                    continue

            # Use event_time_url if available (recurring event), otherwise base event_url
            this_event_url = event_data.pop("_event_time_url", None) or event_url

            # Use the same extraction logic as load_fb_to_ig_map for consistent keys
            fb_key = _extract_fb_id(page_url).lower()
            ig_handle = fb_to_ig.get(fb_key) or fb_to_ig.get(page_name.lower())

            # Default locations for FB pages where venue = page itself
            # Keys are the lowercased result of extract_page_name(fb_url)
            _FB_DEFAULT_LOCATIONS = {
                "rabenssaloner": "Rabens Saloner",
                "cafegazounv": "Cafe Gazou",
                "lygtenstation": "Lygten Station",
                "grundtvigs.kirke": "Grundtvigs Kirke",
                "rortcph": "Rört",
                "ungdomshusetd61": "Ungdomshuset",
                "goldschmidtsakademi": "Goldschmidts Musikakademi",
                "kapernaumskirken": "Kapernaumskirken",
                "makerspacenv": "MakerSpace NV",
                "justsaunadk": "Just Sauna",
            }
            location = _FB_DEFAULT_LOCATIONS.get(page_name.lower()) or event_data.get("location")
            # Normalize full addresses to venue names (e.g. "Flere Fugle, Frederikssundsvej 35, 2400..." → "Flere Fugle")
            cleaned = clean_location(location) if location else None
            if cleaned:
                location = cleaned

            ev = {
                "event_name": event_data.get("event_name"),
                "organizer": event_data.get("organizer"),
                "start_date": event_date_str,
                "end_date": event_date_str,
                "start_time_disp": to_12h(event_data.get("start_time")),
                "end_time_disp": to_12h(event_data.get("end_time")),
                "location": location,
                "description": event_data.get("description"),
                "source_type": "Facebook",
                "source": page_name,
                "url": this_event_url,
                "ig_handle": ig_handle,
                "tag": classify_event(
                    event_data.get("event_name", ""),
                    event_data.get("description", ""),
                    event_data.get("organizer", ""),
                ),
            }
            _primary = ev["tag"]
            _seasonal = classify_seasonal(event_data.get("event_name", ""), event_data.get("description", ""))
            ev["tags_list"] = ([_primary] if _primary else []) + [s for s in _seasonal if s != _primary]

            # Skip events at excluded locations (not in Nordvest)
            if is_excluded_location(ev.get("location", "")):
                log(f"  Skipping excluded location: {ev.get('event_name')} @ {ev.get('location')}")
                continue

            # Flag unknown locations for manual review
            if is_unknown_location(ev.get("location", "")):
                ev["review_notes"] = f"⚠️ Unknown location: {ev['location']}"
                log(f"  ⚠️ Unknown location flagged for review: {ev.get('event_name')} @ {ev.get('location')}")

            dupe = find_duplicate(
                ev.get("event_name", ""),
                ev.get("start_date", ""),
                page_name,
                all_entries,
                source_mapping,
                event_location=ev.get("location", ""),
                event_time=ev.get("start_time", ""),
                gemini_fn=make_gemini_dedup_fn(client),
                resolve_coords_fn=lambda loc: find_location_coords(loc, NOTION_TOKEN),
            )

            dedup_key = make_dedup_key(ev)
            page_id = existing.get(dedup_key)

            # Fallback: if URL-based dedup missed, try name+date+source/location fuzzy match
            if not page_id:
                ev_name = ev.get("event_name", "")
                ev_date = ev.get("start_date", "")
                ev_loc = ev.get("location", "")
                for entry in all_entries:
                    if entry.get("start_date", "")[:10] != ev_date[:10]:
                        continue
                    name_sim = similarity(ev_name, entry.get("name", ""))
                    if name_sim < 0.80:
                        continue
                    # Also require source or location similarity
                    src_ok = are_sources_related(page_name, entry.get("source", ""), source_mapping) or \
                             similarity(page_name, entry.get("source", "")) >= 0.85
                    loc_ok = ev_loc and entry.get("location") and \
                             similarity(ev_loc, entry.get("location", "")) >= 0.85
                    if src_ok or loc_ok:
                        page_id = entry.get("page_id")
                        if DEBUG:
                            log(f"    🔗 Fuzzy name match ({name_sim:.0%}): '{entry.get('name')}' → updating")
                        break
                if DEBUG and not page_id:
                    log(f"    🔍 Dedup miss: key={dedup_key[:100]}")

            # Cross-platform merge: find_duplicate found a match from a different source
            merge_only = False
            if dupe and not page_id:
                current_priority = get_source_priority(event_url)
                dupe_priority = get_source_priority(dupe.get("url", ""))
                page_id = dupe["page_id"]
                flagged_dupes += 1
                dupe_date = (dupe.get('start_date') or '')[:10]
                dupe_src = dupe.get('source', '')

                if current_priority > dupe_priority:
                    # Current (FB) is lower priority than existing (website) — merge FB metadata in
                    merge_only = True
                    ev["duplicate_of"] = f"Also at: {dupe_src} ({dupe_date})"
                    # Check if FB has a richer name than the existing entry
                    existing_name = dupe.get("name") or ""
                    incoming_name = ev.get("event_name") or ""
                    if incoming_name and existing_name:
                        name_lower = incoming_name.lower().strip()
                        exist_lower = existing_name.lower().strip()
                        is_superset = exist_lower in name_lower and len(incoming_name) > len(existing_name)
                        is_substantially_longer = len(incoming_name) > len(existing_name) * 1.3
                        if is_superset or is_substantially_longer:
                            ev["name_is_richer"] = True
                            log(f"    ✏️  Richer name from FB: '{incoming_name}' (was: '{existing_name}')")
                    incoming_desc = ev.get("description") or ""
                    if incoming_desc and len(incoming_desc) > 50:
                        ev["description_is_richer"] = True
                    log(f"    ⬇️  Lower priority — enriching existing entry: {existing_name}")
                else:
                    # Current (FB) is higher or equal priority — upgrade existing entry's link/data
                    # Carry over IG-specific fields from the existing entry so they aren't lost
                    if not ev.get("ig_handle") and dupe.get("ig_handle"):
                        ev["ig_handle"] = dupe["ig_handle"]
                    if not ev.get("to_tag") and dupe.get("to_tag"):
                        ev["to_tag"] = dupe["to_tag"]
                    ev["duplicate_of"] = f"Also at: {dupe_src} ({dupe_date})"
                    log(f"    🔀 Cross-platform match — upgrading existing entry: {dupe.get('name')}")
                ev["possible_duplicate"] = False
            elif dupe:
                ev["possible_duplicate"] = False
            else:
                ev["possible_duplicate"] = False

            if page_id:
                # Check if incoming name/description is richer than existing (same-source update)
                if not merge_only and not ev.get("name_is_richer"):
                    existing_entry = next((e for e in all_entries if e.get("page_id") == page_id), None)
                    if existing_entry:
                        existing_name = existing_entry.get("name") or ""
                        incoming_name = ev.get("event_name") or ""
                        if incoming_name and existing_name:
                            name_lower = incoming_name.lower().strip()
                            exist_lower = existing_name.lower().strip()
                            is_superset = exist_lower in name_lower and len(incoming_name) > len(existing_name)
                            is_substantially_longer = len(incoming_name) > len(existing_name) * 1.3
                            if is_superset or is_substantially_longer:
                                ev["name_is_richer"] = True
                                log(f"    ✏️  Richer name: '{incoming_name}' (was: '{existing_name}')")
                        existing_desc = existing_entry.get("description") or ""
                        incoming_desc = ev.get("description") or ""
                        if incoming_desc and len(incoming_desc) > max(len(existing_desc), 50):
                            ev["description_is_richer"] = True
                r = notion_update(page_id, ev, merge_only=merge_only)
                if r.status_code == 429:
                    time.sleep(1.5)
                    r = notion_update(page_id, ev, merge_only=merge_only)
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
                        all_entries.append({
                            "name": ev.get("event_name", ""),
                            "start_date": ev.get("start_date", ""),
                            "source": page_name,
                            "page_id": nid,
                            "url": event_url,
                            "location": ev.get("location", ""),
                            "start_time": ev.get("start_time", ""),
                        })
                except Exception:
                    log(f"  Create failed for {ev.get('event_name')}")

            log(
                f"    → {ev.get('event_name')} | {ev.get('start_date')} | {ev.get('location')}"
            )
            time.sleep(0.3)

    return {
        "created": created, "updated": updated, "skipped": skipped,
        "flagged_dupes": flagged_dupes, "total_events": total_events,
    }


# -------------------- MAIN (standalone) --------------------
def main():
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not GEMINI_API_KEY:
        log("⚠️ No GEMINI_API_KEY — will try to parse events without AI (limited)")

    fb_pages = load_fb_pages()
    if not fb_pages:
        sys.exit(f"No Facebook pages found in {FB_ACCOUNTS_FILE}")

    log(f"Pages to scrape: {[extract_page_name(p['url']) for p in fb_pages]}")

    client = None
    if GEMINI_API_KEY:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

    existing, all_entries = notion_existing_entries()
    source_mapping = load_source_mapping()
    fb_to_ig = load_fb_to_ig_map()

    # ── Process manually-queued FB posts/events before the regular scrape ──
    try:
        import scrape_fb_queue as fb_queue
        fb_queue.process_queue(client, existing, all_entries, source_mapping)
    except Exception as e:
        log(f"⚠️  FB queue processing failed: {e}")
    totals = {"created": 0, "updated": 0, "skipped": 0, "flagged_dupes": 0, "total_events": 0}

    for idx, page_entry in enumerate(fb_pages, 1):
        page_url = page_entry["url"]
        location_filter = page_entry.get("filter")
        exclude_filter = page_entry.get("exclude")
        page_name = extract_page_name(page_url)
        filter_label = f" (filter: {location_filter})" if location_filter else ""
        if exclude_filter:
            filter_label += f" (exclude: {exclude_filter})"
        log(f"[{idx}/{len(fb_pages)}] Scraping {page_name}{filter_label}...")

        stats = scrape_page_entry(page_entry, client, existing, all_entries, source_mapping, fb_to_ig)
        for k in totals:
            totals[k] += stats.get(k, 0)

        log(f"  ✅ Done with {page_name}")
        time.sleep(2)

    log(f"✅ Done! {totals['total_events']} events found across all pages")
    log(f"   Created {totals['created']}, Updated {totals['updated']}, Skipped {totals['skipped']}")
    if totals["flagged_dupes"]:
        log(f"   ⚠️  {totals['flagged_dupes']} flagged as possible duplicates")


if __name__ == "__main__":
    main()
