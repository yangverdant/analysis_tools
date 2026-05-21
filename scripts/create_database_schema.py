"""
创建数据库表结构
对齐new_data的数据结构
"""
import sqlite3
from pathlib import Path

DB_PATH = Path('d:/football_tools/data/football_unified.db')

def create_database():
    """创建数据库和表结构"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("创建数据库表结构...")

    # 1. 联赛表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leagues (
            league_id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            name_cn TEXT,
            country TEXT,
            tier INTEGER DEFAULT 1,
            league_type TEXT DEFAULT 'league',
            logo_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  [OK] leagues 表")

    # 2. 赛季表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seasons (
            season_id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL,
            season_name TEXT NOT NULL,
            year INTEGER,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (league_id) REFERENCES leagues(league_id)
        )
    """)
    print("  [OK] seasons 表")

    # 3. 球队表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_code TEXT UNIQUE,
            name_en TEXT NOT NULL,
            name_cn TEXT,
            team_type TEXT DEFAULT 'club',
            country TEXT,
            logo_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  [OK] teams 表")

    # 4. 球队别名表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_aliases (
            alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            alias_name TEXT NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    """)
    print("  [OK] team_aliases 表")

    # 5. 比赛表（核心表）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id INTEGER,
            league_id INTEGER NOT NULL,
            match_date DATE NOT NULL,
            match_time TIME,
            round_stage TEXT,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_goals INTEGER,
            away_goals INTEGER,
            result TEXT,
            home_goals_ht INTEGER,
            away_goals_ht INTEGER,
            result_ht TEXT,
            home_goals_et INTEGER,
            away_goals_et INTEGER,
            home_penalties INTEGER,
            away_penalties INTEGER,
            home_shots INTEGER,
            away_shots INTEGER,
            home_shots_target INTEGER,
            away_shots_target INTEGER,
            home_corners INTEGER,
            away_corners INTEGER,
            home_fouls INTEGER,
            away_fouls INTEGER,
            home_yellow INTEGER,
            away_yellow INTEGER,
            home_red INTEGER,
            away_red INTEGER,
            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,
            referee TEXT,
            attendance INTEGER,
            venue TEXT,
            neutral INTEGER DEFAULT 0,
            status TEXT DEFAULT 'finished',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (season_id) REFERENCES seasons(season_id),
            FOREIGN KEY (league_id) REFERENCES leagues(league_id),
            FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
            FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
        )
    """)
    print("  [OK] matches 表")

    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team_id, away_team_id)")
    print("  [OK] matches 索引")

    # 6. 球员表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_code TEXT UNIQUE,
            name_en TEXT NOT NULL,
            name_cn TEXT,
            full_name TEXT,
            nation TEXT,
            birth_date DATE,
            birth_place TEXT,
            height INTEGER,
            weight INTEGER,
            foot TEXT,
            position_main TEXT,
            position_other TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  [OK] players 表")

    # 7. 球员职业生涯表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_career (
            career_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            team_id INTEGER,
            team_name TEXT,
            league TEXT,
            apps INTEGER DEFAULT 0,
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            minutes INTEGER DEFAULT 0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            market_value INTEGER,
            transfer_fee INTEGER,
            is_loan INTEGER DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (player_id) REFERENCES players(player_id),
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    """)
    print("  [OK] player_career 表")

    # 8. 球员身价历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_market_value (
            value_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            date DATE NOT NULL,
            age INTEGER,
            team_name TEXT,
            market_value INTEGER NOT NULL,
            currency TEXT DEFAULT 'EUR',
            source TEXT,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
    """)
    print("  [OK] player_market_value 表")

    # 9. 球员伤病记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_injuries (
            injury_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            season TEXT,
            injury_type TEXT,
            body_part TEXT,
            side TEXT,
            start_date DATE,
            end_date DATE,
            days_missed INTEGER,
            matches_missed INTEGER,
            severity TEXT,
            is_recurrence INTEGER DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
    """)
    print("  [OK] player_injuries 表")

    # 10. 球员赛事表现表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_performance (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            competition TEXT NOT NULL,
            season TEXT NOT NULL,
            team_name TEXT,
            mp INTEGER DEFAULT 0,
            starts INTEGER DEFAULT 0,
            minutes INTEGER DEFAULT 0,
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            g_a INTEGER DEFAULT 0,
            g_pk INTEGER DEFAULT 0,
            pk INTEGER DEFAULT 0,
            pk_att INTEGER DEFAULT 0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
    """)
    print("  [OK] player_performance 表")

    # 11. FIFA排名表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fifa_rankings (
            ranking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rank_date DATE NOT NULL,
            team_id INTEGER NOT NULL,
            rank INTEGER NOT NULL,
            points REAL,
            previous_rank INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    """)
    print("  [OK] fifa_rankings 表")

    # 12. 联赛规则表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS league_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL,
            season TEXT,
            teams_count INTEGER,
            matches_per_team INTEGER,
            promotion_spots INTEGER,
            relegation_spots INTEGER,
            playoff_spots INTEGER,
            champions_league_spots INTEGER,
            europa_league_spots INTEGER,
            conference_league_spots INTEGER,
            rules_text TEXT,
            FOREIGN KEY (league_id) REFERENCES leagues(league_id)
        )
    """)
    print("  [OK] league_rules 表")

    conn.commit()
    conn.close()

    print("\n数据库创建完成!")
    print(f"位置: {DB_PATH}")


if __name__ == '__main__':
    create_database()
