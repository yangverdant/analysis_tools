"""
oddsfe_realtime_refresh.py — 一键刷新近期数据
1. 采集过去5天+未来9天的schedule
2. 提取新event_id，采集detail v2
3. 合并进 oddsfe_data_full_v2.csv 和 oddsfe_detail_v2_all.csv
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import csv
import io
import time
import random
import requests
from datetime import datetime, timedelta
from oddsfe_auth import get_schedule_auth, get_event_auth
from oddsfe_realtime_schedule import fetch_schedule, flatten_event, SCHEDULE_FIELDS
from oddsfe_realtime_detail_v2 import parse_event_odds_v2, DETAIL_V2_FIELDS, create_session as detail_create_session

OUTPUT_DIR = os.path.dirname(__file__)


def step1_schedule(past_days=5, future_days=9):
    """Step 1: 采集schedule，返回新event_id列表"""
    print("=" * 60)
    print("STEP 1: 采集schedule数据")
    print("=" * 60)

    session = requests.Session()
    session.trust_env = False
    today = datetime.now()
    start = today - timedelta(days=past_days)
    end = today + timedelta(days=future_days)
    total_days = (end - start).days + 1

    # 读取现有schedule的event_id
    existing_ids = set()
    schedule_csv = os.path.join(OUTPUT_DIR, 'oddsfe_data_full_v2.csv')
    if os.path.exists(schedule_csv):
        with open(schedule_csv, 'r', encoding='utf-8-sig') as f:
            content = f.read().replace('\x00', '')
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                eid = row.get('event_id', '')
                if eid:
                    existing_ids.add(eid)
    print(f"现有schedule: {len(existing_ids)} event_ids")

    new_rows = []
    new_ids = set()
    failed_days = []

    for day_offset in range(total_days):
        current_date = start + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')

        print(f'[{day_offset+1}/{total_days}] {date_str} ...')

        schedule_data = fetch_schedule(session, date_str)
        if schedule_data is None:
            failed_days.append(date_str)
            time.sleep(2)
            continue

        day_new = 0
        for tournament in schedule_data:
            events = tournament.get('events', [])
            for event in events:
                row = flatten_event(event)
                eid = row.get('event_id', '')
                if eid and eid not in existing_ids and eid not in new_ids:
                    new_rows.append(row)
                    new_ids.add(eid)
                    day_new += 1

        print(f'  -> {day_new} new events')
        time.sleep(0.5)

    print(f"\nSchedule完成: {len(new_ids)} new event_ids, failed: {len(failed_days)}")
    if failed_days:
        print(f"Failed days: {failed_days}")

    return new_rows, new_ids


def step2_detail(new_ids):
    """Step 2: 采集新event的detail v2"""
    print("\n" + "=" * 60)
    print(f"STEP 2: 采集detail v2 ({len(new_ids)} events)")
    print("=" * 60)

    if not new_ids:
        print("没有新event需要采集")
        return []

    # 读取已采集的detail
    detail_csv = os.path.join(OUTPUT_DIR, 'oddsfe_detail_v2_all.csv')
    done_ids = set()
    if os.path.exists(detail_csv):
        with open(detail_csv, 'r', encoding='utf-8-sig') as f:
            content = f.read().replace('\x00', '')
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                eid = row.get('event_id', '')
                if eid:
                    done_ids.add(eid)

    todo_ids = [eid for eid in new_ids if eid not in done_ids]
    print(f"已有detail: {len(done_ids)}, 需要采集: {len(todo_ids)}")

    if not todo_ids:
        print("所有新event已有detail数据")
        return []

    session = detail_create_session()
    detail_rows = []

    for idx, eid in enumerate(todo_ids):
        if (idx + 1) % 50 == 0:
            print(f'  [{idx+1}/{len(todo_ids)}] ...')

        row = parse_event_odds_v2(session, eid)
        if row:
            clean_row = {k: v for k, v in row.items() if k is not None}
            detail_rows.append(clean_row)
        else:
            detail_rows.append({'event_id': eid})

        time.sleep(random.uniform(0.1, 0.3))

    print(f"Detail完成: {len(detail_rows)} rows")
    return detail_rows


def step3_merge(new_schedule_rows, new_detail_rows):
    """Step 3: 合并新数据到主文件"""
    print("\n" + "=" * 60)
    print("STEP 3: 合并数据")
    print("=" * 60)

    # 合并schedule - 只追加SCHEDULE_FIELDS字段（与data_full_v2前30列一致）
    schedule_csv = os.path.join(OUTPUT_DIR, 'oddsfe_data_full_v2.csv')
    if new_schedule_rows:
        # data_full_v2有赔率列（1X2_*等），新schedule行只有SCHEDULE_FIELDS
        # 需要补空赔率列
        with open(schedule_csv, 'r', encoding='utf-8-sig') as f:
            content = f.read().replace('\x00', '')
            reader = csv.DictReader(io.StringIO(content))
            full_fields = reader.fieldnames

        # 补齐赔率列为空字符串
        for row in new_schedule_rows:
            for col in full_fields:
                if col not in row:
                    row[col] = ''

        with open(schedule_csv, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=full_fields)
            writer.writerows(new_schedule_rows)
        print(f"Schedule: 追加 {len(new_schedule_rows)} rows -> {schedule_csv}")

    # 合并detail
    detail_csv = os.path.join(OUTPUT_DIR, 'oddsfe_detail_v2_all.csv')
    if new_detail_rows:
        with open(detail_csv, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=DETAIL_V2_FIELDS)
            writer.writerows(new_detail_rows)
        print(f"Detail: 追加 {len(new_detail_rows)} rows -> {detail_csv}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='oddsfe一键刷新近期数据')
    parser.add_argument('--past-days', type=int, default=5, help='刷新过去N天')
    parser.add_argument('--future-days', type=int, default=9, help='采集未来N天')
    args = parser.parse_args()

    start_time = time.time()

    new_schedule_rows, new_ids = step1_schedule(past_days=args.past_days, future_days=args.future_days)
    new_detail_rows = step2_detail(new_ids)
    step3_merge(new_schedule_rows, new_detail_rows)

    elapsed = time.time() - start_time
    print(f"\n全部完成! 耗时 {elapsed:.0f}s")
    print(f"  新schedule: {len(new_schedule_rows)} rows")
    print(f"  新detail: {len(new_detail_rows)} rows")


if __name__ == '__main__':
    main()