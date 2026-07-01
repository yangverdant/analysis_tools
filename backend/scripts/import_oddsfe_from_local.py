"""从本地oddsfe_merged.db(单表378列)导入到服务器格式(oddsfe_matches表)

本地schema: 单表oddsfe, 378列, 250K场
服务器schema: oddsfe_matches表, 13列(Pinnacle O/U + SPF)

映射:
  event_id → event_id
  event_start_at → event_start_at
  team_home_name → team_home_name
  team_away_name → team_away_name
  category_name → category_name
  tournament_name → tournament_name
  OVER_UNDER_prematch_PINNACLE_line → ou_pinnacle_line
  OVER_UNDER_prematch_PINNACLE_over → ou_pinnacle_over
  OVER_UNDER_prematch_PINNACLE_under → ou_pinnacle_under
  1X2_prematch_PINNACLE_home → spf_pinnacle_home
  1X2_prematch_PINNACLE_draw → spf_pinnacle_draw
  1X2_prematch_PINNACLE_away → spf_pinnacle_away

用法:
  python backend/scripts/import_oddsfe_from_local.py --local-db /path/to/local/oddsfe_merged.db --server-db /path/to/server/oddsfe_merged.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path


def import_data(local_db: str, server_db: str, batch_size: int = 1000):
    """从本地DB导入到服务器DB格式"""
    if not Path(local_db).exists():
        print(f'本地DB不存在: {local_db}')
        sys.exit(1)

    src = sqlite3.connect(local_db)
    src.row_factory = sqlite3.Row

    # 创建目标DB
    dst = sqlite3.connect(server_db)
    dst.execute("""
        CREATE TABLE IF NOT EXISTS oddsfe_matches (
            event_id TEXT PRIMARY KEY,
            event_start_at TEXT,
            team_home_name TEXT,
            team_away_name TEXT,
            category_name TEXT,
            tournament_name TEXT,
            ou_pinnacle_line REAL,
            ou_pinnacle_over REAL,
            ou_pinnacle_under REAL,
            ou_pinnacle_updated_at TEXT,
            spf_pinnacle_home REAL,
            spf_pinnacle_draw REAL,
            spf_pinnacle_away REAL
        )
    """)
    dst.commit()

    # 读取本地数据
    total = src.execute('SELECT COUNT(*) FROM oddsfe').fetchone()[0]
    print(f'本地DB: {total}场')

    inserted = 0
    skipped = 0
    offset = 0

    while offset < total:
        rows = src.execute(
            'SELECT event_id, event_start_at, team_home_name, team_away_name, '
            'category_name, tournament_name, '
            'OVER_UNDER_prematch_PINNACLE_line, '
            'OVER_UNDER_prematch_PINNACLE_over, '
            'OVER_UNDER_prematch_PINNACLE_under, '
            '1X2_prematch_PINNACLE_home, '
            '1X2_prematch_PINNACLE_draw, '
            '1X2_prematch_PINNACLE_away '
            'FROM oddsfe LIMIT ? OFFSET ?',
            (batch_size, offset)
        ).fetchall()

        if not rows:
            break

        batch = []
        for r in rows:
            eid = r['event_id']
            if not eid:
                skipped += 1
                continue
            try:
                ou_line = float(r['OVER_UNDER_prematch_PINNACLE_line']) if r['OVER_UNDER_prematch_PINNACLE_line'] else None
            except (ValueError, TypeError):
                ou_line = None
            try:
                ou_over = float(r['OVER_UNDER_prematch_PINNACLE_over']) if r['OVER_UNDER_prematch_PINNACLE_over'] else None
            except (ValueError, TypeError):
                ou_over = None
            try:
                ou_under = float(r['OVER_UNDER_prematch_PINNACLE_under']) if r['OVER_UNDER_prematch_PINNACLE_under'] else None
            except (ValueError, TypeError):
                ou_under = None
            try:
                spf_h = float(r['1X2_prematch_PINNACLE_home']) if r['1X2_prematch_PINNACLE_home'] else None
            except (ValueError, TypeError):
                spf_h = None
            try:
                spf_d = float(r['1X2_prematch_PINNACLE_draw']) if r['1X2_prematch_PINNACLE_draw'] else None
            except (ValueError, TypeError):
                spf_d = None
            try:
                spf_a = float(r['1X2_prematch_PINNACLE_away']) if r['1X2_prematch_PINNACLE_away'] else None
            except (ValueError, TypeError):
                spf_a = None

            batch.append((
                str(eid),
                r['event_start_at'],
                r['team_home_name'],
                r['team_away_name'],
                r['category_name'],
                r['tournament_name'],
                ou_line, ou_over, ou_under,
                r['event_start_at'],  # ou_pinnacle_updated_at = event_start_at
                spf_h, spf_d, spf_a
            ))

        if batch:
            dst.executemany("""
                INSERT OR REPLACE INTO oddsfe_matches
                (event_id, event_start_at, team_home_name, team_away_name,
                 category_name, tournament_name,
                 ou_pinnacle_line, ou_pinnacle_over, ou_pinnacle_under, ou_pinnacle_updated_at,
                 spf_pinnacle_home, spf_pinnacle_draw, spf_pinnacle_away)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            dst.commit()
            inserted += len(batch)

        offset += batch_size
        if offset % 10000 == 0 or offset >= total:
            print(f'  进度: {min(offset, total)}/{total} (已插入{inserted}, 跳过{skipped})')

    src.close()
    dst.close()
    print(f'\n完成: 共{total}场, 插入{inserted}场, 跳过{skipped}场')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-db', required=True, help='本地oddsfe_merged.db路径')
    parser.add_argument('--server-db', required=True, help='目标oddsfe_merged.db路径')
    parser.add_argument('--batch-size', type=int, default=1000)
    args = parser.parse_args()
    import_data(args.local_db, args.server_db, args.batch_size)


if __name__ == '__main__':
    main()
