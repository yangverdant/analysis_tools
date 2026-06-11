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
import sqlite3
from datetime import date, timedelta
from typing import Dict, List

from .time_utils import today_beijing, yesterday_beijing

logger = logging.getLogger(__name__)


# 翻车归因5级
ATTRIBUTION_LEVELS = {
    'bad_luck': '运气差 — 模型方向正确但结果不利',
    'close_match': '势均力敌 — 概率差距小(<5pp)',
    'correction_wrong': '修正方向错 — 基础模型方向对但修正反了',
    'market_wrong': '市场信号错误 — 赔率暗示与结果相反',
    'intel_missing': '情报缺失 — 关键信息(伤病/阵容)未纳入',
}

# 结果映射: 模型推荐 → SPF代码
RESULT_MAP = {'home_win': '3', 'draw': '1', 'away_win': '0', '3': '3', '1': '1', '0': '0'}
CN_RESULT_MAP = {'主胜': '3', '平局': '1', '平': '1', '客胜': '0', '客': '0'}
SPF_LABEL = {'3': '主胜', '1': '平局', '0': '客胜'}


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

    # Step 2: 确定需要验证的日期范围(含历史回填)
    match_dates = _find_unvalidated_dates(db_path, [yesterday, today])

    # Step 2b: 验证预测
    results['validation'] = _validate_predictions(db_path, match_dates)

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
    """oddsfe备选结果源 — 从schedule API获取已完赛比分"""
    try:
        from fetchers.odds_feed_api.oddsfe_realtime_schedule import (
            fetch_schedule, flatten_event, create_session
        )
    except ImportError:
        logger.warning('oddsfe模块不可用')
        return {'success': False, 'error': 'oddsfe module not available'}

    try:
        session = create_session()
        schedule_data = fetch_schedule(session, match_date)
        if not schedule_data:
            return {'success': False, 'error': 'no schedule data'}

        events = schedule_data if isinstance(schedule_data, list) else schedule_data.get('data', [])
        finished = []
        for tournament in (events if isinstance(events, list) else []):
            if isinstance(tournament, dict):
                for ev in tournament.get('events', []):
                    row = flatten_event(ev)
                    if row.get('event_status') == 'FINISHED' and row.get('event_winner') != '':
                        finished.append(row)

        if not finished:
            return {'success': False, 'error': 'no finished matches', 'date': match_date}

        # 构建oddsfe队名索引
        from fetchers.common.team_names import normalize_team_name
        oddsfe_by_name = {}
        for row in finished:
            h = normalize_team_name(row.get('team_home_name', ''))
            a = normalize_team_name(row.get('team_away_name', ''))
            oddsfe_by_name[(h, a)] = row
            oddsfe_by_name[(a, h)] = row  # 反向匹配

        # 匹配体彩比赛并写入lottery_results
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT lottery_match_id, home_team_cn, away_team_cn, oddsfe_event_id FROM lottery_matches WHERE match_date = ?",
            (match_date,)
        )
        lottery_matches = [dict(r) for r in cursor.fetchall()]

        saved = 0
        # oddsfe winner: 0=home, 1=draw, 2=away → 体彩: 3=home, 1=draw, 0=away
        winner_to_spf = {'0': '3', '1': '1', '2': '0'}

        for lm in lottery_matches:
            # 优先通过oddsfe_event_id匹配
            oddsfe_row = None
            if lm.get('oddsfe_event_id'):
                for row in finished:
                    if str(row.get('event_id')) == str(lm['oddsfe_event_id']):
                        oddsfe_row = row
                        break

            # 其次通过队名匹配
            if not oddsfe_row:
                h = normalize_team_name(lm['home_team_cn'])
                a = normalize_team_name(lm['away_team_cn'])
                oddsfe_row = oddsfe_by_name.get((h, a))

            if not oddsfe_row:
                continue

            winner = str(oddsfe_row.get('event_winner', ''))
            spf = winner_to_spf.get(winner)
            if not spf:
                continue

            home_goals = oddsfe_row.get('event_score_home', 0)
            away_goals = oddsfe_row.get('event_score_away', 0)

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO lottery_results
                    (lottery_match_id, home_goals_ft, away_goals_ft, spf_result)
                    VALUES (?, ?, ?, ?)
                """, (lm['lottery_match_id'], int(home_goals), int(away_goals), spf))
                saved += 1
            except Exception as e:
                logger.debug('结果写入失败 %s: %s', lm['lottery_match_id'], e)

        conn.commit()
        conn.close()
        return {'success': saved > 0, 'saved': saved, 'date': match_date, 'source': 'oddsfe'}

    except Exception as e:
        logger.error('oddsfe结果获取失败: %s', e)
        return {'success': False, 'error': str(e)}


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

        if match_dates:
            placeholders = ','.join(['?'] * len(match_dates))
            date_filter = f"WHERE lm.match_date IN ({placeholders})"
            params = match_dates
        else:
            # 回填模式：验证所有有结果但未验证的
            date_filter = ""
            params = []

        cursor.execute(f"""
            SELECT ar.lottery_match_id, ar.report_data,
                   lm.home_team_cn, lm.away_team_cn, lm.league_name_cn,
                   lr.spf_result, lr.home_goals_ft, lr.away_goals_ft
            FROM lottery_analysis_reports ar
            JOIN lottery_matches lm ON ar.lottery_match_id = lm.lottery_match_id
            JOIN lottery_results lr ON ar.lottery_match_id = lr.lottery_match_id
            {date_filter}
            AND ar.report_type IN ('prediction', 'full')
            GROUP BY ar.lottery_match_id
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

                # Format 1: final_prediction.predicted_result
                fp = report.get('final_prediction', {})
                if fp.get('predicted_result'):
                    predicted = fp['predicted_result']
                    probabilities = fp.get('probabilities', {})
                    confidence = fp.get('confidence', 0)
                    confidence_level = fp.get('confidence_level', 'low')

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
                }

                _save_validation(conn, validation)
                validated += 1

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
    """从oddsfe_merged.db回填历史缺失结果 — 解决odds/results管道缺口

    对每个缺少结果的lottery_match，通过队名+日期在oddsfe中找到已完成比赛，
    写入lottery_results。使用内存索引加速匹配。
    """
    from pathlib import Path
    import re

    oddsfe_path = str(Path(db_path).parent / 'oddsfe_merged.db')
    if not Path(oddsfe_path).exists():
        return {'status': 'skipped', 'reason': 'no oddsfe db'}

    def _simple_normalize(name: str) -> str:
        """简单队名归一化"""
        n = name.strip()
        for suffix in [' FC', ' CF', ' SC', ' AFC', ' United', ' City',
                        ' Hotspur', ' Athletic', ' County', ' Town',
                        ' Rovers', ' Villa', ' Albion', ' Forest', ' Palace',
                        ' Rangers', ' Celtic', ' Wanderers']:
            if n.endswith(suffix):
                n = n[:-len(suffix)]
                break
        return n.strip().lower()

    try:
        dst = sqlite3.connect(db_path, timeout=10)
        dst.row_factory = sqlite3.Row
        cursor = dst.cursor()

        # 查找缺少结果的已关闭比赛
        cursor.execute("""
            SELECT lm.lottery_match_id, lm.match_date,
                   lm.home_team_cn, lm.away_team_cn,
                   ht.name_en as home_en, at.name_en as away_en
            FROM lottery_matches lm
            LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
            LEFT JOIN teams at ON lm.away_team_id = at.team_id
            WHERE lm.lottery_match_id NOT IN (
                SELECT DISTINCT lottery_match_id FROM lottery_results
            )
            AND lm.sell_status = 'closed'
            ORDER BY lm.match_date
        """)
        missing = [dict(r) for r in cursor.fetchall()]

        if not missing:
            dst.close()
            return {'status': 'ok', 'backfilled': 0}

        # 加载中英队名映射
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

        # 从oddsfe加载所有已完赛比赛到内存索引
        src = sqlite3.connect(oddsfe_path, timeout=30)
        logger.info('Loading oddsfe finished matches for backfill...')
        oddsfe_index = {}  # (norm_home, norm_away, date_window) → (score_home, score_away, winner)
        count = 0
        for row in src.execute("""
            SELECT team_home_name, team_away_name,
                   event_score_home, event_score_away, event_winner,
                   event_start_at
            FROM oddsfe
            WHERE event_status = 'FINISHED'
        """):
            h_name, a_name, s_h, s_a, winner, start_at = row
            norm_h = _simple_normalize(h_name or '')
            norm_a = _simple_normalize(a_name or '')
            # 日期窗口: 提取UTC日期(±1天对应北京时区偏移)
            if start_at:
                date_window = start_at[:10]  # YYYY-MM-DD
            else:
                date_window = None
            key = (norm_h, norm_a, date_window)
            # 只保留最近的结果(同队名同日期可能有多场)
            if key not in oddsfe_index:
                oddsfe_index[key] = (s_h, s_a, winner)
            # 也存储精确名匹配
            exact_key = ((h_name or '').strip().lower(), (a_name or '').strip().lower(), date_window)
            if exact_key not in oddsfe_index:
                oddsfe_index[exact_key] = (s_h, s_a, winner)
            count += 1

        src.close()
        logger.info(f'Loaded {count} oddsfe matches, {len(oddsfe_index)} unique keys')

        backfilled = 0
        winner_to_spf = {'0': '3', '1': '1', '2': '0'}

        for lm in missing:
            home_en = lm.get('home_en')
            away_en = lm.get('away_en')

            if not home_en and lm['home_team_cn'] in cn_to_en:
                home_en = cn_to_en[lm['home_team_cn']]
            if not away_en and lm['away_team_cn'] in cn_to_en:
                away_en = cn_to_en[lm['away_team_cn']]

            match_date = lm['match_date']

            if not home_en or not away_en:
                continue

            # 尝试多种匹配方式 — ±3天覆盖(体彩日期可能与oddsfe UTC日期差2-3天)
            result = None
            for day_offset in range(-3, 4):
                from datetime import timedelta, date as date_cls
                try:
                    d = date_cls.fromisoformat(match_date) + timedelta(days=day_offset)
                except ValueError:
                    continue
                d_window = str(d)

                # 精确名匹配
                key1 = (home_en.strip().lower(), away_en.strip().lower(), d_window)
                if key1 in oddsfe_index:
                    result = oddsfe_index[key1]
                    break

                # 归一化名匹配
                key2 = (_simple_normalize(home_en), _simple_normalize(away_en), d_window)
                if key2 in oddsfe_index:
                    result = oddsfe_index[key2]
                    break

            if result:
                try:
                    home_goals = int(result[0]) if result[0] is not None else None
                    away_goals = int(result[1]) if result[1] is not None else None
                    winner = str(result[2])

                    if home_goals is None or away_goals is None:
                        continue

                    spf = winner_to_spf.get(winner)
                    if not spf:
                        if home_goals > away_goals:
                            spf = '3'
                        elif home_goals == away_goals:
                            spf = '1'
                        else:
                            spf = '0'

                    cursor.execute("""
                        INSERT OR IGNORE INTO lottery_results
                        (lottery_match_id, home_goals_ft, away_goals_ft, spf_result)
                        VALUES (?, ?, ?, ?)
                    """, (lm['lottery_match_id'], home_goals, away_goals, spf))
                    backfilled += 1
                except Exception as e:
                    logger.debug(f'回填失败 {lm["lottery_match_id"]}: {e}')

        dst.commit()
        dst.close()

        if backfilled > 0:
            logger.info(f'oddsfe结果回填: {backfilled}场')

        return {'status': 'ok', 'backfilled': backfilled}

    except Exception as e:
        logger.error(f'oddsfe结果回填失败: {e}')
        return {'status': 'error', 'error': str(e)}


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


def _save_validation(conn, validation: dict):
    """写入lottery_validation(去重: 同一match_id+play_type只保留最新)"""
    # 先删除旧记录再插入
    conn.execute("""
        DELETE FROM lottery_validation
        WHERE lottery_match_id = ? AND play_type = ?
    """, (validation['lottery_match_id'], validation['play_type']))

    conn.execute("""
        INSERT INTO lottery_validation
        (lottery_match_id, play_type, predicted_result, actual_result,
         is_correct, predicted_prob, brier_score, scenario_type, validated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        validation['lottery_match_id'],
        validation['play_type'],
        validation['predicted_result'],
        validation['actual_result'],
        validation['is_correct'],
        validation['predicted_prob'],
        validation['brier_score'],
        validation.get('scenario_type', 'unknown'),
    ))


def _attribute_failures(db_path: str, match_dates: list, agent=None) -> dict:
    """翻车归因 — 规则引擎+Agent增强"""
    attributed = 0

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 获取错误预测
        placeholders = ','.join(['?'] * len(match_dates))
        cursor.execute(f"""
            SELECT lv.*, lm.home_team_cn, lm.away_team_cn
            FROM lottery_validation lv
            JOIN lottery_matches lm ON lv.lottery_match_id = lm.lottery_match_id
            WHERE lm.match_date IN ({placeholders}) AND lv.is_correct = 0
        """, match_dates)
        failures = [dict(row) for row in cursor.fetchall()]

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

            # Step 2: Agent增强归因(如果可用)
            if agent:
                try:
                    agent_attr = _agent_attribution(conn, agent, failure, db_path)
                    if agent_attr:
                        # Agent结果覆盖规则引擎(但保留规则引擎作为fallback)
                        attribution['rule_engine_level'] = attribution['level']
                        attribution['level'] = agent_attr.get('attribution_type', attribution['level'])
                        attribution['detail'] = agent_attr.get('detail', attribution['detail'])
                        attribution['actionable'] = int(agent_attr.get('actionable', False))
                        if agent_attr.get('suggested_action'):
                            attribution['suggested_action'] = agent_attr['suggested_action']
                        attribution['agent_confidence'] = agent_attr.get('confidence', 0)
                except Exception as e:
                    logger.debug(f'Agent归因失败 {failure.get("lottery_match_id")}: {e}')

            # 更新lottery_validation归因字段
            cursor.execute("""
                UPDATE lottery_validation
                SET attribution = ?, attribution_detail = ?, scenario_type = ?,
                    actionable = ?
                WHERE lottery_match_id = ? AND play_type = ?
            """, (
                attribution['level'],
                attribution.get('suggested_action', attribution['detail']),
                attribution['scenario'],
                attribution.get('actionable', 0),
                failure.get('lottery_match_id'),
                failure.get('play_type', 'spf'),
            ))

            attributed += 1

        conn.commit()
        conn.close()

    except Exception as e:
        logger.debug('归因失败: %s', e)

    return {'attributed': attributed}


def _determine_attribution(conn, failure: dict) -> dict:
    """确定单场翻车归因"""
    prob = failure.get('predicted_prob', 0)
    match_id = failure.get('lottery_match_id', '')

    # 检查赔率方向: 如果赔率方向与实际一致但模型预测反了 → market_wrong
    odds_direction = _get_odds_direction(conn, match_id)
    actual = failure.get('actual_result', '')
    predicted = failure.get('predicted_result', '')

    if odds_direction and odds_direction == actual and predicted != actual:
        return {
            'level': 'market_wrong',
            'detail': f'赔率暗示{SPF_LABEL.get(odds_direction, odds_direction)}, 模型预测{SPF_LABEL.get(predicted, predicted)}, 实际{SPF_LABEL.get(actual, actual)}',
            'scenario': 'market_divergence',
        }

    # 概率差距小 → 势均力敌
    if prob and prob > 0.35:
        return {
            'level': 'close_match',
            'detail': f'预测概率{prob:.1%}, 方向正确但结果不利',
            'scenario': 'close',
        }

    # 概率很低 → 运气差
    if prob and prob < 0.20:
        return {
            'level': 'bad_luck',
            'detail': f'预测概率仅{prob:.1%}, 低概率事件发生',
            'scenario': 'upset',
        }

    # 默认归因
    return {
        'level': 'correction_wrong',
        'detail': f'预测概率{prob:.1%}, 修正方向可能错误',
        'scenario': 'medium',
    }


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
        row = conn.execute("""
            SELECT report_data FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
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
    """从unified_football.db回填缺失结果 — 备选源

    unified_football.db有14K已完成比赛+比分，通过队名+日期匹配。
    """
    from pathlib import Path

    unified_path = str(Path(db_path).parent / 'unified_football.db')
    if not Path(unified_path).exists():
        return {'status': 'skipped', 'reason': 'no unified db'}

    def _simple_normalize(name: str) -> str:
        n = name.strip()
        for suffix in [' FC', ' CF', ' SC', ' AFC', ' United', ' City',
                        ' Hotspur', ' Athletic', ' County', ' Town',
                        ' Rovers', ' Villa', ' Albion', ' Forest', ' Palace',
                        ' Rangers', ' Celtic', ' Wanderers']:
            if n.endswith(suffix):
                n = n[:-len(suffix)]
                break
        return n.strip().lower()

    try:
        dst = sqlite3.connect(db_path, timeout=10)
        dst.row_factory = sqlite3.Row
        cursor = dst.cursor()

        cursor.execute("""
            SELECT lm.lottery_match_id, lm.match_date,
                   lm.home_team_cn, lm.away_team_cn,
                   ht.name_en as home_en, at.name_en as away_en
            FROM lottery_matches lm
            LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
            LEFT JOIN teams at ON lm.away_team_id = at.team_id
            WHERE lm.lottery_match_id NOT IN (
                SELECT DISTINCT lottery_match_id FROM lottery_results
            )
            AND lm.sell_status = 'closed'
            ORDER BY lm.match_date
        """)
        missing = [dict(r) for r in cursor.fetchall()]

        if not missing:
            dst.close()
            return {'status': 'ok', 'backfilled': 0}

        # 加载中英队名映射
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

        # 从unified_football.db加载已完成比赛
        src = sqlite3.connect(unified_path, timeout=30)
        logger.info('Loading unified_football.db finished matches for backfill...')
        unified_index = {}  # (norm_home, norm_away, date) → (home_score, away_score)
        count = 0
        for row in src.execute("""
            SELECT home_team, away_team, date, home_score, away_score
            FROM matches WHERE status = 'finished' AND home_score IS NOT NULL
        """):
            h_name, a_name, m_date, h_score, a_score = row
            if not h_name or not a_name or not m_date:
                continue
            norm_h = _simple_normalize(h_name)
            norm_a = _simple_normalize(a_name)
            key = (norm_h, norm_a, m_date)
            if key not in unified_index:
                unified_index[key] = (h_score, a_score)
            # Also exact name match
            exact_key = (h_name.strip().lower(), a_name.strip().lower(), m_date)
            if exact_key not in unified_index:
                unified_index[exact_key] = (h_score, a_score)
            count += 1

        src.close()
        logger.info(f'Loaded {count} unified matches, {len(unified_index)} unique keys')

        backfilled = 0
        for lm in missing:
            home_en = lm.get('home_en')
            away_en = lm.get('away_en')

            if not home_en and lm['home_team_cn'] in cn_to_en:
                home_en = cn_to_en[lm['home_team_cn']]
            if not away_en and lm['away_team_cn'] in cn_to_en:
                away_en = cn_to_en[lm['away_team_cn']]

            match_date = lm['match_date']

            if not home_en or not away_en:
                continue

            # 尝试±3天日期窗口
            result = None
            for day_offset in range(-3, 4):
                from datetime import timedelta, date as date_cls
                try:
                    d = date_cls.fromisoformat(match_date) + timedelta(days=day_offset)
                except ValueError:
                    continue
                d_str = str(d)

                key1 = (home_en.strip().lower(), away_en.strip().lower(), d_str)
                if key1 in unified_index:
                    result = unified_index[key1]
                    break

                key2 = (_simple_normalize(home_en), _simple_normalize(away_en), d_str)
                if key2 in unified_index:
                    result = unified_index[key2]
                    break

            if result:
                try:
                    home_goals = int(result[0]) if result[0] is not None else None
                    away_goals = int(result[1]) if result[1] is not None else None
                    if home_goals is None or away_goals is None:
                        continue

                    if home_goals > away_goals:
                        spf = '3'
                    elif home_goals == away_goals:
                        spf = '1'
                    else:
                        spf = '0'

                    cursor.execute("""
                        INSERT OR IGNORE INTO lottery_results
                        (lottery_match_id, home_goals_ft, away_goals_ft, spf_result)
                        VALUES (?, ?, ?, ?)
                    """, (lm['lottery_match_id'], home_goals, away_goals, spf))
                    backfilled += 1
                except Exception as e:
                    logger.debug(f'回填失败 {lm["lottery_match_id"]}: {e}')

        dst.commit()
        dst.close()

        if backfilled > 0:
            logger.info(f'unified结果回填: {backfilled}场')

        return {'status': 'ok', 'backfilled': backfilled}

    except Exception as e:
        logger.error(f'unified结果回填失败: {e}')
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
