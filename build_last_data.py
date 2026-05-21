"""
Build last_data tables from football-data_new + StatsBomb.
Tables: matches, match_detail, odds, statsbomb_shots, statsbomb_passes, statsbomb_player_match
All linked by match_id = {league}_{season}_{date}_{home}_vs_{away}
Only processes data from 2020 onwards.
"""

import csv, json, os, sys, re
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ND = r'd:\football_tools\new_data'
OUT = r'd:\football_tools\last_data'
SB_EVENTS = os.path.join(ND, 'matches', 'clubs', 'leagues', 'StatsBomb_events')
SB_LINEUPS = os.path.join(ND, 'matches', 'clubs', 'leagues', 'StatsBomb_lineups')
SB_MATCHES = os.path.join(ND, 'matches', 'clubs', 'leagues', 'StatsBomb_matches')
SB_COMPETITIONS = os.path.join(ND, 'matches', 'StatsBomb_competitions.json')

def normalize_team(name):
    """Normalize team name for match_id generation."""
    if not name:
        return 'unknown'
    n = name.strip().lower()
    # Common abbreviations -> full
    mappings = {
        'man united': 'manchester_united', 'man city': 'manchester_city',
        'man utd': 'manchester_united', 'man united': 'manchester_united',
        'nottm forest': 'nottingham_forest', 'nott forest': 'nottingham_forest',
        'sheff utd': 'sheffield_united', 'sheff wed': 'sheffield_wednesday',
        'tottenham': 'tottenham_hotspur', 'spurs': 'tottenham_hotspur',
        'wolves': 'wolverhampton', 'brighton': 'brighton_and_hove_albion',
        'w brom': 'west_bromwich', 'west brom': 'west_bromwich',
        'c palace': 'crystal_palace', 'crystal palace': 'crystal_palace',
        'stoke': 'stoke_city', 'huddersfield': 'huddersfield_town',
        'paris sg': 'paris_saint_germain', 'psg': 'paris_saint_germain',
        'ath madrid': 'atletico_madrid', 'atletico madrid': 'atletico_madrid',
        'ath bilbao': 'athletic_bilbao', 'athletic bilbao': 'athletic_bilbao',
        'r madrid': 'real_madrid', 'real madrid': 'real_madrid',
        'barca': 'barcelona', 'bayern': 'bayern_munich',
        'dortmund': 'borussia_dortmund', 'm gladbach': 'borussia_monchengladbach',
        'levante': 'levante_ud', 'celta': 'celta_vigo',
        'inter': 'inter_milan', 'ac milan': 'ac_milan',
        'lazio': 'lazio_roma', 'roma': 'as_roma',
        'fiorentina': 'acf_fiorentina',
    }
    for k, v in mappings.items():
        if n == k:
            return v
    # Replace spaces/special chars
    n = re.sub(r'[^a-z0-9]+', '_', n).strip('_')
    return n

def make_match_id(league, season, date, home, away, round_num=''):
    """Generate match_id: league_season_date_home_vs_away (or with round if teams unknown)"""
    league_n = re.sub(r'[^a-z0-9]+', '_', league.strip().lower()).strip('_')
    season_n = season.replace('/', '-').replace('\\', '-')
    home_n = normalize_team(home)
    away_n = normalize_team(away)
    if home_n == 'unknown' and away_n == 'unknown' and round_num:
        round_n = re.sub(r'[^a-z0-9]+', '_', round_num.strip().lower()).strip('_')
        return '%s_%s_%s_round_%s' % (league_n, season_n, date, round_n)
    return '%s_%s_%s_%s_vs_%s' % (league_n, season_n, date, home_n, away_n)

def safe_float(v):
    if v is None or v == '' or v == 'null' or v == 'None':
        return ''
    try:
        return float(v)
    except:
        return ''

def safe_int(v):
    if v is None or v == '' or v == 'null' or v == 'None':
        return ''
    try:
        return int(float(v))
    except:
        return ''

def get_season_year(season_str):
    """Extract start year from season string like '2020-2021' or '2020/2021' or '2020'"""
    s = season_str.replace('/', '-').replace('\\', '-')
    parts = s.split('-')
    try:
        return int(parts[0])
    except:
        return 0

# ============================================================
# Step 1: Read all football-data_new CSVs and extract rows
# ============================================================
print('Step 1: Reading football-data_new CSVs...')

all_rows = []  # Each row is a dict with standardized fields

# --- Club leagues ---
leagues_dir = os.path.join(ND, 'matches', 'clubs', 'leagues')
for league_name in sorted(os.listdir(leagues_dir)):
    league_path = os.path.join(leagues_dir, league_name)
    if not os.path.isdir(league_path):
        continue
    if league_name.startswith('StatsBomb'):
        continue
    # Skip international competitions that are also in international/ dir
    if league_name in ('world_cup',):
        continue

    for fname in sorted(os.listdir(league_path)):
        if not fname.endswith('.csv'):
            continue
        fpath = os.path.join(league_path, fname)

        with open(fpath, encoding='utf-8-sig') as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames
            for row in reader:
                # Determine season and filter >= 2020
                season = row.get('season', row.get('Season', ''))
                if not season:
                    # Try to extract from filename
                    m = re.search(r'(\d{4})-?(\d{2,4})', fname)
                    if m:
                        season = '%s-%s' % (m.group(1), m.group(2))

                year = get_season_year(season)
                if year < 2020:
                    continue

                # Determine date
                date = row.get('match_date', row.get('date', row.get('Date', '')))
                if not date:
                    continue

                # Determine teams
                home = row.get('home_team', row.get('HomeTeam', ''))
                away = row.get('away_team', row.get('AwayTeam', ''))

                # Determine scores
                home_goals = row.get('home_goals', row.get('FTHG', row.get('ft_home', '')))
                away_goals = row.get('away_goals', row.get('FTAG', row.get('ft_away', '')))
                home_goals_ht = row.get('home_goals_ht', row.get('HTHG', row.get('ht_home', '')))
                away_goals_ht = row.get('away_goals_ht', row.get('HTAG', row.get('ht_away', '')))

                # Determine round
                round_num = row.get('round_num', row.get('round', row.get('Round', '')))

                # Determine division
                division = row.get('division', row.get('Div', league_name))

                # Determine status
                status = row.get('status', row.get('Status', 'Finished'))

                # Determine match_time
                match_time = row.get('match_time', row.get('Time', row.get('time', '')))

                # match_id from football-data
                fd_match_id = row.get('match_id', '')

                match_id = make_match_id(league_name, season, date, home, away, round_num)

                row_data = {
                    'match_id': match_id,
                    'fd_match_id': fd_match_id,
                    'league': league_name,
                    'season': season,
                    'match_date': date,
                    'match_time': match_time,
                    'round': round_num,
                    'division': division,
                    'home_team': home,
                    'away_team': away,
                    'home_goals': safe_int(home_goals),
                    'away_goals': safe_int(away_goals),
                    'home_goals_ht': safe_int(home_goals_ht),
                    'away_goals_ht': safe_int(away_goals_ht),
                    'status': status,
                    'referee': row.get('referee', row.get('Referee', '')),
                    'attendance': row.get('attendance', row.get('Attendance', '')),
                    # match_stats fields
                    'home_shots': safe_int(row.get('home_shots', row.get('HS', ''))),
                    'away_shots': safe_int(row.get('away_shots', row.get('AS', ''))),
                    'home_shots_target': safe_int(row.get('home_shots_target', row.get('HST', ''))),
                    'away_shots_target': safe_int(row.get('away_shots_target', row.get('AST', ''))),
                    'home_corners': safe_int(row.get('home_corners', row.get('HC', ''))),
                    'away_corners': safe_int(row.get('away_corners', row.get('AC', ''))),
                    'home_fouls': safe_int(row.get('home_fouls', row.get('HF', ''))),
                    'away_fouls': safe_int(row.get('away_fouls', row.get('AF', ''))),
                    'home_yellow': safe_int(row.get('home_yellow', row.get('HY', ''))),
                    'away_yellow': safe_int(row.get('away_yellow', row.get('AY', ''))),
                    'home_red': safe_int(row.get('home_red', row.get('HR', ''))),
                    'away_red': safe_int(row.get('away_red', row.get('AR', ''))),
                    # odds fields
                    'b365_home': row.get('b365_home', row.get('B365H', '')),
                    'b365_draw': row.get('b365_draw', row.get('B365D', '')),
                    'b365_away': row.get('b365_away', row.get('B365A', '')),
                    'ps_home': row.get('ps_home', row.get('PSH', '')),
                    'ps_draw': row.get('ps_draw', row.get('PSD', '')),
                    'ps_away': row.get('ps_away', row.get('PSA', '')),
                    'max_home': row.get('max_home', row.get('MaxH', '')),
                    'max_draw': row.get('max_draw', row.get('MaxD', '')),
                    'max_away': row.get('max_away', row.get('MaxA', '')),
                    'avg_home': row.get('avg_home', row.get('AvgH', '')),
                    'avg_draw': row.get('avg_draw', row.get('AvgD', '')),
                    'avg_away': row.get('avg_away', row.get('AvgA', '')),
                    'b365_over_2_5': row.get('b365_over_2_5', row.get('B365>2.5', '')),
                    'b365_under_2_5': row.get('b365_under_2_5', row.get('B365<2.5', '')),
                    'ps_over_2_5': row.get('ps_over_2_5', ''),
                    'ps_under_2_5': row.get('ps_under_2_5', ''),
                    'max_over_2_5': row.get('max_over_2_5', ''),
                    'max_under_2_5': row.get('max_under_2_5', ''),
                    'avg_over_2_5': row.get('avg_over_2_5', ''),
                    'avg_under_2_5': row.get('avg_under_2_5', ''),
                    'asian_handicap': row.get('asian_handicap', row.get('AHh', '')),
                    'b365_ah_home': row.get('b365_ah_home', ''),
                    'b365_ah_away': row.get('b365_ah_away', ''),
                    'ps_ah_home': row.get('ps_ah_home', ''),
                    'ps_ah_away': row.get('ps_ah_away', ''),
                    'max_ah_home': row.get('max_ah_home', ''),
                    'max_ah_away': row.get('max_ah_away', ''),
                    'avg_ah_home': row.get('avg_ah_home', ''),
                    'avg_ah_away': row.get('avg_ah_away', ''),
                    # closing odds
                    'b365_c_home': row.get('b365_c_home', ''),
                    'b365_c_draw': row.get('b365_c_draw', ''),
                    'b365_c_away': row.get('b365_c_away', ''),
                    'ps_c_home': row.get('ps_c_home', ''),
                    'ps_c_draw': row.get('ps_c_draw', ''),
                    'ps_c_away': row.get('ps_c_away', ''),
                    'max_c_home': row.get('max_c_home', ''),
                    'max_c_draw': row.get('max_c_draw', ''),
                    'max_c_away': row.get('max_c_away', ''),
                    'avg_c_home': row.get('avg_c_home', ''),
                    'avg_c_draw': row.get('avg_c_draw', ''),
                    'avg_c_away': row.get('avg_c_away', ''),
                }
                all_rows.append(row_data)

# --- International tournaments ---
intl_dir = os.path.join(ND, 'matches', 'international')
for comp_name in sorted(os.listdir(intl_dir)):
    comp_path = os.path.join(intl_dir, comp_name)
    if not os.path.isdir(comp_path):
        continue

    for fname in sorted(os.listdir(comp_path)):
        if not fname.endswith('.csv'):
            continue
        fpath = os.path.join(comp_path, fname)

        with open(fpath, encoding='utf-8-sig') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                season = row.get('season', '')
                year = get_season_year(season)
                if year < 2020:
                    continue

                date = row.get('match_date', '')
                if not date:
                    continue

                home = row.get('home_team', '')
                away = row.get('away_team', '')

                home_goals = row.get('home_goals', '')
                away_goals = row.get('away_goals', '')
                home_goals_ht = row.get('home_goals_ht', '')
                away_goals_ht = row.get('away_goals_ht', '')

                round_num = row.get('round', '')

                match_id = make_match_id(comp_name, season, date, home, away, round_num)

                row_data = {
                    'match_id': match_id,
                    'fd_match_id': '',
                    'league': comp_name,
                    'season': season,
                    'match_date': date,
                    'match_time': row.get('match_time', ''),
                    'round': row.get('round', ''),
                    'division': comp_name,
                    'home_team': home,
                    'away_team': away,
                    'home_goals': safe_int(home_goals),
                    'away_goals': safe_int(away_goals),
                    'home_goals_ht': safe_int(home_goals_ht),
                    'away_goals_ht': safe_int(away_goals_ht),
                    'status': row.get('status', 'finished'),
                    'referee': row.get('referee', ''),
                    'attendance': row.get('attendance', ''),
                    # match_stats
                    'home_shots': safe_int(row.get('home_shots', '')),
                    'away_shots': safe_int(row.get('away_shots', '')),
                    'home_shots_target': safe_int(row.get('home_shots_target', '')),
                    'away_shots_target': safe_int(row.get('away_shots_target', '')),
                    'home_corners': safe_int(row.get('home_corners', '')),
                    'away_corners': safe_int(row.get('away_corners', '')),
                    'home_fouls': safe_int(row.get('home_fouls', '')),
                    'away_fouls': safe_int(row.get('away_fouls', '')),
                    'home_yellow': safe_int(row.get('home_yellow', '')),
                    'away_yellow': safe_int(row.get('away_yellow', '')),
                    'home_red': safe_int(row.get('home_red', '')),
                    'away_red': safe_int(row.get('away_red', '')),
                    # odds - international has none
                    'b365_home': '', 'b365_draw': '', 'b365_away': '',
                    'ps_home': '', 'ps_draw': '', 'ps_away': '',
                    'max_home': '', 'max_draw': '', 'max_away': '',
                    'avg_home': '', 'avg_draw': '', 'avg_away': '',
                    'b365_over_2_5': '', 'b365_under_2_5': '',
                    'ps_over_2_5': '', 'ps_under_2_5': '',
                    'max_over_2_5': '', 'max_under_2_5': '',
                    'avg_over_2_5': '', 'avg_under_2_5': '',
                    'asian_handicap': '',
                    'b365_ah_home': '', 'b365_ah_away': '',
                    'ps_ah_home': '', 'ps_ah_away': '',
                    'max_ah_home': '', 'max_ah_away': '',
                    'avg_ah_home': '', 'avg_ah_away': '',
                    'b365_c_home': '', 'b365_c_draw': '', 'b365_c_away': '',
                    'ps_c_home': '', 'ps_c_draw': '', 'ps_c_away': '',
                    'max_c_home': '', 'max_c_draw': '', 'max_c_away': '',
                    'avg_c_home': '', 'avg_c_draw': '', 'avg_c_away': '',
                }
                all_rows.append(row_data)

print('  Total football-data_new rows (>= 2020): %d' % len(all_rows))

# ============================================================
# Step 2: Read StatsBomb matches and build match_id mapping
# ============================================================
print('Step 2: Reading StatsBomb matches...')

# StatsBomb competition name -> our league name
SB_LEAGUE_MAP = {
    'La Liga': 'la_liga',
    'Ligue 1': 'ligue_1',
    '1. Bundesliga': 'bundesliga',
    'Premier League': 'premier_league',
    'Serie A': 'serie_a',
    'Champions League': 'champions_league',
    'FIFA World Cup': 'world_cup',
    'UEFA Euro': 'euro',
    'Copa America': 'copa_america',
    'African Cup of Nations': 'africa_cup',
    'Indian Super league': 'indian_super_league',
    'Major League Soccer': 'mls',
    'FA Women\'s Super League': 'wsl',
}

# StatsBomb season name -> our season format
def convert_sb_season(season_name):
    return season_name.replace('/', '-')

sb_match_data = {}  # match_id (sb) -> {match_id, league, season, date, home, away, ...}

for comp_dir in os.listdir(SB_MATCHES):
    comp_path = os.path.join(SB_MATCHES, comp_dir)
    if not os.path.isdir(comp_path):
        continue
    for fname in os.listdir(comp_path):
        fpath = os.path.join(comp_path, fname)
        with open(fpath, encoding='utf-8') as fh:
            matches = json.load(fh)
        for m in matches:
            sb_mid = m['match_id']
            comp_name = m['competition']['competition_name']
            season_name = m['season']['season_name']
            league = SB_LEAGUE_MAP.get(comp_name, comp_name.lower().replace(' ', '_'))
            season = convert_sb_season(season_name)
            date = m['match_date']
            home = m['home_team']['home_team_name']
            away = m['away_team']['away_team_name']

            match_id = make_match_id(league, season, date, home, away, m.get('match_week', ''))

            sb_match_data[sb_mid] = {
                'match_id': match_id,
                'sb_match_id': sb_mid,
                'league': league,
                'season': season,
                'match_date': date,
                'home_team': home,
                'away_team': away,
                'home_goals': m.get('home_score', ''),
                'away_goals': m.get('away_score', ''),
                'home_team_id': m['home_team']['home_team_id'],
                'away_team_id': m['away_team']['away_team_id'],
                'match_week': m.get('match_week', ''),
                'stadium': m.get('stadium', {}).get('name', ''),
                'referee': m.get('referee', {}).get('name', ''),
                'home_manager': ', '.join(mgr.get('nickname', mgr.get('name', '')) for mgr in m.get('home_managers', [])),
                'away_manager': ', '.join(mgr.get('nickname', mgr.get('name', '')) for mgr in m.get('away_managers', [])),
                'competition_stage': m.get('competition_stage', {}).get('name', ''),
            }

print('  StatsBomb matches: %d' % len(sb_match_data))

# ============================================================
# Step 3: Aggregate StatsBomb events per match
# ============================================================
print('Step 3: Aggregating StatsBomb events...')

sb_aggregates = {}  # sb_match_id -> {home_xg, away_xg, ...}

for i, fname in enumerate(sorted(os.listdir(SB_EVENTS))):
    if not fname.endswith('.json'):
        continue
    sb_mid = int(fname.replace('.json', ''))
    fpath = os.path.join(SB_EVENTS, fname)

    try:
        with open(fpath, encoding='utf-8') as fh:
            events = json.load(fh)
    except:
        continue

    # Get team names from first event
    teams = {}
    for e in events:
        tname = e['team']['name']
        tid = e['team']['id']
        if tid not in teams:
            teams[tid] = tname

    team_ids = list(teams.keys())
    home_tid = team_ids[0] if len(team_ids) >= 1 else 0
    away_tid = team_ids[1] if len(team_ids) >= 2 else 0

    # Aggregate per team
    agg = {home_tid: defaultdict(float), away_tid: defaultdict(float)}

    for e in events:
        tid = e['team']['id']
        if tid not in agg:
            continue
        etype = e['type']['name']
        agg[tid][etype] += 1

        if etype == 'Shot':
            shot = e.get('shot', {})
            xg = shot.get('statsbomb_xg', 0) or 0
            agg[tid]['xg_total'] += xg
            outcome = shot.get('outcome', {}).get('name', '')
            if outcome == 'Goal':
                agg[tid]['shot_goal'] += 1
            elif outcome == 'Saved':
                agg[tid]['shot_saved'] += 1
            elif outcome == 'Off T':
                agg[tid]['shot_off_target'] += 1
            elif outcome == 'Blocked':
                agg[tid]['shot_blocked'] += 1
            elif outcome == 'Wayward':
                agg[tid]['shot_wayward'] += 1
            elif outcome == 'Post':
                agg[tid]['shot_post'] += 1

        if etype == 'Pass':
            p = e.get('pass', {})
            poutcome = p.get('outcome', {})
            if poutcome and poutcome.get('name'):
                agg[tid]['pass_incomplete'] += 1
            else:
                agg[tid]['pass_complete'] += 1
            if p.get('cross'):
                agg[tid]['cross'] += 1
            if p.get('goal_assist'):
                agg[tid]['assist'] += 1
            if p.get('shot_assist'):
                agg[tid]['key_pass'] += 1

        if etype == 'Dribble':
            doutcome = e.get('dribble', {}).get('outcome', {}).get('name', '')
            if doutcome == 'Complete':
                agg[tid]['dribble_success'] += 1
            else:
                agg[tid]['dribble_failed'] += 1

    sb_aggregates[sb_mid] = {
        'home_xg': round(agg[home_tid].get('xg_total', 0), 4),
        'away_xg': round(agg[away_tid].get('xg_total', 0), 4),
        'home_shots_total': int(agg[home_tid].get('Shot', 0)),
        'away_shots_total': int(agg[away_tid].get('Shot', 0)),
        'home_shots_on_target': int(agg[home_tid].get('shot_goal', 0) + agg[home_tid].get('shot_saved', 0) + agg[home_tid].get('shot_post', 0)),
        'away_shots_on_target': int(agg[away_tid].get('shot_goal', 0) + agg[away_tid].get('shot_saved', 0) + agg[away_tid].get('shot_post', 0)),
        'home_passes_total': int(agg[home_tid].get('Pass', 0)),
        'away_passes_total': int(agg[away_tid].get('Pass', 0)),
        'home_pass_complete': int(agg[home_tid].get('pass_complete', 0)),
        'away_pass_complete': int(agg[away_tid].get('pass_complete', 0)),
        'home_pass_completion_rate': round(agg[home_tid].get('pass_complete', 0) / max(agg[home_tid].get('Pass', 1), 1), 4),
        'away_pass_completion_rate': round(agg[away_tid].get('pass_complete', 0) / max(agg[away_tid].get('Pass', 1), 1), 4),
        'home_pressures': int(agg[home_tid].get('Pressure', 0)),
        'away_pressures': int(agg[away_tid].get('Pressure', 0)),
        'home_carry_count': int(agg[home_tid].get('Carry', 0)),
        'away_carry_count': int(agg[away_tid].get('Carry', 0)),
        'home_dribbles_success': int(agg[home_tid].get('dribble_success', 0)),
        'away_dribbles_success': int(agg[away_tid].get('dribble_success', 0)),
        'home_dribbles_attempted': int(agg[home_tid].get('Dribble', 0)),
        'away_dribbles_attempted': int(agg[away_tid].get('Dribble', 0)),
        'home_interceptions': int(agg[home_tid].get('Interception', 0)),
        'away_interceptions': int(agg[away_tid].get('Interception', 0)),
        'home_clearances': int(agg[home_tid].get('Clearance', 0)),
        'away_clearances': int(agg[away_tid].get('Clearance', 0)),
        'home_blocks': int(agg[home_tid].get('Block', 0)),
        'away_blocks': int(agg[away_tid].get('Block', 0)),
        'home_ball_recovery': int(agg[home_tid].get('Ball Recovery', 0)),
        'away_ball_recovery': int(agg[away_tid].get('Ball Recovery', 0)),
        'home_fouls_committed': int(agg[home_tid].get('Foul Committed', 0)),
        'away_fouls_committed': int(agg[away_tid].get('Foul Committed', 0)),
        'home_dispossessed': int(agg[home_tid].get('Dispossessed', 0)),
        'away_dispossessed': int(agg[away_tid].get('Dispossessed', 0)),
        'home_miscontrol': int(agg[home_tid].get('Miscontrol', 0)),
        'away_miscontrol': int(agg[away_tid].get('Miscontrol', 0)),
        'home_keeper_actions': int(agg[home_tid].get('Goal Keeper', 0)),
        'away_keeper_actions': int(agg[away_tid].get('Goal Keeper', 0)),
        'home_crosses': int(agg[home_tid].get('cross', 0)),
        'away_crosses': int(agg[away_tid].get('cross', 0)),
        'home_assists': int(agg[home_tid].get('assist', 0)),
        'away_assists': int(agg[away_tid].get('assist', 0)),
        'home_key_passes': int(agg[home_tid].get('key_pass', 0)),
        'away_key_passes': int(agg[away_tid].get('key_pass', 0)),
    }

    if (i + 1) % 100 == 0:
        print('  Processed %d event files...' % (i + 1))

print('  StatsBomb aggregates: %d matches' % len(sb_aggregates))

# ============================================================
# Step 4: Add StatsBomb-only matches to all_rows
# ============================================================
print('Step 4: Adding StatsBomb-only matches...')

# Build set of existing match_ids from football-data
existing_match_ids = set()
for r in all_rows:
    existing_match_ids.add(r['match_id'])

# Also try fuzzy match by date + normalized teams
date_team_index = defaultdict(set)
for r in all_rows:
    key = '%s_%s_%s' % (r['match_date'], normalize_team(r['home_team']), normalize_team(r['away_team']))
    date_team_index[key].add(r['match_id'])

sb_only_count = 0
sb_merged_count = 0

for sb_mid, sb_info in sb_match_data.items():
    # Try to find matching football-data row
    key = '%s_%s_%s' % (sb_info['match_date'], normalize_team(sb_info['home_team']), normalize_team(sb_info['away_team']))
    matched_fd_ids = date_team_index.get(key, set())

    if matched_fd_ids:
        # Found a match - will merge later
        sb_merged_count += 1
        continue
    else:
        # StatsBomb-only match - add as new row
        sb_only_count += 1
        match_id = sb_info['match_id']
        agg = sb_aggregates.get(sb_mid, {})

        row_data = {
            'match_id': match_id,
            'fd_match_id': '',
            'league': sb_info['league'],
            'season': sb_info['season'],
            'match_date': sb_info['match_date'],
            'match_time': '',
            'round': sb_info.get('match_week', ''),
            'division': sb_info['league'],
            'home_team': sb_info['home_team'],
            'away_team': sb_info['away_team'],
            'home_goals': sb_info['home_goals'],
            'away_goals': sb_info['away_goals'],
            'home_goals_ht': '',
            'away_goals_ht': '',
            'status': 'finished',
            'referee': sb_info.get('referee', ''),
            'attendance': '',
            # match_stats from StatsBomb aggregates
            'home_shots': agg.get('home_shots_total', ''),
            'away_shots': agg.get('away_shots_total', ''),
            'home_shots_target': agg.get('home_shots_on_target', ''),
            'away_shots_target': agg.get('away_shots_on_target', ''),
            'home_corners': '',
            'away_corners': '',
            'home_fouls': agg.get('home_fouls_committed', ''),
            'away_fouls': agg.get('away_fouls_committed', ''),
            'home_yellow': '',
            'away_yellow': '',
            'home_red': '',
            'away_red': '',
            # odds - none for StatsBomb-only
            'b365_home': '', 'b365_draw': '', 'b365_away': '',
            'ps_home': '', 'ps_draw': '', 'ps_away': '',
            'max_home': '', 'max_draw': '', 'max_away': '',
            'avg_home': '', 'avg_draw': '', 'avg_away': '',
            'b365_over_2_5': '', 'b365_under_2_5': '',
            'ps_over_2_5': '', 'ps_under_2_5': '',
            'max_over_2_5': '', 'max_under_2_5': '',
            'avg_over_2_5': '', 'avg_under_2_5': '',
            'asian_handicap': '',
            'b365_ah_home': '', 'b365_ah_away': '',
            'ps_ah_home': '', 'ps_ah_away': '',
            'max_ah_home': '', 'max_ah_away': '',
            'avg_ah_home': '', 'avg_ah_away': '',
            'b365_c_home': '', 'b365_c_draw': '', 'b365_c_away': '',
            'ps_c_home': '', 'ps_c_draw': '', 'ps_c_away': '',
            'max_c_home': '', 'max_c_draw': '', 'max_c_away': '',
            'avg_c_home': '', 'avg_c_draw': '', 'avg_c_away': '',
        }
        all_rows.append(row_data)

print('  StatsBomb merged with football-data: %d' % sb_merged_count)
print('  StatsBomb-only (new rows): %d' % sb_only_count)
print('  Total rows now: %d' % len(all_rows))

# ============================================================
# Step 5: Write matches table
# ============================================================
print('Step 5: Writing matches table...')

MATCHES_COLS = [
    'match_id', 'league', 'season', 'match_date', 'match_time',
    'round', 'division', 'home_team', 'away_team',
    'home_goals', 'away_goals', 'home_goals_ht', 'away_goals_ht',
    'status', 'referee', 'attendance',
]

with open(os.path.join(OUT, 'matches.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=MATCHES_COLS, extrasaction='ignore')
    writer.writeheader()
    for r in all_rows:
        writer.writerow(r)

print('  Written %d rows to matches.csv' % len(all_rows))

# ============================================================
# Step 6: Write match_detail table
# ============================================================
print('Step 6: Writing match_detail table...')

DETAIL_COLS = [
    'match_id',
    'home_shots', 'away_shots', 'home_shots_target', 'away_shots_target',
    'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
    'home_yellow', 'away_yellow', 'home_red', 'away_red',
    'sb_match_id', 'sb_home_team_id', 'sb_away_team_id',
    'sb_home_xg', 'sb_away_xg',
    'sb_home_shots_total', 'sb_away_shots_total',
    'sb_home_shots_on_target', 'sb_away_shots_on_target',
    'sb_home_passes_total', 'sb_away_passes_total',
    'sb_home_pass_complete', 'sb_away_pass_complete',
    'sb_home_pass_completion_rate', 'sb_away_pass_completion_rate',
    'sb_home_pressures', 'sb_away_pressures',
    'sb_home_carry_count', 'sb_away_carry_count',
    'sb_home_dribbles_success', 'sb_away_dribbles_success',
    'sb_home_dribbles_attempted', 'sb_away_dribbles_attempted',
    'sb_home_interceptions', 'sb_away_interceptions',
    'sb_home_clearances', 'sb_away_clearances',
    'sb_home_blocks', 'sb_away_blocks',
    'sb_home_ball_recovery', 'sb_away_ball_recovery',
    'sb_home_fouls_committed', 'sb_away_fouls_committed',
    'sb_home_dispossessed', 'sb_away_dispossessed',
    'sb_home_miscontrol', 'sb_away_miscontrol',
    'sb_home_keeper_actions', 'sb_away_keeper_actions',
    'sb_home_crosses', 'sb_away_crosses',
    'sb_home_assists', 'sb_away_assists',
    'sb_home_key_passes', 'sb_away_key_passes',
    'sb_stadium', 'sb_home_manager', 'sb_away_manager',
]

# Build sb_match_id -> our match_id mapping
sb_id_to_match_id = {}
for sb_mid, sb_info in sb_match_data.items():
    sb_id_to_match_id[sb_mid] = sb_info['match_id']

# Also add StatsBomb-only match_ids
for r in all_rows:
    if r['league'] in ['copa_america', 'africa_cup', 'indian_super_league', 'mls', 'wsl']:
        # These are StatsBomb-only, check if any sb_match_data has this match_id
        pass

detail_rows = []
for r in all_rows:
    mid = r['match_id']

    # Find StatsBomb data for this match
    sb_mid = ''
    sb_agg = {}
    sb_info = {}

    # Search by match_id
    for sbm, sbi in sb_match_data.items():
        if sbi['match_id'] == mid:
            sb_mid = sbm
            sb_info = sbi
            sb_agg = sb_aggregates.get(sbm, {})
            break

    # If not found by match_id, try by date+teams
    if not sb_mid:
        key = '%s_%s_%s' % (r['match_date'], normalize_team(r['home_team']), normalize_team(r['away_team']))
        for sbm, sbi in sb_match_data.items():
            sb_key = '%s_%s_%s' % (sbi['match_date'], normalize_team(sbi['home_team']), normalize_team(sbi['away_team']))
            if key == sb_key:
                sb_mid = sbm
                sb_info = sbi
                sb_agg = sb_aggregates.get(sbm, {})
                break

    detail_row = {
        'match_id': mid,
        'home_shots': r['home_shots'],
        'away_shots': r['away_shots'],
        'home_shots_target': r['home_shots_target'],
        'away_shots_target': r['away_shots_target'],
        'home_corners': r['home_corners'],
        'away_corners': r['away_corners'],
        'home_fouls': r['home_fouls'],
        'away_fouls': r['away_fouls'],
        'home_yellow': r['home_yellow'],
        'away_yellow': r['away_yellow'],
        'home_red': r['home_red'],
        'away_red': r['away_red'],
        'sb_match_id': sb_mid if sb_mid else '',
        'sb_home_team_id': sb_info.get('home_team_id', ''),
        'sb_away_team_id': sb_info.get('away_team_id', ''),
        'sb_home_xg': sb_agg.get('home_xg', ''),
        'sb_away_xg': sb_agg.get('away_xg', ''),
        'sb_home_shots_total': sb_agg.get('home_shots_total', ''),
        'sb_away_shots_total': sb_agg.get('away_shots_total', ''),
        'sb_home_shots_on_target': sb_agg.get('home_shots_on_target', ''),
        'sb_away_shots_on_target': sb_agg.get('away_shots_on_target', ''),
        'sb_home_passes_total': sb_agg.get('home_passes_total', ''),
        'sb_away_passes_total': sb_agg.get('away_passes_total', ''),
        'sb_home_pass_complete': sb_agg.get('home_pass_complete', ''),
        'sb_away_pass_complete': sb_agg.get('away_pass_complete', ''),
        'sb_home_pass_completion_rate': sb_agg.get('home_pass_completion_rate', ''),
        'sb_away_pass_completion_rate': sb_agg.get('away_pass_completion_rate', ''),
        'sb_home_pressures': sb_agg.get('home_pressures', ''),
        'sb_away_pressures': sb_agg.get('away_pressures', ''),
        'sb_home_carry_count': sb_agg.get('home_carry_count', ''),
        'sb_away_carry_count': sb_agg.get('away_carry_count', ''),
        'sb_home_dribbles_success': sb_agg.get('home_dribbles_success', ''),
        'sb_away_dribbles_success': sb_agg.get('away_dribbles_success', ''),
        'sb_home_dribbles_attempted': sb_agg.get('home_dribbles_attempted', ''),
        'sb_away_dribbles_attempted': sb_agg.get('away_dribbles_attempted', ''),
        'sb_home_interceptions': sb_agg.get('home_interceptions', ''),
        'sb_away_interceptions': sb_agg.get('away_interceptions', ''),
        'sb_home_clearances': sb_agg.get('home_clearances', ''),
        'sb_away_clearances': sb_agg.get('away_clearances', ''),
        'sb_home_blocks': sb_agg.get('home_blocks', ''),
        'sb_away_blocks': sb_agg.get('away_blocks', ''),
        'sb_home_ball_recovery': sb_agg.get('home_ball_recovery', ''),
        'sb_away_ball_recovery': sb_agg.get('away_ball_recovery', ''),
        'sb_home_fouls_committed': sb_agg.get('home_fouls_committed', ''),
        'sb_away_fouls_committed': sb_agg.get('away_fouls_committed', ''),
        'sb_home_dispossessed': sb_agg.get('home_dispossessed', ''),
        'sb_away_dispossessed': sb_agg.get('away_dispossessed', ''),
        'sb_home_miscontrol': sb_agg.get('home_miscontrol', ''),
        'sb_away_miscontrol': sb_agg.get('away_miscontrol', ''),
        'sb_home_keeper_actions': sb_agg.get('home_keeper_actions', ''),
        'sb_away_keeper_actions': sb_agg.get('away_keeper_actions', ''),
        'sb_home_crosses': sb_agg.get('home_crosses', ''),
        'sb_away_crosses': sb_agg.get('away_crosses', ''),
        'sb_home_assists': sb_agg.get('home_assists', ''),
        'sb_away_assists': sb_agg.get('away_assists', ''),
        'sb_home_key_passes': sb_agg.get('home_key_passes', ''),
        'sb_away_key_passes': sb_agg.get('away_key_passes', ''),
        'sb_stadium': sb_info.get('stadium', ''),
        'sb_home_manager': sb_info.get('home_manager', ''),
        'sb_away_manager': sb_info.get('away_manager', ''),
    }
    detail_rows.append(detail_row)

with open(os.path.join(OUT, 'match_detail.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=DETAIL_COLS, extrasaction='ignore')
    writer.writeheader()
    for r in detail_rows:
        writer.writerow(r)

print('  Written %d rows to match_detail.csv' % len(detail_rows))

# ============================================================
# Step 7: Write odds table
# ============================================================
print('Step 7: Writing odds table...')

ODDS_COLS = [
    'match_id',
    'b365_home', 'b365_draw', 'b365_away',
    'ps_home', 'ps_draw', 'ps_away',
    'max_home', 'max_draw', 'max_away',
    'avg_home', 'avg_draw', 'avg_away',
    'b365_over_2_5', 'b365_under_2_5',
    'ps_over_2_5', 'ps_under_2_5',
    'max_over_2_5', 'max_under_2_5',
    'avg_over_2_5', 'avg_under_2_5',
    'asian_handicap',
    'b365_ah_home', 'b365_ah_away',
    'ps_ah_home', 'ps_ah_away',
    'max_ah_home', 'max_ah_away',
    'avg_ah_home', 'avg_ah_away',
    'b365_c_home', 'b365_c_draw', 'b365_c_away',
    'ps_c_home', 'ps_c_draw', 'ps_c_away',
    'max_c_home', 'max_c_draw', 'max_c_away',
    'avg_c_home', 'avg_c_draw', 'avg_c_away',
]

# Only write rows that have at least one odds value
odds_rows = []
for r in all_rows:
    has_odds = any(r.get(c, '') not in ('', 'null', 'None') for c in ODDS_COLS if c != 'match_id')
    if has_odds:
        odds_rows.append(r)

with open(os.path.join(OUT, 'odds.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=ODDS_COLS, extrasaction='ignore')
    writer.writeheader()
    for r in odds_rows:
        writer.writerow(r)

print('  Written %d rows to odds.csv' % len(odds_rows))

# ============================================================
# Step 8: Write statsbomb_shots table
# ============================================================
print('Step 8: Writing statsbomb_shots table...')

SHOT_COLS = [
    'match_id', 'sb_match_id', 'league', 'season', 'match_date',
    'team', 'team_id', 'player', 'player_id',
    'minute', 'second', 'period',
    'xg', 'shot_type', 'shot_outcome', 'shot_technique',
    'body_part', 'first_time', 'open_play',
    'location_x', 'location_y', 'end_location_x', 'end_location_y', 'end_location_z',
    'key_pass_id', 'play_pattern',
]

shot_rows = []
for fname in sorted(os.listdir(SB_EVENTS)):
    if not fname.endswith('.json'):
        continue
    sb_mid = int(fname.replace('.json', ''))
    sb_info = sb_match_data.get(sb_mid, {})
    match_id = sb_info.get('match_id', '')

    try:
        with open(os.path.join(SB_EVENTS, fname), encoding='utf-8') as fh:
            events = json.load(fh)
    except:
        continue

    for e in events:
        if e['type']['name'] != 'Shot':
            continue
        shot = e.get('shot', {})
        player = e.get('player', {})
        end_loc = shot.get('end_location', [])
        loc = e.get('location', [])

        shot_rows.append({
            'match_id': match_id,
            'sb_match_id': sb_mid,
            'league': sb_info.get('league', ''),
            'season': sb_info.get('season', ''),
            'match_date': sb_info.get('match_date', ''),
            'team': e['team']['name'],
            'team_id': e['team']['id'],
            'player': player.get('name', ''),
            'player_id': player.get('id', ''),
            'minute': e.get('minute', ''),
            'second': e.get('second', ''),
            'period': e.get('period', ''),
            'xg': shot.get('statsbomb_xg', ''),
            'shot_type': shot.get('type', {}).get('name', ''),
            'shot_outcome': shot.get('outcome', {}).get('name', ''),
            'shot_technique': shot.get('technique', {}).get('name', ''),
            'body_part': shot.get('body_part', {}).get('name', ''),
            'first_time': shot.get('first_time', ''),
            'open_play': 1 if shot.get('type', {}).get('name') == 'Open Play' else 0,
            'location_x': loc[0] if len(loc) >= 2 else '',
            'location_y': loc[1] if len(loc) >= 2 else '',
            'end_location_x': end_loc[0] if len(end_loc) >= 1 else '',
            'end_location_y': end_loc[1] if len(end_loc) >= 2 else '',
            'end_location_z': end_loc[2] if len(end_loc) >= 3 else '',
            'key_pass_id': shot.get('key_pass_id', ''),
            'play_pattern': e.get('play_pattern', {}).get('name', ''),
        })

with open(os.path.join(OUT, 'statsbomb_shots.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=SHOT_COLS, extrasaction='ignore')
    writer.writeheader()
    for r in shot_rows:
        writer.writerow(r)

print('  Written %d rows to statsbomb_shots.csv' % len(shot_rows))

# ============================================================
# Step 9: Write statsbomb_passes table
# ============================================================
print('Step 9: Writing statsbomb_passes table...')

PASS_COLS = [
    'match_id', 'sb_match_id', 'league', 'season', 'match_date',
    'team', 'team_id', 'player', 'player_id',
    'minute', 'second', 'period',
    'pass_type', 'pass_outcome', 'pass_length', 'pass_angle',
    'pass_height', 'body_part',
    'location_x', 'location_y', 'end_location_x', 'end_location_y',
    'recipient', 'recipient_id',
    'cross', 'shot_assist', 'goal_assist',
    'play_pattern',
]

pass_rows = []
for fname in sorted(os.listdir(SB_EVENTS)):
    if not fname.endswith('.json'):
        continue
    sb_mid = int(fname.replace('.json', ''))
    sb_info = sb_match_data.get(sb_mid, {})
    match_id = sb_info.get('match_id', '')

    try:
        with open(os.path.join(SB_EVENTS, fname), encoding='utf-8') as fh:
            events = json.load(fh)
    except:
        continue

    for e in events:
        if e['type']['name'] != 'Pass':
            continue
        p = e.get('pass', {})
        player = e.get('player', {})
        recipient = p.get('recipient', {})
        end_loc = p.get('end_location', [])
        loc = e.get('location', [])

        pass_rows.append({
            'match_id': match_id,
            'sb_match_id': sb_mid,
            'league': sb_info.get('league', ''),
            'season': sb_info.get('season', ''),
            'match_date': sb_info.get('match_date', ''),
            'team': e['team']['name'],
            'team_id': e['team']['id'],
            'player': player.get('name', ''),
            'player_id': player.get('id', ''),
            'minute': e.get('minute', ''),
            'second': e.get('second', ''),
            'period': e.get('period', ''),
            'pass_type': p.get('type', {}).get('name', ''),
            'pass_outcome': p.get('outcome', {}).get('name', ''),
            'pass_length': round(p.get('length', 0), 2) if p.get('length') else '',
            'pass_angle': round(p.get('angle', 0), 4) if p.get('angle') else '',
            'pass_height': p.get('height', {}).get('name', ''),
            'body_part': p.get('body_part', {}).get('name', ''),
            'location_x': loc[0] if len(loc) >= 2 else '',
            'location_y': loc[1] if len(loc) >= 2 else '',
            'end_location_x': end_loc[0] if len(end_loc) >= 2 else '',
            'end_location_y': end_loc[1] if len(end_loc) >= 2 else '',
            'recipient': recipient.get('name', ''),
            'recipient_id': recipient.get('id', ''),
            'cross': 1 if p.get('cross') else 0,
            'shot_assist': 1 if p.get('shot_assist') else 0,
            'goal_assist': 1 if p.get('goal_assist') else 0,
            'play_pattern': e.get('play_pattern', {}).get('name', ''),
        })

with open(os.path.join(OUT, 'statsbomb_passes.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=PASS_COLS, extrasaction='ignore')
    writer.writeheader()
    for r in pass_rows:
        writer.writerow(r)

print('  Written %d rows to statsbomb_passes.csv' % len(pass_rows))

# ============================================================
# Step 10: Write statsbomb_player_match table
# ============================================================
print('Step 10: Writing statsbomb_player_match table...')

PLAYER_COLS = [
    'match_id', 'sb_match_id', 'league', 'season', 'match_date',
    'team', 'team_id', 'player', 'player_id', 'player_nickname',
    'jersey_number', 'position', 'country',
    'passes', 'pass_complete', 'pass_completion_rate',
    'shots', 'shots_on_target', 'xg',
    'pressures', 'carries', 'dribbles_success', 'dribbles_attempted',
    'interceptions', 'clearances', 'blocks',
    'fouls_committed', 'fouls_won',
    'dispossessed', 'miscontrol', 'ball_recovery',
    'yellow_card', 'red_card',
    'assists', 'key_passes', 'crosses',
    'minutes_played',
]

player_rows = []
for fname in sorted(os.listdir(SB_LINEUPS)):
    if not fname.endswith('.json'):
        continue
    sb_mid = int(fname.replace('.json', ''))
    sb_info = sb_match_data.get(sb_mid, {})
    match_id = sb_info.get('match_id', '')

    # Read lineup
    try:
        with open(os.path.join(SB_LINEUPS, fname), encoding='utf-8') as fh:
            lineups = json.load(fh)
    except:
        continue

    # Read events for this match
    event_file = os.path.join(SB_EVENTS, '%d.json' % sb_mid)
    if not os.path.exists(event_file):
        continue
    try:
        with open(event_file, encoding='utf-8') as fh:
            events = json.load(fh)
    except:
        continue

    # Aggregate events per player
    player_agg = defaultdict(lambda: defaultdict(float))
    for e in events:
        player = e.get('player', {})
        pid = player.get('id')
        if not pid:
            continue
        etype = e['type']['name']
        player_agg[pid][etype] += 1

        if etype == 'Shot':
            shot = e.get('shot', {})
            xg = shot.get('statsbomb_xg', 0) or 0
            player_agg[pid]['xg_total'] += xg
            outcome = shot.get('outcome', {}).get('name', '')
            if outcome in ('Goal', 'Saved', 'Post'):
                player_agg[pid]['shot_on_target'] += 1

        if etype == 'Pass':
            p = e.get('pass', {})
            poutcome = p.get('outcome', {})
            if poutcome and poutcome.get('name'):
                player_agg[pid]['pass_incomplete'] += 1
            else:
                player_agg[pid]['pass_complete'] += 1
            if p.get('cross'):
                player_agg[pid]['cross'] += 1
            if p.get('goal_assist'):
                player_agg[pid]['assist'] += 1
            if p.get('shot_assist'):
                player_agg[pid]['key_pass'] += 1

        if etype == 'Dribble':
            doutcome = e.get('dribble', {}).get('outcome', {}).get('name', '')
            if doutcome == 'Complete':
                player_agg[pid]['dribble_success'] += 1

    # Build player rows from lineup
    for team_data in lineups:
        team_name = team_data['team_name']
        team_id = team_data['team_id']

        for pl in team_data.get('lineup', []):
            pid = pl['player_id']
            agg = player_agg.get(pid, {})

            # Calculate minutes played
            positions = pl.get('positions', [])
            minutes = 0
            for pos in positions:
                try:
                    from_min = int(pos.get('from', '0:00').split(':')[0]) + int(pos.get('from', '0:00').split(':')[1]) / 60
                    to_min = int(pos.get('to', '90:00').split(':')[0]) + int(pos.get('to', '90:00').split(':')[1]) / 60
                    if pos.get('from_period', 1) == 2:
                        from_min += 45
                    if pos.get('to_period', 2) == 2:
                        to_min += 45
                    minutes += max(0, to_min - from_min)
                except:
                    pass

            # Cards
            yellow = sum(1 for c in pl.get('cards', []) if c.get('card_type') == 'Yellow Card')
            red = sum(1 for c in pl.get('cards', []) if c.get('card_type') == 'Red Card')

            # Position
            start_pos = ''
            if positions:
                start_pos = positions[0].get('position', '')

            total_passes = int(agg.get('Pass', 0))
            pass_complete = int(agg.get('pass_complete', 0))

            player_rows.append({
                'match_id': match_id,
                'sb_match_id': sb_mid,
                'league': sb_info.get('league', ''),
                'season': sb_info.get('season', ''),
                'match_date': sb_info.get('match_date', ''),
                'team': team_name,
                'team_id': team_id,
                'player': pl.get('player_name', ''),
                'player_id': pid,
                'player_nickname': pl.get('player_nickname', ''),
                'jersey_number': pl.get('jersey_number', ''),
                'position': start_pos,
                'country': pl.get('country', {}).get('name', ''),
                'passes': total_passes,
                'pass_complete': pass_complete,
                'pass_completion_rate': round(pass_complete / max(total_passes, 1), 4) if total_passes else '',
                'shots': int(agg.get('Shot', 0)),
                'shots_on_target': int(agg.get('shot_on_target', 0)),
                'xg': round(agg.get('xg_total', 0), 4),
                'pressures': int(agg.get('Pressure', 0)),
                'carries': int(agg.get('Carry', 0)),
                'dribbles_success': int(agg.get('dribble_success', 0)),
                'dribbles_attempted': int(agg.get('Dribble', 0)),
                'interceptions': int(agg.get('Interception', 0)),
                'clearances': int(agg.get('Clearance', 0)),
                'blocks': int(agg.get('Block', 0)),
                'fouls_committed': int(agg.get('Foul Committed', 0)),
                'fouls_won': int(agg.get('Foul Won', 0)),
                'dispossessed': int(agg.get('Dispossessed', 0)),
                'miscontrol': int(agg.get('Miscontrol', 0)),
                'ball_recovery': int(agg.get('Ball Recovery', 0)),
                'yellow_card': yellow,
                'red_card': red,
                'assists': int(agg.get('assist', 0)),
                'key_passes': int(agg.get('key_pass', 0)),
                'crosses': int(agg.get('cross', 0)),
                'minutes_played': round(minutes, 1) if minutes else '',
            })

with open(os.path.join(OUT, 'statsbomb_player_match.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
    writer = csv.DictWriter(fh, fieldnames=PLAYER_COLS, extrasaction='ignore')
    writer.writeheader()
    for r in player_rows:
        writer.writerow(r)

print('  Written %d rows to statsbomb_player_match.csv' % len(player_rows))

# ============================================================
# Summary
# ============================================================
print('\n=== SUMMARY ===')
print('matches.csv: %d rows' % len(all_rows))
print('match_detail.csv: %d rows' % len(detail_rows))
print('odds.csv: %d rows' % len(odds_rows))
print('statsbomb_shots.csv: %d rows' % len(shot_rows))
print('statsbomb_passes.csv: %d rows' % len(pass_rows))
print('statsbomb_player_match.csv: %d rows' % len(player_rows))

# Verify match_id uniqueness
match_ids = [r['match_id'] for r in all_rows]
unique_ids = set(match_ids)
print('\nmatch_id total: %d, unique: %d, duplicates: %d' % (len(match_ids), len(unique_ids), len(match_ids) - len(unique_ids)))

# Check xG fill rate
xg_filled = sum(1 for r in detail_rows if r.get('sb_home_xg', '') != '')
print('xG filled: %d / %d (%.1f%%)' % (xg_filled, len(detail_rows), 100*xg_filled/max(len(detail_rows),1)))

# Check odds fill rate
print('Odds rows: %d / %d (%.1f%%)' % (len(odds_rows), len(all_rows), 100*len(odds_rows)/max(len(all_rows),1)))
