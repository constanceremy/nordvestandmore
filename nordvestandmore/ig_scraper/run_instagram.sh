#!/bin/bash
set -euo pipefail

# 1) Run from this script's folder
cd "$(dirname "$0")"

# 2) Load secrets from shared .env (gitignored, never committed)
set -a
source ../.env
set +a

# 3) Activate venv (shared with nv_scraper)
source ../nv_scraper/.venv/bin/activate

# ---- Scraper settings ----
export DAYS_BACK="7"
export ACCOUNTS_FILE="accounts.txt"

# Optional: uncomment for verbose logging
# export DEBUG=1

# 4) Print header
echo ">>> Runner: $(basename "$0") | Instagram Event Scraper"

# 5) Run the scraper
python scrape_instagram_events.py
