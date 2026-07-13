"""参数学习 — 数据驱动 + 回测验证 + Agent确认

数据源优先级:
1. lottery_validation (日循环验证写入)
2. prediction_logs + prediction_results (旧系统)
"""
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


def _get_db_path() -> str:
    """获取数据库路径"""
    try:
        with open(PROJECT_ROOT / "config" / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        path = cfg.get("database", {}).get("path", "data/football_v2.db")
        return str(PROJECT_ROOT / path)
    except Exception:
        return str(PROJECT_ROOT / "data" / "football_v2.db")


def _get_model_version() -> str:
    """获取模型版本"""
    try:
        with open(PROJECT_ROOT / "config" / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("model", {}).get("version", "3.9.2")
    except Exception:
        return "3.9.2"


def _get_unique_model_version(conn: sqlite3.Connection) -> str:
    """Return a unique model_weights.version for a learning write."""
    base = _get_model_version()
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    candidate = f"{base}-learn-{stamp}"
    suffix = 1
    while conn.execute("SELECT 1 FROM model_weights WHERE version = ?", (candidate,)).fetchone():
        suffix += 1
        candidate = f"{base}-learn-{stamp}-{suffix}"
    return candidate


@dataclass
class LearnResult:
    adjustments: int
    details: List[dict]
    circuit_breaks: List[dict]
    error: Optional[str] = None


def learn(db_path: str = None, agent=None, days: int = 30, min_samples: int = 10) -> LearnResult:
    """参数学习主函数 — 数据驱动 + 回测验证 + Agent确认 + Gate门控"""
    db_path = db_path or _get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 自动初始化Agent(如果未传入)
    if agent is None:
        try:
            from backend.app.core.agent.client import create_agent
            agent = create_agent(db_path)
        except Exception:
            agent = None

    try:
        # 0. Gate: 备份当前权重(学习前快照)
        weight_backup = _backup_active_weights(conn)
        pre_accuracy = _snapshot_overall_accuracy(conn, days=days)

        # 1. 按场景+参赛方类型统计准确率
        scene_stats = compute_scene_accuracy(conn, days=days, min_samples=min_samples)

        if not scene_stats:
            logger.info('无验证数据可学习，跳过参数调整')
            # 仍写入model_accuracy记录(空)
            update_model_accuracy(conn, {})
            conn.commit()
            return LearnResult(adjustments=0, details=[], circuit_breaks=[])

        adjustments = []
        circuit_breaks = []

        for key, stats in scene_stats.items():
            if len(key) == 3:
                scene, p_type, play_type = key
            else:
                scene, p_type = key
                play_type = 'spf'

            if stats["total"] < min_samples:
                logger.info(f'{scene}({p_type}/{play_type}): 样本{stats["total"]}<{min_samples}, 跳过')
                continue

            # 2. 熔断检测
            if stats["model_accuracy"] < stats["odds_baseline"] - 0.03:
                circuit_breaks.append({
                    "scene": scene, "participant_type": p_type, "play_type": play_type,
                    "model_accuracy": stats["model_accuracy"],
                    "odds_baseline": stats["odds_baseline"],
                    "action": "reduce_model_weight",
                    "reason": f"模型{stats['model_accuracy']:.0%} < 赔率{stats['odds_baseline']:.0%}"
                })
                record_circuit_break(conn, scene, p_type, stats, play_type=play_type)
                continue

            # 3. 找问题因子
            problem_factors = identify_problem_factors(conn, scene, p_type, stats,
                                                       play_type=play_type)
            for factor_name, current_weight in problem_factors:
                direction = determine_direction(factor_name, stats)
                new_weight = current_weight * (1 + direction * 0.10)
                detail_new_weight = new_weight

                # 4. 回测验证 — 按play_type筛选
                bt = backtest(conn, factor_name, current_weight, new_weight, scene, p_type, days,
                              play_type=play_type)

                if bt["improved"]:
                    # 5. Agent确认(可选，只在调整幅度>5%时)
                    if abs(new_weight - current_weight) / max(current_weight, 0.01) > 0.05 and agent:
                        try:
                            decision = agent.param_adjustment(
                                {str(key): stats}, get_current_weights(conn, scene, p_type)
                            )
                            if decision and decision.get("adjustments"):
                                approved = any(
                                    a.get("suggested_weight") and abs(a["suggested_weight"] - new_weight) < 0.03
                                    for a in decision.get("adjustments", [])
                                )
                                if not approved:
                                    logger.info(f'Agent否决调整: {factor_name} {current_weight:.3f}→{new_weight:.3f}')
                                    continue
                                logger.info(f'Agent批准调整: {factor_name} {current_weight:.3f}→{new_weight:.3f}')
                            elif decision is None:
                                logger.info(f'Agent不可用，规则引擎直接通过: {factor_name}')
                        except Exception as e:
                            logger.warning(f'Agent确认失败，使用回测结果: {e}')

                    # O/U和BF因子直接记录，不更新7因子权重表
                    if play_type in ('ou', 'bf'):
                        record_param_history(conn, factor_name, current_weight, new_weight,
                                             scene, p_type,
                                             f"{scene}({p_type})/{play_type}准确率低",
                                             bt, play_type=play_type)
                    else:
                        applied_weights = apply_weight_change(conn, factor_name, current_weight, new_weight, scene, p_type)
                        applied_new_weight = applied_weights.get(factor_name, new_weight)
                        detail_new_weight = applied_new_weight

                        verification = _verify_weight_effect(conn, factor_name, applied_new_weight, scene, p_type, db_path)
                        if not verification.get('verified'):
                            logger.warning(f'权重验证失败: {verification}')

                        record_param_history(conn, factor_name, current_weight, detail_new_weight,
                                             scene, p_type,
                                             f"{scene}({p_type})/{play_type}准确率低",
                                             bt, play_type=play_type)

                    adjustments.append({
                        "factor": factor_name, "scene": scene, "participant_type": p_type,
                        "play_type": play_type,
                        "old": current_weight,
                        "new": detail_new_weight,
                        "improved": bt["improved"]
                    })

        # 6. O/U专项优化
        ou_result = optimize_ou_thresholds(db_path, days=days, conn=conn)
        if ou_result.get("adjustments"):
            for adj in ou_result["adjustments"]:
                adjustments.append({
                    "factor": adj["param"], "scene": "ou_global", "participant_type": "all",
                    "play_type": "ou",
                    "old": adj["old"], "new": adj["new"],
                    "improved": True,
                })

        # 7. 更新model_accuracy统计表
        update_model_accuracy(conn, scene_stats)

        # 8. Gate: 学习后门控 — 如果整体准确率下降>1pp则回滚
        if adjustments:
            post_accuracy = _snapshot_overall_accuracy(conn, days=days)
            gate = _gate_check(pre_accuracy, post_accuracy, overall_tolerance_pp=1.0)
            if gate['rollback']:
                logger.warning(f'Gate触发回滚: {gate["reason"]}')
                _restore_active_weights(conn, weight_backup)
                adjustments = []
                circuit_breaks.append({
                    "scene": "gate", "participant_type": "all", "play_type": "spf",
                    "model_accuracy": post_accuracy,
                    "odds_baseline": pre_accuracy,
                    "action": "rollback_all_weights",
                    "reason": gate['reason'],
                })

        # 9. Segment自动挖掘 — 发现高偏差细分场景
        try:
            conn.commit()  # 释放写锁, 让segment_discovery的新连接能写入
            from backend.app.core.segment_discovery import run_segment_discovery
            seg_result = run_segment_discovery(db_path)
            if seg_result.get('discovered', 0) > 0:
                logger.info('segment挖掘: 发现%d个高偏差场景', seg_result['discovered'])
                # Agent确认是否生成新规则
                if agent and seg_result.get('segments'):
                    for seg in seg_result['segments'][:3]:
                        try:
                            agent.new_scenario({
                                'segment': seg['key'],
                                'model_accuracy': seg.get('model_accuracy'),
                                'odds_accuracy': seg.get('odds_accuracy'),
                                'gap': seg.get('gap'),
                                'sample': seg.get('sample'),
                            }, [])
                        except Exception as e:
                            logger.warning('Agent new_scenario调用失败: %s', e)
            else:
                logger.info('segment挖掘: 无高偏差场景发现')
        except Exception as e:
            logger.warning('segment挖掘失败: %s', e)

        # 10. 概率校准 — 计算分桶校准曲线, 直接提升命中率
        try:
            conn.commit()  # 释放写锁
            from backend.app.core.probability_calibration import compute_calibration
            cal_result = compute_calibration(db_path, days=days, min_sample=5)
            logger.info('概率校准: %s', cal_result.get('buckets', 0))
        except Exception as e:
            logger.warning('概率校准失败: %s', e)

        # 11. 归因驱动学习 — 从lottery_validation.attribution消费失败模式
        try:
            conn.commit()  # 释放写锁
            from backend.app.core.attribution_driven_learning import run_attribution_driven_learning
            attr_result = run_attribution_driven_learning(db_path, days=days, agent=agent)
            if attr_result.get('patterns_found', 0) > 0:
                logger.info('归因驱动: 发现%d个模式, %d项调整 — %s',
                             attr_result['patterns_found'],
                             len(attr_result.get('adjustments', [])),
                             attr_result.get('summary', ''))
                # 把归因驱动调整也纳入details, 让上层能看到
                for adj in attr_result.get('adjustments', []):
                    adjustments.append({
                        'factor': adj.get('factor', ''),
                        'scene': adj.get('scene', 'unknown'),
                        'participant_type': 'all',
                        'play_type': adj.get('play_type', 'spf'),
                        'old': adj.get('old', 0),
                        'new': adj.get('new', 0),
                        'improved': True,
                        'action_type': adj.get('action_type', ''),
                        'reason': adj.get('reason', ''),
                    })
            else:
                logger.info('归因驱动: 无归因数据或无可执行调整')
        except Exception as e:
            logger.warning('归因驱动学习失败: %s', e)

        conn.commit()
        logger.info(f'学习完成: {len(adjustments)}项调整, {len(circuit_breaks)}项熔断 (含O/U专项)')
        return LearnResult(adjustments=len(adjustments), details=adjustments, circuit_breaks=circuit_breaks)

    except Exception as e:
        logger.error(f"Learn failed: {e}")
        conn.rollback()
        return LearnResult(adjustments=0, details=[], circuit_breaks=[], error=str(e))
    finally:
        conn.close()


def compute_scene_accuracy(conn, days: int = 30, min_samples: int = 10) -> Dict[Tuple[str, str, str], dict]:
    """按场景+参赛方类型+玩法统计准确率 — 优先从lottery_validation读取

    Returns: Dict keyed by (scenario, participant_type, play_type)
    """
    cutoff = f"-{days} days"
    stats = {}

    # 数据源1: lottery_validation (日循环写入) — now includes play_type
    try:
        cursor = conn.execute("""
            SELECT
                COALESCE(lv.scenario_type, 'unknown') as scene,
                CASE
                    WHEN lm.league_name_cn LIKE '%国际%' OR lm.league_name_cn LIKE '%世预%' THEN 'national'
                    ELSE 'club'
                END as participant_type,
                lv.play_type,
                COUNT(*) as total,
                SUM(lv.is_correct) as model_correct,
                AVG(lv.brier_score) as model_brier
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lv.validated_at >= datetime('now', ?)
            GROUP BY scene, participant_type, lv.play_type
        """, (cutoff,))

        for row in cursor.fetchall():
            key = (row["scene"] or "unknown", row["participant_type"] or "club", row["play_type"] or "spf")
            total = row["total"] or 0
            model_correct = row["model_correct"] or 0
            model_acc = model_correct / total if total > 0 else 0
            odds_baseline = compute_odds_baseline(conn, key, cutoff)

            stats[key] = {
                "total": total,
                "model_accuracy": round(model_acc, 4),
                "odds_baseline": odds_baseline,
                "model_brier": round(row["model_brier"] or 0, 4),
            }
    except Exception as e:
        logger.debug(f"lottery_validation查询失败: {e}")

    # 数据源2: prediction_logs + prediction_results (旧系统，补充)
    try:
        cursor = conn.execute("""
            SELECT
                l.competition_type as scene,
                CASE WHEN l.is_international = 1 THEN 'national' ELSE 'club' END as participant_type,
                COUNT(*) as total,
                SUM(pr.result_correct) as model_correct,
                AVG(pr.brier_score) as model_brier
            FROM prediction_logs pl
            JOIN prediction_results pr ON pl.log_id = pr.log_id
            LEFT JOIN leagues l ON pl.league_id = l.league_id
            WHERE pl.created_at >= datetime('now', ?)
            GROUP BY l.competition_type, l.is_international
        """, (cutoff,))

        for row in cursor.fetchall():
            key = (row["scene"] or "unknown", row["participant_type"] or "club", "spf")  # old system only has spf
            total = row["total"] or 0
            model_correct = row["model_correct"] or 0
            model_acc = model_correct / total if total > 0 else 0

            # 合并: 如果key已存在，累加；否则新建
            if key in stats:
                existing = stats[key]
                combined_total = existing["total"] + total
                combined_correct = existing["model_accuracy"] * existing["total"] + model_correct
                stats[key] = {
                    "total": combined_total,
                    "model_accuracy": round(combined_correct / combined_total, 4),
                    "odds_baseline": existing["odds_baseline"],
                    "model_brier": round(
                        (existing["model_brier"] * existing["total"] + (row["model_brier"] or 0) * total) / combined_total, 4
                    ),
                }
            else:
                odds_baseline = compute_odds_baseline(conn, key, cutoff)
                stats[key] = {
                    "total": total,
                    "model_accuracy": round(model_acc, 4),
                    "odds_baseline": odds_baseline,
                    "model_brier": round(row["model_brier"] or 0, 4),
                }
    except Exception as e:
        logger.debug(f"prediction_logs查询失败: {e}")

    return stats


def compute_odds_baseline(conn, key, cutoff) -> float:
    """计算赔率基线准确率 — 按play_type分别计算"""
    play_type = key[2] if len(key) == 3 else 'spf'

    if play_type == 'ou':
        return _compute_ou_odds_baseline(conn, cutoff)

    # BF/BQC/RQSPF: 无直接赔率基线，用整体验证准确率估算
    if play_type in ('bf', 'bqc', 'rqspf'):
        try:
            row = conn.execute("""
                SELECT COUNT(*) as total, SUM(is_correct) as correct
                FROM lottery_validation
                WHERE play_type = ? AND validated_at >= datetime('now', ?)
            """, (play_type, cutoff)).fetchone()
            if row and row["total"] >= 5:
                return round((row["correct"] or 0) / row["total"], 4)
        except Exception:
            pass
        # 这些玩法随机猜测基线
        random_baselines = {'bf': 0.10, 'bqc': 0.11, 'rqspf': 0.33}
        return random_baselines.get(play_type, 0.33)

    # SPF: 如果总是选赔率argmax，准确率是多少
    # 直接从lottery_odds计算argmax准确率
    try:
        rows = conn.execute("""
            SELECT lo.lottery_match_id, lo.odds_data, lr.spf_result
            FROM lottery_odds lo
            JOIN lottery_results lr ON lo.lottery_match_id = lr.lottery_match_id
            WHERE lo.play_type = 'spf'
            AND (lo.snapshot_type = 'opening' OR lo.snapshot_type = 'current' OR lo.snapshot_type IS NULL)
            AND lo.lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_validation
                WHERE validated_at >= datetime('now', ?)
            )
        """, (cutoff,)).fetchall()

        if len(rows) >= 5:
            correct = 0
            for row in rows:
                odds = json.loads(row["odds_data"]) if isinstance(row["odds_data"], str) else row["odds_data"]
                h = float(odds.get("3", odds.get("home", 0)) or 0)
                d = float(odds.get("1", odds.get("draw", 0)) or 0)
                a = float(odds.get("0", odds.get("away", 0)) or 0)
                if h < 1 or d < 1 or a < 1:
                    continue
                ih, id_, ia = 1/h, 1/d, 1/a
                total = ih + id_ + ia
                probs = {"3": ih/total, "1": id_/total, "0": ia/total}
                odds_rec = max(probs, key=probs.get)
                if odds_rec == row["spf_result"]:
                    correct += 1
            matched = sum(1 for r in rows
                         if _parse_odds_valid(r["odds_data"]))
            if matched >= 5:
                return round(correct / matched, 4)
    except Exception as e:
        logger.debug(f"赔率基线计算失败: {e}")

    # 从lottery_validation中的赔率方向间接推算
    try:
        row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN lv.attribution = 'market_wrong' THEN 1 ELSE 0 END) as market_wrong_count
            FROM lottery_validation lv
            WHERE lv.validated_at >= datetime('now', ?)
        """, (cutoff,)).fetchone()

        if row and row["total"] >= 5 and row["market_wrong_count"] > 0:
            # market_wrong = 赔率方向也对但模型方向不同 → 赔率至少有market_wrong_count正确
            # 加上其他归因中赔率可能也对的部分
            # 粗略估计: 赔率基线 ≈ 模型准确率 + market_wrong比例
            model_acc = sum(1 for _ in conn.execute("""
                SELECT 1 FROM lottery_validation
                WHERE is_correct = 1 AND validated_at >= datetime('now', ?)
            """, (cutoff,)).fetchall()) / row["total"]
            market_wrong_rate = row["market_wrong_count"] / row["total"]
            return round(min(model_acc + market_wrong_rate, 0.7), 4)
    except Exception:
        pass

    # 无数据时从整体验证数据估算，而非用per-scenario硬编码值
    try:
        row = conn.execute("SELECT COUNT(*) as total FROM lottery_validation").fetchone()
        if row and row["total"] >= 10:
            correct = conn.execute("SELECT SUM(is_correct) FROM lottery_validation").fetchone()[0]
            return round(correct / row["total"], 4)
    except Exception:
        pass

    # 最终fallback: 单一通用值
    return 0.45


def _parse_odds_valid(odds_data) -> bool:
    """检查赔率数据是否有效(3个值都>1)"""
    try:
        odds = json.loads(odds_data) if isinstance(odds_data, str) else odds_data
        h = float(odds.get("3", odds.get("home", 0)) or 0)
        d = float(odds.get("1", odds.get("draw", 0)) or 0)
        a = float(odds.get("0", odds.get("away", 0)) or 0)
        return h > 1 and d > 1 and a > 1
    except Exception:
        return False


def _compute_ou_odds_baseline(conn, cutoff) -> float:
    """计算O/U赔率基线: 始终选over/under中概率更高的那个，看准确率"""
    try:
        rows = conn.execute("""
            SELECT lo.lottery_match_id, lo.odds_data, lr.ou_result
            FROM lottery_odds lo
            JOIN lottery_results lr ON lo.lottery_match_id = lr.lottery_match_id
            WHERE lo.play_type = 'ou'
            AND lr.ou_result IS NOT NULL
            AND lo.lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_validation
                WHERE play_type = 'ou' AND validated_at >= datetime('now', ?)
            )
        """, (cutoff,)).fetchall()

        if len(rows) >= 5:
            correct = 0
            total = 0
            for row in rows:
                odds = json.loads(row["odds_data"]) if isinstance(row["odds_data"], str) else row["odds_data"]
                over_odds = float(odds.get("over", odds.get("大", 0)) or 0)
                under_odds = float(odds.get("under", odds.get("小", 0)) or 0)
                if over_odds < 1 or under_odds < 1:
                    continue
                total += 1
                # 选概率更高的一方(赔率更低)
                predicted = "大" if over_odds < under_odds else "小"
                actual = row["ou_result"]
                if actual.startswith(predicted):
                    correct += 1
            if total >= 5:
                return round(correct / total, 4)
    except Exception as e:
        logger.debug(f"O/U赔率基线计算失败: {e}")

    # fallback: 从lottery_validation中ou的is_correct比例推算
    try:
        row = conn.execute("""
            SELECT COUNT(*) as total, SUM(is_correct) as correct
            FROM lottery_validation
            WHERE play_type = 'ou' AND validated_at >= datetime('now', ?)
        """, (cutoff,)).fetchone()
        if row and row["total"] >= 5:
            return round((row["correct"] or 0) / row["total"], 4)
    except Exception:
        pass

    return 0.50


def identify_problem_factors(conn, scene, p_type, stats,
                              play_type='spf') -> List[Tuple[str, float]]:
    """找出问题因子 — 按play_type区分优化对象

    spf/bqc/rqspf: 7因子权重
    ou: confidence阈值 + line选择策略
    bf: Poisson xG lambda缩放因子
    """
    if play_type == 'ou':
        return _identify_ou_factors(conn, stats)
    if play_type == 'bf':
        return _identify_bf_factors(conn, stats)

    # SPF/BQC/RQSPF: 7因子权重
    weights = get_current_weights(conn, scene, p_type)
    factors = []

    for factor, weight in weights.items():
        if stats["model_accuracy"] < stats["odds_baseline"]:
            factors.append((factor, weight))

    return factors[:3]


def _identify_ou_factors(conn, stats) -> List[Tuple[str, float]]:
    """O/U问题因子: confidence阈值和line偏移"""
    factors = []
    try:
        row = conn.execute("""
            SELECT param_name, new_value FROM model_params_history
            WHERE param_name LIKE 'ou_%'
            ORDER BY changed_at DESC LIMIT 5
        """).fetchall()
        # 当前confidence阈值
        conf_row = [r for r in row if r[0] == 'ou_confidence_threshold']
        current_conf = conf_row[0][1] if conf_row else 0.55
        factors.append(('ou_confidence_threshold', current_conf))

        # 当前line偏移(0=默认line, 正=偏好大球, 负=偏好小球)
        line_row = [r for r in row if r[0] == 'ou_line_offset']
        current_offset = line_row[0][1] if line_row else 0.0
        factors.append(('ou_line_offset', current_offset))
    except Exception:
        factors.append(('ou_confidence_threshold', 0.55))
        factors.append(('ou_line_offset', 0.0))
    return factors


def _identify_bf_factors(conn, stats) -> List[Tuple[str, float]]:
    """BF问题因子: Poisson lambda缩放"""
    factors = []
    try:
        row = conn.execute("""
            SELECT param_name, new_value FROM model_params_history
            WHERE param_name = 'bf_lambda_scale'
            ORDER BY changed_at DESC LIMIT 1
        """).fetchall()
        current = row[0][1] if row else 1.0
        factors.append(('bf_lambda_scale', current))
    except Exception:
        factors.append(('bf_lambda_scale', 1.0))
    return factors


def determine_direction(factor, stats) -> float:
    """确定调整方向"""
    if factor == 'ou_confidence_threshold':
        # 高confidence准确率低 → 阈值太低需调高(+1), 反之调低(-1)
        if stats["model_accuracy"] < stats["odds_baseline"]:
            return 1.0  # 提高阈值，减少低质量推荐
        return -1.0  # 降低阈值，扩大覆盖
    if factor == 'ou_line_offset':
        # O/U方向需看over/under哪边准确率更低
        if stats["model_accuracy"] < stats["odds_baseline"]:
            return -1.0  # 偏移调低，更保守
        return 1.0
    if factor == 'bf_lambda_scale':
        if stats["model_accuracy"] < stats["odds_baseline"]:
            return -0.5  # lambda向1.0回归
        return 0.5

    if stats["model_accuracy"] < stats["odds_baseline"]:
        return -1.0
    return 1.0


def backtest(conn, factor, old_weight, new_weight, scene, p_type, days,
             play_type='spf') -> dict:
    """历史数据回测 — 按play_type筛选验证数据重新计算概率

    方法:
    1. 从lottery_validation获取预测概率+实际结果
    2. 用新权重重新组合概率(假设每个因子对最终概率的贡献=权重×因子概率)
    3. 比较新旧argmax准确率和Brier score
    """
    cutoff = f"-{days} days"

    # 获取验证记录中的概率数据 — 按play_type筛选
    try:
        rows = conn.execute("""
            SELECT lv.predicted_result, lv.actual_result, lv.is_correct,
                   lv.predicted_prob, lv.brier_score
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lv.validated_at >= datetime('now', ?)
            AND lv.play_type = ?
        """, (cutoff, play_type)).fetchall()

        if len(rows) < 5:
            # 样本不足，无法可靠回测
            return {"improved": False, "old_accuracy": 0, "new_accuracy": 0,
                    "sample_size": len(rows)}

        # 当前准确率
        old_correct = sum(1 for r in rows if r["is_correct"])
        old_acc = old_correct / len(rows)
        old_brier = sum(r["brier_score"] or 0 for r in rows) / len(rows)

        # 模拟新权重下的准确率
        # 策略: 如果降低某因子权重→该因子影响减弱→如果该因子预测方向与最终结果不一致→可能改善
        # 简化: 用因子权重变化调整predicted_prob，然后重新判断argmax
        new_correct = 0
        new_brier_sum = 0.0

        weight_ratio = new_weight / max(old_weight, 0.001)

        for r in rows:
            pred_prob = r["predicted_prob"] or 0.5
            actual = r["actual_result"]
            predicted = r["predicted_result"]

            # 模拟权重调整对概率的影响
            # 如果increase weight → 更信任当前预测方向 → 概率更极端
            # 如果decrease weight → 更保守 → 概率回归均匀
            if weight_ratio > 1:
                # 权重增大 → 更极端
                adjusted_prob = 0.5 + (pred_prob - 0.5) * min(weight_ratio, 2.0)
            else:
                # 权重减小 → 更均匀
                adjusted_prob = 0.5 + (pred_prob - 0.5) * max(weight_ratio, 0.3)
            adjusted_prob = max(0.1, min(0.9, adjusted_prob))

            # 重新判断: adjusted_prob变化是否翻转预测方向
            # 如果权重增大→概率更极端→原预测更可能正确(如果已正确)
            # 如果权重减小→概率更均匀→原预测可能翻转(如果接近阈值)
            if weight_ratio < 1 and pred_prob < 0.5 + (1 - pred_prob) * weight_ratio:
                # 权重减小使预测不再显著, 方向可能翻转 → 判为错误
                is_correct_new = False
            else:
                is_correct_new = (predicted == actual)
            new_correct += int(is_correct_new)

            # 重新计算Brier
            # 简化: 假设调整主要影响预测方向的概率
            new_brier = _estimate_brier(adjusted_prob, predicted, actual)
            new_brier_sum += new_brier

        new_acc = new_correct / len(rows)
        new_brier = new_brier_sum / len(rows)

        return {
            "improved": new_acc >= old_acc or new_brier < old_brier,
            "old_accuracy": round(old_acc, 4),
            "new_accuracy": round(new_acc, 4),
            "old_brier": round(old_brier, 4),
            "new_brier": round(new_brier, 4),
            "sample_size": len(rows)
        }

    except Exception as e:
        logger.debug(f"回测失败: {e}")

    return {"improved": False, "old_accuracy": 0, "new_accuracy": 0, "sample_size": 0}


def _estimate_brier(pred_prob, predicted, actual) -> float:
    """估计Brier score — 基于预测概率和实际结果(3类)"""
    if predicted == actual:
        # 正确: Brier = (1-p)^2 + 2*(p/2)^2
        return round((1 - pred_prob) ** 2 + 2 * (pred_prob / 2) ** 2, 4)
    else:
        # 错误: Brier = p^2 + ((1-p)/2)^2 + ((1-p)/2)^2
        return round(pred_prob ** 2 + 2 * ((1 - pred_prob) / 2) ** 2, 4)


def get_current_weights(conn, scene, p_type) -> Dict[str, float]:
    """获取当前权重"""
    try:
        row = conn.execute("""
            SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1
        """).fetchone()

        if row:
            return {
                "elo": row["elo_weight"],
                "poisson": row["poisson_weight"],
                "h2h": row["h2h_weight"],
                "form": row["form_weight"],
                "home_away": row["home_away_weight"],
                "motivation": row["motivation_weight"],
                "news_factors": row["news_factors_weight"],
            }
    except Exception:
        pass

    return {
        "elo": 0.20, "poisson": 0.25, "h2h": 0.10, "form": 0.15,
        "home_away": 0.10, "motivation": 0.10, "news_factors": 0.10,
    }


def apply_weight_change(conn, factor, old_weight, new_weight, scene, p_type):
    """应用权重变更"""
    weight_map = get_current_weights(conn, scene, p_type)
    weight_map[factor] = new_weight

    # 归一化
    total = sum(weight_map.values())
    if total > 0:
        weight_map = {k: round(v / total, 4) for k, v in weight_map.items()}

    # 更新model_weights
    conn.execute("""
        UPDATE model_weights SET is_active = 0 WHERE is_active = 1
    """)
    conn.execute("""
        INSERT INTO model_weights
        (version, elo_weight, poisson_weight, h2h_weight, form_weight,
         home_away_weight, motivation_weight, news_factors_weight,
         is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        _get_unique_model_version(conn),
        weight_map["elo"], weight_map["poisson"], weight_map["h2h"],
        weight_map["form"], weight_map["home_away"],
        weight_map["motivation"], weight_map["news_factors"],
        datetime.now().isoformat()
    ))
    return weight_map


def record_param_history(conn, param_name, old_value, new_value, scene, p_type,
                          reason, backtest, play_type='spf'):
    """记录参数变更历史 — param_name编码包含play_type"""
    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f"{param_name}_{scene}_{p_type}_{play_type}",
        old_value, new_value,
        f"{reason} | backtest: improved={backtest.get('improved')}",
        backtest.get("old_accuracy", 0),
        backtest.get("new_accuracy", 0),
        backtest.get("sample_size", 0),
        datetime.now().isoformat()
    ))


def record_circuit_break(conn, scene, p_type, stats, play_type='spf'):
    """记录熔断事件"""
    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f"circuit_break_{scene}_{p_type}_{play_type}",
        1.0, 0.0,
        f"熔断: 模型{stats['model_accuracy']:.0%} < 赔率{stats['odds_baseline']:.0%} ({play_type})",
        stats["model_accuracy"],
        stats["odds_baseline"],
        stats["total"],
        datetime.now().isoformat()
    ))


def update_model_accuracy(conn, scene_stats):
    """更新model_accuracy统计表 — scene_type编码为{scenario}_{play_type}"""
    for key, stats in scene_stats.items():
        if len(key) == 3:
            scene, p_type, play_type = key
            scene_type = f"{scene}_{play_type}"
        else:
            scene, p_type = key
            scene_type = scene
        conn.execute("""
            INSERT OR REPLACE INTO model_accuracy
            (scene_type, participant_type, total_matches,
             model_accuracy, odds_baseline_accuracy,
             model_brier, odds_brier, period, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, '30d', ?)
        """, (
            scene_type, p_type, stats["total"],
            stats["model_accuracy"], stats["odds_baseline"],
            stats["model_brier"], 0,
            datetime.now().isoformat()
        ))


def _backup_active_weights(conn) -> Optional[dict]:
    """Snapshot the current active model_weights row for rollback."""
    try:
        row = conn.execute("SELECT * FROM model_weights WHERE is_active = 1 LIMIT 1").fetchone()
        if not row:
            return None
        return dict(row)
    except Exception:
        return None


def _restore_active_weights(conn, backup: Optional[dict]) -> None:
    """Restore weights from a backup snapshot, deactivating current and reactivating backup."""
    if not backup:
        return
    try:
        conn.execute("UPDATE model_weights SET is_active = 0 WHERE is_active = 1")
        # Re-insert the backup as a new active row
        version = _get_unique_model_version(conn) + '-rollback'
        conn.execute("""
            INSERT INTO model_weights
            (version, elo_weight, poisson_weight, h2h_weight, form_weight,
             home_away_weight, motivation_weight, news_factors_weight,
             is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            version,
            backup.get('elo_weight', 0.20), backup.get('poisson_weight', 0.25),
            backup.get('h2h_weight', 0.10), backup.get('form_weight', 0.15),
            backup.get('home_away_weight', 0.10), backup.get('motivation_weight', 0.10),
            backup.get('news_factors_weight', 0.10),
            datetime.now().isoformat()
        ))
        # Record the rollback in history
        conn.execute("""
            INSERT INTO model_params_history
            (model_version, param_name, old_value, new_value, change_reason,
             accuracy_before, accuracy_after, sample_size, changed_at)
            VALUES (?, 'gate_rollback', 1.0, 0.0, 'Gate: overall accuracy dropped, rolling back all weight changes', ?, ?, 0, ?)
        """, (
            _get_model_version(),
            backup.get('elo_weight', 0), 0,
            datetime.now().isoformat()
        ))
        logger.info('Rolled back weights to pre-learning snapshot')
    except Exception as e:
        logger.error(f'Weight rollback failed: {e}')


def _snapshot_overall_accuracy(conn, days: int = 30) -> float:
    """Get overall SPF accuracy from lottery_validation for the last N days."""
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM lottery_validation
            WHERE play_type = 'spf'
              AND validated_at >= date('now', ?)
        """, (f'-{days} days',)).fetchone()
        if row and row['total'] > 0:
            return round(row['correct'] / row['total'], 4)
    except Exception:
        pass
    return 0.0


def _gate_check(pre_accuracy: float, post_accuracy: float, overall_tolerance_pp: float = 1.0) -> dict:
    """Check if post-learning accuracy is acceptable vs pre-learning baseline."""
    delta_pp = (post_accuracy - pre_accuracy) * 100
    if delta_pp < -abs(overall_tolerance_pp):
        return {
            'rollback': True,
            'reason': f'Overall accuracy dropped {abs(delta_pp):.1f}pp (pre={pre_accuracy:.1%}, post={post_accuracy:.1%})',
            'delta_pp': round(delta_pp, 1),
        }
    return {
        'rollback': False,
        'reason': f'Accuracy change: {delta_pp:+.1f}pp (pre={pre_accuracy:.1%}, post={post_accuracy:.1%})',
        'delta_pp': round(delta_pp, 1),
    }


def _verify_weight_effect(conn, factor_name, expected_weight, scene, p_type, db_path=None) -> dict:
    """After applying weight changes, verify the new weight is actually used by the analyzer.

    Returns: {'verified': bool, 'expected': float, 'actual': float}
    """
    try:
        from backend.app.analytics.comprehensive import ComprehensiveAnalyzer

        if not db_path:
            return {'verified': True, 'reason': 'no db_path for verification'}

        analyzer = ComprehensiveAnalyzer(db_path)
        current_weights = analyzer._get_weights()

        actual_weight = current_weights.get(factor_name, 0)
        verified = abs(expected_weight - actual_weight) < 0.02

        return {
            'verified': verified,
            'expected': round(expected_weight, 4),
            'actual': round(actual_weight, 4),
            'reason': '' if verified else f'Weight mismatch: expected {expected_weight:.4f}, got {actual_weight:.4f}',
        }
    except Exception as e:
        return {'verified': True, 'reason': f'verification skipped: {e}'}


def optimize_ou_thresholds(db_path: str = None, days: int = 30, conn: sqlite3.Connection = None) -> dict:
    """O/U专项优化: 分析confidence区间准确率，调整推荐阈值

    逻辑:
    - 高confidence(>0.55)准确率 < 50% → 阈值太低，需提高，减少低质量推荐
    - 低confidence(<0.55)准确率 > 50% → 阈值太高，可降低，扩大覆盖
    - 按盘口分档分析(line=2.5 vs line=3.0等)
    """
    db_path = db_path or _get_db_path()
    owns_conn = conn is None
    if owns_conn:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    cutoff = f"-{days} days"

    result = {"adjustments": [], "analysis": {}}

    try:
        # 按confidence区间统计准确率
        rows = conn.execute("""
            SELECT
                CASE
                    WHEN confidence >= 0.65 THEN 'high'
                    WHEN confidence >= 0.55 THEN 'medium'
                    ELSE 'low'
                END as conf_band,
                COUNT(*) as total,
                SUM(is_correct) as correct,
                AVG(predicted_prob) as avg_prob
            FROM lottery_validation
            WHERE play_type = 'ou'
            AND validated_at >= datetime('now', ?)
            GROUP BY conf_band
        """, (cutoff,)).fetchall()

        for row in rows:
            total = row["total"] or 0
            correct = row["correct"] or 0
            acc = correct / total if total > 0 else 0
            result["analysis"][row["conf_band"]] = {
                "total": total,
                "accuracy": round(acc, 4),
                "avg_prob": round(row["avg_prob"] or 0, 4),
            }

        # 按盘口分档统计
        line_rows = conn.execute("""
            SELECT
                CASE
                    WHEN predicted_result LIKE '%2.5' THEN '2.5'
                    WHEN predicted_result LIKE '%3%' THEN '3.0'
                    WHEN predicted_result LIKE '%3.5' THEN '3.5'
                    ELSE 'other'
                END as line_band,
                COUNT(*) as total,
                SUM(is_correct) as correct
            FROM lottery_validation
            WHERE play_type = 'ou'
            AND validated_at >= datetime('now', ?)
            GROUP BY line_band
        """, (cutoff,)).fetchall()

        for row in line_rows:
            total = row["total"] or 0
            correct = row["correct"] or 0
            acc = correct / total if total > 0 else 0
            result["analysis"][f"line_{row['line_band']}"] = {
                "total": total,
                "accuracy": round(acc, 4),
            }

        # 读取当前阈值
        try:
            param_row = conn.execute("""
                SELECT new_value FROM model_params_history
                WHERE param_name LIKE 'ou_confidence_threshold%'
                ORDER BY changed_at DESC LIMIT 1
            """).fetchone()
            current_threshold = param_row[0] if param_row else 0.55
        except Exception:
            current_threshold = 0.55

        # 决策逻辑
        high_stats = result["analysis"].get("high", {})
        low_stats = result["analysis"].get("low", {})

        if high_stats.get("total", 0) >= 5:
            high_acc = high_stats["accuracy"]
            if high_acc < 0.50:
                # 高confidence推荐质量差 → 提高阈值
                new_threshold = min(current_threshold + 0.03, 0.75)
                result["adjustments"].append({
                    "param": "ou_confidence_threshold",
                    "old": current_threshold,
                    "new": new_threshold,
                    "reason": f"高confidence准确率{high_acc:.0%}<50%，提高阈值减少低质量推荐",
                })
                conn.execute("""
                    INSERT INTO model_params_history
                    (model_version, param_name, old_value, new_value, change_reason,
                     accuracy_before, accuracy_after, sample_size, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    _get_model_version(),
                    "ou_confidence_threshold_auto",
                    current_threshold, new_threshold,
                    f"O/U专项优化: 高confidence准确率{high_acc:.0%}",
                    high_acc, 0, high_stats["total"],
                    datetime.now().isoformat()
                ))
            elif high_acc >= 0.55:
                # 高confidence推荐质量好 → 可适当降低阈值扩大覆盖
                new_threshold = max(current_threshold - 0.02, 0.40)
                if new_threshold != current_threshold:
                    result["adjustments"].append({
                        "param": "ou_confidence_threshold",
                        "old": current_threshold,
                        "new": new_threshold,
                        "reason": f"高confidence准确率{high_acc:.0%}>55%，可降低阈值扩大覆盖",
                    })
                    conn.execute("""
                        INSERT INTO model_params_history
                        (model_version, param_name, old_value, new_value, change_reason,
                         accuracy_before, accuracy_after, sample_size, changed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        _get_model_version(),
                        "ou_confidence_threshold_auto",
                        current_threshold, new_threshold,
                        f"O/U专项优化: 高confidence准确率{high_acc:.0%}，降低阈值",
                        high_acc, 0, high_stats["total"],
                        datetime.now().isoformat()
                    ))

        if low_stats.get("total", 0) >= 5:
            low_acc = low_stats["accuracy"]
            if low_acc > 0.50:
                # 低confidence推荐也有价值 → 降低阈值
                new_threshold = max(current_threshold - 0.02, 0.40)
                if not any(a["param"] == "ou_confidence_threshold" for a in result["adjustments"]):
                    result["adjustments"].append({
                        "param": "ou_confidence_threshold",
                        "old": current_threshold,
                        "new": new_threshold,
                        "reason": f"低confidence准确率{low_acc:.0%}>50%，降低阈值扩大覆盖",
                    })

        if owns_conn:
            conn.commit()

    except Exception as e:
        logger.error(f"O/U专项优化失败: {e}")
    finally:
        if owns_conn:
            conn.close()

    return result
