#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix malformed time format in CSV files.
The Time column has format like "05-16 20:00" which should be just "20:00".
"""

import os
import re

FILES_TO_FIX = [
    "D:/football_tools/data/01_europe_leagues/eredivisie/eredivisie_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/ligue_1/ligue_1_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/bundesliga/bundesliga_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/jupiler_league/jupiler_league_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/la_liga/la_liga_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/premier_league/premier_league_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/super_lig/super_lig_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/serie_a/serie_a_2024-2025.csv",
    "D:/football_tools/data/01_europe_leagues/primeira_liga/primeira_liga_2024-2025.csv",
]

def fix_time_format(filepath):
    """Fix the Time column format in a CSV file."""
    print("Processing: {}".format(filepath))

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Count malformed entries before fix
    pattern = r',(\d{2})-(\d{2}) (\d{2}:\d{2}),'
    matches = re.findall(pattern, content)

    if len(matches) == 0:
        print("  No malformed entries found")
        return 0

    # Fix: replace "MM-DD HH:MM" with "HH:MM"
    fixed_content = re.sub(pattern, r',\3,', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    print("  Fixed {} malformed time entries".format(len(matches)))
    return len(matches)

def main():
    print("Fixing malformed time format in CSV files...")
    print("=" * 60)

    total_fixed = 0
    for filepath in FILES_TO_FIX:
        if os.path.exists(filepath):
            fixed = fix_time_format(filepath)
            total_fixed += fixed
        else:
            print("File not found: {}".format(filepath))

    print("=" * 60)
    print("Done! Total fixed: {} entries".format(total_fixed))

if __name__ == "__main__":
    main()
