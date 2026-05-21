"""
从FBref采集国家队赛事球员数据
包括：美洲杯、非洲杯、亚洲杯、金杯赛
"""
import requests
import pandas as pd
import os
from datetime import datetime
import time
import re
from io import StringIO

# 数据保存目录
DATA_DIR = 'd:/football_tools/data/players'
os.makedirs(DATA_DIR, exist_ok=True)

# 禁用代理
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

def get_session():
    """创建请求会话"""
    session = requests.Session()
    session.trust_env = False
    session.proxies = {}
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    return session

# 标准字段定义
PLAYER_COLUMNS = [
    'league', 'season', 'team', 'player', 'nation', 'pos', 'age', 'Club', 'born',
    'MP', 'Starts', 'Min', '90s',
    'Gls', 'Ast', 'G+A', 'G-PK', 'PK', 'PKatt', 'CrdY', 'CrdR',
    'Gls_per90', 'Ast_per90', 'G+A_per90', 'G-PK_per90', 'G+A-PK_per90'
]

# 各赛事配置 - FBref的comp_id
TOURNAMENTS = {
    'copa_america': {
        'name': 'Copa America',
        'name_cn': '美洲杯',
        'league_code': 'INT-Copa America',
        'comp_id': '685',
        'years': [2001, 2004, 2007, 2011, 2015, 2016, 2019, 2021, 2024],
    },
    'africa_cup': {
        'name': 'Africa Cup of Nations',
        'name_cn': '非洲杯',
        'league_code': 'INT-Africa Cup of Nations',
        'comp_id': '686',
        'years': [2002, 2004, 2006, 2008, 2010, 2012, 2013, 2015, 2017, 2019, 2021, 2023],
    },
    'asian_cup': {
        'name': 'Asian Cup',
        'name_cn': '亚洲杯',
        'league_code': 'INT-Asian Cup',
        'comp_id': '682',
        'years': [2000, 2004, 2007, 2011, 2015, 2019, 2023],
    },
    'gold_cup': {
        'name': 'Gold Cup',
        'name_cn': '金杯赛',
        'league_code': 'INT-Gold Cup',
        'comp_id': '688',
        'years': [2002, 2003, 2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023],
    }
}

def get_tournament_seasons(session, comp_id):
    """获取赛事的所有赛季链接"""
    url = f"https://fbref.com/en/comps/{comp_id}/history/"
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  获取赛季列表失败: {e}")
        return None

def parse_player_stats_table(html_content, league_code, season):
    """解析FBref的球员统计表格"""
    players = []

    # 查找所有球队统计表格
    # FBref使用table标签和特定的id
    team_pattern = r'<table[^>]*id="stats_[^"]*"[^>]*>'
    tables = re.findall(team_pattern, html_content)

    # 更通用的表格查找
    table_pattern = r'<table[^>]*class="[^"]*stats_table[^"]*"[^>]*>(.*?)</table>'
    table_matches = re.findall(table_pattern, html_content, re.DOTALL)

    for table_html in table_matches:
        try:
            # 提取球队名称
            team_match = re.search(r'<caption[^>]*>.*?([A-Za-z\s]+) Stats', table_html, re.DOTALL)
            if not team_match:
                continue
            team_name = team_match.group(1).strip()

            # 解析表格行
            row_pattern = r'<tr[^>]*>(.*?)</tr>'
            rows = re.findall(row_pattern, table_html, re.DOTALL)

            for row in rows:
                # 跳过表头
                if '<th' in row and 'data-stat' in row:
                    continue

                # 提取数据
                cells = re.findall(r'<td[^>]*data-stat="([^"]*)"[^>]*>(.*?)</td>', row)
                if not cells:
                    continue

                player_data = {}
                for stat_name, cell_content in cells:
                    # 清理HTML标签
                    clean_text = re.sub(r'<[^>]+>', '', cell_content).strip()
                    player_data[stat_name] = clean_text

                if 'player' in player_data and player_data['player']:
                    players.append({
                        'league': league_code,
                        'season': season,
                        'team': team_name,
                        'player': player_data.get('player', ''),
                        'nation': player_data.get('nationality', team_name),
                        'pos': player_data.get('position', ''),
                        'age': player_data.get('age', ''),
                        'Club': player_data.get('squad', ''),
                        'born': player_data.get('birth_year', ''),
                        'MP': player_data.get('games', '0'),
                        'Starts': player_data.get('games_starts', '0'),
                        'Min': player_data.get('minutes', '0'),
                        'Gls': player_data.get('goals', '0'),
                        'Ast': player_data.get('assists', '0'),
                        'G+A': player_data.get('goals_assists', '0'),
                        'G-PK': player_data.get('goals_pens', '0'),
                        'PK': player_data.get('pens_made', '0'),
                        'PKatt': player_data.get('pens_att', '0'),
                        'CrdY': player_data.get('cards_yellow', '0'),
                        'CrdR': player_data.get('cards_red', '0'),
                    })
        except Exception as e:
            continue

    return players

def fetch_tournament_data(session, tournament_key, year):
    """获取特定赛事年份的球员数据"""
    tournament = TOURNAMENTS[tournament_key]
    comp_id = tournament['comp_id']
    league_code = tournament['league_code']

    # FBref URL格式: /en/comps/{comp_id}/{season_id}/{season_name}-Stats
    # 需要先查找season_id
    print(f"    采集 {year} 年数据...")

    # 尝试直接访问历史页面
    url = f"https://fbref.com/en/comps/{comp_id}/{year}-{year+1}/stats/{tournament['name'].replace(' ', '-')}-{year}-Stats"
    if tournament_key == 'copa_america':
        url = f"https://fbref.com/en/comps/{comp_id}/{year}/stats/{tournament['name'].replace(' ', '-')}-{year}-Stats"

    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            players = parse_player_stats_table(resp.text, league_code, year)
            if players:
                return players
    except:
        pass

    # 尝试另一种URL格式
    url2 = f"https://fbref.com/en/comps/{comp_id}/history/{tournament['name'].replace(' ', '-')}-Seasons"
    try:
        resp = session.get(url2, timeout=30)
        if resp.status_code == 200:
            # 从历史页面查找特定年份的链接
            link_pattern = rf'/en/comps/{comp_id}/(\d+)/[^"]*{year}[^"]*"'
            match = re.search(link_pattern, resp.text)
            if match:
                season_id = match.group(1)
                stats_url = f"https://fbref.com/en/comps/{comp_id}/{season_id}/stats/"
                resp2 = session.get(stats_url, timeout=30)
                if resp2.status_code == 200:
                    return parse_player_stats_table(resp2.text, league_code, year)
    except:
        pass

    return []

def save_player_data(tournament_key, all_data):
    """保存球员数据到CSV"""
    if not all_data:
        print(f"  {tournament_key}: 无数据")
        return

    tournament = TOURNAMENTS[tournament_key]
    tournament_name = tournament['name'].lower().replace(' ', '_')
    tournament_dir = os.path.join(DATA_DIR, tournament_name)
    os.makedirs(tournament_dir, exist_ok=True)

    # 创建DataFrame
    df = pd.DataFrame(all_data)

    # 转换数值字段
    numeric_cols = ['MP', 'Starts', 'Min', 'Gls', 'Ast', 'G+A', 'G-PK', 'PK', 'PKatt', 'CrdY', 'CrdR']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # 计算每90分钟数据
    df['90s'] = (df['Min'] / 90).round(2)
    df['Gls_per90'] = (df['Gls'] / df['90s']).round(2)
    df['Ast_per90'] = (df['Ast'] / df['90s']).round(2)
    df['G+A_per90'] = (df['G+A'] / df['90s']).round(2)
    df['G-PK_per90'] = (df['G-PK'] / df['90s']).round(2)
    df['G+A-PK_per90'] = ((df['G+A'] - df['PK']) / df['90s']).round(2)

    # 处理无穷大和NaN
    df = df.replace([float('inf'), float('-inf')], 0)
    df = df.fillna(0)

    # 按年份分组保存
    years = df['season'].unique()
    for year in sorted(years):
        year_df = df[df['season'] == year]
        filename = f"{tournament_name}_players_stats_{int(year)}.csv"
        filepath = os.path.join(tournament_dir, filename)
        year_df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"  保存: {filename} ({len(year_df)}条记录)")

    # 保存汇总文件
    all_filename = f"{tournament_name}_players_all.csv"
    all_filepath = os.path.join(tournament_dir, all_filename)
    df.to_csv(all_filepath, index=False, encoding='utf-8-sig')
    print(f"  保存: {all_filename} ({len(df)}条记录)")

def main():
    print("=" * 60)
    print(f"国家队赛事球员数据采集 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    session = get_session()

    for tournament_key, tournament in TOURNAMENTS.items():
        print(f"\n{tournament['name_cn']} ({tournament['name']}):")

        all_players = []
        for year in tournament['years']:
            players = fetch_tournament_data(session, tournament_key, year)
            if players:
                all_players.extend(players)
                print(f"      获取 {len(players)} 条记录")
            else:
                print(f"      无数据")
            time.sleep(2)  # 避免请求过快

        if all_players:
            save_player_data(tournament_key, all_players)
        else:
            print(f"  {tournament['name_cn']}: 未获取到任何数据")

    print("\n" + "=" * 60)
    print("数据采集完成!")
    print("=" * 60)

if __name__ == '__main__':
    main()
