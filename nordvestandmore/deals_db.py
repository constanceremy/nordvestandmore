"""
Deals Database
--------------------------
Routes deal / special-price announcements to a dedicated Notion database
instead of the main events database.

Examples of deals:
  - "Tirsdagsdeals – 2 for 1 on cocktails"
  - "Happy Hour every Friday 5-7pm: 40kr beers"
  - "Frokosttilbud: pasta + drink for 99kr"
  - "Student discount: 20% off"

Columns: Name, Place, Description, Source, Source Type, URL, Instagramhandle, Date
"""
import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DEALS_DB_ID = "310375efa2cc800ca48bcbb117a74207"

NOTION_API = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _build_deals_props(data: dict) -> dict:
    """Build Notion properties for the deals database."""
    props = {}

    name = data.get("event_name") or data.get("name") or "Untitled Deal"
    props["Name"] = {"title": [{"text": {"content": name[:2000]}}]}

    if data.get("place"):
        props["Place"] = {
            "rich_text": [{"text": {"content": str(data["place"])[:2000]}}]
        }

    if data.get("source"):
        props["Source"] = {
            "rich_text": [{"text": {"content": str(data["source"])[:2000]}}]
        }

    if data.get("description"):
        props["Description"] = {
            "rich_text": [{"text": {"content": str(data["description"])[:2000]}}]
        }

    if data.get("url"):
        props["URL"] = {"url": data["url"]}

    if data.get("source_type"):
        props["Source Type"] = {"select": {"name": data["source_type"]}}

    if data.get("ig_handle"):
        props["Instagramhandle"] = {
            "rich_text": [{"text": {"content": str(data["ig_handle"])[:2000]}}]
        }

    if data.get("date"):
        props["Date"] = {"date": {"start": data["date"]}}

    return props


def push_to_deals_db(data: dict, log_fn=None) -> bool:
    """
    Create an entry in the deals Notion database.

    Parameters
    ----------
    data : dict with keys:
        event_name  – the deal title (e.g. "Tirsdagsdeals")
        place       – which venue (e.g. "Nordvest Ølbar")
        source      – where we found it (e.g. "@nordvest_olbar")
        description – deal details (e.g. "2 for 1 on cocktails every Tuesday")
        url         – link to source post
        source_type – "Instagram", "Facebook", "Website"
        ig_handle   – Instagram handle of the source
        date        – ISO date string (date posted)

    Returns True on success.
    """
    if not NOTION_TOKEN:
        if log_fn:
            log_fn("⚠️  No NOTION_TOKEN — cannot push to deals DB")
        return False

    if not DEALS_DB_ID:
        if log_fn:
            log_fn("⚠️  No NOTION_DEALS_DB_ID set — cannot push to deals DB")
        return False

    payload = {
        "parent": {"database_id": DEALS_DB_ID},
        "properties": _build_deals_props(data),
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                f"{NOTION_API}/pages", headers=NOTION_HEADERS, json=payload, timeout=60,
            )
            if resp.status_code == 429:
                time.sleep(1.5)
                continue
            resp.raise_for_status()
            if log_fn:
                log_fn(f"  💰 Routed to Deals DB: {data.get('event_name')}")
            return True
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            if attempt < 2:
                wait = 10 * (attempt + 1)
                if log_fn:
                    log_fn(f"  Deals DB error (attempt {attempt + 1}/3), retrying in {wait}s… ({e})")
                time.sleep(wait)
            else:
                if log_fn:
                    log_fn(f"  ⚠️  Deals DB create failed after 3 attempts: {e}")
                return False

    if log_fn:
        try:
            log_fn(f"  ⚠️  Deals DB create failed: {resp.status_code} {resp.json()}")
        except Exception:
            log_fn(f"  ⚠️  Deals DB create failed: {resp.status_code}")
    return False
