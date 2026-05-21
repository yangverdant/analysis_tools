#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add empty Time column to CSV files that are missing it.
The Time column is inserted after the Date column.
"""

import os
import csv

def add_time_column(filepath):
    """Add empty Time column after Date column."""
    print("Processing: {}".format(filepath))

    # Try different encodings
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    content = None

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
                break
        except:
            continue

    if content is None:
        print("  Cannot read file, skipping")
        return False

    lines = content.strip().split('\n')
    if len(lines) < 2:
        print("  Empty file, skipping")
        return False

    header = lines[0].split(',')
    if 'Date' not in header:
        print("  No Date column found, skipping")
        return False

    date_idx = header.index('Date')

    # Insert Time column after Date
    new_header = header[:date_idx + 1] + ['Time'] + header[date_idx + 1:]

    new_lines = [','.join(new_header)]
    for line in lines[1:]:
        cols = line.split(',')
        new_row = cols[:date_idx + 1] + [''] + cols[date_idx + 1:]
        new_lines.append(','.join(new_row))

    # Write back with utf-8
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(new_lines))

    print("  Added Time column after Date")
    return True

def main():
    files_to_fix = []

    for root, dirs, files in os.walk('D:/football_tools/data'):
        # Skip non-league directories
        skip_dirs = ['openfootball', 'international_results', 'linkage', 'fifa_rankings',
                     'coaches', 'players', 'football_info', 'formations', 'season_info',
                     'league_rules', 'world_cup_2026', 'european_championship']
        if any(d in root for d in skip_dirs):
            continue

        for f in files:
            if not f.endswith('.csv'):
                continue

            # Skip non-match data files
            if any(x in f for x in ['all.csv', 'template', 'list', 'info', 'stats', 'matches', 'history', 'rules', 'results']):
                continue

            filepath = os.path.join(root, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    header = file.readline().strip()
                    cols = header.split(',')

                    if 'Date' in cols and 'Time' not in cols:
                        files_to_fix.append(filepath)
            except:
                # Try other encodings for detection
                for enc in ['utf-8-sig', 'latin-1', 'cp1252']:
                    try:
                        with open(filepath, 'r', encoding=enc) as file:
                            header = file.readline().strip()
                            cols = header.split(',')
                            if 'Date' in cols and 'Time' not in cols:
                                files_to_fix.append(filepath)
                            break
                    except:
                        continue

    print("Adding Time column to {} files...".format(len(files_to_fix)))
    print("=" * 60)

    fixed_count = 0
    for filepath in files_to_fix:
        if add_time_column(filepath):
            fixed_count += 1

    print("=" * 60)
    print("Done! Fixed {} files".format(fixed_count))

if __name__ == "__main__":
    main()