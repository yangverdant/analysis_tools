"""8:00 临场信息 — 赔率异动优先，伤停/天气/轮换补充

日循环第5步，在analyze之前执行，提供临场信号。
输出写入lottery_analysis_reports(report_type='intel')。
"""

import json
import logging
import sqlite3
from datetime import date
from typing import Dict, List, Optional

from .time_utils import today_beijing, tomorrow_beijing

logger = logging.getLogger(__name__)


def intel(state, db_path: str) -> dict:
    """收集临场信息 — 北京时间窗口"""
    today = today_beijing()
    tomorrow = tomorrow_beijing()
    logger.info('=== 8:00 临场信息 (%s ~ %s) ===', today, tomorrow)

    results = {
        'date': today,
        'odds_movements': [],
        'injuries': [],
        'weather': [],
        'rotation_risks': [],
        'international_break': _check_international_break(today),
        'summary': '',
    }

    # 1. 赔率异动(最有价值)
    try:
        results['odds_movements'] = _detect_odds_movement(db_path, today, tomorrow)
    except Exception as e:
        logger.warning('赔率异动检测失败: %s', e)

    # 2. 伤停信息
    try:
        results['injuries'] = _fetch_injuries(db_path, today, tomorrow)
    except Exception as e:
        logger.warning('伤停查询失败: %s', e)

    # 3. 轮换风险评估
    try:
        results['rotation_risks'] = _estimate_rotation_risks(db_path, today, tomorrow)
    except Exception as e:
        logger.warning('轮换评估失败: %s', e)

    # 4. 天气(仅敏感联赛)
    try:
        results['weather'] = _fetch_weather(db_path, today, tomorrow)
    except Exception as e:
        logger.warning('天气查询失败: %s', e)

    # 5. 保存intel报告
    _save_intel_report(db_path, today, results)

    # 6. 汇总
    n_mov = len(results['odds_movements'])
    n_inj = len(results['injuries'])
    n_rot = len(results['rotation_risks'])
    n_wea = len(results['weather'])
    parts = []
    if n_mov:
        parts.append(f'{n_mov}场赔率异动')
    if n_inj:
        parts.append(f'{n_inj}场伤病')
    if n_rot:
        parts.append(f'{n_rot}场轮换风险')
    if n_wea:
        parts.append(f'{n_wea}场天气影响')
    if results['international_break'].get('is_international_break'):
        parts.append('国际比赛日')
    results['summary'] = ', '.join(parts) if parts else '无明显信号'

    logger.info('临场信息: %s', results['summary'])
    return {'route': 'normal', **results}


# ═══════════════════════════════════════
# 赔率异动检测
# ═══════════════════════════════════════

def _detect_odds_movement(db_path: str, today: str, tomorrow: str, threshold: float = 0.03) -> List[Dict]:
    """对比opening vs当前赔率, 检测>3%异动

    策略:
    1. 优先: lottery_odds中有opening+latest/midday快照 → 直接对比
    2. 回退: 只有opening快照 → 重新采集体彩赔率对比
    3. 最终: 同一match多条opening(不同时间) → 对比首尾
    """
    changes = []
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 方法1: opening vs latest/midday
        cursor.execute("""
            SELECT lm.lottery_match_id,
                   lm.home_team_cn, lm.away_team_cn,
                   open_odds.odds_data AS opening,
                   curr_odds.odds_data AS current
            FROM lottery_matches lm
            JOIN lottery_odds open_odds
                ON lm.lottery_match_id = open_odds.lottery_match_id
                AND open_odds.play_type = 'spf'
                AND (open_odds.snapshot_type = 'opening' OR open_odds.snapshot_type IS NULL)
            JOIN lottery_odds curr_odds
                ON lm.lottery_match_id = curr_odds.lottery_match_id
                AND curr_odds.play_type = 'spf'
                AND curr_odds.snapshot_type IN ('latest', 'midday')
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
        """, (today, tomorrow))

        for row in cursor.fetchall():
            opening = _parse_odds(row['opening'])
            current = _parse_odds(row['current'])
            if not opening or not current:
                continue
            open_probs = _odds_to_probs(opening)
            curr_probs = _odds_to_probs(current)
            if not open_probs or not curr_probs:
                continue

            for outcome, label in [('3', 'home_win'), ('1', 'draw'), ('0', 'away_win')]:
                delta = curr_probs[label] - open_probs[label]
                if abs(delta) >= threshold:
                    changes.append({
                        'lottery_match_id': row['lottery_match_id'],
                        'match': f"{row['home_team_cn']} vs {row['away_team_cn']}",
                        'outcome': label,
                        'direction': 'up' if delta > 0 else 'down',
                        'magnitude': round(abs(delta), 4),
                        'open_prob': round(open_probs[label], 4),
                        'curr_prob': round(curr_probs[label], 4),
                        'source': 'db_snapshot',
                    })

        if changes:
            conn.close()
            return changes

        # 方法2: 重新采集体彩赔率, 与opening对比
        current_odds = _fetch_current_sporttery_odds(db_path, today)

        if current_odds:
            for lm_id, curr_spf in current_odds.items():
                cursor.execute("""
                    SELECT lm.home_team_cn, lm.away_team_cn, lo.odds_data
                    FROM lottery_matches lm
                    JOIN lottery_odds lo ON lm.lottery_match_id = lo.lottery_match_id
                        AND lo.play_type = 'spf'
                        AND (lo.snapshot_type = 'opening' OR lo.snapshot_type IS NULL)
                    WHERE lm.lottery_match_id = ?
                """, (lm_id,))
                row = cursor.fetchone()
                if not row:
                    continue

                opening = _parse_odds(row['odds_data'])
                if not opening:
                    continue
                open_probs = _odds_to_probs(opening)
                curr_probs = _odds_to_probs(curr_spf)
                if not open_probs or not curr_probs:
                    continue

                for outcome, label in [('3', 'home_win'), ('1', 'draw'), ('0', 'away_win')]:
                    delta = curr_probs[label] - open_probs[label]
                    if abs(delta) >= threshold:
                        changes.append({
                            'lottery_match_id': lm_id,
                            'match': f"{row['home_team_cn']} vs {row['away_team_cn']}",
                            'outcome': label,
                            'direction': 'up' if delta > 0 else 'down',
                            'magnitude': round(abs(delta), 4),
                            'open_prob': round(open_probs[label], 4),
                            'curr_prob': round(curr_probs[label], 4),
                            'source': 'sporttery_live',
                        })

                # 保存当前赔率为latest快照
                if curr_spf:
                    cursor.execute("""
                        INSERT INTO lottery_odds
                        (lottery_match_id, play_type, odds_data, snapshot_type, created_at)
                        VALUES (?, 'spf', ?, 'latest', datetime('now'))
                    """, (lm_id, json.dumps(curr_spf, ensure_ascii=False)))

            if changes:
                conn.commit()

        if not changes:
            # 方法3: fallback — 同一match多条记录对比首尾
            changes = _detect_odds_movement_fallback(db_path, today, tomorrow, threshold)

    except Exception as e:
        logger.debug('赔率异动检测异常: %s', e)
    finally:
        conn.close()

    return changes


def _fetch_current_sporttery_odds(db_path: str, match_date: str) -> Dict[str, dict]:
    """重新采集体彩当前赔率"""
    try:
        from backend.app.lottery.services.sync_service import LotterySyncService
        service = LotterySyncService(db_path)
        raw = service.crawler.crawl_matches_sync(str(match_date))
        if not raw:
            return {}

        result = {}
        for match in raw:
            lm_id = match.get('lottery_match_id', '')
            spf_odds = match.get('spf_odds') or match.get('odds', {}).get('spf')
            if lm_id and spf_odds:
                result[lm_id] = spf_odds

        service.close()
        return result
    except Exception as e:
        logger.debug('体彩赔率重采失败: %s', e)
        return {}


# 如果没有latest快照, 也可用opening和第二次采集对比
def _detect_odds_movement_fallback(db_path: str, today: str, tomorrow: str, threshold: float = 0.03) -> List[Dict]:
    """备用: 对比最早和最新的opening赔率(可能来自多次采集)"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT lm.lottery_match_id,
                   lm.home_team_cn, lm.away_team_cn
            FROM lottery_matches lm
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
        """, (today, tomorrow))

        changes = []
        for row in cursor.fetchall():
            lm_id = row['lottery_match_id']

            # 获取最早和最新的SPF赔率
            cursor.execute("""
                SELECT odds_data, created_at FROM lottery_odds
                WHERE lottery_match_id = ? AND play_type = 'spf'
                ORDER BY created_at ASC
            """, (lm_id,))
            odds_rows = cursor.fetchall()

            if len(odds_rows) < 2:
                continue

            opening = _parse_odds(odds_rows[0]['odds_data'])
            current = _parse_odds(odds_rows[-1]['odds_data'])

            if not opening or not current:
                continue

            open_probs = _odds_to_probs(opening)
            curr_probs = _odds_to_probs(current)
            if not open_probs or not curr_probs:
                continue

            for label in ['home_win', 'draw', 'away_win']:
                delta = curr_probs[label] - open_probs[label]
                if abs(delta) >= threshold:
                    changes.append({
                        'lottery_match_id': lm_id,
                        'match': f"{row['home_team_cn']} vs {row['away_team_cn']}",
                        'outcome': label,
                        'direction': 'up' if delta > 0 else 'down',
                        'magnitude': round(abs(delta), 4),
                        'open_prob': round(open_probs[label], 4),
                        'curr_prob': round(curr_probs[label], 4),
                    })

        conn.close()
        return changes

    except Exception as e:
        logger.debug('赔率异动fallback异常: %s', e)
        return []


# ═══════════════════════════════════════
# 伤停信息
# ═══════════════════════════════════════

def _fetch_injuries(db_path: str, today: str, tomorrow: str) -> List[Dict]:
    """查询伤病/停赛(从DB, 如有apifootball数据)"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 检查player_sidelined表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_sidelined'")
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("""
            SELECT ps.player_name, ps.category, ps.type_name,
                   t.name_en AS team_name
            FROM player_sidelined ps
            JOIN teams t ON ps.team_id = t.team_id
            WHERE ps.category IN ('suspended', 'injury')
            AND ps.end_date >= ?
        """, (today,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'player': row[0],
                'team': row[1] if len(row) > 1 else '',
                'category': row[1] if len(row) > 1 else 'unknown',
                'type': row[2] if len(row) > 2 else '',
            })

        conn.close()
        return results

    except Exception as e:
        logger.debug('伤停查询异常: %s', e)
        return []


# ═══════════════════════════════════════
# 轮换风险评估
# ═══════════════════════════════════════

FRIENDLY_ROTATION = {'club': 0.65, 'national_warmup': 0.40, 'national_ranking': 0.25}
CUP_ROTATION = {'domestic_early': 0.45, 'domestic_late': 0.15, 'continental_group': 0.30, 'continental_knockout': 0.05}

def _estimate_rotation_risks(db_path: str, today: str, tomorrow: str) -> List[Dict]:
    """评估今日比赛的轮换风险"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT lm.lottery_match_id,
                   lm.home_team_cn, lm.away_team_cn,
                   l.name_en AS league_name,
                   l.competition_type,
                   l.participant_type
            FROM lottery_matches lm
            LEFT JOIN leagues l ON lm.league_id = l.league_id
                OR l.name_cn = lm.league_name_cn
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
        """, (today, tomorrow))

        results = []
        for row in cursor.fetchall():
            rot = _calc_rotation(row)
            if rot > 0.15:
                results.append({
                    'lottery_match_id': row['lottery_match_id'],
                    'match': f"{row['home_team_cn']} vs {row['away_team_cn']}",
                    'rotation_probability': round(rot, 2),
                    'league': row['league_name'] or '',
                })

        conn.close()
        return results

    except Exception as e:
        logger.debug('轮换评估异常: %s', e)
        return []


def _calc_rotation(match_row: dict) -> float:
    """计算单场轮换概率"""
    comp = match_row.get('competition_type', '') or ''
    league = match_row.get('league_name', '') or ''
    participant = match_row.get('participant_type', '') or ''

    # 友谊赛
    if comp == 'friendly' or '友谊赛' in league:
        if 'national' in participant:
            return FRIENDLY_ROTATION.get('national_warmup', 0.4)
        return FRIENDLY_ROTATION.get('club', 0.5)

    # 杯赛
    if comp == 'cup':
        if any(kw in league.lower() for kw in ['champions', 'europa', 'conference']):
            return CUP_ROTATION.get('continental_group', 0.3)
        return CUP_ROTATION.get('domestic_early', 0.3)

    # 国际比赛日 → 俱乐部轮换
    md_str = match_row.get('match_date', '')
    if md_str:
        try:
            md = date.fromisoformat(md_str)
            if _check_international_break(md).get('is_international_break') and comp == 'league':
                return 0.3
        except ValueError:
            pass

    return 0.0


# ═══════════════════════════════════════
# 天气
# ═══════════════════════════════════════

WEATHER_SENSITIVE = {
    '俄超', '瑞超', '挪超', '芬超', '巴甲', '阿超', '解放者杯', 'J联赛', 'K联赛',
}

def _fetch_weather(db_path: str, today: str, tomorrow: str) -> List[Dict]:
    """天气影响(短期返回空, 需接openweathermap)"""
    return []


# ═══════════════════════════════════════
# 国际比赛日检测
# ═══════════════════════════════════════

FIFA_WINDOWS_2026 = [
    (date(2026, 3, 23), date(2026, 3, 31)),
    (date(2026, 6, 1), date(2026, 6, 14)),
    (date(2026, 6, 11), date(2026, 7, 19)),
    (date(2026, 9, 7), date(2026, 9, 15)),
    (date(2026, 10, 6), date(2026, 10, 14)),
    (date(2026, 11, 9), date(2026, 11, 17)),
]

def _check_international_break(match_date: str) -> Dict:
    """检测是否在FIFA国际比赛日窗口"""
    from datetime import datetime as _dt
    try:
        md = _dt.strptime(match_date, '%Y-%m-%d').date() if isinstance(match_date, str) else match_date
    except (ValueError, TypeError):
        md = match_date
    for start, end in FIFA_WINDOWS_2026:
        if start <= md <= end:
            return {
                'is_international_break': True,
                'window_start': str(start),
                'window_end': str(end),
                'impact_on_club': 'rotation_risk_high',
            }
    return {'is_international_break': False}


# ═══════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════

def _parse_odds(raw) -> Optional[Dict]:
    """解析odds_data JSON"""
    if raw is None:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None


def _odds_to_probs(odds_data: dict) -> Optional[Dict]:
    """赔率 → 隐含概率 (odds_data: {"3": 2.10, "1": 3.40, "0": 3.50})"""
    try:
        h = float(odds_data.get('3', odds_data.get('home', 0)))
        d = float(odds_data.get('1', odds_data.get('draw', 0)))
        a = float(odds_data.get('0', odds_data.get('away', 0)))
        if h <= 1 or d <= 1 or a <= 1:
            return None
        total = 1/h + 1/d + 1/a
        return {
            'home_win': round((1/h) / total, 4),
            'draw': round((1/d) / total, 4),
            'away_win': round((1/a) / total, 4),
        }
    except Exception:
        return None


def _save_intel_report(db_path: str, today: str, results: dict):
    """保存intel报告(按日期聚合, 不按比赛)"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        report_id = f"intel_{today}"
        report_json = json.dumps(results, ensure_ascii=False, default=str)
        cursor.execute("""
            INSERT OR REPLACE INTO lottery_analysis_reports
            (lottery_match_id, report_type, report_data, created_at)
            VALUES (?, 'intel', ?, datetime('now'))
        """, (report_id, report_json))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug('intel报告保存失败: %s', e)
