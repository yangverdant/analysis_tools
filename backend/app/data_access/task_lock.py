"""Small cross-process task lock for long SQLite write phases."""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterator, Optional


def clean_path_arg(value: Any) -> str:
    return str(value or "").strip(" \t\r\n")


def _pid_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _lock_path(task_name: str, db_path: Any) -> Path:
    raw_db = clean_path_arg(db_path)
    try:
        db_key = str(Path(raw_db).resolve())
    except Exception:
        db_key = raw_db
    digest = sha256(f"{task_name}|{db_key}".encode("utf-8")).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / f"football_tools_{task_name}_{digest}.lock"


def inspect_task_lock(task_name: str, db_path: Any) -> Dict[str, Any]:
    path = _lock_path(task_name, db_path)
    holder: Dict[str, Any] = {}
    if not path.exists():
        return {
            "task": task_name,
            "locked": False,
            "path": str(path),
            "holder": None,
            "stale": False,
        }
    try:
        holder = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        holder = {}
    pid = holder.get("pid")
    pid_dead = not _pid_alive(pid)
    return {
        "task": task_name,
        "locked": True,
        "path": str(path),
        "holder": holder or None,
        "stale": bool(pid_dead),
    }


@dataclass
class TaskLockResult:
    acquired: bool
    path: str
    reason: str = ""
    holder: Optional[Dict[str, Any]] = None


@contextmanager
def exclusive_task_lock(
    task_name: str,
    db_path: Any,
    *,
    stale_seconds: int = 7200,
) -> Iterator[TaskLockResult]:
    path = _lock_path(task_name, db_path)
    now = time.time()
    payload = {
        "task": task_name,
        "db_path": clean_path_arg(db_path),
        "pid": os.getpid(),
        "created_at": now,
        "created_at_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
    }

    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            break
        except FileExistsError:
            holder: Dict[str, Any] = {}
            try:
                holder = json.loads(path.read_text(encoding="utf-8") or "{}")
            except Exception:
                holder = {}
            holder_pid = holder.get("pid")
            created_at = float(holder.get("created_at") or 0)
            is_stale = (not _pid_alive(holder_pid)) or (created_at and (now - created_at > stale_seconds))
            if is_stale:
                try:
                    path.unlink()
                    continue
                except FileNotFoundError:
                    continue
            yield TaskLockResult(False, str(path), "task_already_running", holder or None)
            return

    try:
        yield TaskLockResult(True, str(path), "", payload)
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
