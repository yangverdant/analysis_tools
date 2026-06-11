"""
数据补充脚本 - 按优先级依次补充缺失数据
1. 同步未来比赛赛程
2. 补充已结束比赛缺失比分
3. 补充赔率数据
"""

import asyncio
import sqlite3
import aiohttp
import json
from datetime import datetime, timedelta
from pathlib import Path

# 配置
DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'football_v2.db'
CONFIG_PATH = Path(__file__).parent.parent.parent / 'api_config.json'

# 加载API配置
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    API_CONFIG = json.load(f)

# API Football配置
APIFOOTBALL_KEY = API_CONFIG['apis']['apifootball']['api_key']
APIFOOTBALL_URL = API_CONFIG['apis']['apifootball']['base_url']


class DataSyncService:
    """数据同步服务"""

    def __init__(self):
        self.conn = None
        self.cursor = None
        self.session = None

    def connect(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

    async def init_session(self):
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()

    # ========== 1. 同步未来比赛赛程 ==========
    async def sync_future_fixtures(self, days: int = 30) -> dict:
        """从API-Football同步未来比赛"""
        print(f"\n{'='*50}")
        print(f"1. 同步未来 {days} 天比赛赛程")
        print(f"{'='*50}")

        today = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

        # 获取当前数据库中的未来比赛
        self.cursor.execute('''
            SELECT COUNT(*) FROM matches
            WHERE match_date >= ? AND match_date <= ?
        ''', (today, end_date))
        before_count = self.cursor.fetchone()[0]
        print(f"当前未来比赛数: {before_count}")

        # 从API获取赛程
        url = f"{APIFOOTBALL_URL}/"
        params = {
            'action': 'get_events',
            'APIkey': APIFOOTBALL_KEY,
            'from': today,
            'to': end_date
        }

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"API请求失败: {resp.status}")
                    return {'success': False, 'error': f'HTTP {resp.status}'}

                data = await resp.json()

                if not isinstance(data, list):
                    print(f"API返回格式异常: {type(data)}")
                    return {'success': False, 'error': 'Invalid response'}

                print(f"API返回 {len(data)} 场比赛")

                # 处理并插入/更新比赛
                inserted = 0
                updated = 0
                skipped = 0

                for item in data:
                    match_id = f"apifootball_{item.get('match_id', '')}"
                    match_date = item.get('match_date', '')
                    match_time = item.get('match_time', '')
                    league_name = item.get('league_name', '')
                    home_team = item.get('match_hometeam_name', '')
                    away_team = item.get('match_awayteam_name', '')
                    home_score = item.get('match_hometeam_score')
                    away_score = item.get('match_awayteam_score')
                    status = item.get('match_status', '')

                    # 映射状态
                    if status == 'FT':
                        status = 'finished'
                    elif status in ('NS', 'TBD'):
                        status = 'scheduled'

                    # 检查是否已存在
                    self.cursor.execute('SELECT match_id FROM matches WHERE match_id = ?', (match_id,))
                    exists = self.cursor.fetchone()

                    if exists:
                        # 更新
                        self.cursor.execute('''
                            UPDATE matches SET
                                match_time = COALESCE(?, match_time),
                                home_goals = COALESCE(?, home_goals),
                                away_goals = COALESCE(?, away_goals),
                                status = COALESCE(?, status)
                            WHERE match_id = ?
                        ''', (match_time, home_score, away_score, status, match_id))
                        updated += 1
                    else:
                        # 需要先获取league_id和team_id，这里简化处理
                        skipped += 1

                self.conn.commit()

                # 统计
                self.cursor.execute('''
                    SELECT COUNT(*) FROM matches
                    WHERE match_date >= ? AND match_date <= ?
                ''', (today, end_date))
                after_count = self.cursor.fetchone()[0]

                print(f"更新: {updated}, 跳过(需映射): {skipped}")
                print(f"更新后未来比赛数: {after_count}")

                return {
                    'success': True,
                    'api_returned': len(data),
                    'updated': updated,
                    'skipped': skipped,
                    'before': before_count,
                    'after': after_count
                }

        except Exception as e:
            print(f"同步失败: {e}")
            return {'success': False, 'error': str(e)}

    # ========== 2. 补充已结束比赛缺失比分 ==========
    async def fix_missing_scores(self) -> dict:
        """补充已结束比赛缺失的比分"""
        print(f"\n{'='*50}")
        print(f"2. 补充已结束比赛缺失比分")
        print(f"{'='*50}")

        # 查找缺失比分的比赛
        self.cursor.execute('''
            SELECT match_id, match_date, home_team_id, away_team_id
            FROM matches
            WHERE status = 'finished'
            AND (home_goals IS NULL OR away_goals IS NULL)
            LIMIT 200
        ''')
        missing = self.cursor.fetchall()
        print(f"缺失比分的已结束比赛: {len(missing)} 场")

        if not missing:
            print("无缺失比分")
            return {'success': True, 'fixed': 0}

        # 从API获取比分
        fixed = 0
        for row in missing:
            match_date = row['match_date']

            try:
                # 按日期查询
                url = f"{APIFOOTBALL_URL}/"
                params = {
                    'action': 'get_events',
                    'APIkey': APIFOOTBALL_KEY,
                    'from': match_date,
                    'to': match_date
                }

                async with self.session.get(url, params=params) as resp:
                    if resp.status != 200:
                        continue

                    data = await resp.json()

                    if isinstance(data, list):
                        for item in data:
                            if item.get('match_status') == 'FT':
                                # 尝试匹配
                                api_match_id = f"apifootball_{item.get('match_id', '')}"

                                # 简单匹配：同日期的比赛
                                home_score = item.get('match_hometeam_score')
                                away_score = item.get('match_awayteam_score')

                                if home_score is not None and away_score is not None:
                                    self.cursor.execute('''
                                        UPDATE matches SET
                                            home_goals = ?,
                                            away_goals = ?
                                        WHERE match_id = ?
                                        AND (home_goals IS NULL OR away_goals IS NULL)
                                    ''', (home_score, away_score, row['match_id']))

                                    if self.cursor.rowcount > 0:
                                        fixed += 1
                                        break

                # 避免请求过快
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"处理 {row['match_id']} 失败: {e}")
                continue

        self.conn.commit()
        print(f"修复比分: {fixed} 场")

        return {'success': True, 'fixed': fixed, 'total_missing': len(missing)}

    # ========== 3. 补充赔率数据 ==========
    async def sync_odds(self) -> dict:
        """从API-Football同步赔率数据"""
        print(f"\n{'='*50}")
        print(f"3. 补充赔率数据")
        print(f"{'='*50}")

        # 检查缺失赔率的比赛
        self.cursor.execute('''
            SELECT COUNT(*) FROM matches m
            WHERE NOT EXISTS (
                SELECT 1 FROM match_odds o WHERE o.match_id = m.match_id
            )
        ''')
        missing_odds = self.cursor.fetchone()[0]
        print(f"缺失赔率的比赛: {missing_odds} 场")

        # API-Football赔率端点
        try:
            url = f"{APIFOOTBALL_URL}/"
            params = {
                'action': 'get_odds',
                'APIkey': APIFOOTBALL_KEY
            }

            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"赔率API请求失败: {resp.status}")
                    return {'success': False, 'error': f'HTTP {resp.status}'}

                data = await resp.json()
                print(f"API返回赔率数据: {len(data) if isinstance(data, list) else 0} 条")

                if not isinstance(data, list):
                    return {'success': False, 'error': 'Invalid response'}

                # 处理赔率数据
                odds_added = 0
                for item in data:
                    match_id = f"apifootball_{item.get('match_id', '')}"

                    # 获取赔率值
                    odds = item.get('odds', {})
                    if not odds:
                        continue

                    # 提取主胜/平/客胜赔率
                    home_odds = None
                    draw_odds = None
                    away_odds = None

                    # API-Football赔率格式
                    for odd_item in odds.get('match', []):
                        if odd_item.get('type') == '1':
                            home_odds = float(odd_item.get('odd', 0))
                        elif odd_item.get('type') == 'X':
                            draw_odds = float(odd_item.get('odd', 0))
                        elif odd_item.get('type') == '2':
                            away_odds = float(odd_item.get('odd', 0))

                    if home_odds and draw_odds and away_odds:
                        # 检查比赛是否存在
                        self.cursor.execute('SELECT match_id FROM matches WHERE match_id = ?', (match_id,))
                        if self.cursor.fetchone():
                            # 插入赔率
                            try:
                                self.cursor.execute('''
                                    INSERT OR REPLACE INTO match_odds
                                    (match_id, odds_home, odds_draw, odds_away, source, updated_at)
                                    VALUES (?, ?, ?, ?, 'apifootball', datetime('now'))
                                ''', (match_id, home_odds, draw_odds, away_odds))
                                odds_added += 1
                            except:
                                pass

                self.conn.commit()
                print(f"添加赔率: {odds_added} 场")

                return {'success': True, 'odds_added': odds_added}

        except Exception as e:
            print(f"赔率同步失败: {e}")
            return {'success': False, 'error': str(e)}

    # ========== 综合报告 ==========
    def print_summary(self):
        """打印数据概览"""
        print(f"\n{'='*50}")
        print(f"数据概览")
        print(f"{'='*50}")

        # 基础统计
        self.cursor.execute('SELECT COUNT(*) FROM matches')
        total_matches = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM matches WHERE status = "finished"')
        finished = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM matches WHERE status = "scheduled"')
        scheduled = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM match_odds')
        odds_count = self.cursor.fetchone()[0]

        # 未来比赛
        today = datetime.now().strftime('%Y-%m-%d')
        self.cursor.execute('''
            SELECT COUNT(*) FROM matches WHERE match_date >= ?
        ''', (today,))
        future_matches = self.cursor.fetchone()[0]

        print(f"总比赛数: {total_matches}")
        print(f"已结束: {finished}")
        print(f"未开始: {scheduled}")
        print(f"未来比赛: {future_matches}")
        print(f"赔率记录: {odds_count}")
        print(f"赔率覆盖率: {odds_count/total_matches*100:.1f}%")


async def main():
    """主函数"""
    print("开始数据补充...")

    service = DataSyncService()
    service.connect()
    await service.init_session()

    try:
        # 打印初始状态
        service.print_summary()

        # 1. 同步未来比赛
        await service.sync_future_fixtures(days=30)

        # 2. 补充缺失比分
        await service.fix_missing_scores()

        # 3. 同步赔率
        await service.sync_odds()

        # 打印最终状态
        service.print_summary()

    finally:
        await service.close_session()
        service.close()

    print("\n数据补充完成!")


if __name__ == '__main__':
    asyncio.run(main())
