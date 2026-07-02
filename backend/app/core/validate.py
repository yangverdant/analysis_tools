"""次日复盘验证 — 翻车归因 + 结果入库

职责:
1. 调用sync_results获取昨日赛果
2. 写入lottery_results
3. 从lottery_analysis_reports取预测，对比实际结果验证
4. 翻车归因(5级: bad_luck/close_match/correction_wrong/market_wrong/intel_missing)
5. 写入lottery_validation(含attribution)
"""

import json
import logging
import os
import re
import sqlite3
import time
import random
import requests
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .time_utils import today_beijing, yesterday_beijing

logger = logging.getLogger(__name__)


def _table_columns(conn, table_name: str) -> set:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except Exception:
        return set()


def _active_report_filter(conn, alias: str = "") -> str:
    columns = _table_columns(conn, "lottery_analysis_reports")
    if "is_stale" not in columns:
        return ""
    prefix = f"{alias}." if alias else ""
    return f"AND COALESCE({prefix}is_stale, 0) = 0"


# 翻车归因5级(保留兼容) + 细化归因类型
ATTRIBUTION_LEVELS = {
    'bad_luck': '运气差 — 模型方向正确但结果不利',
    'close_match': '势均力敌 — 概率差距小(<5pp)',
    'correction_wrong': '修正方向错 — 基础模型方向对但修正反了',
    'market_wrong': '市场信号错误 — 赔率暗示与结果相反',
    'intel_missing': '情报缺失 — 关键信息(伤病/阵容)未纳入',
    'model_weight': '模型权重 — 数据齐备但权重可能错误',
}

# 细化归因类型 — 替代 generic unknown
FINE_ATTRIBUTION_TYPES = {
    # 数据缺失类
    'missing_lineup': '缺少预计首发/阵容信息',
    'missing_injury': '缺少伤停信息',
    # 模型判断类
    'market_misread': '赔率信号误读 — 赔率方向与结果一致但模型反了',
    'goal_axis_misread': '进球轴误判 — 实际进球数与预测偏离大',
    'margin_axis_misread': '让球边界误判 — 赢球幅度与预测不一致',
    'half_time_axis_misread': '半场节奏误判 — 上半场走向与预测相反',
    'motivation_misread': '赛事动机误判 — 动机/轮换因素未被正确纳入',
    'tournament_context_misread': '赛事上下文误判 — 赛事类型特性未正确应用',
    # 数据质量类
    'data_quality_issue': '数据质量问题 — 赔率/盘口数据不完整或不准确',
    'low_confidence_noise': '低置信噪声 — 置信度低，预测不可靠',
    'model_weight_issue': '模型权重问题 — 数据齐备但因子权重分配不当',
}

# 结果映射: 模型推荐 → SPF代码
RESULT_MAP = {'home_win': '3', 'draw': '1', 'away_win': '0', '3': '3', '1': '1', '0': '0'}
CN_RESULT_MAP = {'主胜': '3', '平局': '1', '平': '1', '客胜': '0', '客': '0'}
SPF_LABEL = {'3': '主胜', '1': '平局', '0': '客胜'}
RQSPF_LABEL = {'3': '让胜', '1': '让平', '0': '让负'}

# 亚盘结算等级
SETTLEMENT_GRADES = {
    'full_win': '全赢',     # 盘口完全命中
    'half_win': '半赢',     # 1/4盘半赢(e.g. 2.25线打出2球→半输对手/半赢自己)
    'push': '走水',         # 刚好打在线上(e.g. 2.0线打出2球)
    'half_loss': '半输',    # 1/4盘半输
    'full_loss': '全输',    # 盘口完全未命中
    'void': '无效',         # 盘口数据缺失
}


def compute_ou_settlement(total_goals: int, ou_line: float, predicted_direction: str) -> str:
    """计算O/U亚盘结算等级

    Args:
        total_goals: 实际总进球
        ou_line: 盘口线(e.g. 2.0, 2.25, 2.5, 2.75, 3.0)
        predicted_direction: '大' or '小'

    Returns:
        'full_win', 'half_win', 'push', 'half_loss', 'full_loss', 'void'
    """
    if ou_line is None or total_goals is None:
        return 'void'

    line = float(ou_line)
    whole = int(line)
    quarter = round((line - whole) * 4)

    if quarter == 0:
        # 整数盘(2.0, 3.0): 走水/全赢/全输
        if total_goals == line:
            return 'push'
        over_wins = total_goals > line
        if predicted_direction == '大':
            return 'full_win' if over_wins else 'full_loss'
        else:
            return 'full_win' if not over_wins else 'full_loss'

    if quarter == 2:
        # 半球盘(2.5, 3.5): 全赢/全输，无走水
        over_wins = total_goals > line
        if predicted_direction == '大':
            return 'full_win' if over_wins else 'full_loss'
        else:
            return 'full_win' if not over_wins else 'full_loss'

    if quarter == 1:
        # 1/4盘(e.g. 2.25 = 2.0 + 2.5): 拆成两个子盘
        low_line = float(whole)
        high_line = whole + 0.5
        low_result = _single_line_result(total_goals, low_line, predicted_direction)
        high_result = _single_line_result(total_goals, high_line, predicted_direction)
        return _merge_half_results(low_result, high_result)

    if quarter == 3:
        # 3/4盘(e.g. 2.75 = 2.5 + 3.0): 拆成两个子盘
        low_line = whole + 0.5
        high_line = float(whole + 1)
        low_result = _single_line_result(total_goals, low_line, predicted_direction)
        high_result = _single_line_result(total_goals, high_line, predicted_direction)
        return _merge_half_results(low_result, high_result)

    return 'void'


def _single_line_result(total_goals: int, line: float, predicted_direction: str) -> str:
    """单个子盘的结果: 'win', 'loss', 'push'"""
    if total_goals > line:
        return 'win' if predicted_direction == '大' else 'loss'
    elif total_goals < line:
        return 'loss' if predicted_direction == '大' else 'win'
    else:
        return 'push'


def _merge_half_results(low_result: str, high_result: str) -> str:
    """合并两个子盘结果 → 最终结算等级"""
    if low_result == 'win' and high_result == 'win':
        return 'full_win'
    if low_result == 'loss' and high_result == 'loss':
        return 'full_loss'
    if low_result == 'win' and high_result == 'push':
        return 'half_win'
    if low_result == 'push' and high_result == 'loss':
        return 'half_loss'
    if low_result == 'push' and high_result == 'push':
        return 'push'
    # 混合: win+loss理论上不应出现在1/4盘(因为两个子盘线相邻)
    # 但作为安全兜底
    if low_result == 'win' and high_result == 'loss':
        return 'push'
    if low_result == 'loss' and high_result == 'win':
        return 'push'
    if low_result == 'push' and high_result == 'win':
        return 'half_win'
    if low_result == 'loss' and high_result == 'push':
        return 'half_loss'
    return 'void'


def compute_handicap_settlement(home_goals: int, away_goals: int, handicap: float, predicted_direction: str) -> str:
    """计算让球胜平负的结算等级

    Args:
        home_goals: 主队进球
        away_goals: 客队进球
        handicap: 让球值(正=主让, e.g. -1表示主让1球)
        predicted_direction: '3'(让胜), '1'(让平), '0'(让负)

    Returns:
        'full_win', 'half_win', 'push', 'half_loss', 'full_loss', 'void'
    """
    if home_goals is None or away_goals is None or handicap is None:
        return 'void'

    hcp = float(handicap)
    # handicap convention: negative = home giving (主让)
    # adjusted = home + goal_line (goal_line negative when home gives)
    # For settlement: we need the actual goal_line used in the bet
    # Convention: goal_line = -handicap for the RQSPF bet
    goal_line = -hcp  # Convert to the line used

    margin = home_goals - away_goals
    adjusted = margin + goal_line  # positive = home wins after handicap

    # Determine the quarter position
    whole = int(abs(adjusted)) if adjusted != 0 else 0
    adj_rounded = round(adjusted * 4) / 4  # snap to 0.25
    adj_whole = int(adj_rounded)
    adj_quarter = round((adj_rounded - adj_whole) * 4)

    if abs(adjusted) < 0.01:
        # Exactly on the line → 让平 result
        if predicted_direction == '1':  # 让平
            return 'full_win'  # predicted exactly right
        elif predicted_direction == '3':
            # Predicted 让胜 but result is 让平 → boundary miss
            return 'push'
        elif predicted_direction == '0':
            # Predicted 让负 but result is 让平 → boundary miss
            return 'push'
        return 'push'

    # Standard handicap (整数让球): adjusted is integer
    if adj_quarter == 0:
        if adjusted > 0:
            # Home wins after handicap → 让胜
            if predicted_direction == '3':
                return 'full_win'
            elif predicted_direction == '1':
                return 'full_loss'
            else:
                return 'full_loss'
        else:
            # Away wins after handicap → 让负
            if predicted_direction == '0':
                return 'full_win'
            elif predicted_direction == '1':
                return 'full_loss'
            else:
                return 'full_loss'

    # 1/4 or 3/4 handicap lines (rare in sporttery but possible)
    return _handicap_quarter_settlement(adjusted, predicted_direction)


def _handicap_quarter_settlement(adjusted: float, predicted_direction: str) -> str:
    """Handle quarter-line handicap settlement"""
    adj_rounded = round(adjusted * 4) / 4
    adj_whole = int(adj_rounded)
    adj_quarter = round((adj_rounded - adj_whole) * 4)

    if adj_quarter == 0:
        home_wins = adjusted > 0
        if home_wins:
            return 'full_win' if predicted_direction == '3' else 'full_loss'
        else:
            return 'full_win' if predicted_direction == '0' else 'full_loss'

    # For quarter lines, split into two components
    if adj_quarter in (1, 3):
        low = float(adj_whole)
        high = adj_whole + 0.5 if adj_quarter == 1 else float(adj_whole + 1)
        low_home = adjusted > low
        high_home = adjusted > high

        results = []
        for home_wins in [low_home, high_home]:
            if home_wins:
                results.append('win' if predicted_direction == '3' else 'loss')
            else:
                results.append('win' if predicted_direction == '0' else 'loss')

        return _merge_half_results(results[0], results[1])

    if adj_quarter == 2:
        # Half-ball line
        line = adj_whole + 0.5
        home_wins = adjusted > line
        if home_wins:
            return 'full_win' if predicted_direction == '3' else 'full_loss'
        else:
            return 'full_win' if predicted_direction == '0' else 'full_loss'

    return 'void'
INVALID_VALIDATION_TEXTS = {'', '--', 'unknown', 'UNKNOWN', 'none', 'None', 'null', 'NULL', 'nan', 'NaN', ':', '::', '未知'}
BQC_TO_CODE = {
    '33': '33', '31': '31', '30': '30',
    '13': '13', '11': '11', '10': '10',
    '03': '03', '01': '01', '00': '00',
    'hh': '33', 'hd': '31', 'ha': '30',
    'dh': '13', 'dd': '11', 'da': '10',
    'ah': '03', 'ad': '01', 'aa': '00',
    '胜胜': '33', '胜平': '31', '胜负': '30',
    '平胜': '13', '平平': '11', '平负': '10',
    '负胜': '03', '负平': '01', '负负': '00',
}


def _clean_validation_text(value) -> str:
    return '' if value is None else str(value).strip()


def _is_valid_validation_text(value) -> bool:
    text = _clean_validation_text(value)
    return bool(text) and text not in INVALID_VALIDATION_TEXTS


def _delete_validation(conn, lottery_match_id, play_type: str) -> None:
    conn.execute(
        "DELETE FROM lottery_validation WHERE lottery_match_id = ? AND play_type = ?",
        (lottery_match_id, play_type),
    )
    try:
        conn.execute(
            "DELETE FROM post_match_reviews WHERE match_key = ? AND play_type = ?",
            (str(lottery_match_id), play_type),
        )
    except Exception:
        pass


def _normalize_bqc_value(value) -> str:
    text = _clean_validation_text(value)
    return BQC_TO_CODE.get(text, BQC_TO_CODE.get(text.lower(), text))


def _normalize_rqspf_value(value) -> str:
    text = _clean_validation_text(value)
    if text in RESULT_MAP:
        return RESULT_MAP[text]
    if text in CN_RESULT_MAP:
        return CN_RESULT_MAP[text]
    if '让胜' in text or '主胜' in text or 'home_win' in text:
        return '3'
    if '让负' in text or '客胜' in text or 'away_win' in text:
        return '0'
    if '让平' in text or '平局' in text or text == '平' or 'draw' in text:
        return '1'
    return text


def validate(state, db_path: str, agent=None) -> dict:
    """执行复盘验证 — 北京时间窗口"""
    yesterday = yesterday_beijing()
    today = today_beijing()

    logger.info('=== 复盘验证 (%s / %s) ===', yesterday, today)

    results = {}

    # Step 0: oddsfe增量同步(确保最新赛果已入库)
    results['oddsfe_sync'] = _sync_oddsfe_before_validate(db_path)

    # Step 1: 获取赛果(oddsfe优先, sporttery备选)
    results['sync_results_oddsfe'] = _sync_results_oddsfe(db_path, yesterday)
    results['sync_results_oddsfe_today'] = _sync_results_oddsfe(db_path, today)
    if not results['sync_results_oddsfe'].get('success') and not results['sync_results_oddsfe_today'].get('success'):
        logger.info('oddsfe结果获取失败, 尝试sporttery备选')
        results['sync'] = _sync_results(db_path, yesterday)

    # Step 1b: 从oddsfe_merged.db回填历史缺失结果
    results['backfill'] = _backfill_results_from_oddsfe(db_path)

    # Step 1c: 从unified_football.db回填(备选源)
    if not results['backfill'].get('backfilled'):
        results['backfill_unified'] = _backfill_results_from_unified(db_path)

    # Step 1d: 从CSV补充开盘赔率(Pinnacle/B365)
    results['csv_odds_sync'] = _sync_csv_opening_odds(db_path)

    # Step 2: 确定需要验证的日期范围(含历史回填)
    match_dates = _find_unvalidated_dates(db_path, [yesterday, today])

    # Step 2b: 验证预测
    results['validation'] = _validate_predictions(db_path, match_dates)
    try:
        from pathlib import Path
        from backend.app.lottery.services.auto_gap_runner import LotteryAutoGapRunner

        oddsfe_db_path = os.environ.get(
            "ODDSFE_DB_PATH",
            str(Path(db_path).parent / "oddsfe_merged.db"),
        )
        results['reanalysis_change_settlement'] = LotteryAutoGapRunner(
            db_path,
            oddsfe_db_path,
        ).settle_reanalysis_changes(
            min(match_dates) if match_dates else None,
            max(match_dates) if match_dates else None,
        )
    except Exception as e:
        logger.warning("Reanalysis change settlement failed after validation: %s", e)
        results['reanalysis_change_settlement'] = {"error": str(e)}

    # Step 3: 翻车归因(规则引擎+Agent增强)
    results['attribution'] = _attribute_failures(db_path, match_dates, agent=agent)

    # Step 4: 结算bet_records
    results['settlement'] = _settle_bets(db_path)

    logger.info('复盘完成: %d场验证, %d场归因, %d笔结算',
                results['validation'].get('validated', 0),
                results['attribution'].get('attributed', 0),
                results['settlement'].get('settled', 0))

    return {
        'route': 'normal',
        'validated': results['validation'].get('validated', 0),
        'reanalysis_change_settlement': results.get('reanalysis_change_settlement'),
    }


def _find_unvalidated_dates(db_path: str, default_dates: list) -> list:
    """查找有结果但未验证的日期，加入回填范围"""
    dates = list(default_dates)
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        rows = conn.execute("""
            SELECT DISTINCT lm.match_date
            FROM lottery_matches lm
            JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
            LEFT JOIN lottery_validation lv ON lm.lottery_match_id = lv.lottery_match_id
            WHERE lv.lottery_match_id IS NULL
            AND lm.match_date < date('now')
        """).fetchall()
        for row in rows:
            if row[0] not in dates:
                dates.append(row[0])
        conn.close()
        if len(dates) > len(default_dates):
            logger.info('历史回填: 新增%d个日期', len(dates) - len(default_dates))
    except Exception as e:
        logger.debug('查找未验证日期失败: %s', e)
    return dates


def _sync_results(db_path: str, match_date: str) -> dict:
    """获取昨日赛果并入库 — sporttery"""
    try:
        from backend.app.lottery.services.sync_service import LotterySyncService
        service = LotterySyncService(db_path)
        result = service.sync_results(date.fromisoformat(match_date))
        return result
    except Exception as e:
        logger.error('赛果获取失败: %s', e)
        return {'success': False, 'error': str(e)}


def _sync_results_oddsfe(db_path: str, match_date: str) -> dict:
    """oddsfe结果源 — 调schedule API + event API获取完整赛果

    流程:
    1. /bind/schedule/football/{date} → event_id + 比分 + winner
    2. /bind/event/{event_id} → score_details(半场/加时/点球比分)
    3. 解析score_details → 推导SPF/BF/BQC/RQSPF全部玩法
    4. INSERT OR REPLACE写入lottery_results

    时间处理:
    - 体彩match_date是北京日期，oddsfe schedule API用UTC日期
    - 北京凌晨0-8点的比赛在oddsfe是前一天UTC
    - lottery_matches.match_date可能与beijing_time日期不一致
      (如match_date='2026-06-15'但beijing_time='2026-06-16 09:00')
    - 因此同时查match_date和beijing_time覆盖的日期
    """
    # 调schedule API — 查match_date当天和前后各一天UTC(覆盖时区偏移)
    all_schedule = []
    dates_to_query = set()
    dates_to_query.add(match_date)
    # 前一天UTC(覆盖北京时间凌晨0-8点的比赛)
    try:
        prev_date = str(date.fromisoformat(match_date) - timedelta(days=1))
        dates_to_query.add(prev_date)
    except ValueError:
        pass
    # 后一天UTC(覆盖match_date记录在前一天但beijing_time在当天的比赛)
    try:
        next_date = str(date.fromisoformat(match_date) + timedelta(days=1))
        dates_to_query.add(next_date)
    except ValueError:
        pass

    for query_date in dates_to_query:
        try:
            sd = _oddsfe_fetch_schedule(query_date)
            if sd:
                all_schedule.extend(sd)
        except Exception as e:
            logger.warning('oddsfe schedule获取失败 %s: %s', query_date, e)

    if not all_schedule:
        return {'success': False, 'error': 'no schedule data'}

    # 提取FINISHED比赛(不再按北京时间过滤 — 由lottery_matches查询决定范围)
    finished = []
    for tournament in all_schedule:
        if isinstance(tournament, dict):
            for ev in tournament.get('events', []):
                if ev.get('event_status') == 'FINISHED':
                    finished.append(ev)

    if not finished:
        return {'success': False, 'error': 'no finished matches', 'date': match_date}

    # 队名归一化索引
    cn_to_en = _load_cn_to_en(db_path)
    oddsfe_by_name = {}
    for ev in finished:
        h_raw = ev.get('team_home_name', '')
        a_raw = ev.get('team_away_name', '')
        h_norm = _norm_team(h_raw)
        a_norm = _norm_team(a_raw)
        oddsfe_by_name[(h_norm, a_norm)] = ev

    # 匹配体彩比赛 — 同时查match_date和beijing_time日期
    # match_date='2026-06-15'但beijing_time='2026-06-16 09:00'的比赛
    # 在查'2026-06-16'时也要能找到
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT lottery_match_id, home_team_cn, away_team_cn, oddsfe_event_id, handicap_line, beijing_time "
        "FROM lottery_matches "
        "WHERE match_date = ? OR beijing_time LIKE ?",
        (match_date, f'{match_date}%')
    )
    lottery_matches = [dict(r) for r in cursor.fetchall()]

    saved = 0
    session = requests.Session()
    session.trust_env = False

    for lm in lottery_matches:
        # 检查已有结果 — 如果有则用oddsfe比分交叉校验
        existing = conn.execute(
            "SELECT home_goals_ft, away_goals_ft FROM lottery_results WHERE lottery_match_id = ? AND bf_result IS NOT NULL",
            (lm['lottery_match_id'],)
        ).fetchone()
        if existing:
            # 交叉校验: 如果oddsfe比分与DB不一致，用oddsfe覆盖
            # 先找到匹配的oddsfe event
            matched_for_check = None
            if lm.get('oddsfe_event_id'):
                for ev in finished:
                    if str(ev.get('event_id')) == str(lm['oddsfe_event_id']):
                        matched_for_check = ev
                        break
            if not matched_for_check:
                home_en = cn_to_en.get(lm['home_team_cn']) or lm.get('home_team_cn', '')
                away_en = cn_to_en.get(lm['away_team_cn']) or lm.get('away_team_cn', '')
                h_norm = _norm_team(home_en)
                a_norm = _norm_team(away_en)
                matched_for_check = oddsfe_by_name.get((h_norm, a_norm))
            if matched_for_check:
                oddsfe_h = _safe_int(matched_for_check.get('event_score_home'))
                oddsfe_a = _safe_int(matched_for_check.get('event_score_away'))
                db_h = existing[0]
                db_a = existing[1]
                if oddsfe_h is not None and oddsfe_a is not None and (oddsfe_h != db_h or oddsfe_a != db_a):
                    logger.warning('比分校验不一致 %s: DB=%d:%d, oddsfe=%d:%d, 用oddsfe覆盖',
                                   lm['lottery_match_id'], db_h, db_a, oddsfe_h, oddsfe_a)
                    # 删除旧结果，让下面的逻辑重新写入
                    conn.execute("DELETE FROM lottery_results WHERE lottery_match_id = ?", (lm['lottery_match_id'],))
                    # 不continue，让后面的逻辑重新写入
                else:
                    continue  # 比分一致，跳过
            else:
                continue  # 找不到oddsfe匹配，保留现有结果

        # 优先通过oddsfe_event_id匹配
        matched_ev = None
        if lm.get('oddsfe_event_id'):
            for ev in finished:
                if str(ev.get('event_id')) == str(lm['oddsfe_event_id']):
                    matched_ev = ev
                    break

        # 其次通过队名匹配
        if not matched_ev:
            home_en = cn_to_en.get(lm['home_team_cn']) or lm.get('home_team_cn', '')
            away_en = cn_to_en.get(lm['away_team_cn']) or lm.get('away_team_cn', '')
            h_norm = _norm_team(home_en)
            a_norm = _norm_team(away_en)
            matched_ev = oddsfe_by_name.get((h_norm, a_norm))

        if not matched_ev:
            continue

        home_goals = _safe_int(matched_ev.get('event_score_home'))
        away_goals = _safe_int(matched_ev.get('event_score_away'))
        if home_goals is None or away_goals is None:
            continue

        # 调event API拿score_details(半场/加时/点球)
        score_details = _oddsfe_fetch_score_details(session, matched_ev.get('event_id', ''))

        # 解析score_details → 半场比分
        ht_h, ht_a = _parse_score_details(score_details)

        # 交叉验证: score_details全场比分应与event_score一致
        if score_details:
            sd_ft_h, sd_ft_a = _parse_fulltime_from_score_details(score_details)
            if sd_ft_h is not None and sd_ft_a is not None:
                if sd_ft_h != home_goals or sd_ft_a != away_goals:
                    logger.warning('赛果不一致 %s: event_score=%d:%d, score_details全场=%d:%d, 使用score_details',
                                   lm['lottery_match_id'], home_goals, away_goals, sd_ft_h, sd_ft_a)
                    home_goals = sd_ft_h
                    away_goals = sd_ft_a

        # 半场比分合理性检查: 半场进球不应超过全场
        if ht_h is not None and ht_a is not None:
            if ht_h > home_goals or ht_a > away_goals:
                logger.warning('半场比分异常 %s: HT %d:%d > FT %d:%d, 置空半场',
                               lm['lottery_match_id'], ht_h, ht_a, home_goals, away_goals)
                ht_h, ht_a = None, None

        # 推导全部玩法结果 — 用goal_line算RQSPF(handicap_line方向不可靠)
        effective_hcp = _get_effective_handicap(conn, lm['lottery_match_id'], lm.get('handicap_line', 0))
        results = _derive_all_play_types(home_goals, away_goals, ht_h, ht_a, effective_hcp,
                                          db_path=db_path, lottery_match_id=lm['lottery_match_id'])

        try:
            conn.execute("""
                INSERT OR REPLACE INTO lottery_results
                (lottery_match_id, home_goals_ft, away_goals_ft,
                 home_goals_ht, away_goals_ht,
                 spf_result, bf_result, bqc_result, rqspf_result, ou_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lm['lottery_match_id'],
                results['home_goals_ft'], results['away_goals_ft'],
                results['home_goals_ht'], results['away_goals_ht'],
                results['spf_result'], results['bf_result'],
                results['bqc_result'], results['rqspf_result'],
                results.get('ou_result'),
            ))
            saved += 1

            # 同时更新lottery_matches: beijing_time + oddsfe_event_id
            _update_match_meta(conn, lm['lottery_match_id'], matched_ev)
        except Exception as e:
            logger.debug('结果写入失败 %s: %s', lm['lottery_match_id'], e)

    conn.commit()
    conn.close()
    return {'success': saved > 0, 'saved': saved, 'date': match_date, 'source': 'oddsfe'}


# ==================== oddsfe API调用(不依赖fetchers包) ====================

_ODDSFE_AUTH_CACHE = {'schedule': None, 'event': None, 'last_fetch': 0}


def _oddsfe_get_auth(auth_type='schedule'):
    """自动从oddsfe.com获取auth headers"""
    now = time.time()
    if _ODDSFE_AUTH_CACHE[auth_type] and (now - _ODDSFE_AUTH_CACHE['last_fetch'] < 3600):
        return _ODDSFE_AUTH_CACHE[auth_type].copy()

    s = requests.Session()
    s.trust_env = False
    try:
        r = s.get('https://oddsfe.com/schedule/football/',
                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                  timeout=15)
        if r.status_code != 200:
            return _ODDSFE_AUTH_CACHE[auth_type] or {}

        scripts = re.findall(r'<script[^>]+src="([^"]+)"', r.text)
        for sc in scripts:
            if 'active' not in sc and 'chunk' not in sc:
                continue
            full_url = 'https://oddsfe.com' + sc if sc.startswith('/') else sc
            try:
                r2 = s.get(full_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                if r2.status_code == 200 and r2.text.strip():
                    js = r2.text
                    auth = {}
                    pairs = re.findall(r'"([a-f0-9]{32})"\s*:\s*"([a-f0-9]{32}|[a-zA-Z0-9+/=]+)"', js)
                    for k, v in pairs:
                        auth[k] = v
                    bearers = re.findall(r'"bearer"\s*:\s*"([^"]+)"', js, re.I)
                    if bearers:
                        auth['bearer'] = bearers[0]
                    n7 = re.findall(r'"n7R6b9CKPdnd46vK1"\s*:\s*"([^"]+)"', js)
                    if n7:
                        auth['n7R6b9CKPdnd46vK1'] = n7[0]
                    if auth:
                        _ODDSFE_AUTH_CACHE['schedule'] = auth
                        _ODDSFE_AUTH_CACHE['event'] = {k: v for k, v in auth.items() if k != 'bearer'}
                        _ODDSFE_AUTH_CACHE['last_fetch'] = now
                        return auth.copy()
            except Exception:
                continue
    except Exception:
        pass

    # fallback
    fallback = {
        '6bc09d2870765cb35436e40a10489f12': 'a46a5f2f1ecc59b0c75d40e04e087ed6',
        'n7R6b9CKPdnd46vK1': '59nfZbY3yIb',
        'bearer': 'SnrsZ0OzuEZvauaA8mq0eXl6Qkq0B7==',
    }
    _ODDSFE_AUTH_CACHE['schedule'] = fallback
    _ODDSFE_AUTH_CACHE['event'] = {'6bc09d2870765cb35436e40a10489f12': 'a46a5f2f1ecc59b0c75d40e04e087ed6'}
    _ODDSFE_AUTH_CACHE['last_fetch'] = now
    return fallback.copy()


def _oddsfe_fetch_schedule(date_str, max_retries=3):
    """调oddsfe schedule API获取某天赛事"""
    url = f'https://oddsfe.com/bind/schedule/football/{date_str}'
    auth = _oddsfe_get_auth('schedule')

    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://oddsfe.com',
                'Referer': f'https://oddsfe.com/schedule/football/{date_str}',
            }
            headers.update(auth)
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 401:
                _oddsfe_get_auth.__code__  # force re-fetch on next call
                _ODDSFE_AUTH_CACHE['last_fetch'] = 0  # 强制刷新
                auth = _oddsfe_get_auth('schedule')
                continue
            elif r.status_code == 429:
                time.sleep(random.uniform(3, 6))
                continue
            else:
                return None
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)
    return None


def _oddsfe_fetch_score_details(session, event_id, max_retries=2):
    """调oddsfe /bind/event/{id} API获取score_details(半场/加时/点球比分)"""
    if not event_id:
        return None
    url = f'https://oddsfe.com/bind/event/{event_id}'
    auth = _oddsfe_get_auth('event')

    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Origin': 'https://oddsfe.com',
                'Referer': f'https://oddsfe.com/events/{event_id}',
            }
            headers.update(auth)
            r = session.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                data = r.json()
                return data.get('score_details', '')
            elif r.status_code == 401:
                _ODDSFE_AUTH_CACHE['last_fetch'] = 0
                auth = _oddsfe_get_auth('event')
                continue
            else:
                return None
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2)
    return None


def _parse_score_details(score_details: str):
    """解析score_details → 半场比分(home_ht, away_ht)

    格式变体:
    - "2:1"                    → 1段: 只有全场(无法区分半场)
    - "0:1, 2:1"              → 2段: 半场, 全场
    - "1:0, 1:2, 8:7"         → 3段: 半场, 全场(常规), 加时后
    - "0:0, 1:1, 0:0, 5:6"    → 4段: 半场, 全场(常规), 加时, 点球
    - "(4:1, 3:3)"            → 括号形式，去掉括号后同上

    我们需要的:
    - 半场比分 = 第1段
    - 全场比分 = 最后一段(或第2段如果有2段+)
    """
    if not score_details:
        return None, None

    # 去括号
    sd = score_details.strip().strip('()')
    # 按,分割
    parts = [p.strip() for p in sd.split(',')]

    if len(parts) < 2:
        return None, None  # 只有全场，无法推断半场

    # 第1段 = 半场比分
    ht_part = parts[0]
    ht_scores = ht_part.split(':')
    if len(ht_scores) == 2:
        try:
            return int(ht_scores[0]), int(ht_scores[1])
        except ValueError:
            return None, None

    return None, None


def _parse_fulltime_from_score_details(score_details: str):
    """从score_details提取全场比分(用于交叉验证event_score)

    oddsfe score_details格式是每半场各自进球:
    - "1:2, 0:2"              → 上半场1:2, 下半场0:2 → 全场=1+0:2+2=1:4
    - "1:0, 2:1"              → 上半场1:0, 下半场2:1 → 全场=1+2:0+1=3:1
    全场 = 各半场进球之和
    """
    if not score_details:
        return None, None

    sd = score_details.strip().strip('()')
    parts = [p.strip() for p in sd.split(',')]

    if len(parts) < 2:
        return None, None

    # 解析每段比分
    parsed = []
    for part in parts:
        scores = part.split(':')
        if len(scores) == 2:
            try:
                parsed.append((int(scores[0]), int(scores[1])))
            except ValueError:
                return None, None
        else:
            return None, None

    if len(parsed) < 2:
        return None, None

    # 全场 = 所有半场进球之和
    total_h = sum(p[0] for p in parsed)
    total_a = sum(p[1] for p in parsed)
    return total_h, total_a


def _get_effective_handicap(conn, lottery_match_id: str, fallback_handicap: float) -> float:
    """获取正确的让球值用于RQSPF计算

    体彩handicap_line方向不可靠(正负含义不统一),
    优先从lottery_odds.rqspf的goal_line字段获取正确方向。

    goal_line约定(体彩标准):
    - "-2" → 主让2球 → RQSPF: home_adj = home_ft - 2
    - "+1" → 客让1球 → RQSPF: home_adj = home_ft + 1
    转换: effective = -goal_line_val (使home_adj = home_ft - effective)
    """
    try:
        row = conn.execute(
            "SELECT odds_data FROM lottery_odds WHERE lottery_match_id = ? AND play_type = 'rqspf' LIMIT 1",
            (lottery_match_id,)
        ).fetchone()
        if row:
            odds = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            gl = str(odds.get('goal_line', '')).strip()
            if gl:
                gl_val = float(gl)
                # Convert: goal_line=-2 → effective=2 (主让2), goal_line=+1 → effective=-1 (客让1)
                return -gl_val
    except Exception:
        pass
    return fallback_handicap or 0


def _derive_all_play_types(home_ft, away_ft, home_ht, away_ht,
                           handicap_line=0, db_path=None, lottery_match_id=None):
    """从比分推导全部体彩玩法结果

    SPF: 胜平负 3=主胜 1=平 0=客胜
    BF: 比分 "2:1"
    BQC: 半全场 胜胜/胜平/胜负/平胜/平平/平负/负胜/负平/负负
    RQSPF: 让球胜平负 (handicap_line让球数)
    OU: 大小球 (需要盘口数据)
    """
    # SPF
    if home_ft > away_ft:
        spf = '3'
    elif home_ft == away_ft:
        spf = '1'
    else:
        spf = '0'

    # BF
    bf = f"{home_ft}:{away_ft}"

    # BQC uses stored sporttery codes: first digit half-time, second digit full-time.
    if home_ht is not None and away_ht is not None:
        if home_ht > away_ht:
            ht_result = '3'
        elif home_ht == away_ht:
            ht_result = '1'
        else:
            ht_result = '0'
        bqc = ht_result + spf
    else:
        bqc = None

    # RQSPF(让球胜平负)
    # handicap_line约定: 正值=主让(不靠谱), 0=不让
    # 优先用goal_line: 负值=主让(如-2), 正值=客让(如+1)
    # 让球后调整: home_adjusted = home_ft + goal_line (goal_line为负时主让)
    effective_handicap = handicap_line  # fallback
    if handicap_line and handicap_line != 0:
        home_adjusted = home_ft - handicap_line
        if home_adjusted > away_ft:
            rqspf = '3'
        elif home_adjusted == away_ft:
            rqspf = '1'
        else:
            rqspf = '0'
    else:
        rqspf = spf  # 无让球时同SPF

    # OU(大小球) — 需要盘口数据
    ou_result = None
    total_goals = home_ft + away_ft
    ou_line = None

    # Try to get O/U line from report
    if db_path and lottery_match_id:
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            c = conn.cursor()
            # Method 1: From prediction report
            active_filter = _active_report_filter(conn)
            c.execute(f"""
                SELECT report_data FROM lottery_analysis_reports
                WHERE lottery_match_id = ? AND report_type = 'prediction'
                {active_filter}
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
            """, (lottery_match_id,))
            row = c.fetchone()
            if row:
                report = json.loads(row[0])
                pp = report.get('play_predictions', {})
                ou = pp.get('ou', {})
                if ou:
                    ou_line = ou.get('best_line', ou.get('line'))
            # Method 2: From lottery_odds ttg
            if ou_line is None:
                c.execute("""
                    SELECT odds_data FROM lottery_odds
                    WHERE lottery_match_id = ? AND play_type = 'ttg'
                    LIMIT 1
                """, (lottery_match_id,))
                row = c.fetchone()
                if row:
                    odds = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    for key in odds:
                        if 'over' in str(key).lower() and '2.5' in str(key):
                            ou_line = 2.5
                            break
            conn.close()
        except Exception:
            pass

    if ou_line is None:
        ou_line = 2.5  # default

    if total_goals > ou_line:
        ou_result = f"大{ou_line}"
    elif total_goals < ou_line:
        ou_result = f"小{ou_line}"
    else:
        ou_result = f"走{ou_line}"

    return {
        'home_goals_ft': home_ft,
        'away_goals_ft': away_ft,
        'home_goals_ht': home_ht,
        'away_goals_ht': away_ht,
        'spf_result': spf,
        'bf_result': bf,
        'bqc_result': bqc,
        'rqspf_result': rqspf,
        'ou_result': ou_result,
    }


def _norm_team(name: str) -> str:
    """队名归一化(用于匹配)"""
    import unicodedata
    n = (name or '').strip().lower()
    n = unicodedata.normalize('NFKD', n)
    n = ''.join(c for c in n if not unicodedata.combining(c))
    special_map = {'ø': 'o', 'å': 'a', 'æ': 'ae', 'ß': 'ss',
                   'đ': 'd', 'ł': 'l', 'ń': 'n', 'ś': 's',
                   'ź': 'z', 'ż': 'z', 'ç': 'c', 'ğ': 'g',
                   'ı': 'i', 'š': 's', 'č': 'c', 'ř': 'r',
                   'ž': 'z', 'ů': 'u', 'ý': 'y', 'é': 'e',
                   'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a',
                   'á': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a',
                   'ó': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o',
                   'ú': 'u', 'û': 'u', 'ü': 'u', 'ì': 'i',
                   'í': 'i', 'î': 'i', 'ï': 'i'}
    n = ''.join(special_map.get(c, c) for c in n)
    suffixes = [' fc', ' cf', ' sc', ' afc', ' united', ' city',
                ' hotspur', ' athletic', ' county', ' town',
                ' rovers', ' villa', ' albion', ' forest', ' palace',
                ' rangers', ' celtic', ' wanderers', ' and hove']
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if n.endswith(suffix):
                n = n[:-len(suffix)]
                changed = True
    return n.strip()


def _safe_int(val):
    """安全转int"""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _loads_json(value: Any, default: Any = None) -> Any:
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _code_label(value: Any, play_type: str = 'spf') -> str:
    text = '' if value is None else str(value)
    if play_type == 'rqspf':
        return RQSPF_LABEL.get(text, RQSPF_LABEL.get(_normalize_rqspf_value(text), text))
    if play_type == 'spf':
        return SPF_LABEL.get(text, text)
    if play_type == 'bqc':
        labels = {
            '33': '胜胜', '31': '胜平', '30': '胜负',
            '13': '平胜', '11': '平平', '10': '平负',
            '03': '负胜', '01': '负平', '00': '负负',
        }
        return labels.get(text, text)
    return text


def _play_label(play_type: Any) -> str:
    labels = {
        'spf': '胜平负',
        'rqspf': '让球胜平负',
        'ou': '大小球',
        'bf': '比分',
        'bqc': '半全场',
    }
    return labels.get(str(play_type or ''), str(play_type or '玩法'))


def _latest_report(conn, match_id: str) -> Dict[str, Any]:
    active_filter = _active_report_filter(conn)
    row = conn.execute(
        f"""
        SELECT report_id, report_data, created_at
        FROM lottery_analysis_reports
        WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
        {active_filter}
        ORDER BY datetime(created_at) DESC, rowid DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if not row:
        return {}
    data = _loads_json(row['report_data'], {})
    if not isinstance(data, dict):
        data = {}
    data['_report_id'] = row['report_id']
    data['_created_at'] = row['created_at']
    return data


def _latest_result(conn, match_id: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT *
        FROM lottery_results
        WHERE lottery_match_id = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    return dict(row) if row else {}


def _latest_match(conn, match_id: str) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM lottery_matches WHERE lottery_match_id = ? LIMIT 1", (match_id,)).fetchone()
    return dict(row) if row else {}


def _latest_odds_payload(conn, match_id: str, play_type: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT odds_data, opening_odds, latest_odds, snapshot_type, update_time
        FROM lottery_odds
        WHERE lottery_match_id = ? AND play_type = ?
        ORDER BY CASE snapshot_type WHEN 'latest' THEN 0 WHEN 'opening' THEN 1 ELSE 2 END,
                 update_time DESC, rowid DESC
        LIMIT 1
        """,
        (match_id, play_type),
    ).fetchone()
    if not row:
        return {}
    current = _loads_json(row['latest_odds'], None) or _loads_json(row['odds_data'], {})
    opening = _loads_json(row['opening_odds'], {})
    return {
        'play_type': play_type,
        'current': current if isinstance(current, dict) else {},
        'opening': opening if isinstance(opening, dict) else {},
        'snapshot_type': row['snapshot_type'],
        'update_time': row['update_time'],
    }


def _implied_probs_from_odds(odds: Dict[str, Any]) -> Dict[str, float]:
    if not isinstance(odds, dict):
        return {}
    values = {}
    for key in ('3', '1', '0'):
        odd = _safe_float(odds.get(key), 0.0)
        if odd > 1:
            values[key] = 1.0 / odd
    total = sum(values.values())
    if total <= 0:
        return {}
    return {key: round(value / total, 4) for key, value in values.items()}


def _prediction_snapshot(report: Dict[str, Any], play_type: str) -> Dict[str, Any]:
    play_predictions = report.get('play_predictions') or {}
    final_prediction = report.get('final_prediction') or {}
    item = play_predictions.get(play_type) or {}
    if play_type == 'spf':
        probs = item.get('probabilities') or final_prediction.get('probabilities') or {}
        return {
            'direction': item.get('direction') or RESULT_MAP.get(final_prediction.get('predicted_result')),
            'probabilities': {
                '3': _safe_float(probs.get('3', probs.get('home_win')), 0.0),
                '1': _safe_float(probs.get('1', probs.get('draw')), 0.0),
                '0': _safe_float(probs.get('0', probs.get('away_win')), 0.0),
            },
            'confidence': final_prediction.get('confidence'),
            'confidence_level': final_prediction.get('confidence_level'),
            'expected_score': final_prediction.get('expected_score') or {},
            'model_vs_odds': report.get('model_vs_odds') or {},
        }
    if play_type == 'rqspf':
        return {
            'direction': item.get('direction') or item.get('recommendation'),
            'handicap': item.get('handicap'),
            'probabilities': item.get('probabilities') or {},
            'confidence': item.get('confidence'),
            'confidence_level': item.get('confidence_level'),
        }
    if play_type == 'ou':
        return {
            'recommendation': item.get('recommendation'),
            'line': item.get('best_line') or item.get('line'),
            'probabilities': item.get('best_line_probs') or item.get('over_under_probs') or {},
            'confidence': item.get('confidence'),
            'confidence_level': item.get('confidence_level'),
            'source': item.get('source'),
        }
    if play_type == 'bqc':
        return {
            'recommendation': item.get('recommendation'),
            'probabilities': item.get('probabilities') or {},
            'half_time': item.get('half_time') or {},
            'confidence': item.get('confidence'),
        }
    if play_type == 'bf':
        return {
            'top3_scores': play_predictions.get('top3_scores') or final_prediction.get('most_likely_scores') or [],
            'expected_score': final_prediction.get('expected_score') or {},
        }
    return item if isinstance(item, dict) else {}


def _latest_intelligence_summary(conn, match_id: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT ij.job_id, ij.status, ip.completeness, ip.missing_required_json,
               ip.package_json, ip.updated_at
        FROM intelligence_jobs ij
        LEFT JOIN intelligence_packages ip ON ip.job_id = ij.job_id
        WHERE ij.lottery_match_id = ?
        ORDER BY ip.updated_at DESC, ij.updated_at DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if not row:
        return {'has_package': False}
    package = _loads_json(row['package_json'], {})
    summary = package.get('summary') if isinstance(package, dict) else {}
    requirements = package.get('requirements') if isinstance(package, dict) else []
    fallback_used = []
    low_confidence = []
    if isinstance(requirements, list):
        for req in requirements:
            if not isinstance(req, dict):
                continue
            key = req.get('key')
            confidence = _safe_float(req.get('confidence'), 0.0)
            if req.get('status') == 'fallback_used' and key:
                fallback_used.append(key)
            if confidence and confidence < 0.45 and key:
                low_confidence.append(key)
    return {
        'has_package': bool(row['updated_at'] or row['completeness'] is not None),
        'job_id': row['job_id'],
        'job_status': row['status'],
        'completeness': row['completeness'] if row['completeness'] is not None else (summary or {}).get('completeness'),
        'strict_completeness': (summary or {}).get('strict_completeness'),
        'average_confidence': (summary or {}).get('average_confidence'),
        'missing_required': _loads_json(row['missing_required_json'], []) or (summary or {}).get('missing_required') or [],
        'fallback_used': fallback_used,
        'low_confidence': low_confidence,
        'updated_at': row['updated_at'],
    }


def _load_cn_to_en(db_path: str) -> dict:
    """加载中文名→英文名映射"""
    from pathlib import Path
    cn_to_en = {}
    linkage_dir = str(Path(db_path).parent / 'linkage')
    cn_file = os.path.join(linkage_dir, 'team_chinese_names.json')
    if os.path.exists(cn_file):
        try:
            with open(cn_file, 'r', encoding='utf-8') as f:
                en_to_cn = json.load(f)
                cn_to_en = {v: k for k, v in en_to_cn.items()}
        except Exception:
            pass

    # sporttery常用简称补充
    SPORTTERY_CN_ALIASES = {
        '尤文': 'Juventus', '斯托克港': 'Stockport County',
        '热刺': 'Tottenham', '哥德堡': 'IFK Goteborg',
        '托特纳姆热刺': 'Tottenham',
    }
    cn_to_en.update(SPORTTERY_CN_ALIASES)
    return cn_to_en


def _update_match_meta(conn, lottery_match_id: str, matched_ev: dict):
    """匹配成功后更新lottery_matches: beijing_time + oddsfe_event_id

    oddsfe的event_start_at是UTC，转北京时间(+8h)存入beijing_time。
    """
    eid = str(matched_ev.get('event_id', ''))
    start_at = matched_ev.get('event_start_at', '')

    updates = []
    params = []

    # 更新oddsfe_event_id(如果原来没有)
    if eid:
        updates.append('oddsfe_event_id = ?')
        params.append(eid)

    # 更新beijing_time: UTC+8h
    if start_at:
        try:
            from datetime import datetime, timedelta as _td
            utc_dt = datetime.fromisoformat(start_at)
            bj_dt = utc_dt + _td(hours=8)
            bj_str = bj_dt.strftime('%Y-%m-%d %H:%M')
            updates.append('beijing_time = ?')
            params.append(bj_str)
        except Exception:
            pass

    if updates:
        params.append(lottery_match_id)
        conn.execute(
            f"UPDATE lottery_matches SET {', '.join(updates)} WHERE lottery_match_id = ?",
            params
        )


def _parse_dt(value: str) -> Optional[datetime]:
    text = str(value or '').strip().replace('T', ' ')
    if not text:
        return None
    for fmt, width in (
        ('%Y-%m-%d %H:%M:%S', 19),
        ('%Y-%m-%d %H:%M', 16),
        ('%Y-%m-%d', 10),
    ):
        try:
            return datetime.strptime(text[:width], fmt)
        except ValueError:
            continue
    return None


def _check_prematch_leakage(report: dict, row, conn) -> str:
    """Check if analysis report may have used post-kickoff data.

    Returns a leakage flag string or empty string if clean.
    Flags: 'report_after_match', 'intel_after_kickoff', 'odds_after_kickoff'.
    """
    match_key = _row_value(row, 'lottery_match_id')
    if not match_key:
        return ''

    # Get kickoff time
    kickoff_row = conn.execute(
        "SELECT beijing_time, match_date FROM lottery_matches WHERE lottery_match_id = ?",
        (match_key,),
    ).fetchone()
    if not kickoff_row:
        return ''
    kickoff = _parse_dt(str(kickoff_row['beijing_time'] or ''))
    if not kickoff:
        md = str(kickoff_row['match_date'] or '').strip()[:10]
        kickoff = _parse_dt(md)
    if not kickoff:
        return ''

    cutoff = kickoff + timedelta(minutes=15)
    flags = []

    # Check report for captured_at timestamps after kickoff
    def _scan_timestamps(data, depth=0):
        if depth > 4 or not isinstance(data, dict):
            return
        for key in ('captured_at', 'updated_at'):
            if key in data:
                ts = _parse_dt(str(data[key]))
                if ts and ts > cutoff:
                    flags.append(f'{key}_after_kickoff')
                    return
        for v in data.values():
            if isinstance(v, dict):
                _scan_timestamps(v, depth + 1)

    _scan_timestamps(report)

    # Check intelligence packages
    try:
        intel_row = conn.execute(
            """SELECT ip.updated_at FROM intelligence_packages ip
               JOIN intelligence_jobs ij ON ip.job_id = ij.job_id
               WHERE ij.lottery_match_id = ?
               ORDER BY ip.updated_at DESC LIMIT 1""",
            (match_key,),
        ).fetchone()
        if intel_row:
            intel_ts = _parse_dt(str(intel_row['updated_at'] or ''))
            if intel_ts and intel_ts > cutoff:
                flags.append('intel_after_kickoff')
    except Exception:
        pass

    if flags:
        return '|'.join(sorted(set(flags)))
    return ''


def _validate_predictions(db_path: str, match_dates: list) -> dict:
    """验证预测 — 从lottery_analysis_reports取预测，对比lottery_results

    支持回填模式：如果match_dates为空，则验证所有有结果但未验证的比赛。
    """
    validated = 0
    correct_count = 0

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_parts = ["ar.report_type IN ('prediction', 'full')"]
        params = []
        if match_dates:
            placeholders = ','.join(['?'] * len(match_dates))
            where_parts.append(f"substr(COALESCE(lm.beijing_time, lm.match_date), 1, 10) IN ({placeholders})")
            params.extend(match_dates)
        else:
            # 回填模式：验证所有有结果但未验证的
            where_parts.append("""
                NOT EXISTS (
                    SELECT 1
                    FROM lottery_validation lv
                    WHERE lv.lottery_match_id = ar.lottery_match_id
                )
            """)
        where_sql = "WHERE " + " AND ".join(where_parts)

        cursor.execute(f"""
            SELECT ar.lottery_match_id, ar.report_data,
                   lm.home_team_cn, lm.away_team_cn, lm.league_name_cn,
                   lm.handicap_line,
                   lr.spf_result, lr.bf_result, lr.bqc_result, lr.rqspf_result,
                   lr.home_goals_ft, lr.away_goals_ft,
                   lr.home_goals_ht, lr.away_goals_ht
            FROM lottery_analysis_reports ar
            JOIN lottery_matches lm ON ar.lottery_match_id = lm.lottery_match_id
            JOIN lottery_results lr ON ar.lottery_match_id = lr.lottery_match_id
            {where_sql}
              AND ar.rowid = (
                  SELECT ar2.rowid
                  FROM lottery_analysis_reports ar2
                  WHERE ar2.lottery_match_id = ar.lottery_match_id
                    AND ar2.report_type IN ('prediction', 'full')
                  ORDER BY ar2.created_at DESC, ar2.rowid DESC
                  LIMIT 1
              )
        """, params)

        rows = cursor.fetchall()

        for row in rows:
            try:
                report = json.loads(row['report_data']) if isinstance(row['report_data'], str) else row['report_data']

                # Extract prediction — support multiple report formats
                predicted = ''
                probabilities = {}
                confidence = 0
                confidence_level = 'low'
                confidence_tier = None

                # Format 1: final_prediction.predicted_result
                fp = report.get('final_prediction', {})
                if fp.get('predicted_result'):
                    predicted = fp['predicted_result']
                    probabilities = fp.get('probabilities', {})
                    confidence = fp.get('confidence', 0)
                    confidence_level = fp.get('confidence_level', 'low')
                    confidence_tier = fp.get('confidence_tier')

                # Format 2: analyses.spf.recommendation
                if not predicted:
                    spf = report.get('analyses', {}).get('spf', {})
                    if spf.get('recommendation'):
                        predicted = spf['recommendation']
                        probabilities = spf.get('probabilities', {})
                        confidence = spf.get('confidence', 0)
                        confidence_level = spf.get('confidence_level', 'low')

                # Format 3: recommendations.spf
                if not predicted:
                    rec = report.get('recommendations', {}).get('spf', {})
                    if rec.get('recommendation'):
                        predicted = rec['recommendation']
                        probabilities = rec.get('probabilities', {})
                        confidence = rec.get('confidence', 0)

                # Pre-match leakage check
                leakage_flag = _check_prematch_leakage(report, row, conn)

                # Translate Chinese recommendations
                if predicted in CN_RESULT_MAP:
                    predicted = {'3': 'home_win', '1': 'draw', '0': 'away_win'}[CN_RESULT_MAP[predicted]]

                # If still no prediction, derive from probabilities
                if not predicted and probabilities:
                    predicted = max(probabilities, key=probabilities.get)

                if not predicted:
                    continue

                actual = row['spf_result']

                # Map result labels to SPF codes
                predicted_spf = RESULT_MAP.get(predicted, predicted)
                if not _is_valid_validation_text(predicted_spf) or not _is_valid_validation_text(actual):
                    _delete_validation(conn, row['lottery_match_id'], 'spf')
                    continue

                is_correct = (predicted_spf == actual)
                if is_correct:
                    correct_count += 1

                # Compute Brier score
                brier = _compute_brier(probabilities, actual)

                # Determine scenario
                scenario = _determine_scenario(row['league_name_cn'])

                # Save validation
                # predicted_prob: highest probability for predicted outcome
                pred_prob = probabilities.get(predicted, 0) if isinstance(probabilities, dict) else 0
                validation = {
                    'lottery_match_id': row['lottery_match_id'],
                    'play_type': 'spf',
                    'predicted_result': predicted_spf,
                    'actual_result': actual,
                    'is_correct': is_correct,
                    'confidence': confidence,
                    'confidence_level': confidence_level,
                    'brier_score': brier,
                    'scenario_type': scenario,
                    'probabilities': probabilities,
                    'predicted_prob': pred_prob,
                    'home_goals': row['home_goals_ft'],
                    'away_goals': row['away_goals_ft'],
                    'confidence_tier': confidence_tier or _compute_tier_from_validation(confidence, probabilities, row, conn, 'spf'),
                    'leakage_flag': leakage_flag,
                }

                _save_validation(conn, validation)
                validated += 1

                # O/U validation — validate over/under predictions
                if row['home_goals_ft'] is not None and row['away_goals_ft'] is not None:
                    _validate_ou_for_report(conn, report, row, scenario, leakage_flag)
                    _validate_bqc_for_report(conn, report, row, scenario, leakage_flag)
                    _validate_bf_for_report(conn, report, row, scenario, leakage_flag)
                    _validate_rqspf_for_report(conn, report, row, scenario, leakage_flag)

            except Exception as e:
                logger.debug(f'验证失败 {row["lottery_match_id"]}: {e}')

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f'预测验证失败: {e}')
        return {'validated': validated, 'correct': correct_count, 'error': str(e)}

    accuracy = round(correct_count / validated * 100, 1) if validated > 0 else 0
    logger.info(f'验证完成: {validated}场, {correct_count}场正确, 准确率{accuracy}%')

    return {
        'validated': validated,
        'correct': correct_count,
        'accuracy': accuracy,
    }


def _backfill_results_from_oddsfe(db_path: str) -> dict:
    """从oddsfe API回填缺失结果 — 精准按日期调API，不加载全量DB

    对每个缺少结果的closed比赛，按match_date调schedule API获取赛果，
    再调event API获取score_details(半全场)，推导全部玩法结果。
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 找缺少完整结果的closed/finished比赛
        cursor.execute("""
            SELECT lm.lottery_match_id, lm.match_date,
                   lm.home_team_cn, lm.away_team_cn,
                   lm.oddsfe_event_id, lm.handicap_line, lm.beijing_time
            FROM lottery_matches lm
            WHERE lm.sell_status IN ('closed', 'finished')
            AND (
                lm.lottery_match_id NOT IN (SELECT lottery_match_id FROM lottery_results)
                OR lm.lottery_match_id IN (
                    SELECT lottery_match_id FROM lottery_results WHERE bf_result IS NULL
                )
            )
            ORDER BY lm.match_date
        """)
        missing = [dict(r) for r in cursor.fetchall()]

        if not missing:
            conn.close()
            return {'status': 'ok', 'backfilled': 0}

        # 按日期分组 — 同时考虑match_date和beijing_time日期
        # 因为match_date可能与beijing_time日期不一致
        from collections import defaultdict
        by_date = defaultdict(list)
        for m in missing:
            by_date[m['match_date']].append(m)
            # 如果beijing_time日期与match_date不同，也加入beijing_time日期的分组
            bj_time = m.get('beijing_time') or ''
            bj_date = bj_time[:10] if len(bj_time) >= 10 else ''
            if bj_date and bj_date != m['match_date']:
                by_date[bj_date].append(m)

        cn_to_en = _load_cn_to_en(db_path)
        backfilled = 0
        session = requests.Session()
        session.trust_env = False

        for match_date, matches in by_date.items():
            logger.info('Backfill %s: %d missing matches', match_date, len(matches))

            # 去重: 同一lottery_match_id只处理一次
            seen_ids = set()
            unique_matches = []
            for m in matches:
                if m['lottery_match_id'] not in seen_ids:
                    seen_ids.add(m['lottery_match_id'])
                    unique_matches.append(m)
            matches = unique_matches

            # 调schedule API — 查当天和前后各一天(覆盖UTC+8时区偏移)
            schedule_data = None
            for offset in [-1, 0, 1]:
                try:
                    query_date = str(date.fromisoformat(match_date) + timedelta(days=offset))
                    sd = _oddsfe_fetch_schedule(query_date)
                    if sd:
                        if schedule_data is None:
                            schedule_data = sd
                        else:
                            schedule_data.extend(sd)
                except ValueError:
                    continue

            if not schedule_data:
                logger.warning('Backfill %s: schedule API failed', match_date)
                continue

            # 提取FINISHED比赛
            finished = []
            for tournament in schedule_data:
                if isinstance(tournament, dict):
                    for ev in tournament.get('events', []):
                        if ev.get('event_status') == 'FINISHED':
                            finished.append(ev)

            if not finished:
                continue

            # 构建队名索引
            oddsfe_by_name = {}
            for ev in finished:
                h_raw = ev.get('team_home_name', '')
                a_raw = ev.get('team_away_name', '')
                h_norm = _norm_team(h_raw)
                a_norm = _norm_team(a_raw)
                oddsfe_by_name[(h_norm, a_norm)] = ev

            for lm in matches:
                # 优先oddsfe_event_id
                matched_ev = None
                if lm.get('oddsfe_event_id'):
                    for ev in finished:
                        if str(ev.get('event_id')) == str(lm['oddsfe_event_id']):
                            matched_ev = ev
                            break

                # 队名匹配
                if not matched_ev:
                    home_en = cn_to_en.get(lm['home_team_cn']) or lm.get('home_team_cn', '')
                    away_en = cn_to_en.get(lm['away_team_cn']) or lm.get('away_team_cn', '')
                    h_norm = _norm_team(home_en)
                    a_norm = _norm_team(away_en)
                    matched_ev = oddsfe_by_name.get((h_norm, a_norm))

                if not matched_ev:
                    continue

                home_goals = _safe_int(matched_ev.get('event_score_home'))
                away_goals = _safe_int(matched_ev.get('event_score_away'))
                if home_goals is None or away_goals is None:
                    continue

                # 调event API拿score_details
                score_details = _oddsfe_fetch_score_details(session, matched_ev.get('event_id', ''))
                ht_h, ht_a = _parse_score_details(score_details)

                # 交叉验证: score_details全场比分应与event_score一致
                if score_details:
                    sd_ft_h, sd_ft_a = _parse_fulltime_from_score_details(score_details)
                    if sd_ft_h is not None and sd_ft_a is not None:
                        if sd_ft_h != home_goals or sd_ft_a != away_goals:
                            logger.warning('赛果不一致 %s: event_score=%d:%d, score_details全场=%d:%d, 使用score_details',
                                           lm['lottery_match_id'], home_goals, away_goals, sd_ft_h, sd_ft_a)
                            home_goals = sd_ft_h
                            away_goals = sd_ft_a

                # 半场比分合理性检查
                if ht_h is not None and ht_a is not None:
                    if ht_h > home_goals or ht_a > away_goals:
                        logger.warning('半场比分异常 %s: HT %d:%d > FT %d:%d, 置空半场',
                                       lm['lottery_match_id'], ht_h, ht_a, home_goals, away_goals)
                        ht_h, ht_a = None, None

                # 推导全部玩法 — 用goal_line算RQSPF
                effective_hcp = _get_effective_handicap(conn, lm['lottery_match_id'], lm.get('handicap_line', 0))
                results = _derive_all_play_types(home_goals, away_goals, ht_h, ht_a, effective_hcp,
                                          db_path=db_path, lottery_match_id=lm['lottery_match_id'])

                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO lottery_results
                        (lottery_match_id, home_goals_ft, away_goals_ft,
                         home_goals_ht, away_goals_ht,
                         spf_result, bf_result, bqc_result, rqspf_result, ou_result)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lm['lottery_match_id'],
                        results['home_goals_ft'], results['away_goals_ft'],
                        results['home_goals_ht'], results['away_goals_ht'],
                        results['spf_result'], results['bf_result'],
                        results['bqc_result'], results['rqspf_result'],
                        results.get('ou_result'),
                    ))
                    backfilled += 1

                    # 同时更新match meta: beijing_time + oddsfe_event_id
                    _update_match_meta(conn, lm['lottery_match_id'], matched_ev)
                except Exception as e:
                    logger.debug('回填失败 %s: %s', lm['lottery_match_id'], e)

                time.sleep(0.1)

        conn.commit()
        conn.close()

        if backfilled > 0:
            logger.info('oddsfe结果回填: %d场', backfilled)

        return {'status': 'ok', 'saved': backfilled}

    except Exception as e:
        logger.error('oddsfe结果回填失败: %s', e)
        return {'status': 'error', 'error': str(e)}


def _compute_tier_from_validation(confidence, probabilities, row, conn, play_type) -> str:
    """Compute confidence_tier during validation"""
    try:
        match_id = row.get('lottery_match_id', '')
        market_alignment = None
        if play_type == 'spf' and probabilities:
            odds_payload = _latest_odds_payload(conn, match_id, 'spf')
            market = _market_top_from_odds(odds_payload.get('current') or {})
            predicted = max(probabilities, key=probabilities.get) if isinstance(probabilities, dict) else ''
            if market.get('top'):
                market_alignment = str(market['top']) == predicted
        intel_completeness = 0
        intel = _latest_intelligence_summary(conn, match_id)
        intel_completeness = _safe_float(intel.get('completeness'), 0.0)
        has_contradictions = False
        report_row = conn.execute('''
            SELECT report_data FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
              AND (is_stale = 0 OR is_stale IS NULL)
            ORDER BY created_at DESC LIMIT 1
        ''', (match_id,)).fetchone()
        if report_row:
            report = json.loads(report_row[0]) if isinstance(report_row[0], str) else report_row[0]
            ms = report.get('match_script', {})
            contradictions = ms.get('contradictions', [])
            has_contradictions = any(c.get('severity') == 'high' for c in contradictions if isinstance(c, dict))
        return compute_confidence_tier(
            confidence=confidence,
            market_alignment=market_alignment,
            intel_completeness=intel_completeness,
            has_contradictions=has_contradictions,
            play_type=play_type,
        )
    except Exception:
        return 'low'


def _determine_scenario(league_name_cn: str) -> str:
    """根据联赛名确定赛事场景"""
    if not league_name_cn:
        return 'unknown'
    league = league_name_cn
    if '友谊' in league or '国际赛' in league:
        return 'friendly_intl'
    if '世预' in league or '欧预' in league or '非预' in league or '亚预' in league or '南美预' in league:
        return 'qualifier'
    if '欧国联' in league:
        return 'nations_league'
    if '世界杯' in league or '欧洲杯' in league or '亚洲杯' in league or '美洲杯' in league or '非洲杯' in league:
        return 'international_cup'
    if '欧冠' in league or '欧联' in league or '欧协' in league or '解放者' in league or '亚冠' in league:
        return 'continental_cup'
    if '杯' in league:
        return 'domestic_cup'
    return 'league'


def _compute_brier(probabilities: dict, actual: str) -> float:
    """计算Brier score"""
    # actual: '3'/'1'/'0'
    actual_vec = {'3': 0, '1': 0, '0': 0}
    if actual in actual_vec:
        actual_vec[actual] = 1

    # 概率键映射
    key_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    pred_vec = {'3': 0, '1': 0, '0': 0}
    for k, v in probabilities.items():
        code = key_map.get(k, k)
        if code in pred_vec:
            pred_vec[code] = v

    brier = sum((pred_vec[k] - actual_vec[k]) ** 2 for k in actual_vec)
    return round(brier, 4)


def _compute_ou_brier(ou_probs: dict, actual_ou: str) -> float:
    """计算O/U Brier score — 二分类: 大 vs 小"""
    over_prob = ou_probs.get('over', ou_probs.get('大', 0))
    under_prob = ou_probs.get('under', ou_probs.get('小', 0))
    # Normalize if not summing to ~1
    total = over_prob + under_prob
    if total > 0:
        over_prob /= total
        under_prob /= total
    actual_over = 1 if '大' in actual_ou else 0
    brier = (over_prob - actual_over) ** 2 + (under_prob - (1 - actual_over)) ** 2
    return round(brier, 4)


def _market_top_from_odds(odds: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(odds, dict):
        return {}
    numeric = {}
    for key, value in odds.items():
        if key == 'goal_line':
            continue
        odd = _safe_float(value, 0.0)
        if odd > 1:
            numeric[str(key)] = odd
    if not numeric:
        return {}
    implied_raw = {key: 1.0 / odd for key, odd in numeric.items()}
    total = sum(implied_raw.values())
    implied = {key: round(value / total, 4) for key, value in implied_raw.items()} if total > 0 else {}
    top = max(implied, key=implied.get) if implied else min(numeric, key=numeric.get)
    return {
        'top': top,
        'top_label': _code_label(top),
        'top_probability': implied.get(top),
        'implied_probabilities': implied,
    }


def _confidence_bucket(value: Any) -> str:
    confidence = _safe_float(value, 0.0)
    if confidence >= 0.62:
        return 'high'
    if confidence >= 0.48:
        return 'medium'
    if confidence > 0:
        return 'low'
    return 'unknown'


def _confidence_bucket_label(value: str) -> str:
    return {
        'high': '高',
        'medium': '中等',
        'low': '低',
        'unknown': '未知',
    }.get(str(value or ''), str(value or '未知'))


def compute_confidence_tier(
    confidence: float,
    market_alignment: bool = None,
    intel_completeness: float = 0,
    has_contradictions: bool = False,
    play_type: str = 'spf',
) -> str:
    """Compute recalibrated confidence tier: strong/medium/low/avoid

    Rules:
    - strong: direction+market+intel at least 3-axis consistent, no contradictions
    - medium: main axis clear but one key uncertainty
    - low: insufficient evidence, show tendency only
    - avoid: conflicting factors, no strong conclusion
    """
    conf = _safe_float(confidence, 0.0)

    # Check for contradictions → avoid
    if has_contradictions:
        return 'avoid'

    # Count consistent axes
    consistent_axes = 0
    if conf >= 0.55:
        consistent_axes += 1  # model direction
    if market_alignment is True:
        consistent_axes += 1  # market agrees
    if intel_completeness >= 80:
        consistent_axes += 1  # intelligence is solid
    elif intel_completeness >= 60:
        consistent_axes += 0.5  # partial intel

    # BF and BQC are inherently harder — lower the bar
    if play_type in ('bf', 'bqc'):
        if consistent_axes >= 2 and conf >= 0.45:
            return 'medium'
        if conf >= 0.35:
            return 'low'
        return 'avoid'

    # SPF, RQSPF, O/U
    if consistent_axes >= 3 and conf >= 0.55:
        return 'strong'
    if consistent_axes >= 2 and conf >= 0.50:
        return 'medium'
    if conf >= 0.40:
        return 'low'
    return 'avoid'


CONFIDENCE_TIER_LABELS = {
    'strong': '强推荐',
    'medium': '中推荐',
    'low': '弱倾向',
    'avoid': '建议观望',
}

CONFIDENCE_TIER_DISPLAY_RULES = {
    'strong': {'show_stars': True, 'max_stars': 4, 'show_recommendation': True},
    'medium': {'show_stars': True, 'max_stars': 3, 'show_recommendation': True},
    'low': {'show_stars': False, 'show_recommendation': True, 'show_risk': True},
    'avoid': {'show_stars': False, 'show_recommendation': False, 'show_warning': '分歧大/建议观望'},
}


def _pressure_level_label(value: str) -> str:
    return {
        'very_high': '极高',
        'high': '高',
        'medium': '中',
        'low': '低',
        'unknown': '未知',
    }.get(str(value or ''), str(value or '未知'))


def _pressure_reason_label(value: str) -> str:
    return {
        'missing_standing': '缺少实时积分',
        'opening_round_positioning': '首轮定位阶段',
        'win_can_push_direct_qualification': '赢球可推动直接晋级',
        'needs_points_before_final_round': '末轮前需要抢分',
        'group_shape_still_open': '小组形势仍开放',
        'protect_or_improve_draw_position': '保护或提升落位',
        'third_place_and_goal_difference_pressure': '第三名与净胜球压力',
        'must_win_or_chase_margin': '必须赢球或追净胜球',
        'live_world_cup_group_pressure_context': '实时小组压力',
        'no_directional_group_pressure_edge': '小组压力差异不明显',
    }.get(str(value or ''), str(value or '晋级压力'))


def _prob_gap(probabilities: Dict[str, Any]) -> Optional[float]:
    values = sorted([_safe_float(v, 0.0) for v in (probabilities or {}).values()], reverse=True)
    if len(values) < 2:
        return None
    return round(values[0] - values[1], 4)


def _world_cup_review_context(report: Dict[str, Any]) -> Dict[str, Any]:
    wc = report.get('world_cup_context') or {}
    if not isinstance(wc, dict):
        return {}
    group_ctx = wc.get('group_stage_context') or {}
    pressure = wc.get('pressure') or {}
    data_status = wc.get('data_status') or {}
    context = {
        'source': data_status.get('mode') or data_status.get('source'),
        'group': (wc.get('group') or {}).get('group') or group_ctx.get('group'),
        'matchday': group_ctx.get('matchday') or (wc.get('match') or {}).get('matchday'),
        'group_progress': {
            'finished': group_ctx.get('group_matches_finished'),
            'total': group_ctx.get('group_matches_total'),
        },
        'pressure': {
            'home': (pressure.get('home') or {}).get('level'),
            'away': (pressure.get('away') or {}).get('level'),
            'home_reason': (pressure.get('home') or {}).get('reason'),
            'away_reason': (pressure.get('away') or {}).get('reason'),
        },
        'notes': pressure.get('notes') or [],
    }
    pressure_values = context.get('pressure') or {}
    has_meaningful_context = any([
        context.get('source'),
        context.get('group'),
        context.get('matchday'),
        (context.get('group_progress') or {}).get('finished') is not None,
        (context.get('group_progress') or {}).get('total') is not None,
        pressure_values.get('home'),
        pressure_values.get('away'),
        bool(context.get('notes')),
    ])
    return context if has_meaningful_context else {}


def _factor_review(
    validation: Dict[str, Any],
    report: Dict[str, Any],
    market: Dict[str, Any],
    intel: Dict[str, Any],
    wc_context: Dict[str, Any],
) -> Dict[str, Any]:
    play_type = validation.get('play_type') or 'unknown'
    predicted = str(validation.get('predicted_result') or '')
    actual = str(validation.get('actual_result') or '')
    prediction = _prediction_snapshot(report, play_type)
    probabilities = prediction.get('probabilities') or validation.get('probabilities') or {}
    pred_prob = _safe_float(validation.get('predicted_prob'), 0.0) or _safe_float(prediction.get('confidence'), 0.0)
    market_top = market.get('top')
    market_alignment = None
    if market_top and play_type in {'spf', 'rqspf'}:
        market_alignment = str(market_top) == predicted
    intel_completeness = _safe_float(intel.get('completeness'), 0.0)
    strict_completeness = _safe_float(intel.get('strict_completeness'), 0.0)

    checks = [
        {
            'factor': 'confidence',
            'state': _confidence_bucket(pred_prob),
            'value': round(pred_prob, 4) if pred_prob else None,
            'prob_gap': _prob_gap(probabilities),
        },
        {
            'factor': 'market_alignment',
            'state': 'aligned' if market_alignment is True else 'diverged' if market_alignment is False else 'unknown',
            'market_top': market_top,
            'market_top_probability': market.get('top_probability'),
        },
        {
            'factor': 'intelligence_quality',
            'state': 'complete' if intel_completeness >= 100 and strict_completeness >= 75 else 'partial' if intel.get('has_package') else 'missing',
            'completeness': intel.get('completeness'),
            'strict_completeness': intel.get('strict_completeness'),
            'fallback_used': intel.get('fallback_used') or [],
            'low_confidence': intel.get('low_confidence') or [],
        },
    ]
    if wc_context:
        checks.append({
            'factor': 'world_cup_context',
            'state': 'available',
            'group': wc_context.get('group'),
            'matchday': wc_context.get('matchday'),
            'home_pressure': (wc_context.get('pressure') or {}).get('home'),
            'away_pressure': (wc_context.get('pressure') or {}).get('away'),
        })

    tags = [f'play:{play_type}', 'result:correct' if validation.get('is_correct') else 'result:wrong']
    scenario = validation.get('scenario_type')
    if scenario:
        tags.append(f'scenario:{scenario}')
    bucket = _confidence_bucket(pred_prob)
    tags.append(f'confidence:{bucket}')
    if market_alignment is not None:
        tags.append('market:aligned' if market_alignment else 'market:diverged')
    if intel.get('fallback_used'):
        tags.append('intel:fallback_used')
    if intel.get('low_confidence'):
        tags.append('intel:low_confidence')
    if wc_context:
        tags.append('context:world_cup')
        if wc_context.get('matchday'):
            tags.append(f"world_cup:matchday_{wc_context.get('matchday')}")
        pressure = wc_context.get('pressure') or {}
        for side in ('home', 'away'):
            if pressure.get(side):
                tags.append(f'pressure:{side}_{pressure.get(side)}')

    action_items = []
    if not validation.get('is_correct'):
        if bucket == 'high':
            action_items.append('review_high_confidence_error')
        if market_alignment is False:
            action_items.append('review_market_divergence_weight')
        if intel.get('fallback_used') or intel.get('low_confidence'):
            action_items.append('improve_low_confidence_intelligence')
        if play_type in {'bf', 'bqc', 'rqspf'}:
            action_items.append('separate_derivative_play_risk')
    else:
        action_items.append('keep_as_positive_case')
        if bucket == 'low':
            action_items.append('mark_low_confidence_positive')

    reason_parts = []
    play_label = _play_label(play_type)
    if play_type == 'bf':
        candidates = validation.get('score_candidates') or []
        candidate_scores = [
            item.get('score')
            for item in candidates
            if isinstance(item, dict) and item.get('score')
        ]
        candidate_text = ' / '.join(candidate_scores) if candidate_scores else _code_label(predicted, play_type)
        hit_rank = validation.get('score_candidate_hit_rank')
        if validation.get('is_correct'):
            rank_text = f"候选第{hit_rank}命中" if hit_rank else "候选命中"
            reason_parts.append(f"{play_label}{rank_text}：候选{candidate_text}，实际{_code_label(actual, play_type)}。")
        else:
            reason_parts.append(f"{play_label}候选未命中：候选{candidate_text}，实际{_code_label(actual, play_type)}。")
    elif validation.get('is_correct'):
        reason_parts.append(f"{play_label}命中：预测{_code_label(predicted, play_type)}，实际{_code_label(actual, play_type)}。")
    else:
        reason_parts.append(f"{play_label}未命中：预测{_code_label(predicted, play_type)}，实际{_code_label(actual, play_type)}。")
    if pred_prob:
        reason_parts.append(f"预测置信约{pred_prob:.1%}，属于{_confidence_bucket_label(bucket)}置信。")
    if market_alignment is True:
        reason_parts.append("模型方向与赔率主方向一致。")
    elif market_alignment is False:
        reason_parts.append(f"模型方向与赔率主方向不一致，赔率倾向{market.get('top_label') or market_top}。")
    weak = []
    weak.extend((intel.get('fallback_used') or [])[:3])
    weak.extend((intel.get('low_confidence') or [])[:3])
    if weak:
        reason_parts.append(f"存在低置信/兜底情报：{', '.join(sorted(set(weak)))}。")
    if wc_context and (wc_context.get('pressure') or {}).get('home'):
        pressure = wc_context.get('pressure') or {}
        home_pressure = _pressure_level_label(pressure.get('home'))
        away_pressure = _pressure_level_label(pressure.get('away'))
        home_reason = _pressure_reason_label(pressure.get('home_reason'))
        away_reason = _pressure_reason_label(pressure.get('away_reason'))
        reason_parts.append(f"世界杯小组语境：主队{home_pressure}压（{home_reason}），客队{away_pressure}压（{away_reason}）。")

    return {
        'prediction': prediction,
        'factor_checks': checks,
        'learning_tags': sorted(set(tags)),
        'action_items': sorted(set(action_items)),
        'reason_text': ' '.join(reason_parts),
    }


def _build_structured_review(conn, validation: Dict[str, Any], attribution: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    match_id = str(validation.get('lottery_match_id') or '')
    play_type = validation.get('play_type') or 'unknown'
    report = _latest_report(conn, match_id)
    match = _latest_match(conn, match_id)
    result = _latest_result(conn, match_id)
    odds_payload = _latest_odds_payload(conn, match_id, 'rqspf' if play_type == 'rqspf' else 'spf')
    market = _market_top_from_odds(odds_payload.get('current') or {})
    intel = _latest_intelligence_summary(conn, match_id)
    wc_context = _world_cup_review_context(report)
    factor_review = _factor_review(validation, report, market, intel, wc_context)
    score = None
    if result.get('home_goals_ft') is not None and result.get('away_goals_ft') is not None:
        score = f"{result.get('home_goals_ft')}-{result.get('away_goals_ft')}"
    return {
        'version': 'post_match_review_v1',
        'match': {
            'lottery_match_id': match_id,
            'match_num': match.get('match_num'),
            'league': match.get('league_name_cn'),
            'home_team': match.get('home_team_cn'),
            'away_team': match.get('away_team_cn'),
            'match_date': match.get('match_date'),
            'beijing_time': match.get('beijing_time'),
            'oddsfe_event_id': match.get('oddsfe_event_id'),
        },
        'outcome': {
            'play_type': play_type,
            'predicted_result': validation.get('predicted_result'),
            'actual_result': validation.get('actual_result'),
            'is_correct': None if validation.get('is_correct') is None else bool(validation.get('is_correct')),
            'score': score,
            'half_score': (
                f"{result.get('home_goals_ht')}-{result.get('away_goals_ht')}"
                if result.get('home_goals_ht') is not None and result.get('away_goals_ht') is not None else None
            ),
            'spf_result': result.get('spf_result'),
            'rqspf_result': result.get('rqspf_result'),
            'ou_result': result.get('ou_result'),
        },
        'market_snapshot': {
            'play_type': odds_payload.get('play_type'),
            'current_odds': odds_payload.get('current') or {},
            'opening_odds': odds_payload.get('opening') or {},
            'implied_probabilities': _implied_probs_from_odds(odds_payload.get('current') or {}),
            'market_top': market.get('top'),
            'market_top_label': market.get('top_label'),
            'market_top_probability': market.get('top_probability'),
            'update_time': odds_payload.get('update_time'),
        },
        'intelligence_quality': intel,
        'world_cup_context': wc_context,
        'attribution': attribution or {},
        **factor_review,
    }


def _save_validation(conn, validation: dict):
    """写入lottery_validation(去重: 同一match_id+play_type只保留最新)"""
    if (
        not _is_valid_validation_text(validation.get('predicted_result'))
        or not _is_valid_validation_text(validation.get('actual_result'))
    ):
        _delete_validation(conn, validation['lottery_match_id'], validation['play_type'])
        return

    # 先删除旧记录再插入
    conn.execute("""
        DELETE FROM lottery_validation
        WHERE lottery_match_id = ? AND play_type = ?
    """, (validation['lottery_match_id'], validation['play_type']))

    columns = {row[1] for row in conn.execute("PRAGMA table_info(lottery_validation)").fetchall()}
    settlement_grade = validation.get('settlement_grade')
    top3_score_hit = validation.get('top3_score_hit')
    goal_bucket_hit = validation.get('goal_bucket_hit')
    margin_bucket_hit = validation.get('margin_bucket_hit')
    btts_hit = validation.get('btts_hit')
    ou_consistency_hit = validation.get('ou_consistency_hit')

    # Build column list dynamically based on available columns
    insert_cols = [
        'lottery_match_id', 'play_type', 'predicted_result', 'actual_result',
        'is_correct', 'predicted_prob', 'brier_score', 'scenario_type',
    ]
    insert_vals = [
        validation['lottery_match_id'],
        validation['play_type'],
        validation['predicted_result'],
        validation['actual_result'],
        validation['is_correct'],
        validation.get('predicted_prob', 0),
        validation.get('brier_score', 0),
        validation.get('scenario_type', 'unknown'),
    ]

    if 'confidence' in columns:
        insert_cols.append('confidence')
        insert_vals.append(validation.get('confidence', 0))

    if 'settlement_grade' in columns and settlement_grade:
        insert_cols.append('settlement_grade')
        insert_vals.append(settlement_grade)

    if 'top3_score_hit' in columns and top3_score_hit is not None:
        insert_cols.append('top3_score_hit')
        insert_vals.append(top3_score_hit)

    if 'goal_bucket_hit' in columns and goal_bucket_hit is not None:
        insert_cols.append('goal_bucket_hit')
        insert_vals.append(goal_bucket_hit)

    if 'margin_bucket_hit' in columns and margin_bucket_hit is not None:
        insert_cols.append('margin_bucket_hit')
        insert_vals.append(margin_bucket_hit)

    if 'btts_hit' in columns and btts_hit is not None:
        insert_cols.append('btts_hit')
        insert_vals.append(btts_hit)

    if 'ou_consistency_hit' in columns and ou_consistency_hit is not None:
        insert_cols.append('ou_consistency_hit')
        insert_vals.append(ou_consistency_hit)

    confidence_tier = validation.get('confidence_tier')
    if confidence_tier and 'confidence_tier' not in columns:
        conn.execute("ALTER TABLE lottery_validation ADD COLUMN confidence_tier TEXT")
        columns.add('confidence_tier')
    if 'confidence_tier' in columns and confidence_tier:
        insert_cols.append('confidence_tier')
        insert_vals.append(confidence_tier)

    # Pre-match leakage flag
    leakage_flag = validation.get('leakage_flag')
    if leakage_flag:
        if 'leakage_flag' not in columns:
            conn.execute("ALTER TABLE lottery_validation ADD COLUMN leakage_flag TEXT")
            columns.add('leakage_flag')
        if 'leakage_flag' in columns:
            insert_cols.append('leakage_flag')
            insert_vals.append(leakage_flag)

    insert_cols.append('validated_at')
    insert_vals_str = ', '.join(['?'] * len(insert_vals) + ["datetime('now')"])
    col_str = ', '.join(insert_cols)

    conn.execute(
        f"INSERT INTO lottery_validation ({col_str}) VALUES ({insert_vals_str})",
        insert_vals,
    )
    _save_foundation_review(conn, validation)


def _save_foundation_review(conn, validation: dict, attribution: dict = None) -> None:
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='post_match_reviews'"
        ).fetchone()
        if not exists:
            return

        import hashlib

        match_key = validation.get('lottery_match_id')
        play_type = validation.get('play_type') or 'unknown'
        if not match_key:
            return

        review_id = 'review_' + hashlib.sha256(f'{match_key}|{play_type}'.encode('utf-8')).hexdigest()[:32]
        structured_review = {}
        try:
            structured_review = _build_structured_review(conn, validation, attribution)
        except Exception as e:
            logger.debug('structured review skipped: %s', e)

        review_json = {
            'validation': validation,
            'attribution': attribution or {},
            'structured_review': structured_review,
        }
        if structured_review:
            review_json['reason_text'] = structured_review.get('reason_text')
            review_json['learning_tags'] = structured_review.get('learning_tags') or []
            review_json['action_items'] = structured_review.get('action_items') or []
        conn.execute("""
            INSERT OR REPLACE INTO post_match_reviews
            (review_id, match_key, play_type, predicted_result, actual_result,
             is_correct, attribution, review_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            review_id,
            str(match_key),
            play_type,
            validation.get('predicted_result'),
            validation.get('actual_result'),
            None if validation.get('is_correct') is None else int(bool(validation.get('is_correct'))),
            (attribution or {}).get('level'),
            json.dumps(review_json, ensure_ascii=False, default=str),
        ))
    except Exception as e:
        logger.debug('foundation review skipped: %s', e)


def _ensure_next_data_requirements_table(conn) -> None:
    """Create next_data_requirements table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS next_data_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_match_id TEXT NOT NULL,
            play_type TEXT NOT NULL,
            error_category TEXT NOT NULL,
            requirement_key TEXT NOT NULL,
            channel TEXT,
            reason TEXT,
            priority INTEGER DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT,
            source_run_id TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ndr_status
            ON next_data_requirements(status, priority)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ndr_match
            ON next_data_requirements(lottery_match_id)
    """)


def _write_next_data_requirements(conn, failure: dict, attribution: dict) -> None:
    """Write next_data_requirements from attribution for auto-consumption."""
    try:
        _ensure_next_data_requirements_table(conn)
        match_id = failure.get('lottery_match_id', '')
        play_type = failure.get('play_type', 'spf')
        level = attribution.get('level', '')
        requirements = attribution.get('next_data_requirements', [])

        if not requirements:
            return

        for req in requirements:
            conn.execute(
                """INSERT INTO next_data_requirements
                   (lottery_match_id, play_type, error_category, requirement_key,
                    channel, reason, priority, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (
                    match_id,
                    play_type,
                    level,
                    req.get('requirement_key', level),
                    req.get('channel', ''),
                    req.get('action', attribution.get('detail', '')),
                    2 if level in ('missing_lineup', 'missing_injury', 'goal_axis_misread') else 1,
                ),
            )
    except Exception as e:
        logger.debug('write next_data_requirements failed: %s', e)


def _attribute_failures(db_path: str, match_dates: list, agent=None) -> dict:
    """翻车归因 — 规则引擎+Agent增强, 含历史回填"""
    attributed = 0

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 获取错误预测: 当日 + 回填缺失归因的
        failures = []
        if match_dates:
            placeholders = ','.join(['?'] * len(match_dates))
            cursor.execute(f"""
                SELECT lv.*, lm.home_team_cn, lm.away_team_cn
                FROM lottery_validation lv
                JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
                WHERE lm.match_date IN ({placeholders}) AND lv.is_correct = 0
            """, match_dates)
            failures.extend(dict(row) for row in cursor.fetchall())

        # 回填: attribution IS NULL 的历史错误
        cursor.execute("""
            SELECT lv.*, lm.home_team_cn, lm.away_team_cn
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lv.is_correct = 0 AND (lv.attribution IS NULL OR lv.attribution = '')
            LIMIT 500
        """)
        backfill_rows = [dict(row) for row in cursor.fetchall()]
        existing_ids = {(f.get('lottery_match_id'), f.get('play_type')) for f in failures}
        for row in backfill_rows:
            key = (row.get('lottery_match_id'), row.get('play_type'))
            if key not in existing_ids:
                failures.append(row)
                existing_ids.add(key)

        # Agent自动初始化(如果未传入)
        if agent is None:
            try:
                from backend.app.core.agent.client import create_agent
                agent = create_agent(db_path)
            except Exception:
                agent = None

        for failure in failures:
            # Step 1: 规则引擎(始终执行，作为基线)
            attribution = _determine_attribution(conn, failure)
            attribution = _enrich_attribution_with_next_data(attribution)

            # Step 2: Agent增强归因(如果可用)
            if agent:
                try:
                    agent_attr = _agent_attribution(conn, agent, failure, db_path)
                    if agent_attr:
                        attribution['rule_engine_level'] = attribution['level']
                        attribution['level'] = agent_attr.get('attribution_type', attribution['level'])
                        attribution['detail'] = agent_attr.get('detail', attribution['detail'])
                        attribution['actionable'] = int(agent_attr.get('actionable', False))
                        if agent_attr.get('suggested_action'):
                            attribution['suggested_action'] = agent_attr['suggested_action']
                        attribution['agent_confidence'] = agent_attr.get('confidence', 0)
                except Exception as e:
                    logger.debug(f'Agent归因失败 {failure.get("lottery_match_id")}: {e}')

            # 更新lottery_validation归因字段(不覆盖scenario_type)
            cursor.execute("""
                UPDATE lottery_validation
                SET attribution = ?, attribution_detail = ?,
                    actionable = ?
                WHERE lottery_match_id = ? AND play_type = ?
            """, (
                attribution['level'],
                attribution.get('suggested_action', attribution['detail']),
                attribution.get('actionable', 0),
                failure.get('lottery_match_id'),
                failure.get('play_type', 'spf'),
            ))
            _save_foundation_review(conn, failure, attribution)

            # Write next_data_requirements for auto-consumption
            _write_next_data_requirements(conn, failure, attribution)

            attributed += 1

        conn.commit()
        conn.close()

    except Exception as e:
        logger.debug('归因失败: %s', e)

    return {'attributed': attributed}


def _determine_attribution(conn, failure: dict) -> dict:
    """确定单场翻车归因 — 支持所有玩法类型的细化归因"""
    prob = failure.get('predicted_prob', 0)
    match_id = failure.get('lottery_match_id', '')
    play_type = failure.get('play_type', 'spf')
    actual = str(failure.get('actual_result', ''))
    predicted = str(failure.get('predicted_result', ''))
    confidence = _safe_float(failure.get('confidence'), 0.0)
    confidence_level = str(failure.get('confidence_level') or 'low')

    # 1. 低置信噪声 — 置信度极低的错误优先归因
    #    注意: confidence=0.5通常是默认值(未设置), 不算低置信
    #    真正低置信: confidence < 0.35 且非默认0.5
    is_low_conf = (confidence > 0 and confidence < 0.35) or (confidence_level == 'low' and confidence > 0 and confidence < 0.5)
    if is_low_conf:
        return {
            'level': 'low_confidence_noise',
            'detail': f'{_play_label(play_type)}置信度低({confidence:.0%}), 预测不可靠',
            'scenario': 'low_confidence',
        }

    # 2. 情报缺失检查 — 按缺失类型细化
    intel_check = _check_intel_completeness(conn, match_id)
    if intel_check.get('is_missing'):
        missing_keys = intel_check.get('missing_keys', [])
        # 细化: lineup vs injury vs other
        if 'expected_lineup' in missing_keys:
            return {
                'level': 'missing_lineup',
                'detail': intel_check['detail'],
                'scenario': 'data_gap',
                'missing_keys': missing_keys,
            }
        if 'injuries_suspensions' in missing_keys:
            return {
                'level': 'missing_injury',
                'detail': intel_check['detail'],
                'scenario': 'data_gap',
                'missing_keys': missing_keys,
            }
        return {
            'level': 'intel_missing',
            'detail': intel_check['detail'],
            'scenario': 'data_gap',
            'missing_keys': missing_keys,
        }

    # 3. 赛事上下文检查
    scenario_type = str(failure.get('scenario_type') or '')
    if scenario_type in ('friendly_intl',):
        return {
            'level': 'tournament_context_misread',
            'detail': f'友谊赛上下文未正确应用, {_play_label(play_type)}预测{predicted}实际{actual}',
            'scenario': 'context_mismatch',
        }

    # 4. 赔率方向检查 — market_misread(赔率对但模型反了)
    odds_direction = _get_odds_direction(conn, match_id)
    if odds_direction and odds_direction == actual and predicted != actual and play_type == 'spf':
        return {
            'level': 'market_misread',
            'detail': f'赔率暗示{SPF_LABEL.get(odds_direction, odds_direction)}, 模型预测{SPF_LABEL.get(predicted, predicted)}, 实际{SPF_LABEL.get(actual, actual)}',
            'scenario': 'market_divergence',
        }

    # 5. 玩法特定归因
    play_attr = _play_specific_attribution(conn, failure, play_type, actual, predicted)
    if play_attr:
        return play_attr

    # 6. 概率差距小 → close_match
    if prob and prob > 0.35:
        return {
            'level': 'close_match',
            'detail': f'{_play_label(play_type)}预测概率{prob:.1%}, 方向正确但结果不利',
            'scenario': 'close',
        }

    # 7. 概率很低 → bad_luck
    if prob and prob < 0.20:
        return {
            'level': 'bad_luck',
            'detail': f'{_play_label(play_type)}预测概率仅{prob:.1%}, 低概率事件发生',
            'scenario': 'upset',
        }

    # 8. 默认 — model_weight_issue
    return {
        'level': 'model_weight_issue',
        'detail': f'{_play_label(play_type)}预测概率{prob:.1%}, 数据齐备但权重可能错误',
        'scenario': 'medium',
    }


def _play_specific_attribution(conn, failure: dict, play_type: str, actual: str, predicted: str) -> Optional[dict]:
    """玩法特定的细化归因逻辑"""
    match_id = failure.get('lottery_match_id', '')
    home_goals = failure.get('home_goals')
    away_goals = failure.get('away_goals')

    if play_type == 'ou':
        # O/U: 检查进球轴是否严重误判
        total_goals = (_safe_int(home_goals) or 0) + (_safe_int(away_goals) or 0)
        # 从预测中提取盘口线
        pred_line = 2.5
        import re
        m = re.search(r'[\d.]+', predicted)
        if m:
            try:
                pred_line = float(m.group())
            except ValueError:
                pass
        deviation = abs(total_goals - pred_line)
        if deviation >= 2:
            return {
                'level': 'goal_axis_misread',
                'detail': f'大小球进球轴严重偏离: 预测线{pred_line:g}, 实际{total_goals}球, 偏差{deviation:.0f}球',
                'scenario': 'goal_axis_error',
            }
        # 检查盘口数据质量
        ou_line_from_db = _check_ou_line_quality(conn, match_id)
        if ou_line_from_db and abs(ou_line_from_db - pred_line) > 0.5:
            return {
                'level': 'data_quality_issue',
                'detail': f'O/U盘口数据不一致: 预测用线{pred_line:g}, DB盘口{ou_line_from_db:g}',
                'scenario': 'data_quality',
            }
        return None

    if play_type == 'rqspf':
        # RQSPF: 让球边界误判
        # 检查是否在1球边界上(最敏感区域)
        if home_goals is not None and away_goals is not None:
            margin = int(home_goals) - int(away_goals)
            # 从预测提取让球值
            handicap = 0
            report = _latest_report(conn, match_id)
            pp = (report.get('play_predictions') or {}).get('rqspf') or {}
            gl = pp.get('goal_line') or pp.get('handicap')
            if gl is not None:
                try:
                    handicap = float(gl)
                except (TypeError, ValueError):
                    pass
            # 边界附近(让球后差1球以内)
            adjusted_margin = margin + handicap  # handicap negative = home giving
            if abs(adjusted_margin) <= 1:
                return {
                    'level': 'margin_axis_misread',
                    'detail': f'让球边界敏感区: 让{handicap:g}球, 净胜{margin}球, 调整后差{adjusted_margin}球',
                    'scenario': 'margin_boundary',
                }
        return None

    if play_type == 'bqc':
        # BQC: 半场节奏误判
        # 检查半场比分是否与预测的半场方向相反
        result_row = None
        try:
            row = conn.execute(
                "SELECT home_goals_ht, away_goals_ht FROM lottery_results WHERE lottery_match_id = ?",
                (match_id,)
            ).fetchone()
            if row:
                result_row = dict(row) if hasattr(row, 'keys') else {'home_goals_ht': row[0], 'away_goals_ht': row[1]}
        except Exception:
            pass
        if result_row and result_row.get('home_goals_ht') is not None and result_row.get('away_goals_ht') is not None:
            ht_h = int(result_row['home_goals_ht'])
            ht_a = int(result_row['away_goals_ht'])
            # 预测的半场方向(从BQC代码第一位)
            pred_ht = predicted[0] if len(predicted) >= 1 else ''
            actual_ht_code = '3' if ht_h > ht_a else ('1' if ht_h == ht_a else '0')
            if pred_ht and pred_ht != actual_ht_code:
                ht_label = {'3': '主胜', '1': '平', '0': '客胜'}
                return {
                    'level': 'half_time_axis_misread',
                    'detail': f'半场节奏误判: 预测半场{ht_label.get(pred_ht, pred_ht)}, 实际半场{ht_h}:{ht_a}({ht_label.get(actual_ht_code, actual_ht_code)})',
                    'scenario': 'half_time_error',
                }
        return None

    if play_type == 'bf':
        # BF: 比分候选未命中 — 检查进球区间是否正确
        if home_goals is not None and away_goals is not None:
            total = int(home_goals) + int(away_goals)
            # 从候选比分推断预测的进球区间
            candidates = failure.get('score_candidates') or []
            pred_totals = []
            for c in candidates:
                if isinstance(c, dict) and c.get('score'):
                    parts = str(c['score']).split(':')
                    if len(parts) == 2:
                        try:
                            pred_totals.append(int(parts[0]) + int(parts[1]))
                        except ValueError:
                            pass
            if pred_totals:
                pred_avg_total = sum(pred_totals) / len(pred_totals)
                if abs(total - pred_avg_total) >= 2:
                    return {
                        'level': 'goal_axis_misread',
                        'detail': f'比分进球轴偏离: 预测总球约{pred_avg_total:.0f}, 实际{total}球',
                        'scenario': 'goal_axis_error',
                    }
        return None

    return None


def _check_ou_line_quality(conn, match_id: str) -> Optional[float]:
    """检查DB中O/U盘口数据质量"""
    try:
        row = conn.execute("""
            SELECT odds_data FROM lottery_odds
            WHERE lottery_match_id = ? AND play_type = 'ttg'
            LIMIT 1
        """, (match_id,)).fetchone()
        if not row:
            return None
        odds = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        # Try to extract line from ttg odds
        for key in odds:
            if 'over' in str(key).lower() and '2.5' in str(key):
                return 2.5
            if 'over' in str(key).lower() and '2.25' in str(key):
                return 2.25
            if 'over' in str(key).lower() and '2.75' in str(key):
                return 2.75
        return None
    except Exception:
        return None


# Attribution → specific data requirements mapping
_ATTRIBUTION_DATA_MAP = {
    'intel_missing': {
        'injuries_suspensions': ['api_sports_injuries', 'apifootball_match_detail', 'news_aggregator'],
        'expected_lineup': ['bifen188_lineups', 'api_sports_injuries', 'apifootball_match_detail'],
        'odds_1x2': ['sporttery_lottery_sync', 'oddsfe_event_detail'],
        'base_info': ['sporttery_lottery_sync', 'oddsfe_event_detail'],
        'recent_form': ['oddsfe_event_detail', 'sporttery_lottery_sync'],
        'team_news': ['news_aggregator', 'apifootball_match_detail'],
        'weather': ['weather_fetcher'],
        'fifa_ranking': ['fifa_ranking_fetcher'],
        'home_away_profile': ['oddsfe_event_detail'],
        'tournament_context': ['sporttery_lottery_sync'],
        'all': ['sporttery_lottery_sync', 'oddsfe_event_detail', 'news_aggregator'],
    },
    'missing_lineup': {
        '_default': ['api_sports_injuries', 'apifootball_match_detail', 'bifen188_lineups'],
        '_note': '缺少预计首发，需优先补充阵容信息',
    },
    'missing_injury': {
        '_default': ['api_sports_injuries', 'apifootball_match_detail', 'news_aggregator'],
        '_note': '缺少伤停信息，需补充伤病/停赛数据',
    },
    'market_misread': {
        '_default': ['oddsfe_event_detail', 'sporttery_lottery_sync'],
        '_note': '赔率信号误读，需要更精确的赔率时间序列和盘口变化数据',
    },
    'goal_axis_misread': {
        '_default': ['oddsfe_event_detail'],
        '_note': '进球轴误判，需补充进攻效率、防守强度、BTTS、近期大小球分布',
    },
    'margin_axis_misread': {
        '_default': ['oddsfe_event_detail'],
        '_note': '让球边界误判，需补充强队杀穿率、弱队抗打能力、净胜球分布',
    },
    'half_time_axis_misread': {
        '_default': ['oddsfe_event_detail'],
        '_note': '半场节奏误判，需补充上半场进失球、半场节奏、早球率',
    },
    'motivation_misread': {
        '_default': ['sporttery_lottery_sync', 'news_aggregator'],
        '_note': '赛事动机误判，需补充积分形势、轮换信息、晋级压力',
    },
    'tournament_context_misread': {
        '_default': ['sporttery_lottery_sync', 'news_aggregator'],
        '_note': '赛事上下文误判，需补充赛事类型特性(友谊赛轮换/杯赛淘汰赛规则)',
    },
    'data_quality_issue': {
        '_default': ['sporttery_lottery_sync', 'oddsfe_event_detail'],
        '_note': '数据质量问题，需重新采集或交叉校验赔率/盘口数据',
    },
    'low_confidence_noise': {
        '_default': [],
        '_note': '低置信噪声，数据质量不足以支撑可靠预测，应标记为不建议',
    },
    'model_weight_issue': {
        '_default': ['oddsfe_event_detail'],
        '_note': '模型权重问题，数据齐备但因子权重需要重新校准',
    },
    'market_wrong': {
        '_default': ['oddsfe_event_detail', 'sporttery_lottery_sync'],
        '_note': '赔率信号分歧时需要更精确的赔率时间序列数据',
    },
    'model_weight': {
        '_default': ['oddsfe_event_detail'],
        '_note': '数据齐备但权重可能需要重新校准',
    },
    'close_match': {
        '_default': [],
        '_note': '势均力敌, 不需要额外数据, 但可考虑更精确的动机/形势数据',
    },
    'bad_luck': {
        '_default': [],
        '_note': '低概率事件, 数据质量已足够',
    },
}


def _enrich_attribution_with_next_data(attribution: dict) -> dict:
    """Add next_data_requirements field based on attribution level and missing_keys."""
    level = attribution.get('level', '')
    data_map = _ATTRIBUTION_DATA_MAP.get(level, {})
    missing_keys = attribution.get('missing_keys', [])

    requirements = []
    if level == 'intel_missing' and missing_keys:
        for key in missing_keys:
            channels = data_map.get(key, data_map.get('all', []))
            for channel in channels:
                requirements.append({
                    'requirement_key': key,
                    'channel': channel,
                    'action': f'collect_{channel}',
                })
    elif level in data_map:
        channels = data_map.get('_default', [])
        note = data_map.get('_note', '')
        # For missing_lineup/missing_injury, also check specific keys
        if missing_keys and level in ('missing_lineup', 'missing_injury'):
            for key in missing_keys:
                specific_channels = data_map.get(key, [])
                for channel in specific_channels:
                    if channel not in channels:
                        channels = channels + [channel]
        for channel in channels:
            requirements.append({
                'requirement_key': level,
                'channel': channel,
                'action': f'collect_{channel}',
            })
        if note:
            attribution['next_data_note'] = note

    # Deduplicate by channel
    seen = set()
    unique = []
    for req in requirements:
        if req['channel'] not in seen:
            seen.add(req['channel'])
            unique.append(req)

    attribution['next_data_requirements'] = unique
    return attribution


def _check_intel_completeness(conn, match_id: str) -> dict:
    """Check if intelligence data was missing or low-confidence for this match."""
    try:
        # Find the intelligence job for this match
        row = conn.execute("""
            SELECT j.job_id, p.completeness, p.strict_completeness, p.missing_required
            FROM intelligence_jobs j
            LEFT JOIN intelligence_packages p ON j.job_id = p.job_id
            WHERE j.lottery_match_id = ?
            LIMIT 1
        """, (match_id,)).fetchone()
        if not row:
            return {
                'is_missing': True,
                'detail': '无情报包，关键数据缺失',
                'missing_keys': ['all'],
            }

        completeness = row[1] or 0
        strict = row[2] or 0
        missing_json = row[3] or '[]'

        # Parse missing_required
        try:
            missing_keys = json.loads(missing_json) if isinstance(missing_json, str) else missing_json
        except Exception:
            missing_keys = []

        # Key requirements that indicate data gap
        critical_keys = {'injuries_suspensions', 'expected_lineup', 'odds_1x2', 'base_info'}
        critical_missing = [k for k in missing_keys if k in critical_keys]

        # If completeness < 70% or critical items missing → intel_missing
        if completeness < 70 or critical_missing:
            return {
                'is_missing': True,
                'detail': f'情报覆盖{completeness:.0f}%, 缺{"/".join(critical_missing[:3]) or "关键项"}',
                'missing_keys': critical_missing or missing_keys[:5],
            }

        # Check for low-confidence fallback items
        req_rows = conn.execute("""
            SELECT key, status, confidence
            FROM intelligence_requirements
            WHERE job_id = ? AND status IN ('fallback_used', 'failed')
        """, (row[0],)).fetchall()
        low_conf = [r[0] for r in req_rows if (r[2] or 0) < 0.4]
        if low_conf and completeness < 90:
            return {
                'is_missing': True,
                'detail': f'情报低置信: {"/".join(low_conf[:3])}',
                'missing_keys': low_conf,
            }

        return {'is_missing': False}

    except Exception:
        return {'is_missing': False}


def _get_odds_direction(conn, match_id: str) -> str:
    """从赔率隐含概率获取赔率方向(argmax)"""
    try:
        row = conn.execute("""
            SELECT odds_data FROM lottery_odds
            WHERE lottery_match_id = ? AND play_type = 'spf'
            AND (snapshot_type = 'opening' OR snapshot_type IS NULL)
            LIMIT 1
        """, (match_id,)).fetchone()
        if not row:
            return ''

        odds = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        # 支持 '3'/'1'/'0' 键
        h = odds.get('3') or odds.get('home') or odds.get('win') or 0
        d = odds.get('1') or odds.get('draw') or 0
        a = odds.get('0') or odds.get('away') or odds.get('loss') or 0

        if not all([h, d, a]):
            return ''

        # 隐含概率
        ih, id_, ia = 1/h, 1/d, 1/a
        total = ih + id_ + ia
        probs = {'3': ih/total, '1': id_/total, '0': ia/total}
        return max(probs, key=probs.get)
    except Exception:
        return ''


def _agent_attribution(conn, agent, failure: dict, db_path: str) -> dict:
    """调用Agent进行深度翻车归因"""
    match_id = failure.get('lottery_match_id', '')

    # 从report_data提取预测细节
    prediction = _get_prediction_features(conn, match_id)
    if not prediction:
        return None

    # 构建result
    result = {
        'spf_result': failure.get('actual_result', ''),
        'home_goals_ft': 0,
        'away_goals_ft': 0,
    }
    # 尝试从lottery_results获取比分
    try:
        row = conn.execute(
            "SELECT home_goals_ft, away_goals_ft FROM lottery_results WHERE lottery_match_id = ?",
            (match_id,)
        ).fetchone()
        if row:
            result['home_goals_ft'] = row[0] if not hasattr(row, 'keys') else row['home_goals_ft']
            result['away_goals_ft'] = row[1] if not hasattr(row, 'keys') else row['away_goals_ft']
    except Exception:
        pass

    # 构建features
    features = _get_match_features(conn, match_id)

    return agent.error_attribution(prediction, result, features)


def _get_prediction_features(conn, match_id: str) -> dict:
    """从lottery_analysis_reports提取预测特征"""
    try:
        active_filter = _active_report_filter(conn)
        row = conn.execute(f"""
            SELECT report_data FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
            {active_filter}
            ORDER BY datetime(created_at) DESC, rowid DESC
        """, (match_id,)).fetchone()
        if not row:
            return None

        report = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        final = report.get('final_prediction', {})
        probs = final.get('probabilities', {})

        return {
            'home_win': probs.get('home_win', 0),
            'draw': probs.get('draw', 0),
            'away_win': probs.get('away_win', 0),
            'recommendation': final.get('predicted_result', '') or final.get('recommended', ''),
            'confidence_level': final.get('confidence', 'medium'),
            'odds_baseline_rec': report.get('model_vs_odds', {}).get('odds_rec', 'unknown'),
            'model_vs_odds': report.get('model_vs_odds', {}),
        }
    except Exception:
        return None


def _get_match_features(conn, match_id: str) -> dict:
    """提取比赛特征供Agent分析"""
    features = {
        'competition_type': 'unknown',
        'friendly_adjustment': 'none',
        'correction_direction': 'none',
        'odds_baseline': {},
        'model_probs': {},
    }

    try:
        # 联赛信息
        row = conn.execute("""
            SELECT league_name_cn FROM lottery_matches WHERE lottery_match_id = ?
        """, (match_id,)).fetchone()
        if row:
            league = row[0] if not hasattr(row, 'keys') else row['league_name_cn']
            if league and ('友谊' in league or '国际' in league):
                features['competition_type'] = 'friendly'

        # 预测报告中的调整信息
        pred = _get_prediction_features(conn, match_id)
        if pred:
            features['model_probs'] = {
                'home_win': pred['home_win'],
                'draw': pred['draw'],
                'away_win': pred['away_win'],
            }

        # 赔率基线
        row = conn.execute("""
            SELECT odds_data FROM lottery_odds
            WHERE lottery_match_id = ? AND play_type = 'spf'
            LIMIT 1
        """, (match_id,)).fetchone()
        if row:
            odds = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            h = float(odds.get('3', odds.get('home', 0)) or 0)
            d = float(odds.get('1', odds.get('draw', 0)) or 0)
            a = float(odds.get('0', odds.get('away', 0)) or 0)
            if h > 1 and d > 1 and a > 1:
                ih, id_, ia = 1/h, 1/d, 1/a
                total = ih + id_ + ia
                features['odds_baseline'] = {
                    'home_win': round(ih/total, 3),
                    'draw': round(id_/total, 3),
                    'away_win': round(ia/total, 3),
                }
    except Exception:
        pass

    return features


def _settle_bets(db_path: str) -> dict:
    """结算bet_records — 匹配lottery_results, 计算盈亏

    逻辑:
    1. 找所有result='pending'的bet_records
    2. 对应lottery_results有spf_result → 结算
    3. selection == spf_result → win, payout = stake * odds, profit = payout - stake
    4. selection != spf_result → lose, payout = 0, profit = -stake
    5. stake=0的记录 → 用默认虚拟投注100元
    """
    DEFAULT_STAKE = 100.0
    settled = 0
    wins = 0
    total_profit = 0.0

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 获取所有pending的bet_records
        cursor.execute("""
            SELECT id, lottery_match_id, play_type, selection, odds, stake
            FROM bet_records
            WHERE result = 'pending'
        """)
        pending_bets = [dict(row) for row in cursor.fetchall()]

        for bet in pending_bets:
            lm_id = bet['lottery_match_id']
            play_type = bet['play_type']
            selection = bet['selection']  # '3', '1', '0'

            # 查找结果
            cursor.execute("""
                SELECT spf_result, rqspf_result, bf_result, bqc_result
                FROM lottery_results
                WHERE lottery_match_id = ?
            """, (lm_id,))
            result_row = cursor.fetchone()

            if not result_row:
                continue  # 还没出结果

            # 根据play_type选择对应结果字段
            if play_type == 'spf':
                actual = result_row['spf_result']
            elif play_type == 'rqspf':
                actual = result_row['rqspf_result']
            elif play_type == 'bf':
                actual = result_row['bf_result']
            elif play_type == 'bqc':
                actual = result_row['bqc_result']
            else:
                actual = result_row['spf_result']

            if not actual:
                continue  # 结果字段为空

            # 计算盈亏
            stake = bet['stake'] or DEFAULT_STAKE
            odds = bet['odds'] or 1.0

            if selection == actual:
                # Win
                payout = round(stake * odds, 2)
                profit = round(payout - stake, 2)
                cursor.execute("""
                    UPDATE bet_records
                    SET result = 'win', stake = ?, payout = ?, profit = ?
                    WHERE id = ?
                """, (stake, payout, profit, bet['id']))
                wins += 1
                total_profit += profit
            else:
                # Lose
                cursor.execute("""
                    UPDATE bet_records
                    SET result = 'lose', stake = ?, payout = 0, profit = ?
                    WHERE id = ?
                """, (stake, -stake, bet['id']))
                total_profit -= stake

            settled += 1

        conn.commit()
        conn.close()

        if settled > 0:
            logger.info('投注结算: %d笔, %d胜, 盈亏%.0f元', settled, wins, total_profit)

    except Exception as e:
        logger.error('投注结算失败: %s', e)
        return {'settled': 0}

    return {'settled': settled, 'wins': wins, 'profit': round(total_profit, 2)}


def _backfill_results_from_unified(db_path: str) -> dict:
    """备选源回填 — 现已由oddsfe API方式替代，保留接口兼容"""
    return {'status': 'ok', 'backfilled': 0, 'note': 'replaced by oddsfe API'}


def _sync_csv_opening_odds(db_path: str) -> dict:
    """从unified_football.db同步CSV开盘赔率到lottery_odds"""
    try:
        from scripts.sync_csv_opening_odds import sync_csv_opening_odds
        return sync_csv_opening_odds(football_v2_path=db_path)
    except ImportError:
        logger.debug('CSV开盘赔率同步脚本不可用')
        return {'status': 'skipped', 'reason': 'sync script not available'}
    except Exception as e:
        logger.debug(f'CSV开盘赔率同步失败: {e}')
        return {'status': 'error', 'error': str(e)}


def _sync_oddsfe_before_validate(db_path: str) -> dict:
    """验证前执行oddsfe增量同步 — 确保赛果和赔率最新"""
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(db_path).parent.parent
    oddsfe_path = str(Path(db_path).parent / 'oddsfe_merged.db')
    sync_script = str(project_root / 'scripts' / 'oddsfe_sync.py')

    if not Path(oddsfe_path).exists() or not Path(sync_script).exists():
        return {'status': 'skipped'}

    try:
        result = subprocess.run(
            [sys.executable, sync_script,
             '--oddsfe', oddsfe_path,
             '--db', db_path,
             '--incremental', '--days', '3'],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            logger.info('验证前oddsfe增量同步完成')
            return {'status': 'ok'}
        else:
            logger.debug('验证前oddsfe同步失败(非阻塞): %s', result.stderr[:100] if result.stderr else '')
            return {'status': 'error'}
    except Exception as e:
        logger.debug('验证前oddsfe同步异常(非阻塞): %s', e)
        return {'status': 'error'}



def _validate_ou_for_report(conn, report, row, scenario, leakage_flag=None):
    """Validate O/U prediction with the same line used by the prediction."""
    total_goals = (row['home_goals_ft'] or 0) + (row['away_goals_ft'] or 0)

    def pick_ou_data():
        pp = report.get('play_predictions', {}) or {}
        analyses = report.get('analyses', {}) or {}
        for item in (pp.get('ou'), pp.get('over_under'), analyses.get('ou')):
            if isinstance(item, dict) and item:
                return item
        return {}

    ou_data = pick_ou_data()
    if not ou_data:
        return

    raw_prediction = (
        ou_data.get('recommendation')
        or ou_data.get('predicted_result')
        or ou_data.get('direction')
        or ''
    )
    if str(raw_prediction).strip() in ('', '--', '未知', 'unknown', 'None'):
        probs = ou_data.get('best_line_probs') or ou_data.get('over_under_probs') or {}
        over_prob = probs.get('over') or probs.get('over_2.5') or probs.get('over_2_5') or 0
        under_prob = probs.get('under') or probs.get('under_2.5') or probs.get('under_2_5') or 0
        line_hint = ou_data.get('best_line') or ou_data.get('line') or 2.5
        try:
            line_hint_text = f"{float(line_hint):g}"
        except (TypeError, ValueError):
            line_hint_text = str(line_hint or '2.5')
        if not over_prob and not under_prob:
            return
        raw_prediction = f"{'大' if over_prob >= under_prob else '小'}{line_hint_text}"

    text = str(raw_prediction).strip()
    lower = text.lower()
    if '大' in text or lower.startswith('over') or lower.startswith('o'):
        direction = '大'
    elif '小' in text or lower.startswith('under') or lower.startswith('u'):
        direction = '小'
    else:
        return

    try:
        from backend.app.lottery.services.ou_calculator import (
            compute_ou_result,
            format_ou_line,
            parse_ou_line,
        )

        line = (
            parse_ou_line(text)
            or parse_ou_line(ou_data.get('best_line'))
            or parse_ou_line(ou_data.get('line'))
            or 2.5
        )
        predicted_ou = f"{direction}{format_ou_line(line)}"
        actual_ou = compute_ou_result(total_goals, line)
    except Exception:
        return

    ou_correct = actual_ou == predicted_ou
    probs = ou_data.get('best_line_probs') or ou_data.get('over_under_probs') or {}
    pred_prob = max([float(v) for v in probs.values() if isinstance(v, (int, float))], default=0)
    ou_brier = _compute_ou_brier(probs, actual_ou)

    # Compute settlement grade for O/U
    settlement_grade = compute_ou_settlement(total_goals, line, direction)

    validation = {
        'lottery_match_id': row['lottery_match_id'],
        'play_type': 'ou',
        'predicted_result': predicted_ou,
        'actual_result': actual_ou,
        'is_correct': ou_correct,
        'confidence': ou_data.get('confidence', 0.5),
        'confidence_level': ou_data.get('confidence_level', 'medium'),
        'brier_score': ou_brier,
        'scenario_type': scenario,
        'probabilities': probs,
        'predicted_prob': pred_prob,
        'home_goals': row['home_goals_ft'],
        'away_goals': row['away_goals_ft'],
        'settlement_grade': settlement_grade,
        'confidence_tier': ou_data.get('confidence_tier') or _compute_tier_from_validation(
            ou_data.get('confidence', 0.5), probs, row, conn, 'ou'),
        'leakage_flag': leakage_flag,
    }
    _save_validation(conn, validation)


def _row_value(row, key, default=None):
    try:
        return row[key]
    except Exception:
        if isinstance(row, dict):
            return row.get(key, default)
        return default


def _normalize_score_text(value):
    if value is None:
        return ''
    text = str(value).strip().replace('：', ':').replace('-', ':')
    import re
    match = re.search(r'(\d+)\s*:\s*(\d+)', text)
    if not match:
        return text
    return f"{int(match.group(1))}:{int(match.group(2))}"


def _score_candidate_text(item: Any) -> str:
    if isinstance(item, dict):
        raw = item.get('score')
        if raw is None and item.get('home_goals') is not None and item.get('away_goals') is not None:
            raw = f"{item.get('home_goals')}:{item.get('away_goals')}"
        return _normalize_score_text(raw)
    return _normalize_score_text(item)


def _score_candidate_probability(item: Any) -> float:
    if not isinstance(item, dict):
        return 0.0
    value = item.get('probability', item.get('prob', 0))
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number / 100.0 if number > 1 else number


def _extract_score_candidates_from_report(report: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    pp = report.get('play_predictions', {}) or {}
    final_prediction = report.get('final_prediction', {}) or {}
    analyses = report.get('analyses', {}) or {}

    raw_items = []
    if isinstance(pp.get('top3_scores'), list):
        raw_items = pp.get('top3_scores') or []
    elif isinstance(final_prediction.get('most_likely_scores'), list):
        raw_items = final_prediction.get('most_likely_scores') or []
    else:
        bf_analysis = analyses.get('bf') if isinstance(analyses.get('bf'), dict) else {}
        if isinstance(bf_analysis.get('top_scores'), list):
            raw_items = bf_analysis.get('top_scores') or []
        elif bf_analysis.get('recommendation'):
            raw_items = [bf_analysis.get('recommendation')]

    seen = set()
    for item in raw_items:
        score = _score_candidate_text(item)
        if not score or score in seen or not _is_valid_validation_text(score):
            continue
        seen.add(score)
        candidates.append({
            'score': score,
            'probability': round(_score_candidate_probability(item), 4),
            'rank': len(candidates) + 1,
        })
        if len(candidates) >= limit:
            break
    return candidates


def _validate_bqc_for_report(conn, report, row, scenario, leakage_flag=None):
    """Validate BQC (半全场) prediction from a report."""
    actual_bqc = _row_value(row, 'bqc_result')
    if not actual_bqc:
        return

    # Extract BQC prediction from report
    bqc_prediction = None
    bqc_confidence = 0.5
    bqc_confidence_level = 'medium'
    bqc_confidence_tier = None

    # Format 1: play_predictions.bqc
    pp = report.get('play_predictions', {})
    if pp and pp.get('bqc'):
        bqc_pred = pp['bqc']
        bqc_prediction = bqc_pred.get('recommendation', '')
        bqc_confidence = bqc_pred.get('confidence', 0.5)
        bqc_confidence_level = bqc_pred.get('confidence_level', 'medium')
        bqc_confidence_tier = bqc_pred.get('confidence_tier')

    # Format 2: analyses.bqc
    if not bqc_prediction:
        bqc_analysis = report.get('analyses', {}).get('bqc', {})
        if bqc_analysis:
            bqc_prediction = bqc_analysis.get('recommendation', '')
            bqc_confidence = bqc_analysis.get('confidence', 0.5)
            bqc_confidence_level = bqc_analysis.get('confidence_level', 'medium')

    if not bqc_prediction:
        return

    pred_normalized = _normalize_bqc_value(bqc_prediction)
    actual_normalized = _normalize_bqc_value(actual_bqc)
    if not _is_valid_validation_text(pred_normalized) or not _is_valid_validation_text(actual_normalized):
        _delete_validation(conn, row['lottery_match_id'], 'bqc')
        return
    is_correct = (pred_normalized == actual_normalized)

    validation = {
        'lottery_match_id': row['lottery_match_id'],
        'play_type': 'bqc',
        'predicted_result': pred_normalized,
        'actual_result': actual_normalized,
        'is_correct': is_correct,
        'confidence': bqc_confidence,
        'confidence_level': bqc_confidence_level,
        'brier_score': 0,
        'scenario_type': scenario,
        'probabilities': {},
        'predicted_prob': bqc_confidence,
        'home_goals': row['home_goals_ft'],
        'away_goals': row['away_goals_ft'],
        'confidence_tier': bqc_confidence_tier or _compute_tier_from_validation(bqc_confidence, {}, row, conn, 'bqc'),
        'leakage_flag': leakage_flag,
    }
    _save_validation(conn, validation)


def _validate_bf_for_report(conn, report, row, scenario, leakage_flag=None):
    """Validate BF (比分) prediction from a report."""
    actual_bf = _row_value(row, 'bf_result')
    if not actual_bf:
        return

    candidates = _extract_score_candidates_from_report(report, limit=3)
    if not candidates:
        return

    actual_bf = _normalize_score_text(actual_bf)
    candidate_scores = [item['score'] for item in candidates if item.get('score')]
    if not candidate_scores or not _is_valid_validation_text(actual_bf):
        _delete_validation(conn, row['lottery_match_id'], 'bf')
        return

    is_correct = actual_bf in candidate_scores
    bf_prediction = ' / '.join(candidate_scores)
    probabilities = {
        item['score']: item.get('probability', 0)
        for item in candidates
        if item.get('score')
    }
    candidate_mass = round(sum(float(item.get('probability') or 0) for item in candidates), 4)
    hit_candidate = next((item for item in candidates if item.get('score') == actual_bf), None)
    pred_prob = (
        float(hit_candidate.get('probability') or 0)
        if hit_candidate
        else float(candidates[0].get('probability') or 0)
    )
    if not pred_prob:
        pred_prob = candidate_mass or 0.0

    # Compute enriched score metrics
    actual_home = row['home_goals_ft'] or 0
    actual_away = row['away_goals_ft'] or 0
    actual_total = int(actual_home) + int(actual_away)

    # goal_bucket_hit: actual total goals falls in predicted goal zone
    pred_totals = []
    for cs in candidate_scores:
        parts = str(cs).split(':')
        if len(parts) == 2:
            try:
                pred_totals.append(int(parts[0]) + int(parts[1]))
            except ValueError:
                pass
    pred_total_set = set(pred_totals)
    # Goal zones: 0-1(极小), 2(小), 3(中), 4(中大), 5+(大)
    actual_zone = '极小' if actual_total <= 1 else '小' if actual_total == 2 else '中' if actual_total == 3 else '中大' if actual_total == 4 else '大'
    pred_zone = None
    if pred_totals:
        avg_pred = sum(pred_totals) / len(pred_totals)
        pred_zone = '极小' if avg_pred <= 1 else '小' if avg_pred <= 2 else '中' if avg_pred <= 3 else '中大' if avg_pred <= 4 else '大'
    goal_bucket_hit = int(actual_zone == pred_zone) if pred_zone else 0

    # margin_bucket_hit: actual margin falls in predicted margin zone
    actual_margin = int(actual_home) - int(actual_away)
    pred_margins = []
    for cs in candidate_scores:
        parts = str(cs).split(':')
        if len(parts) == 2:
            try:
                pred_margins.append(int(parts[0]) - int(parts[1]))
            except ValueError:
                pass
    # Margin zones: -2+(客大胜), -1(客胜1球), 0(平), 1(主胜1球), 2+(主大胜)
    margin_bucket = lambda m: '客大胜' if m <= -2 else '客胜1球' if m == -1 else '平' if m == 0 else '主胜1球' if m == 1 else '主大胜'
    actual_margin_zone = margin_bucket(actual_margin)
    pred_margin_zones = set(margin_bucket(m) for m in pred_margins) if pred_margins else set()
    margin_bucket_hit = int(actual_margin_zone in pred_margin_zones) if pred_margin_zones else 0

    # btts_hit: both teams scored — predicted vs actual
    actual_btts = int(actual_home > 0 and actual_away > 0)
    pred_btts_list = []
    for cs in candidate_scores:
        parts = str(cs).split(':')
        if len(parts) == 2:
            try:
                pred_btts_list.append(int(int(parts[0]) > 0 and int(parts[1]) > 0))
            except ValueError:
                pass
    pred_btts = max(pred_btts_list) if pred_btts_list else 0  # top candidates likely have BTTS
    btts_hit = int(actual_btts == pred_btts)

    # ou_consistency_hit: whether BF prediction is consistent with O/U direction
    # If candidates suggest 大 and actual total > line, or candidates suggest 小 and actual < line
    # Get O/U line for this match
    ou_line = 2.5  # default
    try:
        ou_row = conn.execute(
            "SELECT predicted_result FROM lottery_validation WHERE lottery_match_id = ? AND play_type = 'ou' LIMIT 1",
            (row['lottery_match_id'],)
        ).fetchone()
        if ou_row and ou_row[0]:
            ou_pred = str(ou_row[0])
            m = re.search(r'[\d.]+', ou_pred)
            if m:
                ou_line = float(m.group())
    except Exception:
        pass
    ou_direction_actual = '大' if actual_total > ou_line else '小'
    ou_direction_pred = '大' if (sum(pred_totals) / len(pred_totals) if pred_totals else 2) > ou_line else '小'
    ou_consistency_hit = int(ou_direction_actual == ou_direction_pred)

    report_gate = report.get('recommendation_gate') if isinstance(report.get('recommendation_gate'), dict) else {}
    report_gate_plays = report_gate.get('plays') if isinstance(report_gate.get('plays'), dict) else {}
    bf_gate = report_gate_plays.get('bf') if isinstance(report_gate_plays.get('bf'), dict) else {}

    validation = {
        'lottery_match_id': row['lottery_match_id'],
        'play_type': 'bf',
        'predicted_result': bf_prediction,
        'actual_result': actual_bf,
        'is_correct': is_correct,
        'confidence': candidate_mass,
        'confidence_level': 'low',  # BF is inherently low confidence
        'brier_score': 0,
        'scenario_type': scenario,
        'probabilities': probabilities,
        'predicted_prob': pred_prob,
        'home_goals': row['home_goals_ft'],
        'away_goals': row['away_goals_ft'],
        'score_candidates': candidates,
        'score_candidate_hit_rank': hit_candidate.get('rank') if hit_candidate else None,
        'score_candidate_mass': candidate_mass,
        'top3_score_hit': int(is_correct),
        'goal_bucket_hit': goal_bucket_hit,
        'margin_bucket_hit': margin_bucket_hit,
        'btts_hit': btts_hit,
        'ou_consistency_hit': ou_consistency_hit,
        'confidence_tier': bf_gate.get('tier') or _compute_tier_from_validation(candidate_mass, probabilities, row, conn, 'bf'),
        'leakage_flag': leakage_flag,
    }
    _save_validation(conn, validation)


def _validate_rqspf_for_report(conn, report, row, scenario, leakage_flag=None):
    """Validate RQSPF (让球胜平负) prediction from a report."""
    actual_rqspf = _row_value(row, 'rqspf_result')
    if not actual_rqspf:
        return

    # Extract RQSPF prediction from report
    rqspf_prediction = None
    rqspf_confidence = 0.5
    rqspf_confidence_level = 'medium'
    rqspf_confidence_tier = None

    # Format 1: play_predictions.rqspf
    pp = report.get('play_predictions', {})
    rqspf_context = {}
    rqspf_probs = {}
    if pp and pp.get('rqspf'):
        rqspf_pred = pp['rqspf']
        rqspf_prediction = rqspf_pred.get('direction', '')
        rqspf_confidence = rqspf_pred.get('confidence', 0.5)
        rqspf_confidence_level = rqspf_pred.get('confidence_level', 'medium')
        rqspf_confidence_tier = rqspf_pred.get('confidence_tier')
        rqspf_probs = rqspf_pred.get('probabilities') or {}
        rqspf_context = {
            'display_source': rqspf_pred.get('display_source'),
            'display_prediction': rqspf_pred.get('recommendation_cn'),
            'goal_line': rqspf_pred.get('goal_line'),
            'goal_line_label': rqspf_pred.get('goal_line_label'),
            'margin_requirement': rqspf_pred.get('margin_requirement'),
            'unconditional_direction': rqspf_pred.get('unconditional_direction'),
            'unconditional_prediction': rqspf_pred.get('unconditional_recommendation_cn'),
            'unconditional_margin_requirement': rqspf_pred.get('unconditional_margin_requirement'),
            'unconditional_probabilities': rqspf_pred.get('unconditional_probabilities'),
            'axis_projection': rqspf_pred.get('axis_projection'),
            'axis_context': rqspf_pred.get('axis_context'),
            'axis_adjustment': rqspf_pred.get('axis_adjustment'),
        }

    # Format 2: analyses.rqspf
    if not rqspf_prediction:
        rqspf_analysis = report.get('analyses', {}).get('rqspf', {})
        if rqspf_analysis:
            rqspf_prediction = rqspf_analysis.get('recommendation', '')
            rqspf_confidence = rqspf_analysis.get('confidence', 0.5)
            rqspf_confidence_level = rqspf_analysis.get('confidence_level', 'medium')

    if not rqspf_prediction:
        return

    predicted_rqspf = _normalize_rqspf_value(rqspf_prediction)
    actual_rqspf = _normalize_rqspf_value(actual_rqspf)
    if not _is_valid_validation_text(predicted_rqspf) or not _is_valid_validation_text(actual_rqspf):
        _delete_validation(conn, row['lottery_match_id'], 'rqspf')
        return

    is_correct = (predicted_rqspf == actual_rqspf)

    # Compute handicap settlement grade
    goal_line = rqspf_context.get('goal_line')
    handicap_val = None
    if goal_line is not None:
        try:
            handicap_val = -float(goal_line)  # goal_line=-2 → handicap=2 (home gives 2)
        except (TypeError, ValueError):
            handicap_val = None
    if handicap_val is None:
        # Fallback: use handicap_line from row
        handicap_val = _safe_float(row.get('handicap_line'), 0.0)

    settlement_grade = compute_handicap_settlement(
        row['home_goals_ft'] or 0, row['away_goals_ft'] or 0,
        handicap_val, predicted_rqspf,
    )

    validation = {
        'lottery_match_id': row['lottery_match_id'],
        'play_type': 'rqspf',
        'predicted_result': predicted_rqspf,
        'actual_result': actual_rqspf,
        'is_correct': is_correct,
        'confidence': rqspf_confidence,
        'confidence_level': rqspf_confidence_level,
        'brier_score': 0,
        'scenario_type': scenario,
        'probabilities': rqspf_probs,
        'predicted_prob': rqspf_probs.get(rqspf_prediction, rqspf_confidence) if isinstance(rqspf_probs, dict) else rqspf_confidence,
        'home_goals': row['home_goals_ft'],
        'away_goals': row['away_goals_ft'],
        'rqspf_context': rqspf_context,
        'settlement_grade': settlement_grade,
        'confidence_tier': rqspf_confidence_tier or _compute_tier_from_validation(rqspf_confidence, rqspf_probs, row, conn, 'rqspf'),
        'leakage_flag': leakage_flag,
    }
    _save_validation(conn, validation)
