#!/usr/bin/env python3
import os, re, time, sys, hashlib
from urllib.parse import urljoin, urlparse
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup

# -------------------- CONFIG (via env) --------------------
SLUG = os.environ.get("SCRAPER_SLUG", "VIERRUMMET")
LIST_URL = os.environ.get("LIST_URL")  # e.g. https://www.vierrummet.dk/
LOCATION_NAME = os.environ.get("LOCATION_NAME", "Vier Rummet")

NOTION_TOKEN = os.environ.get(f"NOTION_TOKEN_{SLUG}")
NOTION_DB    = os.environ.get(f"NOTION_DATABASE_ID_{SLUG}")

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

SCRAPER_HEADERS = {
    "User-Agent": "NV&More scraper (contact: nordvestandmore@gmail.com)"
}

DEBUG = bool(os.environ.get("DEBUG"))

# -------------------- helpers --------------------
def log(*a):
    if DEBUG: print(f"[{SLUG}]", *a)

def soup_of(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=SCRAPER_HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def abs_url(base: str, href: str) -> str:
    return urljoin(base, href)

def same_host(u: str, host: str) -> bool:
    return urlparse(u).netloc == host

def slugify(s: str) -> str:
    s0 = re.sub(r"\s+", "-", (s or "").strip().lower())
    s0 = re.sub(r"[^a-z0-9\-]", "", s0)
    return s0[:60] or hashlib.md5((s or "").encode("utf-8")).hexdigest()[:12]

# -------------------- date/time parsing --------------------
MONTHS = {
    # Danish (short)
    "jan":1,"feb":2,"mar":3,"apr":4,"maj":5,"jun":6,"jul":7,"aug":8,"sep":9,"okt":10,"nov":11,"dec":12,
    "jan.":1,"feb.":2,"mar.":3,"apr.":4,"jun.":6,"jul.":7,"aug.":8,"sep.":9,"okt.":10,"nov.":11,"dec.":12,
    # English short (just in case)
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
    "oct.":10,"may.":5,
}

DAY_NAMES = r"(man|tir|ons|tor|fre|lør|søn|mandag|tirsdag|onsdag|torsdag|fredag|lørdag|søndag|sun|mon|tue|wed|thu|fri|sat)\.?,?"

TIME_RANGE_RE = re.compile(r"(\d{1,2})(?:[:\.](\d{2}))?\s*[-–]\s*(\d{1,2})(?:[:\.](\d{2}))?", re.I)
TIME_SINGLE_RE = re.compile(r"\bkl\.?\s*(\d{1,2})(?:[:\.](\d{2}))?\b", re.I)

def to_12h(hh, mm):
    hh = int(hh); mm = int(mm) if mm else 0
    suffix = "am" if hh < 12 else "pm"
    h12 = hh % 12
    if h12 == 0: h12 = 12
    return f"{h12}:{mm:02d}{suffix}"

def _dk_date_to_iso(day:int, mon_word:str, year:int) -> str|None:
    m = MONTHS.get(mon_word.strip(".").lower())
    if not m: 
        return None
    return date(year, m, day).isoformat()

def parse_date_str_any(line: str) -> str|None:
    """
    Handles patterns like:
      'Tirsdag 7. oktober 2025, kl. 17:00 - 18:00'
      'Ons 08. okt. 2025 kl. 19 - 21'
      '7. okt 2025'
    """
    if not line:
        return None
    # 7. okt. 2025
    m = re.search(r"(\d{1,2})\.\s*([a-zæøå\.]+)\s*(\d{4})", line, re.I)
    if m:
        d, monw, y = m.groups()
        return _dk_date_to_iso(int(d), monw, int(y))
    # 07/10/2025
    m = re.search(r"\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b", line)
    if m:
        d, mth, y = m.groups()
        y = int(y);  y = (2000+y) if y < 100 else y
        return date(y, int(mth), int(d)).isoformat()
    return None

def parse_times_any(text: str) -> tuple[str|None, str|None]:
    """Return display start/end like '5:30pm' from 'kl. 17:30 - 19' etc."""
    if not text: 
        return None, None
    m = TIME_RANGE_RE.search(text)
    if m:
        sh, sm, eh, em = m.groups()
        return to_12h(sh, sm or "00"), to_12h(eh, em or "00")
    m = TIME_SINGLE_RE.search(text)
    if m:
        sh, sm = m.groups()
        return to_12h(sh, sm or "00"), None
    return None, None

# -------------------- Notion helpers --------------------
def notion_existing_urls() -> dict:
    """Map of URL -> page_id for the whole DB (handles pagination)."""
    url_to_page, payload = {}, {"page_size": 100}
    while True:
        r = requests.post(f"{NOTION_API}/databases/{NOTION_DB}/query",
                          headers=NOTION_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            url_val = props.get("Event Link", {}).get("url")
            if url_val:
                url_to_page[url_val] = page["id"]
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
    log("preload URLs:", len(url_to_page))
    return url_to_page

def build_props(ev: dict, is_update: bool = False) -> dict:
    props = {
        "Event Name": {"title":[{"text":{"content": ev["title"]}}]},
    }
    if ev.get("url"):         props["Event Link"]  = {"url": ev["url"]}
    if ev.get("start_date"):  props["Start Date"] = {"date":{"start": ev["start_date"]}}
    if ev.get("end_date"):    props["End Date"]   = {"date":{"start": ev["end_date"]}}
    if ev.get("start_time_disp"): props["Start Time"] = {"rich_text":[{"text":{"content": ev["start_time_disp"]}}]}
    if ev.get("end_time_disp"):   props["End Time"]   = {"rich_text":[{"text":{"content": ev["end_time_disp"]}}]}
    # Location — only set on create, preserve manual edits on update
    if ev.get("location") and not is_update:
        props["Location"]   = {"rich_text":[{"text":{"content": ev["location"]}}]}
    if ev.get("source"):      props["Source"]     = {"rich_text":[{"text":{"content": ev["source"]}}]}
    if ev.get("raw_line") and not is_update:
        raw = ev["raw_line"]
        if len(raw) > 1900: raw = raw[:1900]  # stay < Notion 2000 limit
        props["Raw Line"] = {"rich_text":[{"text":{"content": raw}}]}
    return props

def notion_create(ev: dict):
    payload = {"parent":{"database_id": NOTION_DB}, "properties": build_props(ev)}
    r = requests.post(f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=30)
    if r.status_code >= 400:
        try: print("CREATE ERROR:", r.status_code, r.json())
        except: print("CREATE ERROR RAW:", r.status_code, r.text[:500])
    return r

def notion_update(page_id: str, ev: dict):
    payload = {"properties": build_props(ev, is_update=True)}
    r = requests.patch(f"{NOTION_API}/pages/{page_id}", headers=NOTION_HEADERS, json=payload, timeout=30)
    if r.status_code >= 400:
        try: print("UPDATE ERROR:", r.status_code, r.json())
        except: print("UPDATE ERROR RAW:", r.status_code, r.text[:500])
    return r

# -------------------- collector (pagination) --------------------
def collect_event_links(list_url: str) -> list[str]:
    """
    Walks the Vier Rummet calendar, following the Next/Næste (›) pagination.
    Returns a de-duped list of event detail URLs (or synthetic links when needed).
    """
    host = urlparse(list_url).netloc
    seen_pages = set()
    found_links = []
    page_url = list_url
    max_pages = 50

    def smells_like_event(href: str, text: str) -> bool:
        href = (href or "").lower()
        text = (text or "").lower()
        return (
            "/event" in href or "/arrangement" in href or "eventid=" in href or
            bool(re.search(r"\b(kl\.|\d{1,2}[:\.]\d{2})\b", text))
        )

    for _ in range(max_pages):
        if not page_url or page_url in seen_pages:
            break
        seen_pages.add(page_url)

        s = soup_of(page_url)
        anchors = s.find_all("a", href=True)
        log("listing", page_url, "anchors:", len(anchors))

        # collect event links
        page_links = []
        for a in anchors:
            href = abs_url(page_url, a["href"])
            if not same_host(href, host): 
                continue
            txt = a.get_text(" ", strip=True)
            if smells_like_event(href, txt):
                page_links.append(href)
        # unique per page
        uniq, seen = [], set()
        for h in page_links:
            if h not in seen:
                seen.add(h); uniq.append(h)
        found_links.extend(uniq)

        # find "next" arrow
        next_href = None
        a_next = s.find("a", attrs={"rel": "next"})
        if a_next and a_next.get("href"):
            next_href = abs_url(page_url, a_next["href"])
        if not next_href:
            for a in anchors:
                t = (a.get_text(" ", strip=True) or "").strip().lower()
                aria = (a.get("aria-label") or "").lower()
                if t in ("næste","next","›",">", ">>") or "næste" in aria or "next" in aria:
                    next_href = abs_url(page_url, a["href"])
                    break

        if not next_href or next_href == page_url:
            break
        page_url = next_href

    # global de-dupe
    out, seen_all = [], set()
    for h in found_links:
        if h not in seen_all:
            seen_all.add(h); out.append(h)

    log("collected links total:", len(out))
    return out

# -------------------- detail parser (generic) --------------------
def parse_event_detail(url: str) -> dict:
    """
    Generic event page parser (works for ChurchDesk-like pages and simple CMS).
    """
    s = soup_of(url)
    title = ""
    h = s.find(["h1","h2"])
    if h: title = " ".join(h.get_text(" ", strip=True).split())
    if not title:
        # fallback to first strong text
        b = s.find(["strong","b"])
        if b: title = " ".join(b.get_text(" ", strip=True).split())
    if not title:
        title = url  # ultimate fallback

    # pick a short date/time snippet
    text = " ".join(s.get_text(" ", strip=True).split())
    dt_snippet = None
    # favor lines that contain a month and "kl."
    for frag in re.split(r"[|•\n–—-]+", text):
        if re.search(r"\b(kl\.|\d{1,2}[:\.]\d{2})\b", frag, re.I) and re.search(r"\d{1,2}\.\s*[a-zæøå]", frag, re.I):
            dt_snippet = frag.strip()
            break
    if not dt_snippet:
        # just take something with time
        m = re.search(r"[^.]*\bkl\.?\s*\d{1,2}[:\.]?\d{0,2}[^.]*", text, re.I)
        if m: dt_snippet = m.group(0)

    start_date = parse_date_str_any(dt_snippet or text)
    sdisp, edisp = parse_times_any(dt_snippet or text)
    return {
        "title": title,
        "start_date": start_date,
        "end_date": start_date,
        "start_time_disp": sdisp,
        "end_time_disp": edisp,
        "raw_line": (dt_snippet or text)[:1900],
    }

# -------------------- MAIN --------------------
def main():
    if not LIST_URL:      sys.exit("LIST_URL not set")
    if not NOTION_TOKEN or not NOTION_DB:
        sys.exit(f"Missing NOTION_TOKEN_{SLUG} or NOTION_DATABASE_ID_{SLUG}")

    print(f"[{SLUG}] LIST_URL={LIST_URL} LOCATION={LOCATION_NAME}")

    links = collect_event_links(LIST_URL)
    print(f"[{SLUG}] Collected {len(links)} event URLs")

    existing = notion_existing_urls()
    created = updated = skipped = 0

    for href in links:
        try:
            detail = parse_event_detail(href)
        except Exception as e:
            log("detail fail", href, e)
            continue

        ev = {
            "title": detail["title"],
            "url": href,
            "raw_line": detail.get("raw_line",""),
            "location": LOCATION_NAME,
            "source": SLUG,
            "start_date": detail.get("start_date"),
            "end_date": detail.get("end_date"),
            "start_time_disp": detail.get("start_time_disp"),
            "end_time_disp": detail.get("end_time_disp"),
        }

        page_id = existing.get(href)
        if page_id:
            r = notion_update(page_id, ev)
            if r.status_code == 429:
                time.sleep(1.5); r = notion_update(page_id, ev)
            try:
                r.raise_for_status(); updated += 1
            except:
                log("update failed", href)
        else:
            r = notion_create(ev)
            if r.status_code == 429:
                time.sleep(1.5); r = notion_create(ev)
            try:
                r.raise_for_status(); created += 1
                nid = r.json().get("id")
                if nid: existing[href] = nid
            except:
                log("create failed", href)

        time.sleep(0.25)

    print(f"[{SLUG}] ✅ Created {created}, Updated {updated}, Skipped {skipped}")

if __name__ == "__main__":
    main()
