"""
数据库表结构定义和字段映射
记录每个表的字段、含义，以及API字段到数据库字段的映射关系
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ColumnDef:
    """列定义"""
    name: str                # 数据库字段名
    dtype: str               # 数据类型
    name_cn: str = ""        # 中文名
    description: str = ""    # 描述
    is_pk: bool = False      # 是否主键
    is_nullable: bool = True # 是否可空
    default: str = ""        # 默认值


@dataclass
class TableDef:
    """表定义"""
    name: str                # 表名
    name_cn: str             # 中文名
    description: str = ""    # 描述
    columns: List[ColumnDef] = field(default_factory=list)
    count: int = 0           # 记录数


# ==================== 数据库表定义 ====================

TABLES: Dict[str, TableDef] = {
    "matches": TableDef(
        name="matches", name_cn="比赛", count=55942,
        description="核心比赛数据表，包含比分、统计、赔率等",
        columns=[
            ColumnDef("match_id", "TEXT", "比赛ID", is_pk=True, is_nullable=False),
            ColumnDef("match_code", "TEXT", "比赛编码"),
            ColumnDef("season_id", "INTEGER", "赛季ID"),
            ColumnDef("league_id", "INTEGER", "联赛ID", is_nullable=False),
            ColumnDef("match_date", "DATE", "比赛日期", is_nullable=False),
            ColumnDef("match_time", "TIME", "比赛时间"),
            ColumnDef("round_num", "INTEGER", "轮次"),
            ColumnDef("round_stage", "TEXT", "轮次阶段"),
            ColumnDef("stage_type", "TEXT", "阶段类型"),
            ColumnDef("group_name", "TEXT", "分组名"),
            ColumnDef("leg", "INTEGER", "回合(主客场)"),
            ColumnDef("aggregate_home", "INTEGER", "主队总进球"),
            ColumnDef("aggregate_away", "INTEGER", "客队总进球"),
            ColumnDef("home_team_id", "INTEGER", "主队ID", is_nullable=False),
            ColumnDef("away_team_id", "INTEGER", "客队ID", is_nullable=False),
            ColumnDef("venue", "TEXT", "球场"),
            ColumnDef("venue_city", "TEXT", "城市"),
            ColumnDef("neutral", "INTEGER", "是否中立场地"),
            # 比分
            ColumnDef("home_goals", "INTEGER", "主队进球"),
            ColumnDef("away_goals", "INTEGER", "客队进球"),
            ColumnDef("result", "TEXT", "结果(H/D/A)"),
            ColumnDef("home_goals_ht", "INTEGER", "半场主队进球"),
            ColumnDef("away_goals_ht", "INTEGER", "半场客队进球"),
            ColumnDef("home_goals_et", "INTEGER", "加时主队进球"),
            ColumnDef("away_goals_et", "INTEGER", "加时客队进球"),
            ColumnDef("home_penalties", "INTEGER", "主队点球"),
            ColumnDef("away_penalties", "INTEGER", "客队点球"),
            # 统计
            ColumnDef("home_shots", "INTEGER", "主队射门"),
            ColumnDef("away_shots", "INTEGER", "客队射门"),
            ColumnDef("home_shots_target", "INTEGER", "主队射正"),
            ColumnDef("away_shots_target", "INTEGER", "客队射正"),
            ColumnDef("home_corners", "INTEGER", "主队角球"),
            ColumnDef("away_corners", "INTEGER", "客队角球"),
            ColumnDef("home_fouls", "INTEGER", "主队犯规"),
            ColumnDef("away_fouls", "INTEGER", "客队犯规"),
            ColumnDef("home_yellow", "INTEGER", "主队黄牌"),
            ColumnDef("away_yellow", "INTEGER", "客队黄牌"),
            ColumnDef("home_red", "INTEGER", "主队红牌"),
            ColumnDef("away_red", "INTEGER", "客队红牌"),
            ColumnDef("home_possession", "REAL", "主队控球率"),
            ColumnDef("away_possession", "REAL", "客队控球率"),
            ColumnDef("home_passes", "INTEGER", "主队传球"),
            ColumnDef("away_passes", "INTEGER", "客队传球"),
            ColumnDef("home_pass_accuracy", "REAL", "主队传球成功率"),
            ColumnDef("away_pass_accuracy", "REAL", "客队传球成功率"),
            # xG
            ColumnDef("home_xg", "REAL", "主队xG"),
            ColumnDef("away_xg", "REAL", "客队xG"),
            ColumnDef("home_xgot", "REAL", "主队xGOT"),
            ColumnDef("away_xgot", "REAL", "客队xGOT"),
            ColumnDef("home_npxg", "REAL", "主队非点球xG"),
            ColumnDef("away_npxg", "REAL", "客队非点球xG"),
            # 高级统计
            ColumnDef("home_passes_total", "INTEGER", "主队总传球"),
            ColumnDef("away_passes_total", "INTEGER", "客队总传球"),
            ColumnDef("home_pass_complete", "INTEGER", "主队成功传球"),
            ColumnDef("away_pass_complete", "INTEGER", "客队成功传球"),
            ColumnDef("home_pass_completion_rate", "REAL", "主队传球成功率"),
            ColumnDef("away_pass_completion_rate", "REAL", "客队传球成功率"),
            ColumnDef("home_pressures", "INTEGER", "主队压迫"),
            ColumnDef("away_pressures", "INTEGER", "客队压迫"),
            ColumnDef("home_carries", "INTEGER", "主队带球"),
            ColumnDef("away_carries", "INTEGER", "客队带球"),
            ColumnDef("home_dribbles_success", "INTEGER", "主队成功过人"),
            ColumnDef("away_dribbles_success", "INTEGER", "客队成功过人"),
            ColumnDef("home_dribbles_attempted", "INTEGER", "主队尝试过人"),
            ColumnDef("away_dribbles_attempted", "INTEGER", "客队尝试过人"),
            ColumnDef("home_interceptions", "INTEGER", "主队拦截"),
            ColumnDef("away_interceptions", "INTEGER", "客队拦截"),
            ColumnDef("home_clearances", "INTEGER", "主队解围"),
            ColumnDef("away_clearances", "INTEGER", "客队解围"),
            ColumnDef("home_blocks", "INTEGER", "主队封堵"),
            ColumnDef("away_blocks", "INTEGER", "客队封堵"),
            ColumnDef("home_ball_recovery", "INTEGER", "主队夺回球权"),
            ColumnDef("away_ball_recovery", "INTEGER", "客队夺回球权"),
            ColumnDef("home_crosses", "INTEGER", "主队传中"),
            ColumnDef("away_crosses", "INTEGER", "客队传中"),
            ColumnDef("home_key_passes", "INTEGER", "主队关键传球"),
            ColumnDef("away_key_passes", "INTEGER", "客队关键传球"),
            # 其他
            ColumnDef("referee", "TEXT", "裁判"),
            ColumnDef("attendance", "INTEGER", "上座率"),
            # 赔率
            ColumnDef("odds_home", "REAL", "主胜赔率"),
            ColumnDef("odds_draw", "REAL", "平局赔率"),
            ColumnDef("odds_away", "REAL", "客胜赔率"),
            ColumnDef("odds_home_closing", "REAL", "主胜收盘赔率"),
            ColumnDef("odds_draw_closing", "REAL", "平局收盘赔率"),
            ColumnDef("odds_away_closing", "REAL", "客胜收盘赔率"),
            # 状态
            ColumnDef("status", "TEXT", "比赛状态", is_nullable=False),
            ColumnDef("time_type", "TEXT", "时间类型(local/beijing/utc)"),
            ColumnDef("source", "TEXT", "数据来源"),
        ]
    ),

    "teams": TableDef(
        name="teams", name_cn="球队", count=1167,
        description="球队基础信息",
        columns=[
            ColumnDef("team_id", "INTEGER", "球队ID", is_pk=True),
            ColumnDef("team_code", "TEXT", "球队编码"),
            ColumnDef("name_en", "TEXT", "英文名", is_nullable=False),
            ColumnDef("name_cn", "TEXT", "中文名"),
            ColumnDef("short_name", "TEXT", "简称"),
            ColumnDef("tla", "TEXT", "三字缩写"),
            ColumnDef("team_type", "TEXT", "类型(club/national)", is_nullable=False),
            ColumnDef("country", "TEXT", "国家"),
            ColumnDef("country_cn", "TEXT", "国家中文名"),
            ColumnDef("primary_league_id", "INTEGER", "主联赛ID"),
            ColumnDef("founded_year", "INTEGER", "成立年份"),
            ColumnDef("stadium", "TEXT", "主场"),
            ColumnDef("stadium_capacity", "INTEGER", "主场容量"),
            ColumnDef("confederation", "TEXT", "足联"),
            ColumnDef("fifa_code", "TEXT", "FIFA代码"),
            ColumnDef("sm_team_id", "INTEGER", "SportMonks ID"),
            ColumnDef("fd_team_id", "INTEGER", "Football-Data ID"),
            ColumnDef("tsdb_team_id", "INTEGER", "TheSportsDB ID"),
            ColumnDef("sb_team_id", "TEXT", "StatsBomb ID"),
            ColumnDef("logo_url", "TEXT", "队徽URL"),
        ]
    ),

    "leagues": TableDef(
        name="leagues", name_cn="联赛", count=176,
        description="联赛/杯赛基础信息",
        columns=[
            ColumnDef("league_id", "INTEGER", "联赛ID", is_pk=True),
            ColumnDef("league_code", "TEXT", "联赛编码"),
            ColumnDef("name_en", "TEXT", "英文名", is_nullable=False),
            ColumnDef("name_cn", "TEXT", "中文名"),
            ColumnDef("country", "TEXT", "国家"),
            ColumnDef("country_cn", "TEXT", "国家中文名"),
            ColumnDef("competition_type", "TEXT", "类型(league/cup)", is_nullable=False),
            ColumnDef("participant_type", "TEXT", "参赛类型(club/national)", is_nullable=False),
            ColumnDef("format_type", "TEXT", "赛制(round_robin/knockout)", is_nullable=False),
            ColumnDef("tier", "INTEGER", "级别(1=顶级)"),
            ColumnDef("is_international", "INTEGER", "是否国际赛事"),
            ColumnDef("cycle_type", "TEXT", "周期(annual/biennial)"),
            ColumnDef("sm_league_id", "INTEGER", "SportMonks ID"),
            ColumnDef("fd_comp_code", "TEXT", "Football-Data代码"),
            ColumnDef("tsdb_league_id", "INTEGER", "TheSportsDB ID"),
            ColumnDef("logo_url", "TEXT", "Logo URL"),
        ]
    ),

    "standings": TableDef(
        name="standings", name_cn="积分榜", count=1992,
        description="联赛积分榜，含主客场分拆",
        columns=[
            ColumnDef("standing_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("season_id", "INTEGER", "赛季ID", is_nullable=False),
            ColumnDef("league_id", "INTEGER", "联赛ID", is_nullable=False),
            ColumnDef("team_id", "INTEGER", "球队ID", is_nullable=False),
            ColumnDef("position", "INTEGER", "排名"),
            ColumnDef("played", "INTEGER", "已赛"),
            ColumnDef("won", "INTEGER", "胜"),
            ColumnDef("drawn", "INTEGER", "平"),
            ColumnDef("lost", "INTEGER", "负"),
            ColumnDef("goals_for", "INTEGER", "进球"),
            ColumnDef("goals_against", "INTEGER", "失球"),
            ColumnDef("goal_diff", "INTEGER", "净胜球"),
            ColumnDef("points", "INTEGER", "积分"),
            ColumnDef("form", "TEXT", "近期战绩(WDLWD)"),
            ColumnDef("home_played", "INTEGER", "主场已赛"),
            ColumnDef("home_won", "INTEGER", "主场胜"),
            ColumnDef("home_drawn", "INTEGER", "主场平"),
            ColumnDef("home_lost", "INTEGER", "主场负"),
            ColumnDef("home_goals_for", "INTEGER", "主场进球"),
            ColumnDef("home_goals_against", "INTEGER", "主场失球"),
            ColumnDef("home_points", "INTEGER", "主场积分"),
            ColumnDef("away_played", "INTEGER", "客场已赛"),
            ColumnDef("away_won", "INTEGER", "客场胜"),
            ColumnDef("away_drawn", "INTEGER", "客场平"),
            ColumnDef("away_lost", "INTEGER", "客场负"),
            ColumnDef("away_goals_for", "INTEGER", "客场进球"),
            ColumnDef("away_goals_against", "INTEGER", "客场失球"),
            ColumnDef("away_points", "INTEGER", "客场积分"),
            ColumnDef("xpts", "REAL", "期望积分"),
            ColumnDef("last_5_points", "INTEGER", "近5轮积分"),
            ColumnDef("last_10_points", "INTEGER", "近10轮积分"),
            ColumnDef("standing_type", "TEXT", "类型(total/home/away)"),
        ]
    ),

    "match_odds": TableDef(
        name="match_odds", name_cn="比赛赔率", count=18467,
        description="比赛赔率数据，含胜平负/大小球/亚盘/半全场",
        columns=[
            ColumnDef("odds_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("match_id", "TEXT", "比赛ID", is_nullable=False),
            # 胜平负
            ColumnDef("b365_home", "REAL", "Bet365主胜"),
            ColumnDef("b365_draw", "REAL", "Bet365平局"),
            ColumnDef("b365_away", "REAL", "Bet365客胜"),
            ColumnDef("ps_home", "REAL", "Pinnacle主胜"),
            ColumnDef("ps_draw", "REAL", "Pinnacle平局"),
            ColumnDef("ps_away", "REAL", "Pinnacle客胜"),
            ColumnDef("max_home", "REAL", "最高主胜"),
            ColumnDef("max_draw", "REAL", "最高平局"),
            ColumnDef("max_away", "REAL", "最高客胜"),
            ColumnDef("avg_home", "REAL", "平均主胜"),
            ColumnDef("avg_draw", "REAL", "平均平局"),
            ColumnDef("avg_away", "REAL", "平均客胜"),
            # 大小球
            ColumnDef("b365_over_2_5", "REAL", "Bet365大2.5"),
            ColumnDef("b365_under_2_5", "REAL", "Bet365小2.5"),
            ColumnDef("ps_over_2_5", "REAL", "Pinnacle大2.5"),
            ColumnDef("ps_under_2_5", "REAL", "Pinnacle小2.5"),
            ColumnDef("max_over_2_5", "REAL", "最高大2.5"),
            ColumnDef("max_under_2_5", "REAL", "最高小2.5"),
            ColumnDef("avg_over_2_5", "REAL", "平均大2.5"),
            ColumnDef("avg_under_2_5", "REAL", "平均小2.5"),
            # 亚盘
            ColumnDef("asian_handicap", "REAL", "亚盘让球"),
            ColumnDef("b365_ah_home", "REAL", "Bet365亚盘主"),
            ColumnDef("b365_ah_away", "REAL", "Bet365亚盘客"),
            ColumnDef("ps_ah_home", "REAL", "Pinnacle亚盘主"),
            ColumnDef("ps_ah_away", "REAL", "Pinnacle亚盘客"),
            ColumnDef("max_ah_home", "REAL", "最高亚盘主"),
            ColumnDef("max_ah_away", "REAL", "最高亚盘客"),
            ColumnDef("avg_ah_home", "REAL", "平均亚盘主"),
            ColumnDef("avg_ah_away", "REAL", "平均亚盘客"),
            # 半全场
            ColumnDef("b365_c_home", "REAL", "Bet365半全场主主"),
            ColumnDef("b365_c_draw", "REAL", "Bet365半全场主平"),
            ColumnDef("b365_c_away", "REAL", "Bet365半全场主客"),
            ColumnDef("ps_c_home", "REAL", "Pinnacle半全场主主"),
            ColumnDef("ps_c_draw", "REAL", "Pinnacle半全场主平"),
            ColumnDef("ps_c_away", "REAL", "Pinnacle半全场主客"),
            ColumnDef("max_c_home", "REAL", "最高半全场主主"),
            ColumnDef("max_c_draw", "REAL", "最高半全场主平"),
            ColumnDef("max_c_away", "REAL", "最高半全场主客"),
            ColumnDef("avg_c_home", "REAL", "平均半全场主主"),
            ColumnDef("avg_c_draw", "REAL", "平均半全场主平"),
            ColumnDef("avg_c_away", "REAL", "平均半全场主客"),
        ]
    ),

    "players": TableDef(
        name="players", name_cn="球员", count=5614,
        description="球员基础信息",
        columns=[
            ColumnDef("player_id", "INTEGER", "球员ID", is_pk=True),
            ColumnDef("player_code", "TEXT", "球员编码"),
            ColumnDef("name_en", "TEXT", "英文名", is_nullable=False),
            ColumnDef("name_cn", "TEXT", "中文名"),
            ColumnDef("full_name", "TEXT", "全名"),
            ColumnDef("nationality", "TEXT", "国籍"),
            ColumnDef("nationality_cn", "TEXT", "国籍中文名"),
            ColumnDef("birth_date", "DATE", "出生日期"),
            ColumnDef("birth_place", "TEXT", "出生地"),
            ColumnDef("height", "INTEGER", "身高(cm)"),
            ColumnDef("weight", "INTEGER", "体重(kg)"),
            ColumnDef("foot", "TEXT", "惯用脚"),
            ColumnDef("position_main", "TEXT", "主位置"),
            ColumnDef("position_secondary", "TEXT", "副位置"),
            ColumnDef("status", "TEXT", "状态(active/injured)"),
            ColumnDef("sm_player_id", "INTEGER", "SportMonks ID"),
            ColumnDef("fd_player_id", "INTEGER", "Football-Data ID"),
            ColumnDef("sb_player_id", "TEXT", "StatsBomb ID"),
            ColumnDef("logo_url", "TEXT", "头像URL"),
        ]
    ),

    "player_match_stats": TableDef(
        name="player_match_stats", name_cn="球员比赛统计", count=25879,
        description="球员单场比赛详细统计",
        columns=[
            ColumnDef("stat_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("match_id", "TEXT", "比赛ID", is_nullable=False),
            ColumnDef("team_id", "INTEGER", "球队ID"),
            ColumnDef("player_id", "TEXT", "球员ID"),
            ColumnDef("player_name", "TEXT", "球员名"),
            ColumnDef("jersey_number", "INTEGER", "球衣号"),
            ColumnDef("position", "TEXT", "位置"),
            ColumnDef("passes", "INTEGER", "传球"),
            ColumnDef("pass_complete", "INTEGER", "成功传球"),
            ColumnDef("pass_completion_rate", "REAL", "传球成功率"),
            ColumnDef("shots", "INTEGER", "射门"),
            ColumnDef("shots_on_target", "INTEGER", "射正"),
            ColumnDef("xg", "REAL", "xG"),
            ColumnDef("pressures", "INTEGER", "压迫"),
            ColumnDef("interceptions", "INTEGER", "拦截"),
            ColumnDef("clearances", "INTEGER", "解围"),
            ColumnDef("blocks", "INTEGER", "封堵"),
            ColumnDef("carries", "INTEGER", "带球"),
            ColumnDef("dribbles_success", "INTEGER", "成功过人"),
            ColumnDef("dribbles_attempted", "INTEGER", "尝试过人"),
            ColumnDef("assists", "INTEGER", "助攻"),
            ColumnDef("key_passes", "INTEGER", "关键传球"),
            ColumnDef("crosses", "INTEGER", "传中"),
            ColumnDef("yellow_card", "INTEGER", "黄牌"),
            ColumnDef("red_card", "INTEGER", "红牌"),
            ColumnDef("minutes_played", "REAL", "上场时间"),
        ]
    ),

    "league_rules": TableDef(
        name="league_rules", name_cn="联赛规则", count=36,
        description="联赛规则配置，含升降级、欧战名额等",
        columns=[
            ColumnDef("rule_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("league_id", "INTEGER", "联赛ID", is_nullable=False),
            ColumnDef("league_code", "TEXT", "联赛编码"),
            ColumnDef("season", "TEXT", "赛季"),
            ColumnDef("teams_count", "INTEGER", "球队数"),
            ColumnDef("matches_per_team", "INTEGER", "每队比赛数"),
            ColumnDef("format_type", "TEXT", "赛制"),
            ColumnDef("points_for_win", "INTEGER", "胜场积分"),
            ColumnDef("champions_league_spots", "INTEGER", "欧冠名额"),
            ColumnDef("europa_league_spots", "INTEGER", "欧联名额"),
            ColumnDef("conference_league_spots", "INTEGER", "欧会杯名额"),
            ColumnDef("promotion_spots", "INTEGER", "升级名额"),
            ColumnDef("promotion_playoff_spots", "INTEGER", "升级附加赛名额"),
            ColumnDef("relegation_spots", "INTEGER", "降级名额"),
            ColumnDef("relegation_playoff_spots", "INTEGER", "降级附加赛名额"),
            ColumnDef("has_playoffs", "INTEGER", "是否有季后赛"),
            ColumnDef("has_split", "INTEGER", "是否有分段"),
            ColumnDef("season_start_month", "INTEGER", "赛季开始月"),
            ColumnDef("season_end_month", "INTEGER", "赛季结束月"),
            ColumnDef("rules_json", "TEXT", "规则JSON"),
        ]
    ),

    "seasons": TableDef(
        name="seasons", name_cn="赛季", count=197,
        description="赛季信息",
        columns=[
            ColumnDef("season_id", "INTEGER", "赛季ID", is_pk=True),
            ColumnDef("league_id", "INTEGER", "联赛ID", is_nullable=False),
            ColumnDef("season_name", "TEXT", "赛季名", is_nullable=False),
            ColumnDef("year", "INTEGER", "年份"),
            ColumnDef("start_date", "DATE", "开始日期"),
            ColumnDef("end_date", "DATE", "结束日期"),
            ColumnDef("status", "TEXT", "状态(active/finished)"),
        ]
    ),

    "elo_ratings": TableDef(
        name="elo_ratings", name_cn="Elo评分", count=1037,
        description="球队Elo评分",
        columns=[
            ColumnDef("team_id", "INTEGER", "球队ID", is_pk=True),
            ColumnDef("elo_rating", "REAL", "Elo评分", is_nullable=False),
            ColumnDef("elo_change", "REAL", "评分变化"),
            ColumnDef("matches_count", "INTEGER", "比赛数"),
        ]
    ),

    "fifa_rankings": TableDef(
        name="fifa_rankings", name_cn="FIFA排名", count=323,
        description="FIFA国家队/俱乐部排名",
        columns=[
            ColumnDef("ranking_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("rank_date", "DATE", "排名日期", is_nullable=False),
            ColumnDef("team_id", "INTEGER", "球队ID", is_nullable=False),
            ColumnDef("rank", "INTEGER", "排名"),
            ColumnDef("points", "REAL", "积分"),
            ColumnDef("movement", "INTEGER", "排名变化"),
            ColumnDef("confederation", "TEXT", "足联"),
        ]
    ),

    "team_news": TableDef(
        name="team_news", name_cn="球队新闻", count=263,
        description="球队新闻和事件",
        columns=[
            ColumnDef("news_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("team_id", "INTEGER", "球队ID", is_nullable=False),
            ColumnDef("title", "TEXT", "标题", is_nullable=False),
            ColumnDef("content", "TEXT", "内容"),
            ColumnDef("news_type", "TEXT", "类型(injury/transfer/tactical)", is_nullable=False),
            ColumnDef("category", "TEXT", "分类", is_nullable=False),
            ColumnDef("impact_level", "INTEGER", "影响等级(1-5)"),
            ColumnDef("impact_type", "TEXT", "影响类型"),
            ColumnDef("affected_players", "TEXT", "受影响球员"),
            ColumnDef("news_date", "DATE", "日期", is_nullable=False),
            ColumnDef("source", "TEXT", "来源"),
            ColumnDef("verified", "INTEGER", "是否已验证"),
        ]
    ),

    "transfers": TableDef(
        name="transfers", name_cn="转会", count=20,
        description="转会记录",
        columns=[
            ColumnDef("transfer_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("player_id", "INTEGER", "球员ID"),
            ColumnDef("player_name", "TEXT", "球员名"),
            ColumnDef("transfer_type", "TEXT", "类型(transfer/loan/free)", is_nullable=False),
            ColumnDef("from_team_id", "INTEGER", "转出球队ID"),
            ColumnDef("to_team_id", "INTEGER", "转入球队ID"),
            ColumnDef("from_team_name", "TEXT", "转出球队名"),
            ColumnDef("to_team_name", "TEXT", "转入球队名"),
            ColumnDef("transfer_date", "DATE", "转会日期", is_nullable=False),
            ColumnDef("transfer_fee", "INTEGER", "转会费"),
            ColumnDef("transfer_fee_text", "TEXT", "转会费文本"),
        ]
    ),

    "player_status": TableDef(
        name="player_status", name_cn="球员状态", count=1000,
        description="球员伤病/停赛状态",
        columns=[
            ColumnDef("status_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("player_id", "INTEGER", "球员ID", is_nullable=False),
            ColumnDef("team_id", "INTEGER", "球队ID", is_nullable=False),
            ColumnDef("status", "TEXT", "状态(injured/suspended/available)", is_nullable=False),
            ColumnDef("injury_type", "TEXT", "伤病类型"),
            ColumnDef("injury_severity", "TEXT", "严重程度"),
            ColumnDef("expected_return", "DATE", "预计回归日期"),
            ColumnDef("appearance_probability", "REAL", "出场概率"),
        ]
    ),

    "coach_changes": TableDef(
        name="coach_changes", name_cn="教练变更", count=14,
        description="主教练变更记录",
        columns=[
            ColumnDef("change_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("team_id", "INTEGER", "球队ID", is_nullable=False),
            ColumnDef("change_type", "TEXT", "类型(appointed/sacked/resigned)", is_nullable=False),
            ColumnDef("old_coach_name", "TEXT", "前任教练"),
            ColumnDef("new_coach_name", "TEXT", "新任教练"),
            ColumnDef("change_date", "DATE", "变更日期", is_nullable=False),
        ]
    ),

    "group_standings": TableDef(
        name="group_standings", name_cn="小组积分榜", count=339,
        description="杯赛小组赛积分榜",
        columns=[
            ColumnDef("standing_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("season_id", "INTEGER", "赛季ID", is_nullable=False),
            ColumnDef("league_id", "INTEGER", "联赛ID", is_nullable=False),
            ColumnDef("group_name", "TEXT", "组名", is_nullable=False),
            ColumnDef("team_id", "INTEGER", "球队ID", is_nullable=False),
            ColumnDef("position", "INTEGER", "排名"),
            ColumnDef("points", "INTEGER", "积分"),
            ColumnDef("qualified", "INTEGER", "是否出线"),
        ]
    ),

    "knockout_brackets": TableDef(
        name="knockout_brackets", name_cn="淘汰赛对阵", count=15,
        description="淘汰赛对阵图",
        columns=[
            ColumnDef("bracket_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("season_id", "INTEGER", "赛季ID", is_nullable=False),
            ColumnDef("league_id", "INTEGER", "联赛ID", is_nullable=False),
            ColumnDef("stage", "TEXT", "阶段(1/8/1/4/semi/final)", is_nullable=False),
            ColumnDef("team1_id", "INTEGER", "球队1 ID"),
            ColumnDef("team2_id", "INTEGER", "球队2 ID"),
            ColumnDef("winner_team_id", "INTEGER", "胜者ID"),
        ]
    ),

    "statsbomb_shots": TableDef(
        name="statsbomb_shots", name_cn="射门详情", count=14849,
        description="StatsBomb射门详细数据(含xG坐标)",
        columns=[
            ColumnDef("shot_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("match_id", "TEXT", "比赛ID", is_nullable=False),
            ColumnDef("player_name", "TEXT", "球员名"),
            ColumnDef("minute", "INTEGER", "分钟"),
            ColumnDef("xg", "REAL", "xG值"),
            ColumnDef("shot_type", "TEXT", "射门类型"),
            ColumnDef("shot_outcome", "TEXT", "射门结果"),
            ColumnDef("location_x", "REAL", "X坐标"),
            ColumnDef("location_y", "REAL", "Y坐标"),
        ]
    ),

    "statsbomb_passes": TableDef(
        name="statsbomb_passes", name_cn="传球详情", count=582417,
        description="StatsBomb传球详细数据(含坐标)",
        columns=[
            ColumnDef("pass_id", "INTEGER", "ID", is_pk=True),
            ColumnDef("match_id", "TEXT", "比赛ID", is_nullable=False),
            ColumnDef("player_name", "TEXT", "球员名"),
            ColumnDef("minute", "INTEGER", "分钟"),
            ColumnDef("pass_type", "TEXT", "传球类型"),
            ColumnDef("pass_outcome", "TEXT", "传球结果"),
            ColumnDef("location_x", "REAL", "起点X"),
            ColumnDef("location_y", "REAL", "起点Y"),
            ColumnDef("end_location_x", "REAL", "终点X"),
            ColumnDef("end_location_y", "REAL", "终点Y"),
        ]
    ),
}


# ==================== API字段到数据库字段映射 ====================

# API-Sports 返回字段 -> 数据库字段
API_SPORTS_FIELD_MAP: Dict[str, Dict[str, str]] = {
    "matches": {
        "fixture.id": "match_id",
        "fixture.date[:10]": "match_date",
        "fixture.date[11:16]": "match_time",
        "fixture.status.short": "status",
        "league.id": "league_id",
        "league.round": "round_stage",
        "teams.home.id": "home_team_id",
        "teams.home.name": "home_team_name",  # 需要JOIN teams表
        "teams.away.id": "away_team_id",
        "teams.away.name": "away_team_name",  # 需要JOIN teams表
        "goals.home": "home_goals",
        "goals.away": "away_goals",
        "score.halftime.home": "home_goals_ht",
        "score.halftime.away": "away_goals_ht",
        "score.extratime.home": "home_goals_et",
        "score.extratime.away": "away_goals_et",
        "score.penalty.home": "home_penalties",
        "score.penalty.away": "away_penalties",
        "fixture.venue.name": "venue",
        "fixture.venue.city": "venue_city",
        "fixture.referee": "referee",
    },
    "teams": {
        "team.id": "team_id",
        "team.name": "name_en",
        "team.country": "country",
        "team.founded": "founded_year",
        "team.logo": "logo_url",
        "venue.name": "stadium",
        "venue.capacity": "stadium_capacity",
    },
    "standings": {
        "league.id": "league_id",
        "league.season": "season_year",
        "team.id": "team_id",
        "team.name": "team_name",  # 需要JOIN teams表
        "rank": "position",
        "points": "points",
        "all.played": "played",
        "all.win": "won",
        "all.draw": "drawn",
        "all.lose": "lost",
        "all.goals.for": "goals_for",
        "all.goals.against": "goals_against",
        "goalsDiff": "goal_diff",
        "form": "form",
        "all.win.home": "home_won",
        "all.draw.home": "home_drawn",
        "all.lose.home": "home_lost",
        "all.goals.for.home": "home_goals_for",
        "all.goals.against.home": "home_goals_against",
    },
    "statistics": {
        "type": "stat_type",
        "value": "stat_value",
        # 需要映射到 matches 表的对应字段
        "Shots on Goal": "home_shots_target/away_shots_target",
        "Total Shots": "home_shots/away_shots",
        "Corner Kicks": "home_corners/away_corners",
        "Fouls": "home_fouls/away_fouls",
        "Yellow Cards": "home_yellow/away_yellow",
        "Red Cards": "home_red/away_red",
        "Ball Possession": "home_possession/away_possession",
        "Total Passes": "home_passes/away_passes",
        "Passes Accurate": "home_pass_complete/away_pass_complete",
    },
}

# TheSportsDB 返回字段 -> 数据库字段
THESPORTSDB_FIELD_MAP: Dict[str, Dict[str, str]] = {
    "matches": {
        "idEvent": "match_id",
        "dateEvent": "match_date",
        "strTime": "match_time",
        "strHomeTeam": "home_team_name",
        "strAwayTeam": "away_team_name",
        "intHomeScore": "home_goals",
        "intAwayScore": "away_goals",
        "strLeague": "league_name",
        "intRound": "round_num",
        "strVenue": "venue",
    },
    "teams": {
        "idTeam": "team_id",
        "strTeam": "name_en",
        "strStadium": "stadium",
        "intFormedYear": "founded_year",
        "strTeamBadge": "logo_url",
        "strCountry": "country",
    },
}


def get_table_def(table_name: str) -> Optional[TableDef]:
    """获取表定义"""
    return TABLES.get(table_name)


def get_column_names(table_name: str) -> List[str]:
    """获取表的所有字段名"""
    table = TABLES.get(table_name)
    if not table:
        return []
    return [col.name for col in table.columns]


def get_field_map(source_id: str, table_name: str) -> Dict[str, str]:
    """获取API字段映射"""
    if source_id == "api_sports":
        return API_SPORTS_FIELD_MAP.get(table_name, {})
    elif source_id == "thesportsdb":
        return THESPORTSDB_FIELD_MAP.get(table_name, {})
    return {}


def get_all_tables_summary() -> List[Dict]:
    """获取所有表概要"""
    return [
        {
            "name": t.name,
            "name_cn": t.name_cn,
            "count": t.count,
            "columns_count": len(t.columns),
            "description": t.description,
        }
        for t in TABLES.values()
    ]
