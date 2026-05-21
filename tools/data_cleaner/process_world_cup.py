"""
处理世界杯数据
将原始世界杯数据转换为标准化的杯赛格式
"""
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 国家队中文名映射
TEAM_CN_MAP = {
    # A
    'Algeria': '阿尔及利亚',
    'Angola': '安哥拉',
    'Argentina': '阿根廷',
    'Australia': '澳大利亚',
    'Austria': '奥地利',
    # B
    'Belgium': '比利时',
    'Bosnia and Herzegovina': '波黑',
    'Brazil': '巴西',
    # C
    'Cameroon': '喀麦隆',
    'Canada': '加拿大',
    'Cape Verde': '佛得角',
    'China PR': '中国',
    'Chile': '智利',
    'Colombia': '哥伦比亚',
    'Costa Rica': '哥斯达黎加',
    'Croatia': '克罗地亚',
    'Curaçao': '库拉索',
    'Czech Republic': '捷克',
    # D
    'Denmark': '丹麦',
    'DR Congo': '民主刚果',
    # E
    'Ecuador': '厄瓜多尔',
    'Egypt': '埃及',
    'England': '英格兰',
    # F
    'France': '法国',
    # G
    'Germany': '德国',
    'Ghana': '加纳',
    'Greece': '希腊',
    # H
    'Haiti': '海地',
    'Honduras': '洪都拉斯',
    # I
    'Iran': '伊朗',
    'Iraq': '伊拉克',
    'Iceland': '冰岛',
    'Ivory Coast': '科特迪瓦',
    'Italy': '意大利',
    # J
    'Japan': '日本',
    'Jordan': '约旦',
    # K
    'South Korea': '韩国',
    # L
    # M
    'Mexico': '墨西哥',
    'Morocco': '摩洛哥',
    # N
    'Netherlands': '荷兰',
    'New Zealand': '新西兰',
    'Nigeria': '尼日利亚',
    'North Korea': '朝鲜',
    'Norway': '挪威',
    # O
    # P
    'Panama': '巴拿马',
    'Paraguay': '巴拉圭',
    'Peru': '秘鲁',
    'Poland': '波兰',
    'Portugal': '葡萄牙',
    # Q
    'Qatar': '卡塔尔',
    # R
    'Republic of Ireland': '爱尔兰',
    'Russia': '俄罗斯',
    # S
    'Saudi Arabia': '沙特阿拉伯',
    'Scotland': '苏格兰',
    'Senegal': '塞内加尔',
    'Serbia': '塞尔维亚',
    'Serbia and Montenegro': '塞黑',
    'Slovakia': '斯洛伐克',
    'Slovenia': '斯洛文尼亚',
    'South Africa': '南非',
    'Spain': '西班牙',
    'Sweden': '瑞典',
    'Switzerland': '瑞士',
    # T
    'Togo': '多哥',
    'Trinidad and Tobago': '特立尼达和多巴哥',
    'Tunisia': '突尼斯',
    'Turkey': '土耳其',
    # U
    'Ukraine': '乌克兰',
    'United States': '美国',
    'Uruguay': '乌拉圭',
    'Uzbekistan': '乌兹别克斯坦',
    # V
    'Venezuela': '委内瑞拉',
    # W
    'Wales': '威尔士',
    # Z
}

def get_world_cup_season(year):
    """根据年份获取世界杯赛季标识"""
    return f"{year}"

def infer_world_cup_stage(date_str, match_index, total_matches_in_round, year):
    """
    根据日期和年份推断世界杯阶段

    每届世界杯的具体日期不同，需要分别处理
    """
    if not date_str:
        return 'group', 3

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        month = date.month
        day = date.day

        # 2022年世界杯（11-12月举行）
        if year == 2022:
            if month == 11:
                return 'group', 3
            elif month == 12:
                if day <= 2:
                    return 'group', 3
                elif day <= 6:
                    return 'round_of_16', 5
                elif day <= 10:
                    return 'quarterfinal', 6
                elif day <= 14:
                    return 'semifinal', 7
                elif day == 17:
                    return 'third_place', 8
                else:
                    return 'final', 9

        # 2018年世界杯
        elif year == 2018:
            if month == 6:
                if day <= 28:
                    return 'group', 3
                else:
                    return 'round_of_16', 5
            else:  # 7月
                if day <= 3:
                    return 'round_of_16', 5
                elif day <= 7:
                    return 'quarterfinal', 6
                elif day <= 11:
                    return 'semifinal', 7
                elif day == 14:
                    return 'third_place', 8
                else:
                    return 'final', 9

        # 2014年世界杯
        elif year == 2014:
            if month == 6:
                if day <= 26:
                    return 'group', 3
                else:
                    return 'round_of_16', 5
            else:  # 7月
                if day <= 1:
                    return 'round_of_16', 5
                elif day <= 5:
                    return 'quarterfinal', 6
                elif day <= 9:
                    return 'semifinal', 7
                elif day == 12:
                    return 'third_place', 8
                else:
                    return 'final', 9

        # 2010年世界杯
        elif year == 2010:
            if month == 6:
                if day <= 25:
                    return 'group', 3
                else:
                    return 'round_of_16', 5
            else:  # 7月
                if day == 2:
                    return 'quarterfinal', 6
                elif day == 3:
                    return 'quarterfinal', 6
                elif day == 6:
                    return 'quarterfinal', 6
                elif day == 7:
                    return 'quarterfinal', 6
                elif day == 10:
                    return 'third_place', 8
                elif day == 11:
                    return 'final', 9
                else:
                    return 'group', 3

        # 2006年世界杯
        elif year == 2006:
            if month == 6:
                if day <= 23:
                    return 'group', 3
                else:
                    return 'round_of_16', 5
            else:  # 7月
                if day <= 1:
                    return 'round_of_16', 5
                elif day <= 5:
                    return 'quarterfinal', 6
                elif day <= 5:
                    return 'semifinal', 7
                elif day == 8:
                    return 'third_place', 8
                else:
                    return 'final', 9

        # 2002年世界杯（5月31日-6月30日）
        elif year == 2002:
            if month == 5:
                # 5月31日揭幕战是小组赛
                return 'group', 3
            elif month == 6:
                if day <= 14:
                    return 'group', 3
                elif day <= 18:
                    return 'round_of_16', 5
                elif day <= 22:
                    return 'quarterfinal', 6
                elif day <= 26:
                    return 'semifinal', 7
                elif day == 29:
                    return 'third_place', 8
                else:
                    return 'final', 9
            else:  # 7月
                return 'final', 9

        # 默认返回小组赛
        return 'group', 3

    except:
        return 'group', 3

def get_team_cn(team_en):
    """获取球队中文名"""
    return TEAM_CN_MAP.get(team_en, '')

def determine_result(home_goals, away_goals):
    """根据进球数判断比赛结果"""
    if home_goals is None or away_goals is None:
        return ''
    if home_goals > away_goals:
        return 'H'
    elif home_goals < away_goals:
        return 'A'
    else:
        return 'D'

def process_world_cup():
    """处理世界杯数据"""
    input_file = Path('D:/football_tools/data/04_international/world_cup/world_cup_all.csv')
    output_dir = Path('D:/football_tools/new_data/cups/world_cup')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 按赛季分组
    matches_by_season = defaultdict(list)

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get('Date', '').strip()
            if not date_str:
                continue

            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                year = date.year
            except:
                continue

            # 跳过2026年及以后的预定比赛
            status = row.get('Status', '').strip()
            if status == 'Scheduled' or year >= 2026:
                continue

            # 确定世界杯赛季
            # 世界杯在偶数年举行，赛季用年份表示
            season = str(year)

            home_team = row.get('HomeTeam', '').strip()
            away_team = row.get('AwayTeam', '').strip()

            if not home_team or not away_team:
                continue

            # 解析进球
            home_goals_str = row.get('FTHG', '')
            away_goals_str = row.get('FTAG', '')

            try:
                home_goals = int(float(home_goals_str)) if home_goals_str else None
            except:
                home_goals = None

            try:
                away_goals = int(float(away_goals_str)) if away_goals_str else None
            except:
                away_goals = None

            # 半场进球
            home_goals_ht_str = row.get('HTHG', '')
            away_goals_ht_str = row.get('HTAG', '')

            try:
                home_goals_ht = int(float(home_goals_ht_str)) if home_goals_ht_str else None
            except:
                home_goals_ht = None

            try:
                away_goals_ht = int(float(away_goals_ht_str)) if away_goals_ht_str else None
            except:
                away_goals_ht = None

            # 推断阶段
            stage, stage_order = infer_world_cup_stage(date_str, 0, 0, year)

            # 构建比赛记录
            match = {
                'competition': 'world_cup',
                'competition_cn': '世界杯',
                'season': season,
                'phase': 'main',
                'stage': stage,
                'stage_order': stage_order,
                'group_name': '',
                'group_round': '',
                'leg': '',
                'match_date': date_str,
                'match_time': row.get('Time', '').strip(),
                'home_team': home_team,
                'home_team_cn': get_team_cn(home_team),
                'away_team': away_team,
                'away_team_cn': get_team_cn(away_team),
                'home_goals': home_goals if home_goals is not None else '',
                'away_goals': away_goals if away_goals is not None else '',
                'home_goals_ht': home_goals_ht if home_goals_ht is not None else '',
                'away_goals_ht': away_goals_ht if away_goals_ht is not None else '',
                'home_goals_et': '',
                'away_goals_et': '',
                'home_penalties': '',
                'away_penalties': '',
                'result': determine_result(home_goals, away_goals),
                'venue': '',
                'attendance': row.get('Attendance', '').strip(),
                'referee': row.get('Referee', '').strip(),
                'status': 'Finished'
            }

            matches_by_season[season].append(match)

    # 写入各赛季文件
    fieldnames = [
        'competition', 'competition_cn', 'season', 'phase', 'stage', 'stage_order',
        'group_name', 'group_round', 'leg', 'match_date', 'match_time',
        'home_team', 'home_team_cn', 'away_team', 'away_team_cn',
        'home_goals', 'away_goals', 'home_goals_ht', 'away_goals_ht',
        'home_goals_et', 'away_goals_et', 'home_penalties', 'away_penalties',
        'result', 'venue', 'attendance', 'referee', 'status'
    ]

    total_matches = 0
    total_teams = set()
    missing_cn = set()

    for season in sorted(matches_by_season.keys()):
        matches = matches_by_season[season]
        output_file = output_dir / f'world_cup_{season}.csv'

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(matches)

        total_matches += len(matches)

        for m in matches:
            total_teams.add(m['home_team'])
            total_teams.add(m['away_team'])
            if not m['home_team_cn']:
                missing_cn.add(m['home_team'])
            if not m['away_team_cn']:
                missing_cn.add(m['away_team'])

        print(f'{season}: {len(matches)} 场比赛')

    print('='*60)
    print('世界杯数据处理完成')
    print('='*60)
    print(f'赛季数: {len(matches_by_season)}')
    print(f'比赛总数: {total_matches}')
    print(f'球队数: {len(total_teams)}')
    print(f'有中文名: {len(total_teams) - len(missing_cn)}')
    print(f'缺中文名: {len(missing_cn)}')

    if missing_cn:
        print('\n缺失中文名:')
        for team in sorted(missing_cn):
            print(f'  {team}')

if __name__ == '__main__':
    process_world_cup()
