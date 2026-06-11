"""
Okooo - 获取比赛ID列表

功能:
1. 按日期获取当天所有比赛的ID和基本信息
2. 按联赛+轮次获取某轮所有比赛的ID

输出: list of dict, 每个dict包含 match_id, home_team, away_team 等

使用示例:
    from fetchers.okooo.get_match_ids import get_match_ids_by_date, get_match_ids_by_league

    # 获取今天所有比赛
    matches = get_match_ids_by_date("2025-05-25")

    # 获取英超第38轮比赛
    matches = get_match_ids_by_league("英超", round_num=38)

    # 获取英超全部38轮比赛ID
    all_ids = get_match_ids_by_league("英超")
"""

import re
import time
import random
import urllib3
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from fetchers.okooo.config import (
    COOKIE, LEAGUES, BASE_URL,
    REQUEST_INTERVAL_MIN, REQUEST_INTERVAL_MAX, MAX_RETRIES
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _create_session() -> requests.Session:
    """创建带认证的HTTP会话"""
    session = requests.Session()
    session.verify = False
    session.trust_env = False
    # 绕过系统代理
    import os
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    os.environ['NO_PROXY'] = '*'

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })

    if COOKIE:
        session.headers.update({"Cookie": COOKIE})
    else:
        print("[警告] 未配置Cookie! 请在 config.py 中填入Cookie，否则无法访问okooo")

    return session


def _decode_response(res: requests.Response) -> str:
    """智能解码响应"""
    content_lower = res.content[:2000].lower()
    if b'utf-8' in content_lower or 'utf-8' in res.headers.get('Content-Type', '').lower():
        res.encoding = 'utf-8'
    else:
        res.encoding = 'gb18030'
    return res.text


def _is_waf_blocked(html_text: str) -> bool:
    """检测WAF拦截"""
    waf_keywords = ["验证码", "安全中心", "Forbidden", "Access Denied",
                    "您的访问速度过快", "aliyun_waf"]
    if any(k in html_text for k in waf_keywords):
        return True
    if len(html_text) < 500:
        return True
    return False


def _fetch_page(session: requests.Session, url: str, referer: str = "") -> Optional[str]:
    """带重试的页面抓取"""
    if referer:
        session.headers.update({"Referer": referer})

    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(random.uniform(REQUEST_INTERVAL_MIN, REQUEST_INTERVAL_MAX))
            res = session.get(url, timeout=(10, 20), verify=False)
            html_text = _decode_response(res)

            if _is_waf_blocked(html_text):
                print(f"  [WAF] 被拦截 (尝试 {attempt+1}/{MAX_RETRIES}): {html_text[:80]}")
                time.sleep(5.0)
                continue

            return html_text

        except Exception as e:
            print(f"  [网络错误] {str(e)[:50]}")
            time.sleep(8.0)

    print(f"  [跳过] 连续{MAX_RETRIES}次失败: {url}")
    return None


def _parse_match_row(row) -> Optional[Dict]:
    """从HTML行中解析比赛信息"""
    match_id = row.get('matchid', '')
    if not match_id:
        return None

    home_team = ""
    away_team = ""
    home_score = None
    away_score = None
    match_time = ""
    league_name = ""

    # 提取队名 - 多种class名兼容
    team_selectors = ['jsTeamName', 'team-name', 'jsTeam']
    teams_found = []
    for sel in team_selectors:
        teams_found = row.find_all(class_=re.compile(sel))
        if teams_found:
            break

    # 如果没找到，尝试从a标签提取
    if not teams_found:
        links = row.find_all('a', href=re.compile(r'/soccer/match/\d+/'))
        teams_found = [a for a in links if a.get_text(strip=True)]

    if len(teams_found) >= 2:
        home_team = re.sub(r'[【】\[\]]', '', teams_found[0].get_text(strip=True))
        away_team = re.sub(r'[【】\[\]]', '', teams_found[1].get_text(strip=True))

    # 提取比分
    vs_div = row.find('div', class_='vs')
    if vs_div:
        scores = [t.strip() for t in vs_div.stripped_strings if t.strip().isdigit()]
        if len(scores) >= 2:
            home_score = int(scores[0])
            away_score = int(scores[1])

    # 也尝试从文本中提取比分 "2-1" 或 "2:1"
    if home_score is None:
        all_text = row.get_text()
        score_match = re.search(r'(\d+)\s*[-:]\s*(\d+)', all_text)
        if score_match:
            home_score = int(score_match.group(1))
            away_score = int(score_match.group(2))

    return {
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "match_time": match_time,
        "league_name": league_name,
    }


def get_match_ids_by_date(date: str = None) -> List[Dict]:
    """按日期获取比赛ID列表

    Args:
        date: 日期字符串, 格式 "2025-05-25", 默认今天

    Returns:
        [{"match_id": "12345", "home_team": "阿森纳", "away_team": "切尔西", ...}, ...]
    """
    if not date:
        date = time.strftime('%Y-%m-%d')

    session = _create_session()
    url = f"{BASE_URL}/soccer/match/{date}/"
    print(f"[okooo] 获取 {date} 比赛列表: {url}")

    html = _fetch_page(session, url, f"{BASE_URL}/")
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    matches = []

    # 方式1: 从tr[matchid]提取
    match_rows = soup.find_all('tr', attrs={'matchid': True})
    for row in match_rows:
        info = _parse_match_row(row)
        if info:
            matches.append(info)

    # 方式2: 如果方式1没数据, 尝试从其他结构提取
    if not matches:
        print("  [调试] 未找到tr[matchid], 尝试其他解析方式...")
        # 尝试从比赛链接中提取
        for a_tag in soup.find_all('a', href=re.compile(r'/soccer/match/(\d+)/')):
            href = a_tag.get('href', '')
            m = re.search(r'/soccer/match/(\d+)/', href)
            if m:
                match_id = m.group(1)
                # 避免重复
                if not any(x['match_id'] == match_id for x in matches):
                    matches.append({
                        "match_id": match_id,
                        "home_team": "",
                        "away_team": "",
                        "home_score": None,
                        "away_score": None,
                        "match_time": "",
                        "league_name": "",
                    })

    print(f"  [结果] 获取到 {len(matches)} 场比赛")
    return matches


def get_match_ids_by_league(league_name: str, round_num: int = None) -> List[Dict]:
    """按联赛获取比赛ID列表

    Args:
        league_name: 联赛中文名, 如 "英超", "西甲" (需在config.LEAGUES中配置)
        round_num: 轮次号, 如 38. 如果为None则获取全部轮次

    Returns:
        [{"match_id": "12345", "home_team": "阿森纳", "away_team": "切尔西", ...}, ...]
    """
    league_config = LEAGUES.get(league_name)
    if not league_config:
        print(f"[错误] 联赛 '{league_name}' 未在配置中找到")
        print(f"  可用联赛: {', '.join(LEAGUES.keys())}")
        return []

    league_id = league_config["league_id"]
    season_id = league_config.get("season_id")
    total_rounds = league_config.get("rounds", 38)

    if not season_id:
        print(f"[警告] 联赛 '{league_name}' 未配置season_id, 尝试不带赛季ID访问")
        season_id_str = ""
    else:
        season_id_str = f"/{season_id}"

    session = _create_session()
    all_matches = []

    if round_num:
        rounds_to_fetch = [round_num]
    else:
        rounds_to_fetch = range(1, total_rounds + 1)

    for rnd in rounds_to_fetch:
        # URL格式: /soccer/league/{league_id}/schedule/{season_id}/1-36-{round}/
        # 简化格式: /soccer/league/{league_id}/schedule/
        if season_id:
            url = f"{BASE_URL}/soccer/league/{league_id}/schedule/{season_id}/1-{total_rounds}-{rnd}/"
        else:
            url = f"{BASE_URL}/soccer/league/{league_id}/schedule/"

        print(f"[okooo] 获取 {league_name} 第{rnd}轮: {url}")

        html = _fetch_page(session, url, f"{BASE_URL}/soccer/league/{league_id}/")
        if not html:
            continue

        soup = BeautifulSoup(html, 'html.parser')
        match_rows = soup.find_all('tr', attrs={'matchid': True})

        round_matches = []
        for row in match_rows:
            info = _parse_match_row(row)
            if info:
                info["league_name"] = league_name
                info["round"] = rnd
                round_matches.append(info)

        all_matches.extend(round_matches)
        print(f"  第{rnd}轮: {len(round_matches)} 场比赛")

        # 更新Referer
        session.headers.update({"Referer": url})

    print(f"\n[结果] {league_name} 共获取 {len(all_matches)} 场比赛")
    return all_matches


def get_match_ids_to_file(date: str = None, output_path: str = None,
                          league_name: str = None, round_num: int = None) -> str:
    """获取比赛ID并保存到文件

    Args:
        date: 按日期获取
        output_path: 输出文件路径, 默认 match_ids.txt
        league_name: 按联赛获取
        round_num: 指定轮次

    Returns:
        保存的文件路径
    """
    if not output_path:
        if league_name:
            output_path = f"match_ids_{league_name}.txt"
        else:
            output_path = f"match_ids_{date or time.strftime('%Y-%m-%d')}.txt"

    if league_name:
        matches = get_match_ids_by_league(league_name, round_num)
    else:
        matches = get_match_ids_by_date(date)

    if not matches:
        print("[结果] 无比赛数据")
        return output_path

    with open(output_path, 'w', encoding='utf-8') as f:
        for m in matches:
            # 一行一个match_id, 方便其他脚本读取
            f.write(f"{m['match_id']}\n")

    print(f"[保存] {len(matches)} 个比赛ID -> {output_path}")
    return output_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.okooo.get_match_ids date 2025-05-25")
        print("  python -m fetchers.okooo.get_match_ids league 英超")
        print("  python -m fetchers.okooo.get_match_ids league 英超 38")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "date":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        matches = get_match_ids_by_date(date_str)
        for m in matches:
            score = f" {m['home_score']}-{m['away_score']}" if m['home_score'] is not None else ""
            print(f"  {m['match_id']}: {m['home_team']} vs {m['away_team']}{score}")

    elif cmd == "league":
        league = sys.argv[2] if len(sys.argv) > 2 else "英超"
        rnd = int(sys.argv[3]) if len(sys.argv) > 3 else None
        matches = get_match_ids_by_league(league, rnd)
        for m in matches:
            score = f" {m['home_score']}-{m['away_score']}" if m['home_score'] is not None else ""
            print(f"  {m['match_id']}: {m['home_team']} vs {m['away_team']}{score}")
