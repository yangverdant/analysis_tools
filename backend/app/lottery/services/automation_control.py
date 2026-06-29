"""Persistent controls for the lottery automation center."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional


CONTROL_KEY = "automation_center"
DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "mixed",
    "league": "\u4e16\u754c\u676f",
    "historical_dates": 1,
    "historical_lookback_days": 180,
    "include_learning": True,
    "national_ou_gate": True,
    "workers": 3,
    "task_timeout_seconds": 300,
    "max_events": 6,
    "max_analysis": 10,
    "max_intelligence": 6,
    "max_validation_dates": 1,
    "fetch_live_ou": True,
    "network_intelligence": True,
}


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def _loads(value: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = default
    return max(minimum, min(maximum, numeric))


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_control (
            control_key TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            state TEXT NOT NULL DEFAULT 'active',
            config_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            reason TEXT
        )
        """
    )


def _normalize_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raw = {**DEFAULT_CONFIG, **(config or {})}
    return {
        "mode": str(raw.get("mode") or DEFAULT_CONFIG["mode"]).strip().lower(),
        "league": str(raw.get("league") or DEFAULT_CONFIG["league"]).strip(),
        "historical_dates": _int(raw.get("historical_dates"), DEFAULT_CONFIG["historical_dates"], 0, 14),
        "historical_lookback_days": _int(
            raw.get("historical_lookback_days"),
            DEFAULT_CONFIG["historical_lookback_days"],
            1,
            3650,
        ),
        "include_learning": _bool(raw.get("include_learning"), DEFAULT_CONFIG["include_learning"]),
        "national_ou_gate": _bool(raw.get("national_ou_gate"), DEFAULT_CONFIG["national_ou_gate"]),
        "workers": _int(raw.get("workers"), DEFAULT_CONFIG["workers"], 1, 8),
        "task_timeout_seconds": _int(raw.get("task_timeout_seconds"), DEFAULT_CONFIG["task_timeout_seconds"], 60, 1800),
        "max_events": _int(raw.get("max_events"), DEFAULT_CONFIG["max_events"], 1, 50),
        "max_analysis": _int(raw.get("max_analysis"), DEFAULT_CONFIG["max_analysis"], 1, 100),
        "max_intelligence": _int(raw.get("max_intelligence"), DEFAULT_CONFIG["max_intelligence"], 1, 50),
        "max_validation_dates": _int(raw.get("max_validation_dates"), DEFAULT_CONFIG["max_validation_dates"], 1, 14),
        "fetch_live_ou": _bool(raw.get("fetch_live_ou"), DEFAULT_CONFIG["fetch_live_ou"]),
        "network_intelligence": _bool(raw.get("network_intelligence"), DEFAULT_CONFIG["network_intelligence"]),
    }


def get_automation_control_state(db_path: str) -> Dict[str, Any]:
    with _connect(db_path) as conn:
        _ensure_table(conn)
        row = conn.execute(
            """
            SELECT control_key, enabled, state, config_json, updated_at, updated_by, reason
            FROM automation_control
            WHERE control_key = ?
            """,
            (CONTROL_KEY,),
        ).fetchone()
        if not row:
            config = _normalize_config()
            conn.execute(
                """
                INSERT INTO automation_control
                (control_key, enabled, state, config_json, updated_by, reason)
                VALUES (?, 1, 'active', ?, 'system', 'default enabled')
                """,
                (CONTROL_KEY, _json(config)),
            )
            return {
                "control_key": CONTROL_KEY,
                "enabled": True,
                "state": "active",
                "state_label": "自动中",
                "config": config,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "updated_by": "system",
                "reason": "default enabled",
            }
        enabled = bool(row["enabled"])
        state = str(row["state"] or ("active" if enabled else "paused"))
        config = _normalize_config(_loads(row["config_json"], {}))
        return {
            "control_key": row["control_key"],
            "enabled": enabled,
            "state": state,
            "state_label": _state_label(enabled, state),
            "config": config,
            "updated_at": row["updated_at"],
            "updated_by": row["updated_by"],
            "reason": row["reason"],
        }


def set_automation_control_state(
    db_path: str,
    *,
    enabled: Optional[bool] = None,
    state: Optional[str] = None,
    config_patch: Optional[Dict[str, Any]] = None,
    updated_by: str = "api",
    reason: str = "",
) -> Dict[str, Any]:
    current = get_automation_control_state(db_path)
    next_enabled = current["enabled"] if enabled is None else bool(enabled)
    next_state = (state or ("active" if next_enabled else "paused")).strip().lower()
    if next_state not in {"active", "paused", "stopped"}:
        next_state = "active" if next_enabled else "paused"
    next_config = _normalize_config({**(current.get("config") or {}), **(config_patch or {})})
    with _connect(db_path) as conn:
        _ensure_table(conn)
        conn.execute(
            """
            INSERT INTO automation_control
            (control_key, enabled, state, config_json, updated_at, updated_by, reason)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            ON CONFLICT(control_key) DO UPDATE SET
                enabled = excluded.enabled,
                state = excluded.state,
                config_json = excluded.config_json,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = excluded.updated_by,
                reason = excluded.reason
            """,
            (CONTROL_KEY, 1 if next_enabled else 0, next_state, _json(next_config), updated_by, reason),
        )
    return get_automation_control_state(db_path)


def automation_center_kwargs_from_state(state: Dict[str, Any], *, trigger_source: str) -> Dict[str, Any]:
    config = _normalize_config(state.get("config") or {})
    return {
        "mode": config["mode"],
        "date_from": None,
        "date_to": None,
        "league": config["league"],
        "historical_dates": config["historical_dates"],
        "historical_lookback_days": config["historical_lookback_days"],
        "include_learning": config["include_learning"],
        "national_ou_gate": config["national_ou_gate"],
        "workers": config["workers"],
        "task_timeout_seconds": config["task_timeout_seconds"],
        "max_events": config["max_events"],
        "max_analysis": config["max_analysis"],
        "max_intelligence": config["max_intelligence"],
        "max_validation_dates": config["max_validation_dates"],
        "fetch_live_ou": config["fetch_live_ou"],
        "network_intelligence": config["network_intelligence"],
        "trigger_source": trigger_source,
    }


def _state_label(enabled: bool, state: str) -> str:
    if enabled and state == "active":
        return "自动中"
    if state == "stopped":
        return "已停止"
    return "已暂停"
