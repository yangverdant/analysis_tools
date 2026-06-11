import sqlite3, json

DB = 'd:/football_tools/data/unified_football.db'
conn = sqlite3.connect(DB)

total = conn.execute("SELECT COUNT(*) FROM match_data WHERE source='odds_feed' AND data_type='odds'").fetchone()[0]
print('Total odds records: %d' % total)

by_lg = conn.execute("""
    SELECT json_extract(data_json, '$.league'), COUNT(*)
    FROM match_data WHERE source='odds_feed' AND data_type='odds'
    GROUP BY json_extract(data_json, '$.league')
""").fetchall()
print('By league:')
for r in by_lg:
    print('  %s: %d' % (r[0], r[1]))

total_matches = conn.execute('SELECT COUNT(*) FROM matches').fetchone()[0]
finished = conn.execute("SELECT COUNT(*) FROM matches WHERE status='finished'").fetchone()[0]
print('Total matches: %d, finished: %d' % (total_matches, finished))

with_odds = conn.execute("""
    SELECT COUNT(DISTINCT m.match_key)
    FROM matches m
    JOIN match_data md ON m.match_key = md.match_key
    WHERE md.source='odds_feed' AND md.data_type='odds' AND m.status='finished'
""").fetchone()[0]
print('Finished matches with odds: %d / %d = %.1f%%' % (with_odds, finished, 100.0*with_odds/finished))

sample = conn.execute("""
    SELECT match_key, data_json FROM match_data WHERE source='odds_feed' AND data_type='odds' LIMIT 1
""").fetchone()
if sample:
    odds = json.loads(sample[1])
    print('Sample odds keys: %s' % str(list(odds.keys())))
    print('Sample: hw=%s d=%s aw=%s' % (odds.get('home_win'), odds.get('draw'), odds.get('away_win')))

# Check what leagues have matches but no odds
no_odds = conn.execute("""
    SELECT league, COUNT(*) as cnt
    FROM matches
    WHERE status='finished'
    AND match_key NOT IN (
        SELECT DISTINCT match_key FROM match_data WHERE source='odds_feed' AND data_type='odds'
    )
    GROUP BY league
    ORDER BY cnt DESC
""").fetchall()
print('\nMatches WITHOUT odds by league:')
for r in no_odds:
    print('  %s: %d' % (r[0], r[1]))

conn.close()
