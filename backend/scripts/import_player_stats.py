"""导入球员统计数据"""
import sqlite3, pandas as pd, os, json

DB = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'football_unified.db')
DATA = os.path.join(os.path.dirname(__file__), '..', '..', 'data', '09_other_data', 'players')
LEAGUE_MAP = {'英超': 'Premier League', '西甲': 'La Liga', '德甲': 'Bundesliga', '意甲': 'Serie A', '法甲': 'Ligue 1'}

def load_names():
    link = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'linkage')
    team, country = {}, {}
    tf = os.path.join(link, 'team_chinese_names.json')
    if os.path.exists(tf): team = json.load(open(tf, encoding='utf-8'))
    cf = os.path.join(link, 'country_chinese_names.json')
    if os.path.exists(cf): country = json.load(open(cf, encoding='utf-8'))
    return team, country

TEAM_CN, COUNTRY_CN = load_names()

def create_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS player_stats (
        player_stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        league_id INTEGER, league TEXT, league_cn TEXT, season TEXT,
        team TEXT, team_cn TEXT, player TEXT, player_cn TEXT,
        nation TEXT, nation_cn TEXT, position TEXT, age INTEGER,
        matches INTEGER, starts INTEGER, minutes INTEGER,
        goals INTEGER, assists INTEGER, penalties INTEGER,
        penalty_attempts INTEGER, yellow_cards INTEGER, red_cards INTEGER,
        goals_per_90 REAL, assists_per_90 REAL, g_a_per_90 REAL)""")
    conn.commit()

def get_league_id(conn, cn):
    c = conn.cursor()
    eng = LEAGUE_MAP.get(cn, cn)
    c.execute("SELECT league_id FROM leagues WHERE name=? OR name=?", (cn, eng))
    r = c.fetchone()
    return r[0] if r else None

def import_csv(conn, f):
    try: df = pd.read_csv(f, encoding='utf-8-sig')
    except: return 0
    n = 0
    c = conn.cursor()
    for _, r in df.iterrows():
        try:
            lcn = r.get('League', r.get('league', ''))
            lname = LEAGUE_MAP.get(lcn, lcn)
            lid = get_league_id(conn, lcn)
            season = str(r.get('Season', r.get('season', '')))
            team, player = r.get('team', ''), r.get('player', '')
            if not player or not team or pd.isna(player) or pd.isna(team): continue
            nation, pos = str(r.get('nation', '')), r.get('pos', '')
            age = int(r.get('age', 0)) if not pd.isna(r.get('age')) else None
            mp = int(r.get('Playing Time', 0)) if not pd.isna(r.get('Playing Time')) else 0
            st = int(r.get('Playing Time.1', 0)) if not pd.isna(r.get('Playing Time.1')) else 0
            min = int(r.get('Playing Time.2', 0)) if not pd.isna(r.get('Playing Time.2')) else 0
            gl = int(r.get('Performance', 0)) if not pd.isna(r.get('Performance')) else 0
            ast = int(r.get('Performance.1', 0)) if not pd.isna(r.get('Performance.1')) else 0
            pk = int(r.get('Performance.3', 0)) if not pd.isna(r.get('Performance.3')) else 0
            pka = int(r.get('Performance.4', 0)) if not pd.isna(r.get('Performance.4')) else 0
            yc = int(r.get('Performance.5', 0)) if not pd.isna(r.get('Performance.5')) else 0
            rc = int(r.get('Performance.6', 0)) if not pd.isna(r.get('Performance.6')) else 0
            gp90 = float(r.get('Per 90 Minutes', 0)) if not pd.isna(r.get('Per 90 Minutes')) else 0.0
            ap90 = float(r.get('Per 90 Minutes.1', 0)) if not pd.isna(r.get('Per 90 Minutes.1')) else 0.0
            gap90 = float(r.get('Per 90 Minutes.2', 0)) if not pd.isna(r.get('Per 90 Minutes.2')) else 0.0
            tcn = TEAM_CN.get(team, team)
            ncn = COUNTRY_CN.get(nation, nation)
            c.execute("""INSERT INTO player_stats (league_id,league,league_cn,season,team,team_cn,
                player,player_cn,nation,nation_cn,position,age,matches,starts,minutes,goals,assists,
                penalties,penalty_attempts,yellow_cards,red_cards,goals_per_90,assists_per_90,g_a_per_90)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (lid,lname,lcn,season,team,tcn,player,player,nation,ncn,pos,age,mp,st,min,gl,ast,pk,pka,yc,rc,gp90,ap90,gap90))
            n += 1
        except: continue
    conn.commit()
    return n

if __name__ == '__main__':
    print("导入球员数据...")
    conn = sqlite3.connect(DB)
    create_table(conn)
    files = [f for f in os.listdir(DATA) if f.endswith('.csv')] if os.path.exists(DATA) else []
    print(f"找到 {len(files)} 个文件")
    total = sum(import_csv(conn, os.path.join(DATA, f)) for f in files)
    print(f"完成，总计 {total} 条")
    conn.close()