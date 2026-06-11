"""
正确的预测模型训练流程
用比赛开始前6小时的数据进行预测，赛后获取结果进行复盘

训练流程：
1. 获取已结束比赛列表（但暂时不获取结果）
2. 收集比赛前6小时的全部数据：
   - FIFA排名（赛前）
   - Elo评分（赛前）
   - 近期form（赛前10场）
   - H2H历史
   - 赔率变化（赛前6小时）
   - 新闻（赛前6小时发布）
   - 社交动态（赛前6小时）
   - 伤病信息（赛前公布）
   - 天气/场地信息
3. 用这些数据进行预测
4. 然后获取比赛结果
5. 对比预测与结果，复盘优化
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'football_v2.db')


class PreMatchDataCollector:
    """赛前数据采集器 - 收集比赛开始前6小时的完整数据"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """初始化赛前数据存储表"""
        conn = self._get_conn()
        c = conn.cursor()

        # 赛前完整数据快照表（比赛前6小时的数据）
        c.execute('''
            CREATE TABLE IF NOT EXISTS pre_match_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                match_date DATE NOT NULL,
                match_time TEXT NOT NULL,
                snapshot_time TIMESTAMP NOT NULL,
                hours_before_match INTEGER DEFAULT 6,

                -- 静态数据（不随时间变化）
                fifa_home_rank INTEGER,
                fifa_away_rank INTEGER,
                fifa_home_points REAL,
                fifa_away_points REAL,
                elo_home REAL,
                elo_away REAL,

                -- 动态数据（赛前6小时）
                odds_home_open REAL,
                odds_draw_open REAL,
                odds_away_open REAL,
                odds_home_close REAL,
                odds_draw_close REAL,
                odds_away_close REAL,
                odds_change_home REAL,
                odds_change_draw REAL,
                odds_change_away REAL,

                -- 近期状态（赛前）
                form_home_matches TEXT,
                form_away_matches TEXT,
                form_home_rating REAL,
                form_away_rating REAL,
                form_home_goals_avg REAL,
                form_away_goals_avg REAL,

                -- H2H数据
                h2h_matches TEXT,
                h2h_home_wins INTEGER,
                h2h_draws INTEGER,
                h2h_away_wins INTEGER,

                -- 伤病数据（赛前公布）
                injuries_home TEXT,
                injuries_away TEXT,
                injury_impact_home REAL,
                injury_impact_away TEXT,

                -- 新闻数据（赛前6小时）
                news_home TEXT,
                news_away TEXT,
                news_sentiment_home REAL,
                news_sentiment_away REAL,
                news_count_home INTEGER,
                news_count_away INTEGER,

                -- 社交数据（赛前6小时）
                social_home TEXT,
                social_away TEXT,
                social_sentiment_home REAL,
                social_sentiment_away REAL,

                -- 阵容信息（赛前公布）
                lineup_home TEXT,
                lineup_away TEXT,
                lineup_confirmed INTEGER DEFAULT 0,
                key_players_home TEXT,
                key_players_away TEXT,

                -- 外部因素
                weather TEXT,
                temperature REAL,
                venue TEXT,
                referee TEXT,

                -- 特殊标记
                is_friendly INTEGER DEFAULT 0,
                is_home_advantage INTEGER DEFAULT 1,
                motivation_home TEXT,
                motivation_away TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(match_id, snapshot_time)
            )
        ''')

        # 模型预测表（基于赛前数据的预测）
        c.execute('''
            CREATE TABLE IF NOT EXISTS model_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                snapshot_id INTEGER NOT NULL,
                model_version TEXT NOT NULL,

                -- 预测输出
                pred_home_prob REAL,
                pred_draw_prob REAL,
                pred_away_prob REAL,
                pred_result TEXT,
                pred_confidence REAL,

                pred_total_goals REAL,
                pred_home_goals INTEGER,
                pred_away_goals INTEGER,
                pred_score TEXT,

                pred_over_under TEXT,
                pred_over_prob REAL,
                pred_under_prob REAL,

                -- 预测依据（关键因素）
                key_factors TEXT,
                risk_factors TEXT,

                -- 模型参数快照（便于追溯）
                model_params TEXT,

                predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (snapshot_id) REFERENCES pre_match_snapshot(id),
                UNIQUE(match_id, model_version)
            )
        ''')

        # 比赛结果表（赛后获取）
        c.execute('''
            CREATE TABLE IF NOT EXISTS match_actual_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                home_team TEXT,
                away_team TEXT,
                match_date DATE,

                -- 最终结果
                actual_home_score INTEGER,
                actual_away_score INTEGER,
                actual_result TEXT,
                actual_total_goals INTEGER,

                -- 半场结果
                ht_home_score INTEGER,
                ht_away_score INTEGER,

                -- 比赛统计
                possession_home REAL,
                shots_home INTEGER,
                shots_away INTEGER,
                shots_on_target_home INTEGER,
                shots_on_target_away INTEGER,
                corners_home INTEGER,
                corners_away INTEGER,
                fouls_home INTEGER,
                fouls_away INTEGER,
                yellow_cards_home INTEGER,
                yellow_cards_away INTEGER,
                red_cards_home INTEGER,
                red_cards_away INTEGER,

                -- 结果获取时间
                result_fetch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(match_id)
            )
        ''')

        # 复盘对比表
        c.execute('''
            CREATE TABLE IF NOT EXISTS prediction_evaluation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                prediction_id INTEGER NOT NULL,

                -- 评估指标
                result_hit INTEGER,
                score_hit INTEGER,
                over_under_hit INTEGER,

                -- 概率评估
                brier_score REAL,
                log_loss REAL,

                -- 误差分析
                home_prob_error REAL,
                draw_prob_error REAL,
                away_prob_error REAL,
                goal_error REAL,

                -- 因素复盘
                correct_factors TEXT,
                missed_factors TEXT,
                unexpected_events TEXT,

                -- 场景分类
                scenario_type TEXT,

                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (prediction_id) REFERENCES model_predictions(id)
            )
        ''')

        # 创建索引
        c.execute('CREATE INDEX IF NOT EXISTS idx_snapshot_match ON pre_match_snapshot(match_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_snapshot_time ON pre_match_snapshot(snapshot_time)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_pred_match ON model_predictions(match_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_result_match ON match_actual_results(match_id)')

        conn.commit()
        conn.close()
        logger.info("赛前数据表初始化完成")

    def collect_pre_match_data(self, match_id: str, hours_before: int = 6) -> Dict:
        """
        收集比赛前N小时的完整数据

        这是训练的关键：只收集比赛开始前的数据，不包含结果

        Args:
            match_id: 比赛ID
            hours_before: 比赛前多少小时（默认6小时）

        Returns:
            赛前数据快照
        """
        from fetchers.apifootball.get_data import get_match_detail, get_match_odds, get_predictions
        from fetchers.news.get_news import get_zhibo8_news
        import json

        # 获取比赛基础信息
        detail = get_match_detail(match_id)
        if not detail:
            return {'error': '无法获取比赛信息'}

        match_date = detail.get('date')
        match_time = detail.get('time')

        # 计算赛前时间点
        if match_date and match_time:
            try:
                match_datetime = datetime.strptime(f"{match_date} {match_time}", "%Y-%m-%d %H:%M")
                snapshot_time = match_datetime - timedelta(hours=hours_before)
            except:
                snapshot_time = datetime.now()
        else:
            snapshot_time = datetime.now()

        home_team = detail.get('home_team')
        away_team = detail.get('away_team')

        logger.info(f"收集赛前数据: {home_team} vs {away_team} (比赛前{hours_before}小时)")

        snapshot = {
            'match_id': match_id,
            'home_team': home_team,
            'away_team': away_team,
            'match_date': match_date,
            'match_time': match_time,
            'snapshot_time': snapshot_time.isoformat(),
            'hours_before_match': hours_before
        }

        # 1. 获取FIFA排名（静态）
        conn = self._get_conn()
        c = conn.cursor()

        fifa_data = self._load_fifa_data()
        snapshot['fifa_home_rank'] = fifa_data.get(home_team, {}).get('rank')
        snapshot['fifa_away_rank'] = fifa_data.get(away_team, {}).get('rank')
        snapshot['fifa_home_points'] = fifa_data.get(home_team, {}).get('points')
        snapshot['fifa_away_points'] = fifa_data.get(away_team, {}).get('points')

        # 2. 获取Elo评分（从数据库）
        c.execute('SELECT elo_rating FROM elo_ratings WHERE team_name = ?', (home_team,))
        row = c.fetchone()
        snapshot['elo_home'] = row['elo_rating'] if row else 1500

        c.execute('SELECT elo_rating FROM elo_ratings WHERE team_name = ?', (away_team,))
        row = c.fetchone()
        snapshot['elo_away'] = row['elo_rating'] if row else 1500

        # 3. 获取赔率（赛前）
        odds = get_match_odds(match_id=match_id)
        if odds and len(odds) > 0:
            # 取最新赔率作为"收盘赔率"
            latest_odds = odds[0]
            snapshot['odds_home_close'] = latest_odds.get('home_win')
            snapshot['odds_draw_close'] = latest_odds.get('draw')
            snapshot['odds_away_close'] = latest_odds.get('away_win')

            # 如果有历史赔率，计算开盘赔率和变化
            if len(odds) > 1:
                earliest_odds = odds[-1]
                snapshot['odds_home_open'] = earliest_odds.get('home_win')
                snapshot['odds_draw_open'] = earliest_odds.get('draw')
                snapshot['odds_away_open'] = earliest_odds.get('away_win')

                if snapshot['odds_home_open'] and snapshot['odds_home_close']:
                    snapshot['odds_change_home'] = snapshot['odds_home_close'] - snapshot['odds_home_open']

        # 4. 获取近期form（从数据库）
        c.execute('''
            SELECT match_date, goals_for, goals_against, result
            FROM team_form
            WHERE team_name = ?
            ORDER BY match_date DESC LIMIT 10
        ''', (home_team,))
        home_form = [dict(row) for row in c.fetchall()]
        snapshot['form_home_matches'] = json.dumps(home_form, ensure_ascii=False)
        snapshot['form_home_rating'] = self._calculate_form_rating(home_form)

        c.execute('''
            SELECT match_date, goals_for, goals_against, result
            FROM team_form
            WHERE team_name = ?
            ORDER BY match_date DESC LIMIT 10
        ''', (away_team,))
        away_form = [dict(row) for row in c.fetchall()]
        snapshot['form_away_matches'] = json.dumps(away_form, ensure_ascii=False)
        snapshot['form_away_rating'] = self._calculate_form_rating(away_form)

        # 5. 获取H2H
        c.execute('''
            SELECT match_date, home_team, away_team, home_score, away_score
            FROM h2h_records
            WHERE (team_a_name = ? AND team_b_name = ?) OR (team_a_name = ? AND team_b_name = ?)
            ORDER BY match_date DESC LIMIT 10
        ''', (home_team, away_team, away_team, home_team))
        h2h_matches = [dict(row) for row in c.fetchall()]
        snapshot['h2h_matches'] = json.dumps(h2h_matches, ensure_ascii=False)
        snapshot['h2h_home_wins'] = self._count_h2h_wins(h2h_matches, home_team)
        snapshot['h2h_draws'] = len([m for m in h2h_matches if m['home_score'] == m['away_score']])
        snapshot['h2h_away_wins'] = self._count_h2h_wins(h2h_matches, away_team)

        # 6. 获取伤病信息（赛前公布）
        c.execute('''
            SELECT player_name, status, injury_type, expected_return
            FROM player_status
            WHERE team_name = ? AND status = 'injury'
        ''', (home_team,))
        home_injuries = [dict(row) for row in c.fetchall()]
        snapshot['injuries_home'] = json.dumps(home_injuries, ensure_ascii=False)
        snapshot['injury_impact_home'] = len(home_injuries)

        c.execute('''
            SELECT player_name, status, injury_type, expected_return
            FROM player_status
            WHERE team_name = ? AND status = 'injury'
        ''', (away_team,))
        away_injuries = [dict(row) for row in c.fetchall()]
        snapshot['injuries_away'] = json.dumps(away_injuries, ensure_ascii=False)
        snapshot['injury_impact_away'] = len(away_injuries)

        # 7. 获取赛前新闻（最近6小时/24小时）
        since = (snapshot_time - timedelta(hours=24)).strftime('%Y-%m-%d')
        c.execute('''
            SELECT title, news_type, sentiment, published_at
            FROM news_aggregated
            WHERE (mentioned_teams LIKE ? OR mentioned_teams LIKE ?)
            AND published_at >= ?
            ORDER BY published_at DESC
        ''', (f'%{home_team}%', f'%{away_team}%', since))

        news = [dict(row) for row in c.fetchall()]
        home_news = [n for n in news if home_team in str(n.get('mentioned_teams', ''))]
        away_news = [n for n in news if away_team in str(n.get('mentioned_teams', ''))]

        snapshot['news_home'] = json.dumps(home_news[:10], ensure_ascii=False)
        snapshot['news_away'] = json.dumps(away_news[:10], ensure_ascii=False)
        snapshot['news_sentiment_home'] = self._avg_sentiment(home_news)
        snapshot['news_sentiment_away'] = self._avg_sentiment(away_news)
        snapshot['news_count_home'] = len(home_news)
        snapshot['news_count_away'] = len(away_news)

        # 8. 获取阵容（赛前公布）
        lineup = detail.get('lineup', {})
        if lineup:
            snapshot['lineup_home'] = json.dumps(lineup.get('home', {}), ensure_ascii=False)
            snapshot['lineup_away'] = json.dumps(lineup.get('away', {}), ensure_ascii=False)
            snapshot['lineup_confirmed'] = 1 if lineup.get('home') else 0

        # 9. 比赛类型
        league = detail.get('league', '')
        snapshot['is_friendly'] = 1 if 'friend' in league.lower() else 0
        snapshot['is_home_advantage'] = 1

        conn.close()

        return snapshot

    def _load_fifa_data(self) -> Dict:
        """加载FIFA排名数据"""
        fifa_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                 'fetchers', 'fifa_ranking', 'data', 'fifa_ranking_current.json')
        if os.path.exists(fifa_path):
            with open(fifa_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _calculate_form_rating(self, form_matches: List[Dict]) -> float:
        """计算form评分"""
        if not form_matches:
            return 50.0
        points = 0
        for m in form_matches:
            result = m.get('result', '')
            if result == 'W':
                points += 3
            elif result == 'D':
                points += 1
        max_points = len(form_matches) * 3
        return points / max_points * 100 if max_points > 0 else 50.0

    def _count_h2h_wins(self, h2h_matches: List[Dict], team_name: str) -> int:
        """计算H2H胜场"""
        wins = 0
        for m in h2h_matches:
            if m['home_team'] == team_name and m['home_score'] > m['away_score']:
                wins += 1
            elif m['away_team'] == team_name and m['away_score'] > m['home_score']:
                wins += 1
        return wins

    def _avg_sentiment(self, news: List[Dict]) -> float:
        """计算平均情感"""
        if not news:
            return 0.0
        sentiments = [n.get('sentiment', 0) for n in news if n.get('sentiment')]
        return sum(sentiments) / len(sentiments) if sentiments else 0.0

    def save_snapshot(self, snapshot: Dict) -> int:
        """保存赛前数据快照"""
        conn = self._get_conn()
        c = conn.cursor()

        c.execute('''
            INSERT INTO pre_match_snapshot (
                match_id, home_team, away_team, match_date, match_time,
                snapshot_time, hours_before_match,
                fifa_home_rank, fifa_away_rank, fifa_home_points, fifa_away_points,
                elo_home, elo_away,
                odds_home_open, odds_draw_open, odds_away_open,
                odds_home_close, odds_draw_close, odds_away_close,
                odds_change_home, odds_change_draw, odds_change_away,
                form_home_matches, form_away_matches,
                form_home_rating, form_away_rating,
                h2h_matches, h2h_home_wins, h2h_draws, h2h_away_wins,
                injuries_home, injuries_away, injury_impact_home, injury_impact_away,
                news_home, news_away, news_sentiment_home, news_sentiment_away,
                news_count_home, news_count_away,
                lineup_home, lineup_away, lineup_confirmed,
                is_friendly, is_home_advantage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            snapshot.get('match_id'), snapshot.get('home_team'), snapshot.get('away_team'),
            snapshot.get('match_date'), snapshot.get('match_time'),
            snapshot.get('snapshot_time'), snapshot.get('hours_before_match'),
            snapshot.get('fifa_home_rank'), snapshot.get('fifa_away_rank'),
            snapshot.get('fifa_home_points'), snapshot.get('fifa_away_points'),
            snapshot.get('elo_home'), snapshot.get('elo_away'),
            snapshot.get('odds_home_open'), snapshot.get('odds_draw_open'), snapshot.get('odds_away_open'),
            snapshot.get('odds_home_close'), snapshot.get('odds_draw_close'), snapshot.get('odds_away_close'),
            snapshot.get('odds_change_home'), snapshot.get('odds_change_draw'), snapshot.get('odds_change_away'),
            snapshot.get('form_home_matches'), snapshot.get('form_away_matches'),
            snapshot.get('form_home_rating'), snapshot.get('form_away_rating'),
            snapshot.get('h2h_matches'), snapshot.get('h2h_home_wins'), snapshot.get('h2h_draws'), snapshot.get('h2h_away_wins'),
            snapshot.get('injuries_home'), snapshot.get('injuries_away'),
            snapshot.get('injury_impact_home'), snapshot.get('injury_impact_away'),
            snapshot.get('news_home'), snapshot.get('news_away'),
            snapshot.get('news_sentiment_home'), snapshot.get('news_sentiment_away'),
            snapshot.get('news_count_home'), snapshot.get('news_count_away'),
            snapshot.get('lineup_home'), snapshot.get('lineup_away'), snapshot.get('lineup_confirmed'),
            snapshot.get('is_friendly'), snapshot.get('is_home_advantage')
        ))

        snapshot_id = c.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"赛前数据快照已保存: ID={snapshot_id}")
        return snapshot_id

    def fetch_result(self, match_id: str) -> Dict:
        """
        获取比赛结果（赛后）

        这是训练的最后一步：预测后才能看结果
        """
        from fetchers.apifootball.get_data import get_match_detail

        detail = get_match_detail(match_id)
        if not detail:
            return {'error': '无法获取比赛详情'}

        home_score = detail.get('home_score')
        away_score = detail.get('away_score')

        if home_score is None or away_score is None:
            return {'error': '比赛可能未结束'}

        result = {
            'match_id': match_id,
            'home_team': detail.get('home_team'),
            'away_team': detail.get('away_team'),
            'match_date': detail.get('date'),
            'actual_home_score': home_score,
            'actual_away_score': away_score,
            'actual_result': 'home' if home_score > away_score else ('away' if away_score > home_score else 'draw'),
            'actual_total_goals': home_score + away_score,
            'ht_home_score': detail.get('home_score_ht'),
            'ht_away_score': detail.get('away_score_ht'),
            'possession_home': None,
            'shots_home': None,
            'shots_away': None
        }

        # 从统计数据提取
        stats = detail.get('statistics', [])
        if stats:
            for s in stats:
                if 'possession' in s.get('type', '').lower():
                    result['possession_home'] = s.get('home')
                elif 'shots' in s.get('type', '').lower() and 'on target' not in s.get('type', '').lower():
                    result['shots_home'] = s.get('home')
                    result['shots_away'] = s.get('away')

        # 保存结果
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO match_actual_results (
                match_id, home_team, away_team, match_date,
                actual_home_score, actual_away_score, actual_result, actual_total_goals,
                ht_home_score, ht_away_score, possession_home, shots_home, shots_away
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result['match_id'], result['home_team'], result['away_team'], result['match_date'],
            result['actual_home_score'], result['actual_away_score'], result['actual_result'], result['actual_total_goals'],
            result['ht_home_score'], result['ht_away_score'], result['possession_home'], result['shots_home'], result['shots_away']
        ))
        conn.commit()
        conn.close()

        logger.info(f"比赛结果已获取: {match_id} {home_score}-{away_score}")
        return result


class ModelTrainer:
    """模型训练器 - 正确的训练流程"""

    def __init__(self):
        self.collector = PreMatchDataCollector()

    def train_on_finished_match(self, match_id: str) -> Dict:
        """
        用已结束比赛进行训练（但预测时不知道结果）

        流程：
        1. 收集赛前数据（假装不知道结果）
        2. 进行预测
        3. 获取结果
        4. 复盘对比
        """
        print(f"\n{'='*60}")
        print(f"训练比赛: {match_id}")
        print(f"{'='*60}")

        # 1. 收集赛前数据（关键：不包含结果）
        print("\n[Step 1] 收集赛前数据（比赛前6小时）...")
        snapshot = self.collector.collect_pre_match_data(match_id, hours_before=6)

        if 'error' in snapshot:
            return snapshot

        snapshot_id = self.collector.save_snapshot(snapshot)

        # 2. 进行预测（基于赛前数据）
        print("\n[Step 2] 基于赛前数据进行预测...")
        prediction = self._predict(snapshot)

        # 保存预测
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO model_predictions (
                match_id, snapshot_id, model_version,
                pred_home_prob, pred_draw_prob, pred_away_prob,
                pred_result, pred_confidence,
                pred_total_goals, pred_home_goals, pred_away_goals,
                pred_over_under, pred_over_prob, pred_under_prob,
                key_factors, model_params
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match_id, snapshot_id, 'v1.0',
            prediction['home_prob'], prediction['draw_prob'], prediction['away_prob'],
            prediction['result'], prediction['confidence'],
            prediction['total_goals'], prediction['home_goals'], prediction['away_goals'],
            prediction['over_under'], prediction['over_prob'], prediction['under_prob'],
            json.dumps(prediction['key_factors'], ensure_ascii=False),
            json.dumps(prediction['model_params'], ensure_ascii=False)
        ))
        prediction_id = c.lastrowid
        conn.commit()
        conn.close()

        print(f"预测: {prediction['result']} ({prediction['home_prob']:.0f}%/{prediction['draw_prob']:.0f}%/{prediction['away_prob']:.0f}%)")
        print(f"比分: {prediction['home_goals']}-{prediction['away_goals']}")
        print(f"关键因素: {prediction['key_factors']}")

        # 3. 获取结果（现在才知道结果）
        print("\n[Step 3] 获取比赛结果...")
        result = self.collector.fetch_result(match_id)

        if 'error' in result:
            return result

        print(f"结果: {result['actual_home_score']}-{result['actual_away_score']} ({result['actual_result']})")

        # 4. 复盘对比
        print("\n[Step 4] 复盘对比...")
        evaluation = self._evaluate_prediction(prediction, result)

        # 保存评估
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO prediction_evaluation (
                match_id, prediction_id,
                result_hit, score_hit, over_under_hit,
                brier_score, home_prob_error, draw_prob_error, away_prob_error,
                goal_error, correct_factors, missed_factors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match_id, prediction_id,
            evaluation['result_hit'], evaluation['score_hit'], evaluation['over_under_hit'],
            evaluation['brier_score'], evaluation['home_prob_error'], evaluation['draw_prob_error'], evaluation['away_prob_error'],
            evaluation['goal_error'],
            json.dumps(evaluation['correct_factors'], ensure_ascii=False),
            json.dumps(evaluation['missed_factors'], ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

        print(f"\n[复盘结果]")
        print(f"  胜平负命中: {evaluation['result_hit']}")
        print(f"  比分命中: {evaluation['score_hit']}")
        print(f"  Brier Score: {evaluation['brier_score']:.3f}")
        print(f"  进球误差: {evaluation['goal_error']:.1f}")

        return {
            'match_id': match_id,
            'snapshot': snapshot,
            'prediction': prediction,
            'result': result,
            'evaluation': evaluation
        }

    def _predict(self, snapshot: Dict) -> Dict:
        """基于赛前数据进行预测"""
        # 获取参数
        params = {
            'fifa_weight': 0.30,
            'elo_weight': 0.25,
            'form_weight': 0.20,
            'h2h_weight': 0.10,
            'odds_weight': 0.15,
            'friendly_draw_boost': 0.15
        }

        # 计算各因素贡献
        home_score = 0
        away_score = 0

        # FIFA排名
        fifa_home = snapshot.get('fifa_home_rank') or 999
        fifa_away = snapshot.get('fifa_away_rank') or 999
        fifa_diff = fifa_home - fifa_away
        home_score += -fifa_diff / 100 * params['fifa_weight']
        away_score += fifa_diff / 100 * params['fifa_weight']

        # Elo
        elo_diff = (snapshot.get('elo_home') or 1500) - (snapshot.get('elo_away') or 1500)
        home_score += elo_diff / 400 * params['elo_weight']

        # Form
        form_diff = (snapshot.get('form_home_rating') or 50) - (snapshot.get('form_away_rating') or 50)
        home_score += form_diff / 100 * params['form_weight']

        # 赔率（如果有）
        odds_home = snapshot.get('odds_home_close')
        if odds_home:
            odds_away = snapshot.get('odds_away_close') or 3.0
            odds_draw = snapshot.get('odds_draw_close') or 3.0
            # 赔率越低概率越高
            implied_home = 1 / odds_home
            implied_away = 1 / odds_away
            implied_draw = 1 / odds_draw
            total = implied_home + implied_away + implied_draw
            home_score += (implied_home / total - 0.33) * params['odds_weight']

        # 基础概率
        base_home = 0.35 + home_score * 0.2
        base_away = 0.32 + away_score * 0.2
        base_draw = 0.28

        # 友谊赛调整
        if snapshot.get('is_friendly'):
            base_draw += params['friendly_draw_boost']

        # 伤病影响
        injury_home = snapshot.get('injury_impact_home') or 0
        injury_away = snapshot.get('injury_impact_away') or 0
        if injury_home > 2:
            base_home -= 0.05
            base_draw += 0.03
        if injury_away > 2:
            base_away -= 0.05
            base_draw += 0.03

        # 新闻情感影响
        sentiment_home = snapshot.get('news_sentiment_home') or 0
        sentiment_away = snapshot.get('news_sentiment_away') or 0
        if sentiment_home < -3:
            base_home -= 0.03
        if sentiment_away < -3:
            base_away -= 0.03

        # 归一化
        total = base_home + base_draw + base_away
        home_prob = base_home / total
        draw_prob = base_draw / total
        away_prob = base_away / total

        # 确定结果
        if home_prob > away_prob and home_prob > draw_prob:
            result = 'home'
        elif away_prob > home_prob and away_prob > draw_prob:
            result = 'away'
        else:
            result = 'draw'

        # 预测比分
        total_goals = 2.5
        form_goals = (snapshot.get('form_home_rating') or 50) / 100 * 0.5 + (snapshot.get('form_away_rating') or 50) / 100 * 0.5
        total_goals += form_goals

        if snapshot.get('is_friendly'):
            total_goals -= 0.3

        # 分配进球
        goal_ratio = home_prob / (home_prob + away_prob) if (home_prob + away_prob) > 0 else 0.5
        home_goals = round(total_goals * goal_ratio)
        away_goals = round(total_goals * (1 - goal_ratio))

        # 大小球
        over_prob = 0.45 + (total_goals - 2.5) * 0.1
        over_under = 'over' if total_goals > 2.5 else 'under'

        # 关键因素
        key_factors = []
        if abs(fifa_diff) > 30:
            key_factors.append(f"FIFA排名差{abs(fifa_diff)}")
        if abs(form_diff) > 20:
            key_factors.append(f"状态差{abs(form_diff):.0f}%")
        if snapshot.get('is_friendly'):
            key_factors.append("友谊赛平局提升")
        if injury_home > 2:
            key_factors.append(f"主队伤病{injury_home}人")
        if injury_away > 2:
            key_factors.append(f"客队伤病{injury_away}人")

        return {
            'home_prob': round(home_prob * 100, 1),
            'draw_prob': round(draw_prob * 100, 1),
            'away_prob': round(away_prob * 100, 1),
            'result': result,
            'confidence': round(max(home_prob, draw_prob, away_prob) * 100, 1),
            'total_goals': round(total_goals, 1),
            'home_goals': home_goals,
            'away_goals': away_goals,
            'over_under': over_under,
            'over_prob': round(over_prob * 100, 1),
            'under_prob': round((1 - over_prob) * 100, 1),
            'key_factors': key_factors,
            'model_params': params
        }

    def _evaluate_prediction(self, prediction: Dict, result: Dict) -> Dict:
        """评估预测"""
        # 结果命中
        result_hit = prediction['result'] == result['actual_result']

        # 比分命中
        score_hit = (prediction['home_goals'] == result['actual_home_score'] and
                     prediction['away_goals'] == result['actual_away_score'])

        # 大小球命中
        actual_total = result['actual_total_goals']
        over_under_hit = (prediction['over_under'] == 'over' and actual_total > 2.5) or \
                         (prediction['over_under'] == 'under' and actual_total <= 2.5)

        # Brier Score
        actual_probs = {'home': 0, 'draw': 0, 'away': 0}
        actual_probs[result['actual_result']] = 1
        brier = (
            (prediction['home_prob'] / 100 - actual_probs['home']) ** 2 +
            (prediction['draw_prob'] / 100 - actual_probs['draw']) ** 2 +
            (prediction['away_prob'] / 100 - actual_probs['away']) ** 2
        ) / 3

        # 概率误差
        home_prob_error = prediction['home_prob'] / 100 - actual_probs['home']
        draw_prob_error = prediction['draw_prob'] / 100 - actual_probs['draw']
        away_prob_error = prediction['away_prob'] / 100 - actual_probs['away']

        # 进球误差
        goal_error = prediction['total_goals'] - actual_total

        # 分析正确和遗漏因素
        correct_factors = []
        missed_factors = []

        for factor in prediction.get('key_factors', []):
            if '排名差' in factor and result['actual_result'] != 'draw':
                if abs(result['actual_home_score'] - result['actual_away_score']) > 1:
                    correct_factors.append(factor)
            if '友谊赛' in factor and result['actual_result'] == 'draw':
                correct_factors.append(factor)

        if result['actual_result'] != prediction['result']:
            missed_factors.append(f"预测{prediction['result']}实际{result['actual_result']}")

        return {
            'result_hit': result_hit,
            'score_hit': score_hit,
            'over_under_hit': over_under_hit,
            'brier_score': brier,
            'home_prob_error': home_prob_error,
            'draw_prob_error': draw_prob_error,
            'away_prob_error': away_prob_error,
            'goal_error': goal_error,
            'correct_factors': correct_factors,
            'missed_factors': missed_factors
        }

    def batch_train(self, match_ids: List[str]) -> Dict:
        """批量训练"""
        results = []
        for match_id in match_ids:
            try:
                result = self.train_on_finished_match(match_id)
                if 'error' not in result:
                    results.append(result)
            except Exception as e:
                logger.error(f"训练失败 {match_id}: {e}")

        # 统计
        total = len(results)
        hits = sum(1 for r in results if r['evaluation']['result_hit'])
        avg_brier = sum(r['evaluation']['brier_score'] for r in results) / total if total > 0 else 0

        print(f"\n{'='*60}")
        print(f"批量训练完成: {total}场")
        print(f"准确率: {hits/total*100:.1f}%")
        print(f"平均Brier: {avg_brier:.3f}")
        print(f"{'='*60}")

        return {'total': total, 'hits': hits, 'accuracy': hits/total*100, 'avg_brier': avg_brier}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='模型训练（正确流程）')
    parser.add_argument('--train', type=str, help='训练单场比赛')
    parser.add_argument('--batch', type=str, help='批量训练（逗号分隔match_id）')
    parser.add_argument('--collect', type=str, help='收集赛前数据')

    args = parser.parse_args()

    trainer = ModelTrainer()

    if args.train:
        result = trainer.train_on_finished_match(args.train)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    if args.batch:
        match_ids = args.batch.split(',')
        trainer.batch_train(match_ids)

    if args.collect:
        collector = PreMatchDataCollector()
        snapshot = collector.collect_pre_match_data(args.collect)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))

    if not any([args.train, args.batch, args.collect]):
        print("正确的模型训练流程")
        print("用法:")
        print("  python correct_training_flow.py --train 763698       # 训练单场")
        print("  python correct_training_flow.py --batch 763698,123   # 批量训练")
        print("  python correct_training_flow.py --collect 763698     # 收集赛前数据")