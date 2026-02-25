#!/usr/bin/env python3
"""
Drip-feed Instagram scraper
----------------------------
Runs via GitHub Actions cron (every ~60 min), scraping a small batch
of accounts each time.  A state file tracks the cursor position AND
accumulated failures, so each run picks up where the last one left off.

Over ~30 hours, all accounts get covered without hitting IG rate limits.

Usage:
    python3 drip_scrape.py                 # scrape next 5 accounts
    python3 drip_scrape.py --batch-size 3  # scrape next 3
    python3 drip_scrape.py --list          # just print next batch
    python3 drip_scrape.py --status        # show cursor + failures
    python3 drip_scrape.py --daily-report  # output daily digest & reset failures
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
ACCOUNTS_FILE = os.path.join(SCRIPT_DIR, "accounts.txt")

# Add parent dir so we can import dedup
sys.path.insert(0, PARENT_DIR)

# State file — persisted across runs via GitHub Actions cache
# Also accepts legacy IG_CURSOR_FILE for backwards compatibility
STATE_FILE = os.environ.get("IG_STATE_FILE",
             os.environ.get("IG_CURSOR_FILE", "/tmp/ig_cursor/state.json"))

# Summary file — written for GitHub Actions step summary
SUMMARY_FILE = os.environ.get("GITHUB_STEP_SUMMARY", "")

BATCH_SIZE_DEFAULT = 3
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")


# ── Notifications ──

def _ntfy(title: str, message: str, priority: str = "low", tags: str = "camera"):
    """Send a push notification via ntfy.sh (non-blocking, best-effort)."""
    if not NTFY_TOPIC:
        return
    try:
        import subprocess
        subprocess.run([
            "curl", "-s",
            "-H", f"Title: {title}",
            "-H", f"Priority: {priority}",
            "-H", f"Tags: {tags}",
            "-d", message,
            f"https://ntfy.sh/{NTFY_TOPIC}",
        ], timeout=10, check=False,
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ── State management ──

def _default_state() -> dict:
    return {
        "cursor": 0,
        "failures": {},       # {"handle": {"reason": "...", "time": "..."}}
        "successes": 0,
        "total_scraped": 0,
        "last_reset": datetime.now(timezone.utc).isoformat(),
    }


def load_state() -> dict:
    """Load state from file, or return defaults."""
    try:
        data = json.loads(Path(STATE_FILE).read_text())
        # Ensure all expected keys exist
        for k, v in _default_state().items():
            data.setdefault(k, v)
        return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return _default_state()


def save_state(state: dict):
    """Save state for the next run."""
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))


# ── Accounts ──

def load_accounts() -> tuple[list[str], dict[str, str]]:
    """Load account handles and priorities from Google Sheets (via dedup),
    falling back to accounts.txt.

    Returns: (accounts_list, priority_map)
        - accounts_list: list of IG handles (no @)
        - priority_map: {handle: "high"|"medium"|"low"}
    """
    priorities: dict[str, str] = {}

    # Try Google Sheets via dedup._load_csv_rows
    try:
        from dedup import _load_csv_rows
        rows = _load_csv_rows()
        accounts = []
        for row in rows:
            ig = (row.get("instagram") or "").strip().lstrip("@")
            if ig:
                accounts.append(ig)
                prio = (row.get("priority") or "").strip().lower()
                if prio in ("high", "medium", "low"):
                    priorities[ig] = prio
                else:
                    priorities[ig] = "medium"
        if accounts:
            return accounts, priorities
    except Exception as e:
        print(f"⚠️  Could not load from Google Sheets: {e}")

    # Fallback to accounts.txt
    accounts = []
    with open(ACCOUNTS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                handle = line.lstrip("@")
                accounts.append(handle)
                priorities[handle] = "medium"
    return accounts, priorities


def get_batch(state: dict, batch_size: int = BATCH_SIZE_DEFAULT) -> tuple[list[str], int]:
    """Get the next batch of accounts starting from the cursor.

    High-priority accounts are always included in every batch.
    Remaining slots are filled with medium/low accounts from the cursor.
    Low accounts are only scraped every 3rd cycle.

    Returns: (batch, new_cursor)
    """
    all_accounts, priorities = load_accounts()
    if not all_accounts:
        return [], 0

    # Separate high-priority accounts (always scraped)
    high = [a for a in all_accounts if priorities.get(a) == "high"]

    # Regular accounts (medium + low) for cursor-based rotation
    regular = [a for a in all_accounts if priorities.get(a) != "high"]
    N = len(regular)
    if N == 0:
        return high[:batch_size], 0

    # Low-priority accounts only scraped every 3rd full cycle
    cycle_num = state.get("cursor", 0) // N if N else 0
    skip_low = (cycle_num % 3) != 0

    start = state["cursor"] % N
    remaining_slots = max(0, batch_size - len(high))

    batch = list(high)  # Always include high-priority
    cursor_advance = 0
    checked = 0
    while len(batch) < batch_size and checked < N:
        idx = (start + checked) % N
        account = regular[idx]
        checked += 1
        cursor_advance += 1

        if skip_low and priorities.get(account) == "low":
            continue
        batch.append(account)

    new_cursor = (start + cursor_advance) % N
    return batch, new_cursor


# ── Summary output ──

def write_summary(lines: list[str]):
    """Write markdown summary to GitHub Actions step summary."""
    if not SUMMARY_FILE:
        return
    try:
        with open(SUMMARY_FILE, "a") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass  # non-critical


def format_run_summary(batch: list[str], results: dict[str, dict], state: dict) -> list[str]:
    """Format a per-run markdown summary."""
    all_accounts, _ = load_accounts()
    lines = []
    lines.append("## 📸 Instagram Drip Scraper")
    lines.append("")

    succeeded = [a for a, r in results.items() if r["ok"]]
    failed = [a for a, r in results.items() if not r["ok"]]

    lines.append(f"**Batch:** accounts {state['cursor'] - len(batch) + 1}–"
                 f"{state['cursor']} of {len(all_accounts)}")
    lines.append("")

    if succeeded:
        lines.append(f"### ✅ Succeeded ({len(succeeded)})")
        for a in succeeded:
            r = results[a]
            lines.append(f"- `@{a}`: {r.get('posts', 0)} posts, "
                         f"{r.get('events', 0)} events, {r.get('created', 0)} new")

    if failed:
        lines.append(f"### ⚠️ Failed ({len(failed)})")
        for a in failed:
            r = results[a]
            lines.append(f"- `@{a}`: {r.get('reason', 'unknown error')}")

    # Accumulated failures across runs
    total_failures = len(state.get("failures", {}))
    if total_failures > 0:
        lines.append("")
        lines.append(f"### 📊 Accumulated failures: {total_failures} accounts since last reset")

    return lines


# ── Daily report ──

def daily_report():
    """Generate a daily digest of failures and reset the counter."""
    state = load_state()
    all_accounts, _ = load_accounts()
    failures = state.get("failures", {})
    successes = state.get("successes", 0)
    total = state.get("total_scraped", 0)
    last_reset = state.get("last_reset", "unknown")

    print(f"📊 Instagram Drip Scraper — Daily Report")
    print(f"   Period: since {last_reset}")
    print(f"   Accounts scraped: {total}")
    print(f"   Successes: {successes}")
    print(f"   Failures: {len(failures)}")
    print()

    lines = ["## 📊 Instagram Drip Scraper — Daily Digest", ""]
    lines.append(f"**Period:** since {last_reset}")
    lines.append(f"**Total accounts scraped:** {total}")
    lines.append(f"**Successes:** {successes} | **Failures:** {len(failures)}")
    lines.append("")

    if failures:
        print("   Failed accounts:")
        lines.append("### ⚠️ Failed accounts")
        lines.append("")
        for handle, info in sorted(failures.items()):
            reason = info.get("reason", "unknown")
            when = info.get("time", "?")
            line = f"- `@{handle}`: {reason} (at {when})"
            print(f"     @{handle}: {reason}")
            lines.append(line)

        # Build retry command
        failed_handles = sorted(failures.keys())
        lines.append("")
        lines.append("### Manual retry")
        lines.append("```bash")
        lines.append(f"cd nordvestandmore/ig_scraper && python3 scrape_instagram_events.py "
                      f"{' '.join(failed_handles)}")
        lines.append("```")

        print()
        print(f"   Manual retry:")
        print(f"   cd nordvestandmore/ig_scraper && python3 scrape_instagram_events.py "
              f"{' '.join(failed_handles)}")
    else:
        print("   🎉 No failures!")
        lines.append("### 🎉 All accounts scraped successfully!")

    # Not-yet-scraped this cycle
    scraped_this_cycle = set()
    # We can't easily track this without more state, so skip for now

    lines.append("")
    coverage = min(total, len(accounts))
    lines.append(f"**Coverage:** ~{coverage}/{len(accounts)} accounts")

    write_summary(lines)

    # Build ntfy message
    ntfy_topic = os.environ.get("NTFY_TOPIC", "")
    if ntfy_topic:
        import subprocess
        if failures:
            msg = (f"📸 IG Drip Daily Report\n"
                   f"Scraped: {total} | OK: {successes} | Failed: {len(failures)}\n"
                   f"Failed: {', '.join(f'@{h}' for h in sorted(failures.keys())[:10])}"
                   f"{'...' if len(failures) > 10 else ''}")
            priority = "default"
        else:
            msg = f"📸 IG Drip Daily Report\nAll {total} account scrapes succeeded! 🎉"
            priority = "min"

        try:
            subprocess.run([
                "curl", "-s",
                "-H", f"Title: IG Daily Report ({len(failures)} failures)",
                "-H", f"Priority: {priority}",
                "-H", "Tags: camera",
                "-d", msg,
                f"https://ntfy.sh/{ntfy_topic}",
            ], timeout=10, check=False)
        except Exception:
            pass

    # Reset counters for the next day
    state["failures"] = {}
    state["successes"] = 0
    state["total_scraped"] = 0
    state["last_reset"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print("\n   Counters reset for next cycle ✅")


# ── Main scraping logic ──

def _fmt_duration(secs: float) -> str:
    """Format seconds as 'Xm Ys' or 'Ys'."""
    if secs >= 60:
        return f"{int(secs // 60)}m {int(secs % 60)}s"
    return f"{secs:.1f}s"


def run_scrape(batch_size: int):
    """Scrape the next batch of accounts."""
    run_start = time.time()
    time_in_delays = 0.0  # Track time spent in deliberate delays
    time_in_retries = 0.0  # Track time spent in retry waits

    state = load_state()
    batch, new_cursor = get_batch(state, batch_size)

    if not batch:
        print("No accounts to scrape.")
        return

    all_accounts, _ = load_accounts()
    start_pos = state["cursor"] % len(all_accounts) if all_accounts else 0
    print(f"📸 Drip batch: accounts {start_pos + 1}–{start_pos + len(batch)} of {len(all_accounts)}")
    print(f"   Accounts: {', '.join(f'@{a}' for a in batch)}")

    # Notify: batch starting
    _ntfy(
        f"IG Drip: scraping {len(batch)} accounts",
        f"Accounts {start_pos + 1}–{start_pos + len(batch)} of {len(all_accounts)}\n"
        + ", ".join(f"@{a}" for a in batch),
    )

    # ── Import and set up the IG scraper ──
    sys.path.insert(0, SCRIPT_DIR)
    sys.path.insert(0, PARENT_DIR)

    import scrape_instagram_events as ig_mod

    ig_username = os.environ.get("IG_USERNAME", "")
    ig_password = os.environ.get("IG_PASSWORD", "")

    if not ig_mod.NOTION_TOKEN or not ig_mod.NOTION_DB:
        sys.exit("❌ Missing NOTION_TOKEN or NOTION_DATABASE_ID")
    if not ig_mod.GEMINI_API_KEY:
        sys.exit("❌ Missing GEMINI_API_KEY")

    # Try to load a pre-existing session file FIRST (avoids checkpoint challenges)
    session_dir = Path.home() / ".config" / "instaloader"
    session_file = session_dir / f"session-{ig_username}" if ig_username else None
    has_session = session_file and session_file.exists()

    # Create instaloader WITHOUT password login — we try the session file first
    L = ig_mod.setup_instaloader(login_first=False)

    # Step 1: Try session file (bootstrapped from local machine or cached from previous run)
    if has_session and ig_username:
        try:
            L.load_session_from_file(ig_username, str(session_file))
            ig_mod._logged_in = True
            print(f"📸 Loaded saved session for {ig_username} ✅")
        except Exception as e:
            print(f"📸 Session file exists but failed to load: {e}")

    # Step 2: Only try password login if session didn't work
    if not ig_mod._logged_in and ig_username and ig_password:
        print("📸 No session file — trying password login...")
        ig_mod.try_login(L)

    if ig_mod._logged_in:
        print(f"📸 Authenticated as {ig_username} ✅")
    else:
        print("📸 Scraping without login (public posts only)")
        print("   💡 To fix: run locally to create a session, base64-encode it,")
        print("   and add as IG_SESSION_B64 GitHub secret")

    # ── Load Notion data (can be slow with many entries) ──
    t_notion = time.time()
    client = ig_mod.setup_gemini()
    existing, all_entries = ig_mod.notion_existing_entries()
    source_mapping = ig_mod.load_source_mapping()
    notion_load_time = time.time() - t_notion
    print(f"⏱️  Notion + setup loaded in {_fmt_duration(notion_load_time)} ({len(all_entries)} entries)")

    import tempfile
    import shutil
    tmp_dir = tempfile.mkdtemp(prefix="ig_drip_")
    results: dict[str, dict] = {}

    try:
        for i, account in enumerate(batch, 1):
            print(f"\n[{i}/{len(batch)}] Scraping @{account}...")
            t0 = time.time()
            stats = ig_mod.scrape_account(
                account, L, client, existing, all_entries,
                source_mapping, tmp_dir, auto_login_retry=False,
            )
            duration = time.time() - t0

            posts = stats.get("total_posts", 0)
            evts = stats.get("total_events", 0)
            cr = stats.get("created", 0)
            profile_total = stats.get("profile_total", "?")
            latest_date = stats.get("latest_date")

            # If 0 posts while authenticated, retry once after a pause
            # (Instagram sometimes silently returns empty on soft rate limits)
            if posts == 0 and not stats.get("error") and ig_mod._logged_in:
                print(f"  🔄 0/{profile_total} posts — retrying in 30s...")
                time_in_retries += 30
                time.sleep(30)
                stats = ig_mod.scrape_account(
                    account, L, client, existing, all_entries,
                    source_mapping, tmp_dir, auto_login_retry=False,
                )
                duration = time.time() - t0
                posts = stats.get("total_posts", 0)
                evts = stats.get("total_events", 0)
                cr = stats.get("created", 0)
                profile_total = stats.get("profile_total", profile_total)
                latest_date = stats.get("latest_date", latest_date)

            # Format latest post date for display
            date_info = f", latest: {latest_date}" if latest_date else ""

            # Build a short status line for this account
            elapsed_total = _fmt_duration(time.time() - run_start)

            if stats.get("error"):
                reason = f"error after {duration:.1f}s"
                print(f"  ⚠️  @{account}: {reason}")
                results[account] = {"ok": False, "reason": reason}
                state["failures"][account] = {
                    "reason": reason,
                    "time": datetime.now(timezone.utc).strftime("%H:%M UTC"),
                }
                acct_status = f"❌ @{account}: {reason}"
            elif posts == 0:
                # Still 0 after retry — show profile total + latest post date
                # so we can tell if the account is genuinely quiet or rate-limited
                latest_str = f", latest: {latest_date}" if latest_date else ", latest: unknown (rate-limited?)"
                reason = f"0 recent / {profile_total} total posts{latest_str}"
                print(f"  ℹ️  @{account}: {reason} [{duration:.1f}s]")
                results[account] = {"ok": True, "posts": 0, "events": 0, "created": 0, "note": reason}
                state["successes"] += 1
                state["failures"].pop(account, None)
                acct_status = f"💤 @{account}: 0 recent posts"
            else:
                print(f"  ✅ @{account}: {posts}/{profile_total} posts{date_info}, {evts} events, {cr} new [{duration:.1f}s]")
                results[account] = {
                    "ok": True,
                    "posts": posts,
                    "events": evts,
                    "created": cr,
                }
                state["successes"] += 1
                # Clear from failures if it succeeded this time
                state["failures"].pop(account, None)
                acct_status = f"✅ @{account}: {posts} posts, {evts} events, {cr} new"

            # Per-account progress notification
            _ntfy(
                f"[{i}/{len(batch)}] {acct_status}",
                f"Elapsed: {elapsed_total}",
                priority="min",
            )

            state["total_scraped"] += 1

            if i < len(batch):
                # Be gentle with Instagram — 20s between accounts
                print(f"  ⏳ Waiting 20s before next account...")
                time_in_delays += 20
                time.sleep(20)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Update cursor
    state["cursor"] = new_cursor
    save_state(state)

    next_account = all_accounts[new_cursor] if all_accounts else "?"
    print(f"\n📸 Cursor saved: {new_cursor}/{len(all_accounts)} (next: @{next_account})")

    # Write step summary
    summary = format_run_summary(batch, results, state)
    write_summary(summary)

    # Print final stats + timing breakdown
    total_elapsed = time.time() - run_start
    time_scraping = total_elapsed - notion_load_time - time_in_delays - time_in_retries
    ok = sum(1 for r in results.values() if r["ok"])
    fail = sum(1 for r in results.values() if not r["ok"])
    print(f"\n📸 Batch done: {ok} succeeded, {fail} failed")
    print(f"   Accumulated failures today: {len(state.get('failures', {}))}")
    print(f"\n⏱️  Time breakdown (total {_fmt_duration(total_elapsed)}):")
    print(f"   Notion/setup loading: {_fmt_duration(notion_load_time)}")
    print(f"   Scraping + Gemini:    {_fmt_duration(time_scraping)}")
    print(f"   Delays (20s × {len(batch)-1}):    {_fmt_duration(time_in_delays)}")
    if time_in_retries > 0:
        print(f"   Retry waits (30s):    {_fmt_duration(time_in_retries)}")

    # Completion notification
    created_total = sum(r.get("created", 0) for r in results.values() if r.get("ok"))
    events_total = sum(r.get("events", 0) for r in results.values() if r.get("ok"))
    completion_msg = (
        f"✅ {ok} ok, ❌ {fail} failed | {_fmt_duration(total_elapsed)}\n"
        f"Events: {events_total} found, {created_total} new\n"
        f"Notion: {_fmt_duration(notion_load_time)} | Scrape: {_fmt_duration(time_scraping)} | Delays: {_fmt_duration(time_in_delays)}"
    )
    _ntfy(
        f"IG Drip done: {ok}/{len(batch)} ok in {_fmt_duration(total_elapsed)}",
        completion_msg,
        priority="low" if fail == 0 else "default",
        tags="camera,white_check_mark" if fail == 0 else "camera,warning",
    )

    if fail:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Drip-feed IG scraper")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT,
                        help=f"Accounts per run (default: {BATCH_SIZE_DEFAULT})")
    parser.add_argument("--list", action="store_true",
                        help="Just print the batch, don't scrape")
    parser.add_argument("--status", action="store_true",
                        help="Show cursor position and failures")
    parser.add_argument("--daily-report", action="store_true",
                        help="Output daily digest and reset failure counters")
    args = parser.parse_args()

    if args.daily_report:
        daily_report()
        return

    all_accounts, priorities = load_accounts()
    state = load_state()

    if args.status:
        cursor = state["cursor"] % len(all_accounts) if all_accounts else 0
        failures = state.get("failures", {})
        high_count = sum(1 for p in priorities.values() if p == "high")
        low_count = sum(1 for p in priorities.values() if p == "low")
        print(f"📸 Cursor: {cursor}/{len(all_accounts)} ({high_count} high, {low_count} low)")
        print(f"   Next: @{all_accounts[cursor]}")
        print(f"   Scraped this cycle: {state.get('total_scraped', 0)}")
        print(f"   Successes: {state.get('successes', 0)}")
        print(f"   Failures: {len(failures)}")
        if failures:
            for h, info in sorted(failures.items()):
                print(f"     @{h}: {info.get('reason', '?')}")
        print(f"   Last reset: {state.get('last_reset', '?')}")
        return

    if args.list:
        batch, _ = get_batch(state, args.batch_size)
        print(f"Next batch ({len(batch)}): {', '.join(f'@{a}' for a in batch)}")
        return

    run_scrape(args.batch_size)


if __name__ == "__main__":
    main()
