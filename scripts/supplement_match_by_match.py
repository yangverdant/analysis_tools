"""
按比赛逐场补充数据

流程：
1. 遍历每场比赛
2. 对每场比赛：
   - 映射球队ID
   - 获取球队历史比赛
   - 获取联赛积分榜
   - 获取两队交锋历史
3. 完成后继续下一场
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    '鹿岛鹿角': 'Kashima Antlers',
    '川崎前锋': 'Kawasaki Frontale',
    '浦和红钻': 'Urawa Red Diamonds',
    '横滨水手': 'Yokohama F. Marinos',
    '名古屋鲸': 'Nagoya Grampus',
    '柏太阳神': 'Kashiwa Reysol',
    '广岛三箭': 'Sanfrecce Hiroshima',
    '东京FC': 'FC Tokyo',
    '大阪樱花': 'Cerezo Osaka',

    # 英甲
    '博尔顿': 'Bolton',
    '斯托克港': 'Stockport County',
    '维冈竞技': 'Wigan Athletic',
    '巴恩斯利': 'Barnsley',
    '查尔顿': 'Charlton Athletic',

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
    '尤尔加登': 'Djurgardens',

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
    '尤文图斯': 'Juventus',
    '克雷莫纳': 'Cremonese',
    '科莫': 'Como',
    'AC米兰': 'Milan',
    '米兰': 'Milan',
    '卡利亚里': 'Cagliari',
    '博洛尼亚': 'Bologna',
    '佛罗伦萨': 'Fiorentina',
    '亚特兰大': 'Atalanta',
    '拉齐奥': 'Lazio',
    '国际米兰': 'Inter',
    '国米': 'Inter',

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
    '纽卡斯尔联': 'Newcastle',
    '利物浦': 'Liverpool',
    '布伦特': 'Brentford',
    '布伦特福德': 'Brentford',
    '曼城': 'Manchester City',
    '维拉': 'Aston Villa',
    '阿斯顿维拉': 'Aston Villa',
    '桑德兰': 'Sunderland',
    '切尔西': 'Chelsea',
    '伯恩利': 'Burnley',
    '狼队': 'Wolves',
    '水晶宫': 'Crystal Palace',
    '阿森纳': 'Arsenal',
    '西汉姆': 'West Ham',
    '西汉姆联': 'West Ham',
    '利兹联': 'Leeds',
    '热刺': 'Tottenham',
    '埃弗顿': 'Everton',
    '诺丁汉森林': "Nottm Forest",
    '伯恩茅斯': 'Bournemouth',
    '布莱顿': 'Brighton',
    '南安普顿': 'Southampton',
    '莱斯特城': 'Leicester',
    '伊普斯维奇': 'Ipswich',

    # 西甲
    '比利亚雷': 'Villarreal',
    '比利亚雷亚尔': 'Villarreal',
    '马竞': 'Atletico Madrid',
    '马德里竞技': 'Atletico Madrid',
    '皇马': 'Real Madrid',
    '皇家马德里': 'Real Madrid',
    '巴萨': 'Barcelona',
    '巴塞罗那': 'Barcelona',
    '塞维利亚': 'Sevilla',
    '皇家社会': 'Real Sociedad',
    '贝蒂斯': 'Real Betis',
    '瓦伦西亚': 'Valencia',
    '毕尔巴鄂': 'Athletic Bilbao',

    # 美职
    '迈阿密国际': 'Inter Miami',
    '费城联合': 'Philadelphia Union',
    '洛杉矶FC': 'LAFC',
    '西雅图海湾人': 'Seattle Sounders',
    '洛杉矶银河': 'LA Galaxy',
    '纽约红牛': 'New York Red Bulls',

    # 德甲
    '帕德博恩': 'Paderborn',
    '沃尔夫斯堡': 'Wolfsburg',
    '拜仁': 'Bayern Munich',
    '拜仁慕尼黑': 'Bayern Munich',
    '多特': 'Dortmund',
    '多特蒙德': 'Dortmund',
    '莱比锡': 'RB Leipzig',
    '勒沃库森': 'Leverkusen',
    '法兰克福': 'Eintracht Frankfurt',
    '斯图加特': 'Stuttgart',
    '门兴': 'Monchengladbach',
    '霍芬海姆': 'Hoffenheim',
    '弗赖堡': 'Freiburg',
}


class MatchByMatchSupplementer:
    """按比赛逐场补充数据"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_leagues = set()  # 已处理的联赛（避免重复获取积分榜）

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

    async def find_team_id(self, team_name_cn: str, cursor) -> Optional[int]:
        """查找球队ID"""
        # 1. 直接查询teams表
        cursor.execute("""
            SELECT team_id FROM teams
            WHERE name_cn = ? OR name_en = ? OR name_en LIKE ?
        """, (team_name_cn, team_name_cn, f'%{team_name_cn}%'))

        row = cursor.fetchone()
        if row:
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
                return row['team_id']

            # 3. 从API查询
            logger.info(f"Searching team from API: {team_name_cn}")
            data = await self.api_request({
                'action': 'get_teams',
                'team_name': eng_name
            })

            if data and len(data) > 0:
                team_data = data[0]
                team_id = int(team_data.get('team_key', 0))

                if team_id > 0:
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO teams
                            (team_id, name_en, name_cn, country, team_type)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            team_id,
                            team_data.get('team_name', eng_name),
                            team_name_cn,
                            team_data.get('team_country', ''),
                            'club'
                        ))

                        cursor.execute("""
                            INSERT OR REPLACE INTO team_name_mapping
                            (lottery_name, team_id, match_confidence, match_method)
                            VALUES (?, ?, 1.0, 'api')
                        """, (team_name_cn, team_id))

                        return team_id
                    except Exception as e:
                        logger.error(f"Insert team error: {e}")

        return None

    async def fetch_team_matches(self, team_id: int, team_name: str) -> int:
        """获取球队历史比赛，返回新增数量"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        data = await self.api_request({
            'action': 'get_events',
            'team_id': team_id,
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d')
        })

        if not data:
            return 0

        conn = self.get_db()
        cursor = conn.cursor()
        saved = 0

        for match in data:
            try:
                match_id = match.get('match_id', '')

                # 检查是否已存在
                cursor.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
                if cursor.fetchone():
                    continue

                home_goals = int(match.get('match_hometeam_score', 0) or 0)
                away_goals = int(match.get('match_awayteam_score', 0) or 0)
                home_goals_ht = int(match.get('match_hometeam_halftime_score', 0) or 0)
                away_goals_ht = int(match.get('match_awayteam_halftime_score', 0) or 0)

                status = 'finished' if match.get('match_status') == 'FT' else match.get('match_status', 'scheduled')

                cursor.execute("""
                    INSERT OR REPLACE INTO matches
                    (match_id, match_date, match_time, home_team_id, away_team_id,
                     home_goals, away_goals, home_goals_ht, away_goals_ht,
                     status, league_id, season_id, competition_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id,
                    match.get('match_date', ''),
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
                saved += 1

            except Exception as e:
                logger.debug(f"Save match error: {e}")

        conn.commit()
        conn.close()
        return saved

    async def fetch_league_standings(self, league_id: int, league_name: str) -> int:
        """获取联赛积分榜，返回球队数量"""
        data = await self.api_request({
            'action': 'get_standings',
            'league_id': league_id,
            'season_id': '2025'
        })

        if not data:
            return 0

        conn = self.get_db()
        cursor = conn.cursor()
        saved = 0

        for standing in data:
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
                saved += 1
            except Exception as e:
                logger.debug(f"Save standing error: {e}")

        conn.commit()
        conn.close()
        return saved

    async def fetch_h2h_matches(self, team1_id: int, team2_id: int) -> int:
        """获取两队交锋历史"""
        data = await self.api_request({
            'action': 'get_H2H',
            'firstTeamId': team1_id,
            'secondTeamId': team2_id
        })

        if not data:
            return 0

        conn = self.get_db()
        cursor = conn.cursor()
        saved = 0

        for match in data:
            try:
                match_id = match.get('match_id', '')

                # 检查是否已存在
                cursor.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
                if cursor.fetchone():
                    continue

                home_goals = int(match.get('match_hometeam_score', 0) or 0)
                away_goals = int(match.get('match_awayteam_score', 0) or 0)

                cursor.execute("""
                    INSERT OR REPLACE INTO matches
                    (match_id, match_date, match_time, home_team_id, away_team_id,
                     home_goals, away_goals, status, league_id, season_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'finished', ?, ?)
                """, (
                    match_id,
                    match.get('match_date', ''),
                    match.get('match_time', ''),
                    match.get('home_team_key'),
                    match.get('away_team_key'),
                    home_goals,
                    away_goals,
                    match.get('league_id'),
                    match.get('season_id', '2024')
                ))
                saved += 1

            except Exception as e:
                logger.debug(f"Save H2H match error: {e}")

        conn.commit()
        conn.close()
        return saved

    async def process_single_match(self, match: Dict, index: int, total: int):
        """处理单场比赛的所有数据"""
        lottery_match_id = match['lottery_match_id']
        home_team_cn = match['home_team_cn']
        away_team_cn = match['away_team_cn']
        league_name_cn = match['league_name_cn']

        print(f"\n{'='*70}")
        print(f"[{index}/{total}] 处理比赛: {lottery_match_id}")
        print(f"  {home_team_cn} vs {away_team_cn} ({league_name_cn})")
        print(f"{'='*70}")

        conn = self.get_db()
        cursor = conn.cursor()

        try:
            # Step 1: 映射球队ID
            print(f"\n  [Step 1] 映射球队ID...")

            home_team_id = await self.find_team_id(home_team_cn, cursor)
            away_team_id = await self.find_team_id(away_team_cn, cursor)

            if home_team_id:
                print(f"    [OK] 主队 {home_team_cn} -> team_id={home_team_id}")
                cursor.execute("""
                    UPDATE lottery_matches SET home_team_id = ? WHERE lottery_match_id = ?
                """, (home_team_id, lottery_match_id))
            else:
                print(f"    [MISS] 主队 {home_team_cn} -> 未找到")

            if away_team_id:
                print(f"    [OK] 客队 {away_team_cn} -> team_id={away_team_id}")
                cursor.execute("""
                    UPDATE lottery_matches SET away_team_id = ? WHERE lottery_match_id = ?
                """, (away_team_id, lottery_match_id))
            else:
                print(f"    [MISS] 客队 {away_team_cn} -> 未找到")

            conn.commit()

            # Step 2: 获取联赛积分榜（每个联赛只获取一次）
            league_id = LEAGUE_MAPPING.get(league_name_cn)
            if league_id and league_id not in self.processed_leagues:
                print(f"\n  [Step 2] 获取 {league_name_cn} 积分榜...")
                standings_count = await self.fetch_league_standings(league_id, league_name_cn)
                print(f"    [OK] 保存 {standings_count} 条积分榜记录")
                self.processed_leagues.add(league_id)
                await asyncio.sleep(1)
            elif league_id:
                print(f"\n  [Step 2] {league_name_cn} 积分榜已获取，跳过")
            else:
                print(f"\n  [Step 2] 未知联赛: {league_name_cn}，跳过")

            # Step 3: 获取主队历史比赛
            if home_team_id:
                print(f"\n  [Step 3] 获取 {home_team_cn} 历史比赛...")
                home_matches = await self.fetch_team_matches(home_team_id, home_team_cn)
                print(f"    [OK] 新增 {home_matches} 场历史比赛")
                await asyncio.sleep(1)

            # Step 4: 获取客队历史比赛
            if away_team_id:
                print(f"\n  [Step 4] 获取 {away_team_cn} 历史比赛...")
                away_matches = await self.fetch_team_matches(away_team_id, away_team_cn)
                print(f"    [OK] 新增 {away_matches} 场历史比赛")
                await asyncio.sleep(1)

            # Step 5: 获取交锋历史
            if home_team_id and away_team_id:
                print(f"\n  [Step 5] 获取交锋历史...")
                h2h_count = await self.fetch_h2h_matches(home_team_id, away_team_id)
                print(f"    [OK] 新增 {h2h_count} 场交锋记录")
                await asyncio.sleep(1)

            print(f"\n  ** 比赛处理完成: {lottery_match_id}")

        except Exception as e:
            logger.error(f"处理比赛失败 {lottery_match_id}: {e}")
            print(f"  [ERROR] 处理失败: {e}")
        finally:
            conn.close()

    async def supplement_all_matches(self):
        """逐场补充所有比赛数据"""
        await self.init_session()
        conn = self.get_db()
        cursor = conn.cursor()

        try:
            # 获取所有待处理的比赛
            cursor.execute("""
                SELECT lottery_match_id, home_team_cn, away_team_cn, league_name_cn
                FROM lottery_matches
                ORDER BY match_date ASC, lottery_match_id ASC
            """)

            matches = [dict(row) for row in cursor.fetchall()]
            total = len(matches)

            print(f"\n共 {total} 场比赛待处理")
            print("=" * 70)

            for i, match in enumerate(matches, 1):
                await self.process_single_match(match, i, total)

            print("\n" + "=" * 70)
            print("所有比赛数据处理完成!")
            print("=" * 70)

        finally:
            conn.close()
            await self.close_session()


async def main():
    supplementer = MatchByMatchSupplementer()
    await supplementer.supplement_all_matches()


if __name__ == '__main__':
    asyncio.run(main())
