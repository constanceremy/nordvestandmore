#!/usr/bin/env python3
"""
Website Event Scraper
---------------------
Scrapes events from individual website event pages using site-specific parsers.
Each site has its own parser function registered in SITE_PARSERS.
Pushes results to the unified Notion events database.

To add a new site:
  1. Write a parser function: def parse_SITENAME(html, url) -> list[dict]
     Each dict should have: event_name, event_date (YYYY-MM-DD), start_time (HH:MM),
     end_time (HH:MM or None), location, description, url, organizer
  2. Optionally write a custom fetch function: def fetch_SITENAME(url) -> str
     (needed for JS-rendered pages that require Playwright)
  3. Register it in SITE_PARSERS with a key that matches source_mapping.csv
     If fetch function provided, use 3-tuple: (parser, url, fetch_fn)
"""
import os
import re
import sys
import time
import json
import collections
import requests
from datetime import date, datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Add parent dir to path for dedup import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dedup import load_source_mapping, find_duplicate, similarity

# ────────────────── Config ──────────────────

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB = os.environ.get("NOTION_DATABASE_ID", "")
NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
SCRAPER_HEADERS = {
    "User-Agent": "NV&More scraper (contact: nordvestandmore@gmail.com)"
}

DEBUG = os.environ.get("DEBUG", "1") == "1"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_RPM_LIMIT = 14  # stay 1 under the free-tier 15 RPM


def log(msg: str):
    print(f"[WEBSITE] {msg}")


# ────────────────── Gemini helpers ──────────────────

class RateLimiter:
    """Simple sliding-window rate limiter. Sleeps if limit would be exceeded."""

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
                log(f"  ⏳ Gemini rate limit — waiting {sleep_time:.0f}s")
                time.sleep(sleep_time)
        self.timestamps.append(time.time())


_gemini_client = None
_gemini_limiter = RateLimiter(max_calls=GEMINI_RPM_LIMIT, period=60.0)


def get_gemini_client():
    """Lazy-initialize the Gemini client."""
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def analyze_event_page_with_gemini(client, page_text: str, event_url: str,
                                    venue_name: str = "Thoravej 29") -> list[dict]:
    """
    Send event page text to Gemini to extract structured event information.
    Returns a list of event dicts (a single page might describe multiple events).
    """
    from google.genai import types

    today_str = date.today().isoformat()
    prompt = f"""Analyze this event page from {venue_name} (a cultural venue at Thoravej 29, 2400 København NV, Copenhagen).

Extract ALL events as JSON. Pay close attention to these rules:

1. RECURRING EVENTS / SERIES (e.g., a book club, workshop series, talk series):
   If the page lists SPECIFIC DATES for individual sessions (e.g., "18. februar", "18. marts", "15. april"...),
   create a SEPARATE entry for EACH session/date. Use the SAME event name for all, but with the correct date.
   Each session has its own date and time.

2. EXHIBITIONS (art shows running continuously over weeks/months with NO individually listed dates):
   Extract ONLY the opening/vernissage event. Look for "fernisering", "åbning", "opening", or the first date.
   Do NOT create an entry for every day the exhibition is open.

3. SINGLE EVENTS (concert, workshop, talk, screening, party, etc.):
   Extract normally — one entry with the event's date and time.

Other rules:
- Only include events from {today_str} onward. Skip anything in the past.
- The venue address is always "Thoravej 29, 2400 København NV" — but note the specific room/space if mentioned (e.g., "Art Hub Copenhagen", "Snart", "Room Room", "Thoras Have", "Dansekapellet").
- If the page mentions a date range at the top (e.g., "18. feb – 10. jun") but ALSO lists individual dates below, follow rule #1 (recurring event) — create one entry per listed date.
- Times are in Danish 24h format. "kl. 16-17.30" means start_time "16:00", end_time "17:30".

Respond ONLY with valid JSON:
{{
  "events": [
    {{
      "event_name": "Name of the event",
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM (24h format)" or null,
      "end_time": "HH:MM (24h format)" or null,
      "location": "specific room/space within {venue_name}" or null,
      "description": "One-sentence summary of this specific session/event"
    }}
  ]
}}

If NO upcoming events are found, return {{"events": []}}.
Respond ONLY with the JSON, no extra text.

Page URL: {event_url}
Page content:
{page_text[:8000]}"""

    try:
        _gemini_limiter.wait()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4000,
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        return result.get("events", [])
    except Exception as e:
        log(f"  Gemini analysis failed: {e}")
        return []


# ────────────────── Danish date helpers ──────────────────

MONTH_MAP = {
    "jan": 1, "jan.": 1, "januar": 1,
    "feb": 2, "feb.": 2, "februar": 2,
    "mar": 3, "mar.": 3, "marts": 3,
    "apr": 4, "apr.": 4, "april": 4,
    "maj": 5,
    "jun": 6, "jun.": 6, "juni": 6,
    "jul": 7, "jul.": 7, "juli": 7,
    "aug": 8, "aug.": 8, "august": 8,
    "sep": 9, "sep.": 9, "september": 9,
    "okt": 10, "okt.": 10, "oktober": 10,
    "nov": 11, "nov.": 11, "november": 11,
    "dec": 12, "dec.": 12, "december": 12,
}


def parse_danish_date(text: str) -> str | None:
    """
    Parse various Danish date formats into YYYY-MM-DD.
    Handles: "torsdag den 2. april 2026", "2. apr. 2026", etc.
    """
    # Pattern: optional weekday, day number, month name, year
    m = re.search(
        r"(\d{1,2})\.\s*([a-zæøå\.]+)\s+(\d{4})",
        text, re.IGNORECASE
    )
    if not m:
        return None
    day = int(m.group(1))
    month_str = m.group(2).lower().rstrip(".")
    year = int(m.group(3))

    # Try with and without trailing dot
    month = MONTH_MAP.get(month_str) or MONTH_MAP.get(month_str + ".")
    if not month:
        return None

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_time_range(text: str) -> tuple[str | None, str | None]:
    """
    Parse time ranges from text. Returns (start_time, end_time) in HH:MM 24h format.
    Handles: "13.30", "kl. 13", "17.00 - 20.00", "Kl. 19 - 21", etc.
    """
    # Look for HH.MM or HH:MM patterns
    times = re.findall(r"(\d{1,2})[.:](\d{2})", text)
    if len(times) >= 2:
        start = f"{int(times[0][0]):02d}:{times[0][1]}"
        end = f"{int(times[1][0]):02d}:{times[1][1]}"
        return start, end
    elif len(times) == 1:
        start = f"{int(times[0][0]):02d}:{times[0][1]}"
        return start, None

    # Try bare hours: "Kl. 19 - 21"
    m = re.search(r"[Kk]l\.?\s*(\d{1,2})\s*[-–]\s*(\d{1,2})", text)
    if m:
        return f"{int(m.group(1)):02d}:00", f"{int(m.group(2)):02d}:00"

    return None, None


def to_12h(time_str: str | None) -> str | None:
    """Convert HH:MM to 12h display format."""
    if not time_str:
        return None
    try:
        h, m = map(int, time_str.split(":"))
        suffix = "am" if h < 12 else "pm"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d}{suffix}"
    except (ValueError, AttributeError):
        return None


# ────────────────── Site-specific parsers ──────────────────

def parse_rodder(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://www.rodder.dk/events
    Events are in <article> or similar blocks with date, title, location, description.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []

    # Rødder uses Squarespace-style event listing.
    # Each event block contains: date, title (h1/h2), bullet list with details, description
    # Look for event blocks — they typically have headings with event names
    # and lists with date/time/location details

    # Strategy: find all headings that are event names, then gather surrounding context
    # The page structure has event cards with:
    #   - A date/time header
    #   - An h1 with the event name (linked with "Se begivenhed →")
    #   - A bullet list: weekday + date, time range, location, calendar links
    #   - Description text

    # Find all event-like sections by looking for "Se begivenhed" links
    event_links = soup.find_all("a", string=re.compile(r"Se begivenhed", re.IGNORECASE))

    if not event_links:
        # Fallback: look for all internal links that point to event detail pages
        event_links = soup.find_all("a", href=re.compile(r"/events/"))

    # Deduplicate event URLs
    seen_urls = set()
    unique_links = []
    for link in event_links:
        href = link.get("href", "")
        if href and href not in seen_urls:
            seen_urls.add(href)
            unique_links.append(link)

    for link in unique_links:
        # Walk up to find the event container (usually a parent div/section)
        container = link
        for _ in range(10):
            parent = container.parent
            if parent is None:
                break
            text = parent.get_text(" ", strip=True)
            # A good container has both date info and the event name
            if len(text) > 100:
                container = parent
                break
            container = parent

        text = container.get_text("\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Extract event name: look for heading elements
        event_name = None
        headings = container.find_all(["h1", "h2", "h3"])
        for h in headings:
            h_text = h.get_text(strip=True)
            if h_text and len(h_text) > 3 and "Se begivenhed" not in h_text:
                event_name = h_text
                break

        if not event_name:
            # Fallback: use the longest non-date, non-meta line
            for line in lines:
                if (len(line) > 10 and
                    not re.match(r"^(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)", line, re.IGNORECASE) and
                    "Se begivenhed" not in line and
                    "Google kalender" not in line and
                    "ICS" not in line):
                    event_name = line[:200]
                    break

        if not event_name:
            continue

        # Extract date
        event_date = None
        for line in lines:
            d = parse_danish_date(line)
            if d:
                event_date = d
                break

        # Skip past events
        if event_date:
            try:
                if date.fromisoformat(event_date) < date.today():
                    if DEBUG:
                        log(f"  Skipping past event: {event_name} ({event_date})")
                    continue
            except ValueError:
                pass

        # Extract time: look for the 24h display lines (e.g. "13.30", "15.30")
        # The page renders both AM/PM and 24h — we want the 24h ones.
        # They appear as standalone lines like "01.30" (which is actually 13.30)
        # Better: look in the description for "kl. HH" or "kl. HH.MM" patterns
        start_time, end_time = None, None

        # Strategy 1: look for "kl." in description text (most reliable)
        # Find ALL "kl. HH.MM" matches and prefer the first one with minutes
        full_text = "\n".join(lines)
        kl_matches = list(re.finditer(
            r"[Kk]l\.?\s*(\d{1,2})(?:[.:](\d{2}))?"
            r"(?:\s*[-–]\s*(\d{1,2})(?:[.:](\d{2}))?)?",
            full_text
        ))
        # Prefer matches that include minutes (more specific)
        kl_match = None
        for m in kl_matches:
            if m.group(2):  # has minutes
                kl_match = m
                break
        if not kl_match and kl_matches:
            kl_match = kl_matches[0]

        if kl_match:
            sh = int(kl_match.group(1))
            sm = kl_match.group(2) or "00"
            start_time = f"{sh:02d}:{sm}"
            if kl_match.group(3):
                eh = int(kl_match.group(3))
                em = kl_match.group(4) or "00"
                end_time = f"{eh:02d}:{em}"

        # Strategy 2: look for standalone 24h time lines after the date line
        if not start_time:
            time_lines = []
            past_date = False
            for line in lines:
                if parse_danish_date(line):
                    past_date = True
                    continue
                if past_date and re.match(r"^\d{2}[.:]\d{2}$", line):
                    time_lines.append(line)
                elif past_date and len(time_lines) > 0:
                    break
            # The 24h times typically come after the AM/PM ones
            # Take the last pair (which should be 24h format)
            if len(time_lines) >= 2:
                # Take last two — they're the 24h versions
                st_parts = time_lines[-2].replace(".", ":")
                et_parts = time_lines[-1].replace(".", ":")
                start_time = st_parts
                end_time = et_parts

        # Extract location: line right before "(kort)"
        location = None
        for i, line in enumerate(lines):
            if "(kort)" in line.lower():
                # Location is the previous line, or this line minus "(kort)"
                clean = re.sub(r"\s*\(kort\)\s*", "", line, flags=re.IGNORECASE).strip()
                if clean:
                    location = clean
                elif i > 0:
                    location = lines[i - 1].strip()
                break

        # Build event URL
        href = link.get("href", "")
        if href and not href.startswith("http"):
            href = f"https://www.rodder.dk{href}"

        # Description: first paragraph-like text after the title
        description = None
        found_title = False
        for line in lines:
            if event_name and event_name in line:
                found_title = True
                continue
            if found_title and len(line) > 30 and "Se begivenhed" not in line:
                description = line[:500]
                break

        events.append({
            "event_name": event_name,
            "event_date": event_date,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "organizer": "Rødder",
            "description": description,
            "url": href,
        })

    return events


# ────────────────── Ungdomshuset helpers ──────────────────

# Known rooms / sub-venues inside Ungdomshuset
# Include both ø and ö variants (the website uses ö in some places)
UNGDOMSHUSET_ROOMS = [
    "dødsmaskinen + salen", "dødsmaskinen", "dödsmaskinen + salen", "dödsmaskinen",
    "salen", "den røde plads",
    "caféen", "cafeen", "café",
    "svedren", "bølleborgen", "bölleborgen",
    "krea", "bogcaféen", "bogcafeen",
    "barrikaden", "gården", "gaarden",
]


def fetch_ungdomshuset(url: str) -> str:
    """
    Use Playwright to load ungdomshuset.dk and click 'Vis flere arrangementer'
    repeatedly until all events are loaded, then return the final HTML.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="da-DK",
        )
        page = context.new_page()

        log(f"  Loading {url} ...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Click "Vis flere arrangementer" until the button disappears
        max_clicks = 30
        for click_num in range(max_clicks):
            btn = None
            for selector in [
                'text=/Vis flere arrangementer/',
                'button:has-text("Vis flere")',
                'a:has-text("Vis flere")',
                '[class*="show-more"]',
                '[class*="load-more"]',
            ]:
                try:
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible():
                        break
                    btn = None
                except Exception:
                    btn = None

            if not btn:
                if click_num == 0:
                    log("  No 'Vis flere' button found — all events already visible")
                else:
                    log(f"  All events loaded after {click_num} click(s)")
                break

            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                if DEBUG:
                    log(f"  Clicked 'Vis flere arrangementer' ({click_num + 1})")
                time.sleep(2)
            except Exception as e:
                log(f"  Could not click load-more button: {e}")
                break

        html = page.content()
        browser.close()

    return html


def parse_ungdomshuset(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://www.ungdomshuset.dk/
    Events are listed in a calendar section with Danish dates and times.
    Each event typically contains: weekday + date + "kl." + time, optional price,
    a room/venue within the house, and the event name.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    today = date.today()

    # ── Strategy 1: Find links to individual event/calendar pages ──
    event_links: list[tuple] = []  # (container_element, href)
    seen_hrefs: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        if not re.search(r"/(kalender|events?)/[^/]+", href):
            continue
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Walk up to find a container that has date info
        container = a_tag
        for _ in range(10):
            parent = container.parent
            if parent is None:
                break
            parent_text = parent.get_text(" ", strip=True)
            if re.search(r"kl\.?\s*\d{1,2}[.:]\d{2}", parent_text) and len(parent_text) > 20:
                container = parent
                break
            container = parent

        event_links.append((container, href))

    # ── Strategy 2: If no links found, fall back to text-based splitting ──
    if not event_links:
        all_text = soup.get_text("\n", strip=True)
        # Split on Danish date + time pattern
        date_pattern = (
            r"((?:mandag|tirsdag|onsdag|torsdag|fredag|lørdag|søndag)"
            r"\s+\d{1,2}\.\s*[a-zæøå]+\.?\s+\d{4}\s+kl\.?\s*\d{1,2}[.:]\d{2})"
        )
        parts = re.split(date_pattern, all_text, flags=re.IGNORECASE)
        # parts = [before, date1, after1, date2, after2, ...]
        for i in range(1, len(parts), 2):
            date_line = parts[i].strip()
            after = parts[i + 1].strip() if i + 1 < len(parts) else ""
            # Limit "after" text to avoid grabbing the next event
            # Cut at the next date pattern occurrence
            next_event = re.search(date_pattern, after, re.IGNORECASE)
            if next_event:
                after = after[:next_event.start()].strip()
            full_text = date_line + "\n" + after
            event_links.append((full_text, None))

    # ── Process each event ──
    for item in event_links:
        raw_container = item[0]
        href = item[1]

        is_element = not isinstance(raw_container, str)

        if is_element:
            text = raw_container.get_text("\n", strip=True)
        else:
            text = raw_container

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue

        # ── Parse date ──
        event_date = None
        for line in lines:
            d = parse_danish_date(line)
            if d:
                event_date = d
                break

        # Skip past events
        if event_date:
            try:
                if date.fromisoformat(event_date) < today:
                    if DEBUG:
                        log(f"  Skipping past event ({event_date})")
                    continue
            except ValueError:
                pass

        # ── Parse time ──
        start_time = None
        for line in lines:
            m = re.search(r"kl\.?\s*(\d{1,2})[.:](\d{2})", line)
            if m:
                h, mins = int(m.group(1)), m.group(2)
                start_time = f"{h:02d}:{mins}"
                break

        # ── Parse room within the house ──
        room = None
        for line in lines:
            line_lower = line.lower().strip()
            for room_name in UNGDOMSHUSET_ROOMS:
                if room_name in line_lower:
                    # Use the original-cased version from the text
                    room = line.strip()
                    # Clean up: remove leading/trailing pipe chars, price, etc.
                    room = re.sub(r"[|]", "", room).strip()
                    break
            if room:
                break

        # ── Helper: check if a string is a room name ──
        def _is_room(s: str) -> bool:
            sl = s.lower().strip()
            for rn in UNGDOMSHUSET_ROOMS:
                if rn in sl:
                    return True
            return False

        # ── Parse event name ──
        # Strategy A: if we have the actual HTML element, look for heading tags
        # (the event name is displayed as a large orange heading on the page)
        event_name = None
        if is_element:
            for h_tag in raw_container.find_all(["h1", "h2", "h3", "h4"]):
                h_text = h_tag.get_text(strip=True)
                if (h_text and len(h_text) > 2
                        and not _is_room(h_text)
                        and not parse_danish_date(h_text)
                        and "Vis flere" not in h_text
                        and "Kalender" not in h_text):
                    event_name = h_text[:300]
                    break

        # Strategy B: fall back to text-based extraction
        if not event_name:
            skip_patterns = [
                r"kl\.?\s*\d",                          # time
                r"\d{1,2}\.\s*\w+\.?\s+\d{4}",          # date
                r"^\d+\s*kr\b",                          # price
                r"^\d+$",                                # bare number (price without "kr")
                r"^Vis flere",                           # load more button
                r"^Se begivenhed",                       # "see event" link text
                r"^Næste show",                          # "next show" header
                r"^Google kalender",
                r"^ICS$",
                r"^Kalender$",
                r"^Alle$",
                r"^(Koncert|Oplæg|Baraften|Workshop|Folkekøkken|Hygge|Demonstration)$",
            ]
            for line in lines:
                ls = line.strip()
                if not ls or len(ls) < 2:
                    continue
                # Skip lines matching skip patterns
                if any(re.search(p, ls, re.IGNORECASE) for p in skip_patterns):
                    continue
                # Skip if it's a room name
                if _is_room(ls):
                    continue
                # Skip date-only lines
                if parse_danish_date(ls):
                    continue
                # Skip price-only lines (e.g., "50kr", "100KR", or bare "70")
                if re.match(r"^\d+\s*(kr)?\s*$", ls, re.IGNORECASE):
                    continue
                # This is likely the event name
                event_name = ls[:300]
                break

        if not event_name:
            continue

        # ── Parse price (for description) ──
        price = None
        for line in lines:
            m = re.search(r"(\d+)\s*kr\b", line, re.IGNORECASE)
            if m:
                price = f"{m.group(1)} kr"
                break

        # ── Build event URL ──
        event_url = page_url
        if href:
            if not href.startswith("http"):
                event_url = f"https://www.ungdomshuset.dk{href}"
            else:
                event_url = href

        # ── Location ──
        location = "Ungdomshuset, Dortheavej 61, 2400 København NV"
        if room:
            location = f"{room}, Ungdomshuset, Dortheavej 61, 2400 København NV"

        # ── Description ──
        desc_parts = []
        if price:
            desc_parts.append(f"Pris: {price}")
        if room:
            desc_parts.append(f"Rum: {room}")
        description = " | ".join(desc_parts) if desc_parts else None

        events.append({
            "event_name": event_name,
            "event_date": event_date,
            "start_time": start_time,
            "end_time": None,
            "location": location,
            "organizer": "Ungdomshuset",
            "description": description,
            "url": event_url,
        })

    return events


# ────────────────── Thoravej 29 ──────────────────

# Known sub-venues at Thoravej 29
THORAVEJ29_VENUES = [
    "art hub copenhagen", "snart", "room room", "thoras have",
    "snart - laboratorium for mulige fremtider",
    "dansekapellet", "fablab nordvest",
]


def fetch_thoravej29(url: str) -> str:
    """
    Use Playwright to load thoravej29.dk/da/events and wait for the
    'Alle events' section to finish loading (it initially shows 'Henter ...').
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="da-DK",
        )
        page = context.new_page()

        log(f"  Loading {url} ...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Wait for "Henter ..." to disappear (events loading)
        max_wait = 15
        for i in range(max_wait):
            body_text = page.evaluate("() => document.body.innerText") or ""
            if "Henter" not in body_text:
                log(f"  Events loaded after {i + 1}s")
                break
            time.sleep(1)
        else:
            log("  Warning: 'Henter ...' still visible after timeout — parsing anyway")

        # Scroll down to ensure all lazy-loaded content is visible
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        # Check for "load more" / "Vis flere" buttons
        for click_num in range(10):
            btn = None
            for selector in [
                'text=/Vis flere/',
                'button:has-text("Vis flere")',
                'a:has-text("Vis flere")',
                'button:has-text("Load more")',
            ]:
                try:
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible():
                        break
                    btn = None
                except Exception:
                    btn = None
            if not btn:
                break
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                if DEBUG:
                    log(f"  Clicked 'Vis flere' ({click_num + 1})")
                time.sleep(2)
            except Exception:
                break

        html = page.content()
        browser.close()

    return html


def parse_thoravej29(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://www.thoravej29.dk/da/events
    Only uses events from the 'Alle events' section (not 'Udvalgte events').

    Strategy:
    1. Extract individual event page URLs from the 'Alle events' section
    2. Visit each event page with Playwright to get the full content
    3. Send page text to Gemini to extract structured event data
       (handles exhibitions → only the opening/vernissage, recurring events, etc.)
    """
    from playwright.sync_api import sync_playwright

    soup = BeautifulSoup(html, "html.parser")
    events = []
    today = date.today()

    # ── Locate the "Alle events" section ──
    alle_section = None
    for heading in soup.find_all(["h1", "h2", "h3"]):
        if "alle events" in heading.get_text(strip=True).lower():
            alle_section = heading.parent
            break

    search_root = alle_section if alle_section else soup

    # ── Collect event page URLs ──
    event_urls: list[str] = []
    seen_hrefs: set[str] = set()

    for a_tag in search_root.find_all("a", href=True):
        href = a_tag.get("href", "")
        if not re.search(r"/(da/)?(events?|kalender)/[^/]+", href):
            continue
        if href.rstrip("/").endswith("/events") or href.rstrip("/").endswith("/da/events"):
            continue
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)
        full_url = href if href.startswith("http") else f"https://www.thoravej29.dk{href}"
        event_urls.append(full_url)

    if not event_urls:
        log("  No event links found in 'Alle events' section")
        return events

    log(f"  Found {len(event_urls)} event link(s) — visiting each page...")

    # ── Check Gemini availability ──
    client = get_gemini_client()
    if not client:
        log("  ⚠️ No Gemini API key — cannot analyze event pages")
        return events

    # ── Visit each event page and analyze with Gemini ──
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="da-DK",
        )
        page = context.new_page()

        for i, event_url in enumerate(event_urls, 1):
            try:
                if DEBUG:
                    log(f"  [{i}/{len(event_urls)}] Visiting {event_url}")

                page.goto(event_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)

                # Get the visible text content
                page_text = page.evaluate("() => document.body.innerText") or ""

                if not page_text.strip() or len(page_text.strip()) < 30:
                    log(f"    ⚠️ Page has very little content — skipping")
                    continue

                # Send to Gemini for analysis
                gemini_events = analyze_event_page_with_gemini(
                    client, page_text, event_url, venue_name="Thoravej 29",
                )

                if not gemini_events:
                    if DEBUG:
                        log(f"    No upcoming events found on this page")
                    continue

                for ev_data in gemini_events:
                    event_date_str = ev_data.get("event_date")

                    # Skip past events
                    if event_date_str:
                        try:
                            if date.fromisoformat(event_date_str) < today:
                                if DEBUG:
                                    log(f"    Skipping past: {ev_data.get('event_name')} ({event_date_str})")
                                continue
                        except ValueError:
                            pass

                    # Build location
                    location = "Thoravej 29, 2400 København NV"
                    sub_venue = ev_data.get("location")
                    if sub_venue:
                        location = f"{sub_venue}, Thoravej 29, 2400 København NV"

                    events.append({
                        "event_name": ev_data.get("event_name"),
                        "event_date": event_date_str,
                        "start_time": ev_data.get("start_time"),
                        "end_time": ev_data.get("end_time"),
                        "location": location,
                        "organizer": "Thoravej 29",
                        "description": ev_data.get("description"),
                        "url": event_url,
                    })

                if DEBUG and gemini_events:
                    names = [e.get("event_name", "?") for e in gemini_events]
                    log(f"    ✅ {len(gemini_events)} event(s): {', '.join(names)}")

            except Exception as e:
                log(f"    ⚠️ Could not process {event_url}: {e}")

            time.sleep(1)  # Be polite between page loads

        browser.close()

    return events


# ────────────────── Flere Fugle parser ──────────────────

# Map venue slugs (from ?location= links) to display names and addresses
FLEREFUGLE_VENUES = {
    "flere-fugle": ("Flere Fugle", "Flere Fugle, Gammel Jernbanevej 7, 2500 Valby"),
    "lille-fugl": ("Lille Fugl", "Lille Fugl"),
    "fovl": ("Fovl NV", "Fovl, Rentemestervej 64, 2400 København NV"),
    "flok": ("Flok Kantine", "Flok Kantine, Lygten 39, 2400 København NV"),
    "bageri-butik": ("Flere Fugle Bageri", "Flere Fugle Bageri & Butik"),
}


def parse_flerefugle(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://www.flerefugle.dk/events
    Events are in <article class="Card"> elements, each containing:
      - Venue link (@ Flere Fugle) via ?location= href
      - Tags (# Musik, # Workshop, etc.)
      - Event name in <h3>
      - Date+time like "22. feb. 2026 19.30"
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    today = date.today()

    for article in soup.find_all("article", class_="Card"):
        # Skip "Faste events" (recurring / compact cards)
        classes = article.get("class", [])
        if "Card--compact" in classes:
            continue
        # Also skip if tagged as Recurring
        if any("?tag=recurring" in (a.get("href") or "") for a in article.find_all("a", href=True)):
            continue

        text = article.get_text("|", strip=True)

        # ── Extract venue from location link ──
        venue_slug = None
        for a in article.find_all("a", href=True):
            href = a.get("href", "")
            m = re.search(r"\?location=([a-z0-9-]+)", href)
            if m:
                venue_slug = m.group(1)
                break
        venue_name, venue_location = FLEREFUGLE_VENUES.get(
            venue_slug, ("Flere Fugle", "Flere Fugle")
        )

        # ── Extract event name from <h3> ──
        h3 = article.find("h3")
        if not h3:
            continue
        event_name = h3.get_text(strip=True)

        # Strip "Udsolgt!" (sold out) prefix — still include the event
        if event_name.startswith("Udsolgt!"):
            event_name = event_name[len("Udsolgt!"):].strip()
        # Also handle "Udsolgt! ~~Name~~" markdown pattern
        event_name = re.sub(r"^~~|~~$", "", event_name).strip()
        if not event_name:
            continue

        # ── Extract event URL ──
        event_url_path = None
        for a in article.find_all("a", href=True):
            href = a.get("href", "")
            if re.match(r"/events/[0-9a-f-]+", href):
                event_url_path = href
                break
        event_url = f"https://www.flerefugle.dk{event_url_path}" if event_url_path else page_url

        # ── Extract date and time ──
        # Date format: "22. feb. 2026 19.30" or range "28. jun. 2026 00.00 - 6. jul. 2026 00.00"
        event_date = parse_danish_date(text)
        if not event_date:
            if DEBUG:
                log(f"  Skipping (no date): {event_name}")
            continue

        # Check if past
        try:
            event_dt = date.fromisoformat(event_date)
            if event_dt < today:
                if DEBUG:
                    log(f"  Skipping past event: {event_name} ({event_date})")
                continue
        except ValueError:
            pass

        # Extract time — look for HH.MM after the date
        start_time = None
        end_time = None
        # Pattern: date followed by time, e.g. "2026 19.30"
        time_match = re.search(
            r"\d{4}\s+(\d{1,2})\.(\d{2})\s*(?:[-–]\s*(\d{1,2})\.(\d{2}))?",
            text
        )
        if time_match:
            h, m = int(time_match.group(1)), time_match.group(2)
            if h < 24:  # sanity check (avoid matching year fragments)
                start_time = f"{h:02d}:{m}"
            if time_match.group(3) and time_match.group(4):
                eh, em = int(time_match.group(3)), time_match.group(4)
                if eh < 24:
                    end_time = f"{eh:02d}:{em}"

        # Skip events at 00:00 with no real time (like multi-day volunteer events)
        if start_time == "00:00" and end_time is None:
            start_time = None

        # ── Extract tags for description ──
        tags = []
        for a in article.find_all("a", href=True):
            href = a.get("href", "")
            if "?tag=" in href:
                tag_text = a.get_text(strip=True).lstrip("#").strip()
                if tag_text.lower() not in ("event", "recurring"):
                    tags.append(tag_text)
        description = ", ".join(tags) if tags else None

        events.append({
            "event_name": event_name,
            "event_date": event_date,
            "start_time": start_time,
            "end_time": end_time,
            "location": venue_location,
            "organizer": venue_name,
            "description": description,
            "url": event_url,
        })

    return events


# ────────────────── Just Sauna parser (Yogo API) ──────────────────

JUSTSAUNA_LOCATION = "Urban13, Bispeengen 20, 2000 Frederiksberg"
YOGO_CLIENT_ID = "814"
YOGO_API_EVENTS = "https://api.yogo.dk/events"


def fetch_justsauna(_url: str) -> str:
    """Fetch Just Sauna events from the Yogo booking API and return JSON string."""
    today = date.today().isoformat()
    api_url = (
        f"{YOGO_API_EVENTS}?startDate={today}&endDate=2027-01-01"
        f"&populate[]=time_slots&populate[]=event_group"
    )
    r = requests.get(
        api_url, timeout=15,
        headers={"X-Yogo-Client-ID": YOGO_CLIENT_ID, "Accept": "application/json"},
    )
    r.raise_for_status()
    return r.text  # JSON string — parsed by parse_justsauna


def parse_justsauna(json_text: str, page_url: str) -> list[dict]:
    """
    Parser for Just Sauna events via the Yogo booking API.
    Filters to Urban13 Copenhagen only (excludes Frederikssund events).
    """
    try:
        api_events = json.loads(json_text)
    except json.JSONDecodeError:
        log("  Could not parse Yogo API response")
        return []

    events = []
    today = date.today()

    for ev in api_events:
        if ev.get("archived"):
            continue

        name = (ev.get("name") or "").strip()
        if not name:
            continue

        description = (ev.get("description") or "").strip()
        desc_lower = description.lower()

        # Only include SPECIAL EVENTS (all WORKSHOPS & KURSER are in Frederikssund)
        group = ev.get("event_group", {})
        group_name = group.get("name", "") if isinstance(group, dict) else ""
        if group_name != "SPECIAL EVENTS":
            if DEBUG:
                log(f"  Skipping (not Special Event): {name}")
            continue

        # Skip events at Frederikssund / Wellness location
        # "Wellness" = Jernbanegade 39A, Frederikssund; "Urban13" = Bispeengen 20, Frederiksberg
        if any(kw in desc_lower for kw in ("frederikssund", "jernbanegade", "wellness")):
            if DEBUG:
                log(f"  Skipping (Frederikssund/Wellness): {name}")
            continue

        # Skip cancelled events
        if "cancelled" in name.lower() or "cancelled" in desc_lower:
            continue

        # Process each time slot as a separate event entry
        slots = ev.get("time_slots", [])
        if not slots:
            continue

        for slot in slots:
            if not isinstance(slot, dict):
                continue

            event_date = slot.get("date")
            if not event_date:
                continue

            # Skip past events
            try:
                if date.fromisoformat(event_date) < today:
                    continue
            except ValueError:
                continue

            start_time = slot.get("start_time")  # Already in HH:MM format
            end_time = slot.get("end_time")

            # Build a short description from the first line
            short_desc = description.split("\n")[0][:200] if description else None

            events.append({
                "event_name": name,
                "event_date": event_date,
                "start_time": start_time,
                "end_time": end_time,
                "location": JUSTSAUNA_LOCATION,
                "organizer": "Just Sauna",
                "description": short_desc,
                "url": page_url,
            })

    return events


# ────────────────── Sauna 85 parser (Yogo API) ──────────────────

SAUNA85_CLIENT_ID = "664"
SAUNA85_LOCATION = "Rentemestervej 64, 2400 København NV"


def fetch_sauna85(_url: str) -> str:
    """Fetch Sauna 85 events from the Yogo booking API and return JSON string."""
    today = date.today().isoformat()
    api_url = (
        f"{YOGO_API_EVENTS}?startDate={today}&endDate=2027-01-01"
        f"&populate[]=time_slots&populate[]=room&populate[]=event_group"
    )
    r = requests.get(
        api_url, timeout=15,
        headers={"X-Yogo-Client-ID": SAUNA85_CLIENT_ID, "Accept": "application/json"},
    )
    r.raise_for_status()
    return r.text


def parse_sauna85(json_text: str, page_url: str) -> list[dict]:
    """
    Parser for Sauna 85 events via the Yogo booking API.
    Filters to Rentemestervej (København NV) location only.
    """
    try:
        api_events = json.loads(json_text)
    except json.JSONDecodeError:
        log("  Could not parse Yogo API response")
        return []

    events = []
    today = date.today()

    for ev in api_events:
        if ev.get("archived"):
            continue

        name = (ev.get("name") or "").strip()
        if not name:
            continue

        # Filter by room: only keep events at Rentemestervej (København NV)
        room = ev.get("room", {})
        room_name = room.get("name", "") if isinstance(room, dict) else ""
        if room_name and "rentemestervej" not in room_name.lower():
            if DEBUG:
                log(f"  Skipping (not Rentemestervej): {name} — room: {room_name}")
            continue

        # Skip cancelled events
        if "cancelled" in name.lower():
            continue

        description = (ev.get("description") or "").strip()

        # Parse time from time_freetext: "d. 25/02 2026  kl. 17:00 - 22:30"
        time_text = (ev.get("time_freetext") or "").strip()
        start_time = None
        end_time = None
        time_match = re.search(r"kl\.\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", time_text)
        if time_match:
            start_time = time_match.group(1)
            end_time = time_match.group(2)

        # Get event date — first try time_slots, then start_date
        slots = ev.get("time_slots", [])
        if slots:
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                event_date = slot.get("date")
                if not event_date:
                    continue
                try:
                    if date.fromisoformat(event_date) < today:
                        continue
                except ValueError:
                    continue
                slot_start = slot.get("start_time") or start_time
                slot_end = slot.get("end_time") or end_time
                events.append({
                    "event_name": name,
                    "event_date": event_date,
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "location": room_name or SAUNA85_LOCATION,
                    "organizer": "Sauna 85",
                    "description": description.split("\n")[0][:200] if description else None,
                    "url": page_url,
                })
        else:
            # No time slots — use start_date directly
            event_date = ev.get("start_date")
            if not event_date:
                continue
            try:
                if date.fromisoformat(event_date) < today:
                    continue
            except ValueError:
                continue
            events.append({
                "event_name": name,
                "event_date": event_date,
                "start_time": start_time,
                "end_time": end_time,
                "location": room_name or SAUNA85_LOCATION,
                "organizer": "Sauna 85",
                "description": description.split("\n")[0][:200] if description else None,
                "url": page_url,
            })

    return events


# ────────────────── Demokratigarage parser (WordPress / The Events Calendar) ──────────────────

# Patterns that indicate an internal meeting / not a public event
_DG_SKIP_PATTERNS = [
    "holder møde",
    "holder årlig",
    "generalforsamling",
    "studiebesøg",
]

_DG_SKIP_TITLE_PREFIXES = [
    "vi søger",  # job postings
]


def fetch_demokratigarage(url: str) -> str:
    """Fetch Demokratigarage calendar with Playwright (site has bot protection)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        import time as _t
        _t.sleep(3)
        html = page.content()
        browser.close()
    return html


def parse_demokratigarage(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://www.demokratigarage.dk/kalender/
    Uses WordPress "The Events Calendar" plugin.
    Skips internal meetings.
    Flags Flere Fugle cross-posted events with crosspost_entity.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    today = date.today()

    articles = soup.find_all("article", class_="tribe-events-calendar-list__event")

    for art in articles:
        # ── Title + URL ──
        title_el = art.find("h4") or art.find("h3")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = title_el.find("a")
        event_url = link["href"] if link and link.has_attr("href") else page_url

        # ── Date ──
        time_el = art.find("time")
        event_date_str = time_el.get("datetime", "") if time_el else ""
        if not event_date_str:
            continue
        try:
            event_date = date.fromisoformat(event_date_str)
            if event_date < today:
                continue
        except ValueError:
            continue

        # ── Time ──
        date_text_el = art.find(class_=lambda c: c and "datetime" in c.lower() if c else False)
        date_text = date_text_el.get_text(strip=True) if date_text_el else ""
        start_time = None
        end_time = None
        time_match = re.search(r"kl\.?\s*(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", date_text)
        if time_match:
            start_time = time_match.group(1)
            end_time = time_match.group(2)

        # ── Venue ──
        venue_el = art.find(class_=lambda c: c and "venue" in c.lower() if c else False)
        venue_text = venue_el.get_text(strip=True) if venue_el else ""
        # Venue text is like "Demokrati GarageRentemestervej 57, Kbh NV" (concatenated)
        is_flere_fugle = "flere fugle" in venue_text.lower()

        # ── Description ──
        desc_el = art.find(class_=lambda c: c and "description" in c.lower() if c else False)
        description = desc_el.get_text(strip=True) if desc_el else ""

        # ── Skip internal meetings ──
        desc_lower = description.lower()
        title_lower = title.lower()
        skip = False
        for pattern in _DG_SKIP_PATTERNS:
            if pattern in desc_lower:
                skip = True
                break
        if not skip:
            for prefix in _DG_SKIP_TITLE_PREFIXES:
                if title_lower.startswith(prefix):
                    skip = True
                    break
        if skip:
            if DEBUG:
                log(f"  Skipping (internal/private): {title}")
            continue

        event_entry = {
            "event_name": title,
            "event_date": event_date_str,
            "start_time": start_time,
            "end_time": end_time,
            "location": "Rentemestervej 57, 2400 København NV",
            "organizer": "Flere Fugle" if is_flere_fugle else "Demokratigarage",
            "description": description[:200] if description else None,
            "url": event_url,
        }

        # Flag Flere Fugle cross-posts so scrape_site can handle them specially
        if is_flere_fugle:
            event_entry["_crosspost_entity"] = "flere fugle"

        events.append(event_entry)

    return events


# ────────────────── TegneskoleKBH parser ──────────────────

def parse_tegneskolekbh(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://www.tegneskolekbh.dk/workshops/

    Workshops are listed in div.spot.spot--withlink containers.
    Each has a link to a detail page /workshops-liste/?category=...&course=...
    The detail page has dt/dd pairs with:
      - Første møde: first session date + time
      - Sidste møde: last session date + time
      - Mødegange: number of sessions (days)
    We visit each detail page and create one event per day.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    today = date.today()

    # ── Collect workshop detail URLs ──
    workshop_links: list[tuple[str, str]] = []  # (title, url)
    for spot in soup.find_all("div", class_="spot--withlink"):
        a_tag = spot.find("a", href=lambda h: h and "workshops-liste" in h)
        if not a_tag:
            continue
        href = a_tag["href"]
        full_url = href if href.startswith("http") else f"https://www.tegneskolekbh.dk{href}"

        h3 = spot.find("h3")
        title = h3.get_text(strip=True) if h3 else "Untitled Workshop"
        workshop_links.append((title, full_url))

    if not workshop_links:
        log("  No workshop links found on page")
        return events

    log(f"  Found {len(workshop_links)} workshop(s) — visiting each detail page...")

    # ── Visit each detail page ──
    for i, (title, detail_url) in enumerate(workshop_links, 1):
        try:
            if DEBUG:
                log(f"  [{i}/{len(workshop_links)}] {title}")

            r = requests.get(detail_url, headers=SCRAPER_HEADERS, timeout=15)
            r.raise_for_status()
            detail_soup = BeautifulSoup(r.text, "html.parser")

            # ── Extract schedule from dt/dd pairs ──
            dd_map: dict[str, str] = {}
            for dt in detail_soup.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                key = dt.get_text(strip=True).rstrip(":")
                val = dd.get_text(strip=True) if dd else ""
                dd_map[key] = val

            first_raw = dd_map.get("Første møde", "")
            last_raw = dd_map.get("Sidste møde", "")
            sessions_raw = dd_map.get("Mødegange", "")

            if not first_raw:
                if DEBUG:
                    log(f"    ⚠️ No 'Første møde' found — skipping")
                continue

            # ── Parse dates (format: d.mm.yy kl. HH:MM) ──
            def _parse_tegneskole_dt(raw: str):
                """Parse '6.03.26 kl. 16:00' → (date, 'HH:MM')"""
                m = re.match(r"(\d{1,2})\.(\d{2})\.(\d{2})\s+kl\.\s*(\d{1,2}):(\d{2})", raw.strip())
                if not m:
                    return None, None
                day, month, year2, hour, minute = m.groups()
                year = 2000 + int(year2)
                try:
                    d = date(year, int(month), int(day))
                except ValueError:
                    return None, None
                t = f"{int(hour):02d}:{minute}"
                return d, t

            first_date, first_time = _parse_tegneskole_dt(first_raw)
            last_date, last_time = _parse_tegneskole_dt(last_raw)

            if not first_date:
                if DEBUG:
                    log(f"    ⚠️ Could not parse first meeting date '{first_raw}' — skipping")
                continue

            # If no last date, it's a single-day workshop
            if not last_date:
                last_date = first_date
                last_time = first_time

            # Skip entirely past workshops
            if last_date < today:
                if DEBUG:
                    log(f"    Skipping past workshop (ends {last_date.isoformat()})")
                continue

            # ── Parse location from detail page ──
            location = "TegneskoleKBH, Bygmestervej 5, 2400 København NV"
            for heading in detail_soup.find_all(["h2", "h3", "h4"]):
                if "Undervisningssted" in heading.get_text(strip=True):
                    loc_container = heading.find_next_sibling()
                    if loc_container:
                        loc_lines = [l.strip() for l in loc_container.get_text("\n", strip=True).split("\n") if l.strip()]
                        if loc_lines:
                            venue_name = loc_lines[0]
                            # Build full address from subsequent lines
                            address_parts = [l for l in loc_lines[:4] if l and "Se på kort" not in l]
                            if venue_name.lower() != "tegneskolekbh":
                                location = ", ".join(address_parts)
                            # else keep default TegneskoleKBH address
                    break

            # ── Parse number of sessions ──
            try:
                num_sessions = int(sessions_raw) if sessions_raw else None
            except ValueError:
                num_sessions = None

            # ── Generate one event per day ──
            from datetime import timedelta
            total_days = (last_date - first_date).days + 1

            # If we know the number of sessions and it matches the day span, great.
            # Otherwise generate consecutive days from first to last.
            if num_sessions and num_sessions <= total_days:
                # Generate exactly num_sessions consecutive days from first_date
                session_dates = [first_date + timedelta(days=d) for d in range(num_sessions)]
            else:
                session_dates = [first_date + timedelta(days=d) for d in range(total_days)]

            for session_date in session_dates:
                # Skip past individual days
                if session_date < today:
                    continue

                # Use first_time for day 1, last_time for subsequent days (if different)
                if session_date == first_date:
                    start_time = first_time
                else:
                    start_time = last_time or first_time

                # Build description
                desc_parts = []
                instructor = dd_map.get("", None)
                # Try to find instructor from the main page data
                for spot in soup.find_all("div", class_="spot--withlink"):
                    h3 = spot.find("h3")
                    if h3 and h3.get_text(strip=True) == title:
                        text = spot.get_text(" ", strip=True)
                        m = re.search(r"Underviser:\s*(.+?)(?:\s*\||\s*Sted:)", text)
                        if m:
                            desc_parts.append(f"Underviser: {m.group(1).strip()}")
                        break
                # Append day counter to event name
                day_num = (session_date - first_date).days + 1
                total = num_sessions or len(session_dates)
                display_name = f"{title} (day {day_num}/{total})" if total > 1 else title

                if num_sessions:
                    desc_parts.append(f"Dag {day_num}/{num_sessions}")

                events.append({
                    "event_name": display_name,
                    "event_date": session_date.isoformat(),
                    "start_time": start_time,
                    "end_time": None,
                    "location": location,
                    "organizer": "TegneskoleKBH",
                    "description": " | ".join(desc_parts) if desc_parts else None,
                    "url": detail_url,
                })

            if DEBUG:
                day_count = len([d for d in session_dates if d >= today])
                log(f"    ✅ {day_count} day(s): {first_date.isoformat()} → {last_date.isoformat()}")

        except Exception as e:
            log(f"    ⚠️ Could not process {detail_url}: {e}")

        time.sleep(0.5)  # Be polite between requests

    return events


# ────────────────── Urban 13 parser ──────────────────

def parse_urban13(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://www.urban13.dk/events

    Main page lists events with links to /events/<slug>.
    Each detail page has structured info in 'x'-prefixed lines:
      x Dato: DD.MM.YYYY
      x Døre: HH.MM
      x Koncerter begynder: HH.MM  (or 'Programmet begynder')
      x Sted: GARAGEN, URBAN 13 (indendørs)
    Some pages use plain 'Date:', 'Time:', 'Venue:' labels instead.
    We visit each detail page and extract event info.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    today = date.today()

    # ── Collect event links + fallback dates from the main listing ──
    event_entries: list[dict] = []  # {slug, url, title_hint, date_hint}
    seen_hrefs: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith("/events/") or href == "/events" or href == "/events/":
            continue
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        full_url = f"https://www.urban13.dk{href}"
        link_text = a_tag.get_text(" ", strip=True)

        # Try to extract a date hint from the listing text (e.g. "... 26.02.2026")
        date_hint = None
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", link_text)
        if m:
            try:
                date_hint = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass

        # Extract title hint (everything before the date)
        title_hint = link_text
        if m:
            title_hint = link_text[:m.start()].strip()

        # Skip past events based on listing date
        if date_hint and date_hint < today:
            if DEBUG:
                log(f"  Skipping past event: {title_hint} ({date_hint.isoformat()})")
            continue

        event_entries.append({
            "url": full_url,
            "title_hint": title_hint,
            "date_hint": date_hint,
        })

    if not event_entries:
        log("  No upcoming event links found")
        return events

    log(f"  Found {len(event_entries)} upcoming event link(s) — visiting each page...")

    # ── Visit each detail page ──
    for i, entry in enumerate(event_entries, 1):
        detail_url = entry["url"]
        try:
            if DEBUG:
                log(f"  [{i}/{len(event_entries)}] Visiting {detail_url.split('/')[-1]}")

            r = requests.get(detail_url, headers=SCRAPER_HEADERS, timeout=15)
            r.raise_for_status()
            detail_soup = BeautifulSoup(r.text, "html.parser")
            page_text = detail_soup.get_text("\n", strip=True)
            lines = [l.strip() for l in page_text.split("\n") if l.strip()]

            # ── Get event name from first heading ──
            event_name = None
            for tag in detail_soup.find_all(["h1", "h2"]):
                t = tag.get_text(strip=True)
                if t and len(t) > 2 and t not in [
                    "EVents", "Events", "Venue", "Urban Sessions",
                    "coworking", "Om Urban 13", "URBAN13", "PROGRAM",
                ]:
                    event_name = t
                    break
            if not event_name:
                event_name = entry["title_hint"] or "Urban 13 Event"

            # ── Extract info from 'x'-prefixed lines ──
            x_data: dict[str, str] = {}
            for line in lines:
                if line.startswith("x "):
                    # "x Dato: 26.02.2026" → key="Dato", val="26.02.2026"
                    m = re.match(r"x\s+(.+?):\s*(.+)", line)
                    if m:
                        x_data[m.group(1).strip().lower()] = m.group(2).strip()

            # ── Parse date ──
            event_date = None

            # Strategy 1: from x-data
            dato_raw = x_data.get("dato", "")
            if dato_raw:
                m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", dato_raw)
                if m:
                    try:
                        event_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                    except ValueError:
                        pass

            # Strategy 2: plain "Date:" line (English format)
            if not event_date:
                for line in lines:
                    m = re.match(r"Date:\s*(.+)", line, re.IGNORECASE)
                    if m:
                        date_text = m.group(1).strip()
                        # Try "24th February" format
                        dm = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)", date_text)
                        if dm:
                            day = int(dm.group(1))
                            month_name = dm.group(2).lower()[:3]
                            month_num = MONTH_MAP.get(month_name)
                            if not month_num:
                                # English month names
                                eng_months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4,
                                              "may": 5, "jun": 6, "jul": 7, "aug": 8,
                                              "sep": 9, "oct": 10, "nov": 11, "dec": 12}
                                month_num = eng_months.get(month_name)
                            if month_num:
                                year = today.year
                                try:
                                    event_date = date(year, month_num, day)
                                    if event_date < today:
                                        event_date = date(year + 1, month_num, day)
                                except ValueError:
                                    pass
                        break

            # Strategy 3: fall back to listing page date hint
            if not event_date and entry["date_hint"]:
                event_date = entry["date_hint"]

            if not event_date:
                if DEBUG:
                    log(f"    ⚠️ No date found — skipping")
                continue

            # Skip past events
            if event_date < today:
                if DEBUG:
                    log(f"    Skipping past: {event_name} ({event_date.isoformat()})")
                continue

            # ── Parse start time ──
            start_time = None
            end_time = None

            # From x-data: prefer "koncerter begynder" or "programmet begynder" over "døre"
            for key in ["koncerter begynder", "programmet begynder"]:
                raw = x_data.get(key, "")
                if raw:
                    m = re.match(r"(\d{1,2})[.:](\d{2})", raw)
                    if m:
                        start_time = f"{int(m.group(1)):02d}:{m.group(2)}"
                    break

            if not start_time:
                raw = x_data.get("døre", "")
                if raw:
                    m = re.match(r"(\d{1,2})[.:](\d{2})", raw)
                    if m:
                        start_time = f"{int(m.group(1)):02d}:{m.group(2)}"

            # From plain "Time:" line
            if not start_time:
                for line in lines:
                    m = re.match(r"Time:\s*(\d{1,2})[.:](\d{2})\s*[-–]\s*(\d{1,2})[.:](\d{2})", line, re.IGNORECASE)
                    if m:
                        start_time = f"{int(m.group(1)):02d}:{m.group(2)}"
                        end_time = f"{int(m.group(3)):02d}:{m.group(4)}"
                        break
                    m2 = re.match(r"Time:\s*(\d{1,2})[.:](\d{2})", line, re.IGNORECASE)
                    if m2:
                        start_time = f"{int(m2.group(1)):02d}:{m2.group(2)}"
                        break

            # ── Parse location / room ──
            room = x_data.get("sted", "")
            if not room:
                for line in lines:
                    m = re.match(r"Venue:\s*(.+)", line, re.IGNORECASE)
                    if m:
                        room = m.group(1).strip()
                        break

            location = "Urban 13, Bispeengen 20, 2000 Frederiksberg"
            if room:
                location = f"{room}, Bispeengen 20, 2000 Frederiksberg"

            # ── Description (price + doors) ──
            desc_parts = []
            forsalg = x_data.get("forsalg", "")
            dorsalg = x_data.get("dørsalg", "")
            dore = x_data.get("døre", "")
            if forsalg:
                desc_parts.append(f"Forsalg: {forsalg}")
            if dorsalg:
                desc_parts.append(f"Dørsalg: {dorsalg}")
            if dore and start_time and dore not in start_time:
                desc_parts.append(f"Døre: {dore}")

            events.append({
                "event_name": event_name,
                "event_date": event_date.isoformat(),
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "organizer": "Urban 13",
                "description": " | ".join(desc_parts) if desc_parts else None,
                "url": detail_url,
            })

            if DEBUG:
                log(f"    ✅ {event_name} — {event_date.isoformat()} {start_time or '?'}")

        except Exception as e:
            log(f"    ⚠️ Could not process {detail_url}: {e}")

        time.sleep(0.5)  # Be polite between requests

    return events


# ────────────────── Nordic Health House (NOR:) parser ──────────────────

_NOR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
}


def _analyze_nor_page_with_gemini(client, page_text: str, event_url: str) -> list[dict]:
    """
    Use Gemini to extract individual session dates/times from a NOR: workshop page.
    The date formats are highly varied (Danish, English, modules, series, etc.).
    Returns a list of {event_name, event_date, start_time, end_time, description}.
    """
    from google.genai import types

    today_str = date.today().isoformat()
    prompt = f"""Analyze this event/workshop page from NOR: Nordic Health House (a yoga and wellness center at Hejrevej 30, 2400 København NV).

Extract ALL individual session dates as separate entries in JSON. Rules:

1. WORKSHOP SERIES (multiple listed dates with same time):
   Create a SEPARATE entry for EACH date. Use the same event name for all.

2. MULTI-DAY WORKSHOPS/MODULES (e.g., "Modul 1: Fredag + Lørdag"):
   Create a SEPARATE entry for EACH day within each module.

3. "Ekstra workshop" sections are additional separate events with the same name.

4. SINGLE workshops: one entry.

5. Only include sessions from {today_str} onward. Skip past dates.

6. If a date doesn't include a year, assume 2026.

7. Parse BOTH Danish dates ("Søndag den 1. marts", "Onsdag d. 15. april") 
   AND English dates ("Friday the 20th of February").

Respond ONLY with valid JSON:
{{
  "events": [
    {{
      "event_name": "Name of the workshop",
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM (24h)" or null,
      "end_time": "HH:MM (24h)" or null,
      "description": "One-line summary or price info"
    }}
  ]
}}

If NO upcoming events are found, return {{"events": []}}.
Respond ONLY with the JSON, no extra text.

Page URL: {event_url}
Page content:
{page_text[:6000]}"""

    try:
        _gemini_limiter.wait()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4000,
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        return result.get("events", [])
    except Exception as e:
        log(f"    Gemini analysis failed: {e}")
        return []


def parse_norhouse(html: str, page_url: str) -> list[dict]:
    """
    Parser for https://nor.house/events/

    Main page lists events in portfolio cards with CSS classes indicating category
    (workshops, retreats, uddannelse). We only scrape 'workshops'.
    Each card links to a detail page with date/time info in varied formats.
    We use Gemini to reliably extract session dates from each detail page.
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    today = date.today()

    # ── Collect workshop URLs from the main page ──
    workshop_urls: list[tuple[str, str]] = []  # (title, url)
    seen_hrefs: set[str] = set()

    for card in soup.find_all("div", class_="elastic-portfolio-item"):
        classes = " ".join(card.get("class", []))

        # Only include workshops (skip pure retreats)
        if "workshops" not in classes:
            continue
        # Exclude retreats (even if also tagged as workshop)
        if "retreats" in classes:
            if DEBUG:
                h3 = card.find("h3")
                name = h3.get_text(strip=True) if h3 else "?"
                log(f"  Skipping retreat: {name}")
            continue

        a_tag = card.find("a", href=True)
        if not a_tag:
            continue
        href = a_tag["href"]
        if href in seen_hrefs or href == "https://nor.house/events/":
            continue
        seen_hrefs.add(href)

        h3 = card.find("h3")
        title = h3.get_text(strip=True) if h3 else "Workshop"
        # Clean up title: remove "(X pladser tilbage)", "(UDSOLGT)" etc.
        title = re.sub(r"\s*\((?:Få pladser tilbage|UDSOLGT!?|\d+ plads(?:er)? tilbage)\)\s*", "", title).strip()

        workshop_urls.append((title, href))

    if not workshop_urls:
        log("  No workshop links found on page")
        return events

    log(f"  Found {len(workshop_urls)} workshop(s) — visiting each detail page...")

    # ── Check Gemini availability ──
    client = get_gemini_client()
    if not client:
        log("  ⚠️ No Gemini API key — cannot analyze workshop pages")
        return events

    # ── Visit each detail page ──
    for i, (title, detail_url) in enumerate(workshop_urls, 1):
        try:
            if DEBUG:
                log(f"  [{i}/{len(workshop_urls)}] {title}")

            r = requests.get(detail_url, headers=_NOR_HEADERS, timeout=15)
            r.raise_for_status()
            detail_soup = BeautifulSoup(r.text, "html.parser")

            # Extract subtitle from .subheader (e.g. "24-timers fordybelse med Simon Krohn")
            subheader_el = detail_soup.find(class_="subheader")
            subtitle = subheader_el.get_text(strip=True) if subheader_el else None
            # Build a richer title: "Yoga og Kroppen – 24-timers fordybelse med Simon Krohn"
            full_title = f"{title} – {subtitle}" if subtitle else title

            # Extract content area (skip nav/footer)
            main = detail_soup.find("main") or detail_soup.find("article")
            if not main:
                for div in detail_soup.find_all("div"):
                    cls = " ".join(div.get("class", []))
                    if "content" in cls.lower() or "entry" in cls.lower():
                        main = div
                        break

            page_text = main.get_text("\n", strip=True) if main else detail_soup.get_text("\n", strip=True)

            if len(page_text.strip()) < 30:
                if DEBUG:
                    log(f"    ⚠️ Page has very little content — skipping")
                continue

            # Use Gemini to extract sessions
            gemini_events = _analyze_nor_page_with_gemini(client, page_text, detail_url)

            if not gemini_events:
                if DEBUG:
                    log(f"    No upcoming sessions found")
                continue

            session_count = 0
            for ev_data in gemini_events:
                event_date_str = ev_data.get("event_date")

                # Skip past events
                if event_date_str:
                    try:
                        if date.fromisoformat(event_date_str) < today:
                            continue
                    except ValueError:
                        continue

                session_count += 1
                # Prefer our HTML-enriched title (with subtitle) over Gemini's
                gemini_name = ev_data.get("event_name") or ""
                # If Gemini returned a name that's just the base title, use full_title
                if not gemini_name or gemini_name.strip().lower() == title.strip().lower():
                    ev_name = full_title
                else:
                    ev_name = gemini_name
                events.append({
                    "event_name": ev_name,
                    "event_date": event_date_str,
                    "start_time": ev_data.get("start_time"),
                    "end_time": ev_data.get("end_time"),
                    "location": "NOR: Nordic Health House, Hejrevej 30, 2400 København NV",
                    "organizer": "Nordic Health House",
                    "description": ev_data.get("description"),
                    "url": detail_url,
                })

            if DEBUG and session_count:
                log(f"    ✅ {session_count} upcoming session(s)")

        except Exception as e:
            log(f"    ⚠️ Could not process {detail_url}: {e}")

        time.sleep(0.5)

    return events


# ────────────────── Københavns Biblioteker (Cludo API) parser ──────────────────

_KK_CLUDO_API = "https://api.cludo.com/api/v3/2719/14520/search"
_KK_CLUDO_AUTH = "SiteKey MjcxOToxNDUyMDpTZWFyY2hLZXk="

# Events to skip (recurring community-service events, not cultural events)
_KK_SKIP_TITLES = {
    "lektiehjælp",
    "it-café",
    "it-cafe",
    "antidote",
    "fællesspisning",
}

# Map Cludo location names → physical addresses
_KK_LOCATION_ADDRESSES: dict[str, str] = {
    "BIBLIOTEKET Rentemestervej": "Rentemestervej 76, 2400 København NV",
}


def _parse_kk_date(text: str) -> str | None:
    """Parse Cludo Danish date like '22. februar 2026' → 'YYYY-MM-DD'.
    Also handles ranges like '7. - 22. februar 2026' (returns first date)."""
    text = text.strip()
    # Range format: "7. - 22. februar 2026"
    m = re.match(r"(\d{1,2})\.\s*-\s*\d{1,2}\.\s*([a-zæøå]+)\s+(\d{4})", text, re.IGNORECASE)
    if m:
        day, month_str, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = MONTH_MAP.get(month_str)
        if month:
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                pass
        return None
    return parse_danish_date(text)


def _fetch_kk_events(location: str) -> list[dict]:
    """Fetch all events from Cludo API for a given KK library location."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": _KK_CLUDO_AUTH,
        "Origin": "https://bibliotek.kk.dk",
        "Referer": "https://bibliotek.kk.dk/arrangementer/soeg",
    }
    payload = {
        "ResponseType": "JsonObject",
        "query": "*",
        "page": 1,
        "perPage": 100,
        "facets": {
            "Category": ["Arrangementer"],
            "Location": [location],
        },
        "sort": {"SortDate_date": "asc"},
        "applyMultiLevelFacets": True,
    }
    r = requests.post(_KK_CLUDO_API, json=payload, headers=headers, timeout=20)
    if r.status_code != 200:
        log(f"  ❌ Cludo API returned {r.status_code}")
        return []
    data = r.json()
    log(f"  Cludo API: {data.get('TotalDocument', 0)} events for '{location}'")
    return data.get("TypedDocuments", [])


def parse_kk_bibliotek(html: str, page_url: str) -> list[dict]:
    """
    Parser for Københavns Biblioteker events.
    Uses the Cludo search API to get structured event data.
    The location is extracted from the page_url's cludoLocation parameter.
    Each recurring date becomes a separate event entry.
    """
    import urllib.parse

    events: list[dict] = []
    today = date.today()

    # Extract location from URL hash parameters
    location = "BIBLIOTEKET Rentemestervej"  # default
    if "cludoLocation=" in page_url:
        # URL-encoded location in the hash fragment
        m = re.search(r"cludoLocation=([^&]+)", page_url)
        if m:
            location = urllib.parse.unquote(m.group(1))

    # Fetch events from Cludo API
    raw_docs = _fetch_kk_events(location)
    if not raw_docs:
        return events

    for doc in raw_docs:
        fields = doc.get("Fields", {})
        title = fields.get("Title", {}).get("Value", "").strip()
        if not title:
            continue

        # Skip excluded event types
        title_lower = title.lower()
        if any(skip in title_lower for skip in _KK_SKIP_TITLES):
            if DEBUG:
                log(f"  Skipping (excluded): {title}")
            continue

        event_url = fields.get("Url", {}).get("Value", "")
        description_vals = fields.get("Description", {}).get("Values", [])
        description = " ".join(d.strip() for d in description_vals if d.strip())[:2000] if description_vals else None
        price = fields.get("EventPrice", {}).get("Value", "")
        tag = fields.get("Tag", {}).get("Value", "")

        # Add price and tag to description
        desc_parts = []
        if description:
            desc_parts.append(description)
        if price and price.lower() != "gratis":
            desc_parts.append(f"Pris: {price}")
        elif price.lower() == "gratis":
            desc_parts.append("Gratis")
        if tag:
            desc_parts.append(f"Kategori: {tag}")
        full_description = " | ".join(desc_parts) if desc_parts else None

        # Parse main event date and time
        main_date_str = fields.get("EventDate", {}).get("Value", "")
        main_time_str = fields.get("EventTime", {}).get("Value", "").strip()
        main_date = _parse_kk_date(main_date_str) if main_date_str else None

        start_time, end_time = parse_time_range(main_time_str) if main_time_str else (None, None)

        # Collect all dates: main date + related dates
        all_dates: list[tuple[str | None, str | None, str | None]] = []  # (date, start_time, end_time)
        if main_date:
            all_dates.append((main_date, start_time, end_time))

        # Related dates (for recurring events)
        related_dates = fields.get("EventsRelatedDate", {}).get("Values", [])
        related_times = fields.get("EventsRelatedTime", {}).get("Values", [])
        for idx, rd in enumerate(related_dates):
            rd_parsed = _parse_kk_date(rd)
            if not rd_parsed:
                continue
            # Get matching time if available
            rt = related_times[idx].strip() if idx < len(related_times) else ""
            rt_start, rt_end = parse_time_range(rt) if rt else (start_time, end_time)
            all_dates.append((rd_parsed, rt_start, rt_end))

        # Filter out past dates and add events
        for ev_date, ev_start, ev_end in all_dates:
            if not ev_date:
                continue
            try:
                if date.fromisoformat(ev_date) < today:
                    continue
            except ValueError:
                continue

            events.append({
                "event_name": title,
                "event_date": ev_date,
                "start_time": ev_start,
                "end_time": ev_end,
                "location": f"{location}, {_KK_LOCATION_ADDRESSES.get(location, '')}".rstrip(", "),
                "organizer": location,
                "description": full_description,
                "url": event_url,
            })

    return events


def _fetch_kk_dummy(url: str) -> str:
    """Dummy fetch for KK bibliotek — the parser uses the Cludo API directly."""
    return ""


# ────────────────── Generic KK Culture Events fetcher ──────────────────
# Shared by Dansekapellet and Lygten Station (same KK CMS)

def _fetch_kk_events(
    url: str,
    *,
    base_url: str,
    event_link_prefix: str,
    location: str,
    organizer: str,
    exclude_titles: set[str] | None = None,
    exclude_categories: set[str] | None = None,
    gemini_date_ranges: bool = False,
) -> str:
    """
    Generic Playwright-based fetcher for KK (Københavns Kommune) culture sites.
    Handles:
      - "Vis flere" pagination on listing page
      - Cookie banner dismissal
      - Flatpickr calendars with multiple dates
      - Multiple time slots per date
      - Optionally Gemini-based date extraction for date-range events
    Returns JSON string of event dicts.
    """
    from playwright.sync_api import sync_playwright

    exclude_titles = exclude_titles or set()
    exclude_categories = exclude_categories or set()
    events_data: list[dict] = []
    today = date.today()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="da-DK",
        )
        page = context.new_page()

        # ─── Step 1: load listing page ───
        log(f"  Loading {url} ...")
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # Dismiss cookie banner
        try:
            cookie_btn = page.locator('button:has-text("Accepter alle cookies"), button:has-text("Acceptér alle cookies")')
            if cookie_btn.count() > 0:
                cookie_btn.first.click(timeout=3000)
                page.wait_for_timeout(1000)
                log("    Cookie banner dismissed.")
        except Exception:
            pass

        # Handle "Vis flere" pagination
        click_count = 0
        while True:
            try:
                vis_flere = page.locator('a:has-text("Vis flere"), button:has-text("Vis flere")')
                if vis_flere.count() > 0 and vis_flere.first.is_visible():
                    vis_flere.first.click(timeout=5000)
                    page.wait_for_timeout(2000)
                    click_count += 1
                else:
                    break
            except Exception:
                break
        if click_count:
            log(f"    Clicked 'Vis flere' {click_count} time(s)")

        # ─── Step 2: collect event links ───
        soup = BeautifulSoup(page.content(), "html.parser")
        event_links: list[dict] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Match event detail links
            if event_link_prefix in href and href != event_link_prefix and href.rstrip("/") != event_link_prefix.rstrip("/"):
                slug = href.rstrip("/").rsplit("/", 1)[-1]
                link_text = a.get_text(strip=True).lower()
                # Check title exclusion
                if any(ex in link_text for ex in exclude_titles) or \
                   any(ex in slug for ex in exclude_titles):
                    log(f"    Skipping excluded: {slug}")
                    continue
                full_url = f"{base_url}{href}" if href.startswith("/") else href
                if full_url not in [el["url"] for el in event_links]:
                    event_links.append({"slug": slug, "url": full_url})

        log(f"  Found {len(event_links)} event(s) on listing page")

        # ─── Step 3: visit each detail page ───
        for ev_link in event_links:
            ev_url = ev_link["url"]
            slug = ev_link["slug"]
            log(f"    Processing: {slug}")

            try:
                page.goto(ev_url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                # Dismiss cookie banner if it re-appears
                page.evaluate(
                    '() => { const el = document.getElementById("sliding-popup");'
                    ' if (el) el.style.display = "none"; }'
                )

                detail_soup = BeautifulSoup(page.content(), "html.parser")

                # Category check
                if exclude_categories:
                    page_category = None
                    for tag in detail_soup.find_all(["span", "div", "a"]):
                        txt = tag.get_text(strip=True).lower()
                        if txt in ("forestilling", "bevægelse", "fællesskaber",
                                   "kursus", "klasse", "workshop", "udstilling",
                                   "comedy", "koncert", "musik"):
                            page_category = txt
                            break
                    if page_category and page_category in exclude_categories:
                        log(f"      Skipping (category '{page_category}'): {slug}")
                        continue

                # Title
                title = None
                for h1 in detail_soup.find_all("h1"):
                    txt = h1.get_text(strip=True)
                    if txt and not any(skip in txt.lower() for skip in
                                       ["cookie", "primær", "brødkrumme", "navigation"]):
                        title = txt
                        break
                if not title:
                    title_tag = detail_soup.find("title")
                    title = title_tag.get_text(strip=True).split("|")[0].strip() if title_tag else slug

                # Double-check exclusion
                if any(ex in title.lower() for ex in exclude_titles):
                    log(f"      Skipping excluded: {title}")
                    continue

                # Description
                body_field = detail_soup.find(class_="field--name-body")
                description = body_field.get_text(strip=True)[:500] if body_field else None

                # Price
                price_parts = []
                for el in detail_soup.find_all(string=lambda s: s and "kr." in s):
                    t = el.strip()
                    if "kr." in t and len(t) < 50 and "cookie" not in t.lower():
                        price_parts.append(t)
                if price_parts:
                    price_info = " / ".join(price_parts[:3])
                    if description:
                        description = f"{description} | Pris: {price_info}"
                    else:
                        description = f"Pris: {price_info}"

                # Expand date selector
                try:
                    page.click('summary:has-text("Vælg anden dato")', timeout=3000)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass

                # Get all enabled dates from flatpickr
                enabled_dates = page.evaluate('''() => {
                    let fp = null;
                    for (const el of document.querySelectorAll('*')) {
                        if (el._flatpickr) { fp = el._flatpickr; break; }
                    }
                    if (!fp || !fp.config || !fp.config.enable) return [];
                    return fp.config.enable.map(d => {
                        const dt = new Date(d);
                        return dt.getFullYear() + '-'
                            + String(dt.getMonth()+1).padStart(2,'0') + '-'
                            + String(dt.getDate()).padStart(2,'0');
                    });
                }''')

                if not enabled_dates:
                    # Fallback: displayed date/time
                    date_span = detail_soup.find("span", class_="date")
                    time_span = detail_soup.find("span", class_="time")
                    if date_span:
                        dtext = date_span.get_text(strip=True)
                        if " - " in dtext and gemini_date_ranges:
                            parts = dtext.split(" - ", 1)
                            end_d = parse_danish_date(parts[1].strip())
                            if end_d and date.fromisoformat(end_d) >= today:
                                gemini_events = _dansekapellet_gemini_dates(
                                    detail_soup, ev_url, title, description
                                )
                                if gemini_events:
                                    for ge in gemini_events:
                                        try:
                                            if date.fromisoformat(ge["event_date"]) < today:
                                                continue
                                        except (ValueError, KeyError):
                                            continue
                                        events_data.append({
                                            "event_name": ge.get("event_name", title),
                                            "event_date": ge["event_date"],
                                            "start_time": ge.get("start_time"),
                                            "end_time": ge.get("end_time"),
                                            "location": location,
                                            "organizer": organizer,
                                            "description": ge.get("description", description),
                                            "url": ev_url,
                                        })
                                    log(f"      Gemini found {len(gemini_events)} date(s) in images")
                                else:
                                    start_d = parse_danish_date(parts[0].strip())
                                    ev_date = start_d or end_d
                                    st, et = parse_time_range(time_span.get_text(strip=True)) if time_span else (None, None)
                                    desc_with_range = f"Program: {dtext}"
                                    if description:
                                        desc_with_range = f"{description} | {desc_with_range}"
                                    events_data.append({
                                        "event_name": title,
                                        "event_date": ev_date,
                                        "start_time": st,
                                        "end_time": et,
                                        "location": location,
                                        "organizer": organizer,
                                        "description": desc_with_range,
                                        "url": ev_url,
                                    })
                        elif " - " in dtext and not gemini_date_ranges:
                            # Date range but no Gemini — just use end date if future
                            parts = dtext.split(" - ", 1)
                            start_d = parse_danish_date(parts[0].strip())
                            end_d = parse_danish_date(parts[1].strip())
                            ev_date = start_d or end_d
                            if ev_date and date.fromisoformat(ev_date) >= today:
                                st, et = parse_time_range(time_span.get_text(strip=True)) if time_span else (None, None)
                                events_data.append({
                                    "event_name": title,
                                    "event_date": ev_date,
                                    "start_time": st,
                                    "end_time": et,
                                    "location": location,
                                    "organizer": organizer,
                                    "description": description,
                                    "url": ev_url,
                                })
                        else:
                            ev_date = parse_danish_date(dtext)
                            if ev_date:
                                st, et = parse_time_range(time_span.get_text(strip=True)) if time_span else (None, None)
                                if date.fromisoformat(ev_date) >= today:
                                    events_data.append({
                                        "event_name": title,
                                        "event_date": ev_date,
                                        "start_time": st,
                                        "end_time": et,
                                        "location": location,
                                        "organizer": organizer,
                                        "description": description,
                                        "url": ev_url,
                                    })
                    continue

                log(f"      {len(enabled_dates)} date(s) in calendar")

                # For each enabled date, click it and read time slots
                for i, date_str in enumerate(enabled_dates):
                    try:
                        ev_date_obj = date.fromisoformat(date_str)
                    except ValueError:
                        continue
                    if ev_date_obj < today:
                        continue

                    page.evaluate(f'''() => {{
                        const days = document.querySelectorAll(
                            '.flatpickr-day:not(.flatpickr-disabled):not(.prevMonthDay):not(.nextMonthDay)'
                        );
                        if (days.length > {i}) days[{i}].click();
                    }}''')
                    page.wait_for_timeout(800)

                    time_slots = page.evaluate('''() => {
                        const timesDiv = document.querySelector('.date-selector .times');
                        if (!timesDiv) return [];
                        const buttons = timesDiv.querySelectorAll('button');
                        return Array.from(buttons).map(b => ({
                            text: b.textContent.trim(),
                            dataTime: b.getAttribute('data-time'),
                        }));
                    }''')

                    if time_slots:
                        for slot in time_slots:
                            st, et = parse_time_range(slot["text"])
                            if not st and slot.get("dataTime"):
                                st = slot["dataTime"]
                            events_data.append({
                                "event_name": title,
                                "event_date": date_str,
                                "start_time": st,
                                "end_time": et,
                                "location": location,
                                "organizer": organizer,
                                "description": description,
                                "url": ev_url,
                            })
                    else:
                        detail_soup2 = BeautifulSoup(page.content(), "html.parser")
                        time_span = detail_soup2.find("span", class_="time")
                        st, et = parse_time_range(time_span.get_text(strip=True)) if time_span else (None, None)
                        events_data.append({
                            "event_name": title,
                            "event_date": date_str,
                            "start_time": st,
                            "end_time": et,
                            "location": location,
                            "organizer": organizer,
                            "description": description,
                            "url": ev_url,
                        })

                time.sleep(0.5)

            except Exception as e:
                log(f"      ❌ Error processing {slug}: {e}")
                continue

        browser.close()

    return json.dumps(events_data, ensure_ascii=False)


def _parse_kk_events_json(html: str, page_url: str) -> list[dict]:
    """Parse the JSON string produced by _fetch_kk_events."""
    if not html:
        return []
    try:
        return json.loads(html)
    except (json.JSONDecodeError, TypeError):
        return []


# ────────────────── Dansekapellet (dansekapellet.kk.dk) ──────────────────

_DANSEKAPELLET_EXCLUDE_TITLES = {"legestuen"}  # always skip by name
_DANSEKAPELLET_EXCLUDE_CATEGORIES = {"bevægelse"}  # skip class/movement categories
_DANSEKAPELLET_ADDR = "Dansekapellet, Bispebjerg Torv 1, 2400 København NV"


def _dansekapellet_gemini_dates(
    soup: BeautifulSoup, event_url: str, title: str, description: str | None
) -> list[dict]:
    """
    For Dansekapellet events with a date range (long-running programs/exhibitions),
    download the page images and use Gemini to extract specific event dates.
    Returns a list of event dicts with event_name, event_date, start_time, end_time, description.
    """
    client = get_gemini_client()
    if not client:
        log("      ⚠️ No Gemini client — skipping image analysis")
        return []

    from google.genai import types
    from PIL import Image
    import tempfile

    # Collect images from the page
    base_url = "https://dansekapellet.kk.dk"
    image_parts = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src or any(skip in src.lower() for skip in ["logo", "icon", "svg", "placeholder"]):
            continue
        full_url = base_url + src if src.startswith("/") else src
        try:
            r = requests.get(full_url, timeout=15)
            if r.status_code == 200 and len(r.content) > 2000:  # skip tiny images
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(r.content)
                    tmp_path = f.name
                img_obj = Image.open(tmp_path)
                image_parts.append(img_obj)
        except Exception:
            continue

    if not image_parts:
        log("      No usable images found for Gemini analysis")
        return []

    # Get page text
    body = soup.find(class_="field--name-body")
    page_text = body.get_text(strip=True)[:3000] if body else ""

    today_str = date.today().isoformat()
    prompt = f"""This is an event/program page from Dansekapellet (a dance venue in Copenhagen).

Event title: {title}
Event URL: {event_url}
Page text: {page_text[:2000]}

The page shows a date range, meaning this is a long-running program with SPECIFIC individual event dates.
Look at ALL the images carefully — the flyers/posters typically contain the individual dates and times.

Extract ALL individual events/sessions with their specific dates and times.
Only include events from {today_str} onward. Skip past dates.

Respond ONLY with valid JSON:
{{
  "events": [
    {{
      "event_name": "{title}" or a more specific name if the image shows one,
      "event_date": "YYYY-MM-DD",
      "start_time": "HH:MM (24h)" or null,
      "end_time": "HH:MM (24h)" or null,
      "description": "Brief description of this specific session"
    }}
  ]
}}

If no specific dates can be found in the images, return {{"events": []}}.
Respond ONLY with the JSON, no extra text."""

    try:
        _gemini_limiter.wait()
        content = list(image_parts) + [prompt]
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=content,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4000,
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        return result.get("events", [])
    except Exception as e:
        log(f"      Gemini analysis failed: {e}")
        return []


def fetch_dansekapellet(url: str) -> str:
    """Fetch Dansekapellet events using the generic KK fetcher."""
    return _fetch_kk_events(
        url,
        base_url="https://dansekapellet.kk.dk",
        event_link_prefix="/events/",
        location=_DANSEKAPELLET_ADDR,
        organizer="Dansekapellet",
        exclude_titles=_DANSEKAPELLET_EXCLUDE_TITLES,
        exclude_categories=_DANSEKAPELLET_EXCLUDE_CATEGORIES,
        gemini_date_ranges=True,
    )


def parse_dansekapellet(html: str, page_url: str) -> list[dict]:
    return _parse_kk_events_json(html, page_url)


# ────────────────── Lygten Station (kulturogfritidn.kk.dk) ──────────────────

_LYGTENSTATION_ADDR = "Lygten Station, Lygten 2, 2400 København NV"


def fetch_lygtenstation(url: str) -> str:
    """Fetch Lygten Station events using the generic KK fetcher."""
    return _fetch_kk_events(
        url,
        base_url="https://kulturogfritidn.kk.dk",
        event_link_prefix="/det-sker/",
        location=_LYGTENSTATION_ADDR,
        organizer="Lygten Station",
    )


def parse_lygtenstation(html: str, page_url: str) -> list[dict]:
    return _parse_kk_events_json(html, page_url)


# ────────────────── Danish Church Calendar (TYPO3 tx-cal) ──────────────────
# Shared by Tagensbo Kirke, Kapernaumskirken, and other Folkekirke websites.

# Event types to exclude (religious services, not public events)
_CHURCH_EXCLUDE = {
    "højmesse", "gudstjeneste", "andagt", "liturgisk",
    "skærtorsdag", "langfredag", "påskedag", "pinse",
    "babysalmesang", "rytmik", "tumlerytmik", "minirytmik",
    "spirekoret", "juniorkoret", "ungdomskoret",
    "kirkekaffe", "motorik", "kontoret holder",
}


def _parse_church_calendar(
    html: str,
    page_url: str,
    *,
    location: str,
    organizer: str,
    base_url: str,
) -> list[dict]:
    """
    Generic parser for Danish Folkekirke websites using the TYPO3 tx-cal plugin.
    Each event is a div.calendar__item with .date, .month, .event-time,
    h2.calendar__header, and a link containing the full date in the URL.
    """
    soup = BeautifulSoup(html, "html.parser")
    today = date.today()
    events: list[dict] = []

    items = soup.find_all("div", class_="calendar__item")
    log(f"  Found {len(items)} calendar item(s) on page")

    for item in items:
        # Title (some churches use h2, others h3)
        title_el = item.find(["h2", "h3"], class_="calendar__header")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)

        # Check exclusion: skip if any exclude keyword is in the title
        title_lower = title.lower()
        if any(ex in title_lower for ex in _CHURCH_EXCLUDE):
            continue
        # Skip cancelled events
        if "aflyst" in title_lower:
            continue
        # Skip "henviser til" redirect notices
        if "henviser til" in title_lower:
            continue

        # Date: extract from the detail link URL (format: /begivenhed/DD-M-YYYY-...)
        link_el = item.find("a", href=True)
        ev_date = None
        ev_url = page_url
        if link_el:
            href = link_el["href"]
            ev_url = f"{base_url}{href}" if href.startswith("/") else href
            # Try to extract date from URL: /begivenhed/22-2-2026-...
            m = re.search(r"/(\d{1,2})-(\d{1,2})-(\d{4})-", href)
            if m:
                day, month_num, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                try:
                    ev_date = date(year, month_num, day).isoformat()
                except ValueError:
                    pass

        # Fallback: parse from .date + .month spans
        if not ev_date:
            date_el = item.find("span", class_="date")
            month_el = item.find("span", class_="month")
            if date_el and month_el:
                day_str = date_el.get_text(strip=True)
                month_str = month_el.get_text(strip=True).rstrip(".")
                date_text = f"{day_str} {month_str}"
                ev_date = parse_danish_date(date_text)

        if not ev_date:
            continue

        # Skip past events
        try:
            if date.fromisoformat(ev_date) < today:
                continue
        except ValueError:
            continue

        # Time
        time_el = item.find("span", class_="event-time")
        start_time = None
        end_time = None
        if time_el:
            time_text = time_el.get_text(strip=True)
            # Format: "kl. 16:00" or "kl. 16:00 - 17:30"
            time_text = time_text.replace("kl.", "").strip()
            start_time, end_time = parse_time_range(time_text)

        # Description
        desc_el = item.find("div", class_="calendarlist__teaser")
        description = desc_el.get_text(strip=True)[:500] if desc_el else None

        events.append({
            "event_name": title,
            "event_date": ev_date,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "organizer": organizer,
            "description": description,
            "url": ev_url,
        })

    return events


# ── Tagensbo Kirke ──

def parse_tagensbo(html: str, page_url: str) -> list[dict]:
    return _parse_church_calendar(
        html, page_url,
        location="Tagensbo Kirke, Landsdommervej 35, 2400 København NV",
        organizer="Tagensbo Kirke",
        base_url="https://www.tagensbo.dk",
    )


# ── Kapernaumskirken (ChurchDesk widget — requires Playwright) ──

_KAPERNAUMSKIRKEN_WIDGET = (
    "https://widget.churchdesk.com/da/w/444/event/DIqjahiE56tG/1/1393468"
)
_KAPERNAUMSKIRKEN_ADDR = "Kapernaumskirken, Frederikssundsvej 45, 2400 København NV"


def fetch_kapernaumskirken(url: str) -> str:
    """Playwright fetcher for Kapernaumskirken's ChurchDesk event widget."""
    from playwright.sync_api import sync_playwright

    events_data: list[dict] = []
    today = date.today()
    from datetime import timedelta
    max_date = today + timedelta(days=180)  # ~6 months ahead

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="da-DK",
        )

        log(f"  Loading ChurchDesk widget …")
        page.goto(_KAPERNAUMSKIRKEN_WIDGET, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        page_num = 0
        hit_max_date = False
        while True:
            page_num += 1

            raw_events = page.evaluate(r'''() => {
                const cards = document.querySelectorAll(".ant-card");
                const results = [];
                cards.forEach(card => {
                    const h2s = card.querySelectorAll("h2");
                    const spans = card.querySelectorAll("span.ant-typography");
                    let eventName = h2s.length > 1 ? h2s[1].textContent.trim() : "";
                    let dateTime = "";
                    let location = "";
                    for (const span of spans) {
                        const t = span.textContent.trim();
                        if (/\d{4},\s*kl\./.test(t)) dateTime = t;
                        else if (/^[A-ZÆØÅ]{3}\.?$/.test(t)) {} // month abbr
                        else if (/^\d+$/.test(t)) {} // day number
                        else if (t.length > 3 && !location) location = t;
                    }
                    results.push({eventName, dateTime, location});
                });
                return results;
            }''')

            if not raw_events:
                break

            log(f"    Page {page_num}: {len(raw_events)} event(s)")

            for ev in raw_events:
                name = ev.get("eventName", "")
                if not name:
                    continue

                # Apply church exclusions
                name_lower = name.lower()
                if any(ex in name_lower for ex in _CHURCH_EXCLUDE):
                    continue
                if "aflyst" in name_lower or "lukket" in name_lower:
                    continue

                # Parse date/time: "Søndag 22. februar 2026, kl. 11:00 - 12:00"
                dt_str = ev.get("dateTime", "")
                if not dt_str:
                    continue

                ev_date = None
                start_time = None
                end_time = None

                # Extract date
                dm = re.search(
                    r"(\d{1,2})\.\s+"
                    r"(januar|februar|marts|april|maj|juni|juli|august|"
                    r"september|oktober|november|december)\s+(\d{4})",
                    dt_str, re.IGNORECASE,
                )
                if dm:
                    _MONTHS_DA = {
                        "januar": 1, "februar": 2, "marts": 3, "april": 4,
                        "maj": 5, "juni": 6, "juli": 7, "august": 8,
                        "september": 9, "oktober": 10, "november": 11, "december": 12,
                    }
                    day = int(dm.group(1))
                    month = _MONTHS_DA.get(dm.group(2).lower(), 0)
                    year = int(dm.group(3))
                    if month:
                        try:
                            ev_date = date(year, month, day).isoformat()
                        except ValueError:
                            pass

                if not ev_date:
                    continue

                # Skip past events and events too far in the future
                try:
                    ev_date_obj = date.fromisoformat(ev_date)
                    if ev_date_obj < today:
                        continue
                    if ev_date_obj > max_date:
                        hit_max_date = True
                        continue
                except ValueError:
                    continue

                # Extract time: "kl. 11:00 - 12:00" or "kl. 10:30"
                tm = re.search(r"kl\.\s*(\d{1,2}[:.]\d{2})\s*(?:-\s*(\d{1,2}[:.]\d{2}))?", dt_str)
                if tm:
                    start_time = tm.group(1).replace(".", ":")
                    if tm.group(2):
                        end_time = tm.group(2).replace(".", ":")

                loc = ev.get("location", "") or _KAPERNAUMSKIRKEN_ADDR

                events_data.append({
                    "event_name": name,
                    "event_date": ev_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": loc,
                    "organizer": "Kapernaumskirken",
                    "description": None,
                    "url": "https://www.kapernaumskirken.dk/begivenheder--faellesskaber",
                })

            # Stop if all events on this page were beyond max date
            if hit_max_date and not raw_events:
                break

            # Try clicking next page
            next_btn = page.query_selector('button[aria-label="Næste side"]')
            if next_btn and next_btn.is_enabled():
                next_btn.click()
                page.wait_for_timeout(2000)
            else:
                break

            if page_num > 50:  # safety limit
                break

        browser.close()

    log(f"  Total after filtering: {len(events_data)} event(s)")
    return json.dumps(events_data, ensure_ascii=False)


def parse_kapernaumskirken(html: str, page_url: str) -> list[dict]:
    """Parse pre-fetched JSON from fetch_kapernaumskirken."""
    try:
        return json.loads(html)
    except (json.JSONDecodeError, TypeError):
        return []


# ── Ansgarkirken ──

def parse_ansgarkirken(html: str, page_url: str) -> list[dict]:
    return _parse_church_calendar(
        html, page_url,
        location="Ansgarkirken, Sallingvej 35, 2720 Vanløse",
        organizer="Ansgarkirken",
        base_url="https://www.ansgarkirke.dk",
    )


# ────────────────── Parser registry ──────────────────
# Key = lowercase name matching source_mapping.csv "name" column
# Value = (parser_function, events_page_url) for simple HTTP fetch
#     or  (parser_function, events_page_url, fetch_function) for Playwright fetch
SITE_PARSERS: dict[str, tuple] = {
    "rodderne": (parse_rodder, "https://www.rodder.dk/events"),
    "ungdomshuset d61": (parse_ungdomshuset, "https://www.ungdomshuset.dk/", fetch_ungdomshuset),
    "thoravej 29": (parse_thoravej29, "https://www.thoravej29.dk/da/events", fetch_thoravej29),
    "flere fugle": (parse_flerefugle, "https://www.flerefugle.dk/events"),
    "just sauna": (parse_justsauna, "https://www.justsauna.dk/special-events", fetch_justsauna),
    "sauna 85": (parse_sauna85, "https://www.sauna85.dk/bliv-gusmester/", fetch_sauna85),
    "demokratigarage": (parse_demokratigarage, "https://www.demokratigarage.dk/kalender/", fetch_demokratigarage),
    "tegneskole kbh": (parse_tegneskolekbh, "https://www.tegneskolekbh.dk/workshops/"),
    "urban 13": (parse_urban13, "https://www.urban13.dk/events"),
    "nordic health house": (parse_norhouse, "https://nor.house/events/"),
    "biblioteket rentemestervej": (
        parse_kk_bibliotek,
        "https://bibliotek.kk.dk/arrangementer/soeg#?cludoquery=*&cludoCategory=Arrangementer&cludoLocation=BIBLIOTEKET%20Rentemestervej&cludosort=SortDate_date%3Dasc&cludopage=1&cludoinputtype=standard",
        _fetch_kk_dummy,
    ),
    "dansekapellet": (
        parse_dansekapellet,
        "https://dansekapellet.kk.dk/events",
        fetch_dansekapellet,
    ),
    "lygten station": (
        parse_lygtenstation,
        "https://kulturogfritidn.kk.dk/det-sker?place%5B0%5D=Lygten%20Station&title=Det%20sker%20p%C3%A5%20Lygten%20Station",
        fetch_lygtenstation,
    ),
    "tagensbo kirke": (parse_tagensbo, "https://www.tagensbo.dk/aktiviteter-i-kirken"),
    "ansgarkirken": (parse_ansgarkirken, "https://www.ansgarkirke.dk/kalender"),
    "kapernaumskirken": (
        parse_kapernaumskirken,
        "https://www.kapernaumskirken.dk/begivenheder--faellesskaber",
        fetch_kapernaumskirken,
    ),
}


# ────────────────── Notion helpers ──────────────────

def notion_existing_entries() -> tuple[dict, list]:
    """Load existing Notion entries. Returns (url_to_page_id, all_entries_list)."""
    url_to_page: dict[str, str] = {}
    all_entries: list[dict] = []
    payload = {"page_size": 100}

    while True:
        r = requests.post(
            f"{NOTION_API}/databases/{NOTION_DB}/query",
            headers=NOTION_HEADERS, json=payload, timeout=30,
        )
        if r.status_code != 200:
            log(f"Notion query error: {r.status_code}")
            break
        data = r.json()

        for page in data.get("results", []):
            props = page.get("properties", {})
            url_val = (props.get("URL") or {}).get("url")
            name_parts = (props.get("Name") or {}).get("title", [])
            name = name_parts[0]["text"]["content"] if name_parts else ""
            source_parts = (props.get("Source") or {}).get("rich_text", [])
            source = source_parts[0]["text"]["content"] if source_parts else ""
            date_prop = (props.get("Start Date") or {}).get("date") or {}
            start_date = date_prop.get("start", "")
            # Extract start time for dedup key (handles multiple time slots per day)
            start_time_parts = (props.get("Start Time") or {}).get("rich_text", [])
            start_time = start_time_parts[0]["text"]["content"] if start_time_parts else ""

            entry = {
                "page_id": page["id"],
                "name": name,
                "url": url_val or "",
                "source": source,
                "start_date": start_date,
            }
            all_entries.append(entry)
            if url_val:
                # Use url##date##time as dedup key (same page can have multiple time slots per day)
                dedup_key = f"{url_val}##{start_date}##{start_time}"
                url_to_page[dedup_key] = page["id"]
                # Also keep url##date key for backward compat
                dedup_key_no_time = f"{url_val}##{start_date}"
                if dedup_key_no_time not in url_to_page:
                    url_to_page[dedup_key_no_time] = page["id"]
                # Also keep plain URL key for backward compat with FB/IG entries
                if url_val not in url_to_page:
                    url_to_page[url_val] = page["id"]

        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")

    log(f"Preloaded {len(all_entries)} Notion entries")
    return url_to_page, all_entries


def build_notion_props(ev: dict) -> dict:
    """Build Notion properties using the unified column schema."""
    props = {}

    name = ev.get("event_name") or "Untitled Event"
    props["Name"] = {"title": [{"text": {"content": name[:2000]}}]}

    if ev.get("url"):
        props["URL"] = {"url": ev["url"]}

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

    if ev.get("location"):
        props["Location"] = {
            "rich_text": [{"text": {"content": ev["location"][:2000]}}]
        }

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

    if ev.get("description"):
        props["Description"] = {
            "rich_text": [{"text": {"content": ev["description"][:2000]}}]
        }

    if ev.get("possible_duplicate") is not None:
        props["Possible Duplicate"] = {"checkbox": bool(ev["possible_duplicate"])}

    if ev.get("ig_handle"):
        props["Instagramhandle"] = {
            "rich_text": [{"text": {"content": ev["ig_handle"][:2000]}}]
        }

    if ev.get("to_tag"):
        props["To tag"] = {
            "rich_text": [{"text": {"content": ev["to_tag"][:2000]}}]
        }

    return props


def notion_create(ev: dict) -> requests.Response:
    payload = {"parent": {"database_id": NOTION_DB}, "properties": build_notion_props(ev)}
    return requests.post(
        f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=30,
    )


def notion_update(page_id: str, ev: dict) -> requests.Response:
    payload = {"properties": build_notion_props(ev)}
    return requests.patch(
        f"{NOTION_API}/pages/{page_id}", headers=NOTION_HEADERS, json=payload, timeout=30,
    )


# ────────────────── Per-site scrape function (used by runner) ──────────────────

def scrape_site(site_key: str, existing: dict, all_entries: list,
                source_mapping: dict, ig_handle: str | None = None) -> dict:
    """
    Scrape a single website for events.
    Args:
        site_key: lowercase key matching SITE_PARSERS
        existing: dict of url -> page_id (mutated in-place)
        all_entries: list of all Notion entries (mutated in-place)
        source_mapping: from dedup.load_source_mapping()
        ig_handle: optional IG handle to add to Notion entries
    Returns dict: {created, updated, skipped, flagged_dupes, total_events}
    """
    created = updated = skipped = flagged_dupes = total_events = 0

    if site_key not in SITE_PARSERS:
        log(f"  No parser registered for '{site_key}'")
        return {"created": 0, "updated": 0, "skipped": 0,
                "flagged_dupes": 0, "total_events": 0}

    entry = SITE_PARSERS[site_key]
    parser_fn = entry[0]
    events_url = entry[1]
    custom_fetch = entry[2] if len(entry) > 2 else None

    # Fetch the page (custom fetch for Playwright-based sites, else plain HTTP)
    try:
        if custom_fetch:
            html = custom_fetch(events_url)
        else:
            r = requests.get(events_url, headers=SCRAPER_HEADERS, timeout=30)
            r.raise_for_status()
            # Force UTF-8 when server mis-reports encoding (e.g. flerefugle.dk)
            if r.apparent_encoding and r.apparent_encoding.lower().startswith("utf"):
                r.encoding = "utf-8"
            html = r.text
    except Exception as e:
        log(f"  ❌ Could not fetch {events_url}: {e}")
        return {"created": 0, "updated": 0, "skipped": 0,
                "flagged_dupes": 0, "total_events": 0}

    # Parse events
    parsed_events = parser_fn(html, events_url)
    log(f"  Found {len(parsed_events)} upcoming event(s)")
    total_events = len(parsed_events)

    for event_data in parsed_events:
        event_url = event_data.get("url", events_url)

        # ── Handle cross-posted events (e.g. Flere Fugle events on Demokratigarage) ──
        crosspost_entity = event_data.pop("_crosspost_entity", None)
        if crosspost_entity:
            # Search for an existing Notion entry from the cross-post entity with
            # the same event name (fuzzy) and date.  If found, update its "To tag".
            # If not found, create as a regular event and flag as Possible Duplicate.
            ev_name = event_data.get("event_name", "")
            ev_date = event_data.get("event_date", "")
            matched_page_id = None
            for entry in all_entries:
                if entry.get("start_date", "")[:10] != ev_date:
                    continue
                entry_source = (entry.get("source") or "").lower()
                if crosspost_entity not in entry_source:
                    continue
                # Fuzzy name match (Jaccard 60% — titles may differ slightly)
                existing_name = entry.get("name", "")
                if similarity(ev_name, existing_name) >= 0.55 or ev_name.lower() in existing_name.lower():
                    matched_page_id = entry.get("page_id")
                    break

            if matched_page_id:
                # Update existing entry's "To tag" to include @demokratigarage
                tag_update = {"To tag": {
                    "rich_text": [{"text": {"content": "@demokratigarage"}}]
                }}
                resp = requests.patch(
                    f"{NOTION_API}/pages/{matched_page_id}",
                    headers=NOTION_HEADERS,
                    json={"properties": tag_update},
                    timeout=30,
                )
                updated += 1
                log(f"    → ✏️  Cross-post: updated To tag on '{ev_name}' ({crosspost_entity})")
                time.sleep(0.3)
                continue
            else:
                # No match found — create as a regular event for this site,
                # but flag as Possible Duplicate so the user can review.
                log(f"    → ⚠️  Cross-post: no matching '{crosspost_entity}' entry for '{ev_name}' — creating as {site_key} + flagging duplicate")
                event_data["_flag_duplicate"] = True

                # Also flag any existing entries from the cross-post entity on the
                # same date as Possible Duplicate so both sides are marked.
                for entry in all_entries:
                    if entry.get("start_date", "")[:10] != ev_date:
                        continue
                    entry_source = (entry.get("source") or "").lower()
                    if crosspost_entity not in entry_source:
                        continue
                    dup_page_id = entry.get("page_id")
                    if dup_page_id:
                        requests.patch(
                            f"{NOTION_API}/pages/{dup_page_id}",
                            headers=NOTION_HEADERS,
                            json={"properties": {"Possible Duplicate": {"checkbox": True}}},
                            timeout=30,
                        )
                        log(f"    → ⚠️  Also flagged '{entry.get('name', '?')}' ({crosspost_entity}) as Possible Duplicate")

                # Fall through to normal event creation below

        ev = {
            "event_name": event_data.get("event_name"),
            "organizer": event_data.get("organizer"),
            "start_date": event_data.get("event_date"),
            "end_date": event_data.get("event_date"),
            "start_time_disp": to_12h(event_data.get("start_time")),
            "end_time_disp": to_12h(event_data.get("end_time")),
            "location": event_data.get("location"),
            "description": event_data.get("description"),
            "source_type": "Website",
            "source": site_key,
            "url": event_url,
            "ig_handle": f"@{ig_handle}" if ig_handle else None,
            "to_tag": "@demokratigarage" if event_data.get("_flag_duplicate") else None,
        }

        # If flagged from cross-post fallback, mark as possible duplicate
        if event_data.get("_flag_duplicate"):
            ev["possible_duplicate"] = True
            flagged_dupes += 1
        else:
            # Check for cross-platform duplicates
            dupe = find_duplicate(
                ev.get("event_name", ""),
                ev.get("start_date", ""),
                site_key,
                all_entries,
                source_mapping,
            )
            if dupe:
                ev["possible_duplicate"] = True
                flagged_dupes += 1

        # Deduplicate by URL + date + time (same page can have multiple time slots per day)
        start_time_part = ev.get("start_time_disp", "") or ""
        dedup_key = f"{event_url}##{ev.get('start_date', '')}##{start_time_part}"
        page_id = existing.get(dedup_key)
        # Also check without time for backward compat
        if not page_id:
            dedup_key_no_time = f"{event_url}##{ev.get('start_date', '')}"
            page_id = existing.get(dedup_key_no_time)

        if page_id:
            # Update existing
            resp = notion_update(page_id, ev)
            if resp.status_code == 429:
                time.sleep(1.5)
                resp = notion_update(page_id, ev)
            updated += 1
        else:
            # Create new
            resp = notion_create(ev)
            if resp.status_code == 429:
                time.sleep(1.5)
                resp = notion_create(ev)
            if resp.status_code < 400:
                try:
                    new_id = resp.json().get("id")
                    if new_id:
                        existing[dedup_key] = new_id
                        all_entries.append({
                            "page_id": new_id,
                            "name": ev.get("event_name", ""),
                            "start_date": ev.get("start_date", ""),
                            "source": site_key,
                            "url": event_url,
                        })
                except Exception:
                    pass
                created += 1
            else:
                log(f"  Create failed for {ev.get('event_name')}: {resp.status_code}")

        log(f"    → {ev.get('event_name')} | {ev.get('start_date')} | {ev.get('location')}")
        time.sleep(0.3)

    return {
        "created": created, "updated": updated, "skipped": skipped,
        "flagged_dupes": flagged_dupes, "total_events": total_events,
    }


# ────────────────── Standalone main ──────────────────

def main():
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID")

    existing, all_entries = notion_existing_entries()
    source_mapping = load_source_mapping()

    for site_key in SITE_PARSERS:
        log(f"Scraping {site_key}...")
        stats = scrape_site(site_key, existing, all_entries, source_mapping)
        log(f"  Created: {stats['created']}, Updated: {stats['updated']}")


if __name__ == "__main__":
    main()
