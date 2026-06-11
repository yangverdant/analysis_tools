"""
德甲联赛数据完整采集:
1. CSV数据导入
2. 统计数据补充
3. xG数据生成
4. 赛事规则报告
"""

import sqlite3
import csv
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CSV_DIR = PROJECT_ROOT / "data" / "01_europe_leagues" / "bundesliga"

BUNDESLIGA_ID = 7


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(date_str: str) -> str:
    """解析日期"""
    if not date_str:
        return None
    try:
        if '/' in date_str:
            parts = date_str.split('/')
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else None
            if year is not None:
                full_year = 2000 + year if year <= 26 else 1900 + year
                return f"{full_year:04d}-{month:02d}-{day:02d}"
        if '-' in date_str:
            if len(date_str.split('-')[0]) == 2:
                parts = date_str.split('-')
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                full_year = 2000 + year if year <= 26 else 1900 + year
                return f"{full_year:04d}-{month:02d}-{day:02d}"
            return date_str
    except:
        pass
    return None


def safe_int(val):
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except:
        return None


def safe_float(val):
    if val is None or val == '':
        return None
    try:
        return float(val)
    except:
        return None


def get_or_create_team(conn, team_name: str, country: str = 'Germany') -> int:
    """获取或创建球队"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT team_id FROM teams
        WHERE name_en = ? OR name_cn = ? OR name_en LIKE ?
    ''', (team_name, team_name, f'%{team_name}%'))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute('''
        INSERT INTO teams (name_en, name_cn, country, created_at, updated_at)
        VALUES (?, '', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ''', (team_name, country))
    return cursor.lastrowid


def import_bundesliga_csv():
    """导入德甲CSV数据"""
    print("=" * 60)
    print("导入德甲CSV数据")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    csv_files = sorted(CSV_DIR.glob("bundesliga_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    print(f"找到 {len(csv_files)} 个CSV文件")

    total_result = {'total': 0, 'inserted': 0, 'updated': 0, 'skipped': 0}

    for csv_file in csv_files:
        # 从文件名提取赛季
        season_str = csv_file.stem.replace('bundesliga_', '')

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    total_result['total'] += 1

                    home_team = row.get('HomeTeam', '').strip()
                    away_team = row.get('AwayTeam', '').strip()

                    if not home_team or not away_team:
                        total_result['skipped'] += 1
                        continue

                    date_str = row.get('Date', '')
                    match_date = parse_date(date_str)

                    if not match_date:
                        total_result['skipped'] += 1
                        continue

                    home_team_id = get_or_create_team(conn, home_team)
                    away_team_id = get_or_create_team(conn, away_team)

                    match_time = row.get('Time', '')
                    home_goals = safe_int(row.get('FTHG'))
                    away_goals = safe_int(row.get('FTAG'))
                    ftr = row.get('FTR', '')
                    status = 'finished' if home_goals is not None else 'scheduled'

                    # 检查是否已存在
                    cursor.execute('''
                        SELECT match_id FROM matches
                        WHERE match_date = ? AND home_team_id = ? AND away_team_id = ?
                    ''', (match_date, home_team_id, away_team_id))

                    existing = cursor.fetchone()

                    if existing:
                        # 更新
                        cursor.execute('''
                            UPDATE matches SET
                                home_goals = COALESCE(?, home_goals),
                                away_goals = COALESCE(?, away_goals),
                                status = ?,
                                match_time = COALESCE(?, match_time),
                                result = COALESCE(?, result),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE match_id = ?
                        ''', (home_goals, away_goals, status, match_time or None, ftr or None, existing[0]))
                        total_result['updated'] += 1
                    else:
                        # 插入
                        cursor.execute('''
                            INSERT INTO matches (
                                match_date, match_time, home_team_id, away_team_id,
                                home_goals, away_goals, status, league_id, result,
                                source, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv_import',
                                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ''', (match_date, match_time or None, home_team_id, away_team_id,
                              home_goals, away_goals, status, BUNDESLIGA_ID, ftr))
                        total_result['inserted'] += 1

        except Exception as e:
            print(f"处理 {csv_file.name} 出错: {e}")

    conn.commit()

    print(f"\n导入结果:")
    print(f"  总记录: {total_result['total']}")
    print(f"  新增: {total_result['inserted']}")
    print(f"  更新: {total_result['updated']}")

    conn.close()
    return total_result


def import_match_stats():
    """导入比赛统计数据"""
    print("\n" + "=" * 60)
    print("导入德甲统计数据")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 添加缺失的列
    columns_to_add = [
        ('home_shots_on', 'INTEGER'),
        ('away_shots_on', 'INTEGER'),
        ('home_yellows', 'INTEGER'),
        ('away_yellows', 'INTEGER'),
        ('home_reds', 'INTEGER'),
        ('away_reds', 'INTEGER'),
    ]

    for col_name, col_type in columns_to_add:
        cursor.execute(f"PRAGMA table_info(matches)")
        columns = [r[1] for r in cursor.fetchall()]
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE matches ADD COLUMN {col_name} {col_type}")
                print(f"  添加列: {col_name}")
            except:
                pass

    csv_files = sorted(CSV_DIR.glob("bundesliga_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total_updated = 0

    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    home_team = row.get('HomeTeam', '').strip()
                    away_team = row.get('AwayTeam', '').strip()
                    date_str = row.get('Date', '')
                    match_date = parse_date(date_str)

                    if not home_team or not away_team or not match_date:
                        continue

                    # 查找比赛
                    cursor.execute('''
                        SELECT m.match_id, ht.name_en, at.name_en
                        FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.team_id
                        JOIN teams at ON m.away_team_id = at.team_id
                        WHERE m.match_date = ? AND m.league_id = ?
                    ''', (match_date, BUNDESLIGA_ID))

                    matches = cursor.fetchall()
                    match_id = None
                    for m in matches:
                        if home_team.lower() in m[1].lower() or m[1].lower() in home_team.lower():
                            if away_team.lower() in m[2].lower() or m[2].lower() in away_team.lower():
                                match_id = m[0]
                                break

                    if not match_id:
                        continue

                    update_data = {}

                    # 半场比分
                    hthg = safe_int(row.get('HTHG'))
                    htag = safe_int(row.get('HTAG'))
                    if hthg is not None:
                        update_data['home_goals_ht'] = hthg
                    if htag is not None:
                        update_data['away_goals_ht'] = htag

                    # 射门
                    hs = safe_int(row.get('HS'))
                    as_ = safe_int(row.get('AS'))
                    hst = safe_int(row.get('HST'))
                    ast = safe_int(row.get('AST'))
                    if hs is not None:
                        update_data['home_shots'] = hs
                    if as_ is not None:
                        update_data['away_shots'] = as_
                    if hst is not None:
                        update_data['home_shots_on'] = hst
                    if ast is not None:
                        update_data['away_shots_on'] = ast

                    # 犯规、角球
                    hf = safe_int(row.get('HF'))
                    af = safe_int(row.get('AF'))
                    hc = safe_int(row.get('HC'))
                    ac = safe_int(row.get('AC'))
                    if hf is not None:
                        update_data['home_fouls'] = hf
                    if af is not None:
                        update_data['away_fouls'] = af
                    if hc is not None:
                        update_data['home_corners'] = hc
                    if ac is not None:
                        update_data['away_corners'] = ac

                    # 黄红牌
                    hy = safe_int(row.get('HY'))
                    ay = safe_int(row.get('AY'))
                    hr = safe_int(row.get('HR'))
                    ar = safe_int(row.get('AR'))
                    if hy is not None:
                        update_data['home_yellows'] = hy
                    if ay is not None:
                        update_data['away_yellows'] = ay
                    if hr is not None:
                        update_data['home_reds'] = hr
                    if ar is not None:
                        update_data['away_reds'] = ar

                    # 裁判、观众
                    referee = row.get('Referee', '').strip()
                    attendance = safe_int(row.get('Attendance'))
                    if referee:
                        update_data['referee'] = referee
                    if attendance is not None:
                        update_data['attendance'] = attendance

                    # 赔率
                    odds_h = safe_float(row.get('AvgH')) or safe_float(row.get('B365H'))
                    odds_d = safe_float(row.get('AvgD')) or safe_float(row.get('B365D'))
                    odds_a = safe_float(row.get('AvgA')) or safe_float(row.get('B365A'))
                    if odds_h:
                        update_data['odds_home'] = odds_h
                    if odds_d:
                        update_data['odds_draw'] = odds_d
                    if odds_a:
                        update_data['odds_away'] = odds_a

                    if update_data:
                        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
                        values = list(update_data.values()) + [match_id]
                        cursor.execute(f'UPDATE matches SET {set_clause} WHERE match_id = ?', values)
                        total_updated += 1

        except Exception as e:
            pass

    conn.commit()
    print(f"  更新统计: {total_updated} 条")

    conn.close()


def generate_xg_data():
    """生成xG数据"""
    print("\n" + "=" * 60)
    print("生成德甲xG数据")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 检查有射门数据但无xG的比赛
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = ? AND home_shots IS NOT NULL AND home_xg IS NULL
    ''', (BUNDESLIGA_ID,))
    remaining = cursor.fetchone()[0]

    if remaining == 0:
        print("  所有有射门数据的比赛已有xG")
        conn.close()
        return

    print(f"  找到 {remaining} 场比赛需要生成xG")

    # 获取比赛数据
    cursor.execute('''
        SELECT m.match_id, m.home_shots, m.away_shots,
               m.home_shots_on, m.away_shots_on
        FROM matches m
        WHERE m.league_id = ? AND m.home_shots IS NOT NULL AND m.home_xg IS NULL
    ''', (BUNDESLIGA_ID,))

    matches = cursor.fetchall()

    updated = 0
    for match in matches:
        match_id, home_shots, away_shots, home_shots_on, away_shots_on = match

        home_shots = home_shots or 10
        away_shots = away_shots or 10
        home_shots_on = home_shots_on or 3
        away_shots_on = away_shots_on or 3

        # xG估算公式
        home_xg = round(home_shots_on * 0.28 + max(0, home_shots - home_shots_on) * 0.06, 2)
        away_xg = round(away_shots_on * 0.28 + max(0, away_shots - away_shots_on) * 0.06, 2)

        cursor.execute('''
            UPDATE matches SET home_xg = ?, away_xg = ?, source = 'estimated'
            WHERE match_id = ?
        ''', (home_xg, away_xg, match_id))
        updated += 1

    conn.commit()
    print(f"  生成xG: {updated} 场")

    conn.close()


def show_final_stats():
    """显示最终统计"""
    print("\n" + "=" * 60)
    print("德甲数据统计")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (BUNDESLIGA_ID,))
    total = cursor.fetchone()[0]

    fields = [
        ('home_goals', '比分'),
        ('home_goals_ht', '半场比分'),
        ('home_shots', '射门'),
        ('home_shots_on', '射正'),
        ('home_corners', '角球'),
        ('home_fouls', '犯规'),
        ('home_yellows', '黄牌'),
        ('home_reds', '红牌'),
        ('referee', '裁判'),
        ('attendance', '观众人数'),
        ('odds_home', '赔率'),
        ('home_xg', 'xG'),
    ]

    print(f"\n比赛总数: {total}")
    for field, name in fields:
        cursor.execute(f'''
            SELECT COUNT(*) FROM matches WHERE league_id = ?
            AND {field} IS NOT NULL AND {field} != ''
        ''', (BUNDESLIGA_ID,))
        count = cursor.fetchone()[0]
        pct = count / total * 100 if total > 0 else 0
        print(f"  {name}: {count} ({pct:.1f}%)")

    conn.close()


if __name__ == "__main__":
    # 1. 导入CSV数据
    import_bundesliga_csv()

    # 2. 导入统计数据
    import_match_stats()

    # 3. 生成xG数据
    generate_xg_data()

    # 4. 显示最终统计
    show_final_stats()

    print("\n德甲数据采集完成！")
