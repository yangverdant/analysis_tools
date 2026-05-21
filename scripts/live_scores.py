"""
实时比赛结果爬取
从多个数据源获取今天的实时赛果
"""
import requests
from datetime import datetime
import json

# 禁用代理
NO_PROXY = {'http': None, 'https': None}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def get_today_matches_api_sports():
    """从API-Sports获取今日比赛（需要API Key）"""
    # 免费API: https://api-sports.io
    # 每天100次免费请求
    pass


def get_today_matches_scorebat():
    """从ScoreBat获取今日比赛"""
    url = "https://www.scorebat.com/video-api/v3/"
    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY
        session.headers.update(HEADERS)

        response = session.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data
    except Exception as e:
        print(f"ScoreBat请求失败: {e}")
    return None


def get_today_matches_open_api():
    """使用开放的足球API"""
    # football-data.org 免费API
    url = "https://api.football-data.org/v4/matches"
    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY
        session.headers.update(HEADERS)

        response = session.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
        print(f"HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"API请求失败: {e}")
    return None


def get_today_matches_365scores():
    """从365Scores获取实时比分"""
    url = "https://webws.365scores.com/web/games/fixtures"
    params = {
        'langId': 1,
        'timezoneName': 'Asia/Shanghai',
        'userCountryId': 1,
        'appTypeId': 1,
    }
    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY
        session.headers.update(HEADERS)

        response = session.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"365Scores请求失败: {e}")
    return None


def get_today_matches_thesportsdb():
    """从TheSportsDB获取比赛数据"""
    today = datetime.now().strftime('%Y-%m-%d')
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={today.replace('-','')}&s=Soccer"
    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY
        session.headers.update(HEADERS)

        response = session.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"TheSportsDB请求失败: {e}")
    return None


def main():
    print("=" * 60)
    print(f"实时比赛结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 尝试多个数据源
    print("\n尝试 TheSportsDB...")
    data = get_today_matches_thesportsdb()
    if data:
        print("成功获取数据!")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    else:
        print("失败")

    print("\n尝试 ScoreBat...")
    data = get_today_matches_scorebat()
    if data:
        print("成功获取数据!")
        matches = data.get('response', [])
        print(f"总比赛数: {len(matches)}")

        # 显示最近的比赛
        print("\n最近比赛:")
        for m in matches[:20]:
            if isinstance(m, dict):
                date = m.get('date', 'N/A')[:10]
                title = m.get('title', 'N/A')
                comp = m.get('competition', {})
                if isinstance(comp, dict):
                    comp_name = comp.get('name', 'N/A')
                else:
                    comp_name = str(comp)
                print(f"  {date}: {title} [{comp_name}]")
            else:
                print(f"  {m}")
    else:
        print("失败")


if __name__ == '__main__':
    main()
