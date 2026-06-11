"""8:30 赛事分类 — 调用CompetitionRuleEngine

使用core/competition/engine.py的8种类型+分线设计
"""

import json
import logging
import sqlite3
from datetime import date
from typing import Dict, List

from .time_utils import today_beijing, tomorrow_beijing

logger = logging.getLogger(__name__)


def classify(state, db_path: str) -> dict:
    """执行赛事分类 — 北京时间窗口"""
    today = today_beijing()
    tomorrow = tomorrow_beijing()
    logger.info('=== 8:30 赛事分类 (%s ~ %s) ===', today, tomorrow)

    from core.competition.engine import CompetitionRuleEngine, classify_match
    engine = CompetitionRuleEngine()

    matches = _get_matches(db_path, today, tomorrow)
    if not matches:
        return {'route': 'normal', 'classified': 0}

    profiles = []
    for match in matches:
        profile = engine.classify(
            league_name=match.get('league_name_cn', '') or match.get('league_name', ''),
            competition_type_db=match.get('competition_type'),
            participant_type_db=match.get('participant_type'),
            home_team_type=match.get('home_team_type'),
            away_team_type=match.get('away_team_type'),
        )
        profiles.append({
            'match_id': match.get('lottery_match_id'),
            'type': profile.competition_type.value,
            'line': profile.line,
        })
        _save_profile(db_path, match, profile)

    logger.info('分类完成: %d场', len(profiles))

    return {
        'route': 'normal',
        'classified': len(profiles),
    }


def _get_matches(db_path: str, today: str, tomorrow: str) -> List[dict]:
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lm.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
                   lm.league_name_cn, lm.match_date, lm.handicap_line,
                   lm.home_team_id, lm.away_team_id,
                   l.name_en as league_name, l.league_id,
                   l.competition_type, l.participant_type,
                   ht.team_type as home_team_type, at.team_type as away_team_type
            FROM lottery_matches lm
            LEFT JOIN leagues l ON l.name_cn = lm.league_name_cn
            LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
            LEFT JOIN teams at ON lm.away_team_id = at.team_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            ORDER BY lm.match_date, lm.match_time
        """, (today, tomorrow))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error('获取比赛失败: %s', e)
        return []
    finally:
        conn.close()


def _save_profile(db_path: str, match: dict, profile):
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        profile_json = json.dumps(profile.to_dict(), ensure_ascii=False)
        cursor.execute("PRAGMA table_info(lottery_matches)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'match_profile' in columns:
            cursor.execute("UPDATE lottery_matches SET match_profile = ? WHERE lottery_match_id = ?",
                          (profile_json, match.get('lottery_match_id')))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO lottery_analysis_reports
                (lottery_match_id, report_type, report_data, created_at)
                VALUES (?, 'classification', ?, datetime('now'))
            """, (match.get('lottery_match_id'), profile_json))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug('Profile保存失败: %s', e)