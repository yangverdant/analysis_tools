"""
足球数据爬虫 - 从足球数据网站爬取最新赛果
使用Selenium处理JavaScript渲染的页面
"""
import os
import re
import pandas as pd
from datetime import datetime, timedelta
import time

# 尝试导入selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("警告: Selenium未安装，尝试使用requests")

import requests
from bs4 import BeautifulSoup

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


def create_chrome_driver():
    """创建Chrome浏览器驱动"""
    if not SELENIUM_AVAILABLE:
        return None

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US')

    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        print(f"Chrome驱动创建失败: {e}")
        return None


def scrape_777score_with_selenium():
    """使用Selenium爬取777score"""
    matches = []
    driver = None

    try:
        driver = create_chrome_driver()
        if not driver:
            return matches

        url = "https://777score.com/"
        print(f"  访问: {url}")
        driver.get(url)

        # 等待页面加载
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'match-row')))

        # 获取比赛元素
        match_rows = driver.find_elements(By.CLASS_NAME, 'match-row')

        for row in match_rows[:50]:
            try:
                teams = row.find_elements(By.CLASS_NAME, 'team-name')
                if len(teams) >= 2:
                    home = teams[0].text.strip()
                    away = teams[1].text.strip()

                    score_elem = row.find_element(By.CLASS_NAME, 'score')
                    score_text = score_elem.text.strip()

                    # 解析比分
                    scores = re.findall(r'(\d+)\s*-\s*(\d+)', score_text)
                    if scores:
                        hg, ag = int(scores[0][0]), int(scores[0][1])
                        matches.append({
                            'home_team': home,
                            'away_team': away,
                            'home_goals': hg,
                            'away_goals': ag,
                        })
            except:
                continue

    except Exception as e:
        print(f"  爬取失败: {e}")
    finally:
        if driver:
            driver.quit()

    return matches


def scrape_livescores_with_selenium():
    """使用Selenium爬取livescores"""
    matches = []
    driver = None

    try:
        driver = create_chrome_driver()
        if not driver:
            return matches

        url = "https://www.livescores.com/soccer/england/premier-league/"
        print(f"  访问: {url}")
        driver.get(url)

        time.sleep(3)  # 等待页面加载

        # 查找比赛元素
        match_containers = driver.find_elements(By.CSS_SELECTOR, '.match-row, .match')

        for container in match_containers[:30]:
            try:
                # 尝试不同的选择器
                teams = container.find_elements(By.CSS_SELECTOR, '.team-name, .name')
                if len(teams) >= 2:
                    home = teams[0].text.strip()
                    away = teams[1].text.strip()

                    score = container.find_element(By.CSS_SELECTOR, '.score, .scores')
                    score_text = score.text.strip()

                    scores = re.findall(r'(\d+)\s*-\s*(\d+)', score_text)
                    if scores:
                        hg, ag = int(scores[0][0]), int(scores[0][1])
                        matches.append({
                            'home_team': home,
                            'away_team': away,
                            'home_goals': hg,
                            'away_goals': ag,
                        })
            except:
                continue

    except Exception as e:
        print(f"  爬取失败: {e}")
    finally:
        if driver:
            driver.quit()

    return matches


def scrape_with_requests():
    """使用requests爬取（备用方案）"""
    matches = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    session = requests.Session()
    session.headers.update(headers)
    session.trust_env = False
    session.proxies = NO_PROXY

    # 尝试从football-data.co.uk获取最新数据
    print("  尝试 football-data.co.uk...")

    # 当前赛季
    now = datetime.now()
    year = now.year if now.month >= 8 else now.year - 1
    season = f"{str(year)[2:]}{str(year+1)[2:]}"

    league_files = {
        'E0': 'premier_league',
        'D1': 'bundesliga',
        'SP1': 'la_liga',
        'I1': 'serie_a',
        'F1': 'ligue_1',
    }

    for code, league_name in league_files.items():
        url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                from io import StringIO
                df = pd.read_csv(StringIO(response.text), encoding='utf-8', on_bad_lines='skip')

                # 获取最近的比赛
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
                    df = df.dropna(subset=['Date'])

                    # 只取最近30天的比赛
                    recent = df[df['Date'] >= datetime.now() - timedelta(days=30)]

                    for _, row in recent.iterrows():
                        home = row.get('HomeTeam', '')
                        away = row.get('AwayTeam', '')
                        hg = row.get('FTHG')
                        ag = row.get('FTAG')

                        if pd.notna(home) and pd.notna(away) and pd.notna(hg) and pd.notna(ag):
                            matches.append({
                                'home_team': home,
                                'away_team': away,
                                'home_goals': int(hg),
                                'away_goals': int(ag),
                                'league': league_name,
                            })

                    print(f"    {league_name}: 获取到 {len(recent)} 场比赛")
        except Exception as e:
            print(f"    {league_name}: 获取失败 - {e}")

    return matches


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

    # 检查已存在的比赛
    existing = set()
    for _, row in df.iterrows():
        if pd.notna(row['Date']) and pd.notna(row['HomeTeam']):
            key = (str(row['HomeTeam']), str(row['AwayTeam']))
            existing.add(key)

    # 添加新比赛
    added = 0
    today = datetime.now().date()

    for m in league_matches:
        key = (m['home_team'], m['away_team'])

        if key not in existing:
            # 分配日期
            date_str = today.strftime('%Y-%m-%d')

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
    print(f"足球数据爬虫 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_matches = []

    # 方案1: 使用Selenium爬取
    if SELENIUM_AVAILABLE:
        print("\n1. 使用Selenium爬取777score...")
        matches = scrape_777score_with_selenium()
        if matches:
            print(f"  获取到 {len(matches)} 场比赛")
            all_matches.extend(matches)

        print("\n2. 使用Selenium爬取livescores...")
        matches = scrape_livescores_with_selenium()
        if matches:
            print(f"  获取到 {len(matches)} 场比赛")
            all_matches.extend(matches)

    # 方案2: 使用requests爬取football-data.co.uk
    print("\n3. 使用requests爬取football-data.co.uk...")
    matches = scrape_with_requests()
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