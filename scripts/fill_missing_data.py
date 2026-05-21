"""
补齐缺失数据 - 优化版
使用Tavily API搜索比赛结果，优化解析逻辑
"""
import os
import re
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# API配置
TAVILY_API_KEY = "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"

DATA_DIR = 'd:/football_tools/data'
NO_PROXY = {'http': None, 'https': None}

# 英超球队列表（用于过滤）
PREMIER_LEAGUE_TEAMS = [
    'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
    'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Liverpool',
    'Manchester City', 'Manchester United', 'Newcastle', 'Newcastle United',
    'Nottingham Forest', 'Tottenham', 'West Ham', 'West Ham United',
    'Wolves', 'Wolverhampton', 'Burnley', 'Leeds', 'Leeds United',
    'Leicester', 'Leicester City', 'Southampton', 'Sunderland', 'Norwich'
]

# 德甲球队
BUNDESLIGA_TEAMS = [
    'Bayern Munich', 'Bayern', 'Dortmund', 'Borussia Dortmund', 'Leipzig',
    'RB Leipzig', 'Leverkusen', 'Bayer Leverkusen', 'Wolfsburg', 'Freiburg',
    'Frankfurt', 'Eintracht Frankfurt', 'Mainz', 'Borussia M\'gladbach',
    'Gladbach', 'Hoffenheim', 'Werder Bremen', 'Bremen', 'Augsburg',
    'Stuttgart', 'Bochum', 'Heidenheim', 'Holstein Kiel', 'Union Berlin'
]

# 西甲球队
LA_LIGA_TEAMS = [
    'Real Madrid', 'Barcelona', 'Atletico Madrid', 'Sevilla', 'Real Sociedad',
    'Villarreal', 'Athletic Bilbao', 'Athletic', 'Real Betis', 'Valencia',
    'Getafe', 'Osasuna', 'Celta Vigo', 'Rayo Vallecano', 'Girona',
    'Mallorca', 'Las Palmas', 'Alaves', 'Espanyol', 'Leganes', 'Valladolid'
]

# 意甲球队
SERIE_A_TEAMS = [
    'Inter', 'Inter Milan', 'AC Milan', 'Milan', 'Juventus', 'Napoli',
    'Roma', 'AS Roma', 'Lazio', 'Atalanta', 'Fiorentina', 'Bologna',
    'Torino', 'Monza', 'Udinese', 'Sassuolo', 'Empoli', 'Lecce',
    'Genoa', 'Cagliari', 'Parma', 'Como', 'Verona', 'Hellas Verona', 'Venezia'
]

# 法甲球队
LIGUE_1_TEAMS = [
    'PSG', 'Paris Saint-Germain', 'Marseille', 'Lyon', 'Monaco', 'Lille',
    'Nice', 'Lens', 'Rennes', 'Strasbourg', 'Nantes', 'Montpellier',
    'Toulouse', 'Brest', 'Reims', 'Le Havre', 'Nantes', 'Angers',
    'Auxerre', 'Saint-Etienne'
]

LEAGUES_CONFIG = {
    'premier_league': {
        'name': '英超',
        'file': 'england/premier_league_2025-2026.csv',
        'teams': PREMIER_LEAGUE_TEAMS,
        'search_names': ['Premier League', 'EPL'],
    },
    'bundesliga': {
        'name': '德甲',
        'file': 'germany/bundesliga_2025-2026.csv',
        'teams': BUNDESLIGA_TEAMS,
        'search_names': ['Bundesliga Germany'],
    },
    'la_liga': {
        'name': '西甲',
        'file': 'spain/la_liga_2025-2026.csv',
        'teams': LA_LIGA_TEAMS,
        'search_names': ['La Liga Spain'],
    },
    'serie_a': {
        'name': '意甲',
        'file': 'italy/serie_a_2025-2026.csv',
        'teams': SERIE_A_TEAMS,
        'search_names': ['Serie A Italy'],
    },
    'ligue_1': {
        'name': '法甲',
        'file': 'france/ligue_1_2025-2026.csv',
        'teams': LIGUE_1_TEAMS,
        'search_names': ['Ligue 1 France'],
    },
}


def search_tavily(query):
    """Tavily搜索"""
    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}"
    }
    data = {
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": 10
    }

    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY
        response = session.post(url, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"    请求失败: {e}")
    return None


def normalize_team_name(name):
    """标准化球队名称"""
    name = name.strip()

    # 移除HTML标签和多余文字
    name = re.sub(r'<[^>]+>', '', name)
    name = re.sub(r'\s*(badge|FT|Finished|View live|Match highlights|Scorers|Highlights|Complete list of matches|YouTube|video thumbnail|image|from|January|May|September).*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()

    # 清理常见后缀
    for suffix in [' FC', ' CF', ' AFC', ' SC', '  FC', '  CF']:
        name = name.replace(suffix, '')

    # 特殊映射
    mappings = {
        'Man City': 'Manchester City',
        'Man Utd': 'Manchester United',
        'Man United': 'Manchester United',
        'Newcastle': 'Newcastle United',
        'West Ham': 'West Ham United',
        'Wolves': 'Wolverhampton',
        'Brighton': 'Brighton',
        'Tottenham': 'Tottenham',
        'Spurs': 'Tottenham',
        'Bayern': 'Bayern Munich',
        'Bayern M': 'Bayern Munich',
        'Dortmund': 'Borussia Dortmund',
        'Leverkusen': 'Bayer Leverkusen',
        'Inter Milan': 'Inter',
        'AC Milan': 'Milan',
        'PSG': 'Paris Saint-Germain',
        'Paris': 'Paris Saint-Germain',
        'M\'gladbach': 'Borussia M\'gladbach',
        'Gladbach': 'Borussia M\'gladbach',
        'Bremen': 'Werder Bremen',
        'Hamburg': 'Hamburger SV',
        'Pauli': 'St. Pauli',
        'AFC Bournemouth': 'Bournemouth',
    }

    return mappings.get(name, name)


def parse_score_pattern(text):
    """解析比分模式"""
    results = []

    # 清理文本
    text = re.sub(r'<[^>]+>', ' ', text)  # 移除HTML标签
    text = re.sub(r'\s+', ' ', text)  # 合并空格

    # 模式1: "Team1 2-1 Team2" 或 "Team1 2 - 1 Team2"
    pattern1 = r'([A-Z][a-zA-Z\s\'\.\-]+?)\s+(\d+)\s*-\s*(\d+)\s+([A-Z][a-zA-Z\s\'\.\-]+)'
    matches = re.findall(pattern1, text)

    for m in matches:
        home = normalize_team_name(m[0].strip())
        away = normalize_team_name(m[3].strip())

        # 跳过无效的球队名
        if len(home) < 3 or len(away) < 3:
            continue
        if any(x in home.lower() for x in ['badge', 'ft', 'finished', 'view', 'match', 'video', 'image', 'youtube']):
            continue
        if any(x in away.lower() for x in ['badge', 'ft', 'finished', 'view', 'match', 'video', 'image', 'youtube']):
            continue

        try:
            hg = int(m[1])
            ag = int(m[2])
            if 0 <= hg <= 15 and 0 <= ag <= 15:  # 合理比分范围
                results.append({
                    'home_team': home,
                    'away_team': away,
                    'home_goals': hg,
                    'away_goals': ag,
                })
        except:
            continue

    return results


def filter_league_matches(matches, league_teams):
    """过滤出属于该联赛的比赛"""
    filtered = []
    for m in matches:
        home = m['home_team']
        away = m['away_team']

        # 检查是否是联赛球队
        home_in_league = any(t.lower() in home.lower() or home.lower() in t.lower() for t in league_teams)
        away_in_league = any(t.lower() in away.lower() or away.lower() in t.lower() for t in league_teams)

        if home_in_league and away_in_league:
            filtered.append(m)

    return filtered


def get_matches_for_league(league_name, league_teams, date_from, date_to):
    """获取联赛在日期范围内的比赛"""
    all_matches = []

    # 计算缺失的日期
    from datetime import datetime, timedelta
    date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
    date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
    missing_days = (date_to_dt - date_from_dt).days

    # 生成更多针对性查询
    queries = [
        f"{league_name} results {date_from} to {date_to}",
        f"{league_name} matches scores {date_from} {date_to}",
        f"{league_name} latest results May 2026",
        f"{league_name} scores today",
        f"{league_name} match results this week",
    ]

    # 针对每个缺失日期单独查询
    for i in range(missing_days + 1):
        check_date = date_from_dt + timedelta(days=i)
        date_str = check_date.strftime('%Y-%m-%d')
        queries.append(f"{league_name} results {date_str}")
        queries.append(f"{league_name} match {check_date.strftime('%B %d %Y')}")

    # 针对热门球队查询
    popular_teams = league_teams[:5]  # 取前5个热门球队
    for team in popular_teams:
        queries.append(f"{team} match result May 2026")
        queries.append(f"{team} latest score")

    for query in queries:
        print(f"    搜索: {query[:50]}...")
        result = search_tavily(query)

        if result:
            # 解析answer
            answer = result.get('answer', '')
            matches = parse_score_pattern(answer)
            all_matches.extend(matches)

            # 解析搜索结果
            for r in result.get('results', []):
                content = r.get('content', '')
                matches = parse_score_pattern(content)
                all_matches.extend(matches)

        time.sleep(0.5)  # 增加间隔避免限流

    # 过滤联赛比赛
    filtered = filter_league_matches(all_matches, league_teams)

    # 去重
    seen = set()
    unique = []
    for m in filtered:
        key = (m['home_team'], m['away_team'], m['home_goals'], m['away_goals'])
        if key not in seen:
            seen.add(key)
            unique.append(m)

    return unique


def update_league_csv(league_key, config):
    """更新联赛CSV"""
    csv_path = os.path.join(DATA_DIR, '01_leagues', config['file'])

    if not os.path.exists(csv_path):
        print(f"  文件不存在: {csv_path}")
        return 0

    # 读取现有数据
    df = pd.read_csv(csv_path, encoding='utf-8')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    latest_date = df['Date'].max().date()
    today = datetime.now().date()

    print(f"\n{'='*50}")
    print(f"{config['name']}:")
    print(f"  最新数据: {latest_date}")
    print(f"  当前日期: {today}")
    print(f"  缺失天数: {(today - latest_date).days} 天")

    if latest_date >= today:
        print("  数据已是最新")
        return 0

    # 获取缺失日期的比赛
    print(f"  正在获取缺失数据...")
    matches = get_matches_for_league(
        config['search_names'][0],
        config['teams'],
        latest_date.strftime('%Y-%m-%d'),
        today.strftime('%Y-%m-%d')
    )

    print(f"  找到 {len(matches)} 场比赛")

    if not matches:
        return 0

    # 检查已存在的比赛
    existing = set()
    for _, row in df.iterrows():
        if pd.notna(row['Date']) and pd.notna(row['HomeTeam']):
            key = (row['Date'].strftime('%Y-%m-%d'), str(row['HomeTeam']), str(row['AwayTeam']))
            existing.add(key)

    # 添加新比赛
    added = 0
    for m in matches:
        # 尝试多个日期
        for days_offset in range((today - latest_date).days + 1):
            match_date = latest_date + timedelta(days=days_offset)
            date_str = match_date.strftime('%Y-%m-%d')
            key = (date_str, m['home_team'], m['away_team'])

            if key not in existing:
                # 确定结果
                if m['home_goals'] > m['away_goals']:
                    ftr = 'H'
                elif m['home_goals'] < m['away_goals']:
                    ftr = 'A'
                else:
                    ftr = 'D'

                new_row = {
                    'Date': date_str,
                    'HomeTeam': m['home_team'],
                    'AwayTeam': m['away_team'],
                    'FTHG': m['home_goals'],
                    'FTAG': m['away_goals'],
                    'FTR': ftr,
                }

                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                existing.add(key)
                added += 1
                print(f"    + {m['home_team']} {m['home_goals']}-{m['away_goals']} {m['away_team']}")
                break

    if added > 0:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.sort_values('Date')
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"  新增 {added} 条记录")

    return added


def main():
    print("=" * 60)
    print(f"补齐缺失数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    total_added = 0

    for league_key, config in LEAGUES_CONFIG.items():
        added = update_league_csv(league_key, config)
        total_added += added

    print("\n" + "=" * 60)
    print(f"完成! 共新增 {total_added} 条记录")


if __name__ == '__main__':
    main()
