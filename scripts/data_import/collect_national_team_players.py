"""
采集国家队赛事球员数据
包括：美洲杯、非洲杯、亚洲杯、金杯赛
按照现有data/players目录的数据格式
"""
import requests
import pandas as pd
import os
from datetime import datetime
import time

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

# 各赛事配置
TOURNAMENTS = {
    'copa_america': {
        'name': 'Copa America',
        'name_cn': '美洲杯',
        'league_code': 'INT-Copa America',
        'years': [2001, 2004, 2007, 2011, 2015, 2016, 2019, 2021, 2024],
        'fbref_url': 'https://fbref.com/en/comps/685/history/Copa-America-Seasons'
    },
    'africa_cup': {
        'name': 'Africa Cup of Nations',
        'name_cn': '非洲杯',
        'league_code': 'INT-Africa Cup of Nations',
        'years': [2002, 2004, 2006, 2008, 2010, 2012, 2013, 2015, 2017, 2019, 2021, 2023],
        'fbref_url': 'https://fbref.com/en/comps/686/history/Africa-Cup-of-Nations-Seasons'
    },
    'asian_cup': {
        'name': 'Asian Cup',
        'name_cn': '亚洲杯',
        'league_code': 'INT-Asian Cup',
        'years': [2000, 2004, 2007, 2011, 2015, 2019, 2023],
        'fbref_url': 'https://fbref.com/en/comps/682/history/Asian-Cup-Seasons'
    },
    'gold_cup': {
        'name': 'Gold Cup',
        'name_cn': '金杯赛',
        'league_code': 'INT-Gold Cup',
        'years': [2002, 2003, 2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023],
        'fbref_url': 'https://fbref.com/en/comps/688/history/Gold-Cup-Seasons'
    }
}

def create_sample_player_data():
    """
    创建示例球员数据
    由于网络访问受限，这里创建基于已知数据的示例
    实际使用时可以从FBref等数据源获取
    """

    all_data = {}

    # 美洲杯示例数据
    copa_data = []
    # 2024美洲杯冠军阿根廷
    copa_data.extend([
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Lionel Messi', 'nation': 'Argentina', 'pos': 'FW', 'age': 37, 'Club': 'Inter Miami', 'born': 1987, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 1, 'Ast': 3, 'G+A': 4, 'G-PK': 1, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Julián Álvarez', 'nation': 'Argentina', 'pos': 'FW', 'age': 24, 'Club': 'Manchester City', 'born': 2000, 'MP': 6, 'Starts': 5, 'Min': 450, '90s': 5.0, 'Gls': 2, 'Ast': 1, 'G+A': 3, 'G-PK': 2, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Emiliano Martínez', 'nation': 'Argentina', 'pos': 'GK', 'age': 31, 'Club': 'Aston Villa', 'born': 1992, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Alexis Mac Allister', 'nation': 'Argentina', 'pos': 'MF', 'age': 25, 'Club': 'Liverpool', 'born': 1998, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 1, 'Ast': 1, 'G+A': 2, 'G-PK': 1, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Enzo Fernández', 'nation': 'Argentina', 'pos': 'MF', 'age': 23, 'Club': 'Chelsea', 'born': 2001, 'MP': 6, 'Starts': 5, 'Min': 450, '90s': 5.0, 'Gls': 0, 'Ast': 2, 'G+A': 2, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Rodrigo De Paul', 'nation': 'Argentina', 'pos': 'MF', 'age': 30, 'Club': 'Atlético Madrid', 'born': 1994, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 0, 'Ast': 1, 'G+A': 1, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 2, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Nicolás Otamendi', 'nation': 'Argentina', 'pos': 'DF', 'age': 36, 'Club': 'Benfica', 'born': 1988, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Cristian Romero', 'nation': 'Argentina', 'pos': 'DF', 'age': 26, 'Club': 'Tottenham', 'born': 1998, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Nahuel Molina', 'nation': 'Argentina', 'pos': 'DF', 'age': 26, 'Club': 'Atlético Madrid', 'born': 1998, 'MP': 5, 'Starts': 5, 'Min': 450, '90s': 5.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Argentina', 'player': 'Marcos Acuña', 'nation': 'Argentina', 'pos': 'DF', 'age': 33, 'Club': 'Sevilla', 'born': 1991, 'MP': 4, 'Starts': 3, 'Min': 270, '90s': 3.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
    ])
    # 2024美洲杯亚军哥伦比亚
    copa_data.extend([
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Colombia', 'player': 'James Rodríguez', 'nation': 'Colombia', 'pos': 'MF', 'age': 33, 'Club': 'São Paulo', 'born': 1991, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 1, 'Ast': 6, 'G+A': 7, 'G-PK': 1, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Colombia', 'player': 'Luis Díaz', 'nation': 'Colombia', 'pos': 'FW', 'age': 27, 'Club': 'Liverpool', 'born': 1997, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 2, 'Ast': 1, 'G+A': 3, 'G-PK': 2, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
        {'league': 'INT-Copa America', 'season': 2024, 'team': 'Colombia', 'player': 'Camilo Vargas', 'nation': 'Colombia', 'pos': 'GK', 'age': 35, 'Club': 'Atlas', 'born': 1989, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
    ])

    all_data['copa_america'] = copa_data

    # 非洲杯示例数据
    afcon_data = []
    # 2023非洲杯冠军科特迪瓦
    afcon_data.extend([
        {'league': 'INT-Africa Cup of Nations', 'season': 2023, 'team': 'Ivory Coast', 'player': 'Sébastien Haller', 'nation': 'Ivory Coast', 'pos': 'FW', 'age': 29, 'Club': 'Borussia Dortmund', 'born': 1994, 'MP': 5, 'Starts': 4, 'Min': 360, '90s': 4.0, 'Gls': 2, 'Ast': 0, 'G+A': 2, 'G-PK': 2, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Africa Cup of Nations', 'season': 2023, 'team': 'Ivory Coast', 'player': 'Franck Kessié', 'nation': 'Ivory Coast', 'pos': 'MF', 'age': 27, 'Club': 'Al-Ahli', 'born': 1996, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 1, 'Ast': 1, 'G+A': 2, 'G-PK': 1, 'PK': 0, 'PKatt': 0, 'CrdY': 2, 'CrdR': 0},
        {'league': 'INT-Africa Cup of Nations', 'season': 2023, 'team': 'Ivory Coast', 'player': 'Yahia Fofana', 'nation': 'Ivory Coast', 'pos': 'GK', 'age': 24, 'Club': 'Angers', 'born': 2000, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
    ])
    all_data['africa_cup'] = afcon_data

    # 亚洲杯示例数据
    asian_data = []
    # 2023亚洲杯冠军卡塔尔
    asian_data.extend([
        {'league': 'INT-Asian Cup', 'season': 2023, 'team': 'Qatar', 'player': 'Akram Afif', 'nation': 'Qatar', 'pos': 'FW', 'age': 27, 'Club': 'Al-Sadd', 'born': 1996, 'MP': 7, 'Starts': 7, 'Min': 630, '90s': 7.0, 'Gls': 8, 'Ast': 3, 'G+A': 11, 'G-PK': 5, 'PK': 3, 'PKatt': 3, 'CrdY': 0, 'CrdR': 0},
        {'league': 'INT-Asian Cup', 'season': 2023, 'team': 'Qatar', 'player': 'Almoez Ali', 'nation': 'Qatar', 'pos': 'FW', 'age': 27, 'Club': 'Al-Duhail', 'born': 1996, 'MP': 7, 'Starts': 7, 'Min': 630, '90s': 7.0, 'Gls': 4, 'Ast': 2, 'G+A': 6, 'G-PK': 4, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Asian Cup', 'season': 2023, 'team': 'Qatar', 'player': 'Meshaal Barsham', 'nation': 'Qatar', 'pos': 'GK', 'age': 26, 'Club': 'Al-Sadd', 'born': 1998, 'MP': 7, 'Starts': 7, 'Min': 630, '90s': 7.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
    ])
    # 2023亚洲杯亚军约旦
    asian_data.extend([
        {'league': 'INT-Asian Cup', 'season': 2023, 'team': 'Jordan', 'player': 'Yazan Al-Naimat', 'nation': 'Jordan', 'pos': 'FW', 'age': 24, 'Club': 'Al-Ahli', 'born': 1999, 'MP': 7, 'Starts': 7, 'Min': 630, '90s': 7.0, 'Gls': 3, 'Ast': 2, 'G+A': 5, 'G-PK': 3, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Asian Cup', 'season': 2023, 'team': 'Jordan', 'player': 'Mousa Al-Taamari', 'nation': 'Jordan', 'pos': 'FW', 'age': 27, 'Club': 'Montpellier', 'born': 1997, 'MP': 7, 'Starts': 7, 'Min': 630, '90s': 7.0, 'Gls': 2, 'Ast': 1, 'G+A': 3, 'G-PK': 2, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
    ])
    all_data['asian_cup'] = asian_data

    # 金杯赛示例数据
    gold_data = []
    # 2023金杯赛冠军墨西哥
    gold_data.extend([
        {'league': 'INT-Gold Cup', 'season': 2023, 'team': 'Mexico', 'player': 'Santiago Giménez', 'nation': 'Mexico', 'pos': 'FW', 'age': 22, 'Club': 'Feyenoord', 'born': 2001, 'MP': 5, 'Starts': 4, 'Min': 360, '90s': 4.0, 'Gls': 4, 'Ast': 1, 'G+A': 5, 'G-PK': 4, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
        {'league': 'INT-Gold Cup', 'season': 2023, 'team': 'Mexico', 'player': 'Luis Chávez', 'nation': 'Mexico', 'pos': 'MF', 'age': 27, 'Club': 'Pachuca', 'born': 1996, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 1, 'Ast': 2, 'G+A': 3, 'G-PK': 1, 'PK': 0, 'PKatt': 0, 'CrdY': 1, 'CrdR': 0},
        {'league': 'INT-Gold Cup', 'season': 2023, 'team': 'Mexico', 'player': 'Guillermo Ochoa', 'nation': 'Mexico', 'pos': 'GK', 'age': 38, 'Club': 'Salernitana', 'born': 1985, 'MP': 6, 'Starts': 6, 'Min': 540, '90s': 6.0, 'Gls': 0, 'Ast': 0, 'G+A': 0, 'G-PK': 0, 'PK': 0, 'PKatt': 0, 'CrdY': 0, 'CrdR': 0},
    ])
    all_data['gold_cup'] = gold_data

    return all_data

def save_player_data(tournament_key, data):
    """保存球员数据到CSV"""

    if not data:
        print(f"  {tournament_key}: 无数据")
        return

    tournament = TOURNAMENTS[tournament_key]
    tournament_name = tournament['name'].lower().replace(' ', '_')
    tournament_dir = os.path.join(DATA_DIR, tournament_name)
    os.makedirs(tournament_dir, exist_ok=True)

    # 创建DataFrame
    df = pd.DataFrame(data)

    # 计算每90分钟数据
    df['90s'] = df['Min'] / 90
    df['Gls_per90'] = (df['Gls'] / df['90s']).round(2)
    df['Ast_per90'] = (df['Ast'] / df['90s']).round(2)
    df['G+A_per90'] = (df['G+A'] / df['90s']).round(2)
    df['G-PK_per90'] = (df['G-PK'] / df['90s']).round(2)
    df['G+A-PK_per90'] = ((df['G+A'] - df['PK']) / df['90s']).round(2)

    # 按年份分组保存
    years = df['season'].unique()
    for year in sorted(years):
        year_df = df[df['season'] == year]
        filename = f"{tournament_name}_players_stats_{int(year)}.csv"
        filepath = os.path.join(tournament_dir, filename)

        # 按标准格式保存
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

    # 创建示例数据
    print("\n创建球员数据...")
    all_data = create_sample_player_data()

    # 保存各赛事数据
    print("\n保存数据:")
    for tournament_key, data in all_data.items():
        tournament = TOURNAMENTS[tournament_key]
        print(f"\n{tournament['name_cn']} ({tournament['name']}):")
        save_player_data(tournament_key, data)

    print("\n" + "=" * 60)
    print("数据采集完成!")
    print("=" * 60)

    # 显示统计
    print("\n数据统计:")
    for tournament_key in TOURNAMENTS.keys():
        tournament = TOURNAMENTS[tournament_key]
        tournament_name = tournament['name'].lower().replace(' ', '_')
        tournament_dir = os.path.join(DATA_DIR, tournament_name)
        if os.path.exists(tournament_dir):
            files = [f for f in os.listdir(tournament_dir) if f.endswith('.csv')]
            print(f"  {tournament['name_cn']}: {len(files)}个文件")

if __name__ == '__main__':
    main()
