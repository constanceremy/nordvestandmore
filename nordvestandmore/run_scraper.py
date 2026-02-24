#!/usr/bin/env python3
"""
Unified scraper runner — scrapes by entity (IG → FB for each source).

Usage:
    python run_scraper.py all                          # scrape everything
    python run_scraper.py "Gamma" "RORT Copenhagen"    # just these two
    python run_scraper.py --list                        # show available names
    python run_scraper.py all --from "Biblioteket Rentemestervej"  # resume from entity
    python run_scraper.py all --from 11                # resume from entity #11
    python run_scraper.py all --auto                   # non-interactive (for cron)

Reads source_mapping.csv as the single source of truth.
Loads .env once, sets up shared resources (Notion, Gemini, Instaloader)
once, then iterates entity-by-entity.
"""
import csv
import importlib.util
import os
import random
import requests
import sys
import tempfile
import shutil
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAPPING_FILE = ROOT / "source_mapping.csv"
ENV_FILE = ROOT / ".env"

_start_time = time.time()


def _elapsed() -> str:
    """Return elapsed time since script start as mm:ss."""
    s = int(time.time() - _start_time)
    return f"{s // 60}m{s % 60:02d}s"


def log(msg: str = ""):
    """Print with timestamp prefix."""
    print(f"[{_elapsed()}] {msg}")


# ────────────────── Helpers ──────────────────

def load_env():
    """Load .env into os.environ (before importing scraper modules)."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")
    os.environ.setdefault("DEBUG", "1")


def load_mapping() -> list[dict]:
    rows = []
    with open(MAPPING_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "name": (row.get("name") or "").strip(),
                "instagram": (row.get("instagram") or "").strip(),
                "facebook": (row.get("facebook") or "").strip(),
                "fb_filter": (row.get("fb_filter") or "").strip(),
                "fb_exclude": (row.get("fb_exclude") or "").strip(),
                "website": (row.get("website") or "").strip(),
            })
    return rows


def resolve_selections(all_rows: list[dict], args: list[str]) -> list[dict]:
    """Match user arguments (case-insensitive, partial match) to rows."""
    if not args or args[0].lower() == "all":
        return sorted(all_rows, key=lambda r: r["name"].lower())

    selected = []
    names_lower = {r["name"].lower(): r for r in all_rows}

    for arg in args:
        arg_l = arg.lower().strip()
        # Exact match first
        if arg_l in names_lower:
            selected.append(names_lower[arg_l])
            continue
        # Partial / substring match
        matches = [r for r in all_rows if arg_l in r["name"].lower()]
        if matches:
            selected.extend(matches)
        else:
            print(f"⚠️  No match for '{arg}' — skipping")

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for r in selected:
        key = (r["instagram"], r["facebook"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def import_module_from_file(name: str, path: str):
    """Import a Python file as a module by path."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def prepare_fb_url(url: str, fb_filter: str = "", fb_exclude: str = "") -> dict:
    """Ensure FB URL points to events page. Returns page_entry dict."""
    if "sk=events" in url or "/events" in url:
        pass  # already good
    elif "profile.php" in url:
        sep = "&" if "?" in url else "?"
        url = url + sep + "sk=events"
    else:
        url = url.rstrip("/") + "/events"
    return {"url": url, "filter": fb_filter or None, "exclude": fb_exclude or None}


def add_stats(totals: dict, stats: dict):
    for k in totals:
        totals[k] += stats.get(k, 0)


# ────────────────── Post-scrape dedup ──────────────────

def _post_scrape_dedup() -> int:
    """
    Re-fetch all Notion entries and delete exact duplicates
    (same name + date + URL + source). Keeps the oldest entry.
    Returns number of duplicates deleted.
    """
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
    NOTION_DB = os.environ.get("NOTION_DATABASE_ID", "")
    NOTION_API = "https://api.notion.com/v1"
    HEADERS = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # Fetch all entries
    entries = []
    payload: dict = {"page_size": 100}
    pages_fetched = 0
    while True:
        r = requests.post(
            f"{NOTION_API}/databases/{NOTION_DB}/query",
            headers=HEADERS, json=payload, timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            name_parts = props.get("Event Name", {}).get("title", [])
            name = name_parts[0]["text"]["content"] if name_parts else ""
            date_obj = props.get("Start Date", {}).get("date")
            start_date = date_obj["start"] if date_obj else ""
            url_val = props.get("Event Link", {}).get("url", "") or ""
            source_parts = props.get("Source", {}).get("rich_text", [])
            source = source_parts[0]["text"]["content"] if source_parts else ""
            entries.append({
                "page_id": page["id"],
                "name": name, "start_date": start_date,
                "url": url_val, "source": source,
                "created_time": page.get("created_time", ""),
            })
        pages_fetched += 1
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data.get("next_cursor")
        if pages_fetched >= 200:
            break

    # Group by (name, date, url, source) — find exact dupes
    groups: dict[tuple, list] = defaultdict(list)
    for entry in entries:
        key = (
            entry["name"].strip().lower(),
            entry["start_date"],
            entry["url"].strip().rstrip("/"),
            entry["source"].strip().lower(),
        )
        if key[0] and key[1]:
            groups[key].append(entry)

    to_delete = []
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        group.sort(key=lambda e: e["created_time"])
        to_delete.extend(group[1:])  # keep oldest

    if not to_delete:
        print("  ✅ No exact duplicates found")
        return 0

    print(f"  🗑️  Found {len(to_delete)} exact duplicate(s) — deleting...")
    deleted = 0
    for d in to_delete:
        resp = requests.patch(
            f"{NOTION_API}/pages/{d['page_id']}",
            headers=HEADERS,
            json={"archived": True},
            timeout=30,
        )
        if resp.status_code < 400:
            deleted += 1
        time.sleep(0.3)

    print(f"  ✅ Removed {deleted}/{len(to_delete)} duplicate(s)")
    return deleted


# ────────────────── Main ──────────────────

def main():
    if not MAPPING_FILE.exists():
        sys.exit(f"Missing {MAPPING_FILE}")

    all_rows = load_mapping()

    # ── --list mode ──
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        print(f"{'#':<5} {'Name':<40} {'IG':<30} {'FB':<5} {'Web'}")
        print("─" * 115)
        for idx, r in enumerate(sorted(all_rows, key=lambda r: r["name"].lower()), 1):
            ig = r["instagram"] or "—"
            fb = "✓" if r["facebook"] else "—"
            web = "✓" if r["website"] else "—"
            filt = f" (filter: {r['fb_filter']})" if r["fb_filter"] else ""
            if r.get("fb_exclude"):
                filt += f" (exclude: {r['fb_exclude']})"
            print(f"{idx:<5} {r['name']:<40} {ig:<30} {fb:<5} {web}{filt}")
        print(f"\n{len(all_rows)} sources total")
        return

    # ── Resolve selection ──
    args = sys.argv[1:] if len(sys.argv) > 1 else ["all"]

    # Handle --auto flag (non-interactive, for cron/scheduled runs)
    auto_mode = "--auto" in args
    if auto_mode:
        args.remove("--auto")

    # Handle --from flag (resume from a specific entity)
    start_from = None
    if "--from" in args:
        from_idx = args.index("--from")
        if from_idx + 1 < len(args):
            start_from = args[from_idx + 1]
            args = args[:from_idx] + args[from_idx + 2:]
        else:
            print("Error: --from requires a name or number")
            return

    selected = resolve_selections(all_rows, args)

    # Apply --from: skip entities before the specified one
    if start_from and selected:
        try:
            skip_to = int(start_from) - 1  # 1-based → 0-based index
            selected = selected[skip_to:]
            print(f"⏩ Resuming from #{skip_to + 1}: {selected[0]['name']}")
        except ValueError:
            # Match by name (case-insensitive partial match)
            found = False
            for i, ent in enumerate(selected):
                if start_from.lower() in ent["name"].lower():
                    selected = selected[i:]
                    print(f"⏩ Resuming from #{i + 1}: {selected[0]['name']}")
                    found = True
                    break
            if not found:
                print(f"Error: no entity matching '{start_from}' found")
                return

    if not selected:
        print("No sources selected. Use --list to see available names.")
        return

    # ── Load .env BEFORE importing scrapers (they read env at import time) ──
    load_env()

    log("Loading scraper modules...")
    t0 = time.time()

    # ── Import scraper modules ──
    ig_mod = import_module_from_file(
        "scrape_instagram_events",
        str(ROOT / "ig_scraper" / "scrape_instagram_events.py"),
    )
    fb_mod = import_module_from_file(
        "scrape_facebook_events",
        str(ROOT / "fb_scraper" / "scrape_facebook_events.py"),
    )
    web_mod = import_module_from_file(
        "scrape_website_events",
        str(ROOT / "web_scraper" / "scrape_website_events.py"),
    )
    log(f"Modules loaded in {time.time() - t0:.1f}s")

    # ── Determine what we need ──
    has_ig = any(r["instagram"] for r in selected)
    has_fb = any(r["facebook"] for r in selected)
    has_web = any(r["website"] for r in selected)

    # ── Login check ──
    print()
    log("🔐 Login check...")

    # Facebook: check cookies
    fb_cookies_file = ROOT / "fb_scraper" / "fb_cookies.json"
    if has_fb:
        if fb_cookies_file.exists():
            log("  📘 Facebook: cookies found ✅")
        else:
            log("  📘 Facebook: no cookies found ⚠️")
            if auto_mode:
                log("     ⏭️  Skipping FB login (auto mode)")
            else:
                ans = input("     Open browser to log in to Facebook? [y/N] ").strip().lower()
                if ans == "y":
                    fb_login_mod = import_module_from_file(
                        "fb_login", str(ROOT / "fb_scraper" / "fb_login.py"),
                    )
                    fb_login_mod.main()

    # Instagram: log in upfront if credentials are available (CI/data-center IPs
    # get aggressive 429s without login, blocking the entire scraper).
    ig_L = ig_client = None
    if has_ig:
        ig_username = os.environ.get("IG_USERNAME", "")
        ig_password = os.environ.get("IG_PASSWORD", "")
        login_first = bool(ig_username and ig_password)
        ig_L = ig_mod.setup_instaloader(login_first=login_first)
        ig_client = ig_mod.setup_gemini()
        if ig_mod._logged_in:
            log(f"  📸 Instagram: logged in as {ig_username} ✅")
        else:
            log("  📸 Instagram: will scrape without login (public posts only)")

    print()

    # Load Notion entries once — build both IG-style and FB-style dedup indexes
    log("Loading existing Notion entries for dedup...")
    t0 = time.time()
    ig_existing, all_entries = ig_mod.notion_existing_entries()
    log(f"Loaded {len(all_entries)} existing entries in {time.time() - t0:.1f}s")

    fb_existing: dict[str, str] = {}
    for entry in all_entries:
        url = entry.get("url", "")
        if url:
            fb_existing[url] = entry.get("page_id")
            # Also add compound keys for recurring event dedup (url##date##time)
            sd = entry.get("start_date", "")
            if sd:
                fb_existing[f"{url}##{sd}##"] = entry.get("page_id")
                fb_existing[f"{url}##{sd}"] = entry.get("page_id")  # without trailing ##

    source_mapping = ig_mod.load_source_mapping()

    fb_to_ig: dict[str, str] = {}
    if has_fb:
        fb_to_ig = fb_mod.load_fb_to_ig_map()

    tmp_dir = tempfile.mkdtemp(prefix="scraper_") if has_ig else None

    # Track FB URLs already scraped (avoid re-scraping shared pages like Gamma/Gamma Brewing)
    scraped_fb_urls: set[str] = set()
    # Track IG accounts that need login retry (0 posts or errors)
    ig_retry_list: list[dict] = []   # [{"name": ..., "ig_handle": ..., "reason": ...}]
    # Track errors/warnings for the final report
    errors_log: list[str] = []

    totals = {"created": 0, "updated": 0, "skipped": 0, "flagged_dupes": 0, "total_events": 0}

    ig_count = sum(1 for r in selected if r["instagram"])
    fb_count = len({r["facebook"] for r in selected if r["facebook"]})
    web_count = sum(1 for r in selected if r["website"])

    print()
    print("═" * 60)
    log(f"NordVest & More — Scraper Runner")
    log(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Selected: {len(selected)} source(s)")
    log(f"  Instagram: {ig_count} | Facebook: {fb_count} | Website: {web_count}")
    log(f"  Existing Notion entries: {len(all_entries)}")
    log(f"  IG logged in: {'Yes' if ig_mod._logged_in else 'No'}")
    log(f"  FB cookies: {'Yes' if fb_cookies_file.exists() else 'No'}")
    print("═" * 60)
    print()

    try:
        for idx, entity in enumerate(selected, 1):
            entity_start = time.time()
            name = entity["name"]
            ig_handle = entity.get("instagram")
            fb_url_raw = entity.get("facebook")
            fb_filter = entity.get("fb_filter")
            fb_exclude = entity.get("fb_exclude")
            website_url = entity.get("website")

            # Show what platforms this entity has
            platforms = []
            if fb_url_raw:
                platforms.append("FB")
            if ig_handle:
                platforms.append(f"IG @{ig_handle}")
            if website_url:
                platforms.append("Web")
            log(f"━━━ [{idx}/{len(selected)}] {name}  ({' + '.join(platforms) or 'no platforms'}) ━━━")

            fb_ok = "—"
            ig_ok = "—"
            web_ok = "—"

            # ── Facebook first (richer structured data: dates, times, locations) ──
            if fb_url_raw:
                if fb_url_raw not in scraped_fb_urls:
                    page_entry = prepare_fb_url(fb_url_raw, fb_filter, fb_exclude)
                    fb_page_name = fb_mod.extract_page_name(page_entry["url"])
                    filt_label = f" (filter: {fb_filter})" if fb_filter else ""
                    if fb_exclude:
                        filt_label += f" (exclude: {fb_exclude})"
                    log(f"  📘 Scraping FB: {fb_page_name}{filt_label}...")
                    t0 = time.time()
                    try:
                        stats = fb_mod.scrape_page_entry(
                            page_entry, None,
                            fb_existing, all_entries, source_mapping, fb_to_ig,
                        )
                        add_stats(totals, stats)
                        scraped_fb_urls.add(fb_url_raw)
                        ev_count = stats.get("total_events", 0)
                        cr = stats.get("created", 0)
                        fb_ok = f"✅ {ev_count} events ({cr} new) in {time.time() - t0:.1f}s"
                    except Exception as e:
                        fb_ok = f"❌ error: {e}"
                        errors_log.append(f"FB {name}: {e}")
                        log(f"  📘 FB error for {name}: {e}")
                else:
                    fb_ok = "✅ (already scraped)"

            # ── Website (HTTP or Playwright depending on site) ──
            if website_url:
                site_key = name.lower()
                if site_key in web_mod.SITE_PARSERS:
                    log(f"  🌐 Scraping website: {website_url}...")
                    t0 = time.time()
                    try:
                        stats = web_mod.scrape_site(
                            site_key, fb_existing, all_entries,
                            source_mapping, ig_handle=ig_handle,
                        )
                        add_stats(totals, stats)
                        ev_count = stats.get("total_events", 0)
                        cr = stats.get("created", 0)
                        web_ok = f"✅ {ev_count} events ({cr} new) in {time.time() - t0:.1f}s"
                    except Exception as e:
                        web_ok = f"❌ error: {e}"
                        errors_log.append(f"Web {name}: {e}")
                        log(f"  🌐 Web error for {name}: {e}")
                else:
                    web_ok = "⏭️ no parser"

            # ── Instagram ──
            if ig_handle:
                login_label = "logged in" if ig_mod._logged_in else "no login"
                log(f"  📸 Scraping IG: @{ig_handle} ({login_label})...")
                t0 = time.time()
                stats = ig_mod.scrape_account(
                    ig_handle, ig_L, ig_client,
                    ig_existing, all_entries, source_mapping, tmp_dir,
                    auto_login_retry=False,
                )
                ig_duration = time.time() - t0
                add_stats(totals, stats)
                if stats.get("error"):
                    reason = "rate-limited (429)" if ig_duration < 5 else "error"
                    ig_ok = f"⚠️ {reason} — will retry"
                    ig_retry_list.append({"name": name, "ig_handle": ig_handle, "reason": reason})
                    errors_log.append(f"IG @{ig_handle}: {reason}")
                elif stats.get("needs_login"):
                    ig_ok = "⏳ 0 posts — will retry with login"
                    ig_retry_list.append({"name": name, "ig_handle": ig_handle, "reason": "0 posts"})
                else:
                    posts = stats.get("total_posts", 0)
                    evts = stats.get("total_events", 0)
                    created_ig = stats.get("created", 0)
                    dupes = stats.get("flagged_dupes", 0)
                    parts = [f"{posts} posts", f"{evts} events", f"{created_ig} new"]
                    if dupes:
                        parts.append(f"{dupes} dupes")
                    ig_ok = f"✅ {', '.join(parts)} in {ig_duration:.1f}s"

            # Summary line for this entity
            entity_time = time.time() - entity_start
            summary_parts = []
            if fb_url_raw:
                summary_parts.append(f"📘 {fb_ok}")
            if website_url:
                summary_parts.append(f"🌐 {web_ok}")
            if ig_handle:
                summary_parts.append(f"📸 {ig_ok}")
            log(f"  Done: {' | '.join(summary_parts)}  [{entity_time:.0f}s]")

            # Running totals every 10 entities
            if idx % 10 == 0:
                log(f"  ── Progress: {idx}/{len(selected)} entities | "
                    f"{totals['created']} created, {totals['updated']} updated, "
                    f"{totals['total_events']} events found ──")

            print()
            # Random delay between entities (3-6s) to avoid IG rate limits
            if ig_handle and idx < len(selected):
                delay = random.uniform(3, 6)
                time.sleep(delay)
            else:
                time.sleep(1)

        # ── Instagram retry phase ──
        if ig_retry_list:
            print()
            print("═" * 60)
            log(f"🔄 Instagram retry — {len(ig_retry_list)} account(s) failed")
            for r in ig_retry_list:
                log(f"   @{r['ig_handle']} ({r['name']}): {r.get('reason', 'unknown')}")
            print("═" * 60)
            print()

            logged_in = ig_mod._logged_in

            # If not already logged in, try now
            if not logged_in:
                ig_username = os.environ.get("IG_USERNAME", "")
                ig_password = os.environ.get("IG_PASSWORD", "")

                if ig_username:
                    if ig_password:
                        log(f"  📸 Logging in as {ig_username}...")
                        try:
                            ig_L.login(ig_username, ig_password)
                            ig_mod._logged_in = True
                            logged_in = True
                            log(f"  📸 Logged in ✅")
                        except Exception as e:
                            log(f"  📸 Login failed ({e})")

                    if not logged_in and not auto_mode:
                        pw = input("  📸 Enter IG password (or Enter to skip retry): ").strip()
                        if pw:
                            try:
                                ig_L.login(ig_username, pw)
                                ig_mod._logged_in = True
                                logged_in = True
                                log(f"  📸 Logged in ✅")
                            except Exception as e2:
                                log(f"  📸 Login failed ({e2}) — skipping retry")
                    elif not logged_in:
                        log("  📸 Auto login failed — skipping retry (auto mode)")
                else:
                    log("  📸 No IG_USERNAME in .env — skipping retry")
            else:
                # Already logged in but still got errors — wait a bit then retry
                log("  📸 Already logged in — waiting 60s before retry (rate limit cooldown)...")
                time.sleep(60)

            retry_recovered = 0
            retry_failed = 0
            if logged_in:
                print()
                for idx, retry in enumerate(ig_retry_list, 1):
                    name = retry["name"]
                    ig_handle = retry["ig_handle"]
                    log(f"  🔄 [{idx}/{len(ig_retry_list)}] Retrying @{ig_handle} ({name})...")
                    t0 = time.time()
                    stats = ig_mod.scrape_account(
                        ig_handle, ig_L, ig_client,
                        ig_existing, all_entries, source_mapping, tmp_dir,
                        auto_login_retry=False,
                    )
                    add_stats(totals, stats)
                    if stats.get("error"):
                        log(f"     ⚠️ @{ig_handle}: still erroring after {time.time() - t0:.1f}s — skipped")
                        retry_failed += 1
                    else:
                        posts = stats.get("total_posts", 0)
                        evts = stats.get("total_events", 0)
                        created_ig = stats.get("created", 0)
                        log(f"     ✅ @{ig_handle}: {posts} posts, {evts} events, {created_ig} new in {time.time() - t0:.1f}s")
                        retry_recovered += 1
                    time.sleep(random.uniform(3, 6))
                log(f"  Retry results: {retry_recovered} recovered, {retry_failed} still failing")
            else:
                log("  ⏭️  Skipping retry — no login available")
                retry_failed = len(ig_retry_list)

        # ── Recurring events ──
        print()
        print("═" * 60)
        log("🔁 Generating recurring events...")
        print("═" * 60)
        print()

        from recurring_events import generate_recurring_events
        rec_events = generate_recurring_events(months_ahead=6)
        rec_created = 0
        rec_updated = 0
        rec_skipped = 0

        # Group by source for neat output
        from collections import defaultdict
        rec_by_source: dict[str, list] = defaultdict(list)
        for ev in rec_events:
            rec_by_source[ev.get("source", "recurring")].append(ev)

        for source_key, evts in rec_by_source.items():
            first = evts[0]
            print(f"  🔁 {first['event_name']} ({source_key}): {len(evts)} instance(s)")

            for ev in evts:
                dedup_key = f"{ev['url']}##{ev['start_date']}##{ev.get('start_time_disp', '')}"

                page_id = fb_existing.get(dedup_key)
                if not page_id:
                    # Also try without time
                    dedup_key_no_time = f"{ev['url']}##{ev['start_date']}##"
                    page_id = fb_existing.get(dedup_key_no_time)

                try:
                    if page_id:
                        resp = web_mod.notion_update(page_id, ev)
                        if resp.status_code == 429:
                            time.sleep(1.5)
                            resp = web_mod.notion_update(page_id, ev)
                        rec_updated += 1
                    else:
                        resp = web_mod.notion_create(ev)
                        if resp.status_code == 429:
                            time.sleep(1.5)
                            resp = web_mod.notion_create(ev)
                        if resp.status_code < 400:
                            try:
                                new_id = resp.json().get("id")
                                if new_id:
                                    fb_existing[dedup_key] = new_id
                            except Exception:
                                pass
                            rec_created += 1
                        else:
                            rec_skipped += 1
                except Exception as e:
                    print(f"     ⚠️ Notion error for {ev['event_name']} {ev['start_date']}: {e}")
                    rec_skipped += 1
                    time.sleep(2)

                time.sleep(0.2)

            print(f"     ✅ {first['event_name']}: {len(evts)} dates")

        totals["created"] += rec_created
        totals["updated"] += rec_updated
        totals["total_events"] += len(rec_events)

        print()
        log(f"🔁 Recurring: {rec_created} created, {rec_updated} updated, {rec_skipped} errors")

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Post-scrape dedup: remove exact duplicates ──
    print()
    print("═" * 60)
    log("🧹 Post-scrape dedup — checking for exact duplicates...")
    print("═" * 60)
    t0 = time.time()
    dedup_deleted = _post_scrape_dedup()
    log(f"Dedup completed in {time.time() - t0:.1f}s")
    if dedup_deleted:
        totals["dedup_deleted"] = dedup_deleted

    # ── Final report ──
    total_time = time.time() - _start_time
    total_min = int(total_time) // 60
    total_sec = int(total_time) % 60

    print()
    print("═" * 60)
    log(f"✅ FINISHED in {total_min}m {total_sec}s")
    print("═" * 60)
    log(f"  Events found:    {totals['total_events']}")
    log(f"  Created:         {totals['created']}")
    log(f"  Updated:         {totals['updated']}")
    log(f"  Skipped:         {totals['skipped']}")
    if totals.get("dedup_deleted"):
        log(f"  🧹 Deduped:      {totals['dedup_deleted']}")
    if totals["flagged_dupes"]:
        log(f"  ⚠️  Possible dupes: {totals['flagged_dupes']}")
    if ig_retry_list:
        log(f"  ⚠️  IG retries:   {len(ig_retry_list)} accounts needed retry")
        for r in ig_retry_list:
            log(f"       @{r['ig_handle']}: {r.get('reason', '?')}")

    if errors_log:
        print()
        log(f"⚠️  ERRORS/WARNINGS ({len(errors_log)}):")
        for err in errors_log:
            log(f"  • {err}")

    # ── Write summary file (for GitHub Actions job summary + manual retry) ──
    summary_lines = []
    summary_lines.append(f"# Scraper Run Summary")
    summary_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append(f"**Duration:** {total_min}m {total_sec}s")
    summary_lines.append(f"**Sources:** {len(selected)}")
    summary_lines.append("")
    summary_lines.append("## Results")
    summary_lines.append(f"| Metric | Count |")
    summary_lines.append(f"|--------|-------|")
    summary_lines.append(f"| Events found | {totals['total_events']} |")
    summary_lines.append(f"| Created | {totals['created']} |")
    summary_lines.append(f"| Updated | {totals['updated']} |")
    summary_lines.append(f"| Skipped | {totals['skipped']} |")
    if totals.get("dedup_deleted"):
        summary_lines.append(f"| Deduped | {totals['dedup_deleted']} |")
    if totals["flagged_dupes"]:
        summary_lines.append(f"| Possible duplicates | {totals['flagged_dupes']} |")

    # Failed IG accounts
    failed_ig = [r for r in ig_retry_list]
    if failed_ig:
        summary_lines.append("")
        summary_lines.append(f"## ⚠️ Failed Instagram accounts ({len(failed_ig)})")
        summary_lines.append("These accounts could not be scraped (rate-limited or errored):")
        summary_lines.append("")
        for r in failed_ig:
            summary_lines.append(f"- `@{r['ig_handle']}` ({r['name']}): {r.get('reason', '?')}")

        # Build a ready-to-use manual retry command
        failed_names = [f'"{r["name"]}"' for r in failed_ig]
        summary_lines.append("")
        summary_lines.append("### Manual retry command")
        summary_lines.append("Run this locally to scrape just the failed accounts:")
        summary_lines.append("```bash")
        summary_lines.append(f"cd nordvestandmore && python3 run_scraper.py {' '.join(failed_names)}")
        summary_lines.append("```")

    if errors_log:
        summary_lines.append("")
        summary_lines.append(f"## Errors & Warnings")
        for err in errors_log:
            summary_lines.append(f"- {err}")

    summary_text = "\n".join(summary_lines)

    # Write to file (GitHub Action will pick this up)
    summary_file = ROOT / "scraper_summary.md"
    summary_file.write_text(summary_text, encoding="utf-8")
    log(f"Summary written to {summary_file.name}")

    # Also write directly to GitHub Actions step summary if available
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a", encoding="utf-8") as f:
            f.write(summary_text + "\n")
        log("Summary posted to GitHub Actions job summary")

    print("═" * 60)


if __name__ == "__main__":
    main()
