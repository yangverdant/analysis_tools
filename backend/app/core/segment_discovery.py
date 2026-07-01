"""Segment自动挖掘 — 发现模型准确率异常的细分场景

系统原本只按3维切片(scenario_type/participant_type/play_type)，
本模块自动按更多维度组合挖掘高偏差segment，
让系统能发现"世界杯淘汰赛平局率58%"这种模式。

数据来源: lottery_validation JOIN lottery_matches
维度: scenario_type × play_type × league_name_cn × odds_tier(可选)
"""
import json
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def discover_segments(db_path: str, min_sample: int = 10,
                      min_gap: float = 0.10, days: int = 90) -> List[dict]:
    """自动发现准确率异常场景segment

    维度组合：
    - scenario_type (friendly_intl/international_cup/league)
    - play_type (spf/ou/rqspf/bqc)
    - league_name_cn (英超/西甲/世界杯/...)

    逻辑：
    1. 计算整体平均准确率 baseline
    2. 按维度组合 GROUP BY 统计每segment准确率
    3. 找出 |segment_acc - baseline| > min_gap 且样本≥min_sample 的 segment
    """
    try:
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff = f"-{days} days"

        # 整体基线
        cursor.execute("""
            SELECT COUNT(*) as total, SUM(is_correct) as correct
            FROM lottery_validation
            WHERE validated_at >= datetime('now', ?)
            AND is_correct IS NOT NULL
        """, (cutoff,))
        baseline_row = cursor.fetchone()
        baseline_total = baseline_row['total'] if baseline_row else 0
        baseline_correct = baseline_row['correct'] if baseline_row else 0
        baseline_acc = (baseline_correct / baseline_total) if baseline_total > 0 else 0.5
        logger.info('segment挖掘基线: %d场, 准确率%.1f%%',
                    baseline_total, baseline_acc * 100)

        # 按维度组合统计
        cursor.execute("""
            SELECT
                COALESCE(lv.scenario_type, 'unknown') as scenario_type,
                COALESCE(lv.play_type, 'spf') as play_type,
                COALESCE(lm.league_name_cn, '未知') as league,
                COUNT(*) as total,
                SUM(lv.is_correct) as correct
            FROM lottery_validation lv
            LEFT JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lv.validated_at >= datetime('now', ?)
            AND lv.is_correct IS NOT NULL
            GROUP BY scenario_type, play_type, league
            HAVING total >= ?
        """, (cutoff, min_sample))

        segments = []
        for row in cursor.fetchall():
            r = dict(row)
            total = r.get('total', 0)
            correct = r.get('correct') or 0
            seg_acc = correct / total if total > 0 else 0
            gap = seg_acc - baseline_acc

            if abs(gap) >= min_gap:
                key_parts = [r.get('scenario_type', '?'),
                             r.get('play_type', '?'),
                             r.get('league', '?')]
                segments.append({
                    'key': '/'.join(key_parts),
                    'scenario_type': r.get('scenario_type'),
                    'play_type': r.get('play_type'),
                    'league': r.get('league'),
                    'sample': total,
                    'model_accuracy': round(seg_acc, 4),
                    'odds_accuracy': round(baseline_acc, 4),
                    'baseline_accuracy': round(baseline_acc, 4),
                    'segment_accuracy': round(seg_acc, 4),
                    'gap': round(gap, 4),
                    'direction': 'better_than_baseline' if gap > 0 else 'worse_than_baseline',
                })

        conn.close()
        segments.sort(key=lambda x: abs(x['gap']), reverse=True)
        return segments[:20]
    except Exception as e:
        logger.warning('segment挖掘失败: %s', e)
        return []


def record_segment_discovery(conn, segment: dict) -> None:
    """记录发现的segment到model_params_history"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO model_params_history
            (model_version, param_name, old_value, new_value, change_reason,
             accuracy_before, accuracy_after, sample_size, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            'segment_discovery',
            f"segment:{segment['key']}",
            segment['baseline_accuracy'],
            segment['segment_accuracy'],
            f"segment偏差: segment{segment['segment_accuracy']:.0%} vs baseline{segment['baseline_accuracy']:.0%}, "
            f"gap={segment['gap']:+.1%}, 样本{segment['sample']}场, 方向={segment['direction']}",
            segment['baseline_accuracy'],
            segment['segment_accuracy'],
            segment['sample'],
        ))
        conn.commit()
        logger.info('segment发现已记录: %s (gap=%+.1f%%)',
                    segment['key'], segment['gap'] * 100)
    except Exception as e:
        logger.debug('记录segment失败: %s', e)


def run_segment_discovery(db_path: str) -> dict:
    """执行segment挖掘 — 供learn.py调用

    Returns: {discovered: N, recorded: N, segments: [...]}
    """
    segments = discover_segments(db_path)
    if not segments:
        return {'discovered': 0, 'recorded': 0, 'segments': []}

    recorded = 0
    try:
        conn = sqlite3.connect(db_path, timeout=30)
        for seg in segments:
            record_segment_discovery(conn, seg)
            recorded += 1
        conn.close()
    except Exception as e:
        logger.warning('segment记录失败: %s', e)

    logger.info('segment挖掘完成: 发现%d个, 记录%d个', len(segments), recorded)
    return {'discovered': len(segments), 'recorded': recorded, 'segments': segments}
