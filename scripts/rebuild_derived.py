"""
rebuild_derived.py — 从matches表重建所有衍生数据

衍生数据 = 从matches计算出来的数据：
- elo_ratings / elo_history
- team_form (per-match records)
- h2h_records (per-match records)

用法：
    python rebuild_derived.py --db /path/to/football_v2.db
    python rebuild_derived.py --db ... --only elo
    python rebuild_derived.py --db ... --from-date 2024-08-01
"""

import sqlite3
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


class EloRebuilder:
    """重建Elo评分 — 匹配实际schema:
    elo_ratings: team_id, elo_rating, elo_change, matches_count, calculated_at
    elo_history: id, team_id, elo_rating, elo_change, match_id, match_date, created_at
    """

    DEFAULT_ELO = 1500
    K_FACTOR = 32
    HOME_ADVANTAGE = 100
    SCALE_FACTOR = 400

    def rebuild(self, db_path: str, from_date: str = None):
        logger.info(f"Rebuilding Elo ratings (from_date={from_date})...")
        conn = sqlite3.connect(db_path)

        conn.execute("DELETE FROM elo_ratings")
        conn.execute("DELETE FROM elo_history")
        conn.commit()

        if from_date:
            matches = conn.execute("""
                SELECT match_id, home_team_id, away_team_id, home_goals, away_goals, match_date
                FROM matches
                WHERE status = 'finished' AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                  AND match_date >= ?
                ORDER BY match_date ASC
            """, (from_date,)).fetchall()
        else:
            matches = conn.execute("""
                SELECT match_id, home_team_id, away_team_id, home_goals, away_goals, match_date
                FROM matches
                WHERE status = 'finished' AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                ORDER BY match_date ASC
            """).fetchall()

        logger.info(f"  Processing {len(matches):,} matches...")

        elo = {}  # team_id → current_elo
        match_count = {}  # team_id → count
        history_batch = []
        batch_size = 1000
        count = 0

        for match_id, home_id, away_id, hg, ag, match_date in matches:
            home_elo = elo.get(home_id, self.DEFAULT_ELO)
            away_elo = elo.get(away_id, self.DEFAULT_ELO)

            if hg > ag:
                home_actual, away_actual = 1.0, 0.0
            elif hg < ag:
                home_actual, away_actual = 0.0, 1.0
            else:
                home_actual, away_actual = 0.5, 0.5

            home_expected = 1 / (1 + 10 ** ((away_elo - (home_elo + self.HOME_ADVANTAGE)) / self.SCALE_FACTOR))
            away_expected = 1 / (1 + 10 ** (((home_elo + self.HOME_ADVANTAGE) - away_elo) / self.SCALE_FACTOR))

            home_change = self.K_FACTOR * (home_actual - home_expected)
            away_change = self.K_FACTOR * (away_actual - away_expected)
            home_new = home_elo + home_change
            away_new = away_elo + away_change

            elo[home_id] = home_new
            elo[away_id] = away_new
            match_count[home_id] = match_count.get(home_id, 0) + 1
            match_count[away_id] = match_count.get(away_id, 0) + 1

            # elo_history: team_id, elo_rating, elo_change, match_id, match_date, created_at
            history_batch.append((home_id, round(home_new, 2), round(home_change, 2), match_id, match_date, datetime.now().isoformat()))
            history_batch.append((away_id, round(away_new, 2), round(away_change, 2), match_id, match_date, datetime.now().isoformat()))

            count += 1
            if len(history_batch) >= batch_size:
                conn.executemany("""
                    INSERT INTO elo_history (team_id, elo_rating, elo_change, match_id, match_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, history_batch)
                conn.commit()
                history_batch = []
                if count % 50000 == 0:
                    logger.info(f"  Progress: {count:,}/{len(matches):,}")

        if history_batch:
            conn.executemany("""
                INSERT INTO elo_history (team_id, elo_rating, elo_change, match_id, match_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, history_batch)
            conn.commit()

        # 写入elo_ratings
        now = datetime.now().isoformat()
        ratings_batch = []
        for team_id, rating in elo.items():
            mc = match_count.get(team_id, 0)
            # 计算最近变化（取最后一条history的change）
            ratings_batch.append((team_id, round(rating, 2), round(rating - self.DEFAULT_ELO, 2), mc, now))

        conn.executemany("""
            INSERT OR REPLACE INTO elo_ratings (team_id, elo_rating, elo_change, matches_count, calculated_at)
            VALUES (?, ?, ?, ?, ?)
        """, ratings_batch)
        conn.commit()

        logger.info(f"  Done: {len(elo):,} teams rated from {count:,} matches")
        conn.close()


class FormRebuilder:
    """重建team_form — per-match records
    Schema: id, team_id, team_name, match_date, opponent, is_home, goals_for, goals_against, result, competition, xg, xga, source, created_at
    """

    def rebuild(self, db_path: str, from_date: str = None):
        logger.info(f"Rebuilding team_form (per-match records)...")
        conn = sqlite3.connect(db_path)

        conn.execute("DELETE FROM team_form")
        conn.commit()

        # 获取所有完赛比赛（只取最近20场/队）
        # 用批量方式：先写入所有match记录
        query = """
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                ht.name_en as home_name,
                at.name_en as away_name,
                m.home_goals,
                m.away_goals,
                l.name_en as league_name,
                m.competition_type
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE m.status = 'finished' AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        """
        if from_date:
            query += f" AND m.match_date >= '{from_date}'"
        query += " ORDER BY m.match_date DESC"

        matches = conn.execute(query).fetchall()
        logger.info(f"  Processing {len(matches):,} matches...")

        batch = []
        count = 0

        for r in matches:
            match_id, match_date, home_id, away_id, home_name, away_name, hg, ag, league_name, comp_type = r

            # 主队记录
            home_result = 'W' if hg > ag else ('D' if hg == ag else 'L')
            batch.append((
                home_id, home_name, match_date, away_name, 1, hg, ag,
                home_result, comp_type or league_name or '', None, None, 'oddsfe', datetime.now().isoformat()
            ))

            # 客队记录
            away_result = 'W' if ag > hg else ('D' if ag == hg else 'L')
            batch.append((
                away_id, away_name, match_date, home_name, 0, ag, hg,
                away_result, comp_type or league_name or '', None, None, 'oddsfe', datetime.now().isoformat()
            ))

            count += 1
            if len(batch) >= 2000:
                conn.executemany("""
                    INSERT OR IGNORE INTO team_form
                    (team_id, team_name, match_date, opponent, is_home, goals_for, goals_against, result, competition, xg, xga, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                batch = []
                if count % 50000 == 0:
                    logger.info(f"  Progress: {count:,}/{len(matches):,}")

        if batch:
            conn.executemany("""
                INSERT OR IGNORE INTO team_form
                (team_id, team_name, match_date, opponent, is_home, goals_for, goals_against, result, competition, xg, xga, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            conn.commit()

        logger.info(f"  Done: {count*2:,} form records from {count:,} matches")
        conn.close()


class H2HRebuilder:
    """重建h2h_records — per-match records
    Schema: id, team_a_id, team_b_id, team_a_name, team_b_name, match_date, match_id, home_team, away_team, home_score, away_score, competition, source, created_at
    """

    def rebuild(self, db_path: str):
        logger.info(f"Rebuilding h2h_records (per-match records)...")
        conn = sqlite3.connect(db_path)

        conn.execute("DELETE FROM h2h_records")
        conn.commit()

        # 只记录有>=2次交手的球队对之间的比赛
        # 先找有多次交手的球队对
        pairs = conn.execute("""
            SELECT
                MIN(home_team_id, away_team_id) as team_a,
                MAX(home_team_id, away_team_id) as team_b,
                COUNT(*) as total
            FROM matches
            WHERE status = 'finished' AND home_goals IS NOT NULL
            GROUP BY team_a, team_b
            HAVING total >= 2
        """).fetchall()

        # 构建set方便快速查找
        pair_set = set()
        for a, b, total in pairs:
            pair_set.add((a, b))

        logger.info(f"  Found {len(pair_set):,} team pairs with >=2 matches")

        # 批量写入所有H2H match记录
        matches = conn.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                ht.name_en,
                at.name_en,
                m.home_goals,
                m.away_goals,
                l.name_en,
                m.competition_type
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE m.status = 'finished' AND m.home_goals IS NOT NULL
            ORDER BY m.match_date DESC
        """).fetchall()

        batch = []
        count = 0

        for r in matches:
            match_id, match_date, home_id, away_id, home_name, away_name, hg, ag, league_name, comp_type = r

            # 检查是否是H2H pair
            pair_key = (min(home_id, away_id), max(home_id, away_id))
            if pair_key not in pair_set:
                continue

            team_a_id = pair_key[0]
            team_b_id = pair_key[1]

            # 获取team_a/b的name
            if home_id == team_a_id:
                team_a_name = home_name
                team_b_name = away_name
            else:
                team_a_name = away_name
                team_b_name = home_name

            batch.append((
                team_a_id, team_b_id, team_a_name, team_b_name,
                match_date, match_id, home_name, away_name,
                hg, ag, comp_type or league_name or '', 'oddsfe', datetime.now().isoformat()
            ))

            count += 1
            if len(batch) >= 2000:
                conn.executemany("""
                    INSERT OR IGNORE INTO h2h_records
                    (team_a_id, team_b_id, team_a_name, team_b_name, match_date, match_id, home_team, away_team, home_score, away_score, competition, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                batch = []

        if batch:
            conn.executemany("""
                INSERT OR IGNORE INTO h2h_records
                (team_a_id, team_b_id, team_a_name, team_b_name, match_date, match_id, home_team, away_team, home_score, away_score, competition, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            conn.commit()

        logger.info(f"  Done: {count:,} H2H match records")
        conn.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='重建衍生数据')
    parser.add_argument('--db', required=True, help='football_v2.db路径')
    parser.add_argument('--only', nargs='*', help='只重建指定: elo form h2h')
    parser.add_argument('--from-date', help='从指定日期开始计算Elo')
    args = parser.parse_args()

    start = time.time()

    tasks = {
        'elo': lambda: EloRebuilder().rebuild(args.db, args.from_date),
        'form': lambda: FormRebuilder().rebuild(args.db, args.from_date),
        'h2h': lambda: H2HRebuilder().rebuild(args.db),
    }

    if args.only:
        tasks = {k: v for k, v in tasks.items() if k in args.only}

    for name, fn in tasks.items():
        t0 = time.time()
        fn()
        logger.info(f"  '{name}' took {time.time()-t0:.1f}s")

    logger.info(f"\nTotal time: {time.time()-start:.1f}s")