"""
oddsfe_sync.py — oddsfe_merged.db → football_v2.db 增量同步管道

核心原则：
1. 不替换任何现有表，增量添加oddsfe数据
2. 复用现有team_id/league_id（名称匹配时），新增oddsfe独有的队/联赛
3. match_id用"oddsfe_{event_id}"前缀，与现有数据不冲突
4. 新建match_odds_normalized表存储规范化赔率（多行，不替换旧match_odds）
5. 为matches表新增competition_type/participant_type列
6. 统一status为小写，统一时间为北京时间

用法：
    # 首次全量同步
    python oddsfe_sync.py --oddsfe /path/to/oddsfe_merged.db --db /path/to/football_v2.db

    # 只执行某步骤
    python oddsfe_sync.py --oddsfe ... --db ... --step migrate_schema sync_teams sync_leagues sync_matches sync_odds validate

    # 增量同步（每日）
    python oddsfe_sync.py --oddsfe ... --db ... --incremental
"""

import sqlite3
import json
import os
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# 标准化规则
# ============================================================

STATUS_MAP = {
    'FINISHED': 'finished',
    'SCHEDULED': 'scheduled',
    'NOT_STARTED': 'scheduled',
    'Not Started': 'scheduled',
    'LIVE': 'live',
    'IN_PLAY': 'live',
    'PAUSED': 'live',
    'CANCELLED': 'cancelled',
    'CANC.': 'cancelled',
    'Cancl.': 'cancelled',
    'Cancelled': 'cancelled',
    'POSTPONED': 'postponed',
    'Postponed': 'postponed',
    'ABANDONED': 'abandoned',
    'Aban.': 'abandoned',
    'INTERRUPTED': 'interrupted',
    'AWARDED': 'finished',
    'Awarded': 'finished',
    'AFTER_PEN': 'finished',
    'After Pen.': 'finished',
    'AFTER_ET': 'finished',
    'After ET': 'finished',
    'TBA': 'scheduled',
    'Finished': 'finished',
}

BOOKMAKERS = [
    '1XBET', 'BET365', 'PINNACLE', 'BETFAIR_EXCH', 'BETFAIR',
    'BET_IN_ASIA', 'UNIBET', 'BET_AT_HOME', 'WILLIAM_HILL',
    'DAFABET', 'BWIN_ES', 'BWIN', '888_SPORT', 'STAKE_COM', 'MATCHBOOK',
]

COMPETITION_TYPE_RULES = [
    ('friendly', 'friendly'),
    ('Friendlies', 'friendly'),
    ('Friendly', 'friendly'),
    ('Champions League', 'continental_cup'),
    ('Europa League', 'continental_cup'),
    ('Conference League', 'continental_cup'),
    ('Europa Conf', 'continental_cup'),
    ('Copa Libertadores', 'continental_cup'),
    ('Copa Sudamericana', 'continental_cup'),
    ('AFC Champions', 'continental_cup'),
    ('CAF Champions', 'continental_cup'),
    ('CONCACAF Champions', 'continental_cup'),
    ('World Cup', 'international_cup'),
    ('Euro', 'international_cup'),
    ('Copa America', 'international_cup'),
    ('Asian Cup', 'international_cup'),
    ('Africa Cup', 'international_cup'),
    ('Gold Cup', 'international_cup'),
    ('Nations League', 'nations_league'),
    ('World Cup Qualif', 'qualifier'),
    ('Euro Qualif', 'qualifier'),
    ('Copa America Qualif', 'qualifier'),
    ('Asian Qualif', 'qualifier'),
    ('Africa Qualif', 'qualifier'),
    ('Concacaf Qualif', 'qualifier'),
    ('Olympic', 'olympic'),
]

NATIONAL_CATEGORIES = {'World', 'Europe', 'Asia', 'South America', 'North America', 'Africa', 'International'}


def normalize_status(raw_status: str) -> str:
    if not raw_status:
        return 'scheduled'
    return STATUS_MAP.get(raw_status, STATUS_MAP.get(raw_status.upper(), raw_status.lower()))


def utc_to_beijing(utc_str: str) -> tuple:
    if not utc_str:
        return (None, None, 'beijing')
    try:
        clean = utc_str.replace('Z', '').replace('z', '')
        if 'T' in clean:
            dt = datetime.fromisoformat(clean)
        else:
            dt = datetime.strptime(clean, '%Y-%m-%d %H:%M:%S')
        bj = dt + timedelta(hours=8)
        return (bj.strftime('%Y-%m-%d'), bj.strftime('%H:%M'), 'beijing')
    except Exception:
        try:
            return (utc_str[:10], None, 'beijing')
        except:
            return (None, None, 'beijing')


def classify_competition(tournament_name: str, category_name: str) -> tuple:
    if not tournament_name:
        return ('league', 'club')
    tn_lower = tournament_name.lower()
    for keyword, comp_type in COMPETITION_TYPE_RULES:
        if keyword.lower() in tn_lower:
            participant = 'national' if category_name in NATIONAL_CATEGORIES else 'club'
            return (comp_type, participant)
    if category_name in NATIONAL_CATEGORIES:
        return ('other_international', 'national')
    return ('league', 'club')


def safe_float(val) -> Optional[float]:
    if val is None or val == '' or val == 'None':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val) -> Optional[int]:
    if val is None or val == '' or val == 'None':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ============================================================
# 同步管道
# ============================================================

class OddsfeSync:
    def __init__(self, oddsfe_path: str, db_path: str):
        self.oddsfe_path = oddsfe_path
        self.db_path = db_path
        self.team_cache = {}       # name_en → team_id (加载已有的+新增的)
        self.team_alias_cache = {} # alias_name → team_id
        self.league_cache = {}     # (name_en, country) → league_id
        self.cn_names = {}         # 英文名 → 中文名
        self.cn_countries = {}     # 英文国家 → 中文国家
        self.next_team_id = None
        self.next_league_id = None

    def load_chinese_names(self):
        linkage_dir = os.path.join(os.path.dirname(self.db_path), 'linkage')
        for filename, target in [
            ('team_chinese_names.json', self.cn_names),
            ('country_chinese_names.json', self.cn_countries),
        ]:
            filepath = os.path.join(linkage_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    target.update(json.load(f))
        logger.info(f"Loaded {len(self.cn_names)} team CN names, {len(self.cn_countries)} country CN names")

    def _load_existing_teams(self, dst: sqlite3.Connection):
        """加载现有team_id映射"""
        for r in dst.execute("SELECT team_id, name_en FROM teams").fetchall():
            self.team_cache[r[1]] = r[0]
        for r in dst.execute("SELECT alias_name, team_id FROM team_aliases").fetchall():
            self.team_alias_cache[r[0]] = r[1]
        self.next_team_id = dst.execute("SELECT MAX(team_id) FROM teams").fetchone()[0] + 1
        logger.info(f"  Loaded {len(self.team_cache)} existing teams, {len(self.team_alias_cache)} aliases, next_id={self.next_team_id}")

    def _load_existing_leagues(self, dst: sqlite3.Connection):
        """加载现有league_id映射"""
        for r in dst.execute("SELECT league_id, name_en, country FROM leagues").fetchall():
            self.league_cache[(r[1], r[2] or '')] = r[0]
        self.next_league_id = dst.execute("SELECT MAX(league_id) FROM leagues").fetchone()[0] + 1
        logger.info(f"  Loaded {len(self.league_cache)} existing leagues, next_id={self.next_league_id}")

    def _get_or_create_team(self, name: str, country: str, dst: sqlite3.Connection) -> int:
        """获取或创建team_id"""
        # 1. 精确匹配现有队名
        if name in self.team_cache:
            return self.team_cache[name]

        # 2. 匹配别名
        if name in self.team_alias_cache:
            team_id = self.team_alias_cache[name]
            self.team_cache[name] = team_id  # 缓存加速
            return team_id

        # 3. 新队伍 - 注册
        name_cn = self.cn_names.get(name, '')
        country_cn = self.cn_countries.get(country, '')
        team_type = 'national' if country in NATIONAL_CATEGORIES else 'club'

        team_id = self.next_team_id
        self.next_team_id += 1

        dst.execute(
            "INSERT INTO teams (team_id, name_en, name_cn, country, country_cn, team_type) VALUES (?, ?, ?, ?, ?, ?)",
            (team_id, name, name_cn, country or '', country_cn, team_type)
        )

        # 也注册为别名（方便后续匹配）
        dst.execute(
            "INSERT INTO team_aliases (team_id, alias_name, source) VALUES (?, ?, ?)",
            (team_id, name, 'oddsfe')
        )

        self.team_cache[name] = team_id
        self.team_alias_cache[name] = team_id
        return team_id

    def _get_or_create_league(self, tournament_name: str, category_name: str, dst: sqlite3.Connection) -> int:
        """获取或创建league_id"""
        key = (tournament_name, category_name or '')

        # 1. 精确匹配 (name_en, country)
        if key in self.league_cache:
            return self.league_cache[key]

        # 2. 只按name_en匹配（country可能不同表示法）
        for (n, c), lid in self.league_cache.items():
            if n == tournament_name and lid not in [v for k, v in self.league_cache.items() if k != (n, c)]:
                # 唯一匹配
                self.league_cache[key] = lid
                return lid

        # 3. 新联赛 - 注册
        comp_type, part_type = classify_competition(tournament_name, category_name or '')
        cat_cn = self.cn_countries.get(category_name, '')

        league_id = self.next_league_id
        self.next_league_id += 1

        dst.execute(
            "INSERT INTO leagues (league_id, name_en, country, country_cn, competition_type, participant_type) VALUES (?, ?, ?, ?, ?, ?)",
            (league_id, tournament_name, category_name or '', cat_cn, comp_type, part_type)
        )

        self.league_cache[key] = league_id
        return league_id

    # ============================================================
    # Step 1: Schema Migration
    # ============================================================

    def step_migrate_schema(self):
        """为现有表添加缺失的列"""
        logger.info("Step: Migrating schema...")

        migrations = [
            # matches表新增列
            ("matches", "competition_type", "TEXT"),
            ("matches", "participant_type", "TEXT"),
            ("matches", "event_start_at", "TEXT"),
            ("matches", "tournament_name", "TEXT"),
            ("matches", "category_name", "TEXT"),
            # teams表新增列
            ("teams", "oddsfe_team_id", "TEXT"),
            # leagues表新增列
            ("leagues", "oddsfe_tournament_id", "TEXT"),
            ("leagues", "oddsfe_tournament_name", "TEXT"),
        ]

        conn = sqlite3.connect(self.db_path)
        existing_cols = {}
        for table in ['matches', 'teams', 'leagues']:
            existing_cols[table] = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

        for table, col, col_type in migrations:
            if col not in existing_cols.get(table, set()):
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    logger.info(f"  Added {table}.{col}")
                except sqlite3.OperationalError as e:
                    if 'duplicate column' not in str(e):
                        raise

        # 创建match_odds_normalized表（规范化赔率，与旧match_odds并存）
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS match_odds_normalized (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                bookmaker TEXT NOT NULL,
                snapshot_type TEXT DEFAULT 'prematch',
                market TEXT DEFAULT '1X2',
                home REAL,
                draw REAL,
                away REAL,
                line REAL,
                captured_at TIMESTAMP,
                source TEXT DEFAULT 'oddsfe',
                UNIQUE(match_id, bookmaker, snapshot_type, market)
            );
            CREATE INDEX IF NOT EXISTS idx_mon_match ON match_odds_normalized(match_id);
            CREATE INDEX IF NOT EXISTS idx_mon_bk ON match_odds_normalized(bookmaker);
            CREATE INDEX IF NOT EXISTS idx_mon_market ON match_odds_normalized(market);
        """)

        # 统一现有matches的status为小写
        fixed = conn.execute("""
            UPDATE matches SET status = LOWER(status)
            WHERE status != LOWER(status) AND status IS NOT NULL
        """).rowcount
        if fixed:
            logger.info(f"  Normalized {fixed} match status values to lowercase")

        # 处理特殊status
        status_fixes = {
            'not started': 'scheduled',
            'after pen.': 'finished',
            'after et': 'finished',
            'cancl.': 'cancelled',
            'aban.': 'abandoned',
            'tba': 'scheduled',
            '': 'scheduled',
        }
        for old, new in status_fixes.items():
            fixed = conn.execute("UPDATE matches SET status = ? WHERE LOWER(status) = ?", (new, old)).rowcount
            if fixed:
                logger.info(f"  Fixed status '{old}' → '{new}': {fixed} rows")

        conn.commit()
        conn.close()
        logger.info("  Schema migration done")

    # ============================================================
    # Step 2: Sync Teams
    # ============================================================

    def step_sync_teams(self):
        """从oddsfe同步球队：匹配已有team_id，新增oddsfe独有的"""
        logger.info("Step: Syncing teams from oddsfe...")
        src = sqlite3.connect(self.oddsfe_path)
        dst = sqlite3.connect(self.db_path)

        self._load_existing_teams(dst)

        # 提取oddsfe所有队名
        oddsfe_teams = set()
        for r in src.execute("SELECT DISTINCT team_home_name, category_name FROM oddsfe WHERE team_home_name IS NOT NULL").fetchall():
            oddsfe_teams.add((r[0], r[1]))
        for r in src.execute("SELECT DISTINCT team_away_name, category_name FROM oddsfe WHERE team_away_name IS NOT NULL").fetchall():
            oddsfe_teams.add((r[0], r[1]))

        # 分类统计
        matched = 0
        new_teams = 0
        for name, country in sorted(oddsfe_teams):
            tid = self._get_or_create_team(name, country or '', dst)
            if tid in [v for k, v in self.team_cache.items() if k == name]:
                # 检查是否是新增还是已有
                if name in self.team_cache and self.team_cache[name] == tid:
                    pass
            if name not in [k for k, v in self.team_cache.items() if v == tid and k != name]:
                # 简单统计
                if tid >= self.next_team_id - new_teams if new_teams else False:
                    new_teams += 1
                else:
                    matched += 1

        dst.commit()

        # 重新统计
        total_new = dst.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        logger.info(f"  Teams after sync: {total_new:,} (was {len(self.team_cache) - new_teams} before, +{new_teams} new)")

        src.close()
        dst.close()

    # ============================================================
    # Step 3: Sync Leagues
    # ============================================================

    def step_sync_leagues(self):
        """从oddsfe同步联赛：匹配已有league_id，新增oddsfe独有的"""
        logger.info("Step: Syncing leagues from oddsfe...")
        src = sqlite3.connect(self.oddsfe_path)
        dst = sqlite3.connect(self.db_path)

        self._load_existing_leagues(dst)

        # 提取oddsfe所有联赛
        oddsfe_leagues = set()
        for r in src.execute("SELECT DISTINCT tournament_name, tournament_id, category_name FROM oddsfe").fetchall():
            if r[0]:
                oddsfe_leagues.add((r[0], r[1], r[2]))

        new_leagues = 0
        for tname, tid, cat in sorted(oddsfe_leagues):
            lid = self._get_or_create_league(tname, cat or '', dst)
            # 也更新oddsfe_tournament_id
            if tid:
                dst.execute("UPDATE leagues SET oddsfe_tournament_id = ?, oddsfe_tournament_name = ? WHERE league_id = ? AND oddsfe_tournament_id IS NULL",
                           (str(tid), tname, lid))

        dst.commit()

        total_leagues = dst.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
        logger.info(f"  Leagues after sync: {total_leagues:,}")

        src.close()
        dst.close()

    # ============================================================
    # Step 4: Sync Matches
    # ============================================================

    def step_sync_matches(self):
        """从oddsfe同步比赛到matches表（增量，不替换）"""
        logger.info("Step: Syncing matches from oddsfe...")
        src = sqlite3.connect(self.oddsfe_path)
        dst = sqlite3.connect(self.db_path)

        # 加载映射
        self._load_existing_teams(dst)
        self._load_existing_leagues(dst)

        # 检查已有哪些oddsfe_ match_id
        existing_oddsfe_ids = set()
        cur = dst.execute("SELECT match_id FROM matches WHERE match_id LIKE 'oddsfe_%'")
        for r in cur.fetchall():
            existing_oddsfe_ids.add(r[0])

        total = src.execute("SELECT COUNT(*) FROM oddsfe").fetchone()[0]
        logger.info(f"  Total oddsfe rows: {total:,}, already synced: {len(existing_oddsfe_ids):,}")

        batch = []
        batch_size = 1000
        count = 0
        skip_no_team = 0
        skip_exists = 0

        cursor = src.execute("""
            SELECT event_id, event_start_at, event_status,
                   event_score_home, event_score_away,
                   tournament_name, tournament_id,
                   category_name,
                   team_home_name, team_away_name, team_home_id, team_away_id,
                   main_out_0, main_out_1, main_out_2
            FROM oddsfe ORDER BY event_start_at
        """)

        for row in cursor:
            eid, start_at, raw_status, score_h, score_a, \
            tname, tid, cat, \
            home_name, away_name, home_tid, away_tid, \
            main_0, main_1, main_2 = row

            match_id = f"oddsfe_{eid}"

            # 跳过已同步的
            if match_id in existing_oddsfe_ids:
                skip_exists += 1
                continue

            # 标准化
            status = normalize_status(raw_status)
            bj_date, bj_time, time_type = utc_to_beijing(start_at)

            # team_id映射
            home_team_id = self._get_or_create_team(home_name, cat or '', dst) if home_name else None
            away_team_id = self._get_or_create_team(away_name, cat or '', dst) if away_name else None
            if not home_team_id or not away_team_id:
                skip_no_team += 1
                continue

            # league_id映射
            league_id = self._get_or_create_league(tname or '', cat or '', dst)

            # 赛事类型
            comp_type, part_type = classify_competition(tname or '', cat or '')

            # 比分
            hg = safe_int(score_h)
            ag = safe_int(score_a)
            result = None
            if hg is not None and ag is not None:
                if hg > ag: result = 'H'
                elif hg < ag: result = 'A'
                else: result = 'D'

            # PINNACLE摘要赔率
            odds_h = safe_float(main_0)
            odds_d = safe_float(main_1)
            odds_a = safe_float(main_2)

            batch.append((
                match_id, bj_date, bj_time, time_type,
                home_team_id, away_team_id, league_id,
                comp_type, part_type,
                hg, ag, result, status,
                start_at, tname, cat,
                odds_h, odds_d, odds_a,
                'oddsfe'
            ))

            count += 1
            if len(batch) >= batch_size:
                dst.executemany("""
                    INSERT OR IGNORE INTO matches
                    (match_id, match_date, match_time, time_type,
                     home_team_id, away_team_id, league_id,
                     competition_type, participant_type,
                     home_goals, away_goals, result, status,
                     event_start_at, tournament_name, category_name,
                     odds_home, odds_draw, odds_away, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch)
                dst.commit()
                batch = []
                if count % 50000 == 0:
                    logger.info(f"  Progress: {count:,} new matches")

        if batch:
            dst.executemany("""
                INSERT OR IGNORE INTO matches
                (match_id, match_date, match_time, time_type,
                 home_team_id, away_team_id, league_id,
                 competition_type, participant_type,
                 home_goals, away_goals, result, status,
                 event_start_at, tournament_name, category_name,
                 odds_home, odds_draw, odds_away, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)
            dst.commit()

        logger.info(f"  Done: {count:,} new matches, {skip_exists:,} already existed, {skip_no_team} skipped (no team)")
        src.close()
        dst.close()

    # ============================================================
    # Step 5: Sync Odds (normalized)
    # ============================================================

    def step_sync_odds(self):
        """从oddsfe同步赔率到match_odds_normalized表"""
        logger.info("Step: Syncing odds from oddsfe...")
        src = sqlite3.connect(self.oddsfe_path)
        dst = sqlite3.connect(self.db_path)

        # 第一层：PINNACLE摘要赔率 (main_out_0/1/2)
        logger.info("  Layer 1: PINNACLE summary odds (main_out_0/1/2)...")
        batch = []
        count = 0

        cursor = src.execute("""
            SELECT event_id, main_out_0, main_out_1, main_out_2, event_start_at
            FROM oddsfe
            WHERE main_out_0 IS NOT NULL AND main_out_0 != ''
        """)

        for row in cursor:
            eid, h, d, a, start_at = row
            match_id = f"oddsfe_{eid}"
            oh = safe_float(h)
            od = safe_float(d)
            oa = safe_float(a)
            if oh and od and oa:
                batch.append((match_id, 'PINNACLE', 'prematch', '1X2', oh, od, oa, None, start_at, 'oddsfe'))
                count += 1
                if len(batch) >= 1000:
                    dst.executemany("""
                        INSERT OR IGNORE INTO match_odds_normalized
                        (match_id, bookmaker, snapshot_type, market, home, draw, away, line, captured_at, source)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, batch)
                    dst.commit()
                    batch = []

        if batch:
            dst.executemany("""
                INSERT OR IGNORE INTO match_odds_normalized
                (match_id, bookmaker, snapshot_type, market, home, draw, away, line, captured_at, source)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, batch)
            dst.commit()

        logger.info(f"  Layer 1 done: {count:,} PINNACLE 1X2 records")

        # 第二层：378列展开赔率
        logger.info("  Layer 2: Full multi-bookmaker odds (378 columns)...")
        count2 = 0

        all_cols = [col[1] for col in src.execute("PRAGMA table_info(oddsfe)").fetchall()]

        for market, col_names in [
            ('1X2', ['home', 'draw', 'away']),
            ('OVER_UNDER', ['over', 'line', 'under']),
            ('ASIAN_HANDICAP', ['home', 'handicap', 'away']),
            ('BOTH_TEAMS_TO_SCORE', ['yes', 'no']),
        ]:
            for timing in ['prematch', 'live']:
                for bk in BOOKMAKERS:
                    odds_cols = [f'{market}_{timing}_{bk}_{cn}' for cn in col_names]

                    if not all(c in all_cols for c in odds_cols):
                        continue

                    # 跳过PINNACLE 1X2 prematch（已在Layer 1处理）
                    if bk == 'PINNACLE' and market == '1X2' and timing == 'prematch':
                        continue

                    col_select = ', '.join(f'"{c}"' for c in odds_cols)
                    batch = []

                    cursor = src.execute(f"""
                        SELECT event_id, {col_select}
                        FROM oddsfe
                        WHERE "{odds_cols[0]}" IS NOT NULL AND "{odds_cols[0]}" != ''
                    """)

                    for row in cursor:
                        eid = row[0]
                        vals = [safe_float(row[i+1]) for i in range(len(odds_cols))]
                        if not any(vals):
                            continue

                        match_id = f"oddsfe_{eid}"

                        if market == '1X2':
                            h, d, a = vals[0], vals[1], vals[2]
                            line_val = None
                        elif market == 'OVER_UNDER':
                            h, line_val, a = vals[0], vals[1], vals[2]
                            d = None
                        elif market == 'ASIAN_HANDICAP':
                            h, line_val, a = vals[0], vals[1], vals[2]
                            d = None
                        elif market == 'BOTH_TEAMS_TO_SCORE':
                            h, a = vals[0], vals[1]
                            d = None
                            line_val = None

                        batch.append((match_id, bk, timing, market, h, d, a, line_val, None, 'oddsfe'))
                        count2 += 1

                        if len(batch) >= 1000:
                            dst.executemany("""
                                INSERT OR IGNORE INTO match_odds_normalized
                                (match_id, bookmaker, snapshot_type, market, home, draw, away, line, captured_at, source)
                                VALUES (?,?,?,?,?,?,?,?,?,?)
                            """, batch)
                            dst.commit()
                            batch = []

                    if batch:
                        dst.executemany("""
                            INSERT OR IGNORE INTO match_odds_normalized
                            (match_id, bookmaker, snapshot_type, market, home, draw, away, line, captured_at, source)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, batch)
                        dst.commit()

        logger.info(f"  Layer 2 done: {count2:,} additional odds records")
        src.close()
        dst.close()

    # ============================================================
    # Step 6: Validate
    # ============================================================

    def step_validate(self):
        """验证同步结果"""
        logger.info("Step: Validating...")
        conn = sqlite3.connect(self.db_path)

        print("\n" + "=" * 60)
        print("VALIDATION REPORT")
        print("=" * 60)

        # matches
        total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        oddsfe_matches = conn.execute("SELECT COUNT(*) FROM matches WHERE match_id LIKE 'oddsfe_%'").fetchone()[0]
        other_matches = total - oddsfe_matches
        print(f"\nmatches: {total:,} rows ({oddsfe_matches:,} from oddsfe, {other_matches:,} existing)")

        print("  status distribution:")
        for r in conn.execute("SELECT status, COUNT(*) FROM matches GROUP BY status ORDER BY 2 DESC").fetchall():
            print(f"    {r[0]}: {r[1]:,}")

        print("  competition_type distribution (oddsfe only):")
        for r in conn.execute("SELECT competition_type, COUNT(*) FROM matches WHERE match_id LIKE 'oddsfe_%' GROUP BY competition_type ORDER BY 2 DESC").fetchall():
            print(f"    {r[0]}: {r[1]:,}")

        print("  time_type distribution:")
        for r in conn.execute("SELECT time_type, COUNT(*) FROM matches GROUP BY time_type").fetchall():
            print(f"    {r[0]}: {r[1]:,}")

        has_odds = conn.execute("SELECT COUNT(*) FROM matches WHERE odds_home IS NOT NULL").fetchone()[0]
        print(f"  with PINNACLE odds: {has_odds:,} ({has_odds*100//max(total,1)}%)")

        # match_odds_normalized
        odds_total = conn.execute("SELECT COUNT(*) FROM match_odds_normalized").fetchone()[0]
        print(f"\nmatch_odds_normalized: {odds_total:,} rows")
        print("  by bookmaker:")
        for r in conn.execute("SELECT bookmaker, COUNT(*) FROM match_odds_normalized GROUP BY bookmaker ORDER BY 2 DESC LIMIT 10").fetchall():
            print(f"    {r[0]}: {r[1]:,}")
        print("  by market:")
        for r in conn.execute("SELECT market, COUNT(*) FROM match_odds_normalized GROUP BY market ORDER BY 2 DESC").fetchall():
            print(f"    {r[0]}: {r[1]:,}")

        # teams
        team_total = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        team_cn = conn.execute("SELECT COUNT(*) FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''").fetchone()[0]
        print(f"\nteams: {team_total:,} rows, {team_cn:,} with CN name ({team_cn*100//max(team_total,1)}%)")

        # leagues
        league_total = conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
        print(f"\nleagues: {league_total:,} rows")

        # FK integrity
        print("\nFK integrity:")
        bad_fk = conn.execute("""
            SELECT COUNT(*) FROM matches
            WHERE home_team_id NOT IN (SELECT team_id FROM teams)
               OR away_team_id NOT IN (SELECT team_id FROM teams)
        """).fetchone()[0]
        print(f"  matches with invalid team_id: {bad_fk}")

        # Other preserved tables
        print("\nPreserved tables:")
        for table in ['lottery_matches', 'elo_ratings', 'bet_records', 'team_form', 'h2h_records', 'fifa_rankings']:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {cnt:,}")

        # Sample data
        print("\nSample oddsfe matches (most recent):")
        for r in conn.execute("""
            SELECT m.match_date, m.match_time, m.status, m.competition_type,
                   ht.name_en, at.name_en,
                   m.home_goals, m.away_goals,
                   m.odds_home, m.odds_draw, m.odds_away
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE m.match_id LIKE 'oddsfe_%' AND m.status = 'scheduled'
            ORDER BY m.match_date DESC, m.match_time LIMIT 5
        """).fetchall():
            print(f"  {r}")

        conn.close()

    # ============================================================
    # Incremental Sync (for daily updates)
    # ============================================================

    def run_incremental(self, days: int = 5):
        """增量同步：只处理最近N天的数据更新

        处理3种情况：
        1. 新比赛（oddsfe有新event_id）→ INSERT
        2. 赛果更新（scheduled→finished）→ UPDATE status+比分
        3. 赔率变化 → INSERT/UPDATE match_odds_normalized
        """
        logger.info(f"Incremental sync for last {days} days...")
        src = sqlite3.connect(self.oddsfe_path)
        dst = sqlite3.connect(self.db_path)

        self._load_existing_teams(dst)
        self._load_existing_leagues(dst)

        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')

        # 查询oddsfe最近数据
        cursor = src.execute("""
            SELECT event_id, event_start_at, event_status,
                   event_score_home, event_score_away,
                   tournament_name, tournament_id,
                   category_name,
                   team_home_name, team_away_name, team_home_id, team_away_id,
                   main_out_0, main_out_1, main_out_2
            FROM oddsfe
            WHERE event_start_at >= ?
            ORDER BY event_start_at
        """, (cutoff,))

        new_matches = 0
        updated_matches = 0
        new_odds = 0

        for row in cursor:
            eid, start_at, raw_status, score_h, score_a, \
            tname, tid, cat, \
            home_name, away_name, home_tid, away_tid, \
            main_0, main_1, main_2 = row

            match_id = f"oddsfe_{eid}"
            status = normalize_status(raw_status)

            # 检查是否已存在
            existing = dst.execute("SELECT status, home_goals, away_goals FROM matches WHERE match_id = ?", (match_id,)).fetchone()

            if existing:
                old_status, old_hg, old_ag = existing
                hg = safe_int(score_h)
                ag = safe_int(score_a)

                # 赛果更新
                if old_status == 'scheduled' and status == 'finished' and hg is not None:
                    result = 'H' if hg > ag else ('A' if hg < ag else 'D')
                    dst.execute("""
                        UPDATE matches SET status = ?, home_goals = ?, away_goals = ?, result = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE match_id = ?
                    """, (status, hg, ag, result, match_id))
                    updated_matches += 1

                    # 写入closing赔率
                    oh = safe_float(main_0)
                    od = safe_float(main_1)
                    oa = safe_float(main_2)
                    if oh and od and oa:
                        dst.execute("""
                            INSERT OR IGNORE INTO match_odds_normalized
                            (match_id, bookmaker, snapshot_type, market, home, draw, away, line, captured_at, source)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (match_id, 'PINNACLE', 'closing', '1X2', oh, od, oa, None, start_at, 'oddsfe'))
                        new_odds += 1
            else:
                # 新比赛
                bj_date, bj_time, time_type = utc_to_beijing(start_at)
                home_team_id = self._get_or_create_team(home_name, cat or '', dst) if home_name else None
                away_team_id = self._get_or_create_team(away_name, cat or '', dst) if away_name else None
                if not home_team_id or not away_team_id:
                    continue

                league_id = self._get_or_create_league(tname or '', cat or '', dst)
                comp_type, part_type = classify_competition(tname or '', cat or '')

                hg = safe_int(score_h)
                ag = safe_int(score_a)
                result = None
                if hg is not None and ag is not None:
                    if hg > ag: result = 'H'
                    elif hg < ag: result = 'A'
                    else: result = 'D'

                odds_h = safe_float(main_0)
                odds_d = safe_float(main_1)
                odds_a = safe_float(main_2)

                dst.execute("""
                    INSERT OR IGNORE INTO matches
                    (match_id, match_date, match_time, time_type,
                     home_team_id, away_team_id, league_id,
                     competition_type, participant_type,
                     home_goals, away_goals, result, status,
                     event_start_at, tournament_name, category_name,
                     odds_home, odds_draw, odds_away, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    match_id, bj_date, bj_time, time_type,
                    home_team_id, away_team_id, league_id,
                    comp_type, part_type,
                    hg, ag, result, status,
                    start_at, tname, cat,
                    odds_h, odds_d, odds_a,
                    'oddsfe'
                ))

                # 也写入赔率
                if odds_h and odds_d and odds_a:
                    dst.execute("""
                        INSERT OR IGNORE INTO match_odds_normalized
                        (match_id, bookmaker, snapshot_type, market, home, draw, away, line, captured_at, source)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (match_id, 'PINNACLE', 'prematch', '1X2', odds_h, odds_d, odds_a, None, start_at, 'oddsfe'))

                new_matches += 1

        dst.commit()
        src.close()
        dst.close()

        logger.info(f"  Incremental sync done: {new_matches} new matches, {updated_matches} updated, {new_odds} new odds")

    # ============================================================
    # Runner
    # ============================================================

    def run(self, steps=None):
        """执行同步管道"""
        start = time.time()
        self.load_chinese_names()

        all_steps = [
            ('migrate_schema', self.step_migrate_schema),
            ('sync_teams', self.step_sync_teams),
            ('sync_leagues', self.step_sync_leagues),
            ('sync_matches', self.step_sync_matches),
            ('sync_odds', self.step_sync_odds),
            ('validate', self.step_validate),
        ]

        if steps:
            all_steps = [(n, fn) for n, fn in all_steps if n in steps]

        for name, fn in all_steps:
            t0 = time.time()
            fn()
            logger.info(f"  Step '{name}' took {time.time()-t0:.1f}s")

        logger.info(f"\nTotal time: {time.time()-start:.1f}s")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='oddsfe → football_v2.db 增量同步管道')
    parser.add_argument('--oddsfe', required=True, help='oddsfe_merged.db路径')
    parser.add_argument('--db', required=True, help='football_v2.db路径')
    parser.add_argument('--step', nargs='*', help='只执行指定步骤: migrate_schema sync_teams sync_leagues sync_matches sync_odds validate')
    parser.add_argument('--incremental', action='store_true', help='增量同步模式（最近5天）')
    parser.add_argument('--days', type=int, default=5, help='增量同步天数')
    args = parser.parse_args()

    sync = OddsfeSync(args.oddsfe, args.db)

    if args.incremental:
        sync.load_chinese_names()
        sync.run_incremental(days=args.days)
    else:
        sync.run(steps=args.step)
