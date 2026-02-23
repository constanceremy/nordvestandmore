#!/usr/bin/env python3
"""
Auto-tagging module for event classification.
──────────────────────────────────────────────
Classifies events into categories based on their name, description, and organizer.
Uses keyword/pattern matching (fast, no API calls needed).

The TAG_RULES list is ordered by priority — the first matching rule wins.
More specific rules come before broader ones so that e.g. "Sauna" beats "Wellness".

To add a new tag:
  1. Add a dict to TAG_RULES with "tag", "keywords", and optionally "patterns".
  2. Place it in the correct priority position.

To see which tag an event would get:
  python auto_tag.py "Event Name" "optional description"
"""

import csv
import re
from pathlib import Path

# ────────────────── Tag definitions ──────────────────
# Each rule: { "tag": str, "keywords": [str], "patterns": [regex_str] }
# - keywords: checked as substrings in the lowercased combined text
# - patterns: checked as regex against the original text (case-insensitive)
# First match wins — order matters!

TAG_RULES: list[dict] = [
    # ── Book Club / Literature ──  (before Sauna so "Rört Book Club" → Book Club)
    {
        "tag": "Book Club",
        "keywords": [
            "bogklub", "book club", "litteraturkreds", "litteratur",
            "boghandel", "boglancering", "sci-fi bogklub",
        ],
        "patterns": [r"\bBOGKLUB\b", r"\bBOOK\s+CLUB\b"],
    },
    # ── Singing / Choir ──  (before Spirituality so "Fællessang" → Singing)
    {
        "tag": "Singing",
        "keywords": [
            "fællessang", "kor ", "koret", "damekor",
            "højskolesang", "barselskor", "barselskoret",
            "tune in! - koret", "syng i flok",
        ],
        "patterns": [r"\bKORET\b", r"\bFÆLLESSANG\b"],
    },
    # ── Volunteering ──  (before Spirituality so "sogneindsamling" → Volunteering)
    {
        "tag": "Volunteering",
        "keywords": [
            "sogneindsamling", "indsamling",
            "planlægningsmøde",
        ],
        "patterns": [],
    },
    # ── Church / Spiritual ──  (before Drinks so "G&T-natkirke" → Church)
    {
        "tag": "Spirituality",
        "keywords": [
            "natkirke", "kirke", "gudstjeneste", "aftensang",
            "café rummet", "café larsen", "godnathistorier",
        ],
        "patterns": [r"\bNATKIRKE\b", r"\bKIRKE\b"],
    },
    # ── Sauna & Wellness ──
    {
        "tag": "Sauna",
        "keywords": [
            "sauna", "saunagus", "gus session", "gusmester",
            "roklubben sauna", "uberört",
        ],
        "patterns": [r"\bSAUNA\b"],
        # Note: "Rört" is a venue that hosts many event types (yoga, book
        # club, kirtan, etc.) — NOT just sauna. Only explicit "sauna"
        # keywords trigger this tag.
        # Exception: if "dance" is also present → Festival & Party instead.
        "except_when": {"keywords": ["dance"], "redirect": "Festival & Party"},
    },
    # ── Quiz / Banko / Bingo ──
    {
        "tag": "Quiz / Banko / Bingo",
        "keywords": [
            "quiz", "banko", "bingo", "trivia",
            "music bingo", "popquiz", "musikquiz", "music quiz",
        ],
        "patterns": [r"\bQUIZ\b", r"\bBANKO\b", r"\bBINGO\b"],
    },
    # ── Board Games / Chess ──
    {
        "tag": "Games",
        "keywords": [
            "brætspil", "board game", "boardgame",
            "skak ", "chess", "skak for børn",
        ],
        "patterns": [r"\bSKAK\b"],
    },
    # ── Comedy / Improv ──
    {
        "tag": "Comedy",
        "keywords": [
            "comedy", "improv", "stand-up", "standup", "test show",
            "testshow", "humor", "kaoskomplottet", "improsecco",
            "hygge show", "improshow", "impro-show", "impro show",
            "material test", "new show", "sofie hagen",
            "mikael wulff", "mikkel klint", "jason rouse",
        ],
        "patterns": [r"\bIMPROV\b", r"\bCOMEDY\b"],
    },
    # ── Film / Screening ──
    {
        "tag": "Film",
        "keywords": [
            "film", "screening", "roboclub", "cph:dox", "biograf",
            "cinema unscripted", "movie",
        ],
        "patterns": [r"\bROBOCLUB\b", r"CPH:DOX"],
    },
    # ── Market / Sale ──
    {
        "tag": "Market",
        "keywords": [
            "flea market", "loppemarked", "stock & sample",
            "sample sale", "stock sale", "rose tuesday",
            "bazar",
        ],
        "patterns": [r"\bFLEA\s+MARKET\b"],
    },
    # ── Craft Gathering ──  (social craft meetups, before Workshop)
    {
        "tag": "Craft Gathering",
        "keywords": [
            "strikkeklub", "nørklecafé", "mandagshåndværk",
            "strik og hør", "broderi", "fiks og færdig",
            "farv garn", "papirblomster", "blækmaling", "crepepapir",
        ],
        "patterns": [],
    },
    # ── Workshop / Craft ──
    {
        "tag": "Workshop",
        "keywords": [
            "workshop", "kursus", "course", "craft", "masterclass",
            "bootcamp", "intro", "serigrafi", "monotypi", "grafik",
            "linoleum", "tryk",
            "surdejsbrød", "croissant",
            "facilitator uddannelse",
            "drawing", "painting", "sketching", "expressive form",
        ],
        "patterns": [r"\bWORKSHOP\b", r"\bKURSUS\b", r"\bMASTERCLASS\b"],
    },
    # ── Yoga / Meditation / Breathwork ──
    {
        "tag": "Yoga & Mindfulness",
        "keywords": [
            "yoga", "meditation", "breathwork", "yin ", "lydhealing",
            "sound bath", "soundbath", "sound journey", "gong bath",
            "kirtan", "satsang", "retræte", "retreat",
            "tantra", "embodied", "ceremony",
            "shamanist", "trommerejse", "sundhed",
        ],
        "patterns": [r"\bYOGA\b", r"\bYIN\b"],
    },
    # ── Sport / Running / Exercise ──
    {
        "tag": "Sport & Run",
        "keywords": [
            "run ", "running", "løbeklub", "løbetur", "løbehold",
            "social run", "workout",
            "fitness", "træning", "biomekanik", "body & mind",
            "run club", "3k run",
        ],
        "patterns": [r"\bRUN\b(?!\s+(?:BY|AT|IN|ON|THE))", r"\bløb\b"],
    },
    # ── Food Special ──  (before Community Dinner so "Fry-Day" → Food Special)
    {
        "tag": "Food Special",
        "keywords": [
            "fry-day",
        ],
        "patterns": [r"\bFRY-DAY\b"],
    },
    # ── Community Dinner / Food ──
    {
        "tag": "Community Dinner",
        "keywords": [
            "fællesspisning", "middag for alle", "community breakfast",
            "community dinner", "potluck", "peoples kitchen",
            "supperclub", "supper club", "madklub",
            "frokost", "madspild", "stories on plates",
            "gud & burger",
        ],
        "patterns": [],
    },
    # ── Speed Dating ──
    {
        "tag": "Speed Dating",
        "keywords": [
            "speed dating", "speeddating",
        ],
        "patterns": [r"\bSPEED\s*DATING\b"],
    },
    # ── Drinks / Happy Hour ──
    {
        "tag": "Drinks & Bar",
        "keywords": [
            "happy hour", "cocktail", "champagne", "piña colada",
            "behind the brews", "irish coffee", "brew hang",
            "tirsdagsdeals", "putty day",
            "single (hops)", "valentine",
        ],
        "patterns": [r"\bHAPPY\s+HOUR\b"],
    },
    # ── Music / Concert / DJ ──
    {
        "tag": "Music",
        "keywords": [
            "concert", "koncert", "dj ", "live music", "album release",
            "jazz", "punk", "gig", "metal", "hardcore", "doom",
            "soooundsss", "urban sessions", "urban 13", "sessions",
            "musik café", "huskoncert", "orgel", "kammerkonc",
            "powerviolence", "grindcore", "sludge", "moshpit",
            "shuffle", "karaoke", "schwanengesang",
            "show in ungdomshuset",
            "bands of tomorrow", "all tribes are welcome",
            "lament",
        ],
        "patterns": [
            r"\bDJ\b", r"\bD\.J\.", r"\bGIG\b", r"URBAN\s+Sessions",
            r"URBAN\s+13", r"\bKONCERT\b", r"\bPUNK\b",
            # Artist lineup pattern: "NAME + NAME" (common in music events)
            r"^[A-ZÆØÅa-zæøå\$][\w\.\$\s]*\s\+\s",
        ],
    },
    # ── Dance / Performance / Theater ──
    {
        "tag": "Dance & Performance",
        "keywords": [
            "dans ", "dance", "ballet", "koreografi", "performance",
            "teater", "theater", "theatre", "forestilling",
            "akroyoga", "nattens syntese", "månen er af papir",
        ],
        "patterns": [r"\bDANS\b", r"\bDANCE\b"],
    },
    # ── Art / Exhibition / Gallery ──
    {
        "tag": "Art & Exhibition",
        "keywords": [
            "udstilling", "exhibition", "fernisering", "vernissage",
            "galleri", "gallery", "residency", "rundvisning",
        ],
        "patterns": [r"\bFERNISERING\b"],
    },
    # ── Kids / Family ──
    {
        "tag": "Kids & Family",
        "keywords": [
            "børn", "baby", "barsel", "barsels", "familie",
            "ungdomsgård", "fritidsklub", "teaterskole",
            "gravidcirkel", "mødre",
            "children", "kids", "playroom", "legestue",
            "børnekultur", "musikleg", "babysalmesang",
        ],
        "patterns": [r"\b\d+.?\d*\s*(?:year|år)\s*old"],
    },
    # ── Talk / Lecture / Conference ──
    {
        "tag": "Talk & Lecture",
        "keywords": [
            "foredrag", "lecture", "konference", "conference",
            "seminar", "samtale", "talk", "debat",
            "fortællinger", "togrejser",
        ],
        "patterns": [r"\bFOREDRAG\b"],
    },
    # ── Festival / Party ──
    {
        "tag": "Festival & Party",
        "keywords": [
            "festival", "party",
            "fødselsdags", "aperitivo", "klub rört",
            "dance x sauna",
        ],
        "patterns": [r"\bFESTIVAL\b"],
    },
    # ── Social Gathering ──
    {
        "tag": "Social Gathering",
        "keywords": [
            "neighbor sunday", "social", "gathering", "sharing circle",
            "onsdagsklubben", "sommerfest",
            "møde", "open hours",
            "demonstration",
        ],
        "patterns": [],
    },
]


# ── Hours / closure announcements → route to separate DB ──
_HOURS_KEYWORDS = [
    "opening hours", "åbningstider", "åbningstid",
    "lukket", "holder lukket", "vi holder fri",
    "closed for", "we are closed", "we're closed",
    "ferielukket", "lukket for ferie", "sommerferie",
    "påskeåbningstider", "påske åbningstider",
    "juleferie", "juleåbningstider", "jule åbningstider",
    "nytårsåbningstider", "nytår åbningstider",
    "holiday hours", "christmas hours", "easter hours",
    "personalefest", "staff party",
]

_HOURS_PATTERNS = [
    r"\blukket\b.*\bferie\b",
    r"\bferie\b.*\blukket\b",
    r"\bholder?\b.*\blukket\b",
    r"\blukket\b.*\bhelligdag",
    r"\bændrede?\b.*\båbningstid",
]


# ── Deals / special-price announcements → route to Deals DB ──
_DEAL_KEYWORDS = [
    "tilbud", "rabat", "nedsat", "specialpris", "udsalg",
    "deal", "deals", "discount", "special price", "special offer",
    "half price", "halv pris", "studierabat", "student discount",
    "frokosttilbud", "lunch deal", "dagstilbud", "ugens tilbud",
    "2 for 1", "two for one", "2-for-1",
    "tirsdagsdeals", "onsdagsdeals", "torsdagsdeals",
    "mandagsdeals", "fredagsdeals",
    "% off", "% rabat",
]

_DEAL_PATTERNS = [
    r"\b\d+\s*(?:kr|dkk)\.?\s.*\btilbud\b",
    r"\btilbud\b.*\b\d+\s*(?:kr|dkk)",
    r"\b\d+\s*for\s*\d+\b",          # e.g. "2 for 1"
    r"\b\d+%\s*(?:off|rabat)\b",      # e.g. "20% off"
    r"\bspar\s+\d+",                  # e.g. "spar 50kr"
    r"\bkun\s+\d+\s*kr\b",            # e.g. "kun 49kr"
]


# ── Non-event posts to skip entirely (not routed anywhere) ──
_SKIP_KEYWORDS = [
    "application deadline", "ansøgningsfrist", "deadline",
]


def is_not_event(event_name: str) -> bool:
    """Return True if the event name is an hours/closure announcement, not a real event."""
    name_lower = (event_name or "").lower().strip()
    for kw in _HOURS_KEYWORDS:
        if kw in name_lower:
            return True
    for pat in _HOURS_PATTERNS:
        if re.search(pat, name_lower):
            return True
    return False


def is_deal(event_name: str, description: str = "") -> bool:
    """Return True if the event name/description is a deal/special-price announcement."""
    combined = f"{event_name} {description}".lower().strip()
    for kw in _DEAL_KEYWORDS:
        if kw in combined:
            return True
    for pat in _DEAL_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            return True
    return False


def should_skip_entirely(event_name: str, description: str = "") -> bool:
    """Return True if the post should be skipped entirely (not an event, not hours)."""
    name_lower = (event_name or "").lower().strip()
    for kw in _SKIP_KEYWORDS:
        if kw in name_lower:
            return True

    # Residency announcements are not events — unless there's a
    # reception / vernissage / opening on a specific day
    if "residency" in name_lower or "residens" in name_lower:
        combined = f"{name_lower} {(description or '').lower()}"
        has_reception = any(w in combined for w in [
            "reception", "vernissage", "fernisering", "opening",
            "åbning", "event", "performance", "show",
        ])
        if not has_reception:
            return True

    return False


# ── Locations that are NOT in Nordvest → skip these events ──
_EXCLUDED_LOCATIONS = [
    "christiania comedy club",
]


def is_excluded_location(location: str) -> bool:
    """Return True if the location is outside Nordvest and should be skipped."""
    loc_lower = (location or "").lower().strip()
    for excl in _EXCLUDED_LOCATIONS:
        if excl in loc_lower:
            return True
    return False


# ── Known Nordvest locations → flag unknown ones for review ──

def _load_known_nv_locations() -> set[str]:
    """Load known NV venue/org names from source_mapping.csv + extras."""
    locations: set[str] = set()

    csv_path = Path(__file__).resolve().parent / "source_mapping.csv"
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row.get("name", "").strip()
                if name:
                    locations.add(name.lower())

    # Additional venue names / aliases not in the CSV
    locations.update({
        "café rummet", "flok kantine", "fovl nv",
        "sauna 85", "biblioteket rentemestervej",
        "tekno eatery", "engsvinget 55", "thoravej 29",
        "pool pub", "makerspace nv", "repair cafe",
        "dorthea's bar", "dortheas", "dave's", "daves",
        "cafe gazou", "rört", "rort",
        "storm b cafe", "storm b café",
        "sokkelundlille", "utterslev torv",
        "københavnstrup", "flok",
        "gamma nv", "aftenskolernes hus",
    })

    return locations


_KNOWN_NV_LOCATIONS: set[str] = _load_known_nv_locations()

# NV area indicators — if any appears in the location string, it's NV
_NV_AREA_INDICATORS = [
    "2400", "nordvest", "københavn nv",
    "bispebjerg", "bellahøj", "lygten",
    "rentemestervej", "frederikssundsvej", "thoravej",
    "hejrevej", "engsvinget", "birkedommervej",
]


def is_unknown_location(location: str) -> bool:
    """Return True if the location is NOT recognized as a known Nordvest venue.

    Empty / blank locations are NOT flagged — those are caught by the
    "Missing fields" formula in Notion.
    """
    if not location or not location.strip():
        return False

    loc_lower = location.lower().strip()

    # Check NV area indicators (addresses clearly in the area)
    for indicator in _NV_AREA_INDICATORS:
        if indicator in loc_lower:
            return False

    # Check known location names (substring match in either direction)
    for known in _KNOWN_NV_LOCATIONS:
        if known in loc_lower or loc_lower in known:
            return False

    return True


def classify_event(
    event_name: str,
    description: str = "",
    organizer: str = "",
) -> str | None:
    """
    Classify an event into a tag category.

    Returns the tag name (str) or None if no rule matches.
    Checks event_name first (higher weight), then description and organizer.
    """
    # Combine all text for matching
    combined = f"{event_name} | {description} | {organizer}".lower()
    # Also keep original case for regex patterns
    combined_raw = f"{event_name} | {description} | {organizer}"

    for rule in TAG_RULES:
        matched = False

        # Check keywords (substring match in lowercased text)
        for kw in rule.get("keywords", []):
            if kw.lower() in combined:
                matched = True
                break

        # Check regex patterns (case-insensitive)
        if not matched:
            for pattern in rule.get("patterns", []):
                if re.search(pattern, combined_raw, re.IGNORECASE):
                    matched = True
                    break

        if not matched:
            continue

        # Check exceptions: if an "except_when" condition is met, redirect
        exc = rule.get("except_when")
        if exc:
            exc_hit = any(ek.lower() in combined for ek in exc.get("keywords", []))
            if not exc_hit:
                exc_hit = any(
                    re.search(p, combined_raw, re.IGNORECASE)
                    for p in exc.get("patterns", [])
                )
            if exc_hit:
                return exc["redirect"]

        return rule["tag"]

    return None


# ────────────────── Standalone test ──────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        name = sys.argv[1]
        desc = sys.argv[2] if len(sys.argv) > 2 else ""
        tag = classify_event(name, desc)
        print(f"Event: {name}")
        if desc:
            print(f"Desc:  {desc}")
        print(f"Tag:   {tag or '(no match)'}")
    else:
        # Test with sample events
        test_events = [
            ("Brætspilsaften", ""),
            ("Fry-Day", ""),
            ("Happy Hour - 2 for 1 cocktail", ""),
            ("All Crafts Are Beautiful", ""),  # Workshop (generic "craft")
            ("Strikkeklub i Nørklecaféen", ""),  # Craft Gathering
            ("Mandagshåndværk", ""),  # Craft Gathering
            ("Fiks og Færdig - reparationscafé", ""),  # Craft Gathering
            ("Kaoskomplottet Improshow", ""),
            ("BANKO!", ""),
            ("Middag for alle", ""),
            ("Neighbor Sunday", ""),
            ("Special Charity Sauna Session", ""),
            ("Rört Book Club", ""),
            ("DJ YAS WADI", ""),
            ("ROBOCLUB: Interstellar", ""),
            ("Københavnstrup Flea Market", ""),
            ("Taca Copenhagen Social Run for Men", ""),
            ("NordVest Klassisk", "Klassisk koncert"),
            ("Yin Lydhealing", ""),
            ("Fernisering | Det Mosen vil Fortælle", ""),
            ("Foredrag: Biler til Ukraine", ""),
            ("Skak for børn på BIBLIOTEKET", ""),
            ("G&T-natkirke om åndelig oprustning", ""),
            ("Sommerfest", ""),
            ("ALIVE Tantra Festival 2026", ""),
            ("Workshop: Surdejsbrød", ""),
            ("Tekno Supperclub", ""),
            ("Rose Tuesday", ""),
            ("Sofie Hagen material test", ""),
            ("ATAQUE PUNK GIG VII", ""),
            ("Emma Lindquist - album release concert", ""),
            ("Barselscafé med babysang", ""),
            ("$MALIKK + IVER | URBAN Sessions", ""),
            ("PEOPLES KITCHEN - RAMADAN THEME", ""),
            ("TRIVIA QUIZ", ""),
            # Edge cases for priority ordering
            ("Rört Book Club", ""),
            ("G&T-natkirke om åndelig oprustning", ""),
            ("ALIVE Tantra Festival 2026", ""),
            ("Dance x Sauna at Rört with DJ SaS", ""),
            ("Rört Special: Kirtan & Satsang", ""),
            ("Speed Dating at Tapperiet", ""),
            ("Rört Yoga Session", ""),
            # Previously untagged events — now classified
            ("(1) Monique Wittig: Opoponaxen", "fortællinger og samtale"),
            ("1 MARTS DEMONSTRATION", ""),
            ("ALL TRIBES ARE WELCOME #2", ""),
            ("Bands of Tomorrow | 1-års markering", ""),
            ("C.R.O.", "koncert"),
            ("Can she excuse my wrongs? - Dowlands Lament", ""),
            ("D.J. BACONFAR", ""),
            ("Dovenskab, sundhed og kroniske lidelser", ""),
            ("EMI LIA + albert //GLØD", ""),
            ("Fortællinger for Fred", ""),
            ("HUGPUNCH + Bending Backwards + Nina and Alfred", ""),
            ("Hvad nu hvis det bare er fantasi?", "foredrag"),
            ("Joonas + johs + albert", ""),
            ("MUTT", "koncert"),
            ("Månen er af papir", ""),
            ("Nattens Syntese | FAVNER CARMEN", ""),
            ("PUTTY DAY 2026", ""),
            ("SKARNET + De Frigjorte", ""),
            ("THE S.H.A.R.PENING", "punk metal"),
            ("Togrejser for begyndere", ""),
            ("Fortællinger for Fred: En aften om ramadanen", ""),
            # Foredrag with "løber af stablen" in description → Talk, NOT Sport
            ("Foredrag med bid i - info kommer snarest!", "Den første løber af stablen den 6. maj"),
        ]
        print(f"{'Event':<55} {'Tag':<25}")
        print("─" * 80)
        matched = 0
        for name, desc in test_events:
            tag = classify_event(name, desc)
            if tag:
                matched += 1
            print(f"{name:<55} {tag or '(no match)':<25}")
        print(f"\nMatched: {matched}/{len(test_events)}")
