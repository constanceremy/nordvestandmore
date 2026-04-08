"""
locations_cache.py — Fetches all locations from the Notion Locations DB once per
scrape run and provides fuzzy name matching: location text → Notion page ID.

Usage:
    from locations_cache import find_location_id
    location_id = find_location_id("Ungdomshuset, Dortheavej 61, 2400 NV", NOTION_TOKEN)
    # Returns Notion page ID string, or None if no match.
"""
import os
import re
import requests

NOTION_API = "https://api.notion.com/v1"
LOCATIONS_DB = os.environ.get("NOTION_LOCATIONS_DB_ID", "33c375efa2cc8036b52bc40db2aa42fb")

_cache: dict[str, str] | None = None  # normalized_name → page_id


def _normalize(text: str) -> str:
    """Lowercase, remove punctuation/special chars, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load(notion_token: str) -> dict[str, str]:
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

    lookup: dict[str, str] = {}
    for page in results:
        props = page.get("properties", {})
        title_parts = props.get("Name", {}).get("title", [])
        name = "".join(t.get("plain_text", "") for t in title_parts).strip()
        if name:
            lookup[_normalize(name)] = page["id"]
    return lookup


def get_cache(notion_token: str) -> dict[str, str]:
    """Load locations cache lazily (once per process)."""
    global _cache
    if _cache is None:
        try:
            _cache = _load(notion_token)
        except Exception as e:
            print(f"[locations_cache] Failed to load: {e}")
            _cache = {}
    return _cache


def find_location_id(location_text: str, notion_token: str) -> str | None:
    """
    Try to match a location string to a Locations DB entry.
    Strategy:
      1. Exact normalized match
      2. DB name appears as a substring of the event location text
    Returns Notion page ID or None.
    """
    if not location_text or not notion_token:
        return None

    cache = get_cache(notion_token)
    if not cache:
        return None

    normalized = _normalize(location_text)

    # 1. Exact match
    if normalized in cache:
        return cache[normalized]

    # 2. Any DB location name contained within the event location text
    #    (e.g. "ungdomshuset" in "ungdomshuset dortheavej 61 2400 københavn nv")
    #    Sort by length descending so longer/more specific names match first
    for db_name in sorted(cache.keys(), key=len, reverse=True):
        if db_name and db_name in normalized:
            return cache[db_name]

    return None
