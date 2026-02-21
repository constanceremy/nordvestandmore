"""
Cross-platform duplicate detection for NordVest & More scrapers.
Compares new events against existing Notion entries to flag likely duplicates.
Uses source_mapping.csv to know which IG handles and FB pages are the same venue.
"""
import csv
import os
import re
from pathlib import Path

MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_mapping.csv")

# Similarity threshold (0-1). Events above this are flagged as duplicates.
SIMILARITY_THRESHOLD = 0.70


def load_fb_to_ig_map() -> dict[str, str]:
    """
    Load source_mapping.csv and return a dict: fb_identifier → ig_handle.
    Used by the FB scraper to fill in the Instagramhandle column.
    """
    fb_to_ig: dict[str, str] = {}
    path = Path(MAPPING_FILE)
    if not path.exists():
        return fb_to_ig

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ig = (row.get("instagram") or "").strip()
            fb_raw = (row.get("facebook") or "").strip()
            if ig and fb_raw:
                fb_id = _extract_fb_id(fb_raw).lower()
                fb_to_ig[fb_id] = f"@{ig}"
    return fb_to_ig


def load_source_mapping() -> dict[str, set[str]]:
    """
    Load source_mapping.csv and build a lookup: source_id → set of all aliases.

    Each row has: name, instagram, facebook
    We group the IG handle and FB page identifier together so we can check
    if two sources refer to the same venue.

    Returns e.g.:
        {"gamma_nv": {"gamma_nv", "61556180883930"},
         "61556180883930": {"gamma_nv", "61556180883930", "gammabrewing"}, ...}
    """
    groups: dict[str, set[str]] = {}
    path = Path(MAPPING_FILE)
    if not path.exists():
        return {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ig = (row.get("instagram") or "").strip().lower()
            fb_raw = (row.get("facebook") or "").strip()

            if not ig and not fb_raw:
                continue

            # Extract FB identifier from URL
            fb_id = _extract_fb_id(fb_raw).lower() if fb_raw else ""

            identifiers = {x for x in [ig, fb_id] if x}
            if len(identifiers) < 2:
                # Only one platform — nothing to map
                for ident in identifiers:
                    groups.setdefault(ident, set()).add(ident)
                continue

            # Merge into any existing group
            merged = set(identifiers)
            for ident in identifiers:
                if ident in groups:
                    merged |= groups[ident]

            # Point all members to the same group
            for ident in merged:
                groups[ident] = merged

    return groups


def _extract_fb_id(url: str) -> str:
    """Extract a comparable identifier from a Facebook URL.
    - profile.php?id=12345... → '12345'
    - facebook.com/PageName/events → 'pagename'
    """
    # Profile ID
    id_match = re.search(r"[?&]id=(\d+)", url)
    if id_match:
        return id_match.group(1)
    # Page name
    m = re.search(r"facebook\.com/([^/?]+)", url)
    if m and m.group(1) not in ("profile.php", "events"):
        return m.group(1).lower()
    return url


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove punctuation, collapse spaces."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text)      # collapse whitespace
    return text


def similarity(a: str, b: str) -> float:
    """
    Simple word-overlap similarity (Jaccard index on words).
    Returns 0.0 to 1.0.
    """
    if not a or not b:
        return 0.0
    words_a = set(normalize_text(a).split())
    words_b = set(normalize_text(b).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _normalize_source(source: str) -> str:
    """Normalize a source identifier for lookup in the mapping."""
    source = source.strip().lower().lstrip("@")
    # If it's a FB URL, extract the identifier
    if "facebook.com" in source:
        return _extract_fb_id(source)
    return source


def are_sources_related(source_a: str, source_b: str, mapping: dict[str, set[str]]) -> bool:
    """Check if two sources (IG handle or FB page name) are the same venue/org."""
    a = _normalize_source(source_a)
    b = _normalize_source(source_b)
    if a == b:
        return True
    group = mapping.get(a)
    if group and b in group:
        return True
    return False


def find_duplicate(
    event_name: str,
    event_date: str,
    event_source: str,
    existing_entries: list[dict],
    mapping: dict[str, set[str]],
) -> dict | None:
    """
    Check if this event likely duplicates an existing Notion entry.

    Args:
        event_name: Name of the new event
        event_date: Start date (YYYY-MM-DD) of the new event
        event_source: Source identifier (IG handle or FB page name)
        existing_entries: List of dicts with keys: name, start_date, source, page_id
        mapping: Source mapping from load_source_mapping()

    Returns:
        The matching existing entry dict if a likely duplicate is found, else None.
    """
    if not event_name or not event_date:
        return None

    for entry in existing_entries:
        # Must have the same date
        if entry.get("start_date") != event_date:
            continue

        # Check if sources are related (same venue across platforms)
        if not are_sources_related(event_source, entry.get("source", ""), mapping):
            # Even if sources aren't mapped, check for very high name similarity
            name_sim = similarity(event_name, entry.get("name", ""))
            if name_sim >= 0.85:
                return entry
            continue

        # Sources are related — use lower similarity threshold
        name_sim = similarity(event_name, entry.get("name", ""))
        if name_sim >= SIMILARITY_THRESHOLD:
            return entry

    return None
