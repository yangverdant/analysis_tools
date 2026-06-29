"""
体彩实时同步服务

使用现有的 LotteryCrawler 爬取体彩数据，然后：
1. 保存到 lottery_matches 表
2. 保存赔率到 lottery_odds 表
3. 桥接 oddsfe 比赛
4. 更新 sell_status

运行方式：
    python scripts/sync_sporttery_matches.py
"""
import sqlite3
import asyncio
import sys
from datetime import datetime, date, timedelta
sys.path.append('D:/football_tools/backend/app')
sys.stdout.reconfigure(encoding='utf-8')

from lottery.data_sources.scrapers.lottery_crawler import LotteryCrawler

DB_PATH = 'D:/football_tools/data/football_v2.db'
ODDSFE_DB = 'D:/football_tools/fetchers/odds_feed_api/oddsfe_merged.db'


class SportterySyncService:
    """体彩同步服务"""

    def __init__(self):
        self.crawler = LotteryCrawler()
        self.db_conn = sqlite3.connect(DB_PATH)
        self.oddsfe_conn = sqlite3.connect(ODDSFE_DB)
        self.db_cursor = self.db_conn.cursor()
        self.oddsfe_cursor = self.oddsfe_conn.cursor()
        self._known_match_ids = set()

    def _load_known_matches(self):
        """加载已知比赛 ID"""
        self.db_cursor.execute('SELECT lottery_match_id FROM lottery_matches')
        self._known_match_ids = {row[0] for row in self.db_cursor.fetchall()}
        print(f"加载已知比赛：{len(self._known_match_ids)} 场")

    async def sync_matches(self, target_date: date = None) -> dict:
        """同步指定日期的比赛"""
        if target_date is None:
            target_date = date.today()

        print(f"\n=== 同步 {target_date} 的比赛 ===")

        # 爬取比赛
        result = await self.crawler.crawl_matches(target_date)

        if not result.success:
            print(f"爬取失败：{result.error}")
            return {'success': False, 'error': result.error}

        matches = result.data
        print(f"爬取到 {len(matches)} 场比赛")

        # 保存比赛
        saved = 0
        new_matches = []

        for match in matches:
            match_id = match.get('lottery_match_id')

            # 跳过已知的比赛
            if match_id in self._known_match_ids:
                continue

            new_matches.append(match)
            self._known_match_ids.add(match_id)

            # 插入数据库
            self.db_cursor.execute('''
                INSERT OR REPLACE INTO lottery_matches
                (lottery_match_id, match_id, home_team_cn, away_team_cn,
                 league_name_cn, match_date, match_time, beijing_time,
                 play_types, sell_status, handicap_line, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                match_id,
                match.get('match_num', match_id),
                match.get('home_team_cn'),
                match.get('away_team_cn'),
                match.get('league_name_cn'),
                match.get('match_date'),
                match.get('match_time'),
                match.get('beijing_time', f"{match.get('match_date')} {match.get('match_time', '00:00:00')}"),
                ','.join(match.get('play_types', [])),
                match.get('sell_status', 'selling'),
                match.get('handicap_line', 0)
            ))
            saved += 1

        self.db_conn.commit()
        print(f"新增 {saved} 场比赛")

        # 保存赔率
        odds_updated = self._save_odds(new_matches)
        print(f"保存赔率 {odds_updated} 条")

        # 桥接 oddsfe
        bridged = self._bridge_with_oddsfe(new_matches)
        print(f"桥接 oddsfe: {bridged} 场")

        return {
            'success': True,
            'saved': saved,
            'odds_updated': odds_updated,
            'bridged': bridged
        }

    def _save_odds(self, matches: list) -> int:
        """保存赔率数据"""
        updated = 0

        for match in matches:
            match_id = match.get('lottery_match_id')
            odds_data = match.get('odds_data', {})

            for play_type, odds in odds_data.items():
                if not odds:
                    continue

                self.db_cursor.execute('''
                    INSERT INTO lottery_odds
                    (lottery_match_id, play_type, odds_data, snapshot_type, created_at)
                    VALUES (?, ?, ?, 'opening', CURRENT_TIMESTAMP)
                ''', (match_id, play_type, str(odds)))
                updated += 1

        self.db_conn.commit()
        return updated

    def _bridge_with_oddsfe(self, matches: list) -> int:
        """桥接 oddsfe 比赛"""
        bridged = 0

        for match in matches:
            home_cn = match.get('home_team_cn')
            away_cn = match.get('away_team_cn')
            match_date = match.get('match_date')
            match_time = match.get('match_time', '12:00:00')

            # 获取英文队名
            self.db_cursor.execute(
                'SELECT name_en FROM teams WHERE name_cn = ?',
                (home_cn,)
            )
            home_row = self.db_cursor.fetchone()
            self.db_cursor.execute(
                'SELECT name_en FROM teams WHERE name_cn = ?',
                (away_cn,)
            )
            away_row = self.db_cursor.fetchone()

            if not home_row or not away_row:
                continue

            home_en = home_row[0]
            away_en = away_row[0]

            # 计算时间窗口
            beijing_str = f"{match_date} {match_time}"
            try:
                bj_dt = datetime.strptime(beijing_str, "%Y-%m-%d %H:%M:%S")
            except:
                bj_dt = datetime.strptime(match_date, "%Y-%m-%d")

            utc_dt = bj_dt - timedelta(hours=8)
            start_utc = (utc_dt - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
            end_utc = (utc_dt + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")

            # 在 oddsfe 中查找
            self.oddsfe_cursor.execute('''
                SELECT event_id FROM oddsfe
                WHERE event_start_at >= ? AND event_start_at <= ?
                AND (
                    (LOWER(team_home_name) LIKE ? AND LOWER(team_away_name) LIKE ?)
                    OR (LOWER(team_home_name) LIKE ? AND LOWER(team_away_name) LIKE ?)
                )
                LIMIT 1
            ''', (
                start_utc, end_utc,
                f'%{home_en}%', f'%{away_en}%',
                f'%{away_en}%', f'%{home_en}%'
            ))

            oddsfe_row = self.oddsfe_cursor.fetchone()
            if oddsfe_row:
                event_id = oddsfe_row[0]
                self.db_cursor.execute('''
                    UPDATE lottery_matches
                    SET oddsfe_event_id = ?
                    WHERE lottery_match_id = ?
                ''', (event_id, match.get('lottery_match_id')))
                bridged += 1
                print(f"  桥接：{home_cn} vs {away_cn} -> {event_id}")

        self.db_conn.commit()
        return bridged

    async def sync_future_matches(self, days: int = 7) -> dict:
        """同步未来 N 天的比赛"""
        today = date.today()
        total = {'saved': 0, 'odds_updated': 0, 'bridged': 0}

        for i in range(days):
            target_date = today + timedelta(days=i)
            result = await self.sync_matches(target_date)

            if result.get('success'):
                total['saved'] += result.get('saved', 0)
                total['odds_updated'] += result.get('odds_updated', 0)
                total['bridged'] += result.get('bridged', 0)

        return total

    def close(self):
        """关闭连接"""
        self.db_conn.close()
        self.oddsfe_conn.close()


async def main():
    """主函数"""
    print("=== 体彩实时同步服务 ===\n")

    service = SportterySyncService()
    service._load_known_matches()

    try:
        # 同步未来 7 天的比赛
        result = await service.sync_future_matches(7)

        print(f"\n=== 同步完成 ===")
        print(f"新增比赛：{result['saved']} 场")
        print(f"赔率记录：{result['odds_updated']} 条")
        print(f"桥接 oddsfe: {result['bridged']} 场")

    except Exception as e:
        print(f"同步失败：{e}")
        import traceback
        traceback.print_exc()

    finally:
        service.close()


if __name__ == '__main__':
    asyncio.run(main())
