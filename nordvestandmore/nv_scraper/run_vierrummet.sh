#!/usr/bin/env bash
set -euo pipefail

# 1) Run from this script's folder
cd "$(dirname "$0")"

# 2) Load secrets from shared .env (gitignored)
set -a
source ../.env
set +a

# 3) Activate venv
if [[ -f ".venv/bin/activate" ]]; then source .venv/bin/activate; fi

# 4) Site-specific settings
export SCRAPER_SLUG="VIERRUMMET"
export LIST_URL="https://www.vierrummet.dk/"
export LOCATION_NAME="Vier Rummet"

# Map shared env vars to slug-specific ones
export NOTION_TOKEN_VIERRUMMET="$NOTION_TOKEN"
export NOTION_DATABASE_ID_VIERRUMMET="$NOTION_DATABASE_ID"

# Optional debug
# export DEBUG=1

# 5) Run the scraper
python3 scrape_vierrummet.py
