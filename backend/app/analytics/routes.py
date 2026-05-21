"""
足球分析API路由

将所有分析模块的接口整合到FastAPI路由中
"""

from fastapi import APIRouter, Query, Path, HTTPException, Depends
from typing import Optional, List
import sqlite3
import os

from .elo import EloAnalyzer
from .xg import XGAnalyzer
from .poisson import PoissonPredictor
from .h2h import H2HAnalyzer
from .form import FormAnalyzer
from .home_away import HomeAwayAnalyzer
from .motivation import MotivationAnalyzer
from .news_factors import NewsFactorsAnalyzer
from .comprehensive import ComprehensiveAnalyzer

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
            'comprehensive': ComprehensiveAnalyzer(DATABASE_PATH)
        }
    return _analyzers

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    match_id: int = Path(..., description="比赛ID")
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
        return analysis
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
        return form
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
        return comparison
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
    match_id: int = Path(..., description="比赛ID")
):
    """
    根据比赛ID进行综合预测

    自动获取比赛信息并进行分析
    """
    analyzers = get_analyzers()
    conn = get_db()

    try:
        # 获取比赛信息
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                match_id,
                match_date,
                home_team_id,
                away_team_id,
                league_id,
                season_id
            FROM matches
            WHERE match_id = ?
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
        return prediction
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
    match_id: int = Path(..., description="比赛ID")
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
                l.name_en as league_name,
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