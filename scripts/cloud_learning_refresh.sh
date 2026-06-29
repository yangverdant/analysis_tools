#!/usr/bin/env bash
set -euo pipefail

ROOT="${FOOTBALL_TOOLS_ROOT:-/opt/football_tools}"
DB_PATH="${DB_PATH:-$ROOT/data/football_v2.db}"
ODDSFE_DB_PATH="${ODDSFE_DB_PATH:-$ROOT/fetchers/odds_feed_api/oddsfe_merged.db}"
LOG_DIR="${FOOTBALL_AUTOMATION_LOG_DIR:-$ROOT/logs/automation}"
LOCK_FILE="${FOOTBALL_AUTOMATION_LOCK:-/tmp/football_automation_center.lock}"
LEAGUE="${FOOTBALL_AUTOMATION_LEAGUE:-世界杯}"
BACKUP_ROOT="${FOOTBALL_BACKUP_DIR:-/opt/football_tools_backups/runtime}"
APPLY_ARGS=()

if [[ "${FOOTBALL_LEARNING_DRY_RUN:-0}" != "1" ]]; then
  APPLY_ARGS+=(--apply)
fi

mkdir -p "$LOG_DIR" "$BACKUP_ROOT"

cd "$ROOT"

export DB_PATH
export ODDSFE_DB_PATH
export FOOTBALL_BACKUP_DIR="$BACKUP_ROOT"
export PYTHONPATH="$ROOT/backend:$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

{
  echo "=== $(date '+%F %T') cloud learning refresh start ==="
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_PATH" "PRAGMA busy_timeout=30000; PRAGMA journal_mode=WAL;" || true
    sqlite3 "$ODDSFE_DB_PATH" "PRAGMA busy_timeout=30000; PRAGMA journal_mode=WAL;" || true
  fi

  timeout "${FOOTBALL_LEARNING_TIMEOUT:-45m}" \
    flock -n "$LOCK_FILE" \
    nice -n "${FOOTBALL_LEARNING_NICE:-10}" \
    ionice -c2 -n "${FOOTBALL_LEARNING_IONICE:-7}" \
    "$ROOT/venv/bin/python" "$ROOT/scripts/run_automation_center.py" \
      --db "$DB_PATH" \
      --oddsfe-db "$ODDSFE_DB_PATH" \
      --mode mixed \
      --league "$LEAGUE" \
      --historical-dates "${FOOTBALL_LEARNING_HISTORICAL_DATES:-2}" \
      --historical-lookback-days "${FOOTBALL_LEARNING_LOOKBACK_DAYS:-120}" \
      --workers "${FOOTBALL_LEARNING_WORKERS:-1}" \
      --task-timeout "${FOOTBALL_LEARNING_TASK_TIMEOUT:-480}" \
      --max-events "${FOOTBALL_LEARNING_MAX_EVENTS:-3}" \
      --max-analysis "${FOOTBALL_LEARNING_MAX_ANALYSIS:-12}" \
      --max-intelligence "${FOOTBALL_LEARNING_MAX_INTELLIGENCE:-4}" \
      --max-validation-dates "${FOOTBALL_LEARNING_MAX_VALIDATION_DATES:-2}" \
      --force-learning \
      "${APPLY_ARGS[@]}"

  if [[ -d "$BACKUP_ROOT/model_reanalysis" ]]; then
    find "$BACKUP_ROOT/model_reanalysis" -type f -name '*.json' -mtime +"${FOOTBALL_LEARNING_BACKUP_RETENTION_DAYS:-3}" -delete || true
  fi

  echo "=== $(date '+%F %T') cloud learning refresh done ==="
} >> "$LOG_DIR/cloud_learning_refresh.log" 2>&1
