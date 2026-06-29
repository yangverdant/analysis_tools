"""Audit registered collection channels and their local entry points."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.intelligence.source_channels import SOURCE_CHANNELS  # noqa: E402


def _entry_path(command: str) -> Optional[Path]:
    if not command:
        return None
    token = command.split()[0]
    if token.endswith(".py"):
        return ROOT / token
    return None


def audit(requirement: str = "") -> dict:
    rows = []
    by_requirement = {}
    for channel in SOURCE_CHANNELS:
        if requirement and requirement not in channel.requirement_keys:
            continue
        path = _entry_path(channel.command)
        exists = path.exists() if path else True
        item = {
            "name": channel.name,
            "kind": channel.kind,
            "priority": channel.priority,
            "enabled": channel.enabled,
            "network": channel.network,
            "requirements": list(channel.requirement_keys),
            "command": channel.command,
            "entry_path": str(path.relative_to(ROOT)) if path else "",
            "entry_exists": bool(exists),
            "evidence_tables": list(channel.evidence_tables),
            "notes": channel.notes,
        }
        rows.append(item)
        for key in channel.requirement_keys:
            if requirement and key != requirement:
                continue
            by_requirement.setdefault(key, []).append(item["name"])
    missing_entries = [item for item in rows if not item["entry_exists"]]
    return {
        "success": not missing_entries,
        "root": str(ROOT),
        "requirement": requirement or "all",
        "channels": rows,
        "by_requirement": by_requirement,
        "missing_entry_count": len(missing_entries),
        "missing_entries": missing_entries,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirement", default="", help="Filter by requirement key")
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args(argv)

    result = audit(args.requirement)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if args.fail_on_missing and result["missing_entry_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
