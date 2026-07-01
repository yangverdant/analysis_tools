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
import sys
import time
import unicodedata
import requests
from datetime import datetime, date, timedelta

from ..data_sources.scrapers.lottery_crawler import LotteryCrawlerSync
from ..etl.entity_mapper import EntityMapper
from ..dao.lottery_dao import LotteryMatchDAO, LotteryOddsDAO
from backend.app.data_access.foundation_dao import FoundationDAO

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
    """��ȡoddsfe��֤headers"""
    try:
        sys_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'fetchers', 'odds_feed_api')
        sys_path = os.path.normpath(sys_path)
        import sys
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from oddsfe_auth import get_schedule_auth, get_event_auth
        # 返回双 auth，调用方根据需要选择
        return {'schedule': get_schedule_auth(), 'event': get_event_auth()}
    except Exception as e:
        logger.warning(f'Failed to get oddsfe auth: {e}')
        return {}


def _oddsfe_fetch_schedule(date_str: str) -> list:
    """����oddsfe schedule API��ȡĳ�������б�"""
    import requests
    url = f'https://oddsfe.com/bind/schedule/football/{date_str}'
    auth = _oddsfe_get_auth()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://oddsfe.com',
        'Referer': f'https://oddsfe.com/schedule/football/{date_str}',
    }
    if auth and 'schedule' in auth:
        headers.update(auth['schedule'])
    elif auth:
        headers.update(auth)

    try:
        s = requests.Session()
        s.trust_env = False
        timeout = float(os.environ.get("ODDSFE_EVENT_TIMEOUT", "8"))
        r = s.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            events = []
            for tournament in data:
                for event in tournament.get('events', []):
                    events.append(event)
            return events
        elif r.status_code == 401:
            # ˢ��auth����
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
    """调用 oddsfe event API 获取 score_details"""
    import requests
    url = f'https://oddsfe.com/bind/event/{event_id}'
    auth = _oddsfe_get_auth()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Origin': 'https://oddsfe.com',
        'Referer': f'https://oddsfe.com/events/{event_id}',
    }
    # 使用 event auth（不是 schedule auth）
    if auth and 'event' in auth:
        headers.update(auth['event'])
    else:
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


def _safe_int_value(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _event_fulltime_score(event_data: Dict, parsed: Optional[Dict] = None) -> tuple:
    """Return (home_ft, away_ft, home_90min, away_90min, end_type).

    For AET/AP matches:
      - home_ft/away_ft = aggregate score (incl. extra time, excl. penalties)
      - home_90min/away_90min = 90-minute regular time score
      - end_type = 'AET' or 'AP'
    For FT matches:
      - all scores identical, end_type = 'FT'
    """
    event_status = str(event_data.get('event_status') or '').upper()
    is_et_status = event_status in ('AET', 'AP')

    # Aggregate score from event_data (may include penalties for AP)
    home_raw = _safe_int_value(
        event_data.get("score_home")
        or event_data.get("event_score_home")
        or event_data.get("home_score")
    )
    away_raw = _safe_int_value(
        event_data.get("score_away")
        or event_data.get("event_score_away")
        or event_data.get("away_score")
    )

    # Detect AET/AP from parsed periods even when event_status is just FINISHED
    has_et = parsed and parsed.get('et') is not None
    has_pen = parsed and parsed.get('pen') is not None
    if has_pen:
        end_type = 'AP'
    elif has_et:
        end_type = 'AET'
    elif is_et_status:
        end_type = event_status
    else:
        end_type = 'FT'

    # Compute 90min score from parsed periods
    home_90 = None
    away_90 = None
    if parsed and parsed.get('ht') and parsed.get('second_half'):
        ht = parsed['ht']
        sh = parsed['second_half']
        home_90 = ht[0] + sh[0]
        away_90 = ht[1] + sh[1]

    # Compute FT (aggregate excluding penalties) from parsed periods
    home_ft = None
    away_ft = None
    if parsed:
        home_ft = 0
        away_ft = 0
        for key in ('ht', 'second_half', 'et'):
            period = parsed.get(key)
            if period:
                home_ft += period[0]
                away_ft += period[1]

    # Fallback: use event_data raw score for FT (but strip penalties if we know it's AP)
    if home_ft is None or away_ft is None:
        if end_type == 'AP' and home_90 is not None and away_90 is not None:
            if parsed and parsed.get('et'):
                et = parsed['et']
                home_ft = home_90 + et[0]
                away_ft = away_90 + et[1]
            else:
                home_ft = home_90
                away_ft = away_90
        else:
            home_ft = home_raw
            away_ft = away_raw

    if home_90 is None or away_90 is None:
        home_90 = home_ft
        away_90 = away_ft

    return home_ft, away_ft, home_90, away_90, end_type


def _parse_score_details(score_details: str) -> Optional[Dict]:
    """Parse oddsfe period scores.

    oddsfe score_details is period based in current data:
    "(1:2, 0:2)" means first half 1:2, second half 0:2, FT 1:4.
    """
    if not score_details:
        return None

    s = score_details.strip()
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
        result['periods'] = scores
        result['ft'] = scores[0]
    if len(scores) >= 2:
        result['ht'] = scores[0]
        result['second_half'] = scores[1]
        result['ft'] = (
            scores[0][0] + scores[1][0],
            scores[0][1] + scores[1][1],
        )
    if len(scores) >= 3:
        result['et'] = scores[2]
    if len(scores) >= 4:
        result['pen'] = scores[3]

    return result if result else None


def _effective_handicap(db_path: str, lottery_match_id: str, fallback_handicap: float = 0) -> float:
    """Return handicap using rqspf goal_line when available.

    lottery_odds.rqspf.goal_line follows sporttery display:
    -2 means home gives two goals, +1 means away gives one goal.
    _derive_play_types expects positive values to subtract from home score,
    so goal_line is converted with -goal_line.
    """
    if lottery_match_id:
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT odds_data FROM lottery_odds WHERE lottery_match_id = ? AND play_type = 'rqspf' LIMIT 1",
                (lottery_match_id,),
            ).fetchone()
            conn.close()
            if row and row[0]:
                odds = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                goal_line = str((odds or {}).get("goal_line", "")).strip()
                if goal_line:
                    return -float(goal_line)
        except Exception:
            pass
    try:
        return float(fallback_handicap or 0)
    except (TypeError, ValueError):
        return 0


BQC_CODES = {'33', '31', '30', '13', '11', '10', '03', '01', '00'}
BQC_TEXT_TO_CODE = {
    'hh': '33', 'hd': '31', 'ha': '30',
    'dh': '13', 'dd': '11', 'da': '10',
    'ah': '03', 'ad': '01', 'aa': '00',
    'home_home': '33', 'home_draw': '31', 'home_away': '30',
    'draw_home': '13', 'draw_draw': '11', 'draw_away': '10',
    'away_home': '03', 'away_draw': '01', 'away_away': '00',
    '\u80dc\u80dc': '33', '\u80dc\u5e73': '31', '\u80dc\u8d1f': '30',
    '\u5e73\u80dc': '13', '\u5e73\u5e73': '11', '\u5e73\u8d1f': '10',
    '\u8d1f\u80dc': '03', '\u8d1f\u5e73': '01', '\u8d1f\u8d1f': '00',
}


def _normalize_bqc_result(value) -> Optional[str]:
    """Return the stored BQC code, or None for empty/invalid source values."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {'-', '--', 'none', 'null', 'nan', 'unknown'}:
        return None
    if text in BQC_CODES:
        return text
    return BQC_TEXT_TO_CODE.get(text.lower()) or BQC_TEXT_TO_CODE.get(text)


def _bqc_from_scores(
    home_ft: int,
    away_ft: int,
    home_ht: Optional[int] = None,
    away_ht: Optional[int] = None,
) -> Optional[str]:
    if home_ht is None or away_ht is None:
        return None
    ht_code = '3' if home_ht > away_ht else ('1' if home_ht == away_ht else '0')
    ft_code = '3' if home_ft > away_ft else ('1' if home_ft == away_ft else '0')
    return f'{ht_code}{ft_code}'


def _resolve_bqc_result(
    home_ft: int,
    away_ft: int,
    home_ht: Optional[int] = None,
    away_ht: Optional[int] = None,
    source_bqc=None,
    source_name: str = '',
    lottery_match_id: Optional[str] = None,
) -> Optional[str]:
    """Resolve BQC without inventing it when half-time evidence is missing."""
    derived = _bqc_from_scores(home_ft, away_ft, home_ht, away_ht)
    source_code = _normalize_bqc_result(source_bqc)
    if derived:
        if source_code and source_code != derived:
            logger.warning(
                'BQC source conflict for %s from %s: source=%s derived=%s',
                lottery_match_id or '',
                source_name or 'source',
                source_code,
                derived,
            )
        return derived
    return source_code


def _derive_play_types(home_ft: int, away_ft: int,
                       home_ht: int = None, away_ht: int = None,
                       handicap_line: float = 0) -> Dict:
    """�ӱȷ��Ƶ�ȫ���淨��� (��ʱ���: 3=��ʤ, 1=ƽ, 0=��ʤ)"""
    result = {}

    # SPF (ʤƽ��)
    if home_ft > away_ft:
        result['spf_result'] = '3'
    elif home_ft == away_ft:
        result['spf_result'] = '1'
    else:
        result['spf_result'] = '0'

    # BF (�ȷ�) �� ��ʽ "H:A"
    result['bf_result'] = f'{home_ft}:{away_ft}'

    # BQC (��ȫ��) �� ��ʽ "�볡���+ȫ�����"
    bqc_result = _bqc_from_scores(home_ft, away_ft, home_ht, away_ht)
    if bqc_result:
        result['bqc_result'] = bqc_result

    # RQSPF (����ʤƽ��)
    # handicap_line > 0 ��ʾ��������home_adjusted = home_ft - handicap_line
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
    �������ͬ������

    ��������:
    ���� �� EntityMapper �� ������ �� DAO �� oddsfe�Ž� �� ���ݿ�
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

        # ��ʼ�������
        self.crawler = LotteryCrawlerSync()
        self.mapper = EntityMapper(db_path)
        self.match_dao = LotteryMatchDAO(db_path)
        self.odds_dao = LotteryOddsDAO(db_path)
        self.foundation = FoundationDAO(db_path)

        # ����CN��ENӳ��
        self._cn_to_en = _load_cn_to_en()

    def sync_daily_matches(
        self,
        match_date: date = None,
        *,
        bridge_oddsfe: bool = True,
        trigger_source: str = 'manual_or_scheduler',
    ) -> Dict:
        """
        ͬ��ÿ�ձ�������

        ����:
        1. �����ȡ�����б�
        2. EntityMapper ӳ���������
        3. ������: ��rqspf������ȡgoal_line��handicap_line
        4. DAO д�����ݿ� (���� + ���ʣ����ʱ�Ϊopening)
        5. oddsfe�Ž�: ƥ��event_id��д��beijing_time(UTC+8)���Զ�ѧϰCN��ENӳ��
        """
        if match_date is None:
            match_date = date.today()

        logger.info(f"Starting sync for {match_date}")
        run_id = self.foundation.start_run(
            run_type='sporttery_daily_matches',
            match_date=match_date,
            trigger_source=trigger_source,
            summary={'stage': 'crawl_matches', 'bridge_oddsfe': bool(bridge_oddsfe)},
        )

        # 1. ��ȡ����
        raw_matches = self.crawler.crawl_matches_sync(match_date)
        self.foundation.record_artifact(
            run_id=run_id,
            source_name='sporttery',
            source_type='crawler',
            entity_type='match_date',
            entity_id=str(match_date),
            payload=raw_matches,
            confidence=0.75,
        )

        if not raw_matches:
            logger.warning(f"No matches found for {match_date}")
            result = {
                'success': False,
                'date': str(match_date),
                'crawled': 0,
                'mapped': 0,
                'saved': 0,
                'odds_saved': 0,
                'bridged': 0,
                'bridge_oddsfe': bool(bridge_oddsfe),
                'bridge_deferred': False,
                'error': 'No data from crawler'
            }
            self.foundation.finish_run(run_id, status='empty', summary=result, error=result['error'])
            return result

        # ��ȡdata�ֶ�
        matches_data = raw_matches.get('data', []) if isinstance(raw_matches, dict) else raw_matches
        if not matches_data:
            result = {
                'success': False,
                'date': str(match_date),
                'crawled': 0,
                'mapped': 0,
                'saved': 0,
                'odds_saved': 0,
                'bridged': 0,
                'bridge_oddsfe': bool(bridge_oddsfe),
                'bridge_deferred': False,
                'error': 'No matches in response'
            }
            self.foundation.finish_run(run_id, status='empty', summary=result, error=result['error'])
            return result

        # 2. ����ÿ������
        saved_count = 0
        mapped_count = 0
        odds_saved = 0
        errors = []
        saved_match_ids = []  # ��¼����match_id�����ں����Ž�

        for raw_match in matches_data:
            try:
                # �ֶ�ӳ��
                standardized = self.mapper.map_to_standard('lottery', raw_match)

                # ���ӳ��
                home_team_id = self.mapper.get_team_id(raw_match['home_team_cn'])
                away_team_id = self.mapper.get_team_id(raw_match['away_team_cn'])

                # ���ӳ��ʧ�ܣ�������normalize���Ӣ�����Զ�ע��
                if not home_team_id:
                    home_team_id = self._auto_register_team(raw_match['home_team_cn'])
                if not away_team_id:
                    away_team_id = self._auto_register_team(raw_match['away_team_cn'])

                if home_team_id and away_team_id:
                    mapped_count += 1

                # === ������: ��rqspf������ȡhandicap_line ===
                handicap_line = raw_match.get('handicap_line', 0)
                odds_data = raw_match.get('odds_data', {})

                # ���handicap_lineΪ0��rqspf������goal_line����������ȡ
                if handicap_line == 0 and 'rqspf' in odds_data:
                    rqspf = odds_data['rqspf']
                    goal_line = rqspf.get('goal_line', '')
                    if goal_line:
                        try:
                            gl = float(goal_line)
                            # goal_line������ʾ��������(��"-1"��ʾ����1��)
                            # handicap_line������ʾ����������
                            handicap_line = abs(gl)
                        except (ValueError, TypeError):
                            pass

                # ׼���������
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

                # DAO ���
                if self.match_dao.insert(match_data):
                    saved_count += 1
                    saved_match_ids.append(raw_match['lottery_match_id'])
                    self.foundation.record_artifact(
                        run_id=run_id,
                        source_name='sporttery',
                        source_type='crawler',
                        entity_type='lottery_match',
                        entity_id=raw_match['lottery_match_id'],
                        payload=raw_match,
                        confidence=0.8,
                    )
                    self.foundation.upsert_mapping(
                        entity_type='match',
                        canonical_id=raw_match['lottery_match_id'],
                        source_name='sporttery',
                        source_entity_id=raw_match['lottery_match_id'],
                        source_entity_name=f"{raw_match.get('home_team_cn')} vs {raw_match.get('away_team_cn')}",
                        confidence=0.95,
                    )
                    if home_team_id:
                        self.foundation.upsert_mapping(
                            entity_type='team',
                            canonical_id=home_team_id,
                            source_name='sporttery',
                            source_entity_id=raw_match.get('home_team_cn'),
                            source_entity_name=raw_match.get('home_team_cn'),
                            confidence=0.8,
                        )
                    if away_team_id:
                        self.foundation.upsert_mapping(
                            entity_type='team',
                            canonical_id=away_team_id,
                            source_name='sporttery',
                            source_entity_id=raw_match.get('away_team_cn'),
                            source_entity_name=raw_match.get('away_team_cn'),
                            confidence=0.8,
                        )

                    # === �������: ���Ϊopening���� ===
                    if odds_data:
                        self.foundation.record_artifact(
                            run_id=run_id,
                            source_name='sporttery_odds',
                            source_type='crawler',
                            entity_type='lottery_match_odds',
                            entity_id=raw_match['lottery_match_id'],
                            payload=odds_data,
                            confidence=0.8,
                        )
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

        # 3. oddsfe�Ž�
        bridged = 0
        bridge_error = None
        if saved_match_ids and bridge_oddsfe:
            try:
                bridged = self._bridge_oddsfe(match_date, saved_match_ids, run_id=run_id)
            except Exception as e:
                bridge_error = f"oddsfe_bridge_failed: {e}"
                errors.append(bridge_error)
                logger.warning("Oddsfe bridge failed for %s: %s", match_date, e)

        # 3.5 Ensure beijing_time for any matches that didn't get bridged
        ensured = 0
        if saved_match_ids:
            try:
                if bridge_oddsfe:
                    ensured = self._ensure_beijing_time(match_date)
                else:
                    ensured = self._ensure_beijing_time_from_local_fields(
                        match_date=match_date,
                        lottery_match_ids=saved_match_ids,
                    )
            except Exception as e:
                ensure_error = f"beijing_time_ensure_failed: {e}"
                errors.append(ensure_error)
                logger.warning("Beijing time ensure failed for %s: %s", match_date, e)

        # 4. Link match_id to system matches table
        linked = 0
        if saved_match_ids:
            linked = self._link_to_system_matches(saved_match_ids)

        logger.info(f"Sync completed: {saved_count} matches, {odds_saved} odds, {bridged} bridged, {linked} linked")

        result = {
            'success': True,
            'date': str(match_date),
            'crawled': len(matches_data),
            'mapped': mapped_count,
            'saved': saved_count,
            'odds_saved': odds_saved,
            'bridged': bridged,
            'bridge_oddsfe': bool(bridge_oddsfe),
            'bridge_deferred': bool(saved_match_ids and not bridge_oddsfe),
            'bridge_error': bridge_error,
            'beijing_time_ensured': ensured,
            'linked': linked,
            'errors': errors[:10]
        }
        self.foundation.finish_run(
            run_id,
            status='success' if not errors else 'partial_success',
            summary=result,
            error='; '.join(errors[:3]) if errors else None,
        )
        return result

    def _ensure_beijing_time_from_local_fields(
        self,
        match_date: date = None,
        lottery_match_ids: Optional[List[str]] = None,
    ) -> int:
        """Cheap Beijing-time fallback with no network calls."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        cursor = conn.cursor()
        where = [
            "(beijing_time IS NULL OR beijing_time = '')",
            "match_time IS NOT NULL",
            "match_time != ''",
        ]
        params: List[str] = []
        ids = [str(item) for item in (lottery_match_ids or []) if str(item or "").strip()]
        if ids:
            placeholders = ",".join(["?"] * len(ids))
            where.append(f"lottery_match_id IN ({placeholders})")
            params.extend(ids)
        elif match_date is not None:
            where.append("match_date = ?")
            params.append(str(match_date))

        cursor.execute(
            f"""
            SELECT lottery_match_id, match_date, match_time
            FROM lottery_matches
            WHERE {' AND '.join(where)}
            """,
            params,
        )
        updated = 0
        for lm_id, md, mt in cursor.fetchall():
            mt_short = (mt or '')[:5]
            if not md or not mt_short:
                continue
            derived_bt = f"{md} {mt_short}"
            cursor.execute(
                """
                UPDATE lottery_matches
                SET beijing_time = ?, updated_at = CURRENT_TIMESTAMP
                WHERE lottery_match_id = ?
                  AND (beijing_time IS NULL OR beijing_time = '')
                """,
                (derived_bt, lm_id),
            )
            updated += cursor.rowcount

        conn.commit()
        self._update_sell_status(cursor, conn)
        conn.close()
        return updated

    def _bridge_oddsfe(self, match_date: date, lottery_match_ids: List[str], run_id: str = None) -> int:
        """
        oddsfe bridge: match event_id + write beijing_time(UTC+8) + auto-learn CN<->EN.
        Uses the same 5-strategy matching as _ensure_beijing_time.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        placeholders = ','.join(['?'] * len(lottery_match_ids))
        cursor.execute(f"""
            SELECT lottery_match_id, home_team_cn, away_team_cn, match_date,
                   match_time, handicap_line, oddsfe_event_id
            FROM lottery_matches
            WHERE lottery_match_id IN ({placeholders})
        """, lottery_match_ids)
        matches = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not matches:
            return 0

        # Fetch oddsfe schedule (match_date +/- 2 days for UTC offset coverage)
        all_events = []
        all_events_by_norm = {}
        for offset in range(-2, 3):
            d = match_date + timedelta(days=offset)
            raw_events = _oddsfe_fetch_schedule(d.strftime('%Y-%m-%d'))
            self.foundation.record_artifact(
                run_id=run_id,
                source_name='oddsfe',
                source_type='api',
                entity_type='schedule',
                entity_id=d.strftime('%Y-%m-%d'),
                payload=raw_events,
                confidence=0.85,
            )
            for ev in raw_events:
                home_en = ev.get('team_home_name', '').strip()
                away_en = ev.get('team_away_name', '').strip()
                start_at = ev.get('event_start_at', '')
                eid = str(ev.get('event_id', ''))
                if home_en and away_en and eid:
                    ev_dict = {
                        'event_id': eid,
                        'start': start_at,
                        'home_en': home_en,
                        'away_en': away_en,
                    }
                    all_events.append(ev_dict)
                    key = (_norm_team(home_en), _norm_team(away_en))
                    if key not in all_events_by_norm:
                        all_events_by_norm[key] = []
                    all_events_by_norm[key].append(ev_dict)
            time.sleep(0.3)

        if not all_events:
            logger.warning(f'No oddsfe events for {match_date}')
            return 0

        # Build CN->EN multi-value mapping
        cn_to_en_all = {}
        try:
            names_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'linkage', 'team_chinese_names.json')
            with open(names_path, encoding='utf-8') as f:
                en_to_cn = json.load(f)
                for en_name, cn_name in en_to_cn.items():
                    key = cn_name.strip()
                    if key not in cn_to_en_all:
                        cn_to_en_all[key] = []
                    cn_to_en_all[key].append(en_name)
        except Exception:
            pass
        for cn, en in _load_cn_to_en().items():
            cn_key = cn.strip()
            if cn_key not in cn_to_en_all:
                cn_to_en_all[cn_key] = [en]
            elif en not in cn_to_en_all[cn_key]:
                cn_to_en_all[cn_key].append(en)

        # Match each match using 5 strategies. Keep secondary writes outside
        # the main SQLite transaction; otherwise the foundation/mapping helpers
        # can open a second write connection while this one is still locked.
        bridged = 0
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA busy_timeout=30000")
        cursor = conn.cursor()
        post_commit_event_mappings = []
        post_commit_learning = []

        for m in matches:
            lm_id = m['lottery_match_id']
            h_cn = (m['home_team_cn'] or '').strip()
            a_cn = (m['away_team_cn'] or '').strip()
            md = m['match_date']

            # Skip only if already bridged AND beijing_time was set from oddsfe (not naive match_date+match_time)
            existing_bt = m.get('beijing_time', '') or ''
            existing_eid = m.get('oddsfe_event_id', '') or ''
            mt_short = (m.get('match_time', '') or '')[:5]
            derived_bt = f"{m['match_date']} {mt_short}" if m['match_date'] and mt_short else ''
            if existing_eid and existing_bt and existing_bt != derived_bt:
                # Already corrected by oddsfe — skip
                continue

            h_en_variants = list(cn_to_en_all.get(h_cn, []))
            a_en_variants = list(cn_to_en_all.get(a_cn, []))

            # Also try normalize_team_name
            for cn_name, variants in [(h_cn, h_en_variants), (a_cn, a_en_variants)]:
                try:
                    from fetchers.common.team_names import normalize_team_name
                    alt = normalize_team_name(cn_name)
                    if alt and not any('\u4e00' <= c <= '\u9fff' for c in alt) and alt not in variants:
                        variants.append(alt)
                except Exception:
                    pass

            found = None
            match_strategy = None

            # Strategy 1: Exact match with all EN name variants
            if h_en_variants and a_en_variants:
                for he in h_en_variants:
                    for ae in a_en_variants:
                        key = (_norm_team(he), _norm_team(ae))
                        candidates = all_events_by_norm.get(key, [])
                        if candidates:
                            found = self._pick_best_candidate(candidates, md)
                            if found:
                                match_strategy = f'S1({he} vs {ae})'
                                break
                    if found:
                        break
                # Try reversed
                if not found:
                    for he in h_en_variants:
                        for ae in a_en_variants:
                            key = (_norm_team(ae), _norm_team(he))
                            candidates = all_events_by_norm.get(key, [])
                            if candidates:
                                found = self._pick_best_candidate(candidates, md)
                                if found:
                                    match_strategy = f'S1-rev({he} vs {ae})'
                                    break
                        if found:
                            break

            # Strategy 2: CN exact
            if not found:
                key = (_norm_team(h_cn), _norm_team(a_cn))
                candidates = all_events_by_norm.get(key, [])
                if candidates:
                    found = self._pick_best_candidate(candidates, md)
                    if found:
                        match_strategy = 'S2-cn'

            # Strategy 3: Single-team exact (home first)
            if not found:
                for he in h_en_variants:
                    h_norm = _norm_team(he)
                    candidates = []
                    for key, evs in all_events_by_norm.items():
                        if key[0] == h_norm:
                            for ev in evs:
                                for ae in a_en_variants:
                                    if _norm_team(ae) == _norm_team(ev['away_en']):
                                        candidates.append(ev)
                                        break
                    if len(candidates) == 1:
                        found = candidates[0]
                        match_strategy = f'S3-home({he})'
                        break
                    elif len(candidates) > 1:
                        found = self._pick_best_candidate(candidates, md)
                        if found:
                            match_strategy = f'S3-home-date({he})'
                            break

            # Strategy 4: Word-root
            if not found:
                h_search = (h_en_variants[0] if h_en_variants else h_cn).lower()
                a_search = (a_en_variants[0] if a_en_variants else a_cn).lower()
                h_roots = [w for w in h_search.split() if len(w) >= 4]
                a_roots = [w for w in a_search.split() if len(w) >= 4]
                if h_roots and a_roots:
                    candidates = []
                    for key, evs in all_events_by_norm.items():
                        k_h_words = [w for w in key[0].split() if len(w) >= 4]
                        k_a_words = [w for w in key[1].split() if len(w) >= 4]
                        h_root_match = any(hw in kw or kw in hw for hw in h_roots for kw in k_h_words)
                        a_root_match = any(aw in kw or kw in aw for aw in a_roots for kw in k_a_words)
                        if h_root_match and a_root_match:
                            candidates.extend(evs)
                    if candidates:
                        found = self._pick_best_candidate(candidates, md)
                        if found:
                            match_strategy = 'S4-word-root'

            # Strategy 5: Time-window (+/-2h)
            if not found:
                match_time_str = m.get('match_time') or ''
                if md and match_time_str:
                    try:
                        mt_short = match_time_str[:5] if len(match_time_str) > 5 else match_time_str
                        bj_approx = datetime.strptime(f"{md} {mt_short}", '%Y-%m-%d %H:%M')
                        utc_approx = bj_approx - timedelta(hours=8)
                        candidates = []
                        for ev in all_events:
                            try:
                                start_str = ev['start']
                                if 'T' in start_str:
                                    ev_utc = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                                else:
                                    ev_utc = datetime.strptime(start_str[:19], '%Y-%m-%d %H:%M:%S')
                                diff_hours = abs((ev_utc - utc_approx).total_seconds()) / 3600
                                if diff_hours <= 2:
                                    candidates.append((ev, diff_hours))
                            except (ValueError, TypeError):
                                continue
                        if len(candidates) == 1:
                            found = candidates[0][0]
                            match_strategy = f'S5-time({candidates[0][1]:.1f}h)'
                        elif len(candidates) > 1:
                            candidates.sort(key=lambda x: x[1])
                            best_score = 0
                            best_ev = None
                            for ev, dh in candidates:
                                score = 0
                                for he in h_en_variants:
                                    if he.lower() in ev['home_en'].lower() or ev['home_en'].lower() in he.lower():
                                        score += 1
                                        break
                                for ae in a_en_variants:
                                    if ae.lower() in ev['away_en'].lower() or ev['away_en'].lower() in ae.lower():
                                        score += 1
                                        break
                                if score > best_score:
                                    best_score = score
                                    best_ev = ev
                            if best_ev and best_score >= 1:
                                found = best_ev
                                match_strategy = f'S5-time-narrow(score={best_score})'
                    except (ValueError, TypeError):
                        pass

            # Apply match
            if found:
                try:
                    start_str = found['start']
                    eid = str(found['event_id'])
                    if 'T' in start_str:
                        utc_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    else:
                        utc_dt = datetime.strptime(start_str[:19], '%Y-%m-%d %H:%M:%S')
                    bj_dt = utc_dt + timedelta(hours=8)
                    bj_str = bj_dt.strftime('%Y-%m-%d %H:%M')
                    bj_date = bj_dt.strftime('%Y-%m-%d')
                    bj_time = bj_dt.strftime('%H:%M:%S')

                    cursor.execute("""
                        UPDATE lottery_matches
                        SET beijing_time = ?, oddsfe_event_id = ?,
                            match_date = ?, match_time = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE lottery_match_id = ?
                    """, (bj_str, eid, bj_date, bj_time, lm_id))
                    match_update_count = cursor.rowcount

                    # Update play_types from lottery_odds
                    cursor.execute("""
                        SELECT DISTINCT play_type FROM lottery_odds
                        WHERE lottery_match_id = ?
                    """, (lm_id,))
                    available_types = [row[0] for row in cursor.fetchall()]
                    if available_types:
                        mapped = [pt for pt in available_types if pt in ('spf', 'rqspf', 'bf', 'bqc', 'ttg')]
                        if mapped:
                            cursor.execute("""
                                UPDATE lottery_matches
                                SET play_types = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE lottery_match_id = ?
                            """, (json.dumps(mapped), lm_id))

                    if match_update_count > 0:
                        bridged += 1
                        logger.info(f'Bridge {match_strategy}: {h_cn} vs {a_cn} -> eid={eid}, bj={bj_str}')
                        post_commit_event_mappings.append(
                            {
                                "canonical_id": lm_id,
                                "source_entity_id": eid,
                                "source_entity_name": f"{found['home_en']} vs {found['away_en']}",
                            }
                        )

                    post_commit_learning.append((h_cn, found['home_en'], a_cn, found['away_en']))

                except Exception as e:
                    logger.debug(f'Bridge write error: {e}')

        conn.commit()
        conn.close()

        for mapping in post_commit_event_mappings:
            self.foundation.upsert_mapping(
                entity_type='event',
                canonical_id=mapping["canonical_id"],
                source_name='oddsfe',
                source_entity_id=mapping["source_entity_id"],
                source_entity_name=mapping["source_entity_name"],
                confidence=0.9,
            )
        for h_cn, h_en, a_cn, a_en in post_commit_learning:
            self._auto_learn_mapping(h_cn, h_en, a_cn, a_en)

        return bridged

    def _ensure_beijing_time(self, match_date: date, window_before_days: int = 2, window_after_days: int = 7) -> int:
        """
        Ensure all matches for match_date have beijing_time populated.
        5-strategy matching: tournament -> EN variants -> CN -> single-team -> word-root -> time-window.
        All successful matches auto-learn CN<->EN mapping.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        window_start = (match_date - timedelta(days=window_before_days)).strftime('%Y-%m-%d')
        window_end = (match_date + timedelta(days=window_after_days)).strftime('%Y-%m-%d')

        # Find matches near this collection date only. Historical backlog must
        # be handled by idle backfill; a daily collection run must not scan all
        # unfinished rows or one stale batch can block today's data.
        cursor.execute("""
            SELECT lottery_match_id, home_team_cn, away_team_cn, match_date,
                   match_time, league_name_cn, beijing_time, oddsfe_event_id
            FROM lottery_matches
            WHERE sell_status != 'finished'
              AND (
                  beijing_time IS NULL OR beijing_time = ''
                  OR oddsfe_event_id IS NULL OR oddsfe_event_id = ''
              )
              AND substr(COALESCE(beijing_time, match_date), 1, 10) BETWEEN ? AND ?
            ORDER BY match_date, match_time, lottery_match_id
        """, (window_start, window_end))
        missing = [dict(r) for r in cursor.fetchall()]

        if not missing:
            self._update_sell_status(cursor, conn)
            conn.close()
            return 0

        # Get auth for oddsfe
        try:
            sys_path_backup = sys.path.copy()
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'fetchers', 'odds_feed_api'))
            from oddsfe_auth import get_schedule_auth
            auth = get_schedule_auth()
            sys.path = sys_path_backup
        except Exception as e:
            logger.warning(f"Failed to get oddsfe auth: {e}")
            conn.close()
            return 0

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://oddsfe.com",
        }
        if isinstance(auth, dict):
            if 'schedule' in auth:
                headers.update(auth['schedule'])
            else:
                headers.update(auth)

        # Load CN->EN mapping (multi-value: same CN can map to multiple EN names)
        en_to_cn = {}
        cn_to_en_all = {}
        names_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'linkage', 'team_chinese_names.json')
        try:
            with open(names_path, encoding='utf-8') as f:
                en_to_cn = json.load(f)
                for en_name, cn_name in en_to_cn.items():
                    key = cn_name.strip()
                    if key not in cn_to_en_all:
                        cn_to_en_all[key] = []
                    cn_to_en_all[key].append(en_name)
        except Exception:
            pass

        # Also add hardcoded mappings from _load_cn_to_en
        for cn, en in _load_cn_to_en().items():
            cn_key = cn.strip()
            if cn_key not in cn_to_en_all:
                cn_to_en_all[cn_key] = [en]
            elif en not in cn_to_en_all[cn_key]:
                cn_to_en_all[cn_key].append(en)

        # Try normalize_team_name as extra fallback
        try:
            sys_path_backup2 = sys.path.copy()
            sys_path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'fetchers', 'common'))
            from team_names import normalize_team_name
            sys.path = sys_path_backup2
        except Exception:
            normalize_team_name = None

        # Fetch oddsfe schedule for wider date range
        all_events = []  # list of (event_dict, tournament_name)
        all_events_by_norm = {}  # (norm_home, norm_away) -> [event_dict]
        all_events_by_id = {}  # event_id -> event_dict

        # Collect all dates from missing matches
        dates_to_fetch = set()
        for m in missing:
            md = m['match_date']
            if md:
                d = datetime.strptime(md, '%Y-%m-%d').date()
                for offset in range(-2, 5):
                    dates_to_fetch.add(str(d + timedelta(days=offset)))
        # Also add match_date itself
        dates_to_fetch.add(str(match_date))
        for offset in range(-2, 5):
            dates_to_fetch.add(str(match_date + timedelta(days=offset)))

        for d in sorted(dates_to_fetch):
            try:
                url = f"https://oddsfe.com/bind/schedule/football/{d}"
                s = requests.Session()
                s.trust_env = False
                r = s.get(url, headers=headers, timeout=20, verify=False)
                if r.status_code == 200:
                    data = r.json()
                    for t in data:
                        tournament_name = t.get('tournament_name', '') or t.get('name', '')
                        for ev in t.get('events', []):
                            h = ev.get('team_home_name', '').strip()
                            a = ev.get('team_away_name', '').strip()
                            eid = str(ev.get('event_id', ''))
                            start = ev.get('event_start_at', '')
                            if eid and h and a:
                                ev_dict = {
                                    'event_id': eid,
                                    'start': start,
                                    'home_en': h,
                                    'away_en': a,
                                    'tournament': tournament_name,
                                }
                                all_events.append(ev_dict)
                                all_events_by_id[eid] = ev_dict
                                key = (_norm_team(h), _norm_team(a))
                                if key not in all_events_by_norm:
                                    all_events_by_norm[key] = []
                                all_events_by_norm[key].append(ev_dict)
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"Failed to fetch oddsfe schedule for {d}: {e}")

        # Helper: get all EN name variants for a CN team name
        def _get_en_variants(cn_name):
            variants = list(cn_to_en_all.get(cn_name.strip(), []))
            # Also try normalize_team_name
            if normalize_team_name:
                try:
                    alt = normalize_team_name(cn_name)
                    if alt and not any('一' <= c <= '鿿' for c in alt) and alt not in variants:
                        variants.append(alt)
                except Exception:
                    pass
            return variants

        post_commit_learning = []

        # Helper: update DB first; auto-learning runs after commit/close so it
        # cannot contend with this transaction's write lock.
        def _apply_match(lm_id, ev, h_cn, a_cn):
            try:
                start_str = ev['start']
                eid = ev['event_id']
                if 'T' in start_str:
                    utc_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    utc_dt = datetime.strptime(start_str[:19], '%Y-%m-%d %H:%M:%S')
                bj_dt = utc_dt + timedelta(hours=8)
                bj_str = bj_dt.strftime('%Y-%m-%d %H:%M')
                bj_date = bj_dt.strftime('%Y-%m-%d')
                bj_time = bj_dt.strftime('%H:%M:%S')

                cursor.execute("""
                    UPDATE lottery_matches
                    SET beijing_time = ?, oddsfe_event_id = ?,
                        match_date = ?, match_time = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                """, (bj_str, eid, bj_date, bj_time, lm_id))

                post_commit_learning.append((h_cn, ev['home_en'], a_cn, ev['away_en']))
                return True
            except Exception as e:
                logger.warning(f"Failed to set beijing_time for {lm_id}: {e}")
                return False

        # Match each match using 5 strategies
        # Skip matches that already have correct beijing_time from oddsfe (oddsfe_event_id set + beijing_time not derived from match_date+match_time)
        updated = 0
        for m in missing:
            lm_id = m['lottery_match_id']
            h_cn = (m['home_team_cn'] or '').strip()
            a_cn = (m['away_team_cn'] or '').strip()
            league_cn = (m.get('league_name_cn') or '').strip()

            # Skip if already bridged and beijing_time looks correct (not just match_date+match_time)
            existing_bt = m.get('beijing_time', '') or ''
            existing_eid = m.get('oddsfe_event_id', '') or ''
            md = m.get('match_date', '') or ''
            mt = m.get('match_time', '') or ''
            mt_short = mt[:5] if len(mt) > 5 else mt
            derived_bt = f"{md} {mt_short}" if md and mt else ''
            # If oddsfe_event_id exists AND beijing_time differs from naive match_date+match_time,
            # it was already corrected by oddsfe — skip
            if existing_eid and existing_bt and existing_bt != derived_bt:
                continue
            # If oddsfe_event_id exists AND beijing_time matches naive derivation, still skip
            # (it was already bridged, even if the time happens to match)
            if existing_eid and existing_bt:
                continue

            h_en_variants = _get_en_variants(h_cn)
            a_en_variants = _get_en_variants(a_cn)

            found = None
            match_strategy = None

            # === Strategy 1: Exact match with all EN name variants ===
            if h_en_variants and a_en_variants:
                for he in h_en_variants:
                    for ae in a_en_variants:
                        key = (_norm_team(he), _norm_team(ae))
                        candidates = all_events_by_norm.get(key, [])
                        if candidates:
                            # Pick best candidate by date proximity
                            found = self._pick_best_candidate(candidates, m['match_date'])
                            if found:
                                match_strategy = f'S1-exact({he} vs {ae})'
                                break
                    if found:
                        break
                # Also try reversed (oddsfe might swap home/away)
                if not found:
                    for he in h_en_variants:
                        for ae in a_en_variants:
                            key = (_norm_team(ae), _norm_team(he))
                            candidates = all_events_by_norm.get(key, [])
                            if candidates:
                                found = self._pick_best_candidate(candidates, m['match_date'])
                                if found:
                                    match_strategy = f'S1-rev({he} vs {ae})'
                                    break
                        if found:
                            break

            # === Strategy 2: Exact match with CN names (oddsfe might have CN) ===
            if not found:
                key = (_norm_team(h_cn), _norm_team(a_cn))
                candidates = all_events_by_norm.get(key, [])
                if candidates:
                    found = self._pick_best_candidate(candidates, m['match_date'])
                    if found:
                        match_strategy = 'S2-cn-exact'

            # === Strategy 3: Single-team exact match (home first, then away) ===
            # Find all events where one team matches exactly, narrow by the other
            if not found:
                # Try home team first
                for he in h_en_variants:
                    h_norm = _norm_team(he)
                    candidates = []
                    for key, evs in all_events_by_norm.items():
                        if key[0] == h_norm:
                            # Check if away team partially matches
                            for ev in evs:
                                a_norm_ev = _norm_team(ev['away_en'])
                                for ae in a_en_variants:
                                    if _norm_team(ae) == a_norm_ev:
                                        candidates.append(ev)
                                        break
                    if len(candidates) == 1:
                        found = candidates[0]
                        match_strategy = f'S3-home-single({he})'
                        break
                    elif len(candidates) > 1:
                        # Multiple candidates, try to narrow by date
                        found = self._pick_best_candidate(candidates, m['match_date'])
                        if found:
                            match_strategy = f'S3-home-date({he})'
                            break

                # Try away team if home didn't work
                if not found:
                    for ae in a_en_variants:
                        a_norm = _norm_team(ae)
                        candidates = []
                        for key, evs in all_events_by_norm.items():
                            if key[1] == a_norm:
                                for ev in evs:
                                    h_norm_ev = _norm_team(ev['home_en'])
                                    for he in h_en_variants:
                                        if _norm_team(he) == h_norm_ev:
                                            candidates.append(ev)
                                            break
                        if len(candidates) == 1:
                            found = candidates[0]
                            match_strategy = f'S3-away-single({ae})'
                            break
                        elif len(candidates) > 1:
                            found = self._pick_best_candidate(candidates, m['match_date'])
                            if found:
                                match_strategy = f'S3-away-date({ae})'
                                break

            # === Strategy 4: Word-root match ===
            # e.g. "czechia" matches "czech republic" via "czech" root
            if not found:
                h_search = (h_en_variants[0] if h_en_variants else h_cn).lower()
                a_search = (a_en_variants[0] if a_en_variants else a_cn).lower()
                h_roots = [w for w in h_search.split() if len(w) >= 4]
                a_roots = [w for w in a_search.split() if len(w) >= 4]
                if h_roots and a_roots:
                    candidates = []
                    for key, evs in all_events_by_norm.items():
                        k_h_words = [w for w in key[0].split() if len(w) >= 4]
                        k_a_words = [w for w in key[1].split() if len(w) >= 4]
                        h_root_match = any(hw in kw or kw in hw for hw in h_roots for kw in k_h_words)
                        a_root_match = any(aw in kw or kw in aw for aw in a_roots for kw in k_a_words)
                        if h_root_match and a_root_match:
                            candidates.extend(evs)
                    if len(candidates) == 1:
                        found = candidates[0]
                        match_strategy = 'S4-word-root'
                    elif len(candidates) > 1:
                        found = self._pick_best_candidate(candidates, m['match_date'])
                        if found:
                            match_strategy = 'S4-word-root-date'

            # === Strategy 5: Time-window match ===
            # Convert match_date+match_time to UTC, find events within +/-2h
            if not found:
                match_time_str = m.get('match_time') or ''
                if m['match_date'] and match_time_str:
                    try:
                        # match_time from sporttery is Beijing time
                        mt_short = match_time_str[:5] if len(match_time_str) > 5 else match_time_str
                        bj_approx = datetime.strptime(f"{m['match_date']} {mt_short}", '%Y-%m-%d %H:%M')
                        utc_approx = bj_approx - timedelta(hours=8)
                        # Search all events for ones within +/-2h UTC
                        candidates = []
                        for ev in all_events:
                            try:
                                start_str = ev['start']
                                if 'T' in start_str:
                                    ev_utc = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                                else:
                                    ev_utc = datetime.strptime(start_str[:19], '%Y-%m-%d %H:%M:%S')
                                diff_hours = abs((ev_utc - utc_approx).total_seconds()) / 3600
                                if diff_hours <= 2:
                                    candidates.append((ev, diff_hours))
                            except (ValueError, TypeError):
                                continue
                        if len(candidates) == 1:
                            found = candidates[0][0]
                            match_strategy = f'S5-time-window({candidates[0][1]:.1f}h)'
                        elif len(candidates) > 1:
                            # Sort by time proximity, pick closest
                            candidates.sort(key=lambda x: x[1])
                            # If multiple within 2h, try to narrow by team name similarity
                            best = None
                            best_score = 0
                            for ev, dh in candidates:
                                score = 0
                                h_ev = ev['home_en'].lower()
                                a_ev = ev['away_en'].lower()
                                for he in h_en_variants:
                                    if he.lower() in h_ev or h_ev in he.lower():
                                        score += 1
                                        break
                                for ae in a_en_variants:
                                    if ae.lower() in a_ev or a_ev in ae.lower():
                                        score += 1
                                        break
                                # Also check CN names
                                if h_cn.lower() in h_ev or h_ev in h_cn.lower():
                                    score += 0.5
                                if a_cn.lower() in a_ev or a_ev in a_cn.lower():
                                    score += 0.5
                                if score > best_score:
                                    best_score = score
                                    best = ev
                            if best and best_score >= 1:
                                found = best
                                match_strategy = f'S5-time-window-narrow(score={best_score})'
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Time-window parse error for {lm_id}: {e}")

            # Apply the match
            if found:
                if _apply_match(lm_id, found, h_cn, a_cn):
                    updated += 1
                    logger.info(f"Bridge {match_strategy}: {h_cn} vs {a_cn} -> eid={found['event_id']}, bj={found['start']}")
            else:
                logger.debug(f"Could not find oddsfe match for {lm_id} ({h_cn} vs {a_cn})")

        # Fallback: for matches still missing beijing_time, use match_date+match_time
        # sporttery match_time is Beijing time, match_date may be sales-period date
        cursor.execute("""
            SELECT lottery_match_id, match_date, match_time FROM lottery_matches
            WHERE beijing_time IS NULL AND match_time IS NOT NULL
              AND match_date BETWEEN ? AND ?
        """, (window_start, window_end))
        fallback_rows = cursor.fetchall()
        for row in fallback_rows:
            lm_id = row[0]
            md = row[1]
            mt = row[2] or ''
            mt_short = mt[:5] if len(mt) > 5 else mt
            if md and mt_short:
                derived_bt = f"{md} {mt_short}"
                cursor.execute("""
                    UPDATE lottery_matches SET beijing_time = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ?
                """, (derived_bt, lm_id))
                logger.info(f"Fallback beijing_time for {lm_id}: {derived_bt}")

        conn.commit()

        # Also update sell_status
        self._update_sell_status(cursor, conn)

        conn.close()

        for h_cn, h_en, a_cn, a_en in post_commit_learning:
            self._auto_learn_mapping(h_cn, h_en, a_cn, a_en)

        return updated

    def _pick_best_candidate(self, candidates, match_date_str):
        """Pick the best candidate from multiple oddsfe events by date proximity."""
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        try:
            match_d = datetime.strptime(match_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return candidates[0]

        best = None
        best_diff = 999
        for cand in candidates:
            try:
                start_str = cand['start']
                if 'T' in start_str:
                    utc_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    utc_dt = datetime.strptime(start_str[:19], '%Y-%m-%d %H:%M:%S')
                bj_dt = utc_dt + timedelta(hours=8)
                diff = abs((bj_dt.date() - match_d).days)
                if diff < best_diff:
                    best_diff = diff
                    best = cand
            except (ValueError, TypeError):
                continue
        if best and best_diff <= 3:
            return best
        return candidates[0]

    def _update_sell_status(self, cursor, conn):
        """Auto-update sell_status based on beijing_time and results."""
        # Matches whose beijing_time has passed but still 'selling' -> 'closed'
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'closed'
            WHERE sell_status = 'selling'
            AND beijing_time IS NOT NULL
            AND datetime(beijing_time) < datetime('now', '+8 hours')
        """)
        closed = cursor.rowcount

        # Matches with results but still 'closed' -> 'finished'
        cursor.execute("""
            UPDATE lottery_matches SET sell_status = 'finished'
            WHERE sell_status IN ('closed', 'selling')
            AND lottery_match_id IN (SELECT lottery_match_id FROM lottery_results)
        """)
        finished = cursor.rowcount

        conn.commit()
        if closed or finished:
            logger.info(f"Auto sell_status: {closed} closed, {finished} finished")


    def _auto_learn_mapping(self, h_cn: str, h_en: str, a_cn: str, a_en: str):
        """�Զ�ѧϰCN��EN����ӳ��: д��JSON + д��DB team_name_mapping"""
        # �ж��Ƿ���Ҫѧϰ (CN��EN��ͬ��EN��������)
        for cn, en in [(h_cn, h_en), (a_cn, a_en)]:
            if cn == en:
                continue
            if any('\u4e00' <= c <= '\u9fff' for c in en):
                continue
            if cn in self._cn_to_en and self._cn_to_en[cn] == en:
                continue  # ��֪ӳ��

            # д��JSON
            _save_cn_en_mapping(cn, en)

            # �����ڴ滺��
            self._cn_to_en[cn] = en

            # д��DB team_name_mapping (����ж�Ӧteam_id)
            conn = None
            try:
                conn = sqlite3.connect(self.db_path, timeout=30)
                conn.execute("PRAGMA busy_timeout=30000")
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

                    # ����EntityMapper����
                    self.mapper._team_name_cache[cn] = team_id
                    logger.info(f'Auto-learned mapping: {cn} -> {en} (team_id={team_id})')
                conn.close()
            except Exception as e:
                logger.debug(f'Auto-learn DB error: {e}')
            finally:
                if conn is not None:
                    conn.close()

    def _insert_odds_with_snapshot(self, lottery_match_id: str, play_type: str,
                                   odds_data: Dict, snapshot_type: str = 'opening'):
        """�������ʲ���ǿ�������

        �߼�:
        - �״β���: odds_data=opening, opening_odds=opening, snapshot_type='opening'
        - ��������: odds_data=latest, latest_odds=latest, snapshot_type='latest'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # ����Ƿ�����opening����
            cursor.execute("""
                SELECT 1 FROM lottery_odds
                WHERE lottery_match_id = ? AND play_type = ? AND snapshot_type = 'opening'
            """, (lottery_match_id, play_type))
            has_opening = cursor.fetchone() is not None

            odds_json = json.dumps(odds_data)

            if snapshot_type == 'opening' and not has_opening:
                # �״�=opening����
                cursor.execute("""
                    INSERT OR REPLACE INTO lottery_odds
                    (lottery_match_id, play_type, odds_data, opening_odds, snapshot_type, update_time)
                    VALUES (?, ?, ?, ?, 'opening', CURRENT_TIMESTAMP)
                """, (lottery_match_id, play_type, odds_json, odds_json))
            else:
                # ����=latest����
                cursor.execute("""
                    UPDATE lottery_odds
                    SET odds_data = ?, latest_odds = ?, snapshot_type = 'latest',
                        update_time = CURRENT_TIMESTAMP
                    WHERE lottery_match_id = ? AND play_type = ?
                """, (odds_json, odds_json, lottery_match_id, play_type))

                if cursor.rowcount == 0:
                    # û�����м�¼��ֱ�Ӳ���
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

    def _link_to_system_matches(self, lottery_match_ids: List[str]) -> int:
        """Link lottery_matches to system matches table via team_id + date matching"""
        if not lottery_match_ids:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        placeholders = ','.join(['?'] * len(lottery_match_ids))

        # Update lottery_matches.match_id
        cursor.execute(f"""
            UPDATE lottery_matches SET match_id = (
                SELECT m.match_id FROM matches m
                WHERE m.match_date = lottery_matches.match_date
                  AND m.home_team_id = lottery_matches.home_team_id
                  AND m.away_team_id = lottery_matches.away_team_id
                LIMIT 1
            ) WHERE lottery_match_id IN ({placeholders})
              AND match_id IS NULL
              AND home_team_id IS NOT NULL
              AND away_team_id IS NOT NULL
        """, lottery_match_ids)
        linked = cursor.rowcount

        # Also update source_mapping_bridge.system_match_id
        cursor.execute(f"""
            UPDATE source_mapping_bridge SET system_match_id = (
                SELECT m.match_id FROM matches m
                JOIN lottery_matches lm ON lm.lottery_match_id = source_mapping_bridge.lottery_issue_num
                WHERE m.match_date = lm.match_date
                  AND m.home_team_id = lm.home_team_id
                  AND m.away_team_id = lm.away_team_id
                LIMIT 1
            ) WHERE lottery_issue_num IN ({placeholders})
              AND system_match_id IS NULL
        """, lottery_match_ids)
        bridge_linked = cursor.rowcount

        conn.commit()
        conn.close()

        if linked > 0:
            logger.info(f'Linked {linked} lottery_matches to system matches')
        if bridge_linked > 0:
            logger.info(f'Linked {bridge_linked} bridge records to system matches')

        return linked

    def sync_results(self, match_date: date = None) -> Dict:
        """
        ͬ��������� �� sporttery���� + oddsfe��BQC

        ȥ�ز���: ��ɾ�����н�����ٲ����½�� (��֤1:1)
        """
        if match_date is None:
            match_date = date.today()
        run_id = self.foundation.start_run(
            run_type='sporttery_results',
            match_date=match_date,
            trigger_source='manual_or_scheduler',
            summary={'stage': 'crawl_results'},
        )

        # 1. sporttery���
        raw_results = self.crawler.crawl_results_sync(match_date)
        self.foundation.record_artifact(
            run_id=run_id,
            source_name='sporttery_results',
            source_type='crawler',
            entity_type='match_date_results',
            entity_id=str(match_date),
            payload=raw_results,
            confidence=0.75,
        )

        saved = 0
        total = 0

        # 1. sporttery 结果采集（如果失败，则用 oddsfe 补充）
        if raw_results:
            for result in raw_results:
                total += 1
                try:
                    lm_id = result.get('lottery_match_id') or result.get('matchId')
                    if not lm_id:
                        continue
                    self.foundation.record_artifact(
                        run_id=run_id,
                        source_name='sporttery_results',
                        source_type='crawler',
                        entity_type='lottery_match_result',
                        entity_id=lm_id,
                        payload=result,
                        confidence=0.8,
                    )

                    result_data = {
                        'lottery_match_id': lm_id,
                        'home_goals_ft': self._safe_int(result.get('home_goals_ft') or result.get('homeScore')),
                        'away_goals_ft': self._safe_int(result.get('away_goals_ft') or result.get('awayScore')),
                        'home_goals_ht': self._safe_int(result.get('home_goals_ht') or result.get('homeScoreHt')),
                        'away_goals_ht': self._safe_int(result.get('away_goals_ht') or result.get('awayScoreHt')),
                        'home_goals_90min': self._safe_int(result.get('home_goals_90min')),
                        'away_goals_90min': self._safe_int(result.get('away_goals_90min')),
                        'match_end_type': result.get('match_end_type'),
                        'spf_result': result.get('spf_result') or result.get('spfResult'),
                        'bf_result': result.get('bf_result') or result.get('bfResult'),
                        'bqc_result': _normalize_bqc_result(result.get('bqc_result') or result.get('bqcResult')),
                        'rqspf_result': result.get('rqspf_result') or result.get('rqspfResult'),
                    }

                    # 从 sporttery 结果推导其他玩法（如果源数据明确）
                    result_data = self._fill_derived_results(result_data)

                    # INSERT OR REPLACE 利用 UNIQUE(lottery_match_id) 去重
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    try:
                        # Check if result already exists
                        cursor.execute(
                            "SELECT lottery_match_id, home_goals_90min, away_goals_90min, match_end_type, spf_result, bqc_result FROM lottery_results WHERE lottery_match_id = ?",
                            (lm_id,)
                        )
                        existing_row = cursor.fetchone()

                        if existing_row:
                            # Update only missing fields, preserve 90min/end_type/spf_result
                            updates = []
                            params = []
                            if result_data.get('home_goals_ft') is not None:
                                updates.append('home_goals_ft = ?')
                                params.append(result_data['home_goals_ft'])
                            if result_data.get('away_goals_ft') is not None:
                                updates.append('away_goals_ft = ?')
                                params.append(result_data['away_goals_ft'])
                            if result_data.get('home_goals_ht') is not None and existing_row[1] is None:
                                updates.append('home_goals_ht = ?')
                                params.append(result_data['home_goals_ht'])
                            if result_data.get('away_goals_ht') is not None and existing_row[2] is None:
                                updates.append('away_goals_ht = ?')
                                params.append(result_data['away_goals_ht'])
                            if result_data.get('spf_result') and existing_row[4] is None:
                                updates.append('spf_result = ?')
                                params.append(result_data['spf_result'])
                            if result_data.get('bf_result') and not existing_row[4]:
                                updates.append('bf_result = ?')
                                params.append(result_data['bf_result'])
                            if result_data.get('bqc_result') and existing_row[5] is None:
                                updates.append('bqc_result = ?')
                                params.append(result_data['bqc_result'])
                            if result_data.get('rqspf_result') is None:
                                updates.append('rqspf_result = ?')
                                params.append(result_data.get('rqspf_result'))
                            # Never overwrite 90min/end_type from sporttery data
                            if updates:
                                sql = f"UPDATE lottery_results SET {', '.join(updates)} WHERE lottery_match_id = ?"
                                params.append(lm_id)
                                cursor.execute(sql, params)
                        else:
                            # Insert new result
                            cursor.execute("""
                                INSERT INTO lottery_results
                                (lottery_match_id, home_goals_ft, away_goals_ft,
                                 home_goals_ht, away_goals_ht,
                                 home_goals_90min, away_goals_90min, match_end_type,
                                 spf_result, bf_result, bqc_result, rqspf_result)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                lm_id,
                                result_data.get('home_goals_ft'),
                                result_data.get('away_goals_ft'),
                                result_data.get('home_goals_ht'),
                                result_data.get('away_goals_ht'),
                                result_data.get('home_goals_90min'),
                                result_data.get('away_goals_90min'),
                                result_data.get('match_end_type'),
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
                logger.error(f"Result processing error: {e}")

        # 2. oddsfe��BQC (sporttery����ȱ�볡�ȷ�)
        # 2. oddsfe �����������������ȷ�+BQC��
        oddsfe_filled = self._supplement_results_from_oddsfe(match_date)

        result = {
            'success': True,
            'date': str(match_date),
            'saved': saved,
            'total': total,
            'oddsfe_filled': oddsfe_filled,
            'bqc_filled': oddsfe_filled
        }
        self.foundation.finish_run(run_id, status='success', summary=result)
        return result

    def _supplement_bqc_from_oddsfe(self, match_date: date) -> int:
        """��oddsfe score_details����ȱʧ��BQC�Ͱ볡�ȷ�"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # ����ȱBQC��볡�ȷֵĽ��
        date_str = match_date.strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT lr.rowid AS result_rowid, lr.result_id, lr.lottery_match_id,
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
            event_status = str(event_data.get('event_status') or '').upper()
            if event_status and event_status not in ('FINISHED', 'FT', 'ENDED', 'AET', 'AP'):
                continue
            score_details = event_data.get('score_details', '')
            parsed = _parse_score_details(score_details)
            if not parsed or 'ht' not in parsed:
                continue

            ht_home, ht_away = parsed['ht']
            ft_home, ft_away, home_90, away_90, end_type = _event_fulltime_score(event_data, parsed)
            if ft_home is None or ft_away is None:
                ft_home, ft_away = row['home_goals_ft'], row['away_goals_ft']
            if ft_home is None or ft_away is None:
                continue

            # �Ƶ�BQC
            # For SPF/BQC: use 90min scores (AET/AP matches settle on 90min)
            spf_home = home_90 if home_90 is not None else ft_home
            spf_away = away_90 if away_90 is not None else ft_away
            handicap = _effective_handicap(self.db_path, row['lottery_match_id'], row.get('handicap_line', 0) or 0)
            derived = _derive_play_types(
                spf_home, spf_away, ht_home, ht_away,
                handicap
            )

            # ����
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
                resolved_bqc = _resolve_bqc_result(
                    spf_home,
                    spf_away,
                    ht_home,
                    ht_away,
                    source_bqc=row.get('bqc_result'),
                    source_name='oddsfe_event',
                    lottery_match_id=row.get('lottery_match_id'),
                )
                if resolved_bqc and _normalize_bqc_result(row.get('bqc_result')) != resolved_bqc:
                    updates.append('bqc_result = ?')
                    params.append(resolved_bqc)
                # Write 90min and end_type fields for AET/AP matches
                if home_90 is not None:
                    updates.append('home_goals_90min = ?')
                    params.append(home_90)
                if away_90 is not None:
                    updates.append('away_goals_90min = ?')
                    params.append(away_90)
                if end_type != 'FT':
                    updates.append('match_end_type = ?')
                    params.append(end_type)

                if updates:
                    sql = f"UPDATE lottery_results SET {', '.join(updates)} WHERE rowid = ?"
                    params.append(row['result_rowid'])
                    cursor.execute(sql, params)
                    conn.commit()
                    filled += 1
                    logger.info(f'Supplemented BQC for {row["lottery_match_id"]}: {resolved_bqc}')
            except Exception as e:
                logger.debug(f'BQC supplement error: {e}')
            finally:
                conn.close()

            time.sleep(0.2)  # ����

        return filled

    def _supplement_results_from_oddsfe(self, match_date: date) -> int:
        """�� oddsfe score_details ����������������� sporttery ʧ��ʱ�������ȷ֣�"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # ������Ҫ�������ı�����
        # 1. ���� oddsfe_event_id ��û�н��
        # 2. ������������ȱ�볡/BQC��
        date_str = match_date.strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT lm.lottery_match_id, lm.home_team_cn, lm.away_team_cn,
                   lm.oddsfe_event_id, lm.handicap_line,
                   lr.home_goals_ft, lr.away_goals_ft, lr.home_goals_ht, lr.away_goals_ht,
                   lr.bqc_result, lr.spf_result, lr.bf_result, lr.rqspf_result,
                   lr.home_goals_90min, lr.away_goals_90min, lr.match_end_type,
                   lr.penalty_home, lr.penalty_away,
                   CASE WHEN lr.lottery_match_id IS NULL THEN 0 ELSE 1 END AS has_result
            FROM lottery_matches lm
            LEFT JOIN lottery_results lr ON lm.lottery_match_id = lr.lottery_match_id
            WHERE lm.match_date = ?
              AND lm.oddsfe_event_id IS NOT NULL
              AND (lr.lottery_match_id IS NULL OR lr.home_goals_ht IS NULL OR lr.bqc_result IS NULL
                   OR lr.home_goals_90min IS NULL OR lr.match_end_type IS NULL)
        """, (date_str,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not rows:
            return 0

        filled = 0
        for row in rows:
            eid = row['oddsfe_event_id']
            lm_id = row['lottery_match_id']
            if not eid:
                continue

            # ��ȡ oddsfe event ����
            event_data = _oddsfe_fetch_score_details(eid)
            event_status = str(event_data.get('event_status') or '').upper()
            if event_status and event_status not in ('FINISHED', 'FT', 'ENDED', 'AET', 'AP'):
                continue
            score_details = event_data.get('score_details', '')
            if not score_details:
                continue

            # �����ȷ�
            parsed = _parse_score_details(score_details)
            if not parsed:
                continue

            ht_home, ht_away = parsed.get('ht', (None, None))
            ft_home, ft_away, home_90, away_90, end_type = _event_fulltime_score(event_data, parsed)
            if ft_home is None or ft_away is None:
                ft_home, ft_away = row['home_goals_ft'], row['away_goals_ft']

            if ft_home is None or ft_away is None:
                continue

            # �Ƶ�ȫ���淨���
            handicap = _effective_handicap(self.db_path, lm_id, row.get('handicap_line') or 0)
            # For SPF/BQC/OU: use 90min scores (AET/AP matches settle on 90min)
            spf_home = home_90 if home_90 is not None else ft_home
            spf_away = away_90 if away_90 is not None else ft_away
            derived = _derive_play_types(spf_home, spf_away, ht_home, ht_away, handicap)

            # �������½��
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                # ����Ƿ����н��
                cursor.execute("SELECT lottery_match_id FROM lottery_results WHERE lottery_match_id = ?", (lm_id,))
                existing = cursor.fetchone()

                if existing:
                    # ����
                    updates = []
                    params = []
                    if row['home_goals_ft'] is None:
                        updates.append('home_goals_ft = ?')
                        params.append(ft_home)
                    elif end_type in ('AET', 'AP') and ft_home is not None and row['home_goals_ft'] != ft_home:
                        # AET/AP: home_goals_ft should exclude penalties, force correct value
                        updates.append('home_goals_ft = ?')
                        params.append(ft_home)
                    if row['away_goals_ft'] is None:
                        updates.append('away_goals_ft = ?')
                        params.append(ft_away)
                    elif end_type in ('AET', 'AP') and ft_away is not None and row['away_goals_ft'] != ft_away:
                        updates.append('away_goals_ft = ?')
                        params.append(ft_away)
                    if row['home_goals_ht'] is None and ht_home is not None:
                        updates.append('home_goals_ht = ?')
                        params.append(ht_home)
                    if row['away_goals_ht'] is None and ht_away is not None:
                        updates.append('away_goals_ht = ?')
                        params.append(ht_away)
                    resolved_bqc = _resolve_bqc_result(
                        spf_home,
                        spf_away,
                        ht_home,
                        ht_away,
                        source_bqc=row.get('bqc_result'),
                        source_name='oddsfe_event',
                        lottery_match_id=lm_id,
                    )
                    if resolved_bqc and _normalize_bqc_result(row.get('bqc_result')) != resolved_bqc:
                        updates.append('bqc_result = ?')
                        params.append(resolved_bqc)
                    if not row.get('spf_result') and derived.get('spf_result'):
                        updates.append('spf_result = ?')
                        params.append(derived['spf_result'])
                    elif end_type in ('AET', 'AP') and derived.get('spf_result'):
                        # AET/AP: SPF must be based on 90min, force update if wrong
                        if row.get('spf_result') != derived['spf_result']:
                            updates.append('spf_result = ?')
                            params.append(derived['spf_result'])
                    if not row.get('bf_result'):
                        updates.append('bf_result = ?')
                        params.append(f"{spf_home}:{spf_away}")
                    if not row.get('rqspf_result') and derived.get('rqspf_result'):
                        updates.append('rqspf_result = ?')
                        params.append(derived['rqspf_result'])
                    # Write 90min and end_type fields for AET/AP matches
                    if home_90 is not None and row.get('home_goals_90min') is None:
                        updates.append('home_goals_90min = ?')
                        params.append(home_90)
                    elif end_type in ('AET', 'AP') and home_90 is not None and row.get('home_goals_90min') != home_90:
                        updates.append('home_goals_90min = ?')
                        params.append(home_90)
                    if away_90 is not None and row.get('away_goals_90min') is None:
                        updates.append('away_goals_90min = ?')
                        params.append(away_90)
                    elif end_type in ('AET', 'AP') and away_90 is not None and row.get('away_goals_90min') != away_90:
                        updates.append('away_goals_90min = ?')
                        params.append(away_90)
                    if end_type != 'FT' and not row.get('match_end_type'):
                        updates.append('match_end_type = ?')
                        params.append(end_type)
                    elif end_type != 'FT' and row.get('match_end_type') != end_type:
                        updates.append('match_end_type = ?')
                        params.append(end_type)
                    # Write penalty scores for AP matches
                    pen = parsed.get('pen') if parsed else None
                    if pen and end_type == 'AP':
                        pen_home, pen_away = pen
                        if row.get('penalty_home') is None or row.get('penalty_home') != pen_home:
                            updates.append('penalty_home = ?')
                            params.append(pen_home)
                        if row.get('penalty_away') is None or row.get('penalty_away') != pen_away:
                            updates.append('penalty_away = ?')
                            params.append(pen_away)

                    if updates:
                        sql = f"UPDATE lottery_results SET {', '.join(updates)} WHERE lottery_match_id = ?"
                        params.append(lm_id)
                        cursor.execute(sql, params)
                        filled += 1
                        logger.info(f'oddsfe supplemented result for {lm_id}: {ft_home}-{ft_away}')
                else:
                    # �����½��
                    cursor.execute("""
                        INSERT INTO lottery_results
                        (lottery_match_id, home_goals_ft, away_goals_ft,
                         home_goals_ht, away_goals_ht,
                         home_goals_90min, away_goals_90min, match_end_type,
                         spf_result, bf_result, bqc_result, rqspf_result)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lm_id, ft_home, ft_away, ht_home, ht_away,
                        home_90, away_90, end_type,
                        derived.get('spf_result'), f"{spf_home}:{spf_away}",
                        _resolve_bqc_result(
                            spf_home,
                            spf_away,
                            ht_home,
                            ht_away,
                            source_name='oddsfe_event',
                            lottery_match_id=lm_id,
                        ),
                        derived.get('rqspf_result')
                    ))
                    filled += 1
                    logger.info(f'oddsfe inserted result for {lm_id}: {ft_home}-{ft_away}')

                conn.commit()
            except Exception as e:
                logger.debug(f'oddsfe supplement error: {e}')
            finally:
                conn.close()

            time.sleep(0.2)

        return filled

    def _fill_derived_results(self, result_data: Dict) -> Dict:
        """�ӱȷ��Ƶ�ȱʧ���淨���"""
        ft_h = result_data.get('home_goals_ft')
        ft_a = result_data.get('away_goals_ft')
        ht_h = result_data.get('home_goals_ht')
        ht_a = result_data.get('away_goals_ht')

        # For SPF/BQC/OU: use 90min scores when available (AET/AP matches)
        h90 = result_data.get('home_goals_90min')
        a90 = result_data.get('away_goals_90min')
        spf_h = h90 if h90 is not None else ft_h
        spf_a = a90 if a90 is not None else ft_a

        if ft_h is not None and ft_a is not None:
            # ��ȡhandicap_line
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
                handicap = _effective_handicap(self.db_path, lm_id, handicap)

            source_bqc = result_data.get('bqc_result')
            result_data['bqc_result'] = _resolve_bqc_result(
                spf_h,
                spf_a,
                ht_h,
                ht_a,
                source_bqc=source_bqc,
                source_name='sporttery_results',
                lottery_match_id=lm_id,
            )
            derived = _derive_play_types(spf_h, spf_a, ht_h, ht_a, handicap)

            # ֻ���ȱʧ��
            if not result_data.get('spf_result'):
                result_data['spf_result'] = derived.get('spf_result')
            if not result_data.get('bf_result'):
                result_data['bf_result'] = derived.get('bf_result')
            if not result_data.get('rqspf_result'):
                result_data['rqspf_result'] = derived.get('rqspf_result')

        return result_data

    def sync_odds(self, lottery_match_id: str, play_types: List[str] = None) -> Dict:
        """
        ͬ���������� �� ��ǰ��������matchInfoһ�����

        �˷��������ֶ�ˢ�µ�������(����Ҫ��������ʱ)
        """
        return {
            'success': True,
            'note': 'Odds are synced with matches via sync_daily_matches()',
            'lottery_match_id': lottery_match_id
        }

    def get_sync_status(self) -> Dict:
        """��ȡͬ��״̬"""
        today = date.today()
        today_matches = self.match_dao.find_by_date(str(today))
        pending = self.match_dao.find_pending_analysis()

        return {
            'today_matches': len(today_matches),
            'pending_analysis': len(pending),
            'last_sync': datetime.now().isoformat()
        }

    def _auto_register_team(self, cn_name: str) -> Optional[int]:
        """Auto-register team mapping: normalize to English, then try teams table.

        If normalize fails (returns Chinese), try pypinyin as fallback.
        If that also fails, try registering a new team entry with the pinyin name.
        """
        try:
            from fetchers.common.team_names import normalize_team_name
            en_name = normalize_team_name(cn_name)

            # If normalize returned Chinese characters, try pypinyin
            if en_name == cn_name or any('一' <= c <= '鿿' for c in en_name):
                en_name = self._pinyin_fallback(cn_name)
                if not en_name:
                    return None

            # Search teams table
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT team_id FROM teams WHERE name_en = ? COLLATE NOCASE LIMIT 1",
                (en_name,)
            )
            row = cursor.fetchone()

            if row:
                team_id = row[0]
                conn.close()
                self.mapper.register_team_mapping(cn_name, team_id, method='auto_normalize')
                logger.info('Auto-register mapping: %s -> team_id=%d', cn_name, team_id)
                return team_id

            # Team not in table -- register a new entry
            cursor.execute("""
                INSERT INTO teams (name_en, name_cn)
                VALUES (?, ?)
            """, (en_name, cn_name))
            team_id = cursor.lastrowid
            conn.commit()
            conn.close()
            self.mapper.register_team_mapping(cn_name, team_id, method='auto_create')
            logger.info('Auto-create team: %s -> %s (team_id=%d)', cn_name, en_name, team_id)
            return team_id

        except Exception as e:
            logger.debug('Auto-register failed %s: %s', cn_name, e)

        return None

    def _pinyin_fallback(self, cn_name: str) -> str:
        """Convert Chinese name to pinyin when normalize fails."""
        try:
            from pypinyin import lazy_pinyin, Style
            parts = lazy_pinyin(cn_name, style=Style.NORMAL)
            en_name = ''.join(parts).title()
            if en_name and not any('一' <= c <= '鿿' for c in en_name):
                return en_name
        except ImportError:
            logger.debug('pypinyin not installed, skipping pinyin fallback')
        return ''

    @staticmethod
    def _safe_int(val) -> Optional[int]:
        """��ȫ����ת��"""
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def close(self):
        """������Դ"""
        pass
