"""
采集芬超(Veikkausliiga)完整数据

使用FBref免费数据获取:
1. 球队详细信息(球场、国家等)
2. 比赛统计数据(射门、角球、犯规等)
3. 当前赛季积分榜
4. 球员信息
"""

import requests
import sqlite3
import time
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

# 配置
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'football_v2.db')

# FBref配置
FBREF_URL = "https://fbref.com/en/comps/47/Veikkausliiga-Stats"

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_with_retry(url, max_retries=3):
    """带重试的请求"""
    session = requests.Session()
    session.trust_env = False

    for attempt in range(max_retries):
        try:
            response = session.get(url, headers=HEADERS, timeout=30, proxies={'http': None, 'https': None})
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                wait_time = 60 + 30
                print(f"    被限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                print(f"    HTTP {response.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"    请求错误: {e}")
            time.sleep(10)

    return None

def collect_teams_info():
    """采集球队详细信息 - 从FBref获取"""
    print("\n=== 采集芬超球队信息 ===")

    conn = get_db()
    cursor = conn.cursor()

    # 获取FBref页面
    print("从FBref获取芬超数据...")
    response = get_with_retry(FBREF_URL)

    if not response:
        print("无法获取FBref页面")
        conn.close()
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # 解析积分榜表格获取球队信息
    standings_table = soup.find('table', {'id': re.compile('results')})

    if standings_table:
        rows = standings_table.find_all('tr')
        print(f"找到 {len(rows)} 行数据")

        updated = 0
        for row in rows[1:]:  # 跳过表头
            cols = row.find_all('td')
            if len(cols) >= 2:
                # 球队名
                team_cell = cols[0] if cols else None
                if team_cell:
                    team_link = team_cell.find('a')
                    if team_link:
                        team_name = team_link.get_text(strip=True)
                        team_url = team_link.get('href', '')

                        # 查找数据库中的team_id
                        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (team_name,))
                        team_row = cursor.fetchone()
                        team_id = team_row['team_id'] if team_row else None

                        if team_id:
                            # 获取球队详情页面
                            if team_url:
                                full_url = f"https://fbref.com{team_url}"
                                team_response = get_with_retry(full_url)

                                if team_response:
                                    team_soup = BeautifulSoup(team_response.text, 'html.parser')

                                    # 尝试获取球场信息
                                    info_div = team_soup.find('div', {'id': 'info'})
                                    if info_div:
                                        # 查找球场
                                        stadium_text = None
                                        for p in info_div.find_all('p'):
                                            text = p.get_text()
                                            if 'Stadium' in text or 'Venue' in text:
                                                stadium_match = re.search(r'Stadium:\s*(.+)', text)
                                                if stadium_match:
                                                    stadium_text = stadium_match.group(1).strip()
                                                break

                                        if stadium_text:
                                            cursor.execute("""
                                                UPDATE teams SET
                                                    stadium = ?,
                                                    country = 'Finland',
                                                    country_cn = '芬兰'
                                                WHERE team_id = ?
                                            """, (stadium_text, team_id))
                                            updated += 1
                                            print(f"  更新: {team_name} -> stadium={stadium_text}")

                                    time.sleep(3)  # 避免爬虫过快

        conn.commit()
        print(f"共更新 {updated} 个球队信息")
    else:
        print("未找到积分榜表格")

    conn.close()

def collect_match_stats():
    """采集比赛统计数据(射门、角球等) - 从FBref获取"""
    print("\n=== 采集芬超比赛统计数据 ===")

    conn = get_db()
    cursor = conn.cursor()

    # 获取FBref赛程页面
    # 获取最新赛季的比赛统计
    seasons_to_fetch = [2025, 2024, 2023]

    for season in seasons_to_fetch:
        print(f"\n获取 {season} 赛季数据...")
        season_url = f"{FBREF_URL}?season={season}"
        response = get_with_retry(season_url)

        if not response:
            print(f"  无法获取 {season} 赛季页面")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找比赛表格
        match_table = soup.find('table', {'id': re.compile('schedule|match')})

        if not match_table:
            # 尝试查找比分表格
            match_table = soup.find('table')

        if match_table:
            rows = match_table.find_all('tr')
            print(f"  找到 {len(rows)} 行")

            matches_updated = 0
            for row in rows[1:]:
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 10:
                    try:
                        # 提取日期
                        date_cell = cols[0]
                        date_text = date_cell.get_text(strip=True) if date_cell else ''

                        # 提取球队名
                        home_cell = cols[3] if len(cols) > 3 else None
                        away_cell = cols[7] if len(cols) > 7 else None

                        home_team = home_cell.get_text(strip=True) if home_cell else ''
                        away_team = away_cell.get_text(strip=True) if away_cell else ''

                        # 提取比分
                        score_cell = cols[5] if len(cols) > 5 else None
                        score_text = score_cell.get_text(strip=True) if score_cell else ''

                        # 解析比分 (格式: "2-1" 或 "2–1")
                        home_goals, away_goals = None, None
                        if score_text:
                            parts = re.split(r'[-–]', score_text)
                            if len(parts) == 2:
                                try:
                                    home_goals = int(parts[0].strip())
                                    away_goals = int(parts[1].strip())
                                except:
                                    pass

                        # 提取射门等统计 (如果有的话)
                        # FBref的比赛表格可能包含射门、控球等数据

                        # 查找数据库中的team_id
                        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (home_team,))
                        home_row = cursor.fetchone()
                        home_team_id = home_row['team_id'] if home_row else None

                        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (away_team,))
                        away_row = cursor.fetchone()
                        away_team_id = away_row['team_id'] if away_row else None

                        # 转换日期格式
                        match_date = None
                        if date_text:
                            try:
                                # FBref日期格式通常是 "2024-04-06" 或 "Sat Apr 6"
                                if '-' in date_text:
                                    match_date = date_text
                                else:
                                    # 解析 "Sat Apr 6" 格式
                                    from datetime import datetime
                                    dt = datetime.strptime(f"{date_text} {season}", "%a %b %d %Y")
                                    match_date = dt.strftime("%Y-%m-%d")
                            except:
                                pass

                        if home_team_id and away_team_id and match_date:
                            # 更新比赛数据
                            cursor.execute("""
                                UPDATE matches SET
                                    home_goals = COALESCE(home_goals, ?),
                                    away_goals = COALESCE(away_goals, ?)
                                WHERE league_id = 39
                                AND match_date = ?
                                AND home_team_id = ?
                                AND away_team_id = ?
                            """, (home_goals, away_goals, match_date, home_team_id, away_team_id))

                            if cursor.rowcount > 0:
                                matches_updated += 1

                    except Exception as e:
                        continue

            conn.commit()
            print(f"  更新了 {matches_updated} 场比赛")

        time.sleep(3)

    conn.close()

def collect_standings():
    """采集积分榜 - 从FBref获取"""
    print("\n=== 采集芬超积分榜 ===")

    conn = get_db()
    cursor = conn.cursor()

    seasons = [2025, 2024]

    for season in seasons:
        print(f"\n获取 {season} 赛季积分榜...")
        season_url = f"{FBREF_URL}?season={season}"
        response = get_with_retry(season_url)

        if not response:
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找积分榜表格
        standings_table = soup.find('table', {'id': re.compile('results')})

        if standings_table:
            rows = standings_table.find_all('tr')
            print(f"  找到 {len(rows)} 行")

            standings_data = []
            for row in rows[1:]:
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 10:
                    try:
                        rank = cols[0].get_text(strip=True) if cols[0] else ''
                        team_cell = cols[1] if len(cols) > 1 else None
                        team_name = team_cell.get_text(strip=True) if team_cell else ''

                        # 解析积分榜数据
                        mp = cols[2].get_text(strip=True) if len(cols) > 2 else '0'
                        w = cols[3].get_text(strip=True) if len(cols) > 3 else '0'
                        d = cols[4].get_text(strip=True) if len(cols) > 4 else '0'
                        l = cols[5].get_text(strip=True) if len(cols) > 5 else '0'
                        gf = cols[6].get_text(strip=True) if len(cols) > 6 else '0'
                        ga = cols[7].get_text(strip=True) if len(cols) > 7 else '0'
                        gd = cols[8].get_text(strip=True) if len(cols) > 8 else '0'
                        pts = cols[9].get_text(strip=True) if len(cols) > 9 else '0'

                        if team_name and rank.isdigit():
                            standings_data.append({
                                'rank': int(rank),
                                'team': team_name,
                                'played': int(mp) if mp.isdigit() else 0,
                                'wins': int(w) if w.isdigit() else 0,
                                'draws': int(d) if d.isdigit() else 0,
                                'losses': int(l) if l.isdigit() else 0,
                                'gf': int(gf) if gf.isdigit() else 0,
                                'ga': int(ga) if ga.isdigit() else 0,
                                'gd': int(gd) if lstrip('-').isdigit() else 0,
                                'points': int(pts) if pts.isdigit() else 0,
                            })
                            print(f"    #{rank}: {team_name} - {pts}分 ({w}胜{d}平{l}负)")
                    except Exception as e:
                        continue

            print(f"  解析了 {len(standings_data)} 个球队积分榜数据")

        time.sleep(3)

    conn.close()

def collect_fixtures():
    """采集最新赛程 - 从FBref获取"""
    print("\n=== 采集芬超最新赛程 ===")

    conn = get_db()
    cursor = conn.cursor()

    seasons = [2025, 2026]

    for season in seasons:
        print(f"\n获取 {season} 赛季赛程...")
        season_url = f"{FBREF_URL}?season={season}"
        response = get_with_retry(season_url)

        if not response:
            print(f"  无法获取 {season} 赛季页面")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找赛程表格
        match_table = soup.find('table', {'id': re.compile('sched')})

        if not match_table:
            match_table = soup.find('table')

        if match_table:
            rows = match_table.find_all('tr')
            print(f"  找到 {len(rows)} 行赛程数据")

            new_matches = 0
            for row in rows[1:]:
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 8:
                    try:
                        # 日期
                        date_text = cols[0].get_text(strip=True) if cols[0] else ''
                        match_date = None
                        if date_text and '-' in date_text:
                            match_date = date_text[:10]

                        # 时间
                        time_cell = cols[1] if len(cols) > 1 else None
                        match_time = time_cell.get_text(strip=True) if time_cell else ''

                        # 球队
                        home_cell = cols[3] if len(cols) > 3 else None
                        away_cell = cols[7] if len(cols) > 7 else None

                        home_name = home_cell.get_text(strip=True) if home_cell else ''
                        away_name = away_cell.get_text(strip=True) if away_cell else ''

                        # 查找数据库中的team_id
                        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (home_name,))
                        home_row = cursor.fetchone()
                        home_team_id = home_row['team_id'] if home_row else None

                        cursor.execute("SELECT team_id FROM teams WHERE name_en = ?", (away_name,))
                        away_row = cursor.fetchone()
                        away_team_id = away_row['team_id'] if away_row else None

                        if home_team_id and away_team_id and match_date:
                            # 检查是否已存在
                            cursor.execute("""
                                SELECT match_id FROM matches
                                WHERE league_id = 39
                                AND match_date = ?
                                AND home_team_id = ?
                                AND away_team_id = ?
                            """, (match_date, home_team_id, away_team_id))

                            if not cursor.fetchone():
                                # 插入新比赛
                                match_id = f"veikkausliiga_{season}_{match_date}_{home_team_id}_vs_{away_team_id}"
                                cursor.execute("""
                                    INSERT INTO matches (
                                        match_id, league_id, season_id, match_date, match_time,
                                        home_team_id, away_team_id, status
                                    ) VALUES (?, 39, ?, ?, ?, ?, ?, ?, 'scheduled')
                                """, (
                                    match_id, season, match_date, match_time,
                                    home_team_id, away_team_id
                                ))
                                new_matches += 1
                                print(f"    新增: {match_date} {home_name} vs {away_name}")

                    except Exception as e:
                        continue

            conn.commit()
            print(f"  新增 {new_matches} 场比赛")

        time.sleep(3)

    conn.close()
    print("赛程采集完成")

def main():
    """主函数"""
    print("=" * 50)
    print("芬超(Veikkausliiga)数据采集")
    print("=" * 50)

    # 1. 采集球队信息
    collect_teams_info()

    # 2. 采集最新赛程
    collect_fixtures()

    # 3. 采集比赛统计
    collect_match_stats()

    # 4. 采集积分榜
    collect_standings()

    print("\n采集完成!")

if __name__ == "__main__":
    main()