#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/football_tools}"
DB_PATH="${DB_PATH:-$PROJECT_DIR/data/football_v2.db}"
FOOTBALL_BACKUP_DIR="${FOOTBALL_BACKUP_DIR:-/opt/football_tools_backups/runtime}"
FOOTBALL_DATA_OWNER="${FOOTBALL_DATA_OWNER:-ubuntu:ubuntu}"
PYTHONPATH="$PROJECT_DIR:$PROJECT_DIR/backend:${PYTHONPATH:-}"
export DB_PATH FOOTBALL_BACKUP_DIR FOOTBALL_DATA_OWNER PYTHONPATH
mkdir -p "$FOOTBALL_BACKUP_DIR"

APPLY_SNAPSHOT_CLEANUP=0
RESTART_SERVICE=1
SERVICE_STOPPED=0

for arg in "$@"; do
  case "$arg" in
    --apply-snapshot-cleanup)
      APPLY_SNAPSHOT_CLEANUP=1
      ;;
    --no-restart)
      RESTART_SERVICE=0
      ;;
  esac
done

cd "$PROJECT_DIR"

ensure_data_permissions() {
  local data_dir
  data_dir="$(dirname "$DB_PATH")"
  mkdir -p "$data_dir"
  chmod 775 "$data_dir" || true
  if [ "$(id -u)" = "0" ]; then
    chown "$FOOTBALL_DATA_OWNER" "$data_dir" || true
    find "$data_dir" -maxdepth 1 -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.db-*' -o -name '*.sqlite-*' \) \
      -exec chown "$FOOTBALL_DATA_OWNER" {} + \
      -exec chmod 664 {} + || true
  else
    find "$data_dir" -maxdepth 1 -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.db-*' -o -name '*.sqlite-*' \) \
      -exec chmod 664 {} + || true
  fi
  if [ -f "$PROJECT_DIR/fetchers/odds_feed_api/oddsfe_merged.db" ]; then
    if [ "$(id -u)" = "0" ]; then
      chown "$FOOTBALL_DATA_OWNER" "$PROJECT_DIR/fetchers/odds_feed_api" || true
      chown "$FOOTBALL_DATA_OWNER" "$PROJECT_DIR/fetchers/odds_feed_api/oddsfe_merged.db" || true
    fi
    chmod 775 "$PROJECT_DIR/fetchers/odds_feed_api" || true
    chmod 664 "$PROJECT_DIR/fetchers/odds_feed_api/oddsfe_merged.db" || true
  fi
}

ensure_runtime_automation() {
  if [ "$(id -u)" != "0" ]; then
    return
  fi

  mkdir -p /opt/football_tools_backups/runtime "$PROJECT_DIR/logs/automation"
  chown -R "$FOOTBALL_DATA_OWNER" /opt/football_tools_backups/runtime "$PROJECT_DIR/logs/automation" || true
  chmod 775 "$PROJECT_DIR/logs" "$PROJECT_DIR/logs/automation" || true

  chmod 755 "$PROJECT_DIR/scripts/cloud_automation_tick.sh" 2>/dev/null || true
  chmod 755 "$PROJECT_DIR/scripts/cloud_learning_refresh.sh" 2>/dev/null || true
  chmod 755 "$PROJECT_DIR/scripts/health_monitor.sh" 2>/dev/null || true

  mkdir -p /etc/systemd/system/football-analyst.service.d
  cat >/etc/systemd/system/football-analyst.service.d/10-runtime-env.conf <<EOF
[Service]
Environment=ODDSFE_DB_PATH=$PROJECT_DIR/fetchers/odds_feed_api/oddsfe_merged.db
Environment=DISABLE_DAILY_SCHEDULER=1
Environment=PYTHONUNBUFFERED=1
EOF

  cat >/etc/systemd/system/football-automation-tick.service <<EOF
[Unit]
Description=Football segmented automation tick
Wants=network-online.target
After=network-online.target football-analyst.service

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment=FOOTBALL_TOOLS_ROOT=$PROJECT_DIR
Environment=DB_PATH=$DB_PATH
Environment=ODDSFE_DB_PATH=$PROJECT_DIR/fetchers/odds_feed_api/oddsfe_merged.db
Environment=PYTHONUNBUFFERED=1
ExecStart=$PROJECT_DIR/scripts/cloud_automation_tick.sh
EOF

  cat >/etc/systemd/system/football-automation-tick.timer <<EOF
[Unit]
Description=Run football segmented automation tick

[Timer]
OnBootSec=3min
OnUnitActiveSec=15min
Unit=football-automation-tick.service

[Install]
WantedBy=timers.target
EOF

  cat >/etc/systemd/system/football-learning-refresh.service <<EOF
[Unit]
Description=Football nightly learning refresh
Wants=network-online.target
After=network-online.target football-analyst.service

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment=FOOTBALL_TOOLS_ROOT=$PROJECT_DIR
Environment=DB_PATH=$DB_PATH
Environment=ODDSFE_DB_PATH=$PROJECT_DIR/fetchers/odds_feed_api/oddsfe_merged.db
Environment=FOOTBALL_BACKUP_DIR=/opt/football_tools_backups/runtime
Environment=PYTHONUNBUFFERED=1
ExecStart=$PROJECT_DIR/scripts/cloud_learning_refresh.sh
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

  cat >/etc/systemd/system/football-learning-refresh.timer <<EOF
[Unit]
Description=Run football nightly learning refresh

[Timer]
OnCalendar=*-*-* 02:45:00
RandomizedDelaySec=20min
Persistent=true
Unit=football-learning-refresh.service

[Install]
WantedBy=timers.target
EOF

  if crontab -l >/tmp/football_root_crontab 2>/dev/null; then
    grep -v 'backend.app.core.daily_runner' /tmp/football_root_crontab >/tmp/football_root_crontab.filtered || true
    crontab /tmp/football_root_crontab.filtered
  fi

  systemctl daemon-reload
  systemctl enable --now football-automation-tick.timer football-learning-refresh.timer >/dev/null
}

ensure_data_permissions
ensure_runtime_automation

if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/venv/bin/activate"
fi

cleanup() {
  if [ "$SERVICE_STOPPED" = "1" ]; then
    systemctl start football-analyst || true
  fi
}
trap cleanup EXIT

if [ "$RESTART_SERVICE" = "1" ]; then
  systemctl stop football-analyst || true
  SERVICE_STOPPED=1
fi

python -m py_compile \
  backend/app/core/analyze.py \
  backend/app/main.py \
  backend/app/core/validate.py \
  backend/app/data_access/foundation_dao.py \
  backend/app/lottery/routers/lottery.py \
  backend/app/lottery/services/auto_gap_runner.py \
  backend/app/lottery/services/automation_center.py \
  backend/app/lottery/services/oddsfe_event_sync.py \
  scripts/audit_auto_loop_health.py \
  scripts/audit_ou_goal_axis.py \
  scripts/audit_prediction_consistency.py \
  scripts/backfill_data_foundation.py \
  scripts/build_ou_line_calibration.py \
  scripts/build_similar_match_cases.py \
  scripts/cleanup_bqc_axis_adjustments.py \
  scripts/cleanup_foundation_snapshots.py \
  scripts/cleanup_stale_analysis_reports.py \
  scripts/import_data_delta_safe.py \
  scripts/mark_duplicate_reports_stale.py \
  scripts/mark_stale_collection_runs.py \
  scripts/model_change_gate.py \
  scripts/reanalyze_unstarted_after_learning.py \
  scripts/rebuild_lottery_validation.py \
  scripts/repair_lottery_team_mappings.py \
  scripts/run_model_reanalysis_stage.py \
  scripts/run_automation_center.py \
  scripts/run_automation_task.py \
  scripts/settle_reanalysis_changes.py

python scripts/migrate_data_foundation.py --db "$DB_PATH" --apply

python scripts/cleanup_foundation_snapshots.py --db "$DB_PATH"
python scripts/cleanup_bqc_axis_adjustments.py --db "$DB_PATH" --apply
python scripts/cleanup_stale_analysis_reports.py --db "$DB_PATH" --keep-stale-per-match 3 || true
python scripts/mark_duplicate_reports_stale.py --db "$DB_PATH" --apply
python scripts/backfill_data_foundation.py --db "$DB_PATH" --refresh-reviews
python scripts/build_ou_line_calibration.py --db "$DB_PATH" --min-samples-to-print 5

if [ "$APPLY_SNAPSHOT_CLEANUP" = "1" ]; then
  python scripts/cleanup_foundation_snapshots.py --db "$DB_PATH" --apply --backup
fi

python scripts/build_similar_match_cases.py --db "$DB_PATH" --play-type spf --top-k 5 --min-score 0.68
python scripts/build_similar_match_cases.py --db "$DB_PATH" --play-type rqspf --top-k 5 --min-score 0.66
python scripts/build_similar_match_cases.py --db "$DB_PATH" --play-type bqc --top-k 5 --min-score 0.64
python scripts/build_similar_match_cases.py --db "$DB_PATH" --play-type ou --top-k 5 --min-score 0.66
python scripts/build_similar_match_cases.py --db "$DB_PATH" --play-type bf --top-k 5 --min-score 0.62
python scripts/audit_prediction_consistency.py --db "$DB_PATH" || true
python scripts/audit_ou_goal_axis.py --db "$DB_PATH" || true
ensure_data_permissions

if [ "$RESTART_SERVICE" = "1" ]; then
  systemctl start football-analyst
  SERVICE_STOPPED=0
  systemctl reload nginx || true
  sleep 3
  systemctl --no-pager --full status football-analyst | head -n 40
fi

curl -fsS http://127.0.0.1:8000/api/scheduler/status >/tmp/football_scheduler_status.json || true
echo "post-sync maintenance complete"
