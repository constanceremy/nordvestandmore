#!/usr/bin/env python3
"""
Recurring Events Generator
---------------------------
Defines manually-configured recurring events that don't appear reliably
on any website, Facebook, or Instagram feed.

Each recurring event specifies its schedule, and the generator produces
individual event instances for the next N months (default: 6).
"""

from datetime import date, timedelta
import calendar
from auto_tag import classify_event


# ────────────────── Schedule helpers ──────────────────

def _every_weekday(weekday: int, start: date, end: date) -> list[date]:
    """Generate every occurrence of a weekday (0=Mon … 6=Sun) between start and end."""
    d = start
    # Advance to the first matching weekday
    while d.weekday() != weekday:
        d += timedelta(days=1)
    dates = []
    while d <= end:
        dates.append(d)
        d += timedelta(days=7)
    return dates


def _every_n_weeks(weekday: int, n: int, start: date, end: date,
                   even_weeks: bool | None = None) -> list[date]:
    """
    Generate weekday occurrences every N weeks.
    If even_weeks is True, only include ISO-even weeks.
    If even_weeks is False, only include ISO-odd weeks.
    """
    all_dates = _every_weekday(weekday, start, end)
    if even_weeks is None:
        # Simple every-N-weeks from the first occurrence
        return all_dates[::n]
    return [d for d in all_dates if (d.isocalendar()[1] % 2 == 0) == even_weeks]


def _nth_weekday_of_month(weekday: int, n: int, months: list[int],
                          year_start: int, year_end: int,
                          override: dict[tuple[int, int], int] | None = None) -> list[date]:
    """
    Generate the n-th occurrence of a weekday in specific months.
    n=1 → first, n=2 → second, etc.
    override: {(year, month): day} for specific date overrides.
    """
    dates = []
    for year in range(year_start, year_end + 1):
        for month in months:
            if override and (year, month) in override:
                dates.append(date(year, month, override[(year, month)]))
                continue
            # Find all occurrences of that weekday in the month
            cal = calendar.monthcalendar(year, month)
            occurrences = [week[weekday] for week in cal if week[weekday] != 0]
            if n < 0:
                # Negative n: count from end (-1 = last, -2 = second to last)
                idx = n
                if abs(idx) <= len(occurrences):
                    dates.append(date(year, month, occurrences[idx]))
            else:
                if n <= len(occurrences):
                    dates.append(date(year, month, occurrences[n - 1]))
    return dates


# ────────────────── Event definitions ──────────────────

RECURRING_EVENTS = [
    {
        "id": "stormb_braetspil",
        "event_name": "Brætspilsaften",
        "organizer": "Storm B Café",
        "ig_handle": "@stormbcafe",
        "location": "Storm B Café",
        "url": "https://www.instagram.com/p/DTfLNhGl5MA/",
        "start_time": "16:00",
        "end_time": None,
        "source": "stormbcafe",
        "schedule": {"type": "biweekly", "weekday": 3, "even_weeks": True},
        # Thursday (3), even ISO weeks
    },
    {
        "id": "flerefugle_fryday",
        "event_name": "Fry-Day",
        "organizer": "Flere Fugle",
        "ig_handle": "@flerefugle",
        "location": "Flere Fugle",
        "url": "https://www.instagram.com/p/DJHBK3Zi14I/",
        "start_time": "16:30",
        "end_time": None,
        "source": "flerefugle",
        "schedule": {"type": "weekly", "weekday": 4},
        # Friday (4)
    },
    {
        "id": "poolpub_happyhour",
        "event_name": "Happy Hour - 2 for 1 cocktail",
        "organizer": "Pool Pub",
        "ig_handle": "@poolpub_cph",
        "location": "Pool Pub",
        "url": "https://www.instagram.com/poolpub_cph/",
        "start_time": "15:00",
        "end_time": "01:00",
        "source": "poolpub_cph",
        "schedule": {"type": "weekly", "weekday": 3},
        # Thursday (3)
    },
    {
        "id": "stormb_happyhour_thu",
        "event_name": "Happy Hour at Storm B",
        "organizer": "Storm B Café",
        "ig_handle": "@stormbcafe",
        "location": "Storm B Café",
        "url": "https://www.instagram.com/p/DQdQxHsiuds",
        "start_time": "16:00",
        "end_time": "19:00",
        "source": "stormbcafe",
        "schedule": {"type": "weekly", "weekdays": [3, 4, 5]},
        # Thursday (3), Friday (4), Saturday (5)
    },
    {
        "id": "autopoul_rosetuesday",
        "event_name": "Rose Tuesday",
        "organizer": "Autopoul",
        "ig_handle": "@autopoul",
        "location": "Autopoul",
        "url": "https://www.instagram.com/autopoul/",
        "start_time": "12:00",
        "end_time": None,
        "source": "autopoul",
        "schedule": {
            "type": "weekly_seasonal",
            "weekday": 1,  # Tuesday
            "start_month": 4,  # April
            "end_month": 10,   # October
            "first_date": "2026-04-28",  # Specific start date
        },
    },
    {
        "id": "taca_socialrun",
        "event_name": "Taca Copenhagen Social Run for Men",
        "organizer": "Taca Copenhagen",
        "ig_handle": "@tacacopenhagen",
        "location": "Engsvinget 55",
        "url": "https://www.instagram.com/tacacopenhagen/",
        "start_time": "18:00",
        "end_time": None,
        "source": "tacacopenhagen",
        "schedule": {"type": "weekly", "weekday": 2},
        # Wednesday (2)
    },
    {
        "id": "tekno_supperclub",
        "event_name": "Tekno Supperclub",
        "organizer": "Tekno Eatery",
        "ig_handle": "@teknoeatery",
        "location": "Tekno Eatery",
        "url": "https://teknoeatery.dk/#supper",
        "start_time": "17:30",
        "end_time": "20:30",
        "source": "teknoeatery",
        "schedule": {"type": "weekly", "weekday": 3},
        # Thursday (3)
    },
    {
        "id": "daves_happyhour",
        "event_name": "Happy Hour at Dave's",
        "organizer": "Dave's",
        "ig_handle": "@davescph",
        "location": "Dave's",
        "url": "https://www.instagram.com/davescph",
        "start_time": "15:00",
        "end_time": "18:00",
        "source": "davescph",
        "schedule": {"type": "weekly", "weekday": 4},
        # Friday (4)
    },
    {
        "id": "makerspace_neighborsunday",
        "event_name": "Neighbor Sunday",
        "organizer": "MakerSpace NV",
        "ig_handle": "@makerspacenv",
        "location": "MakerSpace NV",
        "url": "https://www.facebook.com/MakerSpacenv/",
        "start_time": "12:00",
        "end_time": "15:00",
        "source": "makerspacenv",
        "schedule": {"type": "weekly", "weekday": 6},
        # Sunday (6)
    },
    {
        "id": "tagensbo_middag",
        "event_name": "Middag for alle",
        "organizer": "Tagensbo Kirke",
        "ig_handle": "@tagensbokirke",
        "location": "Tagensbo Kirke",
        "url": "https://www.tagensbo.dk/aktiviteter-i-kirken/middag-for-alle",
        "start_time": "17:30",
        "end_time": None,
        "source": "tagensbo kirke",
        "schedule": {
            "type": "monthly_weekday",
            "weekday": 4,  # Friday
            "nth": -1,     # Last Friday of the month
            "months": list(range(1, 13)),  # All year
        },
    },
    {
        "id": "makerspace_repaircafe",
        "event_name": "Repair Cafe",
        "organizer": "MakerSpace NV",
        "ig_handle": "@makerspacenv",
        "location": "MakerSpace NV",
        "url": "https://www.facebook.com/repaircafe.nordvest",
        "start_time": "17:00",
        "end_time": "19:30",
        "source": "makerspacenv",
        "schedule": {
            "type": "monthly_weekday",
            "weekday": 1,  # Tuesday
            "nth": 1,      # First Tuesday of the month
            "months": list(range(1, 13)),  # All year
        },
    },
    {
        "id": "kbhtrup_flea",
        "event_name": "Københavnstrup Flea Market",
        "organizer": "Københavns Trup",
        "ig_handle": "@kobenhavnstrup",
        "location": "Københavnstrup",
        "url": "https://www.instagram.com/kobenhavnstrup/",
        "start_time": "12:00",
        "end_time": "16:00",
        "source": "kobenhavnstrup",
        "schedule": {
            "type": "monthly_weekday",
            "weekday": 6,  # Sunday
            "nth": 1,      # First Sunday
            "months": [4, 5, 6, 7, 8, 9, 10],
            "override": {(2026, 4): 12},  # April 12 instead of April 5
        },
    },
]


# ────────────────── Generator ──────────────────

def generate_recurring_events(months_ahead: int = 6) -> list[dict]:
    """
    Generate all recurring event instances from today to months_ahead months.
    Returns a list of event dicts ready for Notion.
    """
    today = date.today()
    end = today + timedelta(days=months_ahead * 30)
    all_events: list[dict] = []

    for rec in RECURRING_EVENTS:
        sched = rec["schedule"]
        stype = sched["type"]
        dates: list[date] = []

        if stype == "weekly":
            if "weekdays" in sched:
                # Multiple weekdays (e.g. Thu+Fri+Sat)
                for wd in sched["weekdays"]:
                    dates.extend(_every_weekday(wd, today, end))
                dates.sort()
            else:
                dates = _every_weekday(sched["weekday"], today, end)

        elif stype == "biweekly":
            dates = _every_n_weeks(
                sched["weekday"], 2, today, end,
                even_weeks=sched.get("even_weeks"),
            )

        elif stype == "weekly_seasonal":
            first_date = date.fromisoformat(sched["first_date"])
            start = max(today, first_date)
            # Generate for the seasonal window in each year
            for year in range(today.year, end.year + 1):
                season_start = date(year, sched["start_month"], 1)
                season_end = date(year, sched["end_month"], 28)
                if season_end.month == 10:
                    season_end = date(year, 10, 31)
                # Respect first_date
                effective_start = max(start, season_start)
                effective_end = min(end, season_end)
                if effective_start <= effective_end:
                    dates.extend(_every_weekday(sched["weekday"], effective_start, effective_end))
            dates.sort()

        elif stype == "monthly_weekday":
            year_start = today.year
            year_end = end.year
            dates = _nth_weekday_of_month(
                sched["weekday"], sched["nth"],
                sched["months"], year_start, year_end,
                override=sched.get("override"),
            )
            dates = [d for d in dates if today <= d <= end]

        # Build event dicts
        for d in dates:
            # Convert time to 12h display format
            start_disp = _to_12h(rec.get("start_time"))
            end_disp = _to_12h(rec.get("end_time"))

            ev = {
                "event_name": rec["event_name"],
                "start_date": d.isoformat(),
                "start_time_disp": start_disp,
                "end_time_disp": end_disp,
                "location": rec.get("location", ""),
                "organizer": rec.get("organizer", ""),
                "source": rec.get("source", "recurring"),
                "source_type": "Recurring",
                "url": rec.get("url", ""),
                "ig_handle": rec.get("ig_handle", ""),
                "description": f"Recurring event: {rec['event_name']}",
                "recurring": True,
                "tag": classify_event(
                    rec["event_name"],
                    f"Recurring event: {rec['event_name']}",
                    rec.get("organizer", ""),
                ),
            }
            all_events.append(ev)

    return all_events


def _to_12h(time_str: str | None) -> str:
    """Convert HH:MM to 12h display format like '4:00pm'."""
    if not time_str:
        return ""
    try:
        parts = time_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        suffix = "am" if h < 12 else "pm"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d}{suffix}"
    except (ValueError, IndexError):
        return time_str


# ────────────────── Standalone test ──────────────────

if __name__ == "__main__":
    events = generate_recurring_events(6)
    print(f"Generated {len(events)} recurring event instances\n")

    # Group by event name
    from collections import Counter
    counts = Counter(ev["event_name"] for ev in events)
    for name, count in counts.most_common():
        print(f"  {count:4d}x  {name}")

    print()
    # Show first 3 per event type
    seen = {}
    for ev in events:
        n = ev["event_name"]
        if n not in seen:
            seen[n] = 0
        seen[n] += 1
        if seen[n] <= 3:
            print(f"  {ev['start_date']} | {ev.get('start_time_disp',''):>8} | {n}")
        elif seen[n] == 4:
            print(f"  ... and more")
