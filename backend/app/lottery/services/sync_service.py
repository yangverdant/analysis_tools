"""
数据同步服务 - 串联爬虫、ETL、DAO、oddsfe桥接

完整流程:
1. 调用爬虫获取数据 (sporttery)
2. EntityMapper 进行字段转换和球队映射
3. 处理层: handicap_line提取、赔率opening快照标记
4. DAO 层入库 (比赛 + 赔率)
5. oddsfe桥接: 匹配event_id、写入beijing_time(UTC+8)、自动学习CN→EN映射
6. 开奖结果入库 (去重 + oddsfe补BQC)
"""

from typing import Dict, List, Optional
import logging
import sqlite3
import json
import os
import re
import time
import unicodedata
from datetime import datetime, date, timedelta

from ..data_sources.scrapers.lottery_crawler import LotteryCrawlerSync
from ..etl.entity_mapper import EntityMapper
from ..dao.lottery_dao import LotteryMatchDAO, LotteryOddsDAO

logger = logging.getLogger(__name__)

# === 路径常量 ===
_DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'football_v2.db')
_CN_EN_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'linkage', 'team_chinese_names.json')


def _norm_team(name: str) -> str:
    """队名标准化: 去变音符号→小写→去后缀"""
    n = (name or '').strip().lower()
    n = unicodedata.normalize('NFKD', n)
    n = ''.join(c for c in n if not unicodedata.combining(c))
    special = {'ø': 'o', 'å': 'a', 'æ': 'ae', 'ß': 'ss', 'đ': 'd', 'ł': 'l', 'ń': 'n', 'ś': 's',
               'ź': 'z', 'ż': 'z', 'ç': 'c', 'ğ': 'g', 'ı': 'i', 'š': 's', 'č': 'c', 'ř': 'r',
               'ž': 'z', 'ů': 'u', 'ý': 'y', 'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a',
               'á': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'ó': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o',
               'ú': 'u', 'û': 'u', 'ü': 'u', 'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i'}
    n = ''.join(special.get(c, c) for c in n)
    for sfx in [' fc', ' cf', ' sc', ' afc', ' united', ' city', ' hotspur', ' athletic',
                ' county', ' town', ' rovers', ' villa', ' albion', ' forest', ' palace',
                ' rangers', ' celtic', ' wanderers', ' and hove']:
        while n.endswith(sfx):
            n = n[:-len(sfx)]
    return n.strip()


def _load_cn_to_en() -> Dict[str, str]:
    """加载CN→EN队名映射"""
    try:
        with open(_CN_EN_PATH, encoding='utf-8') as f:
            en_to_cn = json.load(f)
        cn_to_en = {v: k for k, v in en_to_cn.items()}
        # 手动补充常见缺失
        cn_to_en.update({
            '尤文': 'Juventus', '斯托克港': 'Stockport County',
            '热刺': 'Tottenham', '哥德堡': 'IFK Goteborg',
            '博尔顿': 'Bolton', 'IFK哥德堡': 'IFK Goteborg',
            '曼联': 'Manchester United', '曼城': 'Manchester City',
            '利物浦': 'Liverpool', '阿森纳': 'Arsenal',
            '切尔西': 'Chelsea', '莱斯特城': 'Leicester City',
            '布莱顿': 'Brighton', '纽卡斯尔': 'Newcastle United',
            '西汉姆': 'West Ham United', '阿斯顿维拉': 'Aston Villa',
            '水晶宫': 'Crystal Palace', '诺丁汉森林': 'Nottingham Forest',
            '布伦特福德': 'Brentford', '富勒姆': 'Fulham',
            '伯恩茅斯': 'Bournemouth', '狼队': 'Wolverhampton',
            '埃弗顿': 'Everton', '托特纳姆': 'Tottenham',
            '巴塞罗那': 'Barcelona', '皇家马德里': 'Real Madrid',
            '马德里竞技': 'Atletico Madrid', '拜仁': 'Bayern Munich',
            '多特蒙德': 'Borussia Dortmund', '巴黎圣日耳曼': 'Paris Saint Germain',
            '国际米兰': 'Inter', 'AC米兰': 'AC Milan',
            '尤文图斯': 'Juventus', '那不勒斯': 'Napoli',
            '罗马': 'Roma', '拉齐奥': 'Lazio',
            '葡萄牙': 'Portugal', '西班牙': 'Spain',
            '法国': 'France', '英格兰': 'England',
            '德国': 'Germany', '意大利': 'Italy',
            '荷兰': 'Netherlands', '巴西': 'Brazil',
            '阿根廷': 'Argentina', '日本': 'Japan',
            '韩国': 'South Korea', '澳大利亚': 'Australia',
            '中国': 'China', '比利时': 'Belgium',
            '瑞士': 'Switzerland', '奥地利': 'Austria',
            '丹麦': 'Denmark', '瑞典': 'Sweden',
            '挪威': 'Norway', '芬兰': 'Finland',
            '波兰': 'Poland', '捷克': 'Czech Republic',
            '土耳其': 'Turkey', '俄罗斯': 'Russia',
            '乌克兰': 'Ukraine', '克罗地亚': 'Croatia',
            '塞尔维亚': 'Serbia', '威尔士': 'Wales',
            '苏格兰': 'Scotland', '爱尔兰': 'Ireland',
            '北爱尔兰': 'Northern Ireland', '冰岛': 'Iceland',
            '斯洛伐克': 'Slovakia', '匈牙利': 'Hungary',
            '希腊': 'Greece', '罗马尼亚': 'Romania',
            '保加利亚': 'Bulgaria', '斯洛文尼亚': 'Slovenia',
            '哥伦比亚': 'Colombia', '智利': 'Chile',
            '乌拉圭': 'Uruguay', '巴拉圭': 'Paraguay',
            '厄瓜多尔': 'Ecuador', '秘鲁': 'Peru',
            '委内瑞拉': 'Venezuela', '玻利维亚': 'Bolivia',
            '墨西哥': 'Mexico', '美国': 'USA',
            '加拿大': 'Canada', '哥斯达黎加': 'Costa Rica',
            '巴拿马': 'Panama', '牙买加': 'Jamaica',
            '洪都拉斯': 'Honduras', '特立尼达和多巴哥': 'Trinidad and Tobago',
            '埃及': 'Egypt', '尼日利亚': 'Nigeria',
            '喀麦隆': 'Cameroon', '加纳': 'Ghana',
            '科特迪瓦': 'Ivory Coast', '塞内加尔': 'Senegal',
            '摩洛哥': 'Morocco', '突尼斯': 'Tunisia',
            '阿尔及利亚': 'Algeria', '南非': 'South Africa',
            '民主刚果': 'DR Congo', '安哥拉': 'Angola',
            '马里': 'Mali', '布基纳法索': 'Burkina Faso',
            '几内亚': 'Guinea', '赞比亚': 'Zambia',
            '沙特': 'Saudi Arabia', '伊朗': 'Iran',
            '伊拉克': 'Iraq', '阿曼': 'Oman',
            '阿联酋': 'United Arab Emirates', '卡塔尔': 'Qatar',
            '乌兹别克斯坦': 'Uzbekistan', '约旦': 'Jordan',
            '巴勒斯坦': 'Palestine', '叙利亚': 'Syria',
            '黎巴嫩': 'Lebanon', '巴林': 'Bahrain',
            '科威特': 'Kuwait', '朝鲜': 'North Korea',
            '泰国': 'Thailand', '越南': 'Vietnam',
            '马来西亚': 'Malaysia', '印度尼西亚': 'Indonesia',
            '菲律宾': 'Philippines', '缅甸': 'Myanmar',
            '新加坡': 'Singapore', '印度': 'India',
            '新西兰': 'New Zealand', '斐济': 'Fiji',
        })
        return cn_to_en
    except Exception as e:
        logger.warning(f'Failed to load CN→EN mapping: {e}')
        return {}


def _save_cn_en_mapping(cn_name: str, en_name: str):
    """自动学习: 将新的CN→EN映射写回team_chinese_names.json"""
    try:
        with open(_CN_EN_PATH, encoding='utf-8') as f:
            en_to_cn = json.load(f)

        # en_name已存在且cn一致 → 无需更新
        if en_name in en_to_cn and en_to_cn[en_name] == cn_name:
            return

        # 写入新映射
        en_to_cn[en_name] = cn_name
        with open(_CN_EN_PATH, 'w', encoding='utf-8') as f:
            json.dump(en_to_cn, f, ensure_ascii=False, indent=2)

        logger.info(f'Auto-learned CN→EN: {cn_name} -> {en_name}')
    except Exception as e:
        logger.debug(f'Failed to save CN→EN mapping: {e}')


def _oddsfe_get_auth() -> dict:
    """获取oddsfe认证headers"""
    try:
        sys_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'fetchers', 'odds_feed_api')
        sys_path = os.path.normpath(sys_path)
        import sys
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from oddsfe_auth import get_schedule_auth
        return get_schedule_auth()
    except Exception as e:
        logger.warning(f'Failed to get oddsfe auth: {e}')
        return {}


def _oddsfe_fetch_schedule(date_str: str) -> list:
    """调用oddsfe schedule API获取某天赛事列表"""
    import requests
    url = f'https://oddsfe.com/bind/schedule/football/{date_str}'
    auth = _oddsfe_get_auth()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://oddsfe.com',
        'Referer': f'https://oddsfe.com/schedule/football/{date_str}',
    }
    headers.update(auth)

    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            events = []
            for tournament in data:
                for event in tournament.get('events', []):
                    events.append(event)
            return events
        elif r.status_code == 401:
            # 刷新auth重试
            try:
                sys_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'fetchers', 'odds_feed_api')
                sys_path = os.path.normpath(sys_path)
                import sys
                if sys_path not in sys.path:
                    sys.path.insert(0, sys_path)
                from oddsfe_auth import _refresh_auth
                _refresh_auth()
                auth = _oddsfe_get_auth()
                headers.update(auth)
                r = s.get(url, headers=headers, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    events = []
                    for tournament in data:
                        for event in tournament.get('events', []):
                            events.append(event)
                    return events
            except Exception:
                pass
        logger.warning(f'oddsfe schedule {date_str}: status={r.status_code}')
    except Exception as e:
        logger.warning(f'oddsfe schedule {date_str}: {e}')
    return []


def _oddsfe_fetch_score_details(event_id: str) -> dict:
    """调用oddsfe event API获取score_details"""
    import requests
    url = f'https://oddsfe.com/bind/event/{event_id}'
    auth = _oddsfe_get_auth()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Origin': 'https://oddsfe.com',
        'Referer': f'https://oddsfe.com/events/{event_id}',
    }
    headers.update(auth)

    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f'oddsfe event {event_id}: {e}')
    return {}


def _parse_score_details(score_details: str) -> Optional[Dict]:
    """解析score_details → 半场+全场+加时+点球比分

    格式变体:
    - "2:1" → 仅全场
    - "0:1, 2:1" → 半场, 全场
    - "1:0, 1:2, 8:7" → 半场, 全场, 加时
    - "0:0, 1:1, 0:0, 5:6" → 半场, 全场, 加时, 点球
    - "(4:1, 3:3)" → 括号包裹
    """
    if not score_details:
        return None

    s = score_details.strip()
    # 去括号
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1]

    parts = [p.strip() for p in s.split(',') if ':' in p]
    if not parts:
        return None

    def parse_score(part):
        nums = part.strip().split(':')
        if len(nums) == 2:
            try:
                return int(nums[0]), int(nums[1])
            except ValueError:
                return None
        return None

    scores = [parse_score(p) for p in parts]
    scores = [s for s in scores if s is not None]

    result = {}
    if len(scores) >= 1:
        result['ft'] = scores[-1] if len(scores) == 1 else scores[1] if len(scores) >= 2 else scores[0]
    if len(scores) >= 2:
        result['ht'] = scores[0]
    if len(scores) >= 3:
        result['et'] = scores[2]
    if len(scores) >= 4:
        result['pen'] = scores[3]

    return result if result else None


def _derive_play_types(home_ft: int, away_ft: int,
                       home_ht: int = None, away_ht: int = None,
                       handicap_line: float = 0) -> Dict:
    """从比分推导全部玩法结果 (体彩编码: 3=主胜, 1=平, 0=客胜)"""
    result = {}

    # SPF (胜平负)
    if home_ft > away_ft:
        result['spf_result'] = '3'
    elif home_ft == away_ft:
        result['spf_result'] = '1'
    else:
        result['spf_result'] = '0'

    # BF (比分) — 格式 "H:A"
    result['bf_result'] = f'{home_ft}:{away_ft}'

    # BQC (半全场) — 格式 "半场结果+全场结果"
    if home_ht is not None and away_ht is not None:
        ht_code = '3' if home_ht > away_ht else ('1' if home_ht == away_ht else '0')
        ft_code = result['spf_result']
        result['bqc_result'] = f'{ht_code}{ft_code}'

    # RQSPF (让球胜平负)
    # handicap_line > 0 表示主队让球，home_adjusted = home_ft - handicap_line
    if handicap_line != 0:
        home_adj = home_ft - handicap_line
        if home_adj > away_ft:
            result['rqspf_result'] = '3'
        elif home_adj == away_ft:
            result['rqspf_result'] = '1'
        else:
            result['rqspf_result'] = '0'

    return result


class LotterySyncService:
    """
    体彩数据同步服务

    串联流程:
    爬虫 → EntityMapper → 处理层 → DAO → oddsfe桥接 → 数据库
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

        # 初始化各组件
        self.crawler = LotteryCrawlerSync()
        self.mapper = EntityMapper(db_path)
        self.match_dao = LotteryMatchDAO(db_path)
        self.odds_dao = LotteryOddsDAO(db_path)

        # 加载CN→EN映射
        self._cn_to_en = _load_cn_to_en()

    def sync_daily_matches(self, match_date: date = None) -> Dict:
        """
        同步每日比赛数据

        流程:
        1. 爬虫获取比赛列表
        2. EntityMapper 映射球队名称
        3. 处理层: 从rqspf赔率提取goal_line→handicap_line
        4. DAO 写入数据库 (比赛 + 赔率，赔率标为opening)
        5. oddsfe桥接: 匹配event_id、写入beijing_time(UTC+8)、自动学习CN→EN映射
        """
        if match_date is None:
            match_date = date.today()

        logger.info(f"Starting sync for {match_date}")

        # 1. 爬取数据
        raw_matches = self.crawler.crawl_matches_sync(match_date)

        if not raw_matches:
            logger.warning(f"No matches found for {match_date}")
            return {
                'success': False,
                'date': str(match_date),
                'crawled': 0,
                'mapped': 0,
                'saved': 0,
                'odds_saved': 0,
                'bridged': 0,
                'error': 'No data from crawler'
            }

        # 提取data字段
        matches_data = raw_matches.get('data', []) if isinstance(raw_matches, dict) else raw_matches
        if not matches_data:
            return {
                'success': False,
                'date': str(match_date),
                'crawled': 0,
                'mapped': 0,
                'saved': 0,
                'odds_saved': 0,
                'bridged': 0,
                'error': 'No matches in response'
            }

        # 2. 处理每场比赛
        saved_count = 0
        mapped_count = 0
        odds_saved = 0
        errors = []
        saved_match_ids = []  # 记录入库的match_id，用于后续桥接

        for raw_match in matches_data:
            try:
                # 字段映射
                standardized = self.mapper.map_to_standard('lottery', raw_match)

                # 球队映射
                home_team_id = self.mapper.get_team_id(raw_match['home_team_cn'])
                away_team_id = self.mapper.get_team_id(raw_match['away_team_cn'])

                # 如果映射失败，尝试用normalize后的英文名自动注册
                if not home_team_id:
                    home_team_id = self._auto_register_team(raw_match['home_team_cn'])
                if not away_team_id:
                    away_team_id = self._auto_register_team(raw_match['away_team_cn'])

                if home_team_id and away_team_id:
                    mapped_count += 1

                # === 处理层: 从rqspf赔率提取handicap_line ===
                handicap_line = raw_match.get('handicap_line', 0)
                odds_data = raw_match.get('odds_data', {})

                # 如果handicap_line为0但rqspf赔率有goal_line，从赔率提取
                if handicap_line == 0 and 'rqspf' in odds_data:
                    rqspf = odds_data['rqspf']
                    goal_line = rqspf.get('goal_line', '')
                    if goal_line:
                        try:
                            gl = float(goal_line)
                            # goal_line负数表示主队让球(如"-1"表示主让1球)
                            # handicap_line正数表示主队让球数
                            handicap_line = abs(gl)
                        except (ValueError, TypeError):
                            pass

                # 准备入库数据
                match_data = {
                    'lottery_match_id': raw_match['lottery_match_id'],
                    'home_team_cn': raw_match['home_team_cn'],
                    'away_team_cn': raw_match['away_team_cn'],
                    'match_date': raw_match['match_date'],
                    'match_time': raw_match.get('match_time'),
                    'league_name_cn': raw_match.get('league_name_cn'),
                    'match_num': raw_match.get('match_num'),
                    'sell_status': raw_match.get('sell_status', 'selling'),
                    'play_types': raw_match.get('play_types', []),
                    'handicap_line': handicap_line,
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id
                }

                # DAO 入库
                if self.match_dao.insert(match_data):
                    saved_count += 1
                    saved_match_ids.append(raw_match['lottery_match_id'])

                    # === 赔率入库: 标记为opening快照 ===
                    if odds_data:
                        for play_type, odds in odds_data.items():
                            try:
                                self._insert_odds_with_snapshot(
                                    lottery_match_id=raw_match['lottery_match_id'],
                                    play_type=play_type,
                                    odds_data=odds,
                                    snapshot_type='opening'
                                )
                                odds_saved += 1
                            except Exception as e:
                                logger.debug(f"Odds insert error for {play_type}: {e}")

            except Exception as e:
                errors.append(f"{raw_match.get('lottery_match_id', 'unknown')}: {str(e)}")
                logger.error(f"Error processing match: {e}")

        # 3. oddsfe桥接
        bridged = 0
        if saved_match_ids:
            bridged = self._bridge_oddsfe(match_date, saved_match_ids)

        logger.info(f"Sync completed: {saved_count} matches, {odds_saved} odds, {bridged} bridged")

        return {
            'success': True,
            'date': str(match_date),
            'crawled': len(matches_data),
            'mapped': mapped_count,
            'saved': saved_count,
            'odds_saved': odds_saved,
            'bridged': bridged,
            'errors': errors[:10]
        }

    def _bridge_oddsfe(self, match_date: date, lottery_match_ids: List[str]) -> int:
        """
        oddsfe桥接: 匹配event_id、写入beijing_time(UTC+8)、自动学习CN→EN映射

        策略:
        1. 查询match_date和match_date-1两天的oddsfe schedule (覆盖UTC跨天)
        2. 按CN→EN队名映射匹配
        3. 匹配成功: 写入oddsfe_event_id + beijing_time(UTC+8)
        4. 自动学习: 将新的CN→EN映射写回JSON
        """
        # 查询需要桥接的比赛
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        placeholders = ','.join(['?'] * len(lottery_match_ids))
        cursor.execute(f"""
            SELECT lottery_match_id, home_team_cn, away_team_cn, match_date,
                   handicap_line, oddsfe_event_id
            FROM lottery_matches
            WHERE lottery_match_id IN ({placeholders})
        """, lottery_match_ids)
        matches = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not matches:
            return 0

        # 获取oddsfe schedule数据 (match_date + match_date-1, 覆盖UTC跨天)
        all_events = []
        for offset in [0, -1, 1]:  # 前后各1天
            d = match_date + timedelta(days=offset)
            events = _oddsfe_fetch_schedule(d.strftime('%Y-%m-%d'))
            all_events.extend(events)
            time.sleep(0.3)  # 限流

        if not all_events:
            logger.warning(f'No oddsfe events for {match_date}')
            return 0

        # 构建oddsfe队名索引
        oddsfe_by_norm = {}
        for ev in all_events:
            home_en = ev.get('team_home_name', '')
            away_en = ev.get('team_away_name', '')
            start_at = ev.get('event_start_at', '')
            eid = ev.get('event_id', '')
            if home_en and away_en and eid:
                key = (_norm_team(home_en), _norm_team(away_en))
                if key not in oddsfe_by_norm:
                    oddsfe_by_norm[key] = []
                oddsfe_by_norm[key].append({
                    'event_id': eid,
                    'event_start_at': start_at,
                    'home_en': home_en,
                    'away_en': away_en,
                })

        # 逐场匹配
        bridged = 0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for m in matches:
            lm_id = m['lottery_match_id']
            h_cn = m['home_team_cn']
            a_cn = m['away_team_cn']
            md = m['match_date']

            # 已有oddsfe_event_id且beijing_time非空 → 跳过
            if m.get('oddsfe_event_id') and m.get('beijing_time'):
                continue

            # CN→EN
            home_en = self._cn_to_en.get(h_cn, h_cn)
            away_en = self._cn_to_en.get(a_cn, a_cn)

            # 如果还是中文 → 尝试normalize
            if any('一' <= c <= '鿿' for c in home_en):
                home_en = h_cn  # 无法映射，用原名尝试
            if any('一' <= c <= '鿿' for c in away_en):
                away_en = a_cn

            # 标准化匹配
            key = (_norm_team(home_en), _norm_team(away_en))
            candidates = oddsfe_by_norm.get(key, [])

            if not candidates:
                # 尝试主客互换 (oddsfe可能主客反转)
                key_rev = (_norm_team(away_en), _norm_team(home_en))
                candidates = oddsfe_by_norm.get(key_rev, [])

            if not candidates:
                continue

            # 选最佳候选: 日期最近的
            best = None
            best_diff = 999
            try:
                match_d = datetime.fromisoformat(md).date()
            except (ValueError, TypeError):
                match_d = match_date

            for cand in candidates:
                try:
                    utc_dt = datetime.fromisoformat(cand['event_start_at'])
                    bj_dt = utc_dt + timedelta(hours=8)
                    diff = abs((bj_dt.date() - match_d).days)
                    if diff < best_diff:
                        best_diff = diff
                        best = cand
                except (ValueError, TypeError):
                    continue

            if not best or best_diff > 3:
                continue

            # 匹配成功: 写入beijing_time + oddsfe_event_id
            try:
                utc_dt = datetime.fromisoformat(best['event_start_at'])
                bj_dt = utc_dt + timedelta(hours=8)
                bj_str = bj_dt.strftime('%Y-%m-%d %H:%M')
                eid = str(best['event_id'])

                cursor.execute("""
                    UPDATE lottery_matches
                    SET beijing_time = ?, oddsfe_event_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                """, (bj_str, eid, lm_id))

                if cursor.rowcount > 0:
                    bridged += 1
                    logger.info(f'Bridge: {h_cn} vs {a_cn} -> eid={eid}, bj={bj_str}')

                    # 自动学习CN→EN映射
                    self._auto_learn_mapping(h_cn, best['home_en'], a_cn, best['away_en'])

            except Exception as e:
                logger.debug(f'Bridge write error: {e}')

        conn.commit()
        conn.close()
        return bridged

    def _auto_learn_mapping(self, h_cn: str, h_en: str, a_cn: str, a_en: str):
        """自动学习CN→EN队名映射: 写回JSON + 写入DB team_name_mapping"""
        # 判断是否需要学习 (CN和EN不同且EN不含中文)
        for cn, en in [(h_cn, h_en), (a_cn, a_en)]:
            if cn == en:
                continue
            if any('一' <= c <= '鿿' for c in en):
                continue
            if cn in self._cn_to_en and self._cn_to_en[cn] == en:
                continue  # 已知映射

            # 写回JSON
            _save_cn_en_mapping(cn, en)

            # 更新内存缓存
            self._cn_to_en[cn] = en

            # 写入DB team_name_mapping (如果有对应team_id)
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT team_id FROM teams WHERE name_en = ? COLLATE NOCASE LIMIT 1",
                    (en,)
                )
                row = cursor.fetchone()
                if row:
                    team_id = row[0]
                    cursor.execute("""
                        INSERT OR REPLACE INTO team_name_mapping
                        (lottery_name, team_id, match_confidence, match_method, updated_at)
                        VALUES (?, ?, 0.9, 'auto_bridge', CURRENT_TIMESTAMP)
                    """, (cn, team_id))
                    conn.commit()

                    # 更新EntityMapper缓存
                    self.mapper._team_name_cache[cn] = team_id
                    logger.info(f'Auto-learned mapping: {cn} -> {en} (team_id={team_id})')
                conn.close()
            except Exception as e:
                logger.debug(f'Auto-learn DB error: {e}')

    def _insert_odds_with_snapshot(self, lottery_match_id: str, play_type: str,
                                   odds_data: Dict, snapshot_type: str = 'opening'):
        """插入赔率并标记快照类型

        逻辑:
        - 首次插入: odds_data=opening, opening_odds=opening, snapshot_type='opening'
        - 后续插入: odds_data=latest, latest_odds=latest, snapshot_type='latest'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 检查是否已有opening快照
            cursor.execute("""
                SELECT 1 FROM lottery_odds
                WHERE lottery_match_id = ? AND play_type = ? AND snapshot_type = 'opening'
            """, (lottery_match_id, play_type))
            has_opening = cursor.fetchone() is not None

            odds_json = json.dumps(odds_data)

            if snapshot_type == 'opening' and not has_opening:
                # 首次=opening快照
                cursor.execute("""
                    INSERT OR REPLACE INTO lottery_odds
                    (lottery_match_id, play_type, odds_data, opening_odds, snapshot_type, update_time)
                    VALUES (?, ?, ?, ?, 'opening', CURRENT_TIMESTAMP)
                """, (lottery_match_id, play_type, odds_json, odds_json))
            else:
                # 后续=latest快照
                cursor.execute("""
                    UPDATE lottery_odds
                    SET odds_data = ?, latest_odds = ?, snapshot_type = 'latest',
                        update_time = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ? AND play_type = ?
                """, (odds_json, odds_json, lottery_match_id, play_type))

                if cursor.rowcount == 0:
                    # 没有已有记录，直接插入
                    cursor.execute("""
                        INSERT OR REPLACE INTO lottery_odds
                        (lottery_match_id, play_type, odds_data, latest_odds, snapshot_type, update_time)
                        VALUES (?, ?, ?, ?, 'latest', CURRENT_TIMESTAMP)
                    """, (lottery_match_id, play_type, odds_json, odds_json))

            conn.commit()
        except Exception as e:
            logger.debug(f'Odds snapshot insert error: {e}')
        finally:
            conn.close()

    def sync_results(self, match_date: date = None) -> Dict:
        """
        同步开奖结果 — sporttery优先 + oddsfe补BQC

        去重策略: 先删除已有结果，再插入新结果 (保证1:1)
        """
        if match_date is None:
            match_date = date.today()

        # 1. sporttery结果
        raw_results = self.crawler.crawl_results_sync(match_date)

        if not raw_results:
            return {
                'success': False,
                'date': str(match_date),
                'saved': 0
            }

        saved = 0
        for result in raw_results:
            try:
                lm_id = result.get('lottery_match_id') or result.get('matchId')
                if not lm_id:
                    continue

                result_data = {
                    'lottery_match_id': lm_id,
                    'home_goals_ft': self._safe_int(result.get('home_goals_ft') or result.get('homeScore')),
                    'away_goals_ft': self._safe_int(result.get('away_goals_ft') or result.get('awayScore')),
                    'home_goals_ht': self._safe_int(result.get('home_goals_ht') or result.get('homeScoreHt')),
                    'away_goals_ht': self._safe_int(result.get('away_goals_ht') or result.get('awayScoreHt')),
                    'spf_result': result.get('spf_result') or result.get('spfResult'),
                    'bf_result': result.get('bf_result') or result.get('bfResult'),
                    'bqc_result': result.get('bqc_result') or result.get('bqcResult'),
                    'rqspf_result': result.get('rqspf_result') or result.get('rqspfResult'),
                }

                # 如果sporttery结果不完整，尝试从比分推导
                result_data = self._fill_derived_results(result_data)

                # INSERT OR REPLACE 利用UNIQUE(lottery_match_id)去重
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO lottery_results
                        (lottery_match_id, home_goals_ft, away_goals_ft,
                         home_goals_ht, away_goals_ht,
                         spf_result, bf_result, bqc_result, rqspf_result)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lm_id,
                        result_data.get('home_goals_ft'),
                        result_data.get('away_goals_ft'),
                        result_data.get('home_goals_ht'),
                        result_data.get('away_goals_ht'),
                        result_data.get('spf_result'),
                        result_data.get('bf_result'),
                        result_data.get('bqc_result'),
                        result_data.get('rqspf_result')
                    ))
                    conn.commit()
                    saved += 1
                except Exception as e:
                    logger.error(f"Save result error: {e}")
                finally:
                    conn.close()

            except Exception as e:
                logger.error(f"Result processing error: {e}")

        # 2. oddsfe补BQC (sporttery经常缺半场比分)
        bqc_filled = self._supplement_bqc_from_oddsfe(match_date)

        return {
            'success': True,
            'date': str(match_date),
            'saved': saved,
            'total': len(raw_results),
            'bqc_filled': bqc_filled
        }

    def _supplement_bqc_from_oddsfe(self, match_date: date) -> int:
        """用oddsfe score_details补充缺失的BQC和半场比分"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 查找缺BQC或半场比分的结果
        date_str = match_date.strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT lr.result_id, lr.lottery_match_id,
                   lr.home_goals_ft, lr.away_goals_ft,
                   lr.home_goals_ht, lr.away_goals_ht,
                   lr.bqc_result, lm.oddsfe_event_id, lm.handicap_line
            FROM lottery_results lr
            JOIN lottery_matches lm ON lr.lottery_match_id = lm.lottery_match_id
            WHERE lm.match_date = ?
              AND lm.oddsfe_event_id IS NOT NULL
              AND (lr.bqc_result IS NULL OR lr.home_goals_ht IS NULL)
        """, (date_str,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not rows:
            return 0

        filled = 0
        for row in rows:
            eid = row['oddsfe_event_id']
            if not eid:
                continue

            event_data = _oddsfe_fetch_score_details(eid)
            score_details = event_data.get('score_details', '')
            parsed = _parse_score_details(score_details)
            if not parsed or 'ht' not in parsed:
                continue

            ht_home, ht_away = parsed['ht']
            ft_home, ft_away = parsed.get('ft', (row['home_goals_ft'], row['away_goals_ft']))

            # 推导BQC
            derived = _derive_play_types(
                ft_home, ft_away, ht_home, ht_away,
                row.get('handicap_line', 0) or 0
            )

            # 更新
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                updates = []
                params = []

                if row['home_goals_ht'] is None:
                    updates.append('home_goals_ht = ?')
                    params.append(ht_home)
                if row['away_goals_ht'] is None:
                    updates.append('away_goals_ht = ?')
                    params.append(ht_away)
                if not row.get('bqc_result') and 'bqc_result' in derived:
                    updates.append('bqc_result = ?')
                    params.append(derived['bqc_result'])

                if updates:
                    sql = f"UPDATE lottery_results SET {', '.join(updates)} WHERE result_id = ?"
                    params.append(row['result_id'])
                    cursor.execute(sql, params)
                    conn.commit()
                    filled += 1
                    logger.info(f'Supplemented BQC for {row["lottery_match_id"]}: {derived.get("bqc_result")}')
            except Exception as e:
                logger.debug(f'BQC supplement error: {e}')
            finally:
                conn.close()

            time.sleep(0.2)  # 限流

        return filled

    def _fill_derived_results(self, result_data: Dict) -> Dict:
        """从比分推导缺失的玩法结果"""
        ft_h = result_data.get('home_goals_ft')
        ft_a = result_data.get('away_goals_ft')
        ht_h = result_data.get('home_goals_ht')
        ht_a = result_data.get('away_goals_ht')

        if ft_h is not None and ft_a is not None:
            # 获取handicap_line
            lm_id = result_data.get('lottery_match_id')
            handicap = 0
            if lm_id:
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT handicap_line FROM lottery_matches WHERE lottery_match_id = ?",
                        (lm_id,)
                    )
                    row = cursor.fetchone()
                    conn.close()
                    if row and row[0]:
                        handicap = row[0]
                except Exception:
                    pass

            derived = _derive_play_types(ft_h, ft_a, ht_h, ht_a, handicap)

            # 只填充缺失的
            if not result_data.get('spf_result'):
                result_data['spf_result'] = derived.get('spf_result')
            if not result_data.get('bf_result'):
                result_data['bf_result'] = derived.get('bf_result')
            if not result_data.get('bqc_result'):
                result_data['bqc_result'] = derived.get('bqc_result')
            if not result_data.get('rqspf_result'):
                result_data['rqspf_result'] = derived.get('rqspf_result')

        return result_data

    def sync_odds(self, lottery_match_id: str, play_types: List[str] = None) -> Dict:
        """
        同步赔率数据 — 当前赔率已随matchInfo一起入库

        此方法用于手动刷新单场赔率(如需要最新赔率时)
        """
        return {
            'success': True,
            'note': 'Odds are synced with matches via sync_daily_matches()',
            'lottery_match_id': lottery_match_id
        }

    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        today = date.today()
        today_matches = self.match_dao.find_by_date(str(today))
        pending = self.match_dao.find_pending_analysis()

        return {
            'today_matches': len(today_matches),
            'pending_analysis': len(pending),
            'last_sync': datetime.now().isoformat()
        }

    def _auto_register_team(self, cn_name: str) -> Optional[int]:
        """自动注册球队映射：用normalize后的英文名查teams表"""
        try:
            from fetchers.common.team_names import normalize_team_name
            en_name = normalize_team_name(cn_name)

            # 如果normalize后还是中文，无法自动映射
            if any('一' <= c <= '鿿' for c in en_name):
                return None

            # 在teams表中查找
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT team_id FROM teams WHERE name_en = ? COLLATE NOCASE LIMIT 1",
                (en_name,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                team_id = row[0]
                # 注册映射
                self.mapper.register_team_mapping(cn_name, team_id, method='auto_normalize')
                logger.info(f'自动注册映射: {cn_name} -> team_id={team_id}')
                return team_id

        except Exception as e:
            logger.debug(f'自动注册失败 {cn_name}: {e}')

        return None

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        """安全整数转换"""
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def close(self):
        """清理资源"""
        pass
