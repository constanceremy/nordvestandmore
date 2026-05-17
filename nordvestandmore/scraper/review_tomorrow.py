#!/usr/bin/env python3
"""
Review tomorrow's events and merge duplicates.

Workflow:
  1. Fetches every event with Start Date = tomorrow (or --date)
  2. Clusters events with similar titles using existing dedup.similarity
  3. Prints unique events + likely-duplicate clusters with Notion links
  4. For each cluster, prompts y/n/skip
  5. On 'y':
       - Gemini-merges the titles
       - Picks a winner by source priority (website > facebook > instagram)
       - Unions Tag List values
       - Picks longest non-empty for description, fills missing fields from losers
       - Patches the winner in Notion
       - Archives the loser pages (soft-delete, recoverable 30 days)

Usage:
    cd nordvestandmore/scraper
    python3 review_tomorrow.py                # tomorrow, interactive
    python3 review_tomorrow.py --date 2026-05-18
    python3 review_tomorrow.py --dry-run      # show only, never modify
    python3 review_tomorrow.py --threshold 0.7
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import date, timedelta

# ── Env (same pattern as other scripts here) ──
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / "website" / ".env.local")
except ImportError:
    env_file = Path(__file__).resolve().parent.parent / "website" / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

NOTION_TOKEN  = os.environ.get("NOTION_TOKEN", "")
EVENTS_DB_ID  = os.environ.get("NOTION_EVENTS_DB_ID") or os.environ.get("NOTION_DATABASE_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not NOTION_TOKEN or not EVENTS_DB_ID:
    sys.exit("❌ Missing NOTION_TOKEN or NOTION_EVENTS_DB_ID — check website/.env.local")

# Import existing dedup helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dedup import similarity, get_source_priority, normalize_text  # type: ignore

# ── Notion API ──
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type":  "application/json",
    "Notion-Version": "2022-06-28",
}


def _request(url, payload, method, retries=4):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), headers=HEADERS, method=method
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(2 ** attempt)
    raise last  # type: ignore[misc]


def _post(url, payload):
    return _request(url, payload, "POST")


def _patch(url, payload):
    return _request(url, payload, "PATCH")


# ── Notion property readers ──

def text_of(prop):
    if not prop:
        return ""
    t = prop.get("type")
    if t == "title":      return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if t == "rich_text":  return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    if t == "url":        return prop.get("url") or ""
    if t == "select":     s = prop.get("select"); return s["name"] if s else ""
    return ""


def number_of(prop):
    if not prop or prop.get("type") != "number":
        return None
    return prop.get("number")


def multiselect_of(prop):
    if not prop or prop.get("type") != "multi_select":
        return []
    return [opt["name"] for opt in prop.get("multi_select", [])]


def files_of(prop):
    if not prop or prop.get("type") != "files":
        return []
    out = []
    for f in prop.get("files", []):
        if f.get("type") == "external":
            out.append({"name": f.get("name", ""), "type": "external", "external": {"url": f["external"]["url"]}})
        elif f.get("type") == "file":
            out.append({"name": f.get("name", ""), "type": "external", "external": {"url": f["file"]["url"]}})
    return out


def checkbox_of(prop):
    return bool(prop and prop.get("type") == "checkbox" and prop.get("checkbox"))


# ── Fetch events for a given date ──

def fetch_events_for(target: date):
    iso = target.isoformat()
    payload = {
        "page_size": 100,
        "filter": {"property": "Start Date", "date": {"equals": iso}},
        "sorts": [{"property": "Start Time", "direction": "ascending"}],
    }
    cursor = None
    events = []
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        data = _post(f"https://api.notion.com/v1/databases/{EVENTS_DB_ID}/query", payload)
        for page in data.get("results", []):
            events.append(parse_event(page))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return events


def parse_event(page):
    p = page.get("properties", {})
    title = text_of(p.get("Event Name"))
    return {
        "id":            page["id"],
        "page":          page,                # full page for Notion writeback
        "url":           page.get("url", ""),
        "title":         title,
        "description":   text_of(p.get("Description")),
        "start_time":    text_of(p.get("Start Time")),
        "end_time":      text_of(p.get("End Time")),
        "location":      text_of(p.get("Location")),
        "organizer":     text_of(p.get("Organizer")),
        "source_url":    text_of(p.get("Source")),
        "source_type":   text_of(p.get("Source Type")),
        "event_link":    text_of(p.get("Event Link")),
        "ig_handle":     text_of(p.get("Instagramhandle")),
        "price":         number_of(p.get("Price")),
        "max_spots":     number_of(p.get("Max Spots")),
        "tag_list":      multiselect_of(p.get("Tag List")),
        "tags_legacy":   multiselect_of(p.get("Tags")) or ([text_of(p.get("Tags"))] if text_of(p.get("Tags")) else []),
        "cover_image":   files_of(p.get("Cover Image")),
        "language":      multiselect_of(p.get("Language")),
        "own_event":     checkbox_of(p.get("Own Event")),
    }


# ── Clustering ──

def cluster_events(events, threshold=0.75):
    """Union-find clustering on title similarity."""
    n = len(events)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            sim = similarity(events[i]["title"], events[j]["title"])
            if sim >= threshold:
                union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(events[i])
    return list(groups.values())


def link_for(ev):
    """Best external link on the event, prioritised over Notion URL."""
    return ev["event_link"] or ev["source_url"] or ""


def source_priority(ev):
    """1=website > 2=facebook > 3=instagram. Lower is better."""
    return get_source_priority(link_for(ev))


# ── Gemini title merge ──

_gemini_client = None


def gemini_merge_titles(titles):
    """Ask Gemini for a single cleanest title across N variants."""
    global _gemini_client
    distinct = list(dict.fromkeys(t.strip() for t in titles if t.strip()))
    if len(distinct) <= 1:
        return distinct[0] if distinct else ""

    # Quick exit: if normalisation makes them identical, use the longest original
    if len({normalize_text(t) for t in distinct}) == 1:
        return max(distinct, key=len)

    if not GEMINI_API_KEY:
        return max(distinct, key=len)  # fall back to longest

    try:
        if _gemini_client is None:
            from google import genai
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)

        from google.genai import types
        prompt = (
            "You are merging duplicate event titles into one clean version. "
            "Return ONE title under 80 characters that best names the event. "
            "Do not invent details that aren't in at least one of the inputs. "
            "Reply with ONLY the title — no quotes, no explanation.\n\n"
        ) + "\n".join(f"{i+1}. {t}" for i, t in enumerate(distinct))

        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=80),
        )
        merged = (resp.text or "").strip().strip('"').strip("'")
        if not merged:
            return max(distinct, key=len)
        return merged
    except Exception as e:
        print(f"    ⚠️  Gemini title merge failed ({e}); using longest original")
        return max(distinct, key=len)


# ── Merge policy ──

def first_non_empty(values):
    for v in values:
        if v:
            return v
    return None


def merge_cluster(cluster, dry_run=False):
    """Merge a cluster into one winner; archive the losers."""
    # Winner = best source priority; tie-break = most fields filled
    def fill_score(ev):
        score = 0
        for k in ("description", "location", "organizer", "start_time", "end_time", "event_link", "cover_image", "max_spots", "price", "tag_list"):
            if ev.get(k):
                score += 1
        return score

    sorted_cluster = sorted(cluster, key=lambda e: (source_priority(e), -fill_score(e)))
    winner = sorted_cluster[0]
    losers = sorted_cluster[1:]

    # Merge title via Gemini
    merged_title = gemini_merge_titles([e["title"] for e in sorted_cluster])

    # Tag List = union across cluster, falling back to legacy Tags per event
    # (matches the website's read pattern: prefer Tag List, fall back to Tags)
    merged_tags = []
    for e in sorted_cluster:
        source_tags = e["tag_list"] if e["tag_list"] else e["tags_legacy"]
        for t in source_tags:
            if t and t not in merged_tags:
                merged_tags.append(t)

    # Pick best link by source priority
    link_candidates = sorted(sorted_cluster, key=lambda e: source_priority(e))
    merged_link = next((link_for(e) for e in link_candidates if link_for(e)), "")

    # Single-value text fields: prefer non-empty, longest if multiple
    def longest_non_empty(field):
        vals = [e[field] for e in sorted_cluster if e.get(field)]
        return max(vals, key=len) if vals else ""

    merged = {
        "title":       merged_title,
        "description": longest_non_empty("description"),
        "start_time":  first_non_empty([e["start_time"] for e in sorted_cluster]),
        "end_time":    first_non_empty([e["end_time"] for e in sorted_cluster]),
        "location":    longest_non_empty("location"),
        "organizer":   longest_non_empty("organizer"),
        "event_link":  merged_link,
        "tag_list":    merged_tags,
        "price":       first_non_empty([e["price"] for e in sorted_cluster if e["price"] is not None]),
        "max_spots":   first_non_empty([e["max_spots"] for e in sorted_cluster if e["max_spots"] is not None]),
        "cover_image": first_non_empty([e["cover_image"] for e in sorted_cluster if e["cover_image"]]),
    }

    print("\n  ✨ Merged plan:")
    print(f"     Title:       {merged['title']!r}")
    print(f"     Tag List:    {merged['tag_list']}")
    print(f"     Link:        {merged['event_link'] or '(none)'} (priority {get_source_priority(merged['event_link'])})")
    print(f"     Winner:      {winner['id'][:8]}…  source={winner['source_type'] or '?'}")
    print(f"     Archive:     {', '.join(l['id'][:8] + '…' for l in losers)}")

    if dry_run:
        print("     🧪 dry-run — no changes applied")
        return

    # ── Apply changes ──
    # 1. Patch winner
    props_patch = {
        "Event Name": {"title": [{"text": {"content": merged["title"]}}]},
        "Tag List":   {"multi_select": [{"name": t} for t in merged["tag_list"]]},
    }
    if merged["description"]:
        props_patch["Description"] = {"rich_text": [{"text": {"content": merged["description"]}}]}
    if merged["start_time"]:
        props_patch["Start Time"] = {"rich_text": [{"text": {"content": merged["start_time"]}}]}
    if merged["end_time"]:
        props_patch["End Time"]   = {"rich_text": [{"text": {"content": merged["end_time"]}}]}
    if merged["location"]:
        props_patch["Location"]   = {"rich_text": [{"text": {"content": merged["location"]}}]}
    if merged["organizer"]:
        props_patch["Organizer"]  = {"rich_text": [{"text": {"content": merged["organizer"]}}]}
    if merged["event_link"]:
        props_patch["Event Link"] = {"url": merged["event_link"]}
    if merged["price"] is not None:
        props_patch["Price"] = {"number": merged["price"]}
    if merged["max_spots"] is not None:
        props_patch["Max Spots"] = {"number": merged["max_spots"]}
    if merged["cover_image"]:
        props_patch["Cover Image"] = {"files": merged["cover_image"]}

    _patch(f"https://api.notion.com/v1/pages/{winner['id']}", {"properties": props_patch})
    print("     ✓ winner updated")

    # 2. Archive losers
    for loser in losers:
        _patch(f"https://api.notion.com/v1/pages/{loser['id']}", {"archived": True})
        print(f"     ✓ archived {loser['id'][:8]}…")
        time.sleep(0.35)


# ── Pretty print ──

def format_time(t):
    return t or "—"


def print_event_line(ev, indent="  "):
    src = ev["source_type"] or "?"
    link = link_for(ev)
    link_short = link.split("://")[-1][:60] if link else "(no link)"
    # Truncate very long titles (IG captions can be 1000+ chars)
    title = ev["title"][:120] + ("…" if len(ev["title"]) > 120 else "")
    print(f"{indent}{format_time(ev['start_time']):>8}  {title}  [{src}]")
    # Surface what tags this event currently has so the user can see
    # before merging — preferred Tag List, otherwise legacy Tags.
    shown_tags = ev["tag_list"] if ev["tag_list"] else ev["tags_legacy"]
    if shown_tags:
        which = "Tag List" if ev["tag_list"] else "Tags (legacy)"
        print(f"{indent}          🏷  {which}: {shown_tags}")
    print(f"{indent}          {ev['url']}")
    if link:
        print(f"{indent}          ↗ {link_short}")


# ── Main ──

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Date to review (YYYY-MM-DD). Default: tomorrow.")
    ap.add_argument("--dry-run", action="store_true", help="Don't modify Notion; show planned merges only.")
    ap.add_argument("--threshold", type=float, default=0.65, help="Similarity threshold for clustering (0–1). Lower = more candidate clusters.")
    args = ap.parse_args()

    target = (date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=1))
    print(f"\n🌅  Reviewing events for {target.strftime('%a %Y-%m-%d')} (threshold={args.threshold})")
    if args.dry_run:
        print("    🧪 DRY RUN — no Notion writes\n")

    events = fetch_events_for(target)
    if not events:
        print("   No events found for that date.")
        return
    print(f"   Found {len(events)} event(s).\n")

    clusters = cluster_events(events, threshold=args.threshold)
    singletons = [c for c in clusters if len(c) == 1]
    duplicates = [c for c in clusters if len(c) > 1]

    print(f"✓ {len(singletons)} unique event(s)")
    for c in singletons:
        print_event_line(c[0])

    if not duplicates:
        print("\n🎉 No duplicate clusters detected. Nothing to merge.")
        return

    print(f"\n⚠️  {len(duplicates)} likely-duplicate cluster(s)")
    for i, cluster in enumerate(duplicates, 1):
        # Compute representative similarity (max pairwise)
        sims = [similarity(cluster[0]["title"], e["title"]) for e in cluster[1:]]
        rep = max(sims) if sims else 0.0
        print(f"\n  Cluster #{i} (sim≈{rep:.2f}) — {len(cluster)} events:")
        for ev in cluster:
            print_event_line(ev, indent="    ")

        try:
            answer = input("\n  Merge this cluster? [y/N/q to quit] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Stopped.")
            return
        if answer == "q":
            print("  Stopped.")
            return
        if answer != "y":
            print("  Skipped.")
            continue

        try:
            merge_cluster(cluster, dry_run=args.dry_run)
        except urllib.error.HTTPError as e:
            print(f"    ⚠️  Notion API error: HTTP {e.code} — {e.read().decode()[:200]}")

    print("\n✓ Done.")


if __name__ == "__main__":
    main()
