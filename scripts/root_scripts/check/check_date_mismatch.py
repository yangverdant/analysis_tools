import sqlite3, json

DB = 'd:/football_tools/data/unified_football.db'
conn = sqlite3.connect(DB)

# Check date mismatches between odds and matches
print("=== Date mismatch check ===")

# Odds data dates
odds_dates = conn.execute("""
    SELECT json_extract(data_json, '$.date'), COUNT(*)
    FROM match_data WHERE source='odds_feed' AND data_type='odds'
    GROUP BY json_extract(data_json, '$.date')
    ORDER BY json_extract(data_json, '$.date') DESC
    LIMIT 20
""").fetchall()
print("Odds dates (top 20):")
for r in odds_dates:
    print("  %s: %d" % (r[0], r[1]))

# Matches dates
match_dates = conn.execute("""
    SELECT date, COUNT(*)
    FROM matches WHERE status='finished'
    GROUP BY date
    ORDER BY date DESC
    LIMIT 20
""").fetchall()
print("\nMatches dates (top 20):")
for r in match_dates:
    print("  %s: %d" % (r[0], r[1]))

# Check: odds match_keys that don't match any match
orphan = conn.execute("""
    SELECT md.match_key, json_extract(md.data_json, '$.date') as odds_date,
           json_extract(md.data_json, '$.home_team') as odds_home,
           json_extract(md.data_json, '$.league')
    FROM match_data md
    WHERE md.source='odds_feed' AND md.data_type='odds'
    AND md.match_key NOT IN (SELECT match_key FROM matches)
    LIMIT 20
""").fetchall()
print("\nOrphan odds (no match_key match): %d total" % conn.execute("""
    SELECT COUNT(*) FROM match_data md
    WHERE md.source='odds_feed' AND md.data_type='odds'
    AND md.match_key NOT IN (SELECT match_key FROM matches)
""").fetchone()[0])
for r in orphan[:10]:
    print("  key=%s date=%s home=%s league=%s" % (r[0], r[1], r[2], r[3]))

# Check EPL: odds with match_key that does match
matched = conn.execute("""
    SELECT md.match_key, m.date as match_date,
           json_extract(md.data_json, '$.date') as odds_date,
           json_extract(md.data_json, '$.home_team')
    FROM match_data md
    JOIN matches m ON md.match_key = m.match_key
    WHERE md.source='odds_feed' AND md.data_type='odds'
    AND m.league='Premier League'
    LIMIT 10
""").fetchall()
print("\nEPL matched odds (date comparison):")
for r in matched:
    print("  key=%s match_date=%s odds_date=%s home=%s" % (r[0], r[1], r[2], r[3]))

# Count: how many odds have different date from match date
diff_date = conn.execute("""
    SELECT COUNT(*) FROM match_data md
    JOIN matches m ON md.match_key = m.match_key
    WHERE md.source='odds_feed' AND md.data_type='odds'
    AND m.date != json_extract(md.data_json, '$.date')
""").fetchone()[0]
print("\nOdds with different date from match: %d" % diff_date)

conn.close()