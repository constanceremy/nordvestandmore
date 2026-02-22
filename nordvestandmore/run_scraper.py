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
import sys
import tempfile
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAPPING_FILE = ROOT / "source_mapping.csv"
ENV_FILE = ROOT / ".env"


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

    # ── Determine what we need ──
    has_ig = any(r["instagram"] for r in selected)
    has_fb = any(r["facebook"] for r in selected)
    has_web = any(r["website"] for r in selected)

    # ── Login check: Facebook only (IG login deferred to retry phase) ──
    print()
    print("🔐 Login check...")

    # Facebook: check cookies
    fb_cookies_file = ROOT / "fb_scraper" / "fb_cookies.json"
    if has_fb:
        if fb_cookies_file.exists():
            print("  📘 Facebook: cookies found ✅")
        else:
            print("  📘 Facebook: no cookies found")
            if auto_mode:
                print("     ⏭️  Skipping FB login (auto mode)")
            else:
                ans = input("     Open browser to log in to Facebook? [y/N] ").strip().lower()
                if ans == "y":
                    fb_login_mod = import_module_from_file(
                        "fb_login", str(ROOT / "fb_scraper" / "fb_login.py"),
                    )
                    fb_login_mod.main()

    # Instagram: no login upfront — scrape public posts first, retry with login at end
    ig_L = ig_client = None
    if has_ig:
        ig_L = ig_mod.setup_instaloader()
        ig_client = ig_mod.setup_gemini()
        print("  📸 Instagram: will scrape without login first")

    print()

    # Load Notion entries once — build both IG-style and FB-style dedup indexes
    ig_existing, all_entries = ig_mod.notion_existing_entries()
    fb_existing: dict[str, str] = {}
    for entry in all_entries:
        url = entry.get("url", "")
        if url:
            fb_existing[url] = entry.get("page_id")
            # Also add compound keys for recurring event dedup (url##date##time)
            sd = entry.get("start_date", "")
            if sd:
                fb_existing[f"{url}##{sd}##"] = entry.get("page_id")
                # We don't have start_time in the entry, so we only index without it.
                # The recurring dedup will fall back to this no-time key.

    source_mapping = ig_mod.load_source_mapping()

    fb_to_ig: dict[str, str] = {}
    if has_fb:
        fb_to_ig = fb_mod.load_fb_to_ig_map()

    tmp_dir = tempfile.mkdtemp(prefix="scraper_") if has_ig else None

    # Track FB URLs already scraped (avoid re-scraping shared pages like Gamma/Gamma Brewing)
    scraped_fb_urls: set[str] = set()
    # Track IG accounts that need login retry (0 posts or errors)
    ig_retry_list: list[dict] = []   # [{"name": ..., "ig_handle": ...}, ...]

    totals = {"created": 0, "updated": 0, "skipped": 0, "flagged_dupes": 0, "total_events": 0}

    ig_count = sum(1 for r in selected if r["instagram"])
    fb_count = len({r["facebook"] for r in selected if r["facebook"]})
    web_count = sum(1 for r in selected if r["website"])

    print()
    print("═" * 50)
    print(f"  NordVest & More — Scraper Runner")
    print(f"  Selected: {len(selected)} source(s)")
    print(f"  Instagram: {ig_count} | Facebook: {fb_count} | Website: {web_count}")
    print("═" * 50)
    print()

    try:
        for idx, entity in enumerate(selected, 1):
            name = entity["name"]
            ig_handle = entity.get("instagram")
            fb_url_raw = entity.get("facebook")
            fb_filter = entity.get("fb_filter")
            fb_exclude = entity.get("fb_exclude")
            website_url = entity.get("website")

            print(f"━━━ [{idx}/{len(selected)}] {name} ━━━")

            # Show what platforms this entity has
            fb_label = "📘 FB" if fb_url_raw else "   FB —"
            ig_label = "📸 IG" if ig_handle else "   IG —"
            web_label = "🌐 Web" if website_url else "   Web —"
            print(f"  {fb_label}  |  {ig_label}  |  {web_label}")

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
                    print(f"  📘 Scraping FB: {fb_page_name}{filt_label}...")
                    stats = fb_mod.scrape_page_entry(
                        page_entry, None,
                        fb_existing, all_entries, source_mapping, fb_to_ig,
                    )
                    add_stats(totals, stats)
                    scraped_fb_urls.add(fb_url_raw)
                    ev_count = stats.get("total_events", 0)
                    fb_ok = f"✅ ({ev_count} event{'s' if ev_count != 1 else ''})"
                else:
                    fb_ok = "✅ (already scraped)"

            # ── Website (HTTP or Playwright depending on site) ──
            if website_url:
                site_key = name.lower()
                if site_key in web_mod.SITE_PARSERS:
                    print(f"  🌐 Scraping website: {website_url}...")
                    stats = web_mod.scrape_site(
                        site_key, fb_existing, all_entries,
                        source_mapping, ig_handle=ig_handle,
                    )
                    add_stats(totals, stats)
                    ev_count = stats.get("total_events", 0)
                    web_ok = f"✅ ({ev_count} event{'s' if ev_count != 1 else ''})"
                else:
                    web_ok = "⚠️ no parser"
                    print(f"  🌐 No parser for {name} — skipping website")

            # ── Instagram (NO login — first pass, public only) ──
            if ig_handle:
                print(f"  📸 Scraping IG: @{ig_handle} (no login)...")
                stats = ig_mod.scrape_account(
                    ig_handle, ig_L, ig_client,
                    ig_existing, all_entries, source_mapping, tmp_dir,
                    auto_login_retry=False,
                )
                add_stats(totals, stats)
                if stats.get("error"):
                    ig_ok = "⚠️ error (will retry with login)"
                    ig_retry_list.append({"name": name, "ig_handle": ig_handle})
                elif stats.get("needs_login"):
                    ig_ok = "⏳ 0 posts (will retry with login)"
                    ig_retry_list.append({"name": name, "ig_handle": ig_handle})
                else:
                    posts = stats.get("total_posts", 0)
                    evts = stats.get("total_events", 0)
                    created_ig = stats.get("created", 0)
                    dupes = stats.get("flagged_dupes", 0)
                    parts = [f"{posts} post{'s' if posts != 1 else ''}"]
                    if evts:
                        parts.append(f"{evts} event{'s' if evts != 1 else ''}")
                    if created_ig:
                        parts.append(f"{created_ig} new")
                    if dupes:
                        parts.append(f"{dupes} dupe{'s' if dupes != 1 else ''}")
                    ig_ok = f"✅ ({', '.join(parts)})"

            # Summary line
            parts = [f"📘 FB {fb_ok}", f"📸 IG {ig_ok}"]
            if website_url:
                parts.append(f"🌐 Web {web_ok}")
            print(f"  ✅ {name}  |  {'  |  '.join(parts)}")
            print()
            # Random delay between entities (3-6s) to avoid IG rate limits
            if ig_handle and idx < len(selected):
                delay = random.uniform(3, 6)
                time.sleep(delay)
            else:
                time.sleep(1)

        # ── Instagram retry phase (with login) ──
        if ig_retry_list:
            print()
            print("═" * 50)
            print(f"  🔄 Instagram retry — {len(ig_retry_list)} account(s) need login")
            handles = [r["ig_handle"] for r in ig_retry_list]
            print(f"     {', '.join(f'@{h}' for h in handles)}")
            print("═" * 50)
            print()

            ig_username = os.environ.get("IG_USERNAME", "")
            ig_password = os.environ.get("IG_PASSWORD", "")
            logged_in = False

            if ig_username:
                if ig_password:
                    print(f"  📸 Logging in as {ig_username}...")
                    try:
                        ig_L.login(ig_username, ig_password)
                        ig_mod._logged_in = True
                        logged_in = True
                        print(f"  📸 Logged in ✅")
                    except Exception as e:
                        print(f"  📸 Login failed ({e})")

                if not logged_in and not auto_mode:
                    pw = input("  📸 Enter IG password (or Enter to skip retry): ").strip()
                    if pw:
                        try:
                            ig_L.login(ig_username, pw)
                            ig_mod._logged_in = True
                            logged_in = True
                            print(f"  📸 Logged in ✅")
                        except Exception as e2:
                            print(f"  📸 Login failed ({e2}) — skipping retry")
                elif not logged_in:
                    print("  📸 Auto login failed — skipping retry (auto mode)")
            else:
                print("  📸 No IG_USERNAME in .env — skipping retry")

            if logged_in:
                print()
                for idx, retry in enumerate(ig_retry_list, 1):
                    name = retry["name"]
                    ig_handle = retry["ig_handle"]
                    print(f"  🔄 [{idx}/{len(ig_retry_list)}] Retrying @{ig_handle} ({name})...")
                    stats = ig_mod.scrape_account(
                        ig_handle, ig_L, ig_client,
                        ig_existing, all_entries, source_mapping, tmp_dir,
                        auto_login_retry=False,
                    )
                    add_stats(totals, stats)
                    if stats.get("error"):
                        print(f"     ⚠️ @{ig_handle}: still erroring — skipped")
                    else:
                        posts = stats.get("total_posts", 0)
                        evts = stats.get("total_events", 0)
                        created_ig = stats.get("created", 0)
                        dupes = stats.get("flagged_dupes", 0)
                        parts = [f"{posts} post{'s' if posts != 1 else ''}"]
                        if evts:
                            parts.append(f"{evts} event{'s' if evts != 1 else ''}")
                        if created_ig:
                            parts.append(f"{created_ig} new")
                        if dupes:
                            parts.append(f"{dupes} dupe{'s' if dupes != 1 else ''}")
                        print(f"     ✅ @{ig_handle}: {', '.join(parts)}")
                    time.sleep(random.uniform(3, 6))
            else:
                print("  ⏭️  Skipping retry — accounts with 0 posts were not re-scraped")

        # ── Recurring events ──
        print()
        print("═" * 50)
        print("  🔁 Generating recurring events...")
        print("═" * 50)
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
        print(f"  🔁 Recurring: {rec_created} created, {rec_updated} updated, {rec_skipped} errors")

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    print("═" * 50)
    print(f"  ✅ All done!")
    print(f"     Events found: {totals['total_events']}")
    print(f"     Created:      {totals['created']}")
    print(f"     Updated:      {totals['updated']}")
    print(f"     Skipped:      {totals['skipped']}")
    if totals["flagged_dupes"]:
        print(f"     ⚠️  Duplicates: {totals['flagged_dupes']}")
    if ig_retry_list and not ig_mod._logged_in:
        print(f"     ⚠️  {len(ig_retry_list)} IG account(s) had 0 posts (login needed)")
    print("═" * 50)


if __name__ == "__main__":
    main()
