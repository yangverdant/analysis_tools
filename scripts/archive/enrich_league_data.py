"""
联赛数据补充脚本
从外部API获取完整的联赛信息，补充到数据库
"""

import os
import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Optional


class LeagueDataEnricher:
    """联赛数据补充器"""

    def __init__(self, db_path: str = None):
        if db_path:
            self.db_path = db_path
        else:
            # 直接使用当前目录下的data文件夹
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(current_dir, 'data', 'football_v2.db')

        self.session = requests.Session()
        self.session.trust_env = False

        # 加载API配置
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """加载API配置"""
        config_path = os.path.join(
            os.path.dirname(self.db_path), '..', 'api_config.json'
        )
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _get_db(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def enrich_from_football_data(self) -> Dict:
        """
        从football-data.org获取联赛信息
        该API提供完整的欧洲联赛数据
        """
        api_key = self.config.get('football_data_org', {}).get(
            'api_key', '944e431594bf477fa85d24fa04d9c2fe'
        )

        url = "https://api.football-data.org/v4/competitions"
        headers = {"X-Auth-Token": api_key}

        try:
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return {"success": False, "error": f"API返回 {response.status_code}"}

            data = response.json()
            competitions = data.get('competitions', [])

            conn = self._get_db()
            cursor = conn.cursor()

            updated = 0
            added = 0

            for comp in competitions:
                comp_code = comp.get('code', '')
                name = comp.get('name', '')
                area = comp.get('area', {})
                country = area.get('name', '') if area else ''

                # 联赛类型判断
                comp_type = comp.get('type', 'LEAGUE')
                if comp_type == 'CUP':
                    format_type = 'knockout'
                else:
                    format_type = 'round_robin'

                # 检查是否已存在
                cursor.execute(
                    "SELECT league_id FROM leagues WHERE league_code = ? OR name_en = ?",
                    (comp_code.lower(), name)
                )
                existing = cursor.fetchone()

                if existing:
                    # 更新
                    cursor.execute('''
                        UPDATE leagues SET
                            country = COALESCE(?, country),
                            fd_comp_code = ?,
                            format_type = ?
                        WHERE league_id = ?
                    ''', (country, comp_code, format_type, existing['league_id']))
                    updated += 1
                else:
                    # 插入新联赛
                    cursor.execute('''
                        INSERT INTO leagues (league_code, name_en, country, competition_type, format_type, fd_comp_code)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (comp_code.lower(), name, country, 'league', format_type, comp_code))
                    added += 1

            conn.commit()
            conn.close()

            return {
                "success": True,
                "source": "football-data.org",
                "updated": updated,
                "added": added,
                "total": len(competitions)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def enrich_from_thesportsdb(self) -> Dict:
        """
        从TheSportsDB获取联赛信息
        该API提供全球联赛数据，包括非欧洲联赛
        """
        url = "https://www.thesportsdb.com/api/v1/json/3/allleagues.php"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return {"success": False, "error": f"API返回 {response.status_code}"}

            data = response.json()
            leagues = data.get('leagues', [])

            conn = self._get_db()
            cursor = conn.cursor()

            updated = 0
            added = 0
            soccer_leagues = [l for l in leagues if l and l.get('strSport') == 'Soccer']

            for league in soccer_leagues:
                if not league:
                    continue

                name = league.get('strLeague', '')
                tsdb_id = league.get('idLeague', '')
                country = league.get('strCountry', '')

                # 跳过没有名字的
                if not name:
                    continue

                # 检查是否已存在
                cursor.execute(
                    "SELECT league_id FROM leagues WHERE name_en = ? OR tsdb_league_id = ?",
                    (name, int(tsdb_id) if tsdb_id else None)
                )
                existing = cursor.fetchone()

                if existing:
                    # 更新
                    cursor.execute('''
                        UPDATE leagues SET
                            country = COALESCE(?, country),
                            tsdb_league_id = ?
                        WHERE league_id = ?
                    ''', (country, int(tsdb_id) if tsdb_id else None, existing['league_id']))
                    updated += 1
                else:
                    # 生成联赛代码
                    code = name.lower().replace(' ', '_').replace('-', '_')[:20]

                    # 插入新联赛
                    cursor.execute('''
                        INSERT INTO leagues (league_code, name_en, country, tsdb_league_id)
                        VALUES (?, ?, ?, ?)
                    ''', (code, name, country, int(tsdb_id) if tsdb_id else None))
                    added += 1

            conn.commit()
            conn.close()

            return {
                "success": True,
                "source": "thesportsdb",
                "updated": updated,
                "added": added,
                "total": len(soccer_leagues)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_league_metadata(self) -> Dict:
        """
        更新联赛元数据
        包括：中文名称、联赛等级、是否国际赛事等
        """
        # 预定义的联赛元数据
        league_metadata = {
            # 五大联赛一级
            'premier_league': {
                'name_cn': '英超',
                'country': 'England',
                'country_cn': '英格兰',
                'tier': 1,
                'is_international': 0
            },
            'la_liga': {
                'name_cn': '西甲',
                'country': 'Spain',
                'country_cn': '西班牙',
                'tier': 1,
                'is_international': 0
            },
            'bundesliga': {
                'name_cn': '德甲',
                'country': 'Germany',
                'country_cn': '德国',
                'tier': 1,
                'is_international': 0
            },
            'serie_a': {
                'name_cn': '意甲',
                'country': 'Italy',
                'country_cn': '意大利',
                'tier': 1,
                'is_international': 0
            },
            'ligue_1': {
                'name_cn': '法甲',
                'country': 'France',
                'country_cn': '法国',
                'tier': 1,
                'is_international': 0
            },

            # 五大联赛二级
            'championship': {
                'name_cn': '英冠',
                'country': 'England',
                'country_cn': '英格兰',
                'tier': 2,
                'is_international': 0
            },
            'segunda_division': {
                'name_cn': '西乙',
                'country': 'Spain',
                'country_cn': '西班牙',
                'tier': 2,
                'is_international': 0
            },
            'bundesliga_2': {
                'name_cn': '德乙',
                'country': 'Germany',
                'country_cn': '德国',
                'tier': 2,
                'is_international': 0
            },
            'serie_b': {
                'name_cn': '意乙',
                'country': 'Italy',
                'country_cn': '意大利',
                'tier': 2,
                'is_international': 0
            },
            'ligue_2': {
                'name_cn': '法乙',
                'country': 'France',
                'country_cn': '法国',
                'tier': 2,
                'is_international': 0
            },

            # 英格兰低级别联赛
            'league_one': {
                'name_cn': '英甲',
                'country': 'England',
                'country_cn': '英格兰',
                'tier': 3,
                'is_international': 0
            },
            'league_two': {
                'name_cn': '英乙',
                'country': 'England',
                'country_cn': '英格兰',
                'tier': 4,
                'is_international': 0
            },

            # 其他欧洲联赛
            'eredivisie': {
                'name_cn': '荷甲',
                'country': 'Netherlands',
                'country_cn': '荷兰',
                'tier': 1,
                'is_international': 0
            },
            'primeira_liga': {
                'name_cn': '葡超',
                'country': 'Portugal',
                'country_cn': '葡萄牙',
                'tier': 1,
                'is_international': 0
            },
            'jupiler_league': {
                'name_cn': '比甲',
                'country': 'Belgium',
                'country_cn': '比利时',
                'tier': 1,
                'is_international': 0
            },
            'super_lig': {
                'name_cn': '土超',
                'country': 'Turkey',
                'country_cn': '土耳其',
                'tier': 1,
                'is_international': 0
            },

            # 北欧联赛
            'allsvenskan': {
                'name_cn': '瑞典超',
                'country': 'Sweden',
                'country_cn': '瑞典',
                'tier': 1,
                'is_international': 0
            },
            'eliteserien': {
                'name_cn': '挪超',
                'country': 'Norway',
                'country_cn': '挪威',
                'tier': 1,
                'is_international': 0
            },
            'veikkausliiga': {
                'name_cn': '芬超',
                'country': 'Finland',
                'country_cn': '芬兰',
                'tier': 1,
                'is_international': 0
            },

            # 苏格兰
            'scotland_premier': {
                'name_cn': '苏超',
                'country': 'Scotland',
                'country_cn': '苏格兰',
                'tier': 1,
                'is_international': 0
            },

            # 亚洲联赛
            'j1_league': {
                'name_cn': 'J联赛',
                'country': 'Japan',
                'country_cn': '日本',
                'tier': 1,
                'is_international': 0
            },
            'k1_league': {
                'name_cn': 'K联赛',
                'country': 'South Korea',
                'country_cn': '韩国',
                'tier': 1,
                'is_international': 0
            },
            'csl': {
                'name_cn': '中超',
                'country': 'China',
                'country_cn': '中国',
                'tier': 1,
                'is_international': 0
            },
            'saudi_pro': {
                'name_cn': '沙特联',
                'country': 'Saudi Arabia',
                'country_cn': '沙特阿拉伯',
                'tier': 1,
                'is_international': 0
            },

            # 美洲联赛
            'mls': {
                'name_cn': '美职联',
                'country': 'USA',
                'country_cn': '美国',
                'tier': 1,
                'is_international': 0
            },
            'brasileirao': {
                'name_cn': '巴甲',
                'country': 'Brazil',
                'country_cn': '巴西',
                'tier': 1,
                'is_international': 0
            },
            'a_league': {
                'name_cn': '澳超',
                'country': 'Australia',
                'country_cn': '澳大利亚',
                'tier': 1,
                'is_international': 0
            },

            # 欧洲杯赛
            'champions_league': {
                'name_cn': '欧冠',
                'country': 'Europe',
                'country_cn': '欧洲',
                'tier': 1,
                'is_international': 1,
                'competition_type': 'cup'
            },
            'europa_league': {
                'name_cn': '欧联',
                'country': 'Europe',
                'country_cn': '欧洲',
                'tier': 2,
                'is_international': 1,
                'competition_type': 'cup'
            },

            # 国际赛事
            'world_cup': {
                'name_cn': '世界杯',
                'country': 'World',
                'country_cn': '世界',
                'tier': 1,
                'is_international': 1,
                'competition_type': 'cup'
            },
            'euro': {
                'name_cn': '欧洲杯',
                'country': 'Europe',
                'country_cn': '欧洲',
                'tier': 1,
                'is_international': 1,
                'competition_type': 'cup'
            },
            'copa_america': {
                'name_cn': '美洲杯',
                'country': 'South America',
                'country_cn': '南美洲',
                'tier': 1,
                'is_international': 1,
                'competition_type': 'cup'
            },
            'asian_cup': {
                'name_cn': '亚洲杯',
                'country': 'Asia',
                'country_cn': '亚洲',
                'tier': 1,
                'is_international': 1,
                'competition_type': 'cup'
            },
            'africa_cup': {
                'name_cn': '非洲杯',
                'country': 'Africa',
                'country_cn': '非洲',
                'tier': 1,
                'is_international': 1,
                'competition_type': 'cup'
            },
        }

        conn = self._get_db()
        cursor = conn.cursor()

        updated = 0
        for code, meta in league_metadata.items():
            cursor.execute('''
                UPDATE leagues SET
                    name_cn = COALESCE(?, name_cn),
                    country = COALESCE(?, country),
                    country_cn = COALESCE(?, country_cn),
                    tier = COALESCE(?, tier),
                    is_international = COALESCE(?, is_international),
                    competition_type = COALESCE(?, competition_type)
                WHERE league_code = ?
            ''', (
                meta.get('name_cn'),
                meta.get('country'),
                meta.get('country_cn'),
                meta.get('tier'),
                meta.get('is_international'),
                meta.get('competition_type'),
                code
            ))
            if cursor.rowcount > 0:
                updated += 1

        conn.commit()
        conn.close()

        return {
            "success": True,
            "updated": updated,
            "total_defined": len(league_metadata)
        }

    def get_missing_data_leagues(self) -> List[Dict]:
        """获取数据缺失的联赛"""
        conn = self._get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT l.league_id, l.name_en, l.league_code, l.country,
                   COUNT(m.match_id) as match_count
            FROM leagues l
            LEFT JOIN matches m ON l.league_id = m.league_id
            GROUP BY l.league_id
            HAVING match_count < 100
            ORDER BY match_count DESC
        ''')

        missing = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return missing

    def full_enrich(self) -> Dict:
        """完整的数据补充流程"""
        print(f"[{datetime.now()}] 开始联赛数据补充...")

        results = {}

        # 1. 从football-data.org获取欧洲联赛
        print("  从football-data.org获取数据...")
        results['football_data'] = self.enrich_from_football_data()

        # 2. 从TheSportsDB获取全球联赛
        print("  从TheSportsDB获取数据...")
        results['thesportsdb'] = self.enrich_from_thesportsdb()

        # 3. 更新预定义的元数据
        print("  更新联赛元数据...")
        results['metadata'] = self.update_league_metadata()

        # 4. 获取数据缺失的联赛
        results['missing_data'] = self.get_missing_data_leagues()

        print(f"[{datetime.now()}] 联赛数据补充完成")

        return results


# 命令行入口
if __name__ == "__main__":
    enricher = LeagueDataEnricher()
    result = enricher.full_enrich()
    print(json.dumps(result, indent=2, ensure_ascii=False))
