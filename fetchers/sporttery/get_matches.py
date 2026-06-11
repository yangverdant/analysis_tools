"""
体彩官网 - 获取比赛列表和赔率

功能:
1. 获取开售比赛列表 (含赔率)
2. 获取开奖结果
3. 获取赔率详情

数据来源: webapi.sporttery.cn (中国体彩官网API)
无需Cookie或API Key

使用示例:
    from fetchers.sporttery.get_matches import get_match_list, get_match_results

    # 获取今天开售的比赛
    matches = get_match_list()
    for m in matches:
        print(f"  {m['match_num']}: {m['home_team_cn']} vs {m['away_team_cn']}")

    # 获取某日开奖结果
    results = get_match_results("2025-05-25")
"""

import json
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

import requests
import urllib3

from fetchers.sporttery.config import (
    BASE_URL, URL_MATCH_LIST, URL_MATCH_RESULT, URL_ODDS,
    REQUEST_TIMEOUT, PLAY_TYPES
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


def _create_session() -> requests.Session:
    """创建HTTP会话"""
    session = requests.Session()
    session.trust_env = False
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.sporttery.cn/',
        'Origin': 'https://www.sporttery.cn',
    })
    return session


# ==================== 核心接口 ====================

def get_match_list(match_date: str = None) -> List[Dict]:
    """获取开售比赛列表

    Args:
        match_date: 日期字符串 "2025-05-25", 默认今天

    Returns:
        [{
            "lottery_match_id": "202505257001",
            "match_num": "7001",
            "home_team_cn": "水户蜀葵",
            "away_team_cn": "川崎前锋",
            "league_name_cn": "日职",
            "match_date": "2025-05-25",
            "match_time": "13:00",
            "handicap_line": 0,
            "odds": {
                "spf": {"h": "2.15", "d": "3.20", "a": "3.05"},
                "rqspf": {"h": "1.85", "d": "3.50", "a": "4.20"}
            },
            "play_types": ["spf", "rqspf"],
            ...
        }, ...]
    """
    if match_date is None:
        match_date = date.today().strftime('%Y-%m-%d')

    session = _create_session()
    params = {
        'sellStatus': 'on',
        'date': match_date
    }

    try:
        response = session.get(URL_MATCH_LIST, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        data = json.loads(response.text)
        if not data.get('success'):
            logger.warning("API returned success=false")
            return []

        matches = _parse_matches(data)

        print(f"[sporttery] {match_date}: {len(matches)} 场开售比赛")
        return matches

    except Exception as e:
        logger.error(f"获取比赛列表失败: {e}")
        print(f"[错误] 获取比赛列表失败: {str(e)[:60]}")
        return []


def get_match_results(match_date: str = None) -> List[Dict]:
    """获取开奖结果

    Args:
        match_date: 日期字符串, 默认今天

    Returns:
        [{
            "lottery_match_id": "...",
            "home_team_cn": "...",
            "away_team_cn": "...",
            "home_score": 2,
            "away_score": 1,
            "spf_result": "H",     # 胜平负结果
            ...
        }, ...]
    """
    if match_date is None:
        match_date = date.today().strftime('%Y-%m-%d')

    session = _create_session()
    params = {
        'date': match_date
    }

    try:
        response = session.get(URL_MATCH_RESULT, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        data = json.loads(response.text)
        if not data.get('success'):
            return []

        results = _parse_results(data)

        print(f"[sporttery] {match_date}: {len(results)} 场开奖结果")
        return results

    except Exception as e:
        logger.error(f"获取开奖结果失败: {e}")
        print(f"[错误] 获取开奖结果失败: {str(e)[:60]}")
        return []


def get_odds(lottery_match_id: str, play_type: str = "spf") -> Optional[Dict]:
    """获取赔率详情

    Args:
        lottery_match_id: 体彩比赛ID
        play_type: 玩法类型 (spf/rqspf/bf/bqc/jqs)

    Returns:
        {"h": "2.15", "d": "3.20", "a": "3.05"} 或 None
    """
    session = _create_session()
    params = {
        'matchId': lottery_match_id,
        'playType': play_type
    }

    try:
        response = session.get(URL_ODDS, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        data = json.loads(response.text)
        if not data.get('success'):
            return None

        return data.get('value', {})

    except Exception as e:
        logger.error(f"获取赔率失败: {e}")
        return None


# ==================== 内部解析 ====================

def _parse_matches(data: Dict) -> List[Dict]:
    """解析比赛列表"""
    matches = []
    value = data.get('value', {})
    match_info_list = value.get('matchInfoList', [])

    for date_info in match_info_list:
        business_date = date_info.get('businessDate', '')
        sub_matches = date_info.get('subMatchList', [])

        for item in sub_matches:
            match_num = item.get('matchNum', '')
            lottery_match_id = f"{business_date.replace('-', '')}{match_num}"

            # 让球数(优先从hhad.goalLine, 其次letBall, 最后handicapLine)
            hhad = item.get('hhad', {})
            handicap_line = float(item.get('letBall', 0) or item.get('handicapLine', 0) or 0)
            if hhad.get('goalLine'):
                try:
                    handicap_line = float(hhad['goalLine'])
                except (ValueError, TypeError):
                    pass

            # 提取各玩法赔率(从顶层字段 had/hhad/crs/hafu/ttg)
            odds = {}
            play_types_list = []

            # 胜平负(SPF) — had字段
            had = item.get('had', {})
            if had and had.get('h'):
                odds['spf'] = {'h': had['h'], 'd': had['d'], 'a': had['a']}
                play_types_list.append('spf')

            # 让球胜平负(RQSPF) — hhad字段
            if hhad and hhad.get('h'):
                odds['rqspf'] = {'h': hhad['h'], 'd': hhad['d'], 'a': hhad['a']}
                play_types_list.append('rqspf')

            # 比分(BF) — crs字段
            crs = item.get('crs', {})
            if crs:
                score_odds = {}
                for k, v in crs.items():
                    if k.startswith('s') and not k.endswith('f') and not k.startswith('s1s') and v:
                        score_odds[k] = v
                if score_odds:
                    odds['bf'] = score_odds
                    play_types_list.append('bf')

            # 半全场(BQC) — hafu字段
            hafu = item.get('hafu', {})
            if hafu and hafu.get('hh'):
                odds['bqc'] = {
                    'hh': hafu.get('hh'), 'hd': hafu.get('hd'), 'ha': hafu.get('ha'),
                    'dh': hafu.get('dh'), 'dd': hafu.get('dd'), 'da': hafu.get('da'),
                    'ah': hafu.get('ah'), 'ad': hafu.get('ad'), 'aa': hafu.get('aa'),
                }
                play_types_list.append('bqc')

            # 进球数(JQS) — ttg字段
            ttg = item.get('ttg', {})
            if ttg and ttg.get('s0'):
                goals_odds = {}
                for i in range(8):
                    key = f's{i}'
                    if ttg.get(key):
                        goals_odds[key] = ttg[key]
                if goals_odds:
                    odds['jqs'] = goals_odds
                    play_types_list.append('jqs')

            match = {
                'lottery_match_id': lottery_match_id,
                'match_num': match_num,
                'home_team_cn': item.get('homeTeamAllName') or item.get('homeTeamAbbName', ''),
                'away_team_cn': item.get('awayTeamAllName') or item.get('awayTeamAbbName', ''),
                'league_name_cn': item.get('leagueAbbName') or item.get('leagueName', ''),
                'match_date': business_date,
                'match_time': item.get('matchTime', '').split('.')[0] if item.get('matchTime') else '',
                'handicap_line': handicap_line,
                'odds': odds,
                'play_types': play_types_list,
                'sell_end_time': item.get('sellEndTime', ''),
            }
            matches.append(match)

    return matches


def _parse_results(data: Dict) -> List[Dict]:
    """解析开奖结果"""
    results = []
    value = data.get('value', {})
    match_info_list = value.get('matchInfoList', [])

    for date_info in match_info_list:
        business_date = date_info.get('businessDate', '')
        sub_matches = date_info.get('subMatchList', [])

        for item in sub_matches:
            match_num = item.get('matchNum', '')
            lottery_match_id = f"{business_date.replace('-', '')}{match_num}"

            home_score = item.get('homeTeamScore')
            away_score = item.get('awayTeamScore')

            result = {
                'lottery_match_id': lottery_match_id,
                'match_num': match_num,
                'home_team_cn': item.get('homeTeamAllName') or item.get('homeTeamAbbName', ''),
                'away_team_cn': item.get('awayTeamAllName') or item.get('awayTeamAbbName', ''),
                'league_name_cn': item.get('leagueAbbName') or item.get('leagueName', ''),
                'match_date': business_date,
                'home_score': int(home_score) if home_score else None,
                'away_score': int(away_score) if away_score else None,
            }

            # 开奖结果
            for pt in ['spf', 'rqspf', 'bf', 'bqc', 'jqs']:
                result_code = item.get(f'{pt}Result')
                if result_code:
                    result[f'{pt}_result'] = result_code

            results.append(result)

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.sporttery.get_matches list")
        print("  python -m fetchers.sporttery.get_matches list 2025-05-25")
        print("  python -m fetchers.sporttery.get_matches results")
        print("  python -m fetchers.sporttery.get_matches results 2025-05-25")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        matches = get_match_list(date_str)
        for m in matches:
            spf = m['odds'].get('spf', {})
            odds_str = f" 胜平负={spf.get('h','?')}/{spf.get('d','?')}/{spf.get('a','?')}" if spf else ""
            print(f"  {m['match_num']} {m['league_name_cn']}: {m['home_team_cn']} vs {m['away_team_cn']}{odds_str}")

    elif cmd == "results":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        results = get_match_results(date_str)
        for r in results:
            score = f" {r['home_score']}-{r['away_score']}" if r['home_score'] else ""
            print(f"  {r['match_num']} {r['home_team_cn']}{score} {r['away_team_cn']}")