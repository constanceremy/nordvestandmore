#!/bin/bash
set -euo pipefail

# ---- log header ----
echo "=== daily_scrape.sh start: $(date) ==="
echo "whoami: $(whoami)"
echo "pwd before: $(pwd)"

# ---- project dir ----
cd "/Users/constanceremy/Documents/nordvestandmore/nv_scraper"
echo "pwd now: $(pwd)"

# ---- load env for ALL scrapers (tokens, DB ids, LIST_URLs, etc.) ----
# If you keep a .env file, source it like this:
if [[ -f ".env" ]]; then
  set -a
  source ./.env
  set +a
fi

# ---- activate venv ----
source .venv/bin/activate

# ---- run the multi-runner ----
./run_all.sh

echo "=== daily_scrape.sh end: $(date) ==="

