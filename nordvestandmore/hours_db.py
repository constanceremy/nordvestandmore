"""
Hours & Closures Database
--------------------------
Routes opening-hours / closure announcements to a dedicated Notion database
instead of the main events database.

Columns: Name, Source, Location, Description, URL, Source Type, Instagramhandle, Date
"""
import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
HOURS_DB_ID = "30f375efa2cc80708353c7b70e2ec2cf"

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _build_hours_props(data: dict) -> dict:
    """Build Notion properties for the hours/closures database."""
    props = {}

    name = data.get("event_name") or data.get("name") or "Untitled"
    props["Event Name"] = {"title": [{"text": {"content": name[:2000]}}]}

    if data.get("source"):
        props["Source"] = {
            "rich_text": [{"text": {"content": str(data["source"])[:2000]}}]
        }

    if data.get("location"):
        props["Location"] = {
            "rich_text": [{"text": {"content": str(data["location"])[:2000]}}]
        }

    if data.get("description"):
        props["Description"] = {
            "rich_text": [{"text": {"content": str(data["description"])[:2000]}}]
        }

    if data.get("url"):
        props["Event Link"] = {"url": data["url"]}

    if data.get("source_type"):
        props["Source Type"] = {"select": {"name": data["source_type"]}}

    if data.get("ig_handle"):
        props["Instagramhandle"] = {
            "rich_text": [{"text": {"content": str(data["ig_handle"])[:2000]}}]
        }

    if data.get("date"):
        props["Date"] = {"date": {"start": data["date"]}}

    return props


def push_to_hours_db(data: dict, log_fn=None) -> bool:
    """
    Create an entry in the hours/closures Notion database.

    Parameters
    ----------
    data : dict with keys:
        event_name, source, location, description, url,
        source_type, ig_handle, date (ISO string, date posted)
    log_fn : optional callable for logging

    Returns True on success.
    """
    if not NOTION_TOKEN:
        if log_fn:
            log_fn("⚠️  No NOTION_TOKEN — cannot push to hours DB")
        return False

    payload = {
        "parent": {"database_id": HOURS_DB_ID},
        "properties": _build_hours_props(data),
    }

    resp = requests.post(
        f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=30,
    )

    if resp.status_code == 429:
        time.sleep(1.5)
        resp = requests.post(
            f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=30,
        )

    if resp.status_code < 400:
        if log_fn:
            log_fn(f"  📋 Routed to Hours DB: {data.get('event_name')}")
        return True
    else:
        if log_fn:
            try:
                log_fn(f"  ⚠️  Hours DB create failed: {resp.status_code} {resp.json()}")
            except Exception:
                log_fn(f"  ⚠️  Hours DB create failed: {resp.status_code}")
        return False
