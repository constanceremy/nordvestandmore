#!/usr/bin/env python3
"""Quick script to see what tags/properties exist in the Notion database."""
import os
import requests
from collections import Counter
from pathlib import Path

env_file = Path(__file__).resolve().parent / ".env"
for line in env_file.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"): continue
    if "=" in line:
        key, val = line.split("=", 1)
        os.environ[key.strip()] = val.strip().strip('"').strip("'")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB = os.environ["NOTION_DATABASE_ID"]
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# First: get database schema to see all properties
r = requests.get(
    f"https://api.notion.com/v1/databases/{NOTION_DB}",
    headers=HEADERS, timeout=30,
)
r.raise_for_status()
db = r.json()
print("═" * 60)
print("DATABASE PROPERTIES:")
print("═" * 60)
for name, prop in sorted(db.get("properties", {}).items()):
    ptype = prop.get("type", "?")
    extra = ""
    if ptype == "select":
        opts = [o["name"] for o in prop.get("select", {}).get("options", [])]
        extra = f" → {opts}" if opts else ""
    elif ptype == "multi_select":
        opts = [o["name"] for o in prop.get("multi_select", {}).get("options", [])]
        extra = f" → {opts}" if opts else ""
    print(f"  {name:<30} {ptype}{extra}")

# Now sample entries to see tag values
print()
print("═" * 60)
print("SAMPLE TAGS (from entries):")
print("═" * 60)

entries = []
payload = {"page_size": 100}
pages = 0
while True:
    r = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
        headers=HEADERS, json=payload, timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    for page in data.get("results", []):
        props = page.get("properties", {})
        name_parts = props.get("Event Name", {}).get("title", [])
        name = name_parts[0]["text"]["content"] if name_parts else ""
        
        # Check all properties for tag-like values
        entry = {"name": name}
        for pname, pval in props.items():
            ptype = pval.get("type")
            if ptype == "select" and pval.get("select"):
                entry[pname] = pval["select"]["name"]
            elif ptype == "multi_select":
                entry[pname] = [o["name"] for o in pval.get("multi_select", [])]
            elif ptype == "rich_text" and pname.lower() in ("to tag", "tags", "tag", "category"):
                parts = pval.get("rich_text", [])
                if parts:
                    entry[pname] = parts[0]["text"]["content"]
        entries.append(entry)
    pages += 1
    if not data.get("has_more") or pages >= 50:
        break
    payload["start_cursor"] = data["next_cursor"]

# Show select/multi_select value distributions
for prop_name in sorted(set(k for e in entries for k in e if k != "name")):
    values = [e.get(prop_name) for e in entries if e.get(prop_name)]
    if not values:
        continue
    print(f"\n  {prop_name}:")
    if isinstance(values[0], list):
        flat = [v for vs in values for v in vs]
        for val, count in Counter(flat).most_common(30):
            print(f"    {count:4d}x  {val}")
    else:
        for val, count in Counter(values).most_common(30):
            print(f"    {count:4d}x  {val}")

# Show examples of tagged entries
print()
print("═" * 60)
print("SAMPLE TAGGED ENTRIES:")
print("═" * 60)
tagged = [e for e in entries if any(k not in ("name", "Source Type") for k in e if k != "name" and e[k])]
for e in tagged[:30]:
    tags = {k: v for k, v in e.items() if k != "name" and k != "Source Type"}
    if tags:
        print(f"  {e['name'][:50]:<50} | {tags}")
