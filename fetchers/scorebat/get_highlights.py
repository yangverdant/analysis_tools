"""
ScoreBat视频集锦获取

功能:
1. 获取最新比赛视频集锦
2. 按联赛筛选
3. 按球队筛选

数据来源: scorebat.com (免费, 无需认证)

使用示例:
    from fetchers.scorebat.get_highlights import get_highlights

    # 最新集锦
    highlights = get_highlights()

    # 按联赛筛选
    pl = filter_by_competition(highlights, "Premier League")
"""

import os
import logging
from typing import Dict, List, Optional
import requests

from fetchers.scorebat.config import BASE_URL, REQUEST_TIMEOUT

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['NO_PROXY'] = '*'

logger = logging.getLogger(__name__)

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = False
    return _session


# ==================== 核心接口 ====================

def get_highlights() -> List[Dict]:
    """获取最新比赛视频集锦

    Returns:
        [{"title", "competition", "date", "url", "thumbnail",
          "home_team", "away_team", "videos", "source"}]
    """
    session = _get_session()
    try:
        resp = session.get(BASE_URL, timeout=REQUEST_TIMEOUT,
                           proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            data = resp.json()
            if not isinstance(data, list):
                return []

            highlights = []
            for item in data:
                # 解析比赛双方
                title = item.get("title", "")
                teams = title.split(" - ") if " - " in title else [title, ""]

                # 视频列表
                videos = []
                for v in item.get("videos", []):
                    videos.append({
                        'title': v.get("title", ""),
                        'embed': v.get("embed", ""),
                        'url': v.get("url", ""),
                    })

                highlights.append({
                    'title': title,
                    'competition': item.get("competition", {}).get("name", ""),
                    'competition_id': item.get("competition", {}).get("id"),
                    'date': item.get("date", ""),
                    'url': item.get("url", ""),
                    'thumbnail': item.get("thumbnail", ""),
                    'home_team': teams[0].strip() if len(teams) > 0 else "",
                    'away_team': teams[1].strip() if len(teams) > 1 else "",
                    'matchview_url': item.get("matchviewUrl", ""),
                    'competition_url': item.get("competitionUrl", ""),
                    'videos': videos,
                    'source': 'scorebat'
                })

            print(f"[scorebat] 集锦: {len(highlights)}条")
            return highlights

    except Exception as e:
        logger.error(f"ScoreBat请求失败: {e}")
        print(f"[错误] ScoreBat请求失败: {str(e)[:60]}")

    return []


def filter_by_competition(highlights: List[Dict], competition: str) -> List[Dict]:
    """按联赛筛选集锦

    Args:
        highlights: get_highlights()返回的数据
        competition: 联赛名 (如 "Premier League", "La Liga")

    Returns:
        筛选后的集锦列表
    """
    return [h for h in highlights if competition.lower() in h.get("competition", "").lower()]


def filter_by_team(highlights: List[Dict], team_name: str) -> List[Dict]:
    """按球队筛选集锦

    Args:
        highlights: get_highlights()返回的数据
        team_name: 球队名

    Returns:
        筛选后的集锦列表
    """
    return [h for h in highlights
            if team_name.lower() in h.get("home_team", "").lower()
            or team_name.lower() in h.get("away_team", "").lower()
            or team_name.lower() in h.get("title", "").lower()]


if __name__ == "__main__":
    highlights = get_highlights()
    for h in highlights[:10]:
        print(f"  {h['title']} [{h['competition']}]")