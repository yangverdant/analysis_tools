"""一键回测 — 命令行入口

用法:
  python -m scripts.backtest                  # 默认30天
  python -m scripts.backtest --days 60        # 60天回测
  python -m scripts.backtest --stake 50       # 每场50元
"""
import argparse
import sys

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from backend.app.core.backtest import run_backtest, backtest_to_dict
import json


SPF_LABEL = {'3': '主胜', '1': '平局', '0': '客胜'}


def main():
    parser = argparse.ArgumentParser(description='足球分析师回测')
    parser.add_argument('--days', type=int, default=30, help='回测天数')
    parser.add_argument('--stake', type=float, default=100, help='每场投注金额')
    parser.add_argument('--db', type=str, default='data/football_v2.db', help='数据库路径')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    args = parser.parse_args()

    result = run_backtest(args.db, days=args.days, stake_per_match=args.stake)

    if args.json:
        print(json.dumps(backtest_to_dict(result), ensure_ascii=False, indent=2))
        return

    if result.total_matches == 0:
        print(f'\n过去{args.days}天无验证数据可回测')
        return

    # 格式化输出
    s = result
    print(f'\n{"="*60}')
    print(f'  回测报告 — 过去{args.days}天 (每场{args.stake}元)')
    print(f'{"="*60}')

    print(f'\n  总场次: {s.total_matches}')
    print(f'  总投注: {s.total_stake:.0f}元')
    print(f'  总回报: {s.total_return:.0f}元')
    print(f'  净盈亏: {s.total_profit:+.0f}元')
    print(f'  ROI: {s.roi:+.1%}')
    print(f'  胜率: {s.win_rate:.1%} ({s.win_count}/{s.total_matches})')
    print(f'  Brier: {s.brier_avg:.4f}')

    # 按场景
    if s.by_scene:
        print(f'\n  【按场景】')
        for scene, stats in s.by_scene.items():
            print(f'    {scene}: {stats["matches"]}场, 胜率{stats.get("win_rate",0):.1%}, ROI{stats.get("roi",0):+.1%}, 盈亏{stats["profit"]:+.0f}元')

    # 按日期
    if s.by_date:
        print(f'\n  【按日期】')
        for d in s.by_date:
            print(f'    {d["date"]}: {d["matches"]}场, {d["wins"]}胜, 盈亏{d["profit"]:+.0f}元')

    # 每场详情
    print(f'\n  【逐场明细】')
    for d in s.daily_profit:
        result_str = '✓' if d['correct'] else '✗'
        pred_label = SPF_LABEL.get(d['predicted'], d['predicted'])
        actual_label = SPF_LABEL.get(d['actual'], d['actual'])
        print(f'    {d["date"]} {d["match"]:20s} | 推荐{pred_label} 实际{actual_label} {result_str} | 赔率{d["odds"]:.2f} 盈亏{d["profit"]:+.0f} | 累计{d["cumulative"]:+.0f}')

    print()


if __name__ == '__main__':
    main()
