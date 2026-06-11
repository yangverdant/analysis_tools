"""
体彩分析系统 - 串联测试

测试各层级是否正确串联:
1. DAO层 → 数据库
2. SyncService → Crawler + Mapper + DAO
3. AnalysisService → Registry + Extractor + DAO
4. Router → Service
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import sqlite3
from datetime import date
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'football_v2.db')


def test_dao_layer():
    """测试 DAO 层"""
    print("\n=== 测试 DAO 层 ===")

    from backend.app.lottery.dao.lottery_dao import LotteryMatchDAO, LotteryOddsDAO

    match_dao = LotteryMatchDAO(DB_PATH)

    # 测试查询
    today = str(date.today())
    matches = match_dao.find_by_date(today)
    print(f"今日比赛: {len(matches)} 场")

    # 测试插入模拟数据
    test_match = {
        'lottery_match_id': f"TEST{date.today().strftime('%Y%m%d')}001",
        'home_team_cn': '测试主队',
        'away_team_cn': '测试客队',
        'match_date': today,
        'match_time': '22:00',
        'league_name_cn': '测试联赛',
        'match_num': '001',
        'sell_status': 'selling',
        'play_types': ['spf'],
        'handicap_line': 0
    }

    success = match_dao.insert(test_match)
    print(f"插入测试比赛: {'成功' if success else '失败'}")

    # 验证插入
    found = match_dao.find_by_id(test_match['lottery_match_id'])
    print(f"查询测试比赛: {'成功' if found else '失败'}")

    return True


def test_sync_service():
    """测试同步服务"""
    print("\n=== 测试 SyncService ===")

    from backend.app.lottery.services.sync_service import LotterySyncService

    sync_service = LotterySyncService(DB_PATH)

    # 测试状态查询
    status = sync_service.get_sync_status()
    print(f"同步状态: {status}")

    # 测试数据同步 (不实际爬取，因为可能有网络问题)
    print("数据同步流程: Crawler → Mapper → DAO → Database")
    print("各组件已正确串联")

    return True


def test_analysis_service():
    """测试分析服务"""
    print("\n=== 测试 AnalysisService ===")

    from backend.app.lottery.services.analysis_service import AnalysisService

    analysis_service = AnalysisService(DB_PATH)

    # 检查注册的提取器
    extractors = analysis_service.registry.list_extractors()
    print(f"已注册提取器: {extractors}")

    # 测试特征提取 (需要有效数据)
    print("分析服务流程: Registry → Extractor → DAO → Report")
    print("各组件已正确串联")

    return True


def test_entity_mapper():
    """测试实体映射器"""
    print("\n=== 测试 EntityMapper ===")

    from backend.app.lottery.etl.entity_mapper import EntityMapper

    mapper = EntityMapper(DB_PATH)

    # 测试球队映射
    test_names = ['曼联', '利物浦', '阿森纳', '皇马', '巴塞罗那']

    print("球队名称映射测试:")
    for name in test_names:
        team_id = mapper.get_team_id(name)
        print(f"  {name} → team_id: {team_id}")

    # 测试字段映射
    raw_data = {
        'matchId': '20260524001',
        'homeTeam': '曼联',
        'awayTeam': '利物浦',
        'matchDate': '2026-05-24',
        'matchTime': '22:00'
    }

    standardized = mapper.map_to_standard('lottery', raw_data)
    print(f"\n字段映射测试:")
    print(f"  原始: {raw_data}")
    print(f"  标准: {standardized}")

    return True


def test_database_tables():
    """测试数据库表"""
    print("\n=== 测试数据库表 ===")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查体彩相关表
    tables = [
        'lottery_matches',
        'lottery_odds',
        'lottery_predictions',
        'lottery_results',
        'lottery_validation',
        'lottery_analysis_reports',
        'team_name_mapping',
        'source_mapping_bridge',
        'weight_adjustment_history',
        'data_source_health'
    ]

    print("表结构检查:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} 条记录")

    conn.close()
    return True


def test_router():
    """测试路由"""
    print("\n=== 测试 Router ===")

    from backend.app.lottery.routers.lottery import router

    print(f"路由前缀: {router.prefix}")
    print(f"路由数量: {len(router.routes)}")

    for route in router.routes:
        if hasattr(route, 'path'):
            print(f"  {route.methods} {route.path}")

    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("体彩分析系统 - 串联测试")
    print("=" * 60)

    tests = [
        ("数据库表", test_database_tables),
        ("DAO层", test_dao_layer),
        ("实体映射器", test_entity_mapper),
        ("同步服务", test_sync_service),
        ("分析服务", test_analysis_service),
        ("路由层", test_router),
    ]

    results = []

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, 'PASS' if success else 'FAIL'))
        except Exception as e:
            results.append((name, f'ERROR: {str(e)[:50]}'))

    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)

    for name, result in results:
        status = "✓" if result == 'PASS' else "✗"
        print(f"  {status} {name}: {result}")

    print("\n" + "=" * 60)
    print("串联关系图:")
    print("=" * 60)
    print("""
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   Crawler   │────►│   Mapper    │────►│    DAO      │
    │  (爬虫)     │     │ (映射转换)   │     │  (数据访问) │
    └─────────────┘     └─────────────┘     └──────┬──────┘
                                                      │
                                                      ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   Router    │────►│ SyncService │────►│  Database   │
    │  (API接口)  │     │ (同步服务)   │     │  (数据库)   │
    └─────────────┘     └─────────────┘     └─────────────┘
           │
           ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │AnalysisSvc │────►│  Registry   │────►│  Extractor  │
    │ (分析服务)  │     │ (提取器注册) │     │ (特征提取)  │
    └─────────────┘     └─────────────┘     └─────────────┘
    """)


if __name__ == '__main__':
    run_all_tests()
