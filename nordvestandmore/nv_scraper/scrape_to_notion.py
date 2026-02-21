import os, re, time, sys
from urllib.parse import urljoin
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup

# --------- CONFIG VIA ENV ---------
SLUG = os.environ.get("SCRAPER_SLUG", "LYGTEN_STATION")   # used as "Source" in Notion
LIST_URL = os.environ.get("LIST_URL")                     # listing page to scrape
LOCATION_NAME = os.environ.get("LOCATION_NAME", "")       # human-readable venue

# Notion credentials (one set per SLUG)
NOTION_TOKEN = os.environ.get(f"NOTION_TOKEN_{SLUG}")
NOTION_DB = os.environ.get(f"NOTION_DATABASE_ID_{SLUG}")

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

SCRAPER_HEADERS = {"User-Agent": "NV&More scraper (contact: nordvestandmore@gmail.com)"}

# --------- Lygten Station date/time patterns (DK) ---------
MONTH_MAP = {
    "jan.": 1, "feb.": 2, "mar.": 3, "apr.": 4, "maj": 5, "jun.": 6,
    "jul.": 7, "aug.": 8, "sep.": 9, "okt.": 10, "nov.": 11, "dec.": 12
}

# Examples:
# "Ons. 08. okt. 2025 Kl. 19 - 21"
# "Tor. 09. okt. 2025 Kl. 19.30 - 21.15"
DATE_RE = re.compile(
    r"(Man\.|Tir\.|Ons\.|Tor\.|Fre\.|Lør\.|Søn\.)\s+(\d{2})\.\s+([a-zæøå\.]+)\s+(\d{4})\s+Kl\.\s+"
    r"(\d{1,2})(?:\.(\d{2}))?\s*-\s*(\d{1,2})(?:\.(\d{2}))?",
    re.IGNORECASE
)

def get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=SCRAPER_HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def parse_listing(url: str):
    """Return list of (visible_text, absolute_url) rows from a listing page."""
    soup = get_soup(url)
    main = soup.find("main") or soup
    rows = []
    for a in main.find_all("a", href=True):
        text = " ".join(a.get_text(strip=True).split())
        # crude heuristic: row contains weekday + 'Kl.'
        if any(w in text for w in ["Man.","Tir.","Ons.","Tor.","Fre.","Lør.","Søn."]) and "Kl." in text:
            rows.append((text, urljoin(url, a["href"])))
    # de-dupe by URL
    seen, out = set(), []
    for t, h in rows:
        if h not in seen:
            seen.add(h)
            out.append((t, h))
    return out

def split_title_and_datetime(line_text: str):
    m = DATE_RE.search(line_text)
    if not m:
        return line_text, None
    return line_text[:m.start()].strip(), m.group(0)

def to_12h(hh, mm):
    hh = int(hh)
    mm = int(mm) if mm else 0
    suffix = "am" if hh < 12 else "pm"
    h12 = hh % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{mm:02d}{suffix}"

def parse_dt(dt_str: str):
    m = DATE_RE.search(dt_str or "")
    if not m:
        return None
    _, day, mon_txt, year, sh, sm, eh, em = m.groups()
    d = int(day); y = int(year)
    mnum = MONTH_MAP.get(mon_txt.lower())
    if not mnum:
        return None
    start_date = date(y, mnum, d).isoformat()
    end_date = start_date
    return {
        "start_date": start_date,
        "end_date": end_date,
        "start_time_disp": to_12h(sh, sm or "00"),
        "end_time_disp": to_12h(eh, em or "00"),
        "start_iso": datetime(y, mnum, d, int(sh), int(sm or 0)).isoformat(),
        "end_iso":   datetime(y, mnum, d, int(eh), int(em or 0)).isoformat(),
    }

# --------- Notion helpers ---------
def notion_existing_urls():
    """Return {url: page_id} for all rows in the DB. Robust to pagination."""
    url_to_page = {}
    payload = {"page_size": 100}
    pages_seen = 0
    max_pages = 100  # safety

    while True:
        r = requests.post(
            f"{NOTION_API}/databases/{NOTION_DB}/query",
            headers=NOTION_HEADERS,
            json=payload,
            timeout=30
        )
        r.raise_for_status()
        data = r.json()

        for page in data.get("results", []):
            props = page.get("properties", {})
            url_prop = props.get("URL", {})
            url_val = url_prop.get("url")
            if url_val:
                url_to_page[url_val] = page["id"]

        pages_seen += 1
        if os.environ.get("DEBUG"):
            print(f"[{SLUG}] Preload page {pages_seen}, total URLs: {len(url_to_page)}")

        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break
        payload["start_cursor"] = next_cursor
        if pages_seen >= max_pages:
            if os.environ.get("DEBUG"):
                print(f"[{SLUG}] Stopping preload after {max_pages} pages (safety).")
            break
    return url_to_page

def build_props(ev: dict):
    props = {}
    # Required
    props["Name"] = {"title": [{"text": {"content": ev["title"]}}]}

    # Optional – only include when present
    if ev.get("url"):
        props["URL"] = {"url": ev["url"]}
    if ev.get("start_date"):
        props["Start Date"] = {"date": {"start": ev["start_date"]}}
    if ev.get("end_date"):
        props["End Date"] = {"date": {"start": ev["end_date"]}}
    if ev.get("start_time_disp"):
        props["Start Time"] = {"rich_text": [{"text": {"content": ev["start_time_disp"]}}]}
    if ev.get("end_time_disp"):
        props["End Time"] = {"rich_text": [{"text": {"content": ev["end_time_disp"]}}]}

    if ev.get("location"):
        props["Location"] = {"rich_text": [{"text": {"content": ev["location"]}}]}
    if ev.get("source"):
        props["Source"] = {"rich_text": [{"text": {"content": ev["source"]}}]}
    if ev.get("raw_line"):
        props["Raw Line"] = {"rich_text": [{"text": {"content": ev["raw_line"]}}]}

    return props

def notion_create(ev: dict):
    payload = {"parent": {"database_id": NOTION_DB}, "properties": build_props(ev)}
    r = requests.post(f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=30)
    if r.status_code >= 400:
        try:
            print("CREATE ERROR:", r.status_code, r.json())
        except Exception:
            print("CREATE ERROR RAW:", r.status_code, r.text[:500])
    return r

def notion_update(page_id: str, ev: dict):
    payload = {"properties": build_props(ev)}
    r = requests.patch(f"{NOTION_API}/pages/{page_id}", headers=NOTION_HEADERS, json=payload, timeout=30)
    if r.status_code >= 400:
        try:
            print("UPDATE ERROR:", r.status_code, r.json())
        except Exception:
            print("UPDATE ERROR RAW:", r.status_code, r.text[:500])
    return r

# --- Title cleanup (handles glued words like "UdsolgtLygten") ---
TITLE_STRIP_PATTERNS = [
    r"udsolgt",                 # "Udsolgt"
    r"næste\s*gang",            # "Næste gang"
    r"lygten\s*station",        # "Lygten Station"
    r"få\s*billetter",          # "Få billetter"
]
SEPARATOR_EDGES = r"\s*[-–—|:]\s*"

def clean_title(raw: str) -> str:
    title = raw or ""

    # 1) Remove noisy tokens anywhere, even if glued (case-insensitive)
    for pat in TITLE_STRIP_PATTERNS:
        title = re.sub(pat, " ", title, flags=re.IGNORECASE)

    # 2) If venue token appears at the start after cleanup, strip it again
    title = re.sub(r"^\s*lygten\s*station\s*", " ", title, flags=re.IGNORECASE)

    # 3) Normalize separators and spaces
    title = re.sub(r"\s{2,}", " ", title).strip()
    title = re.sub(rf"^{SEPARATOR_EDGES}", "", title)   # leading sep
    title = re.sub(rf"{SEPARATOR_EDGES}$", "", title)   # trailing sep
    title = re.sub(r"\s*([-–—|:])\s*", r" \1 ", title)  # uniform spacing
    title = re.sub(r"\s{2,}", " ", title).strip()

    return title or (raw or "").strip()

# --------- Main ---------
def main():
    if not LIST_URL:
        sys.exit("LIST_URL not set")
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit(f"Missing NOTION_TOKEN_{SLUG} or NOTION_DATABASE_ID_{SLUG}")

    # Preload existing URL -> page_id map to avoid per-row queries
    existing = notion_existing_urls()

    items = parse_listing(LIST_URL)
    print(f"[{SLUG}] Found {len(items)} event rows")
    created, updated, skipped = 0, 0, 0

    for text, href in items:
        # Split visible line into title and datetime part
        title_raw, dt_raw = split_title_and_datetime(text)

        # Remove common noise then clean venue/status words
        title_raw = title_raw.replace("Få billetter", "").strip()
        title = clean_title(title_raw)

        # Parse dates/times (kept as display strings + ISO for future if needed)
        parsed = parse_dt(dt_raw) if dt_raw else None

        # Build event dict
        ev = {
            "title": title,
            "url": href,
            "raw_line": text,
            "location": LOCATION_NAME,
            "source": SLUG,
        }
        if parsed:
            ev.update(parsed)

        page_id = existing.get(href)

        if page_id:
            # Update existing record (or switch to "skip" if you prefer)
            r = notion_update(page_id, ev)
            if r.status_code == 429:
                time.sleep(1.5); r = notion_update(page_id, ev)
            r.raise_for_status()
            updated += 1
        else:
            # Create new record
            r = notion_create(ev)
            if r.status_code == 429:
                time.sleep(1.5); r = notion_create(ev)
            r.raise_for_status()
            created += 1
            # remember it this run to prevent double-creates
            try:
                new_id = r.json().get("id")
                if new_id:
                    existing[href] = new_id
            except Exception:
                pass

        time.sleep(0.2)  # be nice to rate limits

    print(f"[{SLUG}] ✅ Created {created}, Updated {updated}, Skipped {skipped}")

if __name__ == "__main__":
    main()
