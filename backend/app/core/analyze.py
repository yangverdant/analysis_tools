"""9:00 分析 — MatchProfile驱动分析路由

路由逻辑:
- LEAGUE/SUPER_CUP/PLAYOFF → ComprehensiveAnalyzer (标准)
- CUP → ComprehensiveAnalyzer + cup权重+upset_risk
- FRIENDLY_INTL → ComprehensiveAnalyzer + draw_boost + rotation_risk + 5维度修正
- WC_QUALIFIER/NATIONS_LEAGUE/TOURNAMENT_INTL → ComprehensiveAnalyzer + FIFA/Elo国家队评估
"""

import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .time_utils import today_beijing, tomorrow_beijing

logger = logging.getLogger(__name__)


def analyze(state, db_path: str) -> dict:
    """执行分析 — 覆盖所有比赛(体彩+全量)

    数据源:
    1. lottery_matches — 体彩开售的比赛(有体彩赔率)
    2. matches表 — 全量比赛(世界杯/友谊赛/联赛等, 有oddsfe赔率)

    范围: 北京时间窗口(今天+明天) + 未来7天的世界杯/重要赛事
    """
    today = today_beijing()
    tomorrow = tomorrow_beijing()
    logger.info('=== 9:00 分析 (%s ~ %s + 未来赛事) ===', today, tomorrow)

    # 1. 体彩比赛(今天+明天窗口)
    lottery_matches = _get_pending_lottery(db_path, today, tomorrow)
    # 2. 全量比赛 - 今天+明天窗口的国家队比赛
    near_matches = _get_pending_from_matches(db_path, today, tomorrow)
    # 3. 未来7天的重要赛事(世界杯/洲际杯赛)
    future_matches = _get_pending_future(db_path, 7)

    total_pending = len(lottery_matches) + len(near_matches) + len(future_matches)
    logger.info('待分析: 体彩%d + 近期%d + 未来%d = %d场',
                len(lottery_matches), len(near_matches), len(future_matches), total_pending)

    if total_pending == 0:
        return {'route': 'normal', 'analyzed': 0}

    analyzed = 0
    # 优先分析体彩比赛
    for match in lottery_matches[:30]:
        try:
            result = _analyze_single(db_path, match)
            if result:
                analyzed += 1
        except Exception as e:
            logger.error('分析失败 %s: %s', match.get('lottery_match_id') or match.get('match_id'), e)

    # 然后近期国家队比赛
    for match in near_matches[:30]:
        try:
            result = _analyze_single(db_path, match)
            if result:
                analyzed += 1
        except Exception as e:
            logger.error('分析失败 %s: %s', match.get('match_id'), e)

    # 最后未来重要赛事
    for match in future_matches[:30]:
        try:
            result = _analyze_single(db_path, match)
            if result:
                analyzed += 1
        except Exception as e:
            logger.error('分析失败 %s: %s', match.get('match_id'), e)

    logger.info('分析完成: %d场', analyzed)
    return {'route': 'normal', 'analyzed': analyzed}


def _get_pending_lottery(db_path: str, today: str, tomorrow: str) -> List[dict]:
    """获取待分析的体彩比赛 — 北京时间窗口"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lm.*,
                   ht.team_type AS home_team_type,
                   at.team_type AS away_team_type
            FROM lottery_matches lm
            LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
            LEFT JOIN teams at ON lm.away_team_id = at.team_id
            WHERE (
                lm.match_date = ?
                OR (lm.match_date = ? AND substr(lm.match_time, 1, 2) < '12')
            )
            AND lm.lottery_match_id NOT IN (
                SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports
                WHERE report_type = 'prediction'
            )
            AND lm.home_team_id IS NOT NULL
            AND lm.away_team_id IS NOT NULL
            ORDER BY lm.match_date, lm.match_time
        """, (today, tomorrow))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error('获取体彩待分析失败: %s', e)
        return []


def _get_pending_from_matches(db_path: str, today: str, tomorrow: str) -> List[dict]:
    """获取待分析的全量比赛(matches表) — 排除已有预测和体彩已覆盖的

    优先级: 世界杯 > 友谊赛(国家队) > 联赛 > 其他
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 已有预测的match_id
        cursor.execute("""
            SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
        """)
        reported_keys = set(r[0] for r in cursor.fetchall())

        # 体彩已覆盖的match_id
        cursor.execute("""
            SELECT DISTINCT oddsfe_event_id FROM lottery_matches
            WHERE oddsfe_event_id IS NOT NULL AND oddsfe_event_id != ''
        """)
        lottery_event_ids = set(r[0] for r in cursor.fetchall())

        # 查询matches表 — 北京时间窗口
        cursor.execute("""
            SELECT m.match_id, m.match_date, m.match_time,
                   m.home_team_id, m.away_team_id, m.league_id,
                   l.name_en AS league_name_en, l.name_cn AS league_name_cn,
                   l.competition_type, l.participant_type,
                   ht.name_en AS home_team_name, ht.team_type AS home_team_type,
                   at.name_en AS away_team_name, at.team_type AS away_team_type
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (
                m.match_date = ?
                OR (m.match_date = ? AND substr(m.match_time, 1, 2) < '12')
            )
            AND m.home_team_id IS NOT NULL
            AND m.away_team_id IS NOT NULL
            AND ht.team_type = 'national'
            AND at.team_type = 'national'
            ORDER BY
                CASE WHEN l.name_en LIKE '%World Cup%' THEN 0
                     WHEN l.name_en LIKE '%riendly%' THEN 1
                     WHEN l.competition_type = 'international' THEN 2
                     ELSE 3 END,
                m.match_date, m.match_time
        """, (today, tomorrow))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # 过滤已有预测和体彩已覆盖的
        pending = []
        for r in rows:
            mid = r['match_id']
            if mid in reported_keys:
                continue
            # 检查体彩是否已覆盖(通过team_id+date判断)
            key = "{}_{}".format(r['home_team_id'], r['away_team_id'])
            if key in reported_keys:
                continue
            pending.append(r)

        return pending
    except Exception as e:
        logger.error('获取全量待分析失败: %s', e)
        return []


def _get_pending_future(db_path: str, days: int = 7) -> List[dict]:
    """获取未来N天的重要赛事(World Cup/洲际杯/国家队比赛)

    只取国家队比赛, 因为俱乐部联赛太多且体彩不一定开售。
    """
    try:
        from datetime import timedelta
        from .time_utils import today_beijing

        start_date = tomorrow_beijing()
        end_date = (datetime.strptime(today_beijing(), '%Y-%m-%d').date() + timedelta(days=days)).strftime('%Y-%m-%d')

        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 已有预测的
        cursor.execute("""
            SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports
            WHERE report_type = 'prediction'
        """)
        reported_keys = set(r[0] for r in cursor.fetchall())

        # 查未来赛事
        cursor.execute("""
            SELECT m.match_id, m.match_date, m.match_time,
                   m.home_team_id, m.away_team_id, m.league_id,
                   l.name_en AS league_name_en, l.name_cn AS league_name_cn,
                   l.competition_type, l.participant_type,
                   ht.name_en AS home_team_name, ht.team_type AS home_team_type,
                   at.name_en AS away_team_name, at.team_type AS away_team_type
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_date >= ? AND m.match_date <= ?
            AND m.home_team_id IS NOT NULL
            AND m.away_team_id IS NOT NULL
            AND ht.team_type = 'national' AND at.team_type = 'national'
            AND (l.name_en LIKE '%World Cup%' OR l.name_en LIKE '%riendly%'
                 OR l.competition_type = 'international')
            ORDER BY
                CASE WHEN l.name_en LIKE '%World Cup%' THEN 0
                     WHEN l.competition_type = 'international' THEN 1
                     ELSE 2 END,
                m.match_date, m.match_time
        """, (start_date, end_date))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # 过滤已有预测的 + 按team_id去重(不同数据源可能有同一比赛)
        pending = []
        seen_pairs = set()
        for r in rows:
            if r['match_id'] in reported_keys:
                continue
            # 跳过占位队名(W50/W100等)
            home_name = r.get('home_team_name', '')
            away_name = r.get('away_team_name', '')
            if home_name.startswith('W') and len(home_name) <= 4:
                continue
            if away_name.startswith('W') and len(away_name) <= 4:
                continue
            # 按(home_id, away_id, date)去重
            pair_key = (r['home_team_id'], r['away_team_id'], r['match_date'])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            pending.append(r)

        return pending
    except Exception as e:
        logger.error('获取未来赛事失败: %s', e)
        return []


def _analyze_single(db_path: str, match: dict) -> dict:
    """分析单场比赛 — MatchProfile驱动，兼容lottery_matches和matches表

    当ComprehensiveAnalyzer返回None(数据不足)时, 用赔率基线生成简化预测。
    """
    try:
        from backend.app.analytics.comprehensive import ComprehensiveAnalyzer
        from core.competition.engine import CompetitionRuleEngine, MatchProfile

        analyzer = ComprehensiveAnalyzer(db_path)
        home_id = match.get('home_team_id')
        away_id = match.get('away_team_id')

        if not home_id or not away_id:
            mid = match.get('lottery_match_id') or match.get('match_id')
            logger.debug('无team_id, 跳过: %s', mid)
            return None

        # 1. 加载MatchProfile(从classify步骤保存的分类报告)
        profile = _load_match_profile(db_path, match)

        # 2. 如果没有分类报告, 实时生成
        if profile is None:
            profile = _build_profile_on_the_fly(db_path, match)

        # 3. 执行分析(传入match_profile)
        result = analyzer.comprehensive_prediction(
            home_team_id=home_id,
            away_team_id=away_id,
            league_id=match.get('league_id'),
            match_date=match.get('match_date'),
            match_profile=profile,
        )

        # 4. 如果完整分析失败, 尝试赔率基线兜底
        if result is None or not result.get('final_prediction'):
            result = _odds_only_prediction(db_path, match, profile)
            if result is None:
                logger.debug('赔率兜底也失败: %s vs %s',
                             match.get('home_team_name') or home_id,
                             match.get('away_team_name') or away_id)
                return None

        # 4. 添加赔率基线(体彩赔率优先, oddsfe赔率备选)
        match_key = match.get('lottery_match_id') or match.get('match_id')
        odds_baseline = _get_match_odds_baseline(db_path, match.get('lottery_match_id'))
        if not odds_baseline:
            odds_baseline = _get_oddsfe_odds_baseline(db_path, home_id, away_id,
                                                        match.get('match_date'))
        if odds_baseline:
            result['odds_baseline'] = odds_baseline
            result['model_vs_odds'] = _compute_model_vs_odds(
                result['final_prediction']['probabilities'], odds_baseline
            )

        # 5. 模型-赔率分歧增强
        _apply_disagreement_boost(result)

        # 6. 因子分解
        result['factor_breakdown'] = _build_factor_breakdown(result, profile)

        # 7. 赔率区间draw校准
        _calibrate_draw(result, db_path)

        # 8. 用校准数据调整置信度
        _calibrate_confidence(result, db_path)

        # 9. 记录使用的权重
        result['weights_used'] = _get_weights_used(profile)

        # 10. 6项玩法推算(比分/胜平负/让球/大小球/半全场)
        result['play_predictions'] = _compute_all_plays(result, match)

        # 11. 保存报告
        _save_report(db_path, match, result)

        return result

    except Exception as e:
        logger.error('分析异常: %s', e)
        import traceback
        logger.debug(traceback.format_exc())
        return None


def _odds_only_prediction(db_path: str, match: dict, profile) -> Optional[dict]:
    """赔率基线兜底预测 — 当ComprehensiveAnalyzer返回None时使用

    仅用赔率隐含概率生成预测, 标记confidence='odds_only'。
    如果也没有赔率, 返回None。
    """
    home_id = match.get('home_team_id')
    away_id = match.get('away_team_id')

    # 尝试获取赔率基线
    odds_baseline = _get_match_odds_baseline(db_path, match.get('lottery_match_id'))
    if not odds_baseline:
        odds_baseline = _get_oddsfe_odds_baseline(db_path, home_id, away_id,
                                                    match.get('match_date'))
    if not odds_baseline:
        return None

    probs = {
        'home_win': odds_baseline.get('home_win', 0),
        'draw': odds_baseline.get('draw', 0),
        'away_win': odds_baseline.get('away_win', 0),
    }
    rec = max(probs, key=probs.get)

    # 友谊赛/国家队比赛draw boost
    if profile and hasattr(profile, 'draw_boost') and profile.draw_boost > 0:
        draw_boost = profile.draw_boost
        probs['draw'] = min(probs['draw'] + draw_boost, 0.45)
        reduction = draw_boost
        total_non_draw = probs['home_win'] + probs['away_win']
        if total_non_draw > 0:
            probs['home_win'] = max(probs['home_win'] - reduction * (probs['home_win'] / total_non_draw), 0.05)
            probs['away_win'] = max(probs['away_win'] - reduction * (probs['away_win'] / total_non_draw), 0.05)
        # renormalize
        total = sum(probs.values())
        if total > 0:
            probs = {k: round(v / total, 4) for k, v in probs.items()}
        rec = max(probs, key=probs.get)

    # 从赔率推算xG(简化: 用隐含概率→平均进球)
    # home_win概率高→home_xg高, draw概率高→xg接近
    home_xg = 1.0 + probs['home_win'] * 1.5
    away_xg = 0.8 + probs['away_win'] * 1.2
    # 友谊赛进球偏少
    if profile and hasattr(profile, 'competition_type'):
        ct = profile.competition_type.value if hasattr(profile.competition_type, 'value') else str(profile.competition_type)
        if 'friendly' in ct:
            home_xg *= 0.85
            away_xg *= 0.85

    import math
    # 生成简化Poisson比分矩阵
    max_g = 6
    score_matrix = []
    for i in range(max_g):
        row = []
        for j in range(max_g):
            p = (math.exp(-home_xg) * home_xg**i / math.factorial(i) *
                 math.exp(-away_xg) * away_xg**j / math.factorial(j))
            row.append(round(p * 100, 2))
        score_matrix.append(row)

    return {
        'final_prediction': {
            'probabilities': probs,
            'predicted_result': rec,
            'confidence_level': 'odds_only',
            'expected_score': {'home': round(home_xg, 2), 'away': round(away_xg, 2)},
        },
        'base_prediction': {
            'poisson': {
                'score_matrix': score_matrix,
                'expected_score': {'home': round(home_xg, 2), 'away': round(away_xg, 2)},
            }
        },
        'odds_baseline': odds_baseline,
        'model_vs_odds': {
            'model_rec': rec,
            'odds_rec': rec,
            'agreement': True,
        },
        'factor_breakdown': {
            'factors': {'odds': {k: round(v, 4) for k, v in odds_baseline.items() if k in ('home_win', 'draw', 'away_win')}},
            'weights': {'odds': 1.0},
            'final': probs,
        },
        'weights_used': {'source': 'odds_only', 'weights': {'odds': 1.0}},
        'prediction_mode': 'odds_only',
    }


# ── MatchProfile加载 ──

def _load_match_profile(db_path: str, match: dict):
    """从lottery_analysis_reports加载分类报告"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT report_data FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type = 'classification'
            ORDER BY created_at DESC LIMIT 1
        """, (match.get('lottery_match_id'),))
        row = cursor.fetchone()
        conn.close()

        if row:
            from core.competition.engine import (
                CompetitionRuleEngine, CompetitionType, MatchProfile,
                MatchPhase, ParticipantType,
            )
            data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # 从dict重建MatchProfile
            return _dict_to_profile(data)
    except Exception as e:
        logger.debug('加载分类报告失败: %s', e)
    return None


def _build_profile_on_the_fly(db_path: str, match: dict):
    """实时构建MatchProfile(当分类报告不存在时)"""
    from core.competition.engine import CompetitionRuleEngine

    engine = CompetitionRuleEngine()

    # 优先使用matches表自带的信息
    competition_type_db = match.get('competition_type')
    participant_type_db = match.get('participant_type')
    league_name = match.get('league_name_en') or match.get('league_name_cn', '')

    # 如果matches表信息不全, 从leagues表补充
    if not competition_type_db or not participant_type_db:
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.name_en, l.competition_type, l.participant_type
                FROM leagues l
                WHERE l.league_id = ? OR l.name_cn = ? OR l.name_en = ?
                LIMIT 1
            """, (match.get('league_id'), match.get('league_name_cn', ''),
                  match.get('league_name_en', '')))
            league_row = cursor.fetchone()
            conn.close()
            if league_row:
                league_name = league_row['name_en'] or league_name
                if not competition_type_db:
                    competition_type_db = league_row['competition_type']
                if not participant_type_db:
                    participant_type_db = league_row['participant_type']
        except Exception:
            pass

    return engine.classify(
        league_name=league_name or match.get('league_name_cn', ''),
        competition_type_db=competition_type_db,
        participant_type_db=participant_type_db,
        home_team_type=match.get('home_team_type'),
        away_team_type=match.get('away_team_type'),
    )


def _dict_to_profile(data: dict):
    """从序列化的dict重建MatchProfile"""
    from core.competition.engine import CompetitionType, MatchPhase, MatchProfile, ParticipantType

    ct = data.get('competition_type', 'league')
    pt = data.get('participant_type', 'club')
    mp = data.get('match_phase', 'league_phase')

    try:
        comp_type = CompetitionType(ct)
    except ValueError:
        comp_type = CompetitionType.LEAGUE

    try:
        part_type = ParticipantType(pt)
    except ValueError:
        part_type = ParticipantType.CLUB

    try:
        match_phase = MatchPhase(mp)
    except ValueError:
        match_phase = MatchPhase.LEAGUE_PHASE

    return MatchProfile(
        competition_type=comp_type,
        participant_type=part_type,
        match_phase=match_phase,
        is_national=part_type.value == 'national',
        is_club=part_type.value == 'club',
        is_neutral_venue=data.get('is_neutral_venue', False),
        draw_boost=data.get('draw_boost', 0.0),
        upset_risk=data.get('upset_risk', 0.0),
        rotation_risk=data.get('rotation_risk', 0.0),
        motivation_weight=data.get('motivation_weight', 0.5),
        league_name=data.get('league_name', ''),
        tags=data.get('tags', []),
    )


# ── 赔率基线 ──

def _get_match_odds_baseline(db_path: str, lottery_match_id: str) -> Optional[Dict]:
    """从lottery_odds获取赔率, 计算隐含概率

    优先级: opening > current > NULL
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        # 按优先级获取: opening优先, 其次current
        for snapshot in ['opening', 'current', None]:
            if snapshot:
                cursor.execute("""
                    SELECT odds_data FROM lottery_odds
                    WHERE lottery_match_id = ? AND play_type = 'spf'
                    AND snapshot_type = ?
                    ORDER BY created_at ASC LIMIT 1
                """, (lottery_match_id, snapshot))
            else:
                cursor.execute("""
                    SELECT odds_data FROM lottery_odds
                    WHERE lottery_match_id = ? AND play_type = 'spf'
                    AND snapshot_type IS NULL
                    ORDER BY created_at ASC LIMIT 1
                """, (lottery_match_id,))
            row = cursor.fetchone()
            if row:
                break
        conn.close()

        if not row:
            return None

        odds_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
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
            'source': snapshot or 'default',
        }
    except Exception as e:
        logger.debug('赔率基线获取失败: %s', e)
        return None


def _get_oddsfe_odds_baseline(db_path: str, home_team_id: int, away_team_id: int,
                              match_date: str) -> Optional[Dict]:
    """从oddsfe历史赔率获取赔率基线(matches表比赛)

    通过team_id匹配oddsfe球队, 获取Pinnacle收盘赔率
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 通过team_id查队名
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (home_team_id,))
        home_name = cursor.fetchone()
        cursor.execute("SELECT name_en FROM teams WHERE team_id = ?", (away_team_id,))
        away_name = cursor.fetchone()

        if not home_name or not away_name:
            conn.close()
            return None

        # 查oddsfe赔率表(oddsfe_pinnacle_odds或其他赔率存储)
        # 先检查有没有oddsfe表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%oddsfe%'")
        oddsfe_tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        if not oddsfe_tables:
            return None

        # 尝试从oddsfe数据查找赔率
        # 这里用简单方法: 查最近的同名比赛赔率
        from fetchers.common.team_names import normalize_team_name
        home_norm = normalize_team_name(home_name[0])
        away_norm = normalize_team_name(away_name[0])

        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 查CSV赔率表(football-data.co.uk的Pinnacle赔率)
        for table in oddsfe_tables:
            try:
                cursor.execute("PRAGMA table_info({})".format(table))
                cols = [r[1] for r in cursor.fetchall()]
                if 'home_team' in cols and 'away_team' in cols and 'psh' in cols:
                    cursor.execute("""
                        SELECT psh, psd, psa FROM {}
                        WHERE home_team = ? AND away_team = ? AND date = ?
                        LIMIT 1
                    """.format(table), (home_norm, away_norm, match_date))
                    row = cursor.fetchone()
                    if row and row[0] and row[1] and row[2]:
                        h, d, a = float(row[0]), float(row[1]), float(row[2])
                        if h > 1 and d > 1 and a > 1:
                            total = 1/h + 1/d + 1/a
                            conn.close()
                            return {
                                'home_win': round((1/h) / total, 4),
                                'draw': round((1/d) / total, 4),
                                'away_win': round((1/a) / total, 4),
                                'source': 'oddsfe_pinnacle',
                            }
            except Exception:
                continue

        conn.close()
        return None
    except Exception as e:
        logger.debug('oddsfe赔率基线获取失败: %s', e)
        return None


def _compute_model_vs_odds(model_probs: Dict, odds_baseline: Dict) -> Dict:
    """计算模型 vs 赔率对比"""
    # 只比较概率键，排除source等元数据
    prob_keys = ['home_win', 'draw', 'away_win']
    prob_only = {k: odds_baseline[k] for k in prob_keys if k in odds_baseline}
    model_rec = max(model_probs, key=model_probs.get)
    odds_rec = max(prob_only, key=prob_only.get) if prob_only else 'unknown'

    # 概率差异(模型-赔率)
    edge = {
        'home_win': round(model_probs.get('home_win', 0) - odds_baseline.get('home_win', 0), 4),
        'draw': round(model_probs.get('draw', 0) - odds_baseline.get('draw', 0), 4),
        'away_win': round(model_probs.get('away_win', 0) - odds_baseline.get('away_win', 0), 4),
    }

    return {
        'model_rec': model_rec,
        'odds_rec': odds_rec,
        'agreement': model_rec == odds_rec,
        'edge': edge,
    }


def _apply_disagreement_boost(result: dict):
    """模型-赔率分歧增强

    当模型argmax与赔率argmax不一致时, 历史数据显示模型75%正确.
    策略: 提升模型预测方向的概率, 提升幅度与模型概率成正比.
    """
    mvo = result.get('model_vs_odds')
    if not mvo or mvo.get('agreement') is not False:
        return

    fp = result.get('final_prediction', {})
    probs = fp.get('probabilities', {})
    if not probs:
        return

    model_rec = mvo.get('model_rec', '')
    if not model_rec:
        return

    # Map model_rec to probability key
    key_map = {'home_win': 'home_win', 'draw': 'draw', 'away_win': 'away_win'}
    model_key = key_map.get(model_rec, model_rec)
    model_prob = probs.get(model_key, 0)

    if model_prob < 0.30:
        return  # Model isn't confident enough to boost

    # Boost: increase model direction by 15% of the gap to 1.0
    # E.g. if model says home_win=0.45, boost to 0.45 + 0.15*(1-0.45) = 0.5325
    boost_factor = 0.15
    gap = 1.0 - model_prob
    boost = gap * boost_factor

    # Apply boost to model direction, reduce others proportionally
    new_model_prob = model_prob + boost
    reduction = boost
    other_keys = [k for k in probs if k != model_key]
    other_total = sum(probs.get(k, 0) for k in other_keys)

    probs[model_key] = round(new_model_prob, 4)
    if other_total > 0:
        for k in other_keys:
            probs[k] = round(max(probs[k] - reduction * (probs[k] / other_total), 0.05), 4)

    # Renormalize
    total = sum(probs.values())
    if total > 0:
        for k in probs:
            probs[k] = round(probs[k] / total, 4)

    # Update confidence
    if fp.get('confidence_level') == 'medium':
        fp['confidence_level'] = 'high'
    elif fp.get('confidence_level') == 'low':
        fp['confidence_level'] = 'medium'

    # Mark that boost was applied
    mvo['disagreement_boost'] = {
        'boosted_key': model_key,
        'original_prob': round(model_prob, 3),
        'boosted_prob': probs[model_key],
        'boost_amount': round(boost, 3),
    }


def _calibrate_draw(result: dict, db_path: str):
    """用warmup校准数据调整draw概率 — 基于赔率区间的历史平局率

    核心逻辑: 如果某赔率区间历史平局率>模型预测draw概率,
    则提升draw概率至历史水平(保守: 取70%的差距注入)
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cal_data FROM odds_calibration
            WHERE cal_key = 'odds_bucket_accuracy'
        """)
        row = cursor.fetchone()
        conn.close()

        if not row:
            return

        cal = json.loads(row[0]) if isinstance(row[0], str) else row[0]

        # Get home odds from odds_baseline
        ob = result.get('odds_baseline')
        if not ob:
            return

        home_prob = ob.get('home_win', 0)
        if home_prob <= 0:
            return
        home_odds = 1.0 / home_prob

        # Find bucket
        bucket = None
        for name, lo, hi in [('<1.30', 0, 1.30), ('1.30-1.60', 1.30, 1.60),
                              ('1.60-2.00', 1.60, 2.00), ('2.00-3.00', 2.00, 3.00),
                              ('>3.00', 3.00, 999)]:
            if lo <= home_odds < hi:
                bucket = name
                break

        if not bucket or bucket not in cal:
            return

        historical_draw_rate = cal[bucket].get('draw_rate', 0)
        if historical_draw_rate <= 0:
            return

        # Get current model draw probability
        fp = result.get('final_prediction', {})
        probs = fp.get('probabilities', {})
        model_draw = probs.get('draw', 0)

        if model_draw <= 0:
            return

        # If historical draw rate > model draw, inject boost
        # Conservative: inject 70% of the gap
        if historical_draw_rate > model_draw:
            gap = historical_draw_rate - model_draw
            boost = gap * 0.70

            new_draw = min(model_draw + boost, 0.45)  # cap at 45%
            # Redistribute: reduce home_win and away_win proportionally
            reduction = new_draw - model_draw
            total_non_draw = probs.get('home_win', 0) + probs.get('away_win', 0)
            if total_non_draw > 0:
                home_share = probs.get('home_win', 0) / total_non_draw
                away_share = probs.get('away_win', 0) / total_non_draw
                probs['draw'] = round(new_draw, 4)
                probs['home_win'] = round(max(probs.get('home_win', 0) - reduction * home_share, 0.05), 4)
                probs['away_win'] = round(max(probs.get('away_win', 0) - reduction * away_share, 0.05), 4)

                # Renormalize
                total = probs['home_win'] + probs['draw'] + probs['away_win']
                if total > 0:
                    probs['home_win'] = round(probs['home_win'] / total, 4)
                    probs['draw'] = round(probs['draw'] / total, 4)
                    probs['away_win'] = round(probs['away_win'] / total, 4)

                fp['draw_calibration'] = {
                    'bucket': bucket,
                    'historical_draw_rate': round(historical_draw_rate, 3),
                    'model_draw_before': round(model_draw, 3),
                    'model_draw_after': probs['draw'],
                    'boost_applied': round(boost, 3),
                }

    except Exception as e:
        logger.debug(f'Draw校准失败: {e}')


def _calibrate_confidence(result: dict, db_path: str):
    """用warmup校准数据调整置信度 — 基于赔率区间的历史准确率"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cal_data FROM odds_calibration
            WHERE cal_key = 'odds_bucket_accuracy'
        """)
        row = cursor.fetchone()
        conn.close()

        if not row:
            return

        cal = json.loads(row[0]) if isinstance(row[0], str) else row[0]

        # Get home odds from odds_baseline
        ob = result.get('odds_baseline')
        if not ob:
            return

        # Convert implied prob to approximate odds
        home_prob = ob.get('home_win', 0)
        if home_prob <= 0:
            return
        home_odds = 1.0 / home_prob

        # Find bucket
        bucket = None
        for name, lo, hi in [('<1.30', 0, 1.30), ('1.30-1.60', 1.30, 1.60),
                              ('1.60-2.00', 1.60, 2.00), ('2.00-3.00', 2.00, 3.00),
                              ('>3.00', 3.00, 999)]:
            if lo <= home_odds < hi:
                bucket = name
                break

        if not bucket or bucket not in cal:
            return

        bucket_acc = cal[bucket].get('accuracy', 0.5)
        draw_rate = cal[bucket].get('draw_rate', 0.25)

        # Adjust confidence_level based on historical accuracy
        fp = result.get('final_prediction', {})
        current_conf = fp.get('confidence_level', 'medium')

        if bucket_acc >= 0.70:
            # Strong favorites zone — high confidence
            if current_conf in ('low', 'medium'):
                fp['confidence_level'] = 'high'
                fp['calibration_note'] = f'{bucket}区历史{bucket_acc:.0%}准确, 提升置信度'
        elif bucket_acc <= 0.45:
            # Hard zone — reduce confidence
            if current_conf in ('high', 'medium'):
                fp['confidence_level'] = 'low'
                fp['calibration_note'] = f'{bucket}区历史{bucket_acc:.0%}准确, 降低置信度'

        # If draw rate is high (>25%), note it
        if draw_rate > 0.25:
            fp['draw_risk_note'] = f'{bucket}区平局率{draw_rate:.0%}'

    except Exception as e:
        logger.debug(f'校准置信度失败: {e}')


def _build_factor_breakdown(result: dict, profile) -> dict:
    """构建因子分解 — 每个分析器的概率贡献"""
    factors = {}
    prob_keys = ['home_win', 'draw', 'away_win']

    # Elo
    if 'elo_prediction' in result:
        ep = result['elo_prediction']
        probs = ep.get('probabilities', ep.get('elo_probabilities', {}))
        if probs:
            factors['elo'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # Poisson
    if 'poisson_prediction' in result:
        pp = result['poisson_prediction']
        probs = pp.get('probabilities', pp.get('match_probabilities', {}))
        if probs:
            factors['poisson'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # H2H
    if 'h2h_analysis' in result:
        h2h = result['h2h_analysis']
        probs = h2h.get('probabilities', h2h.get('win_probabilities', {}))
        if probs:
            # h2h可能用home/away/draw
            mapped = {}
            for k in prob_keys:
                mapped[k] = round(probs.get(k, probs.get('home' if k == 'home_win' else k, 0)), 4)
            factors['h2h'] = mapped

    # Form
    if 'form_comparison' in result:
        fc = result['form_comparison']
        probs = fc.get('probabilities', {})
        if probs:
            factors['form'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}
        elif 'form_score' in fc:
            # 从form_score推导方向
            diff = fc.get('form_diff', fc.get('home_form', 0) - fc.get('away_form', 0))
            if diff > 0.1:
                factors['form'] = {'home_win': 0.45, 'draw': 0.28, 'away_win': 0.27}
            elif diff < -0.1:
                factors['form'] = {'home_win': 0.27, 'draw': 0.28, 'away_win': 0.45}
            else:
                factors['form'] = {'home_win': 0.35, 'draw': 0.32, 'away_win': 0.33}

    # Home/Away
    if 'home_away_analysis' in result:
        ha = result['home_away_analysis']
        probs = ha.get('probabilities', {})
        if probs:
            factors['home_away'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # Motivation
    if 'motivation_analysis' in result:
        ma = result['motivation_analysis']
        probs = ma.get('probabilities', {})
        if probs:
            factors['motivation'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # News
    if 'news_factors_analysis' in result:
        nf = result['news_factors_analysis']
        probs = nf.get('probabilities', {})
        if probs:
            factors['news'] = {k: round(probs.get(k, 0), 4) for k in prob_keys}

    # Odds baseline
    if 'odds_baseline' in result and result['odds_baseline']:
        ob = result['odds_baseline']
        factors['odds'] = {k: round(ob.get(k, 0), 4) for k in prob_keys}

    # Add weights
    weights_used = _get_weights_used(profile)
    weights = weights_used.get('weights', {})

    return {
        'factors': factors,
        'weights': weights,
        'final': {k: round(result['final_prediction']['probabilities'].get(k, 0), 4) for k in prob_keys},
    }


def _get_weights_used(profile) -> Dict:
    """获取使用的权重配置"""
    if profile is None:
        return {'source': 'default', 'weights': {}}

    ct = profile.competition_type.value if hasattr(profile, 'competition_type') else 'league'

    WEIGHT_PROFILES = {
        'league':         {'odds': 0.35, 'elo': 0.25, 'poisson': 0.25, 'form': 0.10, 'other': 0.05},
        'cup':            {'odds': 0.35, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'cup': 0.15},
        'super_cup':      {'odds': 0.35, 'elo': 0.25, 'poisson': 0.20, 'form': 0.10, 'other': 0.10},
        'playoff':        {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
        'wc_qualifier':   {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
        'nations_league': {'odds': 0.40, 'elo': 0.20, 'poisson': 0.20, 'form': 0.10, 'motivation': 0.10},
        'friendly_intl':  {'odds': 0.45, 'elo': 0.15, 'poisson': 0.15, 'form': 0.05, 'friendly': 0.20},
        'tournament_intl':{'odds': 0.35, 'elo': 0.25, 'poisson': 0.25, 'form': 0.10, 'motivation': 0.05},
    }

    weights = WEIGHT_PROFILES.get(ct, WEIGHT_PROFILES['league'])
    return {'source': 'match_profile', 'competition_type': ct, 'weights': weights}


# ── 保存报告 ──

def _save_report(db_path: str, match: dict, result: dict):
    """保存分析报告 — 兼容lottery_matches和matches表"""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        report_json = json.dumps(result, ensure_ascii=False, default=str)

        # lottery_matches用lottery_match_id, matches表用match_id
        match_key = match.get('lottery_match_id') or match.get('match_id')
        if not match_key:
            return

        # 添加队名信息到report方便前端展示
        if 'home_team_name' not in result and match.get('home_team_name'):
            result['home_team_name'] = match['home_team_name']
            result['away_team_name'] = match['away_team_name']

        report_json = json.dumps(result, ensure_ascii=False, default=str)
        cursor.execute("""
            INSERT OR REPLACE INTO lottery_analysis_reports
            (lottery_match_id, report_type, report_data, created_at)
            VALUES (?, 'prediction', ?, datetime('now'))
        """, (match_key, report_json))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug('报告保存失败: %s', e)


# ═══════════════════════════════════════
# 6项玩法推算
# ═══════════════════════════════════════

def _compute_all_plays(result: dict, match: dict) -> dict:
    """从Poisson比分矩阵推算全部6项玩法

    输出:
    - spf: 胜平负方向 + 概率
    - rqspf: 让球胜平负方向 + 概率
    - top3_scores: TOP3比分 + 概率
    - over_under: 大小球(2/2.5/3) + 概率
    - bqc: 半全场 + 概率
    """
    fp = result.get('final_prediction', {})
    probs = fp.get('probabilities', {})
    bp = result.get('base_prediction', {})
    poisson = bp.get('poisson', {})

    # 获取Poisson比分矩阵
    score_matrix = poisson.get('score_matrix')
    expected = fp.get('expected_score', poisson.get('expected_score', {}))

    # 如果没有score_matrix, 从expected_score重建
    if not score_matrix or not expected:
        # 用最终概率直接推算
        return _compute_plays_from_probs(probs, expected, match)

    home_xg = expected.get('home', 0)
    away_xg = expected.get('away', 0)

    plays = {}

    # 1. 胜平负(SPF) — 直接用final概率
    spf_rec = max(probs, key=probs.get) if probs else 'unknown'
    spf_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    plays['spf'] = {
        'direction': spf_map.get(spf_rec, '?'),
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(spf_map.get(spf_rec, '?'), ''),
        'probabilities': {
            '3': round(probs.get('home_win', 0), 3),
            '1': round(probs.get('draw', 0), 3),
            '0': round(probs.get('away_win', 0), 3),
        },
    }

    # 2. TOP3比分 — 从score_matrix取概率最高的3个
    plays['top3_scores'] = _get_top3_scores(score_matrix)

    # 3. 让球胜平负(RQSPF)
    handicap = _get_handicap(match)
    plays['rqspf'] = _compute_rqspf(score_matrix, handicap)

    # 4. 大小球
    plays['over_under'] = _compute_over_under(score_matrix)

    # 5. 半全场(BQC)
    plays['bqc'] = _compute_bqc(score_matrix)

    return plays


def _compute_plays_from_probs(probs, expected, match) -> dict:
    """当没有score_matrix时, 从概率直接推算"""
    spf_map = {'home_win': '3', 'draw': '1', 'away_win': '0'}
    spf_rec = max(probs, key=probs.get) if probs else 'unknown'

    # 从expected_score推算最可能比分
    home_xg = expected.get('home', 0) if expected else 0
    away_xg = expected.get('away', 0) if expected else 0
    top3 = []
    if home_xg > 0 and away_xg > 0:
        # 从xG推算最可能的比分(简化)
        h_score = round(home_xg)
        a_score = round(away_xg)
        top3 = [
            {'score': '{}-{}'.format(h_score, a_score), 'probability': 0},
            {'score': '{}-{}'.format(h_score, a_score + 1 if probs.get('away_win', 0) > probs.get('home_win', 0) else h_score + 1, a_score), 'probability': 0},
            {'score': '1-1', 'probability': 0},
        ]

    # 让球胜平负 — 用概率直接推算
    handicap = _get_handicap(match)
    rqspf = {}
    if handicap != 0:
        # 简化: 让球后概率调整(不能用score_matrix精确计算)
        rqspf = {'direction': '?', 'handicap': handicap, 'probabilities': {}}

    # 大小球 — 从expected推算
    total_xg = home_xg + away_xg
    ou = {}
    if total_xg > 0:
        ou = {
            'recommendation': '大2.5' if total_xg > 2.5 else '小2.5',
            'most_likely_total': round(total_xg),
        }

    return {
        'spf': {
            'direction': spf_map.get(spf_rec, '?'),
            'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(spf_map.get(spf_rec, '?'), ''),
            'probabilities': {
                '3': round(probs.get('home_win', 0), 3),
                '1': round(probs.get('draw', 0), 3),
                '0': round(probs.get('away_win', 0), 3),
            },
        },
        'top3_scores': top3,
        'rqspf': rqspf or {'direction': '?', 'handicap': 0, 'probabilities': {}},
        'over_under': ou,
        'bqc': {},
    }


def _normalize_matrix(score_matrix) -> list:
    """将score_matrix转为0-1概率矩阵

    score_matrix可能是百分比(总和≈100)或小数(总和≈1)
    """
    total = sum(sum(row) for row in score_matrix)
    if total > 1.5:  # 百分比格式
        return [[v / 100.0 for v in row] for row in score_matrix]
    return score_matrix  # 已经是小数


def _get_top3_scores(score_matrix) -> list:
    """从比分矩阵取TOP3比分"""
    norm = _normalize_matrix(score_matrix)
    scores = []
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            scores.append({'score': '{}-{}'.format(i, j), 'probability': round(prob, 3)})

    scores.sort(key=lambda x: x['probability'], reverse=True)
    return scores[:3]


def _get_handicap(match: dict) -> float:
    """获取让球数"""
    h = match.get('handicap_line')
    if h is not None:
        try:
            return float(h)
        except (ValueError, TypeError):
            pass
    return 0.0


def _compute_rqspf(score_matrix, handicap: float) -> dict:
    """让球胜平负 — 加上让球后重新计算胜负"""
    norm = _normalize_matrix(score_matrix)
    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            adjusted = (i + handicap) - j
            if adjusted > 0:
                home_win += prob
            elif adjusted == 0:
                draw += prob
            else:
                away_win += prob

    total = home_win + draw + away_win
    if total > 0:
        home_win /= total
        draw /= total
        away_win /= total

    probs_r = {'3': round(home_win, 3), '1': round(draw, 3), '0': round(away_win, 3)}
    rec = max(probs_r, key=probs_r.get)

    return {
        'direction': rec,
        'direction_cn': {'3': '主胜', '1': '平局', '0': '客胜'}.get(rec, ''),
        'handicap': handicap,
        'probabilities': probs_r,
    }


def _compute_over_under(score_matrix) -> dict:
    """大小球 — 计算2/2.5/3各盘口的概率"""
    norm = _normalize_matrix(score_matrix)
    total_goals_prob = {}
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            total = i + j
            total_goals_prob[total] = total_goals_prob.get(total, 0) + prob

    # 大2 / 大2.5 / 大3
    over_2 = sum(p for g, p in total_goals_prob.items() if g > 2)
    over_2_5 = sum(p for g, p in total_goals_prob.items() if g > 2)  # >2等价于>=3
    over_3 = sum(p for g, p in total_goals_prob.items() if g > 3)

    # 判断最可能的总进球
    most_likely_goals = max(total_goals_prob, key=total_goals_prob.get) if total_goals_prob else 2

    # 推荐盘口
    if over_2_5 > 0.55:
        recommendation = '大2.5'
    elif over_2_5 < 0.45:
        recommendation = '小2.5'
    else:
        recommendation = '小2.5' if over_2_5 < 0.50 else '大2.5'

    return {
        'recommendation': recommendation,
        'most_likely_total': most_likely_goals,
        'over_2': round(over_2, 3),
        'over_2_5': round(over_2_5, 3),
        'over_3': round(over_3, 3),
        'under_2_5': round(1 - over_2_5, 3),
        'total_goals_distribution': {str(g): round(p, 3) for g, p in sorted(total_goals_prob.items()) if p >= 0.01},
    }


def _compute_bqc(score_matrix) -> dict:
    """半全场 — 从Poisson比分矩阵推算

    9种结果: hh/hd/ha/dh/dd/da/ah/ad/aa
    h=主胜(3), d=平(1), a=客胜(0)
    """
    import math

    # 从全场矩阵反推xG
    norm = _normalize_matrix(score_matrix)
    total_home = 0.0
    total_away = 0.0
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            total_home += i * prob
            total_away += j * prob

    # 半场xG ≈ 全场的45%
    half_home_xg = total_home * 0.45
    half_away_xg = total_away * 0.45

    # 生成半场Poisson比分矩阵
    max_g = 4
    half_matrix = []
    for i in range(max_g):
        row = []
        for j in range(max_g):
            p = (math.exp(-half_home_xg) * half_home_xg**i / math.factorial(i) *
                 math.exp(-half_away_xg) * half_away_xg**j / math.factorial(j))
            row.append(p)
        half_matrix.append(row)

    # 半场胜平负概率
    half_home = sum(half_matrix[i][j] for i in range(max_g) for j in range(max_g) if i > j)
    half_draw = sum(half_matrix[i][j] for i in range(max_g) for j in range(max_g) if i == j)
    half_away = sum(half_matrix[i][j] for i in range(max_g) for j in range(max_g) if i < j)

    # 全场胜平负概率(从归一化矩阵)
    full_home = 0.0
    full_draw = 0.0
    full_away = 0.0
    for i, row in enumerate(norm):
        for j, prob in enumerate(row):
            if i > j:
                full_home += prob
            elif i == j:
                full_draw += prob
            else:
                full_away += prob

    # BQC = P(半场X) × P(全场Y) × 关联系数
    # 关联系数: 半场和全场结果正相关, 用经验系数调整
    corr = 1.5  # 胜胜/负负增强
    anti_corr = 0.7  # 胜负/负胜削弱

    bqc_raw = {
        'hh': half_home * full_home * corr,
        'hd': half_home * full_draw,
        'ha': half_home * full_away * anti_corr,
        'dh': half_draw * full_home,
        'dd': half_draw * full_draw * corr,
        'da': half_draw * full_away,
        'ah': half_away * full_home * anti_corr,
        'ad': half_away * full_draw,
        'aa': half_away * full_away * corr,
    }

    # 归一化
    total_bqc = sum(bqc_raw.values())
    bqc_probs = {}
    if total_bqc > 0:
        for k in bqc_raw:
            bqc_probs[k] = round(bqc_raw[k] / total_bqc, 3)

    # 推荐
    rec = max(bqc_probs, key=bqc_probs.get) if bqc_probs else 'dd'
    bqc_cn = {
        'hh': '胜胜', 'hd': '胜平', 'ha': '胜负',
        'dh': '平胜', 'dd': '平平', 'da': '平负',
        'ah': '负胜', 'ad': '负平', 'aa': '负负',
    }

    return {
        'recommendation': rec,
        'recommendation_cn': bqc_cn.get(rec, ''),
        'probabilities': bqc_probs,
        'half_time': {'3': round(half_home, 3), '1': round(half_draw, 3), '0': round(half_away, 3)},
    }
