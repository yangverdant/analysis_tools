"""
体彩数据表创建脚本
执行方式: python backend/scripts/create_lottery_tables.py
"""

import sqlite3
import os
import sys

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'football_v2.db')


def create_lottery_tables():
    """创建体彩相关数据表"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"连接数据库: {DB_PATH}")

    # 1. 数据源桥接映射表
    print("创建表: source_mapping_bridge")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS source_mapping_bridge (
            bridge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_match_id INTEGER,
            lottery_issue_num VARCHAR(50) UNIQUE,
            apifootball_id INTEGER,
            sportmonks_id INTEGER,
            bet365_id VARCHAR(50),
            fbref_id VARCHAR(50),
            statsbomb_id VARCHAR(50),
            sofascore_id INTEGER,
            home_team_lottery_name VARCHAR(50),
            away_team_lottery_name VARCHAR(50),
            match_confidence REAL DEFAULT 1.0,
            match_method VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (system_match_id) REFERENCES matches(match_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_lottery ON source_mapping_bridge(lottery_issue_num)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_match ON source_mapping_bridge(system_match_id)")

    # 2. 体彩开售比赛表
    print("创建表: lottery_matches")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_matches (
            lottery_match_id TEXT PRIMARY KEY,
            match_id INTEGER,
            home_team_id INTEGER,
            away_team_id INTEGER,
            home_team_cn TEXT NOT NULL,
            away_team_cn TEXT NOT NULL,
            league_name_cn TEXT,
            match_num TEXT,
            match_date DATE NOT NULL,
            match_time TEXT,
            beijing_time TEXT,
            sell_status TEXT DEFAULT 'selling',
            sell_end_time TEXT,
            play_types TEXT,
            handicap_line REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches(match_id),
            FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
            FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_matches_date ON lottery_matches(match_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_matches_status ON lottery_matches(sell_status)")

    # 3. 体彩赔率表
    print("创建表: lottery_odds")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_odds (
            odds_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_match_id TEXT NOT NULL,
            match_id INTEGER,
            play_type TEXT NOT NULL,
            odds_data TEXT NOT NULL,
            opening_odds TEXT,
            latest_odds TEXT,
            odds_movement TEXT,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lottery_match_id) REFERENCES lottery_matches(lottery_match_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_odds_match ON lottery_odds(lottery_match_id, play_type)")

    # 4. 体彩预测记录表
    print("创建表: lottery_predictions")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_match_id TEXT NOT NULL,
            match_id INTEGER,
            play_type TEXT NOT NULL,
            predictions TEXT NOT NULL,
            recommendation TEXT,
            confidence REAL,
            confidence_level TEXT,
            has_value_bet INTEGER DEFAULT 0,
            value_bets TEXT,
            features_json TEXT,
            weights_json TEXT,
            model_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lottery_match_id) REFERENCES lottery_matches(lottery_match_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_predictions_match ON lottery_predictions(lottery_match_id)")

    # 5. 体彩开奖结果表
    print("创建表: lottery_results")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_match_id TEXT NOT NULL,
            match_id INTEGER,
            home_goals_ft INTEGER,
            away_goals_ft INTEGER,
            home_goals_ht INTEGER,
            away_goals_ht INTEGER,
            spf_result TEXT,
            bf_result TEXT,
            bqc_result TEXT,
            rqspf_result TEXT,
            draw_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lottery_match_id) REFERENCES lottery_matches(lottery_match_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_results_match ON lottery_results(lottery_match_id)")

    # 6. 体彩预测验证表
    print("创建表: lottery_validation")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_validation (
            validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER NOT NULL,
            lottery_match_id TEXT NOT NULL,
            play_type TEXT NOT NULL,
            predicted_result TEXT,
            actual_result TEXT,
            is_correct INTEGER DEFAULT 0,
            predicted_prob REAL,
            brier_score REAL,
            validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prediction_id) REFERENCES lottery_predictions(prediction_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_validation_play ON lottery_validation(play_type)")

    # 7. 体彩分析报告表
    print("创建表: lottery_analysis_reports")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_analysis_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_match_id TEXT NOT NULL,
            match_id INTEGER,
            report_type TEXT DEFAULT 'full',
            report_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lottery_match_id) REFERENCES lottery_matches(lottery_match_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_reports_match ON lottery_analysis_reports(lottery_match_id)")

    # 8. 球队名称映射表
    print("创建表: team_name_mapping")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_name_mapping (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_name TEXT NOT NULL UNIQUE,
            team_id INTEGER,
            aliases TEXT,
            match_confidence REAL DEFAULT 1.0,
            match_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_name_mapping ON team_name_mapping(lottery_name)")

    # 9. 权重调整历史表
    print("创建表: weight_adjustment_history")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weight_adjustment_history (
            adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            extractor_name TEXT NOT NULL,
            feature_category TEXT,
            old_weight REAL,
            new_weight REAL,
            adjustment_delta REAL,
            accuracy REAL,
            sample_count INTEGER,
            adjustment_reason TEXT,
            adjusted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_weight_adjustment_extractor ON weight_adjustment_history(extractor_name)")

    # 10. 数据源健康状态表
    print("创建表: data_source_health")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_source_health (
            health_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_category TEXT,
            status TEXT,
            last_success TIMESTAMP,
            last_failure TIMESTAMP,
            failure_count INTEGER DEFAULT 0,
            success_rate REAL DEFAULT 1.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_name, source_category)
        )
    """)

    conn.commit()

    # 插入初始球队名称映射
    print("插入球队名称映射...")
    team_mappings = [
        # 英超
        ('曼联', 'Manchester United'),
        ('曼城', 'Manchester City'),
        ('利物浦', 'Liverpool'),
        ('阿森纳', 'Arsenal'),
        ('切尔西', 'Chelsea'),
        ('热刺', 'Tottenham'),
        ('纽卡斯尔', 'Newcastle'),
        ('布莱顿', 'Brighton'),
        ('阿斯顿维拉', 'Aston Villa'),
        ('西汉姆', 'West Ham'),
        ('富勒姆', 'Fulham'),
        ('水晶宫', 'Crystal Palace'),
        ('狼队', 'Wolves'),
        ('埃弗顿', 'Everton'),
        ('伯恩茅斯', 'Bournemouth'),
        ('布伦特福德', 'Brentford'),
        ('诺丁汉森林', 'Nottingham'),
        ('南安普顿', 'Southampton'),
        ('伊普斯维奇', 'Ipswich'),
        ('莱斯特城', 'Leicester'),
        # 西甲
        ('皇马', 'Real Madrid'),
        ('巴塞罗那', 'Barcelona'),
        ('马德里竞技', 'Atletico Madrid'),
        ('马竞', 'Atletico Madrid'),
        ('塞维利亚', 'Sevilla'),
        ('皇家社会', 'Real Sociedad'),
        ('皇家贝蒂斯', 'Real Betis'),
        ('比利亚雷亚尔', 'Villarreal'),
        ('瓦伦西亚', 'Valencia'),
        ('毕尔巴鄂竞技', 'Athletic Bilbao'),
        # 德甲
        ('拜仁慕尼黑', 'Bayern Munich'),
        ('拜仁', 'Bayern Munich'),
        ('多特蒙德', 'Dortmund'),
        ('莱比锡红牛', 'RB Leipzig'),
        ('勒沃库森', 'Leverkusen'),
        ('法兰克福', 'Frankfurt'),
        ('沃尔夫斯堡', 'Wolfsburg'),
        ('门兴格拉德巴赫', 'Monchengladbach'),
        # 意甲
        ('AC米兰', 'AC Milan'),
        ('米兰', 'AC Milan'),
        ('国际米兰', 'Inter Milan'),
        ('国米', 'Inter Milan'),
        ('尤文图斯', 'Juventus'),
        ('尤文', 'Juventus'),
        ('那不勒斯', 'Napoli'),
        ('罗马', 'Roma'),
        ('拉齐奥', 'Lazio'),
        ('亚特兰大', 'Atalanta'),
        # 法甲
        ('巴黎圣日耳曼', 'Paris Saint Germain'),
        ('巴黎', 'Paris Saint Germain'),
        ('马赛', 'Marseille'),
        ('里昂', 'Lyon'),
        ('摩纳哥', 'Monaco'),
        ('里尔', 'Lille'),
    ]

    for cn_name, en_name in team_mappings:
        cursor.execute("""
            SELECT team_id FROM teams
            WHERE name_en LIKE ? OR name_en LIKE ? OR name_cn LIKE ?
            LIMIT 1
        """, (f'%{en_name}%', f'%{en_name.split()[0]}%', f'%{cn_name}%'))

        row = cursor.fetchone()
        if row:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO team_name_mapping (lottery_name, team_id, match_method)
                    VALUES (?, ?, 'exact')
                """, (cn_name, row[0]))
            except:
                pass

    conn.commit()

    # 统计
    cursor.execute("SELECT COUNT(*) FROM team_name_mapping")
    mapping_count = cursor.fetchone()[0]

    print(f"\n=== 创建完成 ===")
    print(f"球队名称映射: {mapping_count} 条")

    # 列出所有新建的表
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE 'lottery%' OR name LIKE 'source%' OR name LIKE 'team_name%' OR name LIKE 'weight%' OR name LIKE 'data_source%'
        ORDER BY name
    """)
    tables = cursor.fetchall()
    print(f"\n新建表:")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t[0]}")
        count = cursor.fetchone()[0]
        print(f"  - {t[0]}: {count} 条记录")

    conn.close()
    print("\n数据库连接已关闭")


if __name__ == '__main__':
    create_lottery_tables()
