"""
Cross-platform duplicate detection for NordVest & More scrapers.
Compares new events against existing Notion entries to flag likely duplicates.
Uses source_mapping.csv to know which IG handles and FB pages are the same venue.

──────────────────────────────────────────────────────────────────────
FUTURE: Automatic duplicate resolution
──────────────────────────────────────────────────────────────────────
When we implement auto-dedup (removing duplicates instead of just flagging),
follow these rules:

1. SOURCE PRIORITY (keep the higher-priority link):
       Website  >  Facebook  >  Instagram
   - Websites are accessible to everyone (no login needed).
   - Facebook events have structured data (dates, times, locations).
   - Instagram posts have the least structured info.

2. MERGE, DON'T JUST DELETE:
   When removing the lower-priority duplicate, first merge its unique
   metadata INTO the winning (higher-priority) entry. In particular:
   - Tagged accounts ("To tag" field) — only available from Instagram
   - Instagram handle ("Instagramhandle" field)
   - Gemini-extracted description, organizer, or other enrichment
   - Any fields the winning entry is missing

   Goal: best link + richest combined metadata in one entry.
──────────────────────────────────────────────────────────────────────
"""
import csv
import io
import math
import os
import re
from pathlib import Path

MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_mapping.csv")

# Google Sheets URL (public, read-only) — edit the sheet at:
# https://docs.google.com/spreadsheets/d/1aKJo3jTLT8fSDDRFSIkRX9XU_MtrXalnVsJ7_T3UCCk/edit
_GSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1aKJo3jTLT8fSDDRFSIkRX9XU_MtrXalnVsJ7_T3UCCk"
    "/export?format=csv&gid=0"
)

# Cache the rows so we only fetch once per run
_cached_rows: list[dict] | None = None


def _load_csv_rows() -> list[dict]:
    """Load source mapping rows from Google Sheets, falling back to local CSV.

    Returns a list of dicts (one per row) with keys matching the sheet headers:
    name, instagram, facebook, fb_filter, fb_exclude, website, priority
    """
    global _cached_rows
    if _cached_rows is not None:
        return _cached_rows

    rows: list[dict] = []

    # Try Google Sheets first
    try:
        import urllib.request
        resp = urllib.request.urlopen(_GSHEET_CSV_URL, timeout=10)
        text = resp.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if rows:
            print(f"📋 Loaded {len(rows)} sources from Google Sheets")
            _cached_rows = rows
            return rows
    except Exception as e:
        print(f"📋 Google Sheets fetch failed ({e}), falling back to local CSV")

    # Fallback to local CSV
    path = Path(MAPPING_FILE)
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"📋 Loaded {len(rows)} sources from local CSV")

    _cached_rows = rows
    return rows

def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Two locations are considered the same venue if within this distance (metres).
SAME_VENUE_RADIUS_M = 150

# Similarity threshold (0-1). Events above this are flagged as duplicates.
SIMILARITY_THRESHOLD = 0.70


def load_fb_to_ig_map() -> dict[str, str]:
    """
    Load source mapping and return a dict: fb_identifier → ig_handle.
    Used by the FB scraper to fill in the Instagramhandle column.
    """
    fb_to_ig: dict[str, str] = {}
    for row in _load_csv_rows():
        ig = (row.get("instagram") or "").strip()
        fb_raw = (row.get("facebook") or "").strip()
        if ig and fb_raw:
            fb_id = _extract_fb_id(fb_raw).lower()
            fb_to_ig[fb_id] = f"@{ig}"
    return fb_to_ig


def load_source_mapping() -> dict[str, set[str]]:
    """
    Load source mapping and build a lookup: source_id → set of all aliases.

    Each row has: name, instagram, facebook, ..., website
    We group the entity name, IG handle, and FB page identifier together so we
    can check if two sources refer to the same venue — including the website
    scraper which uses the entity name (e.g. "lygten station") as its source.

    Returns e.g.:
        {"gamma_nv": {"gamma_nv", "61556180883930", "gamma"},
         "61556180883930": {"gamma_nv", "61556180883930", "gamma"},
         "gamma": {"gamma_nv", "61556180883930", "gamma"}, ...}
    """
    groups: dict[str, set[str]] = {}

    for row in _load_csv_rows():
        name = (row.get("name") or "").strip().lower()
        ig = (row.get("instagram") or "").strip().lower()
        fb_raw = (row.get("facebook") or "").strip()

        # Extract FB identifier from URL
        fb_id = _extract_fb_id(fb_raw).lower() if fb_raw else ""

        # Collect all identifiers for this entity:
        # entity name (used by website scraper as source key),
        # IG handle, and FB page id
        identifiers = {x for x in [name, ig, fb_id] if x}
        if not identifiers:
            continue

        if len(identifiers) < 2:
            # Only one identifier — nothing to cross-reference
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


_DANISH_MONTHS = r"(?:jan(?:uar)?|feb(?:ruar)?|mar(?:ts)?|apr(?:il)?|maj|jun[ie]?|jul[ie]?|aug(?:ust)?|sep(?:tember)?|okt(?:ober)?|nov(?:ember)?|dec(?:ember)?)"


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove punctuation, collapse spaces."""
    text = text.lower().strip()
    # Strip trailing date references like "- 3. april", "- 6. marts"
    text = re.sub(rf"\s*[-–]\s*\d{{1,2}}\.?\s*{_DANISH_MONTHS}\.?\s*$", "", text)
    text = re.sub(r"[^\w\s]", " ", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text)      # collapse whitespace
    return text


def _strip_date_suffix(text: str) -> str:
    """Strip trailing date references like '- 3. april' from event names."""
    return re.sub(rf"\s*[-–]\s*\d{{1,2}}\.?\s*{_DANISH_MONTHS}\.?\s*$", "", text.lower().strip())


def _compress(text: str) -> str:
    """Remove all spaces and punctuation for substring matching."""
    return re.sub(r"[^a-zæøå0-9]", "", _strip_date_suffix(text))


def _trigrams(text: str) -> set[str]:
    """Generate character trigrams from text."""
    t = _compress(text)
    if len(t) < 3:
        return {t} if t else set()
    return {t[i:i+3] for i in range(len(t) - 2)}


def similarity(a: str, b: str) -> float:
    """
    Multi-strategy similarity for event name matching.
    Combines word-level Jaccard, compressed containment, and character trigrams.
    Returns 0.0 to 1.0.
    """
    if not a or not b:
        return 0.0

    # Strategy 1: word-level Jaccard
    words_a = set(normalize_text(a).split())
    words_b = set(normalize_text(b).split())
    word_sim = 0.0
    if words_a and words_b:
        word_sim = len(words_a & words_b) / len(words_a | words_b)

    # Strategy 2: compressed containment (handles compound words like
    # "ImproSecco" vs "Impro-show med Impro-secco")
    ca, cb = _compress(a), _compress(b)
    containment = 0.0
    if ca and cb:
        shorter, longer = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
        if shorter in longer:
            containment = len(shorter) / len(longer)
            if containment >= 0.4:
                # Shorter string is a significant portion of the longer one
                containment = max(containment, 0.85)
            elif len(shorter) >= 8 and longer.startswith(shorter):
                # Shorter name is a clear prefix of the longer name
                # e.g. "Yoga'n'Sushi" → "yogansushi" is a prefix of
                # "yogansushisocialdiningnorxsticksnsushi"
                containment = 0.90
            elif len(shorter) >= 8 and containment >= 0.2:
                # Meaningful substring but not dominant — partial boost
                containment = max(containment, 0.80)

    # Strategy 3: character trigram Jaccard (handles word-form variations like
    # "kaoskomplottet" vs "kaoskomplottets")
    tri_a = _trigrams(a)
    tri_b = _trigrams(b)
    trigram_sim = 0.0
    if tri_a and tri_b:
        trigram_sim = len(tri_a & tri_b) / len(tri_a | tri_b)

    # Return the best of all strategies
    return max(word_sim, containment, trigram_sim)


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


# Similarity range for Gemini borderline check
_BORDERLINE_LOW = 0.40


def build_dedup_prompt(ev_a: dict, ev_b: dict) -> str:
    """Build a short prompt asking Gemini if two events are the same."""
    def fmt(ev):
        parts = [f'"{ev.get("name", "")}"', f'on {ev.get("date", "")}']
        if ev.get("time"):
            parts.append(f'at {ev["time"]}')
        if ev.get("location"):
            parts.append(f'at {ev["location"]}')
        return " ".join(parts)
    return (
        'Are these two event listings describing the same real-world event? '
        'Answer only "yes" or "no".\n\n'
        f"Event A: {fmt(ev_a)}\n"
        f"Event B: {fmt(ev_b)}"
    )


def find_duplicate(
    event_name: str,
    event_date: str,
    event_source: str,
    existing_entries: list[dict],
    mapping: dict[str, set[str]],
    event_location: str = "",
    event_time: str = "",
    gemini_fn=None,
    resolve_coords_fn=None,
) -> dict | None:
    """
    Check if this event likely duplicates an existing Notion entry.

    Rules (any match = duplicate):
      A. Same date + similar name (≥70%) + one of:
         - Source similarity >= 85% (or sources related via mapping)
         - Location similarity >= 85% (text) OR within 150 m (lat/lng)
         - Name similarity >= 85% (catch-all)
      B. Same date + same time + same location (≥85% text OR within 150 m) — regardless of name
      C. [if gemini_fn provided] Same date + borderline name similarity (40–70%) +
         related source or similar location → ask Gemini to confirm

    Args:
        event_name: Name of the new event
        event_date: Start date (YYYY-MM-DD) of the new event
        event_source: Source identifier (IG handle or FB page name)
        existing_entries: List of dicts with keys: name, start_date, source, page_id, location, start_time
        mapping: Source mapping from load_source_mapping()
        event_location: Location/venue of the new event
        event_time: Start time (HH:MM) of the new event
        gemini_fn: Optional callable(ev_a: dict, ev_b: dict) -> bool | None
                   Called for borderline similarity cases. Returns True if duplicate.
        resolve_coords_fn: Optional callable(location_text: str) -> (lat, lng) | None
                   Resolves a location string to coordinates via the Locations DB.

    Returns:
        The matching existing entry dict if a likely duplicate is found, else None.
    """
    if not event_name or not event_date:
        return None

    SOURCE_SIM_THRESHOLD = 0.85
    LOCATION_SIM_THRESHOLD = 0.85

    def _locations_near(loc_a: str, loc_b: str) -> bool:
        """Return True if both locations resolve to coordinates within SAME_VENUE_RADIUS_M."""
        if not resolve_coords_fn or not loc_a or not loc_b:
            return False
        coords_a = resolve_coords_fn(loc_a)
        coords_b = resolve_coords_fn(loc_b)
        if coords_a and coords_b:
            return _haversine_m(coords_a[0], coords_a[1], coords_b[0], coords_b[1]) <= SAME_VENUE_RADIUS_M
        return False

    def _location_match(loc_a: str, loc_b: str) -> bool:
        """Text similarity ≥ threshold OR within SAME_VENUE_RADIUS_M."""
        if not loc_a or not loc_b:
            return False
        return similarity(loc_a, loc_b) >= LOCATION_SIM_THRESHOLD or _locations_near(loc_a, loc_b)

    borderline_candidates: list[dict] = []

    for entry in existing_entries:
        # Must have the same date
        if entry.get("start_date") != event_date:
            continue

        # ── Rule B: same date + same time + same location ──
        # Different names but same place at the same time = same event
        entry_time = (entry.get("start_time") or "").strip()
        if (event_time and entry_time and event_time == entry_time
                and event_location and entry.get("location")):
            if _location_match(event_location, entry.get("location", "")):
                return entry

        # ── Rule A: same date + similar name + source/location/name catch-all ──
        name_sim = similarity(event_name, entry.get("name", ""))
        if name_sim < SIMILARITY_THRESHOLD:
            # ── Rule C: collect borderline candidates for Gemini ──
            if gemini_fn and name_sim >= _BORDERLINE_LOW:
                src_related = are_sources_related(event_source, entry.get("source", ""), mapping)
                loc_sim = similarity(event_location, entry.get("location", "")) if (event_location and entry.get("location")) else 0.0
                loc_near = _locations_near(event_location, entry.get("location", ""))
                if src_related or loc_sim >= 0.70 or loc_near:
                    borderline_candidates.append(entry)
            continue

        # Catch-all: high name similarity alone is enough
        if name_sim >= 0.85:
            return entry

        # Otherwise must match on source OR location
        # Check source: either via mapping or fuzzy similarity
        source_match = are_sources_related(event_source, entry.get("source", ""), mapping)
        if not source_match:
            source_sim = similarity(event_source, entry.get("source", ""))
            source_match = source_sim >= SOURCE_SIM_THRESHOLD

        if source_match:
            return entry

        # Check location (text similarity or proximity)
        if _location_match(event_location, entry.get("location", "")):
            return entry

        # Name sim is 0.70-0.85 and source/location didn't confirm — ask Gemini
        if gemini_fn:
            borderline_candidates.append(entry)

    # ── Rule C: ask Gemini about borderline candidates ──
    if gemini_fn and borderline_candidates:
        ev_a = {"name": event_name, "date": event_date, "time": event_time, "location": event_location}
        for entry in borderline_candidates:
            ev_b = {
                "name": entry.get("name", ""),
                "date": entry.get("start_date", ""),
                "time": entry.get("start_time", ""),
                "location": entry.get("location", ""),
            }
            result = gemini_fn(ev_a, ev_b)
            if result is True:
                return entry

    return None


def get_source_priority(url: str) -> int:
    """
    Return source priority for cross-platform dedup merging (lower = better):
      1 = website  (best — structured, no login required)
      2 = facebook
      3 = instagram (worst — unstructured text, AI-extracted data)
    """
    url = (url or "").lower()
    if "instagram.com" in url:
        return 3
    if "facebook.com" in url:
        return 2
    return 1
