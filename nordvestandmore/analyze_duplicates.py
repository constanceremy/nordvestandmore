#!/usr/bin/env python3
"""Categorize duplicate groups by pattern for efficient review."""
import json
from pathlib import Path
from collections import Counter

data = json.loads((Path(__file__).resolve().parent / "duplicate_review.json").read_text())

categories = {
    "exact_same_url_same_source": [],      # Same URL, same source — pure re-scrape dupes
    "different_url_same_source": [],        # Different URL, same source — site quirks
    "cross_platform": [],                   # Same event from different platforms (FB vs Web vs IG)
    "recurring_fb_base_vs_timeid": [],      # FB base URL vs event_time_id URL
    "other": [],
}

for group in data:
    entries = group["entries"]
    urls = set(e["url"] for e in entries)
    sources = set(e["source"].lower() for e in entries)
    source_types = set(e["source_type"] for e in entries)
    
    # Check for FB base vs event_time_id
    has_base_fb = any("facebook.com/events/" in e["url"] and "event_time_id" not in e["url"] for e in entries)
    has_timeid_fb = any("event_time_id" in e["url"] for e in entries)
    
    if has_base_fb and has_timeid_fb:
        categories["recurring_fb_base_vs_timeid"].append(group)
    elif len(source_types) > 1:
        categories["cross_platform"].append(group)
    elif len(urls) == 1:
        categories["exact_same_url_same_source"].append(group)
    elif len(sources) == 1:
        categories["different_url_same_source"].append(group)
    else:
        categories["other"].append(group)

print("=" * 70)
print("DUPLICATE ANALYSIS")
print("=" * 70)

for cat_name, groups in categories.items():
    if not groups:
        continue
    total_dupes = sum(g["count"] - 1 for g in groups)
    print(f"\n{'─' * 70}")
    print(f"📁 {cat_name}")
    print(f"   {len(groups)} group(s), {total_dupes} duplicate(s) to remove")
    print(f"{'─' * 70}")
    
    if cat_name == "exact_same_url_same_source":
        # Show a few examples
        for g in groups[:3]:
            print(f"   • {g['name'][:55]:<55} | {g['start_date']} | {g['count']}x | {g['entries'][0]['source_type']}")
        if len(groups) > 3:
            print(f"   ... and {len(groups) - 3} more")
    
    elif cat_name == "different_url_same_source":
        for g in groups[:5]:
            e = g["entries"]
            print(f"   • {g['name'][:55]:<55} | {g['start_date']} | {g['count']}x")
            for entry in e:
                print(f"     URL: {entry['url'][:80]}")
        if len(groups) > 5:
            print(f"   ... and {len(groups) - 5} more")
    
    elif cat_name == "cross_platform":
        for g in groups[:5]:
            e = g["entries"]
            print(f"   • {g['name'][:55]:<55} | {g['start_date']}")
            for entry in e:
                print(f"     [{entry['source_type']:<10}] {entry['source']:<25} | {entry['url'][:60]}")
        if len(groups) > 5:
            print(f"   ... and {len(groups) - 5} more")
    
    elif cat_name == "recurring_fb_base_vs_timeid":
        for g in groups[:5]:
            e = g["entries"]
            print(f"   • {g['name'][:55]:<55} | {g['start_date']}")
            for entry in e:
                label = "BASE" if "event_time_id" not in entry["url"] else "TIME"
                print(f"     [{label}] {entry['url'][:70]}")
        if len(groups) > 5:
            print(f"   ... and {len(groups) - 5} more")
    
    else:
        for g in groups[:5]:
            e = g["entries"]
            print(f"   • {g['name'][:55]:<55} | {g['start_date']} | {g['count']}x")
            for entry in e:
                print(f"     [{entry['source_type']:<10}] {entry['source']:<20} | {entry['url'][:60]}")
        if len(groups) > 5:
            print(f"   ... and {len(groups) - 5} more")

# Also count recurring events specifically
print(f"\n{'─' * 70}")
print("📁 RECURRING EVENTS (from recurring_events.py)")
print(f"{'─' * 70}")
recurring_names = [
    "brætspilsaften", "fry-day", "happy hour - 2 for 1 cocktail",
    "happy hour at storm b", "rose tuesday",
    "taca copenhagen social run for men", "tekno supperclub",
    "happy hour at dave's", "københavnstrup flea market",
]
rec_groups = [g for g in data if g["name"].strip().lower() in recurring_names]
rec_dupes = sum(g["count"] - 1 for g in rec_groups)
print(f"   {len(rec_groups)} group(s), {rec_dupes} duplicate(s)")
for g in rec_groups[:10]:
    print(f"   • {g['name']:<45} | {g['start_date']} | {g['count']}x")
if len(rec_groups) > 10:
    print(f"   ... and {len(rec_groups) - 10} more")

print(f"\n{'=' * 70}")
print(f"SUMMARY")
print(f"{'=' * 70}")
for cat_name, groups in categories.items():
    if groups:
        total_dupes = sum(g["count"] - 1 for g in groups)
        print(f"  {cat_name:<40} {len(groups):>4} groups, {total_dupes:>4} dupes")
print(f"  {'TOTAL':<40} {len(data):>4} groups, {sum(g['count']-1 for g in data):>4} dupes")
