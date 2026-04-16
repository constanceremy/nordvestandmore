#!/usr/bin/env python3
"""
today_graphic.py — Generate daily "Today in Nordvest" Instagram Story graphic.

Layout (1080×1920, white minimal aesthetic matching website):
  - Header:  "NV & MORE" + date label row  →  "Today in Nordvest" (Helvetica Neue Light)  →  1px black border-b
  - CTA strip (last slide only): "ALL EVENT DETAILS" (bold) + "nordvestandmore.com" (gray) + drawn arrow
  - Body: event list — meta line (TAG · TIME, gray) + name (mixed case, light) + gray dividers
  - Footer: 1px black border-t  +  "NORDVEST · COPENHAGEN" (gray, tracked)

Multi-slide: if events don't fit at minimum font size, they are split across multiple slides.
CTA appears only on the last slide. All slides share the same header/footer.

Sends via ntfy:
  1. Each slide image in order (PUT binary)
  2. IG caption bullets (POST text, for copy-paste)

Usage:
    python3 today_graphic.py
    python3 today_graphic.py --date 2026-04-16
    python3 today_graphic.py --dry-run
"""
import argparse
import base64
import io
import os
import pickle
import re
import smtplib
import sys
import tempfile
import urllib.parse
import uuid as uuidmod
from datetime import date, datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# ── Config ────────────────────────────────────────────────────────────────────

NOTION_TOKEN    = os.environ.get("NOTION_TOKEN", "")
NOTION_DB       = os.environ.get("NOTION_DATABASE_ID", "")
NTFY_TOPIC      = os.environ.get("NTFY_TOPIC", "")
GMAIL_USER      = os.environ.get("GMAIL_USER", "nordvestandmore@gmail.com")
GMAIL_APP_PASS  = os.environ.get("GMAIL_APP_PASSWORD", "")
IG_SESSION_B64  = os.environ.get("IG_SESSION_B64", "")
IG_USERNAME       = "nordvestandmore"   # sender
IG_RECIPIENT      = "constanceremy"     # receiver
IG_RECIPIENT_ID   = 186062440           # numeric ID — avoids a rate-limited API lookup

W, H = 1080, 1920

# Colours — matches website globals.css
BLACK     = (10, 10, 10)
WHITE     = (255, 255, 255)
BORDER    = (0, 0, 0)
META_GRAY = (130, 130, 130)
MID_GRAY  = META_GRAY
DIV_GRAY  = (210, 210, 210)

# Layout
HEADER_H   = int(H * 0.20)   # 384px
FOOTER_H   = int(H * 0.07)   # 134px
CTA_H      = 120              # strip reserved for CTA (between header border and first event)
BODY_TOP   = HEADER_H + CTA_H
BODY_H     = H - BODY_TOP - FOOTER_H   # available for events: ~1282px

PADDING    = 64
LINK_SPACE = 320   # px to the right of CTA text for link sticker

# Event typography
EVENT_FONT_MAX = 28
EVENT_FONT_MIN = 22
EVENT_GAP      = 36   # vertical gap between events
META_GAP       = 8    # gap between meta line and event name


# ── Font loading ──────────────────────────────────────────────────────────────

def _find_weighted_font(weight_keywords: list[str], exclude: list[str] | None = None) -> str | None:
    """Search system font dirs for a font whose filename contains any weight keyword."""
    exclude = exclude or []
    search_dirs = [
        "/usr/share/fonts", "/usr/local/share/fonts",
        str(Path.home() / ".fonts"),
        "/System/Library/Fonts", "/Library/Fonts",
        str(Path.home() / "Library/Fonts"),
    ]
    for d in search_dirs:
        root = Path(d)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            fname = p.name.lower()
            if any(ex in fname for ex in exclude):
                continue
            if any(kw in fname for kw in weight_keywords):
                return str(p)
    return None


def _find_light_spec() -> str | None:
    """Return path:index for Helvetica Neue Light on macOS, else any light/thin font."""
    mac_ttc = "/System/Library/Fonts/HelveticaNeue.ttc"
    if Path(mac_ttc).exists():
        try:
            f = ImageFont.truetype(mac_ttc, 40, index=7)
            if "Light" in f.getname()[1]:
                return f"{mac_ttc}:7"
        except Exception:
            pass
    path = _find_weighted_font(["light", "thin"], exclude=["italic", "oblique"])
    return path


def _find_bold_spec() -> str | None:
    """Return path:index for Helvetica Neue Bold on macOS, else any bold font."""
    mac_ttc = "/System/Library/Fonts/HelveticaNeue.ttc"
    if Path(mac_ttc).exists():
        try:
            f = ImageFont.truetype(mac_ttc, 40, index=1)
            name = f.getname()[1]
            if "Bold" in name and "Italic" not in name:
                return f"{mac_ttc}:1"
        except Exception:
            pass
    path = _find_weighted_font(["bold", "-bd", "b.ttf"], exclude=["italic", "oblique"])
    return path


def _find_regular_spec() -> str | None:
    """Return path for a regular (non-bold, non-italic) font."""
    mac_ttc = "/System/Library/Fonts/HelveticaNeue.ttc"
    if Path(mac_ttc).exists():
        return f"{mac_ttc}:0"
    path = _find_weighted_font(
        ["liberationsans-regular", "arial.ttf", "arial-regular",
         "dejavusans.ttf", "helveticaneue.ttc", "notosans-regular"],
        exclude=["bold", "italic", "oblique"],
    )
    if not path:
        # Download Inter as fallback
        url  = "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf"
        dest = "/tmp/nv_inter_var.ttf"
        if not Path(dest).exists():
            try:
                import urllib.request
                print("⬇️  Downloading Inter font…")
                urllib.request.urlretrieve(url, dest)
            except Exception as e:
                print(f"⚠️  Font download failed: {e}")
                return None
        return dest
    return path


def _load_spec(spec: str | None, size: int) -> ImageFont.FreeTypeFont:
    """Load a font from 'path:index' or 'path', fallback to default."""
    if not spec:
        return ImageFont.load_default(size)
    if ":" in spec:
        path, idx = spec.rsplit(":", 1)
        try:
            return ImageFont.truetype(path, size, index=int(idx))
        except Exception:
            pass
    try:
        return ImageFont.truetype(spec, size)
    except Exception:
        return ImageFont.load_default(size)


def _load_fonts() -> dict:
    light  = _find_light_spec()
    bold   = _find_bold_spec()
    reg    = _find_regular_spec()
    print(f"🔤 Light:   {light  or '(fallback)'}")
    print(f"🔤 Bold:    {bold   or '(fallback)'}")
    print(f"🔤 Regular: {reg    or '(fallback)'}")
    return {"light": light, "bold": bold, "reg": reg}


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _tracked_width(draw: ImageDraw, text: str, font: ImageFont, tracking: int = 0) -> int:
    total = 0
    for ch in text:
        bb = draw.textbbox((0, 0), ch, font=font)
        total += (bb[2] - bb[0]) + tracking
    return max(total - tracking, 0)


def _draw_tracked(draw: ImageDraw, xy: tuple, text: str, font: ImageFont,
                  fill, tracking: int = 0) -> int:
    """Draw letter-spaced text. Returns final x position."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        bb = draw.textbbox((0, 0), ch, font=font)
        x += (bb[2] - bb[0]) + tracking
    return x


def _font_height(draw: ImageDraw, font: ImageFont) -> int:
    bb = draw.textbbox((0, 0), "A", font=font)
    return bb[3] - bb[1]


def _wrap_lines(draw: ImageDraw, text: str, font: ImageFont,
                max_w: int, tracking: int = 0) -> list[str]:
    words = text.split()
    lines, cur = [], []
    for w in words:
        candidate = " ".join(cur + [w])
        if _tracked_width(draw, candidate, font, tracking) <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines or [text]


def _draw_arrow(draw: ImageDraw, cx: int, cy: int, size: int,
                color, lw: int = 3):
    """Draw a → arrow centred at (cx, cy). size = half-length of shaft."""
    draw.line([(cx - size, cy), (cx + size, cy)], fill=color, width=lw)
    tip = size // 2
    draw.line([(cx + size, cy), (cx + size - tip, cy - tip)], fill=color, width=lw)
    draw.line([(cx + size, cy), (cx + size - tip, cy + tip)], fill=color, width=lw)


# ── Slide splitting ───────────────────────────────────────────────────────────

def _measure_events_height(events: list[dict], font_name: ImageFont,
                            font_meta: ImageFont, draw: ImageDraw,
                            max_w: int) -> int:
    """Return the pixel height needed to render a list of events."""
    name_h = _font_height(draw, font_name)
    meta_h = _font_height(draw, font_meta)
    total  = EVENT_GAP  # top padding before first event

    for i, ev in enumerate(events):
        if i > 0:
            total += EVENT_GAP  # gap + divider between events

        # Meta line
        total += meta_h + META_GAP

        # Name (word-wrapped)
        lines  = _wrap_lines(draw, ev["name"], font_name, max_w, 1)
        total += len(lines) * name_h + (len(lines) - 1) * 2

    return total


def _split_into_slides(events: list[dict], fonts: dict) -> list[list[dict]]:
    """
    Greedily split events into slides.
    Each slide uses EVENT_FONT_MAX for its events.
    If a chunk overflows BODY_H we shrink the chunk until it fits.
    """
    if not events:
        return [[]]

    tmp  = Image.new("RGB", (W, H))
    d    = ImageDraw.Draw(tmp)
    fnom = _load_spec(fonts["reg"],   EVENT_FONT_MAX)
    fmet = _load_spec(fonts["reg"],   18)
    max_w = W - PADDING * 2

    slides    = []
    remaining = list(events)

    while remaining:
        chunk = []
        for ev in remaining:
            candidate = chunk + [ev]
            if _measure_events_height(candidate, fnom, fmet, d, max_w) <= BODY_H:
                chunk = candidate
            else:
                break
        if not chunk:
            # Single event overflows (very long name) — force it onto its own slide
            chunk = [remaining[0]]
        slides.append(chunk)
        remaining = remaining[len(chunk):]

    return slides


# ── Notion data fetch ─────────────────────────────────────────────────────────

def _parse_time_minutes(time_str: str) -> int:
    if not time_str or time_str == "—":
        return 99 * 60
    s = time_str.strip().lower()
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)?", s)
    if not m:
        return 99 * 60
    h, mn, meridiem = int(m.group(1)), int(m.group(2)), m.group(3)
    if meridiem == "pm" and h != 12:
        h += 12
    elif meridiem == "am" and h == 12:
        h = 0
    return h * 60 + mn


def fetch_todays_events(target_date: date) -> list[dict]:
    if not NOTION_TOKEN or not NOTION_DB:
        print("⚠️  NOTION_TOKEN or NOTION_DATABASE_ID not set — using empty event list")
        return []

    date_str = target_date.isoformat()
    headers  = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type":   "application/json",
    }
    payload = {
        "page_size": 100,
        "filter": {
            "and": [
                {"property": "Start Date", "date":     {"equals": date_str}},
                {"property": "Approved",   "checkbox": {"equals": True}},
                {"property": "Deleted",    "checkbox": {"equals": False}},
            ]
        },
    }
    try:
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
            headers=headers, json=payload, timeout=30,
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
        time_str   = time_parts[0]["text"]["content"] if time_parts else ""

        ig_prop    = p.get("IG post", {})
        ig_caption = (ig_prop.get("formula") or {}).get("string", "").strip()

        loc_parts  = p.get("Location", {}).get("rich_text", [])
        location   = loc_parts[0]["text"]["content"] if loc_parts else ""

        tag_list_ms = p.get("Tag List", {}).get("multi_select", [])
        tags = [t["name"] for t in tag_list_ms]
        if not tags:
            tags_ms = p.get("Tags", {}).get("multi_select", [])
            tags = [t["name"] for t in tags_ms]
        if not tags:
            sel = (p.get("Tags", {}).get("select") or {}).get("name", "")
            tags = [sel] if sel else []

        # Strip leading time prefix from IG caption for graphic display
        ig_display = ig_caption
        if ig_display:
            ig_display = re.sub(
                r"^•\s*(?:All day|\d{1,2}:\d{2}[ap]m)\s*-\s*", "", ig_display
            ).strip()

        events.append({
            "name":       ig_display if ig_display else name,
            "ig_caption": ig_caption,
            "time":       time_str,
            "location":   location,
            "tags":       tags,
            "_sort_key":  _parse_time_minutes(time_str),
        })

    events.sort(key=lambda e: e["_sort_key"])
    return events


# ── Slide rendering ───────────────────────────────────────────────────────────

def _render_header(draw: ImageDraw, fonts: dict, target_date: date):
    """Draw the header on an existing draw surface (shared across all slides)."""

    def _ordinal(n: int) -> str:
        if 11 <= (n % 100) <= 13:
            return f"{n}TH"
        return f"{n}" + {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")

    # Label row: NV & MORE (left)  ·  date (right)
    label_fnt      = _load_spec(fonts["reg"], 22)
    label_tracking = 7
    label_y        = 48

    day_name   = target_date.strftime("%A").upper()
    month_name = target_date.strftime("%B").upper()
    date_label = f"{day_name}  {month_name} {_ordinal(target_date.day)}"
    dw         = _tracked_width(draw, date_label, label_fnt, label_tracking)
    _draw_tracked(draw, (PADDING, label_y),            "NV & MORE", label_fnt, META_GRAY, label_tracking)
    _draw_tracked(draw, (W - PADDING - dw, label_y),   date_label,  label_fnt, META_GRAY, label_tracking)

    # Title: "Today in Nordvest" — Helvetica Neue Light
    title = "Today in Nordvest"
    for sz in range(120, 30, -2):
        fnt_title = _load_spec(fonts["light"], sz)
        if _tracked_width(draw, title, fnt_title, 1) <= W - PADDING * 2:
            break
    _draw_tracked(draw, (PADDING, label_y + 36), title, fnt_title, BLACK, 1)

    # 1px black border-b
    draw.line([(0, HEADER_H), (W, HEADER_H)], fill=BORDER, width=2)


def _render_cta(draw: ImageDraw, fonts: dict):
    """Draw the CTA strip (no rectangle, no border line) — last slide only."""
    line1_text     = "ALL EVENT DETAILS"
    line1_fnt      = _load_spec(fonts["bold"], 32)
    line1_tracking = 5

    line2_text     = "NORDVESTANDMORE.COM"
    line2_fnt      = _load_spec(fonts["reg"], 20)
    line2_tracking = 4

    line_gap   = 18
    arrow_len  = 32
    arrow_gap  = 20   # gap between right edge of text block and arrow centre

    line1_h = _font_height(draw, line1_fnt)
    line2_h = _font_height(draw, line2_fnt)
    line1_w = _tracked_width(draw, line1_text, line1_fnt, line1_tracking)
    line2_w = _tracked_width(draw, line2_text, line2_fnt, line2_tracking)

    block_h    = line1_h + line_gap + line2_h
    block_y    = HEADER_H + (CTA_H - block_h) // 2
    text_right = W - LINK_SPACE   # right edge of text (arrow is further right)

    # Line 1: bold
    bb1     = draw.textbbox((0, 0), line1_text, font=line1_fnt)
    text1_y = block_y - bb1[1]
    _draw_tracked(draw, (text_right - line1_w, text1_y), line1_text, line1_fnt, BLACK, line1_tracking)

    # Line 2: URL in gray
    bb2     = draw.textbbox((0, 0), line2_text, font=line2_fnt)
    text2_y = text1_y + line1_h + line_gap - bb2[1]
    _draw_tracked(draw, (text_right - line2_w, text2_y), line2_text, line2_fnt, META_GRAY, line2_tracking)

    # Arrow: centred between the two lines, to the right of text block
    arrow_cx = text_right + arrow_gap + arrow_len
    arrow_cy = block_y + line1_h + line_gap // 2
    _draw_arrow(draw, arrow_cx, arrow_cy, arrow_len, BLACK, lw=3)


def _render_footer(draw: ImageDraw, fonts: dict,
                   slide_num: int, total_slides: int):
    """Draw the footer."""
    footer_y = H - FOOTER_H
    draw.line([(0, footer_y), (W, footer_y)], fill=BORDER, width=2)

    foot_fnt      = _load_spec(fonts["reg"], 22)
    foot_tracking = 7
    stamp         = "NORDVEST · COPENHAGEN"
    fh            = _font_height(draw, foot_fnt)
    foot_text_y   = footer_y + (FOOTER_H - fh) // 2

    _draw_tracked(draw, (PADDING, foot_text_y), stamp, foot_fnt, META_GRAY, foot_tracking)

    # Multi-slide: show page indicator on the right
    if total_slides > 1:
        indicator = f"{slide_num} / {total_slides}"
        ind_w     = _tracked_width(draw, indicator, foot_fnt, foot_tracking)
        _draw_tracked(draw, (W - PADDING - ind_w, foot_text_y), indicator, foot_fnt, META_GRAY, foot_tracking)


def _render_events(draw: ImageDraw, events: list[dict], fonts: dict):
    """Render event rows into the body area."""
    if not events:
        fnt = _load_spec(fonts["bold"], 64)
        msg = "NO EVENTS TODAY"
        mw  = _tracked_width(draw, msg, fnt, 6)
        _draw_tracked(draw, ((W - mw) // 2, BODY_TOP + BODY_H // 2 - 40), msg, fnt, MID_GRAY, 6)
        return

    font_name = _load_spec(fonts["reg"], EVENT_FONT_MAX)
    font_meta = _load_spec(fonts["reg"], 18)
    max_w     = W - PADDING * 2
    name_h    = _font_height(draw, font_name)
    meta_h    = _font_height(draw, font_meta)

    y = BODY_TOP + EVENT_GAP

    for i, ev in enumerate(events):
        if i > 0:
            draw.line([(PADDING, y - EVENT_GAP // 2), (W - PADDING, y - EVENT_GAP // 2)],
                      fill=DIV_GRAY, width=1)

        # Meta: TAG  ·  TIME
        tag_str  = ev["tags"][0].upper() if ev.get("tags") else ""
        time_str = (ev["time"] or "").upper()
        meta     = f"{tag_str}  ·  {time_str}" if tag_str and time_str else (tag_str or time_str)
        if meta:
            _draw_tracked(draw, (PADDING, y), meta, font_meta, MID_GRAY, 4)
        y += meta_h + META_GAP

        # Event name (word-wrapped, light weight)
        lines = _wrap_lines(draw, ev["name"], font_name, max_w, 1)
        for li, line in enumerate(lines):
            _draw_tracked(draw, (PADDING, y), line, font_name, BLACK, 1)
            y += name_h + (2 if li < len(lines) - 1 else 0)

        y += EVENT_GAP


def render_slide(events: list[dict], target_date: date, fonts: dict,
                 show_cta: bool, slide_num: int, total_slides: int) -> Image.Image:
    img  = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    _render_header(draw, fonts, target_date)
    if show_cta:
        _render_cta(draw, fonts)
    _render_events(draw, events, fonts)
    _render_footer(draw, fonts, slide_num, total_slides)

    return img


def render_all(events: list[dict], target_date: date) -> tuple[list[Image.Image], list[list[dict]]]:
    """Returns (images, slides) — one image and one event-list per slide."""
    fonts  = _load_fonts()
    slides = _split_into_slides(events, fonts)
    total  = len(slides)

    print(f"📊 {len(events)} event(s) → {total} slide(s)")

    images = []
    for i, chunk in enumerate(slides):
        slide_num = i + 1
        print(f"   Slide {slide_num}/{total}: {len(chunk)} event(s)")
        img = render_slide(chunk, target_date, fonts,
                           show_cta=True,
                           slide_num=slide_num,
                           total_slides=total)
        images.append(img)

    return images, slides


# ── ntfy sending ──────────────────────────────────────────────────────────────

def send_email(images: list[Image.Image], slides: list[list[dict]], target_date: date):
    """Send each slide as an image attachment + @mentions as body text."""
    if not GMAIL_APP_PASS:
        print("⚠️  GMAIL_APP_PASSWORD not set — skipping email")
        return

    date_str = target_date.strftime("%A %-d %B")

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg["Subject"] = f"Today in Nordvest - {date_str}"

    # Body: @mentions per slide, separated by slide header
    body_parts = []
    for i, slide_events in enumerate(slides, 1):
        if len(slides) > 1:
            body_parts.append(f"--- Slide {i} ---")
        seen, mentions = set(), []
        for ev in slide_events:
            for handle in re.findall(r"@[\w.]+", ev.get("ig_caption") or ev.get("name") or ""):
                if handle.lower() not in seen:
                    seen.add(handle.lower())
                    mentions.append(handle)
        body_parts.append("\n".join(mentions) if mentions else "(no @mentions)")
    msg.attach(MIMEText("\n\n".join(body_parts), "plain"))

    # Attach each slide image
    for i, img in enumerate(images, 1):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        part = MIMEImage(buf.getvalue(), name=f"today_{target_date}_{i}.png")
        part["Content-Disposition"] = f'attachment; filename="today_{target_date}_{i}.png"'
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASS)
            smtp.send_message(msg)
        print(f"✅ Email sent to {GMAIL_USER}")
    except Exception as e:
        print(f"⚠️  Email failed: {e}")


def _build_caption(slide_events: list[dict]) -> str:
    """Extract all @mentions from the slide's events — one per line, no duplicates."""
    seen = set()
    mentions = []
    for ev in slide_events:
        source = ev.get("ig_caption") or ev.get("name") or ""
        for handle in re.findall(r"@[\w.]+", source):
            if handle.lower() not in seen:
                seen.add(handle.lower())
                mentions.append(handle)
    return "\n".join(mentions) if mentions else "(no @mentions found)"


def send_images(images: list[Image.Image], slides: list[list[dict]], target_date: date):
    if not NTFY_TOPIC:
        print("⚠️  NTFY_TOPIC not set — skipping send")
        return

    date_str   = target_date.strftime("%A %-d %B")
    total      = len(images)
    multi      = total > 1

    for i, (img, slide_events) in enumerate(zip(images, slides)):
        slide_num   = i + 1
        slide_label = f" ({slide_num}/{total})" if multi else ""

        # Image
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        try:
            requests.put(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=buf.read(),
                headers={
                    "Title":    f"Today in Nordvest - {date_str}{slide_label}",
                    "Filename": f"today_{target_date.isoformat()}_{slide_num}.png",
                    "Tags":     "camera,sunrise",
                    "Priority": "default",
                },
                timeout=30,
            )
            print(f"✅ Slide {slide_num} image sent via ntfy")
        except Exception as e:
            print(f"⚠️  Failed to send slide {slide_num} image: {e}")

        # Caption for this slide
        caption = _build_caption(slide_events)
        caption_label = f"IG caption{slide_label} - {date_str}"
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=caption.encode(),
                headers={
                    "Title":    caption_label,
                    "Tags":     "label",
                    "Priority": "default",
                },
                timeout=30,
            )
            print(f"✅ Slide {slide_num} caption sent via ntfy")
        except Exception as e:
            print(f"⚠️  Failed to send slide {slide_num} caption: {e}")


# ── Instagram DM sending ──────────────────────────────────────────────────────

def _all_mentions(slides: list[list[dict]]) -> str:
    """Return deduplicated @mentions across all slides, one per line."""
    seen, mentions = set(), []
    for ev in (ev for slide in slides for ev in slide):
        for handle in re.findall(r"@[\w.]+", ev.get("ig_caption") or ev.get("name") or ""):
            if handle.lower() not in seen:
                seen.add(handle.lower())
                mentions.append(handle)
    return "\n".join(mentions) if mentions else "(no @mentions)"


def _ig_session() -> tuple[str, str, int] | None:
    """
    Decode IG_SESSION_B64 → (sessionid, csrftoken, user_id).
    user_id is extracted from the sessionid string (no API call needed).
    Returns None if the secret is missing or unparseable.
    """
    if not IG_SESSION_B64:
        return None
    try:
        data      = pickle.loads(base64.b64decode(IG_SESSION_B64))
        sessionid = data.get("sessionid") or data.get("session_id", "")
        csrftoken = data.get("csrftoken", "")
        if not sessionid:
            return None
        user_id = int(urllib.parse.unquote(sessionid).split(":")[0])
        return sessionid, csrftoken, user_id
    except Exception as e:
        print(f"⚠️  Could not parse IG_SESSION_B64: {e}")
        return None


def _ig_session_requests(sessionid: str, csrftoken: str) -> requests.Session:
    """Build a requests.Session that looks like an Instagram browser client."""
    sess = requests.Session()
    sess.headers.update({
        "User-Agent":          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/124.0.0.0 Safari/537.36",
        "X-IG-App-ID":         "936619743392459",
        "X-CSRFToken":         csrftoken,
        "X-Instagram-AJAX":    "1",
        "Content-Type":        "application/x-www-form-urlencoded",
        "Origin":              "https://www.instagram.com",
        "Referer":             "https://www.instagram.com/direct/inbox/",
    })
    sess.cookies.set("sessionid", sessionid, domain=".instagram.com")
    if csrftoken:
        sess.cookies.set("csrftoken", csrftoken, domain=".instagram.com")
    return sess


def send_instagram_dm(images: list[Image.Image], slides: list[list[dict]], target_date: date):
    """
    Send @mentions text + each slide image as a DM from nordvestandmore to itself.
    Uses the Instagram web API directly (browser session, no instagrapi needed).
    """
    creds = _ig_session()
    if not creds:
        print("⚠️  IG_SESSION_B64 not set or invalid — skipping Instagram DM")
        return

    sessionid, csrftoken, _ = creds
    sess    = _ig_session_requests(sessionid, csrftoken)
    ig_base = "https://www.instagram.com/api/v1"

    recipient_id = IG_RECIPIENT_ID
    print(f"📲 Instagram DM {IG_USERNAME} → {IG_RECIPIENT} (uid={recipient_id})")

    # Send @mentions text first
    try:
        r = sess.post(
            f"{ig_base}/direct_v2/threads/broadcast/text/",
            data={
                "recipient_users": f"[[{recipient_id}]]",
                "action":          "send_item",
                "client_context":  uuidmod.uuid4().hex,
                "text":            _all_mentions(slides),
            },
            timeout=30,
        )
        if r.ok:
            print("✅ @mentions sent via Instagram DM")
        else:
            print(f"⚠️  Instagram DM text failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"⚠️  Instagram DM text error: {e}")

    # Send each slide image (multipart upload + broadcast in one step)
    for i, img in enumerate(images, 1):
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            img.convert("RGB").save(tmp.name, format="JPEG", quality=95)
            tmp.close()
            img_bytes = Path(tmp.name).read_bytes()

            br = sess.post(
                f"{ig_base}/direct_v2/threads/broadcast/upload_photo/",
                files={"photo": (f"today_{target_date}_{i}.jpg", img_bytes, "image/jpeg")},
                data={
                    "recipient_users": f"[[{recipient_id}]]",
                    "action":          "send_item",
                    "client_context":  uuidmod.uuid4().hex,
                },
                timeout=60,
            )
            if br.ok:
                print(f"✅ Slide {i} image sent via Instagram DM")
            else:
                print(f"⚠️  Instagram DM photo failed (slide {i}): {br.status_code} {br.text[:200]}")
        except Exception as e:
            print(f"⚠️  Instagram DM photo error (slide {i}): {e}")
        finally:
            Path(tmp.name).unlink(missing_ok=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    help="Override date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate images only, don't send")
    parser.add_argument("--out",     help="Save first image to this path")
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

    images, slides = render_all(events, target_date)

    if args.out:
        images[0].save(args.out)
        print(f"💾 Saved slide 1 to {args.out}")
        for i, img in enumerate(images[1:], 2):
            p = args.out.replace(".png", f"_{i}.png")
            img.save(p)
            print(f"💾 Saved slide {i} to {p}")
    elif args.dry_run:
        for i, (img, slide_events) in enumerate(zip(images, slides), 1):
            out = f"/tmp/today_nordvest_{target_date}_{i}.png"
            img.save(out)
            print(f"💾 Dry run — saved to {out}")
            print(f"   Caption preview:\n{_build_caption(slide_events)}\n")
    else:
        send_email(images, slides, target_date)
        send_instagram_dm(images, slides, target_date)


if __name__ == "__main__":
    main()
