"""
联赛赛季命名规则配置

根据联赛的赛季周期决定命名格式：
1. 跨年赛季（欧洲主流）：使用 YYYY-YYYY 格式，如 2025-2026
2. 不跨年赛季（北欧、南美等）：使用 YYYY 格式，如 2025
"""

# 跨年赛季联赛（8月/9月开始 → 次年5月结束）
CROSS_YEAR_LEAGUES = {
    # 五大联赛
    'premier_league': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'la_liga': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'bundesliga': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'serie_a': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'ligue_1': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},

    # 其他欧洲联赛
    'eredivisie': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'primeira_liga': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'jupiler_pro_league': {'start_month': 7, 'end_month': 5, 'format': 'cross_year'},
    'scottish_premiership': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'austrian_bundesliga': {'start_month': 7, 'end_month': 5, 'format': 'cross_year'},
    'swiss_super_league': {'start_month': 7, 'end_month': 5, 'format': 'cross_year'},
    'turkish_super_lig': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'greek_superleague': {'start_month': 8, 'end_month': 5, 'format': 'cross_year'},
    'russian_premier_league': {'start_month': 7, 'end_month': 5, 'format': 'cross_year'},
    'polish_ekstraklasa': {'start_month': 7, 'end_month': 5, 'format': 'cross_year'},
    'czech_first_league': {'start_month': 7, 'end_month': 5, 'format': 'cross_year'},

    # 欧冠、欧联等
    'champions_league': {'start_month': 9, 'end_month': 6, 'format': 'cross_year'},
    'europa_league': {'start_month': 9, 'end_month': 5, 'format': 'cross_year'},

    # 澳超（跨年）
    'a_league': {'start_month': 10, 'end_month': 5, 'format': 'cross_year'},
}

# 不跨年赛季联赛（当年开始 → 当年结束）
SAME_YEAR_LEAGUES = {
    # 北欧联赛（4月开始 → 11月结束）
    'allsvenskan': {'start_month': 4, 'end_month': 11, 'format': 'same_year', 'country': 'Sweden'},
    'eliteserien': {'start_month': 4, 'end_month': 11, 'format': 'same_year', 'country': 'Norway'},
    'danish_superliga': {'start_month': 7, 'end_month': 5, 'format': 'cross_year', 'country': 'Denmark'},  # 丹麦超跨年
    'veikkausliiga': {'start_month': 4, 'end_month': 10, 'format': 'same_year', 'country': 'Finland'},
    'icelandic_league': {'start_month': 5, 'end_month': 9, 'format': 'same_year', 'country': 'Iceland'},

    # 南美联赛（1月/2月开始 → 11月/12月结束）
    'brasileirao': {'start_month': 4, 'end_month': 12, 'format': 'same_year', 'country': 'Brazil'},
    'argentina_primera': {'start_month': 2, 'end_month': 12, 'format': 'same_year', 'country': 'Argentina'},
    'chilean_primera': {'start_month': 2, 'end_month': 11, 'format': 'same_year', 'country': 'Chile'},
    'colombian_league': {'start_month': 1, 'end_month': 12, 'format': 'same_year', 'country': 'Colombia'},
    'mexican_liga_mx': {'start_month': 1, 'end_month': 12, 'format': 'same_year', 'country': 'Mexico'},

    # 美职联
    'mls': {'start_month': 2, 'end_month': 10, 'format': 'same_year', 'country': 'USA'},

    # 亚洲联赛
    'j_league': {'start_month': 2, 'end_month': 12, 'format': 'same_year', 'country': 'Japan'},
    'k_league': {'start_month': 3, 'end_month': 11, 'format': 'same_year', 'country': 'South Korea'},
    'chinese_super_league': {'start_month': 3, 'end_month': 11, 'format': 'same_year', 'country': 'China'},

    # 国际赛事（夏季举办）
    'world_cup': {'format': 'same_year'},  # 6-7月
    'euro': {'format': 'same_year'},  # 6-7月
    'copa_america': {'format': 'same_year'},  # 6-7月
    'africa_cup': {'format': 'same_year'},  # 1-2月（实际是跨年，但用单年命名）
    'asian_cup': {'format': 'same_year'},  # 1-2月
}

# 杯赛和附加赛（通常跟随所属联赛的赛季格式，但有特殊情况）
CUP_COMPETITIONS = {
    # 国内杯赛 - 跨年格式（跟随欧洲联赛）
    'fa_cup': {'format': 'cross_year', 'country': 'England'},
    'efl_cup': {'format': 'cross_year', 'country': 'England'},  # 联赛杯
    'copa_del_rey': {'format': 'cross_year', 'country': 'Spain'},
    'dfb_pokal': {'format': 'cross_year', 'country': 'Germany'},
    'coppa_italia': {'format': 'cross_year', 'country': 'Italy'},
    'coupe_de_france': {'format': 'cross_year', 'country': 'France'},
    'knvb_cup': {'format': 'cross_year', 'country': 'Netherlands'},
    'turkish_cup': {'format': 'cross_year', 'country': 'Turkey'},

    # 国内杯赛 - 单年格式（跟随北欧/南美联赛）
    'swedish_cup': {'format': 'same_year', 'country': 'Sweden'},
    'norwegian_cup': {'format': 'same_year', 'country': 'Norway'},
    'copa_do_brasil': {'format': 'same_year', 'country': 'Brazil'},
    'emperors_cup': {'format': 'same_year', 'country': 'Japan'},  # 天皇杯

    # 欧洲俱乐部赛事 - 跨年格式
    'champions_league': {'format': 'cross_year'},
    'europa_league': {'format': 'cross_year'},
    'conference_league': {'format': 'cross_year'},

    # 超级杯 - 单场赛事，用举办年份
    'community_shield': {'format': 'same_year', 'country': 'England'},
    'spanish_super_cup': {'format': 'same_year', 'country': 'Spain'},
    'german_super_cup': {'format': 'same_year', 'country': 'Germany'},
    'italian_super_cup': {'format': 'same_year', 'country': 'Italy'},
    'french_super_cup': {'format': 'same_year', 'country': 'France'},

    # 附加赛/升降级赛 - 跟随所属联赛格式
    # 英冠升级附加赛等跟随英冠（跨年）
    'championship_playoff': {'format': 'cross_year', 'country': 'England'},
    # 瑞典超升降级附加赛跟随瑞典超（单年）
    'allsvenskan_playoff': {'format': 'same_year', 'country': 'Sweden'},
}


def get_correct_season_name(league_name: str, year: int) -> str:
    """
    根据联赛和年份返回正确的赛季命名

    Args:
        league_name: 联赛名称（如 'allsvenskan', 'premier_league', 'fa_cup'）
        year: 赛季开始年份

    Returns:
        正确的赛季命名（如 '2025' 或 '2025-2026'）
    """
    league_lower = league_name.lower().replace(' ', '_').replace('-', '_')

    # 检查是否是跨年联赛
    for key in CROSS_YEAR_LEAGUES:
        if key.replace('_', '') in league_lower.replace('_', ''):
            return f"{year}-{year + 1}"

    # 检查是否是不跨年联赛
    for key in SAME_YEAR_LEAGUES:
        if key.replace('_', '') in league_lower.replace('_', ''):
            return str(year)

    # 检查是否是杯赛/附加赛
    for key in CUP_COMPETITIONS:
        if key.replace('_', '') in league_lower.replace('_', ''):
            cup_info = CUP_COMPETITIONS[key]
            if cup_info.get('format') == 'same_year':
                return str(year)
            else:
                return f"{year}-{year + 1}"

    # 默认使用跨年格式（欧洲主流）
    return f"{year}-{year + 1}"


def parse_season_year(season_name: str) -> tuple:
    """
    解析赛季名称，返回开始年份和结束年份

    Args:
        season_name: 赛季名称（如 '2025-2026' 或 '2025'）

    Returns:
        (start_year, end_year)
    """
    if '-' in str(season_name):
        parts = season_name.split('-')
        return int(parts[0]), int(parts[1])
    else:
        year = int(season_name)
        return year, year


# 测试
if __name__ == '__main__':
    print('赛季命名规则测试:')
    print('=' * 60)

    test_cases = [
        # 联赛
        ('premier_league', 2025, '2025-2026'),
        ('allsvenskan', 2025, '2025'),
        ('brasileirao', 2025, '2025'),
        ('la_liga', 2024, '2024-2025'),
        ('mls', 2025, '2025'),
        ('champions_league', 2025, '2025-2026'),
        ('world_cup', 2026, '2026'),
        # 杯赛
        ('fa_cup', 2024, '2024-2025'),
        ('copa_do_brasil', 2025, '2025'),
        ('emperors_cup', 2025, '2025'),
        ('community_shield', 2025, '2025'),
        # 附加赛
        ('championship_playoff', 2024, '2024-2025'),
        ('allsvenskan_playoff', 2025, '2025'),
    ]

    for league, year, expected in test_cases:
        result = get_correct_season_name(league, year)
        status = '✓' if result == expected else '✗'
        print(f'  {status} {league} {year} → {result} (期望: {expected})')
