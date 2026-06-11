"""
采集德乙联赛xG数据

数据源尝试顺序:
1. API-Football (含xG统计)
2. Sportmonks (xgfixture端点)
3. FBref爬虫 (备选)
"""

import sqlite3
import json
import time
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DATABASE_PATH = PROJECT_ROOT / "data" / "football_v2.db"

BUNDESLIGA_2_ID = 8

# API配置
API_FOOTBALL_KEY = "bf82d62ee5412d32a95362699389583fdbefa113f4efb371b87b585f12d64443"
SPORTMONKS_TOKEN = "4iBqABzPSz3JX65i166agPqQiliD4f79vD7o2NrJX1OmMBt7wHJ2ttvxdQoq"


class SSLContext:
    """创建不验证SSL的上下文（用于绕过SSL问题）"""
    @staticmethod
    def create():
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def fetch_url(url: str, params: Dict = None, headers: Dict = None, timeout: int = 30) -> Optional[Dict]:
    """获取URL内容（绕过SSL验证）"""
    try:
        # 构建完整URL
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        # 创建请求
        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)

        # 发送请求（使用自定义SSL上下文）
        ctx = SSLContext.create()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_apifootball_xg(league_id: int = 36, season: str = "2024-2025") -> List[Dict]:
    """
    从API-Football获取xG数据

    API-Football的get_events端点返回比赛事件，含xG统计
    """
    print(f"\n尝试API-Football获取德乙xG数据...")

    base_url = "https://apiv3.apifootball.com"

    # 日期范围
    from_date = f"{int(season.split('-')[0])}-08-01"
    to_date = f"{int(season.split('-')[1])}-05-31"

    params = {
        "action": "get_events",
        "league_id": league_id,
        "from": from_date,
        "to": to_date,
        "APIkey": API_FOOTBALL_KEY,
    }

    # 尝试使用requests（设置trust_env=False）
    try:
        import requests
        session = requests.Session()
        session.trust_env = False  # 不使用代理

        response = session.get(base_url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                print(f"  成功获取 {len(data)} 场比赛")
                # 检查xG字段
                match = data[0]
                xg_fields = [k for k in match.keys() if 'xg' in k.lower() or 'x_g' in k.lower()]
                print(f"  xG相关字段: {xg_fields if xg_fields else '未找到'}")
                return data
    except Exception as e:
        print(f"  API-Football请求失败: {e}")

    return []


def fetch_sportmonks_xg(league_id: int = 36) -> List[Dict]:
    """
    从Sportmonks获取xG数据

    Sportmonks的xgfixture端点返回每场比赛的xG统计
    """
    print(f"\n尝试Sportmonks获取德乙xG数据...")

    base_url = "https://api.sportmonks.com/v3/football"

    # 首先获取当前赛季ID
    try:
        import requests
        session = requests.Session()
        session.trust_env = False

        # 获取联赛的当前赛季
        response = session.get(
            f"{base_url}/leagues/{league_id}",
            params={"api_token": SPORTMONKS_TOKEN},
            timeout=30
        )

        if response.status_code == 200:
            league_data = response.json()
            print(f"  联赛信息获取成功")

            # 获取当前赛季的比赛
            if 'data' in league_data:
                season_id = league_data['data'].get('current_season_id')
                if season_id:
                    print(f"  当前赛季ID: {season_id}")

                    # 获取赛季比赛（含xG）
                    response = session.get(
                        f"{base_url}/seasons/{season_id}/fixtures",
                        params={
                            "api_token": SPORTMONKS_TOKEN,
                            "include": "xgfixture;participants;scores"
                        },
                        timeout=60
                    )

                    if response.status_code == 200:
                        fixtures = response.json()
                        if 'data' in fixtures:
                            print(f"  成功获取 {len(fixtures['data'])} 场比赛")
                            return fixtures['data']
        else:
            print(f"  响应错误: {response.status_code}")
    except Exception as e:
        print(f"  Sportmonks请求失败: {e}")

    return []


def update_match_xg(conn, match_id: int, home_xg: float, away_xg: float, source: str = "api") -> bool:
    """更新比赛的xG数据"""
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE matches
            SET home_xg = ?, away_xg = ?, source = COALESCE(source || '+xg', ?)
            WHERE match_id = ?
        ''', (home_xg, away_xg, source, match_id))
        return True
    except Exception as e:
        print(f"  更新失败: {e}")
        return False


def match_xg_to_db(conn, matches: List[Dict], source: str = "apifootball") -> int:
    """将xG数据匹配到数据库"""
    cursor = conn.cursor()
    updated = 0

    for match in matches:
        try:
            # 提取xG数据
            home_xg = None
            away_xg = None

            if source == "apifootball":
                # API-Football字段格式
                home_xg = float(match.get('match_xG_home', 0) or 0)
                away_xg = float(match.get('match_xG_away', 0) or 0)
                match_date = match.get('match_date', '')
                home_team = match.get('match_hometeam_name', '')
                away_team = match.get('match_awayteam_name', '')
                home_score = int(match.get('match_hometeam_score', 0) or 0)
                away_score = int(match.get('match_awayteam_score', 0) or 0)

            elif source == "sportmonks":
                # Sportmonks字段格式
                xg_data = match.get('xgfixture', [])
                for xg in xg_data:
                    if xg.get('type_id') == 5304:  # xG type
                        if xg.get('location') == 'home':
                            home_xg = float(xg.get('value', 0))
                        else:
                            away_xg = float(xg.get('value', 0))

                # 解析比赛信息
                match_date = match.get('starting_at', '')[:10]
                participants = match.get('participants', [])

                if len(participants) >= 2:
                    for p in participants:
                        if p.get('meta', {}).get('location') == 'home':
                            home_team = p.get('name', '')
                        else:
                            away_team = p.get('name', '')

                scores = match.get('scores', [])
                for score in scores:
                    if score.get('type') == 'FT':
                        home_score = score.get('home_score', 0)
                        away_score = score.get('away_score', 0)

            if not home_xg and not away_xg:
                continue

            # 在数据库中查找比赛
            cursor.execute('''
                SELECT m.match_id, m.home_xg, m.away_xg
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                JOIN teams at ON m.away_team_id = at.team_id
                WHERE m.league_id = ?
                AND (ht.name_en LIKE ? OR ht.name_cn LIKE ?)
                AND (at.name_en LIKE ? OR at.name_cn LIKE ?)
                AND m.home_goals = ?
                AND m.away_goals = ?
                AND (m.home_xg IS NULL OR m.home_xg = 0)
                ORDER BY m.match_date DESC
                LIMIT 1
            ''', (BUNDESLIGA_2_ID, f'%{home_team}%', f'%{home_team}%',
                  f'%{away_team}%', f'%{away_team}%', home_score, away_score))

            result = cursor.fetchone()
            if result:
                match_id = result[0]
                if update_match_xg(conn, match_id, home_xg, away_xg, source):
                    updated += 1
                    if updated <= 10:
                        print(f"  更新: {home_team} {home_score}-{away_score} {away_team}, xG: {home_xg:.2f}-{away_xg:.2f}")

        except Exception as e:
            continue

    conn.commit()
    return updated


def generate_sample_xg_data() -> List[Dict]:
    """
    生成示例xG数据（基于统计模型）

    当API不可用时，使用历史统计模型生成近似的xG数据
    """
    print(f"\n生成基于统计模型的xG数据...")

    conn = get_db()
    cursor = conn.cursor()

    # 获取德乙比赛的统计数据
    cursor.execute('''
        SELECT
            m.match_id,
            m.match_date,
            m.home_goals,
            m.away_goals,
            m.home_shots,
            m.away_shots,
            m.home_shots_on,
            m.away_shots_on,
            ht.name_en as home_team,
            at.name_en as away_team
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.league_id = ?
        AND m.home_shots IS NOT NULL
        AND m.home_xg IS NULL
        ORDER BY m.match_date DESC
    ''', (BUNDESLIGA_2_ID,))

    matches = cursor.fetchall()
    print(f"  找到 {len(matches)} 场有射门数据的比赛")

    results = []

    for match in matches:
        # 基于射门数据估算xG
        # 德乙平均xG/射门比约为 0.09-0.11
        home_shots = match[4] or 10
        away_shots = match[5] or 10
        home_shots_on = match[6] or 3
        away_shots_on = match[7] or 3

        # xG估算公式: 射正数 × 0.28 + (射门数-射正数) × 0.06
        home_xg = round(home_shots_on * 0.28 + max(0, home_shots - home_shots_on) * 0.06, 2)
        away_xg = round(away_shots_on * 0.28 + max(0, away_shots - away_shots_on) * 0.06, 2)

        results.append({
            'match_id': match[0],
            'home_team': match[8],
            'away_team': match[9],
            'home_goals': match[2],
            'away_goals': match[3],
            'home_xg': home_xg,
            'away_xg': away_xg,
        })

    conn.close()
    return results


def main():
    """主函数"""
    print("=" * 60)
    print("德乙xG数据采集")
    print("=" * 60)

    conn = get_db()
    cursor = conn.cursor()

    # 检查当前xG数据情况
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_xg IS NOT NULL', (BUNDESLIGA_2_ID,))
    current_xg = cursor.fetchone()[0]
    print(f"\n当前德乙xG数据: {current_xg} 场")

    # 尝试API-Football
    api_matches = fetch_apifootball_xg()
    if api_matches:
        updated = match_xg_to_db(conn, api_matches, "apifootball")
        print(f"API-Football更新: {updated} 场")

    # 尝试Sportmonks
    if len(api_matches) == 0:
        sportmonks_matches = fetch_sportmonks_xg()
        if sportmonks_matches:
            updated = match_xg_to_db(conn, sportmonks_matches, "sportmonks")
            print(f"Sportmonks更新: {updated} 场")

    # 如果API都失败，使用统计模型生成剩余数据
    cursor.execute('''
        SELECT COUNT(*) FROM matches
        WHERE league_id = ?
        AND home_shots IS NOT NULL
        AND home_xg IS NULL
    ''', (BUNDESLIGA_2_ID,))
    remaining = cursor.fetchone()[0]

    if remaining > 0:
        print(f"\n还有 {remaining} 场比赛有射门数据但无xG，使用统计模型生成...")
        sample_data = generate_sample_xg_data()

        if sample_data:
            updated = 0
            for data in sample_data:
                cursor.execute('''
                    UPDATE matches SET home_xg = ?, away_xg = ?, source = 'estimated'
                    WHERE match_id = ? AND home_xg IS NULL
                ''', (data['home_xg'], data['away_xg'], data['match_id']))
                if cursor.rowcount > 0:
                    updated += 1

            conn.commit()
            print(f"统计模型更新: {updated} 场")

            # 显示示例
            print("\n生成xG示例:")
            for data in sample_data[:5]:
                try:
                    print(f"  {data['home_goals']}-{data['away_goals']}, xG: {data['home_xg']:.2f}-{data['away_xg']:.2f}")
                except:
                    pass

    # 最终统计
    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ? AND home_xg IS NOT NULL', (BUNDESLIGA_2_ID,))
    final_xg = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM matches WHERE league_id = ?', (BUNDESLIGA_2_ID,))
    total = cursor.fetchone()[0]

    print("\n" + "=" * 60)
    print("采集结果")
    print("=" * 60)
    print(f"德乙比赛总数: {total}")
    print(f"有xG数据: {final_xg} ({final_xg/total*100:.1f}%)")

    # 按来源统计
    cursor.execute('''
        SELECT source, COUNT(*) as cnt
        FROM matches
        WHERE league_id = ? AND home_xg IS NOT NULL
        GROUP BY source
    ''', (BUNDESLIGA_2_ID,))

    print("\nxG数据来源:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} 场")

    conn.close()
    print("\n采集完成！")


if __name__ == "__main__":
    main()
