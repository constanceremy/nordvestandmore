#!/usr/bin/env bash
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
export SCRAPER_SLUG="THORAVEJ29"
export LIST_URL="https://www.thoravej29.dk/en/events"
export LOCATION_NAME="Thoravej 29"

# Map shared env vars to slug-specific ones
export NOTION_TOKEN_THORAVEJ29="$NOTION_TOKEN"
export NOTION_DATABASE_ID_THORAVEJ29="$NOTION_DATABASE_ID"

# Optional debug
# export DEBUG=1

# 5) Run the scraper
python3 scrape_thoravej29.py
