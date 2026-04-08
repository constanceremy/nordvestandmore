# NV & more — System Overview

This document describes every moving part of the NV & more platform.

---

## Overview

NV & more is a Copenhagen events and experiences platform. It has two main functions:
1. **Community events feed** — scrapes events from Instagram, Facebook, and venue websites and displays them in a filterable list
2. **Own experiences** — bookable events run by NV & more, with Stripe payments, Supabase bookings, and Notion as the CMS

---

## Repos & Hosting

| Thing | Where |
|-------|-------|
| Code | GitHub: `constanceremy/nordvestandmore` |
| Website | Vercel: `nordvestandmore.vercel.app` (future: nordvestandmore.com) |
| Scraper jobs | GitHub Actions on a self-hosted Mac runner (for Instagram) and GitHub-hosted runner (for everything else) |

---

## Website

**Stack:** Next.js 16, React 19, Tailwind CSS v4, deployed on Vercel

**Root directory on Vercel:** `nordvestandmore/website`

**Cache:** Pages revalidate every 60 minutes (ISR). To force an immediate refresh, trigger a redeploy on Vercel.

### Design

- **Heading font:** DM Serif Display (serif, from Google Fonts)
- **Body font:** System sans-serif
- **Style inspiration:** Tipster.io — thin/light weight sans, all-caps labels, editorial grid
- **Palette:** Black and white, minimal — uppercase tracking, border-black grid aesthetic
- **Logo:** Pink circle (`/public/logo.jpg`) in nav

### Pages

| URL | What it does |
|-----|-------------|
| `/` | Home — hero, upcoming events strip, latest blog posts |
| `/events` | Community events feed — filterable by date/period and location |
| `/events/[slug]` | Detail page for NV & more's own events (scraped events link externally) |
| `/with-us` | NV & more's own bookable sessions list |
| `/with-us/[id]` | Session detail page with booking CTA |
| `/blog` | Blog post list |
| `/blog/[slug]` | Blog post detail (renders Notion blocks) |
| `/about` | About page |
| `/terms` | Terms of Sale (pulled from Notion) |
| `/privacy` | Privacy Policy (pulled from Notion) |
| `/booking/success` | Post-payment confirmation page |

### Key source files

| File | Purpose |
|------|---------|
| `src/lib/notion.ts` | All Notion queries and TypeScript types |
| `src/lib/stripe.ts` | Stripe client |
| `src/lib/supabase.ts` | Supabase client |
| `src/components/Nav.tsx` | Sticky nav with logo, desktop links, mobile drawer |
| `src/components/Footer.tsx` | Footer with links, social, copyright |
| `src/components/BookButton.tsx` | Stripe checkout trigger button |
| `src/components/EventFilters.tsx` | Date/period pills + location combobox (desktop & mobile) |
| `src/components/NotionBlocks.tsx` | Renders Notion block content for blog posts |
| `src/app/api/checkout/route.ts` | Creates Stripe checkout session |
| `src/app/api/webhook/route.ts` | Handles Stripe webhook after payment |

### Key npm dependencies

| Package | Purpose |
|---------|---------|
| `@notionhq/client` | Notion API |
| `stripe` | Stripe server SDK |
| `@stripe/stripe-js` | Stripe client SDK |
| `@supabase/supabase-js` | Supabase client |
| `nodemailer` | Confirmation emails via Gmail SMTP |
| `lucide-react` | Icons |
| `tailwindcss` v4 | Styling |

---

## Notion (CMS)

Notion is the content management layer. All content is managed here and pulled by the website.

| Database | ID | Purpose |
|----------|----|---------|
| Events | `283375efa2cc80678d42f5b20163c523` | Community + own events |
| Blog | `31e375efa2cc8094a237c22281705373` | Blog posts |
| Experiences | `320375efa2cc809ca2dae69a1aa15423` | NV & more experience templates |
| Sessions | `320375efa2cc8068b2b4f8428008d1ff` | Dated instances of experiences |
| Booking Policies | `320375efa2cc8053872ee9636f1b100e` | Cancellation/booking rules |
| Terms of Sale | `320375efa2cc805caf4edd4e2b0ddf36` | Terms page content (Notion page, not DB) |
| Privacy Policy | `320375efa2cc80beaa21d8119d085d55` | Privacy policy content (Notion page, not DB) |

### Key Notion fields

**Events DB**
- `Own Event` checkbox — if checked, links internally on the website; if unchecked, links externally
- `Approved` checkbox — must be checked for the event to appear on the website (own events bypass this)
- `Possible Duplicate` checkbox — if checked, event is hidden
- `Deleted` checkbox — if checked, event is hidden

**Sessions DB**
- `Booked spots` — incremented automatically by the webhook on every confirmed payment
- `Max spots` — controls availability display and sold-out state
- `Experience` — relation to Experiences DB
- `Status` — must be "Open" for session to appear
- `Price override` — overrides the experience-level price if set

**Experiences DB**
- `Stripe Product ID` — the `prod_...` ID from Stripe, links the experience to a Stripe product
- `Active` checkbox — controls whether experience appears on `/with-us`

---

## Booking Flow

When a user books a session on `/with-us/[id]`:

```
User clicks "Book now"
  → POST /api/checkout
    → Creates Stripe Checkout Session (price_data with product ID, phone collection enabled)
    → Returns checkout URL
  → User redirected to Stripe
  → User pays
  → Stripe fires checkout.session.completed webhook
  → POST /api/webhook
    → Verifies Stripe signature
    → Saves booking to Supabase (bookings table)
    → Increments "Booked spots" in Notion Sessions DB
    → Sends confirmation email via Gmail SMTP
  → User lands on /booking/success
```

### Supabase — bookings table

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | Auto-generated |
| `event_id` | text | Notion Session page ID |
| `event_slug` | text | Notion Session page ID (used as slug) |
| `event_date` | text | ISO date of the session |
| `name` | text | From Stripe customer details |
| `email` | text | From Stripe customer details |
| `phone` | text | From Stripe phone collection |
| `stripe_session_id` | text | Stripe checkout session ID |
| `stripe_payment_intent` | text | Stripe payment intent ID |
| `amount_paid` | numeric | In major currency units (e.g. 150, not 15000) |
| `currency` | text | e.g. DKK |
| `status` | text | Always "confirmed" for now |
| `created_at` | timestamp | Auto-generated |

Supabase project: `lpjewaznxlggjoxdetsh.supabase.co`

---

## Stripe

- Currently in **test mode** — no real payments
- Switch to live mode before launch: swap `sk_test_` / `pk_test_` keys for `sk_live_` / `pk_live_` and create a new live webhook endpoint
- Webhook endpoint registered at: `https://nordvestandmore.vercel.app/api/webhook`
- Event listened to: `checkout.session.completed`
- Test card: `4242 4242 4242 4242`, any future expiry, any CVC

---

## Scraper

The scraper populates the Notion Events DB with community events. It runs via GitHub Actions.

### Sources

| Scraper | What it scrapes | Schedule |
|---------|----------------|---------|
| Instagram drip scraper | ~144 IG accounts | Every 30 min (5 accounts/run) on self-hosted Mac runner |
| Web scraper | Venue websites (Vierrummet, Lygten, Thoravej 29, etc.) | Daily at ~9:30 PM Copenhagen |
| Facebook scraper | Facebook pages | Daily (same job as web scraper) |

### GitHub Actions workflows

| Workflow | File | Schedule | Runner |
|----------|------|---------|--------|
| Scrape Events | `scrape-events.yml` | Daily 19:30 UTC | GitHub-hosted (Ubuntu) |
| Instagram Drip Scraper | `scrape-ig-drip.yml` | Every 30 minutes | Self-hosted Mac (residential IP) |
| Sync to Wix | `sync-to-wix.yml` | Daily 03:00 UTC | GitHub-hosted (to be retired) |

> The self-hosted Mac runner is required for Instagram scraping to avoid rate limits — a residential IP is needed.

### Scraper filter (what gets shown on website)

Events appear only if:
- Not deleted
- Not marked as a possible duplicate
- Start date is today or in the future
- Either: `Approved = true` OR `Own Event = true`

### source_mapping.csv

Master list of all venues/accounts (`scraper/source_mapping.csv`). Maps venue names to Instagram handles, Facebook pages, and websites. Used by the scraper as the single source of truth for what to scrape and by `dedup.py` to match cross-platform events to the same venue.

Columns: `name, instagram, facebook, fb_filter, fb_exclude, website, priority`

### AI extraction

The scraper uses **Google Gemini** (free tier) to extract structured event data (title, date, time, location, description) from Instagram posts and website HTML.

### Key scraper files

| File | Purpose |
|------|---------|
| `scraper/run_scraper.py` | Main entry point — orchestrates all scrapers |
| `scraper/scrape_posts.py` | Manual Instagram post scraper (interactive) |
| `scraper/ig_scraper/drip_scrape.py` | Instagram drip scraper (30-min batches) |
| `scraper/ig_scraper/scrape_instagram_events.py` | Core IG scraping logic |
| `scraper/fb_scraper/scrape_facebook_events.py` | Facebook events scraper |
| `scraper/web_scraper/scrape_website_events.py` | Website/venue scraper |
| `scraper/nv_scraper/scrape_vierrummet.py` | Vierrummet-specific scraper |
| `scraper/nv_scraper/scrape_thoravej29.py` | Thoravej 29-specific scraper |
| `scraper/dedup.py` | Cross-platform duplicate detection and flagging |
| `scraper/auto_tag.py` | Auto-tags events by keyword/pattern (~40+ rules) |
| `scraper/fix_locations.py` | Normalises location names |
| `scraper/recurring_events.py` | Handles recurring event logic |
| `scraper/deals_db.py` | Pushes deals/promotions to Notion |
| `scraper/hours_db.py` | Manages business hours in Notion |
| `scraper/cleanup_duplicates.py` | Removes/merges flagged duplicates |
| `scraper/retag_all.py` | Bulk re-tags all existing events |
| `scraper/sync_to_wix.py` | Syncs Notion events to legacy Wix CMS (to be retired) |
| `scraper/scrape_wix_blog.py` | One-off: imported blog posts from Wix |
| `scraper/fill_blog_content.py` | Fills missing content in imported blog posts |
| `scraper/count_mentions.py` | Counts how often IG accounts are mentioned |
| `scraper/_import_browser_session.py` | Imports Instaloader session from browser cookies |

---

## Email

Confirmation emails are sent via **Gmail SMTP** (nodemailer) from `nordvestandmore@gmail.com` using a Google App Password.

**Planned:** Reminder emails the day before an event — to be built as a GitHub Actions cron job querying Supabase for `event_date = tomorrow`.

---

## Environment Variables

### Website (`website/.env.local` + Vercel project settings)

| Variable | Purpose |
|----------|---------|
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_EVENTS_DB_ID` | Events database |
| `NOTION_BLOG_DB_ID` | Blog database |
| `NOTION_EXPERIENCES_DB_ID` | Experiences database |
| `NOTION_SESSIONS_DB_ID` | Sessions database |
| `NOTION_BOOKING_POLICIES_DB_ID` | Booking policies database |
| `NOTION_TC_PAGE_ID` | Terms of Sale page |
| `STRIPE_SECRET_KEY` | Stripe server-side key |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe client-side key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `GMAIL_USER` | Gmail address for sending emails |
| `GMAIL_APP_PASSWORD` | Gmail App Password |

### Scraper (`.env` at repo root + GitHub Actions secrets)

| Variable | Purpose |
|----------|---------|
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_DATABASE_ID` | Events database |
| `GEMINI_API_KEY` | Google Gemini API (AI event extraction) |
| `WIX_API_KEY` | Wix CMS API (for sync, to be retired) |
| `WIX_SITE_ID` | Wix site ID |
| `IG_SESSION_B64` | Base64-encoded Instaloader session file (GitHub secret) |
| `FB_COOKIES_B64` | Base64-encoded Facebook session cookies (GitHub secret) |

---

## What's still to do

### Booking flow
- [x] Stripe live keys in Vercel
- [x] Stripe live webhook + STRIPE_WEBHOOK_SECRET
- [x] Booking saved to Supabase on payment, deduplication in place
- [x] Confirmation email to booker + notification email to nordvestandmore@gmail.com
- [x] Sold-out status on website (sessions page + detail page)
- [ ] Fill in start times for sessions in Notion
- [ ] Test full booking flow end-to-end with live Stripe keys
- [ ] Build reminder email cron job (day before event, queries Supabase)

### Beta testing
- [ ] Send DMs to Instagram followers — code **NVANDMORE100**, expires Apr 12
- [ ] Collect feedback on booking flow, events page, "With us" tab, naming/clarity
- [ ] Ask: *"Is there anything missing that would make you use this to plan your week and stay on top of what's going on in the neighbourhood? Any features you'd want to see?"*

### Guide / Locations feature
The guide is a filterable map + list of favourite NV spots, linked to events and articles.
Import file ready: `Downloads/locations_notion_import.csv` (67 spots, coords from Google My Maps KML)

**Step 1 — Notion setup (manual)**
- [ ] Create Locations DB — fields: Name (title), Tags (multi-select), Description (text), Address (text), Instagram (text), Website (url), Lat (number), Lng (number), Published (checkbox)
- [ ] Import `locations_notion_import.csv`; switch Tags→multi-select, Lat/Lng→number, Published→checkbox after import
- [ ] Fill in missing coordinates for 10 spots: Ansgarkirken, Dansekapellet, Kapernaumskirken, Lygten Station, Nordic Health House, Tagensbo Kirke, TegneskoleKBH, Thoravej 29, Ungdomshuset, Urban 13
- [ ] Add "Venue" relation field on Events DB → Locations DB
- [ ] Add "Places mentioned" relation field on Blog DB → Locations DB
- [ ] Link existing events to their venues in Notion
- [ ] Link existing blog posts to places they mention (33 spots already have article links in the CSV)
- [ ] Add descriptions + Instagram/website per location (can do gradually)
- [ ] Add `NOTION_LOCATIONS_DB_ID` to `.env.local`, Vercel env vars, and GitHub Actions secrets
- [ ] Share Locations DB ID so code work can begin

**Step 1b — Scraper auto-linking (once Locations DB exists)**
- [ ] Build `scraper/locations_cache.py` — fetches all Published locations from Notion at startup, builds normalised name→ID lookup dict
- [ ] All scrapers (nv_scraper, web_scraper, fb_scraper, ig_scraper): after writing text Location field, fuzzy-match name against cache → if matched, PATCH the Venue relation field on the event
- [ ] Unmatched locations skip silently — no breakage to existing scraper behaviour

**Step 2 — Website (once Locations DB exists)**
- [ ] Add `getLocations()` and `getLocationBySlug()` to `src/lib/notion.ts`
- [ ] Build `/guide` page — tag filter pills (same style as events), Leaflet + OpenStreetMap map (free), list of spots
- [ ] Build `/guide/[slug]` location detail page — name, tags, description, map pin, Instagram/website links, "Events here" (from Venue relation), "Read about it" (from Places mentioned relation)
- [ ] On `/events/[slug]` — show "Venue" as a link to `/guide/[slug]` if relation exists
- [ ] On `/blog/[slug]` — show "Places in this article" as linked chips if relation exists
- [ ] Add "Guide" link to main navigation
- [ ] Include locations in `/api/search` results

### Content
- [ ] Fix remaining blog posts in Notion — inline images and links missing from Wix import

### Legal
- [ ] Privacy policy page (GDPR required — collecting emails + payments)

### Launch
- [ ] Connect custom domain `nordvestandmore.com` (Wix → Vercel)
- [ ] Add Vercel Analytics or Plausible
- [ ] Retire Wix sync once website is live

### Tech debt
- [ ] Events DB Tags: change from `select` → `multi_select` in Notion after launch (website already handles both; scraper needs updating too)
- [ ] Blog: `getPageBlocks` only fetches first 100 blocks — add pagination for very long posts
