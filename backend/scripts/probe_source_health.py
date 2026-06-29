#!/usr/bin/env python3
"""Lightweight source health probe for data sources that don't need complex collection.

Probes:
- FIFA ranking (local file)
- wttr.in weather API
- football-data.co.uk CSV availability
- apifootball API
- api-sports (api-football-v1) API
- bifen188 live score site
- zhibo8 news feed

Updates data_source_health table with results.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import requests, fallback to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "football_v2.db"
FIFA_RANKING_PATH = PROJECT_ROOT / "fetchers" / "fifa_ranking" / "data" / "fifa_ranking_current.json"
WTTR_URL = "https://wttr.in/?format=j1"
FOOTBALL_DATA_UK_BASE = "https://www.football-data.co.uk"
APIFOOTBALL_BASE = "https://apiv3.apifootball.com"
API_SPORTS_BASE = "https://v3.football.api-sports.io"
BIFEN188_URL = "http://www.bifen188.com"
ZHIBO8_NEWS_URL = "https://news.zhibo8.com/zuqiu/more.htm"


def probe_fifa_ranking() -> Dict[str, Any]:
    """Check if FIFA ranking file exists and has valid content."""
    result = {
        "source_name": "fifa_ranking",
        "source_category": "team_strength",
        "status": "unknown",
        "message": "",
        "record_count": 0,
    }

    try:
        if not FIFA_RANKING_PATH.exists():
            result["status"] = "missing"
            result["message"] = f"File not found: {FIFA_RANKING_PATH}"
            return result

        with open(FIFA_RANKING_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check if it's a valid ranking structure
        if isinstance(data, list):
            result["record_count"] = len(data)
            if len(data) > 0:
                result["status"] = "healthy"
                result["message"] = f"{len(data)} teams in ranking"
            else:
                result["status"] = "empty"
                result["message"] = "Empty ranking file"
        elif isinstance(data, dict):
            # Could be {"rankings": [...]} or similar
            rankings = data.get("rankings") or data.get("teams") or data
            if isinstance(rankings, list):
                result["record_count"] = len(rankings)
                result["status"] = "healthy" if len(rankings) > 0 else "empty"
                result["message"] = f"{len(rankings)} teams in ranking"
            else:
                result["status"] = "healthy"
                result["message"] = "Valid JSON structure"
        else:
            result["status"] = "invalid"
            result["message"] = "Unexpected data format"

    except json.JSONDecodeError as e:
        result["status"] = "error"
        result["message"] = f"JSON parse error: {e}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    return result


def probe_wttr_in() -> Dict[str, Any]:
    """Check wttr.in weather API availability."""
    result = {
        "source_name": "wttr_in",
        "source_category": "weather",
        "status": "unknown",
        "message": "",
    }

    try:
        if HAS_REQUESTS:
            resp = requests.get(WTTR_URL, timeout=10, headers={"User-Agent": "curl"})
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, dict):
                    result["status"] = "healthy"
                    result["message"] = "API responding"
                else:
                    result["status"] = "degraded"
                    result["message"] = "Unexpected response format"
            else:
                result["status"] = "error"
                result["message"] = f"HTTP {resp.status_code}"
        else:
            req = urllib.request.Request(WTTR_URL, headers={"User-Agent": "curl"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data and isinstance(data, dict):
                    result["status"] = "healthy"
                    result["message"] = "API responding"
                else:
                    result["status"] = "degraded"
                    result["message"] = "Unexpected response format"

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)[:100]

    return result


def probe_football_data_uk() -> Dict[str, Any]:
    """Check football-data.co.uk CSV availability for current season."""
    result = {
        "source_name": "football_data_uk",
        "source_category": "odds_history",
        "status": "unknown",
        "message": "",
    }

    # Try to fetch a known CSV file (e.g., Premier League current season)
    try:
        # URL pattern: https://www.football-data.co.uk/mmz4281/2425/E0.csv
        # Use a simple HEAD request to check availability
        test_url = f"{FOOTBALL_DATA_UK_BASE}/mmz4281/2425/E0.csv"

        if HAS_REQUESTS:
            resp = requests.head(test_url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                result["status"] = "healthy"
                result["message"] = "CSV files accessible (2425 season)"
            elif resp.status_code == 404:
                # Try previous season
                test_url_prev = f"{FOOTBALL_DATA_UK_BASE}/mmz4281/2324/E0.csv"
                resp = requests.head(test_url_prev, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    result["status"] = "degraded"
                    result["message"] = "Only 2324 season CSV available"
                else:
                    result["status"] = "error"
                    result["message"] = "CSV files not accessible"
            else:
                result["status"] = "error"
                result["message"] = f"HTTP {resp.status_code}"
        else:
            req = urllib.request.Request(test_url, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        result["status"] = "healthy"
                        result["message"] = "CSV files accessible"
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    result["status"] = "degraded"
                    result["message"] = "Season CSV not found"
                else:
                    result["status"] = "error"
                    result["message"] = f"HTTP {e.code}"

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)[:100]

    return result


def _load_api_key(source: str) -> Optional[str]:
    """Load API key from config files."""
    # Try api_keys.yaml first
    yaml_path = PROJECT_ROOT / "config" / "api_keys.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if source == "apifootball" and data:
                return (data.get("apifootball") or {}).get("api_key")
            if source == "api_sports" and data:
                return (data.get("rapidapi") or {}).get("key")
        except Exception:
            pass

    # Try direct config import
    if source == "apifootball":
        try:
            import sys
            sys.path.insert(0, str(PROJECT_ROOT))
            from fetchers.apifootball.config import API_KEY
            return API_KEY
        except Exception:
            pass
    if source == "api_sports":
        try:
            import sys
            sys.path.insert(0, str(PROJECT_ROOT))
            from fetchers.api_sports.config import RAPIDAPI_KEY
            return RAPIDAPI_KEY
        except Exception:
            pass

    return None


def probe_apifootball() -> Dict[str, Any]:
    """Check apifootball API availability with a lightweight request."""
    result = {
        "source_name": "apifootball",
        "source_category": "match_data",
        "status": "unknown",
        "message": "",
    }

    api_key = _load_api_key("apifootball")
    if not api_key:
        result["status"] = "missing"
        result["message"] = "API key not found"
        return result

    try:
        # Use get_countries action — lightweight, returns small payload
        url = f"{APIFOOTBALL_BASE}/?action=get_countries&APIkey={api_key}"
        if HAS_REQUESTS:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("error"):
                    err_msg = data.get("message", str(data.get("error")))
                    if "payment" in err_msg.lower() or "subscribe" in err_msg.lower():
                        result["status"] = "degraded"
                        result["message"] = f"Account needs payment: {err_msg}"
                    else:
                        result["status"] = "error"
                        result["message"] = f"API error: {err_msg}"
                elif isinstance(data, list) and len(data) > 0:
                    result["status"] = "healthy"
                    result["message"] = f"API responding, {len(data)} countries"
                else:
                    result["status"] = "degraded"
                    result["message"] = "Unexpected response format"
            else:
                result["status"] = "error"
                result["message"] = f"HTTP {resp.status_code}"
        else:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("error"):
                    result["status"] = "error"
                    result["message"] = f"API error: {data.get('message', data.get('error'))}"
                elif isinstance(data, list) and len(data) > 0:
                    result["status"] = "healthy"
                    result["message"] = f"API responding, {len(data)} countries"
                else:
                    result["status"] = "degraded"
                    result["message"] = "Unexpected response"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)[:100]

    return result


def probe_api_sports() -> Dict[str, Any]:
    """Check api-sports (api-football-v1) API availability."""
    result = {
        "source_name": "api_sports",
        "source_category": "match_data",
        "status": "unknown",
        "message": "",
    }

    api_key = _load_api_key("api_sports")
    if not api_key:
        result["status"] = "missing"
        result["message"] = "API key not found"
        return result

    try:
        # Use /status endpoint — lightweight
        url = f"{API_SPORTS_BASE}/status"
        headers = {"x-apisports-key": api_key}
        if HAS_REQUESTS:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # Check for token errors — API returns 200 even with invalid key
                errors = data.get("errors") or {}
                token_error = errors.get("token") or ""
                if token_error:
                    result["status"] = "error"
                    result["message"] = f"API key invalid: {token_error[:80]}"
                else:
                    account = (data.get("response") or {}).get("account", {}) if isinstance(data.get("response"), dict) else {}
                    req_limit = account.get("requests", {}) if isinstance(account, dict) else {}
                    current = req_limit.get("current", 0)
                    limit_day = req_limit.get("limit_day", 0)
                    result["status"] = "healthy"
                    result["message"] = f"API responding, {current}/{limit_day} requests used today"
            else:
                result["status"] = "error"
                result["message"] = f"HTTP {resp.status_code}"
        else:
            req = urllib.request.Request(url, headers={"x-apisports-key": api_key})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                errors = data.get("errors") or {}
                if errors.get("token"):
                    result["status"] = "error"
                    result["message"] = f"API key invalid: {errors['token'][:80]}"
                else:
                    result["status"] = "healthy"
                    result["message"] = "API responding"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)[:100]

    return result


def probe_bifen188() -> Dict[str, Any]:
    """Check bifen188 live score site availability."""
    result = {
        "source_name": "bifen188",
        "source_category": "live_score",
        "status": "disabled",
        "message": "Site is a blank shell (404 iframe); collection disabled",
    }
    return result


def probe_zhibo8() -> Dict[str, Any]:
    """Check zhibo8 news feed availability."""
    result = {
        "source_name": "zhibo8",
        "source_category": "news",
        "status": "unknown",
        "message": "",
    }

    try:
        if HAS_REQUESTS:
            resp = requests.get(
                ZHIBO8_NEWS_URL,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                if "dataList" in resp.text or "新闻" in resp.text or "zuqiu" in resp.text:
                    result["status"] = "healthy"
                    result["message"] = "News feed accessible"
                else:
                    result["status"] = "degraded"
                    result["message"] = "Feed responding but content unexpected"
            else:
                result["status"] = "error"
                result["message"] = f"HTTP {resp.status_code}"
        else:
            req = urllib.request.Request(
                ZHIBO8_NEWS_URL, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                if "dataList" in content or "新闻" in content:
                    result["status"] = "healthy"
                    result["message"] = "News feed accessible"
                else:
                    result["status"] = "degraded"
                    result["message"] = "Content unexpected"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)[:100]

    return result


def update_health_table(db_path: str, probe_results: List[Dict[str, Any]]) -> int:
    """Update data_source_health table with probe results."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    updated = 0

    # Ensure failure_reason column exists
    try:
        cursor.execute("ALTER TABLE data_source_health ADD COLUMN failure_reason TEXT")
    except Exception:
        pass  # Column already exists

    for result in probe_results:
        source_name = result["source_name"]
        source_category = result.get("source_category", "general")
        status = result["status"]
        success = status in ("healthy", "degraded")
        message = result.get("message", "")
        failure_reason = None if success else message

        # Check if entry exists
        cursor.execute(
            "SELECT health_id FROM data_source_health WHERE source_name = ?",
            (source_name,)
        )
        existing = cursor.fetchone()

        if existing:
            if success:
                cursor.execute("""
                    UPDATE data_source_health
                    SET status = ?, last_success = ?, updated_at = ?,
                        success_rate = CASE WHEN success_rate = 0 THEN 1.0
                                       ELSE success_rate * 0.9 + 0.1 END,
                        failure_reason = NULL
                    WHERE source_name = ?
                """, (status, now, now, source_name))
            else:
                cursor.execute("""
                    UPDATE data_source_health
                    SET status = ?, last_failure = ?, updated_at = ?,
                        success_rate = success_rate * 0.9,
                        failure_count = COALESCE(failure_count, 0) + 1,
                        failure_reason = ?
                    WHERE source_name = ?
                """, (status, now, now, failure_reason, source_name))
            updated += 1
        else:
            # Insert new entry
            cursor.execute("""
                INSERT OR REPLACE INTO data_source_health
                (source_name, source_category, status, last_success, updated_at, success_rate, failure_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (source_name, source_category, status, now if success else None, now, 1.0 if success else 0.5, failure_reason))
            updated += 1

    conn.commit()
    conn.close()
    return updated


def run_probes() -> Dict[str, Any]:
    """Run all probes and return results."""
    results = []

    logger.info("Probing FIFA ranking...")
    fifa = probe_fifa_ranking()
    results.append(fifa)
    logger.info(f"  FIFA ranking: {fifa['status']} - {fifa['message']}")

    logger.info("Probing wttr.in...")
    wttr = probe_wttr_in()
    results.append(wttr)
    logger.info(f"  wttr.in: {wttr['status']} - {wttr['message']}")

    logger.info("Probing football-data.co.uk...")
    fd_uk = probe_football_data_uk()
    results.append(fd_uk)
    logger.info(f"  football-data.co.uk: {fd_uk['status']} - {fd_uk['message']}")

    logger.info("Probing apifootball...")
    af = probe_apifootball()
    results.append(af)
    logger.info(f"  apifootball: {af['status']} - {af['message']}")

    logger.info("Probing api-sports...")
    asp = probe_api_sports()
    results.append(asp)
    logger.info(f"  api-sports: {asp['status']} - {asp['message']}")

    logger.info("Probing bifen188...")
    bf = probe_bifen188()
    results.append(bf)
    logger.info(f"  bifen188: {bf['status']} - {bf['message']}")

    logger.info("Probing zhibo8...")
    zb = probe_zhibo8()
    results.append(zb)
    logger.info(f"  zhibo8: {zb['status']} - {zb['message']}")

    # Update database
    db_path = str(DB_PATH)
    if DB_PATH.exists():
        updated = update_health_table(db_path, results)
        logger.info(f"Updated {updated} entries in data_source_health")
    else:
        logger.warning(f"Database not found: {db_path}")

    return {
        "success": True,
        "probed_at": datetime.now().isoformat(),
        "sources": results,
        "updated_count": len(results),
    }


if __name__ == "__main__":
    result = run_probes()
    print(json.dumps(result, indent=2, ensure_ascii=False))
