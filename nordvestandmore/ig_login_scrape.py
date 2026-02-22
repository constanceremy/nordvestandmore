#!/usr/bin/env python3
"""
IG Login Scrape — log in first, then scrape all Instagram accounts.

Usage:
    python ig_login_scrape.py              # scrape all accounts
    python ig_login_scrape.py 20           # scrape first 20 accounts
    python ig_login_scrape.py --from 50    # start from account #50
"""
import getpass
import os
import sys
import tempfile
import shutil
import time
import random
from pathlib import Path

# Load .env
env_file = Path(__file__).resolve().parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

os.environ.setdefault("DEBUG", "1")

# Import scraper module
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ig_scraper"))
import scrape_instagram_events as ig_mod


def main():
    if not os.environ.get("NOTION_TOKEN") or not os.environ.get("NOTION_DATABASE_ID"):
        sys.exit("Missing NOTION_TOKEN or NOTION_DATABASE_ID in .env")
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("Missing GEMINI_API_KEY in .env")

    accounts = ig_mod.load_accounts()
    if not accounts:
        sys.exit("No accounts found in accounts.txt")

    # Parse args
    start_from = 0
    limit = len(accounts)
    args = sys.argv[1:]
    if "--from" in args:
        idx = args.index("--from")
        start_from = int(args[idx + 1]) - 1  # 1-based to 0-based
        args = args[:idx] + args[idx + 2:]
    if args:
        limit = int(args[0])

    accounts = accounts[start_from:start_from + limit]
    print(f"📸 Will scrape {len(accounts)} IG accounts (starting from #{start_from + 1})")
    print()

    # Login first
    L = ig_mod.setup_instaloader()
    ig_username = os.environ.get("IG_USERNAME", "")
    if not ig_username:
        ig_username = input("IG username: ").strip()
    ig_password = getpass.getpass(f"IG password for {ig_username}: ")

    if not ig_password:
        sys.exit("No password provided")

    print(f"📸 Logging in as {ig_username}...")
    try:
        L.login(ig_username, ig_password)
        ig_mod._logged_in = True
        print("📸 Logged in ✅")
    except Exception as e:
        sys.exit(f"📸 Login failed: {e}")

    print()
    client = ig_mod.setup_gemini()
    existing, all_entries = ig_mod.notion_existing_entries()
    source_mapping = ig_mod.load_source_mapping()
    tmp_dir = tempfile.mkdtemp(prefix="ig_login_")

    total_created = 0
    total_events = 0
    total_posts = 0
    errors = []

    try:
        for idx, account in enumerate(accounts, 1):
            real_idx = start_from + idx
            print(f"  [{idx}/{len(accounts)}] @{account} (#{real_idx})...", end=" ", flush=True)
            stats = ig_mod.scrape_account(
                account, L, client,
                existing, all_entries, source_mapping, tmp_dir,
                auto_login_retry=False,
            )
            posts = stats.get("total_posts", 0)
            evts = stats.get("total_events", 0)
            created = stats.get("created", 0)
            total_posts += posts
            total_events += evts
            total_created += created

            if stats.get("error"):
                errors.append(account)
                print("❌ error")
            else:
                parts = [f"{posts} posts"]
                if evts:
                    parts.append(f"{evts} events")
                if created:
                    parts.append(f"{created} new")
                print(f"✅ {', '.join(parts)}")

            time.sleep(random.uniform(3, 6))

    except KeyboardInterrupt:
        print(f"\n\n⏹️  Stopped at account #{start_from + idx}")
        print(f"   Resume with: python ig_login_scrape.py --from {start_from + idx}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    print("═" * 50)
    print(f"✅ Done! {total_posts} posts, {total_events} events, {total_created} new")
    if errors:
        print(f"⚠️  {len(errors)} error(s): {', '.join(f'@{e}' for e in errors)}")
    print("═" * 50)


if __name__ == "__main__":
    main()
