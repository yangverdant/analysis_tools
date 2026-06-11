"""数据库Schema迁移脚本

窗口1 Step 3: 为日循环核心功能添加必要的表和字段
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'football_v2.db'


def migrate(db_path: str = None):
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # 1. lottery_matches 加 oddsfe_event_id
    try:
        cursor.execute("ALTER TABLE lottery_matches ADD COLUMN oddsfe_event_id TEXT")
        print("  + lottery_matches.oddsfe_event_id")
    except Exception:
        print("  - lottery_matches.oddsfe_event_id (exists)")

    # 2. lottery_odds 加 snapshot_type
    try:
        cursor.execute("ALTER TABLE lottery_odds ADD COLUMN snapshot_type TEXT DEFAULT 'current'")
        print("  + lottery_odds.snapshot_type")
    except Exception:
        print("  - lottery_odds.snapshot_type (exists)")

    # 3. lottery_validation 加归因字段
    for col, typ in [('attribution', 'TEXT'), ('attribution_detail', 'TEXT'),
                     ('scenario_type', 'TEXT'), ('actionable', 'INTEGER DEFAULT 0')]:
        try:
            cursor.execute(f"ALTER TABLE lottery_validation ADD COLUMN {col} {typ}")
            print(f"  + lottery_validation.{col}")
        except Exception:
            print(f"  - lottery_validation.{col} (exists)")

    # 4. 新建 daily_cycle_state 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_cycle_state (
            date TEXT PRIMARY KEY,
            current_node TEXT NOT NULL,
            perceive_result TEXT,
            collect_result TEXT,
            intel_result TEXT,
            classify_result TEXT,
            analyze_result TEXT,
            push_result TEXT,
            clv_result TEXT,
            validate_result TEXT,
            learn_result TEXT,
            status TEXT DEFAULT 'running',
            error_message TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  + daily_cycle_state table")

    # 5. 新建 model_accuracy 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_accuracy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_type TEXT NOT NULL,
            odds_tier TEXT,
            participant_type TEXT DEFAULT 'club',
            total_matches INTEGER DEFAULT 0,
            model_accuracy REAL,
            odds_baseline_accuracy REAL,
            model_brier REAL,
            odds_brier REAL,
            period TEXT,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  + model_accuracy table")

    # 6. 新建 bet_records 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bet_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            lottery_match_id TEXT,
            play_type TEXT,
            selection TEXT,
            odds REAL,
            stake REAL DEFAULT 0,
            result TEXT,
            payout REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prediction_id) REFERENCES lottery_predictions(prediction_id)
        )
    """)
    print("  + bet_records table")

    # 7. 新建 lottery_results 表 (如果不存在)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_results (
            lottery_match_id TEXT PRIMARY KEY,
            home_goals_ft INTEGER,
            away_goals_ft INTEGER,
            home_goals_ht INTEGER,
            away_goals_ht INTEGER,
            spf_result TEXT,
            bf_result TEXT,
            bqc_result TEXT,
            rqspf_result TEXT,
            draw_time TEXT,
            FOREIGN KEY (lottery_match_id) REFERENCES lottery_matches(lottery_match_id)
        )
    """)
    print("  + lottery_results table")

    # 8. data_source_health 初始化
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_source_health (
            source_name TEXT PRIMARY KEY,
            source_category TEXT,
            status TEXT DEFAULT 'unknown',
            last_success TEXT,
            last_failure TEXT,
            success_rate REAL DEFAULT 0,
            updated_at TEXT
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO data_source_health (source_name, source_category, status)
        VALUES
            ('sporttery', 'lottery', 'unknown'),
            ('oddsfe', 'odds', 'unknown'),
            ('apifootball', 'injury', 'unknown'),
            ('fifa', 'ranking', 'unknown'),
            ('football_data_uk', 'historical', 'unknown')
    """)
    print("  + data_source_health initialized")

    # 9. leagues表 competition_type 细分
    try:
        cursor.execute("""
            UPDATE leagues SET competition_type = 'qualifier'
            WHERE name_en LIKE '%qualif%' OR name_cn LIKE '%预选赛%'
        """)
        cursor.execute("""
            UPDATE leagues SET competition_type = 'nations_league'
            WHERE name_en LIKE '%nations league%' OR name_cn LIKE '%国联%'
        """)
        cursor.execute("""
            UPDATE leagues SET competition_type = 'olympic'
            WHERE name_en LIKE '%olympic%' OR name_cn LIKE '%奥运%'
        """)
        print(f"  + leagues competition_type refined ({cursor.rowcount} rows)")
    except Exception:
        print("  - leagues competition_type (no update needed)")

    conn.commit()
    conn.close()
    print("\nMigration complete!")


def fix_lottery_validation(db_path: str = None):
    """修复lottery_validation表: prediction_id改为可为空

    因为日循环validate从lottery_analysis_reports取预测，没有prediction_id
    """
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # 检查prediction_id是否NOT NULL
    cursor.execute("PRAGMA table_info(lottery_validation)")
    columns = {row[1]: row for row in cursor.fetchall()}

    if 'prediction_id' in columns:
        col_info = columns['prediction_id']
        # col_info: (cid, name, type, notnull, default, pk)
        if col_info[3] == 1:  # notnull=1
            # SQLite不支持ALTER COLUMN，需要重建表
            cursor.execute('SELECT COUNT(*) FROM lottery_validation')
            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute('DROP TABLE lottery_validation')
                cursor.execute("""
                    CREATE TABLE lottery_validation (
                        validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prediction_id INTEGER,
                        lottery_match_id TEXT NOT NULL,
                        play_type TEXT NOT NULL,
                        predicted_result TEXT,
                        actual_result TEXT,
                        is_correct INTEGER DEFAULT 0,
                        predicted_prob REAL,
                        brier_score REAL,
                        validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        attribution TEXT,
                        attribution_detail TEXT,
                        scenario_type TEXT,
                        actionable INTEGER DEFAULT 0
                    )
                """)
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_lottery_validation_play ON lottery_validation(play_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_lottery_validation_match ON lottery_validation(lottery_match_id)')
                print("  + lottery_validation recreated (prediction_id nullable)")
            else:
                print(f"  - lottery_validation has {count} rows, manual migration needed")
        else:
            print("  - lottery_validation.prediction_id already nullable")
    else:
        print("  - lottery_validation table not found")

    conn.commit()
    conn.close()


if __name__ == '__main__':
    db = sys.argv[1] if len(sys.argv) > 1 else None
    migrate(db)
    fix_lottery_validation(db)
