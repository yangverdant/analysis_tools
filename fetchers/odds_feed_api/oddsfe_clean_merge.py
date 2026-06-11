"""
oddsfe_clean_merge.py — 清洗实时数据并合并到 v2 CSV

核心规则 (RED LINE):
- 历史数据(非recent_days范围内的)绝对不能删除或修改
- 只更新 recent_days 范围内的行
- 新 event_id 直接追加

流程:
1. 读取 oddsfe_realtime_schedule.csv (schedule数据)
2. 读取 oddsfe_realtime_detail.csv (赔率数据)
3. 合并 → 展开赔率字段 → 生成 v2 格式行
4. 读取现有 v2 CSV
5. 根据 event_id 匹配:
   - 新 event_id → 追加
   - 已存在且在 recent_days 内 → 更新
   - 已存在且不在 recent_days 内 → 跳过 (RED LINE)
6. 写入新的 v2 CSV
"""

import os
import csv
from datetime import datetime, timedelta
from collections import defaultdict

OUTPUT_DIR = os.path.dirname(__file__)

# 15个bookmaker
BOOKMAKERS = [
    '1XBET', 'BET365', 'PINNACLE', 'BETFAIR_EXCH', 'BETFAIR',
    'BET_IN_ASIA', 'UNIBET', 'BET_AT_HOME', 'WILLIAM_HILL',
    'DAFABET', 'BWIN_ES', 'BWIN', '888_SPORT', 'STAKE_COM', 'MATCHBOOK'
]

# 4个市场类型及其列结构
MARKET_COLS = {
    '1X2': ['home', 'draw', 'away'],
    'OVER_UNDER': ['over', 'line', 'under'],
    'ASIAN_HANDICAP': ['home', 'handicap', 'away'],
    'BOTH_TEAMS_TO_SCORE': ['yes', 'no'],
}

TIMINGS = ['prematch', 'live']

# v2 的 29 个基础字段
BASE_FIELDS = [
    'event_id', 'event_start_at', 'event_status', 'event_winner',
    'event_score_home', 'event_score_away', 'tournament_id', 'tournament_name',
    'tournament_slug', 'season_id', 'season_slug', 'category_id', 'category_name',
    'category_slug', 'team_home_id', 'team_home_name', 'team_away_id', 'team_away_name',
    'main_out_0', 'main_out_1', 'main_out_2', 'main_volume_0', 'main_volume_1',
    'main_volume_2', 'event_outcome_0', 'event_outcome_1', 'event_outcome_2',
    'event_pin_event_id', 'sum_tournament_outcome_volume',
]


def build_v2_fieldnames():
    """构建 v2 CSV 的所有列名"""
    fields = list(BASE_FIELDS)
    for mt in ['1X2', 'OVER_UNDER', 'ASIAN_HANDICAP', 'BOTH_TEAMS_TO_SCORE']:
        for timing in TIMINGS:
            for bk in BOOKMAKERS:
                for col in MARKET_COLS[mt]:
                    fields.append(f'{mt}_{timing}_{bk}_{col}')
    return fields


V2_FIELDS = build_v2_fieldnames()


def parse_bookmaker_odds(odds_str):
    """
    解析赔率字符串
    格式: bookmaker1:odds1:odds2:odds3;bookmaker2:odds1:odds2:odds3
    返回: {bookmaker: [odds1, odds2, odds3], ...}
    """
    if not odds_str:
        return {}
    result = {}
    for bk_entry in odds_str.split(';'):
        parts = bk_entry.split(':')
        if len(parts) >= 2:
            bk_name = parts[0].strip()
            odds_vals = parts[1:]
            result[bk_name] = odds_vals
    return result


def expand_odds_to_v2(row_with_odds):
    """
    将 packed 赔率字段展开为 v2 格式的独立列
    输入: 包含 {market}_{timing}_bookmakers 字段的行
    输出: 包含所有 v2 列的行
    """
    expanded = {}

    # 复制基础字段
    for f in BASE_FIELDS:
        expanded[f] = row_with_odds.get(f, '')

    # 展开赔率字段
    for mt in ['1X2', 'OVER_UNDER', 'ASIAN_HANDICAP', 'BOTH_TEAMS_TO_SCORE']:
        for timing in TIMINGS:
            key = f'{mt}_{timing}_bookmakers'
            odds_str = row_with_odds.get(key, '')
            parsed = parse_bookmaker_odds(odds_str)

            for bk in BOOKMAKERS:
                bk_odds = parsed.get(bk, [])
                col_names = MARKET_COLS[mt]
                for i, col in enumerate(col_names):
                    val = bk_odds[i] if i < len(bk_odds) else ''
                    expanded[f'{mt}_{timing}_{bk}_{col}'] = val

    return expanded


def load_schedule_csv(filepath):
    """加载 schedule CSV，返回 {event_id: row}"""
    if not os.path.exists(filepath):
        return {}
    result = {}
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get('event_id', '')
            if eid:
                result[eid] = row
    return result


def load_detail_csv(filepath):
    """加载 detail CSV，返回 {event_id: row}"""
    if not os.path.exists(filepath):
        return {}
    result = {}
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get('event_id', '')
            if eid:
                result[eid] = row
    return result


def load_v2_csv(filepath):
    """加载 v2 CSV，返回 {event_id: row}"""
    if not os.path.exists(filepath):
        return {}
    result = {}
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get('event_id', '')
            if eid:
                result[eid] = row
    return result


def is_recent_event(row, recent_days, today=None):
    """判断事件是否在 recent_days 范围内"""
    if today is None:
        today = datetime.now()
    start_at = row.get('event_start_at', '')
    if not start_at:
        return False
    try:
        # 解析日期 (格式: 2026-05-30T15:00:00Z 或 2026-05-30 15:00:00)
        dt_str = start_at.replace('T', ' ').replace('Z', '').split('.')[0].split(' ')[0]
        event_date = datetime.strptime(dt_str, '%Y-%m-%d')
        return (today - event_date).days <= recent_days
    except:
        return False


def merge_and_clean(schedule_csv=None, detail_csv=None, v2_csv=None, recent_days=10, backup=True):
    """
    合并实时数据到 v2 CSV

    Args:
        schedule_csv: 实时 schedule CSV 路径
        detail_csv: 实时 detail CSV 路径
        v2_csv: v2 master CSV 路径
        recent_days: 只更新最近N天内的数据 (RED LINE 保护)
        backup: 是否备份原 v2 文件
    """
    if schedule_csv is None:
        schedule_csv = os.path.join(OUTPUT_DIR, 'oddsfe_realtime_schedule.csv')
    if detail_csv is None:
        detail_csv = os.path.join(OUTPUT_DIR, 'oddsfe_realtime_detail.csv')
    if v2_csv is None:
        v2_csv = os.path.join(OUTPUT_DIR, 'oddsfe_data_full_v2.csv')

    print(f'Loading schedule: {schedule_csv}')
    schedule_data = load_schedule_csv(schedule_csv)
    print(f'  -> {len(schedule_data)} events')

    print(f'Loading detail: {detail_csv}')
    detail_data = load_detail_csv(detail_csv)
    print(f'  -> {len(detail_data)} events')

    print(f'Loading v2: {v2_csv}')
    v2_data = load_v2_csv(v2_csv)
    print(f'  -> {len(v2_data)} events')

    today = datetime.now()
    new_count = 0
    update_count = 0
    skip_count = 0

    # 合并 schedule + detail
    for eid, sched_row in schedule_data.items():
        detail_row = detail_data.get(eid, {})

        # 合并两行数据
        merged = dict(sched_row)
        merged.update(detail_row)

        # 展开赔率字段
        expanded = expand_odds_to_v2(merged)

        if eid in v2_data:
            # 已存在
            if is_recent_event(sched_row, recent_days, today):
                # 在 recent_days 内，更新
                v2_data[eid] = expanded
                update_count += 1
            else:
                # 不在 recent_days 内，跳过 (RED LINE)
                skip_count += 1
        else:
            # 新 event_id，追加
            v2_data[eid] = expanded
            new_count += 1

    print(f'\nMerge summary:')
    print(f'  New: {new_count}')
    print(f'  Updated (recent {recent_days} days): {update_count}')
    print(f'  Skipped (historical, RED LINE): {skip_count}')
    print(f'  Total: {len(v2_data)}')

    # 备份原文件
    if backup and os.path.exists(v2_csv):
        backup_path = v2_csv.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        print(f'\nBacking up v2 to: {backup_path}')
        import shutil
        shutil.copy2(v2_csv, backup_path)

    # 写入新 v2
    print(f'\nWriting v2: {v2_csv}')
    with open(v2_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=V2_FIELDS)
        writer.writeheader()
        for eid in sorted(v2_data.keys(), key=lambda x: v2_data[x].get('event_start_at', '')):
            writer.writerow(v2_data[eid])

    print(f'Done! {len(v2_data)} rows written.')
    return len(v2_data)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='清洗实时数据并合并到 v2 CSV')
    parser.add_argument('--schedule', default=None, help='实时 schedule CSV 路径')
    parser.add_argument('--detail', default=None, help='实时 detail CSV 路径')
    parser.add_argument('--v2', default=None, help='v2 master CSV 路径')
    parser.add_argument('--recent-days', type=int, default=10, help='只更新最近N天内的数据 (RED LINE 保护)')
    parser.add_argument('--no-backup', action='store_true', help='不备份原 v2 文件')
    args = parser.parse_args()

    merge_and_clean(
        schedule_csv=args.schedule,
        detail_csv=args.detail,
        v2_csv=args.v2,
        recent_days=args.recent_days,
        backup=not args.no_backup,
    )
