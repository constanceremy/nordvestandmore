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
import hashlib
import json
import os
import random
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
        "last_post_dates": {},   # {"handle": "YYYY-MM-DD"} — last post seen per account
        "last_scraped": {},      # {"handle": ISO timestamp} — when we last attempted scrape
        "auth_failure_streak": 0,  # consecutive all-failed runs (likely expired session)
        "suspended": False,        # if True, skip runs until session is refreshed
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

def _account_stagger(account: str) -> int:
    """Return a stable, evenly-distributed stagger offset for an account.

    Uses a hash of the account name so:
    - Adding new accounts never reshuffles existing ones
    - Accounts are spread evenly regardless of their order in the sheet
    - Same account always gets the same offset across runs
    """
    return int(hashlib.md5(account.encode()).hexdigest(), 16)


def _parse_priority(prio_raw: str, default: int = 3) -> int:
    """Parse a priority value from the Google Sheet.

    Accepts integers directly (0, 1, 2, 3, 5 …) or legacy named values:
        0 / skip      → 0  (never scrape)
        1 / high      → 1  (every cycle — fastest)
        2 / medium    → 2  (every 2nd cycle)
        3 / low       → 3  (every 3rd cycle — DEFAULT)
        5 / very_low  → 5  (every 5th cycle)
    Any other integer is also valid (e.g. 7 = every 7th cycle).
    """
    _named = {"skip": 0, "high": 1, "medium": 2, "low": 3, "very_low": 5}
    raw = str(prio_raw).strip().lower()
    if raw in _named:
        return _named[raw]
    try:
        return max(0, int(raw))
    except (ValueError, TypeError):
        return default


def load_accounts() -> tuple[list[str], dict[str, int]]:
    """Load account handles and priorities from Google Sheets (via dedup),
    falling back to accounts.txt.

    Returns: (accounts_list, priority_map)
        - accounts_list: list of IG handles (no @), priority-0 accounts excluded
        - priority_map: {handle: int}  where int = "scrape every N cycles"

    Priority semantics (N = priority value):
        0  — skip (never scraped, excluded entirely)
        1  — scraped every cycle (fastest)
        2  — scraped every 2nd cycle
        3  — scraped every 3rd cycle  ← DEFAULT
        5  — scraped every 5th cycle
        N  — scraped every Nth cycle
    Legacy named values (high/medium/low/very_low) are also accepted.
    """
    priorities: dict[str, int] = {}

    # Try Google Sheets via dedup._load_csv_rows
    try:
        from dedup import _load_csv_rows
        rows = _load_csv_rows()
        accounts = []
        skipped = 0
        for row in rows:
            ig = (row.get("instagram") or "").strip().lstrip("@")
            if ig:
                prio = _parse_priority(row.get("priority") or "")
                if prio == 0:
                    skipped += 1
                    continue  # excluded entirely
                priorities[ig] = prio
                accounts.append(ig)
        if accounts or skipped:
            if skipped:
                print(f"   ({skipped} accounts skipped — priority=0)")
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
                priorities[handle] = 3  # default
    return accounts, priorities


def get_batch(state: dict, max_cursor_size: int = BATCH_SIZE_DEFAULT) -> tuple[list[str], int]:
    """Two-tier batch selection for organic, human-like scraping patterns.

    Tier 1 — P1 overrides (time-based, bypasses cursor):
        Any p1 account not scraped in >30h is pulled in immediately,
        up to 3 per run. This guarantees p1 coverage within ~36h
        regardless of skip rate or batch size.

    Tier 2 — Cursor fill (position-based, randomised count):
        A random number (1..max_cursor_size) of eligible accounts are
        taken from the cursor position and added to the batch, skipping
        any already selected as p1 overrides.

    Returns: (batch, new_cursor)
    """
    all_accounts, priorities = load_accounts()
    if not all_accounts:
        return [], state.get("cursor", 0)

    N = len(all_accounts)
    cycle_num = state.get("cursor", 0) // N if N else 0
    start = state["cursor"] % N

    # ── Cycle order: reshuffle at the start of each cycle ──
    # Accounts are visited in a random order each cycle so no account
    # is always scraped before/after the same neighbours, and new accounts
    # slot in naturally without disrupting the existing order mid-cycle.
    cycle_order = state.get("cycle_order", [])
    current_set = set(all_accounts)
    existing_set = set(cycle_order)

    if start == 0 or not cycle_order:
        # New cycle (or very first run) — full reshuffle
        cycle_order = all_accounts.copy()
        random.shuffle(cycle_order)
        state["cycle_order"] = cycle_order
        if cycle_num > 0 or not state.get("cycle_order"):
            print(f"   🔀 New cycle order shuffled ({N} accounts)")
    elif existing_set != current_set:
        # Accounts added/removed mid-cycle — patch without reshuffling
        removed = existing_set - current_set
        added = [a for a in all_accounts if a not in existing_set]
        cycle_order = [a for a in cycle_order if a not in removed] + added
        state["cycle_order"] = cycle_order
        if added:
            print(f"   ➕ {len(added)} new account(s) appended to current cycle order")
        if removed:
            print(f"   ➖ {len(removed)} removed account(s) dropped from cycle order")

    # Use the (possibly shuffled) cycle order for cursor traversal
    N = len(cycle_order)
    start = state["cursor"] % N

    now = datetime.now(timezone.utc)
    last_scraped = state.get("last_scraped", {})

    # ── Tier 1: p1 accounts overdue (>30h since last scrape) ──
    P1_MAX_AGE_H = 30
    overdue_p1: list[str] = []
    for acct, prio in priorities.items():
        if prio == 1:
            ls = last_scraped.get(acct)
            if ls is None:
                overdue_p1.append(acct)
            else:
                age_h = (now - datetime.fromisoformat(ls)).total_seconds() / 3600
                if age_h > P1_MAX_AGE_H:
                    overdue_p1.append(acct)
    random.shuffle(overdue_p1)  # Don't always pick the same overdue account first
    p1_override = overdue_p1[:3]
    p1_override_set = set(p1_override)

    # Print priority distribution + overdue count
    from collections import Counter
    prio_dist = Counter(priorities.values())
    dist_str = ", ".join(f"p{k}×{v}" for k, v in sorted(prio_dist.items()))
    overdue_note = f", {len(overdue_p1)} p1 overdue" if overdue_p1 else ""
    print(f"   Priorities: {dist_str}  (cycle {cycle_num}{overdue_note})")

    # ── Tier 2: random count of cursor accounts ──
    cursor_size = random.randint(1, max(1, max_cursor_size))
    cursor_batch: list[str] = []
    cursor_advance = 0
    checked = 0

    while len(cursor_batch) < cursor_size and checked < N:
        idx = (start + checked) % N
        account = cycle_order[idx]
        checked += 1
        cursor_advance += 1

        if account in p1_override_set:
            continue  # Already in batch via tier-1 override

        prio = priorities.get(account, 3)
        if prio > 1 and (cycle_num + _account_stagger(account)) % prio != 0:
            continue

        cursor_batch.append(account)

    new_cursor = (start + cursor_advance) % N
    batch = p1_override + cursor_batch
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


def run_scrape(batch_size: int, force: bool = False):
    """Scrape the next batch of accounts.

    Args:
        batch_size: Maximum number of accounts to pull from the cursor
                    (actual count is randomised 1..batch_size).
        force:      If True, skip the random-skip check (used for manual/
                    workflow_dispatch runs so they always execute).
    """
    run_start = time.time()
    time_in_delays = 0.0  # Track time spent in deliberate delays
    time_in_retries = 0.0  # Track time spent in retry waits

    # ── Random skip: ~30% of scheduled slots are silently dropped ──
    # This creates organic timing variation without changing the cron schedule.
    # Manual runs (force=True) always execute.
    SKIP_PROB = 0.30
    if not force and random.random() < SKIP_PROB:
        print(f"⏩ Randomly skipping this slot ({int(SKIP_PROB * 100)}% skip rate for organic timing)")
        return

    # ── Random startup delay: 0–5 minutes ──
    # Spreads actual scrape start times across the 30-min window so
    # Instagram doesn't see perfectly regular 30-min intervals.
    if not force:
        startup_delay = random.uniform(0, 300)  # 0–5 min
        print(f"⏱️  Startup delay: {startup_delay:.0f}s (randomised)…")
        time.sleep(startup_delay)

    state = load_state()

    # ── Suspension check (expired session) ──
    if state.get("suspended"):
        print("⏸️  Scraper is suspended due to repeated auth failures (401).")
        print("   The Instagram session cookie has likely expired.")
        print("   Fix: refresh the session and update IG_SESSION_B64 secret.")
        print("   The scraper will resume automatically once a run succeeds.")
        return  # exit cleanly — no failure, no notification spam

    batch, new_cursor = get_batch(state, max_cursor_size=batch_size)

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

            # Persist latest post date and scrape timestamp regardless of outcome
            if latest_date:
                state.setdefault("last_post_dates", {})[account] = latest_date
            state.setdefault("last_scraped", {})[account] = datetime.now(timezone.utc).isoformat()

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
                upd = stats.get("updated", 0)
                already = upd  # updated = already existed in Notion
                if evts == 0:
                    print(f"  ✅ @{account}: {posts}/{profile_total} posts{date_info}, 0 events [{duration:.1f}s]")
                elif cr == evts:
                    print(f"  ✅ @{account}: {posts}/{profile_total} posts{date_info}, {evts} events (all new) [{duration:.1f}s]")
                elif already == evts:
                    print(f"  ✅ @{account}: {posts}/{profile_total} posts{date_info}, {evts} events (all already in Notion) [{duration:.1f}s]")
                else:
                    print(f"  ✅ @{account}: {posts}/{profile_total} posts{date_info}, {evts} events ({cr} new, {already} already in Notion) [{duration:.1f}s]")
                results[account] = {
                    "ok": True,
                    "posts": posts,
                    "events": evts,
                    "created": cr,
                }
                state["successes"] += 1
                # Clear from failures if it succeeded this time
                state["failures"].pop(account, None)
                if cr:
                    acct_status = f"✅ @{account}: {cr} new event(s)!"
                elif evts:
                    acct_status = f"✅ @{account}: {evts} event(s), all already in Notion"
                else:
                    acct_status = f"✅ @{account}: {posts} posts, no events"

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

    # ── Auth failure streak tracking ──
    ok = sum(1 for r in results.values() if r["ok"])
    fail = sum(1 for r in results.values() if not r["ok"])

    if ok > 0:
        # At least one success — session is alive, reset streak
        state["auth_failure_streak"] = 0
        state["suspended"] = False
    elif fail == len(batch) and fail > 0:
        # Every account in this batch failed — likely a dead session
        state["auth_failure_streak"] = state.get("auth_failure_streak", 0) + 1
        streak = state["auth_failure_streak"]
        print(f"⚠️  All {fail} accounts failed — auth failure streak: {streak}/2")
        if streak >= 2:
            state["suspended"] = True
            print("🚫 Suspending scraper after 2 consecutive all-failed runs.")
            print("   Refresh the IG session cookie and update IG_SESSION_B64.")
            _ntfy(
                "IG Scraper suspended — session expired",
                "All accounts failing with 401. Refresh IG_SESSION_B64 secret to resume.",
                priority="high",
                tags="warning",
            )
    else:
        # Mixed results — don't count as a full auth failure
        state["auth_failure_streak"] = 0

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


def export_tracker(output_path: str = ""):
    """Write a markdown table of all accounts with last scrape time, last post date, and failures."""
    all_accounts, priorities = load_accounts()
    state = load_state()
    last_scraped = state.get("last_scraped", {})
    last_post_dates = state.get("last_post_dates", {})
    failures = state.get("failures", {})

    now = datetime.now(timezone.utc)

    def age_str(iso: str | None) -> str:
        if not iso:
            return "never"
        try:
            dt = datetime.fromisoformat(iso)
            hours = (now - dt).total_seconds() / 3600
            if hours < 1:
                return f"{int(hours * 60)}m ago"
            if hours < 48:
                return f"{hours:.0f}h ago"
            return f"{hours / 24:.0f}d ago"
        except Exception:
            return iso

    rows = []
    for acct in all_accounts:
        prio = priorities.get(acct, 3)
        scraped = last_scraped.get(acct)
        post_date = last_post_dates.get(acct, "—")
        failed = "⚠️ " + failures[acct].get("reason", "?") if acct in failures else ""
        rows.append((age_str(scraped), acct, prio, scraped or "", post_date, failed))

    # Sort: never scraped first, then oldest → newest
    rows.sort(key=lambda r: r[3])

    lines = [
        f"# Instagram Scrape Tracker",
        f"",
        f"_Updated: {now.strftime('%Y-%m-%d %H:%M UTC')} · {len(all_accounts)} accounts_",
        f"",
        f"| Account | Priority | Last scraped | Last post | Status |",
        f"|---------|----------|--------------|-----------|--------|",
    ]
    for age, acct, prio, _, post_date, failed in rows:
        status = failed if failed else "✅"
        lines.append(f"| @{acct} | p{prio} | {age} | {post_date} | {status} |")

    not_seen = [a for a in all_accounts if a not in last_scraped]
    if not_seen:
        lines += ["", f"**Not yet scraped ({len(not_seen)}):** " + ", ".join(f"`@{a}`" for a in not_seen)]

    content = "\n".join(lines) + "\n"

    if output_path:
        Path(output_path).write_text(content)
        print(f"📊 Tracker written to {output_path} ({len(all_accounts)} accounts)")
    else:
        print(content)


def main():
    parser = argparse.ArgumentParser(description="Drip-feed IG scraper")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT,
                        help=f"Max cursor accounts per run (default: {BATCH_SIZE_DEFAULT}; actual count is randomised 1..N)")
    parser.add_argument("--force", action="store_true",
                        help="Skip random-skip and startup-delay (for manual/workflow_dispatch runs)")
    parser.add_argument("--list", action="store_true",
                        help="Just print the batch, don't scrape")
    parser.add_argument("--status", action="store_true",
                        help="Show cursor position and failures")
    parser.add_argument("--daily-report", action="store_true",
                        help="Output daily digest and reset failure counters")
    parser.add_argument("--last-posts", action="store_true",
                        help="Show last seen post date for each account")
    parser.add_argument("--export-tracker", metavar="FILE", nargs="?", const="scrape_tracker.md",
                        help="Write markdown tracker table to FILE (default: scrape_tracker.md)")
    parser.add_argument("--unsuspend", action="store_true",
                        help="Clear suspension flag and auth_failure_streak from state (use after refreshing session)")
    args = parser.parse_args()

    if args.export_tracker is not None:
        export_tracker(args.export_tracker)
        return

    if args.unsuspend:
        state = load_state()
        state["suspended"] = False
        state["auth_failure_streak"] = 0
        save_state(state)
        print("🔓 Scraper unsuspended — auth_failure_streak reset to 0.")
        return

    if args.daily_report:
        daily_report()
        return

    all_accounts, priorities = load_accounts()
    state = load_state()

    if args.last_posts:
        last_dates = state.get("last_post_dates", {})
        if not last_dates:
            print("No last post dates recorded yet — run the scraper a few times first.")
            return
        # Sort by date ascending (oldest first) so quiet accounts stand out at top
        sorted_dates = sorted(last_dates.items(), key=lambda x: x[1] or "")
        print(f"\n📅 Last post date per account ({len(sorted_dates)} tracked):\n")
        for handle, d in sorted_dates:
            prio = priorities.get(handle, "?")
            prio_str = f"p{prio}" if isinstance(prio, int) else str(prio)
            print(f"  {d}  @{handle}  [{prio_str}]")
        not_seen = [a for a in all_accounts if a not in last_dates]
        if not_seen:
            print(f"\n  ⏳ Not yet scraped ({len(not_seen)}): {', '.join(f'@{a}' for a in not_seen)}")
        return

    if args.status:
        cursor = state["cursor"] % len(all_accounts) if all_accounts else 0
        N = len(all_accounts)
        cycle_num = state["cursor"] // N if N else 0
        failures = state.get("failures", {})
        from collections import Counter
        prio_dist = Counter(priorities.values())
        dist_str = ", ".join(f"p{k}×{v}" for k, v in sorted(prio_dist.items()))
        print(f"📸 Cursor: {cursor}/{N}  (cycle {cycle_num})")
        print(f"   Priorities: {dist_str}")
        print(f"   Next: @{all_accounts[cursor]}" if all_accounts else "")
        print(f"   Scraped this cycle: {state.get('total_scraped', 0)}")
        print(f"   Successes: {state.get('successes', 0)}")
        print(f"   Failures: {len(failures)}")
        if failures:
            for h, info in sorted(failures.items()):
                print(f"     @{h}: {info.get('reason', '?')}")
        print(f"   Last reset: {state.get('last_reset', '?')}")
        return

    if args.list:
        batch, _ = get_batch(state, max_cursor_size=args.batch_size)
        print(f"Next batch ({len(batch)}): {', '.join(f'@{a}' for a in batch)}")
        return

    run_scrape(args.batch_size, force=args.force)


if __name__ == "__main__":
    main()
