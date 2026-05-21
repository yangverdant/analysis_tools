#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据采集和导入脚本
- 从CSV文件导入比赛数据到数据库
- 自动去重
- 支持多种赛事类型（联赛、杯赛、锦标赛）
"""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib

# 配置
DATABASE_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'
DATA_DIR = Path(__file__).parent.parent / 'new_data' / 'matches' / 'clubs' / 'leagues'

# 联赛映射配置
LEAGUE_CONFIG = {
    # 英格兰
    'premier_league': {
        'league_id': 23,
        'name_en': 'Premier League',
        'name_cn': '英格兰超级联赛',
        'country': 'England',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 1,
        'is_international': 0
    },
    'championship': {
        'league_id': 24,
        'name_en': 'Championship',
        'name_cn': '英格兰冠军联赛',
        'country': 'England',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 2,
        'is_international': 0
    },
    'league_one': {
        'league_id': 25,
        'name_en': 'League One',
        'name_cn': '英格兰甲级联赛',
        'country': 'England',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 3,
        'is_international': 0
    },
    'league_two': {
        'league_id': 26,
        'name_en': 'League Two',
        'name_cn': '英格兰乙级联赛',
        'country': 'England',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 4,
        'is_international': 0
    },
    # 西班牙
    'la_liga': {
        'league_id': 27,
        'name_en': 'La Liga',
        'name_cn': '西班牙甲级联赛',
        'country': 'Spain',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 1,
        'is_international': 0
    },
    'segunda_division': {
        'league_id': 28,
        'name_en': 'Segunda Division',
        'name_cn': '西班牙乙级联赛',
        'country': 'Spain',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 2,
        'is_international': 0
    },
    # 德国
    'bundesliga': {
        'league_id': 29,
        'name_en': 'Bundesliga',
        'name_cn': '德国甲级联赛',
        'country': 'Germany',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 1,
        'is_international': 0
    },
    'bundesliga_2': {
        'league_id': 30,
        'name_en': '2. Bundesliga',
        'name_cn': '德国乙级联赛',
        'country': 'Germany',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 2,
        'is_international': 0
    },
    'bundesliga_3': {
        'league_id': 31,
        'name_en': '3. Liga',
        'name_cn': '德国丙级联赛',
        'country': 'Germany',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 3,
        'is_international': 0
    },
    # 意大利
    'serie_a': {
        'league_id': 32,
        'name_en': 'Serie A',
        'name_cn': '意大利甲级联赛',
        'country': 'Italy',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 1,
        'is_international': 0
    },
    'serie_b': {
        'league_id': 33,
        'name_en': 'Serie B',
        'name_cn': '意大利乙级联赛',
        'country': 'Italy',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 2,
        'is_international': 0
    },
    # 法国
    'ligue_1': {
        'league_id': 34,
        'name_en': 'Ligue 1',
        'name_cn': '法国甲级联赛',
        'country': 'France',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 1,
        'is_international': 0
    },
    'ligue_2': {
        'league_id': 35,
        'name_en': 'Ligue 2',
        'name_cn': '法国乙级联赛',
        'country': 'France',
        'competition_type': 'league',
        'participant_type': 'club',
        'format_type': 'round_robin',
        'tier': 2,
        'is_international': 0
    },
    # 欧洲杯赛
    'champions_league': {
        'league_id': 40,
        'name_en': 'Champions League',
        'name_cn': '欧洲冠军联赛',
        'country': 'Europe',
        'competition_type': 'tournament',
        'participant_type': 'club',
        'format_type': 'group_knockout',
        'tier': 1,
        'is_international': 1
    },
    # 国家队赛事
    'world_cup': {
        'league_id': 44,
        'name_en': 'World Cup',
        'name_cn': '世界杯',
        'country': 'FIFA',
        'competition_type': 'tournament',
        'participant_type': 'national',
        'format_type': 'group_knockout',
        'tier': 1,
        'is_international': 1
    },
    'euro_championship': {
        'league_id': 42,
        'name_en': 'European Championship',
        'name_cn': '欧洲杯',
        'country': 'UEFA',
        'competition_type': 'tournament',
        'participant_type': 'national',
        'format_type': 'group_knockout',
        'tier': 1,
        'is_international': 1
    },
}

# 其他联赛默认配置
DEFAULT_LEAGUE_CONFIG = {
    'competition_type': 'league',
    'participant_type': 'club',
    'format_type': 'round_robin',
    'tier': 1,
    'is_international': 0
}


class DataImporter:
    """数据导入器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.stats = {
            'leagues_processed': 0,
            'matches_imported': 0,
            'matches_skipped': 0,
            'matches_updated': 0,
            'teams_added': 0,
            'errors': []
        }
        self.team_cache = {}  # 球队名 -> team_id 缓存
        self.match_hashes = set()  # 已存在比赛的hash集合

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        print(f"已连接数据库: {self.db_path}")

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()

    def load_existing_matches(self):
        """加载已存在的比赛hash，用于去重"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT match_id, match_date, home_team_id, away_team_id, league_id, season_id
            FROM matches
        """)

        for row in cursor.fetchall():
            # 生成唯一hash：日期 + 主队 + 客队 + 联赛
            match_hash = self._generate_match_hash(
                row['match_date'],
                row['home_team_id'],
                row['away_team_id'],
                row['league_id']
            )
            self.match_hashes.add(match_hash)

        print(f"已加载 {len(self.match_hashes)} 条现有比赛记录")

    def _generate_match_hash(self, date: str, home_team_id: int, away_team_id: int, league_id: int) -> str:
        """生成比赛唯一hash"""
        key = f"{date}_{home_team_id}_{away_team_id}_{league_id}"
        return hashlib.md5(key.encode()).hexdigest()

    def get_or_create_team(self, team_name: str, team_tla: str = None, league_id: int = None) -> int:
        """
        获取或创建球队

        Returns:
            team_id
        """
        # 检查缓存
        cache_key = team_name.lower()
        if cache_key in self.team_cache:
            return self.team_cache[cache_key]

        cursor = self.conn.cursor()

        # 先按名称查找
        cursor.execute("""
            SELECT team_id, name_en, name_cn FROM teams
            WHERE name_en = ? OR name_cn = ? OR short_name = ?
        """, (team_name, team_name, team_name))

        result = cursor.fetchone()
        if result:
            self.team_cache[cache_key] = result['team_id']
            return result['team_id']

        # 按TLA查找
        if team_tla:
            cursor.execute("""
                SELECT team_id FROM teams WHERE tla = ?
            """, (team_tla,))
            result = cursor.fetchone()
            if result:
                self.team_cache[cache_key] = result['team_id']
                return result['team_id']

        # 创建新球队
        cursor.execute("""
            INSERT INTO teams (name_en, name_cn, short_name, tla, team_type, league_id, created_at)
            VALUES (?, ?, ?, ?, 'club', ?, datetime('now'))
        """, (team_name, None, team_name, team_tla, league_id))

        team_id = cursor.lastrowid
        self.conn.commit()

        self.team_cache[cache_key] = team_id
        self.stats['teams_added'] += 1
        print(f"  新增球队: {team_name} (ID: {team_id})")

        return team_id

    def get_or_create_league(self, league_code: str) -> int:
        """获取或创建联赛"""
        cursor = self.conn.cursor()

        # 检查配置
        config = LEAGUE_CONFIG.get(league_code, {})

        # 先按league_code查找
        cursor.execute("SELECT league_id FROM leagues WHERE league_code = ?",
                      (league_code,))
        result = cursor.fetchone()
        if result:
            return result['league_id']

        # 再按league_id查找（如果有配置）
        if config.get('league_id'):
            cursor.execute("SELECT league_id FROM leagues WHERE league_id = ?",
                          (config.get('league_id'),))
            result = cursor.fetchone()
            if result:
                return result['league_id']

        # 创建新联赛
        league_id = config.get('league_id') or hash(league_code) % 10000
        name_en = config.get('name_en', league_code.replace('_', ' ').title())

        try:
            cursor.execute("""
                INSERT INTO leagues (league_id, league_code, name_en, name_cn, country,
                                   competition_type, participant_type, format_type, tier, is_international)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                league_id,
                league_code,
                name_en,
                config.get('name_cn'),
                config.get('country', 'Unknown'),
                config.get('competition_type', 'league'),
                config.get('participant_type', 'club'),
                config.get('format_type', 'round_robin'),
                config.get('tier', 1),
                config.get('is_international', 0)
            ))

            self.conn.commit()
            print(f"  新增联赛: {name_en} (ID: {league_id})")
        except sqlite3.IntegrityError:
            # 如果插入失败，再次查找
            cursor.execute("SELECT league_id FROM leagues WHERE league_code = ?",
                          (league_code,))
            result = cursor.fetchone()
            if result:
                return result['league_id']
            # 最后尝试按name查找
            cursor.execute("SELECT league_id FROM leagues WHERE name_en = ?",
                          (name_en,))
            result = cursor.fetchone()
            if result:
                return result['league_id']
            # 如果还是找不到，生成一个新的ID
            cursor.execute("SELECT MAX(league_id) FROM leagues")
            max_id = cursor.fetchone()[0] or 0
            league_id = max_id + 1
            cursor.execute("""
                INSERT INTO leagues (league_id, league_code, name_en, competition_type, participant_type, format_type)
                VALUES (?, ?, ?, 'league', 'club', 'round_robin')
            """, (league_id, league_code, name_en))
            self.conn.commit()
            print(f"  新增联赛(新ID): {name_en} (ID: {league_id})")

        return league_id

    def get_or_create_season(self, league_id: int, season_name: str) -> int:
        """获取或创建赛季"""
        cursor = self.conn.cursor()

        # 查找
        cursor.execute("""
            SELECT season_id FROM seasons
            WHERE league_id = ? AND season_name = ?
        """, (league_id, season_name))
        result = cursor.fetchone()
        if result:
            return result['season_id']

        # 创建 - 处理年份
        try:
            if '-' in season_name:
                year = int(season_name.split('-')[0])
            else:
                year = int(season_name)
        except ValueError:
            year = datetime.now().year

        cursor.execute("""
            INSERT INTO seasons (league_id, season_name, year, status, created_at)
            VALUES (?, ?, ?, 'active', datetime('now'))
        """, (league_id, season_name, year))

        season_id = cursor.lastrowid
        self.conn.commit()

        return season_id

    def parse_season_from_filename(self, filename: str) -> str:
        """从文件名解析赛季"""
        # football-data_new_premier_league_2024-2025.csv
        # 过滤掉backup等特殊文件
        filename = filename.replace('.csv', '').lower()
        if 'backup' in filename or 'teams' in filename:
            return str(datetime.now().year)

        parts = filename.split('_')
        if len(parts) >= 4:
            season_part = parts[-1]
            # 处理各种格式: 2024-2025, 2024-25, 2024
            if '-' in season_part:
                return season_part
            # 尝试匹配年份
            import re
            match = re.search(r'(\d{4})', season_part)
            if match:
                return match.group(1)
        return str(datetime.now().year)

    def import_csv_file(self, csv_path: Path, league_code: str) -> Dict:
        """
        导入单个CSV文件

        Returns:
            导入统计
        """
        print(f"\n处理: {csv_path.name}")

        stats = {
            'total': 0,
            'imported': 0,
            'skipped': 0,
            'updated': 0,
            'errors': []
        }

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"  错误: 无法读取CSV - {e}")
            return stats

        if df.empty:
            print(f"  跳过: 空文件")
            return stats

        stats['total'] = len(df)

        # 获取联赛和赛季
        league_id = self.get_or_create_league(league_code)
        season_name = self.parse_season_from_filename(csv_path.name)
        season_id = self.get_or_create_season(league_id, season_name)

        print(f"  联赛ID: {league_id}, 赛季: {season_name}")

        # 遍历比赛
        for idx, row in df.iterrows():
            try:
                match_data = self._parse_match_row(row, league_id, season_id)
                if not match_data:
                    stats['skipped'] += 1
                    continue

                # 检查重复
                match_hash = self._generate_match_hash(
                    match_data['match_date'],
                    match_data['home_team_id'],
                    match_data['away_team_id'],
                    league_id
                )

                if match_hash in self.match_hashes:
                    stats['skipped'] += 1
                    continue

                # 插入比赛
                self._insert_match(match_data)

                self.match_hashes.add(match_hash)
                stats['imported'] += 1

            except Exception as e:
                stats['errors'].append(f"行{idx}: {str(e)}")

        print(f"  结果: 导入 {stats['imported']}, 跳过 {stats['skipped']}, 错误 {len(stats['errors'])}")

        return stats

    def _parse_match_row(self, row: pd.Series, league_id: int, season_id: int) -> Optional[Dict]:
        """解析CSV行为比赛数据"""
        # 日期
        date = row.get('date') or row.get('Date')
        if pd.isna(date):
            return None

        # 球队名
        home_team = row.get('home_team') or row.get('HomeTeam')
        away_team = row.get('away_team') or row.get('AwayTeam')

        if pd.isna(home_team) or pd.isna(away_team):
            return None

        # TLA
        home_tla = row.get('home_team_tla')
        away_tla = row.get('away_team_tla')

        # 获取球队ID
        home_team_id = self.get_or_create_team(home_team, home_tla, league_id)
        away_team_id = self.get_or_create_team(away_team, away_tla, league_id)

        # 比分
        home_goals = row.get('ft_home') or row.get('FTHG') or row.get('home_goals')
        away_goals = row.get('ft_away') or row.get('FTAG') or row.get('away_goals')

        # 半场比分
        ht_home = row.get('ht_home') or row.get('HTHG')
        ht_away = row.get('ht_away') or row.get('HTAG')

        # 轮次
        round_num = row.get('round') or row.get('Round')
        round_stage = str(round_num) if pd.notna(round_num) else None

        # 状态
        status = row.get('status') or row.get('Status')
        if pd.isna(status):
            if pd.notna(home_goals) and pd.notna(away_goals):
                status = 'finished'
            else:
                status = 'scheduled'

        # match_id（外部ID）
        external_id = row.get('match_id')

        return {
            'match_date': str(date),
            'match_time': None,
            'league_id': league_id,
            'season_id': season_id,
            'round_stage': round_stage,
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_goals': int(home_goals) if pd.notna(home_goals) else None,
            'away_goals': int(away_goals) if pd.notna(away_goals) else None,
            'home_goals_ht': int(ht_home) if pd.notna(ht_home) else None,
            'away_goals_ht': int(ht_away) if pd.notna(ht_away) else None,
            'status': status,
            'external_id': str(external_id) if pd.notna(external_id) else None,
            'source': 'csv_import'
        }

    def _insert_match(self, match_data: Dict):
        """插入比赛数据"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO matches (
                match_date, match_time, league_id, season_id, round_stage,
                home_team_id, away_team_id,
                home_goals, away_goals,
                home_goals_ht, away_goals_ht,
                status, external_id, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            match_data['match_date'],
            match_data['match_time'],
            match_data['league_id'],
            match_data['season_id'],
            match_data['round_stage'],
            match_data['home_team_id'],
            match_data['away_team_id'],
            match_data['home_goals'],
            match_data['away_goals'],
            match_data['home_goals_ht'],
            match_data['away_goals_ht'],
            match_data['status'],
            match_data['external_id'],
            match_data['source']
        ))

        self.conn.commit()

    def import_all_leagues(self, data_dir: Path):
        """导入所有联赛数据"""
        print("=" * 60)
        print("开始导入所有联赛数据")
        print("=" * 60)

        # 遍历联赛目录
        for league_dir in sorted(data_dir.iterdir()):
            if not league_dir.is_dir():
                continue

            league_code = league_dir.name

            # 跳过特殊目录
            if league_code.startswith('StatsBomb') or league_code.startswith('_'):
                continue

            # 处理该联赛的所有CSV文件
            csv_files = list(league_dir.glob('*.csv'))

            if not csv_files:
                continue

            print(f"\n{'='*50}")
            print(f"联赛: {league_code}")
            print(f"文件数: {len(csv_files)}")

            league_stats = {
                'total': 0,
                'imported': 0,
                'skipped': 0
            }

            for csv_file in sorted(csv_files):
                # 跳过球队文件和备份文件
                if 'teams' in csv_file.name.lower() or 'backup' in csv_file.name.lower():
                    continue

                file_stats = self.import_csv_file(csv_file, league_code)
                league_stats['total'] += file_stats['total']
                league_stats['imported'] += file_stats['imported']
                league_stats['skipped'] += file_stats['skipped']

            self.stats['leagues_processed'] += 1
            self.stats['matches_imported'] += league_stats['imported']
            self.stats['matches_skipped'] += league_stats['skipped']

            print(f"\n联赛汇总: 总计 {league_stats['total']}, 导入 {league_stats['imported']}, 跳过 {league_stats['skipped']}")

    def print_summary(self):
        """打印导入汇总"""
        print("\n" + "=" * 60)
        print("导入完成汇总")
        print("=" * 60)
        print(f"处理联赛数: {self.stats['leagues_processed']}")
        print(f"导入比赛数: {self.stats['matches_imported']}")
        print(f"跳过比赛数: {self.stats['matches_skipped']}")
        print(f"新增球队数: {self.stats['teams_added']}")
        if self.stats['errors']:
            print(f"错误数: {len(self.stats['errors'])}")


def main():
    """主函数"""
    print("足球数据导入工具")
    print("=" * 60)

    # 初始化导入器
    importer = DataImporter(str(DATABASE_PATH))

    try:
        importer.connect()

        # 加载现有数据用于去重
        importer.load_existing_matches()

        # 导入所有联赛
        importer.import_all_leagues(DATA_DIR)

        # 打印汇总
        importer.print_summary()

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        importer.close()


if __name__ == '__main__':
    main()
