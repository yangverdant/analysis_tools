"""
Fix World Cup knockout match results where ET/penalty scores were stored
instead of 90-minute regular time scores.

Settlement rule: SPF/BQC/OU are based on 90-minute regular time ONLY.

Run: python backend/scripts/fix_wc_ko_90min.py
"""

import sqlite3
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'football_v2.db')


def fix_wc_ko_results():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"Database: {DB_PATH}")

    # Check which WC KO matches have wrong data (AET/AP but no 90min fields)
    cursor.execute("""
        SELECT lr.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
               lr.home_goals_ft, lr.away_goals_ft,
               lr.home_goals_ht, lr.away_goals_ht,
               lr.home_goals_90min, lr.away_goals_90min, lr.match_end_type,
               lr.spf_result, lr.bqc_result, lr.bf_result
        FROM lottery_results lr
        JOIN lottery_matches lm ON lr.lottery_match_id = lm.lottery_match_id
        WHERE lr.match_end_type IS NULL
          AND lr.home_goals_ft IS NOT NULL
          AND lr.home_goals_ht IS NOT NULL
        ORDER BY lr.lottery_match_id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]

    print(f"\nFound {len(rows)} results without match_end_type")

    # Known WC KO matches with ET/penalty (from oddsfe data)
    # These have aggregate scores stored but need 90min correction
    known_fixes = {
        # Germany 5-6 Paraguay (AP): 90min=1-1, HT=0-0
        '202606291075': {'home_90': 1, 'away_90': 1, 'end_type': 'AP',
                         'spf': '1', 'bqc': '11', 'bf': '1:1'},
        # Netherlands 3-4 Morocco (AP): 90min=1-1, HT=0-0
        '202606291076': {'home_90': 1, 'away_90': 1, 'end_type': 'AP',
                         'spf': '1', 'bqc': '11', 'bf': '1:1'},
        # Brazil 2-1 Japan (FT): no change needed, just mark end_type
        '202606291074': {'home_90': 2, 'away_90': 1, 'end_type': 'FT'},
    }

    # Also check for any other AET/AP matches that might have been synced
    # by the updated sync_service and need 90min fields populated
    cursor.execute("""
        SELECT lr.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
               lr.home_goals_ft, lr.away_goals_ft,
               lr.home_goals_ht, lr.away_goals_ht,
               lr.home_goals_90min, lr.away_goals_90min, lr.match_end_type
        FROM lottery_results lr
        JOIN lottery_matches lm ON lr.lottery_match_id = lm.lottery_match_id
        WHERE lr.match_end_type IN ('AET', 'AP')
          AND (lr.home_goals_90min IS NULL OR lr.away_goals_90min IS NULL)
    """)
    aet_rows = [dict(r) for r in cursor.fetchall()]
    print(f"AET/AP matches missing 90min data: {len(aet_rows)}")
    for r in aet_rows:
        print(f"  {r['lottery_match_id']}: {r['home_team_cn']} {r['home_goals_ft']}-{r['away_goals_ft']} {r['away_team_cn']} ({r['match_end_type']})")

    # Apply known fixes
    fixed = 0
    for lm_id, fix in known_fixes.items():
        cursor.execute("SELECT lottery_match_id FROM lottery_results WHERE lottery_match_id = ?", (lm_id,))
        if not cursor.fetchone():
            print(f"  Skip {lm_id}: not in DB yet")
            continue

        updates = []
        params = []

        updates.append('home_goals_90min = ?')
        params.append(fix['home_90'])
        updates.append('away_goals_90min = ?')
        params.append(fix['away_90'])
        updates.append('match_end_type = ?')
        params.append(fix['end_type'])

        if 'spf' in fix:
            updates.append('spf_result = ?')
            params.append(fix['spf'])
        if 'bqc' in fix:
            updates.append('bqc_result = ?')
            params.append(fix['bqc'])
        if 'bf' in fix:
            updates.append('bf_result = ?')
            params.append(fix['bf'])

        sql = f"UPDATE lottery_results SET {', '.join(updates)} WHERE lottery_match_id = ?"
        params.append(lm_id)
        cursor.execute(sql, params)
        fixed += 1
        print(f"  Fixed {lm_id}: 90min={fix['home_90']}-{fix['away_90']} ({fix['end_type']})")

    conn.commit()

    # Also set match_end_type='FT' for all other results that don't have it
    cursor.execute("""
        UPDATE lottery_results
        SET match_end_type = 'FT',
            home_goals_90min = COALESCE(home_goals_90min, home_goals_ft),
            away_goals_90min = COALESCE(away_goals_90min, away_goals_ft)
        WHERE match_end_type IS NULL
          AND home_goals_ft IS NOT NULL
    """)
    ft_fixed = cursor.rowcount
    conn.commit()

    print(f"\n=== Fix Summary ===")
    print(f"Known WC KO fixes: {fixed}")
    print(f"FT defaults set: {ft_fixed}")

    # Verify
    cursor.execute("""
        SELECT lr.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
               lr.home_goals_ft, lr.away_goals_ft,
               lr.home_goals_90min, lr.away_goals_90min, lr.match_end_type,
               lr.spf_result, lr.bqc_result
        FROM lottery_results lr
        JOIN lottery_matches lm ON lr.lottery_match_id = lm.lottery_match_id
        WHERE lr.match_end_type IN ('AET', 'AP')
        ORDER BY lr.lottery_match_id
    """)
    aet_results = cursor.fetchall()
    if aet_results:
        print(f"\nAET/AP results after fix:")
        for r in aet_results:
            print(f"  {r[0]}: {r[1]} {r[2]} | FT={r[3]}-{r[4]} | 90min={r[5]}-{r[6]} | {r[7]} | SPF={r[8]} BQC={r[9]}")

    conn.close()


if __name__ == '__main__':
    fix_wc_ko_results()
