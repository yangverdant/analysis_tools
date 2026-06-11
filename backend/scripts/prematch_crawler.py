"""
赛前资讯爬虫 - 获取比赛前瞻、阵容预测、伤病名单

数据来源:
1. 直播吧赛前分析
2. 188比分阵容预测
3. 各联赛官方伤病名单

入库表: team_news, player_status, match_preview_analysis
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class PreMatchCrawler:
    """赛前资讯爬虫"""

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        self.session.trust_env = False  # 不使用环境变量中的代理

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== 直播吧赛前分析 ====================

    def crawl_zhibo8_preview(self, match_id: str) -> Dict:
        """爬取直播吧比赛前瞻"""
        preview = {
            'match_id': match_id,
            'home_injuries': [],
            'away_injuries': [],
            'home_lineup': [],
            'away_lineup': [],
            'analysis': '',
            'source': 'zhibo8'
        }

        try:
            # 直播吧比赛详情页
            url = f"https://www.zhibo8.cc/match/{match_id}.htm"
            resp = self.session.get(url, timeout=15, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找伤病信息
            injury_section = soup.select_one('.injury-list, .伤病名单')
            if injury_section:
                items = injury_section.select('li')
                for item in items:
                    player_name = item.select_one('.player-name')
                    injury_type = item.select_one('.injury-type')
                    if player_name:
                        preview['home_injuries'].append({
                            'player': player_name.get_text(strip=True),
                            'type': injury_type.get_text(strip=True) if injury_type else ''
                        })

            # 查找阵容预测
            lineup_section = soup.select_one('.lineup-prediction, .阵容预测')
            if lineup_section:
                home_lineup = lineup_section.select_one('.home-lineup')
                away_lineup = lineup_section.select_one('.away-lineup')

                if home_lineup:
                    for player in home_lineup.select('.player'):
                        preview['home_lineup'].append(player.get_text(strip=True))

                if away_lineup:
                    for player in away_lineup.select('.player'):
                        preview['away_lineup'].append(player.get_text(strip=True))

            # 查找比赛分析
            analysis_section = soup.select_one('.match-analysis, .比赛分析')
            if analysis_section:
                preview['analysis'] = analysis_section.get_text(strip=True)

        except Exception as e:
            print(f"直播吧前瞻爬取失败: {e}")

        return preview

    def crawl_zhibo8_today_matches(self) -> List[Dict]:
        """爬取直播吧今日比赛列表"""
        matches = []

        try:
            # 使用直播吧数据接口
            url = "https://www.zhibo8.cc/zuqiu/"
            resp = self.session.get(url, timeout=15, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找所有链接
            links = soup.find_all('a', href=True)
            print(f"直播吧: 找到 {len(links)} 个链接")

            for link in links:
                href = link.get('href', '')
                title = link.get('title', '') or link.get_text(strip=True)

                # 匹配比赛链接格式
                if '/match/' in href or '/video/' in href:
                    match_id = ''
                    id_match = re.search(r'/match/(\d+)', href)
                    if id_match:
                        match_id = id_match.group(1)

                    if title and len(title) > 5:
                        # 尝试从标题解析球队
                        vs_match = re.search(r'(.+?)\s*(?:vs|VS|对阵|迎战)\s*(.+)', title)
                        if vs_match:
                            matches.append({
                                'match_id': match_id,
                                'home_team': vs_match.group(1).strip(),
                                'away_team': vs_match.group(2).strip(),
                                'time': '',
                                'league': '',
                                'url': href
                            })

        except Exception as e:
            print(f"直播吧比赛列表爬取失败: {e}")

        return matches

    # ==================== 188比分阵容预测 ====================

    def crawl_188bifen_lineups(self) -> List[Dict]:
        """爬取188比分阵容预测"""
        lineups = []

        try:
            url = "https://www.188bifen.com/lineup/"
            resp = self.session.get(url, timeout=15, proxies={'http': None, 'https': None})
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找阵容预测列表
            lineup_items = soup.select('.lineup-item, .match-lineup')
            print(f"188比分: 找到 {len(lineup_items)} 场阵容预测")

            for item in lineup_items[:20]:
                try:
                    home_team = item.select_one('.home-team, .team-home')
                    away_team = item.select_one('.away-team, .team-away')

                    home_players = []
                    away_players = []

                    home_list = item.select_one('.home-lineup')
                    if home_list:
                        for p in home_list.select('.player'):
                            home_players.append(p.get_text(strip=True))

                    away_list = item.select_one('.away-lineup')
                    if away_list:
                        for p in away_list.select('.player'):
                            away_players.append(p.get_text(strip=True))

                    if home_team and away_team:
                        lineups.append({
                            'home_team': home_team.get_text(strip=True),
                            'away_team': away_team.get_text(strip=True),
                            'home_lineup': home_players,
                            'away_lineup': away_players,
                            'source': '188bifen'
                        })

                except Exception:
                    continue

        except Exception as e:
            print(f"188比分阵容爬取失败: {e}")

        return lineups

    # ==================== 官方伤病名单 ====================

    def crawl_premier_league_injuries(self) -> List[Dict]:
        """爬取英超官方伤病名单"""
        injuries = []

        try:
            # 英超官网伤病页面
            url = "https://www.premierleague.com/injuries"
            resp = self.session.get(url, timeout=20, proxies={'http': None, 'https': None})
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 解析伤病表格
            rows = soup.select('.injuryTable tbody tr, .table tbody tr')
            print(f"英超官网: 找到 {len(rows)} 条伤病信息")

            for row in rows:
                try:
                    cols = row.select('td')
                    if len(cols) >= 3:
                        player = cols[0].get_text(strip=True)
                        team = cols[1].get_text(strip=True)
                        injury_type = cols[2].get_text(strip=True) if len(cols) > 2 else ''
                        return_date = cols[3].get_text(strip=True) if len(cols) > 3 else ''

                        injuries.append({
                            'player': player,
                            'team': team,
                            'injury_type': injury_type,
                            'return_date': return_date,
                            'league': 'Premier League',
                            'source': 'premier_league_official',
                            'date': datetime.now().strftime('%Y-%m-%d')
                        })

                except Exception:
                    continue

        except Exception as e:
            print(f"英超伤病爬取失败: {e}")

        return injuries

    def crawl_laliga_injuries(self) -> List[Dict]:
        """爬取西甲官方伤病名单"""
        injuries = []

        try:
            url = "https://www.laliga.com/en-GB/injuries"
            resp = self.session.get(url, timeout=20, proxies={'http': None, 'https': None})
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 解析伤病信息
            items = soup.select('.injury-item, .player-injury')
            print(f"西甲官网: 找到 {len(items)} 条伤病信息")

            for item in items:
                try:
                    player = item.select_one('.player-name, .name')
                    team = item.select_one('.team-name, .team')
                    injury_type = item.select_one('.injury-type, .type')

                    if player and team:
                        injuries.append({
                            'player': player.get_text(strip=True),
                            'team': team.get_text(strip=True),
                            'injury_type': injury_type.get_text(strip=True) if injury_type else '',
                            'league': 'La Liga',
                            'source': 'laliga_official',
                            'date': datetime.now().strftime('%Y-%m-%d')
                        })

                except Exception:
                    continue

        except Exception as e:
            print(f"西甲伤病爬取失败: {e}")

        return injuries

    # ==================== 数据入库 ====================

    def save_injuries_to_db(self, injuries: List[Dict]) -> int:
        """保存伤病数据到数据库"""
        conn = self.get_connection()
        cursor = conn.cursor()

        saved_count = 0
        for injury in injuries:
            try:
                # 查找球队ID
                cursor.execute("""
                    SELECT team_id FROM teams
                    WHERE name_en LIKE ? OR name_cn LIKE ?
                """, (f"%{injury['team']}%", f"%{injury['team']}%"))
                team_row = cursor.fetchone()

                if not team_row:
                    continue

                team_id = team_row['team_id']

                # 查找球员ID
                cursor.execute("""
                    SELECT player_id FROM players
                    WHERE team_id = ? AND (name_en LIKE ? OR name_cn LIKE ?)
                """, (team_id, f"%{injury['player']}%", f"%{injury['player']}%"))
                player_row = cursor.fetchone()

                player_id = player_row['player_id'] if player_row else None

                # 更新球员状态
                if player_id:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_status
                        (player_id, team_id, status, injury_type, source, updated_at)
                        VALUES (?, ?, 'injured', ?, ?, CURRENT_TIMESTAMP)
                    """, (player_id, team_id, injury['injury_type'], injury['source']))

                # 插入team_news
                cursor.execute("""
                    INSERT INTO team_news
                    (team_id, title, news_type, category, impact_level, news_date, source, verified)
                    VALUES (?, ?, 'injury', 'negative', 3, ?, ?, 1)
                """, (
                    team_id,
                    f"{injury['player']}因{injury['injury_type']}缺阵",
                    injury['date'],
                    injury['source']
                ))

                saved_count += 1

            except Exception:
                continue

        conn.commit()
        conn.close()
        return saved_count

    def save_lineups_to_db(self, lineups: List[Dict]) -> int:
        """保存阵容预测到数据库"""
        conn = self.get_connection()
        cursor = conn.cursor()

        saved_count = 0
        for lineup in lineups:
            try:
                # 查找比赛
                cursor.execute("""
                    SELECT match_id, home_team_id, away_team_id FROM matches
                    WHERE home_team_id IN (SELECT team_id FROM teams WHERE name_en LIKE ? OR name_cn LIKE ?)
                    AND away_team_id IN (SELECT team_id FROM teams WHERE name_en LIKE ? OR name_cn LIKE ?)
                    AND match_date >= date('now')
                    ORDER BY match_date LIMIT 1
                """, (f"%{lineup['home_team']}%", f"%{lineup['home_team']}%",
                      f"%{lineup['away_team']}%", f"%{lineup['away_team']}%"))

                match = cursor.fetchone()
                if not match:
                    continue

                # 更新match_preview_analysis
                cursor.execute("""
                    INSERT OR REPLACE INTO match_preview_analysis
                    (match_id, home_predicted_lineup, away_predicted_lineup, source, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    match['match_id'],
                    json.dumps(lineup['home_lineup'], ensure_ascii=False),
                    json.dumps(lineup['away_lineup'], ensure_ascii=False),
                    lineup['source']
                ))

                saved_count += 1

            except Exception:
                continue

        conn.commit()
        conn.close()
        return saved_count

    # ==================== 主运行函数 ====================

    def run(self, crawl_injuries: bool = True, crawl_lineups: bool = True):
        """运行爬虫"""
        print("=" * 60)
        print("赛前资讯爬虫启动")
        print("=" * 60)

        total_saved = 0

        # 1. 今日比赛列表
        print("\n[1] 爬取今日比赛列表...")
        matches = self.crawl_zhibo8_today_matches()
        print(f"    获取 {len(matches)} 场比赛")

        # 2. 官方伤病名单
        if crawl_injuries:
            print("\n[2] 爬取英超伤病名单...")
            pl_injuries = self.crawl_premier_league_injuries()
            if pl_injuries:
                saved = self.save_injuries_to_db(pl_injuries)
                print(f"    保存 {saved} 条伤病信息")
                total_saved += saved

            print("\n[3] 爬取西甲伤病名单...")
            laliga_injuries = self.crawl_laliga_injuries()
            if laliga_injuries:
                saved = self.save_injuries_to_db(laliga_injuries)
                print(f"    保存 {saved} 条伤病信息")
                total_saved += saved

        # 3. 阵容预测
        if crawl_lineups:
            print("\n[4] 爬取阵容预测...")
            lineups = self.crawl_188bifen_lineups()
            if lineups:
                saved = self.save_lineups_to_db(lineups)
                print(f"    保存 {saved} 场阵容预测")
                total_saved += saved

        print(f"\n总计保存 {total_saved} 条数据")
        return total_saved


def main():
    db_path = r"d:\football_tools\data\football_v2.db"
    crawler = PreMatchCrawler(db_path)
    crawler.run()


if __name__ == "__main__":
    main()
