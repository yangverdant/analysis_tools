"""
世界杯完整数据采集脚本
- 2018/2022历史比赛数据 (football_data_org)
- 2022/2026球队阵容 (football_data_org)
- 2018/2022比赛统计 (apifootball)
- WC 2026赛程/分组
"""
import sys, io, json, os, time, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = 'd:/football_tools/data/world_cup'
os.makedirs(DATA_DIR, exist_ok=True)

# ---- football_data_org ----
FD_TOKEN = "944e431594bf477fa85d24fa04d9c2fe"
FD_BASE = "https://api.football-data.org/v4"
FD_HEADERS = {"X-Auth-Token": FD_TOKEN}
FD_INTERVAL = 7

# ---- apifootball ----
AF_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
AF_BASE = "https://apiv3.apifootball.com"
AF_INTERVAL = 2

def fd_request(endpoint, params=None):
    url = f"{FD_BASE}/{endpoint}"
    try:
        r = requests.get(url, headers=FD_HEADERS, params=params, timeout=15,
                         proxies={'http': None, 'https': None})
        if r.status_code == 200:
            return r.json()
        print(f"  FD错误 {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"  FD请求失败: {e}")
    return None

def af_request(action, params=None):
    url = f"{AF_BASE}/"
    p = {"action": action, "APIkey": AF_KEY}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=15,
                         proxies={'http': None, 'https': None})
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and data.get("ERROR"):
                print(f"  AF错误: {data['ERROR']}")
                return None
            return data
        print(f"  AF HTTP {r.status_code}")
    except Exception as e:
        print(f"  AF请求失败: {e}")
    return None

def save_json(name, data):
    path = os.path.join(DATA_DIR, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    count = len(data) if isinstance(data, (list, dict)) else 0
    print(f"  已保存 {name}: {count}条")

def process_fd_matches(raw_matches, year):
    results = []
    for m in raw_matches:
        score = m.get("score", {})
        ft = score.get("fullTime", {})
        ht_score = score.get("halfTime", {})
        et = score.get("extraTime", {})
        pen = score.get("penalties", {})

        home_score_ft = ft.get("home")
        away_score_ft = ft.get("away")

        result = None
        if home_score_ft is not None and away_score_ft is not None:
            if home_score_ft > away_score_ft: result = 'H'
            elif home_score_ft == away_score_ft: result = 'D'
            else: result = 'A'

        results.append({
            'match_id': str(m.get("id", "")),
            'home_team': m.get("homeTeam", {}).get("shortName", ""),
            'home_team_id': str(m.get("homeTeam", {}).get("id", "")),
            'home_team_tla': m.get("homeTeam", {}).get("tla", ""),
            'away_team': m.get("awayTeam", {}).get("shortName", ""),
            'away_team_id': str(m.get("awayTeam", {}).get("id", "")),
            'away_team_tla': m.get("awayTeam", {}).get("tla", ""),
            'home_score_ft': home_score_ft,
            'away_score_ft': away_score_ft,
            'home_score_ht': ht_score.get("home"),
            'away_score_ht': ht_score.get("away"),
            'home_score_et': et.get("home"),
            'away_score_et': et.get("away"),
            'home_score_pen': pen.get("home"),
            'away_score_pen': pen.get("away"),
            'date': m.get("utcDate", "")[:10],
            'time': m.get("utcDate", "")[11:16] if len(m.get("utcDate", "") or "") > 11 else None,
            'status': m.get("status", ""),
            'stage': m.get("stage", ""),
            'group': m.get("group", ""),
            'matchday': m.get("matchday"),
            'result': result,
            'competition': m.get("competition", {}).get("name", ""),
            'season_year': year,
            'source': 'football_data_org'
        })
    return results

def process_fd_team(raw_team):
    squad = []
    for p in raw_team.get("squad", []):
        squad.append({
            'player_id': str(p.get("id", "")),
            'name': p.get("name", ""),
            'position': p.get("position", ""),
            'nationality': p.get("nationality", ""),
            'date_of_birth': p.get("dateOfBirth", "")[:10] if p.get("dateOfBirth") else None,
        })

    return {
        'team_id': str(raw_team.get("id", "")),
        'name': raw_team.get("name", ""),
        'short_name': raw_team.get("shortName", ""),
        'tla': raw_team.get("tla", ""),
        'crest': raw_team.get("crest", ""),
        'country': raw_team.get("area", {}).get("name", ""),
        'founded': raw_team.get("founded"),
        'venue': raw_team.get("venue", ""),
        'squad': squad,
        'squad_size': len(squad),
        'source': 'football_data_org'
    }

# ===== 采集执行 =====
print("=" * 60)
print("  世界杯数据采集开始")
print("=" * 60)

# 1. FD.org: WC 2018 比赛
print("\n[1] WC 2018 比赛 (FD.org)...")
wc2018 = fd_request("competitions/WC/matches", {"season": 2018})
m2018 = []
if wc2018 and "matches" in wc2018:
    m2018 = process_fd_matches(wc2018["matches"], 2018)
    save_json("wc_2018_matches.json", m2018)
    finished = [m for m in m2018 if m['status'] == 'FINISHED']
    print(f"  2018: {len(m2018)}场, 已完赛{len(finished)}场")
else:
    print("  2018数据获取失败")
time.sleep(FD_INTERVAL)

# 2. FD.org: WC 2022 比赛
print("\n[2] WC 2022 比赛 (FD.org)...")
wc2022 = fd_request("competitions/WC/matches", {"season": 2022})
m2022 = []
if wc2022 and "matches" in wc2022:
    m2022 = process_fd_matches(wc2022["matches"], 2022)
    save_json("wc_2022_matches.json", m2022)
    finished = [m for m in m2022 if m['status'] == 'FINISHED']
    print(f"  2022: {len(m2022)}场, 已完赛{len(finished)}场")
time.sleep(FD_INTERVAL)

# 3. FD.org: WC 2026 比赛(赛程)
print("\n[3] WC 2026 赛程 (FD.org)...")
wc2026 = fd_request("competitions/WC/matches", {"season": 2026})
m2026 = []
if wc2026 and "matches" in wc2026:
    m2026 = process_fd_matches(wc2026["matches"], 2026)
    save_json("wc_2026_matches.json", m2026)
    scheduled = [m for m in m2026 if m['status'] in ('SCHEDULED', 'TIMED')]
    print(f"  2026: {len(m2026)}场, 未开始{len(scheduled)}场")
else:
    print("  2026数据获取失败或尚未开放")
time.sleep(FD_INTERVAL)

# 4. WC 2018 球队阵容
print("\n[4] WC 2018 球队阵容 (FD.org)...")
team_ids_2018 = set()
for m in m2018:
    if m['home_team_id']: team_ids_2018.add(m['home_team_id'])
    if m['away_team_id']: team_ids_2018.add(m['away_team_id'])

teams_2018 = []
for tid in sorted(team_ids_2018):
    print(f"  获取球队 {tid}...")
    td = fd_request(f"teams/{tid}")
    if td:
        teams_2018.append(process_fd_team(td))
    time.sleep(FD_INTERVAL)

if teams_2018:
    save_json("wc_2018_teams.json", teams_2018)
    print(f"  2018球队: {len(teams_2018)}")

# 5. WC 2022 球队阵容
print("\n[5] WC 2022 球队阵容 (FD.org)...")
team_ids_2022 = set()
for m in m2022:
    if m['home_team_id']: team_ids_2022.add(m['home_team_id'])
    if m['away_team_id']: team_ids_2022.add(m['away_team_id'])

teams_2022 = []
for tid in sorted(team_ids_2022):
    print(f"  获取球队 {tid}...")
    td = fd_request(f"teams/{tid}")
    if td:
        teams_2022.append(process_fd_team(td))
    time.sleep(FD_INTERVAL)

if teams_2022:
    save_json("wc_2022_teams.json", teams_2022)
    print(f"  2022球队: {len(teams_2022)}")

# 6. WC 2026 球队阵容
print("\n[6] WC 2026 球队阵容 (FD.org)...")
team_ids_2026 = set()
for m in m2026:
    if m['home_team_id']: team_ids_2026.add(m['home_team_id'])
    if m['away_team_id']: team_ids_2026.add(m['away_team_id'])

teams_2026 = []
for tid in sorted(team_ids_2026):
    print(f"  获取球队 {tid}...")
    td = fd_request(f"teams/{tid}")
    if td:
        teams_2026.append(process_fd_team(td))
    time.sleep(FD_INTERVAL)

if teams_2026:
    save_json("wc_2026_teams.json", teams_2026)
    print(f"  2026球队: {len(teams_2026)}")

# 7. apifootball: WC 2022 比赛统计
print("\n[7] WC 2022 比赛统计 (apifootball, league_id=28)...")
af_wc2022 = af_request("get_events", {"league_id": 28, "from": "2022-11-01", "to": "2022-12-31"})
if af_wc2022 and isinstance(af_wc2022, list):
    save_json("wc_2022_af_matches.json", af_wc2022)
    print(f"  AF 2022: {len(af_wc2022)}场")
time.sleep(AF_INTERVAL)

# 8. apifootball: WC 2018 比赛统计
print("\n[8] WC 2018 比赛统计 (apifootball, league_id=28)...")
af_wc2018 = af_request("get_events", {"league_id": 28, "from": "2018-06-01", "to": "2018-07-31"})
if af_wc2018 and isinstance(af_wc2018, list):
    save_json("wc_2018_af_matches.json", af_wc2018)
    print(f"  AF 2018: {len(af_wc2018)}场")
time.sleep(AF_INTERVAL)

# 9. apifootball: WC 2026 赛程
print("\n[9] WC 2026 赛程 (apifootball)...")
af_wc2026 = af_request("get_events", {"league_id": 28, "from": "2026-06-01", "to": "2026-07-31"})
if af_wc2026 and isinstance(af_wc2026, list):
    save_json("wc_2026_af_matches.json", af_wc2026)
    print(f"  AF 2026: {len(af_wc2026)}场")
else:
    print("  AF 2026暂无数据")

# ===== 采集报告 =====
print("\n" + "=" * 60)
print("  采集完成，汇总:")
print("=" * 60)

files = sorted(os.listdir(DATA_DIR))
for f in files:
    if f.endswith('.json'):
        path = os.path.join(DATA_DIR, f)
        size = os.path.getsize(path)
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            count = len(data) if isinstance(data, list) else 1
        print(f"  {f}: {size/1024:.1f}KB, {count}条")
