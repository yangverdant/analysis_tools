"""
未来比赛数据同步服务
自动检查并更新未来比赛的时间和赔率数据
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FutureMatchSyncService:
    """未来比赛数据同步服务"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def get_matches_needing_update(self, days_ahead: int = 30) -> List[Dict]:
        """获取需要更新的未来比赛"""
        today = datetime.now().strftime('%Y-%m-%d')
        future = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

        self.cursor.execute('''
            SELECT m.match_id, m.match_date, m.match_time, m.league_id,
                   l.league_code, l.name_cn,
                   t1.name_en as home_team, t2.name_en as away_team,
                   m.odds_home, m.odds_draw, m.odds_away, m.status
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams t1 ON m.home_team_id = t1.team_id
            JOIN teams t2 ON m.away_team_id = t2.team_id
            WHERE m.match_date >= ? AND m.match_date <= ?
            AND m.status IN ('scheduled', 'TIMED', None, '')
            AND (
                m.match_time IS NULL OR m.match_time = ''
                OR m.odds_home IS NULL
            )
            ORDER BY m.match_date
        ''', (today, future))

        matches = []
        for row in self.cursor.fetchall():
            matches.append({
                'match_id': row[0],
                'match_date': row[1],
                'match_time': row[2],
                'league_id': row[3],
                'league_code': row[4],
                'league_name': row[5],
                'home_team': row[6],
                'away_team': row[7],
                'odds_home': row[8],
                'odds_draw': row[9],
                'odds_away': row[10],
                'status': row[11],
            })

        return matches

    async def sync_from_api(self, source_name: str = 'football_data_org') -> Dict:
        """从API同步数据"""
        from app.data_sources.manager import DataSourceManager

        manager = DataSourceManager()
        source = manager.get_source(source_name)

        if not source:
            return {'success': False, 'error': f'Source {source_name} not found'}

        results = {
            'total_checked': 0,
            'time_updated': 0,
            'odds_updated': 0,
            'errors': [],
        }

        # 获取需要更新的比赛
        matches = self.get_matches_needing_update(days_ahead=30)
        results['total_checked'] = len(matches)

        logger.info(f'Found {len(matches)} matches needing update')

        # 按联赛分组
        league_matches = {}
        for m in matches:
            code = m['league_code']
            if code not in league_matches:
                league_matches[code] = []
            league_matches[code].append(m)

        # 从API获取数据
        for league_code, league_matches_list in league_matches.items():
            try:
                # 获取该联赛的赛程
                fixtures = await source.get_fixtures(league_code, None)

                if not fixtures:
                    continue

                # 匹配并更新
                for fixture in fixtures:
                    for match in league_matches_list:
                        if self._match_fixture(fixture, match):
                            # 更新时间
                            if fixture.time and (not match['match_time'] or match['match_time'] == ''):
                                self.cursor.execute('''
                                    UPDATE matches SET
                                        match_time = ?,
                                        status = COALESCE(?, status),
                                        source = COALESCE(source || '+sync_api', 'sync_api')
                                    WHERE match_id = ?
                                ''', (fixture.time, fixture.status, match['match_id']))

                                if self.cursor.rowcount > 0:
                                    results['time_updated'] += 1
                                    logger.info(f"Updated time for {match['home_team']} vs {match['away_team']}: {fixture.time}")

                            # 更新赔率（如果API返回）
                            if hasattr(fixture, 'odds_home') and fixture.odds_home:
                                self.cursor.execute('''
                                    UPDATE matches SET
                                        odds_home = ?,
                                        odds_draw = ?,
                                        odds_away = ?,
                                        source = COALESCE(source || '+odds', 'odds')
                                    WHERE match_id = ?
                                ''', (fixture.odds_home, fixture.odds_draw, fixture.odds_away, match['match_id']))

                                if self.cursor.rowcount > 0:
                                    results['odds_updated'] += 1

                self.conn.commit()

            except Exception as e:
                error_msg = f'Error syncing {league_code}: {str(e)}'
                logger.error(error_msg)
                results['errors'].append(error_msg)

        return results

    def _match_fixture(self, fixture, match: Dict) -> bool:
        """匹配fixture和match"""
        # 日期匹配
        if fixture.date != match['match_date']:
            return False

        # 球队名模糊匹配
        home_match = match['home_team'].lower() in fixture.home_team.lower() or \
                     fixture.home_team.lower() in match['home_team'].lower()
        away_match = match['away_team'].lower() in fixture.away_team.lower() or \
                     fixture.away_team.lower() in match['away_team'].lower()

        return home_match and away_match

    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        today = datetime.now().strftime('%Y-%m-%d')
        future_7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        future_30 = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        # 未来7天
        self.cursor.execute('''
            SELECT COUNT(*),
                   SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN odds_home IS NOT NULL THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_7))
        row_7 = self.cursor.fetchone()

        # 未来30天
        self.cursor.execute('''
            SELECT COUNT(*),
                   SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN odds_home IS NOT NULL THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_30))
        row_30 = self.cursor.fetchone()

        return {
            'next_7_days': {
                'total': row_7[0],
                'has_time': row_7[1],
                'has_odds': row_7[2],
                'time_coverage': row_7[1] / row_7[0] * 100 if row_7[0] > 0 else 0,
                'odds_coverage': row_7[2] / row_7[0] * 100 if row_7[0] > 0 else 0,
            },
            'next_30_days': {
                'total': row_30[0],
                'has_time': row_30[1],
                'has_odds': row_30[2],
                'time_coverage': row_30[1] / row_30[0] * 100 if row_30[0] > 0 else 0,
                'odds_coverage': row_30[2] / row_30[0] * 100 if row_30[0] > 0 else 0,
            },
        }


async def run_sync():
    """运行同步任务"""
    db_path = 'D:/football_tools/data/football_v2.db'

    service = FutureMatchSyncService(db_path)
    service.connect()

    try:
        # 获取同步前状态
        print('Before sync:')
        status = service.get_sync_status()
        print(f"  Next 7 days: {status['next_7_days']['has_time']}/{status['next_7_days']['total']} have time")
        print(f"  Next 30 days: {status['next_30_days']['has_time']}/{status['next_30_days']['total']} have time")

        # 执行同步
        print('\nSyncing from API...')
        results = await service.sync_from_api()

        print(f'\nSync results:')
        print(f"  Checked: {results['total_checked']}")
        print(f"  Time updated: {results['time_updated']}")
        print(f"  Odds updated: {results['odds_updated']}")
        if results['errors']:
            print(f"  Errors: {results['errors']}")

        # 获取同步后状态
        print('\nAfter sync:')
        status = service.get_sync_status()
        print(f"  Next 7 days: {status['next_7_days']['has_time']}/{status['next_7_days']['total']} have time ({status['next_7_days']['time_coverage']:.1f}%)")
        print(f"  Next 30 days: {status['next_30_days']['has_time']}/{status['next_30_days']['total']} have time ({status['next_30_days']['time_coverage']:.1f}%)")

    finally:
        service.close()


if __name__ == '__main__':
    asyncio.run(run_sync())
