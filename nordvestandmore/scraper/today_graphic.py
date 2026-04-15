#!/usr/bin/env python3
"""
today_graphic.py — Generate daily "Today in Nordvest" Instagram Story graphic.

Layout (1080×1920, black & white grid aesthetic):
  - Header (black bar): "TODAY IN NORDVEST" + date
  - Body (white, graph-paper texture): event list with 1px separators
  - Footer (black bar): "NV & MORE" + timestamp

Sends two ntfy messages:
  1. The image (for Instagram Story)
  2. Tags-only text, one per line (for copy-paste as IG caption)

Usage:
    python3 today_graphic.py
    python3 today_graphic.py --date 2026-04-16   # override date for testing
    python3 today_graphic.py --dry-run            # generate image only, don't send
"""
import argparse
import io
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# ── Config ────────────────────────────────────────────────────────────────────

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB    = os.environ.get("NOTION_DATABASE_ID", "")
NTFY_TOPIC   = os.environ.get("NTFY_TOPIC", "")

W, H = 1080, 1920          # Instagram Story dimensions

# Colour palette
BLACK      = (0, 0, 0)
WHITE      = (255, 255, 255)
LIGHT_GRAY = (230, 230, 230)   # graph-paper lines
MID_GRAY   = (160, 160, 160)   # secondary text
DARK_GRAY  = (80, 80, 80)      # tertiary text

HEADER_H = int(H * 0.18)       # top 18 %
FOOTER_H = int(H * 0.08)       # bottom 8 %
BODY_H   = H - HEADER_H - FOOTER_H

PADDING  = 60                  # horizontal margin

# ── Font loading ──────────────────────────────────────────────────────────────

def _find_font(name: str) -> str | None:
    """Search common system font paths for a font file by name fragment."""
    search_dirs = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        str(Path.home() / ".fonts"),
        "/System/Library/Fonts",         # macOS
        "/Library/Fonts",                # macOS
    ]
    for d in search_dirs:
        for p in Path(d).rglob("*.ttf") if Path(d).exists() else []:
            if name.lower() in p.name.lower():
                return str(p)
    return None


def _load_fonts():
    """Return a dict of PIL ImageFont objects at various sizes."""
    # Prefer Liberation Sans (usually available on Ubuntu runners)
    # Fall back to DejaVu Sans, then Pillow's default bitmap font
    candidates = [
        ("LiberationSans-Bold",    "bold"),
        ("LiberationSans-Regular", "regular"),
        ("DejaVuSans-Bold",        "bold"),
        ("DejaVuSans",             "regular"),
    ]
    bold_path    = None
    regular_path = None
    for name, kind in candidates:
        path = _find_font(name)
        if path:
            if kind == "bold" and bold_path is None:
                bold_path = path
            elif kind == "regular" and regular_path is None:
                regular_path = path
        if bold_path and regular_path:
            break

    def _f(path, size):
        if path:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    return {
        "header_title": _f(bold_path,    96),
        "header_date":  _f(regular_path, 44),
        "event_name":   _f(bold_path,    52),
        "event_meta":   _f(regular_path, 38),
        "event_tags":   _f(regular_path, 32),
        "footer":       _f(regular_path, 34),
        "no_events":    _f(regular_path, 52),
    }


# ── Notion data fetch ─────────────────────────────────────────────────────────

def fetch_todays_events(target_date: date) -> list[dict]:
    """Fetch events from Notion for target_date, sorted by start time."""
    if not NOTION_TOKEN or not NOTION_DB:
        print("⚠️  NOTION_TOKEN or NOTION_DATABASE_ID not set — using empty event list")
        return []

    date_str = target_date.isoformat()
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    payload = {
        "page_size": 100,
        "filter": {
            "property": "Start Date",
            "date": {"equals": date_str},
        },
        "sorts": [{"property": "Start Time", "direction": "ascending"}],
    }
    try:
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  Notion API error: {e}")
        return []

    events = []
    for page in resp.json().get("results", []):
        p = page.get("properties", {})

        name_parts = p.get("Event Name", {}).get("title", [])
        name = "".join(t.get("plain_text", "") for t in name_parts).strip()
        if not name:
            continue

        time_parts = p.get("Start Time", {}).get("rich_text", [])
        time_str = time_parts[0]["text"]["content"] if time_parts else ""

        loc_parts = p.get("Location", {}).get("rich_text", [])
        location = loc_parts[0]["text"]["content"] if loc_parts else ""

        # Tag List (multi_select) first, then Tags (select fallback)
        tag_list_ms = p.get("Tag List", {}).get("multi_select", [])
        tags = [t["name"] for t in tag_list_ms]
        if not tags:
            tags_ms = p.get("Tags", {}).get("multi_select", [])
            tags = [t["name"] for t in tags_ms]
        if not tags:
            sel = (p.get("Tags", {}).get("select") or {}).get("name", "")
            tags = [sel] if sel else []

        events.append({
            "name": name,
            "time": time_str,
            "location": location,
            "tags": tags,
        })

    return events


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _draw_graph_paper(draw: ImageDraw, x0: int, y0: int, x1: int, y1: int, spacing: int = 48):
    """Draw a subtle graph-paper grid in the body area."""
    for x in range(x0, x1, spacing):
        draw.line([(x, y0), (x, y1)], fill=LIGHT_GRAY, width=1)
    for y in range(y0, y1, spacing):
        draw.line([(x0, y), (x1, y)], fill=LIGHT_GRAY, width=1)


def _text_width(draw: ImageDraw, text: str, font: ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _truncate(draw: ImageDraw, text: str, font: ImageFont, max_width: int) -> str:
    if _text_width(draw, text, font) <= max_width:
        return text
    while text and _text_width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text + "…"


# ── Main render ───────────────────────────────────────────────────────────────

def render(events: list[dict], target_date: date) -> Image.Image:
    fonts = _load_fonts()
    img  = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([(0, 0), (W, HEADER_H)], fill=BLACK)

    title = "TODAY IN NORDVEST"
    tw = _text_width(draw, title, fonts["header_title"])
    draw.text(((W - tw) // 2, 60), title, font=fonts["header_title"], fill=WHITE)

    day_name = target_date.strftime("%A").upper()
    day_num  = target_date.day
    month    = target_date.strftime("%B").upper()
    year     = target_date.year
    date_str = f"{day_name}  {day_num} {month} {year}"
    dw = _text_width(draw, date_str, fonts["header_date"])
    draw.text(((W - dw) // 2, 178), date_str, font=fonts["header_date"], fill=LIGHT_GRAY)

    # thin white line under header text
    draw.line([(PADDING, HEADER_H - 2), (W - PADDING, HEADER_H - 2)], fill=WHITE, width=1)

    # ── Body ──────────────────────────────────────────────────────────────────
    body_y0 = HEADER_H
    body_y1 = H - FOOTER_H
    _draw_graph_paper(draw, 0, body_y0, W, body_y1, spacing=48)

    if not events:
        msg = "No events today"
        mw = _text_width(draw, msg, fonts["no_events"])
        draw.text(
            ((W - mw) // 2, body_y0 + BODY_H // 2 - 30),
            msg, font=fonts["no_events"], fill=MID_GRAY,
        )
    else:
        n = len(events)
        # Allocate row height — clamp between 130 and 220 px
        row_h = max(130, min(220, BODY_H // n))
        available = BODY_H

        y = body_y0 + 24
        for i, ev in enumerate(events):
            row_bottom = y + row_h

            # Separator line at top of each row (except first)
            if i > 0:
                draw.line([(PADDING, y), (W - PADDING, y)], fill=BLACK, width=1)
                y += 12

            # Row number stamp (left margin)
            num_str = f"{i+1:02d}"
            draw.text((PADDING, y + 4), num_str, font=fonts["event_tags"], fill=LIGHT_GRAY)

            text_x = PADDING + 68
            max_w  = W - text_x - PADDING

            # Event name
            name = _truncate(draw, ev["name"].upper(), fonts["event_name"], max_w)
            draw.text((text_x, y), name, font=fonts["event_name"], fill=BLACK)
            y += 58

            # Time + location on one line
            meta_parts = []
            if ev["time"]:
                meta_parts.append(ev["time"])
            if ev["location"]:
                meta_parts.append(ev["location"].upper())
            meta = "  ·  ".join(meta_parts)
            if meta:
                meta = _truncate(draw, meta, fonts["event_meta"], max_w)
                draw.text((text_x, y), meta, font=fonts["event_meta"], fill=DARK_GRAY)
                y += 46

            # Tags
            if ev["tags"]:
                tag_str = "  ".join(f"#{t.replace(' ', '').upper()}" for t in ev["tags"])
                tag_str = _truncate(draw, tag_str, fonts["event_tags"], max_w)
                draw.text((text_x, y), tag_str, font=fonts["event_tags"], fill=MID_GRAY)
                y += 40

            # Pad to row bottom
            y = max(y + 8, row_bottom)

            if y >= body_y1 - 20:
                remaining = n - i - 1
                if remaining:
                    draw.line([(PADDING, y), (W - PADDING, y)], fill=BLACK, width=1)
                    more = f"+ {remaining} more event{'s' if remaining > 1 else ''}"
                    draw.text((text_x, y + 10), more, font=fonts["event_meta"], fill=MID_GRAY)
                break

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_y = H - FOOTER_H
    draw.rectangle([(0, footer_y), (W, H)], fill=BLACK)
    draw.line([(PADDING, footer_y), (W - PADDING, footer_y)], fill=WHITE, width=1)

    draw.text((PADDING, footer_y + 22), "NV & MORE", font=fonts["footer"], fill=WHITE)

    stamp = f"NV_2400  ·  07:00"
    sw = _text_width(draw, stamp, fonts["footer"])
    draw.text((W - PADDING - sw, footer_y + 22), stamp, font=fonts["footer"], fill=MID_GRAY)

    return img


# ── ntfy sending ──────────────────────────────────────────────────────────────

def send_image(img: Image.Image, events: list[dict], target_date: date):
    if not NTFY_TOPIC:
        print("⚠️  NTFY_TOPIC not set — skipping send")
        return

    date_str = target_date.strftime("%A %-d %B")

    # Message 1: the image
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    try:
        requests.put(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=buf.read(),
            headers={
                "Title":    f"Today in Nordvest — {date_str}",
                "Filename": f"today_{target_date.isoformat()}.png",
                "Tags":     "camera,sunrise",
                "Priority": "default",
            },
            timeout=30,
        )
        print("✅ Image sent via ntfy")
    except Exception as e:
        print(f"⚠️  Failed to send image: {e}")

    # Message 2: tags-only text for IG caption
    all_tags = []
    for ev in events:
        for t in ev["tags"]:
            tag = "#" + t.replace(" ", "").lower()
            if tag not in all_tags:
                all_tags.append(tag)

    # Add standard NV & more tags
    for fixed in ["#nordvest", "#nordvestkøbenhavn", "#nordvestmore", "#copenhagen", "#København"]:
        if fixed.lower() not in [t.lower() for t in all_tags]:
            all_tags.append(fixed)

    tags_text = "\n".join(all_tags)
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=tags_text.encode(),
            headers={
                "Title":    f"IG tags — {date_str}",
                "Tags":     "label",
                "Priority": "default",
            },
            timeout=30,
        )
        print("✅ Tags sent via ntfy")
    except Exception as e:
        print(f"⚠️  Failed to send tags: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    help="Override date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Generate image only, don't send")
    parser.add_argument("--out",     help="Save image to this path instead of temp file")
    args = parser.parse_args()

    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        import zoneinfo
        target_date = datetime.now(tz=zoneinfo.ZoneInfo("Europe/Copenhagen")).date()

    print(f"📅 Generating graphic for {target_date}")
    events = fetch_todays_events(target_date)
    print(f"📋 Found {len(events)} event(s)")
    for ev in events:
        print(f"   • {ev['time'] or '--:--'}  {ev['name']}  [{', '.join(ev['tags'])}]")

    img = render(events, target_date)

    if args.out:
        img.save(args.out)
        print(f"💾 Saved to {args.out}")
    elif args.dry_run:
        out = f"/tmp/today_nordvest_{target_date}.png"
        img.save(out)
        print(f"💾 Dry run — saved to {out}")
    else:
        send_image(img, events, target_date)


if __name__ == "__main__":
    main()
