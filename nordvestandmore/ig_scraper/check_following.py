#!/usr/bin/env python3
"""
Compare your Instagram following list with the scraper's source mapping.

Shows:
  - Accounts you follow on IG that are NOT in the source mapping (potential adds)
  - Accounts in the source mapping that you do NOT follow on IG (potential removes)

Usage:
    python3 check_following.py              # compare following vs sources
    python3 check_following.py --list       # just list who you follow

Requires: IG_USERNAME env var (or session file in ~/.config/instaloader/)
"""

import os
import sys
import time
from pathlib import Path

import instaloader

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)


def get_following(username: str) -> list[str]:
    """Fetch the list of accounts the given user follows."""
    L = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        post_metadata_txt_pattern="",
        request_timeout=30,
    )

    # Try to load session
    session_dir = Path.home() / ".config" / "instaloader"
    session_file = session_dir / f"session-{username}"

    if session_file.exists():
        try:
            L.load_session_from_file(username, str(session_file))
            print(f"✅ Loaded session for @{username}")
        except Exception as e:
            print(f"⚠️  Session file failed: {e}")
            sys.exit(1)
    else:
        # Try password login
        password = os.environ.get("IG_PASSWORD", "")
        if password:
            try:
                L.login(username, password)
                print(f"✅ Logged in as @{username}")
            except Exception as e:
                print(f"❌ Login failed: {e}")
                sys.exit(1)
        else:
            print("❌ No session file and no IG_PASSWORD — cannot fetch following list.")
            print(f"   Expected session at: {session_file}")
            sys.exit(1)

    # Fetch the profile
    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except Exception as e:
        print(f"❌ Could not load profile @{username}: {e}")
        sys.exit(1)

    following_count = profile.followees
    print(f"📋 @{username} follows {following_count} accounts. Fetching list...")

    following = []
    try:
        for i, followee in enumerate(profile.get_followees(), 1):
            following.append(followee.username.lower())
            if i % 50 == 0:
                print(f"   ...fetched {i}/{following_count}")
                time.sleep(1)  # Be gentle
    except Exception as e:
        print(f"⚠️  Error fetching followees (got {len(following)} so far): {e}")
        if not following:
            sys.exit(1)

    print(f"✅ Fetched {len(following)} accounts")
    return sorted(following)


def load_source_accounts() -> set[str]:
    """Load IG handles from the Google Sheet / source mapping."""
    from dedup import _load_csv_rows
    handles = set()
    for row in _load_csv_rows():
        ig = (row.get("instagram") or "").strip().lstrip("@").lower()
        if ig:
            handles.add(ig)
    return handles


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compare IG following with source mapping")
    parser.add_argument("--list", action="store_true", help="Just list who you follow")
    parser.add_argument("--username", default=os.environ.get("IG_USERNAME", ""),
                        help="IG username (default: $IG_USERNAME)")
    args = parser.parse_args()

    username = args.username
    if not username:
        print("❌ No username. Set IG_USERNAME env var or use --username")
        sys.exit(1)

    following = get_following(username)

    if args.list:
        print(f"\n📋 You follow {len(following)} accounts:\n")
        for handle in following:
            print(f"  @{handle}")
        return

    # Compare with source mapping
    source_accounts = load_source_accounts()
    following_set = set(following)

    not_in_sources = sorted(following_set - source_accounts)
    not_following = sorted(source_accounts - following_set)
    in_both = sorted(following_set & source_accounts)

    print(f"\n{'='*60}")
    print(f"📊 Comparison: IG following vs source mapping")
    print(f"{'='*60}")
    print(f"   You follow:        {len(following_set)} accounts")
    print(f"   In source mapping: {len(source_accounts)} accounts")
    print(f"   Overlap:           {len(in_both)} accounts")
    print()

    if not_in_sources:
        print(f"🆕 You follow these {len(not_in_sources)} accounts that are NOT in the scraper:")
        print(f"   (Consider adding them to the Google Sheet)")
        print()
        for handle in not_in_sources:
            print(f"   @{handle}")
        print()

    if not_following:
        print(f"👻 These {len(not_following)} accounts are in the scraper but you DON'T follow them:")
        print(f"   (These may be scraped via Facebook/website only, or you unfollowed them)")
        print()
        for handle in not_following:
            print(f"   @{handle}")
        print()

    if not not_in_sources and not not_following:
        print("🎉 Perfect sync! Your following list matches the source mapping exactly.")


if __name__ == "__main__":
    main()
