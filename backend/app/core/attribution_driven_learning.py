"""归因驱动学习 — 消费lottery_validation.attribution生成针对性调整

核心理念:
- learn.py的scene-based loop只看"scene准确率<赔率基线"→调权重, 但不知道"为什么"
- 本模块从attribution分布入手, 识别失败模式, 生成具体可执行的调整
- 调整对象: confidence阈值, 概率校准曲线, 场景特定权重, HT/O/U transition参数

调整策略 (按attribution类型):
1. low_confidence_noise (prob<0.5仍预测) → 提高confidence_threshold, 减少低质量预测
2. model_overconfidence (prob>=0.65但错) → 降低high-prob bucket的校准乘数
3. close_match (0.35-0.65) → 不可调, 标记为inherent uncertainty
4. half_time_axis_misread (bqc) → 重算scene-specific HT→FT transition matrix
5. goal_axis_misread (ou) → 计算OU lambda缩放因子, 调整xG
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
                'action_params': dict,    # 调整参数
                'samples': list           # 失败case的actual/pred/HT/FT数据, 供action使用
            }
        }
    """
    cutoff = f"-{days} days"
    rows = conn.execute("""
        SELECT lv.play_type, lv.attribution, lv.predicted_prob, lv.confidence,
               lv.is_correct, COALESCE(lv.scenario_type, 'unknown') as scene,
               lv.predicted_result, lv.actual_result,
               lr.home_goals_ht, lr.away_goals_ht,
               lr.home_goals_ft, lr.away_goals_ft
        FROM lottery_validation lv
        LEFT JOIN lottery_results lr ON lv.lottery_match_id = lr.lottery_match_id
        WHERE lv.validated_at >= datetime('now', ?)
          AND lv.attribution IS NOT NULL
    """, (cutoff,)).fetchall()

    # 按(scene, play_type)分组
    groups = defaultdict(lambda: {
        'total_errors': 0,
        'total_correct': 0,
        'patterns': defaultdict(lambda: {'count': 0, 'prob_sum': 0.0, 'conf_sum': 0.0}),
        'samples': [],
        'correct_totals': [],  # correct case的总进球数 (for ou)
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
            if r['home_goals_ft'] is not None:
                total = (r['home_goals_ft'] or 0) + (r['away_goals_ft'] or 0)
                group['correct_totals'].append(total)
        else:
            group['total_errors'] += 1
            pat = group['patterns'][attr]
            pat['count'] += 1
            pat['prob_sum'] += r['predicted_prob'] or 0.5
            pat['conf_sum'] += r['confidence'] or 0.5
            # 保留失败case的sample数据 (只在错误case)
            sample = {
                'predicted': r['predicted_result'],
                'actual': r['actual_result'],
                'ht_home': r['home_goals_ht'],
                'ht_away': r['away_goals_ht'],
                'ft_home': r['home_goals_ft'],
                'ft_away': r['away_goals_ft'],
            }
            group['samples'].append(sample)

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

    # 4. half_time_axis_misread (bqc): 从数据重算HT→FT transition
    if dominant_pattern == 'half_time_axis_misread':
        # 实际计算场景的empirical transition, 写入model_params_history
        transition = _compute_scene_transition(group, pattern_data)
        # sample太少时不要transition, 标记flag即可
        # 最少30条: 18条样本产出了严重偏差的transition(h->h=0.2), 需要足够样本保证稳定
        actual_samples = transition.get('_sample_count', 0)
        if actual_samples < 30:
            return 'flag_ht_transition_issue', {
                'play_type': 'bqc',
                'sample_count': count,
                'reason': f'bqc HT方向错误{count}条(有效HT/FT数据{actual_samples}条<30), sample不足, 暂flag不重算',
            }
        return 'recompute_ht_transition', {
            'play_type': 'bqc',
            'sample_count': count,
            'transition_matrix': transition,
            'reason': f'bqc HT方向错误{count}条, 重算HT→FT transition(有效{actual_samples}条)',
        }

    # 5. goal_axis_misread (ou): 计算lambda缩放因子
    if dominant_pattern == 'goal_axis_misread':
        # 失败case平均总进球 vs 成功case平均总进球 → 缩放因子
        lambda_scale = _compute_ou_lambda_scale(group)
        return 'apply_ou_lambda_scale', {
            'play_type': 'ou',
            'sample_count': count,
            'avg_prob': avg_prob,
            'lambda_scale': lambda_scale,
            'reason': f'ou进球轴错误{count}条, lambda缩放{lambda_scale:.3f}',
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

            elif action_type == 'recompute_ht_transition':
                adj = _apply_ht_transition_recompute(conn, scene, play_type, params)
                if adj:
                    adj['scene'] = scene
                    adj['play_type'] = play_type
                    adjustments.append(adj)

            elif action_type == 'apply_ou_lambda_scale':
                adj = _apply_ou_lambda_scale(conn, scene, play_type, params)
                if adj:
                    adj['scene'] = scene
                    adj['play_type'] = play_type
                    adjustments.append(adj)

            elif action_type == 'flag_ht_transition_issue':
                adj = _record_issue_flag(conn, scene, play_type, action_type, params)
                if adj:
                    adj['scene'] = scene
                    adj['play_type'] = play_type
                    adjustments.append(adj)

            elif action_type == 'flag_tournament_rule_review':
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


def _apply_ht_transition_recompute(conn, scene, play_type, params) -> Optional[dict]:
    """应用HT transition matrix重算 — 从失败case数据计算的scene-specific transition

    写入model_params_history, param_name编码scene.
    bqc_analyzer在analyze时读取这个值替代全局empirical matrix.
    """
    transition = params.get('transition_matrix', {})
    sample_count = params.get('sample_count', 0)
    reason = params.get('reason', '')

    if not transition or sample_count < 5:
        return None

    # 检查是否已有相同transition记录 (避免重复)
    transition_json = json.dumps(transition, ensure_ascii=False)
    param_name = f'bqc_ht_transition_{scene}'

    # 读取当前transition
    try:
        row = conn.execute("""
            SELECT new_value FROM model_params_history
            WHERE param_name LIKE ?
            ORDER BY changed_at DESC LIMIT 1
        """, (f'{param_name}%',)).fetchone()
        current_json = row[0] if row else '{}'
        if current_json == transition_json:
            return None  # 已应用相同调整, 不重复
    except Exception:
        pass

    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f'{param_name}_attribution',
        current_json, transition_json,
        f'归因驱动: {reason} | sample={sample_count}',
        0, 0, sample_count,
        datetime.now().isoformat()
    ))

    return {
        'factor': param_name,
        'old': current_json,
        'new': transition_json,
        'action_type': 'recompute_ht_transition',
        'reason': reason,
        'sample_count': sample_count,
    }


def _apply_ou_lambda_scale(conn, scene, play_type, params) -> Optional[dict]:
    """应用OU lambda缩放因子 — 从失败case数据计算的scene-specific scale

    写入model_params_history, param_name编码scene.
    ou分析在运行时读取这个scale, 调整xG lambda.
    """
    scale = params.get('lambda_scale', 1.0)
    sample_count = params.get('sample_count', 0)
    reason = params.get('reason', '')

    if abs(scale - 1.0) < 0.02 or sample_count < 5:
        return None  # 缩放太接近1.0 或样本太少

    param_name = f'ou_lambda_scale_{scene}'
    current = _read_current_param(conn, param_name, 1.0)

    # 已应用相同scale, 不重复
    if abs(scale - current) < 0.02:
        return None

    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f'{param_name}_attribution',
        current, scale,
        f'归因驱动: {reason} | scale {current:.3f}→{scale:.3f}',
        0, 0, sample_count,
        datetime.now().isoformat()
    ))

    return {
        'factor': param_name,
        'old': current,
        'new': scale,
        'action_type': 'apply_ou_lambda_scale',
        'reason': reason,
        'sample_count': sample_count,
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


def _compute_scene_transition(group: dict, pattern_data: dict) -> dict:
    """从失败case的HT/FT结果重算empirical transition matrix

    Returns: {'h': {'h': p, 'd': p, 'a': p}, 'd': {...}, 'a': {...}}
    其中h=主胜半场, d=平局半场, a=客胜半场
    """
    # 计数: HT结果 → FT结果
    counts = {'h': {'h': 0, 'd': 0, 'a': 0},
              'd': {'h': 0, 'd': 0, 'a': 0},
              'a': {'h': 0, 'd': 0, 'a': 0}}
    total = {'h': 0, 'd': 0, 'a': 0}

    for s in group.get('samples', []):
        ht_h = s.get('ht_home')
        ht_a = s.get('ht_away')
        ft_h = s.get('ft_home')
        ft_a = s.get('ft_away')
        if ht_h is None or ft_h is None:
            continue

        def result_key(h, a):
            if h > a:
                return 'h'
            if h < a:
                return 'a'
            return 'd'

        ht_key = result_key(ht_h, ht_a)
        ft_key = result_key(ft_h, ft_a)
        counts[ht_key][ft_key] += 1
        total[ht_key] += 1

    transition = {}
    for ht_key in ('h', 'd', 'a'):
        t = total[ht_key]
        if t > 0:
            transition[ht_key] = {
                'h': round(counts[ht_key]['h'] / t, 3),
                'd': round(counts[ht_key]['d'] / t, 3),
                'a': round(counts[ht_key]['a'] / t, 3),
            }
        else:
            # 无数据时用全局empirical (analyze.py:9643)
            empirical = {'h': {'h': 0.776, 'd': 0.159, 'a': 0.065},
                         'd': {'h': 0.349, 'd': 0.401, 'a': 0.251},
                         'a': {'h': 0.111, 'd': 0.209, 'a': 0.680}}
            transition[ht_key] = empirical[ht_key]

    transition['_sample_count'] = sum(total.values())
    return transition


def _compute_ou_lambda_scale(group: dict) -> float:
    """计算OU lambda缩放因子

    逻辑:
    - 失败case: 大球预测错(实际小球) → 模型xG偏高 → scale<1
    - 失败case: 小球预测错(实际大球) → 模型xG偏低 → scale>1
    - 用预测线的期望总进球 vs 实际总进球之比作为scale

    例如: 预测"大2.5"说明模型期望>2.5球, 但实际2球 → scale ≈ 2/2.5 = 0.8
    """
    over_errors = []  # (实际总进球, 预测线)
    under_errors = []
    for s in group.get('samples', []):
        ft_h = s.get('ft_home')
        ft_a = s.get('ft_away')
        pred = str(s.get('predicted') or '')
        if ft_h is None:
            continue
        total = (ft_h or 0) + (ft_a or 0)

        # 提取预测线: "大2.5" → 2.5, "小3" → 3.0
        import re
        m = re.search(r'[大小](\d+\.?\d*)', pred)
        line = float(m.group(1)) if m else 2.5

        if '大' in pred:
            over_errors.append((total, line))
        elif '小' in pred:
            under_errors.append((total, line))

    scale = 1.0

    if len(over_errors) > len(under_errors):
        # 大球预测错的多 → xG偏高 → scale<1
        ratios = [total / max(line, 0.5) for total, line in over_errors if total < line]
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            scale = avg_ratio  # scale < 1
    elif under_errors:
        # 小球预测错的多 → xG偏低 → scale>1
        ratios = [total / max(line, 0.5) for total, line in under_errors if total > line]
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            scale = avg_ratio  # scale > 1

    # 限制在0.80-1.20, 避免激进调整
    scale = max(0.80, min(1.20, scale))
    return round(scale, 3)


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
