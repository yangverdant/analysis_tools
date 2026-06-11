"""
将世界杯详细数据导入数据库
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'football_v2.db'
DATA_DIR = Path('d:/football_tools')
DETAIL_DIR = DATA_DIR / 'world_cup_details'


def import_match_details():
    """导入比赛详情"""
    print("=" * 60)
    print("导入世界杯比赛详细数据")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    # 创建详细数据表（如果不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_details (
            match_id TEXT PRIMARY KEY,
            match_date TEXT,
            match_time TEXT,
            stadium TEXT,
            city TEXT,
            referee TEXT,
            home_formation TEXT,
            away_formation TEXT,
            home_goals_ft INTEGER,
            away_goals_ft INTEGER,
            home_goals_ht INTEGER,
            away_goals_ht INTEGER,
            home_goals_et INTEGER,
            away_goals_et INTEGER,
            home_goals_pen INTEGER,
            away_goals_pen INTEGER,
            goalscorer_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            stat_type TEXT,
            home_value TEXT,
            away_value TEXT,
            period TEXT DEFAULT 'full',
            UNIQUE(match_id, stat_type, period)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_match_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            player_key TEXT,
            player_name TEXT,
            team_name TEXT,
            player_number TEXT,
            player_position TEXT,
            minutes_played INTEGER,
            goals INTEGER,
            assists INTEGER,
            shots_total INTEGER,
            shots_on_goal INTEGER,
            passes INTEGER,
            passes_acc INTEGER,
            key_passes INTEGER,
            tackles INTEGER,
            interceptions INTEGER,
            clearances INTEGER,
            fouls_committed INTEGER,
            fouls_drawn INTEGER,
            yellow_cards INTEGER,
            red_cards INTEGER,
            rating TEXT,
            UNIQUE(match_id, player_key)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            team_type TEXT,
            player_key TEXT,
            player_name TEXT,
            player_number TEXT,
            position TEXT,
            is_starter INTEGER DEFAULT 1,
            UNIQUE(match_id, team_type, player_key)
        )
    ''')

    conn.commit()

    # 统计
    details_count = 0
    stats_count = 0
    player_stats_count = 0
    lineups_count = 0

    # 导入详情
    print("\n导入比赛详情...")
    for f in DETAIL_DIR.glob('detail_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, list) and len(data) > 0:
                    m = data[0]
                    match_id = m.get('match_id')
                    match_date = m.get('match_date')
                    match_time = m.get('match_time')
                    stadium = m.get('match_stadium', '')
                    referee = m.get('match_referee', '')
                    home_formation = m.get('match_hometeam_system', '')
                    away_formation = m.get('match_awayteam_system', '')

                    # 提取城市
                    city = ''
                    if stadium and '(' in stadium:
                        city = stadium.split('(')[-1].rstrip(')')

                    # 比分
                    home_goals_ft = m.get('match_hometeam_ft_score')
                    away_goals_ft = m.get('match_awayteam_ft_score')
                    home_goals_ht = m.get('match_hometeam_halftime_score')
                    away_goals_ht = m.get('match_awayteam_halftime_score')
                    home_goals_et = m.get('match_hometeam_extra_score')
                    away_goals_et = m.get('match_awayteam_extra_score')
                    home_goals_pen = m.get('match_hometeam_penalty_score')
                    away_goals_pen = m.get('match_awayteam_penalty_score')

                    # 进球者
                    goalscorer = m.get('goalscorer', [])
                    goalscorer_json = json.dumps(goalscorer, ensure_ascii=False) if goalscorer else None

                    cursor.execute('''
                        INSERT OR REPLACE INTO match_details
                        (match_id, match_date, match_time, stadium, city, referee,
                         home_formation, away_formation, home_goals_ft, away_goals_ft,
                         home_goals_ht, away_goals_ht, home_goals_et, away_goals_et,
                         home_goals_pen, away_goals_pen, goalscorer_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (match_id, match_date, match_time, stadium, city, referee,
                          home_formation, away_formation, home_goals_ft, away_goals_ft,
                          home_goals_ht, away_goals_ht, home_goals_et, away_goals_et,
                          home_goals_pen, away_goals_pen, goalscorer_json))
                    details_count += 1
        except Exception as e:
            pass

    conn.commit()
    print(f"  比赛详情: {details_count} 场")

    # 导入统计数据
    print("\n导入比赛统计...")
    for f in DETAIL_DIR.glob('stats_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, dict):
                    for mid, stats_data in data.items():
                        # 全场统计
                        stats = stats_data.get('statistics', [])
                        for s in stats:
                            stat_type = s.get('type', '')
                            home_val = s.get('home', '')
                            away_val = s.get('away', '')
                            if stat_type:
                                cursor.execute('''
                                    INSERT OR REPLACE INTO match_statistics
                                    (match_id, stat_type, home_value, away_value, period)
                                    VALUES (?, ?, ?, ?, 'full')
                                ''', (mid, stat_type, home_val, away_val))
                                stats_count += 1

                        # 半场统计
                        half_stats = stats_data.get('statistics_1half', [])
                        for s in half_stats:
                            stat_type = s.get('type', '')
                            home_val = s.get('home', '')
                            away_val = s.get('away', '')
                            if stat_type:
                                cursor.execute('''
                                    INSERT OR REPLACE INTO match_statistics
                                    (match_id, stat_type, home_value, away_value, period)
                                    VALUES (?, ?, ?, ?, 'half')
                                ''', (mid, stat_type, home_val, away_val))
                                stats_count += 1

                        # 球员统计
                        player_stats = stats_data.get('player_statistics', [])
                        for p in player_stats:
                            cursor.execute('''
                                INSERT OR REPLACE INTO player_match_stats
                                (match_id, player_key, player_name, team_name, player_number,
                                 player_position, minutes_played, goals, assists, shots_total,
                                 shots_on_goal, passes, passes_acc, key_passes, tackles,
                                 interceptions, clearances, fouls_committed, fouls_drawn,
                                 yellow_cards, red_cards, rating)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (mid, p.get('player_key'), p.get('player_name'), p.get('team_name'),
                                  p.get('player_number'), p.get('player_position'),
                                  p.get('player_minutes_played'), p.get('player_goals'),
                                  p.get('player_assists'), p.get('player_shots_total'),
                                  p.get('player_shots_on_goal'), p.get('player_passes'),
                                  p.get('player_passes_acc'), p.get('player_key_passes'),
                                  p.get('player_tackles'), p.get('player_interceptions'),
                                  p.get('player_clearances'), p.get('player_fouls_commited'),
                                  p.get('player_fouls_drawn'), p.get('player_yellowcards'),
                                  p.get('player_redcards'), p.get('player_rating')))
                            player_stats_count += 1
        except Exception as e:
            pass

    conn.commit()
    print(f"  比赛统计: {stats_count} 条")
    print(f"  球员统计: {player_stats_count} 条")

    # 导入阵容
    print("\n导入比赛阵容...")
    for f in DETAIL_DIR.glob('lineup_*.json'):
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, dict):
                    for mid, lineup_data in data.items():
                        lineup = lineup_data.get('lineup', {})
                        # 主队
                        home = lineup.get('home', {})
                        starters = home.get('starting_lineups', [])
                        subs = home.get('substitutes', [])

                        for p in starters:
                            cursor.execute('''
                                INSERT OR REPLACE INTO match_lineups
                                (match_id, team_type, player_key, player_name, player_number, position, is_starter)
                                VALUES (?, 'home', ?, ?, ?, ?, 1)
                            ''', (mid, p.get('player_key'), p.get('lineup_player'),
                                  p.get('lineup_number'), p.get('lineup_position')))
                            lineups_count += 1

                        for p in subs:
                            cursor.execute('''
                                INSERT OR REPLACE INTO match_lineups
                                (match_id, team_type, player_key, player_name, player_number, position, is_starter)
                                VALUES (?, 'home', ?, ?, ?, ?, 0)
                            ''', (mid, p.get('player_key'), p.get('lineup_player'),
                                  p.get('lineup_number'), p.get('lineup_position')))
                            lineups_count += 1

                        # 客队
                        away = lineup.get('away', {})
                        starters = away.get('starting_lineups', [])
                        subs = away.get('substitutes', [])

                        for p in starters:
                            cursor.execute('''
                                INSERT OR REPLACE INTO match_lineups
                                (match_id, team_type, player_key, player_name, player_number, position, is_starter)
                                VALUES (?, 'away', ?, ?, ?, ?, 1)
                            ''', (mid, p.get('player_key'), p.get('lineup_player'),
                                  p.get('lineup_number'), p.get('lineup_position')))
                            lineups_count += 1

                        for p in subs:
                            cursor.execute('''
                                INSERT OR REPLACE INTO match_lineups
                                (match_id, team_type, player_key, player_name, player_number, position, is_starter)
                                VALUES (?, 'away', ?, ?, ?, ?, 0)
                            ''', (mid, p.get('player_key'), p.get('lineup_player'),
                                  p.get('lineup_number'), p.get('lineup_position')))
                            lineups_count += 1
        except Exception as e:
            pass

    conn.commit()
    print(f"  阵容记录: {lineups_count} 条")

    conn.close()

    print(f"\n{'=' * 60}")
    print(f"导入完成!")
    print(f"  比赛详情: {details_count}")
    print(f"  比赛统计: {stats_count}")
    print(f"  球员统计: {player_stats_count}")
    print(f"  阵容记录: {lineups_count}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    import_match_details()