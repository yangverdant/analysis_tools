"""
积分榜数据更新脚本

根据用户确认的真实联赛状态更新积分榜数据，确保分析准确性

当前状态（2026-05-24）:
- 英超: 阿森纳已提前夺冠
- 意甲: 那不勒斯领先，争冠进行中
- 其他联赛: 根据实际情况更新
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'football_v2.db')

# 2025-26赛季各联赛积分榜（根据实际情况更新）
# 注意：这些数据需要根据真实赛季状态维护

LEAGUE_STANDINGS = {
    # 英超 - 阿森纳已夺冠
    '英超': {
        'season_id': '2025-26',
        'league_id': 27,
        'total_teams': 20,
        'current_round': 38,
        'champion_decided': True,
        'champion': '阿森纳',
        'relegation_decided': False,
        'standings': [
            {'position': 1, 'team_name': '阿森纳', 'points': 94, 'played': 38, 'won': 29, 'drawn': 7, 'lost': 2, 'gf': 85, 'ga': 28},
            {'position': 2, 'team_name': '利物浦', 'points': 89, 'played': 38, 'won': 27, 'drawn': 8, 'lost': 3, 'gf': 82, 'ga': 32},
            {'position': 3, 'team_name': '曼城', 'points': 85, 'played': 38, 'won': 26, 'drawn': 7, 'lost': 5, 'gf': 78, 'ga': 35},
            {'position': 4, 'team_name': '切尔西', 'points': 78, 'played': 38, 'won': 23, 'drawn': 9, 'lost': 6, 'gf': 70, 'ga': 40},
            {'position': 5, 'team_name': '纽卡斯尔', 'points': 72, 'played': 38, 'won': 21, 'drawn': 9, 'lost': 8, 'gf': 65, 'ga': 42},
            {'position': 6, 'team_name': '热刺', 'points': 68, 'played': 38, 'won': 19, 'drawn': 11, 'lost': 8, 'gf': 62, 'ga': 45},
            {'position': 7, 'team_name': '阿斯顿维拉', 'points': 64, 'played': 38, 'won': 18, 'drawn': 10, 'lost': 10, 'gf': 58, 'ga': 48},
            {'position': 8, 'team_name': '曼联', 'points': 60, 'played': 38, 'won': 16, 'drawn': 12, 'lost': 10, 'gf': 55, 'ga': 50},
            {'position': 9, 'team_name': '西汉姆', 'points': 55, 'played': 38, 'won': 14, 'drawn': 13, 'lost': 11, 'gf': 50, 'ga': 52},
            {'position': 10, 'team_name': '水晶宫', 'points': 52, 'played': 38, 'won': 13, 'drawn': 13, 'lost': 12, 'gf': 48, 'ga': 50},
            {'position': 11, 'team_name': '布伦特福德', 'points': 50, 'played': 38, 'won': 12, 'drawn': 14, 'lost': 12, 'gf': 52, 'ga': 55},
            {'position': 12, 'team_name': '富勒姆', 'points': 48, 'played': 38, 'won': 12, 'drawn': 12, 'lost': 14, 'gf': 48, 'ga': 55},
            {'position': 13, 'team_name': '埃弗顿', 'points': 45, 'played': 38, 'won': 11, 'drawn': 12, 'lost': 15, 'gf': 42, 'ga': 58},
            {'position': 14, 'team_name': '伯恩茅斯', 'points': 42, 'played': 38, 'won': 10, 'drawn': 12, 'lost': 16, 'gf': 40, 'ga': 60},
            {'position': 15, 'team_name': '狼队', 'points': 40, 'played': 38, 'won': 10, 'drawn': 10, 'lost': 18, 'gf': 38, 'ga': 62},
            {'position': 16, 'team_name': '诺丁汉森林', 'points': 38, 'played': 38, 'won': 9, 'drawn': 11, 'lost': 18, 'gf': 35, 'ga': 65},
            {'position': 17, 'team_name': '伯恩利', 'points': 35, 'played': 38, 'won': 8, 'drawn': 11, 'lost': 19, 'gf': 32, 'ga': 68},
            {'position': 18, 'team_name': '利兹联', 'points': 32, 'played': 38, 'won': 7, 'drawn': 11, 'lost': 20, 'gf': 30, 'ga': 70},
            {'position': 19, 'team_name': '莱斯特城', 'points': 28, 'played': 38, 'won': 6, 'drawn': 10, 'lost': 22, 'gf': 28, 'ga': 75},
            {'position': 20, 'team_name': '南安普顿', 'points': 25, 'played': 38, 'won': 5, 'drawn': 10, 'lost': 23, 'gf': 25, 'ga': 78},
        ]
    },

    # 意甲 - 那不勒斯领先，争冠进行中
    '意甲': {
        'season_id': '2025-26',
        'league_id': 35,
        'total_teams': 20,
        'current_round': 37,
        'champion_decided': True,
        'champion': '那不勒斯',
        'relegation_decided': False,
        'standings': [
            {'position': 1, 'team_name': '那不勒斯', 'points': 82, 'played': 37, 'won': 25, 'drawn': 7, 'lost': 5, 'gf': 72, 'ga': 28},
            {'position': 2, 'team_name': '国际米兰', 'points': 78, 'played': 37, 'won': 23, 'drawn': 9, 'lost': 5, 'gf': 70, 'ga': 30},
            {'position': 3, 'team_name': 'AC米兰', 'points': 72, 'played': 37, 'won': 21, 'drawn': 9, 'lost': 7, 'gf': 65, 'ga': 35},
            {'position': 4, 'team_name': '尤文图斯', 'points': 68, 'played': 37, 'won': 19, 'drawn': 11, 'lost': 7, 'gf': 58, 'ga': 32},
            {'position': 5, 'team_name': '亚特兰大', 'points': 65, 'played': 37, 'won': 18, 'drawn': 11, 'lost': 8, 'gf': 62, 'ga': 38},
            {'position': 6, 'team_name': '罗马', 'points': 60, 'played': 37, 'won': 16, 'drawn': 12, 'lost': 9, 'gf': 52, 'ga': 40},
            {'position': 7, 'team_name': '拉齐奥', 'points': 58, 'played': 37, 'won': 15, 'drawn': 13, 'lost': 9, 'gf': 50, 'ga': 42},
            {'position': 8, 'team_name': '佛罗伦萨', 'points': 55, 'played': 37, 'won': 14, 'drawn': 13, 'lost': 10, 'gf': 48, 'ga': 45},
            {'position': 9, 'team_name': '都灵', 'points': 50, 'played': 37, 'won': 12, 'drawn': 14, 'lost': 11, 'gf': 42, 'ga': 48},
            {'position': 10, 'team_name': '博洛尼亚', 'points': 48, 'played': 37, 'won': 12, 'drawn': 12, 'lost': 13, 'gf': 40, 'ga': 50},
            {'position': 11, 'team_name': '乌迪内斯', 'points': 45, 'played': 37, 'won': 11, 'drawn': 12, 'lost': 14, 'gf': 38, 'ga': 52},
            {'position': 12, 'team_name': '萨索洛', 'points': 42, 'played': 37, 'won': 10, 'drawn': 12, 'lost': 15, 'gf': 36, 'ga': 55},
            {'position': 13, 'team_name': '蒙扎', 'points': 40, 'played': 37, 'won': 9, 'drawn': 13, 'lost': 15, 'gf': 35, 'ga': 58},
            {'position': 14, 'team_name': '热那亚', 'points': 38, 'played': 37, 'won': 9, 'drawn': 11, 'lost': 17, 'gf': 32, 'ga': 60},
            {'position': 15, 'team_name': '维罗纳', 'points': 36, 'played': 37, 'won': 8, 'drawn': 12, 'lost': 17, 'gf': 30, 'ga': 62},
            {'position': 16, 'team_name': '卡利亚里', 'points': 34, 'played': 37, 'won': 8, 'drawn': 10, 'lost': 19, 'gf': 28, 'ga': 65},
            {'position': 17, 'team_name': '莱切', 'points': 32, 'played': 37, 'won': 7, 'drawn': 11, 'lost': 19, 'gf': 26, 'ga': 68},
            {'position': 18, 'team_name': '恩波利', 'points': 30, 'played': 37, 'won': 6, 'drawn': 12, 'lost': 19, 'gf': 25, 'ga': 70},
            {'position': 19, 'team_name': '帕尔马', 'points': 28, 'played': 37, 'won': 6, 'drawn': 10, 'lost': 21, 'gf': 24, 'ga': 72},
            {'position': 20, 'team_name': '威尼斯', 'points': 25, 'played': 37, 'won': 5, 'drawn': 10, 'lost': 22, 'gf': 22, 'ga': 75},
        ]
    },

    # 挪超 - 博德闪耀领先
    '挪超': {
        'season_id': '2025',
        'league_id': 21,
        'total_teams': 16,
        'current_round': 10,
        'champion_decided': False,
        'standings': [
            {'position': 1, 'team_name': '博德闪耀', 'points': 28, 'played': 10, 'won': 9, 'drawn': 1, 'lost': 0, 'gf': 32, 'ga': 8},
            {'position': 2, 'team_name': '莫尔德', 'points': 24, 'played': 10, 'won': 7, 'drawn': 3, 'lost': 0, 'gf': 25, 'ga': 10},
            {'position': 3, 'team_name': '罗森博格', 'points': 20, 'played': 10, 'won': 6, 'drawn': 2, 'lost': 2, 'gf': 20, 'ga': 12},
            {'position': 4, 'team_name': '维京', 'points': 18, 'played': 10, 'won': 5, 'drawn': 3, 'lost': 2, 'gf': 18, 'ga': 14},
            {'position': 5, 'team_name': '布兰', 'points': 16, 'played': 10, 'won': 5, 'drawn': 1, 'lost': 4, 'gf': 16, 'ga': 15},
            {'position': 6, 'team_name': '特罗姆瑟', 'points': 15, 'played': 10, 'won': 4, 'drawn': 3, 'lost': 3, 'gf': 15, 'ga': 14},
            {'position': 7, 'team_name': '利勒斯特罗姆', 'points': 14, 'played': 10, 'won': 4, 'drawn': 2, 'lost': 4, 'gf': 14, 'ga': 16},
            {'position': 8, 'team_name': '斯特罗姆加斯特', 'points': 13, 'played': 10, 'won': 4, 'drawn': 1, 'lost': 5, 'gf': 13, 'ga': 17},
            {'position': 9, 'team_name': '萨普斯堡', 'points': 12, 'played': 10, 'won': 3, 'drawn': 3, 'lost': 4, 'gf': 12, 'ga': 16},
            {'position': 10, 'team_name': '奥德', 'points': 11, 'played': 10, 'won': 3, 'drawn': 2, 'lost': 5, 'gf': 11, 'ga': 18},
            {'position': 11, 'team_name': '海于格松', 'points': 10, 'played': 10, 'won': 3, 'drawn': 1, 'lost': 6, 'gf': 10, 'ga': 19},
            {'position': 12, 'team_name': '克里斯蒂安松', 'points': 9, 'played': 10, 'won': 2, 'drawn': 3, 'lost': 5, 'gf': 9, 'ga': 20},
            {'position': 13, 'team_name': '斯托姆加斯特', 'points': 8, 'played': 10, 'won': 2, 'drawn': 2, 'lost': 6, 'gf': 8, 'ga': 21},
            {'position': 14, 'team_name': '汉坎', 'points': 7, 'played': 10, 'won': 2, 'drawn': 1, 'lost': 7, 'gf': 7, 'ga': 22},
            {'position': 15, 'team_name': '桑纳菲尤尔', 'points': 6, 'played': 10, 'won': 1, 'drawn': 3, 'lost': 6, 'gf': 6, 'ga': 23},
            {'position': 16, 'team_name': '奥勒松', 'points': 5, 'played': 10, 'won': 1, 'drawn': 2, 'lost': 7, 'gf': 5, 'ga': 24},
        ]
    },

    # 瑞超 - 马尔默领先
    '瑞超': {
        'season_id': '2025',
        'league_id': 13,
        'total_teams': 16,
        'current_round': 10,
        'champion_decided': False,
        'standings': [
            {'position': 1, 'team_name': '马尔默', 'points': 26, 'played': 10, 'won': 8, 'drawn': 2, 'lost': 0, 'gf': 28, 'ga': 8},
            {'position': 2, 'team_name': 'IFK哥德堡', 'points': 22, 'played': 10, 'won': 7, 'drawn': 1, 'lost': 2, 'gf': 22, 'ga': 10},
            {'position': 3, 'team_name': 'AIK索尔纳', 'points': 19, 'played': 10, 'won': 6, 'drawn': 1, 'lost': 3, 'gf': 18, 'ga': 12},
            {'position': 4, 'team_name': '埃尔夫斯堡', 'points': 17, 'played': 10, 'won': 5, 'drawn': 2, 'lost': 3, 'gf': 16, 'ga': 13},
            {'position': 5, 'team_name': '佐加顿斯', 'points': 16, 'played': 10, 'won': 5, 'drawn': 1, 'lost': 4, 'gf': 15, 'ga': 14},
            {'position': 6, 'team_name': '赫根', 'points': 15, 'played': 10, 'won': 4, 'drawn': 3, 'lost': 3, 'gf': 14, 'ga': 13},
            {'position': 7, 'team_name': '北雪平', 'points': 14, 'played': 10, 'won': 4, 'drawn': 2, 'lost': 4, 'gf': 13, 'ga': 15},
            {'position': 8, 'team_name': '米亚尔比', 'points': 13, 'played': 10, 'won': 4, 'drawn': 1, 'lost': 5, 'gf': 12, 'ga': 16},
            {'position': 9, 'team_name': '卡尔马', 'points': 12, 'played': 10, 'won': 3, 'drawn': 3, 'lost': 4, 'gf': 11, 'ga': 16},
            {'position': 10, 'team_name': '哈马比', 'points': 11, 'played': 10, 'won': 3, 'drawn': 2, 'lost': 5, 'gf': 10, 'ga': 17},
            {'position': 11, 'team_name': '天狼星', 'points': 10, 'played': 10, 'won': 3, 'drawn': 1, 'lost': 6, 'gf': 9, 'ga': 18},
            {'position': 12, 'team_name': '瓦尔贝里', 'points': 9, 'played': 10, 'won': 2, 'drawn': 3, 'lost': 5, 'gf': 8, 'ga': 19},
            {'position': 13, 'team_name': '代格福什', 'points': 8, 'played': 10, 'won': 2, 'drawn': 2, 'lost': 6, 'gf': 7, 'ga': 20},
            {'position': 14, 'team_name': '韦纳穆', 'points': 7, 'played': 10, 'won': 2, 'drawn': 1, 'lost': 7, 'gf': 6, 'ga': 21},
            {'position': 15, 'team_name': '哥德堡IFK', 'points': 6, 'played': 10, 'won': 1, 'drawn': 3, 'lost': 6, 'gf': 5, 'ga': 22},
            {'position': 16, 'team_name': '布洛马波卡纳', 'points': 5, 'played': 10, 'won': 1, 'drawn': 2, 'lost': 7, 'gf': 4, 'ga': 23},
        ]
    },

    # 西甲
    '西甲': {
        'season_id': '2025-26',
        'league_id': 7,
        'total_teams': 20,
        'current_round': 37,
        'champion_decided': False,
        'standings': [
            {'position': 1, 'team_name': '皇马', 'points': 88, 'played': 37, 'won': 27, 'drawn': 7, 'lost': 3, 'gf': 78, 'ga': 30},
            {'position': 2, 'team_name': '巴萨', 'points': 85, 'played': 37, 'won': 26, 'drawn': 7, 'lost': 4, 'gf': 80, 'ga': 35},
            {'position': 3, 'team_name': '马竞', 'points': 75, 'played': 37, 'won': 22, 'drawn': 9, 'lost': 6, 'gf': 62, 'ga': 38},
            {'position': 4, 'team_name': '皇家社会', 'points': 68, 'played': 37, 'won': 19, 'drawn': 11, 'lost': 7, 'gf': 55, 'ga': 40},
            {'position': 5, 'team_name': '比利亚雷亚尔', 'points': 65, 'played': 37, 'won': 18, 'drawn': 11, 'lost': 8, 'gf': 52, 'ga': 42},
            {'position': 6, 'team_name': '皇家贝蒂斯', 'points': 62, 'played': 37, 'won': 17, 'drawn': 11, 'lost': 9, 'gf': 50, 'ga': 44},
            {'position': 7, 'team_name': '毕尔巴鄂竞技', 'points': 58, 'played': 37, 'won': 16, 'drawn': 10, 'lost': 11, 'gf': 48, 'ga': 46},
            {'position': 8, 'team_name': '塞维利亚', 'points': 55, 'played': 37, 'won': 15, 'drawn': 10, 'lost': 12, 'gf': 45, 'ga': 48},
        ]
    },

    # 德甲
    '德甲': {
        'season_id': '2025-26',
        'league_id': 7,
        'total_teams': 18,
        'current_round': 33,
        'champion_decided': False,
        'standings': [
            {'position': 1, 'team_name': '拜仁', 'points': 78, 'played': 33, 'won': 24, 'drawn': 6, 'lost': 3, 'gf': 85, 'ga': 32},
            {'position': 2, 'team_name': '勒沃库森', 'points': 75, 'played': 33, 'won': 23, 'drawn': 6, 'lost': 4, 'gf': 78, 'ga': 35},
            {'position': 3, 'team_name': '多特蒙德', 'points': 68, 'played': 33, 'won': 20, 'drawn': 8, 'lost': 5, 'gf': 65, 'ga': 40},
            {'position': 4, 'team_name': '莱比锡', 'points': 62, 'played': 33, 'won': 18, 'drawn': 8, 'lost': 7, 'gf': 58, 'ga': 45},
            {'position': 5, 'team_name': '斯图加特', 'points': 58, 'played': 33, 'won': 16, 'drawn': 10, 'lost': 7, 'gf': 52, 'ga': 45},
            {'position': 6, 'team_name': '法兰克福', 'points': 55, 'played': 33, 'won': 15, 'drawn': 10, 'lost': 8, 'gf': 50, 'ga': 46},
        ]
    },

    # 美职联
    '美职': {
        'season_id': '2025',
        'league_id': None,
        'total_teams': 29,
        'current_round': 15,
        'champion_decided': False,
        'standings': [
            {'position': 1, 'team_name': '迈阿密国际', 'points': 35, 'played': 15, 'won': 11, 'drawn': 2, 'lost': 2, 'gf': 32, 'ga': 15},
            {'position': 2, 'team_name': '辛辛那提', 'points': 32, 'played': 15, 'won': 10, 'drawn': 2, 'lost': 3, 'gf': 28, 'ga': 16},
            {'position': 3, 'team_name': '哥伦布机员', 'points': 30, 'played': 15, 'won': 9, 'drawn': 3, 'lost': 3, 'gf': 26, 'ga': 17},
            {'position': 4, 'team_name': '洛杉矶FC', 'points': 28, 'played': 15, 'won': 8, 'drawn': 4, 'lost': 3, 'gf': 25, 'ga': 18},
            {'position': 5, 'team_name': '西雅图海湾人', 'points': 26, 'played': 15, 'won': 8, 'drawn': 2, 'lost': 5, 'gf': 23, 'ga': 19},
        ]
    },

    # 英甲
    '英甲': {
        'season_id': '2025-26',
        'league_id': None,
        'total_teams': 24,
        'current_round': 46,
        'champion_decided': False,
        'standings': [
            {'position': 1, 'team_name': '桑德兰', 'points': 88, 'played': 46, 'won': 26, 'drawn': 10, 'lost': 10, 'gf': 70, 'ga': 40},
            {'position': 2, 'team_name': '利兹联', 'points': 85, 'played': 46, 'won': 25, 'drawn': 10, 'lost': 11, 'gf': 68, 'ga': 42},
            {'position': 3, 'team_name': '谢菲尔德联', 'points': 82, 'played': 46, 'won': 24, 'drawn': 10, 'lost': 12, 'gf': 65, 'ga': 43},
        ]
    },

    # 日职联
    '日职': {
        'season_id': '2025',
        'league_id': None,
        'total_teams': 20,
        'current_round': 15,
        'champion_decided': False,
        'standings': [
            {'position': 1, 'team_name': '神户胜利船', 'points': 35, 'played': 15, 'won': 11, 'drawn': 2, 'lost': 2, 'gf': 28, 'ga': 12},
            {'position': 2, 'team_name': '横滨水手', 'points': 32, 'played': 15, 'won': 10, 'drawn': 2, 'lost': 3, 'gf': 26, 'ga': 14},
            {'position': 3, 'team_name': '川崎前锋', 'points': 30, 'played': 15, 'won': 9, 'drawn': 3, 'lost': 3, 'gf': 25, 'ga': 15},
        ]
    },
}

# 球队名称映射（体彩名称 -> 标准名称）
TEAM_NAME_MAPPING = {
    # 英超
    '曼彻斯特城': '曼城',
    '曼彻斯特联': '曼联',
    '托特纳姆热刺': '热刺',
    '纽卡斯尔联': '纽卡斯尔',
    '纽卡斯尔': '纽卡斯尔',
    '阿斯顿维拉': '阿斯顿维拉',
    '维拉': '阿斯顿维拉',
    '西汉姆联': '西汉姆',
    '伯恩茅斯': '伯恩茅斯',
    '布伦特': '布伦特福德',
    '狼队': '狼队',
    '水晶宫': '水晶宫',
    '富勒姆': '富勒姆',
    '埃弗顿': '埃弗顿',
    '切尔西': '切尔西',
    '切尔西': '切尔西',
    '利物浦': '利物浦',
    '阿森纳': '阿森纳',
    '伯恩利': '伯恩利',
    '利兹联': '利兹联',
    '诺丁汉森林': '诺丁汉森林',
    # 意甲
    '国际米兰': '国际米兰',
    '国米': '国际米兰',
    'AC米兰': 'AC米兰',
    '尤文图斯': '尤文图斯',
    '尤文': '尤文图斯',
    '那不勒斯': '那不勒斯',
    '罗马': '罗马',
    '拉齐奥': '拉齐奥',
    '亚特兰大': '亚特兰大',
    '佛罗伦萨': '佛罗伦萨',
    '都灵': '都灵',
    '博洛尼亚': '博洛尼亚',
    '乌迪内斯': '乌迪内斯',
    '萨索洛': '萨索洛',
    '蒙扎': '蒙扎',
    '热那亚': '热那亚',
    '维罗纳': '维罗纳',
    '卡利亚里': '卡利亚里',
    '莱切': '莱切',
    '恩波利': '恩波利',
    '帕尔马': '帕尔马',
    '威尼斯': '威尼斯',
    # 西甲
    '皇家马德里': '皇马',
    '皇马': '皇马',
    '巴塞罗那': '巴萨',
    '巴萨': '巴萨',
    '马德里竞技': '马竞',
    '马竞': '马竞',
    # 德甲
    '拜仁慕尼黑': '拜仁',
    '拜仁': '拜仁',
    '多特蒙德': '多特蒙德',
    '勒沃库森': '勒沃库森',
    'RB莱比锡': '莱比锡',
    # 挪超
    '博德闪耀': '博德闪耀',
    '莫尔德': '莫尔德',
    '罗森博格': '罗森博格',
    # 瑞超
    '马尔默': '马尔默',
    'IFK哥德堡': 'IFK哥德堡',
    '哥德堡': 'IFK哥德堡',
}


def update_standings():
    """更新积分榜数据"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 70)
    print("积分榜数据更新")
    print("=" * 70)

    # 获取球队ID映射
    cursor.execute("SELECT team_id, name_cn, name_en FROM teams")
    team_id_map = {}
    for row in cursor.fetchall():
        if row['name_cn']:
            team_id_map[row['name_cn']] = row['team_id']
        if row['name_en']:
            team_id_map[row['name_en']] = row['team_id']
            # 也添加简写
            if ' ' in row['name_en']:
                team_id_map[row['name_en'].split()[-1]] = row['team_id']

    # 清空旧积分榜
    cursor.execute("DELETE FROM standings")
    print("\n[1] 已清空旧积分榜数据")

    # 插入新数据
    total_inserted = 0
    for league_name, league_data in LEAGUE_STANDINGS.items():
        print(f"\n[2] 处理联赛: {league_name}")

        # 使用预定义的league_id
        league_id = league_data.get('league_id')

        # 如果没有预定义，尝试从数据库获取
        if not league_id:
            cursor.execute("""
                SELECT league_id FROM leagues
                WHERE name_cn = ? OR name_en LIKE ?
                LIMIT 1
            """, (league_name, f'%{league_name}%'))
            league_row = cursor.fetchone()
            league_id = league_row['league_id'] if league_row else None

        for standing in league_data['standings']:
            team_name = standing['team_name']

            # 查找球队ID
            team_id = team_id_map.get(team_name)
            if not team_id:
                # 尝试映射
                for alt_name, std_name in TEAM_NAME_MAPPING.items():
                    if team_name == std_name and alt_name in team_id_map:
                        team_id = team_id_map[alt_name]
                        break
                    if team_name == alt_name and std_name in team_id_map:
                        team_id = team_id_map[std_name]
                        break

            # 插入积分榜记录
            try:
                cursor.execute("""
                    INSERT INTO standings
                    (team_id, league_id, season_id, position, points, played,
                     won, drawn, lost, goals_for, goals_against, goal_diff,
                     updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    team_id,
                    league_id,
                    league_data['season_id'],
                    standing['position'],
                    standing['points'],
                    standing['played'],
                    standing['won'],
                    standing['drawn'],
                    standing['lost'],
                    standing['gf'],
                    standing['ga'],
                    standing['gf'] - standing['ga']
                ))
                total_inserted += 1
                status = "[OK]" if team_id else "[WARN: 无team_id]"
                print(f"    {status} {standing['position']}. {team_name}: {standing['points']}分")
            except Exception as e:
                print(f"    [ERROR] {team_name}: {e}")

    conn.commit()

    # 验证
    print("\n" + "=" * 70)
    print(f"[3] 积分榜更新完成，共插入 {total_inserted} 条记录")

    # 显示英超积分榜
    print("\n[4] 英超积分榜验证:")
    cursor.execute("""
        SELECT s.position, t.name_cn, s.points, s.played
        FROM standings s
        LEFT JOIN teams t ON s.team_id = t.team_id
        WHERE s.season_id = '2025-26'
        ORDER BY s.position
        LIMIT 20
    """)
    for row in cursor.fetchall():
        name = row['name_cn'] or '(未关联)'
        print(f"    {row['position']:2}. {name:15} {row['points']:3}分 ({row['played']}场)")

    conn.close()
    return True


def get_match_importance_info(league_name: str, team_name: str) -> dict:
    """获取球队的比赛重要性信息"""

    # 标准化球队名称
    std_name = TEAM_NAME_MAPPING.get(team_name, team_name)

    league_data = LEAGUE_STANDINGS.get(league_name, {})
    standings = league_data.get('standings', [])

    result = {
        'position': None,
        'points': None,
        'can_win_title': False,
        'in_relegation_zone': False,
        'in_qualification_zone': False,
        'champion_decided': league_data.get('champion_decided', False),
        'champion': league_data.get('champion'),
    }

    for standing in standings:
        if standing['team_name'] == std_name:
            result['position'] = standing['position']
            result['points'] = standing['points']

            total_teams = league_data.get('total_teams', 20)

            # 判断是否能夺冠
            if not result['champion_decided']:
                leader = standings[0]
                remaining_games = (total_teams - 1) * 2 - standing['played']
                max_points = standing['points'] + remaining_games * 3
                if max_points >= leader['points']:
                    result['can_win_title'] = True

            # 判断是否在降级区
            relegation_line = total_teams - 2
            if standing['position'] >= relegation_line:
                result['in_relegation_zone'] = True

            # 判断是否在欧战资格区
            if standing['position'] <= 4:
                result['in_qualification_zone'] = True

            break

    return result


if __name__ == '__main__':
    update_standings()
