"""校准效果回测 — 量化校准作为"信心分层"的价值

校准不是用来重选 argmax 方向(因为 validation 表只有已选方向的概率, 无法重做 argmax),
而是作为"信心评级": 把预测按校准后概率分档, 看高信心档的准确率是否显著高于低信心档。

如果校准有效:
  - 高信心档 (cal≥0.6) 准确率应明显高于 raw 同档
  - 低信心档 (cal<0.4) 准确率应明显低于 raw 同档
  - 校准让"值得跟"和"该弃"的区分度变高

输出: 每玩法各档 raw_acc vs cal_acc, 以及区分度(高信心-低信心)提升。
"""
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_calibrated_prob_lookup(db_path: str, play_type: str) -> dict:
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT bucket_lower, calibrated_prob FROM probability_calibration
            WHERE play_type = ?
        """, (play_type,)).fetchall()
        conn.close()
        return {round(r['bucket_lower'], 2): r['calibrated_prob'] for r in rows}
    except Exception:
        return {}


def _calibrate(prob: float, lookup: dict) -> Optional[float]:
    if not prob or prob <= 0 or not lookup:
        return None
    bucket = round(prob * 10) / 10
    return lookup.get(round(bucket, 2))


def _tier(prob: float) -> str:
    if prob is None:
        return 'unknown'
    if prob >= 0.6:
        return 'high'
    if prob >= 0.4:
        return 'medium'
    return 'low'


def backtest_calibration(db_path: str, days: int = 60) -> dict:
    """回测校准的信心分层价值

    Returns: {play_type: {sample, tiers: {high/medium/low: {raw_acc, cal_acc, n}}, separation_lift}}
    separation_lift = (cal_high_acc - cal_low_acc) - (raw_high_acc - raw_low_acc)
    正值 = 校准让高低信心档的准确率差距更大, 区分度提升
    """
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT play_type, is_correct, predicted_prob
        FROM lottery_validation
        WHERE validated_at >= datetime('now', ?)
          AND predicted_prob IS NOT NULL
          AND predicted_prob > 0
          AND is_correct IS NOT NULL
    """, (f'-{days} days',)).fetchall()
    conn.close()

    by_play = {}
    for r in rows:
        pt = r['play_type']
        by_play.setdefault(pt, []).append(dict(r))

    result = {}
    for pt, items in by_play.items():
        lookup = get_calibrated_prob_lookup(db_path, pt)

        # 按raw和cal分别分档
        raw_tiers = {'high': [], 'medium': [], 'low': []}
        cal_tiers = {'high': [], 'medium': [], 'low': []}
        for x in items:
            rt = _tier(x['predicted_prob'])
            if rt in raw_tiers:
                raw_tiers[rt].append(x['is_correct'])
            if lookup:
                cp = _calibrate(x['predicted_prob'], lookup)
                ct = _tier(cp) if cp else 'unknown'
                if ct in cal_tiers:
                    cal_tiers[ct].append(x['is_correct'])

        def _acc(arr):
            return round(sum(arr) / len(arr), 4) if arr else None

        raw_stats = {t: {'acc': _acc(v), 'n': len(v)} for t, v in raw_tiers.items()}
        cal_stats = {t: {'acc': _acc(v), 'n': len(v)} for t, v in cal_tiers.items()} if lookup else {}

        # 区分度: 高信心档准确率 - 低信心档准确率
        raw_sep = None
        if raw_stats['high']['acc'] is not None and raw_stats['low']['acc'] is not None:
            raw_sep = round(raw_stats['high']['acc'] - raw_stats['low']['acc'], 4)
        cal_sep = None
        if cal_stats and cal_stats.get('high', {}).get('acc') is not None and cal_stats.get('low', {}).get('acc') is not None:
            cal_sep = round(cal_stats['high']['acc'] - cal_stats['low']['acc'], 4)

        sep_lift = None
        if raw_sep is not None and cal_sep is not None:
            sep_lift = round(cal_sep - raw_sep, 4)

        result[pt] = {
            'sample': len(items),
            'cal_available': bool(lookup),
            'raw_tiers': raw_stats,
            'cal_tiers': cal_stats,
            'raw_separation': raw_sep,
            'cal_separation': cal_sep,
            'separation_lift': sep_lift,
        }
        logger.info('%s: raw分离度=%s cal分离度=%s lift=%s (n=%d)',
                    pt, raw_sep, cal_sep, sep_lift, len(items))

    return result


def backtest_summary(db_path: str, days: int = 60) -> dict:
    """简化版摘要 — 供API返回"""
    full = backtest_calibration(db_path, days)
    summary = {}
    for pt, info in full.items():
        summary[pt] = {
            'sample': info['sample'],
            'cal_available': info['cal_available'],
            'raw_high_acc': info['raw_tiers'].get('high', {}).get('acc'),
            'raw_low_acc': info['raw_tiers'].get('low', {}).get('acc'),
            'cal_high_acc': info['cal_tiers'].get('high', {}).get('acc'),
            'cal_low_acc': info['cal_tiers'].get('low', {}).get('acc'),
            'raw_separation': info['raw_separation'],
            'cal_separation': info['cal_separation'],
            'separation_lift': info['separation_lift'],
        }
    return summary
