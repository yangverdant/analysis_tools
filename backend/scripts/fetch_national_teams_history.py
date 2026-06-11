"""
获取主要国家队的完整比赛历史数据
"""

import json
import urllib.request
import time
from pathlib import Path

DATA_DIR = Path('d:/football_tools')
OUTPUT_DIR = DATA_DIR / 'national_teams_data'
OUTPUT_DIR.mkdir(exist_ok=True)

API_KEY = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'
BASE_URL = 'https://apiv3.apifootball.com'

# 主要国家队列表（按FIFA排名前列）
TOP_NATIONAL_TEAMS = [
    # 南美
    ('Argentina', 66, '阿根廷'),
    ('Brazil', 75, '巴西'),
    ('Uruguay', 115, '乌拉圭'),
    ('Colombia', 94, '哥伦比亚'),
    ('Chile', 91, '智利'),
    ('Peru', 110, '秘鲁'),
    ('Ecuador', 101, '厄瓜多尔'),
    ('Venezuela', 119, '委内瑞拉'),
    ('Paraguay', 111, '巴拉圭'),
    ('Bolivia', 85, '玻利维亚'),

    # 欧洲
    ('France', 22, '法国'),
    ('England', 10, '英格兰'),
    ('Spain', 9, '西班牙'),
    ('Germany', 34, '德国'),
    ('Netherlands', 82, '荷兰'),
    ('Portugal', 95, '葡萄牙'),
    ('Belgium', 7, '比利时'),
    ('Italy', 54, '意大利'),
    ('Croatia', 50, '克罗地亚'),
    ('Switzerland', 166, '瑞士'),
    ('Denmark', 59, '丹麦'),
    ('Poland', 96, '波兰'),
    ('Ukraine', 179, '乌克兰'),
    ('Serbia', 159, '塞尔维亚'),
    ('Austria', 5, '奥地利'),
    ('Czech Republic', 52, '捷克'),
    ('Turkey', 174, '土耳其'),
    ('Hungary', 48, '匈牙利'),
    ('Romania', 129, '罗马尼亚'),
    ('Sweden', 163, '瑞典'),
    ('Norway', 88, '挪威'),
    ('Scotland', 140, '苏格兰'),
    ('Wales', 183, '威尔士'),
    ('Ireland', 55, '爱尔兰'),
    ('Greece', 42, '希腊'),
    ('Russia', 132, '俄罗斯'),

    # 非洲
    ('Senegal', 149, '塞内加尔'),
    ('Morocco', 79, '摩洛哥'),
    ('Egypt', 60, '埃及'),
    ('Nigeria', 86, '尼日利亚'),
    ('Cameroon', 27, '喀麦隆'),
    ('Ghana', 40, '加纳'),
    ('Algeria', 42, '阿尔及利亚'),
    ('Tunisia', 172, '突尼斯'),
    ('Ivory Coast', 56, '科特迪瓦'),
    ('South Africa', 158, '南非'),

    # 中北美
    ('USA', 180, '美国'),
    ('Mexico', 77, '墨西哥'),
    ('Canada', 28, '加拿大'),
    ('Costa Rica', 46, '哥斯达黎加'),
    ('Jamaica', 62, '牙买加'),
    ('Panama', 92, '巴拿马'),

    # 亚洲
    ('Japan', 61, '日本'),
    ('South Korea', 156, '韩国'),
    ('Iran', 53, '伊朗'),
    ('Australia', 6, '澳大利亚'),
    ('Saudi Arabia', 138, '沙特阿拉伯'),
    ('Qatar', 102, '卡塔尔'),
    ('China', 31, '中国'),
    ('Uzbekistan', 181, '乌兹别克斯坦'),
    ('Iraq', 49, '伊拉克'),
    ('United Arab Emirates', 176, '阿联酋'),
    ('Oman', 87, '阿曼'),
    ('Jordan', 64, '约旦'),
    ('Bahrain', 13, '巴林'),
    ('Vietnam', 182, '越南'),
    ('Thailand', 165, '泰国'),
    ('Syria', 167, '叙利亚'),
    ('Palestine', 93, '巴勒斯坦'),
    ('India', 47, '印度'),
    ('North Korea', 84, '朝鲜'),
    ('Lebanon', 68, '黎巴嫩'),
    ('Kyrgyzstan', 67, '吉尔吉斯斯坦'),
    ('Tajikistan', 168, '塔吉克斯坦'),
]


def fetch_team_matches(team_name, team_id, team_cn):
    """获取球队的所有比赛"""
    print(f"\n{team_cn} ({team_name}) - Team ID: {team_id}")
    print("-" * 50)

    all_matches = []
    seasons = ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', '2010']

    for season in seasons:
        # 获取该年度的比赛
        url = f"{BASE_URL}/?action=get_events&APIkey={API_KEY}&team_id={team_id}&from={season}-01-01&to={season}-12-31"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode('utf-8'))

                if isinstance(data, list) and len(data) > 0:
                    all_matches.extend(data)
                    print(f"  {season}: {len(data)} 场")
                else:
                    pass  # 无数据

        except Exception as e:
            pass

        time.sleep(0.3)

    # 保存数据
    if all_matches:
        # 去重
        seen = set()
        unique_matches = []
        for m in all_matches:
            mid = m.get('match_id')
            if mid and mid not in seen:
                seen.add(mid)
                unique_matches.append(m)

        filename = f"{team_id}_{team_name.replace(' ', '_')}.json"
        filepath = OUTPUT_DIR / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(unique_matches, f, ensure_ascii=False, indent=2)

        print(f"  总计: {len(unique_matches)} 场比赛 (保存到 {filename})")
        return len(unique_matches)

    return 0


def main():
    print("=" * 70)
    print("获取主要国家队完整比赛历史")
    print("=" * 70)

    total_matches = 0
    team_stats = []

    for team_name, team_id, team_cn in TOP_NATIONAL_TEAMS:
        matches = fetch_team_matches(team_name, team_id, team_cn)
        total_matches += matches
        team_stats.append((team_cn, matches))
        time.sleep(0.5)

    # 汇总
    print("\n" + "=" * 70)
    print("数据获取汇总")
    print("=" * 70)

    for name, matches in sorted(team_stats, key=lambda x: -x[1]):
        print(f"  {name}: {matches} 场")

    print(f"\n总计: {total_matches} 场比赛")
    print(f"数据保存在: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()