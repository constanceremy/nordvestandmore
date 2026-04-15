# NV & more — Branding Guidelines

Derived from `website/src/app/globals.css`, `Nav.tsx`, `Footer.tsx`, and page components.

---

## Colours

| Token | Hex | Use |
|---|---|---|
| Background | `#ffffff` | All backgrounds — no dark sections |
| Foreground | `#0a0a0a` | All primary text |
| Border | `#000000` | 1px structural lines (`border-black`) |
| Meta / labels | `#9ca3af` (gray-400) | Tags, dates, secondary info |
| Muted bg | `#f5f5f5` | Subtle fills (rarely used) |
| Border light | `#e0e0e0` | Light dividers |

**Rule:** The palette is strictly monochrome. Never use colour for backgrounds, highlights, or accents.

---

## Typography

**Font:** Neue Haas Grotesk Display Pro → fallback: Helvetica Neue → Arial
**Weight:** 300 (light) for everything — body, headings, labels
**Rendering:** `-webkit-font-smoothing: antialiased`

| Role | Size | Weight | Case | Letter-spacing |
|---|---|---|---|---|
| Hero heading | clamp(4rem–12rem) | 300 | Mixed | `tracking-tight` (−0.02em) |
| Page heading (h1) | 5xl–7xl | 300 | Mixed | `tracking-tight` |
| Section label | xs (12px) | 300 | UPPERCASE | `tracking-[0.3em]` |
| Nav links | sm (14px) | medium | UPPERCASE | `tracking-widest` |
| Event title | xl–2xl | 300 | Mixed | `tracking-tight` |
| Meta (tag / date / location) | xs (12px) | 300 | UPPERCASE | `tracking-[0.15–0.2em]` |
| Body / excerpt | xs (12px) | 300 | UPPERCASE | `tracking-[0.1em]` |

---

## Layout

- **Container:** `max-w-6xl mx-auto px-6` (max 1152px, 24px side padding)
- **Sections** separated by `border-b border-black` (1px black bottom border)
- **Event rows:** `divide-y divide-black` — 1px black line between each row
- **Section header pattern:**
  ```
  SMALL UPPERCASE LABEL   ← text-xs tracking-[0.3em] gray-400
  ─────────────────────── ← border-b border-black
  Large heading
  ```
- **No coloured backgrounds** — hover states invert to black background / white text

---

## Interactive states

- **Hover:** `bg-black text-white transition-colors` — full invert on hover
- **Active nav link:** `border-b border-black` underline
- **Buttons:** `border border-black px-8 py-4`, uppercase tracked text, hover inverts

---

## Components

### Navigation
- Sticky, white background, `border-b border-black`
- Logo: round image, 44×44px, left-aligned
- Links: right-aligned, uppercase, `tracking-widest`

### Footer
- White background, `border-t border-black`
- Small uppercase tracked text, gray-400

### Event row (grid columns)
```
DATE/TIME  |  TAG  |  TITLE (large)  |  LOCATION  |  actions
```
- Date/tag: `text-xs tracking-[0.2em] uppercase text-gray-400`
- Title: `text-xl–2xl tracking-tight`

---

## Graphic / Instagram story rules

Derived from the above for the daily "Today in Nordvest" image:

- **Background:** white (`#ffffff`) throughout — no dark bands
- **Header:** `NV & MORE` label (tiny, uppercase, wide tracking, gray) + `TODAY IN NORDVEST` (large, weight 300) + date (small, uppercase, gray) + 1px black border-b
- **Event rows:** meta line (TAG · TIME, small uppercase gray) + name line (mixed case, weight 300) + soft gray divider between events
- **Footer:** 1px black border-t + `NV & MORE` (black, tracked) left + `NORDVEST · COPENHAGEN` (gray, tracked) right
- **Grid texture:** very subtle graph-paper lines (120px spacing, `#ebebeb`) — decorative only
- **Font on runner:** Helvetica Neue (macOS) / Liberation Sans (Ubuntu) — closest available to Neue Haas Grotesk
