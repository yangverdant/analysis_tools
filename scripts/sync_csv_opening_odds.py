"""CSV开盘赔率同步 — 将football-data.co.uk的Pinnacle开盘价写入lottery_odds

数据流:
  unified_football.db.match_data (source='football-data-co-uk')
  → 解析Pinnacle赔率(PSH/PSD/PSA) + B365(B365H/B365D/B365A) + Average(AvgH/AvgD/AvgA)
  → 匹配football_v2.db的lottery_matches(通过队名+日期)
  → 写入lottery_odds(snapshot_type='opening', source='csv_pinnacle')

用途:
1. 为CLV赔率对比提供开盘基线
2. 为validate提供赔率基线(对比模型vs赔率方向)
3. 补充lottery_odds中缺失的opening赔率
"""
import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def sync_csv_opening_odds(football_v2_path: str = None,
                          unified_path: str = None,
                          overwrite: bool = False) -> dict:
    """同步CSV开盘赔率到lottery_odds

    Args:
        football_v2_path: football_v2.db路径
        unified_path: unified_football.db路径
        overwrite: 是否覆盖已存在的opening赔率
    """
    if not football_v2_path:
        football_v2_path = str(Path(__file__).parent.parent / 'data' / 'football_v2.db')
    if not unified_path:
        unified_path = str(Path(football_v2_path).parent / 'unified_football.db')

    if not Path(unified_path).exists():
        return {'status': 'skipped', 'reason': 'no unified db'}

    def _normalize(name: str) -> str:
        """归一化队名 — 移除所有常见后缀(循环移除)"""
        n = name.strip().lower()
        suffixes = [' fc', ' cf', ' sc', ' afc', ' united', ' city',
                     ' hotspur', ' athletic', ' county', ' town',
                     ' rovers', ' villa', ' albion', ' forest', ' palace',
                     ' rangers', ' celtic', ' wanderers', ' and hove']
        changed = True
        while changed:
            changed = False
            for suffix in suffixes:
                if n.endswith(suffix):
                    n = n[:-len(suffix)]
                    changed = True
        return n.strip()

    # 加载中英队名映射
    cn_to_en = {}
    linkage_dir = str(Path(football_v2_path).parent / 'linkage')
    cn_file = str(Path(linkage_dir) / 'team_chinese_names.json')
    try:
        with open(cn_file, 'r', encoding='utf-8') as f:
            en_to_cn = json.load(f)
            cn_to_en = {v: k for k, v in en_to_cn.items()}
    except Exception:
        pass

    try:
        # 读取unified_football.db中的CSV赔率
        src = sqlite3.connect(unified_path, timeout=30)
        csv_odds = {}  # (norm_home, norm_away, date) → odds_data
        count = 0

        for row in src.execute("""
            SELECT data_json FROM match_data
            WHERE source = 'football-data-co-uk' AND data_type = 'odds'
        """):
            try:
                data = json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                continue

            home = data.get('home_team', '')
            away = data.get('away_team', '')
            match_date = data.get('date', '')

            if not home or not away or not match_date:
                continue

            # 提取Pinnacle开盘赔率
            ps_h = data.get('pinnacle_home_win')
            ps_d = data.get('pinnacle_draw')
            ps_a = data.get('pinnacle_away_win')

            # Pinnacle优先, B365其次, Average最后
            h = ps_h or data.get('b365_home_win') or data.get('avg_home_win') or data.get('home_win')
            d = ps_d or data.get('b365_draw') or data.get('avg_draw') or data.get('draw')
            a = ps_a or data.get('b365_away_win') or data.get('avg_away_win') or data.get('away_win')

            if not h or not d or not a:
                continue

            try:
                h, d, a = float(h), float(d), float(a)
            except (ValueError, TypeError):
                continue

            if h < 1.01 or d < 1.01 or a < 1.01:
                continue

            norm_h = _normalize(home)
            norm_a = _normalize(away)
            key = (norm_h, norm_a, match_date)

            # 同时存储Pinnacle收盘价(如果有)
            closing = None
            ch = data.get('closing_avg_home_win')
            cd = data.get('closing_avg_draw')
            ca = data.get('closing_avg_away_win')
            if ch and cd and ca:
                try:
                    closing = {'3': float(ch), '1': float(cd), '0': float(ca)}
                except (ValueError, TypeError):
                    pass

            # 只保留Pinnacle数据(避免覆盖Pinnacle赔率)
            if key not in csv_odds or ps_h:
                odds_data = {'3': h, '1': d, '0': a}
                if ps_h:
                    odds_data['bookmaker'] = 'Pinnacle'
                elif data.get('b365_home_win'):
                    odds_data['bookmaker'] = 'Bet365'
                else:
                    odds_data['bookmaker'] = 'Average'

                csv_odds[key] = {
                    'opening': odds_data,
                    'closing': closing,
                    'home_team': home,
                    'away_team': away,
                    'date': match_date,
                }
                count += 1

        src.close()
        logger.info(f'Loaded {count} CSV odds records, {len(csv_odds)} unique matches')

        # 匹配到football_v2.db的lottery_matches
        dst = sqlite3.connect(football_v2_path, timeout=10)
        dst.row_factory = sqlite3.Row
        cursor = dst.cursor()

        # 找出缺少opening赔率的lottery_matches
        if overwrite:
            cursor.execute("""
                SELECT lm.lottery_match_id, lm.match_date,
                       lm.home_team_cn, lm.away_team_cn,
                       ht.name_en as home_en, at.name_en as away_en
                FROM lottery_matches lm
                LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
                LEFT JOIN teams at ON lm.away_team_id = at.team_id
            """)
        else:
            cursor.execute("""
                SELECT lm.lottery_match_id, lm.match_date,
                       lm.home_team_cn, lm.away_team_cn,
                       ht.name_en as home_en, at.name_en as away_en
                FROM lottery_matches lm
                LEFT JOIN teams ht ON lm.home_team_id = ht.team_id
                LEFT JOIN teams at ON lm.away_team_id = at.team_id
                WHERE lm.lottery_match_id NOT IN (
                    SELECT DISTINCT lottery_match_id FROM lottery_odds
                    WHERE play_type = 'spf' AND snapshot_type = 'opening'
                )
            """)

        missing = [dict(r) for r in cursor.fetchall()]

        synced_opening = 0
        synced_closing = 0

        for lm in missing:
            home_en = lm.get('home_en')
            away_en = lm.get('away_en')

            if not home_en and lm['home_team_cn'] in cn_to_en:
                home_en = cn_to_en[lm['home_team_cn']]
            if not away_en and lm['away_team_cn'] in cn_to_en:
                away_en = cn_to_en[lm['away_team_cn']]

            if not home_en or not away_en:
                continue

            match_date = lm['match_date']

            # 尝试匹配(含±3天窗口)
            odds_info = None
            for day_offset in range(-3, 4):
                from datetime import timedelta, date as date_cls
                try:
                    d = date_cls.fromisoformat(match_date) + timedelta(days=day_offset)
                except ValueError:
                    continue
                d_str = str(d)

                key1 = (_normalize(home_en), _normalize(away_en), d_str)
                if key1 in csv_odds:
                    odds_info = csv_odds[key1]
                    break

            if not odds_info:
                continue

            lm_id = lm['lottery_match_id']

            # 写入opening赔率
            opening_data = odds_info['opening']
            opening_data['source'] = 'csv_pinnacle'
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO lottery_odds
                    (lottery_match_id, play_type, snapshot_type, odds_data, opening_odds, created_at)
                    VALUES (?, 'spf', 'opening', ?, ?, datetime('now'))
                """, (lm_id, json.dumps(opening_data, ensure_ascii=False),
                      json.dumps(opening_data, ensure_ascii=False)))
                if cursor.rowcount > 0:
                    synced_opening += 1
            except Exception as e:
                logger.debug(f'开盘赔率写入失败 {lm_id}: {e}')

            # 写入closing赔率(如果有)
            closing_data = odds_info.get('closing')
            if closing_data:
                closing_data['source'] = 'csv_avg'
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO lottery_odds
                        (lottery_match_id, play_type, snapshot_type, odds_data, latest_odds, created_at)
                        VALUES (?, 'spf', 'closing', ?, ?, datetime('now'))
                    """, (lm_id, json.dumps(closing_data, ensure_ascii=False),
                          json.dumps(closing_data, ensure_ascii=False)))
                    if cursor.rowcount > 0:
                        synced_closing += 1
                except Exception as e:
                    logger.debug(f'收盘赔率写入失败 {lm_id}: {e}')

        dst.commit()

        # 也写入match_odds_normalized(用于赔率分析)
        synced_normalized = 0
        for lm in missing:
            home_en = lm.get('home_en')
            away_en = lm.get('away_en')
            if not home_en and lm['home_team_cn'] in cn_to_en:
                home_en = cn_to_en[lm['home_team_cn']]
            if not away_en and lm['away_team_cn'] in cn_to_en:
                away_en = cn_to_en[lm['away_team_cn']]
            if not home_en or not away_en:
                continue

            match_date = lm['match_date']
            odds_info = None
            for day_offset in range(-3, 4):
                from datetime import timedelta, date as date_cls
                try:
                    d = date_cls.fromisoformat(match_date) + timedelta(days=day_offset)
                except ValueError:
                    continue
                if (_normalize(home_en), _normalize(away_en), str(d)) in csv_odds:
                    odds_info = csv_odds[(_normalize(home_en), _normalize(away_en), str(d))]
                    break

            if not odds_info:
                continue

            opening = odds_info['opening']
            bk = opening.get('bookmaker', 'Pinnacle')

            try:
                # Check if match exists in matches table
                match_id = dst.execute("""
                    SELECT match_id FROM matches
                    WHERE match_date = ? AND home_team_id IN (
                        SELECT team_id FROM teams WHERE name_en = ?
                    ) AND away_team_id IN (
                        SELECT team_id FROM teams WHERE name_en = ?
                    )
                    LIMIT 1
                """, (match_date, home_en, away_en)).fetchone()

                if match_id:
                    mid = match_id[0]
                    dst.execute("""
                        INSERT OR IGNORE INTO match_odds_normalized
                        (match_id, bookmaker, snapshot_type, market, home, draw, away, captured_at, source)
                        VALUES (?, ?, 'prematch', '1X2', ?, ?, ?, ?, 'csv_sync')
                    """, (
                        mid, bk,
                        opening['3'], opening['1'], opening['0'],
                        match_date,
                    ))
                    synced_normalized += 1
            except Exception as e:
                logger.debug(f'Normalized赔率写入失败: {e}')

        dst.commit()
        dst.close()

        result = {
            'status': 'ok',
            'csv_odds_loaded': len(csv_odds),
            'opening_synced': synced_opening,
            'closing_synced': synced_closing,
            'normalized_synced': synced_normalized,
        }
        logger.info(f'CSV开盘赔率同步: {result}')
        return result

    except Exception as e:
        logger.error(f'CSV开盘赔率同步失败: {e}')
        return {'status': 'error', 'error': str(e)}


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)

    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    result = sync_csv_opening_odds(football_v2_path=db_path)
    print(f'同步结果: {result}')
