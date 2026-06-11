"""Oddsfe大规模回测 — 赔率基线准确率

回答核心问题: 纯Pinnacle赔率argmax准确率是多少？
按赔率区间、联赛类型、年份分别统计。

用法:
    python -m backend.app.core.oddsfe_backtest
    python -m backend.app.core.oddsfe_backtest --limit 50000
"""
import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CSV_PATH = PROJECT_ROOT / 'fetchers' / 'odds_feed_api' / 'oddsfe_data_full_v2.csv'


def run_oddsfe_backtest(csv_path=None, limit=None):
    """运行oddsfe大规模赔率回测

    Returns:
        dict with accuracy stats by bucket, year, etc.
    """
    csv_path = csv_path or CSV_PATH
    if not csv_path.exists():
        logger.error(f'CSV not found: {csv_path}')
        return {'error': 'CSV not found'}

    # event_winner: 0=home, 1=draw, 2=away
    winner_to_spf = {'0': '3', '1': '1', '2': '0'}
    spf_label = {'3': '主胜', '1': '平局', '0': '客胜'}

    # Odds buckets (by home odds)
    buckets = {
        '<1.30': (0, 1.30),
        '1.30-1.60': (1.30, 1.60),
        '1.60-2.00': (1.60, 2.00),
        '2.00-3.00': (2.00, 3.00),
        '>3.00': (3.00, 999),
    }

    # Results collectors
    total = defaultdict(lambda: {'count': 0, 'correct': 0, 'draw_count': 0,
                                  'home_win_count': 0, 'away_win_count': 0})
    by_bucket = defaultdict(lambda: {'count': 0, 'correct': 0, 'draw_count': 0,
                                      'home_win_count': 0, 'away_win_count': 0})
    by_year = defaultdict(lambda: {'count': 0, 'correct': 0})

    processed = 0
    errors = 0

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            if limit and processed >= limit:
                break

            if row.get('event_status') != 'FINISHED':
                continue

            # Result
            ew = row.get('event_winner', '')
            if ew not in ('0', '1', '2'):
                continue

            actual = winner_to_spf[ew]

            # Odds - try main_out first (larger sample), then Pinnacle prematch
            odds = None
            for prefix in ['main_out', '1X2_prematch_PINNACLE']:
                keys = {
                    '3': f'{prefix}_0' if prefix == 'main_out' else f'{prefix}_home',
                    '1': f'{prefix}_1' if prefix == 'main_out' else f'{prefix}_draw',
                    '0': f'{prefix}_2' if prefix == 'main_out' else f'{prefix}_away',
                }
                try:
                    h = float(row.get(keys['3'], '').split()[0]) if row.get(keys['3'], '').strip() else 0
                    d = float(row.get(keys['1'], '').split()[0]) if row.get(keys['1'], '').strip() else 0
                    a = float(row.get(keys['0'], '').split()[0]) if row.get(keys['0'], '').strip() else 0
                    if h > 1 and d > 1 and a > 1:
                        odds = {'3': h, '1': d, '0': a}
                        break
                except (ValueError, IndexError):
                    continue

            if not odds:
                continue

            # Implied probabilities (1/odds normalized)
            imp = {k: 1.0/v for k, v in odds.items()}
            total_imp = sum(imp.values())
            probs = {k: v/total_imp for k, v in imp.items()}

            # Argmax prediction
            predicted = max(probs, key=probs.get)
            is_correct = (predicted == actual)

            processed += 1

            # Total stats
            total['all']['count'] += 1
            total['all']['correct'] += int(is_correct)
            total['all']['draw_count'] += int(actual == '1')
            total['all']['home_win_count'] += int(actual == '3')
            total['all']['away_win_count'] += int(actual == '0')

            # By bucket
            home_odds = odds['3']
            for bname, (lo, hi) in buckets.items():
                if lo <= home_odds < hi:
                    by_bucket[bname]['count'] += 1
                    by_bucket[bname]['correct'] += int(is_correct)
                    by_bucket[bname]['draw_count'] += int(actual == '1')
                    by_bucket[bname]['home_win_count'] += int(actual == '3')
                    by_bucket[bname]['away_win_count'] += int(actual == '0')
                    break

            # By year
            event_date = row.get('event_start_at', '')[:4]
            if event_date:
                by_year[event_date]['count'] += 1
                by_year[event_date]['correct'] += int(is_correct)

    # Build results
    def stats(d):
        return {k: {
            'count': v['count'],
            'accuracy': round(v['correct'] / v['count'] * 100, 2) if v['count'] else 0,
            'draw_rate': round(v['draw_count'] / v['count'] * 100, 1) if v['count'] else 0,
            'home_win_rate': round(v['home_win_count'] / v['count'] * 100, 1) if v['count'] else 0,
            'away_win_rate': round(v.get('away_win_count', 0) / v['count'] * 100, 1) if v['count'] else 0,
        } for k, v in d.items()}

    result = {
        'processed': processed,
        'errors': errors,
        'total': stats(total)['all'],
        'by_bucket': stats(by_bucket),
        'by_year': {k: {'count': v['count'], 'accuracy': round(v['correct']/v['count']*100, 2) if v['count'] else 0}
                    for k, v in sorted(by_year.items())},
    }

    return result


def print_backtest_result(result):
    """打印回测结果"""
    if 'error' in result:
        print(f'Error: {result["error"]}')
        return

    t = result['total']
    print(f'=== Oddsfe赔率回测 ({result["processed"]:,}场) ===')
    print(f'总体准确率: {t["accuracy"]:.2f}%')
    print(f'主胜率: {t["home_win_rate"]:.1f}%  平局率: {t["draw_rate"]:.1f}%  客胜率: {t["away_win_rate"]:.1f}%')
    print()

    print('按赔率区间:')
    print(f'{"区间":<12} {"场次":>8} {"准确率":>8} {"平局率":>8}')
    for bname in ['<1.30', '1.30-1.60', '1.60-2.00', '2.00-3.00', '>3.00']:
        b = result['by_bucket'].get(bname, {})
        if b:
            print(f'{bname:<12} {b["count"]:>8,} {b["accuracy"]:>7.2f}% {b["draw_rate"]:>7.1f}%')

    print()
    print('按年份:')
    for year, y in sorted(result['by_year'].items()):
        if y['count'] > 100:
            print(f'  {year}: {y["count"]:>8,}  {y["accuracy"]:>6.2f}%')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    result = run_oddsfe_backtest(limit=args.limit)
    print_backtest_result(result)
