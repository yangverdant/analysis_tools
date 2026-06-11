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

    # 获取今日有预测的比赛(北京时间窗口)
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
    push_content = format_daily_push(today, mode, predictions, top3, stop_loss, roi_summary)
    push_results = push_to_all_channels(
        f'{today} 分析师日报',
        push_content
    )

    return {
        'route': 'normal',
        'pushed': len(predictions),
        'top3': top3,
        'stop_loss': stop_loss,
        'roi_summary': roi_summary,
        'channels': push_results,
    }


def _get_today_predictions(db_path: str, today: str, tomorrow: str) -> List[dict]:
    """获取今日预测 — 北京时间窗口(today全天 + tomorrow凌晨<12:00)"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ar.lottery_match_id, ar.report_data,
                   lm.home_team_cn, lm.away_team_cn, lm.league_name_cn
            FROM lottery_analysis_reports ar
            JOIN lottery_matches lm ON ar.lottery_match_id = lm.lottery_match_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            AND ar.report_type IN ('prediction', 'full')
        """, (today, tomorrow))
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
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
                pred['recommended'] = final.get('predicted_result', '') or final.get('recommended', '')
                pred['model_vs_odds'] = report.get('model_vs_odds')
                pred['odds_baseline'] = report.get('odds_baseline')
                pred['play_predictions'] = report.get('play_predictions', {})
                # confidence_level → numeric for sorting
                conf_map = {'high': 0.8, 'medium': 0.6, 'low': 0.4}
                pred['confidence_numeric'] = conf_map.get(pred['confidence'], 0.5)
            except Exception:
                pass
            results.append(pred)

        results.sort(key=lambda x: x.get('confidence_numeric', 0), reverse=True)
        return results
    except Exception as e:
        logger.error('获取预测失败: %s', e)
        return []


def _rank_value_bets(predictions: List[dict]) -> List[dict]:
    """按Edge/Kelly排序价值投注"""
    bets = []
    for pred in predictions:
        try:
            probs = pred.get('probabilities', {})
            if not probs:
                continue

            # oddsfe赔率 → 隐含概率(1/odds归一化)
            odds_baseline = pred.get('odds_baseline')
            implied_probs = None
            if odds_baseline:
                try:
                    # 只取概率键，排除source等元数据
                    prob_keys = {'home_win', 'draw', 'away_win'}
                    prob_values = [v for k, v in odds_baseline.items() if k in prob_keys and v > 0]
                    total = sum(1.0 / v for v in prob_values) if prob_values else 0
                    if total > 0:
                        implied_probs = {k: (1.0 / v) / total for k, v in odds_baseline.items()
                                        if k in prob_keys and v > 0}
                except Exception:
                    pass

            # 概率键映射: home_win/3, draw/1, away_win/0
            key_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
            norm_probs = {}
            for k, v in probs.items():
                nk = key_map.get(k, k)
                norm_probs[nk] = v

            # 找最大概率选项
            if not norm_probs:
                continue
            best = max(norm_probs, key=norm_probs.get)
            model_prob = norm_probs[best]

            # 计算edge
            implied_prob = (implied_probs or {}).get(best, 0)
            edge = model_prob - implied_prob if implied_prob > 0 else model_prob - 0.33

            # Kelly简化: (prob * odds - 1) / (odds - 1), 用edge近似
            kelly = max(0, edge * 2)  # 简化Kelly

            bets.append({
                'lottery_match_id': pred.get('lottery_match_id'),
                'home': pred.get('home_team_cn', ''),
                'away': pred.get('away_team_cn', ''),
                'league': pred.get('league_name_cn', ''),
                'selection': best,
                'prob': model_prob,
                'implied_prob': implied_prob,
                'confidence': pred.get('confidence_numeric', 0.5),
                'edge': edge,
                'kelly': kelly,
                'play_type': 'spf',
                'model_vs_odds': pred.get('model_vs_odds'),
            })
        except Exception:
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
    """从lottery_odds获取体彩实际赔率(如SPF: 1.45)"""
    try:
        # Try SPF first, then RQSPF as fallback
        for pt in [play_type, 'rqspf']:
            if pt == play_type or play_type == 'spf':
                cursor.execute("""
                    SELECT odds_data FROM lottery_odds
                    WHERE lottery_match_id = ? AND play_type = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (lottery_match_id, pt))
                row = cursor.fetchone()
                if not row:
                    continue

                import json as _json
                odds_data = _json.loads(row[0]) if isinstance(row[0], str) else row[0]

                key = selection  # '3', '1', '0'
                odds_value = float(odds_data.get(key, 0))
                if odds_value > 1:
                    return odds_value
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