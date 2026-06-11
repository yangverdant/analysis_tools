#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
联赛信息API
- 获取联赛规则（升降级、欧战资格等）
- 获取积分榜
- 获取赛季信息
"""

import os
import sys
import pandas as pd
from pathlib import Path
import json

DATA_DIR = Path("data")
RULES_FILE = DATA_DIR / "09_other_data/league_rules/league_rules.json"

# 加载规则数据
_rules_cache = None

def _load_rules():
    global _rules_cache
    if _rules_cache is None:
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                _rules_cache = json.load(f)
        except:
            _rules_cache = {}
    return _rules_cache

def get_league_info(league_code):
    """
    获取联赛完整信息

    返回:
        dict: 联赛规则、升降级、欧战资格等信息
    """
    rules = _load_rules()

    if league_code not in rules:
        return None

    info = rules[league_code].copy()

    # 格式化关键信息
    result = {
        'code': league_code,
        'name': info.get('name', ''),
        'name_en': info.get('name_en', ''),
        'country': info.get('country', ''),
        'founded': info.get('founded', ''),
        'teams': info.get('teams', 0),

        # 赛制
        'format': info.get('format', {}),

        # 升降级
        'promotion_relegation': info.get('promotion_relegation', {}),

        # 欧战资格
        'qualification': info.get('qualification', {}),

        # 球队规则
        'squad_rules': info.get('squad_rules', {}),

        # 转会规则
        'transfer_rules': info.get('transfer_rules', {}),

        # 比赛规则
        'match_rules': info.get('match_rules', {}),

        # 财政规则
        'financial_rules': info.get('financial_rules', {}),

        # 奖金
        'prize_money': info.get('prize_money', {}),
    }

    return result

def get_qualification_rules(league_code):
    """
    获取欧战/升降级资格规则

    返回:
        dict: {
            'champions_league': {'spots': 4, 'positions': [1,2,3,4]},
            'europa_league': {'spots': 2, 'positions': [5,6]},
            'conference_league': {'spots': 1, 'positions': [7]},
            'relegation': {'spots': 3, 'positions': [18,19,20]}
        }
    """
    info = get_league_info(league_code)
    if not info:
        return None

    result = {}

    # 欧战资格
    qual = info.get('qualification', {})
    for comp, details in qual.items():
        result[comp] = {
            'spots': details.get('spots', 0),
            'description': details.get('description', ''),
        }

    # 降级
    pro_rel = info.get('promotion_relegation', {})
    if 'relegation' in pro_rel:
        result['relegation'] = {
            'spots': pro_rel['relegation'].get('spots', 0),
            'description': pro_rel['relegation'].get('description', ''),
        }

    return result

def get_standings_with_info(competition_type, competition_code, season):
    """
    获取积分榜，附带联赛规则信息

    返回:
        dict: {
            'standings': DataFrame,
            'info': dict (联赛规则),
            'qualification': dict (资格规则)
        }
    """
    from standings_api import get_standings

    standings = get_standings(competition_type, competition_code, season)

    result = {
        'standings': standings,
        'info': get_league_info(competition_code),
        'qualification': get_qualification_rules(competition_code),
        'season': season,
    }

    return result

def list_all_leagues():
    """列出所有联赛及其规则"""
    rules = _load_rules()

    leagues = []
    for code, info in rules.items():
        leagues.append({
            'code': code,
            'name': info.get('name', ''),
            'name_en': info.get('name_en', ''),
            'country': info.get('country', ''),
            'teams': info.get('teams', 0),
        })

    return leagues

def demo():
    """演示用法"""
    print("="*70)
    print("联赛信息API演示")
    print("="*70)

    # 1. 获取英超完整信息
    print("\n【英超联赛信息】")
    info = get_league_info('premier_league')
    if info:
        print(f"名称: {info['name']} ({info['name_en']})")
        print(f"国家: {info['country']}")
        print(f"成立: {info['founded']}年")
        print(f"球队数: {info['teams']}")

    # 2. 获取欧战资格规则
    print("\n【英超欧战资格规则】")
    qual = get_qualification_rules('premier_league')
    if qual:
        for comp, details in qual.items():
            print(f"  {comp}: {details.get('spots', 0)}个名额 - {details.get('description', '')}")

    # 3. 获取积分榜+规则
    print("\n【英超2025-26积分榜 + 资格标记】")
    data = get_standings_with_info('01_europe_leagues', 'premier_league', '2025-2026')
    if data['standings'] is not None:
        df = data['standings'].head(7).copy()
        # 添加资格标记
        qual = data['qualification']
        if qual and 'champions_league' in qual:
            spots = qual['champions_league'].get('spots', 0)
            df['Qualification'] = df['Position'].apply(
                lambda x: 'CL' if x <= spots else ('EL' if x <= spots + 2 else '')
            )
        print(df[['Position', 'Team', 'Points', 'Qualification']].to_string(index=False))

    # 4. 列出所有联赛
    print("\n【所有联赛列表】")
    leagues = list_all_leagues()
    for league in leagues[:10]:
        print(f"  {league['code']}: {league['name']} ({league['country']})")

if __name__ == "__main__":
    demo()