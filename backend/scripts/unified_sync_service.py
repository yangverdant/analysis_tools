"""
统一数据同步服务
整合未来比赛同步和实时比赛事件同步
"""

import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.data_sources.manager import DataSourceManager
from app.data_sources.apifootball_source import APIFootballSource
from app.data_sources.base import DataSourceConfig, DataSourceType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedSyncService:
    """统一同步服务"""

    LEAGUES = {
        '152': 'Premier League',
        '302': 'La Liga',
        '207': 'Bundesliga',
        '168': 'Serie A',
        '153': 'Ligue 1',
        '3': 'Champions League',
    }

    def __init__(self, db_path: str, api_key: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.manager = DataSourceManager()

        config = DataSourceConfig(
            name='apifootball',
            source_type=DataSourceType.API,
            base_url='https://apiv3.apifootball.com',
            api_key=api_key,
            enabled=True
        )
        self.api = APIFootballSource(config)

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

    def _find_team_id(self, team_name: str) -> int:
        self.cursor.execute('''
            SELECT team_id FROM teams
            WHERE name_en LIKE ? OR name_cn LIKE ? OR short_name LIKE ?
            LIMIT 1
        ''', (f'%{team_name}%', f'%{team_name}%', f'%{team_name}%'))
        result = self.cursor.fetchone()
        return result[0] if result else None

    # ==================== 未来比赛同步 ====================

    async def sync_future_matches(self, days: int = 7) -> dict:
        """同步未来比赛（时间、状态）"""
        logger.info("Syncing future matches...")

        source = self.manager.get_source('apifootball')
        if not source:
            return {'error': 'apifootball source not found'}

        results = {'synced': 0, 'updated': 0, 'added': 0, 'errors': []}

        today = datetime.now().strftime('%Y-%m-%d')
        future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

        for league_id, league_name in self.LEAGUES.items():
            try:
                fixtures = await source.get_fixtures(
                    league_id=league_id,
                    from_date=today,
                    to_date=future
                )

                if not fixtures:
                    continue

                for f in fixtures:
                    home_id = self._find_team_id(f.home_team)
                    away_id = self._find_team_id(f.away_team)

                    if not home_id or not away_id:
                        continue

                    self.cursor.execute('''
                        SELECT match_id FROM matches
                        WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                    ''', (f.date, home_id, away_id))

                    existing = self.cursor.fetchone()

                    if existing:
                        self.cursor.execute('''
                            UPDATE matches SET
                                match_time = ?,
                                status = ?,
                                source = 'apifootball'
                            WHERE match_id = ?
                        ''', (f.time, f.status or 'scheduled', existing[0]))
                        results['updated'] += 1
                    else:
                        self.cursor.execute('''
                            INSERT INTO matches (
                                match_date, match_time, home_team_id, away_team_id,
                                status, league_id, source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (f.date, f.time, home_id, away_id, f.status or 'scheduled',
                              int(league_id), 'apifootball'))
                        results['added'] += 1

                    results['synced'] += 1

                self.conn.commit()

            except Exception as e:
                results['errors'].append(f"{league_name}: {str(e)}")
                logger.error(f"Error: {e}")

        logger.info(f"Future sync done: {results['synced']} matches")
        return results

    # ==================== 实时比赛事件同步 ====================

    async def sync_recent_events(self, days: int = 7) -> dict:
        """同步最近比赛事件（进球、换人、红黄牌等）"""
        logger.info("Syncing recent match events...")

        results = {'synced': 0, 'goals': 0, 'cards': 0, 'lineups': 0, 'errors': []}

        past = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')

        for league_id, league_name in self.LEAGUES.items():
            try:
                events = await self.api.get_match_events_by_date(past, today, league_id)

                for event in events:
                    match_date = event.get('date')
                    home_team = event.get('home_team', '')
                    away_team = event.get('away_team', '')

                    home_id = self._find_team_id(home_team)
                    away_id = self._find_team_id(away_team)

                    if not home_id or not away_id:
                        continue

                    self.cursor.execute('''
                        SELECT match_id FROM matches
                        WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                    ''', (match_date, home_id, away_id))

                    existing = self.cursor.fetchone()
                    if not existing:
                        continue

                    # 更新比分和状态
                    self.cursor.execute('''
                        UPDATE matches SET
                            home_goals = ?,
                            away_goals = ?,
                            home_goals_ht = ?,
                            away_goals_ht = ?,
                            status = ?,
                            venue = COALESCE(?, venue),
                            referee = COALESCE(?, referee),
                            source = 'apifootball_events'
                        WHERE match_id = ?
                    ''', (
                        event.get('home_score'),
                        event.get('away_score'),
                        event.get('home_score_ht'),
                        event.get('away_score_ht'),
                        self._map_status(event.get('status')),
                        event.get('venue'),
                        event.get('referee'),
                        existing[0]
                    ))

                    results['goals'] += len(event.get('goalscorer', []))
                    results['cards'] += len(event.get('cards', []))
                    if event.get('lineup'):
                        results['lineups'] += 1
                    results['synced'] += 1

                self.conn.commit()

            except Exception as e:
                results['errors'].append(f"{league_name}: {str(e)}")
                logger.error(f"Error: {e}")

        logger.info(f"Events sync done: {results['synced']} matches, {results['goals']} goals")
        return results

    # ==================== 过期比赛修复 ====================

    def fix_expired_matches(self) -> dict:
        """修复过期比赛状态"""
        logger.info("Fixing expired matches...")

        today = datetime.now().strftime('%Y-%m-%d')

        # 查找过期但状态错误的比赛
        self.cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE match_date < ?
            AND status IN ('scheduled', 'SCHEDULED', 'TIMED', 'timed')
        ''', (today,))

        count = self.cursor.fetchone()[0]

        if count > 0:
            self.cursor.execute('''
                UPDATE matches SET
                    status = 'finished',
                    source = 'auto_fixed'
                WHERE match_date < ?
                AND status IN ('scheduled', 'SCHEDULED', 'TIMED', 'timed')
            ''', (today,))
            self.conn.commit()

        logger.info(f"Fixed {count} expired matches")
        return {'fixed': count}

    def _map_status(self, status: str) -> str:
        if not status:
            return 'scheduled'
        if "'" in status:
            return 'live'
        status_map = {
            'Finished': 'finished',
            'Half Time': 'halftime',
            'Postponed': 'postponed',
            'Cancelled': 'cancelled',
        }
        return status_map.get(status, status.lower())

    # ==================== 统一同步入口 ====================

    async def sync_all(self) -> dict:
        """执行完整同步"""
        print('=' * 60)
        print('Unified Sync Service')
        print('=' * 60)
        print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print()

        results = {
            'future': {},
            'events': {},
            'expired': {}
        }

        # 1. 修复过期比赛
        print('[1/3] Fixing expired matches...')
        results['expired'] = self.fix_expired_matches()
        print(f"  Fixed: {results['expired']['fixed']} matches")
        print()

        # 2. 同步未来比赛
        print('[2/3] Syncing future matches...')
        results['future'] = await self.sync_future_matches(days=7)
        print(f"  Synced: {results['future']['synced']} matches")
        print(f"  Updated: {results['future']['updated']}")
        print(f"  Added: {results['future']['added']}")
        print()

        # 3. 同步最近事件
        print('[3/3] Syncing recent events...')
        results['events'] = await self.sync_recent_events(days=7)
        print(f"  Synced: {results['events']['synced']} matches")
        print(f"  Goals: {results['events']['goals']}")
        print(f"  Cards: {results['events']['cards']}")
        print()

        # 汇总
        print('=' * 60)
        print('Summary:')
        total_errors = len(results['future'].get('errors', [])) + len(results['events'].get('errors', []))
        print(f'  Total errors: {total_errors}')
        print('  Done!')

        return results

    def get_status_report(self) -> dict:
        """获取数据状态报告"""
        today = datetime.now().strftime('%Y-%m-%d')
        future_3 = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        future_7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        past_7 = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        report = {'timestamp': datetime.now().isoformat()}

        # 未来3天
        self.cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_3))
        row = self.cursor.fetchone()
        report['next_3_days'] = {'total': row[0], 'with_time': row[1], 'coverage': round(row[1]/row[0]*100, 1) if row[0] > 0 else 0}

        # 未来7天
        self.cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_7))
        row = self.cursor.fetchone()
        report['next_7_days'] = {'total': row[0], 'with_time': row[1], 'coverage': round(row[1]/row[0]*100, 1) if row[0] > 0 else 0}

        # 最近7天已结束
        self.cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE match_date >= ? AND match_date < ?
            AND status IN ('finished', 'FINISHED')
        ''', (past_7, today))
        report['recent_finished'] = self.cursor.fetchone()[0]

        # 过期但状态错误
        self.cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE match_date < ?
            AND status IN ('scheduled', 'SCHEDULED', 'TIMED', 'timed')
        ''', (today,))
        report['expired_wrong_status'] = self.cursor.fetchone()[0]

        return report


async def main():
    db_path = 'D:/football_tools/data/football_v2.db'
    api_key = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'

    service = UnifiedSyncService(db_path, api_key)
    service.connect()

    try:
        # 显示同步前状态
        before = service.get_status_report()
        print('Before sync:')
        print(f'  Next 3 days: {before["next_3_days"]["with_time"]}/{before["next_3_days"]["total"]} ({before["next_3_days"]["coverage"]}%)')
        print(f'  Expired wrong status: {before["expired_wrong_status"]}')
        print()

        # 执行同步
        await service.sync_all()

        # 显示同步后状态
        print()
        after = service.get_status_report()
        print('After sync:')
        print(f'  Next 3 days: {after["next_3_days"]["with_time"]}/{after["next_3_days"]["total"]} ({after["next_3_days"]["coverage"]}%)')
        print(f'  Expired wrong status: {after["expired_wrong_status"]}')

    finally:
        service.close()


if __name__ == '__main__':
    asyncio.run(main())
