"""
CSV字段分析工具 - 分析所有联赛CSV文件的字段
"""
import os
import csv
from pathlib import Path
from collections import Counter, defaultdict

DATA_DIR = Path("D:/football_tools/data")

# 字段含义解释
FIELD_MEANINGS = {
    # 核心比赛信息
    'Date': '比赛日期',
    'Time': '比赛时间',
    'HomeTeam': '主队名称',
    'AwayTeam': '客队名称',
    'FTHG': '主队全场进球',
    'FTAG': '客队全场进球',
    'FTR': '全场结果 (H=主胜, D=平, A=客胜)',
    'Status': '比赛状态',

    # 半场数据
    'HTHG': '主队半场进球',
    'HTAG': '客队半场进球',
    'HTR': '半场结果',

    # 射门统计
    'HS': '主队射门次数',
    'AS': '客队射门次数',
    'HST': '主队射正次数',
    'AST': '客队射正次数',

    # 犯规统计
    'HF': '主队犯规次数',
    'AF': '客队犯规次数',
    'HC': '主队角球次数',
    'AC': '客队角球次数',
    'HY': '主队黄牌数',
    'AY': '客队黄牌数',
    'HR': '主队红牌数',
    'AR': '客队红牌数',

    # 其他比赛信息
    'Div': '联赛代码',
    'Referee': '裁判',
    'Attendance': '观众人数',
    'Season': '赛季',

    # 赔率相关 (H=主胜, D=平, A=客胜)
    'B365H': 'Bet365主胜赔率',
    'B365D': 'Bet365平局赔率',
    'B365A': 'Bet365客胜赔率',
    'BWH': 'Betway主胜赔率',
    'BWD': 'Betway平局赔率',
    'BWA': 'Betway客胜赔率',
    'WHH': 'William Hill主胜赔率',
    'WHD': 'William Hill平局赔率',
    'WHA': 'William Hill客胜赔率',
    'IWH': 'Interwetten主胜赔率',
    'IWD': 'Interwetten平局赔率',
    'IWA': 'Interwetten客胜赔率',
    'PSH': 'Pinnacle主胜赔率',
    'PSD': 'Pinnacle平局赔率',
    'PSA': 'Pinnacle客胜赔率',
    'VCH': 'VC Bet主胜赔率',
    'VCD': 'VC Bet平局赔率',
    'VCA': 'VC Bet客胜赔率',
    'MaxH': '最高主胜赔率',
    'MaxD': '最高平局赔率',
    'MaxA': '最高客胜赔率',
    'AvgH': '平均主胜赔率',
    'AvgD': '平均平局赔率',
    'AvgA': '平均客胜赔率',

    # 大小球赔率
    'B365>2.5': 'Bet365大于2.5球赔率',
    'B365<2.5': 'Bet365小于2.5球赔率',
    'P>2.5': 'Pinnacle大于2.5球赔率',
    'P<2.5': 'Pinnacle小于2.5球赔率',
    'Max>2.5': '最高大于2.5球赔率',
    'Max<2.5': '最高小于2.5球赔率',
    'Avg>2.5': '平均大于2.5球赔率',
    'Avg<2.5': '平均小于2.5球赔率',

    # 亚盘赔率
    'AHh': '亚盘让球数',
    'B365AHH': 'Bet365亚盘主队赔率',
    'B365AHA': 'Bet365亚盘客队赔率',
}

def analyze_all_csv_headers():
    """分析所有CSV文件的字段"""
    results = {
        'all_headers': Counter(),
        'header_combos': Counter(),
        'files_by_header_count': defaultdict(list),
        'unknown_headers': set(),
        'sample_files': {}
    }

    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith('.csv'):
                file_path = Path(root) / f
                try:
                    with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
                        reader = csv.reader(csvfile)
                        headers = next(reader)

                        # 清理字段名
                        clean_headers = []
                        for h in headers:
                            h_clean = h.strip().replace('﻿', '')
                            clean_headers.append(h_clean)
                            results['all_headers'][h_clean] += 1

                            # 检查是否是已知字段
                            if h_clean and h_clean not in FIELD_MEANINGS:
                                results['unknown_headers'].add(h_clean)

                        # 记录字段组合
                        header_key = tuple(sorted(clean_headers))
                        results['header_combos'][header_key] += 1

                        # 按字段数量分组
                        count = len(clean_headers)
                        results['files_by_header_count'][count].append(str(file_path))

                        # 保存样本文件
                        if count not in results['sample_files']:
                            results['sample_files'][count] = {
                                'file': str(file_path),
                                'headers': clean_headers
                            }

                except Exception as e:
                    pass

    return results

def print_field_analysis():
    """打印字段分析结果"""
    results = analyze_all_csv_headers()

    print("\n" + "="*80)
    print("CSV字段完整分析报告")
    print("="*80)

    # 1. 核心字段统计
    print("\n【一、核心比赛字段】")
    print("-"*60)
    core_fields = ['Date', 'Time', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'Status']
    for h in core_fields:
        count = results['all_headers'].get(h, 0)
        meaning = FIELD_MEANINGS.get(h, '未知')
        print(f"  {h:15} : {count:5} 个文件 - {meaning}")

    # 2. 统计字段
    print("\n【二、比赛统计字段】")
    print("-"*60)
    stats_fields = ['HTHG', 'HTAG', 'HTR', 'HS', 'AS', 'HST', 'AST',
                    'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR']
    for h in stats_fields:
        count = results['all_headers'].get(h, 0)
        meaning = FIELD_MEANINGS.get(h, '未知')
        print(f"  {h:15} : {count:5} 个文件 - {meaning}")

    # 3. 赔率字段
    print("\n【三、赔率字段 (部分)】")
    print("-"*60)
    odds_fields = ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA',
                   'WHH', 'WHD', 'WHA', 'MaxH', 'MaxD', 'MaxA',
                   'AvgH', 'AvgD', 'AvgA']
    for h in odds_fields:
        count = results['all_headers'].get(h, 0)
        meaning = FIELD_MEANINGS.get(h, '未知')
        print(f"  {h:15} : {count:5} 个文件 - {meaning}")

    # 4. 其他常见字段
    print("\n【四、其他常见字段】")
    print("-"*60)
    other_fields = ['Div', 'Referee', 'Attendance', 'Season']
    for h in other_fields:
        count = results['all_headers'].get(h, 0)
        meaning = FIELD_MEANINGS.get(h, '未知')
        print(f"  {h:15} : {count:5} 个文件 - {meaning}")

    # 5. 未知字段
    print("\n【五、未知/未解释字段】")
    print("-"*60)
    unknown = sorted(results['unknown_headers'])
    if unknown:
        print(f"  共 {len(unknown)} 个未知字段:")
        for h in unknown[:30]:  # 只显示前30个
            count = results['all_headers'].get(h, 0)
            print(f"    {h:20} : {count:5} 个文件")
        if len(unknown) > 30:
            print(f"    ... 还有 {len(unknown) - 30} 个")
    else:
        print("  无未知字段")

    # 6. 字段数量分布
    print("\n【六、字段数量分布】")
    print("-"*60)
    for count in sorted(results['files_by_header_count'].keys(), reverse=True)[:10]:
        files = results['files_by_header_count'][count]
        print(f"  {count:3} 个字段: {len(files):4} 个文件")

    # 7. 建议的标准字段
    print("\n【七、建议的标准字段列表】")
    print("-"*60)
    standard_fields = [
        'match_date', 'match_time', 'home_team', 'away_team',
        'home_goals', 'away_goals', 'result', 'status',
        'home_goals_ht', 'away_goals_ht', 'result_ht',
        'home_shots', 'away_shots', 'home_shots_target', 'away_shots_target',
        'home_fouls', 'away_fouls', 'home_corners', 'away_corners',
        'home_yellow', 'away_yellow', 'home_red', 'away_red',
        'home_odds', 'draw_odds', 'away_odds',
        'division', 'season', 'league_id'
    ]
    print("  标准字段映射:")
    mapping = {
        'Date': 'match_date',
        'Time': 'match_time',
        'HomeTeam': 'home_team',
        'AwayTeam': 'away_team',
        'FTHG': 'home_goals',
        'FTAG': 'away_goals',
        'FTR': 'result',
        'Status': 'status',
        'HTHG': 'home_goals_ht',
        'HTAG': 'away_goals_ht',
        'HTR': 'result_ht',
        'HS': 'home_shots',
        'AS': 'away_shots',
        'HST': 'home_shots_target',
        'AST': 'away_shots_target',
        'HF': 'home_fouls',
        'AF': 'away_fouls',
        'HC': 'home_corners',
        'AC': 'away_corners',
        'HY': 'home_yellow',
        'AY': 'away_yellow',
        'HR': 'home_red',
        'AR': 'away_red',
        'B365H': 'home_odds',
        'B365D': 'draw_odds',
        'B365A': 'away_odds',
        'Div': 'division',
        'Season': 'season',
    }
    for old, new in mapping.items():
        print(f"    {old:15} -> {new}")

    print("\n" + "="*80)

    return results

if __name__ == '__main__':
    print_field_analysis()
