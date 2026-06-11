"""
采集德乙联赛数据

数据源:
1. API-Football (apifootball) - 主要数据源
2. Sportmonks - 备用数据源
3. football-data.org - 备用数据源

采集内容:
- 联赛信息
- 球队信息
- 赛程/比赛结果
- 积分榜
- 射手榜
"""

import asyncio
import sqlite3
import json
import os
import httpx
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CONFIG_PATH = PROJECT_ROOT / "api_config.json"

# 德乙联赛ID配置
BUNDESLIGA_2_ID = 8  # 数据库中的league_id
APIFOOTBALL_BUNDESLIGA_2_ID = 80  # API-Football中的联赛ID
SPORTMONKS_BUNDESLIGA_2_ID = 36  # Sportmonks中的联赛ID


def load_config():
    """加载API配置"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class Bundesliga2Scraper:
    """德乙数据采集器"""

    def __init__(self):
        self.config = load_config()
        self.apifootball_key = self.config['apis']['apifootball']['api_key']
        self.sportmonks_token = self.config['apis']['sportmonks']['api_token']
        self.football_data_key = self.config['apis']['football_data_org']['api_token']

    async def fetch_from_apifootball(self, action: str, params: dict = None) -> dict:
        """从API-Football获取数据"""
        url = "https://apiv3.apifootball.com"
        all_params = {
            "action": action,
            "APIkey": self.apifootball_key
        }
        if params:
            all_params.update(params)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=all_params)
            return resp.json()

    async def fetch_from_sportmonks(self, endpoint: str, params: dict = None) -> dict:
        """从Sportmonks获取数据"""
        url = f"https://api.sportmonks.com/v3/football{endpoint}"
        all_params = {"api_token": self.sportmonks_token}
        if params:
            all_params.update(params)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=all_params)
            return resp.json()

    async def get_standings_apifootball(self, season: int = None) -> list:
        """获取积分榜 (API-Football)"""
        params = {"league_id": APIFOOTBALL_BUNDESLIGA_2_ID}
        if season:
            params["season"] = season

        data = await self.fetch_from_apifootball("get_standings", params)
        return data if isinstance(data, list) else []

    async def get_fixtures_apifootball(self, from_date: str = None, to_date: str = None) -> list:
        """获取赛程 (API-Football)"""
        params = {"league_id": APIFOOTBALL_BUNDESLIGA_2_ID}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        data = await self.fetch_from_apifootball("get_events", params)
        return data if isinstance(data, list) else []

    async def get_teams_apifootball(self) -> list:
        """获取球队列表 (API-Football)"""
        params = {"league_id": APIFOOTBALL_BUNDESLIGA_2_ID}
        data = await self.fetch_from_apifootball("get_teams", params)
        return data if isinstance(data, list) else []

    async def get_topscorers_apifootball(self, season: int = None) -> list:
        """获取射手榜 (API-Football)"""
        params = {"league_id": APIFOOTBALL_BUNDESLIGA_2_ID}
        if season:
            params["season"] = season

        data = await self.fetch_from_apifootball("get_topscorers", params)
        return data if isinstance(data, list) else []

    def save_teams_to_db(self, teams: list) -> int:
        """保存球队到数据库"""
        conn = get_db()
        cursor = conn.cursor()
        saved = 0

        for team in teams:
            try:
                team_key = team.get('team_key')
                team_name = team.get('team_name', '')
                country = team.get('team_country', 'Germany')

                # 检查是否已存在
                cursor.execute('SELECT team_id FROM teams WHERE sm_team_id = ? OR name_en = ?',
                             (team_key, team_name))
                if cursor.fetchone():
                    continue

                # 插入新球队
                cursor.execute('''
                    INSERT INTO teams (name_en, name_cn, country, sm_team_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (team_name, '', country, int(team_key)))
                saved += 1

            except Exception as e:
                print(f"保存球队失败: {e}")

        conn.commit()
        conn.close()
        return saved

    def save_standings_to_db(self, standings: list) -> int:
        """保存积分榜到数据库"""
        conn = get_db()
        cursor = conn.cursor()
        saved = 0

        for standing in standings:
            try:
                team_name = standing.get('team_name', '')
                position = standing.get('overall_league_position', 0)
                played = standing.get('overall_league_payed', 0)
                won = standing.get('overall_league_W', 0)
                drawn = standing.get('overall_league_D', 0)
                lost = standing.get('overall_league_L', 0)
                goals_for = standing.get('overall_league_GF', 0)
                goals_against = standing.get('overall_league_GA', 0)
                points = standing.get('overall_league_PTS', 0)

                # 获取team_id
                cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR sm_team_id = ?',
                             (team_name, standing.get('team_key')))
                row = cursor.fetchone()
                if not row:
                    continue

                team_id = row[0]

                # 创建或更新积分榜记录
                cursor.execute('''
                    INSERT OR REPLACE INTO standings (
                        league_id, season_id, team_id, position,
                        played, won, drawn, lost, goals_for, goals_against, points,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (BUNDESLIGA_2_ID, 126, team_id, position,
                      played, won, drawn, lost, goals_for, goals_against, points))
                saved += 1

            except Exception as e:
                print(f"保存积分榜失败: {e}")

        conn.commit()
        conn.close()
        return saved

    def save_fixtures_to_db(self, fixtures: list) -> dict:
        """保存赛程到数据库"""
        conn = get_db()
        cursor = conn.cursor()
        result = {'inserted': 0, 'updated': 0, 'skipped': 0}

        for fixture in fixtures:
            try:
                match_date = fixture.get('match_date', '')
                match_time = fixture.get('match_time', '')
                home_team = fixture.get('match_hometeam_name', '')
                away_team = fixture.get('match_awayteam_name', '')
                home_score = fixture.get('match_hometeam_score')
                away_score = fixture.get('match_awayteam_score')
                status = fixture.get('match_status', 'scheduled')
                round_num = fixture.get('match_round', '')

                # 获取team_id
                cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?',
                             (f'%{home_team}%',))
                home_row = cursor.fetchone()
                cursor.execute('SELECT team_id FROM teams WHERE name_en LIKE ?',
                             (f'%{away_team}%',))
                away_row = cursor.fetchone()

                if not home_row or not away_row:
                    result['skipped'] += 1
                    continue

                home_team_id = home_row[0]
                away_team_id = away_row[0]

                # 检查是否已存在
                cursor.execute('''
                    SELECT match_id FROM matches
                    WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                ''', (match_date, home_team_id, away_team_id))

                existing = cursor.fetchone()

                if existing:
                    # 更新比分
                    cursor.execute('''
                        UPDATE matches SET
                            home_goals = ?, away_goals = ?, status = ?,
                            match_time = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE match_id = ?
                    ''', (home_score, away_score, status, match_time, existing[0]))
                    result['updated'] += 1
                else:
                    # 插入新比赛
                    cursor.execute('''
                        INSERT INTO matches (
                            match_date, match_time, home_team_id, away_team_id,
                            home_goals, away_goals, status, league_id, season_id,
                            round_num, source, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'apifootball',
                                  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (match_date, match_time, home_team_id, away_team_id,
                          home_score, away_score, status, BUNDESLIGA_2_ID, 126,
                          round_num))
                    result['inserted'] += 1

            except Exception as e:
                print(f"保存比赛失败: {e}")

        conn.commit()
        conn.close()
        return result


async def main():
    """主函数"""
    print("=" * 60)
    print("德乙联赛数据采集")
    print("=" * 60)

    scraper = Bundesliga2Scraper()

    # 1. 获取球队列表
    print("\n1. 获取球队列表...")
    try:
        teams = await scraper.get_teams_apifootball()
        print(f"   获取到 {len(teams)} 支球队")
        if teams:
            saved = scraper.save_teams_to_db(teams)
            print(f"   新保存 {saved} 支球队")
    except Exception as e:
        print(f"   获取球队失败: {e}")

    # 2. 获取积分榜
    print("\n2. 获取积分榜...")
    try:
        standings = await scraper.get_standings_apifootball()
        print(f"   获取到 {len(standings)} 条积分榜记录")
        if standings:
            saved = scraper.save_standings_to_db(standings)
            print(f"   保存 {saved} 条积分榜记录")
    except Exception as e:
        print(f"   获取积分榜失败: {e}")

    # 3. 获取本赛季赛程
    print("\n3. 获取本赛季赛程...")
    try:
        from datetime import datetime, timedelta
        today = datetime.now()
        from_date = (today - timedelta(days=180)).strftime('%Y-%m-%d')  # 过去6个月
        to_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')  # 未来1个月

        fixtures = await scraper.get_fixtures_apifootball(from_date, to_date)
        print(f"   获取到 {len(fixtures)} 场比赛")
        if fixtures:
            result = scraper.save_fixtures_to_db(fixtures)
            print(f"   新增 {result['inserted']} 场, 更新 {result['updated']} 场, 跳过 {result['skipped']} 场")
    except Exception as e:
        print(f"   获取赛程失败: {e}")

    # 4. 获取射手榜
    print("\n4. 获取射手榜...")
    try:
        scorers = await scraper.get_topscorers_apifootball()
        print(f"   获取到 {len(scorers)} 名射手")
        if scorers:
            for i, s in enumerate(scorers[:5]):
                name = s.get('player_name', '')
                goals = s.get('goals', 0)
                team = s.get('team_name', '')
                print(f"   {i+1}. {name} ({team}) - {goals}球")
    except Exception as e:
        print(f"   获取射手榜失败: {e}")

    # 5. 统计当前数据库状态
    print("\n" + "=" * 60)
    print("数据库统计")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (BUNDESLIGA_2_ID,))
    match_count = cursor.fetchone()[0]
    print(f"德乙比赛总数: {match_count} 场")

    cursor.execute('SELECT COUNT(*) FROM teams WHERE country = ?', ('Germany',))
    team_count = cursor.fetchone()[0]
    print(f"德国球队总数: {team_count} 支")

    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = ? AND status = 'finished'
    ''', (BUNDESLIGA_2_ID,))
    finished = cursor.fetchone()[0]
    print(f"已结束比赛: {finished} 场")

    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = ? AND status = 'scheduled'
    ''', (BUNDESLIGA_2_ID,))
    scheduled = cursor.fetchone()[0]
    print(f"未开始比赛: {scheduled} 场")

    conn.close()

    print("\n采集完成！")


if __name__ == "__main__":
    asyncio.run(main())
