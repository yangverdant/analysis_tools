"""
足球分析模块
包含各种分析函数：Elo 评分、xG 计算、预测等
"""

import sqlite3
import math
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


def get_elo_rating(team_id: int, conn: sqlite3.Connection) -> float:
    """获取球队 Elo 评分"""
    cursor = conn.cursor()
    cursor.execute("SELECT elo_rating FROM elo_ratings WHERE team_id = ?", (team_id,))
    result = cursor.fetchone()
    elo = result['elo_rating'] if result else 1500
    return elo


def calculate_xg(home_team_id: int, away_team_id: int, conn: sqlite3.Connection) -> Tuple[float, float]:
    """计算预期进球 (xG)"""
    cursor = conn.cursor()

    # 主队主场进攻力
    cursor.execute("""
        SELECT
            AVG(home_goals) as avg_home_goals,
            AVG(away_goals) as avg_conceded,
            COUNT(*) as matches
        FROM matches
        WHERE home_team_id = ? AND home_goals IS NOT NULL
    """, (home_team_id,))
    home_stats = cursor.fetchone()

    # 客队客场数据
    cursor.execute("""
        SELECT
            AVG(away_goals) as avg_away_goals,
            AVG(home_goals) as avg_conceded,
            COUNT(*) as matches
        FROM matches
        WHERE away_team_id = ? AND away_goals IS NOT NULL
    """, (away_team_id,))
    away_stats = cursor.fetchone()

    # 计算 xG（简化模型）
    home_xg = home_stats['avg_home_goals'] or 1.35
    away_xg = away_stats['avg_away_goals'] or 1.05

    # 考虑防守因素
    if away_stats['avg_conceded']:
        home_xg = (home_xg + away_stats['avg_conceded']) / 2
    if home_stats['avg_conceded']:
        away_xg = (away_xg + home_stats['avg_conceded']) / 2

    return round(home_xg, 2), round(away_xg, 2)


def predict_match(home_team_id: int, away_team_id: int, conn: sqlite3.Connection) -> Dict[str, Any]:
    """预测比赛结果"""
    # 获取 Elo 评分
    home_elo = get_elo_rating(home_team_id, conn)
    away_elo = get_elo_rating(away_team_id, conn)

    # 主场优势
    home_elo += 100

    # 计算 xG
    home_xg, away_xg = calculate_xg(home_team_id, away_team_id, conn)

    # 基于 Elo 计算胜率
    elo_diff = home_elo - away_elo
    home_win_prob = 1 / (1 + 10 ** (-elo_diff / 400))

    # 使用泊松分布计算精确概率
    def poisson_prob(k, lambda_val):
        return (lambda_val ** k) * math.exp(-lambda_val) / math.factorial(k)

    # 计算各结果概率
    home_win = 0
    draw = 0
    away_win = 0

    for h in range(8):
        for a in range(8):
            prob = poisson_prob(h, home_xg) * poisson_prob(a, away_xg)
            if h > a:
                home_win += prob
            elif h == a:
                draw += prob
            else:
                away_win += prob

    return {
        'home_win_prob': round(home_win * 100, 1),
        'draw_prob': round(draw * 100, 1),
        'away_win_prob': round(away_win * 100, 1),
        'predicted_home_goals': home_xg,
        'predicted_away_goals': away_xg,
        'home_elo': round(home_elo, 0),
        'away_elo': round(away_elo, 0)
    }


def get_league_importance(league_id: int, conn: sqlite3.Connection) -> str:
    """获取联赛重要性"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tier, competition_type, is_international
        FROM leagues WHERE league_id = ?
    """, (league_id,))
    league = cursor.fetchone()

    if not league:
        return 'normal'

    tier = league['tier'] or 1
    is_intl = league['is_international']
    comp_type = league['competition_type']

    if is_intl or comp_type == 'cup':
        return 'high'
    elif tier == 1:
        return 'high'
    elif tier <= 3:
        return 'normal'
    else:
        return 'low'


def get_team_upcoming_fixtures(team_id: int, days: int, conn: sqlite3.Connection) -> Dict[str, Any]:
    """获取球队未来赛程"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.home_team_id,
            m.away_team_id,
            ht.name_en as home_team, ht.name_cn as home_team_cn,
            at.name_en as away_team, at.name_cn as away_team_cn,
            l.name_en as league_name, l.name_cn as league_name_cn,
            l.tier as league_tier
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE (m.home_team_id = ? OR m.away_team_id = ?)
        AND m.status = 'scheduled'
        AND m.match_date BETWEEN date('now') AND date('now', '+' || ? || ' days')
        ORDER BY m.match_date
    """, (team_id, team_id, days))

    fixtures = [dict(row) for row in cursor.fetchall()]

    # 计算密集度
    intensity = 'normal'
    if len(fixtures) >= 4:
        intensity = 'very_high'
    elif len(fixtures) >= 3:
        intensity = 'high'

    return {
        'team_id': team_id,
        'days': days,
        'matches_count': len(fixtures),
        'intensity': intensity,
        'fixtures': fixtures
    }


def get_team_league_position(team_id: int, league_id: int, season: int, conn: sqlite3.Connection) -> Optional[Dict]:
    """获取球队联赛排名"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            s.position,
            s.points,
            s.played,
            s.won,
            s.drawn,
            s.lost,
            s.goals_for,
            s.goals_against,
            s.goal_diff,
            s.form
        FROM standings s
        WHERE s.team_id = ? AND s.league_id = ?
        AND s.season_id = (
            SELECT season_id FROM seasons
            WHERE league_id = ? AND year = ?
            LIMIT 1
        )
        LIMIT 1
    """, (team_id, league_id, league_id, season))

    result = cursor.fetchone()
    return dict(result) if result else None


def analyze_team_motivation(team_id: int, league_id: int, season: int, conn: sqlite3.Connection) -> Dict[str, Any]:
    """分析球队战意"""
    position_data = get_team_league_position(team_id, league_id, season, conn)

    if not position_data:
        return {'motivation': 'normal', 'reason': '无排名数据'}

    position = position_data['position']
    form = position_data.get('form', '')

    # 根据排名判断战意
    if position <= 2:
        motivation = 'very_high'
        reason = '争夺冠军/升级'
    elif position <= 6:
        motivation = 'high'
        reason = '争夺欧战/升级附加赛'
    elif position >= len(str(position_data)) - 3:
        motivation = 'very_high'
        reason = '保级战'
    else:
        motivation = 'normal'
        reason = '中游无压力'

    # 考虑近期状态
    if form:
        recent_wins = form.count('W')
        if recent_wins >= 4:
            motivation = 'very_high'
            reason = '状态火热'
        elif recent_wins <= 1:
            motivation = 'low'
            reason = '状态低迷'

    return {
        'motivation': motivation,
        'reason': reason,
        'position': position,
        'form': form
    }


def generate_match_summary(home_team: str, away_team: str, home_elo: float,
                           away_elo: float, prediction: Dict, h2h: Dict) -> str:
    """生成比赛总结"""
    home_win_prob = prediction.get('home_win_prob', 0)
    draw_prob = prediction.get('draw_prob', 0)
    away_win_prob = prediction.get('away_win_prob', 0)

    if home_win_prob > 50:
        favorite = home_team
    elif away_win_prob > 50:
        favorite = away_team
    else:
        favorite = '势均力敌'

    return f"{home_team} vs {away_team} - 预测：{favorite} 占优，胜率{max(home_win_prob, away_win_prob)}%"


def get_recent_trend_analysis(home_team_id: int, away_team_id: int,
                               conn: sqlite3.Connection) -> Dict[str, Any]:
    """获取近期趋势分析"""
    cursor = conn.cursor()

    # 主队近 5 场
    cursor.execute("""
        SELECT
            SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) as losses,
            AVG(home_goals) as avg_goals,
            AVG(away_goals) as avg_conceded
        FROM (
            SELECT home_goals, away_goals
            FROM matches
            WHERE home_team_id = ? AND home_goals IS NOT NULL
            ORDER BY match_date DESC
            LIMIT 5
        )
    """, (home_team_id,))
    home_form = cursor.fetchone()

    # 客队近 5 场
    cursor.execute("""
        SELECT
            SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN away_goals < home_goals THEN 1 ELSE 0 END) as losses,
            AVG(away_goals) as avg_goals,
            AVG(home_goals) as avg_conceded
        FROM (
            SELECT home_goals, away_goals
            FROM matches
            WHERE away_team_id = ? AND away_goals IS NOT NULL
            ORDER BY match_date DESC
            LIMIT 5
        )
    """, (away_team_id,))
    away_form = cursor.fetchone()

    return {
        'home_recent': {
            'wins': home_form['wins'] or 0,
            'draws': home_form['draws'] or 0,
            'losses': home_form['losses'] or 0,
            'avg_goals': round(home_form['avg_goals'] or 0, 2),
            'avg_conceded': round(home_form['avg_conceded'] or 0, 2)
        },
        'away_recent': {
            'wins': away_form['wins'] or 0,
            'draws': away_form['draws'] or 0,
            'losses': away_form['losses'] or 0,
            'avg_goals': round(away_form['avg_goals'] or 0, 2),
            'avg_conceded': round(away_form['avg_conceded'] or 0, 2)
        }
    }


def get_h2h_stats(team1_id: int, team2_id: int, conn: sqlite3.Connection, limit: int = 10) -> List[Dict]:
    """获取历史交锋记录"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.home_team_id,
            m.away_team_id,
            m.home_goals,
            m.away_goals,
            ht.name_en as home_team, ht.name_cn as home_team_cn,
            at.name_en as away_team, at.name_cn as away_team_cn
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE (m.home_team_id = ? AND m.away_team_id = ?)
           OR (m.home_team_id = ? AND m.away_team_id = ?)
        AND m.home_goals IS NOT NULL
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (team1_id, team2_id, team2_id, team1_id, limit))

    return [dict(row) for row in cursor.fetchall()]


def calculate_h2h_summary(h2h_matches: List[Dict], team1_id: int) -> Dict[str, Any]:
    """计算交锋统计"""
    team1_wins = 0
    team2_wins = 0
    draws = 0

    for match in h2h_matches:
        if match['home_team_id'] == team1_id:
            if match['home_goals'] > match['away_goals']:
                team1_wins += 1
            elif match['home_goals'] < match['away_goals']:
                team2_wins += 1
            else:
                draws += 1
        else:
            if match['away_goals'] > match['home_goals']:
                team1_wins += 1
            elif match['away_goals'] < match['home_goals']:
                team2_wins += 1
            else:
                draws += 1

    total = len(h2h_matches)
    return {
        'total_matches': total,
        'team1_wins': team1_wins,
        'team2_wins': team2_wins,
        'draws': draws,
        'team1_win_rate': round(team1_wins / total * 100, 1) if total > 0 else 0
    }
