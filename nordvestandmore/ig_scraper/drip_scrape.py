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

# State file — persisted across runs via GitHub Actions cache
# Also accepts legacy IG_CURSOR_FILE for backwards compatibility
STATE_FILE = os.environ.get("IG_STATE_FILE",
             os.environ.get("IG_CURSOR_FILE", "/tmp/ig_cursor/state.json"))

# Summary file — written for GitHub Actions step summary
SUMMARY_FILE = os.environ.get("GITHUB_STEP_SUMMARY", "")

BATCH_SIZE_DEFAULT = 5


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

def load_accounts() -> list[str]:
    """Load account handles from accounts.txt."""
    accounts = []
    with open(ACCOUNTS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                accounts.append(line.lstrip("@"))
    return accounts


def get_batch(state: dict, batch_size: int = BATCH_SIZE_DEFAULT) -> tuple[list[str], int]:
    """Get the next batch of accounts starting from the cursor.

    Returns: (batch, new_cursor)
    """
    accounts = load_accounts()
    if not accounts:
        return [], 0

    N = len(accounts)
    start = state["cursor"] % N

    batch = []
    for i in range(min(batch_size, N)):
        idx = (start + i) % N
        batch.append(accounts[idx])

    new_cursor = (start + len(batch)) % N
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
    accounts = load_accounts()
    lines = []
    lines.append("## 📸 Instagram Drip Scraper")
    lines.append("")

    succeeded = [a for a, r in results.items() if r["ok"]]
    failed = [a for a, r in results.items() if not r["ok"]]

    lines.append(f"**Batch:** accounts {state['cursor'] - len(batch) + 1}–"
                 f"{state['cursor']} of {len(accounts)}")
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
    accounts = load_accounts()
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

def run_scrape(batch_size: int):
    """Scrape the next batch of accounts."""
    state = load_state()
    batch, new_cursor = get_batch(state, batch_size)

    if not batch:
        print("No accounts to scrape.")
        return

    accounts = load_accounts()
    start_pos = state["cursor"] % len(accounts) if accounts else 0
    print(f"📸 Drip batch: accounts {start_pos + 1}–{start_pos + len(batch)} of {len(accounts)}")
    print(f"   Accounts: {', '.join(f'@{a}' for a in batch)}")

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

    client = ig_mod.setup_gemini()
    existing, all_entries = ig_mod.notion_existing_entries()
    source_mapping = ig_mod.load_source_mapping()

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

            if stats.get("error"):
                reason = f"error after {duration:.1f}s"
                print(f"  ⚠️  @{account}: {reason}")
                results[account] = {"ok": False, "reason": reason}
                state["failures"][account] = {
                    "reason": reason,
                    "time": datetime.now(timezone.utc).strftime("%H:%M UTC"),
                }
            elif posts == 0 and stats.get("needs_login"):
                reason = "429 rate-limited (0 posts, needs login)"
                print(f"  ⚠️  @{account}: {reason} [{duration:.1f}s]")
                results[account] = {"ok": False, "reason": reason}
                state["failures"][account] = {
                    "reason": reason,
                    "time": datetime.now(timezone.utc).strftime("%H:%M UTC"),
                }
            elif posts == 0:
                # Could be a genuinely empty account or a silent rate limit
                reason = "0 posts returned (possibly rate-limited)"
                print(f"  ⚠️  @{account}: {reason} [{duration:.1f}s]")
                results[account] = {"ok": False, "reason": reason}
                state["failures"][account] = {
                    "reason": reason,
                    "time": datetime.now(timezone.utc).strftime("%H:%M UTC"),
                }
            else:
                print(f"  ✅ @{account}: {posts} posts, {evts} events, {cr} new [{duration:.1f}s]")
                results[account] = {
                    "ok": True,
                    "posts": posts,
                    "events": evts,
                    "created": cr,
                }
                state["successes"] += 1
                # Clear from failures if it succeeded this time
                state["failures"].pop(account, None)

            state["total_scraped"] += 1

            if i < len(batch):
                # Be gentle with Instagram — 15s between accounts
                time.sleep(15)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Update cursor
    state["cursor"] = new_cursor
    save_state(state)

    next_account = accounts[new_cursor] if accounts else "?"
    print(f"\n📸 Cursor saved: {new_cursor}/{len(accounts)} (next: @{next_account})")

    # Write step summary
    summary = format_run_summary(batch, results, state)
    write_summary(summary)

    # Print final stats
    ok = sum(1 for r in results.values() if r["ok"])
    fail = sum(1 for r in results.values() if not r["ok"])
    print(f"\n📸 Batch done: {ok} succeeded, {fail} failed")
    print(f"   Accumulated failures today: {len(state.get('failures', {}))}")

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

    accounts = load_accounts()
    state = load_state()

    if args.status:
        cursor = state["cursor"] % len(accounts) if accounts else 0
        failures = state.get("failures", {})
        print(f"📸 Cursor: {cursor}/{len(accounts)}")
        print(f"   Next: @{accounts[cursor]}")
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
