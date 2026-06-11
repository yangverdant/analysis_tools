"""
align_oddsfe_csv.py — 将CSV开盘价与oddsfe_merged.db对齐

从CSV all.csv提取开盘价(PSH/B365H等)，按日期+球队名匹配oddsfe比赛
输出: oddsfe_opening_odds.csv — 每行一场比赛，包含oddsfe基础数据+CSV开盘价

匹配策略:
1. 日期精确匹配 (YYYY-MM-DD)
2. 球队名: 直接匹配 → 常见映射表 → 模糊匹配(包含关系)
"""

import sqlite3
import csv
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_PATH = os.path.join(PROJECT_DIR, 'fetchers', 'odds_feed_api', 'oddsfe_merged.db')
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
OUTPUT_PATH = os.path.join(PROJECT_DIR, 'fetchers', 'odds_feed_api', 'oddsfe_opening_odds.csv')

# CSV球队名 → oddsfe球队名 的常见映射
TEAM_NAME_MAP = {
    # 英超
    'Man City': 'Manchester City',
    'Man United': 'Manchester Utd',
    "Nott'm Forest": 'Nottingham',
    'Nottingham Forest': 'Nottingham',
    'Tottenham': 'Tottenham',
    'Wolves': 'Wolves',
    # 德甲
    'Bayern Munich': 'Bayern Munich',
    'Borussia M\'gladbach': 'Monchengladbach',
    'M\'gladbach': 'Monchengladbach',
    'Leverkusen': 'Bayer Leverkusen',
    'Ein Frankfurt': 'Eintracht Frankfurt',
    'TSG Hoffenheim': 'Hoffenheim',
    'Friburg': 'Freiburg',
    'Mainz 05': 'Mainz',
    'Stuttgart': 'Stuttgart',
    'Wolfsburg': 'Wolfsburg',
    'Augsburg': 'Augsburg',
    'Union Berlin': 'Union Berlin',
    'Bochum': 'Bochum',
    'Darmstadt': 'Darmstadt',
    'Heidenheim': 'Heidenheim',
    'Holstein Kiel': 'Holstein Kiel',
    'St Pauli': 'St. Pauli',
    # 西甲
    'Ath Madrid': 'Atletico Madrid',
    'Ath Bilbao': 'Athletic Bilbao',
    'Celta Vigo': 'Celta Vigo',
    'Alaves': 'Alaves',
    'Real Sociedad': 'Real Sociedad',
    'Real Betis': 'Real Betis',
    'Las Palmas': 'Las Palmas',
    'Leganes': 'Leganes',
    'Espanyol': 'Espanyol',
    'Girona': 'Girona',
    'Sevilla': 'Sevilla',
    'Valencia': 'Valencia',
    'Villarreal': 'Villarreal',
    'Getafe': 'Getafe',
    'Mallorca': 'Mallorca',
    'Osasuna': 'Osasuna',
    # 意甲
    'Inter': 'Inter',
    'Milan': 'Milan',
    'Roma': 'Roma',
    'Lazio': 'Lazio',
    'Napoli': 'Napoli',
    'Fiorentina': 'Fiorentina',
    'Atalanta': 'Atalanta',
    'Juventus': 'Juventus',
    'Torino': 'Torino',
    'Bologna': 'Bologna',
    'Monza': 'Monza',
    'Udinese': 'Udinese',
    'Sassuolo': 'Sassuolo',
    'Cagliari': 'Cagliari',
    'Genoa': 'Genoa',
    'Verona': 'Verona',
    'Lecce': 'Lecce',
    'Empoli': 'Empoli',
    'Salernitana': 'Salernitana',
    'Frosinone': 'Frosinone',
    'Venezia': 'Venezia',
    'Parma': 'Parma',
    'Como': 'Como',
    # 法甲
    'Paris SG': 'Paris Saint-Germain',
    'PSG': 'Paris Saint-Germain',
    'Marseille': 'Marseille',
    'Lyon': 'Lyon',
    'Monaco': 'Monaco',
    'Lille': 'Lille',
    'Nice': 'Nice',
    'Rennes': 'Rennes',
    'Lens': 'Lens',
    'Strasbourg': 'Strasbourg',
    'Toulouse': 'Toulouse',
    'Montpellier': 'Montpellier',
    'Nantes': 'Nantes',
    'Reims': 'Reims',
    'Brest': 'Brest',
    'Le Havre': 'Le Havre',
    'Metz': 'Metz',
    'Lorient': 'Lorient',
    'Clermont': 'Clermont',
    'Auxerre': 'Auxerre',
    'Angers': 'Angers',
    'Saint-Etienne': 'Saint-Etienne',
    # 荷甲
    'PSV': 'PSV Eindhoven',
    'Feyenoord': 'Feyenoord',
    'Ajax': 'Ajax',
    'AZ Alkmaar': 'AZ Alkmaar',
    'Twente': 'Twente',
    'Utrecht': 'Utrecht',
    'Vitesse': 'Vitesse',
    'Heerenveen': 'Heerenveen',
    'Groningen': 'Groningen',
    'Sparta': 'Sparta',
    'NAC Breda': 'NAC Breda',
    'Willem II': 'Willem II',
    'Go Ahead Eagles': 'Go Ahead Eagles',
    'Heracles': 'Heracles',
    'PEC Zwolle': 'PEC Zwolle',
    'RKC Waalwijk': 'RKC Waalwijk',
    'Fortuna Sittard': 'Fortuna Sittard',
    'Almere City': 'Almere City',
    'Excelsior': 'Excelsior',
    # 葡超
    'Benfica': 'Benfica',
    'Porto': 'Porto',
    'Sporting': 'Sporting CP',
    'Braga': 'Braga',
    # 比甲
    'Genk': 'Genk',
    'Club Brugge': 'Club Brugge',
    'Anderlecht': 'Anderlecht',
    'Antwerp': 'Antwerp',
    'Standard': 'Standard Liege',
    'Gent': 'Gent',
    # 苏格兰
    'Celtic': 'Celtic',
    'Rangers': 'Rangers',
    'Aberdeen': 'Aberdeen',
    'Hearts': 'Hearts',
    'Hibernian': 'Hibernian',
    'Dundee Utd': 'Dundee United',
    'Motherwell': 'Motherwell',
    'St Mirren': 'St. Mirren',
    'Kilmarnock': 'Kilmarnock',
    'Ross County': 'Ross County',
    'Livingston': 'Livingston',
    # 土耳其
    'Galatasaray': 'Galatasaray',
    'Fenerbahce': 'Fenerbahce',
    'Besiktas': 'Besiktas',
    'Trabzonspor': 'Trabzonspor',
    'Istanbul BB': 'Istanbul Basaksehir',
    'Kasimpasa': 'Kasimpasa',
    'Antalyaspor': 'Antalyaspor',
    'Sivasspor': 'Sivasspor',
    'Alanyaspor': 'Alanyaspor',
    'Konyaspor': 'Konyaspor',
    'Rizespor': 'Rizespor',
    'Kayserispor': 'Kayserispor',
    'Hatayspor': 'Hatayspor',
    'Gaziantep FK': 'Gaziantep',
    'Adana Demirspor': 'Adana Demirspor',
    'Pendikspor': 'Pendikspor',
    'Samsunspor': 'Samsunspor',
    # 希腊
    'PAOK': 'PAOK',
    'Olympiacos': 'Olympiacos',
    'Panathinaikos': 'Panathinaikos',
    'AEK Athens': 'AEK Athens',
}


def parse_csv_date(d):
    """解析CSV日期 DD-MM-YY 或 DD/MM/YYYY → YYYY-MM-DD"""
    d = d.strip()
    if not d:
        return ''
    if '/' in d:
        parts = d.split('/')
        if len(parts) == 3:
            dd, mm, yy = parts
            if len(yy) == 4:
                return f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
            else:
                prefix = '20' if int(yy) < 50 else '19'
                return f"{prefix}{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
    elif '-' in d:
        parts = d.split('-')
        if len(parts) == 3:
            if len(parts[0]) == 4:
                return d
            else:
                dd, mm, yy = parts
                prefix = '20' if int(yy) < 50 else '19'
                return f"{prefix}{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
    return d


def safe_odds(val):
    """安全解析赔率值，返回float或0。处理 '1.972 250€'、'05-30' 等异常值"""
    if not val or not val.strip():
        return 0
    try:
        return float(val.strip().split()[0])
    except (ValueError, IndexError):
        return 0


def match_team(csv_name, oddsfe_name):
    """匹配球队名: 直接→映射→模糊"""
    if csv_name == oddsfe_name:
        return True

    # 映射表
    mapped = TEAM_NAME_MAP.get(csv_name, '')
    if mapped and mapped == oddsfe_name:
        return True

    # 包含关系 (如 "Manchester City" 包含 "City")
    if csv_name in oddsfe_name or oddsfe_name in csv_name:
        # 排除误匹配: "City" 不能匹配 "Hull City"
        shorter = min(csv_name, oddsfe_name, key=len)
        longer = max(csv_name, oddsfe_name, key=len)
        if len(shorter) >= 4 and shorter in longer:
            return True

    return False


def load_csv_opening_odds(data_dir):
    """加载所有CSV all.csv的开盘价数据，返回 {(date, home, away): {field: value}}"""
    csv_lookup = {}

    all_csvs = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith('.csv'):
                # 排除非比赛数据文件
                if any(x in f.lower() for x in ['teams', 'ranking', 'linkage', 'fixture', 'formation', 'rules', 'player', 'coach', 'season', 'name', 'summary', 'history', 'goal', 'shootout']):
                    continue
                path = os.path.join(root, f)
                all_csvs.append(path)

    print(f"Loading {len(all_csvs)} CSV files...")

    for path in all_csvs:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)

                # 检查必需字段
                required = ['Date', 'HomeTeam', 'AwayTeam']
                if not all(r in header for r in required):
                    continue
                if 'PSH' not in header and 'B365H' not in header:
                    continue  # 没有任何开盘价，跳过

                idx = {h: i for i, h in enumerate(header)}
                rows = list(reader)

                for r in rows:
                    if len(r) <= max(idx['Date'], idx['HomeTeam'], idx['AwayTeam']):
                        continue

                    date_raw = r[idx['Date']]
                    date = parse_csv_date(date_raw)
                    home = r[idx['HomeTeam']]
                    away = r[idx['AwayTeam']]

                    if not date or not home or not away:
                        continue

                    key = (date, home, away)

                    # 提取开盘价字段
                    odds_fields = {}
                    for field in ['PSH', 'PSD', 'PSA', 'PSCH', 'B365H', 'B365D', 'B365A', 'B365CH',
                                  'WHH', 'WHD', 'WHA', 'BWH', 'BWD', 'BWA', 'IWH', 'IWD', 'IWA',
                                  'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG',
                                  'HS', 'AS', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC',
                                  'HY', 'AY', 'HR', 'AR',
                                  'AHh', 'B365AHH', 'B365AHA', 'PAHH', 'PAHA',
                                  'B365>2.5', 'B365<2.5', 'PS>2.5', 'PS<2.5']:
                        if field in idx and len(r) > idx[field] and r[idx[field]] and r[idx[field]].strip():
                            odds_fields[field] = r[idx[field]].strip()

                    if odds_fields:
                        csv_lookup[key] = odds_fields
        except Exception as e:
            print(f"  Warning: {path}: {e}")

    print(f"  Loaded {len(csv_lookup)} CSV matches with opening odds")
    return csv_lookup


def build_csv_index(csv_lookup):
    """建日期索引: {date: [(home, away, odds_dict), ...]}"""
    index = {}
    for (date, home, away), odds in csv_lookup.items():
        if date not in index:
            index[date] = []
        index[date].append((home, away, odds))
    return index


def find_csv_match(date, oddsfe_home, oddsfe_away, csv_lookup, csv_index):
    """在CSV中找到匹配的比赛，返回开盘价dict"""
    # 1. 直接匹配
    key = (date, oddsfe_home, oddsfe_away)
    if key in csv_lookup:
        return csv_lookup[key], 'direct'

    # 2. 映射匹配
    mapped_home = TEAM_NAME_MAP.get(oddsfe_home, oddsfe_home)
    mapped_away = TEAM_NAME_MAP.get(oddsfe_away, oddsfe_away)
    key2 = (date, mapped_home, mapped_away)
    if key2 in csv_lookup:
        return csv_lookup[key2], 'mapped'

    # 3. 模糊匹配: 只在同日期的记录中搜索
    day_entries = csv_index.get(date, [])
    for ch, ca, odds in day_entries:
        if match_team(ch, oddsfe_home) and match_team(ca, oddsfe_away):
            return odds, 'fuzzy'

    return None, None


def main():
    print("=" * 60)
    print("oddsfe_merged.db <-> CSV opening odds alignment")
    print("=" * 60)

    # 1. 加载CSV开盘价
    csv_lookup = load_csv_opening_odds(DATA_DIR)
    csv_index = build_csv_index(csv_lookup)

    # 2. 加载oddsfe数据
    print(f"\nLoading oddsfe from {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 取所有有1X2赔率的比赛（不限Pinnacle）
    c.execute('''SELECT event_id, substr(event_start_at,1,10),
        category_name, tournament_name,
        team_home_name, team_away_name,
        event_score_home, event_score_away, event_winner,
        main_out_0, main_out_1, main_out_2,
        "1X2_prematch_PINNACLE_home", "1X2_prematch_PINNACLE_draw", "1X2_prematch_PINNACLE_away",
        "1X2_prematch_BET365_home", "1X2_prematch_BET365_draw", "1X2_prematch_BET365_away",
        "1X2_prematch_1XBET_home", "1X2_prematch_1XBET_draw", "1X2_prematch_1XBET_away",
        "OVER_UNDER_prematch_PINNACLE_over", "OVER_UNDER_prematch_PINNACLE_line", "OVER_UNDER_prematch_PINNACLE_under",
        "ASIAN_HANDICAP_prematch_PINNACLE_home", "ASIAN_HANDICAP_prematch_PINNACLE_handicap", "ASIAN_HANDICAP_prematch_PINNACLE_away",
        "BOTH_TEAMS_TO_SCORE_prematch_PINNACLE_yes", "BOTH_TEAMS_TO_SCORE_prematch_PINNACLE_no"
    FROM oddsfe
    WHERE CAST("1X2_prematch_PINNACLE_home" AS FLOAT) > 1.01
       OR CAST("1X2_prematch_BET365_home" AS FLOAT) > 1.01
       OR CAST("1X2_prematch_1XBET_home" AS FLOAT) > 1.01
    ORDER BY event_start_at''')

    oddsfe_rows = c.fetchall()
    print(f"  Loaded {len(oddsfe_rows)} oddsfe matches with Pinnacle odds")
    conn.close()

    # 3. 匹配
    print(f"\nMatching...")
    matched_direct = 0
    matched_mapped = 0
    matched_fuzzy = 0
    not_matched = 0
    results = []

    for r in oddsfe_rows:
        event_id = r[0]
        date = r[1]
        category = r[2]
        tournament = r[3]
        home = r[4]
        away = r[5]
        score_h = r[6]
        score_a = r[7]
        winner = r[8]
        pin_main_h, pin_main_d, pin_main_a = r[9], r[10], r[11]
        # Pinnacle 1X2
        pin_h = r[12] if safe_odds(r[12]) > 1.01 else ''
        pin_d = r[13] if safe_odds(r[13]) > 1.01 else ''
        pin_a = r[14] if safe_odds(r[14]) > 1.01 else ''
        # Bet365 1X2
        b365_h = r[15] if safe_odds(r[15]) > 1.01 else ''
        b365_d = r[16] if safe_odds(r[16]) > 1.01 else ''
        b365_a = r[17] if safe_odds(r[17]) > 1.01 else ''
        # 1XBET 1X2
        xbet_h = r[18] if safe_odds(r[18]) > 1.01 else ''
        xbet_d = r[19] if safe_odds(r[19]) > 1.01 else ''
        xbet_a = r[20] if safe_odds(r[20]) > 1.01 else ''
        # O/U Pinnacle
        ou_over = r[21] if safe_odds(r[21]) > 1.01 else ''
        ou_line = r[22] or ''
        ou_under = r[23] if safe_odds(r[23]) > 1.01 else ''
        # AH Pinnacle
        ah_home = r[24] if safe_odds(r[24]) > 1.01 else ''
        ah_hcp = r[25] or ''
        ah_away = r[26] if safe_odds(r[26]) > 1.01 else ''
        # BTTS Pinnacle
        btts_yes = r[27] if safe_odds(r[27]) > 1.01 else ''
        btts_no = r[28] if safe_odds(r[28]) > 1.01 else ''

        csv_odds, match_type = find_csv_match(date, home, away, csv_lookup, csv_index)

        row = {
            'event_id': event_id,
            'date': date,
            'category': category or '',
            'tournament': tournament or '',
            'home': home,
            'away': away,
            'score_home': score_h or '',
            'score_away': score_a or '',
            'winner': winner or '',
            # oddsfe收盘价 (prematch ≈ closing)
            'pin_close_h': pin_h,
            'pin_close_d': pin_d,
            'pin_close_a': pin_a,
            'b365_close_h': b365_h,
            'b365_close_d': b365_d,
            'b365_close_a': b365_a,
            '1xbet_close_h': xbet_h,
            '1xbet_close_d': xbet_d,
            '1xbet_close_a': xbet_a,
            # O/U AH BTTS
            'ou_over': ou_over,
            'ou_line': ou_line,
            'ou_under': ou_under,
            'ah_home': ah_home,
            'ah_hcp': ah_hcp,
            'ah_away': ah_away,
            'btts_yes': btts_yes,
            'btts_no': btts_no,
            # 匹配信息
            'match_type': match_type or '',
        }

        if csv_odds:
            # CSV开盘价
            row['psh'] = csv_odds.get('PSH', '')
            row['psd'] = csv_odds.get('PSD', '')
            row['psa'] = csv_odds.get('PSA', '')
            # CSV收盘价 (独立验证)
            row['psch'] = csv_odds.get('PSCH', '')
            # B365开盘
            row['b365h'] = csv_odds.get('B365H', '')
            row['b365d'] = csv_odds.get('B365D', '')
            row['b365a'] = csv_odds.get('B365A', '')
            # B365收盘
            row['b365ch'] = csv_odds.get('B365CH', '')
            # 其他庄开盘
            row['whh'] = csv_odds.get('WHH', '')
            row['bwh'] = csv_odds.get('BWH', '')
            row['iwh'] = csv_odds.get('IWH', '')
            # 比赛统计
            row['hs'] = csv_odds.get('HS', '')
            row['as'] = csv_odds.get('AS', '')
            row['hst'] = csv_odds.get('HST', '')
            row['ast'] = csv_odds.get('AST', '')
            row['hc'] = csv_odds.get('HC', '')
            row['ac'] = csv_odds.get('AC', '')
            row['hf'] = csv_odds.get('HF', '')
            row['af'] = csv_odds.get('AF', '')
            row['hy'] = csv_odds.get('HY', '')
            row['ay'] = csv_odds.get('AY', '')
            row['hr'] = csv_odds.get('HR', '')
            row['ar'] = csv_odds.get('AR', '')
            # 大小球/亚盘
            row['b365_ou25'] = csv_odds.get('B365>2.5', '')
            row['b365_under25'] = csv_odds.get('B365<2.5', '')
            row['ah_handicap'] = csv_odds.get('AHh', '')
            row['b365_ahh'] = csv_odds.get('B365AHH', '')
            row['b365_aha'] = csv_odds.get('B365AHA', '')
            row['ps_ahh'] = csv_odds.get('PAHH', '')
            row['ps_aha'] = csv_odds.get('PAHA', '')
            # 半场
            row['hthg'] = csv_odds.get('HTHG', '')
            row['htag'] = csv_odds.get('HTAG', '')

            if match_type == 'direct':
                matched_direct += 1
            elif match_type == 'mapped':
                matched_mapped += 1
            elif match_type == 'fuzzy':
                matched_fuzzy += 1
        else:
            not_matched += 1

        results.append(row)

    # 4. 写入CSV
    # 固定fieldnames，确保包含所有字段
    fieldnames = [
        'event_id', 'date', 'category', 'tournament', 'home', 'away',
        'score_home', 'score_away', 'winner',
        'pin_close_h', 'pin_close_d', 'pin_close_a',
        'b365_close_h', 'b365_close_d', 'b365_close_a',
        '1xbet_close_h', '1xbet_close_d', '1xbet_close_a',
        'ou_over', 'ou_line', 'ou_under',
        'ah_home', 'ah_hcp', 'ah_away',
        'btts_yes', 'btts_no',
        'match_type',
        'psh', 'psd', 'psa', 'psch',
        'b365h', 'b365d', 'b365a', 'b365ch',
        'whh', 'bwh', 'iwh',
        'hs', 'as', 'hst', 'ast', 'hc', 'ac', 'hf', 'af',
        'hy', 'ay', 'hr', 'ar',
        'b365_ou25', 'b365_under25',
        'ah_handicap', 'b365_ahh', 'b365_aha', 'ps_ahh', 'ps_aha',
        'hthg', 'htag',
    ]

    print(f"\nWriting {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    # 5. 统计
    total = len(results)
    has_opening = sum(1 for r in results if r.get('psh'))
    has_pin_close = sum(1 for r in results if r.get('pin_close_h'))
    has_b365_close = sum(1 for r in results if r.get('b365_close_h'))
    has_xbet_close = sum(1 for r in results if r.get('1xbet_close_h'))
    has_clv = sum(1 for r in results if r.get('psh') and r.get('pin_close_h'))

    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Total matches: {total:,}")
    print(f"  Matched to CSV: {matched_direct + matched_mapped + matched_fuzzy:,}")
    print(f"    Direct: {matched_direct:,}")
    print(f"    Mapped: {matched_mapped:,}")
    print(f"    Fuzzy: {matched_fuzzy:,}")
    print(f"  Not matched: {not_matched:,}")
    print(f"  Has Pinnacle open (PSH): {has_opening:,}")
    print(f"  Has Pinnacle close: {has_pin_close:,}")
    print(f"  Has Bet365 close: {has_b365_close:,}")
    print(f"  Has 1XBET close: {has_xbet_close:,}")
    print(f"  CLV ready (open+close): {has_clv:,}")
    print(f"  Coverage: {has_opening/total*100:.1f}%")
    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
