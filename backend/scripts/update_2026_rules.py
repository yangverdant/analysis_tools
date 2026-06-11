"""
更新2026赛季日韩联赛最新规则
"""
import sqlite3
import json
from datetime import datetime

conn = sqlite3.connect('data/football_v2.db')
cursor = conn.cursor()

# 2026赛季日韩联赛最新规则
latest_rules = {
    # J1联赛
    18: {
        'season': '2026',
        'teams_count': 20,
        'matches_per_team': 38,
        'format_type': 'double_round_robin',
        'promotion_spots': 0,
        'promotion_playoff_spots': 0,
        'relegation_spots': 3,
        'relegation_playoff_spots': 0,
        'afc_champions_league_spots': 3,
        'afc_cup_spots': 1,
        'has_playoffs': 0,
        'has_split': 0,
        'season_start_month': 2,
        'season_end_month': 12,
        'rules_json': json.dumps({
            'format': '双循环赛制',
            'promotion': {'direct': 0, 'note': '顶级联赛无升级'},
            'relegation': {'direct': 3, 'note': '第18、19、20名直接降级J2'},
            'continental': {
                'afc_champions_league_elite': '前3名',
                'afc_champions_league_2': '第4名',
                'emperor_cup': '冠军获亚冠资格'
            },
            'notes': '2024赛季起改为单年度制(2-12月)'
        }, ensure_ascii=False)
    },

    # J2联赛
    7433: {
        'season': '2026',
        'teams_count': 20,
        'matches_per_team': 38,
        'format_type': 'double_round_robin',
        'promotion_spots': 2,
        'promotion_playoff_spots': 1,
        'relegation_spots': 2,
        'relegation_playoff_spots': 1,
        'has_playoffs': 1,
        'has_promotion_playoff': 1,
        'has_relegation_playoff': 1,
        'playoff_teams': 6,
        'has_split': 0,
        'season_start_month': 2,
        'season_end_month': 12,
        'rules_json': json.dumps({
            'format': '双循环赛制',
            'promotion': {
                'direct': 2,
                'playoff': 1,
                'playoff_teams': 6,
                'playoff_format': '第3vs第6，第4vs第5，胜者对决',
                'note': '前2名直接升级J1，第3-6名附加赛'
            },
            'relegation': {
                'direct': 2,
                'playoff': 1,
                'note': '最后2名直接降级J3，第18名与J3附加赛'
            }
        }, ensure_ascii=False)
    },

    # J3联赛
    7434: {
        'season': '2026',
        'teams_count': 20,
        'matches_per_team': 38,
        'format_type': 'double_round_robin',
        'promotion_spots': 2,
        'promotion_playoff_spots': 1,
        'relegation_spots': 0,
        'relegation_playoff_spots': 0,
        'has_playoffs': 1,
        'has_promotion_playoff': 1,
        'has_relegation_playoff': 0,
        'has_split': 0,
        'season_start_month': 2,
        'season_end_month': 12,
        'rules_json': json.dumps({
            'format': '双循环赛制',
            'promotion': {
                'direct': 2,
                'playoff': 1,
                'note': '前2名直接升级J2，第3-6名附加赛'
            },
            'relegation': {
                'direct': 0,
                'note': 'J3为最低职业联赛，无降级。JFL冠军可升级至J3'
            }
        }, ensure_ascii=False)
    },

    # K联赛1 (分阶段赛制)
    20: {
        'season': '2026',
        'teams_count': 12,
        'matches_per_team': 38,
        'format_type': 'split_season',
        'promotion_spots': 0,
        'promotion_playoff_spots': 0,
        'relegation_spots': 1,
        'relegation_playoff_spots': 1,
        'afc_champions_league_spots': 2,
        'afc_cup_spots': 3,
        'has_playoffs': 0,
        'has_split': 1,
        'split_after_rounds': 33,
        'season_start_month': 3,
        'season_end_month': 12,
        'rules_json': json.dumps({
            'format': '分阶段赛制',
            'split': {
                'has_split': True,
                'split_after_rounds': 33,
                'split_groups': 2,
                'split_group_names': ['Final A (争冠组)', 'Final B (保级组)'],
                'description': '33轮后按排名分两组，前6名争冠组，后6名保级组，各打5轮'
            },
            'promotion': {'direct': 0, 'note': '顶级联赛无升级'},
            'relegation': {
                'direct': 1,
                'playoff': 1,
                'playoff_format': 'K联赛1第11名 vs K联赛2第2名',
                'note': '最后1名直接降级，第11名与K联赛2附加赛'
            },
            'continental': {
                'afc_champions_league_elite': '联赛冠军+足协杯冠军',
                'afc_champions_league_2': '联赛第2-4名'
            },
            'foreign_players': {'limit': '注册5人(含亚外)，上场4人'}
        }, ensure_ascii=False)
    },

    # K联赛2
    7436: {
        'season': '2026',
        'teams_count': 13,
        'matches_per_team': 36,
        'format_type': 'double_round_robin',
        'promotion_spots': 1,
        'promotion_playoff_spots': 1,
        'relegation_spots': 0,
        'relegation_playoff_spots': 0,
        'has_playoffs': 1,
        'has_promotion_playoff': 1,
        'has_relegation_playoff': 0,
        'playoff_teams': 4,
        'has_split': 0,
        'season_start_month': 3,
        'season_end_month': 11,
        'rules_json': json.dumps({
            'format': '双循环赛制',
            'promotion': {
                'direct': 1,
                'playoff': 1,
                'playoff_format': '第2-4名进行附加赛',
                'note': '冠军直接升级K联赛1，第2-4名附加赛'
            },
            'relegation': {
                'direct': 0,
                'note': 'K联赛2为次级联赛，无降级'
            }
        }, ensure_ascii=False)
    }
}

# 更新数据库
updated = 0
for league_id, rules in latest_rules.items():
    cursor.execute('''
        SELECT rule_id FROM league_rules
        WHERE league_id = ? AND season = ?
    ''', (league_id, rules['season']))

    if cursor.fetchone():
        cursor.execute('''
            UPDATE league_rules SET
                teams_count = ?, matches_per_team = ?, format_type = ?,
                promotion_spots = ?, promotion_playoff_spots = ?,
                relegation_spots = ?, relegation_playoff_spots = ?,
                afc_champions_league_spots = ?, afc_cup_spots = ?,
                has_playoffs = ?, has_split = ?, split_after_rounds = ?,
                season_start_month = ?, season_end_month = ?,
                rules_json = ?, updated_at = ?
            WHERE league_id = ? AND season = ?
        ''', (
            rules.get('teams_count'), rules.get('matches_per_team'), rules.get('format_type'),
            rules.get('promotion_spots', 0), rules.get('promotion_playoff_spots', 0),
            rules.get('relegation_spots', 0), rules.get('relegation_playoff_spots', 0),
            rules.get('afc_champions_league_spots', 0), rules.get('afc_cup_spots', 0),
            rules.get('has_playoffs', 0), rules.get('has_split', 0), rules.get('split_after_rounds'),
            rules.get('season_start_month'), rules.get('season_end_month'),
            rules.get('rules_json'), datetime.now().isoformat(),
            league_id, rules['season']
        ))
        print(f'更新联赛 {league_id} 2026赛季规则')
    else:
        cursor.execute('''
            INSERT INTO league_rules (
                league_id, season, teams_count, matches_per_team, format_type,
                promotion_spots, promotion_playoff_spots,
                relegation_spots, relegation_playoff_spots,
                afc_champions_league_spots, afc_cup_spots,
                has_playoffs, has_split, split_after_rounds,
                season_start_month, season_end_month,
                rules_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            league_id, rules['season'], rules.get('teams_count'), rules.get('matches_per_team'),
            rules.get('format_type'), rules.get('promotion_spots', 0), rules.get('promotion_playoff_spots', 0),
            rules.get('relegation_spots', 0), rules.get('relegation_playoff_spots', 0),
            rules.get('afc_champions_league_spots', 0), rules.get('afc_cup_spots', 0),
            rules.get('has_playoffs', 0), rules.get('has_split', 0), rules.get('split_after_rounds'),
            rules.get('season_start_month'), rules.get('season_end_month'),
            rules.get('rules_json'), datetime.now().isoformat()
        ))
        print(f'新增联赛 {league_id} 2026赛季规则')

    updated += 1

conn.commit()
conn.close()
print(f'\n共更新/新增 {updated} 条联赛规则')
