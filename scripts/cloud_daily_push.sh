#!/usr/bin/env bash
# Football daily push — 调用 backend.app.core.daily_runner --mode push
# 该节点串联: 生成TOP3价值投注 + Agent自然语言早报 + 止损决策 + 写入push_history + 渠道推送
set -uo pipefail

ROOT="${FOOTBALL_TOOLS_ROOT:-/opt/football_tools}"
DB_PATH="${DB_PATH:-$ROOT/data/football_v2.db}"
LOG_DIR="${FOOTBALL_AUTOMATION_LOG_DIR:-$ROOT/logs/automation}"
LOCK_FILE="${FOOTBALL_PUSH_LOCK:-/tmp/football_daily_push.lock}"

mkdir -p "$LOG_DIR"

cd "$ROOT"

export DB_PATH
export PYTHONPATH="$ROOT/backend:$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

{
  echo "=== $(date '+%F %T') daily push start ==="

  # flock 防止并发, 5分钟超时
  flock -n -w 300 "$LOCK_FILE" \
    "$ROOT/venv/bin/python" -X utf8 -m backend.app.core.daily_runner --mode push --db "$DB_PATH"
  rc=$?

  if [[ $rc -ne 0 ]]; then
    echo "=== $(date '+%F %T') daily push FAILED (exit=$rc) ==="
    exit $rc
  fi

  echo "=== $(date '+%F %T') daily push done ==="
} >> "$LOG_DIR/cloud_daily_push.log" 2>&1
