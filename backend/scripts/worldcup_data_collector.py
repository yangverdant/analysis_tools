"""
世界杯数据采集器 - 完整版
对接apifootball API，持久化存储所有世界杯相关数据
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
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')

# API配置
API_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
BASE_URL = "https://apiv3.apifootball.com"
WORLD_CUP_LEAGUE_ID = 28  # 世界杯


class WorldCupDataCollector:
    """世界杯数据采集器"""

    def __init__(self):
        self.db_path = DB_PATH
        self.session = requests.Session()
        self.session.trust_env = False
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """确保表存在"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        # 确保基础表存在
        tables = [
            '''CREATE TABLE IF NOT EXISTS h2h_records (
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
            )''',
            '''CREATE TABLE IF NOT EXISTS team_form (
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
            )''',
            '''CREATE TABLE IF NOT EXISTS player_status (
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
            )''',
            '''CREATE TABLE IF NOT EXISTS apifootball_teams (
                apifootball_id INTEGER PRIMARY KEY,
                team_name TEXT NOT NULL,
                team_name_cn TEXT,
                country TEXT,
                country_code TEXT,
                is_national INTEGER DEFAULT 0,
                logo_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS wc_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT,
                home_team TEXT,
                away_team TEXT,
                match_date DATE,
                home_win_prob REAL,
                draw_prob REAL,
                away_win_prob REAL,
                over_2_5_prob REAL,
                btts_prob REAL,
                source TEXT DEFAULT 'apifootball',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(match_id)
            )'''
        ]

        for sql in tables:
            c.execute(sql)

        conn.commit()
        conn.close()

    # ==================== API调用 ====================

    def _request(self, action: str, params: Dict = None) -> Optional[List]:
        """发送API请求"""
        query = {"action": action, "APIkey": API_KEY}
        if params:
            query.update(params)

        try:
            resp = self.session.get(BASE_URL, params=query, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and data.get('errors'):
                    logger.error(f"API错误: {data['errors']}")
                return data
        except Exception as e:
            logger.error(f"API请求失败 [{action}]: {e}")
        return None

    def get_world_cup_matches(self, season: str = "2026") -> List[Dict]:
        """获取世界杯比赛"""
        data = self._request("get_events", {"league_id": WORLD_CUP_LEAGUE_ID, "season": season})
        return data if data else []

    def get_team_matches(self, team_id: int, from_date: str = None, to_date: str = None) -> List[Dict]:
        """获取球队比赛历史"""
        params = {"team_id": team_id}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        data = self._request("get_events", params)
        return data if data else []

    def get_h2h(self, team1_id: int, team2_id: int) -> List[Dict]:
        """获取两队交锋记录"""
        data = self._request("get_H2H", {"firstTeamId": team1_id, "secondTeamId": team2_id})

        # API返回dict格式，包含firstTeam_VS_secondTeam字段
        if isinstance(data, dict):
            vs_matches = data.get('firstTeam_VS_secondTeam', [])
            return vs_matches if isinstance(vs_matches, list) else []
        elif isinstance(data, list):
            return data
        return []

    def get_predictions(self, match_id: str) -> Dict:
        """获取比赛预测"""
        data = self._request("get_predictions", {"match_id": match_id})
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, dict):
            return data
        return {}

    def get_team_info(self, team_id: int) -> Dict:
        """获取球队信息"""
        data = self._request("get_teams", {"team_id": team_id})
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        return {}

    # ==================== 数据持久化 ====================

    def _get_or_create_team_id(self, team_name: str) -> int:
        """获取或创建球队ID"""
        conn = self._get_conn()
        c = conn.cursor()

        try:
            c.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?', (team_name, team_name))
            row = c.fetchone()

            if row:
                conn.close()
                return row[0]

            # 创建新球队
            c.execute('''
                INSERT INTO teams (name_en, team_type, country)
                VALUES (?, 'national', ?)
            ''', (team_name, team_name))

            team_id = c.lastrowid
            conn.commit()
            conn.close()
            return team_id
        except Exception as e:
            conn.close()
            # 如果创建失败，尝试再次查询
            conn2 = self._get_conn()
            c2 = conn2.cursor()
            c2.execute('SELECT team_id FROM teams WHERE name_en = ?', (team_name,))
            row = c2.fetchone()
            conn2.close()
            if row:
                return row[0]
            raise e

    def save_h2h_records(self, team1_name: str, team2_name: str, team1_api_id: int, team2_api_id: int):
        """保存H2H记录"""
        h2h_matches = self.get_h2h(team1_api_id, team2_api_id)

        if not h2h_matches:
            logger.warning(f"未获取到H2H: {team1_name} vs {team2_name}")
            return 0

        conn = self._get_conn()
        c = conn.cursor()

        team1_id = self._get_or_create_team_id(team1_name)
        team2_id = self._get_or_create_team_id(team2_name)

        saved = 0
        for m in h2h_matches:
            try:
                home_score = int(m.get("match_hometeam_score", 0) or 0)
                away_score = int(m.get("match_awayteam_score", 0) or 0)

                c.execute('''
                    INSERT OR IGNORE INTO h2h_records
                    (team_a_id, team_b_id, team_a_name, team_b_name, match_date,
                     match_id, home_team, away_team, home_score, away_score, competition)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team1_id, team2_id, team1_name, team2_name,
                    m.get("match_date"),
                    m.get("match_id"),
                    m.get("match_hometeam_name"),
                    m.get("match_awayteam_name"),
                    home_score, away_score,
                    m.get("league_name")
                ))
                saved += 1
            except Exception as e:
                logger.warning(f"保存H2H失败: {e}")

        conn.commit()
        conn.close()
        logger.info(f"H2H保存: {team1_name} vs {team2_name} - {saved}场")
        return saved

    def save_team_form(self, team_name: str, team_api_id: int, days: int = 365):
        """保存球队近期form"""
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')

        matches = self.get_team_matches(team_api_id, from_date, to_date)

        if not matches:
            logger.warning(f"未获取到form数据: {team_name}")
            return 0

        conn = self._get_conn()
        c = conn.cursor()

        team_id = self._get_or_create_team_id(team_name)

        saved = 0
        for m in matches:
            try:
                home_team = m.get("match_hometeam_name")
                away_team = m.get("match_awayteam_name")
                home_score = int(m.get("match_hometeam_score", 0) or 0)
                away_score = int(m.get("match_awayteam_score", 0) or 0)

                is_home = 1 if home_team == team_name else 0
                goals_for = home_score if is_home else away_score
                goals_against = away_score if is_home else home_score
                opponent = away_team if is_home else home_team

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
                    team_id, team_name, m.get("match_date"), opponent, is_home,
                    goals_for, goals_against, result, m.get("league_name"), 'apifootball'
                ))
                saved += 1
            except Exception as e:
                logger.warning(f"保存form失败: {e}")

        conn.commit()
        conn.close()
        logger.info(f"Form保存: {team_name} - {saved}场")
        return saved

    def save_predictions(self, match_id: str, home_team: str, away_team: str, match_date: str):
        """保存比赛预测"""
        pred = self.get_predictions(match_id)

        if not pred:
            return None

        conn = self._get_conn()
        c = conn.cursor()

        c.execute('''
            INSERT OR REPLACE INTO wc_predictions
            (match_id, home_team, away_team, match_date, home_win_prob, draw_prob,
             away_win_prob, over_2_5_prob, btts_prob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match_id, home_team, away_team, match_date,
            float(pred.get("prob_HW", 0) or 0),
            float(pred.get("prob_D", 0) or 0),
            float(pred.get("prob_AW", 0) or 0),
            float(pred.get("prob_O", 0) or 0),
            float(pred.get("prob_bts", 0) or 0)
        ))

        conn.commit()
        conn.close()
        logger.info(f"预测保存: {home_team} vs {away_team}")
        return pred

    # ==================== 国家队ID映射 ====================

    def build_team_id_mapping(self):
        """构建国家队apifootball ID映射"""
        # 手动映射主要国家队（apifootball的team_id）
        national_teams = {
            "Argentina": 44,
            "Brazil": 54,
            "France": 18,
            "England": 10,
            "Spain": 9,
            "Germany": 27,
            "Netherlands": 36,
            "Portugal": 39,
            "Belgium": 24,
            "Croatia": 52,
            "Uruguay": 53,
            "Colombia": 46,
            "Mexico": 61,
            "USA": 78,
            "Canada": 79,
            "Japan": 74,
            "South Korea": 71,
            "Australia": 75,
            "Iran": 76,
            "Saudi Arabia": 80,
            "Morocco": 62,
            "Senegal": 63,
            "Ghana": 65,
            "Nigeria": 64,
            "Egypt": 66,
            "Algeria": 67,
            "Tunisia": 68,
            "Cameroon": 69,
            "Italy": 16,
            "Switzerland": 42,
            "Denmark": 30,
            "Sweden": 38,
            "Norway": 41,
            "Poland": 33,
            "Austria": 23,
            "Hungary": 47,
            "Turkey": 48,
            "Russia": 51,
            "Ukraine": 49,
            "Serbia": 50,
            "Chile": 45,
            "Peru": 55,
            "Ecuador": 56,
            "Venezuela": 57,
            "Paraguay": 58,
            "Bolivia": 59,
            "Costa Rica": 82,
            "Panama": 83,
            "Honduras": 84,
            "Jamaica": 85,
            "Trinidad": 86,
            "New Zealand": 77,
            "Ireland": 11,
            "Scotland": 12,
            "Wales": 14,
            "Northern Ireland": 13,
            "Czech Republic": 31,
            "Slovakia": 32,
            "Romania": 34,
            "Bulgaria": 35,
            "Greece": 40,
            "Finland": 43,
            "Iceland": 37,
            "Bosnia": 569,
            "Montenegro": 570,
            "Albania": 571,
            "North Macedonia": 572,
            "Israel": 573,
            "Cyprus": 574,
            "Luxembourg": 575,
            "Malta": 576,
            "Andorra": 577,
            "San Marino": 578,
            "Faroe Islands": 579,
            "Gibraltar": 580,
            "Kosovo": 581,
            "Armenia": 582,
            "Azerbaijan": 583,
            "Georgia": 584,
            "Belarus": 585,
            "Moldova": 586,
            "Latvia": 587,
            "Lithuania": 588,
            "Estonia": 589,
            "Kazakhstan": 590,
            "Uzbekistan": 591,
            "Tajikistan": 592,
            "Kyrgyzstan": 593,
            "Turkmenistan": 594,
            "Afghanistan": 595,
            "Myanmar": 596,
            "Vietnam": 597,
            "Thailand": 598,
            "Malaysia": 599,
            "Indonesia": 600,
            "Philippines": 601,
            "Singapore": 602,
            "Cambodia": 603,
            "Laos": 604,
            "Brunei": 605,
            "Timor-Leste": 606,
            "China": 607,
            "Hong Kong": 608,
            "Macau": 609,
            "Taiwan": 610,
            "North Korea": 611,
            "Mongolia": 612,
            "India": 613,
            "Pakistan": 614,
            "Bangladesh": 615,
            "Sri Lanka": 616,
            "Nepal": 617,
            "Bhutan": 618,
            "Maldives": 619,
            "Iraq": 620,
            "Syria": 621,
            "Jordan": 622,
            "Lebanon": 623,
            "Palestine": 624,
            "Oman": 625,
            "UAE": 626,
            "Qatar": 627,
            "Bahrain": 628,
            "Kuwait": 629,
            "Yemen": 630,
            "South Africa": 70,
            "Zimbabwe": 631,
            "Kenya": 632,
            "Tanzania": 633,
            "Uganda": 634,
            "Ethiopia": 635,
            "Sudan": 636,
            "Congo": 637,
            "DR Congo": 638,
            "Angola": 639,
            "Mali": 640,
            "Burkina Faso": 641,
            "Niger": 642,
            "Guinea": 643,
            "Benin": 644,
            "Togo": 645,
            "Sierra Leone": 646,
            "Liberia": 647,
            "Cote d'Ivoire": 648,
            "Mauritania": 649,
            "Cape Verde": 650,
            "Guinea-Bissau": 651,
            "Equatorial Guinea": 652,
            "Gabon": 653,
            "Republic of Congo": 654,
            "Central African Republic": 655,
            "Chad": 656,
            "Burundi": 657,
            "Rwanda": 658,
            "Malawi": 659,
            "Mozambique": 660,
            "Madagascar": 661,
            "Comoros": 662,
            "Mauritius": 663,
            "Seychelles": 664,
            "Namibia": 665,
            "Botswana": 666,
            "Lesotho": 667,
            "Swaziland": 668,
            "Somalia": 669,
            "Djibouti": 670,
            "Eritrea": 671,
            "South Sudan": 672,
            "Libya": 673,
            "Tunisia": 674,
            "Western Sahara": 675,
            "Sao Tome": 676,
            "Gambia": 677,
            "Senegal": 678,
        }

        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        for team_name, api_id in national_teams.items():
            c.execute('''
                INSERT OR REPLACE INTO apifootball_teams
                (apifootball_id, team_name, is_national)
                VALUES (?, ?, 1)
            ''', (api_id, team_name))

            # 查找或创建球队
            c.execute('SELECT team_id FROM teams WHERE name_en = ? OR name_cn = ?', (team_name, team_name))
            row = c.fetchone()

            if row:
                team_id = row[0]
            else:
                c.execute('''
                    INSERT INTO teams (name_en, team_type, country)
                    VALUES (?, 'national', ?)
                ''', (team_name, team_name))
                team_id = c.lastrowid

            # 更新teams表
            c.execute('''
                UPDATE teams SET
                    sm_team_id = ?,
                    team_type = 'national'
                WHERE team_id = ?
            ''', (api_id, team_id))

        conn.commit()
        conn.close()
        logger.info(f"国家队ID映射: {len(national_teams)}队")

    # ==================== 批量采集 ====================

    def collect_all_wc_teams(self):
        """采集所有世界杯参赛队数据"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute('SELECT name_en, sm_team_id FROM teams WHERE team_type = "national" AND sm_team_id IS NOT NULL')
        teams = c.fetchall()
        conn.close()

        logger.info(f"开始采集 {len(teams)} 个国家队数据...")

        for team_name, api_id in teams:
            if api_id:
                # 采集form
                self.save_team_form(team_name, api_id, days=365)
                time.sleep(1)  # 避免API限流

        logger.info("国家队form数据采集完成")

    def collect_wc_h2h_matrix(self):
        """采集世界杯参赛队之间的H2H矩阵"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute('SELECT name_en, sm_team_id FROM teams WHERE team_type = "national" AND sm_team_id IS NOT NULL')
        teams = c.fetchall()
        conn.close()

        # 只采集主要强队之间的H2H
        top_teams = [t for t in teams if t[0] in [
            'Argentina', 'Brazil', 'France', 'England', 'Spain', 'Germany',
            'Netherlands', 'Portugal', 'Belgium', 'Croatia', 'Uruguay', 'Colombia',
            'Mexico', 'USA', 'Japan', 'South Korea', 'Australia', 'Morocco'
        ]]

        logger.info(f"采集 {len(top_teams)} 强队H2H矩阵...")

        for i, (team1, id1) in enumerate(top_teams):
            for team2, id2 in top_teams[i+1:]:
                if id1 and id2:
                    self.save_h2h_records(team1, team2, id1, id2)
                    time.sleep(1)

        logger.info("H2H矩阵采集完成")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='世界杯数据采集')
    parser.add_argument('--mapping', action='store_true', help='构建国家队ID映射')
    parser.add_argument('--form', action='store_true', help='采集所有国家队form')
    parser.add_argument('--h2h', action='store_true', help='采集H2H矩阵')
    parser.add_argument('--team', type=str, help='采集单个国家队')

    args = parser.parse_args()

    collector = WorldCupDataCollector()

    if args.mapping:
        collector.build_team_id_mapping()

    if args.form:
        collector.collect_all_wc_teams()

    if args.h2h:
        collector.collect_wc_h2h_matrix()

    if args.team:
        # 采集单个队
        conn = collector._get_conn()
        c = conn.cursor()
        c.execute('SELECT sm_team_id FROM teams WHERE name_en = ? AND team_type = "national"', (args.team,))
        row = c.fetchone()
        conn.close()

        if row and row[0]:
            collector.save_team_form(args.team, row[0])
        else:
            print(f"未找到国家队: {args.team}")

    if not any([args.mapping, args.form, args.h2h, args.team]):
        print("世界杯数据采集器")
        print("用法:")
        print("  python worldcup_data_collector.py --mapping    # 构建ID映射")
        print("  python worldcup_data_collector.py --form       # 采集form数据")
        print("  python worldcup_data_collector.py --h2h        # 采集H2H矩阵")
        print("  python worldcup_data_collector.py --team Brazil # 采集单个队")