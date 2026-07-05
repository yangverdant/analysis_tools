#!/usr/bin/env bash
set -euo pipefail

ROOT="${FOOTBALL_TOOLS_ROOT:-/opt/football_tools}"
DB_PATH="${DB_PATH:-$ROOT/data/football_v2.db}"
ODDSFE_DB_PATH="${ODDSFE_DB_PATH:-$ROOT/fetchers/odds_feed_api/oddsfe_merged.db}"
LOG_DIR="${FOOTBALL_AUTOMATION_LOG_DIR:-$ROOT/logs/automation}"
LOCK_FILE="${FOOTBALL_AUTOMATION_LOCK:-/tmp/football_automation_center.lock}"
LEAGUE="${FOOTBALL_AUTOMATION_LEAGUE:-}"
BACKUP_ROOT="${FOOTBALL_BACKUP_DIR:-/opt/football_tools_backups/runtime}"
LEARNING_ARGS=()

if [[ "${FOOTBALL_AUTOMATION_INCLUDE_LEARNING:-0}" != "1" ]]; then
  LEARNING_ARGS+=(--no-learning)
fi

mkdir -p "$LOG_DIR" "$BACKUP_ROOT"

cd "$ROOT"

export DB_PATH
export ODDSFE_DB_PATH
export FOOTBALL_BACKUP_DIR="$BACKUP_ROOT"
export PYTHONPATH="$ROOT/backend:$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

{
  echo "=== $(date '+%F %T') cloud automation tick start ==="
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_PATH" "PRAGMA busy_timeout=30000; PRAGMA journal_mode=WAL;" || true
    sqlite3 "$ODDSFE_DB_PATH" "PRAGMA busy_timeout=30000; PRAGMA journal_mode=WAL;" || true
  fi
  # oddsfe schedule sync — primary source since sporttery WAF ban (2026-07-04)
  # Fetches future 3 days of mainstream-league matches with whitelist filter
  "$ROOT/venv/bin/python" "$ROOT/scripts/oddsfe_schedule_to_lottery.py" 2>&1 | grep -E 'oddsfe_schedule_sync|total_inserted' | tail -5 || true
  # Backfill oddsfe_event_id for existing rows without one (so results supplement can run)
  "$ROOT/venv/bin/python" "$ROOT/scripts/oddsfe_eid_backfill.py" 2>&1 | grep -E 'backfill|updated|done' | tail -5 || true
  # oddsfe results supplement — backfill FT/HT/BQC for matches finished in last 4 days
  "$ROOT/venv/bin/python" "$ROOT/scripts/oddsfe_results_supplement.py" 2>&1 | grep -E 'supplement|done' | tail -5 || true
  # Sporttery sync — best-effort fallback (will likely 403/captcha, silently skip)
  "$ROOT/venv/bin/python" "$ROOT/scripts/cloud_tick_sporttery_sync.py" 2>&1 | grep -E 'sync|saved|skip' | tail -5 || true
  timeout "${FOOTBALL_AUTOMATION_TIMEOUT:-12m}" \
    flock -n "$LOCK_FILE" \
    "$ROOT/venv/bin/python" "$ROOT/scripts/run_automation_center.py" \
      --db "$DB_PATH" \
      --oddsfe-db "$ODDSFE_DB_PATH" \
      --mode mixed \
      --league "$LEAGUE" \
      --historical-dates "${FOOTBALL_AUTOMATION_HISTORICAL_DATES:-1}" \
      --historical-lookback-days "${FOOTBALL_AUTOMATION_LOOKBACK_DAYS:-90}" \
      --workers "${FOOTBALL_AUTOMATION_WORKERS:-2}" \
      --task-timeout "${FOOTBALL_AUTOMATION_TASK_TIMEOUT:-180}" \
      --max-events "${FOOTBALL_AUTOMATION_MAX_EVENTS:-4}" \
      --max-analysis "${FOOTBALL_AUTOMATION_MAX_ANALYSIS:-8}" \
      --max-intelligence "${FOOTBALL_AUTOMATION_MAX_INTELLIGENCE:-4}" \
      --max-validation-dates "${FOOTBALL_AUTOMATION_MAX_VALIDATION_DATES:-1}" \
      "${LEARNING_ARGS[@]}" \
      --apply
  if [[ -d "$BACKUP_ROOT/model_reanalysis" ]]; then
    find "$BACKUP_ROOT/model_reanalysis" -type f -name '*.json' -mtime +"${FOOTBALL_AUTOMATION_BACKUP_RETENTION_DAYS:-3}" -delete || true
  fi
  echo "=== $(date '+%F %T') cloud automation tick done ==="
} >> "$LOG_DIR/cloud_automation_tick.log" 2>&1
