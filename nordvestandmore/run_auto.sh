#!/bin/bash
# Automated scraper run — designed for cron / launchd
# Logs output to logs/ directory with timestamped filenames
#
# Usage:
#   ./run_auto.sh              # full run
#   ./run_auto.sh --from 50    # resume from entity #50

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Create logs directory
mkdir -p "$DIR/logs"

# Timestamp for log file
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M")
LOG_FILE="$DIR/logs/scraper_${TIMESTAMP}.log"

echo "🕐 Starting scraper at $(date)" | tee "$LOG_FILE"

# Load environment
set -a
source "$DIR/.env"
set +a

# Check Facebook cookies — notify if missing/expired
FB_COOKIES="$DIR/fb_scraper/fb_cookies.json"
if [ ! -f "$FB_COOKIES" ]; then
    osascript -e 'display notification "Facebook cookies not found — FB scraping will fail. Run fb_login.py to fix." with title "NV&More Scraper ⚠️"'
    echo "⚠️ Facebook cookies missing!" | tee -a "$LOG_FILE"
fi

# Activate venv
source "$DIR/nv_scraper/.venv/bin/activate"

# Run scraper in auto mode (non-interactive), pass through any extra args
python3 "$DIR/run_scraper.py" all --auto "$@" 2>&1 | tee -a "$LOG_FILE"

echo ""
echo "✅ Finished at $(date)" | tee -a "$LOG_FILE"
echo "📄 Log saved to: $LOG_FILE"

# Clean up old logs (keep last 30 days)
find "$DIR/logs" -name "scraper_*.log" -mtime +30 -delete 2>/dev/null || true
