"""归因驱动学习 — 消费lottery_validation.attribution生成针对性调整

核心理念:
- learn.py的scene-based loop只看"scene准确率<赔率基线"→调权重, 但不知道"为什么"
- 本模块从attribution分布入手, 识别失败模式, 生成具体可执行的调整
- 调整对象: confidence阈值, 概率校准曲线, 场景特定权重, HT/O/U transition参数

调整策略 (按attribution类型):
1. low_confidence_noise (prob<0.5仍预测) → 提高confidence_threshold, 减少低质量预测
2. model_overconfidence (prob>=0.65但错) → 降低high-prob bucket的校准乘数
3. close_match (0.35-0.65) → 不可调, 标记为inherent uncertainty
4. half_time_axis_misread (bqc) → 标记HT transition需调整, 记录样本
5. goal_axis_misread (ou) → 标记xG lambda需调整, 记录样本
6. market_misread → blend赔率权重提高
7. tournament_context_misread → 场景规则需复核
"""
import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


def _get_model_version() -> str:
    try:
        import yaml
        with open(PROJECT_ROOT / "config" / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("model", {}).get("version", "3.9.2")
    except Exception:
        return "3.9.2"


def analyze_attribution_patterns(conn, days: int = 30) -> Dict:
    """分析归因分布模式, 按scene+play_type分组

    Returns:
        {
            (scene, play_type): {
                'total_errors': int,
                'patterns': {attribution: {'count': int, 'avg_prob': float, 'avg_conf': float}},
                'dominant_pattern': str,  # 数量最多的attribution
                'actionable': bool,       # 是否有可执行调整
                'action_type': str,       # 调整类型
                'action_params': dict     # 调整参数
            }
        }
    """
    cutoff = f"-{days} days"
    rows = conn.execute("""
        SELECT lv.play_type, lv.attribution, lv.predicted_prob, lv.confidence,
               lv.is_correct, COALESCE(lv.scenario_type, 'unknown') as scene,
               lv.predicted_result, lv.actual_result
        FROM lottery_validation lv
        WHERE lv.validated_at >= datetime('now', ?)
          AND lv.attribution IS NOT NULL
    """, (cutoff,)).fetchall()

    # 按(scene, play_type)分组
    groups = defaultdict(lambda: {
        'total_errors': 0,
        'total_correct': 0,
        'patterns': defaultdict(lambda: {'count': 0, 'prob_sum': 0.0, 'conf_sum': 0.0})
    })

    for r in rows:
        scene = r['scene'] or 'unknown'
        play_type = r['play_type'] or 'spf'
        attr = r['attribution']
        if not attr:
            continue

        key = (scene, play_type)
        group = groups[key]

        if r['is_correct']:
            group['total_correct'] += 1
        else:
            group['total_errors'] += 1

        if not r['is_correct']:
            pat = group['patterns'][attr]
            pat['count'] += 1
            pat['prob_sum'] += r['predicted_prob'] or 0.5
            pat['conf_sum'] += r['confidence'] or 0.5

    # 分析每个group的可执行调整
    results = {}
    for key, group in groups.items():
        scene, play_type = key
        patterns = {k: {
            'count': v['count'],
            'avg_prob': v['prob_sum'] / max(v['count'], 1),
            'avg_conf': v['conf_sum'] / max(v['count'], 1)
        } for k, v in group['patterns'].items()}

        if not patterns:
            continue

        # 找dominant pattern
        dominant = max(patterns.items(), key=lambda x: x[1]['count'])
        dominant_name = dominant[0]
        dominant_data = dominant[1]

        # 判断action_type
        action_type, action_params = _determine_action(
            play_type, dominant_name, dominant_data, group
        )

        results[key] = {
            'scene': scene,
            'play_type': play_type,
            'total_errors': group['total_errors'],
            'total_correct': group['total_correct'],
            'patterns': patterns,
            'dominant_pattern': dominant_name,
            'actionable': action_type is not None,
            'action_type': action_type,
            'action_params': action_params,
        }

    return results


def _determine_action(play_type: str, dominant_pattern: str,
                      pattern_data: dict, group: dict) -> tuple:
    """根据dominant pattern确定调整动作

    Returns: (action_type, action_params)
    """
    count = pattern_data['count']
    avg_prob = pattern_data['avg_prob']
    avg_conf = pattern_data['avg_conf']

    # 样本太少不调
    if count < 5:
        return None, {}

    # 1. low_confidence_noise: prob低仍预测失败 → 提高confidence_threshold
    if dominant_pattern == 'low_confidence_noise':
        # 当前avg_prob就是失败预测的平均概率
        # 建议threshold = avg_prob + 0.05, 避免这类预测
        new_threshold = min(avg_prob + 0.05, 0.55)
        return 'raise_confidence_threshold', {
            'play_type': play_type,
            'current_threshold': 0.40,  # 默认值, 实际从model_params_history读
            'suggested_threshold': new_threshold,
            'reason': f'low_confidence_noise {count}条, avg_prob={avg_prob:.3f}',
        }

    # 2. model_overconfidence: 高概率预测失败 → 降低high-prob校准乘数
    if dominant_pattern == 'model_overconfidence':
        return 'reduce_high_prob_calibration', {
            'play_type': play_type,
            'current_multiplier': 1.0,
            'suggested_multiplier': 0.92,  # 高prob预测概率降8%
            'reason': f'model_overconfidence {count}条, avg_prob={avg_prob:.3f}',
        }

    # 3. close_match: 不可调, inherent uncertainty
    if dominant_pattern == 'close_match':
        return None, {'reason': 'close_match is inherent uncertainty, no adjustment'}

    # 4. half_time_axis_misread (bqc): HT transition需调整
    if dominant_pattern == 'half_time_axis_misread':
        return 'flag_ht_transition_issue', {
            'play_type': 'bqc',
            'sample_count': count,
            'reason': f'bqc HT方向错误{count}条, 需调整HT transition matrix',
        }

    # 5. goal_axis_misread (ou): xG lambda需调整
    if dominant_pattern == 'goal_axis_misread':
        return 'flag_xg_calibration_issue', {
            'play_type': 'ou',
            'sample_count': count,
            'avg_prob': avg_prob,
            'reason': f'ou进球轴错误{count}条, 需调整xG lambda',
        }

    # 6. market_misread: 提高赔率blend权重
    if dominant_pattern == 'market_misread':
        return 'increase_odds_blend', {
            'play_type': play_type,
            'current_blend': 0.30,
            'suggested_blend': 0.35,
            'reason': f'market_misread {count}条, 模型未跟随赔率信号',
        }

    # 7. tournament_context_misread: 标记场景规则需复核
    if dominant_pattern == 'tournament_context_misread':
        return 'flag_tournament_rule_review', {
            'play_type': play_type,
            'sample_count': count,
            'reason': f'赛事上下文误判{count}条, 场景规则需复核',
        }

    # 8. market_wrong: 赔率方向错, 模型反了 → 模型正确, 无需调整
    if dominant_pattern == 'market_wrong':
        return None, {'reason': 'market_wrong: 赔率错模型对, 无需调整'}

    return None, {}


def apply_attribution_driven_adjustments(conn, patterns: Dict, agent=None) -> List[dict]:
    """应用归因驱动的调整

    Returns: 调整记录列表
    """
    adjustments = []

    for key, pattern in patterns.items():
        if not pattern.get('actionable'):
            continue

        action_type = pattern['action_type']
        params = pattern['action_params']
        scene = pattern['scene']
        play_type = pattern['play_type']

        try:
            if action_type == 'raise_confidence_threshold':
                adj = _apply_confidence_threshold(conn, scene, play_type, params)
                if adj:
                    adj['scene'] = scene
                    adj['play_type'] = play_type
                    adjustments.append(adj)

            elif action_type == 'reduce_high_prob_calibration':
                adj = _apply_high_prob_calibration(conn, scene, play_type, params)
                if adj:
                    adj['scene'] = scene
                    adj['play_type'] = play_type
                    adjustments.append(adj)

            elif action_type == 'increase_odds_blend':
                adj = _apply_odds_blend_adjustment(conn, scene, play_type, params)
                if adj:
                    adj['scene'] = scene
                    adj['play_type'] = play_type
                    adjustments.append(adj)

            elif action_type in ('flag_ht_transition_issue',
                                  'flag_xg_calibration_issue',
                                  'flag_tournament_rule_review'):
                # 记录flag, 不直接调参, 留给后续专门模块处理
                adj = _record_issue_flag(conn, scene, play_type, action_type, params)
                if adj:
                    adj['scene'] = scene
                    adj['play_type'] = play_type
                    adjustments.append(adj)

        except Exception as e:
            logger.warning(f'归因调整失败 {scene}/{play_type}/{action_type}: {e}')

    return adjustments


def _apply_confidence_threshold(conn, scene, play_type, params) -> Optional[dict]:
    """应用confidence阈值调整

    逻辑: 读取当前阈值, 如果建议阈值更高, 记录变更
    """
    suggested = params.get('suggested_threshold', 0.45)
    current = _read_current_param(conn, f'{play_type}_confidence_threshold', 0.40)

    if suggested <= current:
        return None  # 建议值不比当前高, 不调

    param_name = f'{play_type}_confidence_threshold'
    reason = params.get('reason', '')

    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f'{param_name}_{scene}_attribution',
        current, suggested,
        f'归因驱动: {reason} | threshold {current:.3f}→{suggested:.3f}',
        0, 0, 0,
        datetime.now().isoformat()
    ))

    return {
        'factor': param_name,
        'old': current,
        'new': suggested,
        'action_type': 'raise_confidence_threshold',
        'reason': reason,
    }


def _apply_high_prob_calibration(conn, scene, play_type, params) -> Optional[dict]:
    """应用高概率校准调整 — 记录建议, 由probability_calibration模块读取"""
    suggested = params.get('suggested_multiplier', 0.92)
    current = params.get('current_multiplier', 1.0)

    param_name = f'{play_type}_high_prob_multiplier'
    reason = params.get('reason', '')

    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f'{param_name}_{scene}_attribution',
        current, suggested,
        f'归因驱动: {reason} | high_prob_multiplier {current:.3f}→{suggested:.3f}',
        0, 0, 0,
        datetime.now().isoformat()
    ))

    return {
        'factor': param_name,
        'old': current,
        'new': suggested,
        'action_type': 'reduce_high_prob_calibration',
        'reason': reason,
    }


def _apply_odds_blend_adjustment(conn, scene, play_type, params) -> Optional[dict]:
    """应用赔率blend权重调整"""
    suggested = params.get('suggested_blend', 0.35)
    current = params.get('current_blend', 0.30)

    if abs(suggested - current) < 0.02:
        return None

    param_name = f'{play_type}_odds_blend_weight'
    reason = params.get('reason', '')

    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f'{param_name}_{scene}_attribution',
        current, suggested,
        f'归因驱动: {reason} | odds_blend {current:.3f}→{suggested:.3f}',
        0, 0, 0,
        datetime.now().isoformat()
    ))

    return {
        'factor': param_name,
        'old': current,
        'new': suggested,
        'action_type': 'increase_odds_blend',
        'reason': reason,
    }


def _record_issue_flag(conn, scene, play_type, action_type, params) -> Optional[dict]:
    """记录issue flag, 不直接调参"""
    reason = params.get('reason', '')
    sample_count = params.get('sample_count', 0)

    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f'{action_type}_{scene}_{play_type}_attribution',
        0, 0,
        f'归因驱动flag: {reason} | sample={sample_count}',
        0, 0, sample_count,
        datetime.now().isoformat()
    ))

    return {
        'factor': action_type,
        'old': 0,
        'new': 0,
        'action_type': action_type,
        'reason': reason,
        'sample_count': sample_count,
    }


def _read_current_param(conn, param_name_prefix: str, default: float) -> float:
    """从model_params_history读取最新参数值"""
    try:
        row = conn.execute("""
            SELECT new_value FROM model_params_history
            WHERE param_name LIKE ?
            ORDER BY changed_at DESC LIMIT 1
        """, (f'{param_name_prefix}%',)).fetchone()
        if row:
            return float(row[0])
    except Exception:
        pass
    return default


def run_attribution_driven_learning(db_path: str, days: int = 30, agent=None) -> dict:
    """主入口: 归因驱动学习

    Returns:
        {
            'patterns_found': int,
            'adjustments': List[dict],
            'summary': str,
        }
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        patterns = analyze_attribution_patterns(conn, days=days)

        if not patterns:
            return {
                'patterns_found': 0,
                'adjustments': [],
                'summary': '无归因数据可分析',
            }

        adjustments = apply_attribution_driven_adjustments(conn, patterns, agent=agent)

        # 生成摘要
        summary_parts = []
        for key, pat in patterns.items():
            if pat.get('actionable'):
                summary_parts.append(
                    f"{pat['scene']}/{pat['play_type']}: "
                    f"{pat['dominant_pattern']}({pat['action_type']})"
                )

        summary = '; '.join(summary_parts) if summary_parts else '无可执行调整'

        conn.commit()

        return {
            'patterns_found': len(patterns),
            'adjustments': adjustments,
            'summary': summary,
        }

    except Exception as e:
        logger.error(f'归因驱动学习失败: {e}')
        conn.rollback()
        return {
            'patterns_found': 0,
            'adjustments': [],
            'summary': f'error: {e}',
        }
    finally:
        conn.close()
