#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量同步所有赛事数据
- 添加Status字段
- 添加Season和League字段
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_status(row, today):
    """计算比赛状态"""
    # 检查是否有比分
    fthg = row.get('FTHG')
    ftag = row.get('FTAG')

    if pd.notna(fthg) and pd.notna(ftag):
        return 'Finished'

    # 检查日期
    match_date = row.get('Date', '')
    if match_date:
        try:
            # 处理不同日期格式
            if '/' in str(match_date):
                # DD/MM/YYYY 格式
                date_obj = datetime.strptime(str(match_date), '%d/%m/%Y')
                match_date_str = date_obj.strftime('%Y-%m-%d')
            else:
                match_date_str = str(match_date)

            if match_date_str < today:
                return 'Postponed'
            elif match_date_str == today:
                return 'Today'
            else:
                return 'Scheduled'
        except:
            pass

    return 'Unknown'

def sync_directory(dir_path, dir_desc, season='2025-2026'):
    """同步一个目录下的所有联赛数据"""
    if not dir_path.exists():
        return []

    print(f'\n【{dir_desc}】')
    stats = []

    for league_dir in sorted(dir_path.iterdir()):
        if not league_dir.is_dir():
            continue

        league_name = league_dir.name

        # 找到当前赛季文件
        current_file = None
        for pattern in [f'*{season}*', '*2025*', '*2026*', '*.csv']:
            matches = list(league_dir.glob(pattern))
            if matches:
                # 选择最新的文件
                current_file = max(matches, key=lambda x: x.stat().st_mtime)
                break

        if not current_file:
            continue

        try:
            df = pd.read_csv(current_file, low_memory=True)

            if len(df) == 0:
                continue

            # 添加Status字段
            today = datetime.now().strftime('%Y-%m-%d')
            df['Status'] = df.apply(lambda row: get_status(row, today), axis=1)

            # 添加Season和League字段
            if 'Season' not in df.columns:
                df['Season'] = season
            if 'League' not in df.columns:
                df['League'] = league_name

            # 保存
            df.to_csv(current_file, index=False, encoding='utf-8-sig')

            # 统计
            status_counts = df['Status'].value_counts()
            total = len(df)
            finished = status_counts.get('Finished', 0)
            today_cnt = status_counts.get('Today', 0)
            scheduled = status_counts.get('Scheduled', 0)
            postponed = status_counts.get('Postponed', 0)

            print(f'  {league_name:<25} Total: {total:>4}  Finished: {finished:>4}  Today: {today_cnt:>2}  Scheduled: {scheduled:>3}  Postponed: {postponed:>2}')

            stats.append({
                'Category': dir_desc,
                'League': league_name,
                'Total': total,
                'Finished': finished,
                'Today': today_cnt,
                'Scheduled': scheduled,
                'Postponed': postponed
            })

        except Exception as e:
            print(f'  {league_name:<25} Error: {str(e)[:40]}')

    return stats

def main():
    print('='*80)
    print('批量同步所有赛事数据')
    print('='*80)

    today = datetime.now().strftime('%Y-%m-%d')
    print(f'Today: {today}')

    all_stats = []

    # 同步所有数据目录
    data_dirs = [
        ('data/01_europe_leagues', '欧洲联赛', '2025-2026'),
        ('data/02_europe_cups', '欧洲杯赛', '2025-2026'),
        ('data/03_european_competitions', '欧战赛事', '2025-2026'),
        ('data/04_international', '国家队赛事', '2025-2026'),
        ('data/05_asia_leagues', '亚洲联赛', '2025-2026'),
        ('data/06_south_america', '南美洲联赛', '2025-2026'),
        ('data/07_north_america', '北美洲联赛', '2025-2026'),
        ('data/08_africa', '非洲联赛', '2025-2026'),
    ]

    for dir_path, dir_desc, season in data_dirs:
        stats = sync_directory(Path(dir_path), dir_desc, season)
        all_stats.extend(stats)

    # 汇总
    print('\n' + '='*80)
    print('同步完成 - 汇总统计')
    print('='*80)

    # 按类别汇总
    categories = {}
    for s in all_stats:
        cat = s['Category']
        if cat not in categories:
            categories[cat] = {'Total': 0, 'Finished': 0, 'Scheduled': 0}
        categories[cat]['Total'] += s['Total']
        categories[cat]['Finished'] += s['Finished']
        categories[cat]['Scheduled'] += s['Scheduled']

    print(f'\n{"类别":<15} {"总数":>8} {"已结束":>10} {"未开始":>10}')
    print('-'*50)
    for cat, counts in categories.items():
        print(f'{cat:<15} {counts["Total"]:>8} {counts["Finished"]:>10} {counts["Scheduled"]:>10}')

if __name__ == "__main__":
    main()