"""
足球分析API路由

将所有分析模块的接口整合到FastAPI路由中
"""

from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional, List
import sqlite3
import os
from datetime import datetime

from .elo import EloAnalyzer
from .xg import XGAnalyzer
from .poisson import PoissonPredictor
from .h2h import H2HAnalyzer
from .form import FormAnalyzer
from .home_away import HomeAwayAnalyzer
from .motivation import MotivationAnalyzer
from .news_factors import NewsFactorsAnalyzer
from .comprehensive import ComprehensiveAnalyzer
from .cup import CupAnalyzer
from .cup_factors import is_cup
from .weather import WeatherAnalyzer
from .value_bet import ValueBetAnalyzer
from .referee import RefereeAnalyzer
from .venue import VenueAnalyzer
from .fatigue import FatigueAnalyzer
from .league_impact import LeagueImpactAnalyzer
from .ml_predictor import MLPredictor
from .live_odds import LiveOddsAnalyzer
from .sofascore_crawler import SofascoreCrawler
from .social_news import SocialMediaNewsAggregator
from .thesportsdb_client import TheSportsDBClient
from .world_time import WorldTimeConverter
from .handicap import HandicapAnalyzer
from .efficiency import EfficiencyAnalyzer
from .manager_change import ManagerChangeAnalyzer
from .upset import UpsetAnalyzer
from .season_scenario import SeasonScenarioAnalyzer
from .prediction_tracker import PredictionTracker
from .weight_optimizer import WeightOptimizer

# 数据库路径
DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'football_v2.db')

# 创建路由器
router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

# 分析器实例（懒加载）
_analyzers = None

def get_analyzers():
    """获取分析器实例"""
    global _analyzers
    if _analyzers is None:
        _analyzers = {
            'elo': EloAnalyzer(DATABASE_PATH),
            'xg': XGAnalyzer(DATABASE_PATH),
            'poisson': PoissonPredictor(DATABASE_PATH),
            'h2h': H2HAnalyzer(DATABASE_PATH),
            'form': FormAnalyzer(DATABASE_PATH),
            'home_away': HomeAwayAnalyzer(DATABASE_PATH),
            'motivation': MotivationAnalyzer(DATABASE_PATH),
            'news_factors': NewsFactorsAnalyzer(DATABASE_PATH),
            'comprehensive': ComprehensiveAnalyzer(DATABASE_PATH),
            'weather': WeatherAnalyzer(DATABASE_PATH),
            'value_bet': ValueBetAnalyzer(DATABASE_PATH),
            'referee': RefereeAnalyzer(DATABASE_PATH),
            'venue': VenueAnalyzer(DATABASE_PATH),
            'fatigue': FatigueAnalyzer(DATABASE_PATH),
            'league_impact': LeagueImpactAnalyzer(DATABASE_PATH),
            'ml_predictor': MLPredictor(DATABASE_PATH),
            'live_odds': LiveOddsAnalyzer(DATABASE_PATH),
            'sofascore': SofascoreCrawler(DATABASE_PATH),
            'social_news': SocialMediaNewsAggregator(DATABASE_PATH),
            'thesportsdb': TheSportsDBClient(DATABASE_PATH),
            'world_time': WorldTimeConverter(DATABASE_PATH),
            'handicap': HandicapAnalyzer(DATABASE_PATH),
            'efficiency': EfficiencyAnalyzer(DATABASE_PATH),
            'manager_change': ManagerChangeAnalyzer(DATABASE_PATH),
            'upset': UpsetAnalyzer(DATABASE_PATH),
            'season_scenario': SeasonScenarioAnalyzer(DATABASE_PATH),
            'prediction_tracker': PredictionTracker(DATABASE_PATH),
            'weight_optimizer': WeightOptimizer(DATABASE_PATH)
        }
    return _analyzers

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# 中文名称映射缓存
_cn_team_map = None
_cn_league_map = None

def _load_cn_maps():
    """加载中文名称映射"""
    global _cn_team_map, _cn_league_map
    if _cn_team_map is None:
        conn = get_db()
        try:
            rows = conn.execute("SELECT name_en, name_cn FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''").fetchall()
            _cn_team_map = {r['name_en']: r['name_cn'] for r in rows}
            rows = conn.execute("SELECT name_en, name_cn FROM leagues WHERE name_cn IS NOT NULL AND name_cn != ''").fetchall()
            _cn_league_map = {r['name_en']: r['name_cn'] for r in rows}
        finally:
            conn.close()
    return _cn_team_map, _cn_league_map


def cnify(data):
    """将响应数据中的英文名称替换为中文名称"""
    if not data:
        return data
    team_map, league_map = _load_cn_maps()
    if isinstance(data, dict):
        result = dict(data)
        for key in ('home_team', 'away_team', 'home_team_name', 'away_team_name'):
            if key in result and result[key] and result[key] in team_map:
                cn_key = key + '_cn'
                if cn_key not in result or not result[cn_key]:
                    result[cn_key] = team_map[result[key]]
        if 'league_name' in result and result['league_name'] and result['league_name'] in league_map:
            if 'league_name_cn' not in result or not result.get('league_name_cn'):
                result['league_name_cn'] = league_map[result['league_name']]
        if 'league' in result and result['league'] and result['league'] in league_map:
            if 'league_cn' not in result or not result.get('league_cn'):
                result['league_cn'] = league_map[result['league']]
        return result
    elif isinstance(data, list):
        return [cnify(item) for item in data]
    return data


# ==================== Elo评分接口 ====================

# 注意：具体路径必须放在参数路径前面，否则会被 /elo/{team_id} 匹配

@router.get("/elo/rankings")
async def get_elo_rankings(
    league_id: Optional[int] = Query(None, description="联赛ID，不传则返回全部"),
    limit: int = Query(50, description="返回数量限制")
):
    """
    获取Elo排名列表

    返回按Elo评分排序的球队排名
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        rankings = analyzers['elo'].get_elo_rankings(league_id, limit, conn)
        return {
            'total': len(rankings),
            'league_id': league_id,
            'rankings': rankings
        }
    finally:
        conn.close()


@router.get("/elo/prediction")
async def get_elo_prediction(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID")
):
    """
    基于Elo预测比赛结果

    返回基于Elo评分的胜平负概率预测
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        prediction = analyzers['elo'].calculate_match_elo_prediction(home_team_id, away_team_id, conn)
        return prediction
    finally:
        conn.close()


@router.get("/elo/{team_id}")
async def get_team_elo(
    team_id: int = Path(..., description="球队ID"),
    include_history: bool = Query(False, description="是否包含历史记录"),
    history_days: int = Query(365, description="历史记录天数")
):
    """
    获取球队Elo评分

    返回球队当前Elo评分，可选包含历史变化记录
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        elo_rating = analyzers['elo'].get_team_elo(team_id, conn)

        result = {
            'team_id': team_id,
            'elo_rating': round(elo_rating, 2),
            'elo_level': analyzers['elo']._get_elo_level(elo_rating) if hasattr(analyzers['elo'], '_get_elo_level') else 'normal'
        }

        if include_history:
            history = analyzers['elo'].get_elo_history(team_id, history_days, conn)
            result['history'] = history

        return result
    finally:
        conn.close()


# ==================== xG预期进球接口 ====================

@router.get("/xg/prediction")
async def get_xg_prediction(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    recent_matches: int = Query(10, description="参考最近N场比赛")
):
    """
    计算预期进球(xG)

    返回基于进攻/防守统计的预期进球分析
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        xg_analysis = analyzers['xg'].calculate_simple_xg(
            home_team_id, away_team_id, recent_matches, conn
        )
        return xg_analysis
    finally:
        conn.close()


@router.get("/xg/team/{team_id}/performance")
async def get_team_xg_performance(
    team_id: int = Path(..., description="球队ID"),
    recent_matches: int = Query(20, description="参考最近N场比赛")
):
    """
    分析球队xG表现

    对比实际进球与预期进球，评估球队把握机会能力
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        performance = analyzers['xg'].analyze_team_xg_performance(team_id, recent_matches, conn)
        return performance
    finally:
        conn.close()


@router.get("/xg/match/{match_id}")
async def get_match_xg(
    match_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛xG数据

    比较不同来源的xG数据（简单模型 vs StatsBomb）
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        xg_comparison = analyzers['xg'].compare_xg_sources(match_id, conn)
        return xg_comparison
    finally:
        conn.close()


@router.get("/xg/team/{team_id}/statsbomb-stats")
async def get_team_statsbomb_xg_stats(
    team_id: int = Path(..., description="球队ID"),
    limit: int = Query(20, description="参考比赛数")
):
    """
    获取球队StatsBomb xG统计

    从射门数据聚合xG，计算效率指标
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        stats = analyzers['xg'].get_team_statsbomb_xg_stats(team_id, limit, conn)
        return stats
    finally:
        conn.close()


@router.get("/xg/league/{league_id}/season/{season_id}/rankings")
async def get_league_xg_rankings(
    league_id: int = Path(..., description="联赛ID"),
    season_id: int = Path(..., description="赛季ID")
):
    """
    获取联赛xG排名

    基于StatsBomb数据计算各队xG效率排名
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        rankings = analyzers['xg'].get_league_xg_rankings(league_id, season_id, conn)
        return {
            'league_id': league_id,
            'season_id': season_id,
            'total_teams': len(rankings),
            'rankings': rankings
        }
    finally:
        conn.close()


# ==================== Poisson预测接口 ====================

@router.get("/poisson/prediction")
async def get_poisson_prediction(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    recent_matches: int = Query(20, description="参考最近N场比赛")
):
    """
    Poisson分布预测比赛

    返回基于Poisson分布的比分概率矩阵和胜平负概率
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        prediction = analyzers['poisson'].predict_match(
            home_team_id, away_team_id, recent_matches, conn
        )
        return prediction
    finally:
        conn.close()


@router.get("/poisson/correct-score")
async def predict_correct_score(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    home_goals: int = Query(..., description="主队进球数"),
    away_goals: int = Query(..., description="客队进球数")
):
    """
    预测特定比分概率

    返回特定比分的出现概率
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        prediction = analyzers['poisson'].predict_correct_score(
            home_team_id, away_team_id, home_goals, away_goals, conn
        )
        return prediction
    finally:
        conn.close()


@router.get("/poisson/team/{team_id}/distribution")
async def get_team_goal_distribution(
    team_id: int = Path(..., description="球队ID"),
    is_home: bool = Query(True, description="是否主场"),
    recent_matches: int = Query(30, description="参考最近N场比赛")
):
    """
    获取球队进球分布

    返回球队进球数的统计分布
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        distribution = analyzers['poisson'].get_team_goal_distribution(
            team_id, is_home, recent_matches, conn
        )
        return distribution
    finally:
        conn.close()


# ==================== 交锋记录(H2H)接口 ====================

@router.get("/h2h/analysis")
async def get_h2h_analysis(
    team1_id: int = Query(..., description="球队1 ID"),
    team2_id: int = Query(..., description="球队2 ID"),
    limit: int = Query(20, description="参考最近N场交锋")
):
    """
    分析两队交锋记录

    返回历史交锋统计、心理优势分析
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        analysis = analyzers['h2h'].analyze_h2h(team1_id, team2_id, limit, conn)
        return cnify(analysis)
    finally:
        conn.close()


@router.get("/h2h/patterns")
async def get_h2h_patterns(
    team1_id: int = Query(..., description="球队1 ID"),
    team2_id: int = Query(..., description="球队2 ID")
):
    """
    分析交锋常见比分模式

    返回两队交锋中最常出现的比分
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        patterns = analyzers['h2h'].get_common_score_patterns(team1_id, team2_id, conn)
        return patterns
    finally:
        conn.close()


# ==================== 近期状态(Form)接口 ====================

@router.get("/form/team/{team_id}")
async def get_team_form(
    team_id: int = Path(..., description="球队ID"),
    recent_matches: int = Query(10, description="参考最近N场比赛")
):
    """
    分析球队近期状态

    返回近期战绩、进球统计、趋势分析
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        form = analyzers['form'].analyze_form(team_id, recent_matches, conn)
        return cnify(form)
    finally:
        conn.close()


@router.get("/form/compare")
async def compare_teams_form(
    team1_id: int = Query(..., description="球队1 ID"),
    team2_id: int = Query(..., description="球队2 ID"),
    recent_matches: int = Query(10, description="参考最近N场比赛")
):
    """
    比较两队近期状态

    返回两队状态对比和优势判断
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        comparison = analyzers['form'].compare_teams_form(team1_id, team2_id, recent_matches, conn)
        cursor = conn.cursor()
        cursor.execute("SELECT name_en, name_cn FROM teams WHERE team_id IN (?, ?)", (team1_id, team2_id))
        for row in cursor.fetchall():
            if row['team_id'] if 'team_id' in row.keys() else None:
                pass
        # Add team names
        t1 = conn.execute("SELECT name_en, name_cn FROM teams WHERE team_id = ?", (team1_id,)).fetchone()
        t2 = conn.execute("SELECT name_en, name_cn FROM teams WHERE team_id = ?", (team2_id,)).fetchone()
        if t1:
            comparison['team1_name'] = t1['name_cn'] or t1['name_en']
            comparison['team1_name_en'] = t1['name_en']
        if t2:
            comparison['team2_name'] = t2['name_cn'] or t2['name_en']
            comparison['team2_name_en'] = t2['name_en']
        return cnify(comparison)
    finally:
        conn.close()


# ==================== 主客场优势接口 ====================

@router.get("/home-away/team/{team_id}")
async def get_home_away_performance(
    team_id: int = Path(..., description="球队ID"),
    recent_matches: int = Query(20, description="参考最近N场比赛")
):
    """
    分析球队主客场表现

    返回主客场战绩对比、主场优势强度
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        performance = analyzers['home_away'].analyze_home_away_performance(team_id, recent_matches, conn)
        return performance
    finally:
        conn.close()


@router.get("/home-away/league/{league_id}")
async def get_league_home_advantage(
    league_id: int = Path(..., description="联赛ID"),
    season_id: Optional[int] = Query(None, description="赛季ID")
):
    """
    获取联赛整体主场优势统计

    返回联赛主场胜率、主场进球均值等
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        stats = analyzers['home_away'].get_league_home_advantage(league_id, season_id, conn)
        return stats
    finally:
        conn.close()


# ==================== 动机分析接口 ====================

@router.get("/motivation/team/{team_id}")
async def get_team_motivation(
    team_id: int = Path(..., description="球队ID"),
    league_id: int = Query(..., description="联赛ID"),
    season_id: int = Query(..., description="赛季ID")
):
    """
    分析球队比赛动机

    返回动机类型（争冠/保级/中游）、紧迫程度
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        motivation = analyzers['motivation'].analyze_motivation(team_id, league_id, season_id, conn=conn)
        return motivation
    finally:
        conn.close()


@router.get("/motivation/compare")
async def compare_teams_motivation(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    league_id: int = Query(..., description="联赛ID"),
    season_id: int = Query(..., description="赛季ID")
):
    """
    比较两队动机差异

    返回动机对比和优势判断
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        comparison = analyzers['motivation'].compare_teams_motivation(
            home_team_id, away_team_id, league_id, season_id, conn
        )
        return comparison
    finally:
        conn.close()


@router.get("/motivation/fatigue")
async def analyze_fatigue_factor(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    match_date: str = Query(..., description="比赛日期 YYYY-MM-DD")
):
    """
    分析疲劳因素

    返回两队休息天数和疲劳影响
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        fatigue = analyzers['motivation'].analyze_fatigue_factor(
            home_team_id, away_team_id, match_date, conn
        )
        return fatigue
    finally:
        conn.close()


@router.get("/importance")
async def analyze_match_importance(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    league_id: int = Query(..., description="联赛ID"),
    season_id: int = Query(..., description="赛季ID"),
    match_date: Optional[str] = Query(None, description="比赛日期 YYYY-MM-DD")
):
    """
    分析比赛重要性：为什么需要赢、不能输的理由

    从两队角度分析争冠、欧战、保级等形势
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        importance = analyzers['motivation'].analyze_match_importance(
            home_team_id, away_team_id, league_id, season_id, match_date, conn
        )
        return importance
    finally:
        conn.close()


# ==================== 利好利空因素接口 ====================

@router.get("/factors/team/{team_id}")
async def get_team_factors(
    team_id: int = Path(..., description="球队ID"),
    days: int = Query(30, description="分析最近N天的资讯")
):
    """
    分析球队利好利空因素

    返回近期资讯汇总、球员状态、净影响评分
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        factors = analyzers['news_factors'].analyze_team_factors(team_id, days, conn)
        return factors
    finally:
        conn.close()


@router.get("/factors/compare")
async def compare_teams_factors(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    days: int = Query(30, description="分析最近N天的资讯")
):
    """
    比较两队利好利空因素

    返回因素对比和优势判断
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        comparison = analyzers['news_factors'].compare_teams_factors(
            home_team_id, away_team_id, days, conn
        )
        return comparison
    finally:
        conn.close()


@router.get("/factors/team/{team_id}/player-status")
async def get_team_player_status(
    team_id: int = Path(..., description="球队ID")
):
    """
    获取球队球员状态汇总

    返回伤病、停赛球员统计
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        status = analyzers['news_factors'].get_player_status(team_id, conn)
        return status
    finally:
        conn.close()


# ==================== 综合预测接口 ====================

@router.get("/predict/comprehensive")
async def comprehensive_prediction(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    league_id: Optional[int] = Query(None, description="联赛ID"),
    season_id: Optional[int] = Query(None, description="赛季ID"),
    match_date: Optional[str] = Query(None, description="比赛日期 YYYY-MM-DD")
):
    """
    综合预测比赛结果

    整合所有分析维度（Elo、xG、Poisson、H2H、状态、主客场、动机、利好利空）
    生成最终预测和详细报告
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        prediction = analyzers['comprehensive'].comprehensive_prediction(
            home_team_id, away_team_id,
            league_id, season_id, match_date, conn
        )
        return prediction
    finally:
        conn.close()


@router.get("/predict/quick")
async def quick_prediction(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID")
):
    """
    快速预测比赛结果

    仅使用核心分析维度（Elo + Poisson），适用于快速响应场景
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        prediction = analyzers['comprehensive'].quick_prediction(
            home_team_id, away_team_id, conn
        )
        return prediction
    finally:
        conn.close()


@router.get("/predict/match/{match_id}")
async def predict_match_by_id(
    match_id: str = Path(..., description="比赛ID"),
    log: bool = Query(True, description="是否自动记录预测")
):
    """
    根据比赛ID进行综合预测

    自动获取比赛信息并进行分析，可选自动记录预测结果用于闭环学习
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        # 获取比赛信息
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.league_id,
                m.season_id,
                ht.name_en as home_team, ht.name_cn as home_team_cn,
                at.name_en as away_team, at.name_cn as away_team_cn,
                l.name_en as league, l.name_cn as league_cn
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            JOIN leagues l ON m.league_id = l.league_id
            WHERE m.match_id = ?
        """, (match_id,))
        match = cursor.fetchone()

        if not match:
            raise HTTPException(status_code=404, detail="比赛不存在")

        prediction = analyzers['comprehensive'].comprehensive_prediction(
            match['home_team_id'],
            match['away_team_id'],
            match['league_id'],
            match['season_id'],
            match['match_date'],
            conn
        )
        prediction['match_id'] = match_id
        prediction['home_team'] = match['home_team']
        prediction['away_team'] = match['away_team']
        prediction['league'] = match['league']
        if match['home_team_cn']:
            prediction['home_team_cn'] = match['home_team_cn']
        if match['away_team_cn']:
            prediction['away_team_cn'] = match['away_team_cn']
        if match['league_cn']:
            prediction['league_cn'] = match['league_cn']

        # 自动记录预测（闭环学习）
        if log:
            try:
                weights = analyzers['weight_optimizer'].get_active_weights()
                weights_dict = {k.replace('_weight', ''): weights[k] for k in weights if k.endswith('_weight')}
                analyzers['prediction_tracker'].log_prediction(match_id, prediction, weights_dict)
            except Exception:
                pass  # 记录失败不影响返回预测结果

        return cnify(prediction)
    finally:
        conn.close()


@router.post("/predict/batch")
async def batch_prediction(
    matches: List[dict]
):
    """
    批量预测多场比赛

    输入比赛列表，返回批量预测结果
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        results = analyzers['comprehensive'].batch_prediction(matches, conn)
        return {
            'total': len(results),
            'predictions': results
        }
    finally:
        conn.close()


# ==================== 比赛前瞻接口 ====================

@router.get("/preview/match/{match_id}")
async def get_match_preview(
    match_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛前瞻分析

    整合所有分析维度，生成完整的前瞻报告
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        # 获取比赛信息
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.home_team_id,
                m.away_team_id,
                m.league_id,
                m.season_id,
                m.round_stage,
                ht.name_en as home_team_name,
                ht.name_cn as home_team_name_cn,
                at.name_en as away_team_name,
                at.name_cn as away_team_name_cn,
                l.name_en as league_name, l.name_cn as league_name_cn,
                l.name_cn as league_name_cn
            FROM matches m
            LEFT JOIN teams ht ON m.home_team_id = ht.team_id
            LEFT JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE m.match_id = ?
        """, (match_id,))
        match = cursor.fetchone()

        if not match:
            raise HTTPException(status_code=404, detail="比赛不存在")

        # 综合预测
        prediction = analyzers['comprehensive'].comprehensive_prediction(
            match['home_team_id'],
            match['away_team_id'],
            match['league_id'],
            match['season_id'],
            match['match_date'],
            conn
        )

        return {
            'match_info': {
                'match_id': match['match_id'],
                'match_date': match['match_date'],
                'match_time': match['match_time'],
                'round_stage': match['round_stage'],
                'home_team': {
                    'id': match['home_team_id'],
                    'name_en': match['home_team_name'],
                    'name_cn': match['home_team_name_cn']
                },
                'away_team': {
                    'id': match['away_team_id'],
                    'name_en': match['away_team_name'],
                    'name_cn': match['away_team_name_cn']
                },
                'league': {
                    'id': match['league_id'],
                    'name_en': match['league_name'],
                    'name_cn': match['league_name_cn']
                }
            },
            'prediction': prediction['final_prediction'],
            'analysis_details': {
                'elo': prediction['base_prediction']['elo'],
                'xg': prediction['xg_analysis'],
                'h2h': prediction['h2h_analysis'],
                'form': prediction['form_comparison'],
                'home_away': prediction['home_away_analysis'],
                'motivation': prediction['motivation_analysis'],
                'news_factors': prediction['news_factors_analysis']
            },
            'report': prediction['report']
        }
    finally:
        conn.close()


# ==================== 天气数据接口 ====================

@router.get("/weather/city/{city}")
async def get_city_weather(
    city: str = Path(..., description="城市名称")
):
    """
    获取城市天气

    返回当前天气状况和对比赛的影响分析
    """
    analyzers = get_analyzers()
    weather = analyzers['weather'].get_weather_openweathermap(city)
    impact = analyzers['weather'].calculate_weather_impact(weather)

    return {
        'city': city,
        'weather': weather,
        'impact': impact
    }


@router.get("/weather/match/{match_id}")
async def get_match_weather(
    match_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛天气

    根据比赛地点和时间获取天气数据，并分析对比赛的影响
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['weather'].get_match_weather(match_id, conn)
        return result
    finally:
        conn.close()


@router.post("/weather/batch-update")
async def batch_update_weather(
    days: int = Query(7, description="更新未来N天的比赛天气")
):
    """
    批量更新比赛天气数据

    更新未来N天内所有比赛的天气预测
    """
    analyzers = get_analyzers()
    updated = analyzers['weather'].batch_update_weather(days)

    return {
        'success': True,
        'updated_matches': updated,
        'message': f'成功更新{updated}场比赛的天气数据'
    }


# ==================== 价值投注接口 ====================

@router.get("/value-bet/match/{match_id}")
async def analyze_match_value_bets(
    match_id: str = Path(..., description="比赛ID")
):
    """
    分析比赛的价值投注机会

    整合预测概率和市场赔率，识别价值投注
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['value_bet'].analyze_match_value_bets(match_id, conn)
        return result
    except Exception as e:
        return {'match_id': match_id, 'has_odds': False, 'message': f'价值投注分析暂不可用: {str(e)[:100]}'}
    finally:
        conn.close()


@router.get("/value-bet/scan")
async def scan_value_bets(
    days: int = Query(7, description="扫描未来N天"),
    min_edge: float = Query(0.05, description="最小优势阈值(0.05=5%)")
):
    """
    扫描未来比赛的价值投注机会

    返回所有符合条件的价值投注列表
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        value_bets = analyzers['value_bet'].scan_upcoming_value_bets(days, min_edge, conn)
        return {
            'total_matches': len(value_bets),
            'scan_params': {
                'days': days,
                'min_edge': min_edge
            },
            'value_bets': value_bets
        }
    finally:
        conn.close()


@router.post("/value-bet/analyze")
async def analyze_value_bets(
    prediction: dict,
    odds: dict
):
    """
    分析自定义预测和赔率的价值投注

    输入预测概率和赔率，返回价值投注分析
    """
    analyzers = get_analyzers()

    value_bets = analyzers['value_bet'].find_value_bets(prediction, odds)

    return {
        'prediction': prediction,
        'odds': odds,
        'value_bets': [
            {
                'market': vb.market,
                'prediction_prob': round(vb.prediction_probability * 100, 1),
                'implied_prob': round(vb.implied_probability * 100, 1),
                'odds': vb.odds,
                'edge': round(vb.edge * 100, 1),
                'value_rating': vb.value_rating,
                'kelly_fraction': round(vb.kelly_fraction * 100, 1),
                'expected_value': round(vb.expected_value * 100, 1),
                'recommendation': analyzers['value_bet']._generate_recommendation(vb)
            } for vb in value_bets
        ],
        'summary': analyzers['value_bet']._generate_summary(value_bets)
    }


@router.post("/value-bet/arbitrage")
async def find_arbitrage_opportunity(
    odds_list: List[dict]
):
    """
    计算套利机会

    输入多个庄家的赔率，计算是否存在套利机会
    """
    analyzers = get_analyzers()

    result = analyzers['value_bet'].calculate_arbitrage_opportunity(odds_list)

    if result is None:
        return {
            'has_arbitrage': False,
            'message': '未发现套利机会'
        }

    return result


@router.get("/value-bet/kelly")
async def calculate_kelly(
    prediction_prob: float = Query(..., description="预测概率(0-1)"),
    odds: float = Query(..., description="赔率"),
    fractional: float = Query(0.5, description="Kelly系数(0.5=半Kelly)")
):
    """
    计算Kelly Criterion投注比例

    返回推荐的投注资金比例
    """
    analyzers = get_analyzers()

    kelly = analyzers['value_bet'].calculate_kelly_criterion(
        prediction_prob, odds, fractional
    )
    edge = analyzers['value_bet'].calculate_edge(prediction_prob, odds)
    ev = analyzers['value_bet'].calculate_expected_value(prediction_prob, odds)
    implied = analyzers['value_bet'].calculate_implied_probability(odds)

    return {
        'prediction_prob': round(prediction_prob * 100, 1),
        'odds': odds,
        'implied_prob': round(implied * 100, 1),
        'edge': round(edge * 100, 1),
        'expected_value': round(ev * 100, 1),
        'kelly_fraction': round(kelly * 100, 1),
        'kelly_fraction_decimal': kelly,
        'value_rating': analyzers['value_bet'].assess_value_rating(edge),
        'recommendation': f"建议投注资金比例: {kelly*100:.1f}%" if kelly > 0 else "无价值投注"
    }


# ==================== 裁判分析接口 ====================

@router.get("/referee/list")
async def get_referee_list(
    limit: int = Query(50, description="返回数量限制")
):
    """
    获取裁判列表

    返回执法场次最多的裁判及其统计数据
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        referees = analyzers['referee'].get_referee_list(limit, conn)
        return {
            'total': len(referees),
            'referees': referees
        }
    finally:
        conn.close()


@router.get("/referee/{referee_name}")
async def get_referee_stats(
    referee_name: str = Path(..., description="裁判姓名")
):
    """
    获取裁判统计数据

    返回裁判的历史执法统计、风格分析
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        stats = analyzers['referee'].get_referee_stats(referee_name, conn)
        if stats is None:
            return {'error': '裁判不存在或无数据'}

        return {
            'name': stats.referee_name,
            'matches': stats.total_matches,
            'avg_yellow_cards': stats.avg_yellow_cards,
            'avg_red_cards': stats.avg_red_cards,
            'avg_penalties': stats.avg_penalties,
            'home_win_rate': stats.home_win_rate,
            'away_win_rate': stats.away_win_rate,
            'draw_rate': stats.draw_rate,
            'strictness': stats.strictness,
            'home_bias': stats.home_bias
        }
    finally:
        conn.close()


@router.get("/referee/impact/{match_id}")
async def analyze_referee_impact(
    match_id: str = Path(..., description="比赛ID")
):
    """
    分析裁判对比赛的影响

    整合裁判统计和两队历史执法记录
    """
    analyzers = get_analyzers()
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取比赛信息
        cursor.execute("""
            SELECT
                m.referee,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_team, ht.name_cn as home_team_cn,
                at.name_en as away_team, at.name_cn as away_team_cn
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_id = ?
        """, (match_id,))

        match = cursor.fetchone()
        if not match:
            return {'error': '比赛不存在'}

        referee_name = match['referee']
        if not referee_name or referee_name == 'null':
            return {
                'has_referee': False,
                'message': '该比赛暂无裁判信息'
            }

        result = analyzers['referee'].analyze_referee_impact(
            referee_name,
            match['home_team_id'],
            match['away_team_id'],
            conn
        )

        result['match_id'] = match_id
        result['home_team'] = match['home_team']
        result['away_team'] = match['away_team']

        return result
    finally:
        conn.close()


# ==================== 球场分析接口 ====================

@router.get("/venue/distance")
async def calculate_distance(
    city1: str = Query(..., description="城市1"),
    city2: str = Query(..., description="城市2")
):
    """
    计算两城市间距离

    返回直线距离(公里)
    """
    analyzers = get_analyzers()
    distance = analyzers['venue'].calculate_distance(city1, city2)

    return {
        'city1': city1,
        'city2': city2,
        'distance_km': distance
    }


@router.get("/venue/impact/{match_id}")
async def analyze_venue_impact(
    match_id: str = Path(..., description="比赛ID")
):
    """
    分析球场对比赛的影响

    整合海拔、旅行距离、历史战绩等因素
    """
    analyzers = get_analyzers()
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取比赛信息
        cursor.execute("""
            SELECT
                m.match_id,
                m.venue,
                m.venue_city,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_team, ht.name_cn as home_team_cn,
                at.name_en as away_team, at.name_cn as away_team_cn
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_id = ?
        """, (match_id,))

        match = cursor.fetchone()
        if not match:
            return {'error': '比赛不存在'}

        result = analyzers['venue'].analyze_venue_advantage(
            match['home_team_id'],
            match['away_team_id'],
            match['venue'],
            match['venue_city'],
            conn
        )

        result['match_id'] = match_id
        result['home_team'] = match['home_team']
        result['away_team'] = match['away_team']

        return result
    finally:
        conn.close()


@router.get("/venue/team/{team_id}/home-performance")
async def get_team_home_performance(
    team_id: int = Path(..., description="球队ID"),
    recent_matches: int = Query(20, description="最近N场主场")
):
    """
    获取球队主场表现

    返回主场战绩统计
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        stats = analyzers['venue'].get_team_home_performance(team_id, recent_matches, conn)
        return stats
    finally:
        conn.close()


# ==================== 疲劳度分析接口 ====================

@router.get("/fatigue/team/{team_id}")
async def get_team_fatigue(
    team_id: int = Path(..., description="球队ID"),
    match_date: str = Query(..., description="比赛日期 YYYY-MM-DD")
):
    """
    获取球队疲劳度

    返回休息天数、近期比赛数、疲劳等级
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        fatigue = analyzers['fatigue'].calculate_team_fatigue(team_id, match_date, conn)
        return {
            'team_id': team_id,
            'rest_days': fatigue.rest_days,
            'matches_7days': fatigue.matches_last_7days,
            'matches_14days': fatigue.matches_last_14days,
            'fatigue_level': fatigue.fatigue_level,
            'fatigue_factor': fatigue.fatigue_factor,
            'description': analyzers['fatigue'].get_fatigue_description(fatigue)
        }
    finally:
        conn.close()


@router.get("/fatigue/compare")
async def compare_teams_fatigue(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    match_date: str = Query(..., description="比赛日期 YYYY-MM-DD")
):
    """
    比较两队疲劳度

    返回疲劳度对比和体能优势判断
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        comparison = analyzers['fatigue'].compare_teams_fatigue(
            home_team_id, away_team_id, match_date, conn
        )
        return comparison
    finally:
        conn.close()


@router.get("/fatigue/match/{match_id}")
async def analyze_match_fatigue(
    match_id: str = Path(..., description="比赛ID")
):
    """
    分析比赛疲劳因素

    整合两队疲劳度对比
    """
    analyzers = get_analyzers()
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 获取比赛信息
        cursor.execute("""
            SELECT
                match_id,
                match_date,
                home_team_id,
                away_team_id,
                ht.name_en as home_team, ht.name_cn as home_team_cn,
                at.name_en as away_team, at.name_cn as away_team_cn
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_id = ?
        """, (match_id,))

        match = cursor.fetchone()
        if not match:
            return {'error': '比赛不存在'}

        comparison = analyzers['fatigue'].compare_teams_fatigue(
            match['home_team_id'],
            match['away_team_id'],
            match['match_date'],
            conn
        )

        comparison['match_id'] = match_id
        comparison['home_team_name'] = match['home_team']
        comparison['away_team_name'] = match['away_team']

        return comparison
    finally:
        conn.close()


# ==================== 连锁反应分析接口 ====================

@router.get("/league-impact/standings/{league_id}/{season_id}")
async def get_current_standings(
    league_id: int = Path(..., description="联赛ID"),
    season_id: int = Path(..., description="赛季ID")
):
    """
    获取当前积分榜

    返回联赛积分排名
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        standings = analyzers['league_impact'].get_current_standings(league_id, season_id, conn)
        return {
            'league_id': league_id,
            'season_id': season_id,
            'total_teams': len(standings),
            'standings': [
                {
                    'rank': i + 1,
                    'team_id': t.team_id,
                    'team': t.team_name,
                    'points': t.points,
                    'matches': t.matches,
                    'wins': t.wins,
                    'draws': t.draws,
                    'losses': t.losses,
                    'goals_for': t.goals_for,
                    'goals_against': t.goals_against,
                    'goal_diff': t.goal_diff
                } for i, t in enumerate(standings)
            ]
        }
    finally:
        conn.close()


@router.get("/league-impact/match/{match_id}")
async def analyze_match_impact(
    match_id: str = Path(..., description="比赛ID")
):
    """
    分析比赛结果的连锁影响

    模拟三种结果对积分榜的影响，分析降级/争冠/欧战形势
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['league_impact'].analyze_match_impact(match_id, conn)
        return result
    finally:
        conn.close()


@router.get("/league-impact/team/{team_id}/relegation")
async def analyze_relegation_impact(
    team_id: int = Path(..., description="球队ID"),
    league_id: int = Query(..., description="联赛ID"),
    season_id: int = Query(..., description="赛季ID")
):
    """
    分析球队降级形势

    返回降级风险评估
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        standings = analyzers['league_impact'].get_current_standings(league_id, season_id, conn)

        # 找到球队排名
        team_rank = next(
            (i + 1 for i, t in enumerate(standings) if t.team_id == team_id), None
        )

        if not team_rank:
            return {'error': '球队不在积分榜中'}

        total_teams = len(standings)
        relegation_line = total_teams - analyzers['league_impact'].RELEGATION_ZONE + 1

        team_data = next(t for t in standings if t.team_id == team_id)

        return {
            'team_id': team_id,
            'current_rank': team_rank,
            'current_points': team_data.points,
            'relegation_line': relegation_line,
            'gap_to_safe': team_rank - relegation_line if team_rank >= relegation_line else 0,
            'is_in_danger_zone': team_rank >= relegation_line,
            'teams_below': total_teams - team_rank,
            'risk_level': 'critical' if team_rank >= relegation_line else 'high' if team_rank >= relegation_line - 2 else 'moderate' if team_rank >= relegation_line - 4 else 'low'
        }
    finally:
        conn.close()


@router.get("/league-impact/team/{team_id}/title")
async def analyze_title_impact(
    team_id: int = Path(..., description="球队ID"),
    league_id: int = Query(..., description="联赛ID"),
    season_id: int = Query(..., description="赛季ID")
):
    """
    分析球队争冠形势

    返回争冠可能性评估
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        standings = analyzers['league_impact'].get_current_standings(league_id, season_id, conn)

        # 找到球队排名和榜首
        team_rank = next(
            (i + 1 for i, t in enumerate(standings) if t.team_id == team_id), None
        )

        if not team_rank:
            return {'error': '球队不在积分榜中'}

        team_data = next(t for t in standings if t.team_id == team_id)
        leader = standings[0]

        points_gap = leader.points - team_data.points
        total_matches = 38  # 默认值，后续从league_rules获取
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT total_rounds FROM league_rules WHERE league_id = ?", (league_id,))
            rule = cursor.fetchone()
            if rule and rule[0]:
                total_matches = rule[0]
        except Exception:
            pass
        matches_remaining = total_matches - team_data.matches

        # 计算追赶可能性
        max_possible_points = team_data.points + matches_remaining * 3

        return {
            'team_id': team_id,
            'current_rank': team_rank,
            'current_points': team_data.points,
            'leader_points': leader.points,
            'points_gap': points_gap,
            'matches_remaining': matches_remaining,
            'max_possible_points': max_possible_points,
            'can_mathematically_win': max_possible_points > leader.points,
            'title_probability': 'high' if team_rank == 1 else 'moderate' if points_gap <= 3 else 'low' if points_gap <= 6 else 'none'
        }
    finally:
        conn.close()


# ==================== AI预测增强接口 ====================

@router.get("/ml/predict")
async def ml_predict(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    match_date: str = Query(..., description="比赛日期 YYYY-MM-DD")
):
    """
    ML模型预测比赛

    使用特征工程和加权评分模型预测
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['ml_predictor'].predict_match(
            home_team_id, away_team_id, match_date, conn
        )
        return result
    finally:
        conn.close()


@router.get("/ml/features")
async def extract_features(
    home_team_id: int = Query(..., description="主队ID"),
    away_team_id: int = Query(..., description="客队ID"),
    match_date: str = Query(..., description="比赛日期 YYYY-MM-DD")
):
    """
    提取比赛特征

    返回用于ML预测的特征向量
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        features = analyzers['ml_predictor'].extract_features(
            home_team_id, away_team_id, match_date, conn
        )
        return {
            'home_elo': features.home_elo,
            'away_elo': features.away_elo,
            'elo_diff': features.elo_diff,
            'home_form_points': features.home_form_points,
            'away_form_points': features.away_form_points,
            'home_home_win_rate': features.home_home_win_rate,
            'away_away_win_rate': features.away_away_win_rate,
            'h2h_home_wins': features.h2h_home_wins,
            'h2h_total': features.h2h_total,
            'home_avg_goals': features.home_avg_goals,
            'away_avg_goals': features.away_avg_goals,
            'home_avg_conceded': features.home_avg_conceded,
            'away_avg_conceded': features.away_avg_conceded,
            'rest_days_diff': features.rest_days_diff
        }
    finally:
        conn.close()


@router.post("/ml/blend")
async def blend_predictions(
    ml_prediction: dict,
    elo_prediction: dict,
    poisson_prediction: dict,
    ml_weight: float = Query(0.35, description="ML权重"),
    elo_weight: float = Query(0.35, description="Elo权重"),
    poisson_weight: float = Query(0.30, description="Poisson权重")
):
    """
    融合多个预测结果

    整合ML、Elo、Poisson三种预测
    """
    analyzers = get_analyzers()

    weights = {
        'ml': ml_weight,
        'elo': elo_weight,
        'poisson': poisson_weight
    }

    result = analyzers['ml_predictor'].blend_predictions(
        ml_prediction, elo_prediction, poisson_prediction, weights
    )
    return result


# ==================== 实时赔率接口 ====================

@router.get("/odds/upcoming")
async def get_upcoming_odds(
    league: Optional[str] = Query(None, description="联赛代码 (如 soccer_epl)")
):
    """
    获取即将开始的比赛赔率

    从The Odds API获取实时赔率数据
    """
    analyzers = get_analyzers()

    odds = analyzers['live_odds'].get_upcoming_odds(league)

    # 格式化输出
    formatted = []
    for match in odds:
        best_odds = analyzers['live_odds'].get_best_odds(match.get('bookmakers', []))
        probabilities = analyzers['live_odds'].calculate_implied_probabilities({
            'home': best_odds.get('home', {}).get('odds'),
            'draw': best_odds.get('draw', {}).get('odds'),
            'away': best_odds.get('away', {}).get('odds')
        })

        formatted.append({
            'home_team': match.get('home_team'),
            'away_team': match.get('away_team'),
            'commence_time': match.get('commence_time'),
            'best_odds': best_odds,
            'implied_probabilities': probabilities,
            'bookmakers_count': len(match.get('bookmakers', []))
        })

    return {
        'total_matches': len(formatted),
        'league': league,
        'matches': formatted
    }


@router.get("/odds/leagues")
async def get_available_leagues():
    """
    获取支持的联赛列表

    返回可查询赔率的足球联赛
    """
    analyzers = get_analyzers()

    return {
        'leagues': [
            {'code': 'soccer_epl', 'name': '英超'},
            {'code': 'soccer_spain_la_liga', 'name': '西甲'},
            {'code': 'soccer_germany_bundesliga', 'name': '德甲'},
            {'code': 'soccer_italy_serie_a', 'name': '意甲'},
            {'code': 'soccer_france_ligue_one', 'name': '法甲'},
            {'code': 'soccer_uefa_champs_league', 'name': '欧冠'},
            {'code': 'soccer_uefa_europa_league', 'name': '欧联'},
            {'code': 'soccer_fifa_world_cup', 'name': '世界杯'},
            {'code': 'soccer_uefa_euro', 'name': '欧洲杯'}
        ]
    }


@router.get("/odds/best")
async def get_best_odds_analysis(
    home_odds: float = Query(..., description="主胜赔率"),
    draw_odds: float = Query(..., description="平局赔率"),
    away_odds: float = Query(..., description="客胜赔率")
):
    """
    分析最佳赔率

    计算隐含概率和真实概率
    """
    analyzers = get_analyzers()

    odds = {'home': home_odds, 'draw': draw_odds, 'away': away_odds}
    probabilities = analyzers['live_odds'].calculate_implied_probabilities(odds)

    return {
        'odds': odds,
        'analysis': probabilities
    }


@router.get("/odds/api-usage")
async def get_api_usage():
    """
    获取API使用情况

    返回The Odds API的请求配额使用情况
    """
    analyzers = get_analyzers()

    usage = analyzers['live_odds'].get_api_usage()
    return usage


@router.post("/odds/sync")
async def sync_odds_to_db(
    league: Optional[str] = Query(None, description="联赛代码")
):
    """
    同步赔率到数据库

    将API获取的赔率保存到本地数据库
    """
    analyzers = get_analyzers()

    updated = analyzers['live_odds'].sync_upcoming_odds(league)

    return {
        'success': True,
        'updated_matches': updated,
        'message': f'成功同步{updated}场比赛的赔率数据'
    }


# ==================== Sofascore实时数据接口 ====================

@router.get("/live/matches")
async def get_live_matches():
    """
    获取正在进行的比赛

    从Sofascore获取实时比分数据
    """
    analyzers = get_analyzers()

    matches = analyzers['sofascore'].get_live_matches()

    return {
        'total': len(matches),
        'matches': matches
    }


@router.get("/live/upcoming")
async def get_upcoming_matches(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD")
):
    """
    获取即将开始的比赛

    从Sofascore获取未来比赛日程
    """
    analyzers = get_analyzers()

    matches = analyzers['sofascore'].get_upcoming_matches(date)

    return {
        'date': date,
        'total': len(matches),
        'matches': matches
    }


@router.get("/live/match/{event_id}/events")
async def get_match_events(
    event_id: int = Path(..., description="Sofascore比赛ID")
):
    """
    获取比赛事件

    返回进球、红黄牌、换人等事件
    """
    analyzers = get_analyzers()

    events = analyzers['sofascore'].get_match_events(event_id)

    return {
        'event_id': event_id,
        'total_events': len(events),
        'events': events
    }


@router.get("/live/match/{event_id}/statistics")
async def get_match_statistics(
    event_id: int = Path(..., description="Sofascore比赛ID")
):
    """
    获取比赛统计

    返回控球率、射门、传球等统计数据
    """
    analyzers = get_analyzers()

    stats = analyzers['sofascore'].get_match_statistics(event_id)

    return {
        'event_id': event_id,
        'statistics': stats
    }


@router.get("/live/match/{event_id}/ratings")
async def get_player_ratings(
    event_id: int = Path(..., description="Sofascore比赛ID")
):
    """
    获取球员评分

    返回比赛中球员的实时评分
    """
    analyzers = get_analyzers()

    ratings = analyzers['sofascore'].get_player_ratings(event_id)

    return {
        'event_id': event_id,
        'total_players': len(ratings),
        'ratings': ratings
    }


@router.get("/live/team/search")
async def search_team(
    team_name: str = Query(..., description="球队名称")
):
    """
    搜索球队

    在Sofascore中搜索球队
    """
    analyzers = get_analyzers()

    teams = analyzers['sofascore'].search_team(team_name)

    return {
        'query': team_name,
        'total': len(teams),
        'teams': teams
    }


@router.get("/live/team/{team_id}/matches")
async def get_team_matches(
    team_id: int = Path(..., description="Sofascore球队ID")
):
    """
    获取球队近期比赛

    返回球队最近比赛记录
    """
    analyzers = get_analyzers()

    matches = analyzers['sofascore'].get_team_matches(team_id)

    return {
        'team_id': team_id,
        'total': len(matches),
        'matches': matches
    }


# ==================== 社交媒体新闻接口 ====================

@router.get("/news/aggregate")
async def aggregate_all_news(
    team_name: Optional[str] = Query(None, description="球队名称（可选）")
):
    """
    聚合所有来源的新闻

    整合微博、Twitter、虎扑、直播吧等平台的足球新闻
    """
    analyzers = get_analyzers()

    news = analyzers['social_news'].aggregate_all_news(team_name)

    return {
        'team_filter': team_name,
        'total': len(news),
        'news': [
            {
                'title': item.title,
                'content': item.content[:200] if len(item.content) > 200 else item.content,
                'source': item.source,
                'url': item.url,
                'published_at': item.published_at,
                'team_mentioned': item.team_mentioned,
                'sentiment': item.sentiment
            } for item in news[:50]  # 限制返回50条
        ]
    }


@router.get("/news/weibo")
async def get_weibo_news(
    keyword: str = Query('足球', description="搜索关键词")
):
    """
    获取微博足球新闻

    从微博搜索足球相关资讯
    """
    analyzers = get_analyzers()

    news = analyzers['social_news'].get_weibo_football_news(keyword)

    return {
        'keyword': keyword,
        'total': len(news),
        'news': [
            {
                'title': item.title,
                'content': item.content[:200] if len(item.content) > 200 else item.content,
                'url': item.url,
                'published_at': item.published_at,
                'team_mentioned': item.team_mentioned,
                'sentiment': item.sentiment
            } for item in news
        ]
    }


@router.get("/news/twitter")
async def get_twitter_news(
    accounts: Optional[str] = Query(None, description="Twitter账号列表(逗号分隔)")
):
    """
    获取Twitter足球新闻

    从Twitter获取足球资讯（通过Nitter RSS）
    """
    analyzers = get_analyzers()

    account_list = accounts.split(',') if accounts else None
    news = analyzers['social_news'].get_twitter_football_news(account_list)

    return {
        'accounts': account_list,
        'total': len(news),
        'news': [
            {
                'title': item.title,
                'content': item.content[:200] if len(item.content) > 200 else item.content,
                'url': item.url,
                'published_at': item.published_at,
                'team_mentioned': item.team_mentioned,
                'sentiment': item.sentiment
            } for item in news
        ]
    }


@router.get("/news/hupu")
async def get_hupu_news():
    """
    获取虎扑足球新闻

    从虎扑获取足球资讯
    """
    analyzers = get_analyzers()

    news = analyzers['social_news'].get_hupu_football_news()

    return {
        'total': len(news),
        'news': [
            {
                'title': item.title,
                'content': item.content[:200] if len(item.content) > 200 else item.content,
                'url': item.url,
                'published_at': item.published_at,
                'team_mentioned': item.team_mentioned,
                'sentiment': item.sentiment
            } for item in news
        ]
    }


@router.get("/news/zhibo8")
async def get_zhibo8_news():
    """
    获取直播吧新闻

    从直播吧获取足球资讯
    """
    analyzers = get_analyzers()

    news = analyzers['social_news'].get_zhibo8_news()

    return {
        'total': len(news),
        'news': [
            {
                'title': item.title,
                'content': item.content[:200] if len(item.content) > 200 else item.content,
                'url': item.url,
                'published_at': item.published_at,
                'team_mentioned': item.team_mentioned,
                'sentiment': item.sentiment
            } for item in news
        ]
    }


@router.get("/news/team/{team_name}")
async def get_team_news(
    team_name: str = Path(..., description="球队名称")
):
    """
    获取特定球队的新闻

    从所有来源聚合特定球队的资讯
    """
    analyzers = get_analyzers()

    # 微博搜索
    weibo_news = analyzers['social_news'].get_weibo_team_news(team_name)

    # 综合聚合
    all_news = analyzers['social_news'].aggregate_all_news(team_name)

    return {
        'team': team_name,
        'weibo_count': len(weibo_news),
        'total_count': len(all_news),
        'news': [
            {
                'title': item.title,
                'content': item.content[:200] if len(item.content) > 200 else item.content,
                'source': item.source,
                'url': item.url,
                'published_at': item.published_at,
                'sentiment': item.sentiment
            } for item in all_news[:30]
        ]
    }


# ==================== TheSportsDB 接口 ====================

@router.get("/thesportsdb/search/team")
async def search_team(
    team_name: str = Query(..., description="球队名称")
):
    """
    搜索球队

    从TheSportsDB搜索球队信息
    """
    analyzers = get_analyzers()

    teams = analyzers['thesportsdb'].search_team(team_name)

    return {
        'query': team_name,
        'total': len(teams),
        'teams': teams
    }


@router.get("/thesportsdb/search/player")
async def search_player(
    player_name: str = Query(..., description="球员名称")
):
    """
    搜索球员

    从TheSportsDB搜索球员信息
    """
    analyzers = get_analyzers()

    players = analyzers['thesportsdb'].search_player(player_name)

    return {
        'query': player_name,
        'total': len(players),
        'players': players
    }


@router.get("/thesportsdb/team/{team_id}")
async def get_team_info(
    team_id: str = Path(..., description="球队ID")
):
    """
    获取球队详情

    返回球队完整信息
    """
    analyzers = get_analyzers()

    team = analyzers['thesportsdb'].get_team_by_id(team_id)

    if not team:
        raise HTTPException(status_code=404, detail="球队不存在")

    return team


@router.get("/thesportsdb/team/{team_id}/players")
async def get_team_players_list(
    team_id: str = Path(..., description="球队ID")
):
    """
    获取球队所有球员

    返回球队阵容列表
    """
    analyzers = get_analyzers()

    players = analyzers['thesportsdb'].get_team_players(team_id)

    return {
        'team_id': team_id,
        'total': len(players),
        'players': players
    }


@router.get("/thesportsdb/team/{team_id}/events/next")
async def get_team_next_events_list(
    team_id: str = Path(..., description="球队ID"),
    limit: int = Query(10, description="返回数量")
):
    """
    获取球队即将开始的比赛

    返回未来赛程
    """
    analyzers = get_analyzers()

    events = analyzers['thesportsdb'].get_team_next_events(team_id, limit)

    return {
        'team_id': team_id,
        'total': len(events),
        'events': events
    }


@router.get("/thesportsdb/team/{team_id}/events/previous")
async def get_team_previous_events_list(
    team_id: str = Path(..., description="球队ID"),
    limit: int = Query(10, description="返回数量")
):
    """
    获取球队最近比赛

    返回历史战绩
    """
    analyzers = get_analyzers()

    events = analyzers['thesportsdb'].get_team_previous_events(team_id, limit)

    return {
        'team_id': team_id,
        'total': len(events),
        'events': events
    }


@router.get("/thesportsdb/player/{player_id}")
async def get_player_info(
    player_id: str = Path(..., description="球员ID")
):
    """
    获取球员详情

    返回球员完整信息
    """
    analyzers = get_analyzers()

    player = analyzers['thesportsdb'].get_player_by_id(player_id)

    if not player:
        raise HTTPException(status_code=404, detail="球员不存在")

    return player


@router.get("/thesportsdb/player/{player_id}/honours")
async def get_player_honours_list(
    player_id: str = Path(..., description="球员ID")
):
    """
    获取球员荣誉

    返回球员获得的荣誉列表
    """
    analyzers = get_analyzers()

    honours = analyzers['thesportsdb'].get_player_honours(player_id)

    return {
        'player_id': player_id,
        'total': len(honours),
        'honours': honours
    }


@router.get("/thesportsdb/player/{player_id}/former-teams")
async def get_player_former_teams_list(
    player_id: str = Path(..., description="球员ID")
):
    """
    获取球员前球队

    返回球员效力过的球队
    """
    analyzers = get_analyzers()

    teams = analyzers['thesportsdb'].get_player_former_teams(player_id)

    return {
        'player_id': player_id,
        'total': len(teams),
        'former_teams': teams
    }


@router.get("/thesportsdb/event/{event_id}")
async def get_event_info(
    event_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛详情

    返回比赛完整信息
    """
    analyzers = get_analyzers()

    event = analyzers['thesportsdb'].get_event_by_id(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="比赛不存在")

    return event


@router.get("/thesportsdb/event/{event_id}/lineup")
async def get_event_lineup_info(
    event_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛阵容

    返回双方首发和替补阵容
    """
    analyzers = get_analyzers()

    lineup = analyzers['thesportsdb'].get_event_lineup(event_id)

    return lineup


@router.get("/thesportsdb/event/{event_id}/timeline")
async def get_event_timeline_info(
    event_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛时间线

    返回进球、换人、黄牌等事件
    """
    analyzers = get_analyzers()

    timeline = analyzers['thesportsdb'].get_event_timeline(event_id)

    return {
        'event_id': event_id,
        'total': len(timeline),
        'timeline': timeline
    }


@router.get("/thesportsdb/event/{event_id}/statistics")
async def get_event_statistics_info(
    event_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛统计

    返回射门、控球等统计数据
    """
    analyzers = get_analyzers()

    stats = analyzers['thesportsdb'].get_event_statistics(event_id)

    return {
        'event_id': event_id,
        'total': len(stats),
        'statistics': stats
    }


@router.get("/thesportsdb/league/{league_id}/teams")
async def get_league_teams_list(
    league_id: str = Path(..., description="联赛ID")
):
    """
    获取联赛所有球队

    返回联赛参赛球队列表
    """
    analyzers = get_analyzers()

    teams = analyzers['thesportsdb'].get_league_teams(league_id)

    return {
        'league_id': league_id,
        'total': len(teams),
        'teams': teams
    }


@router.get("/thesportsdb/league/{league_id}/events/next")
async def get_league_next_events_list(
    league_id: str = Path(..., description="联赛ID"),
    limit: int = Query(10, description="返回数量")
):
    """
    获取联赛即将开始的比赛

    返回未来赛程
    """
    analyzers = get_analyzers()

    events = analyzers['thesportsdb'].get_league_next_events(league_id, limit)

    return {
        'league_id': league_id,
        'total': len(events),
        'events': events
    }


@router.get("/thesportsdb/league/{league_id}/events/previous")
async def get_league_previous_events_list(
    league_id: str = Path(..., description="联赛ID"),
    limit: int = Query(10, description="返回数量")
):
    """
    获取联赛最近比赛

    返回历史战绩
    """
    analyzers = get_analyzers()

    events = analyzers['thesportsdb'].get_league_previous_events(league_id, limit)

    return {
        'league_id': league_id,
        'total': len(events),
        'events': events
    }


@router.get("/thesportsdb/league/{league_id}/table")
async def get_league_table_info(
    league_id: str = Path(..., description="联赛ID"),
    season: Optional[str] = Query(None, description="赛季")
):
    """
    获取联赛积分榜

    返回联赛排名和积分
    """
    analyzers = get_analyzers()

    table = analyzers['thesportsdb'].get_league_table(league_id, season)

    return {
        'league_id': league_id,
        'season': season,
        'total': len(table),
        'table': table
    }


@router.get("/thesportsdb/events/day")
async def get_events_by_day_info(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    sport: str = Query('Soccer', description="运动类型"),
    league_id: Optional[str] = Query(None, description="联赛ID")
):
    """
    获取某天的比赛

    返回指定日期的所有比赛
    """
    analyzers = get_analyzers()

    events = analyzers['thesportsdb'].get_events_by_day(date, sport, league_id)

    return {
        'date': date,
        'sport': sport,
        'league_id': league_id,
        'total': len(events),
        'events': events
    }


@router.get("/thesportsdb/all/leagues")
async def get_all_leagues_list():
    """
    获取所有联赛

    返回系统支持的所有联赛
    """
    analyzers = get_analyzers()

    leagues = analyzers['thesportsdb'].get_all_leagues()

    return {
        'total': len(leagues),
        'leagues': leagues
    }


@router.get("/thesportsdb/all/countries")
async def get_all_countries_list():
    """
    获取所有国家

    返回系统支持的所有国家
    """
    analyzers = get_analyzers()

    countries = analyzers['thesportsdb'].get_all_countries()

    return {
        'total': len(countries),
        'countries': countries
    }


# ==================== 世界时间转换接口 ====================

@router.get("/time/current")
async def get_current_times():
    """
    获取主要城市当前时间

    返回全球主要足球城市的当前时间
    """
    analyzers = get_analyzers()

    times = analyzers['world_time'].get_current_times()

    return {
        'total': len(times),
        'times': times
    }


@router.get("/time/convert")
async def convert_time(
    utc_time: str = Query(..., description="UTC时间，格式: YYYY-MM-DD HH:MM"),
    target_city: Optional[str] = Query(None, description="目标城市")
):
    """
    转换UTC时间到多个时区

    将UTC时间转换为各城市本地时间
    """
    analyzers = get_analyzers()

    # 解析UTC时间字符串
    from datetime import datetime
    import pytz

    try:
        dt = datetime.strptime(utc_time, '%Y-%m-%d %H:%M')
        dt = pytz.utc.localize(dt)
    except:
        return {'error': '时间格式错误，请使用 YYYY-MM-DD HH:MM 格式'}

    if target_city:
        # 转换到单个城市
        tz = analyzers['world_time'].get_city_timezone(target_city)
        if tz:
            local_time = analyzers['world_time'].convert_time(dt, tz)
            offset = analyzers['world_time'].get_timezone_offset(tz, dt)
            return {
                'utc_time': utc_time,
                'target_city': target_city,
                'local_time': local_time.strftime('%Y-%m-%d %H:%M:%S'),
                'timezone': tz,
                'utc_offset': offset
            }
        else:
            return {'error': f'未找到城市: {target_city}'}
    else:
        # 转换到多个主要城市
        result = {'utc_time': utc_time, 'conversions': {}}
        major_cities = ['London', 'Madrid', 'Munich', 'Milan', 'Paris', 'Shanghai', 'New York', 'Tokyo']
        for city in major_cities:
            tz = analyzers['world_time'].get_city_timezone(city)
            if tz:
                local_time = analyzers['world_time'].convert_time(dt, tz)
                offset = analyzers['world_time'].get_timezone_offset(tz, dt)
                result['conversions'][city] = {
                    'local_time': local_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'timezone': tz,
                    'utc_offset': offset
                }
        return result


@router.get("/time/match/{match_id}")
async def get_match_local_times(
    match_id: str = Path(..., description="比赛ID")
):
    """
    获取比赛在多个时区的本地时间

    根据比赛时间和参赛队伍，返回多个城市的本地时间
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        # 获取比赛信息
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_team, ht.name_cn as home_team_cn,
                at.name_en as away_team, at.name_cn as away_team_cn,
                l.name_en as league_name, l.name_cn as league_name_cn
            FROM matches m
            LEFT JOIN teams ht ON m.home_team_id = ht.team_id
            LEFT JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE m.match_id = ?
        """, (match_id,))
        match = cursor.fetchone()

        if not match:
            raise HTTPException(status_code=404, detail="比赛不存在")

        # 构建UTC时间字符串
        from datetime import datetime
        import pytz

        match_time = match['match_time'] or '15:00'
        utc_time_str = f"{match['match_date']} {match_time}"
        try:
            dt = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M')
            dt = pytz.utc.localize(dt)
        except:
            dt = datetime.strptime(match['match_date'], '%Y-%m-%d')
            dt = pytz.utc.localize(dt)

        # 获取时间转换
        times = analyzers['world_time'].get_match_local_times(
            dt,
            match['home_team'],
            match['away_team']
        )

        return {
            'match_id': match_id,
            'match_date': match['match_date'],
            'match_time': match['match_time'],
            'home_team': match['home_team'],
            'away_team': match['away_team'],
            'league': match['league_name'],
            'utc_time': times.get('utc'),
            'home_team_local': times.get('home_local'),
            'away_team_local': times.get('away_local'),
            'major_cities': times.get('major_cities', [])
        }
    finally:
        conn.close()


@router.get("/time/team/{team_name}")
async def get_team_timezone_info(
    team_name: str = Path(..., description="球队名称")
):
    """
    获取球队所在城市的时区信息

    返回球队主场城市的时区和当前时间
    """
    analyzers = get_analyzers()

    city = analyzers['world_time'].get_team_city(team_name)
    tz = analyzers['world_time'].get_team_timezone(team_name)

    if not city or not tz:
        return {
            'team': team_name,
            'found': False,
            'message': '未找到球队对应的时区信息'
        }

    # 获取当前时间
    from datetime import datetime
    import pytz
    now_utc = datetime.now(pytz.utc)
    local_time = analyzers['world_time'].convert_time(now_utc, tz)
    offset = analyzers['world_time'].get_timezone_offset(tz)

    return {
        'team': team_name,
        'found': True,
        'city': city,
        'timezone': tz,
        'current_time': local_time.strftime('%Y-%m-%d %H:%M:%S'),
        'utc_offset': offset
    }


@router.get("/time/cities")
async def get_supported_cities():
    """
    获取支持的城市列表

    返回所有支持时间转换的城市
    """
    analyzers = get_analyzers()

    cities = analyzers['world_time'].get_all_cities()

    return {
        'total': len(cities),
        'cities': cities
    }


# ==================== 盘路分析接口 ====================

@router.get("/handicap/ats/{team_id}")
async def get_team_ats(
    team_id: int = Path(..., description="球队 ID"),
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    season_id: Optional[int] = Query(None, description="赛季 ID"),
    limit: int = Query(20, description="比赛数量")
):
    """
    获取球队赢盘率 (ATS)

    分析球队让球盘路的赢盘表现
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['handicap'].analyze_team_ats(
            team_id, league_id, season_id, limit, conn
        )
        return result
    finally:
        conn.close()


@router.get("/handicap/over-under/{team_id}")
async def get_team_over_under(
    team_id: int = Path(..., description="球队 ID"),
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    season_id: Optional[int] = Query(None, description="赛季 ID"),
    limit: int = Query(20, description="比赛数量")
):
    """
    获取球队大小球趋势

    分析球队大球/小球率
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['handicap'].analyze_over_under(
            team_id, league_id, season_id, limit, conn
        )
        return result
    finally:
        conn.close()


@router.get("/handicap/trend/{team_id}")
async def get_team_handicap_trend(
    team_id: int = Path(..., description="球队 ID"),
    last_n: int = Query(10, description="最近 N 场")
):
    """
    获取球队盘路趋势

    返回最近 N 场的赢盘/输盘走势
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['handicap'].get_team_handicap_trends(team_id, last_n, conn)
        return result
    finally:
        conn.close()


@router.get("/handicap/compare/{home_team_id}/{away_team_id}")
async def compare_handicap(
    home_team_id: int = Path(..., description="主队 ID"),
    away_team_id: int = Path(..., description="客队 ID")
):
    """
    比较两队盘路表现
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['handicap'].compare_teams_handicap(home_team_id, away_team_id, conn)
        return result
    finally:
        conn.close()


# ==================== 效率分析接口 ====================

@router.get("/efficiency/attacking/{team_id}")
async def get_attacking_efficiency(
    team_id: int = Path(..., description="球队 ID"),
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    season_id: Optional[int] = Query(None, description="赛季 ID"),
    limit: int = Query(20, description="比赛数量")
):
    """
    分析球队进攻效率

    包括射门转化率、射正率等指标
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['efficiency'].analyze_attacking_efficiency(
            team_id, league_id, season_id, limit, conn
        )
        return result
    finally:
        conn.close()


@router.get("/efficiency/defensive/{team_id}")
async def get_defensive_efficiency(
    team_id: int = Path(..., description="球队 ID"),
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    season_id: Optional[int] = Query(None, description="赛季 ID"),
    limit: int = Query(20, description="比赛数量")
):
    """
    分析球队防守效率

    包括零封率、场均失球等指标
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['efficiency'].analyze_defensive_efficiency(
            team_id, league_id, season_id, limit, conn
        )
        return result
    finally:
        conn.close()


@router.get("/efficiency/possession/{team_id}")
async def get_possession_efficiency(
    team_id: int = Path(..., description="球队 ID"),
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    season_id: Optional[int] = Query(None, description="赛季 ID"),
    limit: int = Query(20, description="比赛数量")
):
    """
    分析球队控球效率

    包括控球率、有效控球等指标
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['efficiency'].analyze_possession_efficiency(
            team_id, league_id, season_id, limit, conn
        )
        return result
    finally:
        conn.close()


@router.get("/efficiency/compare/{home_team_id}/{away_team_id}")
async def compare_efficiency(
    home_team_id: int = Path(..., description="主队 ID"),
    away_team_id: int = Path(..., description="客队 ID"),
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    season_id: Optional[int] = Query(None, description="赛季 ID")
):
    """
    比较两队效率
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['efficiency'].compare_efficiency(
            home_team_id, away_team_id, league_id, season_id, conn
        )
        return result
    finally:
        conn.close()


# ==================== 换帅效应接口 ====================

@router.get("/manager-change/{team_id}")
async def get_manager_change_effect(
    team_id: int = Path(..., description="球队 ID"),
    change_date: str = Query(..., description="换帅日期 YYYY-MM-DD"),
    matches_before: int = Query(10, description="换帅前场数"),
    matches_after: int = Query(10, description="换帅后场数")
):
    """
    分析换帅效应

    对比换帅前后的表现变化
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['manager_change'].analyze_team_manager_change(
            team_id, change_date, matches_before, matches_after, conn
        )
        return result
    finally:
        conn.close()


@router.get("/manager-changes/recent")
async def get_recent_manager_changes(
    limit: int = Query(20, description="返回数量")
):
    """
    获取最近换帅记录
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['manager_change'].get_recent_manager_changes(limit, conn)
        return result
    finally:
        conn.close()


@router.get("/manager-changes/league/{league_id}/{season_id}")
async def get_league_manager_changes(
    league_id: int = Path(..., description="联赛 ID"),
    season_id: int = Path(..., description="赛季 ID")
):
    """
    分析联赛内换帅效果
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['manager_change'].analyze_league_manager_changes(
            league_id, season_id, conn
        )
        return result
    finally:
        conn.close()


# ==================== 爆冷分析接口 ====================

@router.get("/upset/analysis")
async def analyze_upset_potential(
    home_team_id: int = Query(..., description="主队 ID"),
    away_team_id: int = Query(..., description="客队 ID"),
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    season_id: Optional[int] = Query(None, description="赛季 ID")
):
    """
    分析比赛爆冷潜力

    评估强弱对比及爆冷可能性
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['upset'].analyze_match_upset_potential(
            home_team_id, away_team_id, league_id, season_id, conn
        )
        return result
    finally:
        conn.close()


@router.get("/upset/scan")
async def scan_upset_matches(
    league_id: Optional[int] = Query(None, description="联赛 ID"),
    match_date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    min_probability: float = Query(25, description="最小爆冷概率")
):
    """
    扫描具有爆冷潜力的比赛
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['upset'].scan_upset_matches(
            league_id, match_date, min_probability, conn
        )
        return result
    finally:
        conn.close()


@router.get("/upset/giant-killing/{team_id}")
async def get_giant_killing_history(
    team_id: int = Path(..., description="球队 ID"),
    limit: int = Query(20, description="比赛数量")
):
    """
    获取球队爆冷赢球历史记录

    作为弱队战胜强队的记录
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['upset'].get_underdog_win_history(team_id, limit, conn)
        return result
    finally:
        conn.close()


# ==================== 赛季积分推理接口 ====================

@router.get("/season-scenario/{team_id}")
async def get_team_season_scenario(
    team_id: int = Path(..., description="球队 ID"),
    league_id: int = Query(..., description="联赛 ID"),
    season_id: int = Query(..., description="赛季 ID")
):
    """
    分析球队赛季积分形势

    包括：当前排名、距离各区域差距、剩余赛程、理论极值、关键比赛、战意评估
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['season_scenario'].analyze_team_season_scenario(
            team_id, league_id, season_id, conn
        )
        return result
    finally:
        conn.close()


@router.get("/rotation-risk/{team_id}")
async def get_rotation_risk(
    team_id: int = Path(..., description="球队 ID"),
    league_id: int = Query(..., description="联赛 ID"),
    season_id: int = Query(..., description="赛季 ID")
):
    """
    分析球队轮换风险

    判断下一场是否可能轮换：联赛形势、更关键比赛、赛程密集度
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['season_scenario'].analyze_rotation_risk(
            team_id, league_id, season_id, conn=conn
        )
        return result
    finally:
        conn.close()


@router.get("/six-pointer/{home_team_id}/{away_team_id}")
async def get_six_pointer_analysis(
    home_team_id: int = Path(..., description="主队 ID"),
    away_team_id: int = Path(..., description="客队 ID"),
    league_id: int = Query(..., description="联赛 ID"),
    season_id: int = Query(..., description="赛季 ID")
):
    """
    分析 6 分战

    判断两队是否直接竞争对手，模拟三种结果对排名的影响
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['season_scenario'].analyze_six_pointer(
            home_team_id, away_team_id, league_id, season_id, conn
        )
        return result
    finally:
        conn.close()


@router.get("/title-race/{league_id}/{season_id}")
async def get_title_race(
    league_id: int = Path(..., description="联赛 ID"),
    season_id: int = Path(..., description="赛季 ID")
):
    """
    分析争冠形势

    各队争冠概率、追赶条件
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['season_scenario'].analyze_title_race(
            league_id, season_id, conn
        )
        return result
    finally:
        conn.close()


@router.get("/relegation-battle/{league_id}/{season_id}")
async def get_relegation_battle(
    league_id: int = Path(..., description="联赛 ID"),
    season_id: int = Path(..., description="赛季 ID")
):
    """
    分析保级形势

    各队保级概率、逃脱条件
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        result = analyzers['season_scenario'].analyze_relegation_battle(
            league_id, season_id, conn
        )
        return result
    finally:
        conn.close()


# ==================== 预测追踪与闭环学习接口 ====================

@router.get("/tracking/accuracy")
async def get_prediction_accuracy(
    model_version: Optional[str] = Query(None, description="模型版本"),
    days: int = Query(30, description="统计最近N天")
):
    """
    获取预测准确率指标

    返回总体准确率、Brier Score、Log Loss、按置信度/结果分组统计
    """
    analyzers = get_analyzers()
    metrics = analyzers['prediction_tracker'].get_accuracy_metrics(model_version, days)
    return metrics


@router.get("/tracking/pending-validations")
async def get_pending_validations():
    """
    获取待验证的预测列表

    返回已结束但尚未验证的比赛预测
    """
    analyzers = get_analyzers()
    pending = analyzers['prediction_tracker'].get_pending_validations()
    return {
        'total': len(pending),
        'pending': pending
    }


@router.post("/tracking/validate")
async def validate_predictions():
    """
    验证已结束比赛的预测

    对比预测和实际赛果，计算准确度指标
    这是闭环学习的核心：预测 → 验证 → 优化
    """
    analyzers = get_analyzers()
    result = analyzers['prediction_tracker'].validate_predictions()
    return result


@router.post("/tracking/validate-batch")
async def validate_batch_predictions(
    match_ids: List[str]
):
    """
    批量验证指定比赛的预测

    输入比赛ID列表，验证这些比赛的预测
    """
    analyzers = get_analyzers()
    result = analyzers['prediction_tracker'].validate_predictions(match_ids)
    return result


@router.post("/tracking/log/{match_id}")
async def log_prediction(
    match_id: str = Path(..., description="比赛ID")
):
    """
    手动记录比赛预测

    对指定比赛执行综合分析并记录预测结果
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT home_team_id, away_team_id, league_id, season_id, match_date
            FROM matches WHERE match_id = ?
        """, (match_id,))
        match = cursor.fetchone()

        if not match:
            raise HTTPException(status_code=404, detail="比赛不存在")

        # 执行综合预测
        prediction = analyzers['comprehensive'].comprehensive_prediction(
            match['home_team_id'], match['away_team_id'],
            match['league_id'], match['season_id'], match['match_date'], conn
        )
        prediction['match_id'] = match_id

        # 获取当前权重
        weights = analyzers['weight_optimizer'].get_active_weights()
        weights_dict = {k.replace('_weight', ''): weights[k] for k in weights if k.endswith('_weight')}

        # 记录预测
        log_id = analyzers['prediction_tracker'].log_prediction(
            match_id, prediction, weights_dict
        )

        return {
            'log_id': log_id,
            'match_id': match_id,
            'predicted_result': prediction['final_prediction']['predicted_result'],
            'confidence': prediction['final_prediction']['confidence'],
            'message': '预测已记录'
        }
    finally:
        conn.close()


@router.post("/tracking/log-upcoming")
async def log_upcoming_predictions(
    days: int = Query(7, description="记录未来N天的比赛预测")
):
    """
    批量记录即将开始的比赛预测

    对未来N天内的未开赛比赛执行预测并记录
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT match_id, home_team_id, away_team_id, league_id, season_id, match_date
            FROM matches
            WHERE status IN ('not_started', 'scheduled', 'upcoming')
            AND match_date >= date('now')
            AND match_date <= date('now', ?)
            ORDER BY match_date ASC
        """, (f'+{days} days',))

        matches = cursor.fetchall()
        results = []

        weights = analyzers['weight_optimizer'].get_active_weights()
        weights_dict = {k.replace('_weight', ''): weights[k] for k in weights if k.endswith('_weight')}

        for match in matches[:50]:  # 限制50场
            try:
                prediction = analyzers['comprehensive'].comprehensive_prediction(
                    match['home_team_id'], match['away_team_id'],
                    match['league_id'], match['season_id'], match['match_date'], conn
                )
                prediction['match_id'] = match['match_id']

                log_id = analyzers['prediction_tracker'].log_prediction(
                    match['match_id'], prediction, weights_dict
                )

                results.append({
                    'match_id': match['match_id'],
                    'log_id': log_id,
                    'predicted': prediction['final_prediction']['predicted_result']
                })
            except Exception as e:
                results.append({
                    'match_id': match['match_id'],
                    'error': str(e)
                })

        return {
            'total': len(matches),
            'logged': len([r for r in results if 'log_id' in r]),
            'errors': len([r for r in results if 'error' in r]),
            'results': results
        }
    finally:
        conn.close()


@router.get("/tracking/dimension-accuracy")
async def get_dimension_accuracy(
    model_version: Optional[str] = Query(None, description="模型版本")
):
    """
    获取各分析维度的方向准确率

    返回每个子分析器（Elo、Poisson、H2H、Form等）的预测方向与实际赛果对齐的比例
    """
    analyzers = get_analyzers()
    result = analyzers['weight_optimizer'].compute_dimension_accuracy(model_version)
    return result


@router.post("/tracking/optimize-weights")
async def optimize_weights(
    force: bool = Query(False, description="强制优化（忽略样本数限制）")
):
    """
    优化分析权重

    基于历史预测的维度准确率，自动调整各子分析器的权重
    准确率高的维度增大权重，准确率低的减小权重
    """
    analyzers = get_analyzers()
    result = analyzers['weight_optimizer'].optimize_weights(force)
    return result


@router.get("/tracking/weight-history")
async def get_weight_history():
    """
    获取权重优化历史

    返回所有权重版本及其准确率
    """
    analyzers = get_analyzers()
    history = analyzers['weight_optimizer'].get_optimization_history()
    return {
        'total': len(history),
        'history': history
    }


@router.post("/tracking/rollback-weights")
async def rollback_weights(
    version: str = Query(..., description="目标版本号")
):
    """
    回滚权重到指定版本

    当新版本权重效果不佳时，可回滚到之前的版本
    """
    analyzers = get_analyzers()
    result = analyzers['weight_optimizer'].rollback_weights(version)
    return result


@router.post("/tracking/run-full-cycle")
async def run_full_learning_cycle():
    """
    执行完整的闭环学习周期

    1. 验证已结束比赛的预测
    2. 基于验证结果优化权重
    3. 记录即将开始比赛的预测（使用新权重）

    这是自主化学习的核心接口
    """
    analyzers = get_analyzers()
    results = {'steps': []}

    # Step 1: 验证
    try:
        validation = analyzers['prediction_tracker'].validate_predictions()
        results['steps'].append({
            'step': 'validate',
            'status': 'success',
            'validated_count': validation['validated_count']
        })
    except Exception as e:
        results['steps'].append({'step': 'validate', 'status': 'error', 'error': str(e)})

    # Step 2: 优化权重
    try:
        optimization = analyzers['weight_optimizer'].optimize_weights()
        results['steps'].append({
            'step': 'optimize',
            'status': 'success' if optimization.get('success') else 'skipped',
            'detail': optimization
        })
    except Exception as e:
        results['steps'].append({'step': 'optimize', 'status': 'error', 'error': str(e)})

    # Step 3: 记录新预测
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT match_id, home_team_id, away_team_id, league_id, season_id, match_date
            FROM matches
            WHERE status IN ('not_started', 'scheduled', 'upcoming')
            AND match_date >= date('now')
            AND match_date <= date('now', '+3 days')
            ORDER BY match_date ASC
        """)
        upcoming = cursor.fetchall()

        weights = analyzers['weight_optimizer'].get_active_weights()
        weights_dict = {k.replace('_weight', ''): weights[k] for k in weights if k.endswith('_weight')}

        logged = 0
        for match in upcoming[:20]:
            try:
                prediction = analyzers['comprehensive'].comprehensive_prediction(
                    match['home_team_id'], match['away_team_id'],
                    match['league_id'], match['season_id'], match['match_date'], conn
                )
                prediction['match_id'] = match['match_id']
                analyzers['prediction_tracker'].log_prediction(match['match_id'], prediction, weights_dict)
                logged += 1
            except:
                pass

        results['steps'].append({
            'step': 'log_new_predictions',
            'status': 'success',
            'logged_count': logged
        })
    finally:
        conn.close()

    results['completed_at'] = datetime.now().isoformat()
    return results


# ==================== 分析详情+Agent ====================

@router.get("/detail/{match_id}")
async def get_analysis_detail(match_id: str = Path(..., description="比赛ID")):
    """获取分析详情 — 因子分解+赔率对比+翻车归因"""
    analyzers = get_analyzers()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # 获取预测记录
        log = conn.execute("""
            SELECT pl.*, m.home_goals, m.away_goals, m.status,
                   pr.result_correct, pr.brier_score, pr.dimension_contribution
            FROM prediction_logs pl
            LEFT JOIN matches m ON pl.match_id = m.match_id
            LEFT JOIN prediction_results pr ON pl.log_id = pr.log_id
            WHERE pl.match_id = ?
            ORDER BY pl.created_at DESC LIMIT 1
        """, (match_id,)).fetchone()

        if not log:
            raise HTTPException(status_code=404, detail="No prediction found")

        result = dict(log)

        # 赔率基线 (from normalized odds table)
        odds = conn.execute("""
            SELECT home, draw, away FROM match_odds_normalized
            WHERE match_id = ? AND bookmaker = 'PINNACLE' AND snapshot_type = 'prematch' AND market = '1X2'
        """, (match_id,)).fetchone()

        # fallback to matches table odds
        if not odds:
            odds_row = conn.execute("""
                SELECT odds_home, odds_draw, odds_away FROM matches WHERE match_id = ?
            """, (match_id,)).fetchone()
            if odds_row:
                odds = odds_row

        if odds:
            result['odds'] = {'home': odds[0], 'draw': odds[1], 'away': odds[2]}

        # 因子权重
        import json
        if result.get('weights_used'):
            try:
                result['weights'] = json.loads(result['weights_used'])
            except:
                pass

        # 维度贡献
        if result.get('dimension_contribution'):
            try:
                result['contributions'] = json.loads(result['dimension_contribution'])
            except:
                pass

        # 赔率vs模型对比
        if result.get('odds'):
            o = result['odds']
            h, d, a = 1/o['home'], 1/o['draw'], 1/o['away']
            t = h + d + a
            odds_rec = max([('home_win', h/t), ('draw', d/t), ('away_win', a/t)], key=lambda x: x[1])[0]
            model_rec = result.get('predicted_result', '')
            result['model_vs_odds'] = {'agreement': odds_rec == model_rec, 'odds_rec': odds_rec}

        return cnify(result)
    finally:
        conn.close()


@router.post("/agent/warmup")
async def run_warmup():
    """执行热启动回测"""
    from backend.app.core.warmup import run_warmup
    result = run_warmup(DATABASE_PATH)
    return result


@router.post("/agent/learn")
async def run_learn():
    """执行参数学习"""
    from backend.app.core.learn import learn
    result = learn(DATABASE_PATH)
    return {"adjustments": result.adjustments, "details": result.details, "circuit_breaks": result.circuit_breaks}


@router.post("/agent/clv-update")
async def run_clv_update():
    """执行CLV赔率更新"""
    from backend.app.core.clv_update import clv_update
    result = clv_update(db_path=DATABASE_PATH)
    return result


@router.get("/agent/scene-accuracy")
async def get_scene_accuracy(days: int = Query(30, description="统计天数")):
    """获取按场景分类的准确率"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT scene_type, participant_type, total_matches,
                   model_accuracy, odds_baseline_accuracy, model_brier
            FROM model_accuracy
            WHERE period = '30d'
            ORDER BY scene_type, participant_type
        """).fetchall()
        return {"scenes": [dict(r) for r in rows]}
    finally:
        conn.close()