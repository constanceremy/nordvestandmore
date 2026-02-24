#!/usr/bin/env python3
"""
Location cleaning utility.
Maps full addresses to clean venue names for the Nordvest area.
Used by all scrapers to normalize locations before pushing to Notion.
"""

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
    # KK Bibliotek — various capitalizations and formats
    "BIBLIOTEKET Rentemestervej, Rentemestervej 76, 2400 København NV": "Biblioteket Rentemestervej",
    "BIBLIOTEKET Rentemestervej": "Biblioteket Rentemestervej",
    "Biblioteket rentemestervej": "Biblioteket Rentemestervej",
    "biblioteket rentemestervej": "Biblioteket Rentemestervej",
    "Rentemestervej 76, 2400 København NV": "Biblioteket Rentemestervej",
    # Ansgarkirken
    "Ansgarkirken, Sallingvej 55, 2720 Vanløse": "Ansgarkirken",
    "Ansgarkirken, Sallingvej 55, 2720 København NV": "Ansgarkirken",
    # Grundtvigs Kirke
    "Grundtvigs Kirke, På Bjerget 14B, 2400 København NV": "Grundtvigs Kirke",
    "Grundtvigskirken, På Bjerget 14B, 2400 København NV": "Grundtvigs Kirke",
    # Ungdomshuset
    "Ungdomshuset, Dortheavej 61, 2400 København NV": "Ungdomshuset",
    "Ungdomshuset D61, Dortheavej 61, 2400 København NV": "Ungdomshuset",
    # Rört
    "Rört, Lygten 33, 2400 København NV": "Rört",
    "RÖRT, Lygten 33, 2400 København NV": "Rört",
    # Goldschmidts Musikakademi
    "Goldschmidts Musikakademi, Helga Larsens Plads 2, 2400 København NV": "Goldschmidts Musikakademi",
    # Dave's
    "Dave's, Frederikssundsvej 21, 2400 København NV": "Dave's",
    # Lygten Station
    "Lygten Station, Lygten 2, 2400 København NV": "Lygten Station",
    # Tribeca
    "Tribeca Beer & Pizza Lab, Frederikssundsvej 31, 2400 København NV": "Tribeca",
    # Gamma NV
    "Gamma NV, Rentemestervej 67, 2400 København NV": "Gamma NV",
    # Dorthea's Bar
    "Dorthea's Bar, Dortheavej 4, 2400 København NV": "Dorthea's Bar",
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
    ", Lygten 33, 2400 København NV",
    ", Lygten 2, 2400 København NV",
    ", Hejrevej 30, 2400 København NV",
    ", Bispeengen 20, 2000 Frederiksberg",
    ", Frederikssundsvej 45, 2400 København NV",
    ", Frederikssundsvej 31, 2400 København NV",
    ", Frederikssundsvej 21, 2400 København NV",
    ", Gammel Jernbanevej 7, 2500 Valby",
    ", Engsvinget 55, 2400 København NV",
    ", Sallingvej 55, 2720 Vanløse",
    ", Sallingvej 55, 2720 København NV",
    ", På Bjerget 14B, 2400 København NV",
    ", Dortheavej 61, 2400 København NV",
    ", Dortheavej 4, 2400 København NV",
    ", Helga Larsens Plads 2, 2400 København NV",
    ", Landsdommervej 35, 2400 København NV",
    ", Rentemestervej 67, 2400 København NV",
    # Generic Copenhagen suffixes (catch-all for any venue we missed)
    ", 2400 København NV",
    ", 2400 Copenhagen NV",
    ", Copenhagen, Denmark",
    ", København, Denmark",
    ", Denmark",
]


# Build a case-insensitive lookup for LOCATION_FIXES
_LOCATION_FIXES_LOWER: dict[str, str] = {k.lower(): v for k, v in LOCATION_FIXES.items()}


def clean_location(loc: str) -> str | None:
    """Return cleaned location or None if no change needed.
    Matching is case-insensitive.
    """
    if not loc:
        return None

    # Exact match first (case-insensitive)
    fixed = _LOCATION_FIXES_LOWER.get(loc.lower())
    if fixed:
        return fixed

    # Strip known address suffixes (case-insensitive)
    loc_lower = loc.lower()
    for suffix in ADDRESS_SUFFIXES:
        if loc_lower.endswith(suffix.lower()):
            cleaned = loc[: -len(suffix)].strip()
            if cleaned:
                return cleaned

    return None
