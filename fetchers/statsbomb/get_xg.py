"""
StatsBomb xG数据获取

功能:
1. 从本地JSON文件读取StatsBomb数据
2. 计算比赛xG
3. 提取球员/球队xG统计

数据来源: StatsBomb Open Data (本地JSON文件, 需先下载)

使用示例:
    from fetchers.statsbomb.get_xg import get_match_xg, get_competition_matches

    # 获取比赛xG
    xg = get_match_xg(match_id="3788741")

    # 获取某赛事比赛列表
    matches = get_competition_matches("champions_league")
"""

import os
import json
import logging
from typing import Dict, List, Optional

from fetchers.statsbomb.config import DATA_DIR, COMPETITION_IDS, COMPETITION_CN

logger = logging.getLogger(__name__)


def _resolve_competition(comp: str) -> int:
    if comp in COMPETITION_IDS:
        return COMPETITION_IDS[comp]
    cn = COMPETITION_CN.get(comp)
    if cn and cn in COMPETITION_IDS:
        return COMPETITION_IDS[cn]
    try:
        return int(comp)
    except:
        return 0


def _load_json(filepath: str) -> Optional[Dict]:
    """加载本地JSON文件"""
    if not os.path.exists(filepath):
        logger.error(f"文件不存在: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"JSON解析失败: {e}")
    return None


# ==================== 核心接口 ====================

def get_competition_matches(competition: str, season: str = None) -> List[Dict]:
    """获取赛事比赛列表

    Args:
        competition: 赛事名 (如 "champions_league")
        season: 赛季ID

    Returns:
        [{"match_id", "home_team", "away_team", "home_score", "away_score",
          "competition", "season", "match_date", "source"}]
    """
    comp_id = _resolve_competition(competition)
    if comp_id == 0:
        print(f"[statsbomb] 未知赛事: {competition}")
        return []

    # 尝试从本地加载
    matches_path = os.path.join(DATA_DIR, "matches", f"{comp_id}.json")
    if season:
        matches_path = os.path.join(DATA_DIR, "matches", f"{comp_id}_{season}.json")

    data = _load_json(matches_path)
    if not data:
        print(f"[statsbomb] 本地数据不存在, 请先下载: {matches_path}")
        return []

    matches = []
    for item in data:
        home = item.get("home_team", {})
        away = item.get("away_team", {})
        score = item.get("home_score"), item.get("away_score")

        matches.append({
            'match_id': str(item.get("match_id", "")),
            'home_team': home.get("home_team_name", ""),
            'home_team_id': home.get("home_team_id"),
            'away_team': away.get("away_team_name", ""),
            'away_team_id': away.get("away_team_id"),
            'home_score': item.get("home_score"),
            'away_score': item.get("away_score"),
            'competition': item.get("competition", {}).get("competition_name", ""),
            'season': item.get("season", {}).get("season_name", ""),
            'match_date': item.get("match_date", ""),
            'source': 'statsbomb'
        })

    print(f"[statsbomb] {competition}: {len(matches)}场")
    return matches


def get_match_xg(match_id: str) -> Dict:
    """获取比赛xG数据

    Args:
        match_id: 比赛ID

    Returns:
        {"match_id", "home_team", "away_team", "home_xg", "away_xg",
         "home_shots", "away_shots", "home_goals", "away_goals", "source"}
    """
    events_path = os.path.join(DATA_DIR, "events", f"{match_id}.json")
    data = _load_json(events_path)
    if not data:
        print(f"[statsbomb] 本地数据不存在, 请先下载: {events_path}")
        return {}

    home_xg = 0.0
    away_xg = 0.0
    home_shots = 0
    away_shots = 0
    home_team = ""
    away_team = ""

    for event in data:
        if event.get("type", {}).get("name") == "Shot":
            shot = event.get("shot", {})
            xg = shot.get("statsbomb_xg", 0) or 0
            team = event.get("team", {}).get("name", "")

            if not home_team:
                home_team = team
            elif team != home_team and not away_team:
                away_team = team

            if team == home_team:
                home_xg += xg
                home_shots += 1
            else:
                away_xg += xg
                away_shots += 1

    return {
        'match_id': match_id,
        'home_team': home_team,
        'away_team': away_team,
        'home_xg': round(home_xg, 2),
        'away_xg': round(away_xg, 2),
        'home_shots': home_shots,
        'away_shots': away_shots,
        'source': 'statsbomb'
    }


def get_match_events(match_id: str) -> List[Dict]:
    """获取比赛事件列表

    Returns:
        [{"event_id", "type", "player", "team", "minute", "xg", "detail"}]
    """
    events_path = os.path.join(DATA_DIR, "events", f"{match_id}.json")
    data = _load_json(events_path)
    if not data:
        return []

    events = []
    for event in data:
        evt_type = event.get("type", {}).get("name", "")
        events.append({
            'event_id': event.get("id"),
            'type': evt_type,
            'player': event.get("player", {}).get("name", ""),
            'team': event.get("team", {}).get("name", ""),
            'minute': event.get("minute"),
            'second': event.get("second"),
            'xg': event.get("shot", {}).get("statsbomb_xg") if evt_type == "Shot" else None,
            'detail': event,
            'source': 'statsbomb'
        })

    return events


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.statsbomb.get_xg competitions")
        print("  python -m fetchers.statsbomb.get_xg match 3788741")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "competitions":
        for name, cid in COMPETITION_IDS.items():
            print(f"  {name}: {cid}")
    elif cmd == "match":
        mid = sys.argv[2] if len(sys.argv) > 2 else "3788741"
        xg = get_match_xg(mid)
        if xg:
            print(f"  {xg['home_team']} ({xg['home_xg']}) vs ({xg['away_xg']}) {xg['away_team']}")