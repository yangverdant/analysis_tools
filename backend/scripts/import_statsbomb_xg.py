"""
StatsBomb xG数据导入脚本
从StatsBomb事件文件中提取xG数据并更新到数据库
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import re


class StatsBombXGImporter:
    """StatsBomb xG数据导入器"""

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
        # 直接映射
        if name in self.TEAM_NAME_MAPPING:
            return self.TEAM_NAME_MAPPING[name]

        # 移除特殊字符
        normalized = name.replace('FC', '').replace('CF', '').strip()

        # 检查部分匹配
        for key, value in self.TEAM_NAME_MAPPING.items():
            if key in name or name in key:
                return value

        return name

    def extract_match_info(self, events: List[Dict]) -> Optional[Dict]:
        """从StatsBomb事件中提取比赛信息"""
        # 获取首发阵容信息
        starting_xi = [e for e in events if e.get('type', {}).get('name') == 'Starting XI']

        if len(starting_xi) < 2:
            return None

        home_team = starting_xi[0].get('team', {}).get('name')
        away_team = starting_xi[1].get('team', {}).get('name')

        if not home_team or not away_team:
            return None

        # 提取射门事件
        shots = [e for e in events if e.get('type', {}).get('name') == 'Shot']

        # 计算xG
        home_xg = 0.0
        away_xg = 0.0
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
                if outcome in ['Saved', 'Goal']:
                    home_shots_target += 1
            else:
                away_xg += xg
                away_shots += 1
                if outcome in ['Saved', 'Goal']:
                    away_shots_target += 1

        # 提取其他统计
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

    def find_match_in_db(self, match_info: Dict) -> Optional[str]:
        """在数据库中查找对应的比赛"""
        home_team = match_info['home_team']
        away_team = match_info['away_team']

        # 使用LIKE模糊匹配球队名
        query = '''
            SELECT m.match_id, m.match_date, t1.name_en, t2.name_en,
                   m.home_xg, m.away_xg, m.home_shots, m.away_shots
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.team_id
            JOIN teams t2 ON m.away_team_id = t2.team_id
            WHERE (t1.name_en LIKE ? OR t1.name_cn LIKE ?)
              AND (t2.name_en LIKE ? OR t2.name_cn LIKE ?)
              AND m.home_xg IS NULL
            ORDER BY m.match_date DESC
            LIMIT 1
        '''

        self.cursor.execute(query, (
            f'%{home_team}%', f'%{home_team}%',
            f'%{away_team}%', f'%{away_team}%'
        ))

        result = self.cursor.fetchone()
        if result:
            return result[0]  # 返回match_id
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
            'matched': 0,
            'updated': 0,
            'errors': 0,
            'details': []
        }

        for i, f in enumerate(files):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    events = json.load(fp)

                # 提取比赛信息
                match_info = self.extract_match_info(events)
                if not match_info:
                    continue

                results['extracted'] += 1

                # 查找数据库中的比赛
                match_id = self.find_match_in_db(match_info)
                if not match_id:
                    continue

                results['matched'] += 1

                # 更新数据
                if self.update_match_stats(match_id, match_info):
                    results['updated'] += 1
                    results['details'].append({
                        'file': f.stem,
                        'match_id': match_id,
                        'teams': f"{match_info['home_team']} vs {match_info['away_team']}",
                        'xg': f"{match_info['home_xg']} - {match_info['away_xg']}"
                    })

                if (i + 1) % 100 == 0:
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

    print('StatsBomb xG数据导入')
    print('=' * 50)

    importer = StatsBombXGImporter(db_path, statsbomb_dir)
    importer.connect()

    try:
        # 导入所有文件
        print('\\n开始导入...')
        results = importer.import_all(limit=None)

        print(f'\\n导入结果:')
        print(f'  总文件数: {results["total_files"]}')
        print(f'  成功提取: {results["extracted"]}')
        print(f'  匹配比赛: {results["matched"]}')
        print(f'  更新成功: {results["updated"]}')
        print(f'  错误数: {results["errors"]}')

        if results['details']:
            print(f'\\n前5个更新示例:')
            for d in results['details'][:5]:
                print(f'  {d["teams"]}: xG {d["xg"]}')

    finally:
        importer.close()


if __name__ == '__main__':
    main()
