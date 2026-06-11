"""
数据流转演示脚本 - 展示字段映射完整流程

演示:
1. 体彩官网数据 → lottery_matches 表
2. Sportmonks数据 → matches 表
3. API-Football数据 → matches 表
4. FBref数据 → matches + match_stats 表
5. 多数据源合并
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
from datetime import date

# 模拟各数据源原始数据
SAMPLE_DATA = {
    # 体彩官网返回数据
    'lottery': {
        'matchId': '20260524001',
        'matchNum': '001',
        'homeTeam': '曼联',
        'awayTeam': '利物浦',
        'leagueName': '英超',
        'matchDate': '2026-05-24',
        'matchTime': '22:00:00',
        'beijingTime': '2026-05-24 22:00',
        'sellStatus': 'on',
        'sellEndTime': '2026-05-24 21:30',
        'handicapLine': -1,
        'playTypes': ['spf', 'bf', 'bqc'],
        'spfOdds': {'3': 2.15, '1': 3.20, '0': 3.05}
    },

    # Sportmonks返回数据
    'sportmonks': {
        'id': 12345678,
        'starting_at': '2026-05-24 22:00:00',
        'league_id': 8,
        'season_id': 25659,
        'state_id': 1,
        'venue_id': 500,
        'round': {'name': 'Round 38'},
        'participants': [
            {'id': 585, 'name': 'Manchester United', 'meta': {'location': 'home', 'winner': True}},
            {'id': 561, 'name': 'Liverpool', 'meta': {'location': 'away', 'winner': False}}
        ],
        'scores': [
            {'type': 'halftime', 'home_score': 1, 'away_score': 0},
            {'type': 'fulltime', 'home_score': 2, 'away_score': 1}
        ],
        'referee': {'id': 100, 'common_name': 'Michael Oliver'}
    },

    # API-Football返回数据
    'api_football': {
        'fixture': {
            'id': 987654,
            'date': '2026-05-24',
            'time': '22:00',
            'status': {'short': 'FT', 'long': 'Match Finished'}
        },
        'league': {
            'id': 39,
            'name': 'Premier League',
            'country': 'England'
        },
        'teams': {
            'home': {'id': 33, 'name': 'Manchester United'},
            'away': {'id': 40, 'name': 'Liverpool'}
        },
        'goals': {
            'home': 2,
            'away': 1
        },
        'score': {
            'halftime': {'home': 1, 'away': 0},
            'fulltime': {'home': 2, 'away': 1}
        }
    },

    # FBref爬虫数据
    'fbref': {
        'Date': '2026-05-24',
        'Time': '22:00',
        'HomeTeam': 'Manchester United',
        'AwayTeam': 'Liverpool',
        'FTHG': 2,
        'FTAG': 1,
        'HTHG': 1,
        'HTAG': 0,
        'FTR': 'H',
        'Referee': 'Michael Oliver',
        'HS': 15,
        'AS': 8,
        'HST': 6,
        'AST': 3,
        'HC': 5,
        'AC': 2,
        'HF': 12,
        'AF': 14,
        'HY': 1,
        'AY': 2,
        'HR': 0,
        'AR': 0,
        'home_xg': 1.85,
        'away_xg': 0.92
    },

    # Football-Data.org返回数据
    'football_data_org': {
        'id': 301234,
        'matchday': 38,
        'utcDate': '2026-05-24T22:00:00Z',
        'status': 'FINISHED',
        'homeTeam': {'id': 33, 'shortName': 'Man United', 'tla': 'MUN'},
        'awayTeam': {'id': 40, 'shortName': 'Liverpool', 'tla': 'LIV'},
        'score': {
            'fullTime': {'home': 2, 'away': 1},
            'halfTime': {'home': 1, 'away': 0}
        },
        'competition': {'code': 'PL', 'name': 'Premier League'}
    },

    # TheSportsDB返回数据
    'thesportsdb': {
        'idEvent': '998877',
        'strEvent': 'Manchester United vs Liverpool',
        'dateEvent': '2026-05-24',
        'strTime': '22:00',
        'idHomeTeam': '133604',
        'strHomeTeam': 'Manchester United',
        'idAwayTeam': '133613',
        'strAwayTeam': 'Liverpool',
        'intHomeScore': 2,
        'intAwayScore': 1,
        'idLeague': '4328',
        'strLeague': 'Premier League',
        'strVenue': 'Old Trafford'
    }
}


def demo_field_mapping():
    """演示字段映射"""
    print("\n" + "="*80)
    print("字段映射演示")
    print("="*80)

    # 导入EntityMapper
    from backend.app.lottery.etl.entity_mapper import EntityMapper

    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'football_v2.db')

    mapper = EntityMapper(DB_PATH)

    # 1. 体彩数据映射
    print("\n【1. 体彩官网 → 标准字段】")
    print("-"*80)
    print("原始数据:")
    print(json.dumps(SAMPLE_DATA['lottery'], indent=2, ensure_ascii=False))

    standardized = mapper.map_to_standard('lottery', SAMPLE_DATA['lottery'])
    print("\n标准化后:")
    print(json.dumps(standardized, indent=2, ensure_ascii=False))

    # 球队映射
    print("\n球队名称映射:")
    home_team_id = mapper.get_team_id('曼联')
    away_team_id = mapper.get_team_id('利物浦')
    print(f"  '曼联' → team_id: {home_team_id}")
    print(f"  '利物浦' → team_id: {away_team_id}")

    # 2. Sportmonks数据映射
    print("\n【2. Sportmonks → 标准字段】")
    print("-"*80)
    print("原始数据:")
    print(json.dumps(SAMPLE_DATA['sportmonks'], indent=2, ensure_ascii=False))

    standardized = mapper.map_to_standard('sportmonks', SAMPLE_DATA['sportmonks'])
    print("\n标准化后:")
    print(json.dumps(standardized, indent=2, ensure_ascii=False))

    # 3. API-Football数据映射
    print("\n【3. API-Football → 标准字段】")
    print("-"*80)
    print("原始数据:")
    print(json.dumps(SAMPLE_DATA['api_football'], indent=2, ensure_ascii=False))

    standardized = mapper.map_to_standard('api_football', SAMPLE_DATA['api_football'])
    print("\n标准化后:")
    print(json.dumps(standardized, indent=2, ensure_ascii=False))

    # 4. FBref数据映射
    print("\n【4. FBref → 标准字段】")
    print("-"*80)
    print("原始数据:")
    print(json.dumps(SAMPLE_DATA['fbref'], indent=2, ensure_ascii=False))

    standardized = mapper.map_to_standard('fbref', SAMPLE_DATA['fbref'])
    print("\n标准化后:")
    print(json.dumps(standardized, indent=2, ensure_ascii=False))

    # 5. 多数据源合并
    print("\n【5. 多数据源合并】")
    print("-"*80)

    # 合并sportmonks + fbref (sportmonks优先)
    sources_data = {
        'sportmonks': SAMPLE_DATA['sportmonks'],
        'fbref': SAMPLE_DATA['fbref']
    }

    merged = mapper.merge_multi_source(sources_data)
    print("合并结果 (sportmonks优先，fbref补充xG):")
    print(json.dumps(merged, indent=2, ensure_ascii=False))


def demo_database_flow():
    """演示数据库写入流程"""
    print("\n" + "="*80)
    print("数据库写入流程演示")
    print("="*80)

    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'football_v2.db')

    # 导入DAO
    from backend.app.lottery.dao.lottery_dao import LotteryMatchDAO, LotteryOddsDAO

    match_dao = LotteryMatchDAO(DB_PATH)
    odds_dao = LotteryOddsDAO(DB_PATH)

    # 1. 模拟体彩数据入库
    print("\n【体彩比赛入库】")
    print("-"*80)

    match_data = {
        'lottery_match_id': f"TEST{date.today().strftime('%Y%m%d')}001",
        'match_num': '001',
        'home_team_cn': '曼联',
        'away_team_cn': '利物浦',
        'home_team_id': 585,
        'away_team_id': 561,
        'match_date': str(date.today()),
        'match_time': '22:00',
        'league_name_cn': '英超',
        'sell_status': 'selling',
        'play_types': ['spf', 'bf', 'bqc'],
        'handicap_line': -1
    }

    print("入库数据:")
    print(json.dumps(match_data, indent=2, ensure_ascii=False))

    success = match_dao.insert(match_data)
    print(f"\nDAO.insert() → {'成功' if success else '失败'}")

    # 验证写入
    found = match_dao.find_by_id(match_data['lottery_match_id'])
    if found:
        print("\n数据库查询结果:")
        print(json.dumps(found, indent=2, ensure_ascii=False))

    # 2. 模拟赔率入库
    print("\n【体彩赔率入库】")
    print("-"*80)

    odds_data = {
        'lottery_match_id': match_data['lottery_match_id'],
        'play_type': 'spf',
        'odds_data': json.dumps({'3': 2.15, '1': 3.20, '0': 3.05})
    }

    print("入库数据:")
    print(json.dumps(odds_data, indent=2, ensure_ascii=False))

    success = odds_dao.insert(odds_data)
    print(f"\nDAO.insert() → {'成功' if success else '失败'}")


def demo_flow_diagram():
    """打印数据流转图"""
    print("\n" + "="*80)
    print("完整数据流转图")
    print("="*80)

    # 使用ASCII兼容的流程图
    flow_diagram = """
================================================================================
                         数据源 -> EntityMapper -> DAO -> Database
================================================================================

+---------------+
| 体彩官网API   |
| lottery_crawler|
+-------+-------+
        | 原始字段: matchId, homeTeam, sellStatus...
        v
+---------------+     +---------------------------------------------------------+
| EntityMapper  |     | 字段映射:                                                |
|               |     |   matchId -> lottery_match_id                          |
|               |     |   homeTeam -> home_team_cn                             |
|               |     | 值转换:                                                  |
|               |     |   sellStatus: "on" -> "selling"                        |
|               |     | 球队映射:                                                |
|               |     |   "曼联" -> team_id: 585                               |
+-------+-------+     +---------------------------------------------------------+
        | 标准字段: lottery_match_id, home_team_cn, home_team_id...
        v
+---------------+     +---------------------------------------------------------+
| LotteryMatchDAO|    | SQL:                                                     |
|               |     | INSERT INTO lottery_matches (                           |
|               |     |   lottery_match_id, match_num, home_team_cn, ...       |
|               |     | ) VALUES (?, ?, ?, ...)                                |
+-------+-------+     +---------------------------------------------------------+
        |
        v
+---------------+     +---------------------------------------------------------+
| lottery_matches|    | 数据库表:                                                |
| 表             |     | lottery_match_id | match_num | home_team_cn | home_team_id|
|               |     | 20260524001      | 001       | 曼联          | 585        |
+---------------+     +---------------------------------------------------------+


+---------------+
| Sportmonks API|
+-------+-------+
        | 原始字段: id, starting_at, participants[0].id, scores...
        v
+---------------+     +---------------------------------------------------------+
| EntityMapper  |     | 字段映射:                                                |
|               |     |   id -> match_id                                        |
|               |     |   starting_at -> match_datetime                         |
|               |     |   participants[location=home].id -> home_team_id       |
|               |     |   scores[type=fulltime].home_score -> home_goals       |
+-------+-------+     +---------------------------------------------------------+
        | 标准字段: match_id, match_datetime, home_team_id, home_goals...
        v
+---------------+
| matches 表    |
+---------------+


+---------------+
| FBref 爬虫    |
+-------+-------+
        | 原始字段: Date, HomeTeam, FTHG, HS, home_xg...
        v
+---------------+     +---------------------------------------------------------+
| EntityMapper  |     | 字段映射:                                                |
|               |     |   Date -> match_date                                    |
|               |     |   HomeTeam -> home_team_name                            |
|               |     |   FTHG -> home_goals                                    |
|               |     |   HS -> home_shots                                      |
|               |     |   home_xg -> home_xg                                    |
+-------+-------+     +---------------------------------------------------------+
        | 标准字段: match_date, home_team_name, home_goals, home_shots, home_xg...
        v
+---------------+     +---------------------------------------------------------+
| MatchDAO      |---> | matches 表 (基础信息)                                    |
| StatsDAO      |---> | match_stats 表 (统计信息)                                |
| XGDAO         |---> | match_xg 表 (xG数据)                                     |
+---------------+     +---------------------------------------------------------+


================================================================================
                              多数据源合并
================================================================================

+---------------+     +---------------+     +---------------+
| Sportmonks    |     | FBref         |     | API-Football  |
| (优先级1)     |     | (优先级2)     |     | (优先级3)     |
+-------+-------+     +-------+-------+     +-------+-------+
        |                     |                     |
        +---------------------+---------------------+
                              |
                              v
                 +---------------------------+
                 | EntityMapper.merge_multi_ |
                 | source()                  |
                 |                           |
                 | 策略: 按优先级填充         |
                 | - sportmonks提供基础字段   |
                 | - fbref补充xG数据          |
                 | - api-football补充赔率     |
                 +---------------------------+
                              |
                              v
                 +---------------------------+
                 | 合并后数据                 |
                 | {                         |
                 |   match_id: 12345678,     | <- sportmonks
                 |   match_datetime: "...",  | <- sportmonks
                 |   home_goals: 2,          | <- sportmonks
                 |   home_xg: 1.85,          | <- fbref
                 |   odds: {...},            | <- api-football
                 | }                         |
                 +---------------------------+
"""
    print(flow_diagram)


def main():
    """运行所有演示"""
    demo_flow_diagram()
    demo_field_mapping()
    demo_database_flow()

    print("\n" + "="*80)
    print("演示完成")
    print("="*80)
    print("\n关键文件:")
    print("  - backend/app/lottery/etl/entity_mapper.py  (字段映射核心)")
    print("  - backend/app/lottery/dao/lottery_dao.py     (数据库操作)")
    print("  - backend/app/lottery/FIELD_MAPPING_COMPLETE.md  (完整映射文档)")


if __name__ == '__main__':
    main()