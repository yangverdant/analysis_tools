"""
Okooo - 获取赔率数据

功能:
1. 获取单场比赛基本面(队名、比分)
2. 获取单家公司欧赔变化历史(初盘→终盘)
3. 获取单家公司亚盘变化历史
4. 获取单家公司大小球变化历史
5. 获取一场比赛完整赔率矩阵(多家公司×三种盘口)
6. 计算凯利指数

输出: dict or list of dict, 包含赔率数据

使用示例:
    from fetchers.okooo.get_odds import (
        get_match_basic, get_odds_change, get_ah_change,
        get_ou_change, get_full_odds_matrix
    )

    # 获取比赛基本面
    basic = get_match_basic("12345")

    # 获取Bet365欧赔变化
    odds = get_odds_change("12345", 27)  # 27 = B365

    # 获取完整赔率矩阵
    matrix = get_full_odds_matrix("12345")

    # 批量获取(从match_ids.txt)
    from fetchers.okooo.get_match_ids import get_match_ids_by_league
    ids = get_match_ids_by_league("英超", round_num=38)
    for m in ids:
        matrix = get_full_odds_matrix(m["match_id"])
"""

import re
import csv
import time
import random
import urllib3
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from fetchers.okooo.config import (
    COOKIE, COMPANIES, TARGET_HOURS, TIME_LABELS,
    BASE_URL, URL_MATCH_ODDS, URL_ODDS_CHANGE, URL_AH_CHANGE, URL_OU_CHANGE,
    REQUEST_INTERVAL_MIN, REQUEST_INTERVAL_MAX,
    COMPANY_INTERVAL_MIN, COMPANY_INTERVAL_MAX,
    MATCH_INTERVAL_MIN, MATCH_INTERVAL_MAX,
    MAX_RETRIES
)
from fetchers.common.team_names import normalize_team_name

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _create_session() -> requests.Session:
    """创建带认证的HTTP会话"""
    session = requests.Session()
    session.verify = False
    session.trust_env = False
    import os
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    os.environ['NO_PROXY'] = '*'

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })

    if COOKIE:
        session.headers.update({"Cookie": COOKIE})
    else:
        print("[警告] 未配置Cookie! 请在 config.py 中填入Cookie")

    return session


def warm_up_session(session: requests.Session, match_id: str = None) -> bool:
    """预热会话以绕过WAF

    必须在访问详情页(odds/change/ah/ou)之前调用。
    流程: 主页 → 赔率页 → (可选)AH/OU页

    Args:
        session: HTTP会话
        match_id: 可选,预热后直接跳到某场比赛

    Returns:
        True=预热成功, False=被WAF拦截
    """
    steps = [
        (BASE_URL + "/", f"{BASE_URL}/"),
    ]
    if match_id:
        steps.append((URL_MATCH_ODDS.format(match_id=match_id), f"{BASE_URL}/"))

    for url, referer in steps:
        session.headers.update({"Referer": referer})
        try:
            time.sleep(random.uniform(2.0, 3.5))
            res = session.get(url, timeout=(10, 20), verify=False)
            html = _decode_response(res)
            if _is_waf_blocked(html):
                print(f"  [WAF] 预热失败: {url}")
                return False
        except Exception as e:
            print(f"  [预热错误] {str(e)[:50]}")
            return False

    print("  [预热] 成功")
    return True


def _decode_response(res: requests.Response) -> str:
    """智能解码响应"""
    content_lower = res.content[:2000].lower()
    if b'utf-8' in content_lower or 'utf-8' in res.headers.get('Content-Type', '').lower():
        res.encoding = 'utf-8'
    else:
        res.encoding = 'gb18030'
    return res.text


def _is_waf_blocked(html_text: str) -> bool:
    """检测WAF拦截"""
    waf_keywords = ["验证码", "安全中心", "Forbidden", "Access Denied",
                    "您的访问速度过快", "aliyun_waf"]
    return any(k in html_text for k in waf_keywords) or len(html_text) < 500


def _fetch_page(session: requests.Session, url: str, referer: str = "",
                max_retries: int = None) -> Optional[str]:
    """带重试的页面抓取"""
    retries = max_retries or MAX_RETRIES

    if referer:
        session.headers.update({"Referer": referer})

    for attempt in range(retries):
        try:
            time.sleep(random.uniform(REQUEST_INTERVAL_MIN, REQUEST_INTERVAL_MAX))
            res = session.get(url, timeout=(10, 20), verify=False)
            html_text = _decode_response(res)

            if _is_waf_blocked(html_text):
                print(f"    [WAF] 被拦截 (尝试 {attempt+1}/{retries})")
                print(f"           特征: {html_text[:80].strip()}")
                time.sleep(5.0)
                continue

            return html_text

        except Exception as e:
            print(f"    [网络错误] {str(e)[:50]}")
            time.sleep(8.0)

    print(f"    [跳过] 连续{retries}次失败")
    return None


def _parse_time_to_hours(time_str: str) -> float:
    """将okooo盘口时间标签转为小时数"""
    if "终" in time_str:
        return 0.0
    if "初" in time_str:
        return 9999.0

    m_h = re.search(r'赛前(\d+)(?:小时|时)(?:(\d+)分)?', time_str)
    if m_h:
        hours = int(m_h.group(1))
        minutes = int(m_h.group(2)) if m_h.group(2) else 0
        return hours + (minutes / 60.0)

    m_m = re.search(r'赛前(\d+)分', time_str)
    if m_m:
        return int(m_m.group(1)) / 60.0

    return 0.0


def _parse_change_table(html_text: str) -> List[Dict]:
    """解析盘口变化表格

    Returns:
        [{"h": 48.0, "v": "2.15|3.20|3.05"}, ...]
        h = 赛前小时数, v = 管道符分隔的值
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    rows = soup.find_all('tr')
    data_list = []

    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 5 or "时间" in row.text:
            continue

        t_txt = cols[1].get_text(strip=True)
        if any(k in t_txt for k in ["赛前", "初", "终"]):
            h = _parse_time_to_hours(t_txt)

            v_list = []
            for c in cols[2:5]:
                raw_text = c.get_text(strip=True)
                clean_text = re.sub(r'[↑↓\s]', '', raw_text)
                v_list.append(clean_text)

            if len(v_list) == 3 and all(v for v in v_list):
                data_list.append({"h": h, "v": "|".join(v_list)})

    return data_list


# ==================== 公开接口 ====================

def get_match_basic(match_id: str, session: requests.Session = None) -> Dict:
    """获取比赛基本面(队名、比分)

    Returns:
        {
            "match_id": "12345",
            "home_team": "阿森纳",
            "away_team": "切尔西",
            "home_score": "2",
            "away_score": "1"
        }
    """
    own_session = session is None
    if own_session:
        session = _create_session()

    result = {
        "match_id": match_id,
        "home_team": "N/A",
        "away_team": "N/A",
        "home_score": "N/A",
        "away_score": "N/A"
    }

    url = URL_MATCH_ODDS.format(match_id=match_id)
    html = _fetch_page(session, url, f"{BASE_URL}/")

    if html:
        soup = BeautifulSoup(html, 'html.parser')

        teams = soup.find_all('div', class_=re.compile(r'jsTeamName'))
        if len(teams) >= 2:
            result['home_team'] = re.sub(r'[【】\[\]]', '', teams[0].get_text(strip=True))
            result['away_team'] = re.sub(r'[【】\[\]]', '', teams[1].get_text(strip=True))

        vs_div = soup.find('div', class_='vs')
        if vs_div:
            scores = [t.strip() for t in vs_div.stripped_strings if t.strip().isdigit()]
            if len(scores) >= 2:
                result['home_score'] = scores[0]
                result['away_score'] = scores[1]

    return result


def get_odds_change(match_id: str, company_id: int,
                    session: requests.Session = None) -> Optional[List[Dict]]:
    """获取欧赔变化历史

    Args:
        match_id: okooo比赛ID
        company_id: 博彩公司ID (如 B365=27, WH=14)
        session: 复用会话

    Returns:
        [{"h": 48.0, "v": "2.15|3.20|3.05", "time_label": "48h"}, ...]
        v = 主胜|平|客胜
        None = 抓取失败, [] = 机构未开盘
    """
    own_session = session is None
    if own_session:
        session = _create_session()
        warm_up_session(session, match_id)

    url = URL_ODDS_CHANGE.format(match_id=match_id, company_id=company_id)
    referer = URL_MATCH_ODDS.format(match_id=match_id)
    html = _fetch_page(session, url, referer)

    if not html:
        return None

    data = _parse_change_table(html)

    if not data:
        none_keywords = ["盘口变化表", "更新", "暂无数据", "没有相关记录"]
        if any(k in html for k in none_keywords):
            return []  # 机构未开盘
        return None  # 结构异常

    # 添加时间标签 + 串联字段
    for item in data:
        item["time_label"] = _hours_to_label(item["h"])
        item["match_id"] = match_id
        item["company_id"] = company_id

    return data


def get_ah_change(match_id: str, company_id: int,
                  session: requests.Session = None) -> Optional[List[Dict]]:
    """获取亚盘变化历史

    Returns:
        [{"h": 48.0, "v": "0.85|0.5|1.05", "time_label": "48h"}, ...]
        v = 主队水位|让球数|客队水位
        None = 抓取失败, [] = 机构未开盘
    """
    own_session = session is None
    if own_session:
        session = _create_session()
        warm_up_session(session, match_id)

    url = URL_AH_CHANGE.format(match_id=match_id, company_id=company_id)
    referer = URL_MATCH_ODDS.format(match_id=match_id)
    html = _fetch_page(session, url, referer)

    if not html:
        return None

    data = _parse_change_table(html)

    if not data:
        none_keywords = ["盘口变化表", "更新", "暂无数据", "没有相关记录"]
        if any(k in html for k in none_keywords):
            return []
        return None

    for item in data:
        item["time_label"] = _hours_to_label(item["h"])
        item["match_id"] = match_id
        item["company_id"] = company_id

    return data


def get_ou_change(match_id: str, company_id: int,
                  session: requests.Session = None) -> Optional[List[Dict]]:
    """获取大小球变化历史

    Returns:
        [{"h": 48.0, "v": "0.90|2.5|0.95", "time_label": "48h"}, ...]
        v = 大球水位|盘口线|小球水位
        None = 抓取失败, [] = 机构未开盘
    """
    own_session = session is None
    if own_session:
        session = _create_session()
        warm_up_session(session, match_id)

    url = URL_OU_CHANGE.format(match_id=match_id, company_id=company_id)
    referer = URL_MATCH_ODDS.format(match_id=match_id)
    html = _fetch_page(session, url, referer)

    if not html:
        return None

    data = _parse_change_table(html)

    if not data:
        none_keywords = ["盘口变化表", "更新", "暂无数据", "没有相关记录"]
        if any(k in html for k in none_keywords):
            return []
        return None

    for item in data:
        item["time_label"] = _hours_to_label(item["h"])
        item["match_id"] = match_id
        item["company_id"] = company_id

    return data


def get_full_odds_matrix(match_id: str) -> Dict:
    """获取一场比赛的完整赔率矩阵

    遍历所有公司 × 三种盘口, 获取变化历史并按时间节点映射

    Returns:
        {
            "match_id": "12345",
            "home_team": "阿森纳",
            "away_team": "切尔西",
            "home_score": "2",
            "away_score": "1",
            "odds": {
                "WH": {
                    "odds":      {"opening": "2.15|3.20|3.05", "closing": "...", "48h": "...", ...},
                    "ah":        {"opening": "0.85|0.5|1.05", ...},
                    "overunder": {"opening": "0.90|2.5|0.95", ...}
                },
                "B365": { ... },
                ...
            }
        }
    """
    session = _create_session()
    warm_up_session(session, match_id)

    # 获取基本面
    basic = get_match_basic(match_id, session)
    result = {
        "match_id": match_id,
        "home_team": basic["home_team"],
        "away_team": basic["away_team"],
        "home_score": basic["home_score"],
        "away_score": basic["away_score"],
        "odds": {}
    }

    print(f"[okooo] 抓取比赛 {match_id}: {basic['home_team']} vs {basic['away_team']}")

    time.sleep(random.uniform(1.5, 2.5))

    for c_name, c_id in COMPANIES.items():
        print(f"  -> 机构: {c_name}")
        result["odds"][c_name] = {}

        for m_type, fetch_fn in [("odds", get_odds_change), ("ah", get_ah_change), ("overunder", get_ou_change)]:
            raw_data = fetch_fn(match_id, c_id, session)

            if raw_data:
                time_map = _build_time_map(raw_data)
                result["odds"][c_name][m_type] = time_map
            elif raw_data is None:
                result["odds"][c_name][m_type] = "FETCH_FAILED"
            else:
                result["odds"][c_name][m_type] = "NO_DATA"

            # 盘口间休眠
            time.sleep(random.uniform(1.0, 2.0))

        # 公司间休眠
        company_sleep = random.uniform(COMPANY_INTERVAL_MIN, COMPANY_INTERVAL_MAX)
        print(f"     机构间隙休眠 {company_sleep:.1f}s")
        time.sleep(company_sleep)

    return result


def calc_kelly_index(odds_home: float, odds_draw: float, odds_away: float,
                     prob_home: float, prob_draw: float, prob_away: float,
                     return_rate: float = None) -> Dict:
    """计算凯利指数

    凯利指数 = (赔率 × 概率 - 1) / (赔率 - 1)
    凯利指数>1 表示博彩公司对该结果持怀疑态度
    凯利指数<1 表示博彩公司认可该概率

    Args:
        odds_home/draw/away: 主胜/平/客胜赔率
        prob_home/draw/away: 主胜/平/客胜概率 (0-1)
        return_rate: 返还率, 如果不提供则从赔率计算

    Returns:
        {"kelly_home": 0.95, "kelly_draw": 1.02, "kelly_away": 0.98,
         "return_rate": 0.92}
    """
    if return_rate is None:
        return_rate = 1.0 / (1.0/odds_home + 1.0/odds_draw + 1.0/odds_away)

    kelly_home = (odds_home * prob_home - 1) / (odds_home - 1) if odds_home > 1 else 0
    kelly_draw = (odds_draw * prob_draw - 1) / (odds_draw - 1) if odds_draw > 1 else 0
    kelly_away = (odds_away * prob_away - 1) / (odds_away - 1) if odds_away > 1 else 0

    return {
        "kelly_home": round(kelly_home, 4),
        "kelly_draw": round(kelly_draw, 4),
        "kelly_away": round(kelly_away, 4),
        "return_rate": round(return_rate, 4),
    }


def calc_kelly_from_odds(odds_home: float, odds_draw: float, odds_away: float) -> Dict:
    """从欧赔直接计算凯利指数 (假设隐含概率=返还率/赔率)

    Args:
        odds_home/draw/away: 主胜/平/客胜赔率

    Returns:
        {"kelly_home": ..., "kelly_draw": ..., "kelly_away": ...,
         "return_rate": ..., "prob_home": ..., "prob_draw": ..., "prob_away": ...}
    """
    return_rate = 1.0 / (1.0/odds_home + 1.0/odds_draw + 1.0/odds_away)

    prob_home = return_rate / odds_home
    prob_draw = return_rate / odds_draw
    prob_away = return_rate / odds_away

    result = calc_kelly_index(odds_home, odds_draw, odds_away,
                              prob_home, prob_draw, prob_away, return_rate)
    result["prob_home"] = round(prob_home, 4)
    result["prob_draw"] = round(prob_draw, 4)
    result["prob_away"] = round(prob_away, 4)

    return result


def batch_fetch_to_csv(match_ids: List[str], output_path: str) -> str:
    """批量抓取赔率并保存到CSV

    每场比赛一行, 列 = match_id + home_team + away_team + home_score + away_score
    + {公司}_{盘口}_{时间节点} 的矩阵格式

    Args:
        match_ids: 比赛ID列表
        output_path: CSV输出路径

    Returns:
        保存的文件路径
    """
    # 构建表头
    fieldnames = ["match_id", "home_team", "away_team", "home_score", "away_score"]
    for cn in COMPANIES.keys():
        for mt in ["odds", "ah", "overunder"]:
            for tl in TIME_LABELS:
                fieldnames.append(f"{cn}_{mt}_{tl}")

    file_exists = False
    import os
    if os.path.isfile(output_path):
        file_exists = True

    with open(output_path, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for index, match_id in enumerate(match_ids):
            print(f"\n--- 进度: {index+1}/{len(match_ids)} ---")

            try:
                matrix = get_full_odds_matrix(match_id)

                row = {
                    "match_id": matrix["match_id"],
                    "home_team": matrix["home_team"],
                    "away_team": matrix["away_team"],
                    "home_score": matrix["home_score"],
                    "away_score": matrix["away_score"],
                }

                for c_name, c_data in matrix["odds"].items():
                    for m_type, time_map in c_data.items():
                        prefix = f"{c_name}_{m_type}"
                        for tl in TIME_LABELS:
                            row[f"{prefix}_{tl}"] = time_map.get(tl, "N/A")

                writer.writerow(row)
                print(f"[成功] {match_id} 数据已写入")

            except Exception as e:
                print(f"[错误] 比赛 {match_id}: {e}")

            # 比赛间休眠
            sleep_time = random.uniform(MATCH_INTERVAL_MIN, MATCH_INTERVAL_MAX)
            print(f"[休眠] {sleep_time:.1f}s...")
            time.sleep(sleep_time)

    print(f"\n[完成] 数据已保存到 {output_path}")
    return output_path


# ==================== 内部辅助 ====================

def _hours_to_label(hours: float) -> str:
    """小时数转时间标签"""
    if hours == 0.0:
        return "closing"
    if hours >= 9999.0:
        return "opening"
    if hours == int(hours):
        return f"{int(hours)}h"
    return f"{hours}h"


def _build_time_map(raw_data: List[Dict]) -> Dict[str, str]:
    """将盘口变化数据按时间节点映射

    Args:
        raw_data: [{"h": 48.0, "v": "2.15|3.20|3.05", "time_label": "48h"}, ...]
                  按h降序排列 (closing在前, opening在后)

    Returns:
        {"opening": "2.15|3.20|3.05", "closing": "2.10|3.25|3.10",
         "48h": "2.12|3.22|3.08", ...}
    """
    time_map = {}

    if not raw_data:
        return time_map

    # closing = 列表第一个 (最接近开赛)
    time_map["closing"] = raw_data[0]["v"]
    # opening = 列表最后一个 (最远离开赛)
    time_map["opening"] = raw_data[-1]["v"]

    # 按时间节点映射: 找到 >= target_hours 的最新记录
    for target in TARGET_HOURS:
        val = "N/A"
        for item in reversed(raw_data):
            if item["h"] >= target:
                val = item["v"]
            else:
                break
        str_target = f"{int(target)}h" if target == int(target) else f"{target}h"
        time_map[str_target] = val

    return time_map


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m fetchers.okooo.get_odds basic 12345")
        print("  python -m fetchers.okooo.get_odds odds 12345 27")
        print("  python -m fetchers.okooo.get_odds ah 12345 27")
        print("  python -m fetchers.okooo.get_odds ou 12345 27")
        print("  python -m fetchers.okooo.get_odds matrix 12345")
        print("  python -m fetchers.okooo.get_odds batch match_ids.txt output.csv")
        print("  python -m fetchers.okooo.get_odds kelly 2.15 3.20 3.05")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "basic":
        match_id = sys.argv[2]
        result = get_match_basic(match_id)
        print(f"  {result['home_team']} {result['home_score']}-{result['away_score']} {result['away_team']}")

    elif cmd == "odds":
        match_id = sys.argv[2]
        company_id = int(sys.argv[3])
        data = get_odds_change(match_id, company_id)
        if data:
            for item in data:
                print(f"  {item['time_label']:8s} h={item['h']:6.1f}  {item['v']}")
        else:
            print("  无数据")

    elif cmd == "ah":
        match_id = sys.argv[2]
        company_id = int(sys.argv[3])
        data = get_ah_change(match_id, company_id)
        if data:
            for item in data:
                print(f"  {item['time_label']:8s} h={item['h']:6.1f}  {item['v']}")
        else:
            print("  无数据")

    elif cmd == "ou":
        match_id = sys.argv[2]
        company_id = int(sys.argv[3])
        data = get_ou_change(match_id, company_id)
        if data:
            for item in data:
                print(f"  {item['time_label']:8s} h={item['h']:6.1f}  {item['v']}")
        else:
            print("  无数据")

    elif cmd == "matrix":
        match_id = sys.argv[2]
        import json
        result = get_full_odds_matrix(match_id)
        # 简化输出
        print(f"  {result['home_team']} vs {result['away_team']}")
        for c_name, c_data in result["odds"].items():
            for m_type, time_map in c_data.items():
                if isinstance(time_map, dict):
                    print(f"    {c_name}/{m_type}: 开盘={time_map.get('opening','?')} 终盘={time_map.get('closing','?')}")
                else:
                    print(f"    {c_name}/{m_type}: {time_map}")

    elif cmd == "batch":
        input_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else "odds_output.csv"
        with open(input_file, 'r', encoding='utf-8') as f:
            ids = [line.strip() for line in f if line.strip()]
        batch_fetch_to_csv(ids, output_file)

    elif cmd == "kelly":
        h = float(sys.argv[2])
        d = float(sys.argv[3])
        a = float(sys.argv[4])
        result = calc_kelly_from_odds(h, d, a)
        print(f"  返还率: {result['return_rate']}")
        print(f"  隐含概率: 主{result['prob_home']} 平{result['prob_draw']} 客{result['prob_away']}")
        print(f"  凯利指数: 主{result['kelly_home']} 平{result['kelly_draw']} 客{result['kelly_away']}")
