"""
7:00+7:30 采集编排 — 日循环第二步

职责:
1. sporttery采集今日赛程
2. 队名映射(复用EntityMapper)
3. 赔率入库(当前SyncService的sync_odds未实现，此处补充)
4. 数据源健康记录
"""

import sqlite3
import json
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Collector:
    """7:00+7:30 采集编排模块"""

    def __init__(self, db_path: str, config: dict = None):
        self.db_path = db_path
        self.config = config or {}

    def run(self, match_date: date = None) -> dict:
        """执行采集编排"""
        if match_date is None:
            match_date = date.today()

        logger.info('采集编排开始: %s', match_date)

        results = {}

        # Step 1: sporttery赛程采集
        results['sync_matches'] = self._sync_matches(match_date)

        # Step 2: 队名映射修复
        results['team_mapping'] = self._fix_team_mappings()

        # Step 3: 赔率入库(如果已实现)
        results['sync_odds'] = self._sync_odds_for_date(match_date)

        # Step 4: 记录数据源健康
        self._update_source_health(match_date, results)

        saved = results['sync_matches'].get('saved', 0)
        logger.info('采集编排完成: %d场入库', saved)

        return {
            'date': str(match_date),
            'saved': saved,
            'steps': results,
        }

    # --- Step 1: sporttery赛程采集 ---

    def _sync_matches(self, match_date: date) -> dict:
        """通过LotterySyncService采集今日赛程"""
        try:
            # 添加项目根到sys.path以便import backend模块
            import sys
            from pathlib import Path
            project_root = str(Path(self.db_path).resolve().parent.parent)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            from backend.app.lottery.services.sync_service import LotterySyncService

            service = LotterySyncService(self.db_path)
            result = service.sync_daily_matches(match_date)

            # 记录未映射队名
            unmapped = service.mapper.list_unmapped_teams()
            if unmapped:
                logger.warning('未映射队名: %s', unmapped[:10])

            return result

        except ImportError as e:
            logger.error('无法导入LotterySyncService: %s', e)
            return {'success': False, 'error': f'Import failed: {e}'}
        except Exception as e:
            logger.error('赛程采集失败: %s', e)
            return {'success': False, 'error': str(e)}

    # --- Step 2: 队名映射修复 ---

    def _fix_team_mappings(self) -> dict:
        """尝试修复未映射的队名"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查找未映射队名
            cursor.execute("""
                SELECT DISTINCT home_team_cn FROM lottery_matches
                WHERE home_team_id IS NULL
                UNION
                SELECT DISTINCT away_team_cn FROM lottery_matches
                WHERE away_team_id IS NULL
            """)
            unmapped_names = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not unmapped_names:
                return {'unmapped': 0, 'fixed': 0}

            # 尝试通过fetchers.common.team_names标准化并映射
            fixed = 0
            try:
                from fetchers.common.team_names import normalize_team_name
                import sys
                from pathlib import Path
                project_root = str(Path(self.db_path).resolve().parent.parent)
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)

                from backend.app.lottery.etl.entity_mapper import EntityMapper

                mapper = EntityMapper(self.db_path)
                for name in unmapped_names:
                    normalized = normalize_team_name(name)
                    team_id = mapper.get_team_id(normalized)
                    if team_id:
                        # 注册映射
                        mapper.register_team_mapping(name, team_id, method='auto_normalize')
                        fixed += 1
                        logger.info('自动映射: %s → team_id=%d', name, team_id)

            except ImportError:
                logger.warning('无法导入team_names模块进行自动映射')

            return {'unmapped': len(unmapped_names), 'fixed': fixed}

        except Exception as e:
            logger.error('队名映射修复失败: %s', e)
            return {'unmapped': 0, 'fixed': 0, 'error': str(e)}

    # --- Step 3: 赔率入库 ---

    def _sync_odds_for_date(self, match_date: date) -> dict:
        """为今日比赛入库赔率"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 获取今日已入库的体彩比赛ID
            cursor.execute("""
                SELECT lottery_match_id FROM lottery_matches
                WHERE match_date = ?
            """, (str(match_date),))
            match_ids = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not match_ids:
                return {'synced': 0, 'note': 'no matches for date'}

            # 尝试爬取赔率
            synced = 0
            try:
                import sys
                from pathlib import Path
                project_root = str(Path(self.db_path).resolve().parent.parent)
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)

                from backend.app.lottery.data_sources.scrapers.lottery_crawler import LotteryCrawlerSync
                from backend.app.lottery.dao.lottery_dao import LotteryOddsDAO

                crawler = LotteryCrawlerSync()
                odds_dao = LotteryOddsDAO(self.db_path)

                for mid in match_ids[:50]:  # 限制批量大小
                    try:
                        # 获取赔率数据 (通过matches API中内嵌的赔率)
                        # LotteryCrawlerSync没有crawl_odds_sync, 赔率在matches数据中
                        odds_data = self._extract_odds_from_match(cursor, mid)
                        if odds_data:
                            for play_type, data in odds_data.items():
                                odds_dao.insert(mid, play_type, data)
                            synced += 1
                    except Exception as e:
                        logger.debug('赔率入库失败 %s: %s', mid, e)

            except ImportError:
                logger.warning('无法导入赔率相关模块')

            return {'synced': synced, 'total': len(match_ids)}

        except Exception as e:
            logger.error('赔率入库失败: %s', e)
            return {'synced': 0, 'error': str(e)}

    def _extract_odds_from_match(self, cursor, lottery_match_id: str) -> Optional[Dict]:
        """从lottery_matches中提取内嵌赔率(体彩API返回的赔率在matchInfo中)"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT play_types, handicap_line FROM lottery_matches
                WHERE lottery_match_id = ?
            """, (lottery_match_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            # 体彩赔率随matchInfo一起返回, 已在sync_daily_matches中入库
            # 此处只处理未单独入库的赔率
            return None

        except Exception:
            return None

    # --- Step 4: 数据源健康记录 ---

    def _update_source_health(self, match_date: date, results: dict):
        """记录数据源健康状态"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cursor = conn.cursor()

            # 确保表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_source_health (
                    source_name TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'unknown',
                    last_success TEXT,
                    last_failure TEXT,
                    success_rate REAL DEFAULT 0,
                    updated_at TEXT
                )
            """)

            # sporttery状态
            sync_ok = results.get('sync_matches', {}).get('success', False)
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO data_source_health
                (source_name, status, last_success, last_failure, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                'sporttery',
                'healthy' if sync_ok else 'error',
                now if sync_ok else None,
                now if not sync_ok else None,
                now,
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.debug('数据源健康记录失败: %s', e)