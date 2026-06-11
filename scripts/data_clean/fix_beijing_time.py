#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert Beijing time to local time in CSV files.
Handle date changes when time crosses midnight.

Beijing time is UTC+8
- Premier League (UK): UTC+0 (winter) / UTC+1 (summer BST) -> -8/-7 hours
- La Liga (Spain): UTC+1 (winter) / UTC+2 (summer CEST) -> -7/-6 hours
- Bundesliga (Germany): UTC+1 (winter) / UTC+2 (summer CEST) -> -7/-6 hours
- Serie A (Italy): UTC+1 (winter) / UTC+2 (summer CEST) -> -7/-6 hours
- Ligue 1 (France): UTC+1 (winter) / UTC+2 (summer CEST) -> -7/-6 hours

For simplicity, we use:
- Premier League: -8 hours (UK local time)
- Other European leagues: -7 hours (Central European time)
"""

import os
import csv
from datetime import datetime, timedelta

# Files to fix with their timezone offset from Beijing
FILES_TO_FIX = {
    # Premier League - UK time (Beijing -8 hours)
    "D:/football_tools/data/01_europe_leagues/premier_league/premier_league_2024-2025.csv": -8,
    # La Liga - Spain time (Beijing -7 hours)
    "D:/football_tools/data/01_europe_leagues/la_liga/la_liga_2024-2025.csv": -7,
    # Bundesliga - Germany time (Beijing -7 hours)
    "D:/football_tools/data/01_europe_leagues/bundesliga/bundesliga_2024-2025.csv": -7,
    # Serie A - Italy time (Beijing -7 hours)
    "D:/football_tools/data/01_europe_leagues/serie_a/serie_a_2024-2025.csv": -7,
    # Ligue 1 - France time (Beijing -7 hours)
    "D:/football_tools/data/01_europe_leagues/ligue_1/ligue_1_2024-2025.csv": -7,
    # Eredivisie - Netherlands time (Beijing -7 hours)
    "D:/football_tools/data/01_europe_leagues/eredivisie/eredivisie_2024-2025.csv": -7,
    # Jupiler League - Belgium time (Beijing -7 hours)
    "D:/football_tools/data/01_europe_leagues/jupiler_league/jupiler_league_2024-2025.csv": -7,
    # Primeira Liga - Portugal time (Beijing -8 hours, same as UK)
    "D:/football_tools/data/01_europe_leagues/primeira_liga/primeira_liga_2024-2025.csv": -8,
    # Super Lig - Turkey time (Beijing -6 hours)
    "D:/football_tools/data/01_europe_leagues/super_lig/super_lig_2024-2025.csv": -6,
}

def is_beijing_time(time_str):
    """Check if time is likely Beijing time (00:00-07:00 range for European matches)."""
    try:
        hour = int(time_str.split(':')[0])
        # Beijing time 00:00-07:00 corresponds to European evening matches (17:00-00:00 local)
        return 0 <= hour < 8
    except:
        return False

def convert_beijing_to_local(date_str, time_str, offset_hours):
    """
    Convert Beijing time to local time.
    Returns (new_date, new_time) tuple.
    """
    try:
        # Parse date and time
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        # Apply offset (offset is negative, e.g., -8 for UK)
        local_dt = dt + timedelta(hours=offset_hours)

        new_date = local_dt.strftime("%Y-%m-%d")
        new_time = local_dt.strftime("%H:%M")

        return new_date, new_time
    except Exception as e:
        print(f"  Error converting {date_str} {time_str}: {e}")
        return date_str, time_str

def fix_file(filepath, offset_hours):
    """Fix time format in a CSV file."""
    print(f"Processing: {filepath}")
    print(f"  Timezone offset from Beijing: {offset_hours} hours")

    rows = []
    converted_count = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            date = row.get('Date', '')
            time = row.get('Time', '')

            # Check if this is Beijing time (late night/early morning)
            if time and is_beijing_time(time):
                new_date, new_time = convert_beijing_to_local(date, time, offset_hours)

                if new_date != date or new_time != time:
                    row['Date'] = new_date
                    row['Time'] = new_time
                    converted_count += 1
                    print(f"  Converted: {date} {time} -> {new_date} {new_time}")

            rows.append(row)

    # Write back
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Total converted: {converted_count} entries")
    return converted_count

def main():
    print("Converting Beijing time to local time...")
    print("=" * 60)

    total_converted = 0

    for filepath, offset in FILES_TO_FIX.items():
        if os.path.exists(filepath):
            converted = fix_file(filepath, offset)
            total_converted += converted
        else:
            print(f"File not found: {filepath}")

    print("=" * 60)
    print(f"Done! Total converted: {total_converted} entries")

if __name__ == "__main__":
    main()
