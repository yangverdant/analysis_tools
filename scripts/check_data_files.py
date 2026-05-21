import os
import pandas as pd

def check_directory(base_path):
    """Check all CSV files in directory tree"""
    results = []

    for root, dirs, files in os.walk(base_path):
        for f in files:
            if f.endswith('.csv'):
                filepath = os.path.join(root, f)
                try:
                    df = pd.read_csv(filepath)
                    line_count = len(df) + 1  # +1 for header

                    # Check if empty (only header)
                    if len(df) == 0:
                        results.append({
                            'path': filepath,
                            'lines': line_count,
                            'status': 'EMPTY',
                            'action': 'DELETE'
                        })
                    else:
                        results.append({
                            'path': filepath,
                            'lines': line_count,
                            'status': 'OK',
                            'action': 'KEEP'
                        })
                except Exception as e:
                    results.append({
                        'path': filepath,
                        'lines': 0,
                        'status': f'ERROR: {str(e)[:50]}',
                        'action': 'CHECK'
                    })

    return results

def check_year_validity(filepath, competition_type):
    """Check if year is valid for competition type"""
    filename = os.path.basename(filepath)

    # Extract year from filename
    import re
    match = re.search(r'(\d{4})', filename)
    if not match:
        return None, "No year found"

    year = int(match.group(1))

    # Competition year rules
    rules = {
        'world_cup': list(range(1930, 2030, 4)),  # Every 4 years from 1930
        'euro': list(range(1960, 2030, 4)),  # Every 4 years from 1960
        'copa_america': [2001, 2004, 2007, 2011, 2015, 2016, 2019, 2021, 2024],  # Irregular
        'africa_cup': [2002, 2004, 2006, 2008, 2010, 2012, 2013, 2015, 2017, 2019, 2021, 2023],
        'asian_cup': [2000, 2004, 2007, 2011, 2015, 2019, 2023],
    }

    for comp, valid_years in rules.items():
        if comp in filepath.lower():
            if year not in valid_years:
                return year, f"Invalid year for {comp}"
            return year, "OK"

    return year, "OK (no rule)"

# Check international matches
print("=" * 80)
print("CHECKING INTERNATIONAL MATCHES")
print("=" * 80)

base_path = 'd:/football_tools/new_data/matches/international'
results = check_directory(base_path)

# Group by status
empty_files = [r for r in results if r['status'] == 'EMPTY']
ok_files = [r for r in results if r['status'] == 'OK']
error_files = [r for r in results if 'ERROR' in r['status']]

print(f"\nTotal files: {len(results)}")
print(f"OK files: {len(ok_files)}")
print(f"Empty files: {len(empty_files)}")
print(f"Error files: {len(error_files)}")

if empty_files:
    print("\n--- EMPTY FILES TO DELETE ---")
    for r in empty_files:
        print(f"  {r['path']}")

if error_files:
    print("\n--- ERROR FILES ---")
    for r in error_files:
        print(f"  {r['path']}: {r['status']}")

# Check year validity for each competition
print("\n" + "=" * 80)
print("CHECKING YEAR VALIDITY")
print("=" * 80)

for r in results:
    if r['status'] == 'OK':
        year, status = check_year_validity(r['path'], '')
        if status != "OK" and status != "OK (no rule)":
            print(f"  {r['path']}: {status}")

# Check club matches
print("\n" + "=" * 80)
print("CHECKING CLUB MATCHES")
print("=" * 80)

base_path = 'd:/football_tools/new_data/matches/clubs'
results = check_directory(base_path)

empty_files = [r for r in results if r['status'] == 'EMPTY']
ok_files = [r for r in results if r['status'] == 'OK']
error_files = [r for r in results if 'ERROR' in r['status']]

print(f"\nTotal files: {len(results)}")
print(f"OK files: {len(ok_files)}")
print(f"Empty files: {len(empty_files)}")
print(f"Error files: {len(error_files)}")

if empty_files:
    print("\n--- EMPTY FILES TO DELETE ---")
    for r in empty_files:
        print(f"  {r['path']}")

if error_files:
    print("\n--- ERROR FILES ---")
    for r in error_files:
        print(f"  {r['path']}: {r['status']}")

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
