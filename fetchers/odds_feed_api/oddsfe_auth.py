"""
oddsfe_auth.py — 自动从 oddsfe.com 获取最新认证headers
每次调用 get_auth() 时从 active.js 拉取，失败则用缓存的fallback
"""

import requests
import re
import time

_CACHE = {
    'schedule_auth': None,
    'event_auth': None,
    'last_fetch': 0,
    'fallback_schedule': {
        '6bc09d2870765cb35436e40a10489f12': 'a46a5f2f1ecc59b0c75d40e04e087ed6',
        'n7R6b9CKPdnd46vK1': '59nfZbY3yIb',
        'bearer': 'SnrsZ0OzuEZvauaA8mq0eXl6Qkq0B7==',
    },
    'fallback_event': {
        '6bc09d2870765cb35436e40a10489f12': 'a46a5f2f1ecc59b0c75d40e04e087ed6',
    },
}

# auth更新间隔（秒），避免频繁请求
AUTH_REFRESH_INTERVAL = 3600  # 1小时


def _fetch_active_js():
    """从oddsfe.com页面获取active.js URL，再获取其内容"""
    s = requests.Session()
    s.trust_env = False

    try:
        # 访问任意schedule页面获取JS文件列表
        r = s.get('https://oddsfe.com/schedule/football/',
                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                  timeout=15)
        if r.status_code != 200:
            return None

        scripts = re.findall(r'<script[^>]+src="([^"]+)"', r.text)

        for sc in scripts:
            if 'active' not in sc:
                continue
            full_url = 'https://oddsfe.com' + sc if sc.startswith('/') else sc
            try:
                r2 = s.get(full_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                if r2.status_code == 200 and r2.text.strip():
                    return r2.text
            except Exception:
                continue

        # 没有active.js，搜索所有chunk JS
        for sc in scripts:
            full_url = 'https://oddsfe.com' + sc if sc.startswith('/') else sc
            try:
                r2 = s.get(full_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                if 'bearer' in r2.text.lower() or re.search(r'[a-f0-9]{32}', r2.text):
                    return r2.text
            except Exception:
                continue

    except Exception:
        pass
    return None


def _parse_auth(js_text):
    """从JS文本中解析auth headers"""
    schedule_auth = {}
    event_auth = {}

    # 找所有 32位hex key-value 对
    pairs = re.findall(r'"([a-f0-9]{32})"\s*:\s*"([a-f0-9]{32}|[a-zA-Z0-9+/=]+)"', js_text)
    for k, v in pairs:
        schedule_auth[k] = v
        event_auth[k] = v

    # 找bearer
    bearers = re.findall(r'"bearer"\s*:\s*"([^"]+)"', js_text, re.I)
    if bearers:
        schedule_auth['bearer'] = bearers[0]

    # 找n7R6b9
    n7 = re.findall(r'"n7R6b9CKPdnd46vK1"\s*:\s*"([^"]+)"', js_text)
    if n7:
        schedule_auth['n7R6b9CKPdnd46vK1'] = n7[0]

    return schedule_auth, event_auth


def _refresh_auth():
    """刷新auth缓存"""
    js_text = _fetch_active_js()
    if js_text:
        schedule_auth, event_auth = _parse_auth(js_text)
        if schedule_auth:
            _CACHE['schedule_auth'] = schedule_auth
            _CACHE['event_auth'] = event_auth
            _CACHE['last_fetch'] = time.time()
            return True

    # 获取失败，用fallback
    if _CACHE['schedule_auth'] is None:
        _CACHE['schedule_auth'] = _CACHE['fallback_schedule']
        _CACHE['event_auth'] = _CACHE['fallback_event']
    return False


def get_schedule_auth():
    """获取schedule API的认证headers，自动刷新"""
    if _CACHE['schedule_auth'] is None or (time.time() - _CACHE['last_fetch'] > AUTH_REFRESH_INTERVAL):
        _refresh_auth()
    return _CACHE['schedule_auth'].copy()


def get_event_auth():
    """获取event详情页的认证headers，自动刷新"""
    if _CACHE['event_auth'] is None or (time.time() - _CACHE['last_fetch'] > AUTH_REFRESH_INTERVAL):
        _refresh_auth()
    return _CACHE['event_auth'].copy()


if __name__ == '__main__':
    print('Testing auth auto-fetch...')
    sa = get_schedule_auth()
    ea = get_event_auth()
    print(f'Schedule auth: {sa}')
    print(f'Event auth: {ea}')

    # 验证
    s = requests.Session()
    s.trust_env = False
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
        'Origin': 'https://oddsfe.com',
        'Referer': 'https://oddsfe.com/schedule/football/2026-05-30',
    }
    headers.update(sa)
    r = s.get('https://oddsfe.com/bind/schedule/football/2026-05-30', headers=headers, timeout=20)
    print(f'\nValidation: status={r.status_code}')
    if r.status_code == 200:
        data = r.json()
        events = sum(len(t.get('events', [])) for t in data)
        print(f'Events: {events}')
