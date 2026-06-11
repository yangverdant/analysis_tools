"""
使用Tavily API获取实时足球赛果
"""
import requests
import json
from datetime import datetime

# API配置
TAVILY_API_KEY = "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"
BRAVE_API_KEY = "BSAmkdXRBkbVDqD6mHralmPbYtSY5JH"

NO_PROXY = {'http': None, 'https': None}


def search_tavily(query):
    """使用Tavily搜索"""
    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}"
    }
    data = {
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": False,
        "max_results": 10
    }

    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY

        response = session.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Tavily错误: {response.status_code}")
            print(response.text[:500])
    except Exception as e:
        print(f"Tavily请求失败: {e}")
    return None


def search_brave(query):
    """使用Brave Search API"""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    params = {
        "q": query,
        "count": 10
    }

    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = NO_PROXY

        response = session.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Brave错误: {response.status_code}")
            print(response.text[:500])
    except Exception as e:
        print(f"Brave请求失败: {e}")
    return None


def get_today_football_results():
    """获取今日足球赛果"""
    today = datetime.now().strftime('%Y-%m-%d')
    today_cn = datetime.now().strftime('%Y年%m月%d日')

    queries = [
        f"football soccer results today {today}",
        f"英超 比分 今天 {today_cn}",
        f"Premier League results {today}",
        f"Champions League results May 2026",
        f"足球比赛结果 {today}",
    ]

    all_results = []

    for query in queries:
        print(f"\n搜索: {query}")
        print("-" * 40)

        # 尝试Tavily
        result = search_tavily(query)
        if result:
            answer = result.get('answer', '')
            if answer:
                print(f"Tavily回答: {answer}")
                all_results.append({
                    'source': 'tavily',
                    'query': query,
                    'answer': answer,
                    'results': result.get('results', [])
                })

            # 显示搜索结果
            for r in result.get('results', [])[:5]:
                title = r.get('title', 'N/A').encode('gbk', errors='replace').decode('gbk')
                url = r.get('url', 'N/A')
                content = r.get('content', '')[:100].encode('gbk', errors='replace').decode('gbk')
                print(f"  - {title}")
                print(f"    {url}")
                if content:
                    print(f"    {content}...")
            continue

        # 尝试Brave
        result = search_brave(query)
        if result:
            web_results = result.get('web', {}).get('results', [])
            for r in web_results[:5]:
                title = r.get('title', 'N/A').encode('gbk', errors='replace').decode('gbk')
                url = r.get('url', 'N/A')
                desc = r.get('description', '').encode('gbk', errors='replace').decode('gbk')
                print(f"  - {title}")
                print(f"    {url}")
                if desc:
                    print(f"    {desc[:100]}...")
            all_results.append({
                'source': 'brave',
                'query': query,
                'results': web_results
            })

    return all_results


def main():
    print("=" * 60)
    print(f"实时足球赛果搜索 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = get_today_football_results()

    print("\n" + "=" * 60)
    print("搜索完成")

    # 保存结果
    output_file = "d:/football_tools/data/live_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"结果已保存到: {output_file}")


if __name__ == '__main__':
    main()
