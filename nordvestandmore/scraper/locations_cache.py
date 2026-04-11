"""
locations_cache.py — Fetches all locations from the Notion Locations DB once per
scrape run and provides fuzzy name matching: location text → Notion page ID or coords.

Usage:
    from locations_cache import find_location_id, find_location_coords
    location_id = find_location_id("Ungdomshuset, Dortheavej 61, 2400 NV", NOTION_TOKEN)
    coords = find_location_coords("Thoras", NOTION_TOKEN)  # → (55.69, 12.52)
"""
import os
import re
import requests

NOTION_API = "https://api.notion.com/v1"
LOCATIONS_DB = os.environ.get("NOTION_LOCATIONS_DB_ID", "33c375efa2cc8036b52bc40db2aa42fb")

# normalized_name → {"id": page_id, "lat": float|None, "lng": float|None}
_cache: dict[str, dict] | None = None


def _normalize(text: str) -> str:
    """Lowercase, remove punctuation/special chars, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load(notion_token: str) -> dict[str, dict]:
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

    lookup: dict[str, dict] = {}
    for page in results:
        props = page.get("properties", {})
        title_parts = props.get("Name", {}).get("title", [])
        name = "".join(t.get("plain_text", "") for t in title_parts).strip()
        if not name:
            continue
        lat_raw = props.get("Lat", {}).get("number")
        lng_raw = props.get("Lng", {}).get("number")
        lookup[_normalize(name)] = {
            "id": page["id"],
            "lat": float(lat_raw) if lat_raw is not None else None,
            "lng": float(lng_raw) if lng_raw is not None else None,
        }
    return lookup


def get_cache(notion_token: str) -> dict[str, dict]:
    """Load locations cache lazily (once per process)."""
    global _cache
    if _cache is None:
        try:
            _cache = _load(notion_token)
        except Exception as e:
            print(f"[locations_cache] Failed to load: {e}")
            _cache = {}
    return _cache


def _match_key(location_text: str, cache: dict[str, dict]) -> str | None:
    """Return the cache key that best matches location_text, or None."""
    normalized = _normalize(location_text)
    if normalized in cache:
        return normalized
    for db_name in sorted(cache.keys(), key=len, reverse=True):
        if db_name and db_name in normalized:
            return db_name
    return None


def find_location_id(location_text: str, notion_token: str) -> str | None:
    """
    Try to match a location string to a Locations DB entry.
    Returns Notion page ID or None.
    """
    if not location_text or not notion_token:
        return None
    cache = get_cache(notion_token)
    key = _match_key(location_text, cache)
    return cache[key]["id"] if key else None


def find_location_coords(location_text: str, notion_token: str) -> tuple[float, float] | None:
    """
    Try to match a location string to a Locations DB entry.
    Returns (lat, lng) tuple or None if no match or no coordinates stored.
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
