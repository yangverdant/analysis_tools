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
import os
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

    # Step 3b: oddsfe O/U并发采集 + 自动merge到oddsfe_merged.db
    results['ou_collect'] = _collect_and_merge_oddsfe_ou(db_path, match_date_str)

    # Step 4: 更新数据源健康
    _update_health(db_path, results['sync'].get('success', False), 'sporttery')
    _update_health(db_path, results['odds'].get('success', False), 'oddsfe')
    _update_health(db_path, results['ou_collect'].get('success', False), 'oddsfe_ou')

    # Step 5: 更新已过开赛时间的比赛状态
    results['status_update'] = _update_match_status(db_path)

    # Step 6: 刷新player_status(伤病/阵容)
    results['player_status'] = _refresh_player_status(db_path)

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
            result = service.sync_daily_matches(
                match_date,
                bridge_oddsfe=False,
                trigger_source='core_collect_fast_sporttery',
            )

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
        logger.debug(f'健康更新失败: %s', e)


def _update_match_status(db_path: str) -> dict:
    """更新已过开赛时间的比赛状态

    selling → closed: 比赛时间已过
    closed → finished: 已有结果数据
    """
    closed_count = 0
    finished_count = 0

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # selling → closed: 有beijing_time且已过
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'closed'
            WHERE sell_status = 'selling'
            AND beijing_time IS NOT NULL
            AND datetime(beijing_time) < datetime('now', '+8 hours')
        """)
        closed_count += cursor.rowcount

        # selling → closed: 无beijing_time，用match_date判断
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'closed'
            WHERE sell_status = 'selling'
            AND beijing_time IS NULL
            AND match_date < date('now', '+8 hours')
        """)
        closed_count += cursor.rowcount

        # closed → finished: 有结果数据
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'finished'
            WHERE sell_status = 'closed'
            AND lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_results
            )
        """)
        finished_count = cursor.rowcount

        conn.commit()
        conn.close()

        logger.info('状态更新: %d场→closed, %d场→finished', closed_count, finished_count)
        return {'closed': closed_count, 'finished': finished_count}

    except Exception as e:
        logger.warning('状态更新失败: %s', e)
        return {'closed': 0, 'finished': 0, 'error': str(e)}


def _refresh_player_status(db_path: str) -> dict:
    """Refresh player_status from ESPN injuries (active leagues only).

    Only fetches when there are upcoming matches within 48h.
    Runs at most once per 12h (tracked in data_source_health).
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)

        # Check if we ran recently
        row = conn.execute(
            "SELECT last_success FROM data_source_health WHERE source_name = 'player_status_refresh'"
        ).fetchone()
        if row and row[0]:
            from datetime import timedelta
            last = datetime.fromisoformat(row[0]) if isinstance(row[0], str) else row[0]
            if datetime.now() - last < timedelta(hours=12):
                conn.close()
                return {'skipped': True, 'reason': 'ran_within_12h'}

        # Check for upcoming matches
        today = date.today().isoformat()
        upcoming = conn.execute(
            "SELECT COUNT(*) FROM lottery_matches WHERE match_date >= ?", (today,)
        ).fetchone()[0]
        if upcoming == 0:
            conn.close()
            return {'skipped': True, 'reason': 'no_upcoming_matches'}

        # Fetch ESPN injuries for active leagues
        total_injuries = 0
        active_leagues = ['eng.1', 'esp.1', 'ger.1', 'ita.1', 'fra.1',
                          'uefa.champions', 'uefa.europa', 'fifa.world',
                          'usa.1', 'bra.1']

        from fetchers.espn.get_lineups import get_league_injuries

        for lg_code in active_leagues:
            try:
                data = get_league_injuries(lg_code)
                injuries = data.get('injuries', [])
                for inj in injuries:
                    team_name = inj.get('team_name', '')
                    player_name = inj.get('athlete_name', '')
                    injury_type = inj.get('injury_type', '')
                    status = inj.get('status', '')

                    if not player_name or not team_name:
                        continue

                    status_map = {
                        'Out': 'injured', 'Doubtful': 'doubtful',
                        'Questionable': 'doubtful', 'Probable': 'available',
                        'Day To Day': 'doubtful',
                    }
                    mapped = status_map.get(status, 'injured' if 'out' in status.lower() else 'doubtful')

                    # Find team_id
                    team_id = _find_team_id(conn, team_name)
                    if not team_id:
                        continue

                    conn.execute(
                        """INSERT INTO player_status (player_name, team_id, status, status_detail,
                                                      injury_type, source, updated_at)
                           VALUES (?, ?, ?, ?, ?, 'espn_api', ?)
                           ON CONFLICT(player_name, team_id) DO UPDATE SET
                               status = excluded.status, status_detail = excluded.status_detail,
                               injury_type = excluded.injury_type, source = excluded.source,
                               updated_at = excluded.updated_at""",
                        (player_name, team_id, mapped, status, injury_type,
                         datetime.now().isoformat()),
                    )
                    total_injuries += 1
            except Exception:
                continue

        conn.commit()

        # Update health record
        conn.execute(
            """INSERT INTO data_source_health (source_name, last_success, status)
               VALUES ('player_status_refresh', ?, 'ok')
               ON CONFLICT(source_name) DO UPDATE SET last_success = excluded.last_success, status = 'ok'""",
            (datetime.now().isoformat(),),
        )
        conn.commit()
        conn.close()

        logger.info('player_status刷新: %d条伤病更新', total_injuries)
        return {'injuries': total_injuries}

    except Exception as e:
        logger.warning('player_status刷新失败: %s', e)
        return {'error': str(e)}


def _find_team_id(conn, team_name: str) -> int:
    """Find internal team_id from team name."""
    try:
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name_en = ? LIMIT 1", (team_name,),
        ).fetchone()
        if row:
            return row[0]
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name_en LIKE ? OR name_cn LIKE ? LIMIT 1",
            (f"%{team_name}%", f"%{team_name}%"),
        ).fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    return None


def _resolve_oddsfe_db_path(db_path: str) -> str:
    """Resolve the oddsfe merged cache path used by both local and cloud jobs."""
    env_path = os.environ.get('ODDSFE_DB_PATH')
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    preferred = os.path.join(project_root, 'fetchers', 'odds_feed_api', 'oddsfe_merged.db')
    legacy = os.path.join(os.path.dirname(db_path), 'oddsfe_merged.db')
    candidates = [path for path in (env_path, preferred, legacy) if path]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0] if candidates else legacy


def _collect_and_merge_oddsfe_ou(db_path: str, match_date: str) -> dict:
    """并发采集oddsfe O/U + 1X2赔率，直写oddsfe_merged.db

    采集后自动同步Pinnacle O/U到football_v2.db的oddsfe_matches表，
    并标记受影响的分析报告为stale。
    """
    try:
        from fetchers.odds_feed_api.oddsfe_ou_concurrent import collect_ou_concurrent
    except ImportError:
        logger.warning('oddsfe_ou_concurrent模块不可用，跳过O/U采集')
        return {'success': False, 'error': 'module not available'}

    # 确定oddsfe_merged.db路径
    oddsfe_db = _resolve_oddsfe_db_path(db_path)

    # 健康检查：如果O/U数据<24h，可选跳过
    health = _check_oddsfe_ou_health(oddsfe_db)
    if health.get('healthy') and health.get('hours_since', 999) < 6:
        logger.info(f'oddsfe O/U数据新鲜({health["hours_since"]:.0f}h前更新)，跳过采集')
        return {'success': True, 'skipped': True, 'reason': 'data fresh'}

    # 执行并发采集
    try:
        result = collect_ou_concurrent(
            past_days=2,
            future_days=5,
            oddsfe_db_path=oddsfe_db,
            max_workers=8,
        )
    except Exception as e:
        logger.error(f'oddsfe O/U采集异常: {e}')
        return {'success': False, 'error': str(e)}

    # 同步Pinnacle O/U到football_v2.db的oddsfe_matches表
    sync_result = _sync_ou_to_football_v2(oddsfe_db, db_path, match_date)

    # 标记受影响的分析报告为stale
    _invalidate_stale_analysis(db_path, match_date)

    return {
        'success': result.get('pinnacle_ou', 0) > 0,
        'events_collected': result.get('details_fetched', 0),
        'ou_written': result.get('ou_written', 0),
        'pinnacle_ou': result.get('pinnacle_ou', 0),
        'sync': sync_result,
    }


def _check_oddsfe_ou_health(oddsfe_db_path: str) -> dict:
    """检查oddsfe_merged.db的O/U数据新鲜度

    Returns: {'healthy': bool, 'hours_since': float, 'reason': str}
    """
    import os as _os

    if not _os.path.exists(oddsfe_db_path):
        return {'healthy': False, 'reason': 'oddsfe_merged.db not found'}

    try:
        conn = sqlite3.connect(oddsfe_db_path, timeout=10)
        row = conn.execute("""
            SELECT MAX(event_start_at) FROM oddsfe
            WHERE OVER_UNDER_prematch_lines IS NOT NULL
            AND OVER_UNDER_prematch_lines != ''
        """).fetchone()
        conn.close()

        if not row or not row[0]:
            return {'healthy': False, 'reason': 'no O/U data at all'}

        from datetime import timezone
        latest_str = row[0].replace('Z', '+00:00')
        try:
            # oddsfe timestamps are UTC without timezone suffix
            if '+' not in latest_str and not latest_str.endswith('00:00'):
                latest_str += '+00:00'
            latest_dt = datetime.fromisoformat(latest_str)
            hours_since = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            # Fallback: parse as naive UTC
            try:
                latest_dt = datetime.strptime(row[0][:19], '%Y-%m-%dT%H:%M:%S')
                hours_since = (datetime.utcnow() - latest_dt).total_seconds() / 3600
            except (ValueError, TypeError):
                return {'healthy': False, 'reason': 'cannot parse timestamp'}

        if hours_since > 48:
            return {'healthy': False, 'hours_since': hours_since, 'reason': f'data {hours_since:.0f}h old'}

        return {'healthy': True, 'hours_since': max(0, hours_since)}

    except Exception as e:
        return {'healthy': False, 'reason': str(e)}


def _sync_ou_to_football_v2(oddsfe_db_path: str, football_v2_path: str, match_date: str) -> dict:
    """从oddsfe_merged.db同步Pinnacle O/U数据到football_v2.db的oddsfe_matches表"""
    import os as _os

    if not _os.path.exists(oddsfe_db_path):
        return {'success': False, 'reason': 'oddsfe_merged.db not found'}

    try:
        oddsfe_conn = sqlite3.connect(oddsfe_db_path, timeout=10)
        v2_conn = sqlite3.connect(football_v2_path, timeout=10)

        # 确保oddsfe_matches表存在
        v2_conn.executescript("""
            CREATE TABLE IF NOT EXISTS oddsfe_matches (
                event_id TEXT PRIMARY KEY,
                event_start_at TEXT,
                team_home_name TEXT,
                team_away_name TEXT,
                category_name TEXT,
                tournament_name TEXT,
                ou_pinnacle_line REAL,
                ou_pinnacle_over REAL,
                ou_pinnacle_under REAL,
                ou_pinnacle_updated_at TEXT,
                spf_pinnacle_home REAL,
                spf_pinnacle_draw REAL,
                spf_pinnacle_away REAL,
                UNIQUE(event_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ou_teams ON oddsfe_matches(team_home_name, team_away_name);
        """)

        # 从oddsfe_merged.db获取有Pinnacle O/U数据的近期赛事
        rows = oddsfe_conn.execute("""
            SELECT event_id, event_start_at, team_home_name, team_away_name,
                   category_name, tournament_name,
                   OVER_UNDER_prematch_PINNACLE_line,
                   OVER_UNDER_prematch_PINNACLE_over,
                   OVER_UNDER_prematch_PINNACLE_under,
                   "1X2_prematch_PINNACLE_home",
                   "1X2_prematch_PINNACLE_draw",
                   "1X2_prematch_PINNACLE_away"
            FROM oddsfe
            WHERE event_start_at >= date('now', '-3 days')
            AND OVER_UNDER_prematch_PINNACLE_line IS NOT NULL
            AND OVER_UNDER_prematch_PINNACLE_line != ''
        """).fetchall()

        synced = 0
        for row in rows:
            try:
                v2_conn.execute("""
                    INSERT OR REPLACE INTO oddsfe_matches
                    (event_id, event_start_at, team_home_name, team_away_name,
                     category_name, tournament_name,
                     ou_pinnacle_line, ou_pinnacle_over, ou_pinnacle_under,
                     ou_pinnacle_updated_at,
                     spf_pinnacle_home, spf_pinnacle_draw, spf_pinnacle_away)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
                """, row)
                synced += 1
            except Exception:
                pass

        v2_conn.commit()
        oddsfe_conn.close()
        v2_conn.close()

        return {'success': True, 'synced': synced}

    except Exception as e:
        logger.error(f'O/U同步到football_v2失败: {e}')
        return {'success': False, 'error': str(e)}


def _invalidate_stale_analysis(db_path: str, match_date: str):
    """标记分析报告为stale — 当O/U赔率数据更新后旧分析可能过时"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 检查is_stale列是否存在
        cols = {r[1] for r in cursor.execute("PRAGMA table_info(lottery_analysis_reports)").fetchall()}
        if 'is_stale' not in cols:
            conn.execute("ALTER TABLE lottery_analysis_reports ADD COLUMN is_stale INTEGER DEFAULT 0")

        # 标记今日分析为stale
        cursor.execute("""
            UPDATE lottery_analysis_reports SET is_stale = 1
            WHERE lottery_match_id IN (
                SELECT lottery_match_id FROM lottery_matches WHERE match_date = ?
            )
            AND is_stale = 0
        """, (match_date,))

        count = cursor.rowcount
        conn.commit()
        conn.close()

        if count > 0:
            logger.info(f'标记{count}个分析报告为stale (O/U数据更新)')
    except Exception as e:
        logger.debug(f'标记stale失败: {e}')
