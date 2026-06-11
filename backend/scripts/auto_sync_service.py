"""
自动同步服务 - 定期更新未来比赛数据
确保未来7天比赛数据完整，包括时间、状态、赔率等
"""

import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.data_sources.manager import DataSourceManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoSyncService:
    """自动同步服务"""

    LEAGUES = {
        '152': 'Premier League',
        '302': 'La Liga',
        '207': 'Bundesliga',
        '168': 'Serie A',
        '153': 'Ligue 1',
        '3': 'Champions League',
    }

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.manager = DataSourceManager()

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

    async def sync_upcoming_matches(self) -> dict:
        """同步未来比赛数据"""
        source = self.manager.get_source('apifootball')
        if not source:
            return {'error': 'apifootball source not found'}

        results = {
            'synced': 0,
            'updated': 0,
            'added': 0,
            'errors': []
        }

        today = datetime.now().strftime('%Y-%m-%d')
        future_7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

        for league_id, league_name in self.LEAGUES.items():
            try:
                logger.info(f"Syncing {league_name}...")
                fixtures = await source.get_fixtures(
                    league_id=league_id,
                    from_date=today,
                    to_date=future_7
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
                        # 更新
                        self.cursor.execute('''
                            UPDATE matches SET
                                match_time = ?,
                                status = ?,
                                home_goals = COALESCE(?, home_goals),
                                away_goals = COALESCE(?, away_goals),
                                source = 'apifootball'
                            WHERE match_id = ?
                        ''', (f.time, f.status or 'scheduled',
                              f.home_score, f.away_score, existing[0]))
                        results['updated'] += 1
                    else:
                        # 新增
                        self.cursor.execute('''
                            INSERT INTO matches (
                                match_date, match_time, home_team_id, away_team_id,
                                home_goals, away_goals, status, league_id, source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (f.date, f.time, home_id, away_id,
                              f.home_score, f.away_score, f.status or 'scheduled',
                              int(league_id), 'apifootball'))
                        results['added'] += 1

                    results['synced'] += 1

                self.conn.commit()

            except Exception as e:
                results['errors'].append(f"{league_name}: {str(e)}")
                logger.error(f"Error syncing {league_name}: {e}")

        return results

    def get_coverage_report(self) -> dict:
        """获取数据覆盖率报告"""
        today = datetime.now().strftime('%Y-%m-%d')
        future_3 = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        future_7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

        report = {
            'timestamp': datetime.now().isoformat(),
            'next_3_days': {},
            'next_7_days': {},
            'by_date': []
        }

        # 未来3天
        self.cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_3))
        row = self.cursor.fetchone()
        report['next_3_days'] = {
            'total': row[0],
            'with_time': row[1],
            'coverage': round(row[1]/row[0]*100, 1) if row[0] > 0 else 0
        }

        # 未来7天
        self.cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
        ''', (today, future_7))
        row = self.cursor.fetchone()
        report['next_7_days'] = {
            'total': row[0],
            'with_time': row[1],
            'coverage': round(row[1]/row[0]*100, 1) if row[0] > 0 else 0
        }

        # 按日期
        self.cursor.execute('''
            SELECT match_date, COUNT(*), SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END)
            FROM matches WHERE match_date >= ? AND match_date <= ?
            GROUP BY match_date ORDER BY match_date
        ''', (today, future_7))
        for row in self.cursor.fetchall():
            report['by_date'].append({
                'date': row[0],
                'total': row[1],
                'with_time': row[2],
                'coverage': round(row[2]/row[1]*100, 1) if row[1] > 0 else 0
            })

        return report


async def main():
    """主函数"""
    db_path = 'D:/football_tools/data/football_v2.db'
    service = AutoSyncService(db_path)
    service.connect()

    try:
        # 同步前报告
        print('=' * 60)
        print('Auto Sync Service')
        print('=' * 60)
        print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print()

        before = service.get_coverage_report()
        print(f'Before sync:')
        print(f'  Next 3 days: {before["next_3_days"]["with_time"]}/{before["next_3_days"]["total"]} ({before["next_3_days"]["coverage"]}%)')
        print(f'  Next 7 days: {before["next_7_days"]["with_time"]}/{before["next_7_days"]["total"]} ({before["next_7_days"]["coverage"]}%)')
        print()

        # 执行同步
        print('Syncing...')
        results = await service.sync_upcoming_matches()
        print(f'  Synced: {results["synced"]} matches')
        print(f'  Updated: {results["updated"]} matches')
        print(f'  Added: {results["added"]} matches')

        if results['errors']:
            print(f'  Errors: {len(results["errors"])}')

        print()

        # 同步后报告
        after = service.get_coverage_report()
        print(f'After sync:')
        print(f'  Next 3 days: {after["next_3_days"]["with_time"]}/{after["next_3_days"]["total"]} ({after["next_3_days"]["coverage"]}%)')
        print(f'  Next 7 days: {after["next_7_days"]["with_time"]}/{after["next_7_days"]["total"]} ({after["next_7_days"]["coverage"]}%)')
        print()

        print('Coverage by date:')
        for d in after['by_date']:
            print(f'  {d["date"]}: {d["with_time"]}/{d["total"]} ({d["coverage"]}%)')

    finally:
        service.close()


if __name__ == '__main__':
    asyncio.run(main())
