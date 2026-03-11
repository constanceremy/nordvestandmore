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

**Stack:** Next.js 15, Tailwind CSS v4, deployed on Vercel

**Root directory on Vercel:** `nordvestandmore/website`

**Cache:** Pages revalidate every 60 minutes (ISR). To force an immediate refresh, trigger a redeploy on Vercel.

### Pages

| URL | What it does |
|-----|-------------|
| `/` | Home |
| `/events` | Community events feed — filterable by date/period and location |
| `/events/[slug]` | Detail page for NV & more's own events (scraped events link externally) |
| `/with-us` | NV & more's own bookable sessions list |
| `/with-us/[id]` | Session detail page with booking CTA |
| `/blog` | Blog post list |
| `/blog/[slug]` | Blog post detail |
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
| `src/components/Nav.tsx` | Navigation with NV & more logo |
| `src/components/BookButton.tsx` | Stripe checkout trigger button |
| `src/components/EventFilters.tsx` | Date/period pills + location combobox |
| `src/app/api/checkout/route.ts` | Creates Stripe checkout session |
| `src/app/api/webhook/route.ts` | Handles Stripe webhook after payment |

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
| Terms of Sale | `320375efa2cc805caf4edd4e2b0ddf36` | Terms page content (Notion page) |
| Privacy Policy | `320375efa2cc80beaa21d8119d085d55` | Privacy policy content (Notion page) |

### Key Notion fields

**Events DB**
- `Own Event` checkbox — if checked, links internally on the website; if unchecked, links externally
- `Approved` checkbox — must be checked for the event to appear on the website (own events bypass this)
- `Possible Duplicate` checkbox — if checked, event is hidden

**Sessions DB**
- `Booked spots` — incremented automatically by the webhook on every confirmed payment
- `Max spots` — controls availability display and sold-out state
- `Experience` — relation to Experiences DB

**Experiences DB**
- `Stripe Product ID` — the `prod_...` ID from Stripe, links the experience to a Stripe product

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

---

## Scraper

The scraper populates the Notion Events DB with community events. It runs via GitHub Actions.

### Sources

| Scraper | What it scrapes | Schedule |
|---------|----------------|---------|
| Instagram drip scraper | ~144 IG accounts | Every 30 min (5 accounts/run) on self-hosted Mac runner |
| Web scraper | Venue websites (Vierrummet, Lygten, etc.) | Daily at ~9:30 PM Copenhagen |
| Facebook scraper | Facebook events | Daily (same job) |

### GitHub Actions workflows

| Workflow | File | Schedule |
|----------|------|---------|
| Scrape Events | `scrape-events.yml` | Daily 19:30 UTC |
| Instagram Drip Scraper | `scrape-ig-drip.yml` | Every 30 minutes |
| Sync to Wix | `sync-to-wix.yml` | Daily 03:00 UTC (to be retired) |

### Scraper filter (what gets shown)

Events appear on the website only if:
- Not deleted
- Not marked as a possible duplicate
- Start date is today or in the future
- Either: `Approved = true` OR `Own Event = true`

### Key scraper files

| File | Purpose |
|------|---------|
| `scraper/run_scraper.py` | Main entry point |
| `scraper/scrape_posts.py` | Scrapes and writes events to Notion |
| `scraper/ig_scraper/drip_scrape.py` | Instagram drip scraper |
| `scraper/dedup.py` | Deduplication logic |
| `scraper/auto_tag.py` | Auto-tagging |
| `scraper/fix_locations.py` | Location normalisation |

---

## Email

Confirmation emails are sent via **Gmail SMTP** (nodemailer) from `nordvestandmore@gmail.com` using a Google App Password.

**Planned:** Reminder emails the day before an event — to be built as a GitHub Actions cron job querying Supabase for upcoming bookings.

---

## Environment Variables

Stored in `.env.local` locally and in Vercel project settings for production.

| Variable | What it's for |
|----------|--------------|
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

---

## What's still to do

- [ ] Switch Stripe to live mode before launch
- [ ] Build reminder email cron job (day before event, queries Supabase)
- [ ] Deploy to custom domain `nordvestandmore.com`
- [ ] Privacy policy — keep updated in Notion
- [ ] Blog: add pagination for very long posts (getPageBlocks only fetches first 100 blocks)
- [ ] Retire Wix sync once website is the primary platform
