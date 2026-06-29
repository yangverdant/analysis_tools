"""Build league_poisson_calibration table from historical match data

Computes per-league avg home/away goals, draw rate, home/away win rate
from all finished matches in the DB. This replaces hardcoded league averages
and provides more accurate Poisson parameters.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

DB_PATH = '/opt/football_tools/data/football_v2.db'


def build_calibration(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS league_poisson_calibration (
            league_id TEXT PRIMARY KEY,
            avg_home_goals REAL,
            avg_away_goals REAL,
            draw_rate REAL,
            home_win_rate REAL,
            away_win_rate REAL,
            sample_count INTEGER,
            avg_total_goals REAL,
            updated_at TEXT
        )
    """)
    conn.commit()

    # Compute calibration per league
    cursor.execute("""
        SELECT
            m.league_id,
            AVG(m.home_goals) as avg_home_goals,
            AVG(m.away_goals) as avg_away_goals,
            AVG(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draw_rate,
            AVG(CASE WHEN m.home_goals > m.away_goals THEN 1 ELSE 0 END) as home_win_rate,
            AVG(CASE WHEN m.home_goals < m.away_goals THEN 1 ELSE 0 END) as away_win_rate,
            AVG(m.home_goals + m.away_goals) as avg_total_goals,
            COUNT(*) as sample_count
        FROM matches m
        WHERE m.status = 'finished'
        AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        AND m.match_date > date('now', '-3 years')
        GROUP BY m.league_id
        HAVING COUNT(*) >= 30
    """)

    rows = cursor.fetchall()
    count = 0
    for row in rows:
        cursor.execute("""
            INSERT OR REPLACE INTO league_poisson_calibration
            (league_id, avg_home_goals, avg_away_goals, draw_rate,
             home_win_rate, away_win_rate, avg_total_goals,
             sample_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, row)
        count += 1

    conn.commit()

    # Also compute global average for leagues with <30 matches
    cursor.execute("""
        SELECT
            AVG(m.home_goals) as avg_home_goals,
            AVG(m.away_goals) as avg_away_goals,
            AVG(CASE WHEN m.home_goals = m.away_goals THEN 1 ELSE 0 END) as draw_rate,
            AVG(CASE WHEN m.home_goals > m.away_goals THEN 1 ELSE 0 END) as home_win_rate,
            AVG(CASE WHEN m.home_goals < m.away_goals THEN 1 ELSE 0 END) as away_win_rate,
            AVG(m.home_goals + m.away_goals) as avg_total_goals,
            COUNT(*) as sample_count
        FROM matches m
        WHERE m.status = 'finished'
        AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
    """)
    global_row = cursor.fetchone()

    # Store as 'global' key
    cursor.execute("""
        INSERT OR REPLACE INTO league_poisson_calibration
        (league_id, avg_home_goals, avg_away_goals, draw_rate,
         home_win_rate, away_win_rate, avg_total_goals,
         sample_count, updated_at)
        VALUES ('_global', ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, global_row)
    conn.commit()

    print(f'Calibrated {count} leagues + global average')
    print(f'Global avg: home={global_row[0]:.3f}, away={global_row[1]:.3f}, draw={global_row[2]:.3f}')

    # Show top leagues
    cursor.execute("""
        SELECT lc.league_id, l.name_en, lc.avg_home_goals, lc.avg_away_goals,
               lc.draw_rate, lc.sample_count
        FROM league_poisson_calibration lc
        LEFT JOIN leagues l ON lc.league_id = l.league_id
        WHERE lc.league_id != '_global'
        ORDER BY lc.sample_count DESC
        LIMIT 20
    """)
    top = cursor.fetchall()
    print(f'\nTop 20 leagues:')
    for r in top:
        print(f'  {r[1] or r[0]}: home={r[2]:.3f}, away={r[3]:.3f}, draw={r[4]:.3f}, n={r[5]}')

    conn.close()


if __name__ == '__main__':
    build_calibration()
