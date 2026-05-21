#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面检查并同步所有联赛数据
- 添加Status字段
- 合并未开始的比赛
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def sync_all_leagues():
    """同步所有联赛数据"""
    print("="*70)
    print("全面同步所有联赛数据")
    print("="*70)

    today = datetime.now()
    print(f"今天日期: {today.strftime('%Y-%m-%d')}")

    leagues_dir = Path('data/01_europe_leagues')
    stats = []

    for league_dir in sorted(leagues_dir.iterdir()):
        if not league_dir.is_dir():
            continue

        league_code = league_dir.name

        # 找到当前赛季文件 (2025-2026)
        current_file = None
        for pattern in ['*2025-2026*', '*2025*']:
            matches = list(league_dir.glob(pattern))
            if matches:
                current_file = matches[0]
                break

        if not current_file:
            continue

        print(f"\n{league_code}:")
        df = pd.read_csv(current_file)
        original_count = len(df)

        # 添加Status字段
        def get_status(row):
            if pd.notna(row.get('FTHG')) and pd.notna(row.get('FTAG')):
                return 'Finished'
            match_date = row.get('Date', '')
            if match_date:
                try:
                    # 处理不同日期格式
                    if '/' in match_date:
                        date_obj = datetime.strptime(match_date, '%d/%m/%Y')
                    else:
                        date_obj = datetime.strptime(match_date, '%Y-%m-%d')

                    if date_obj < today:
                        return 'Unknown'
                    else:
                        return 'Scheduled'
                except:
                    return 'Unknown'
            return 'Unknown'

        df['Status'] = df.apply(get_status, axis=1)

        # 添加Season和League字段
        df['Season'] = '2025-2026'
        df['League'] = league_code

        # 统计
        status_counts = df['Status'].value_counts()
        finished = status_counts.get('Finished', 0)
        scheduled = status_counts.get('Scheduled', 0)
        unknown = status_counts.get('Unknown', 0)

        print(f"  总场次: {len(df)}")
        print(f"  已结束: {finished}")
        print(f"  未开始: {scheduled}")
        print(f"  未知: {unknown}")

        # 保存
        df.to_csv(current_file, index=False, encoding='utf-8-sig')

        stats.append({
            'League': league_code,
            'File': current_file.name,
            'Total': len(df),
            'Finished': finished,
            'Scheduled': scheduled,
            'Unknown': unknown
        })

    return stats

def check_other_data():
    """检查其他数据目录"""
    print("\n" + "="*70)
    print("检查其他数据目录")
    print("="*70)

    # 检查fixtures
    fixtures_dir = Path('data/fixtures')
    if fixtures_dir.exists():
        print("\n[fixtures目录]")
        for f in fixtures_dir.glob('*.csv'):
            df = pd.read_csv(f)
            print(f"  {f.name}: {len(df)}条记录")

    # 检查fifa_rankings
    fifa_dir = Path('data/fifa_rankings')
    if fifa_dir.exists():
        print("\n[fifa_rankings目录]")
        for f in fifa_dir.glob('*.csv'):
            df = pd.read_csv(f)
            print(f"  {f.name}: {len(df)}条记录")

    # 检查players
    players_dir = Path('data/players')
    if players_dir.exists():
        print("\n[players目录]")
        for f in players_dir.rglob('*.csv'):
            df = pd.read_csv(f)
            rel_path = f.relative_to(players_dir)
            print(f"  {rel_path}: {len(df)}条记录")

    # 检查09_other_data
    other_dir = Path('data/09_other_data')
    if other_dir.exists():
        print("\n[09_other_data目录]")
        for f in other_dir.rglob('*.csv'):
            df = pd.read_csv(f)
            rel_path = f.relative_to(other_dir)
            print(f"  {rel_path}: {len(df)}条记录")

def main():
    # 同步所有联赛
    stats = sync_all_leagues()

    # 检查其他数据
    check_other_data()

    # 汇总
    print("\n" + "="*70)
    print("同步完成 - 数据汇总")
    print("="*70)

    print(f"\n{'联赛':<20} {'总数':>6} {'已结束':>8} {'未开始':>8} {'未知':>6}")
    print("-"*60)
    for s in stats:
        print(f"{s['League']:<20} {s['Total']:>6} {s['Finished']:>8} {s['Scheduled']:>8} {s['Unknown']:>6}")

if __name__ == "__main__":
    main()