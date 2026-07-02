"""推送 — TOP3价值投注 + 自然语言理由

职责:
1. 汇总今日预测
2. TOP3价值投注(按Kelly排序)
3. 自然语言理由
4. 投资回报追踪(bet_records表)
5. 推送渠道: 初期只写日志
"""

import json
import logging
import sqlite3
from datetime import date
from typing import Dict, List

from .time_utils import today_beijing, tomorrow_beijing

logger = logging.getLogger(__name__)


def push(state, db_path: str) -> dict:
    """推送今日推荐 — 北京时间窗口: 今天00:00~明天12:00"""
    today = today_beijing()
    tomorrow = tomorrow_beijing()
    logger.info('=== 推送 (%s ~ %s) ===', today, tomorrow)

    # 止损检查: 近7天亏损>30%则降级
    stop_loss = _check_stop_loss(db_path)
    predictions = _get_today_predictions(db_path, today, tomorrow)

    if not predictions:
        logger.info('今日无预测可推送')
        return {'route': 'normal', 'pushed': 0, 'top3': [], 'stop_loss': stop_loss}

    # 计算Kelly/Edge排序
    value_bets = _rank_value_bets(predictions)

    # 止损模式: 只推TOP1, Kelly减半
    if stop_loss.get('active'):
        value_bets = value_bets[:1]
        for bet in value_bets:
            bet['kelly'] = bet.get('kelly', 0) * 0.5
            bet['stop_loss_reduced'] = True

    # TOP3
    top3 = value_bets[:3]

    # 生成自然语言理由
    for bet in top3:
        bet['reason'] = _generate_reason(bet)

    # 写入bet_records
    _record_bets(db_path, top3)

    # 计算ROI概况
    roi_summary = _compute_roi_summary(db_path)

    # ===== Agent生成自然语言早报 =====
    agent_report_text = ''
    agent_decision = None
    try:
        from .agent.client import AnalystAgent
        agent = AnalystAgent(db_path)

        # 获取昨日翻车归因
        recent_failures = _get_recent_failures(db_path, today)
        # 获取今早模型调整
        recent_changes = _get_recent_model_changes(db_path)
        # Agent早报
        report = agent.daily_report(predictions, top3, recent_failures,
                                     recent_changes, roi_summary)
        if report:
            agent_report_text = report.get('text', '')
            if report.get('fallback'):
                logger.info('Agent早报使用规则化兜底 (%d字)', len(agent_report_text))
            else:
                logger.info('Agent早报LLM生成成功 (%d字)', len(agent_report_text))

        # 止损决策
        if stop_loss.get('active'):
            recent_bets = _get_recent_bets(db_path, days=7)
            decision = agent.stop_loss_advice(roi_summary, stop_loss, recent_bets)
            if decision and not decision.get('fallback'):
                agent_decision = decision
                stop_loss['agent_advice'] = decision.get('text', '')
                stop_loss['recommended_action'] = decision.get('action', 'reduce')
                logger.info('Agent止损决策: %s', decision.get('action'))
    except Exception as e:
        logger.warning('Agent早报生成失败: %s', e)

    # 推送(初期只写日志)
    for i, bet in enumerate(top3, 1):
        logger.info('TOP%d: %s vs %s — %s (赔率%.2f, edge=%.1f%%)',
                    i, bet.get('home'), bet.get('away'),
                    bet.get('reason', ''), bet.get('odds', 0), bet.get('edge', 0) * 100)

    if stop_loss.get('active'):
        logger.warning('止损模式: 近7天ROI %.1f%%, Kelly减半, 只推TOP1', stop_loss.get('roi', 0))

    # 推送到所有渠道
    mode = stop_loss.get('active') and '止损' or 'normal'
    from .push_channels import format_daily_push, push_to_all_channels
    push_content = format_daily_push(today, mode, predictions, top3, stop_loss, roi_summary,
                                     agent_section=agent_report_text)
    push_results = push_to_all_channels(
        f'{today} 分析师日报',
        push_content
    )

    # 写入push_history
    _record_push_history(db_path, today, mode, predictions, top3,
                         stop_loss, roi_summary, agent_report_text, agent_decision,
                         push_results)

    return {
        'route': 'normal',
        'pushed': len(predictions),
        'top3': top3,
        'stop_loss': stop_loss,
        'roi_summary': roi_summary,
        'channels': push_results,
        'agent_report': agent_report_text,
    }


def _get_recent_failures(db_path: str, today: str) -> list:
    """获取昨日翻车归因"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lv.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
                   lv.predicted_result, lv.actual_result,
                   lv.attribution, lv.attribution_detail, lv.actionable
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lv.is_correct = 0
            AND lv.validated_at >= date('now', '-2 days')
            ORDER BY lv.validated_at DESC
            LIMIT 10
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return [{
            'match': f"{r.get('home_team_cn','')} vs {r.get('away_team_cn','')}",
            'home': r.get('home_team_cn', ''),
            'away': r.get('away_team_cn', ''),
            'predicted': r.get('predicted_result', ''),
            'actual': r.get('actual_result', ''),
            'attribution_type': r.get('attribution', ''),
            'actionable': bool(r.get('actionable')),
        } for r in rows]
    except Exception as e:
        logger.debug('获取翻车归因失败: %s', e)
        return []


def _get_recent_model_changes(db_path: str) -> list:
    """获取今早模型参数变更"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT param_name, old_value, new_value, change_reason, changed_at
            FROM model_params_history
            WHERE changed_at >= date('now', '-1 day')
            ORDER BY changed_at DESC
            LIMIT 10
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.debug('获取模型变更失败: %s', e)
        return []


def _get_recent_bets(db_path: str, days: int = 7) -> list:
    """获取近期投注记录"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT br.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
                   br.play_type, br.selection, br.odds, br.stake, br.result, br.profit
            FROM bet_records br
            LEFT JOIN lottery_matches lm ON br.lottery_match_id = lm.lottery_match_id
            WHERE br.created_at >= datetime('now', ?)
            ORDER BY br.created_at DESC
            LIMIT 20
        """, (f'-{days} days',))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return [{
            'match': f"{r.get('home_team_cn','')} vs {r.get('away_team_cn','')}",
            'home': r.get('home_team_cn', ''),
            'away': r.get('away_team_cn', ''),
            'play_type': r.get('play_type', ''),
            'selection': r.get('selection', ''),
            'result': r.get('result', ''),
            'profit': r.get('profit', 0),
        } for r in rows]
    except Exception as e:
        logger.debug('获取近期投注失败: %s', e)
        return []


def _record_push_history(db_path: str, push_date: str, mode: str,
                         predictions: list, top3: list, stop_loss: dict,
                         roi_summary: dict, agent_report: str,
                         agent_decision: dict, channels: dict) -> None:
    """记录推送历史到push_history表"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        # 确保表存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                push_date TEXT NOT NULL,
                mode TEXT,
                predictions_count INTEGER,
                top3_json TEXT,
                stop_loss_json TEXT,
                roi_summary_json TEXT,
                agent_report_text TEXT,
                agent_decision_json TEXT,
                channels_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("""
            INSERT INTO push_history
            (push_date, mode, predictions_count, top3_json, stop_loss_json,
             roi_summary_json, agent_report_text, agent_decision_json, channels_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            push_date, mode, len(predictions),
            json.dumps(top3, ensure_ascii=False),
            json.dumps(stop_loss, ensure_ascii=False),
            json.dumps(roi_summary, ensure_ascii=False),
            agent_report,
            json.dumps(agent_decision or {}, ensure_ascii=False),
            json.dumps(channels, ensure_ascii=False),
        ))
        conn.commit()
        conn.close()
        logger.info('push_history已记录: %s', push_date)
    except Exception as e:
        logger.warning('记录push_history失败: %s', e)


def _get_today_predictions(db_path: str, today: str, tomorrow: str) -> List[dict]:
    """获取今日预测 — 北京时间窗口(today全天 + tomorrow凌晨<12:00)"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ar.lottery_match_id, ar.report_data, ar.created_at,
                   lm.home_team_cn, lm.away_team_cn, lm.league_name_cn
            FROM lottery_analysis_reports ar
            JOIN lottery_matches lm ON ar.lottery_match_id = lm.lottery_match_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            AND ar.report_type IN ('prediction', 'full')
            AND (ar.is_stale = 0 OR ar.is_stale IS NULL)
            ORDER BY ar.lottery_match_id, ar.created_at DESC
        """, (today, tomorrow))
        rows = cursor.fetchall()
        conn.close()

        results = []
        seen_matches = set()  # 按 lottery_match_id 去重, 只取最新一份
        for row in rows:
            mid = row['lottery_match_id']
            if mid in seen_matches:
                continue
            seen_matches.add(mid)
            pred = dict(row)
            try:
                report = json.loads(pred['report_data']) if isinstance(pred['report_data'], str) else pred['report_data']
                final = report.get('final_prediction', {})
                if not final and 'analyses' in report:
                    spf = report.get('analyses', {}).get('spf', {})
                    final = {
                        'probabilities': spf.get('probabilities', {}),
                        'predicted_result': spf.get('recommendation', ''),
                        'confidence': spf.get('confidence', 'medium'),
                    }
                pred['probabilities'] = final.get('probabilities', {})
                pred['confidence'] = final.get('confidence', 'medium')
                pred['confidence_level'] = final.get('confidence_level') or final.get('confidence_tier') or 'medium'
                pred['recommended'] = final.get('predicted_result', '') or final.get('recommended', '')
                pred['model_vs_odds'] = report.get('model_vs_odds')
                pred['odds_baseline'] = report.get('odds_baseline')
                pred['play_predictions'] = report.get('play_predictions', {})
                # confidence_level → numeric for sorting
                conf_map = {'high': 0.8, 'medium': 0.6, 'low': 0.4, 'avoid': 0.2}
                pred['confidence_numeric'] = conf_map.get(pred['confidence_level'], 0.5)
            except Exception:
                pass
            results.append(pred)

        results.sort(key=lambda x: x.get('confidence_numeric', 0), reverse=True)
        return results
    except Exception as e:
        logger.error('获取预测失败: %s', e)
        return []


def _rank_value_bets(predictions: List[dict]) -> List[dict]:
    """按Edge/Kelly排序价值投注 — 多玩法选择(spf/rqspf)取每场最大edge

    体彩可投玩法: spf/rqspf/bf/bqc (无ou). 按准确率+edge筛选:
    - spf: 55.9%准确率, 主玩法, 概率vs赔率基线
    - rqspf: 49.0%准确率, 概率vs market_probabilities
    - bf/bqc: 27.3%/35.8%准确率低, 不纳入top3价值投注(只在玩法推算里展示)
    ou虽53.7%但体彩无此玩法不投注.
    """
    bets = []
    for pred in predictions:
        try:
            # 过滤校准降级为avoid的预测 — 历史证明这个区间不准
            if pred.get('confidence_level') == 'avoid':
                logger.info('过滤avoid预测: %s %s vs %s (校准降级)',
                            pred.get('lottery_match_id'),
                            pred.get('home_team_cn', ''),
                            pred.get('away_team_cn', ''))
                continue

            play_predictions = pred.get('play_predictions', {}) or {}
            candidate_bets = []

            # === 1. SPF ===
            spf = play_predictions.get('spf', {}) or {}
            spf_probs = spf.get('probabilities', {}) or {}
            if spf_probs and spf.get('recommendation'):
                odds_baseline = pred.get('odds_baseline') or {}
                prob_keys = {'home_win': '3', 'draw': '1', 'away_win': '0'}
                implied_probs = None
                try:
                    prob_values = [v for k, v in odds_baseline.items() if k in prob_keys and v > 0]
                    total = sum(1.0 / v for v in prob_values) if prob_values else 0
                    if total > 0:
                        implied_probs = {k: (1.0 / v) / total for k, v in odds_baseline.items()
                                        if k in prob_keys and v > 0}
                except Exception:
                    pass
                rec = str(spf.get('recommendation', ''))
                # spf_probs可能用 '3'/'1'/'0' 或 'home_win'/'draw'/'away_win' 作键
                key_alt = {'3': 'home_win', '1': 'draw', '0': 'away_win'}.get(rec, rec)
                model_prob = spf_probs.get(rec) or spf_probs.get(key_alt) or 0
                implied_prob = (implied_probs or {}).get(key_alt, 0)
                edge = model_prob - implied_prob if implied_prob > 0 else model_prob - 0.33
                conf_map = {'high': 0.8, 'medium': 0.6, 'low': 0.4, 'avoid': 0.2}
                conf_numeric = conf_map.get(spf.get('confidence_level') or spf.get('confidence_tier') or 'medium', 0.5)
                if model_prob > 0:
                    candidate_bets.append({
                        'play_type': 'spf',
                        'selection': rec,
                        'selection_cn': spf.get('recommendation_cn') or {'3': '主胜', '1': '平', '0': '客胜'}.get(rec, rec),
                        'model_prob': model_prob,
                        'implied_prob': implied_prob,
                        'confidence': conf_numeric,
                        'edge': edge,
                        'confidence_level': spf.get('confidence_level') or spf.get('confidence_tier') or 'medium',
                    })

            # === 2. RQSPF (让球胜平负) ===
            rqspf = play_predictions.get('rqspf', {}) or {}
            if rqspf.get('recommendation') and rqspf.get('probabilities'):
                rec = str(rqspf.get('recommendation', ''))
                probs = rqspf.get('probabilities', {}) or {}
                market_probs = rqspf.get('market_probabilities') or {}
                rec_clean = rec.split('+')[0].split('-')[0].strip() if rec else ''
                model_prob = probs.get(rec) or probs.get(rec_clean) or 0
                implied_prob = market_probs.get(rec) or market_probs.get(rec_clean) or 0
                edge = model_prob - implied_prob if implied_prob > 0 else model_prob - 0.33
                conf_map = {'high': 0.8, 'medium': 0.6, 'low': 0.4, 'avoid': 0.2}
                conf_numeric = conf_map.get(rqspf.get('confidence_level') or rqspf.get('confidence_tier') or 'medium', 0.5)
                if model_prob > 0:
                    candidate_bets.append({
                        'play_type': 'rqspf',
                        'selection': rec,
                        'selection_cn': rqspf.get('recommendation_cn') or rec,
                        'model_prob': model_prob,
                        'implied_prob': implied_prob,
                        'confidence': conf_numeric,
                        'edge': edge,
                        'confidence_level': rqspf.get('confidence_level') or rqspf.get('confidence_tier') or 'medium',
                        'handicap': rqspf.get('handicap'),
                    })

            if not candidate_bets:
                continue

            # 过滤avoid候选 — 校准降级的不纳入
            candidate_bets = [c for c in candidate_bets if c.get('confidence_level') != 'avoid']
            if not candidate_bets:
                continue

            # 取该场最大edge的玩法作为推荐
            best_bet = max(candidate_bets, key=lambda x: x.get('edge', 0))
            # 只有edge>0.03(3pp)才值得投注
            if best_bet.get('edge', 0) < 0.03:
                continue

            kelly = max(0, best_bet.get('edge', 0) * 2)
            best_bet.update({
                'lottery_match_id': pred.get('lottery_match_id'),
                'home': pred.get('home_team_cn', ''),
                'away': pred.get('away_team_cn', ''),
                'league': pred.get('league_name_cn', ''),
                'kelly': kelly,
                'model_vs_odds': pred.get('model_vs_odds'),
                'alternative_bets': [
                    {'play_type': c.get('play_type'), 'selection': c.get('selection'),
                     'edge': round(c.get('edge', 0), 4), 'confidence': c.get('confidence')}
                    for c in candidate_bets if c != best_bet
                ],
            })
            bets.append(best_bet)
        except Exception as e:
            logger.debug('rank_value_bets处理失败 %s: %s', pred.get('lottery_match_id'), e)
            continue

    bets.sort(key=lambda x: x.get('edge', 0), reverse=True)
    return bets


def _generate_reason(bet: dict) -> str:
    """生成自然语言推荐理由 — 含因子引用"""
    home = bet.get('home', '')
    away = bet.get('away', '')
    league = bet.get('league', '')
    selection = bet.get('selection', '')
    confidence = bet.get('confidence', 0)
    edge = bet.get('edge', 0)
    model_vs_odds = bet.get('model_vs_odds')

    # 结果映射
    result_map = {'3': '主胜', '1': '平局', '0': '客胜'}
    result_text = result_map.get(selection, selection)

    # 置信度描述
    if confidence > 0.7:
        strength = '强烈看好'
    elif confidence > 0.6:
        strength = '看好'
    else:
        strength = '倾向于'

    parts = [f'{league} {home}vs{away}, {strength}{result_text}']

    # 模型vs赔率
    if model_vs_odds and isinstance(model_vs_odds, dict):
        if model_vs_odds.get('agreement') is True:
            parts.append('模型与赔率方向一致')
        elif model_vs_odds.get('agreement') is False:
            parts.append('模型与赔率分歧(可能存在价值)')

    # Edge
    if edge > 0.05:
        parts.append(f'优势+{edge:.0%}')
    elif edge > 0:
        parts.append(f'微弱优势+{edge:.0%}')

    return ', '.join(parts)


def _record_bets(db_path: str, bets: List[dict]):
    """写入bet_records表 — 使用体彩实际赔率"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 先清理今天pending的旧记录(避免重复)
        cursor.execute("""
            DELETE FROM bet_records WHERE result = 'pending'
            AND lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_matches WHERE match_date = date('now')
            )
        """)

        for bet in bets:
            lm_id = bet.get('lottery_match_id')
            selection = bet.get('selection', '')
            play_type = bet.get('play_type', 'spf')

            # 从lottery_odds获取体彩实际赔率
            real_odds = _get_real_odds(cursor, lm_id, play_type, selection)
            if not real_odds:
                real_odds = bet.get('prob', 0)  # fallback: 用概率

            # 虚拟投注: 基础100元, Kelly比例调整
            kelly = bet.get('kelly', 0)
            stake = round(100 * min(kelly, 0.25), 2) if kelly > 0 else 100.0  # 默认100元

            cursor.execute("""
                INSERT INTO bet_records
                (prediction_id, lottery_match_id, play_type, selection, odds, stake, result)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """, (
                bet.get('prediction_id'),
                lm_id,
                play_type,
                selection,
                real_odds,
                stake,
            ))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug('Bet记录失败: %s', e)


def _get_real_odds(cursor, lottery_match_id: str, play_type: str, selection: str) -> float:
    """从lottery_odds获取体彩实际赔率. 支持spf/rqspf/bqc/bf/ttg."""
    try:
        import json as _json
        # 选项清洗: rqspf的selection可能是'3+1'/'1'等, 取首个数字键
        sel_key = str(selection).split('+')[0].split('-')[0].strip() if selection else ''

        # 按play_type查询, 找不到再尝试rqspf作为spf的fallback
        search_types = [play_type] if play_type != 'spf' else ['spf', 'rqspf']
        for pt in search_types:
            cursor.execute("""
                SELECT odds_data FROM lottery_odds
                WHERE lottery_match_id = ? AND play_type = ?
                ORDER BY created_at DESC LIMIT 1
            """, (lottery_match_id, pt))
            row = cursor.fetchone()
            if not row:
                continue
            odds_data = _json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # 尝试完整selection或清洗后的sel_key
            for key in (selection, sel_key):
                if not key:
                    continue
                try:
                    odds_value = float(odds_data.get(key, 0))
                    if odds_value > 1:
                        return odds_value
                except Exception:
                    continue
        return 0
    except Exception:
        return 0


def _check_stop_loss(db_path: str) -> dict:
    """止损检查 — 近7天ROI < -30%则激活"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT count(*) as total,
                   sum(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                   sum(profit) as profit,
                   sum(stake) as total_stake
            FROM bet_records
            WHERE result IN ('win', 'lose')
            AND created_at >= datetime('now', '-7 days')
        """)
        row = cursor.fetchone()
        conn.close()

        if not row or row[0] == 0 or not row[3]:
            return {'active': False}

        total, wins, profit, total_stake = row
        roi = (profit or 0) / total_stake if total_stake else 0

        return {
            'active': roi < -0.30,
            'roi': round(roi * 100, 1),
            'recent_wins': wins,
            'recent_total': total,
            'recent_profit': round(profit or 0, 0),
        }
    except Exception as e:
        logger.debug('止损检查失败: %s', e)
        return {'active': False}


def _compute_roi_summary(db_path: str) -> dict:
    """计算ROI概况 — 7天/30天/全部"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        summary = {}
        for label, days in [('7d', 7), ('30d', 30), ('all', None)]:
            if days:
                cursor.execute("""
                    SELECT count(*),
                           sum(CASE WHEN result = 'win' THEN 1 ELSE 0 END),
                           sum(profit),
                           sum(stake)
                    FROM bet_records
                    WHERE result IN ('win', 'lose')
                    AND created_at >= datetime('now', ?)
                """, (f'-{days} days',))
            else:
                cursor.execute("""
                    SELECT count(*),
                           sum(CASE WHEN result = 'win' THEN 1 ELSE 0 END),
                           sum(profit),
                           sum(stake)
                    FROM bet_records
                    WHERE result IN ('win', 'lose')
                """)
            row = cursor.fetchone()
            if row and row[0] > 0 and row[3]:
                roi = (row[2] or 0) / row[3]
                summary[label] = {
                    'matches': row[0],
                    'wins': row[1],
                    'profit': round(row[2] or 0, 0),
                    'roi': f'{roi*100:.1f}%',
                }
        conn.close()
        return summary
    except Exception as e:
        logger.debug('ROI计算失败: %s', e)
        return {}