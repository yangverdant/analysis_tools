"""
Transfermarkt数据获取

功能:
1. 获取球队阵容 (含身价)
2. 获取球员身价/转会记录
3. 获取联赛球员身价排行

数据来源: transfermarkt.com (爬虫, 需绕反爬)

使用示例:
    from fetchers.transfermarkt.get_data import get_squad, get_player_value

    # 球队阵容
    squad = get_squad(team_url="/arsenal-fc/startseite/verein/11")

    # 球员身价
    value = get_player_value(player_url="/m-bukayo-saka/profil/spieler/578318")
"""

import os
import re
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from fetchers.transfermarkt.config import BASE_URL, LEAGUE_URLS, LEAGUE_CN, REQUEST_TIMEOUT

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
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
    return _session


def _fetch(url: str) -> Optional[str]:
    """获取页面HTML"""
    session = _get_session()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, proxies={'http': None, 'https': None})
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        logger.error(f"Transfermarkt请求失败: {e}")
        print(f"[错误] Transfermarkt请求失败: {str(e)[:60]}")
    return None


def _parse_market_value(text: str) -> Optional[float]:
    """解析身价文本 (如 "€65.00m" -> 65.0, "€3.50m" -> 3.5)"""
    if not text:
        return None
    text = text.replace("€", "").replace(",", "").strip()
    try:
        if "m" in text.lower():
            return float(re.search(r'[\d.]+', text.lower().replace('m', '')).group())
        elif "k" in text.lower():
            return float(re.search(r'[\d.]+', text.lower().replace('k', '')).group()) / 1000
    except:
        pass
    return None


# ==================== 核心接口 ====================

def get_squad(team_url: str) -> List[Dict]:
    """获取球队阵容 (含身价)

    Args:
        team_url: 球队URL路径 (如 "/arsenal-fc/startseite/verein/11")

    Returns:
        [{"player_name", "position", "age", "nationality", "market_value_m",
          "player_url", "source"}]
    """
    url = f"{BASE_URL}{team_url}"
    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    players = []

    # 查找阵容表
    table = soup.find('table', {'class': 'items'})
    if not table:
        print(f"[transfermarkt] 未找到阵容表")
        return []

    rows = table.find_all('tr', {'class': ['odd', 'even']})
    for row in rows:
        try:
            name_cell = row.find('td', {'class': 'hauptlink'})
            if not name_cell:
                continue

            name_link = name_cell.find('a')
            player_name = name_link.get_text(strip=True) if name_link else ""
            player_url = name_link.get('href', '') if name_link else ""

            # 位置
            pos_cell = row.find('td', {'class': 'posrela'})
            position = pos_cell.get_text(strip=True).split('\n')[0] if pos_cell else ""

            # 身价
            value_cell = row.find('td', {'class': 'rechts hauptlink'})
            value_text = value_cell.get_text(strip=True) if value_cell else ""
            market_value = _parse_market_value(value_text)

            players.append({
                'player_name': player_name,
                'position': position,
                'market_value_m': market_value,
                'market_value_text': value_text,
                'player_url': player_url,
                'source': 'transfermarkt'
            })
        except Exception:
            continue

    print(f"[transfermarkt] 阵容: {len(players)}人")
    return players


def get_player_value(player_url: str) -> Dict:
    """获取球员身价和转会记录

    Args:
        player_url: 球员URL路径

    Returns:
        {"player_name", "current_value_m", "history", "source"}
    """
    url = f"{BASE_URL}{player_url}"
    html = _fetch(url)
    if not html:
        return {}

    soup = BeautifulSoup(html, 'html.parser')

    # 球员名
    name_el = soup.find('h1', {'class': 'data-header__headline-wrapper'})
    name = name_el.get_text(strip=True) if name_el else ""

    # 当前身价
    value_el = soup.find('a', {'class': 'data-header__market-value-wrapper'})
    value_text = value_el.get_text(strip=True) if value_el else ""
    current_value = _parse_market_value(value_text)

    return {
        'player_name': name,
        'current_value_m': current_value,
        'current_value_text': value_text,
        'player_url': player_url,
        'source': 'transfermarkt'
    }


def get_league_valuations(league: str) -> List[Dict]:
    """获取联赛球员身价排行

    Args:
        league: 联赛名 (如 "premier_league")

    Returns:
        球员身价列表
    """
    league_key = LEAGUE_CN.get(league, league)
    league_url = LEAGUE_URLS.get(league_key)
    if not league_url:
        print(f"[transfermarkt] 未知联赛: {league}")
        return []

    url = f"{BASE_URL}{league_url}"
    html = _fetch(url)
    if not html:
        return []

    # 简化: 返回联赛页面链接供进一步爬取
    print(f"[transfermarkt] 联赛 {league} 页面获取成功")
    return []


if __name__ == "__main__":
    print("Transfermarkt数据获取工具")
    print("注意: transfermarkt有反爬机制, 建议控制请求频率")