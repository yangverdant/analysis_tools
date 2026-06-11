"""
实时赔率模块

功能:
1. 从The Odds API获取实时赔率
2. 赔率变化追踪
3. 市场情绪分析
4. 最佳赔率比较

API文档: https://the-odds-api.com/
"""

import requests
import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import time


@dataclass
class OddsData:
    """赔率数据"""
    match_id: str
    home_team: str
    away_team: str
    commence_time: str
    bookmaker: str
    home_odds: float
    draw_odds: float
    away_odds: float
    updated_at: str


class LiveOddsAnalyzer:
    """实时赔率分析器"""

    # The Odds API配置
    API_KEY = "1cb8aeb78d1e7a0d975ebd3d6d77ee40"
    BASE_URL = "https://api.the-odds-api.com/v4"

    # 支持的足球联赛
    SOCCER_LEAGUES = {
        'premier_league': 'soccer_epl',
        'la_liga': 'soccer_spain_la_liga',
        'bundesliga': 'soccer_germany_bundesliga',
        'serie_a': 'soccer_italy_serie_a',
        'ligue_1': 'soccer_france_ligue_one',
        'champions_league': 'soccer_uefa_champs_league',
        'europa_league': 'soccer_uefa_europa_league',
        'world_cup': 'soccer_fifa_world_cup',
        'euro': 'soccer_uefa_euro'
    }

    # 主流博彩公司
    MAIN_BOOKMAKERS = ['bet365', 'pinnacle', 'williamhill', 'betvictor', '1xbet']

    def __init__(self, db_path: str, api_key: str = None):
        self.db_path = db_path
        self.api_key = api_key or self.API_KEY

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'

        self.session = requests.Session()
        self.session.trust_env = False  # 不使用环境变量中的代理
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 缓存
        self.cache = {}
        self.cache_duration = 300  # 5分钟缓存

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_upcoming_odds(
        self,
        league: str = None,
        bookmakers: List[str] = None
    ) -> List[Dict]:
        """
        获取即将开始的比赛赔率

        Args:
            league: 联赛代码 (如 'soccer_epl')
            bookmakers: 博彩公司列表

        Returns:
            比赛赔率列表
        """
        cache_key = f"odds_{league}_{','.join(bookmakers or [])}"

        # 检查缓存
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_duration:
                return cached['data']

        try:
            # 构建URL
            if league:
                url = f"{self.BASE_URL}/sports/{league}/odds/"
            else:
                url = f"{self.BASE_URL}/sports/soccer/odds/"

            params = {
                'apiKey': self.api_key,
                'regions': 'uk,eu,us',  # 英国、欧洲、美国
                'markets': 'h2h',  # 胜平负
                'oddsFormat': 'decimal',  # 小数赔率
            }

            if bookmakers:
                params['bookmakers'] = ','.join(bookmakers)

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                self.cache[cache_key] = {
                    'timestamp': time.time(),
                    'data': data
                }
                return data
            else:
                print(f"API错误: {response.status_code}")
                return []

        except Exception as e:
            print(f"获取赔率失败: {e}")
            return []

    def get_best_odds(self, odds_list: List[Dict]) -> Dict:
        """
        获取最佳赔率

        从多个博彩公司中找出每个市场的最高赔率
        """
        if not odds_list:
            return {}

        best_home = {'odds': 0, 'bookmaker': ''}
        best_draw = {'odds': 0, 'bookmaker': ''}
        best_away = {'odds': 0, 'bookmaker': ''}

        for bookmaker_data in odds_list:
            bookmaker = bookmaker_data.get('title', '')
            markets = bookmaker_data.get('markets', [])

            for market in markets:
                if market.get('key') == 'h2h':
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        if outcome.get('name') == 'Home' or outcome.get('name') == bookmaker_data.get('home_team'):
                            if outcome.get('price', 0) > best_home['odds']:
                                best_home = {'odds': outcome['price'], 'bookmaker': bookmaker}
                        elif outcome.get('name') == 'Draw':
                            if outcome.get('price', 0) > best_draw['odds']:
                                best_draw = {'odds': outcome['price'], 'bookmaker': bookmaker}
                        elif outcome.get('name') == 'Away' or outcome.get('name') == bookmaker_data.get('away_team'):
                            if outcome.get('price', 0) > best_away['odds']:
                                best_away = {'odds': outcome['price'], 'bookmaker': bookmaker}

        return {
            'home': best_home,
            'draw': best_draw,
            'away': best_away
        }

    def calculate_implied_probabilities(self, odds: Dict) -> Dict:
        """
        计算隐含概率

        隐含概率 = 1 / 赔率
        """
        home_prob = 1 / odds.get('home', 1) if odds.get('home') else 0
        draw_prob = 1 / odds.get('draw', 1) if odds.get('draw') else 0
        away_prob = 1 / odds.get('away', 1) if odds.get('away') else 0

        # 计算庄家利润率
        total_implied = home_prob + draw_prob + away_prob
        margin = total_implied - 1

        # 去除利润后的真实概率
        if total_implied > 0:
            true_home = home_prob / total_implied
            true_draw = draw_prob / total_implied
            true_away = away_prob / total_implied
        else:
            true_home = true_draw = true_away = 0

        return {
            'implied': {
                'home': round(home_prob * 100, 1),
                'draw': round(draw_prob * 100, 1),
                'away': round(away_prob * 100, 1)
            },
            'true_probability': {
                'home': round(true_home * 100, 1),
                'draw': round(true_draw * 100, 1),
                'away': round(true_away * 100, 1)
            },
            'bookmaker_margin': round(margin * 100, 1)
        }

    def analyze_odds_movement(
        self,
        match_id: str,
        conn: sqlite3.Connection = None
    ) -> Dict:
        """
        分析赔率变化

        比较当前赔率与历史赔率
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取历史赔率
        cursor.execute("""
            SELECT
                bookmaker,
                home as home_odds,
                draw as draw_odds,
                away as away_odds,
                captured_at as updated_at
            FROM match_odds_normalized
            WHERE match_id = ? AND market = '1X2'
            ORDER BY captured_at DESC
        """, (match_id,))

        history = cursor.fetchall()

        if len(history) < 2:
            return {
                'has_movement': False,
                'message': '赔率数据不足，无法分析变化'
            }

        # 比较最新和之前的赔率
        latest = history[0]
        previous = history[1]

        home_change = latest['home_odds'] - previous['home_odds']
        draw_change = latest['draw_odds'] - previous['draw_odds']
        away_change = latest['away_odds'] - previous['away_odds']

        # 分析变化趋势
        def interpret_change(change: float) -> str:
            if change > 0.1:
                return '上升明显'
            elif change > 0.02:
                return '小幅上升'
            elif change < -0.1:
                return '下降明显'
            elif change < -0.02:
                return '小幅下降'
            else:
                return '基本持平'

        return {
            'has_movement': True,
            'latest_update': latest['updated_at'],
            'previous_update': previous['updated_at'],
            'changes': {
                'home': {
                    'change': round(home_change, 3),
                    'trend': interpret_change(home_change)
                },
                'draw': {
                    'change': round(draw_change, 3),
                    'trend': interpret_change(draw_change)
                },
                'away': {
                    'change': round(away_change, 3),
                    'trend': interpret_change(away_change)
                }
            },
            'market_sentiment': self._analyze_market_sentiment(home_change, away_change)
        }

    def _analyze_market_sentiment(self, home_change: float, away_change: float) -> str:
        """分析市场情绪"""
        if home_change < -0.05 and away_change > 0.05:
            return '市场看好主队，主胜赔率下降'
        elif home_change > 0.05 and away_change < -0.05:
            return '市场看好客队，客胜赔率下降'
        elif home_change < -0.03 and away_change < -0.03:
            return '市场预期平局可能性增加'
        else:
            return '市场情绪稳定'

    def save_odds_to_db(
        self,
        match_id: str,
        bookmaker: str,
        home_odds: float,
        draw_odds: float,
        away_odds: float,
        conn: sqlite3.Connection = None
    ) -> bool:
        """保存赔率到数据库"""
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO match_odds_normalized
                (match_id, bookmaker, snapshot_type, market, home, draw, away, captured_at, source)
                VALUES (?, ?, 'live', '1X2', ?, ?, ?, ?, ?)
            """, (
                match_id,
                bookmaker,
                home_odds,
                draw_odds,
                away_odds,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'live_api'
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"保存赔率失败: {e}")
            return False

    def get_api_usage(self) -> Dict:
        """获取API使用情况"""
        try:
            # 发送一个简单请求获取使用情况
            url = f"{self.BASE_URL}/sports/"
            params = {'apiKey': self.api_key}

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                # 从响应头获取使用情况
                used = response.headers.get('x-requests-used', '0')
                remaining = response.headers.get('x-requests-remaining', '0')

                return {
                    'requests_used': int(used),
                    'requests_remaining': int(remaining),
                    'status': 'active'
                }
            else:
                return {
                    'status': 'error',
                    'code': response.status_code
                }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    def sync_upcoming_odds(self, league: str = None) -> int:
        """
        同步即将开始的比赛赔率

        Returns:
            更新的比赛数量
        """
        odds_data = self.get_upcoming_odds(league)

        if not odds_data:
            return 0

        conn = self.get_connection()
        cursor = conn.cursor()
        updated = 0

        for match in odds_data:
            try:
                home_team = match.get('home_team')
                away_team = match.get('away_team')
                commence_time = match.get('commence_time')

                # 查找对应的match_id
                cursor.execute("""
                    SELECT match_id FROM matches
                    WHERE (home_team_id IN (SELECT team_id FROM teams WHERE name_en = ?)
                    AND away_team_id IN (SELECT team_id FROM teams WHERE name_en = ?))
                    AND match_date = DATE(?)
                """, (home_team, away_team, commence_time[:10]))

                result = cursor.fetchone()
                if result:
                    match_id = result['match_id']

                    # 保存每个博彩公司的赔率
                    for bookmaker in match.get('bookmakers', []):
                        for market in bookmaker.get('markets', []):
                            if market.get('key') == 'h2h':
                                outcomes = market.get('outcomes', [])
                                home_odds = draw_odds = away_odds = None

                                for outcome in outcomes:
                                    name = outcome.get('name')
                                    if name == 'Home' or name == home_team:
                                        home_odds = outcome.get('price')
                                    elif name == 'Draw':
                                        draw_odds = outcome.get('price')
                                    elif name == 'Away' or name == away_team:
                                        away_odds = outcome.get('price')

                                if home_odds and draw_odds and away_odds:
                                    self.save_odds_to_db(
                                        match_id,
                                        bookmaker.get('title'),
                                        home_odds,
                                        draw_odds,
                                        away_odds,
                                        conn
                                    )
                                    updated += 1

            except Exception as e:
                print(f"处理比赛失败: {e}")
                continue

        conn.close()
        return updated


def main():
    """测试实时赔率模块"""
    db_path = r"d:\football_tools\data\football_v2.db"
    analyzer = LiveOddsAnalyzer(db_path)

    print("实时赔率模块测试")
    print("=" * 60)

    # 检查API使用情况
    print("\n[API使用情况]")
    usage = analyzer.get_api_usage()
    print(f"  已使用: {usage.get('requests_used', 'N/A')}")
    print(f"  剩余: {usage.get('requests_remaining', 'N/A')}")

    # 获取英超赔率
    print("\n[获取英超赔率]")
    odds = analyzer.get_upcoming_odds('soccer_epl')
    print(f"  获取到 {len(odds)} 场比赛")

    if odds:
        match = odds[0]
        print(f"  示例: {match.get('home_team')} vs {match.get('away_team')}")
        print(f"  开始时间: {match.get('commence_time')}")

        # 获取最佳赔率
        best = analyzer.get_best_odds(match.get('bookmakers', []))
        print(f"  最佳赔率: 主{best.get('home', {}).get('odds')} / 平{best.get('draw', {}).get('odds')} / 客{best.get('away', {}).get('odds')}")


if __name__ == "__main__":
    main()
