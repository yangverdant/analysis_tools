#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新数据库中比赛的时间（北京时间转当地时间）"""

import sqlite3

DATABASE_PATH = 'data/football_unified.db'

# 联赛时区偏移（北京时间UTC+8 到当地时间的偏移）
TIMEZONE_OFFSETS = {
    'Bundesliga': -6,
    'Bundesliga 2': -6,
    'Premier League': -7,
    'Championship': -7,
    'La Liga': -6,
    'Segunda Division': -6,
    'Serie A': -6,
    'Serie B': -6,
    'Ligue 1': -6,
    'Ligue 2': -6,
    'Eredivisie': -6,
    'Primeira Liga': -7,
    'Super Lig': -5,
    'Jupiler League': -6,
    'Eliteserien': -6,
    'Allsvenskan': -6,
    'J1 League': -1,
    'J2 League': -1,
    'K League 1': -1,
    'K League 2': -1,
    'Chinese Super League': 0,
    'Saudi Pro League': -5,
    'MLS': -12,
    'Serie A Brazil': -11,
    'Serie B Brazil': -11,
    'Primera Division': -11,
    'FA Cup': -7,
}

def convert_time(beijing_time_str, offset):
    """将北京时间转换为当地时间"""
    try:
        hours, minutes = map(int, beijing_time_str.split(':'))
        beijing_total_minutes = hours * 60 + minutes
        local_total_minutes = beijing_total_minutes + offset * 60

        if local_total_minutes < 0:
            local_total_minutes += 24 * 60
        elif local_total_minutes >= 24 * 60:
            local_total_minutes -= 24 * 60

        local_hours = local_total_minutes // 60
        local_minutes = local_total_minutes % 60

        return f"{local_hours:02d}:{local_minutes:02d}"
    except:
        return beijing_time_str

def main():
    """主函数"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取所有联赛
    cursor.execute("SELECT league_id, name FROM leagues")
    leagues = cursor.fetchall()

    total_updated = 0

    for league_id, league_name in leagues:
        offset = TIMEZONE_OFFSETS.get(league_name, 0)
        if offset == 0:
            continue

        # 获取该联赛2026年5月的比赛
        cursor.execute("""
            SELECT match_id, match_time FROM matches
            WHERE league_id = ? AND match_date >= '2026-05-01' AND match_date <= '2026-05-31'
            AND status = 'Finished'
        """, (league_id,))

        matches = cursor.fetchall()
        if not matches:
            continue

        updated = 0
        for match_id, match_time in matches:
            if not match_time:
                continue

            # 检查时间是否是典型的北京时间（晚上18-24或凌晨00-08）
            try:
                hours = int(match_time.split(':')[0])
                # 北京时间通常在晚上
                if 18 <= hours <= 24 or 0 <= hours <= 8:
                    new_time = convert_time(match_time, offset)
                    if new_time != match_time:
                        cursor.execute("""
                            UPDATE matches SET match_time = ? WHERE match_id = ?
                        """, (new_time, match_id))
                        updated += 1
            except:
                continue

        if updated > 0:
            print(f"{league_name}: Updated {updated} matches")
            total_updated += updated

    conn.commit()
    conn.close()
    print(f"\nTotal updated: {total_updated} matches")

if __name__ == '__main__':
    main()