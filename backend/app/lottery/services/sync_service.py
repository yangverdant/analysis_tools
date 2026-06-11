"""
数据同步服务 - 串联爬虫、ETL、DAO

完整流程:
1. 调用爬虫获取数据
2. EntityMapper 进行字段转换和球队映射
3. DAO 层入库 (比赛 + 赔率)
4. 开奖结果入库
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime, date

from ..data_sources.scrapers.lottery_crawler import LotteryCrawlerSync
from ..etl.entity_mapper import EntityMapper
from ..dao.lottery_dao import LotteryMatchDAO, LotteryOddsDAO

logger = logging.getLogger(__name__)


class LotterySyncService:
    """
    体彩数据同步服务

    串联流程:
    爬虫 → EntityMapper → DAO → 数据库
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 初始化各组件
        self.crawler = LotteryCrawlerSync()
        self.mapper = EntityMapper(db_path)
        self.match_dao = LotteryMatchDAO(db_path)
        self.odds_dao = LotteryOddsDAO(db_path)

    def sync_daily_matches(self, match_date: date = None) -> Dict:
        """
        同步每日比赛数据

        流程:
        1. 爬虫获取比赛列表
        2. EntityMapper 映射球队名称
        3. DAO 写入数据库 (比赛 + 赔率)
        """
        if match_date is None:
            match_date = date.today()

        logger.info(f"Starting sync for {match_date}")

        # 1. 爬取数据
        raw_matches = self.crawler.crawl_matches_sync(match_date)

        if not raw_matches:
            logger.warning(f"No matches found for {match_date}")
            return {
                'success': False,
                'date': str(match_date),
                'crawled': 0,
                'mapped': 0,
                'saved': 0,
                'odds_saved': 0,
                'error': 'No data from crawler'
            }

        # 提取data字段 (crawl_matches_sync返回{'success', 'data', 'count'})
        matches_data = raw_matches.get('data', []) if isinstance(raw_matches, dict) else raw_matches
        if not matches_data:
            return {
                'success': False,
                'date': str(match_date),
                'crawled': 0,
                'mapped': 0,
                'saved': 0,
                'odds_saved': 0,
                'error': 'No matches in response'
            }

        # 2. 处理每场比赛
        saved_count = 0
        mapped_count = 0
        odds_saved = 0
        errors = []

        for raw_match in matches_data:
            try:
                # 字段映射
                standardized = self.mapper.map_to_standard('lottery', raw_match)

                # 球队映射
                home_team_id = self.mapper.get_team_id(raw_match['home_team_cn'])
                away_team_id = self.mapper.get_team_id(raw_match['away_team_cn'])

                # 如果映射失败，尝试用normalize后的英文名自动注册
                if not home_team_id:
                    home_team_id = self._auto_register_team(raw_match['home_team_cn'])
                if not away_team_id:
                    away_team_id = self._auto_register_team(raw_match['away_team_cn'])

                if home_team_id and away_team_id:
                    mapped_count += 1

                # 准备入库数据
                match_data = {
                    'lottery_match_id': raw_match['lottery_match_id'],
                    'home_team_cn': raw_match['home_team_cn'],
                    'away_team_cn': raw_match['away_team_cn'],
                    'match_date': raw_match['match_date'],
                    'match_time': raw_match.get('match_time'),
                    'league_name_cn': raw_match.get('league_name_cn'),
                    'match_num': raw_match.get('match_num'),
                    'sell_status': raw_match.get('sell_status', 'selling'),
                    'play_types': raw_match.get('play_types', []),
                    'handicap_line': raw_match.get('handicap_line', 0),
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id
                }

                # DAO 入库
                if self.match_dao.insert(match_data):
                    saved_count += 1

                    # 赔率入库 — 从raw_match的odds_data字段提取
                    odds_data = raw_match.get('odds_data', {})
                    if odds_data:
                        for play_type, odds in odds_data.items():
                            try:
                                self.odds_dao.insert(
                                    lottery_match_id=raw_match['lottery_match_id'],
                                    play_type=play_type,
                                    odds_data=odds
                                )
                                odds_saved += 1
                            except Exception as e:
                                logger.debug(f"Odds insert error for {play_type}: {e}")

            except Exception as e:
                errors.append(f"{raw_match.get('lottery_match_id', 'unknown')}: {str(e)}")
                logger.error(f"Error processing match: {e}")

        logger.info(f"Sync completed: {saved_count} matches saved, {odds_saved} odds saved")

        return {
            'success': True,
            'date': str(match_date),
            'crawled': len(matches_data),
            'mapped': mapped_count,
            'saved': saved_count,
            'odds_saved': odds_saved,
            'errors': errors[:10]
        }

    def sync_results(self, match_date: date = None) -> Dict:
        """
        同步开奖结果 — 爬取 + 入库

        用于闭环学习验证
        """
        if match_date is None:
            match_date = date.today()

        raw_results = self.crawler.crawl_results_sync(match_date)

        if not raw_results:
            return {
                'success': False,
                'date': str(match_date),
                'saved': 0
            }

        saved = 0
        for result in raw_results:
            try:
                result_data = {
                    'lottery_match_id': result.get('lottery_match_id') or result.get('matchId'),
                    'home_goals_ft': result.get('home_goals_ft') or result.get('homeScore'),
                    'away_goals_ft': result.get('away_goals_ft') or result.get('awayScore'),
                    'home_goals_ht': result.get('home_goals_ht') or result.get('homeScoreHt'),
                    'away_goals_ht': result.get('away_goals_ht') or result.get('awayScoreHt'),
                    'spf_result': result.get('spf_result') or result.get('spfResult'),
                    'bf_result': result.get('bf_result') or result.get('bfResult'),
                    'bqc_result': result.get('bqc_result') or result.get('bqcResult'),
                    'rqspf_result': result.get('rqspf_result') or result.get('rqspfResult'),
                }

                # 直接写入lottery_results表
                conn = __import__('sqlite3').connect(self.db_path)
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO lottery_results
                        (lottery_match_id, home_goals_ft, away_goals_ft,
                         home_goals_ht, away_goals_ht,
                         spf_result, bf_result, bqc_result, rqspf_result)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        result_data['lottery_match_id'],
                        result_data.get('home_goals_ft'),
                        result_data.get('away_goals_ft'),
                        result_data.get('home_goals_ht'),
                        result_data.get('away_goals_ht'),
                        result_data.get('spf_result'),
                        result_data.get('bf_result'),
                        result_data.get('bqc_result'),
                        result_data.get('rqspf_result')
                    ))
                    conn.commit()
                    saved += 1
                except Exception as e:
                    logger.error(f"Save result error: {e}")
                finally:
                    conn.close()

            except Exception as e:
                logger.error(f"Result processing error: {e}")

        return {
            'success': True,
            'date': str(match_date),
            'saved': saved,
            'total': len(raw_results)
        }

    def sync_odds(self, lottery_match_id: str, play_types: List[str] = None) -> Dict:
        """
        同步赔率数据 — 当前赔率已随matchInfo一起入库

        此方法用于手动刷新单场赔率(如需要最新赔率时)
        """
        return {
            'success': True,
            'note': 'Odds are synced with matches via sync_daily_matches()',
            'lottery_match_id': lottery_match_id
        }

    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        today = date.today()
        today_matches = self.match_dao.find_by_date(str(today))
        pending = self.match_dao.find_pending_analysis()

        return {
            'today_matches': len(today_matches),
            'pending_analysis': len(pending),
            'last_sync': datetime.now().isoformat()
        }

    def _auto_register_team(self, cn_name: str) -> Optional[int]:
        """自动注册球队映射：用normalize后的英文名查teams表"""
        try:
            from fetchers.common.team_names import normalize_team_name
            en_name = normalize_team_name(cn_name)

            # 如果normalize后还是中文，无法自动映射
            if any('一' <= c <= '鿿' for c in en_name):
                return None

            # 在teams表中查找
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT team_id FROM teams WHERE name_en = ? COLLATE NOCASE LIMIT 1",
                (en_name,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                team_id = row[0]
                # 注册映射
                self.mapper.register_team_mapping(cn_name, team_id, method='auto_normalize')
                logger.info(f'自动注册映射: {cn_name} -> team_id={team_id}')
                return team_id

        except Exception as e:
            logger.debug(f'自动注册失败 {cn_name}: {e}')

        return None

    def close(self):
        """清理资源"""
        pass
