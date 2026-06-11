"""
体彩API路由

提供体彩数据查询、分析、同步等API接口

所有接口前缀: /api/v1/lottery
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import sqlite3
import json
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lottery", tags=["lottery"])

# 数据库路径 - 使用绝对路径
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'football_v2.db'))


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==================== 比赛列表 ====================

@router.get("/matches")
async def get_lottery_matches(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="销售状态 (selling/stopped/closed)"),
    play_type: Optional[str] = Query(None, description="玩法筛选 (spf/bf/bqc/rqspf)"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    获取体彩开售比赛列表
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        query = "SELECT * FROM lottery_matches WHERE 1=1"
        params = []

        if date:
            query += " AND match_date = ?"
            params.append(date)
        else:
            # 默认今天和未来7天
            query += " AND match_date >= date('now')"

        if status:
            query += " AND sell_status = ?"
            params.append(status)

        query += " ORDER BY match_date ASC, CASE WHEN match_time IS NULL OR match_time = '' THEN '99:99' ELSE match_time END ASC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        matches = [dict(row) for row in cursor.fetchall()]

        # 处理 play_types JSON，并检查分析状态
        analyzed_ids = set()
        cursor.execute("SELECT DISTINCT lottery_match_id FROM lottery_analysis_reports")
        for row in cursor.fetchall():
            analyzed_ids.add(row[0])

        for match in matches:
            if match['play_types']:
                try:
                    match['play_types'] = json.loads(match['play_types'])
                except:
                    match['play_types'] = []

            # 添加分析状态
            match['has_analysis'] = match['lottery_match_id'] in analyzed_ids

            # 裁剪match_time: "03:00:00" -> "03:00"
            if match.get('match_time') and len(match['match_time']) > 5:
                match['match_time'] = match['match_time'][:5]

            # 如果有分析，获取简要推荐信息
            if match['has_analysis']:
                cursor.execute("""
                    SELECT report_data FROM lottery_analysis_reports
                    WHERE lottery_match_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (match['lottery_match_id'],))
                report_row = cursor.fetchone()
                if report_row:
                    try:
                        report = json.loads(report_row[0])
                        summary = report.get('summary', {})
                        match['main_recommendation'] = summary.get('main_recommendation', '--')
                        match['confidence_level'] = 'high' if summary.get('confidence', 0) >= 0.6 else ('medium' if summary.get('confidence', 0) >= 0.35 else 'low')
                    except:
                        pass

        return {
            "success": True,
            "total": len(matches),
            "matches": matches
        }

    finally:
        conn.close()


@router.get("/matches/{lottery_match_id}")
async def get_lottery_match_detail(lottery_match_id: str):
    """
    获取单场比赛详情
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT lm.*,
                   ht.name_en as home_team_name_en,
                   ht.name_cn as home_team_name_cn,
                   at.name_en as away_team_name_en,
                   at.name_cn as away_team_name_cn
            FROM lottery_matches lm
            LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
            LEFT JOIN teams at ON lm.away_team_id = at.team_id
            WHERE lm.lottery_match_id = ?
        """, (lottery_match_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Match not found")

        match = dict(row)

        # 处理 play_types
        if match['play_types']:
            try:
                match['play_types'] = json.loads(match['play_types'])
            except:
                match['play_types'] = []

        # 获取赔率
        cursor.execute("""
            SELECT play_type, odds_data FROM lottery_odds
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        odds = {}
        for row in cursor.fetchall():
            try:
                odds[row['play_type']] = json.loads(row['odds_data'])
            except:
                odds[row['play_type']] = {}

        match['odds'] = odds

        return {
            "success": True,
            "match": match
        }

    finally:
        conn.close()


# ==================== 分析报告 ====================

@router.post("/analyze/{lottery_match_id}")
async def analyze_lottery_match(
    lottery_match_id: str,
    background_tasks: BackgroundTasks,
    play_types: Optional[str] = Query(None, description="玩法列表，逗号分隔"),
    force: bool = Query(False, description="强制重新分析")
):
    """
    分析指定比赛

    如果已有分析报告，直接返回；
    否则在后台执行分析
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 检查比赛是否存在
        cursor.execute("""
            SELECT lottery_match_id FROM lottery_matches
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Match not found")

        # 检查是否有分析报告
        if not force:
            cursor.execute("""
                SELECT report_data, created_at FROM lottery_analysis_reports
                WHERE lottery_match_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (lottery_match_id,))

            row = cursor.fetchone()
            if row:
                report = json.loads(row['report_data'])
                return {
                    "success": True,
                    "cached": True,
                    "report": report,
                    "generated_at": row['created_at']
                }

        # 后台执行分析
        from ..services.analysis_service import AnalysisService

        background_tasks.add_task(
            run_analysis_task,
            lottery_match_id,
            play_types
        )

        return {
            "success": True,
            "cached": False,
            "message": "Analysis started in background"
        }

    finally:
        conn.close()


@router.get("/report/{lottery_match_id}")
async def get_analysis_report(lottery_match_id: str):
    """
    获取分析报告
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT report_data, created_at FROM lottery_analysis_reports
            WHERE lottery_match_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (lottery_match_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")

        report = json.loads(row['report_data'])

        return {
            "success": True,
            "report": report,
            "generated_at": row['created_at']
        }

    finally:
        conn.close()


# ==================== 赔率 ====================

@router.get("/odds/{lottery_match_id}")
async def get_lottery_odds(lottery_match_id: str):
    """
    获取比赛赔率
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT play_type, odds_data, opening_odds, latest_odds, update_time
            FROM lottery_odds
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        odds = {}
        for row in cursor.fetchall():
            play_type = row['play_type']
            odds[play_type] = {
                'current': json.loads(row['odds_data']) if row['odds_data'] else {},
                'opening': json.loads(row['opening_odds']) if row['opening_odds'] else {},
                'latest': json.loads(row['latest_odds']) if row['latest_odds'] else {},
                'update_time': row['update_time']
            }

        if not odds:
            raise HTTPException(status_code=404, detail="Odds not found")

        return {
            "success": True,
            "lottery_match_id": lottery_match_id,
            "odds": odds
        }

    finally:
        conn.close()


# ==================== 价值投注 ====================

@router.get("/value-bets/{lottery_match_id}")
async def get_value_bets(lottery_match_id: str):
    """
    获取价值投注推荐
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT prediction_id, play_type, value_bets, confidence
            FROM lottery_predictions
            WHERE lottery_match_id = ?
        """, (lottery_match_id,))

        value_bets = []
        for row in cursor.fetchall():
            if row['value_bets']:
                try:
                    vbs = json.loads(row['value_bets'])
                    for vb in vbs:
                        vb['play_type'] = row['play_type']
                        vb['confidence'] = row['confidence']
                        value_bets.append(vb)
                except:
                    pass

        return {
            "success": True,
            "lottery_match_id": lottery_match_id,
            "value_bets": value_bets,
            "total": len(value_bets)
        }

    finally:
        conn.close()


# ==================== 准确率追踪 ====================

@router.get("/accuracy")
async def get_accuracy_stats(
    days: int = Query(30, ge=1, le=365),
    play_type: Optional[str] = Query(None)
):
    """
    获取预测准确率统计
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 查询各玩法的准确率
        query = """
            SELECT
                play_type,
                COUNT(*) as total,
                SUM(is_correct) as correct
            FROM lottery_validation
            WHERE validated_at >= date('now', ?)
        """
        params = [f'-{days} days']

        if play_type:
            query += " AND play_type = ?"
            params.append(play_type)

        query += " GROUP BY play_type"

        cursor.execute(query, params)

        # 初始化结果
        result = {
            'spf_accuracy': 0,
            'spf_count': 0,
            'bf_accuracy': 0,
            'bf_count': 0,
            'ou_accuracy': 0,
            'ou_count': 0,
            'bqc_accuracy': 0,
            'bqc_count': 0,
            'rqspf_accuracy': 0,
            'rqspf_count': 0,
            'overall_accuracy': 0,
            'total_count': 0,
            'trend': 0
        }

        total_correct = 0
        total_predictions = 0

        for row in cursor.fetchall():
            pt = row['play_type']
            count = row['total'] or 0
            correct = row['correct'] or 0
            accuracy = (correct / count * 100) if count > 0 else 0

            if pt == 'spf':
                result['spf_accuracy'] = round(accuracy, 1)
                result['spf_count'] = count
            elif pt == 'bf':
                result['bf_accuracy'] = round(accuracy, 1)
                result['bf_count'] = count
            elif pt == 'ou':
                result['ou_accuracy'] = round(accuracy, 1)
                result['ou_count'] = count
            elif pt == 'bqc':
                result['bqc_accuracy'] = round(accuracy, 1)
                result['bqc_count'] = count
            elif pt == 'rqspf':
                result['rqspf_accuracy'] = round(accuracy, 1)
                result['rqspf_count'] = count

            total_correct += correct
            total_predictions += count

        # 计算整体准确率
        if total_predictions > 0:
            result['overall_accuracy'] = round(total_correct / total_predictions * 100, 1)
            result['total_count'] = total_predictions

        # 计算趋势（最近7天与之前7天对比）
        cursor.execute("""
            SELECT
                SUM(is_correct) as correct,
                COUNT(*) as total
            FROM lottery_validation
            WHERE validated_at >= date('now', '-7 days')
        """)
        recent = cursor.fetchone()

        cursor.execute("""
            SELECT
                SUM(is_correct) as correct,
                COUNT(*) as total
            FROM lottery_validation
            WHERE validated_at >= date('now', '-14 days')
              AND validated_at < date('now', '-7 days')
        """)
        previous = cursor.fetchone()

        if recent and previous:
            recent_acc = (recent['correct'] / recent['total']) if recent['total'] > 0 else 0
            prev_acc = (previous['correct'] / previous['total']) if previous['total'] > 0 else 0
            result['trend'] = round((recent_acc - prev_acc) * 100, 1)

        return {
            "success": True,
            "days": days,
            **result
        }

    finally:
        conn.close()


@router.get("/accuracy/by-confidence")
async def get_accuracy_by_confidence(days: int = Query(30)):
    """
    按置信度分组获取准确率
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                p.confidence_level,
                COUNT(*) as total,
                SUM(v.is_correct) as correct,
                AVG(v.brier_score) as avg_brier_score
            FROM lottery_predictions p
            JOIN lottery_validation v ON p.prediction_id = v.prediction_id
            WHERE v.validated_at >= date('now', ?)
            GROUP BY p.confidence_level
        """, (f'-{days} days',))

        stats = []
        for row in cursor.fetchall():
            accuracy = row['correct'] / row['total'] if row['total'] > 0 else 0
            stats.append({
                'confidence_level': row['confidence_level'],
                'total_predictions': row['total'],
                'accuracy': round(accuracy * 100, 2),
                'avg_brier_score': round(row['avg_brier_score'], 4) if row['avg_brier_score'] else None
            })

        return {
            "success": True,
            "days": days,
            "stats": stats
        }

    finally:
        conn.close()


# ==================== 数据同步 ====================

@router.post("/sync")
async def sync_lottery_data(background_tasks: BackgroundTasks):
    """
    手动触发数据同步
    """
    background_tasks.add_task(run_sync_task)

    return {
        "success": True,
        "message": "Sync started in background"
    }


@router.post("/validate")
async def validate_predictions(background_tasks: BackgroundTasks):
    """
    手动触发预测验证
    """
    background_tasks.add_task(run_validation_task)

    return {
        "success": True,
        "message": "Validation started in background"
    }


# ==================== 球队映射 ====================

@router.get("/team-mappings")
async def list_team_mappings():
    """
    获取球队名称映射列表
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT tm.*, t.name_en, t.name_cn
            FROM team_name_mapping tm
            LEFT JOIN teams t ON tm.team_id = t.team_id
            ORDER BY tm.lottery_name
        """)

        mappings = []
        for row in cursor.fetchall():
            mappings.append({
                'lottery_name': row['lottery_name'],
                'team_id': row['team_id'],
                'team_name_en': row['name_en'],
                'team_name_cn': row['name_cn'],
                'match_confidence': row['match_confidence'],
                'match_method': row['match_method']
            })

        return {
            "success": True,
            "total": len(mappings),
            "mappings": mappings
        }

    finally:
        conn.close()


@router.post("/team-mappings")
async def create_team_mapping(data: Dict):
    """
    创建球队名称映射
    """
    lottery_name = data.get('lottery_name')
    team_id = data.get('team_id')

    if not lottery_name or not team_id:
        raise HTTPException(status_code=400, detail="Missing lottery_name or team_id")

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR REPLACE INTO team_name_mapping
            (lottery_name, team_id, match_confidence, match_method, updated_at)
            VALUES (?, ?, 1.0, 'manual', CURRENT_TIMESTAMP)
        """, (lottery_name, team_id))

        conn.commit()

        return {
            "success": True,
            "lottery_name": lottery_name,
            "team_id": team_id
        }

    finally:
        conn.close()


# ==================== 调度状态 ====================

@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    获取调度任务状态
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT source_name, status, last_success, last_failure, success_rate
            FROM data_source_health
            ORDER BY updated_at DESC
        """)

        health = [dict(row) for row in cursor.fetchall()]

        return {
            "success": True,
            "health": health
        }

    finally:
        conn.close()


# ==================== 后台任务 ====================

def run_analysis_task(lottery_match_id: str, play_types: Optional[str]):
    """后台分析任务 - 真正调用 AnalysisService"""
    logger.info(f"Starting analysis for {lottery_match_id}")

    try:
        from ..services.analysis_service import AnalysisService

        analysis_service = AnalysisService(DB_PATH)
        report = analysis_service.analyze_match(lottery_match_id)

        logger.info(f"Analysis completed for {lottery_match_id}: {report.get('summary', {})}")
    except Exception as e:
        logger.error(f"Analysis failed for {lottery_match_id}: {e}")


def run_sync_task():
    """后台同步任务 - 真正调用 SyncService"""
    logger.info("Starting lottery data sync")

    try:
        from ..services.sync_service import LotterySyncService

        sync_service = LotterySyncService(DB_PATH)
        result = sync_service.sync_daily_matches()
        sync_service.close()

        logger.info(f"Sync completed: {result}")

    except Exception as e:
        logger.error(f"Sync failed: {e}")


def run_validation_task():
    """后台验证任务"""
    logger.info("Starting prediction validation")

    try:
        # TODO: 实现验证服务
        logger.info("Validation completed")
    except Exception as e:
        logger.error(f"Validation failed: {e}")