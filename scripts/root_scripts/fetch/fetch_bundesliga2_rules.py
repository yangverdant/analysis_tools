"""
德乙联赛赛事规则和升降级信息

收集内容:
1. 联赛基本信息
2. 赛制规则
3. 升降级制度
4. 历年升降级球队
5. 参赛球队统计
"""

import sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

BUNDESLIGA_2_ID = 8


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_league_basic_info():
    """获取联赛基本信息"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM leagues WHERE league_id = ?
    ''', (BUNDESLIGA_2_ID,))

    league = cursor.fetchone()

    # 获取赛季统计
    cursor.execute('''
        SELECT
            COUNT(DISTINCT s.season_id) as seasons,
            MIN(s.year) as first_season,
            MAX(s.year) as last_season
        FROM seasons s
        WHERE s.league_id = ?
    ''', (BUNDESLIGA_2_ID,))

    season_stats = cursor.fetchone()

    # 获取比赛统计
    cursor.execute('''
        SELECT
            COUNT(*) as total_matches,
            COUNT(DISTINCT home_team_id) as total_teams,
            SUM(home_goals) + SUM(away_goals) as total_goals
        FROM matches
        WHERE league_id = ?
    ''', (BUNDESLIGA_2_ID,))

    match_stats = cursor.fetchone()

    conn.close()

    return {
        'name_en': league['name_en'] if league else '2. Bundesliga',
        'name_cn': league['name_cn'] if league else '德乙',
        'country': league['country'] if league else 'Germany',
        'tier': league['tier'] if league else 2,
        'format_type': league['format_type'] if league else 'round_robin',
        'cycle_type': league['cycle_type'] if league else 'annual',
        'total_seasons': season_stats[0] if season_stats else 0,
        'first_season': season_stats[1] if season_stats else None,
        'last_season': season_stats[2] if season_stats else None,
        'total_matches': match_stats[0] if match_stats else 0,
        'total_teams': match_stats[1] if match_stats else 0,
        'total_goals': match_stats[2] if match_stats else 0,
    }


def get_competition_rules():
    """获取赛制规则（基于数据分析）"""
    conn = get_db()
    cursor = conn.cursor()

    rules = {
        'teams_per_season': 18,
        'matches_per_team': 34,
        'total_matches_per_season': 306,
        'points_system': '胜3分 平1分 负0分',
        'match_frequency': '周末为主，周中补赛',
    }

    # 验证每赛季比赛数
    cursor.execute('''
        SELECT s.year, COUNT(*) as matches
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ?
        GROUP BY s.year
        ORDER BY s.year DESC
        LIMIT 10
    ''', (BUNDESLIGA_2_ID,))

    season_matches = cursor.fetchall()

    # 计算每赛季球队数
    cursor.execute('''
        SELECT s.year, COUNT(DISTINCT m.home_team_id) as teams
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ?
        GROUP BY s.year
        ORDER BY s.year DESC
        LIMIT 10
    ''', (BUNDESLIGA_2_ID,))

    season_teams = cursor.fetchall()

    conn.close()

    return {
        'rules': rules,
        'season_matches': [(r[0], r[1]) for r in season_matches],
        'season_teams': [(r[0], r[1]) for r in season_teams],
    }


def get_promotion_relegation_info():
    """
    获取升降级制度信息

    德乙升降级规则:
    - 升级: 前两名直接升级德甲，第3名与德甲倒数第3名进行升降级附加赛
    - 降级: 倒数两名直接降入德丙，倒数第3名与德丙第3名进行升降级附加赛
    """
    return {
        'promotion': {
            'direct': 2,  # 直接升级名额
            'playoff': 1,  # 附加赛名额
            'description': '前两名直接升级德甲，第3名与德甲倒数第3名进行升降级附加赛（主客场两回合）'
        },
        'relegation': {
            'direct': 2,  # 直接降级名额
            'playoff': 1,  # 附加赛名额
            'description': '倒数两名直接降入德丙，倒数第3名与德丙第3名进行升降级附加赛（主客场两回合）'
        },
        'total_teams': 18,
        'matches_per_season': 306,
    }


def analyze_season_standings(season_year: int = None):
    """分析赛季积分榜（模拟积分榜）"""
    conn = get_db()
    cursor = conn.cursor()

    if season_year:
        cursor.execute('''
            SELECT season_id FROM seasons
            WHERE league_id = ? AND year = ?
        ''', (BUNDESLIGA_2_ID, season_year))
        season = cursor.fetchone()
        if not season:
            return None
        season_id = season[0]
    else:
        # 获取最近完整赛季
        cursor.execute('''
            SELECT season_id, year FROM seasons
            WHERE league_id = ?
            ORDER BY year DESC
            LIMIT 1
        ''', (BUNDESLIGA_2_ID,))
        season = cursor.fetchone()
        if not season:
            return None
        season_id, season_year = season[0], season[1]

    # 计算积分榜
    cursor.execute('''
        SELECT
            t.team_id,
            t.name_en,
            t.name_cn,
            COUNT(*) as played,
            SUM(CASE
                WHEN m.home_team_id = t.team_id AND m.home_goals > m.away_goals THEN 1
                WHEN m.away_team_id = t.team_id AND m.away_goals > m.home_goals THEN 1
                ELSE 0
            END) as won,
            SUM(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as drawn,
            SUM(CASE
                WHEN m.home_team_id = t.team_id AND m.home_goals < m.away_goals THEN 1
                WHEN m.away_team_id = t.team_id AND m.away_goals < m.home_goals THEN 1
                ELSE 0
            END) as lost,
            SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_goals ELSE m.away_goals END) as goals_for,
            SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_goals ELSE m.home_goals END) as goals_against
        FROM matches m
        JOIN teams t ON t.team_id IN (m.home_team_id, m.away_team_id)
        WHERE m.league_id = ? AND m.season_id = ? AND m.home_goals IS NOT NULL
        GROUP BY t.team_id
        ORDER BY
            (SUM(CASE
                WHEN m.home_team_id = t.team_id AND m.home_goals > m.away_goals THEN 3
                WHEN m.away_team_id = t.team_id AND m.away_goals > m.home_goals THEN 3
                WHEN m.home_goals = m.away_goals THEN 1
                ELSE 0
            END)) DESC,
            (SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_goals ELSE m.away_goals END) -
             SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_goals ELSE m.home_goals END)) DESC
    ''', (BUNDESLIGA_2_ID, season_id))

    standings = cursor.fetchall()

    conn.close()

    return {
        'season': season_year,
        'standings': [
            {
                'position': i + 1,
                'team_id': r[0],
                'team_en': r[1],
                'team_cn': r[2],
                'played': r[3],
                'won': r[4],
                'drawn': r[5],
                'lost': r[6],
                'goals_for': r[7],
                'goals_against': r[8],
                'goal_diff': r[7] - r[8],
                'points': r[4] * 3 + r[5],
            }
            for i, r in enumerate(standings)
        ]
    }


def get_team_participation_stats():
    """获取球队参赛统计"""
    conn = get_db()
    cursor = conn.cursor()

    # 统计每支球队参赛赛季数
    cursor.execute('''
        SELECT
            t.team_id,
            t.name_en,
            t.name_cn,
            COUNT(DISTINCT s.year) as seasons,
            MIN(s.year) as first_season,
            MAX(s.year) as last_season,
            COUNT(*) as total_matches
        FROM matches m
        JOIN teams t ON t.team_id IN (m.home_team_id, m.away_team_id)
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ?
        GROUP BY t.team_id
        ORDER BY seasons DESC, total_matches DESC
    ''', (BUNDESLIGA_2_ID,))

    teams = cursor.fetchall()

    conn.close()

    return [
        {
            'team_id': r[0],
            'team_en': r[1],
            'team_cn': r[2],
            'seasons': r[3],
            'first_season': r[4],
            'last_season': r[5],
            'total_matches': r[6],
        }
        for r in teams
    ]


def get_season_stats_summary():
    """获取各赛季统计摘要"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            s.year,
            COUNT(*) as matches,
            COUNT(DISTINCT m.home_team_id) as teams,
            SUM(m.home_goals) + SUM(m.away_goals) as total_goals,
            ROUND(AVG(m.home_goals + m.away_goals), 2) as avg_goals,
            SUM(CASE WHEN m.result = 'H' THEN 1 ELSE 0 END) as home_wins,
            SUM(CASE WHEN m.result = 'D' THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN m.result = 'A' THEN 1 ELSE 0 END) as away_wins,
            SUM(CASE WHEN m.home_goals > m.away_goals THEN 1 ELSE 0 END) as home_team_wins
        FROM matches m
        JOIN seasons s ON m.season_id = s.season_id
        WHERE m.league_id = ? AND m.home_goals IS NOT NULL
        GROUP BY s.year
        ORDER BY s.year DESC
    ''', (BUNDESLIGA_2_ID,))

    seasons = cursor.fetchall()

    conn.close()

    return [
        {
            'year': r[0],
            'matches': r[1],
            'teams': r[2],
            'total_goals': r[3],
            'avg_goals': r[4],
            'home_wins': r[5],
            'draws': r[6],
            'away_wins': r[7],
            'home_win_rate': round(r[5] / r[1] * 100, 1) if r[1] > 0 else 0,
        }
        for r in seasons
    ]


def generate_report():
    """生成完整报告"""
    print("=" * 70)
    print("德乙联赛 (2. Bundesliga) 赛事规则和升降级信息")
    print("=" * 70)
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 联赛基本信息
    print("\n一、联赛基本信息")
    print("-" * 50)
    basic_info = get_league_basic_info()
    print(f"联赛名称: {basic_info['name_en']} ({basic_info['name_cn']})")
    print(f"所在国家: {basic_info['country']}")
    print(f"联赛等级: 第{basic_info['tier']}级别")
    print(f"赛制类型: 双循环积分赛 ({basic_info['format_type']})")
    print(f"赛季周期: {basic_info['cycle_type']}")
    print(f"数据覆盖: {basic_info['first_season']} - {basic_info['last_season']} ({basic_info['total_seasons']}个赛季)")
    print(f"总比赛数: {basic_info['total_matches']:,}场")
    print(f"总进球数: {basic_info['total_goals']:,}个")
    print(f"涉及球队: {basic_info['total_teams']}支")

    # 2. 赛制规则
    print("\n二、赛制规则")
    print("-" * 50)
    rules_info = get_competition_rules()
    rules = rules_info['rules']
    print(f"每赛季球队数: {rules['teams_per_season']}支")
    print(f"每队比赛场次: {rules['matches_per_team']}场 (主客场各17场)")
    print(f"每赛季总场次: {rules['total_matches_per_season']}场")
    print(f"积分规则: {rules['points_system']}")
    print(f"比赛时间: {rules['match_frequency']}")

    # 3. 升降级制度
    print("\n三、升降级制度")
    print("-" * 50)
    promo_info = get_promotion_relegation_info()

    print("\n【升级规则】")
    print(f"  直接升级: {promo_info['promotion']['direct']}个名额 (联赛第1、2名)")
    print(f"  附加赛: {promo_info['promotion']['playoff']}个名额 (联赛第3名 vs 德甲倒数第3名)")
    print(f"  说明: {promo_info['promotion']['description']}")

    print("\n【降级规则】")
    print(f"  直接降级: {promo_info['relegation']['direct']}个名额 (联赛倒数第1、2名)")
    print(f"  附加赛: {promo_info['relegation']['playoff']}个名额 (联赛倒数第3名 vs 德丙第3名)")
    print(f"  说明: {promo_info['relegation']['description']}")

    # 4. 各赛季统计
    print("\n四、各赛季统计")
    print("-" * 50)
    season_stats = get_season_stats_summary()
    print(f"{'赛季':<10} {'场次':<6} {'球队':<4} {'总进球':<8} {'场均':<6} {'主胜%':<8}")
    print("-" * 50)
    for s in season_stats[:15]:
        print(f"{s['year']:<10} {s['matches']:<6} {s['teams']:<4} {s['total_goals']:<8} {s['avg_goals']:<6} {s['home_win_rate']:<8}%")

    # 5. 球队参赛统计
    print("\n五、参赛球队统计 (Top 20)")
    print("-" * 50)
    team_stats = get_team_participation_stats()
    print(f"{'排名':<4} {'球队':<25} {'赛季数':<6} {'首赛季':<8} {'最近':<8} {'总场次':<8}")
    print("-" * 50)
    for i, t in enumerate(team_stats[:20]):
        team_name = t['team_en'][:22] if t['team_en'] else 'Unknown'
        print(f"{i+1:<4} {team_name:<25} {t['seasons']:<6} {t['first_season']:<8} {t['last_season']:<8} {t['total_matches']:<8}")

    # 6. 最近赛季积分榜
    print("\n六、最近赛季积分榜模拟 (前8名)")
    print("-" * 50)
    standings_info = analyze_season_standings()
    if standings_info:
        print(f"赛季: {standings_info['season']}")
        print(f"{'名次':<4} {'球队':<20} {'场次':<4} {'胜':<4} {'平':<4} {'负':<4} {'进球':<6} {'失球':<6} {'净胜':<6} {'积分':<6} {'状态'}")
        print("-" * 70)

        status_map = {
            1: '↑直接升级',
            2: '↑直接升级',
            3: '±附加赛',
            16: '±附加赛',
            17: '↓直接降级',
            18: '↓直接降级',
        }

        for team in standings_info['standings'][:8]:
            pos = team['position']
            status = status_map.get(pos, '')
            team_name = team['team_en'][:18] if team['team_en'] else 'Unknown'
            print(f"{pos:<4} {team_name:<20} {team['played']:<4} {team['won']:<4} {team['drawn']:<4} {team['lost']:<4} {team['goals_for']:<6} {team['goals_against']:<6} {team['goal_diff']:<+6} {team['points']:<6} {status}")

    # 7. 数据质量说明
    print("\n七、数据说明")
    print("-" * 50)
    print("1. 数据来源: football-data.co.uk CSV文件")
    print("2. 数据覆盖: 2000-2001赛季至2025-2026赛季")
    print("3. 统计字段: 2020年后数据含射门、角球、犯规等详细统计")
    print("4. xG数据: 基于射门数据估算，覆盖有统计的比赛")
    print("5. 升降级信息: 根据联赛规则整理，实际结果以官方为准")

    print("\n" + "=" * 70)
    print("报告生成完成")
    print("=" * 70)


if __name__ == "__main__":
    generate_report()
