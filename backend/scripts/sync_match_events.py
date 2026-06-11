"""
同步比赛事件数据（进球时间、换人、红黄牌等）
从 API Football 获取并更新到数据库
"""

import asyncio
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys
import os

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.data_sources.apifootball_source import APIFootballSource
from app.data_sources.base import DataSourceConfig, DataSourceType


class MatchEventsSync:
    """比赛事件同步器"""

    # 主要联赛ID
    LEAGUES = {
        '152': '英超',
        '302': '西甲',
        '207': '德甲',
        '168': '意甲',
        '153': '法甲',
    }

    def __init__(self, db_path: str, api_key: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

        # 初始化API源
        config = DataSourceConfig(
            name='apifootball',
            source_type=DataSourceType.API,
            base_url='https://apiv3.apifootball.com',
            api_key=api_key,
            enabled=True
        )
        self.api = APIFootballSource(config)

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def _find_match_id(self, home_team: str, away_team: str, match_date: str) -> Optional[str]:
        """根据球队名称和日期查找数据库中的match_id"""
        self.cursor.execute('''
            SELECT m.match_id
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_date = ?
            AND (ht.name_en LIKE ? OR ht.name_cn LIKE ? OR ht.short_name LIKE ?)
            AND (at.name_en LIKE ? OR at.name_cn LIKE ? OR at.short_name LIKE ?)
            LIMIT 1
        ''', (match_date, f'%{home_team}%', f'%{home_team}%', f'%{home_team}%',
              f'%{away_team}%', f'%{away_team}%', f'%{away_team}%'))
        result = self.cursor.fetchone()
        return result[0] if result else None

    async def sync_match_events(self, from_date: str, to_date: str, league_id: str = None) -> Dict:
        """同步比赛事件数据"""
        results = {
            'total_matches': 0,
            'updated_matches': 0,
            'goals_added': 0,
            'cards_added': 0,
            'lineups_added': 0,
            'errors': [],
            'details': []
        }

        try:
            # 获取比赛事件
            events = await self.api.get_match_events_by_date(from_date, to_date, league_id)
            results['total_matches'] = len(events)

            for event in events:
                try:
                    match_date = event.get('date')
                    home_team = event.get('home_team', '')
                    away_team = event.get('away_team', '')

                    # 查找数据库中的比赛
                    db_match_id = self._find_match_id(home_team, away_team, match_date)

                    if not db_match_id:
                        continue

                    # 更新比赛基本信息
                    self.cursor.execute('''
                        UPDATE matches SET
                            match_time = COALESCE(?, match_time),
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
                        event.get('time'),
                        event.get('home_score'),
                        event.get('away_score'),
                        event.get('home_score_ht'),
                        event.get('away_score_ht'),
                        self._map_status(event.get('status')),
                        event.get('venue'),
                        event.get('referee'),
                        db_match_id
                    ))

                    # 处理进球事件
                    goalscorer = event.get('goalscorer', [])
                    if goalscorer:
                        self._save_goals(db_match_id, goalscorer)
                        results['goals_added'] += len(goalscorer)

                    # 处理红黄牌
                    cards = event.get('cards', [])
                    if cards:
                        results['cards_added'] += len(cards)

                    # 处理阵容
                    lineup = event.get('lineup', {})
                    if lineup:
                        results['lineups_added'] += 1

                    results['updated_matches'] += 1
                    results['details'].append({
                        'match': f'{home_team} vs {away_team}',
                        'date': match_date,
                        'goals': len(goalscorer),
                        'cards': len(cards)
                    })

                except Exception as e:
                    results['errors'].append(f"Error processing match: {str(e)}")

            self.conn.commit()

        except Exception as e:
            results['errors'].append(f"API error: {str(e)}")

        return results

    def _save_goals(self, match_id: str, goalscorer: List[Dict]):
        """保存进球数据到数据库"""
        for goal in goalscorer:
            time = goal.get('time', '')
            scorer = goal.get('home_scorer') or goal.get('away_scorer')
            assist = goal.get('home_assist') or goal.get('away_assist')
            is_home = bool(goal.get('home_scorer'))

            # 解析分钟数
            minute = self._parse_minute(time)

            # 可以保存到专门的进球表，或者更新比赛统计
            # 这里先记录到日志
            print(f"  Goal: {minute}min - {scorer} (assist: {assist})")

    def _parse_minute(self, time_str: str) -> int:
        """解析时间字符串为分钟数"""
        if not time_str:
            return 0
        try:
            # 处理 "45+2", "90+3" 等格式
            if '+' in time_str:
                parts = time_str.split('+')
                return int(parts[0]) + int(parts[1])
            return int(time_str.replace("'", "").replace('"', ''))
        except:
            return 0

    def _map_status(self, status: str) -> str:
        """映射比赛状态"""
        if not status:
            return 'scheduled'
        status_map = {
            'Finished': 'finished',
            'Half Time': 'halftime',
            'Postponed': 'postponed',
            'Cancelled': 'cancelled',
            'After ET': 'finished_aet',
            'After Pen.': 'finished_pen',
        }
        if "'" in status:
            return 'live'
        try:
            int(status)
            return 'live'
        except:
            pass
        return status_map.get(status, status.lower())


async def run_sync():
    """运行同步"""
    db_path = 'D:/football_tools/data/football_v2.db'
    api_key = 'bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443'

    sync = MatchEventsSync(db_path, api_key)
    sync.connect()

    try:
        today = datetime.now().strftime('%Y-%m-%d')
        past_7 = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        print('=' * 60)
        print('比赛事件数据同步')
        print('=' * 60)
        print(f'时间范围: {past_7} ~ {today}')
        print()

        total_results = {
            'total_matches': 0,
            'updated_matches': 0,
            'goals_added': 0,
            'cards_added': 0,
            'lineups_added': 0,
            'errors': []
        }

        for league_id, league_name in sync.LEAGUES.items():
            print(f'同步 {league_name}...')
            results = await sync.sync_match_events(past_7, today, league_id)

            total_results['total_matches'] += results['total_matches']
            total_results['updated_matches'] += results['updated_matches']
            total_results['goals_added'] += results['goals_added']
            total_results['cards_added'] += results['cards_added']
            total_results['lineups_added'] += results['lineups_added']
            total_results['errors'].extend(results['errors'])

            print(f'  比赛数: {results["total_matches"]}')
            print(f'  更新数: {results["updated_matches"]}')
            print(f'  进球数: {results["goals_added"]}')
            print()

        print('=' * 60)
        print('汇总:')
        print(f'  总比赛数: {total_results["total_matches"]}')
        print(f'  总更新数: {total_results["updated_matches"]}')
        print(f'  总进球数: {total_results["goals_added"]}')
        print(f'  总红黄牌: {total_results["cards_added"]}')
        print(f'  总阵容数: {total_results["lineups_added"]}')

        if total_results['errors']:
            print(f'  错误数: {len(total_results["errors"])}')

    finally:
        sync.close()


if __name__ == '__main__':
    asyncio.run(run_sync())
