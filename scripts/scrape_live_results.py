"""
足球实时赛果爬虫
从多个足球数据网站爬取最新比赛结果
"""
import os
import re
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time

DATA_DIR = 'd:/football_tools/data'
NO_PROXY = {'http': None, 'https': None}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

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


def create_session():
    """创建请求会话"""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.trust_env = False
    session.proxies = NO_PROXY
    return session


def scrape_premier_league_official():
    """从英超官网爬取"""
    url = "https://www.premierleague.com/results"
    matches = []

    try:
        session = create_session()
        response = session.get(url, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 解析比赛数据
            match_items = soup.find_all('div', class_='matchFixtureContainer')
            for item in match_items[:20]:
                try:
                    home = item.find('span', class_='home').text.strip()
                    away = item.find('span', class_='away').text.strip()
                    score = item.find('span', class_='score').text.strip()
                    scores = score.split('-')
                    if len(scores) == 2:
                        matches.append({
                            'home_team': home,
                            'away_team': away,
                            'home_goals': int(scores[0].strip()),
                            'away_goals': int(scores[1].strip()),
                        })
                except:
                    continue
    except Exception as e:
        print(f"英超官网爬取失败: {e}")

    return matches


def scrape_espn_scores():
    """从ESPN爬取足球比分"""
    url = "https://www.espn.com/soccer/scoreboard"
    matches = []

    try:
        session = create_session()
        response = session.get(url, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找比赛元素
            game_containers = soup.find_all('div', class_='game-score-container')
            for container in game_containers[:30]:
                try:
                    teams = container.find_all('span', class_='team-name')
                    if len(teams) >= 2:
                        home = teams[0].text.strip()
                        away = teams[1].text.strip()

                        scores = container.find_all('span', class_='score')
                        if len(scores) >= 2:
                            hg = int(scores[0].text.strip())
                            ag = int(scores[1].text.strip())

                            matches.append({
                                'home_team': home,
                                'away_team': away,
                                'home_goals': hg,
                                'away_goals': ag,
                            })
                except:
                    continue
    except Exception as e:
        print(f"ESPN爬取失败: {e}")

    return matches


def scrape_flashscores():
    """从FlashScores爬取"""
    url = "https://www.flashscore.com/"
    matches = []

    try:
        session = create_session()
        response = session.get(url, timeout=30)
        if response.status_code == 200:
            # FlashScores使用JavaScript渲染，这里只获取基本信息
            soup = BeautifulSoup(response.text, 'html.parser')
            # 查找比赛数据
            match_rows = soup.find_all('div', class_='event__match')
            for row in match_rows[:30]:
                try:
                    home = row.find('div', class_='event__participant--home').text.strip()
                    away = row.find('div', class_='event__participant--away').text.strip()
                    score_home = row.find('div', class_='event__score--home').text.strip()
                    score_away = row.find('div', class_='event__score--away').text.strip()

                    if score_home.isdigit() and score_away.isdigit():
                        matches.append({
                            'home_team': home,
                            'away_team': away,
                            'home_goals': int(score_home),
                            'away_goals': int(score_away),
                        })
                except:
                    continue
    except Exception as e:
        print(f"FlashScores爬取失败: {e}")

    return matches


def scrape_soccerway():
    """从Soccerway爬取"""
    matches = []

    # Soccerway的联赛页面
    urls = [
        ("https://int.soccerway.com/national/england/premier-league/", '英超'),
        ("https://int.soccerway.com/national/germany/bundesliga/", '德甲'),
        ("https://int.soccerway.com/national/spain/primera-division/", '西甲'),
        ("https://int.soccerway.com/national/italy/serie-a/", '意甲'),
        ("https://int.soccerway.com/national/france/ligue-1/", '法甲'),
    ]

    session = create_session()

    for url, league in urls:
        try:
            print(f"  爬取 {league}...")
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找最近的比赛
                match_rows = soup.find_all('tr', class_='match')
                for row in match_rows[:15]:
                    try:
                        # 解析球队
                        teams = row.find_all('td', class_='team')
                        if len(teams) >= 2:
                            home = teams[0].text.strip()
                            away = teams[1].text.strip()

                            # 解析比分
                            score_td = row.find('td', class_='score')
                            if score_td:
                                score_text = score_td.text.strip()
                                scores = re.findall(r'(\d+)\s*-\s*(\d+)', score_text)
                                if scores:
                                    hg, ag = int(scores[0][0]), int(scores[0][1])
                                    matches.append({
                                        'home_team': home,
                                        'away_team': away,
                                        'home_goals': hg,
                                        'away_goals': ag,
                                        'league': league,
                                    })
                    except:
                        continue

            time.sleep(1)
        except Exception as e:
            print(f"    {league}爬取失败: {e}")

    return matches


def normalize_team_name(name):
    """标准化球队名称"""
    name = name.strip()

    # 清理常见后缀
    for suffix in [' FC', ' CF', ' AFC', ' SC']:
        name = name.replace(suffix, '')

    # 特殊映射
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
            key = (row['Date'].strftime('%Y-%m-%d'), str(row['HomeTeam']), str(row['AwayTeam']))
            existing.add(key)

    # 添加新比赛
    added = 0
    for m in league_matches:
        # 尝试多个日期
        for days_offset in range((today - latest_date).days + 1):
            match_date = latest_date + timedelta(days=days_offset + 1)
            date_str = match_date.strftime('%Y-%m-%d')
            key = (date_str, m['home_team'], m['away_team'])

            if key not in existing and match_date <= today:
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
    print(f"足球实时赛果爬虫 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 从多个数据源爬取
    all_matches = []

    print("\n1. 尝试 Soccerway...")
    matches = scrape_soccerway()
    if matches:
        print(f"  获取到 {len(matches)} 场比赛")
        all_matches.extend(matches)

    print("\n2. 尝试 ESPN...")
    matches = scrape_espn_scores()
    if matches:
        print(f"  获取到 {len(matches)} 场比赛")
        all_matches.extend(matches)

    print("\n3. 尝试英超官网...")
    matches = scrape_premier_league_official()
    if matches:
        print(f"  获取到 {len(matches)} 场比赛")
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
