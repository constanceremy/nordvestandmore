#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export SCRAPER_SLUG="THORAVEJ29"
export LIST_URL="https://www.thoravej29.dk/en/events"
export LOCATION_NAME="Thoravej 29"

# Notion creds for this slug:
export NOTION_TOKEN_THORAVEJ29="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"
export NOTION_DATABASE_ID_THORAVEJ29="283375efa2cc80678d42f5b20163c523"

export DEBUG=1   # turn off when happy

. .venv/bin/activate
python3 scrape_thoravej29.py
