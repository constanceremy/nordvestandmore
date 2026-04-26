#!/usr/bin/env python3
"""
unapproved_events_report.py — Nightly report of future events not yet approved in Notion.

Queries Notion Events DB for events where:
  - Approved = false
  - Deleted  = false
  - Start Date >= today

Sends:
  1. ntfy notification with count of unapproved events
  2. Email to nordvestandmore@gmail.com with full list for duplicate review

Usage:
    python3 unapproved_events_report.py
    python3 unapproved_events_report.py --dry-run
"""
import argparse
import os
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
NOTION_DB      = os.environ.get("NOTION_DATABASE_ID", "")
NTFY_TOPIC     = os.environ.get("NTFY_TOPIC", "")
GMAIL_USER     = os.environ.get("GMAIL_USER", "nordvestandmore@gmail.com")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def fetch_unapproved_events(target_date: date) -> list[dict]:
    if not NOTION_TOKEN or not NOTION_DB:
        print("⚠️  NOTION_TOKEN or NOTION_DATABASE_ID not set")
        return []

    payload = {
        "page_size": 100,
        "sorts": [{"property": "Start Date", "direction": "ascending"}],
        "filter": {
            "and": [
                {"property": "Start Date", "date":     {"equals": target_date.isoformat()}},
                {"property": "Approved",   "checkbox": {"equals": False}},
                {"property": "Deleted",    "checkbox": {"equals": False}},
            ]
        },
    }

    events = []
    has_more = True
    cursor = None

    while has_more:
        if cursor:
            payload["start_cursor"] = cursor
        try:
            resp = requests.post(
                f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
                headers=NOTION_HEADERS, json=payload, timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"⚠️  Notion API error: {e}")
            break

        data = resp.json()
        for page in data.get("results", []):
            p = page.get("properties", {})

            name_parts = p.get("Event Name", {}).get("title", [])
            name = "".join(t.get("plain_text", "") for t in name_parts).strip()
            if not name:
                continue

            date_val = (p.get("Start Date", {}).get("date") or {}).get("start", "")

            time_parts = p.get("Start Time", {}).get("rich_text", [])
            time_str = time_parts[0]["text"]["content"] if time_parts else ""

            loc_parts = p.get("Location", {}).get("rich_text", [])
            location = loc_parts[0]["text"]["content"] if loc_parts else ""

            source_parts = p.get("Source", {}).get("rich_text", [])
            source = source_parts[0]["text"]["content"] if source_parts else ""

            events.append({
                "name":     name,
                "date":     date_val,
                "time":     time_str,
                "location": location,
                "source":   source,
                "url":      f"https://notion.so/{page['id'].replace('-', '')}",
            })

        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")

    return events


def send_ntfy(count: int, dry_run: bool):
    if dry_run:
        print(f"[dry-run] ntfy: {count} unapproved events")
        return
    if not NTFY_TOPIC:
        print("⚠️  NTFY_TOPIC not set — skipping ntfy")
        return

    if count == 0:
        msg = "All future events are approved"
        title = "NV Events - All clear"
        priority = "low"
    else:
        msg = f"{count} upcoming event{'s' if count != 1 else ''} need approval in Notion"
        title = f"NV Events - {count} unapproved"
        priority = "default"

    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=msg.encode(),
            headers={"Title": title, "Priority": priority},
            timeout=10,
        )
        print(f"✅ ntfy sent: {msg}")
    except Exception as e:
        print(f"⚠️  ntfy failed: {e}")


def send_email(events: list[dict], today: date, dry_run: bool):
    if dry_run:
        print(f"[dry-run] email: would send {len(events)} events")
        for ev in events:
            print(f"  - {ev['date']}  {ev['name']}  ({ev['location']})")
        return
    if not GMAIL_APP_PASS:
        print("⚠️  GMAIL_APP_PASSWORD not set — skipping email")
        return

    date_str = today.strftime("%-d %B %Y")
    subject = f"NV Events — {len(events)} unapproved as of {date_str}" if events else f"NV Events — All approved ({date_str})"

    if not events:
        body = "All upcoming events are approved. Nothing to review."
    else:
        lines = [
            f"Unapproved upcoming events as of {date_str}.",
            f"Total: {len(events)}\n",
            "Review in Notion to approve or mark as deleted.\n",
            "─" * 60,
        ]
        prev_date = None
        for ev in events:
            if ev["date"] != prev_date:
                lines.append(f"\n{ev['date']}")
                lines.append("─" * 30)
                prev_date = ev["date"]
            time_part = f"  {ev['time']}" if ev["time"] else ""
            loc_part  = f"  · {ev['location']}" if ev["location"] else ""
            src_part  = f"  [{ev['source']}]" if ev["source"] else ""
            lines.append(f"• {ev['name']}{time_part}{loc_part}{src_part}")
            lines.append(f"  {ev['url']}")
        body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASS)
            smtp.send_message(msg)
        print(f"✅ Email sent to {GMAIL_USER}")
    except Exception as e:
        print(f"⚠️  Email failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print output without sending notifications")
    args = parser.parse_args()

    today    = date.today()
    tomorrow = today + timedelta(days=1)
    print(f"📋 Fetching unapproved events from {tomorrow.isoformat()} onwards…")

    events = fetch_unapproved_events(tomorrow)
    print(f"   Found {len(events)} unapproved event(s)")

    send_ntfy(len(events), args.dry_run)
    send_email(events, today, args.dry_run)


if __name__ == "__main__":
    main()
