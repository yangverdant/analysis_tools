"""概率校准模块 — 用历史验证数据校准模型概率

方案: 分桶校准 + 保序回归(Isotonic Regression)
  1. 把历史 predicted_prob 按 0.1 步长分桶
  2. 计算每桶的实际命中率
  3. 保序回归: 合并非单调相邻桶, 保证校准后概率单调递增
  4. 预测时: 模型概率 → 找到对应桶 → 返回校准后概率

保序回归确保: 模型概率越高 → 校准后概率也越高(或至少不低),
避免小样本噪声导致非单调校准(如rqspf 0.9-1.0桶25%但0.7-0.8桶58%).
"""
import sqlite3
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _ensure_calibration_table(conn):
    """确保校准表存在"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS probability_calibration (
            play_type TEXT NOT NULL,
            bucket_lower REAL NOT NULL,
            bucket_upper REAL NOT NULL,
            calibrated_prob REAL NOT NULL,
            sample_size INTEGER NOT NULL,
            actual_accuracy REAL NOT NULL,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (play_type, bucket_lower)
        )
    """)
    conn.commit()


def _isotonic_regression(buckets: List[Tuple[float, float, int]]) -> List[Tuple[float, float, int]]:
    """Pool Adjacent Violators Algorithm (PAVA) for isotonic regression.

    Args:
        buckets: [(bucket_lower, raw_accuracy, sample_size), ...] sorted by bucket_lower

    Returns:
        [(bucket_lower, calibrated_prob, merged_sample_size), ...] with monotonic non-decreasing probs.
        Only the first bucket_lower of each merged group is returned.
    """
    if len(buckets) <= 1:
        return list(buckets)

    # Stack of (weighted_sum, total_weight, start_idx, end_idx)
    stack: List[Tuple[float, float, int, int]] = []
    for i, (bl, acc, n) in enumerate(buckets):
        stack.append((acc * n, float(n), i, i))
        while len(stack) >= 2:
            prev_wsum, prev_w, prev_start, prev_end = stack[-2]
            curr_wsum, curr_w, _, curr_end = stack[-1]
            prev_val = prev_wsum / prev_w
            curr_val = curr_wsum / curr_w
            if prev_val > curr_val + 1e-9:
                stack[-2] = (prev_wsum + curr_wsum, prev_w + curr_w, prev_start, curr_end)
                stack.pop()
            else:
                break

    result = []
    for wsum, w, start_idx, _ in stack:
        bl = buckets[start_idx][0]
        result.append((bl, wsum / w, int(w)))
    return result


def _apply_isotonic_to_buckets(buckets: list, iso: list) -> dict:
    """Map each original bucket_lower to its isotonic calibrated value.

    Args:
        buckets: original bucket list with 'bucket_lower' keys
        iso: isotonic regression result [(start_bl, calibrated, n), ...]

    Returns:
        {bucket_lower: calibrated_prob}
    """
    mapping = {}
    for b in buckets:
        bl = b['bucket_lower']
        # Find the iso group this bucket belongs to (latest start_bl <= bl)
        best_cal = b['actual_acc']
        for iso_bl, iso_cal, _ in iso:
            if iso_bl <= bl + 0.001:
                best_cal = iso_cal
            else:
                break
        mapping[bl] = best_cal
    return mapping


def compute_calibration(db_path: str, days: int = 60, min_sample: int = 5) -> dict:
    """从历史验证数据计算校准曲线 (含保序回归)

    Returns: {play_type: [{bucket, model_prob, actual_acc, sample, calibrated_prob}]}
    """
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    _ensure_calibration_table(conn)

    conn.execute("DELETE FROM probability_calibration")

    cursor = conn.cursor()
    cursor.execute("""
        SELECT play_type,
               ROUND(predicted_prob * 10) / 10 as bucket_lower,
               COUNT(*) as n,
               AVG(CASE WHEN is_correct=1 THEN 1.0 ELSE 0 END) as acc,
               AVG(predicted_prob) as avg_model_prob
        FROM lottery_validation
        WHERE validated_at >= datetime('now', ?)
          AND predicted_prob IS NOT NULL
          AND predicted_prob > 0
        GROUP BY play_type, bucket_lower
        HAVING n >= ?
        ORDER BY play_type, bucket_lower
    """, (f'-{days} days', min_sample))

    rows = [dict(r) for r in cursor.fetchall()]

    # Group by play_type, then apply isotonic regression per type
    by_type: dict = {}
    for r in rows:
        pt = r['play_type']
        bl = r['bucket_lower']
        if bl is None:
            continue
        by_type.setdefault(pt, []).append({
            'bucket_lower': float(bl),
            'bucket_upper': float(bl) + 0.1,
            'actual_acc': float(r['acc']),
            'n': int(r['n']),
            'avg_model_prob': float(r['avg_model_prob']),
        })

    result = {}
    inserted = 0

    for pt, buckets in by_type.items():
        # Step 1: Bayesian smoothing — shrink each bucket toward global mean
        # This prevents small-sample buckets from causing excessive merging
        total_n = sum(b['n'] for b in buckets)
        total_correct = sum(b['actual_acc'] * b['n'] for b in buckets)
        global_acc = total_correct / total_n if total_n > 0 else 0.5
        # Prior strength: equivalent to 20 pseudo-observations (moderate shrinkage)
        prior_n = 20
        smoothed = []
        for b in buckets:
            # Bayesian: (correct + prior_n * global_acc) / (n + prior_n)
            bayes_acc = (b['actual_acc'] * b['n'] + prior_n * global_acc) / (b['n'] + prior_n)
            smoothed.append((b['bucket_lower'], bayes_acc, b['n']))

        # Step 2: Apply isotonic regression on smoothed values
        iso = _isotonic_regression(smoothed)
        iso_map = _apply_isotonic_to_buckets(buckets, iso)

        for b in buckets:
            bl = b['bucket_lower']
            calibrated = max(0.05, min(0.95, iso_map[bl]))

            cursor.execute("""
                INSERT OR REPLACE INTO probability_calibration
                (play_type, bucket_lower, bucket_upper, calibrated_prob,
                 sample_size, actual_accuracy, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (pt, bl, bl + 0.1, calibrated, b['n'], b['actual_acc']))

            if pt not in result:
                result[pt] = []
            result[pt].append({
                'bucket': f'{bl:.1f}-{bl + 0.1:.1f}',
                'model_prob': round(b['avg_model_prob'], 3),
                'actual_acc': round(b['actual_acc'], 3),
                'calibrated_prob': round(calibrated, 3),
                'sample': b['n'],
            })
            inserted += 1

    conn.commit()
    conn.close()
    logger.info('概率校准完成(含保序回归): %d个桶, 覆盖%d个玩法', inserted, len(result))
    return {'buckets': inserted, 'play_types': list(result.keys()), 'detail': result}


def get_calibrated_probability(db_path: str, play_type: str,
                                model_prob: float) -> Optional[float]:
    """获取校准后的概率 — 供analyze调用

    使用线性插值: 在相邻桶之间插值, 避免阶梯式跳变。
    若无精确匹配, 使用最近的桶(距离加权)。

    Args:
        play_type: spf/ou/bf/rqspf/bqc
        model_prob: 模型原始概率 (0-1)

    Returns:
        校准后概率, 或 None(无校准数据时)
    """
    if not model_prob or model_prob <= 0:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT bucket_lower, calibrated_prob FROM probability_calibration
            WHERE play_type = ?
            ORDER BY bucket_lower
        """, (play_type,)).fetchall()
        conn.close()
        if not rows:
            return None

        # Linear interpolation between adjacent buckets
        bucket_lower = round(model_prob * 10) / 10
        # Find exact match first
        for r in rows:
            if abs(r['bucket_lower'] - bucket_lower) < 0.001:
                return float(r['calibrated_prob'])

        # No exact match — find surrounding buckets and interpolate
        lower_row = None
        upper_row = None
        for r in rows:
            bl = float(r['bucket_lower'])
            if bl < bucket_lower:
                lower_row = r
            elif bl > bucket_lower and upper_row is None:
                upper_row = r

        if lower_row and upper_row:
            # Linear interpolation
            x0 = float(lower_row['bucket_lower'])
            x1 = float(upper_row['bucket_lower'])
            y0 = float(lower_row['calibrated_prob'])
            y1 = float(upper_row['calibrated_prob'])
            if abs(x1 - x0) > 1e-9:
                t = (bucket_lower - x0) / (x1 - x0)
                return round(y0 + t * (y1 - y0), 4)

        # Fallback: nearest bucket
        nearest = lower_row or upper_row
        if nearest:
            return float(nearest['calibrated_prob'])
        return None
    except Exception as e:
        logger.debug('校准查询失败: %s', e)
        return None


def apply_calibration_to_play(db_path: str, play_type: str,
                               play: dict) -> bool:
    """对单个玩法的预测应用校准

    修改 play['confidence'] 和 play['probability'] 为校准后值
    保留 play['raw_probability'] 作为原始值

    若校准后概率大幅下降(>=0.3), 降级 confidence_level 到 low/avoid,
    让推送时能过滤掉"模型高信心但历史证明不准"的预测(如 rqspf vhigh档).

    Returns: True if applied
    """
    if not isinstance(play, dict):
        return False
    raw_prob = play.get('confidence') or play.get('probability')
    if raw_prob is None:
        return False
    try:
        raw_prob = float(raw_prob)
    except (TypeError, ValueError):
        return False

    calibrated = get_calibrated_probability(db_path, play_type, raw_prob)
    if calibrated is None or abs(calibrated - raw_prob) < 0.001:
        return False

    play['raw_probability'] = round(raw_prob, 4)
    play['confidence'] = round(calibrated, 4)
    if 'probability' in play:
        play['probability'] = round(calibrated, 4)
    play['calibration_applied'] = True

    # 大幅下调: 模型高信心但历史证明不准, 降级 confidence_level
    # 触发条件: 原概率>=0.6(原本高信心)但校准后<0.5(历史证明这个区间准确率<50%)
    if raw_prob >= 0.6 and calibrated < 0.5:
        current_level = play.get('confidence_level') or play.get('confidence_tier')
        if current_level != 'avoid':
            play['confidence_level'] = 'avoid'
            play['confidence_tier'] = 'avoid'
            play['calibration_downgraded'] = True
            play['calibration_drop'] = round(raw_prob - calibrated, 4)

    return True


def get_calibration_summary(db_path: str) -> dict:
    """获取校准概况 — 供驾驶舱展示"""
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT play_type,
                   COUNT(*) as buckets,
                   SUM(sample_size) as total_sample,
                   MIN(actual_accuracy) as min_acc,
                   MAX(actual_accuracy) as max_acc
            FROM probability_calibration
            GROUP BY play_type
            ORDER BY play_type
        """).fetchall()
        conn.close()
        return {r['play_type']: dict(r) for r in rows}
    except Exception:
        return {}
