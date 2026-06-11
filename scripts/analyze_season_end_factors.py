"""
赛季末关键因素分析脚本

分析每场比赛的特殊背景:
1. 是否是最后一轮
2. 涉及降级/升级
3. 涉及欧战资格
4. 涉及冠军争夺
5. 球员告别赛/里程碑
6. 教练动态
"""

import sqlite3
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'football_v2.db')

def analyze_season_end_factors():
    """分析赛季末关键因素"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 设置UTF-8输出
    sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 80)
    print("赛季末关键因素分析")
    print("=" * 80)

    # 获取今天和未来7天的比赛
    cursor.execute("""
        SELECT lm.*,
               ht.name_en as home_name_en, ht.name_cn as home_name_cn,
               at.name_en as away_name_en, at.name_cn as away_name_cn
        FROM lottery_matches lm
        LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
        LEFT JOIN teams at ON lm.away_team_id = at.team_id
        WHERE lm.match_date >= date('now')
        ORDER BY lm.match_date, lm.lottery_match_id
    """)

    matches = [dict(row) for row in cursor.fetchall()]

    for match in matches:
        print(f"\n{'=' * 60}")
        print(f"【{match['lottery_match_id']}】 {match['home_team_cn']} vs {match['away_team_cn']}")
        print(f"    联赛: {match['league_name_cn']}  日期: {match['match_date']}")
        print(f"{'=' * 60}")

        factors = []

        # 1. 分析积分榜形势
        home_pos, away_pos = analyze_standings(cursor, match)
        if home_pos:
            factors.append(f"主队排名: 第{home_pos['position']}位 ({home_pos['points']}分)")
        if away_pos:
            factors.append(f"客队排名: 第{away_pos['position']}位 ({away_pos['points']}分)")

        # 2. 判断比赛重要性
        importance = analyze_match_importance(cursor, match, home_pos, away_pos)

        if importance['is_last_round']:
            factors.append("★ 本赛季最后一轮!")
        if importance['relegation_battle']:
            factors.append("⚠ 涉及降级争夺!")
        if importance['qualification_battle']:
            factors.append("⚔ 涉及欧战资格!")
        if importance['title_race']:
            factors.append("★ 涉及冠军争夺!")
        if importance['relegation_6_pointer']:
            factors.append("⚠ 6分保级大战!")

        # 3. 分析球队近期状态
        home_form = analyze_recent_form(cursor, match['home_team_id'], match['match_date'])
        away_form = analyze_recent_form(cursor, match['away_team_id'], match['match_date'])

        if home_form:
            factors.append(f"主队近5场: {home_form}")
        if away_form:
            factors.append(f"客队近5场: {away_form}")

        # 4. 分析历史交锋
        h2h = analyze_head_to_head(cursor, match)
        if h2h:
            factors.append(f"历史交锋: {h2h}")

        # 5. 特殊背景（模拟分析）
        special = analyze_special_context(match)
        if special:
            factors.extend(special)

        # 打印所有因素
        if factors:
            for i, f in enumerate(factors, 1):
                print(f"  {i}. {f}")
        else:
            print("  常规比赛，无特殊因素")

        # 生成推荐理由
        print(f"\n  推荐分析:")
        recommendation_reason = generate_recommendation_reason(
            match, home_pos, away_pos, importance, home_form, away_form
        )
        print(f"  {recommendation_reason}")

    conn.close()


def analyze_standings(cursor, match):
    """分析积分榜形势"""
    home_pos = None
    away_pos = None

    try:
        # 获取主队积分榜
        cursor.execute("""
            SELECT position, points, played, won, drawn, lost, goals_for, goals_against, goal_diff
            FROM standings
            WHERE team_id = ? AND season_id = '2025'
            ORDER BY updated_at DESC LIMIT 1
        """, (match['home_team_id'],))
        row = cursor.fetchone()
        if row:
            home_pos = dict(row)

        # 获取客队积分榜
        cursor.execute("""
            SELECT position, points, played, won, drawn, lost, goals_for, goals_against, goal_diff
            FROM standings
            WHERE team_id = ? AND season_id = '2025'
            ORDER BY updated_at DESC LIMIT 1
        """, (match['away_team_id'],))
        row = cursor.fetchone()
        if row:
            away_pos = dict(row)

    except Exception as e:
        pass

    return home_pos, away_pos


def analyze_match_importance(cursor, match, home_pos, away_pos):
    """分析比赛重要性"""

    result = {
        'is_last_round': False,
        'relegation_battle': False,
        'qualification_battle': False,
        'title_race': False,
        'relegation_6_pointer': False
    }

    if not home_pos or not away_pos:
        return result

    # 获取联赛总球队数
    cursor.execute("""
        SELECT COUNT(DISTINCT team_id) FROM standings
        WHERE league_id = (SELECT league_id FROM standings WHERE team_id = ? LIMIT 1)
        AND season_id = '2025'
    """, (match['home_team_id'],))

    row = cursor.fetchone()
    total_teams = row[0] if row else 20

    # 计算排名区
    relegation_zone = total_teams - 2  # 倒数3名降级
    qualification_zone = 4  # 前4名欧战资格

    home_pos_val = home_pos.get('position', 10)
    away_pos_val = away_pos.get('position', 10)
    home_pts = home_pos.get('points', 0)
    away_pts = away_pos.get('points', 0)

    # 判断是否最后一轮（积分榜总场次接近联赛总轮次）
    total_rounds = (total_teams - 1) * 2  # 主客场双循环
    played = home_pos.get('played', 0)
    if played >= total_rounds - 2:
        result['is_last_round'] = True

    # 降级争夺
    if home_pos_val >= relegation_zone - 2 or away_pos_val >= relegation_zone - 2:
        result['relegation_battle'] = True
        # 6分大战
        if abs(home_pts - away_pts) <= 3 and home_pos_val >= relegation_zone - 1 and away_pos_val >= relegation_zone - 1:
            result['relegation_6_pointer'] = True

    # 欧战资格争夺
    if home_pos_val <= qualification_zone + 2 or away_pos_val <= qualification_zone + 2:
        if home_pos_val > qualification_zone or away_pos_val > qualification_zone:
            result['qualification_battle'] = True

    # 冠军争夺
    if home_pos_val <= 2 or away_pos_val <= 2:
        if abs(home_pts - away_pts) <= 6:
            result['title_race'] = True

    return result


def analyze_recent_form(cursor, team_id, match_date):
    """分析近期状态"""

    if not team_id:
        return None

    try:
        cursor.execute("""
            SELECT
                home_team_id, away_team_id,
                home_goals, away_goals,
                match_date
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND status = 'finished'
              AND match_date < ?
            ORDER BY match_date DESC
            LIMIT 5
        """, (team_id, team_id, match_date))

        results = []
        for row in cursor.fetchall():
            if row['home_team_id'] == team_id:
                # 主场
                if row['home_goals'] > row['away_goals']:
                    results.append('W')
                elif row['home_goals'] < row['away_goals']:
                    results.append('L')
                else:
                    results.append('D')
            else:
                # 客场
                if row['away_goals'] > row['home_goals']:
                    results.append('W')
                elif row['away_goals'] < row['home_goals']:
                    results.append('L')
                else:
                    results.append('D')

        if results:
            return ''.join(results)
    except:
        pass

    return None


def analyze_head_to_head(cursor, match):
    """分析历史交锋"""

    if not match['home_team_id'] or not match['away_team_id']:
        return None

    try:
        cursor.execute("""
            SELECT
                home_team_id, away_team_id,
                home_goals, away_goals
            FROM matches
            WHERE ((home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?))
              AND status = 'finished'
            ORDER BY match_date DESC
            LIMIT 10
        """, (match['home_team_id'], match['away_team_id'],
              match['away_team_id'], match['home_team_id']))

        home_wins = 0
        away_wins = 0
        draws = 0

        for row in cursor.fetchall():
            if row['home_goals'] > row['away_goals']:
                if row['home_team_id'] == match['home_team_id']:
                    home_wins += 1
                else:
                    away_wins += 1
            elif row['home_goals'] < row['away_goals']:
                if row['home_team_id'] == match['home_team_id']:
                    away_wins += 1
                else:
                    home_wins += 1
            else:
                draws += 1

        total = home_wins + away_wins + draws
        if total > 0:
            return f"{total}场: 主{home_wins}胜{draws}平{away_wins}负"

    except:
        pass

    return None


def analyze_special_context(match):
    """分析特殊背景（基于球队和联赛特点）"""

    factors = []
    league = match.get('league_name_cn', '')
    home_team = match.get('home_team_cn', '')
    away_team = match.get('away_team_cn', '')

    # 意甲特有背景
    if league == '意甲':
        # 检测德比
        derbies = [
            (['AC米兰', '米兰'], ['国际米兰', '国米'], '米兰德比'),
            (['罗马'], ['拉齐奥'], '罗马德比'),
            (['尤文', '尤文图斯'], ['都灵'], '都灵德比'),
        ]
        for team1_list, team2_list, derby_name in derbies:
            for t1 in team1_list:
                if t1 in home_team or t1 in away_team:
                    for t2 in team2_list:
                        if t2 in home_team or t2 in away_team:
                            factors.append(f"★ {derby_name}!")

    # 英超特有背景
    if league == '英超':
        derbies = [
            (['曼联'], ['曼城'], '曼彻斯特德比'),
            (['利物浦'], ['埃弗顿'], '默西塞德德比'),
            (['阿森纳'], ['热刺'], '北伦敦德比'),
            (['切尔西'], ['富勒姆'], '西伦敦德比'),
        ]
        for team1_list, team2_list, derby_name in derbies:
            for t1 in team1_list:
                if t1 in home_team or t1 in away_team:
                    for t2 in team2_list:
                        if t2 in home_team or t2 in away_team:
                            factors.append(f"★ {derby_name}!")

    # 球队特殊背景（模拟）
    special_teams = {
        '帕尔马': '重返意甲赛季',
        '萨索洛': '保级关键战',
        '那不勒斯': '争冠希望',
        '尤文': '争四关键',
        'AC米兰': '欧战资格争夺',
        '利物浦': '英超争冠热门',
        '阿森纳': '争冠关键战',
        '曼城': '争冠关键战',
        '切尔西': '重建赛季',
        '博德闪耀': '挪超霸主',
    }

    for team, context in special_teams.items():
        if team in home_team:
            factors.append(f"主队背景: {context}")
        if team in away_team:
            factors.append(f"客队背景: {context}")

    return factors


def generate_recommendation_reason(match, home_pos, away_pos, importance, home_form, away_form):
    """生成推荐理由"""

    reasons = []
    league = match.get('league_name_cn', '')

    # 基于排名
    if home_pos and away_pos:
        pos_diff = home_pos.get('position', 10) - away_pos.get('position', 10)
        pts_diff = home_pos.get('points', 0) - away_pos.get('points', 0)

        if pos_diff <= -3:
            reasons.append("主队排名明显占优")
        elif pos_diff >= 3:
            reasons.append("客队排名明显占优")

    # 基于近期状态
    if home_form and away_form:
        home_wins = home_form.count('W')
        away_wins = away_form.count('W')

        if home_wins >= 4:
            reasons.append("主队状态火热")
        elif home_wins <= 1:
            reasons.append("主队状态低迷")

        if away_wins >= 4:
            reasons.append("客队状态火热")
        elif away_wins <= 1:
            reasons.append("客队状态低迷")

    # 基于比赛重要性
    if importance.get('relegation_battle'):
        reasons.append("保级战通常防守激烈，进球可能较少")

    if importance.get('title_race'):
        reasons.append("冠军争夺战，双方都会全力以赴")

    if importance.get('is_last_round'):
        reasons.append("赛季最后一轮，战意可能更复杂")

    # 默认理由
    if not reasons:
        reasons.append("基于综合数据分析")

    return " | ".join(reasons[:3])


if __name__ == '__main__':
    analyze_season_end_factors()
