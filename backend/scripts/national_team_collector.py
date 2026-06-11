"""
国家队数据采集器 - 持久化存储
采集内容：
1. FIFA排名 → fifa_rankings表
2. 国家队H2H → h2h_records表
3. 国家队近期form → team_form表
4. 伤病停赛 → player_status表
5. 球队身价 → teams.squad_value
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')
FIFA_RANKING_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'fetchers', 'fifa_ranking', 'data', 'fifa_ranking_current.json')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NationalTeamCollector:
    """国家队数据采集器"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化需要的表"""
        conn = self._get_conn()
        c = conn.cursor()

        # H2H记录表
        c.execute('''
            CREATE TABLE IF NOT EXISTS h2h_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_a_id INTEGER NOT NULL,
                team_b_id INTEGER NOT NULL,
                team_a_name TEXT,
                team_b_name TEXT,
                match_date DATE,
                match_id TEXT,
                home_team TEXT,
                away_team TEXT,
                home_score INTEGER,
                away_score INTEGER,
                competition TEXT,
                source TEXT DEFAULT 'apifootball',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_a_id, team_b_id, match_date)
            )
        ''')

        # 球队近期form表
        c.execute('''
            CREATE TABLE IF NOT EXISTS team_form (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                team_name TEXT,
                match_date DATE,
                opponent TEXT,
                is_home INTEGER,
                goals_for INTEGER,
                goals_against INTEGER,
                result TEXT,
                competition TEXT,
                xg REAL,
                xga REAL,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, match_date, opponent)
            )
        ''')

        # 球员状态表（伤病/停赛）
        c.execute('''
            CREATE TABLE IF NOT EXISTS player_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                player_name TEXT NOT NULL,
                team_id INTEGER,
                team_name TEXT,
                status_type TEXT NOT NULL,
                status_reason TEXT,
                expected_return DATE,
                source TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_name, team_name, status_type)
            )
        ''')

        # 球队内部新闻（更衣室氛围、矛盾等）
        c.execute('''
            CREATE TABLE IF NOT EXISTS team_internal_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER,
                team_name TEXT,
                news_type TEXT NOT NULL,
                title TEXT,
                content TEXT,
                sentiment REAL DEFAULT 0,
                impact_level TEXT DEFAULT 'medium',
                source TEXT,
                url TEXT,
                published_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 阵容磨合度表
        c.execute('''
            CREATE TABLE IF NOT EXISTS team_chemistry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                team_name TEXT,
                match_date DATE,
                starting_xi TEXT,
                chemistry_score REAL,
                together_matches INTEGER,
                key_pairs_count INTEGER,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 点球记录表
        c.execute('''
            CREATE TABLE IF NOT EXISTS penalty_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT,
                team_id INTEGER,
                team_name TEXT,
                player_name TEXT,
                position INTEGER,
                result TEXT,
                goalkeeper_name TEXT,
                competition TEXT,
                match_date DATE,
                is_decisive INTEGER DEFAULT 0,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("数据库表初始化完成")

    # ==================== FIFA排名 ====================

    def import_fifa_rankings(self):
        """导入FIFA排名数据"""
        if not os.path.exists(FIFA_RANKING_PATH):
            logger.error(f"FIFA排名文件不存在: {FIFA_RANKING_PATH}")
            return 0

        with open(FIFA_RANKING_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conn = self._get_conn()
        c = conn.cursor()

        imported = 0
        rank_date = datetime.now().strftime('%Y-%m-%d')

        for team_name, info in data.items():
            # 查找或创建球队
            team_id = self._get_or_create_team(c, team_name, team_type='national')

            # 插入排名
            c.execute('''
                INSERT OR REPLACE INTO fifa_rankings
                (rank_date, team_id, rank, points, confederation)
                VALUES (?, ?, ?, ?, ?)
            ''', (rank_date, team_id, info.get('rank'), info.get('points'), info.get('confederation')))

            imported += 1

        conn.commit()
        conn.close()
        logger.info(f"导入FIFA排名: {imported}条")
        return imported

    # ==================== 球队管理 ====================

    def _get_or_create_team(self, cursor, team_name: str, team_type: str = 'national') -> int:
        """获取或创建球队ID"""
        cursor.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?', (team_name, team_name))
        row = cursor.fetchone()
        if row:
            return row[0]

        # 创建新球队
        cursor.execute('''
            INSERT INTO teams (name_en, team_type, country)
            VALUES (?, ?, ?)
        ''', (team_name, team_type, team_name))
        return cursor.lastrowid

    def update_team_value(self, team_name: str, value_eur: float):
        """更新球队身价"""
        conn = self._get_conn()
        c = conn.cursor()

        team_id = self._get_or_create_team(c, team_name)
        c.execute('''
            UPDATE teams SET squad_value = ? WHERE team_id = ?
        ''', (value_eur, team_id))

        conn.commit()
        conn.close()

    # ==================== H2H记录 ====================

    def save_h2h_records(self, team_a_id: str, team_b_id: str, matches: List[Dict]):
        """保存H2H记录"""
        conn = self._get_conn()
        c = conn.cursor()

        saved = 0
        for m in matches:
            try:
                c.execute('''
                    INSERT OR IGNORE INTO h2h_records
                    (team_a_id, team_b_id, team_a_name, team_b_name, match_date, match_id,
                     home_team, away_team, home_score, away_score, competition, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team_a_id, team_b_id,
                    m.get('home_team'), m.get('away_team'),
                    m.get('date'), m.get('match_id'),
                    m.get('home_team'), m.get('away_team'),
                    m.get('home_score'), m.get('away_score'),
                    m.get('league'), 'apifootball'
                ))
                saved += 1
            except Exception as e:
                logger.warning(f"保存H2H记录失败: {e}")

        conn.commit()
        conn.close()
        logger.info(f"保存H2H记录: {saved}条")
        return saved

    # ==================== Form数据 ====================

    def save_team_form(self, team_id: int, team_name: str, matches: List[Dict]):
        """保存球队近期form"""
        conn = self._get_conn()
        c = conn.cursor()

        saved = 0
        for m in matches:
            try:
                is_home = 1 if m.get('home_team') == team_name else 0
                goals_for = m.get('home_score') if is_home else m.get('away_score')
                goals_against = m.get('away_score') if is_home else m.get('home_score')

                result = 'D'
                if goals_for > goals_against:
                    result = 'W'
                elif goals_for < goals_against:
                    result = 'L'

                c.execute('''
                    INSERT OR IGNORE INTO team_form
                    (team_id, team_name, match_date, opponent, is_home, goals_for,
                     goals_against, result, competition, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team_id, team_name,
                    m.get('date'),
                    m.get('away_team') if is_home else m.get('home_team'),
                    is_home, goals_for, goals_against, result,
                    m.get('league'), 'apifootball'
                ))
                saved += 1
            except Exception as e:
                logger.warning(f"保存form失败: {e}")

        conn.commit()
        conn.close()
        logger.info(f"保存form数据: {team_name} {saved}场")
        return saved

    # ==================== 伤病停赛 ====================

    def save_player_status(self, player_name: str, team_name: str, status_type: str,
                           status_reason: str = None, expected_return: str = None, source: str = 'unknown'):
        """保存球员状态"""
        conn = self._get_conn()
        c = conn.cursor()

        team_id = self._get_or_create_team(c, team_name)

        c.execute('''
            INSERT OR REPLACE INTO player_status
            (player_name, team_id, team_name, status_type, status_reason, expected_return, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (player_name, team_id, team_name, status_type, status_reason, expected_return, source))

        conn.commit()
        conn.close()

    def save_injuries_from_apifootball(self, injuries: List[Dict]):
        """从apifootball保存伤病数据"""
        saved = 0
        for inj in injuries:
            try:
                self.save_player_status(
                    player_name=inj.get('player_name'),
                    team_name=inj.get('team_name'),
                    status_type='injury',
                    status_reason=inj.get('injury_type'),
                    expected_return=inj.get('return_date'),
                    source='apifootball'
                )
                saved += 1
            except Exception as e:
                logger.warning(f"保存伤病失败: {e}")

        logger.info(f"保存伤病数据: {saved}条")
        return saved

    # ==================== 内部新闻 ====================

    def save_internal_news(self, team_name: str, news_type: str, title: str, content: str,
                           sentiment: float = 0, impact_level: str = 'medium',
                           source: str = None, url: str = None, published_at: str = None):
        """保存球队内部新闻"""
        conn = self._get_conn()
        c = conn.cursor()

        team_id = self._get_or_create_team(c, team_name)

        c.execute('''
            INSERT INTO team_internal_news
            (team_id, team_name, news_type, title, content, sentiment, impact_level, source, url, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (team_id, team_name, news_type, title, content, sentiment, impact_level, source, url, published_at))

        conn.commit()
        conn.close()

    # ==================== 阵容磨合度 ====================

    def calculate_chemistry(self, team_id: int, starting_xi: List[str], match_date: str) -> float:
        """计算阵容磨合度"""
        conn = self._get_conn()
        c = conn.cursor()

        # 查询这11人一起首发过几次
        placeholders = ','.join(['?' for _ in starting_xi])
        c.execute(f'''
            SELECT COUNT(DISTINCT match_id)
            FROM match_lineups
            WHERE player_name IN ({placeholders})
            AND match_date < ?
            GROUP BY match_id
            HAVING COUNT(DISTINCT player_name) >= 8
        ''', starting_xi + [match_date])

        together_matches = len(c.fetchall())

        # 计算两两配合次数
        pairs_count = 0
        for i in range(len(starting_xi)):
            for j in range(i+1, len(starting_xi)):
                c.execute('''
                    SELECT COUNT(*) FROM match_lineups ml1
                    JOIN match_lineups ml2 ON ml1.match_id = ml2.match_id
                    WHERE ml1.player_name = ? AND ml2.player_name = ?
                ''', (starting_xi[i], starting_xi[j]))
                if c.fetchone()[0] >= 5:
                    pairs_count += 1

        total_pairs = len(starting_xi) * (len(starting_xi) - 1) / 2
        chemistry_score = pairs_count / total_pairs if total_pairs > 0 else 0

        conn.close()
        return chemistry_score

    # ==================== 综合采集 ====================

    def collect_national_team_data(self, team_name: str, team_id_apifootball: str = None):
        """采集单个国家队的完整数据"""
        from fetchers.apifootball.get_data import get_h2h, get_teams

        conn = self._get_conn()
        c = conn.cursor()
        team_id = self._get_or_create_team(c, team_name)
        conn.close()

        logger.info(f"采集国家队数据: {team_name} (ID: {team_id})")

        # TODO: 调用apifootball获取H2H、form等数据
        # 需要team_id_apifootball

        return team_id

    def collect_world_cup_teams(self):
        """采集所有世界杯参赛队数据"""
        # 2026世界杯参赛队（已确认的）
        wc_teams = [
            'Argentina', 'Brazil', 'France', 'England', 'Spain', 'Germany',
            'Netherlands', 'Portugal', 'Belgium', 'Croatia', 'Uruguay', 'Colombia',
            'Mexico', 'USA', 'Canada', 'Japan', 'South Korea', 'Australia',
            'Iran', 'Saudi Arabia', 'Qatar', 'Morocco', 'Senegal', 'Ghana',
            'Cameroon', 'Nigeria', 'Tunisia', 'Egypt', 'Algeria', 'South Africa'
        ]

        for team in wc_teams:
            self.collect_national_team_data(team)
            time.sleep(0.5)

        logger.info(f"世界杯参赛队数据采集完成: {len(wc_teams)}队")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='国家队数据采集器')
    parser.add_argument('--fifa', action='store_true', help='导入FIFA排名')
    parser.add_argument('--team', type=str, help='采集单个国家队')
    parser.add_argument('--world-cup', action='store_true', help='采集世界杯参赛队')

    args = parser.parse_args()

    collector = NationalTeamCollector()

    if args.fifa:
        collector.import_fifa_rankings()

    if args.team:
        collector.collect_national_team_data(args.team)

    if args.world_cup:
        collector.collect_world_cup_teams()

    if not any([args.fifa, args.team, args.world_cup]):
        # 默认执行所有
        print("国家队数据采集器")
        print("用法:")
        print("  python national_team_collector.py --fifa          # 导入FIFA排名")
        print("  python national_team_collector.py --team Brazil   # 采集单个队")
        print("  python national_team_collector.py --world-cup     # 采集世界杯参赛队")
