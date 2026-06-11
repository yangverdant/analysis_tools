"""
补充德乙联赛CSV中的详细数据到数据库:
- 半场比分
- 射门、射正、犯规、角球
- 黄红牌
- 裁判、观众人数
- 多家庄家赔率
"""

import sqlite3
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"
CSV_DIR = PROJECT_ROOT / "data" / "01_europe_leagues" / "bundesliga_2"

BUNDESLIGA_2_ID = 8


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
    """安全转换为整数"""
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except:
        return None


def safe_float(val):
    """安全转换为浮点数"""
    if val is None or val == '':
        return None
    try:
        return float(val)
    except:
        return None


def import_match_stats(csv_path: Path, conn) -> dict:
    """导入比赛统计数据"""
    result = {
        'file': csv_path.name,
        'total': 0,
        'updated': 0,
        'not_found': 0
    }

    cursor = conn.cursor()

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                result['total'] += 1

                try:
                    home_team = row.get('HomeTeam', '').strip()
                    away_team = row.get('AwayTeam', '').strip()
                    date_str = row.get('Date', '')

                    if not home_team or not away_team or not date_str:
                        continue

                    match_date = parse_date(date_str)
                    if not match_date:
                        continue

                    # 查找比赛
                    cursor.execute('''
                        SELECT m.match_id, ht.name_en, at.name_en
                        FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.team_id
                        JOIN teams at ON m.away_team_id = at.team_id
                        WHERE m.match_date = ?
                        AND m.league_id = ?
                    ''', (match_date, BUNDESLIGA_2_ID))

                    matches = cursor.fetchall()

                    # 匹配球队
                    match_id = None
                    for m in matches:
                        if home_team.lower() in m[1].lower() or m[1].lower() in home_team.lower():
                            if away_team.lower() in m[2].lower() or m[2].lower() in away_team.lower():
                                match_id = m[0]
                                break

                    if not match_id:
                        result['not_found'] += 1
                        continue

                    # 提取数据
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

                    # 犯规
                    hf = safe_int(row.get('HF'))
                    af = safe_int(row.get('AF'))
                    if hf is not None:
                        update_data['home_fouls'] = hf
                    if af is not None:
                        update_data['away_fouls'] = af

                    # 角球
                    hc = safe_int(row.get('HC'))
                    ac = safe_int(row.get('AC'))
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

                    # 裁判
                    referee = row.get('Referee', '').strip()
                    if referee:
                        update_data['referee'] = referee

                    # 观众人数
                    attendance = safe_int(row.get('Attendance'))
                    if attendance is not None:
                        update_data['attendance'] = attendance

                    # 时间
                    time_str = row.get('Time', '').strip()
                    if time_str:
                        update_data['match_time'] = time_str

                    # 赔率 (使用平均赔率或Bet365)
                    odds_h = safe_float(row.get('AvgH')) or safe_float(row.get('B365H'))
                    odds_d = safe_float(row.get('AvgD')) or safe_float(row.get('B365D'))
                    odds_a = safe_float(row.get('AvgA')) or safe_float(row.get('B365A'))
                    if odds_h:
                        update_data['odds_home'] = odds_h
                    if odds_d:
                        update_data['odds_draw'] = odds_d
                    if odds_a:
                        update_data['odds_away'] = odds_a

                    # 更新数据库
                    if update_data:
                        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
                        values = list(update_data.values()) + [match_id]
                        cursor.execute(f'''
                            UPDATE matches SET {set_clause}
                            WHERE match_id = ?
                        ''', values)
                        result['updated'] += 1

                except Exception as e:
                    pass

        conn.commit()

    except Exception as e:
        result['error'] = str(e)

    return result


def main():
    print("=" * 60)
    print("补充德乙比赛详细统计数据")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 首先添加缺失的列
    print("\n1. 检查并添加缺失的列...")
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
                print(f"   添加列: {col_name}")
            except Exception as e:
                print(f"   添加列失败 {col_name}: {e}")

    conn.commit()

    # 导入CSV数据
    print("\n2. 导入CSV统计数据...")
    csv_files = sorted(CSV_DIR.glob("bundesliga_2_*.csv"))
    csv_files = [f for f in csv_files if '_all' not in f.name]

    total_result = {'total': 0, 'updated': 0, 'not_found': 0}

    for csv_file in csv_files:
        result = import_match_stats(csv_file, conn)
        total_result['total'] += result['total']
        total_result['updated'] += result['updated']
        total_result['not_found'] += result['not_found']

        if result['updated'] > 0:
            print(f"   {csv_file.name}: 更新 {result['updated']}/{result['total']}")

    print(f"\n   总计: {total_result['total']} 条, 更新 {total_result['updated']} 条")

    # 统计结果
    print("\n" + "=" * 60)
    print("更新后数据统计")
    print("=" * 60)

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = 8')
    total = cursor.fetchone()[0]

    fields = [
        ('home_goals_ht', '半场比分'),
        ('home_shots', '射门'),
        ('home_shots_on', '射正'),
        ('home_corners', '角球'),
        ('home_fouls', '犯规'),
        ('home_yellows', '黄牌'),
        ('home_reds', '红牌'),
        ('referee', '裁判'),
        ('attendance', '观众人数'),
        ('match_time', '开球时间'),
        ('odds_home', '赔率'),
    ]

    print(f"\n比赛总数: {total}")
    for field, name in fields:
        cursor.execute(f'''
            SELECT COUNT(*) FROM matches WHERE league_id = 8
            AND {field} IS NOT NULL AND {field} != ''
        ''')
        count = cursor.fetchone()[0]
        pct = count / total * 100
        print(f"   {name}: {count} ({pct:.1f}%)")

    conn.close()
    print("\n补充完成！")


if __name__ == "__main__":
    main()
