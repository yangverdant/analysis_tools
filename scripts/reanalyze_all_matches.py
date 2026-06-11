"""
重新分析所有体彩比赛

使用修复后的积分榜数据，正确判断冠军已定、降级争夺、欧战资格等情况
"""

import sqlite3
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.lottery.feature_extractors.context.key_match_factors_analyzer import KeyMatchFactorsAnalyzer
from backend.app.lottery.feature_extractors.base import ExtractionContext

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'football_v2.db')


def reanalyze_all_matches():
    """重新分析所有比赛"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    analyzer = KeyMatchFactorsAnalyzer(DB_PATH)

    # 获取所有比赛
    cursor.execute("""
        SELECT lottery_match_id, home_team_cn, away_team_cn,
               home_team_id, away_team_id, match_date, league_name_cn
        FROM lottery_matches
        WHERE home_team_id IS NOT NULL AND away_team_id IS NOT NULL
        ORDER BY match_date, lottery_match_id
    """)

    matches = cursor.fetchall()
    print(f"共 {len(matches)} 场比赛需要分析")
    print("=" * 70)

    results = {
        'champion_decided': [],
        'title_race': [],
        'relegation': [],
        'qualification': [],
        'normal': []
    }

    for match in matches:
        context = ExtractionContext(
            match_id=None,
            home_team_id=match['home_team_id'],
            away_team_id=match['away_team_id'],
            league_id=None,
            match_date=match['match_date'],
            db_conn=conn,
            lottery_match_id=match['lottery_match_id']
        )

        try:
            result = analyzer.extract(context)
            importance = result.raw_data.get('match_importance', {})

            match_info = {
                'id': match['lottery_match_id'],
                'home': match['home_team_cn'],
                'away': match['away_team_cn'],
                'league': match['league_name_cn'],
                'date': match['match_date']
            }

            if importance.get('champion_decided'):
                match_info['champion'] = importance.get('champion_team')
                results['champion_decided'].append(match_info)

            if importance.get('involves_title_race'):
                results['title_race'].append(match_info)

            if importance.get('involves_relegation'):
                results['relegation'].append(match_info)

            if importance.get('involves_qualification'):
                results['qualification'].append(match_info)

            if not any([importance.get('champion_decided'),
                       importance.get('involves_title_race'),
                       importance.get('involves_relegation'),
                       importance.get('involves_qualification')]):
                results['normal'].append(match_info)

        except Exception as e:
            print(f"Error analyzing {match['lottery_match_id']}: {e}")

    # 输出结果
    print("\n" + "=" * 70)
    print("分析结果汇总:")
    print("=" * 70)

    print(f"\n【冠军已定】({len(results['champion_decided'])}场)")
    for m in results['champion_decided'][:10]:
        print(f"  {m['id']}: {m['home']} vs {m['away']} ({m['league']}) - 冠军: {m['champion']}")

    print(f"\n【涉及冠军争夺】({len(results['title_race'])}场)")
    for m in results['title_race'][:10]:
        print(f"  {m['id']}: {m['home']} vs {m['away']} ({m['league']})")

    print(f"\n【涉及降级争夺】({len(results['relegation'])}场)")
    for m in results['relegation'][:10]:
        print(f"  {m['id']}: {m['home']} vs {m['away']} ({m['league']})")

    print(f"\n【涉及欧战资格】({len(results['qualification'])}场)")
    for m in results['qualification'][:10]:
        print(f"  {m['id']}: {m['home']} vs {m['away']} ({m['league']})")

    print(f"\n【普通比赛】({len(results['normal'])}场)")

    conn.close()
    return results


if __name__ == '__main__':
    reanalyze_all_matches()
