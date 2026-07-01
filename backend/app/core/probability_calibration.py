"""概率校准模块 — 用历史验证数据校准模型概率

问题: 模型预测概率系统性偏差
  - spf avg_prob=50.3% 但实际 55.7% (低估5.4pp)
  - rqspf avg_prob=59.2% 但实际 48.7% (高估10.5pp)
  - bqc avg_prob=46.5% 但实际 36.8% (高估9.7pp)

方案: 分桶校准 (Isotonic-like)
  1. 把历史 predicted_prob 按 0.1 步长分桶 [0.0-0.1, 0.1-0.2, ..., 0.9-1.0]
  2. 计算每桶的实际命中率
  3. 预测时: 模型概率 → 找到对应桶 → 返回该桶的历史命中率

这样 argmax 决策会用校准后的概率, 直接提升命中率。
"""
import sqlite3
import logging
from typing import Optional

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


def compute_calibration(db_path: str, days: int = 60, min_sample: int = 5) -> dict:
    """从历史验证数据计算校准曲线

    Returns: {play_type: [{bucket, model_prob, actual_acc, sample, calibrated_prob}]}
    """
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    _ensure_calibration_table(conn)

    # 清空旧数据
    conn.execute("DELETE FROM probability_calibration")

    cursor = conn.cursor()
    # 按 0.1 步长分桶统计
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
    result = {}
    inserted = 0

    for r in rows:
        pt = r['play_type']
        bl = r['bucket_lower']
        if bl is None:
            continue
        bucket_lower = float(bl)
        bucket_upper = bucket_lower + 0.1
        actual_acc = float(r['acc'])
        n = int(r['n'])

        # 校准后的概率 = 该桶实际命中率 (clamped to [0.05, 0.95])
        calibrated = max(0.05, min(0.95, actual_acc))

        cursor.execute("""
            INSERT OR REPLACE INTO probability_calibration
            (play_type, bucket_lower, bucket_upper, calibrated_prob,
             sample_size, actual_accuracy, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (pt, bucket_lower, bucket_upper, calibrated, n, actual_acc))

        if pt not in result:
            result[pt] = []
        result[pt].append({
            'bucket': f'{bucket_lower:.1f}-{bucket_upper:.1f}',
            'model_prob': round(float(r['avg_model_prob']), 3),
            'actual_acc': round(actual_acc, 3),
            'calibrated_prob': round(calibrated, 3),
            'sample': n,
        })
        inserted += 1

    conn.commit()
    conn.close()
    logger.info('概率校准完成: %d个桶, 覆盖%d个玩法', inserted, len(result))
    return {'buckets': inserted, 'play_types': list(result.keys()), 'detail': result}


def get_calibrated_probability(db_path: str, play_type: str,
                                model_prob: float) -> Optional[float]:
    """获取校准后的概率 — 供analyze调用

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
        # 找到对应桶
        bucket_lower = round(model_prob * 10) / 10
        row = conn.execute("""
            SELECT calibrated_prob FROM probability_calibration
            WHERE play_type = ? AND ABS(bucket_lower - ?) < 0.001
        """, (play_type, bucket_lower)).fetchone()
        conn.close()
        if row:
            return float(row['calibrated_prob'])
        return None
    except Exception as e:
        logger.debug('校准查询失败: %s', e)
        return None


def apply_calibration_to_play(db_path: str, play_type: str,
                               play: dict) -> bool:
    """对单个玩法的预测应用校准

    修改 play['confidence'] 和 play['probability'] 为校准后值
    保留 play['raw_probability'] 作为原始值

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
