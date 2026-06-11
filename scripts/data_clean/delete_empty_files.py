import os
import pandas as pd

def find_empty_files(base_path):
    """Find all empty CSV files (only header, no data)"""
    empty_files = []

    for root, dirs, files in os.walk(base_path):
        for f in files:
            if f.endswith('.csv'):
                filepath = os.path.join(root, f)
                try:
                    df = pd.read_csv(filepath)
                    if len(df) == 0:
                        empty_files.append(filepath)
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")

    return empty_files

# Find empty files
base_path = 'd:/football_tools/new_data/matches/clubs'
empty_files = find_empty_files(base_path)

print(f"Found {len(empty_files)} empty files")

# Delete empty files
deleted = 0
for filepath in empty_files:
    try:
        os.remove(filepath)
        deleted += 1
        print(f"Deleted: {filepath}")
    except Exception as e:
        print(f"Error deleting {filepath}: {e}")

print(f"\nDeleted {deleted} empty CSV files")
print("Note: Empty directories are preserved for future data filling")
