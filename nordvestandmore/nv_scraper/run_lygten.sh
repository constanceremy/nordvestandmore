#!/bin/bash
set -euo pipefail

# 1) Run from this script's folder
cd "$(dirname "$0")"

# 2) Activate your venv (adjust path if yours differs)
source .venv/bin/activate

# 3) Export environment for THIS site
# ---- site-specific settings ----
export SCRAPER_SLUG="LYGTEN_STATION"
export LIST_URL="https://kulturogfritidn.kk.dk/det-sker?place%5B0%5D=Lygten%20Station&title=Det%20sker%20p%C3%A5%20Lygten%20Station"
export LOCATION_NAME="Lygten Station"

# ---- Notion credentials for this slug ----
export NOTION_TOKEN_LYGTEN_STATION="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"
export NOTION_DATABASE_ID_LYGTEN_STATION="283375efa2cc80678d42f5b20163c523"

# 4) Print a clear header (this is what run_all.sh parses for nice logs)
echo ">>> Runner: $(basename "$0") | Location: ${LOCATION_NAME}"

# 5) Run the scraper
python scrape_to_notion.py
