#!/usr/bin/env bash
set -euo pipefail

export SCRAPER_SLUG="VIERRUMMET"
export LIST_URL="https://www.vierrummet.dk/"
export LOCATION_NAME="Vier Rummet"

# Your per-site Notion secrets (already created for other scrapers)
export NOTION_TOKEN_VIERRUMMET="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"
export NOTION_DATABASE_ID_VIERRUMMET="283375efa2cc80678d42f5b20163c523"

# Optional debug
# export DEBUG=1

# Activate venv if you use one
if [[ -f ".venv/bin/activate" ]]; then source .venv/bin/activate; fi

python3 scrape_vierrummet.py
