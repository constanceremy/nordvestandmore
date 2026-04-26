"""
locations_cache.py — Fetches all locations from the Notion Locations DB once per
scrape run and provides location matching: location text → Notion page ID or coords.

Matching strategy (in order):
  1. Fast string match — exact or substring on normalized name (free, instant)
  2. Gemini fallback — semantic match against full venue list (API call, cached per text)

Usage:
    from locations_cache import find_location_id, find_location_coords
    location_id = find_location_id("Ungdomshuset, Dortheavej 61, 2400 NV", NOTION_TOKEN)
    location_id = find_location_id("Frederikssundsvej 40", NOTION_TOKEN, gemini_client)
    coords = find_location_coords("Thoras", NOTION_TOKEN)  # → (55.69, 12.52)
"""
import os
import re
import requests

NOTION_API = "https://api.notion.com/v1"
LOCATIONS_DB = os.environ.get("NOTION_LOCATIONS_DB_ID", "33c375efa2cc8036b52bc40db2aa42fb")

# normalized_name → {"id": page_id, "name": original_name, "lat": float|None, "lng": float|None}
_cache: dict[str, dict] | None = None

# normalized_ig_handle → page_id
_ig_cache: dict[str, str] | None = None

# normalized_fb_id → page_id  (FB page name or numeric ID extracted from URL)
_fb_cache: dict[str, str] | None = None

# Cache Gemini answers: location_text → page_id | None
# Avoids repeated API calls for the same location string within a run.
_gemini_cache: dict[str, str | None] = {}


def _normalize(text: str) -> str:
    """Lowercase, remove punctuation/special chars, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_fb_id(url: str) -> str:
    """Extract a normalised FB identifier from a URL (page name or numeric ID)."""
    import re as _re
    m = _re.search(r"[?&]id=(\d+)", url)
    if m:
        return m.group(1)
    m = _re.search(r"facebook\.com/([^/?#]+)", url)
    if m and m.group(1) not in ("profile.php", "events", "pages"):
        return m.group(1).lower()
    return url.lower()


def _load(notion_token: str) -> tuple[dict[str, dict], dict[str, str], dict[str, str]]:
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    results = []
    cursor = None
    while True:
        payload: dict = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        resp = requests.post(
            f"{NOTION_API}/databases/{LOCATIONS_DB}/query",
            headers=headers,
            json=payload,
            timeout=30,
        )
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    name_lookup: dict[str, dict] = {}
    ig_lookup:   dict[str, str]  = {}
    fb_lookup:   dict[str, str]  = {}

    for page in results:
        props = page.get("properties", {})
        title_parts = props.get("Name", {}).get("title", [])
        name = "".join(t.get("plain_text", "") for t in title_parts).strip()
        if not name:
            continue
        page_id = page["id"]
        lat_raw = props.get("Lat", {}).get("number")
        lng_raw = props.get("Lng", {}).get("number")
        name_lookup[_normalize(name)] = {
            "id": page_id,
            "name": name,
            "lat": float(lat_raw) if lat_raw is not None else None,
            "lng": float(lng_raw) if lng_raw is not None else None,
        }

        ig_raw = "".join(t.get("plain_text", "") for t in props.get("Instagram", {}).get("rich_text", [])).strip().lstrip("@")
        if ig_raw:
            ig_lookup[ig_raw.lower()] = page_id

        fb_raw = (props.get("Facebook", {}).get("url") or "").strip()
        if fb_raw:
            fb_lookup[_extract_fb_id(fb_raw)] = page_id

    return name_lookup, ig_lookup, fb_lookup


def get_cache(notion_token: str) -> dict[str, dict]:
    """Load name cache lazily (once per process)."""
    global _cache, _ig_cache, _fb_cache
    if _cache is None:
        try:
            _cache, _ig_cache, _fb_cache = _load(notion_token)
            print(f"[locations_cache] Loaded {len(_cache)} locations ({len(_ig_cache)} IG, {len(_fb_cache)} FB)")
        except Exception as e:
            print(f"[locations_cache] Failed to load: {e}")
            _cache, _ig_cache, _fb_cache = {}, {}, {}
    return _cache


def _match_key(location_text: str, cache: dict[str, dict]) -> str | None:
    """Fast string match: exact or substring on normalized name."""
    normalized = _normalize(location_text)
    if normalized in cache:
        return normalized
    for db_name in sorted(cache.keys(), key=len, reverse=True):
        if db_name and db_name in normalized:
            return db_name
    return None


def _ask_gemini(location_text: str, cache: dict[str, dict], gemini_client) -> str | None:
    """
    Ask Gemini which venue from the Locations DB this location text refers to.
    Returns the matched page_id, or None if no clear match.
    """
    if location_text in _gemini_cache:
        return _gemini_cache[location_text]

    names = [entry["name"] for entry in cache.values()]
    if not names:
        _gemini_cache[location_text] = None
        return None

    venue_list = "\n".join(f"- {n}" for n in sorted(names))
    prompt = (
        f'The following event location was scraped: "{location_text}"\n\n'
        f"Which of the following known venues does it most likely refer to?\n"
        f"Reply with ONLY the exact venue name from the list, or 'none' if it does not clearly match any.\n\n"
        f"Venues:\n{venue_list}"
    )

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        answer = (response.text or "").strip().strip('"').strip("'")
        if answer.lower() == "none" or not answer:
            _gemini_cache[location_text] = None
            return None

        # Find the matching entry by original name
        norm_answer = _normalize(answer)
        result = cache.get(norm_answer, {}).get("id")
        if not result:
            # Fuzzy fallback in case Gemini reformatted the name slightly
            for key, entry in cache.items():
                if _normalize(entry["name"]) == norm_answer:
                    result = entry["id"]
                    break
        _gemini_cache[location_text] = result
        if result:
            matched_name = next((e["name"] for e in cache.values() if e["id"] == result), answer)
            print(f"[locations_cache] Gemini matched '{location_text}' → '{matched_name}'")
        return result
    except Exception as e:
        print(f"[locations_cache] Gemini error for '{location_text}': {e}")
        _gemini_cache[location_text] = None
        return None


def find_location_id(
    location_text: str,
    notion_token: str,
    gemini_client=None,
) -> str | None:
    """
    Match a location string to a Locations DB entry.
    1. Fast string match (exact/substring)
    2. Gemini semantic match (if gemini_client provided and fast match fails)
    Returns Notion page ID or None.
    """
    if not location_text or not notion_token:
        return None
    cache = get_cache(notion_token)
    key = _match_key(location_text, cache)
    if key:
        return cache[key]["id"]
    if gemini_client:
        return _ask_gemini(location_text, cache, gemini_client)
    return None


def find_location_id_by_ig_handle(ig_handle: str, notion_token: str) -> str | None:
    """Match an Instagram handle directly against the Locations DB Instagram field."""
    if not ig_handle or not notion_token:
        return None
    get_cache(notion_token)
    return _ig_cache.get(ig_handle.lstrip("@").lower())  # type: ignore[union-attr]


def find_location_id_by_fb(fb_url: str, notion_token: str) -> str | None:
    """Match a Facebook URL directly against the Locations DB Facebook field."""
    if not fb_url or not notion_token:
        return None
    get_cache(notion_token)
    return _fb_cache.get(_extract_fb_id(fb_url))  # type: ignore[union-attr]


def find_location_coords(location_text: str, notion_token: str) -> tuple[float, float] | None:
    """
    Match a location string to a Locations DB entry.
    Returns (lat, lng) tuple or None if no match or no coordinates stored.
    Uses fast string match only (coords are used in hot dedup loop).
    """
    if not location_text or not notion_token:
        return None
    cache = get_cache(notion_token)
    key = _match_key(location_text, cache)
    if not key:
        return None
    entry = cache[key]
    if entry["lat"] is not None and entry["lng"] is not None:
        return (entry["lat"], entry["lng"])
    return None
