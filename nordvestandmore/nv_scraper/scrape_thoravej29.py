#!/usr/bin/env python3
import os, re, time, sys, hashlib
from urllib.parse import urljoin, urlparse, urlunparse
from datetime import date
import requests
from bs4 import BeautifulSoup

# ----------------- ENV / CONFIG -----------------
SLUG = os.environ.get("SCRAPER_SLUG", "THORAVEJ29")
LIST_URL = os.environ.get("LIST_URL")  # e.g. https://www.thoravej29.dk/en/events
LOCATION_NAME = os.environ.get("LOCATION_NAME", "Thoravej 29")
DEBUG = bool(os.environ.get("DEBUG"))

NOTION_TOKEN = os.environ.get(f"NOTION_TOKEN_{SLUG}")
NOTION_DB    = os.environ.get(f"NOTION_DATABASE_ID_{SLUG}")

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
SCRAPER_HEADERS = {"User-Agent": "NV&More scraper (contact: nordvestandmore@gmail.com)"}

# ----------------- UTIL -----------------
def absolute(base, href): return urljoin(base, href)

def get(url):
    if DEBUG: print(f"[{SLUG}] fetch {url}")
    r = requests.get(url, headers=SCRAPER_HEADERS, timeout=30)
    r.raise_for_status()
    return r

def get_soup(url: str) -> BeautifulSoup:
    r = get(url)
    return BeautifulSoup(r.text, "html.parser")

def clean_spaces(s: str) -> str:
    return " ".join((s or "").replace("\xa0", " ").split())

def slugify(s: str) -> str:
    s2 = re.sub(r"\s+", "-", s.strip().lower())
    s2 = re.sub(r"[^a-z0-9\-]", "", s2)
    return s2[:60] or hashlib.md5(s.encode("utf-8")).hexdigest()[:12]

# ----------------- DATE/TIME PARSING -----------------
MONTH_EN = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
MONTH_DA = {"jan":1,"feb":2,"mar":3,"apr":4,"maj":5,"jun":6,"jul":7,"aug":8,"sep":9,"okt":10,"nov":11,"dec":12}

TIME_RANGE_RE  = re.compile(r"\b(\d{1,2})(?:[:\.](\d{2}))?\s*[-–]\s*(\d{1,2})(?:[:\.](\d{2}))?\b")
TIME_SINGLE_RE = re.compile(r"\b(\d{1,2})(?:[:\.](\d{2}))\b")
YEAR_RE        = re.compile(r"\b(20\d{2})\b")

def to_12h(hh, mm="00"):
    hh = int(hh); mm = int(mm) if mm else 0
    suffix = "am" if hh < 12 else "pm"
    h12 = hh % 12
    if h12 == 0: h12 = 12
    return f"{h12}:{mm:02d}{suffix}"

def parse_date_str_any(s: str) -> str|None:
    if not s: return None
    t = s.lower()
    m = re.search(r"\b(\d{1,2})[\.]?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[,\s]+(20\d{2})", t)
    if m:
        d, mon, y = int(m.group(1)), m.group(2)[:3], int(m.group(3))
        return date(y, MONTH_EN[mon], d).isoformat()
    m = re.search(r"\b(\d{1,2})[\.]?\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)[a-z\.]*\s+(20\d{2})", t)
    if m:
        d, mon, y = int(m.group(1)), m.group(2)[:3], int(m.group(3))
        return date(y, MONTH_DA[mon], d).isoformat()
    return None

# ----------------- DETAIL PARSER -----------------
def parse_event_detail(detail_url: str) -> dict:
    soup = get_soup(detail_url)

    # Title
    title_el = soup.find(["h1","h2"])
    title = clean_spaces(title_el.get_text()) if title_el else "Event"

    # Raw text (clipped for Notion)
    text_chunks = []
    for sel in ["header","main",".wp-block-group",".event",".content",".entry-content"]:
        for node in soup.select(sel):
            text_chunks.append(node.get_text(" ", strip=True))
    raw_line = clean_spaces(" | ".join(text_chunks))[:1900]

    header_txt = clean_spaces((soup.find("header") or soup).get_text(" ", strip=True))
    date_str = parse_date_str_any(header_txt) or parse_date_str_any(raw_line)

    # Time range or single time
    mtime = TIME_RANGE_RE.search(header_txt) or TIME_RANGE_RE.search(raw_line)
    if mtime:
        sh, sm, eh, em = mtime.groups()
        start_disp = to_12h(sh, sm or "00")
        end_disp   = to_12h(eh, em or "00")
    else:
        m2 = TIME_SINGLE_RE.search(header_txt) or TIME_SINGLE_RE.search(raw_line)
        start_disp = to_12h(m2.group(1), m2.group(2)) if m2 else None
        end_disp   = None

    # If date missing, try infer from visible year + day+month mention
    if not date_str:
        y = YEAR_RE.search(raw_line)
        if y:
            dm = re.search(r"\b(\d{1,2})[\.]?\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z\.]*", raw_line.lower())
            if dm:
                d = int(dm.group(1))
                mon = dm.group(2)[:3]
                mon_map = MONTH_DA if mon in MONTH_DA else MONTH_EN
                date_str = date(int(y.group(1)), mon_map[mon], d).isoformat()

    return {
        "title": title,
        "raw_line": raw_line,
        "start_date": date_str,
        "end_date": date_str,
        "start_time_disp": start_disp,
        "end_time_disp": end_disp,
    }

# ----------------- LIST DISCOVERY -----------------
EVENT_REL_RE = re.compile(r'(?P<rel>/(?:en|da)/event/[a-z0-9\-\_\/]*)', re.IGNORECASE)
EVENT_ABS_RE = re.compile(r'https?://[^"\']+/(?:en|da)/event/[a-z0-9\-\_\/]*', re.IGNORECASE)
EVENT_HREF_RE = re.compile(r"/(en|da)?/event/")

def extract_event_links_from_html(html: str, base_url: str) -> list[str]:
    """Find event URLs inside the raw HTML (including scripts)."""
    links = set()
    for m in EVENT_ABS_RE.finditer(html):
        links.add(m.group(0))
    for m in EVENT_REL_RE.finditer(html):
        links.add(urljoin(base_url, m.group("rel")))
    return list(links)

def discover_from_listing(list_url: str) -> list[str]:
    """Combine anchors + HTML regex + simple pagination for EN & DK."""
    seeds = [list_url]
    dk = list_url.replace("/en/events", "/events")
    if dk != list_url:
        seeds.append(dk)

    bases = list(seeds)
    # query pagination ?page=N
    for base in list(bases):
        for p in range(2, 8):
            seeds.append(f"{base}?page={p}")
    # path pagination /page/N/ (ignore 404s)
    for base in list(bases):
        for p in range(2, 8):
            seeds.append(base.rstrip("/") + f"/page/{p}/")

    anchor_found = 0
    regex_found  = 0

    links, seen = [], set()
    for u in seeds:
        try:
            r = get(u)
            html = r.text
            soup = BeautifulSoup(html, "html.parser")

            # 1) Anchors
            anchors = soup.find_all("a", href=True)
            anchor_found += len(anchors)
            for a in anchors:
                href = a["href"]
                if EVENT_HREF_RE.search(href):
                    absu = urljoin(u, href)
                    if absu not in seen:
                        seen.add(absu); links.append(absu)

            # 2) Regex across full HTML (catches links inside <script> JSON)
            regex_links = extract_event_links_from_html(html, u)
            regex_found += len(regex_links)
            for absu in regex_links:
                if EVENT_HREF_RE.search(absu) and absu not in seen:
                    seen.add(absu); links.append(absu)

        except requests.HTTPError as e:
            # ignore 404s from pagination
            if DEBUG: print(f"[{SLUG}] listing fetch fail {u}: {e}")
        except Exception as e:
            if DEBUG: print(f"[{SLUG}] listing parse fail {u}: {e}")

    if DEBUG:
        print(f"[{SLUG}] listing anchors seen: {anchor_found}")
        print(f"[{SLUG}] regex link hits: {regex_found}")
        print(f"[{SLUG}] collected event links: {len(links)}")

    return links

def collect_event_links(list_url: str) -> list[str]:
    links = discover_from_listing(list_url)
    # de-dupe & keep order
    seen, uniq = set(), []
    for u in links:
        if u not in seen:
            seen.add(u); uniq.append(u)
    return uniq

# ----------------- NOTION HELPERS -----------------
def notion_existing_urls():
    url_to_page = {}
    payload = {"page_size": 100}
    while True:
        r = requests.post(f"{NOTION_API}/databases/{NOTION_DB}/query",
                          headers=NOTION_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            url_val = (props.get("Event Link") or {}).get("url")
            if url_val: url_to_page[url_val] = page["id"]
        if not data.get("has_more"): break
        payload["start_cursor"] = data.get("next_cursor")
        if not payload["start_cursor"]: break
    if DEBUG: print(f"[{SLUG}] preload URLs: {len(url_to_page)}")
    return url_to_page

def build_props(ev: dict):
    props = {"Event Name": {"title":[{"text":{"content": ev.get("title") or "Event"}}]}}
    if ev.get("url"): props["Event Link"] = {"url": ev["url"]}
    if ev.get("start_date"): props["Start Date"] = {"date":{"start": ev["start_date"]}}
    if ev.get("end_date"):   props["End Date"]   = {"date":{"start": ev["end_date"]}}
    if ev.get("start_time_disp"): props["Start Time"] = {"rich_text":[{"text":{"content": ev["start_time_disp"]}}]}
    if ev.get("end_time_disp"):   props["End Time"]   = {"rich_text":[{"text":{"content": ev["end_time_disp"]}}]}
    if ev.get("location"):  props["Location"] = {"rich_text":[{"text":{"content": ev["location"]}}]}
    if ev.get("source"):    props["Source"]   = {"rich_text":[{"text":{"content": ev["source"]}}]}
    if ev.get("raw_line"):  props["Raw Line"] = {"rich_text":[{"text":{"content": ev["raw_line"][:1900]}}]}
    return props

def notion_create(ev: dict):
    payload = {"parent":{"database_id": NOTION_DB}, "properties": build_props(ev)}
    r = requests.post(f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=30)
    if r.status_code >= 400:
        try: print("CREATE ERROR:", r.status_code, r.json())
        except: print("CREATE ERROR RAW:", r.status_code, r.text[:400])
    return r

def notion_update(page_id: str, ev: dict):
    payload = {"properties": build_props(ev)}
    r = requests.patch(f"{NOTION_API}/pages/{page_id}", headers=NOTION_HEADERS, json=payload, timeout=30)
    if r.status_code >= 400:
        try: print("UPDATE ERROR:", r.status_code, r.json())
        except: print("UPDATE ERROR RAW:", r.status_code, r.text[:400])
    return r

# ----------------- MAIN -----------------
def main():
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit(f"Missing NOTION_TOKEN_{SLUG} or NOTION_DATABASE_ID_{SLUG}")
    if not LIST_URL:
        sys.exit("LIST_URL not set")
    if DEBUG: print(f"[{SLUG}] LIST_URL={LIST_URL} LOCATION={LOCATION_NAME}")

    event_links = collect_event_links(LIST_URL)
    print(f"[{SLUG}] Collected {len(event_links)} event URLs")

    existing = notion_existing_urls()
    created = updated = skipped = 0

    for href in event_links:
        try:
            detail = parse_event_detail(href)
        except Exception as e:
            if DEBUG: print(f"[{SLUG}] detail parse failed {href}: {e}")
            continue

        ev = {
            "title": detail.get("title"),
            "url": href,
            "raw_line": detail.get("raw_line"),
            "location": LOCATION_NAME,
            "source": SLUG,
            "start_date": detail.get("start_date"),
            "end_date":   detail.get("end_date") or detail.get("start_date"),
            "start_time_disp": detail.get("start_time_disp"),
            "end_time_disp":   detail.get("end_time_disp"),
        }

        page_id = existing.get(href)
        if page_id:
            r = notion_update(page_id, ev)
            if r.status_code == 429: time.sleep(1.5); r = notion_update(page_id, ev)
            try: r.raise_for_status(); updated += 1
            except Exception as e:
                if DEBUG: print(f"[{SLUG}] update failed for {href}: {e}")
        else:
            r = notion_create(ev)
            if r.status_code == 429: time.sleep(1.5); r = notion_create(ev)
            try:
                r.raise_for_status(); created += 1
                nid = r.json().get("id")
                if nid: existing[href] = nid
            except Exception as e:
                if DEBUG: print(f"[{SLUG}] create failed for {href}: {e}")

        time.sleep(0.25)

    print(f"[{SLUG}] ✅ Created {created}, Updated {updated}, Skipped {skipped}")

if __name__ == "__main__":
    main()
