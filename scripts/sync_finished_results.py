"""
同步已结束比赛的结果

从 oddsfe 获取已结束比赛的完整结果（比分、SPF、BQC、RQSPF、BF）
"""
import sqlite3
import sys
sys.path.insert(0, '/opt/football_tools/fetchers/odds_feed_api')
from oddsfe_auth import get_event_auth
from datetime import datetime, timedelta
import requests
import json

DB_PATH = '/opt/football_tools/data/football_v2.db'

def parse_score_details(score_details: str):
    """Parse oddsfe period score_details into HT and 90-minute FT."""
    if not score_details:
        return None, None, None, None

    s = score_details.strip()
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1]

    parts = [p.strip() for p in s.split(',') if ':' in p]
    if len(parts) < 1:
        return None, None, None, None

    def parse_score(part):
        nums = part.strip().split(':')
        if len(nums) == 2:
            try:
                return int(nums[0]), int(nums[1])
            except:
                return None, None
        return None, None

    # Current oddsfe format is period based:
    # (first half, second half[, extra time, penalties]).
    ht_home, ht_away = None, None
    ft_home, ft_away = None, None

    if len(parts) >= 1:
        ht_home, ht_away = parse_score(parts[0])
        ft_home, ft_away = ht_home, ht_away

    if len(parts) >= 2:
        sh_home, sh_away = parse_score(parts[1])
        if ht_home is not None and sh_home is not None:
            ft_home, ft_away = ht_home + sh_home, ht_away + sh_away

    return ht_home, ht_away, ft_home, ft_away


def derive_play_types(ft_home, ft_away, ht_home, ht_away, handicap):
    """从比分推导全部玩法结果"""
    results = {}

    # SPF (胜平负)
    if ft_home is not None and ft_away is not None:
        if ft_home > ft_away:
            results['spf_result'] = '3'
        elif ft_home == ft_away:
            results['spf_result'] = '1'
        else:
            results['spf_result'] = '0'

    # BQC: stored as sporttery code, half-time digit + full-time digit.
    if ht_home is not None and ht_away is not None and ft_home is not None and ft_away is not None:
        ht_result = '3' if ht_home > ht_away else ('1' if ht_home == ht_away else '0')
        ft_result = '3' if ft_home > ft_away else ('1' if ft_home == ft_away else '0')
        results['bqc_result'] = ht_result + ft_result

    # BF (比分)
    if ft_home is not None and ft_away is not None:
        results['bf_result'] = f'{ft_home}:{ft_away}'

    # RQSPF (让球胜平负)
    if ft_home is not None and ft_away is not None and handicap is not None:
        try:
            hc = float(handicap)
            home_adj = ft_home - hc
            if home_adj > ft_away:
                results['rqspf_result'] = '3'
            elif home_adj == ft_away:
                results['rqspf_result'] = '1'
            else:
                results['rqspf_result'] = '0'
        except:
            pass

    return results


def effective_handicap(raw_handicap, rqspf_odds_data):
    """Use sporttery rqspf goal_line when present."""
    try:
        odds = json.loads(rqspf_odds_data) if rqspf_odds_data else {}
        goal_line = str((odds or {}).get('goal_line', '')).strip()
        if goal_line:
            return -float(goal_line)
    except Exception:
        pass
    try:
        return float(raw_handicap or 0)
    except Exception:
        return 0


def sync_finished_results():
    """同步已结束比赛的结果"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 获取所有已结束但没有结果的比赛
    # 判断标准：match_datetime < now - 3 hours (给比赛留完赛时间)
    now = datetime.now()
    cutoff = now - timedelta(hours=3)
    cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M')

    c.execute("""
        SELECT lm.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
               lm.match_date, lm.match_time, lm.oddsfe_event_id, lm.handicap_line,
               lo.odds_data AS rqspf_odds_data,
               lr.home_goals_ft, lr.away_goals_ft
        FROM lottery_matches lm
        LEFT JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
        LEFT JOIN lottery_odds lo ON lm.lottery_match_id = lo.lottery_match_id AND lo.play_type = 'rqspf'
        WHERE (lm.match_date || ' ' || substr(lm.match_time, 1, 5)) < ?
          AND lr.lottery_match_id IS NULL
          AND lm.oddsfe_event_id IS NOT NULL
        ORDER BY lm.match_date, lm.match_time
    """, (cutoff_str,))

    matches = c.fetchall()
    print(f'Found {len(matches)} finished matches without results')

    auth = get_event_auth()
    s = requests.Session()
    s.trust_env = False

    synced = 0
    errors = 0

    for m in matches:
        lm_id = m['lottery_match_id']
        eid = m['oddsfe_event_id']
        handicap = effective_handicap(m['handicap_line'], m['rqspf_odds_data'])

        if not eid:
            continue

        # 从 oddsfe 获取结果
        try:
            url = f'https://oddsfe.com/bind/event/{eid}'
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Origin': 'https://oddsfe.com',
                'Referer': f'https://oddsfe.com/events/{eid}',
            }
            headers.update(auth)

            r = s.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f'  API error for {eid}: {r.status_code}')
                errors += 1
                continue

            data = r.json()
            score_details = data.get('score_details', '')

            if not score_details:
                print(f'  No score_details for {eid}')
                errors += 1
                continue

            # 解析比分
            ht_home, ht_away, ft_home, ft_away = parse_score_details(score_details)
            api_ft_home = data.get('score_home')
            api_ft_away = data.get('score_away')
            if api_ft_home is not None and api_ft_away is not None:
                ft_home, ft_away = int(api_ft_home), int(api_ft_away)

            if ft_home is None or ft_away is None:
                print(f'  Invalid score_details: {score_details}')
                errors += 1
                continue

            # 推导全部玩法
            derived = derive_play_types(ft_home, ft_away, ht_home, ht_away, handicap)

            # 插入结果
            c.execute("""
                INSERT INTO lottery_results
                (lottery_match_id, home_goals_ft, away_goals_ft,
                 home_goals_ht, away_goals_ht,
                 spf_result, bf_result, bqc_result, rqspf_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lm_id, ft_home, ft_away, ht_home, ht_away,
                derived.get('spf_result'), derived.get('bf_result'),
                derived.get('bqc_result'), derived.get('rqspf_result')
            ))

            synced += 1
            print(f'  ✓ {lm_id}: {m["home_team_cn"]} vs {m["away_team_cn"]} = {ft_home}-{ft_away}')

        except Exception as e:
            print(f'  Error: {e}')
            errors += 1

    conn.commit()
    conn.close()

    print(f'\nSynced: {synced}, Errors: {errors}')
    return synced, errors


if __name__ == '__main__':
    sync_finished_results()
