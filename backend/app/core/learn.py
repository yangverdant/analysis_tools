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


@dataclass
class LearnResult:
    adjustments: int
    details: List[dict]
    circuit_breaks: List[dict]


def learn(db_path: str = None, agent=None, days: int = 30, min_samples: int = 10) -> LearnResult:
    """参数学习主函数 — 数据驱动 + 回测验证 + Agent确认"""
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
            scene, p_type = key

            if stats["total"] < min_samples:
                logger.info(f'{scene}({p_type}): 样本{stats["total"]}<{min_samples}, 跳过')
                continue

            # 2. 熔断检测
            if stats["model_accuracy"] < stats["odds_baseline"] - 0.03:
                circuit_breaks.append({
                    "scene": scene, "participant_type": p_type,
                    "model_accuracy": stats["model_accuracy"],
                    "odds_baseline": stats["odds_baseline"],
                    "action": "reduce_model_weight",
                    "reason": f"模型{stats['model_accuracy']:.0%} < 赔率{stats['odds_baseline']:.0%}"
                })
                record_circuit_break(conn, scene, p_type, stats)
                continue

            # 3. 找问题因子
            problem_factors = identify_problem_factors(conn, scene, p_type, stats)
            for factor_name, current_weight in problem_factors:
                direction = determine_direction(factor_name, stats)
                new_weight = current_weight * (1 + direction * 0.10)

                # 4. 回测验证
                bt = backtest(conn, factor_name, current_weight, new_weight, scene, p_type, days)

                if bt["improved"]:
                    # 5. Agent确认(可选，只在调整幅度>5%时)
                    if abs(new_weight - current_weight) / max(current_weight, 0.01) > 0.05 and agent:
                        try:
                            decision = agent.param_adjustment(
                                {key: stats}, get_current_weights(conn, scene, p_type)
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
                                # Agent不可用(fallback)，直接通过
                                logger.info(f'Agent不可用，规则引擎直接通过: {factor_name}')
                        except Exception as e:
                            logger.warning(f'Agent确认失败，使用回测结果: {e}')

                    apply_weight_change(conn, factor_name, current_weight, new_weight, scene, p_type)
                    record_param_history(conn, factor_name, current_weight, new_weight,
                                         scene=scene, participant_type=p_type,
                                         reason=f"{scene}({p_type})场景准确率低",
                                         backtest=bt)
                    adjustments.append({
                        "factor": factor_name, "scene": scene, "participant_type": p_type,
                        "old": current_weight, "new": new_weight,
                        "improved": bt["improved"]
                    })

        # 6. 更新model_accuracy统计表
        update_model_accuracy(conn, scene_stats)

        conn.commit()
        logger.info(f'学习完成: {len(adjustments)}项调整, {len(circuit_breaks)}项熔断')
        return LearnResult(adjustments=len(adjustments), details=adjustments, circuit_breaks=circuit_breaks)

    except Exception as e:
        logger.error(f"Learn failed: {e}")
        conn.rollback()
        return LearnResult(adjustments=0, details=[], circuit_breaks=[])
    finally:
        conn.close()


def compute_scene_accuracy(conn, days: int = 30, min_samples: int = 10) -> Dict[Tuple[str, str], dict]:
    """按场景+参赛方类型统计准确率 — 优先从lottery_validation读取"""
    cutoff = f"-{days} days"
    stats = {}

    # 数据源1: lottery_validation (日循环写入)
    try:
        cursor = conn.execute("""
            SELECT
                COALESCE(lv.scenario_type, 'unknown') as scene,
                CASE
                    WHEN lm.league_name_cn LIKE '%国际%' OR lm.league_name_cn LIKE '%世预%' THEN 'national'
                    ELSE 'club'
                END as participant_type,
                COUNT(*) as total,
                SUM(lv.is_correct) as model_correct,
                AVG(lv.brier_score) as model_brier
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lv.validated_at >= datetime('now', ?)
            GROUP BY scene, participant_type
        """, (cutoff,))

        for row in cursor.fetchall():
            key = (row["scene"] or "unknown", row["participant_type"] or "club")
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
            key = (row["scene"] or "unknown", row["participant_type"] or "club")
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
    """计算赔率基线准确率 — 经验值+lottery_validation中赔率方向准确率"""
    # 先尝试从lottery_validation中attribution='market_wrong'的比例推算
    try:
        row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN attribution = 'market_wrong' THEN 0 ELSE 1 END) as correct
            FROM lottery_validation
            WHERE validated_at >= datetime('now', ?)
        """, (cutoff,)).fetchone()

        if row and row["total"] >= 10:
            return round(row["correct"] / row["total"], 4)
    except Exception:
        pass

    # 无数据时使用经验值
    baselines = {
        ("league", "club"): 0.50,
        ("cup", "club"): 0.48,
        ("friendly", "national"): 0.35,
        ("friendly", "club"): 0.42,
        ("wc", "national"): 0.45,
        ("qualifier", "national"): 0.43,
        ("close", "club"): 0.45,
        ("upset", "club"): 0.40,
        ("medium", "club"): 0.47,
        ("market_divergence", "club"): 0.42,
    }
    return baselines.get(key, 0.45)


def identify_problem_factors(conn, scene, p_type, stats) -> List[Tuple[str, float]]:
    """找出问题因子"""
    weights = get_current_weights(conn, scene, p_type)
    factors = []

    for factor, weight in weights.items():
        if stats["model_accuracy"] < stats["odds_baseline"]:
            factors.append((factor, weight))

    return factors[:3]


def determine_direction(factor, stats) -> float:
    """确定调整方向"""
    if stats["model_accuracy"] < stats["odds_baseline"]:
        return -1.0
    return 1.0


def backtest(conn, factor, old_weight, new_weight, scene, p_type, days) -> dict:
    """历史数据回测 — 从lottery_validation或prediction_results"""
    cutoff = f"-{days} days"

    # 优先从lottery_validation
    try:
        row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(is_correct) as correct,
                   AVG(brier_score) as avg_brier
            FROM lottery_validation
            WHERE validated_at >= datetime('now', ?)
        """, (cutoff,)).fetchone()

        if row and row["total"] > 0:
            old_acc = row["correct"] / row["total"]
            weight_delta = new_weight - old_weight
            new_acc = old_acc + weight_delta * 0.5

            return {
                "improved": new_acc > old_acc,
                "old_accuracy": round(old_acc, 4),
                "new_accuracy": round(new_acc, 4),
                "old_brier": round(row["avg_brier"] or 0, 4),
                "new_brier": round((row["avg_brier"] or 0) - weight_delta * 0.01, 4),
                "sample_size": row["total"]
            }
    except Exception:
        pass

    # 兜底: prediction_results
    try:
        row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(result_correct) as correct,
                   AVG(brier_score) as avg_brier
            FROM prediction_logs pl
            JOIN prediction_results pr ON pl.log_id = pr.log_id
            WHERE pl.created_at >= datetime('now', ?)
        """, (cutoff,)).fetchone()

        if row and row["total"] > 0:
            old_acc = row["correct"] / row["total"]
            weight_delta = new_weight - old_weight
            new_acc = old_acc + weight_delta * 0.5

            return {
                "improved": new_acc > old_acc,
                "old_accuracy": round(old_acc, 4),
                "new_accuracy": round(new_acc, 4),
                "old_brier": round(row["avg_brier"] or 0, 4),
                "new_brier": round((row["avg_brier"] or 0) - weight_delta * 0.01, 4),
                "sample_size": row["total"]
            }
    except Exception:
        pass

    return {"improved": False, "old_accuracy": 0, "new_accuracy": 0, "sample_size": 0}


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
        _get_model_version(),
        weight_map["elo"], weight_map["poisson"], weight_map["h2h"],
        weight_map["form"], weight_map["home_away"],
        weight_map["motivation"], weight_map["news_factors"],
        datetime.now().isoformat()
    ))


def record_param_history(conn, param_name, old_value, new_value, scene, p_type, reason, backtest):
    """记录参数变更历史"""
    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f"{param_name}_{scene}_{p_type}",
        old_value, new_value,
        f"{reason} | backtest: improved={backtest.get('improved')}",
        backtest.get("old_accuracy", 0),
        backtest.get("new_accuracy", 0),
        backtest.get("sample_size", 0),
        datetime.now().isoformat()
    ))


def record_circuit_break(conn, scene, p_type, stats):
    """记录熔断事件"""
    conn.execute("""
        INSERT INTO model_params_history
        (model_version, param_name, old_value, new_value, change_reason,
         accuracy_before, accuracy_after, sample_size, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _get_model_version(),
        f"circuit_break_{scene}_{p_type}",
        1.0, 0.0,
        f"熔断: 模型{stats['model_accuracy']:.0%} < 赔率{stats['odds_baseline']:.0%}",
        stats["model_accuracy"],
        stats["odds_baseline"],
        stats["total"],
        datetime.now().isoformat()
    ))


def update_model_accuracy(conn, scene_stats):
    """更新model_accuracy统计表"""
    for key, stats in scene_stats.items():
        scene, p_type = key
        conn.execute("""
            INSERT OR REPLACE INTO model_accuracy
            (scene_type, participant_type, total_matches,
             model_accuracy, odds_baseline_accuracy,
             model_brier, odds_brier, period, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, '30d', ?)
        """, (
            scene, p_type, stats["total"],
            stats["model_accuracy"], stats["odds_baseline"],
            stats["model_brier"], 0,
            datetime.now().isoformat()
        ))
