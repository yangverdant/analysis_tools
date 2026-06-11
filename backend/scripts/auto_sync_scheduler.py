"""
自动同步调度器
定期检查并更新未来比赛的时间和赔率数据
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutoSyncScheduler:
    """自动同步调度器"""

    # 联赛配置 - API Football league_id
    LEAGUES = {
        '152': {'name': '英超', 'api_code': 'PL'},
        '302': {'name': '西甲', 'api_code': 'PD'},
        '207': {'name': '德甲', 'api_code': 'BL1'},
        '168': {'name': '意甲', 'api_code': 'SA'},
        '153': {'name': '法甲', 'api_code': 'FL1'},
        '3': {'name': '欧冠', 'api_code': 'CL'},
    }

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

    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        today = datetime.now().strftime('%Y-%m-%d')
        future_3 = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        future_7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

        status = {}

        for days, label in [(3, 'next_3_days'), (7, 'next_7_days')]:
            future = future_3 if days == 3 else future_7
            self.cursor.execute('''
                SELECT COUNT(*),
                       SUM(CASE WHEN match_time IS NOT NULL AND match_time != '' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN odds_home IS NOT NULL THEN 1 ELSE 0 END)
                FROM matches WHERE match_date >= ? AND match_date <= ?
            ''', (today, future))

            row = self.cursor.fetchone()
            status[label] = {
                'total': row[0],
                'has_time': row[1],
                'has_odds': row[2],
                'time_coverage': round(row[1] / row[0] * 100, 1) if row[0] > 0 else 0,
                'odds_coverage': round(row[2] / row[0] * 100, 1) if row[0] > 0 else 0,
            }

        return status

    def _find_team_id(self, team_name: str) -> Optional[int]:
        """根据球队名称查找team_id"""
        self.cursor.execute('''
            SELECT team_id FROM teams
            WHERE name_en LIKE ? OR name_cn LIKE ? OR short_name LIKE ?
            LIMIT 1
        ''', (f'%{team_name}%', f'%{team_name}%', f'%{team_name}%'))
        result = self.cursor.fetchone()
        return result[0] if result else None

    async def sync_from_api(self) -> Dict:
        """从API同步数据 - 使用apifootball作为主要数据源"""
        from app.data_sources.manager import DataSourceManager

        manager = DataSourceManager()

        # 使用apifootball作为主要数据源
        source = manager.get_source('apifootball')

        if not source:
            return {'success': False, 'error': 'apifootball source not found'}

        results = {
            'success': True,
            'time_updated': 0,
            'odds_updated': 0,
            'matches_added': 0,
            'errors': [],
            'details': []
        }

        today = datetime.now().strftime('%Y-%m-%d')
        future_7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

        for league_id, league_info in self.LEAGUES.items():
            try:
                logger.info(f"Syncing {league_info['name']}...")

                # 获取未来7天赛程
                fixtures = await source.get_fixtures(
                    league_id=league_id,
                    from_date=today,
                    to_date=future_7
                )

                if not fixtures:
                    logger.info(f"No fixtures found for {league_info['name']}")
                    continue

                logger.info(f"Found {len(fixtures)} fixtures for {league_info['name']}")

                for f in fixtures:
                    # 查找球队ID
                    home_team_id = self._find_team_id(f.home_team)
                    away_team_id = self._find_team_id(f.away_team)

                    if not home_team_id or not away_team_id:
                        logger.warning(f"Team not found: {f.home_team} or {f.away_team}")
                        continue

                    # 检查比赛是否已存在
                    self.cursor.execute('''
                        SELECT match_id FROM matches
                        WHERE match_date = ?
                        AND home_team_id = ?
                        AND away_team_id = ?
                    ''', (f.date, home_team_id, away_team_id))

                    existing = self.cursor.fetchone()

                    if existing:
                        # 更新时间和状态（强制更新未来比赛）
                        if f.time:
                            self.cursor.execute('''
                                UPDATE matches SET
                                    match_time = ?,
                                    status = ?,
                                    source = 'apifootball'
                                WHERE match_id = ?
                            ''', (f.time, f.status or 'scheduled', existing[0]))

                            if self.cursor.rowcount > 0:
                                results['time_updated'] += 1
                                results['details'].append({
                                    'league': league_info['name'],
                                    'date': f.date,
                                    'match': f'{f.home_team} vs {f.away_team}',
                                    'time': f.time,
                                    'action': 'updated'
                                })
                    else:
                        # 插入新比赛
                        self.cursor.execute('''
                            INSERT INTO matches (
                                match_date, match_time, home_team_id, away_team_id,
                                home_goals, away_goals, status, league_id,
                                source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            f.date, f.time, home_team_id, away_team_id,
                            f.home_score, f.away_score, f.status,
                            int(league_id), 'apifootball'
                        ))

                        results['matches_added'] += 1
                        results['details'].append({
                            'league': league_info['name'],
                            'date': f.date,
                            'match': f'{f.home_team} vs {f.away_team}',
                            'time': f.time,
                            'action': 'added'
                        })

                self.conn.commit()

            except Exception as e:
                error_msg = f"Error syncing {league_info['name']}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

        return results

    def check_missing_matches(self) -> List[Dict]:
        """检查缺失的比赛（未来3天应该有但没有的比赛）"""
        today = datetime.now().strftime('%Y-%m-%d')
        future_3 = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')

        # 检查五大联赛未来3天的比赛数量
        missing = []

        for league_id, league_info in self.LEAGUES.items():
            self.cursor.execute('''
                SELECT COUNT(*) FROM matches
                WHERE league_id = ?
                AND match_date >= ? AND match_date <= ?
            ''', (league_id, today, future_3))

            count = self.cursor.fetchone()[0]

            # 如果未来3天比赛少于3场，可能缺少数据
            if count < 3:
                missing.append({
                    'league': league_info['name'],
                    'league_id': league_id,
                    'api_code': league_info['api_code'],
                    'matches_count': count,
                    'expected': '>=3'
                })

        return missing

    def generate_sync_report(self) -> Dict:
        """生成同步报告"""
        status = self.get_sync_status()
        missing = self.check_missing_matches()

        report = {
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'missing_matches': missing,
            'recommendations': []
        }

        # 生成建议
        if status['next_3_days']['time_coverage'] < 90:
            report['recommendations'].append(
                f"未来3天时间覆盖率仅{status['next_3_days']['time_coverage']}%，建议立即同步"
            )

        if status['next_3_days']['odds_coverage'] < 50:
            report['recommendations'].append(
                f"未来3天赔率覆盖率仅{status['next_3_days']['odds_coverage']}%，建议获取赔率数据"
            )

        if missing:
            report['recommendations'].append(
                f"以下联赛可能缺少比赛数据: {', '.join([m['league'] for m in missing])}"
            )

        return report


async def run_auto_sync():
    """运行自动同步"""
    db_path = 'D:/football_tools/data/football_v2.db'

    scheduler = AutoSyncScheduler(db_path)
    scheduler.connect()

    try:
        # 生成同步报告
        print('=' * 70)
        print('自动同步报告')
        print('=' * 70)
        print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print()

        report = scheduler.generate_sync_report()

        print('数据状态:')
        print(f"  未来3天: {report['status']['next_3_days']['has_time']}/{report['status']['next_3_days']['total']} 有时间 ({report['status']['next_3_days']['time_coverage']}%)")
        print(f"  未来7天: {report['status']['next_7_days']['has_time']}/{report['status']['next_7_days']['total']} 有时间 ({report['status']['next_7_days']['time_coverage']}%)")
        print()

        if report['missing_matches']:
            print('可能缺少比赛的联赛:')
            for m in report['missing_matches']:
                print(f"  {m['league']}: 仅{m['matches_count']}场比赛")
            print()

        if report['recommendations']:
            print('建议:')
            for r in report['recommendations']:
                print(f'  - {r}')
            print()

        # 执行同步
        print('开始同步...')
        results = await scheduler.sync_from_api()

        print(f'同步结果:')
        print(f'  时间更新: {results["time_updated"]}场')
        print(f'  赔率更新: {results["odds_updated"]}场')

        if results['errors']:
            print(f'  错误: {results["errors"]}')

        # 同步后状态
        print()
        print('同步后状态:')
        status = scheduler.get_sync_status()
        print(f"  未来3天: {status['next_3_days']['has_time']}/{status['next_3_days']['total']} 有时间 ({status['next_3_days']['time_coverage']}%)")

        # 保存报告
        report_path = Path('logs/sync_report.json')
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'before': report['status'],
                'after': status,
                'results': results
            }, f, ensure_ascii=False, indent=2)

        print(f'\n报告已保存: {report_path}')

    finally:
        scheduler.close()


if __name__ == '__main__':
    asyncio.run(run_auto_sync())
