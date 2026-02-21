#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

LOGDIR="$DIR/logs"
mkdir -p "$LOGDIR"
STAMP="$(date +%F_%H-%M)"
LOGFILE="$LOGDIR/run_all_${STAMP}.log"

echo "===== NV SCRAPERS: $(date) =====" | tee -a "$LOGFILE"

shopt -s nullglob
for f in "$DIR"/run_*.sh; do
  # Skip this file itself if it matches the pattern
  if [[ "$(basename "$f")" == "run_all.sh" ]]; then
    continue
  fi

  echo -e "\n--- START $(basename "$f") ---" | tee -a "$LOGFILE"
  # Each site runner prints:
  #   >>> Runner: run_X.sh | Location: ...
  # and then your Python script prints:
  #   [SLUG] ✅ Created X, Updated Y, Skipped Z
  bash "$f" 2>&1 | tee -a "$LOGFILE"
  echo "--- END $(basename "$f") ---" | tee -a "$LOGFILE"
done

echo -e "\n===== DONE: $(date) =====" | tee -a "$LOGFILE"

