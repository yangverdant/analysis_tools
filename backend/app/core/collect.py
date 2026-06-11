"""
7:00+7:30 采集编排 — 日循环第二步

职责:
1. sporttery采集今日赛程
2. 队名映射(依赖Step 1修复)
3. oddsfe赔率采集(Pinnacle 1X2赔率) — 替代体彩赔率API
4. 赔率入库(snapshot_type='opening')
5. sell_status更新
6. data_source_health更新
"""

import json
import logging
import sqlite3
from datetime import date, datetime, timedelta

from .time_utils import today_beijing

logger = logging.getLogger(__name__)


def collect(state, db_path: str) -> dict:
    """执行采集编排"""
    match_date_str = today_beijing()
    match_date = datetime.strptime(match_date_str, '%Y-%m-%d').date()
    logger.info('=== 7:00 采集编排 (%s) ===', match_date_str)

    results = {}

    # Step 1: sporttery赛程采集
    results['sync'] = _sync_matches(db_path, match_date)

    # Step 2: 队名映射修复
    results['mapping'] = _fix_mappings(db_path)

    # Step 3: oddsfe赔率采集 + 入库
    results['odds'] = _fetch_and_save_oddsfe_odds(db_path, match_date_str)

    # Step 4: 更新数据源健康
    _update_health(db_path, results['sync'].get('success', False), 'sporttery')
    _update_health(db_path, results['odds'].get('success', False), 'oddsfe')

    logger.info('采集完成: %d场入库, %d赔率入库',
                results['sync'].get('saved', 0),
                results['odds'].get('saved', 0))

    return {
        'route': 'normal',
        'saved': results['sync'].get('saved', 0),
        'odds_saved': results['odds'].get('saved', 0),
        'mapped': results['sync'].get('mapped', 0),
        'steps': results,
    }


def _sync_matches(db_path: str, match_date: date) -> dict:
    """通过LotterySyncService采集赛程(含重试)"""
    max_retries = 3
    retry_delay = 60  # seconds

    for attempt in range(1, max_retries + 1):
        try:
            from backend.app.lottery.services.sync_service import LotterySyncService
            service = LotterySyncService(db_path)
            result = service.sync_daily_matches(match_date)

            unmapped = service.mapper.list_unmapped_teams()
            if unmapped:
                logger.warning('未映射队名: %s', unmapped[:10])

            return result

        except ImportError as e:
            logger.error('无法导入LotterySyncService: %s', e)
            return {'success': False, 'error': f'Import failed: {e}'}
        except Exception as e:
            logger.warning('采集失败(尝试%d/%d): %s', attempt, max_retries, e)
            if attempt < max_retries:
                import time
                time.sleep(retry_delay)
            else:
                logger.error('采集最终失败: %s', e)
                return {'success': False, 'error': str(e)}


def _fetch_and_save_oddsfe_odds(db_path: str, match_date: str, snapshot_type: str = 'opening') -> dict:
    """用oddsfe获取Pinnacle 1X2赔率，匹配体彩比赛，入库

    Args:
        match_date: 北京时间日期(YYYY-MM-DD)
        snapshot_type: 'opening' (晨间采集) 或 'midday' (14:00 CLV更新)
    """
    try:
        from fetchers.odds_feed_api.oddsfe_realtime_schedule import (
            fetch_schedule, flatten_event, create_session
        )
    except ImportError:
        logger.warning('oddsfe模块不可用，跳过赔率采集')
        return {'success': False, 'saved': 0, 'error': 'oddsfe module not available'}

    from .time_utils import oddsfe_date_range

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row

    # 1. 获取今日体彩比赛
    cursor = conn.cursor()
    cursor.execute(
        "SELECT lottery_match_id, home_team_cn, away_team_cn FROM lottery_matches WHERE match_date = ?",
        (match_date,)
    )
    lottery_matches = [dict(row) for row in cursor.fetchall()]

    if not lottery_matches:
        conn.close()
        return {'success': False, 'saved': 0, 'error': 'no lottery matches'}

    # 2. 获取oddsfe赛事
    # oddsfe日期=UTC, 体彩日期=北京时间(UTC+8)
    # 使用time_utils自动计算UTC日期范围
    oddsfe_dates = oddsfe_date_range(match_date)
    session = create_session()
    all_events = []
    fetched_days = []
    for date_str in oddsfe_dates:
        try:
            schedule_data = fetch_schedule(session, date_str)
        except Exception as e:
            logger.debug(f'oddsfe schedule fetch failed for {date_str}: {e}')
            continue
        if not schedule_data:
            continue
        events = schedule_data if isinstance(schedule_data, list) else schedule_data.get('data', [])
        day_count = 0
        for tournament in (events if isinstance(events, list) else []):
            if isinstance(tournament, dict):
                for ev in tournament.get('events', []):
                    all_events.append(ev)
                    day_count += 1
        fetched_days.append(f'{date_str}({day_count})')

    if not all_events:
        conn.close()
        return {'success': False, 'saved': 0, 'error': 'no events in schedule'}

    logger.info(f'oddsfe多日共{len(all_events)}场赛事: {", ".join(fetched_days)}')

    # 3. 构建oddsfe队名索引 — 支持精确+模糊匹配
    from fetchers.common.team_names import normalize_team_name
    oddsfe_by_norm = {}   # (norm_home, norm_away) → event
    oddsfe_by_stripped = {}  # (stripped_home, stripped_away) → event (去掉FC/United等后缀)

    def _strip_suffix(name: str) -> str:
        """去掉常见后缀用于模糊匹配"""
        import re
        s = name.strip()
        for suffix in [' FC', ' CF', ' SC', ' AFC', ' United', ' City', ' Wanderers',
                        ' Hotspur', ' Spurs', ' Athletic', ' County', ' Town',
                        ' Rovers', ' Villa', ' Albion', ' Forest', ' Palace',
                        ' Rangers', ' Celtic', ' United FC', ' City FC']:
            if s.endswith(suffix):
                s = s[:-len(suffix)]
                break
        # 缩写还原
        abbr_map = {'Atl.': 'Atletico', 'Wolves': 'Wolverhampton',
                    'Leeds': 'Leeds', 'Spurs': 'Tottenham'}
        for abbr, full in abbr_map.items():
            if s == abbr:
                s = full
                break
        return s.strip()

    for event in all_events:
        home_name = event.get('team_home_name', '')
        away_name = event.get('team_away_name', '')
        if home_name and away_name:
            norm_h = normalize_team_name(home_name)
            norm_a = normalize_team_name(away_name)
            oddsfe_by_norm[(norm_h, norm_a)] = event
            stripped_h = _strip_suffix(norm_h)
            stripped_a = _strip_suffix(norm_a)
            oddsfe_by_stripped[(stripped_h, stripped_a)] = event

    # 4. 匹配体彩比赛 → oddsfe赛事 → 提取赔率
    saved = 0
    bridged = 0
    unmapped_teams = []

    for lm in lottery_matches:
        home_en = normalize_team_name(lm['home_team_cn'])
        away_en = normalize_team_name(lm['away_team_cn'])

        # 精确匹配
        event = oddsfe_by_norm.get((home_en, away_en))

        # 反向精确匹配(主客可能互换)
        if not event:
            event = oddsfe_by_norm.get((away_en, home_en))

        # 模糊匹配(去掉后缀)
        if not event:
            stripped_h = _strip_suffix(home_en)
            stripped_a = _strip_suffix(away_en)
            event = oddsfe_by_stripped.get((stripped_h, stripped_a))

        # 反向模糊匹配
        if not event:
            stripped_h = _strip_suffix(home_en)
            stripped_a = _strip_suffix(away_en)
            event = oddsfe_by_stripped.get((stripped_a, stripped_h))

        if not event:
            unmapped_teams.append(f"{lm['home_team_cn']} vs {lm['away_team_cn']}")
            continue

        # 5. 提取Pinnacle 1X2赔率
        out_0 = event.get('main_out_0', '')  # 主胜
        out_1 = event.get('main_out_1', '')  # 平局
        out_2 = event.get('main_out_2', '')  # 客胜
        event_id = event.get('event_id', '')
        pin_event_id = event.get('event_pin_event_id', '')

        if not out_0 or not out_1 or not out_2:
            continue

        try:
            odds = {
                '3': float(out_0),
                '1': float(out_1),
                '0': float(out_2),
            }

            # 验证赔率合理性
            if any(v <= 1.0 or v > 50.0 for v in odds.values()):
                logger.warning(f'赔率异常: {lm["lottery_match_id"]} {odds}')
                continue

        except (ValueError, TypeError):
            continue

        # 6. 写入lottery_odds
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_odds
                (lottery_match_id, play_type, odds_data, snapshot_type, update_time)
                VALUES (?, 'spf', ?, ?, CURRENT_TIMESTAMP)
            """, (lm['lottery_match_id'], json.dumps(odds), snapshot_type))
            saved += 1
        except Exception as e:
            logger.debug(f'Odds insert error: {e}')

        # 7. 写入source_mapping_bridge (桥接oddsfe)
        if event_id or pin_event_id:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO source_mapping_bridge
                    (lottery_issue_num, oddsfe_event_id, home_team_lottery_name, away_team_lottery_name,
                     match_confidence, match_method, updated_at)
                    VALUES (?, ?, ?, ?, 0.90, 'name_match', CURRENT_TIMESTAMP)
                """, (lm['lottery_match_id'], event_id or pin_event_id,
                      lm['home_team_cn'], lm['away_team_cn']))
                bridged += 1
            except Exception as e:
                logger.debug(f'Bridge insert error: {e}')

        # 8. 更新lottery_matches的oddsfe_event_id
        if event_id:
            try:
                cursor.execute(
                    "UPDATE lottery_matches SET oddsfe_event_id = ? WHERE lottery_match_id = ?",
                    (event_id, lm['lottery_match_id'])
                )
            except Exception:
                pass

    conn.commit()
    conn.close()

    if unmapped_teams:
        logger.info(f'{len(unmapped_teams)}场未匹配oddsfe: {unmapped_teams[:5]}')

    return {
        'success': saved > 0,
        'saved': saved,
        'bridged': bridged,
        'unmatched': len(unmapped_teams),
    }


def _fix_mappings(db_path: str) -> dict:
    """自动修复未映射队名"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT home_team_cn FROM lottery_matches WHERE home_team_id IS NULL
            UNION
            SELECT DISTINCT away_team_cn FROM lottery_matches WHERE away_team_id IS NULL
        """)
        unmapped = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not unmapped:
            return {'unmapped': 0, 'fixed': 0}

        fixed = 0
        try:
            from fetchers.common.team_names import normalize_team_name
            from backend.app.lottery.etl.entity_mapper import EntityMapper

            mapper = EntityMapper(db_path)
            for name in unmapped:
                normalized = normalize_team_name(name)
                team_id = mapper.get_team_id(normalized)
                if team_id:
                    mapper.register_team_mapping(name, team_id, method='auto_normalize')
                    fixed += 1
                    logger.info('自动映射: %s → team_id=%d', name, team_id)
        except ImportError:
            logger.warning('team_names模块不可用')

        return {'unmapped': len(unmapped), 'fixed': fixed}

    except Exception as e:
        logger.debug(f'映射修复失败: {e}')
        return {'unmapped': 0, 'fixed': 0, 'error': str(e)}


def _update_health(db_path: str, success: bool, source_name: str):
    """更新数据源健康状态"""
    try:
        from backend.app.data_access.health_dao import DataSourceHealthDAO
        dao = DataSourceHealthDAO(db_path)
        status = 'healthy' if success else 'error'
        dao.update_status(source_name, status, success=success)
    except Exception as e:
        logger.debug(f'健康更新失败: {e}')
