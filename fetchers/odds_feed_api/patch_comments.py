"""
patch_comments.py — 补填 event_comments 列
只请求 /bind/event/ API，不重新爬赔率页面
6个worker并行处理
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import csv
import requests
import time
import random

from oddsfe_auth import get_event_auth

OUTPUT_DIR = os.path.dirname(__file__)


def create_session():
    s = requests.Session()
    s.trust_env = False
    return s


def get_event_info(session, event_id):
    """从 /bind/event/ API 获取 comments 和 score_details"""
    auth = get_event_auth()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Origin': 'https://oddsfe.com',
        'Referer': f'https://oddsfe.com/events/{event_id}',
    }
    headers.update(auth)
    try:
        r = session.get(f'https://oddsfe.com/bind/event/{event_id}', headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get('comments', ''), data.get('score_details', '')
    except:
        pass
    return '', ''


def patch_file(input_csv, output_csv=None):
    """补填 event_comments 和 score_details 列"""
    if output_csv is None:
        output_csv = input_csv.replace('.csv', '_patched.csv')

    session = create_session()
    rows = []
    fields = None
    filled_comments = 0
    filled_score = 0
    total = 0

    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)

        # 确保 event_comments 字段存在
        if 'event_comments' not in fields:
            fields.insert(fields.index('score_details') + 1, 'event_comments')

        for row in reader:
            total += 1

            # 补填 event_comments
            if not row.get('event_comments') or row['event_comments'].strip() == '':
                comments, score_details = get_event_info(session, row['event_id'])
                if comments:
                    row['event_comments'] = comments
                    filled_comments += 1
                if score_details and (not row.get('score_details') or row['score_details'].strip() == ''):
                    row['score_details'] = score_details
                    filled_score += 1
                time.sleep(0.05)

            # 确保所有字段都在
            for field in fields:
                if field not in row:
                    row[field] = ''

            rows.append(row)

            if total % 1000 == 0:
                print(f'  {total} rows, comments filled: {filled_comments}, score filled: {filled_score}')

    with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f'Done! {total} rows, comments: {filled_comments}, score: {filled_score}')
    return total


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='补填event_comments')
    parser.add_argument('--file', required=True, help='要补填的CSV文件')
    parser.add_argument('--output', default=None, help='输出文件(默认原文件名_patched)')
    args = parser.parse_args()
    patch_file(args.file, args.output)