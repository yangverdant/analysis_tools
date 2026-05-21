#!/usr/bin/env python3
"""
将football_v2.db中的StatsBomb比赛同步到football_unified.db
"""

import sqlite3
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

SOURCE_DB = 'd:/football_tools/data/football_v2.db'
TARGET_DB = 'd:/football_tools/data/football_unified.db'

def sync_data():
    src_conn = sqlite3.connect(SOURCE_DB)
    src_cursor = src_conn.cursor()

    tgt_conn = sqlite3.connect(TARGET_DB)
    tgt_cursor = tgt_conn.cursor()

    print("=" * 60)
    print("同步StatsBomb数据到football_unified.db")
    print("=" * 60)

    # 1. 同步联赛
    print("\n[1] 同步联赛...")
    src_cursor.execute('''
        SELECT league_id, league_code, name_en, name_cn, country, tier
        FROM leagues
    ''')
    leagues_added = 0
    for row in src_cursor.fetchall():
        league_id, league_code, name_en, name_cn, country, tier = row
        # 检查是否存在
        tgt_cursor.execute('SELECT league_id FROM leagues WHERE league_id = ?', (league_id,))
        if not tgt_cursor.fetchone():
            tgt_cursor.execute('''
                INSERT INTO leagues (league_id, league_code, name, name_cn, country, tier)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (league_id, league_code, name_en, name_cn, country, tier))
            leagues_added += 1
            print(f"  添加联赛: {name_en}")

    print(f"  新增联赛: {leagues_added}")

    # 2. 同步球队
    print("\n[2] 同步球队...")
    src_cursor.execute('''
        SELECT team_id, team_code, name_en, name_cn, country, team_type, sb_team_id
        FROM teams
        WHERE sb_team_id IS NOT NULL
    ''')
    teams_added = 0
    for row in src_cursor.fetchall():
        team_id, team_code, name_en, name_cn, country, team_type, sb_team_id = row
        # 检查是否存在
        tgt_cursor.execute('SELECT team_id FROM teams WHERE team_id = ?', (team_id,))
        if not tgt_cursor.fetchone():
            tgt_cursor.execute('''
                INSERT INTO teams (team_id, team_code, name, name_cn, country, team_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (team_id, team_code, name_en, name_cn, country, team_type))
            teams_added += 1

    print(f"  新增球队: {teams_added}")

    # 3. 同步赛季
    print("\n[3] 同步赛季...")
    src_cursor.execute('''
        SELECT season_id, season_name, league_id, year
        FROM seasons
    ''')
    seasons_added = 0
    for row in src_cursor.fetchall():
        season_id, season_name, league_id, year = row
        tgt_cursor.execute('SELECT season_id FROM seasons WHERE season_id = ?', (season_id,))
        if not tgt_cursor.fetchone():
            tgt_cursor.execute('''
                INSERT INTO seasons (season_id, season_name, league_id)
                VALUES (?, ?, ?)
            ''', (season_id, season_name, league_id))
            seasons_added += 1

    print(f"  新增赛季: {seasons_added}")

    # 4. 同步比赛
    print("\n[4] 同步比赛...")
    src_cursor.execute('''
        SELECT match_id, league_id, season_id, match_date, match_time,
               home_team_id, away_team_id, home_goals, away_goals,
               status, round_num, venue, sb_match_id, sb_home_team_id, sb_away_team_id,
               home_xg, away_xg, attendance
        FROM matches
        WHERE sb_match_id IS NOT NULL
    ''')
    matches_added = 0
    matches_skipped = 0

    for row in src_cursor.fetchall():
        match_id = row[0]
        # 检查是否存在
        tgt_cursor.execute('SELECT match_id FROM matches WHERE match_id = ?', (match_id,))
        if tgt_cursor.fetchone():
            matches_skipped += 1
            continue

        tgt_cursor.execute('''
            INSERT INTO matches (
                match_id, league_id, season_id, match_date, match_time,
                home_team_id, away_team_id, home_goals, away_goals,
                status, round_num, venue, sb_match_id, sb_home_team_id, sb_away_team_id,
                home_xg, away_xg, attendance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', row)
        matches_added += 1

    print(f"  新增比赛: {matches_added}")
    print(f"  已存在跳过: {matches_skipped}")

    # 5. 同步player_match_stats的match_id链接
    print("\n[5] 更新player_match_stats链接...")
    tgt_cursor.execute('''
        UPDATE player_match_stats
        SET match_id = (
            SELECT m.match_id
            FROM matches m
            WHERE m.sb_match_id = player_match_stats.sb_match_id
        )
        WHERE sb_match_id IS NOT NULL
        AND match_id IS NULL
    ''')
    stats_updated = tgt_cursor.rowcount
    print(f"  更新链接: {stats_updated}")

    tgt_conn.commit()
    src_conn.close()
    tgt_conn.close()

    print("\n" + "=" * 60)
    print("同步完成!")
    print("=" * 60)

if __name__ == '__main__':
    sync_data()
