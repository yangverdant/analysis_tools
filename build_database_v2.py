#!/usr/bin/env python3
"""
构建足球分析数据库 v2
基于 DATABASE_DESIGN.md 和 COMPETITION_TYPES.md 设计
核心原则：禁止虚假数据，数据来源可追溯，宁可缺失不可错误
"""

import os
import sqlite3
from datetime import datetime

# 配置
OUTPUT_DB = 'd:/football_tools/data/football_v2.db'

def create_database():
    """创建数据库和表结构"""
    conn = sqlite3.connect(OUTPUT_DB)
    cursor = conn.cursor()

    print("=" * 70)
    print("创建足球分析数据库 v2")
    print("基于 DATABASE_DESIGN.md + NEWS_AND_FACTORS_DESIGN.md 设计")
    print("=" * 70)

    # ============================================================
    # 1. 联赛表 (leagues)
    # ============================================================
    print("\n[1/17] 创建联赛表 (leagues)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leagues (
        -- 主键
        league_id INTEGER PRIMARY KEY,
        league_code TEXT UNIQUE,

        -- 基本信息
        name_en TEXT NOT NULL,
        name_cn TEXT,
        country TEXT,
        country_cn TEXT,

        -- 赛事分类（核心）
        competition_type TEXT NOT NULL DEFAULT 'league',
        participant_type TEXT NOT NULL DEFAULT 'club',
        format_type TEXT NOT NULL DEFAULT 'round_robin',

        -- 赛事属性
        tier INTEGER DEFAULT 1,
        is_international INTEGER DEFAULT 0,
        cycle_type TEXT DEFAULT 'annual',

        -- 外部ID映射
        sm_league_id INTEGER,
        fd_comp_code TEXT,
        tsdb_league_id INTEGER,

        -- 元数据
        logo_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # ============================================================
    # 2. 赛季表 (seasons)
    # ============================================================
    print("[2/17] 创建赛季表 (seasons)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seasons (
        season_id INTEGER PRIMARY KEY,
        league_id INTEGER NOT NULL,

        -- 赛季标识
        season_name TEXT NOT NULL,
        year INTEGER,

        -- 赛季周期
        start_date DATE,
        end_date DATE,

        -- 状态
        status TEXT DEFAULT 'active',

        -- 外部ID
        sm_season_id INTEGER,

        -- 元数据
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        UNIQUE(league_id, season_name)
    )
    ''')

    # ============================================================
    # 3. 球队表 (teams)
    # ============================================================
    print("[3/17] 创建球队表 (teams)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teams (
        team_id INTEGER PRIMARY KEY,
        team_code TEXT UNIQUE,

        -- 基本信息
        name_en TEXT NOT NULL,
        name_cn TEXT,
        short_name TEXT,
        tla TEXT,

        -- 球队类型（核心区分）
        team_type TEXT NOT NULL DEFAULT 'club',

        -- 所属
        country TEXT,
        country_cn TEXT,

        -- 俱乐部专属
        primary_league_id INTEGER,
        founded_year INTEGER,
        stadium TEXT,
        stadium_capacity INTEGER,

        -- 国家队专属
        confederation TEXT,
        fifa_code TEXT,

        -- 外部ID映射
        sm_team_id INTEGER,
        fd_team_id INTEGER,
        tsdb_team_id INTEGER,
        sb_team_id TEXT,

        -- 元数据
        logo_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (primary_league_id) REFERENCES leagues(league_id)
    )
    ''')

    # ============================================================
    # 4. 球队别名表 (team_aliases)
    # ============================================================
    print("[4/17] 创建球队别名表 (team_aliases)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_aliases (
        alias_id INTEGER PRIMARY KEY,
        team_id INTEGER NOT NULL,
        alias_name TEXT NOT NULL,
        source TEXT NOT NULL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        UNIQUE(team_id, alias_name, source)
    )
    ''')

    # ============================================================
    # 5. 比赛表 (matches) — 核心表
    # ============================================================
    print("[5/17] 创建比赛表 (matches)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        -- 主键（使用TEXT支持复杂ID）
        match_id TEXT PRIMARY KEY,
        match_code TEXT UNIQUE,

        -- 关联
        season_id INTEGER,
        league_id INTEGER NOT NULL,

        -- 比赛时间
        match_date DATE NOT NULL,
        match_time TIME,

        -- 轮次/阶段
        round_num INTEGER,
        round_stage TEXT,
        stage_type TEXT,

        -- 小组赛专用
        group_name TEXT,

        -- 淘汰赛专用
        leg INTEGER,
        aggregate_home INTEGER,
        aggregate_away INTEGER,

        -- 球队
        home_team_id INTEGER NOT NULL,
        away_team_id INTEGER NOT NULL,

        -- 场地
        venue TEXT,
        venue_city TEXT,
        neutral INTEGER DEFAULT 0,

        -- 比分（死数据）
        home_goals INTEGER,
        away_goals INTEGER,
        result TEXT,

        home_goals_ht INTEGER,
        away_goals_ht INTEGER,

        home_goals_et INTEGER,
        away_goals_et INTEGER,

        home_penalties INTEGER,
        away_penalties INTEGER,

        -- 比赛统计（死数据）
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

        -- 高级统计
        home_possession REAL,
        away_possession REAL,
        home_passes INTEGER,
        away_passes INTEGER,
        home_pass_accuracy REAL,
        away_pass_accuracy REAL,

        -- xG数据
        home_xg REAL,
        away_xg REAL,
        home_xgot REAL,
        away_xgot REAL,
        home_npxg REAL,
        away_npxg REAL,

        -- StatsBomb高级统计
        home_passes_total INTEGER,
        away_passes_total INTEGER,
        home_pass_complete INTEGER,
        away_pass_complete INTEGER,
        home_pass_completion_rate REAL,
        away_pass_completion_rate REAL,
        home_pressures INTEGER,
        away_pressures INTEGER,
        home_carries INTEGER,
        away_carries INTEGER,
        home_dribbles_success INTEGER,
        away_dribbles_success INTEGER,
        home_dribbles_attempted INTEGER,
        away_dribbles_attempted INTEGER,
        home_interceptions INTEGER,
        away_interceptions INTEGER,
        home_clearances INTEGER,
        away_clearances INTEGER,
        home_blocks INTEGER,
        away_blocks INTEGER,
        home_ball_recovery INTEGER,
        away_ball_recovery INTEGER,
        home_crosses INTEGER,
        away_crosses INTEGER,
        home_key_passes INTEGER,
        away_key_passes INTEGER,

        -- 上下文
        referee TEXT,
        attendance INTEGER,

        -- 赔率（收盘赔率）
        odds_home REAL,
        odds_draw REAL,
        odds_away REAL,
        odds_home_closing REAL,
        odds_draw_closing REAL,
        odds_away_closing REAL,

        -- 状态
        status TEXT NOT NULL DEFAULT 'finished',

        -- StatsBomb元数据
        sb_match_id INTEGER,
        sb_home_team_id TEXT,
        sb_away_team_id TEXT,
        sb_stadium TEXT,
        sb_home_manager TEXT,
        sb_away_manager TEXT,

        -- 元数据
        source TEXT DEFAULT 'last_data',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
        FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
    )
    ''')

    # ============================================================
    # 6. 赔率表 (match_odds)
    # ============================================================
    print("[6/17] 创建赔率表 (match_odds)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS match_odds (
        odds_id INTEGER PRIMARY KEY,
        match_id TEXT NOT NULL,

        -- 1X2赔率
        b365_home REAL, b365_draw REAL, b365_away REAL,
        ps_home REAL, ps_draw REAL, ps_away REAL,
        max_home REAL, max_draw REAL, max_away REAL,
        avg_home REAL, avg_draw REAL, avg_away REAL,

        -- 大小球赔率
        b365_over_2_5 REAL, b365_under_2_5 REAL,
        ps_over_2_5 REAL, ps_under_2_5 REAL,
        max_over_2_5 REAL, max_under_2_5 REAL,
        avg_over_2_5 REAL, avg_under_2_5 REAL,

        -- 亚盘赔率
        asian_handicap REAL,
        b365_ah_home REAL, b365_ah_away REAL,
        ps_ah_home REAL, ps_ah_away REAL,
        max_ah_home REAL, max_ah_away REAL,
        avg_ah_home REAL, avg_ah_away REAL,

        -- 收盘赔率
        b365_c_home REAL, b365_c_draw REAL, b365_c_away REAL,
        ps_c_home REAL, ps_c_draw REAL, ps_c_away REAL,
        max_c_home REAL, max_c_draw REAL, max_c_away REAL,
        avg_c_home REAL, avg_c_draw REAL, avg_c_away REAL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        UNIQUE(match_id)
    )
    ''')

    # ============================================================
    # 7. 射门事件表 (statsbomb_shots)
    # ============================================================
    print("[7/17] 创建射门事件表 (statsbomb_shots)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statsbomb_shots (
        shot_id INTEGER PRIMARY KEY,
        match_id TEXT NOT NULL,
        sb_match_id INTEGER,

        team_id INTEGER,
        team_name TEXT,
        player_id TEXT,
        player_name TEXT,

        minute INTEGER,
        second INTEGER,
        period INTEGER,

        xg REAL,
        shot_type TEXT,
        shot_outcome TEXT,
        shot_technique TEXT,
        body_part TEXT,
        first_time INTEGER,
        open_play INTEGER,

        location_x REAL,
        location_y REAL,
        end_location_x REAL,
        end_location_y REAL,
        end_location_z REAL,

        key_pass_id TEXT,
        play_pattern TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        FOREIGN KEY (team_id) REFERENCES teams(team_id)
    )
    ''')

    # ============================================================
    # 8. 传球事件表 (statsbomb_passes)
    # ============================================================
    print("[8/17] 创建传球事件表 (statsbomb_passes)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statsbomb_passes (
        pass_id INTEGER PRIMARY KEY,
        match_id TEXT NOT NULL,
        sb_match_id INTEGER,

        team_id INTEGER,
        team_name TEXT,
        player_id TEXT,
        player_name TEXT,

        minute INTEGER,
        second INTEGER,
        period INTEGER,

        pass_type TEXT,
        pass_outcome TEXT,
        pass_length REAL,
        pass_angle REAL,
        pass_height TEXT,
        body_part TEXT,

        location_x REAL,
        location_y REAL,
        end_location_x REAL,
        end_location_y REAL,

        recipient_name TEXT,
        recipient_id TEXT,

        cross INTEGER,
        shot_assist INTEGER,
        goal_assist INTEGER,
        play_pattern TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        FOREIGN KEY (team_id) REFERENCES teams(team_id)
    )
    ''')

    # ============================================================
    # 9. 球员比赛统计表 (player_match_stats)
    # ============================================================
    print("[9/17] 创建球员比赛统计表 (player_match_stats)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_match_stats (
        stat_id INTEGER PRIMARY KEY,
        match_id TEXT NOT NULL,
        sb_match_id INTEGER,

        team_id INTEGER,
        team_name TEXT,
        player_id TEXT,
        player_name TEXT,
        player_nickname TEXT,

        jersey_number INTEGER,
        position TEXT,
        country TEXT,

        -- 传球统计
        passes INTEGER,
        pass_complete INTEGER,
        pass_completion_rate REAL,

        -- 射门统计
        shots INTEGER,
        shots_on_target INTEGER,
        xg REAL,

        -- 防守统计
        pressures INTEGER,
        interceptions INTEGER,
        clearances INTEGER,
        blocks INTEGER,

        -- 进攻统计
        carries INTEGER,
        dribbles_success INTEGER,
        dribbles_attempted INTEGER,

        -- 其他统计
        fouls_committed INTEGER,
        fouls_won INTEGER,
        dispossessed INTEGER,
        miscontrol INTEGER,
        ball_recovery INTEGER,

        -- 助攻/关键传球
        assists INTEGER,
        key_passes INTEGER,
        crosses INTEGER,

        -- 牌
        yellow_card INTEGER,
        red_card INTEGER,

        minutes_played REAL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        FOREIGN KEY (team_id) REFERENCES teams(team_id)
    )
    ''')

    # ============================================================
    # 10. 积分榜表 (standings)
    # ============================================================
    print("[10/17] 创建积分榜表 (standings)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS standings (
        standing_id INTEGER PRIMARY KEY,
        season_id INTEGER NOT NULL,
        league_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,

        position INTEGER,

        played INTEGER DEFAULT 0,
        won INTEGER DEFAULT 0,
        drawn INTEGER DEFAULT 0,
        lost INTEGER DEFAULT 0,
        goals_for INTEGER DEFAULT 0,
        goals_against INTEGER DEFAULT 0,
        goal_diff INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,

        form TEXT,

        -- 主客场分榜
        home_played INTEGER DEFAULT 0,
        home_won INTEGER DEFAULT 0,
        home_drawn INTEGER DEFAULT 0,
        home_lost INTEGER DEFAULT 0,
        home_goals_for INTEGER DEFAULT 0,
        home_goals_against INTEGER DEFAULT 0,
        home_points INTEGER DEFAULT 0,

        away_played INTEGER DEFAULT 0,
        away_won INTEGER DEFAULT 0,
        away_drawn INTEGER DEFAULT 0,
        away_lost INTEGER DEFAULT 0,
        away_goals_for INTEGER DEFAULT 0,
        away_goals_against INTEGER DEFAULT 0,
        away_points INTEGER DEFAULT 0,

        -- 高级数据
        xpts REAL,
        last_5_points INTEGER,
        last_10_points INTEGER,

        standing_type TEXT DEFAULT 'total',

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (season_id) REFERENCES seasons(season_id),
        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        UNIQUE(season_id, team_id, standing_type)
    )
    ''')

    # ============================================================
    # 11. 小组积分榜表 (group_standings)
    # ============================================================
    print("[11/17] 创建小组积分榜表 (group_standings)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS group_standings (
        standing_id INTEGER PRIMARY KEY,
        season_id INTEGER NOT NULL,
        league_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        team_id INTEGER NOT NULL,

        position INTEGER,
        played INTEGER DEFAULT 0,
        won INTEGER DEFAULT 0,
        drawn INTEGER DEFAULT 0,
        lost INTEGER DEFAULT 0,
        goals_for INTEGER DEFAULT 0,
        goals_against INTEGER DEFAULT 0,
        goal_diff INTEGER DEFAULT 0,
        points INTEGER DEFAULT 0,

        qualified INTEGER DEFAULT 0,
        qualification_type TEXT,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (season_id) REFERENCES seasons(season_id),
        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        UNIQUE(season_id, group_name, team_id)
    )
    ''')

    # ============================================================
    # 12. 淘汰赛对阵表 (knockout_brackets)
    # ============================================================
    print("[12/17] 创建淘汰赛对阵表 (knockout_brackets)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS knockout_brackets (
        bracket_id INTEGER PRIMARY KEY,
        season_id INTEGER NOT NULL,
        league_id INTEGER NOT NULL,

        stage TEXT NOT NULL,
        stage_order INTEGER,
        bracket_position INTEGER,

        team1_id INTEGER,
        team2_id INTEGER,

        match1_id INTEGER,
        match2_id INTEGER,

        winner_team_id INTEGER,
        aggregate_score TEXT,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (season_id) REFERENCES seasons(season_id),
        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        FOREIGN KEY (team1_id) REFERENCES teams(team_id),
        FOREIGN KEY (team2_id) REFERENCES teams(team_id),
        FOREIGN KEY (match1_id) REFERENCES matches(match_id),
        FOREIGN KEY (match2_id) REFERENCES matches(match_id),
        UNIQUE(season_id, stage, bracket_position)
    )
    ''')

    # ============================================================
    # 13. Elo评分表 (elo_ratings)
    # ============================================================
    print("[13/17] 创建Elo评分表 (elo_ratings)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS elo_ratings (
        team_id INTEGER PRIMARY KEY,
        elo_rating REAL NOT NULL DEFAULT 1500,
        elo_change REAL DEFAULT 0,
        matches_count INTEGER DEFAULT 0,
        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (team_id) REFERENCES teams(team_id)
    )
    ''')

    # ============================================================
    # 14. Elo历史表 (elo_history)
    # ============================================================
    print("[14/17] 创建Elo历史表 (elo_history)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS elo_history (
        id INTEGER PRIMARY KEY,
        team_id INTEGER NOT NULL,
        elo_rating REAL NOT NULL,
        elo_change REAL DEFAULT 0,
        match_id INTEGER,
        match_date DATE,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        FOREIGN KEY (match_id) REFERENCES matches(match_id)
    )
    ''')

    # ============================================================
    # 15. 联赛规则表 (league_rules)
    # ============================================================
    print("[15/17] 创建联赛规则表 (league_rules)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS league_rules (
        rule_id INTEGER PRIMARY KEY,
        league_id INTEGER NOT NULL,
        season TEXT,

        teams_count INTEGER,
        matches_per_team INTEGER,

        champions_league_spots INTEGER,
        europa_league_spots INTEGER,
        conference_league_spots INTEGER,
        promotion_spots INTEGER,
        relegation_spots INTEGER,
        playoff_spots INTEGER,

        rules_text TEXT,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (league_id) REFERENCES leagues(league_id),
        UNIQUE(league_id, season)
    )
    ''')

    # ============================================================
    # 16. FIFA排名表 (fifa_rankings)
    # ============================================================
    print("[16/17] 创建FIFA排名表 (fifa_rankings)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fifa_rankings (
        ranking_id INTEGER PRIMARY KEY,
        rank_date DATE NOT NULL,
        team_id INTEGER NOT NULL,

        rank INTEGER,
        points REAL,
        previous_rank INTEGER,
        previous_points REAL,
        movement INTEGER,

        confederation TEXT,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        UNIQUE(rank_date, team_id)
    )
    ''')

    # ============================================================
    # 17. 球员主表 (players)
    # ============================================================
    print("[17/23] 创建球员主表 (players)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY,
        player_code TEXT UNIQUE,

        name_en TEXT NOT NULL,
        name_cn TEXT,
        full_name TEXT,

        nationality TEXT,
        nationality_cn TEXT,
        birth_date DATE,
        birth_place TEXT,

        height INTEGER,
        weight INTEGER,
        foot TEXT,

        position_main TEXT,
        position_secondary TEXT,

        status TEXT DEFAULT 'active',

        sm_player_id INTEGER,
        fd_player_id INTEGER,
        sb_player_id TEXT,

        logo_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # ============================================================
    # 18. 球队资讯表 (team_news) — NEWS_AND_FACTORS_DESIGN.md
    # ============================================================
    print("[18/23] 创建球队资讯表 (team_news)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_news (
        news_id INTEGER PRIMARY KEY,
        team_id INTEGER NOT NULL,

        title TEXT NOT NULL,
        content TEXT,
        news_type TEXT NOT NULL,
        category TEXT NOT NULL,

        impact_level INTEGER,
        impact_type TEXT,
        affected_players TEXT,

        news_date DATE NOT NULL,
        news_time TIME,

        related_match_id INTEGER,

        source TEXT,
        source_url TEXT,

        verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        FOREIGN KEY (related_match_id) REFERENCES matches(match_id)
    )
    ''')

    # ============================================================
    # 19. 球员状态表 (player_status) — NEWS_AND_FACTORS_DESIGN.md
    # ============================================================
    print("[19/23] 创建球员状态表 (player_status)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_status (
        status_id INTEGER PRIMARY KEY,
        player_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,

        status TEXT NOT NULL,
        status_detail TEXT,

        injury_type TEXT,
        injury_severity TEXT,
        expected_return DATE,

        suspension_reason TEXT,
        suspension_matches INTEGER,

        appearance_probability REAL,

        team_impact_score REAL,
        replacement_quality TEXT,

        source TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (player_id) REFERENCES players(player_id),
        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        UNIQUE(player_id)
    )
    ''')

    # ============================================================
    # 20. 球队状态汇总表 (team_status_summary) — NEWS_AND_FACTORS_DESIGN.md
    # ============================================================
    print("[20/23] 创建球队状态汇总表 (team_status_summary)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_status_summary (
        summary_id INTEGER PRIMARY KEY,
        team_id INTEGER NOT NULL,

        squad_health_score REAL,
        first_team_available INTEGER,
        first_team_injured INTEGER,
        first_team_suspended INTEGER,

        key_players_available INTEGER,
        key_players_absent INTEGER,
        key_absent_names TEXT,

        recent_news_count INTEGER,
        positive_news_count INTEGER,
        negative_news_count INTEGER,

        morale_score REAL,
        stability_score REAL,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (team_id) REFERENCES teams(team_id),
        UNIQUE(team_id)
    )
    ''')

    # ============================================================
    # 21. 比赛前瞻分析表 (match_preview_analysis) — NEWS_AND_FACTORS_DESIGN.md
    # ============================================================
    print("[21/23] 创建比赛前瞻分析表 (match_preview_analysis)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS match_preview_analysis (
        analysis_id INTEGER PRIMARY KEY,
        match_id INTEGER NOT NULL,

        home_squad_health REAL,
        home_key_absent TEXT,
        home_morale_score REAL,
        home_recent_news TEXT,
        home_advantage_factors TEXT,
        home_disadvantage_factors TEXT,

        away_squad_health REAL,
        away_key_absent TEXT,
        away_morale_score REAL,
        away_recent_news TEXT,
        away_advantage_factors TEXT,
        away_disadvantage_factors TEXT,

        home_adjustment REAL,
        away_adjustment REAL,

        adjusted_home_win_prob REAL,
        adjusted_draw_prob REAL,
        adjusted_away_win_prob REAL,

        key_factors TEXT,
        recommendation TEXT,
        confidence REAL,

        analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        UNIQUE(match_id)
    )
    ''')

    # ============================================================
    # 22. 教练变动表 (coach_changes) — NEWS_AND_FACTORS_DESIGN.md
    # ============================================================
    print("[22/23] 创建教练变动表 (coach_changes)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS coach_changes (
        change_id INTEGER PRIMARY KEY,
        team_id INTEGER NOT NULL,

        change_type TEXT NOT NULL,

        old_coach_name TEXT,
        new_coach_name TEXT,

        change_date DATE NOT NULL,

        reason TEXT,

        expected_impact TEXT,
        impact_reason TEXT,

        source TEXT,
        source_url TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (team_id) REFERENCES teams(team_id)
    )
    ''')

    # ============================================================
    # 23. 转会记录表 (transfers) — NEWS_AND_FACTORS_DESIGN.md
    # ============================================================
    print("[23/23] 创建转会记录表 (transfers)...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transfers (
        transfer_id INTEGER PRIMARY KEY,
        player_id INTEGER,
        player_name TEXT,

        transfer_type TEXT NOT NULL,

        from_team_id INTEGER,
        to_team_id INTEGER,
        from_team_name TEXT,
        to_team_name TEXT,

        transfer_date DATE NOT NULL,
        transfer_window TEXT,

        transfer_fee INTEGER,
        transfer_fee_text TEXT,

        team_impact TEXT,
        impact_detail TEXT,

        source TEXT,
        source_url TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (player_id) REFERENCES players(player_id),
        FOREIGN KEY (from_team_id) REFERENCES teams(team_id),
        FOREIGN KEY (to_team_id) REFERENCES teams(team_id)
    )
    ''')

    # ============================================================
    # 创建索引
    # ============================================================
    print("\n创建索引...")
    indexes = [
        # leagues
        ('idx_leagues_competition_type', 'leagues(competition_type)'),
        ('idx_leagues_participant_type', 'leagues(participant_type)'),

        # seasons
        ('idx_seasons_league_id', 'seasons(league_id)'),
        ('idx_seasons_status', 'seasons(status)'),

        # teams
        ('idx_teams_team_type', 'teams(team_type)'),
        ('idx_teams_country', 'teams(country)'),

        # team_aliases
        ('idx_team_aliases_alias_name', 'team_aliases(alias_name)'),
        ('idx_team_aliases_team_id', 'team_aliases(team_id)'),

        # matches
        ('idx_matches_season_id', 'matches(season_id)'),
        ('idx_matches_league_id', 'matches(league_id)'),
        ('idx_matches_date', 'matches(match_date)'),
        ('idx_matches_status', 'matches(status)'),
        ('idx_matches_home_team', 'matches(home_team_id)'),
        ('idx_matches_away_team', 'matches(away_team_id)'),
        ('idx_matches_code', 'matches(match_code)'),
        ('idx_matches_teams_date', 'matches(home_team_id, away_team_id, match_date)'),

        # match_odds
        ('idx_odds_match', 'match_odds(match_id)'),

        # statsbomb_shots
        ('idx_shots_match', 'statsbomb_shots(match_id)'),
        ('idx_shots_team', 'statsbomb_shots(team_id)'),
        ('idx_shots_player', 'statsbomb_shots(player_id)'),

        # statsbomb_passes
        ('idx_passes_match', 'statsbomb_passes(match_id)'),
        ('idx_passes_team', 'statsbomb_passes(team_id)'),
        ('idx_passes_player', 'statsbomb_passes(player_id)'),

        # player_match_stats
        ('idx_pms_match', 'player_match_stats(match_id)'),
        ('idx_pms_team', 'player_match_stats(team_id)'),
        ('idx_pms_player', 'player_match_stats(player_id)'),

        # standings
        ('idx_standings_season', 'standings(season_id)'),
        ('idx_standings_position', 'standings(season_id, position)'),

        # group_standings
        ('idx_group_standings_season', 'group_standings(season_id)'),
        ('idx_group_standings_group', 'group_standings(season_id, group_name)'),

        # knockout_brackets
        ('idx_knockout_season', 'knockout_brackets(season_id)'),
        ('idx_knockout_stage', 'knockout_brackets(season_id, stage)'),

        # elo_history
        ('idx_elo_history_team', 'elo_history(team_id, match_date)'),

        # fifa_rankings
        ('idx_fifa_rankings_date', 'fifa_rankings(rank_date)'),
        ('idx_fifa_rankings_team', 'fifa_rankings(team_id, rank_date)'),

        # players
        ('idx_players_nationality', 'players(nationality)'),
        ('idx_players_position', 'players(position_main)'),

        # team_news
        ('idx_team_news_team', 'team_news(team_id, news_date)'),
        ('idx_team_news_type', 'team_news(news_type, category)'),
        ('idx_team_news_match', 'team_news(related_match_id)'),

        # player_status
        ('idx_player_status_team', 'player_status(team_id)'),
        ('idx_player_status_status', 'player_status(status)'),

        # team_status_summary
        ('idx_team_status_health', 'team_status_summary(squad_health_score)'),

        # coach_changes
        ('idx_coach_changes_team', 'coach_changes(team_id, change_date)'),

        # transfers
        ('idx_transfers_team_in', 'transfers(to_team_id, transfer_date)'),
        ('idx_transfers_team_out', 'transfers(from_team_id, transfer_date)'),
    ]

    for idx_name, idx_sql in indexes:
        cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_sql}')

    conn.commit()
    print("\n数据库表创建完成！")

    # 打印表结构摘要
    print("\n" + "=" * 70)
    print("数据库结构摘要")
    print("=" * 70)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"\n{table}: {len(columns)} 列, {count} 行")

    return conn


def verify_database(conn):
    """验证数据库结构"""
    cursor = conn.cursor()

    print("\n" + "=" * 70)
    print("验证数据库完整性")
    print("=" * 70)

    # 检查外键约束
    cursor.execute("PRAGMA foreign_key_check")
    fk_errors = cursor.fetchall()
    if fk_errors:
        print(f"外键约束错误: {len(fk_errors)} 个")
        for err in fk_errors[:5]:
            print(f"  - {err}")
    else:
        print("外键约束: OK")

    # 检查表结构
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"表数量: {len(tables)}")

    # 检查索引
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
    indexes = [row[0] for row in cursor.fetchall()]
    print(f"索引数量: {len(indexes)}")

    print("\n数据库验证完成！")


if __name__ == '__main__':
    conn = create_database()
    verify_database(conn)
    conn.close()

    print(f"\n数据库文件: {OUTPUT_DB}")
    print("完成！")
