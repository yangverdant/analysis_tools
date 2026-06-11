"""
修复过期比赛状态
检查数据库中已过期但状态仍为scheduled的比赛，从API获取真实结果并更新
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.data_sources.apifootball_source import APIFootballSource
from app.data_sources.base import DataSourceConfig, DataSourceType


class ExpiredMatchFixer:
    """过期比赛修复器"""

    LEAGUES = {
        '152': 'Premier League',
        '302': 'La Liga',
        '207': 'Bundesliga',
        '168': 'Serie A',
        '153': 'Ligue 1',
    }

    def __init__(self, db_path: str, api_key: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

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

    def find_expired_matches(self) -> list:
        """查找过期但状态错误的比赛"""
        today = datetime.now().strftime('%Y-%m-%d')

        self.cursor.execute('''
            SELECT m.match_id, m.match_date, m.match_time, m.status,
                   ht.name_en as home, at.name_en as away,
                   m.home_goals, m.away_goals, m.league_id
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_date < ?
            AND m.status IN ('scheduled', 'SCHEDULED', 'TIMED', 'timed')
            ORDER BY m.match_date DESC
        ''', (today,))

        return self.cursor.fetchall()

    async def fix_expired_matches(self) -> dict:
        """修复过期比赛"""
        results = {
            'total_found': 0,
            'fixed': 0,
            'not_found_in_api': 0,
            'errors': []
        }

        expired = self.find_expired_matches()
        results['total_found'] = len(expired)

        if not expired:
            return results

        # 按日期分组
        dates = set(row[1] for row in expired)
        min_date = min(dates)
        max_date = max(dates)

        print(f'Found {len(expired)} expired matches')
        print(f'Date range: {min_date} to {max_date}')
        print()

        # 从API获取这些日期的比赛结果
        for league_id, league_name in self.LEAGUES.items():
            try:
                print(f'Fetching {league_name} results...')
                fixtures = await self.api.get_fixtures(
                    league_id=league_id,
                    from_date=min_date,
                    to_date=max_date
                )

                if not fixtures:
                    continue

                print(f'  Found {len(fixtures)} matches in API')

                # 创建查找字典
                api_matches = {}
                for f in fixtures:
                    key = (f.date, f.home_team, f.away_team)
                    api_matches[key] = f

                # 更新过期比赛
                for row in expired:
                    match_id, date, time, status, home, away, hg, ag, league = row

                    # 尝试匹配
                    for key, f in api_matches.items():
                        api_date, api_home, api_away = key
                        if api_date == date and (home in api_home or api_home in home):
                            # 找到匹配
                            self.cursor.execute('''
                                UPDATE matches SET
                                    status = ?,
                                    home_goals = ?,
                                    away_goals = ?,
                                    home_goals_ht = ?,
                                    away_goals_ht = ?,
                                    source = 'apifootball_fixed'
                                WHERE match_id = ?
                            ''', (
                                f.status or 'finished',
                                f.home_score,
                                f.away_score,
                                f.home_score_ht,
                                f.away_score_ht,
                                match_id
                            ))
                            results['fixed'] += 1
                            print(f'  Fixed: {date} {home} vs {away} -> {f.home_score}-{f.away_score}')
                            break

                self.conn.commit()

            except Exception as e:
                results['errors'].append(f"{league_name}: {str(e)}")

        return results

    def mark_as_finished(self):
        """将所有过期的scheduled比赛标记为finished"""
        today = datetime.now().strftime('%Y-%m-%d')

        self.cursor.execute('''
            UPDATE matches SET
                status = 'finished',
                source = 'auto_marked'
            WHERE match_date < ?
            AND status IN ('scheduled', 'SCHEDULED', 'TIMED', 'timed')
        ''', (today,))

        updated = self.cursor.rowcount
        self.conn.commit()

        return updated


async def main():
    db_path = 'D:/football_tools/data/football_v2.db'
    api_key = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'

    fixer = ExpiredMatchFixer(db_path, api_key)
    fixer.connect()

    try:
        print('=' * 60)
        print('Fix Expired Matches')
        print('=' * 60)
        print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print()

        # 先尝试从API获取真实结果
        results = await fixer.fix_expired_matches()

        print()
        print('Results:')
        print(f'  Total found: {results["total_found"]}')
        print(f'  Fixed from API: {results["fixed"]}')
        print(f'  Not found in API: {results["not_found_in_api"]}')

        # 如果还有剩余的，标记为finished
        remaining = fixer.find_expired_matches()
        if remaining:
            print()
            print(f'Marking {len(remaining)} remaining matches as finished...')
            marked = fixer.mark_as_finished()
            print(f'  Marked: {marked}')

        print()
        print('Done!')

    finally:
        fixer.close()


if __name__ == '__main__':
    asyncio.run(main())
