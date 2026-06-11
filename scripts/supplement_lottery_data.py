"""
补充体彩比赛分析所需的所有数据

数据来源：
1. API-Football (apiv3.apifootball.com) - 比赛数据、球队数据、联赛数据
2. 现有数据库 - 历史比赛数据

需要补充的数据：
1. 球队名称映射 (team_name_mapping)
2. 球队历史比赛 (matches)
3. 联赛积分榜 (standings)
4. 球队统计 (球队攻击力、防守力等)
5. Elo评分
6. 球员数据
"""

import asyncio
import aiohttp
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# API配置
API_URL = "https://apiv3.apifootball.com"
API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'football_v2.db')

# 联赛ID映射
LEAGUE_MAPPING = {
    '日职': 98,      # J1 League
    '英甲': 137,     # League One
    '瑞典超': 113,   # Allsvenskan
    '意甲': 135,     # Serie A
    '挪超': 115,     # Eliteserien
    '英超': 148,     # Premier League
    '西甲': 140,     # La Liga
    '美职': 207,     # MLS
    '德甲': 78,      # Bundesliga
}

# 球队名称映射（中文名 -> 英文名/常用名）
TEAM_NAME_MAPPING = {
    # 日职
    '清水鼓动': 'Shimizu S-Pulse',
    '大阪钢巴': 'Gamba Osaka',

    # 英甲
    '博尔顿': 'Bolton',
    '斯托克港': 'Stockport County',

    # 瑞典超
    '哈马比': 'Hammarby',
    '索尔纳': 'AIK',
    '天狼星': 'Sirius',
    '哥德堡盖斯': 'GAIS',
    '马尔默': 'Malmo FF',
    '韦斯特罗斯': 'Vasteras SK',
    'IFK哥德堡': 'IFK Goteborg',
    '埃尔夫斯堡': 'Elfsborg',
    '米亚尔比': 'Mjallby',
    '赫根': 'Hacken',

    # 意甲
    '帕尔马': 'Parma',
    '萨索洛': 'Sassuolo',
    '那不勒斯': 'Napoli',
    '乌迪内斯': 'Udinese',
    '莱切': 'Lecce',
    '热那亚': 'Genoa',
    '维罗纳': 'Verona',
    '罗马': 'Roma',
    '都灵': 'Torino',
    '尤文': 'Juventus',
    '克雷莫纳': 'Cremonese',
    '科莫': 'Como',
    'AC米兰': 'Milan',
    '卡利亚里': 'Cagliari',

    # 挪超
    '博德闪耀': 'Bodo/Glimt',
    '布兰': 'Brann',
    '克里斯蒂安松': 'Kristiansund',
    '维京': 'Viking',
    '萨尔普斯堡': 'Sarpsborg',
    '莫尔德': 'Molde',
    '斯托姆加斯特': 'Stromsgodset',
    '桑纳菲尤尔': 'Sandefjord',
    '腓特烈斯塔': 'Fredrikstad',
    '斯塔贝克': 'Stabaek',
    '罗森博格': 'Rosenborg',
    '特罗姆瑟': 'Tromso',
    '奥德': 'Odd',
    'KFUM奥斯陆': 'KFUM Oslo',
    '汉坎': 'HamKam',
    '瓦勒伦加': 'Valerenga',
    '利勒斯特罗姆': 'Lillestrom',

    # 英超
    '富勒姆': 'Fulham',
    '纽卡斯尔': 'Newcastle',
    '利物浦': 'Liverpool',
    '布伦特': 'Brentford',
    '曼城': 'Manchester City',
    '维拉': 'Aston Villa',
    '桑德兰': 'Sunderland',
    '切尔西': 'Chelsea',
    '伯恩利': 'Burnley',
    '狼队': 'Wolves',
    '水晶宫': 'Crystal Palace',
    '阿森纳': 'Arsenal',
    '西汉姆': 'West Ham',
    '利兹联': 'Leeds',
    '热刺': 'Tottenham',
    '埃弗顿': 'Everton',
    '诺丁汉森林': "Nottm Forest",
    '伯恩茅斯': 'Bournemouth',

    # 西甲
    '比利亚雷': 'Villarreal',
    '马竞': 'Atletico Madrid',

    # 美职
    '迈阿密国际': 'Inter Miami',
    '费城联合': 'Philadelphia Union',
    '洛杉矶FC': 'LAFC',
    '西雅图海湾人': 'Seattle Sounders',

    # 德甲
    '帕德博恩': 'Paderborn',
    '沃尔夫斯堡': 'Wolfsburg',
}


class DataSupplementer:
    """数据补充器"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        """初始化HTTP会话"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None

    def get_db(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def api_request(self, params: Dict) -> Optional[List]:
        """发送API请求"""
        params['APIkey'] = API_KEY
        url = f"{API_URL}/"

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and 'error' not in data:
                        return [data]
                else:
                    logger.warning(f"API request failed: {response.status}")
        except Exception as e:
            logger.error(f"API request error: {e}")
        return None

    async def find_team_id(self, team_name_cn: str) -> Optional[int]:
        """查找球队ID"""
        conn = self.get_db()
        cursor = conn.cursor()

        # 1. 直接查询teams表
        cursor.execute("""
            SELECT team_id FROM teams
            WHERE name_cn = ? OR name_en = ? OR name_en LIKE ?
        """, (team_name_cn, team_name_cn, f'%{team_name_cn}%'))

        row = cursor.fetchone()
        if row:
            conn.close()
            return row['team_id']

        # 2. 使用映射表查找英文名
        if team_name_cn in TEAM_NAME_MAPPING:
            eng_name = TEAM_NAME_MAPPING[team_name_cn]
            cursor.execute("""
                SELECT team_id FROM teams
                WHERE name_en = ? OR name_en LIKE ?
            """, (eng_name, f'%{eng_name}%'))

            row = cursor.fetchone()
            if row:
                conn.close()
                return row['team_id']

        # 3. 从API查询
        logger.info(f"Searching team from API: {team_name_cn}")
        if team_name_cn in TEAM_NAME_MAPPING:
            search_name = TEAM_NAME_MAPPING[team_name_cn]
        else:
            search_name = team_name_cn

        data = await self.api_request({
            'action': 'get_teams',
            'team_name': search_name
        })

        if data and len(data) > 0:
            team_data = data[0]
            team_id = int(team_data.get('team_key', 0))

            # 插入到teams表
            if team_id > 0:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO teams
                        (team_id, name_en, name_cn, country, team_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        team_id,
                        team_data.get('team_name', search_name),
                        team_name_cn,
                        team_data.get('team_country', ''),
                        'club'
                    ))
                    conn.commit()

                    # 更新映射表
                    cursor.execute("""
                        INSERT OR REPLACE INTO team_name_mapping
                        (lottery_name, team_id, match_confidence, match_method)
                        VALUES (?, ?, 1.0, 'api')
                    """, (team_name_cn, team_id))
                    conn.commit()

                    conn.close()
                    return team_id
                except Exception as e:
                    logger.error(f"Insert team error: {e}")

        conn.close()
        return None

    async def update_lottery_team_ids(self):
        """更新lottery_matches表中的team_id"""
        conn = self.get_db()
        cursor = conn.cursor()

        # 获取所有需要映射的球队
        cursor.execute("""
            SELECT DISTINCT home_team_cn FROM lottery_matches
            WHERE home_team_id IS NULL
        """)
        home_teams = [row['home_team_cn'] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT away_team_cn FROM lottery_matches
            WHERE away_team_id IS NULL
        """)
        away_teams = [row['away_team_cn'] for row in cursor.fetchall()]

        all_teams = list(set(home_teams + away_teams))

        print(f"需要映射的球队数量: {len(all_teams)}")

        # 映射每个球队
        for i, team_name in enumerate(all_teams):
            team_id = await self.find_team_id(team_name)
            if team_id:
                # 更新lottery_matches表
                cursor.execute("""
                    UPDATE lottery_matches
                    SET home_team_id = ?
                    WHERE home_team_cn = ?
                """, (team_id, team_name))

                cursor.execute("""
                    UPDATE lottery_matches
                    SET away_team_id = ?
                    WHERE away_team_cn = ?
                """, (team_id, team_name))

                conn.commit()
                print(f"[{i+1}/{len(all_teams)}] {team_name} -> team_id={team_id}")
            else:
                print(f"[{i+1}/{len(all_teams)}] {team_name} -> 未找到")

        conn.close()

    async def fetch_team_matches(self, team_id: int, days: int = 365) -> List[Dict]:
        """获取球队历史比赛"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        data = await self.api_request({
            'action': 'get_events',
            'team_id': team_id,
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d')
        })

        return data or []

    async def fetch_league_standings(self, league_id: int, season: str = '2025') -> Optional[List]:
        """获取联赛积分榜"""
        data = await self.api_request({
            'action': 'get_standings',
            'league_id': league_id,
            'season_id': season
        })

        return data

    async def fetch_h2h_matches(self, team1_id: int, team2_id: int) -> List[Dict]:
        """获取两队交锋历史"""
        data = await self.api_request({
            'action': 'get_H2H',
            'firstTeamId': team1_id,
            'secondTeamId': team2_id
        })

        return data or []

    def save_match_data(self, conn: sqlite3.Connection, matches: List[Dict]):
        """保存比赛数据"""
        cursor = conn.cursor()

        for match in matches:
            try:
                match_id = match.get('match_id', '')
                match_date = match.get('match_date', '')

                # 解析比分
                home_goals = int(match.get('match_hometeam_score', 0) or 0)
                away_goals = int(match.get('match_awayteam_score', 0) or 0)
                home_goals_ht = int(match.get('match_hometeam_halftime_score', 0) or 0)
                away_goals_ht = int(match.get('match_awayteam_halftime_score', 0) or 0)

                # 确定状态
                status = 'finished' if match.get('match_status') == 'FT' else match.get('match_status', 'scheduled')

                cursor.execute("""
                    INSERT OR REPLACE INTO matches
                    (match_id, match_date, match_time, home_team_id, away_team_id,
                     home_goals, away_goals, home_goals_ht, away_goals_ht,
                     status, league_id, season_id, competition_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id,
                    match_date,
                    match.get('match_time', ''),
                    match.get('home_team_key'),
                    match.get('away_team_key'),
                    home_goals,
                    away_goals,
                    home_goals_ht,
                    away_goals_ht,
                    status,
                    match.get('league_id'),
                    match.get('season_id', '2025'),
                    match.get('league_id')
                ))

            except Exception as e:
                logger.debug(f"Save match error: {e}")

        conn.commit()

    def save_standings_data(self, conn: sqlite3.Connection, standings: List[Dict], league_id: int):
        """保存积分榜数据"""
        cursor = conn.cursor()

        for standing in standings:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO standings
                    (league_id, season_id, team_id, position, played,
                     won, drawn, lost, goals_for, goals_against, goal_diff,
                     points, form, standing_type, home_played, home_won,
                     home_drawn, home_lost, home_goals_for, home_goals_against,
                     home_points, away_played, away_won, away_drawn, away_lost,
                     away_goals_for, away_goals_against, away_points, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    league_id,
                    '2025',
                    standing.get('team_id'),
                    standing.get('overall_league_position', 0),
                    standing.get('overall_league_payed', 0),
                    standing.get('overall_league_W', 0),
                    standing.get('overall_league_D', 0),
                    standing.get('overall_league_L', 0),
                    standing.get('overall_league_GF', 0),
                    standing.get('overall_league_GA', 0),
                    standing.get('overall_league_GD', 0),
                    standing.get('overall_league_PTS', 0),
                    standing.get('overall_league_form', ''),
                    'total',
                    standing.get('home_league_payed', 0),
                    standing.get('home_league_W', 0),
                    standing.get('home_league_D', 0),
                    standing.get('home_league_L', 0),
                    standing.get('home_league_GF', 0),
                    standing.get('home_league_GA', 0),
                    standing.get('home_league_PTS', 0),
                    standing.get('away_league_payed', 0),
                    standing.get('away_league_W', 0),
                    standing.get('away_league_D', 0),
                    standing.get('away_league_L', 0),
                    standing.get('away_league_GF', 0),
                    standing.get('away_league_GA', 0),
                    standing.get('away_league_PTS', 0),
                    datetime.now().isoformat()
                ))
            except Exception as e:
                logger.debug(f"Save standing error: {e}")

        conn.commit()

    async def supplement_all_data(self):
        """补充所有数据"""
        await self.init_session()
        conn = self.get_db()

        try:
            # 1. 更新球队ID映射
            print("=" * 60)
            print("Step 1: 更新球队ID映射")
            print("=" * 60)
            await self.update_lottery_team_ids()

            # 2. 获取联赛积分榜
            print("\n" + "=" * 60)
            print("Step 2: 获取联赛积分榜")
            print("=" * 60)

            for league_name, league_id in LEAGUE_MAPPING.items():
                print(f"\n获取 {league_name} (ID: {league_id}) 积分榜...")
                standings = await self.fetch_league_standings(league_id)
                if standings:
                    self.save_standings_data(conn, standings, league_id)
                    print(f"  保存 {len(standings)} 条积分榜记录")
                await asyncio.sleep(1)  # 避免API限制

            # 3. 获取球队历史比赛
            print("\n" + "=" * 60)
            print("Step 3: 获取球队历史比赛")
            print("=" * 60)

            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT home_team_id FROM lottery_matches
                WHERE home_team_id IS NOT NULL
                UNION
                SELECT DISTINCT away_team_id FROM lottery_matches
                WHERE away_team_id IS NOT NULL
            """)
            team_ids = [row[0] for row in cursor.fetchall()]

            total_matches = 0
            for i, team_id in enumerate(team_ids):
                print(f"\n[{i+1}/{len(team_ids)}] 获取team_id={team_id}的历史比赛...")
                matches = await self.fetch_team_matches(team_id)
                if matches:
                    self.save_match_data(conn, matches)
                    total_matches += len(matches)
                    print(f"  保存 {len(matches)} 场比赛")
                await asyncio.sleep(1)  # 避免API限制

            print(f"\n总计保存 {total_matches} 场历史比赛")

            # 4. 获取交锋历史
            print("\n" + "=" * 60)
            print("Step 4: 获取交锋历史")
            print("=" * 60)

            cursor.execute("""
                SELECT DISTINCT lm.home_team_id, lm.away_team_id,
                       t1.name_en as home_name, t2.name_en as away_name
                FROM lottery_matches lm
                LEFT JOIN teams t1 ON lm.home_team_id = t1.team_id
                LEFT JOIN teams t2 ON lm.away_team_id = t2.team_id
                WHERE lm.home_team_id IS NOT NULL AND lm.away_team_id IS NOT NULL
            """)

            h2h_pairs = cursor.fetchall()
            for i, pair in enumerate(h2h_pairs):
                print(f"\n[{i+1}/{len(h2h_pairs)}] 获取 {pair['home_name']} vs {pair['away_name']} 交锋历史...")
                h2h_matches = await self.fetch_h2h_matches(pair['home_team_id'], pair['away_team_id'])
                if h2h_matches:
                    self.save_match_data(conn, h2h_matches)
                    print(f"  保存 {len(h2h_matches)} 场交锋记录")
                await asyncio.sleep(1)  # 避免API限制

            print("\n" + "=" * 60)
            print("数据补充完成!")
            print("=" * 60)

        finally:
            conn.close()
            await self.close_session()


async def main():
    supplementer = DataSupplementer()
    await supplementer.supplement_all_data()


if __name__ == '__main__':
    asyncio.run(main())
