#!/bin/bash
set -euo pipefail

# 1) Run from this script's folder
cd "$(dirname "$0")"

# 2) Load secrets from shared .env (gitignored)
set -a
source ../.env
set +a

# 3) Activate venv
source .venv/bin/activate

# 4) Site-specific settings
export SCRAPER_SLUG="LYGTEN_STATION"
export LIST_URL="https://kulturogfritidn.kk.dk/det-sker?place%5B0%5D=Lygten%20Station&title=Det%20sker%20p%C3%A5%20Lygten%20Station"
export LOCATION_NAME="Lygten Station"

# Map shared env vars to slug-specific ones (for backwards compat with scraper)
export NOTION_TOKEN_LYGTEN_STATION="$NOTION_TOKEN"
export NOTION_DATABASE_ID_LYGTEN_STATION="$NOTION_DATABASE_ID"

# 5) Print header
echo ">>> Runner: $(basename "$0") | Location: ${LOCATION_NAME}"

# 6) Run the scraper
python scrape_to_notion.py
