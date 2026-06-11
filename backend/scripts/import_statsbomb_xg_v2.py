"""
StatsBomb xG数据导入脚本 - 改进版
从StatsBomb事件文件中提取xG数据并更新到数据库
使用比分验证确保数据正确匹配
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import re


class StatsBombXGImporterV2:
    """StatsBomb xG数据导入器 - 改进版"""

    # 球队名称映射（StatsBomb名称 -> 数据库名称）
    TEAM_NAME_MAPPING = {
        'Barcelona': 'Barcelona',
        'Real Madrid': 'Real Madrid',
        'Atlético Madrid': 'Atletico Madrid',
        'Athletic Club': 'Athletic Bilbao',
        'Deportivo Alavés': 'Alaves',
        'Real Valladolid': 'Valladolid',
        'Real Sociedad': 'Real Sociedad',
        'Girona': 'Girona',
        'Leganés': 'Leganes',
        'Valencia': 'Valencia',
        'Sevilla': 'Sevilla',
        'Real Betis': 'Real Betis',
        'Villarreal': 'Villarreal',
        'Espanyol': 'Espanyol',
        'Getafe': 'Getafe',
        'Celta Vigo': 'Celta Vigo',
        'Levante': 'Levante',
        'Granada': 'Granada',
        'Osasuna': 'Osasuna',
        'Mallorca': 'Mallorca',
        'Rayo Vallecano': 'Rayo Vallecano',
        'Cádiz': 'Cadiz',
        'Bayern Munich': 'Bayern Munich',
        'Borussia Dortmund': 'Dortmund',
        'Paris Saint-Germain': 'Paris Saint Germain',
        'Manchester City': 'Manchester City',
        'Manchester United': 'Man United',
        'Liverpool': 'Liverpool',
        'Chelsea': 'Chelsea',
        'Arsenal': 'Arsenal',
        'Tottenham Hotspur': 'Tottenham',
        'Juventus': 'Juventus',
        'Inter': 'Inter Milan',
        'Milan': 'AC Milan',
        'Napoli': 'Napoli',
        'Roma': 'Roma',
        'Lazio': 'Lazio',
        'Germany': 'Germany',
        'Spain': 'Spain',
        'France': 'France',
        'England': 'England',
        'Italy': 'Italy',
        'Netherlands': 'Netherlands',
        'Portugal': 'Portugal',
        'Belgium': 'Belgium',
        'Croatia': 'Croatia',
        'Switzerland': 'Switzerland',
        'Hungary': 'Hungary',
        'Poland': 'Poland',
        'Scotland': 'Scotland',
        'Albania': 'Albania',
        'Austria': 'Austria',
        'Denmark': 'Denmark',
        'Slovakia': 'Slovakia',
        'Slovenia': 'Slovenia',
        'Serbia': 'Serbia',
        'Ukraine': 'Ukraine',
        'Romania': 'Romania',
        'Turkey': 'Turkey',
        'Georgia': 'Georgia',
        'Czech Republic': 'Czech Republic',
        'Sweden': 'Sweden',
        'Norway': 'Norway',
        'Finland': 'Finland',
        'Ireland': 'Ireland',
        'Russia': 'Russia',
        'Greece': 'Greece',
        'Wales': 'Wales',
        'North Macedonia': 'North Macedonia',
    }

    def __init__(self, db_path: str, statsbomb_dir: str):
        self.db_path = db_path
        self.statsbomb_dir = Path(statsbomb_dir)
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

    def normalize_team_name(self, name: str) -> str:
        """标准化球队名称"""
        if name in self.TEAM_NAME_MAPPING:
            return self.TEAM_NAME_MAPPING[name]

        for key, value in self.TEAM_NAME_MAPPING.items():
            if key in name or name in key:
                return value

        return name

    def extract_match_info(self, events: List[Dict]) -> Optional[Dict]:
        """从StatsBomb事件中提取比赛信息"""
        starting_xi = [e for e in events if e.get('type', {}).get('name') == 'Starting XI']

        if len(starting_xi) < 2:
            return None

        home_team = starting_xi[0].get('team', {}).get('name')
        away_team = starting_xi[1].get('team', {}).get('name')

        if not home_team or not away_team:
            return None

        # 提取射门事件
        shots = [e for e in events if e.get('type', {}).get('name') == 'Shot']

        # 计算xG和进球
        home_xg = 0.0
        away_xg = 0.0
        home_goals = 0
        away_goals = 0
        home_shots = 0
        away_shots = 0
        home_shots_target = 0
        away_shots_target = 0

        for shot in shots:
            team = shot.get('team', {}).get('name')
            xg = shot.get('shot', {}).get('statsbomb_xg', 0) or 0
            outcome = shot.get('shot', {}).get('outcome', {}).get('name', '')

            if team == home_team:
                home_xg += xg
                home_shots += 1
                if outcome == 'Goal':
                    home_goals += 1
                    home_shots_target += 1
                elif outcome == 'Saved':
                    home_shots_target += 1
            elif team == away_team:
                away_xg += xg
                away_shots += 1
                if outcome == 'Goal':
                    away_goals += 1
                    away_shots_target += 1
                elif outcome == 'Saved':
                    away_shots_target += 1

        # 控球率
        possession_events = [e for e in events if 'possession' in e]
        if possession_events:
            home_possession = sum(1 for e in possession_events if e.get('team', {}).get('name') == home_team)
            total = len(possession_events)
            home_possession_pct = (home_possession / total * 100) if total > 0 else 50.0
            away_possession_pct = 100 - home_possession_pct
        else:
            home_possession_pct = 50.0
            away_possession_pct = 50.0

        # 犯规
        fouls = [e for e in events if e.get('type', {}).get('name') == 'Foul Committed']
        home_fouls = sum(1 for f in fouls if f.get('team', {}).get('name') == home_team)
        away_fouls = sum(1 for f in fouls if f.get('team', {}).get('name') == away_team)

        # 角球
        corners = [e for e in events if e.get('type', {}).get('name') == 'Corner Awarded']
        home_corners = sum(1 for c in corners if c.get('team', {}).get('name') == home_team)
        away_corners = sum(1 for c in corners if c.get('team', {}).get('name') == away_team)

        # 黄牌
        yellow_cards = [e for e in events if e.get('type', {}).get('name') == 'Bad Behaviour'
                        and e.get('bad_behaviour', {}).get('card', {}).get('name') == 'Yellow Card']
        home_yellow = sum(1 for y in yellow_cards if y.get('team', {}).get('name') == home_team)
        away_yellow = sum(1 for y in yellow_cards if y.get('team', {}).get('name') == away_team)

        # 红牌
        red_cards = [e for e in events if e.get('type', {}).get('name') == 'Bad Behaviour'
                     and e.get('bad_behaviour', {}).get('card', {}).get('name') in ['Red Card', 'Second Yellow']]
        home_red = sum(1 for r in red_cards if r.get('team', {}).get('name') == home_team)
        away_red = sum(1 for r in red_cards if r.get('team', {}).get('name') == away_team)

        return {
            'home_team': self.normalize_team_name(home_team),
            'away_team': self.normalize_team_name(away_team),
            'home_goals': home_goals,
            'away_goals': away_goals,
            'home_xg': round(home_xg, 2),
            'away_xg': round(away_xg, 2),
            'home_shots': home_shots,
            'away_shots': away_shots,
            'home_shots_target': home_shots_target,
            'away_shots_target': away_shots_target,
            'home_possession': round(home_possession_pct, 1),
            'away_possession': round(away_possession_pct, 1),
            'home_fouls': home_fouls,
            'away_fouls': away_fouls,
            'home_corners': home_corners,
            'away_corners': away_corners,
            'home_yellow': home_yellow,
            'away_yellow': away_yellow,
            'home_red': home_red,
            'away_red': away_red,
        }

    def find_match_in_db(self, match_info: Dict) -> Optional[Tuple[str, bool]]:
        """在数据库中查找对应的比赛，使用比分验证"""
        home_team = match_info['home_team']
        away_team = match_info['away_team']
        home_goals = match_info['home_goals']
        away_goals = match_info['away_goals']

        # 使用球队名和比分精确匹配
        query = '''
            SELECT m.match_id, m.match_date, t1.name_en, t2.name_en,
                   m.home_goals, m.away_goals, m.home_xg, m.away_xg
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.team_id
            JOIN teams t2 ON m.away_team_id = t2.team_id
            WHERE (t1.name_en LIKE ? OR t1.name_cn LIKE ?)
              AND (t2.name_en LIKE ? OR t2.name_cn LIKE ?)
              AND m.home_goals = ?
              AND m.away_goals = ?
              AND m.home_xg IS NULL
            ORDER BY m.match_date DESC
            LIMIT 1
        '''

        self.cursor.execute(query, (
            f'%{home_team}%', f'%{home_team}%',
            f'%{away_team}%', f'%{away_team}%',
            home_goals, away_goals
        ))

        result = self.cursor.fetchone()
        if result:
            return result[0], True  # match_id, verified

        # 如果比分匹配失败，尝试只按球队名匹配（返回未验证）
        query2 = '''
            SELECT m.match_id, m.match_date, t1.name_en, t2.name_en,
                   m.home_goals, m.away_goals, m.home_xg, m.away_xg
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.team_id
            JOIN teams t2 ON m.away_team_id = t2.team_id
            WHERE (t1.name_en LIKE ? OR t1.name_cn LIKE ?)
              AND (t2.name_en LIKE ? OR t2.name_cn LIKE ?)
              AND m.home_xg IS NULL
            ORDER BY m.match_date DESC
            LIMIT 1
        '''

        self.cursor.execute(query2, (
            f'%{home_team}%', f'%{home_team}%',
            f'%{away_team}%', f'%{away_team}%'
        ))

        result = self.cursor.fetchone()
        if result:
            return result[0], False  # match_id, not verified

        return None

    def update_match_stats(self, match_id: str, stats: Dict) -> bool:
        """更新比赛统计数据"""
        try:
            self.cursor.execute('''
                UPDATE matches SET
                    home_xg = ?,
                    away_xg = ?,
                    home_shots = ?,
                    away_shots = ?,
                    home_shots_target = ?,
                    away_shots_target = ?,
                    home_possession = ?,
                    away_possession = ?,
                    home_fouls = ?,
                    away_fouls = ?,
                    home_corners = ?,
                    away_corners = ?,
                    home_yellow = ?,
                    away_yellow = ?,
                    home_red = ?,
                    away_red = ?,
                    source = COALESCE(source || '+statsbomb', 'statsbomb')
                WHERE match_id = ?
            ''', (
                stats['home_xg'], stats['away_xg'],
                stats['home_shots'], stats['away_shots'],
                stats['home_shots_target'], stats['away_shots_target'],
                stats['home_possession'], stats['away_possession'],
                stats['home_fouls'], stats['away_fouls'],
                stats['home_corners'], stats['away_corners'],
                stats['home_yellow'], stats['away_yellow'],
                stats['home_red'], stats['away_red'],
                match_id
            ))
            return True
        except Exception as e:
            print(f'更新失败 {match_id}: {e}')
            return False

    def import_all(self, limit: int = None) -> Dict:
        """导入所有StatsBomb数据"""
        files = list(self.statsbomb_dir.glob('*.json'))
        if limit:
            files = files[:limit]

        results = {
            'total_files': len(files),
            'extracted': 0,
            'matched_verified': 0,
            'matched_unverified': 0,
            'updated': 0,
            'errors': 0,
            'verified_details': [],
            'unverified_details': [],
        }

        # 先清除之前导入的数据
        self.cursor.execute('''
            UPDATE matches SET
                home_xg = NULL, away_xg = NULL,
                home_shots = NULL, away_shots = NULL,
                home_possession = NULL, away_possession = NULL
            WHERE source LIKE '%statsbomb%'
        ''')
        self.conn.commit()

        for i, f in enumerate(files):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    events = json.load(fp)

                match_info = self.extract_match_info(events)
                if not match_info:
                    continue

                results['extracted'] += 1

                match_result = self.find_match_in_db(match_info)
                if not match_result:
                    continue

                match_id, verified = match_result

                if verified:
                    results['matched_verified'] += 1
                    results['verified_details'].append({
                        'file': f.stem,
                        'match_id': match_id,
                        'teams': f"{match_info['home_team']} vs {match_info['away_team']}",
                        'score': f"{match_info['home_goals']}-{match_info['away_goals']}",
                        'xg': f"{match_info['home_xg']} - {match_info['away_xg']}"
                    })
                else:
                    results['matched_unverified'] += 1
                    results['unverified_details'].append({
                        'file': f.stem,
                        'match_id': match_id,
                        'teams': f"{match_info['home_team']} vs {match_info['away_team']}",
                        'sb_score': f"{match_info['home_goals']}-{match_info['away_goals']}",
                        'xg': f"{match_info['home_xg']} - {match_info['away_xg']}"
                    })

                if self.update_match_stats(match_id, match_info):
                    results['updated'] += 1

                if (i + 1) % 500 == 0:
                    print(f'处理进度: {i + 1}/{len(files)}')
                    self.conn.commit()

            except Exception as e:
                results['errors'] += 1

        self.conn.commit()
        return results


def main():
    """主函数"""
    db_path = 'D:/football_tools/data/football_v2.db'
    statsbomb_dir = 'd:/football_tools/new_data/matches/clubs/leagues_backup/statsbomb_events'

    print('StatsBomb xG数据导入 (改进版 - 比分验证)')
    print('=' * 50)

    importer = StatsBombXGImporterV2(db_path, statsbomb_dir)
    importer.connect()

    try:
        print('\n开始导入...')
        results = importer.import_all(limit=None)

        print(f'\n导入结果:')
        print(f'  总文件数: {results["total_files"]}')
        print(f'  成功提取: {results["extracted"]}')
        print(f'  比分验证匹配: {results["matched_verified"]}')
        print(f'  未验证匹配: {results["matched_unverified"]}')
        print(f'  更新成功: {results["updated"]}')
        print(f'  错误数: {results["errors"]}')

        if results['verified_details']:
            print(f'\n比分验证匹配示例 (前5个):')
            for d in results['verified_details'][:5]:
                print(f'  {d["teams"]} ({d["score"]}): xG {d["xg"]}')

        if results['unverified_details']:
            print(f'\n未验证匹配示例 (前5个):')
            for d in results['unverified_details'][:5]:
                print(f'  {d["teams"]} (StatsBomb比分: {d["sb_score"]}): xG {d["xg"]}')

    finally:
        importer.close()


if __name__ == '__main__':
    main()