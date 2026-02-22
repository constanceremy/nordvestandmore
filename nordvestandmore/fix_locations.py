#!/usr/bin/env python3
"""
One-time script to update Notion database entries:
Replace full addresses in the Location field with venue names only.
"""
import os
import requests
from pathlib import Path

# ── Load .env ──
env_file = Path(__file__).resolve().parent / ".env"
for line in env_file.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    if "=" in line:
        key, val = line.split("=", 1)
        os.environ[key.strip()] = val.strip().strip('"').strip("'")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB = os.environ["NOTION_DATABASE_ID"]
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# ── Location replacements ──
# Maps known full-address locations → clean venue names
LOCATION_FIXES: dict[str, str] = {
    # Storm B Café
    "Storm B Café, Blågårdsgade 28, 2200 København N": "Storm B Café",
    # Flere Fugle
    "Flere Fugle, Frederikssundsvej 35, 2400 København NV": "Flere Fugle",
    "Flere Fugle, Gammel Jernbanevej 7, 2500 Valby": "Flere Fugle",
    # Fovl
    "Fovl, Rentemestervej 64, 2400 København NV": "Fovl NV",
    "Fovl NV, Rentemestervej 64, 2400 København NV": "Fovl NV",
    # Flok Kantine
    "Flok Kantine, Lygten 39, 2400 København NV": "Flok Kantine",
    # Taca (keep as meeting point address only, no city)
    "Engsvinget 55, 2400 København NV": "Engsvinget 55",
    # Tekno Eatery
    "Tekno Eatery, Rentemestervej 62, 2400 København NV": "Tekno Eatery",
    # Tagensbo Kirke
    "Tagensbo Kirke, Landsdommervej 35, 2400 København NV": "Tagensbo Kirke",
    # Demokratigarage / Rentemestervej 57
    "Rentemestervej 57, 2400 København NV": "Demokratigarage",
    # Just Sauna / Urban 13
    "Urban13, Bispeengen 20, 2000 Frederiksberg": "Urban 13",
    "Urban 13, Bispeengen 20, 2000 Frederiksberg": "Urban 13",
    # Sauna 85
    "Rentemestervej 64, 2400 København NV": "Sauna 85",
    # Nordic Health House
    "NOR: Nordic Health House, Hejrevej 30, 2400 København NV": "Nordic Health House",
    "Nordic Health House, Hejrevej 30, 2400 København NV": "Nordic Health House",
    # Kapernaumskirken
    "Kapernaumskirken, Frederikssundsvej 45, 2400 København NV": "Kapernaumskirken",
    # Thoravej 29
    "Thoravej 29, 2400 København NV": "Thoravej 29",
    # KK Bibliotek
    "BIBLIOTEKET Rentemestervej, Rentemestervej 76, 2400 København NV": "Biblioteket Rentemestervej",
}

# Also fix locations that have sub-venue + full address (e.g. "Dansekapellet, Thoravej 29, 2400 København NV")
ADDRESS_SUFFIXES = [
    ", Thoravej 29, 2400 København NV",
    ", Blågårdsgade 28, 2200 København N",
    ", Frederikssundsvej 35, 2400 København NV",
    ", Rentemestervej 64, 2400 København NV",
    ", Rentemestervej 62, 2400 København NV",
    ", Rentemestervej 57, 2400 København NV",
    ", Rentemestervej 76, 2400 København NV",
    ", Lygten 39, 2400 København NV",
    ", Hejrevej 30, 2400 København NV",
    ", Bispeengen 20, 2000 Frederiksberg",
    ", Frederikssundsvej 45, 2400 København NV",
    ", Gammel Jernbanevej 7, 2500 Valby",
    ", Engsvinget 55, 2400 København NV",
]


def clean_location(loc: str) -> str | None:
    """Return cleaned location or None if no change needed."""
    if not loc:
        return None

    # Exact match first
    if loc in LOCATION_FIXES:
        return LOCATION_FIXES[loc]

    # Strip known address suffixes (for sub-venue cases like "Dansekapellet, Thoravej 29, ...")
    for suffix in ADDRESS_SUFFIXES:
        if loc.endswith(suffix):
            cleaned = loc[: -len(suffix)].strip()
            if cleaned:
                return cleaned

    return None


def main():
    # ── Fetch all entries ──
    print("Fetching all entries from Notion...")
    all_pages = []
    payload: dict = {"page_size": 100}
    while True:
        r = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        all_pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    print(f"Found {len(all_pages)} entries total.")

    # ── Find entries that need updating ──
    to_update: list[tuple[str, str, str, str]] = []  # (page_id, name, old_loc, new_loc)

    for page in all_pages:
        props = page.get("properties", {})
        page_id = page["id"]

        # Get event name for logging
        name_parts = props.get("Event Name", {}).get("title", [])
        name = name_parts[0]["text"]["content"] if name_parts else "(untitled)"

        # Get current location
        loc_parts = props.get("Location", {}).get("rich_text", [])
        if not loc_parts:
            continue
        old_loc = loc_parts[0]["text"]["content"]

        new_loc = clean_location(old_loc)
        if new_loc and new_loc != old_loc:
            to_update.append((page_id, name, old_loc, new_loc))

    if not to_update:
        print("\n✅ No locations need updating — all clean!")
        return

    print(f"\n{'─' * 80}")
    print(f"Found {len(to_update)} entries to update:\n")
    for _, name, old_loc, new_loc in to_update:
        print(f"  {name[:50]:<50}")
        print(f"    OLD: {old_loc}")
        print(f"    NEW: {new_loc}")
        print()

    # ── Confirm ──
    answer = input(f"Update {len(to_update)} entries? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled.")
        return

    # ── Apply updates ──
    updated = 0
    errors = 0
    for page_id, name, old_loc, new_loc in to_update:
        payload = {
            "properties": {
                "Location": {
                    "rich_text": [{"text": {"content": new_loc}}]
                }
            }
        }
        r = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=HEADERS,
            json=payload,
            timeout=30,
        )
        if r.status_code < 400:
            updated += 1
            print(f"  ✅ {name[:60]}")
        else:
            errors += 1
            print(f"  ❌ {name[:60]} — {r.status_code}: {r.text[:200]}")

    print(f"\n{'─' * 80}")
    print(f"Done! Updated: {updated}, Errors: {errors}")


if __name__ == "__main__":
    main()
