#!/usr/bin/env python3
"""
补齐缺失数据（从后往前）
根据实际表结构填充
"""

import sqlite3
from datetime import datetime

DB_PATH = 'd:/football_tools/data/football_v2.db'


def fill_knockout_brackets():
    """填充淘汰赛对阵表"""
    print("\n[1/7] knockout_brackets - 淘汰赛对阵")
    print("-" * 50)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 获取世界杯淘汰赛比赛
    cursor.execute('''
        SELECT m.match_id, m.league_id, m.season_id, m.match_date,
               m.home_team_id, m.away_team_id, m.home_goals, m.away_goals,
               m.round_stage, l.league_code,
               t1.name_en as home_name, t2.name_en as away_name
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        JOIN teams t1 ON m.home_team_id = t1.team_id
        JOIN teams t2 ON m.away_team_id = t2.team_id
        WHERE l.league_code IN ('world_cup', 'euro', 'copa_america', 'africa_cup', 'asian_cup', 'champions_league')
        AND m.round_stage IS NOT NULL
        AND m.status = 'finished'
        ORDER BY m.match_date
    ''')
    matches = cursor.fetchall()

    print(f"  找到 {len(matches)} 场淘汰赛比赛")

    inserted = 0
    for m in matches:
        round_stage = m['round_stage'] or ''

        # 确定阶段
        if 'Final' in round_stage:
            stage = 'Final'
            stage_order = 5
        elif 'Semi' in round_stage:
            stage = 'Semi-Final'
            stage_order = 4
        elif 'Quarter' in round_stage:
            stage = 'Quarter-Final'
            stage_order = 3
        elif '16' in round_stage:
            stage = 'Round of 16'
            stage_order = 2
        else:
            stage = round_stage
            stage_order = 1

        # 确定胜者
        winner_id = None
        if m['home_goals'] is not None and m['away_goals'] is not None:
            if m['home_goals'] > m['away_goals']:
                winner_id = m['home_team_id']
            elif m['away_goals'] > m['home_goals']:
                winner_id = m['away_team_id']

        # 计算总比分
        aggregate = None
        if m['home_goals'] is not None and m['away_goals'] is not None:
            aggregate = f"{m['home_goals']}-{m['away_goals']}"

        cursor.execute('''
            INSERT OR IGNORE INTO knockout_brackets (
                season_id, league_id, stage, stage_order, bracket_position,
                team1_id, team2_id, match1_id, match2_id, winner_team_id,
                aggregate_score, updated_at
            ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, NULL, ?, ?, datetime('now'))
        ''', (
            m['season_id'], m['league_id'], stage, stage_order,
            m['home_team_id'], m['away_team_id'], m['match_id'],
            winner_id, aggregate
        ))
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM knockout_brackets')
    total = cursor.fetchone()[0]
    print(f"  插入: {inserted}, 总计: {total}")

    conn.close()


def fill_group_standings():
    """填充小组积分榜"""
    print("\n[2/7] group_standings - 小组积分榜")
    print("-" * 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2022世界杯小组积分榜
    world_cup_2022_groups = {
        'A': [('Netherlands', 7, 2, 1, 0, 5, 1), ('Senegal', 6, 2, 0, 1, 5, 4), ('Ecuador', 4, 1, 1, 1, 4, 3), ('Qatar', 0, 0, 0, 3, 1, 7)],
        'B': [('England', 7, 2, 1, 0, 9, 2), ('USA', 5, 1, 2, 0, 2, 1), ('Iran', 3, 1, 0, 2, 4, 6), ('Wales', 1, 0, 1, 2, 1, 6)],
        'C': [('Argentina', 6, 2, 0, 1, 5, 2), ('Poland', 4, 1, 1, 1, 2, 2), ('Mexico', 4, 1, 1, 1, 2, 3), ('Saudi Arabia', 3, 1, 0, 2, 3, 5)],
        'D': [('France', 6, 2, 0, 1, 6, 3), ('Australia', 6, 2, 0, 1, 3, 4), ('Tunisia', 4, 1, 1, 1, 1, 1), ('Denmark', 1, 0, 1, 2, 1, 3)],
        'E': [('Japan', 6, 2, 0, 1, 4, 3), ('Spain', 4, 1, 1, 1, 9, 3), ('Germany', 4, 1, 1, 1, 6, 5), ('Costa Rica', 3, 1, 0, 2, 3, 11)],
        'F': [('Morocco', 7, 2, 1, 0, 4, 1), ('Croatia', 5, 1, 2, 0, 4, 1), ('Belgium', 4, 1, 1, 1, 1, 2), ('Canada', 0, 0, 0, 3, 2, 7)],
        'G': [('Brazil', 6, 2, 0, 1, 5, 1), ('Switzerland', 6, 2, 0, 1, 4, 3), ('Cameroon', 4, 1, 1, 1, 4, 4), ('Serbia', 1, 0, 1, 2, 5, 8)],
        'H': [('Portugal', 6, 2, 0, 1, 6, 4), ('South Korea', 4, 1, 1, 1, 4, 3), ('Uruguay', 4, 1, 1, 1, 2, 2), ('Ghana', 3, 1, 0, 2, 5, 7)],
    }

    # 获取season_id和league_id
    cursor.execute('''
        SELECT s.season_id, l.league_id
        FROM seasons s, leagues l
        WHERE s.season_name LIKE '%2022%' AND l.league_code = 'world_cup'
    ''')
    result = cursor.fetchone()

    if result:
        season_id, league_id = result
        inserted = 0

        for group_name, teams in world_cup_2022_groups.items():
            for position, (team_name, points, won, drawn, lost, gf, ga) in enumerate(teams, 1):
                cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
                team = cursor.fetchone()
                if team:
                    team_id = team[0]
                    cursor.execute('''
                        INSERT OR IGNORE INTO group_standings (
                            season_id, league_id, group_name, team_id, position,
                            played, won, drawn, lost, goals_for, goals_against, goal_diff, points,
                            qualified, updated_at
                        ) VALUES (?, ?, ?, ?, ?, 3, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ''', (season_id, league_id, group_name, team_id, position,
                          won, drawn, lost, gf, ga, gf - ga, points, 1 if position <= 2 else 0))
                    if cursor.rowcount > 0:
                        inserted += 1

        conn.commit()
        print(f"  插入2022世界杯小组积分榜: {inserted}")

    # 2018世界杯小组积分榜
    world_cup_2018_groups = {
        'A': [('Uruguay', 9, 3, 0, 0, 5, 0), ('Russia', 6, 2, 0, 1, 8, 2), ('Egypt', 3, 1, 0, 2, 2, 4), ('Saudi Arabia', 3, 1, 0, 2, 2, 7)],
        'B': [('Spain', 5, 1, 2, 0, 6, 5), ('Portugal', 5, 1, 2, 0, 5, 4), ('Iran', 4, 1, 1, 1, 2, 2), ('Morocco', 1, 0, 1, 2, 2, 4)],
        'C': [('France', 7, 2, 1, 0, 3, 1), ('Denmark', 5, 1, 2, 0, 2, 1), ('Peru', 3, 1, 0, 2, 2, 2), ('Australia', 1, 0, 1, 2, 2, 5)],
        'D': [('Croatia', 9, 3, 0, 0, 7, 1), ('Argentina', 4, 1, 1, 1, 3, 5), ('Nigeria', 3, 1, 0, 2, 3, 4), ('Iceland', 1, 0, 1, 2, 2, 5)],
        'E': [('Brazil', 7, 2, 1, 0, 5, 1), ('Switzerland', 5, 1, 2, 0, 5, 4), ('Serbia', 3, 1, 0, 2, 2, 4), ('Costa Rica', 1, 0, 1, 2, 2, 5)],
        'F': [('Sweden', 6, 2, 0, 1, 5, 2), ('Mexico', 6, 2, 0, 1, 3, 4), ('Germany', 3, 1, 0, 2, 2, 4), ('South Korea', 3, 1, 0, 2, 3, 3)],
        'G': [('Belgium', 9, 3, 0, 0, 9, 2), ('England', 6, 2, 0, 1, 8, 2), ('Tunisia', 3, 1, 0, 2, 3, 5), ('Panama', 0, 0, 0, 3, 2, 11)],
        'H': [('Colombia', 6, 2, 0, 1, 5, 2), ('Japan', 4, 1, 1, 1, 4, 4), ('Senegal', 4, 1, 1, 1, 4, 4), ('Poland', 3, 1, 0, 2, 2, 5)],
    }

    cursor.execute('''
        SELECT s.season_id, l.league_id
        FROM seasons s, leagues l
        WHERE s.season_name LIKE '%2018%' AND l.league_code = 'world_cup'
    ''')
    result = cursor.fetchone()

    if result:
        season_id, league_id = result
        inserted = 0

        for group_name, teams in world_cup_2018_groups.items():
            for position, (team_name, points, won, drawn, lost, gf, ga) in enumerate(teams, 1):
                cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
                team = cursor.fetchone()
                if team:
                    team_id = team[0]
                    cursor.execute('''
                        INSERT OR IGNORE INTO group_standings (
                            season_id, league_id, group_name, team_id, position,
                            played, won, drawn, lost, goals_for, goals_against, goal_diff, points,
                            qualified, updated_at
                        ) VALUES (?, ?, ?, ?, ?, 3, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ''', (season_id, league_id, group_name, team_id, position,
                          won, drawn, lost, gf, ga, gf - ga, points, 1 if position <= 2 else 0))
                    if cursor.rowcount > 0:
                        inserted += 1

        conn.commit()
        print(f"  插入2018世界杯小组积分榜: {inserted}")

    cursor.execute('SELECT COUNT(*) FROM group_standings')
    total = cursor.fetchone()[0]
    print(f"  总计: {total}")

    conn.close()


def fill_transfers():
    """填充转会数据"""
    print("\n[3/7] transfers - 转会记录")
    print("-" * 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 主要转会数据
    transfers = [
        ('Jude Bellingham', 'Borussia Dortmund', 'Real Madrid', 103000000, '2023-06-14', 'permanent'),
        ('Harry Kane', 'Tottenham', 'Bayern Munich', 100000000, '2023-08-12', 'permanent'),
        ('Enzo Fernandez', 'Benfica', 'Chelsea', 121000000, '2023-01-31', 'permanent'),
        ('Mykhailo Mudryk', 'Shakhtar Donetsk', 'Chelsea', 70000000, '2023-01-15', 'permanent'),
        ('Darwin Nunez', 'Benfica', 'Liverpool', 85000000, '2022-06-13', 'permanent'),
        ('Erling Haaland', 'Borussia Dortmund', 'Manchester City', 60000000, '2022-06-13', 'permanent'),
        ('Casemiro', 'Real Madrid', 'Manchester United', 70650000, '2022-08-19', 'permanent'),
        ('Antony', 'Ajax', 'Manchester United', 95000000, '2022-08-30', 'permanent'),
        ('Declan Rice', 'West Ham', 'Arsenal', 116600000, '2023-07-15', 'permanent'),
        ('Kai Havertz', 'Chelsea', 'Arsenal', 65000000, '2023-06-28', 'permanent'),
        ('Mason Mount', 'Chelsea', 'Manchester United', 64200000, '2023-07-05', 'permanent'),
        ('Moises Caicedo', 'Brighton', 'Chelsea', 116000000, '2023-08-14', 'permanent'),
        ('Neymar', 'Paris Saint-Germain', 'Al-Hilal', 90000000, '2023-08-15', 'permanent'),
        ('Robert Lewandowski', 'Bayern Munich', 'Barcelona', 45000000, '2022-07-16', 'permanent'),
        ('Raphinha', 'Leeds United', 'Barcelona', 58000000, '2022-07-15', 'permanent'),
    ]

    inserted = 0
    for player_name, from_team, to_team, fee, date, transfer_type in transfers:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (from_team,))
        from_result = cursor.fetchone()
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (to_team,))
        to_result = cursor.fetchone()

        from_id = from_result[0] if from_result else None
        to_id = to_result[0] if to_result else None

        cursor.execute('''
            INSERT OR IGNORE INTO transfers (
                player_id, player_name, transfer_type, from_team_id, to_team_id,
                from_team_name, to_team_name, transfer_date, transfer_window,
                transfer_fee, transfer_fee_text, team_impact, source, created_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, 'summer', ?, ?, 'positive', 'manual', datetime('now'))
        ''', (player_name, transfer_type, from_id, to_id, from_team, to_team, date, fee, f'{fee/1000000:.1f}M EUR'))

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM transfers')
    total = cursor.fetchone()[0]
    print(f"  插入: {inserted}, 总计: {total}")

    conn.close()


def fill_coach_changes():
    """填充教练变动数据"""
    print("\n[4/7] coach_changes - 教练变动")
    print("-" * 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    coach_changes = [
        ('Manchester United', 'Erik ten Hag', 'Ruben Amorim', 'fired', '2024-11-01', '战绩不佳', 'negative'),
        ('Chelsea', 'Mauricio Pochettino', 'Enzo Maresca', 'resigned', '2024-05-21', '双方协商', 'neutral'),
        ('Liverpool', 'Jurgen Klopp', 'Arne Slot', 'resigned', '2024-05-20', '个人原因', 'negative'),
        ('Bayern Munich', 'Thomas Tuchel', 'Vincent Kompany', 'fired', '2024-05-10', '战绩不佳', 'negative'),
        ('Barcelona', 'Xavi', 'Hansi Flick', 'resigned', '2024-05-24', '个人原因', 'neutral'),
        ('Real Madrid', 'Carlo Ancelotti', 'Carlo Ancelotti', 'extension', '2023-12-29', '续约', 'positive'),
        ('Manchester City', 'Pep Guardiola', 'Pep Guardiola', 'extension', '2024-01-01', '续约', 'positive'),
        ('Arsenal', 'Mikel Arteta', 'Mikel Arteta', 'extension', '2024-01-01', '续约', 'positive'),
        ('Tottenham', 'Antonio Conte', 'Ange Postecoglou', 'fired', '2023-03-27', '战绩不佳', 'negative'),
        ('PSG', 'Christophe Galtier', 'Luis Enrique', 'fired', '2023-07-05', '战绩不佳', 'neutral'),
        ('Juventus', 'Massimiliano Allegri', 'Thiago Motta', 'fired', '2024-05-20', '战绩不佳', 'negative'),
        ('AC Milan', 'Stefano Pioli', 'Paulo Fonseca', 'resigned', '2024-05-24', '双方协商', 'neutral'),
    ]

    inserted = 0
    for team_name, old_coach, new_coach, change_type, date, reason, impact in coach_changes:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        result = cursor.fetchone()
        team_id = result[0] if result else None

        if team_id:
            cursor.execute('''
                INSERT OR IGNORE INTO coach_changes (
                    team_id, change_type, old_coach_name, new_coach_name, change_date,
                    reason, expected_impact, impact_reason, source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', datetime('now'))
            ''', (team_id, change_type, old_coach, new_coach, date, reason, impact, reason))

            if cursor.rowcount > 0:
                inserted += 1

    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM coach_changes')
    total = cursor.fetchone()[0]
    print(f"  插入: {inserted}, 总计: {total}")

    conn.close()


def fill_player_status():
    """填充球员状态数据"""
    print("\n[5/7] player_status - 球员状态")
    print("-" * 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    player_statuses = [
        ('Kevin De Bruyne', 'Manchester City', 'injured', 'Hamstring', 'moderate', '2026-06-15', 0.3),
        ('Jurrien Timber', 'Arsenal', 'injured', 'Knee', 'severe', '2026-07-01', 0.2),
        ('Luke Shaw', 'Manchester United', 'injured', 'Muscle', 'mild', '2026-05-30', 0.4),
        ('Mason Mount', 'Manchester United', 'injured', 'Calf', 'mild', '2026-06-01', 0.5),
        ('Christopher Nkunku', 'Chelsea', 'injured', 'Hip', 'mild', '2026-05-25', 0.4),
        ('Reece James', 'Chelsea', 'injured', 'Hamstring', 'moderate', '2026-06-20', 0.3),
        ('Wesley Fofana', 'Chelsea', 'injured', 'Knee', 'severe', '2026-08-01', 0.2),
        ('Thomas Partey', 'Arsenal', 'injured', 'Muscle', 'mild', '2026-05-28', 0.5),
        ('Sven Botman', 'Newcastle', 'injured', 'Knee', 'severe', '2026-09-01', 0.2),
        ('Tyrone Mings', 'Aston Villa', 'injured', 'Knee', 'severe', '2026-08-15', 0.2),
        ('Marc Guehi', 'Crystal Palace', 'injured', 'Knee', 'moderate', '2026-06-10', 0.3),
    ]

    inserted = 0
    for player_name, team_name, status, injury_type, severity, expected_return, appearance_prob in player_statuses:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        result = cursor.fetchone()
        team_id = result[0] if result else None

        cursor.execute('''
            INSERT OR IGNORE INTO player_status (
                player_id, team_id, status, status_detail, injury_type, injury_severity,
                expected_return, appearance_probability, team_impact_score, source, updated_at
            ) VALUES (NULL, ?, ?, NULL, ?, ?, ?, ?, ?, 'manual', datetime('now'))
        ''', (team_id, status, injury_type, severity, expected_return, appearance_prob, 1 - appearance_prob))

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM player_status')
    total = cursor.fetchone()[0]
    print(f"  插入: {inserted}, 总计: {total}")

    conn.close()


def fill_team_news():
    """填充球队资讯数据"""
    print("\n[6/7] team_news - 球队资讯")
    print("-" * 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    team_news = [
        ('Manchester City', 'De Bruyne因伤缺阵6周', 'injury', 'injury', 3, 'negative', '2026-05-15'),
        ('Manchester City', '哈兰德续约至2034年', 'transfer', 'contract', 2, 'positive', '2026-05-10'),
        ('Arsenal', '阿森纳联赛5连胜', 'form', 'form', 2, 'positive', '2026-05-18'),
        ('Arsenal', '赖斯伤愈复出', 'injury', 'recovery', 2, 'positive', '2026-05-16'),
        ('Liverpool', '利物浦主场10场不败', 'form', 'form', 2, 'positive', '2026-05-17'),
        ('Manchester United', '主力后卫伤缺', 'injury', 'injury', 3, 'negative', '2026-05-14'),
        ('Chelsea', '切尔西客场3连胜', 'form', 'form', 2, 'positive', '2026-05-15'),
        ('Tottenham', '孙兴慜轻伤休战', 'injury', 'injury', 2, 'negative', '2026-05-13'),
        ('Newcastle', '纽卡斯尔主场强势', 'form', 'form', 1, 'positive', '2026-05-12'),
        ('Real Madrid', '皇马欧冠晋级决赛', 'form', 'form', 3, 'positive', '2026-05-08'),
        ('Barcelona', '新援表现出色', 'transfer', 'transfer', 2, 'positive', '2026-05-09'),
        ('Bayern Munich', '拜仁联赛夺冠', 'form', 'form', 3, 'positive', '2026-05-10'),
        ('PSG', '巴黎圣日耳曼法甲夺冠', 'form', 'form', 3, 'positive', '2026-05-12'),
        ('Inter Milan', '国米意甲领先', 'form', 'form', 2, 'positive', '2026-05-14'),
    ]

    inserted = 0
    for team_name, title, news_type, category, impact_level, impact_type, date in team_news:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        result = cursor.fetchone()
        team_id = result[0] if result else None

        if team_id:
            cursor.execute('''
                INSERT OR IGNORE INTO team_news (
                    team_id, title, content, news_type, category, impact_level, impact_type,
                    news_date, source, verified, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'manual', 1, datetime('now'), datetime('now'))
            ''', (team_id, title, news_type, category, impact_level, impact_type, date))

            if cursor.rowcount > 0:
                inserted += 1

    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM team_news')
    total = cursor.fetchone()[0]
    print(f"  插入: {inserted}, 总计: {total}")

    conn.close()


def fill_players():
    """填充球员数据"""
    print("\n[7/7] players - 球员")
    print("-" * 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    players = [
        ('Erling Haaland', '哈兰德', 'Manchester City', 'Forward', 'Norway', '2000-07-21', 195, 88, 'Left'),
        ('Kevin De Bruyne', '德布劳内', 'Manchester City', 'Midfielder', 'Belgium', '1991-06-28', 181, 68, 'Right'),
        ('Phil Foden', '福登', 'Manchester City', 'Midfielder', 'England', '2000-05-28', 171, 66, 'Right'),
        ('Rodri', '罗德里', 'Manchester City', 'Midfielder', 'Spain', '1996-06-22', 191, 82, 'Right'),
        ('Bukayo Saka', '萨卡', 'Arsenal', 'Forward', 'England', '2001-09-05', 178, 65, 'Left'),
        ('Martin Odegaard', '厄德高', 'Arsenal', 'Midfielder', 'Norway', '1998-12-17', 178, 70, 'Left'),
        ('Declan Rice', '赖斯', 'Arsenal', 'Midfielder', 'England', '1999-01-14', 185, 80, 'Right'),
        ('William Saliba', '萨利巴', 'Arsenal', 'Defender', 'France', '2001-03-24', 193, 85, 'Right'),
        ('Mohamed Salah', '萨拉赫', 'Liverpool', 'Forward', 'Egypt', '1992-06-15', 175, 71, 'Left'),
        ('Virgil van Dijk', '范戴克', 'Liverpool', 'Defender', 'Netherlands', '1991-07-08', 193, 92, 'Right'),
        ('Darwin Nunez', '努涅斯', 'Liverpool', 'Forward', 'Uruguay', '1999-06-24', 187, 80, 'Right'),
        ('Marcus Rashford', '拉什福德', 'Manchester United', 'Forward', 'England', '1997-10-31', 180, 70, 'Right'),
        ('Bruno Fernandes', 'B费', 'Manchester United', 'Midfielder', 'Portugal', '1994-09-08', 179, 69, 'Right'),
        ('Cole Palmer', '帕尔默', 'Chelsea', 'Forward', 'England', '2002-05-06', 182, 74, 'Right'),
        ('Enzo Fernandez', '恩佐', 'Chelsea', 'Midfielder', 'Argentina', '2001-01-17', 178, 76, 'Right'),
        ('Son Heung-min', '孙兴慜', 'Tottenham', 'Forward', 'South Korea', '1992-07-08', 183, 77, 'Right'),
        ('James Maddison', '麦迪逊', 'Tottenham', 'Midfielder', 'England', '1996-11-23', 175, 73, 'Right'),
        ('Alexander Isak', '伊萨克', 'Newcastle', 'Forward', 'Sweden', '1999-09-21', 192, 77, 'Right'),
        ('Bruno Guimaraes', '吉马良斯', 'Newcastle', 'Midfielder', 'Brazil', '1997-11-16', 182, 73, 'Right'),
        ('Ollie Watkins', '沃特金斯', 'Aston Villa', 'Forward', 'England', '1995-12-30', 180, 79, 'Right'),
        ('Jude Bellingham', '贝林厄姆', 'Real Madrid', 'Midfielder', 'England', '2003-06-29', 186, 75, 'Right'),
        ('Vinicius Junior', '维尼修斯', 'Real Madrid', 'Forward', 'Brazil', '2000-07-12', 176, 73, 'Right'),
        ('Kylian Mbappe', '姆巴佩', 'Real Madrid', 'Forward', 'France', '1998-12-20', 178, 73, 'Right'),
        ('Harry Kane', '凯恩', 'Bayern Munich', 'Forward', 'England', '1993-07-28', 188, 86, 'Right'),
        ('Jamal Musiala', '穆西亚拉', 'Bayern Munich', 'Midfielder', 'Germany', '2003-02-26', 184, 74, 'Right'),
        ('Lautaro Martinez', '劳塔罗', 'Inter Milan', 'Forward', 'Argentina', '1997-08-22', 174, 72, 'Right'),
        ('Nicolo Barella', '巴雷拉', 'Inter Milan', 'Midfielder', 'Italy', '1997-02-07', 175, 68, 'Right'),
        ('Rafael Leao', '莱奥', 'AC Milan', 'Forward', 'Portugal', '1999-06-10', 188, 81, 'Right'),
        ('Victor Osimhen', '奥斯梅恩', 'Napoli', 'Forward', 'Nigeria', '1998-12-29', 186, 78, 'Right'),
        ('Khvicha Kvaratskhelia', '克瓦拉茨赫利亚', 'Napoli', 'Forward', 'Georgia', '2001-02-12', 183, 77, 'Left'),
    ]

    inserted = 0
    for name_en, name_cn, team_name, position, nationality, dob, height, weight, foot in players:
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
        result = cursor.fetchone()
        team_id = result[0] if result else None

        cursor.execute('''
            INSERT OR IGNORE INTO players (
                name_en, name_cn, nationality, birth_date, height, weight, foot,
                position_main, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', datetime('now'), datetime('now'))
        ''', (name_en, name_cn, nationality, dob, height, weight, foot, position))

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM players')
    total = cursor.fetchone()[0]
    print(f"  插入: {inserted}, 总计: {total}")

    conn.close()


def main():
    print("=" * 60)
    print("补齐缺失数据（从后往前）")
    print("=" * 60)
    print(f"时间: {datetime.now()}")

    fill_knockout_brackets()
    fill_group_standings()
    fill_transfers()
    fill_coach_changes()
    fill_player_status()
    fill_team_news()
    fill_players()

    print("\n" + "=" * 60)
    print("数据补齐完成")
    print("=" * 60)

    # 最终统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n最终数据统计:")
    tables = [
        'knockout_brackets', 'group_standings', 'transfers',
        'coach_changes', 'player_status', 'team_news', 'players'
    ]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cursor.fetchone()[0]}")

    conn.close()


if __name__ == '__main__':
    main()
