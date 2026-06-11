"""
使用免费足球API获取实时赛果
"""
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

DATA_DIR = 'd:/football_tools/data'
NO_PROXY = {'http': None, 'https': None}

# 联赛配置
LEAGUES = {
    'premier_league': {
        'name': '英超',
        'file': 'england/premier_league_2025-2026.csv',
        'teams': ['Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
                  'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Liverpool',
                  'Manchester City', 'Manchester United', 'Newcastle United', 'Nottingham Forest',
                  'Tottenham', 'West Ham United', 'Wolverhampton', 'Burnley', 'Leeds United',
                  'Leicester City', 'Southampton', 'Sunderland'],
    },
    'bundesliga': {
        'name': '德甲',
        'file': 'germany/bundesliga_2025-2026.csv',
        'teams': ['Bayern Munich', 'Borussia Dortmund', 'RB Leipzig', 'Bayer Leverkusen',
                  'Wolfsburg', 'Freiburg', 'Eintracht Frankfurt', 'Mainz', 'Borussia M\'gladbach',
                  'Hoffenheim', 'Werder Bremen', 'Augsburg', 'Stuttgart', 'Bochum',
                  'Heidenheim', 'Holstein Kiel', 'Union Berlin', 'Hamburg', 'FC Koln'],
    },
    'la_liga': {
        'name': '西甲',
        'file': 'spain/la_liga_2025-2026.csv',
        'teams': ['Real Madrid', 'Barcelona', 'Atletico Madrid', 'Sevilla', 'Real Sociedad',
                  'Villarreal', 'Athletic Bilbao', 'Real Betis', 'Valencia', 'Getafe',
                  'Osasuna', 'Celta Vigo', 'Rayo Vallecano', 'Girona', 'Mallorca',
                  'Las Palmas', 'Alaves', 'Espanyol', 'Leganes', 'Valladolid'],
    },
    'serie_a': {
        'name': '意甲',
        'file': 'italy/serie_a_2025-2026.csv',
        'teams': ['Inter', 'AC Milan', 'Juventus', 'Napoli', 'Roma', 'Lazio',
                  'Atalanta', 'Fiorentina', 'Bologna', 'Torino', 'Monza', 'Udinese',
                  'Sassuolo', 'Empoli', 'Lecce', 'Genoa', 'Cagliari', 'Parma', 'Como', 'Hellas Verona', 'Venezia'],
    },
    'ligue_1': {
        'name': '法甲',
        'file': 'france/ligue_1_2025-2026.csv',
        'teams': ['Paris Saint-Germain', 'Marseille', 'Lyon', 'Monaco', 'Lille',
                  'Nice', 'Lens', 'Rennes', 'Strasbourg', 'Nantes', 'Montpellier',
                  'Toulouse', 'Brest', 'Reims', 'Le Havre', 'Angers', 'Auxerre', 'Saint-Etienne'],
    },
}


def get_thesportsdb_matches(date_str):
    """从TheSportsDB获取比赛数据"""
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={date_str}&s=Soccer"

    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY

        response = session.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            matches = []

            for event in events:
                if event:
                    home_team = event.get('homeTeam', '')
                    away_team = event.get('awayTeam', '')

                    # 获取比分
                    home_score = event.get('homeScore')
                    away_score = event.get('awayScore')

                    if home_team and away_team and home_score is not None and away_score is not None:
                        matches.append({
                            'home_team': home_team,
                            'away_team': away_team,
                            'home_goals': int(home_score),
                            'away_goals': int(away_score),
                            'league': event.get('league', ''),
                        })

            return matches
    except Exception as e:
        print(f"    TheSportsDB请求失败: {e}")

    return []


def get_scorebat_matches():
    """从ScoreBat获取比赛数据"""
    url = "https://www.scorebat.com/video-api/v3/"

    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY

        response = session.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            matches = []

            for item in data.get('response', []):
                title = item.get('title', '')
                competition = item.get('competition', '')

                # 解析标题中的比分 "Team1 2-1 Team2"
                import re
                match = re.search(r'(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)', title)
                if match:
                    home = match.group(1).strip()
                    away = match.group(4).strip()
                    hg = int(match.group(2))
                    ag = int(match.group(3))

                    matches.append({
                        'home_team': home,
                        'away_team': away,
                        'home_goals': hg,
                        'away_goals': ag,
                        'league': competition,
                    })

            return matches
    except Exception as e:
        print(f"    ScoreBat请求失败: {e}")

    return []


def normalize_team_name(name):
    """标准化球队名称"""
    name = name.strip()

    mappings = {
        'Man City': 'Manchester City',
        'Man Utd': 'Manchester United',
        'Man United': 'Manchester United',
        'Newcastle': 'Newcastle United',
        'West Ham': 'West Ham United',
        'Wolves': 'Wolverhampton',
        'Spurs': 'Tottenham',
        'Bayern': 'Bayern Munich',
        'Dortmund': 'Borussia Dortmund',
        'Leverkusen': 'Bayer Leverkusen',
        'Inter Milan': 'Inter',
        'AC Milan': 'Milan',
        'PSG': 'Paris Saint-Germain',
    }

    return mappings.get(name, name)


def filter_league_matches(matches, league_teams):
    """过滤联赛比赛"""
    filtered = []
    for m in matches:
        home = normalize_team_name(m['home_team'])
        away = normalize_team_name(m['away_team'])

        home_in_league = any(t.lower() in home.lower() or home.lower() in t.lower() for t in league_teams)
        away_in_league = any(t.lower() in away.lower() or away.lower() in t.lower() for t in league_teams)

        if home_in_league and away_in_league:
            m['home_team'] = home
            m['away_team'] = away
            filtered.append(m)

    return filtered


def update_league_csv(league_key, config, all_matches):
    """更新联赛CSV"""
    csv_path = os.path.join(DATA_DIR, '01_leagues', config['file'])

    if not os.path.exists(csv_path):
        print(f"  文件不存在: {csv_path}")
        return 0

    # 过滤该联赛的比赛
    league_matches = filter_league_matches(all_matches, config['teams'])

    if not league_matches:
        return 0

    # 读取现有数据
    df = pd.read_csv(csv_path, encoding='utf-8')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    latest_date = df['Date'].max().date()
    today = datetime.now().date()

    # 检查已存在的比赛
    existing = set()
    for _, row in df.iterrows():
        if pd.notna(row['Date']) and pd.notna(row['HomeTeam']):
            key = (str(row['HomeTeam']), str(row['AwayTeam']))
            existing.add(key)

    # 添加新比赛
    added = 0
    for m in league_matches:
        key = (m['home_team'], m['away_team'])

        if key not in existing:
            # 分配日期（从最新日期之后开始）
            days_offset = added + 1
            match_date = latest_date + timedelta(days=days_offset)

            if match_date > today:
                match_date = today

            date_str = match_date.strftime('%Y-%m-%d')

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

    if added > 0:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.sort_values('Date')
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"  新增 {added} 条记录")

    return added


def main():
    print("=" * 60)
    print(f"足球API实时赛果获取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_matches = []

    # 获取最近几天的比赛
    today = datetime.now()
    for i in range(7):
        check_date = today - timedelta(days=i)
        date_str = check_date.strftime('%Y%m%d')
        print(f"\n获取 {check_date.strftime('%Y-%m-%d')} 的比赛...")
        matches = get_thesportsdb_matches(date_str)
        if matches:
            print(f"  TheSportsDB: {len(matches)} 场")
            all_matches.extend(matches)
        time.sleep(0.5)

    # 获取ScoreBat数据
    print("\n获取 ScoreBat 数据...")
    matches = get_scorebat_matches()
    if matches:
        print(f"  ScoreBat: {len(matches)} 场")
        all_matches.extend(matches)

    # 去重
    seen = set()
    unique_matches = []
    for m in all_matches:
        key = (m['home_team'], m['away_team'], m['home_goals'], m['away_goals'])
        if key not in seen:
            seen.add(key)
            unique_matches.append(m)

    print(f"\n总共获取到 {len(unique_matches)} 场不重复比赛")

    # 更新各联赛CSV
    total_added = 0
    for league_key, config in LEAGUES.items():
        print(f"\n更新 {config['name']}...")
        added = update_league_csv(league_key, config, unique_matches)
        total_added += added

    print("\n" + "=" * 60)
    print(f"完成! 共新增 {total_added} 条记录")


if __name__ == '__main__':
    main()