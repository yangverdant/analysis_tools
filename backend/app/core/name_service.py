"""统一名称服务 — 所有队名/联赛名映射的唯一入口

设计原则:
  1. 单一规范化函数 (替代4处重复的_norm_team/_norm_name)
  2. 单一CN↔EN查找 (合并8处散落的映射字典)
  3. 自动学习: 发现新映射时持久化到DB+JSON
  4. 所有调用者委托给此服务

用法:
  from backend.app.core.name_service import NameService
  ns = NameService(db_path)
  cn = ns.to_cn('Qarabag')           # → '卡拉巴赫'
  en = ns.to_en('卡拉巴赫')           # → 'Qarabag'
  norm = ns.normalize('Qarabag FK')   # → 'qarabag'
  ns.learn('卡拉巴赫', 'Qarabag')     # 持久化新映射
"""

import json
import os
import re
import unicodedata
import logging
from typing import Dict, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ── 路径 ──────────────────────────────────────────────
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_CN_EN_JSON = os.path.join(_PROJECT_ROOT, 'data', 'linkage', 'team_chinese_names.json')
_ALIASES_JSON = os.path.join(_PROJECT_ROOT, 'fetchers', 'common', 'data', 'team_aliases.json')

# ── Unicode特殊字符映射 (合并自sync_service/validate/oddsfe_event_sync) ──
_SPECIAL_CHARS = {
    'ø': 'o', 'å': 'a', 'æ': 'ae', 'ß': 'ss', 'đ': 'd', 'ł': 'l',
    'ń': 'n', 'ś': 's', 'ź': 'z', 'ż': 'z', 'ç': 'c', 'ğ': 'g',
    'ı': 'i', 'š': 's', 'č': 'c', 'ř': 'r', 'ž': 'z', 'ů': 'u',
    'ý': 'y', 'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a',
    'á': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'ó': 'o', 'ô': 'o',
    'ö': 'o', 'õ': 'o', 'ú': 'u', 'û': 'u', 'ü': 'u', 'ì': 'i',
    'í': 'i', 'î': 'i', 'ï': 'i',
}

# ── 后缀剥离 (合并自sync_service/validate/collect) ──
_SUFFIXES = [
    ' fc', ' cf', ' sc', ' afc', ' united', ' city', ' hotspur',
    ' athletic', ' county', ' town', ' rovers', ' villa', ' albion',
    ' forest', ' palace', ' rangers', ' celtic', ' wanderers', ' and hove',
    ' fk', ' sk', ' bk', ' ik', ' as', ' sa', ' paok', ' aek',
]

# ── 国家名别名 (合并自oddsfe_event_sync/football_data_wc_sync/build_team_id_mappings) ──
_COUNTRY_ALIASES = {
    'czechrepublic': 'czechia', 'czech': 'czechia',
    'southkorea': 'korearepublic', 'korea': 'korearepublic',
    'unitedstates': 'usa', 'unitedstatesofamerica': 'usa', 'usmnt': 'usa',
    'drcongo': 'congodr', 'drc': 'congodr', 'democraticrepublicofthecongo': 'congodr',
    'cotedivoire': 'ivorycoast', 'ivorycoast': 'ivorycoast',
    'bosniaherzegovina': 'bosniah', 'bosniaandherzegovina': 'bosniah',
    'bosnia': 'bosniah',
    'republicofireland': 'ireland',
    'northmacedonia': 'macedonia',
    'trinidadandtobago': 'trinidad',
    'antiguaandbarbuda': 'antigua',
    'saintkittsandnevis': 'saintkitts',
    'saintvincentandthegrenadines': 'saintvincent',
}

# ── 常见CN→EN别名 (合并自sync_service/validate/worldcup/team_names) ──
_CN_EN_EXTRA = {
    # 五大联赛
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
    # 国家队
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
    '匈牙利': 'Hungary', '罗马尼亚': 'Romania',
    '保加利亚': 'Bulgaria', '希腊': 'Greece',
    '墨西哥': 'Mexico', '哥伦比亚': 'Colombia',
    '智利': 'Chile', '秘鲁': 'Peru',
    '乌拉圭': 'Uruguay', '巴拉圭': 'Paraguay',
    '厄瓜多尔': 'Ecuador', '委内瑞拉': 'Venezuela',
    '玻利维亚': 'Bolivia', '哥斯达黎加': 'Costa Rica',
    '巴拿马': 'Panama', '洪都拉斯': 'Honduras',
    '牙买加': 'Jamaica', '海地': 'Haiti',
    '特立尼达和多巴哥': 'Trinidad and Tobago',
    '埃及': 'Egypt', '尼日利亚': 'Nigeria',
    '喀麦隆': 'Cameroon', '加纳': 'Ghana',
    '塞内加尔': 'Senegal', '科特迪瓦': 'Ivory Coast',
    '摩洛哥': 'Morocco', '突尼斯': 'Tunisia',
    '阿尔及利亚': 'Algeria', '南非': 'South Africa',
    '刚果': 'Congo DR', '马里': 'Mali',
    '布基纳法索': 'Burkina Faso', '几内亚': 'Guinea',
    '沙特阿拉伯': 'Saudi Arabia', '伊朗': 'Iran',
    '伊拉克': 'Iraq', '卡塔尔': 'Qatar',
    '阿联酋': 'United Arab Emirates', '乌兹别克斯坦': 'Uzbekistan',
    '泰国': 'Thailand', '越南': 'Vietnam',
    '印度尼西亚': 'Indonesia', '马来西亚': 'Malaysia',
    '菲律宾': 'Philippines', '印度': 'India',
    '新西兰': 'New Zealand', '加拿大': 'Canada',
    '古巴': 'Cuba', '以色列': 'Israel',
    '黑山': 'Montenegro', '斯洛文尼亚': 'Slovenia',
    '斯洛伐克': 'Slovakia', '白俄罗斯': 'Belarus',
    '格鲁吉亚': 'Georgia', '亚美尼亚': 'Armenia',
    '阿塞拜疆': 'Azerbaijan', '哈萨克斯坦': 'Kazakhstan',
    '立陶宛': 'Lithuania', '拉脱维亚': 'Latvia',
    '爱沙尼亚': 'Estonia', '塞浦路斯': 'Cyprus',
    '卢森堡': 'Luxembourg', '马耳他': 'Malta',
    '安道尔': 'Andorra', '法罗群岛': 'Faroe Islands',
    '直布罗陀': 'Gibraltar', '圣马力诺': 'San Marino',
    '列支敦士登': 'Liechtenstein', '摩尔多瓦': 'Moldova',
    '北马其顿': 'North Macedonia', '科索沃': 'Kosovo',
    '波黑': 'Bosnia-Herzegovina', '巴勒斯坦': 'Palestine',
    '约旦': 'Jordan', '阿曼': 'Oman',
    '巴林': 'Bahrain', '科威特': 'Kuwait',
    '叙利亚': 'Syria', '黎巴嫩': 'Lebanon',
    '塔吉克斯坦': 'Tajikistan', '吉尔吉斯斯坦': 'Kyrgyzstan',
    '土库曼斯坦': 'Turkmenistan', '缅甸': 'Myanmar',
    '柬埔寨': 'Cambodia', '新加坡': 'Singapore',
    '老挝': 'Laos', '文莱': 'Brunei',
    '东帝汶': 'Timor-Leste', '蒙古': 'Mongolia',
    '中华台北': 'Chinese Taipei', '中国香港': 'Hong Kong',
    '中国澳门': 'Macau', '朝鲜': 'North Korea',
    '中国国奥': 'China PR U23', '韩国国奥': 'South Korea U23',
    '日本国奥': 'Japan U23',
    # 常见俱乐部简称
    '大巴黎': 'Paris Saint Germain', '皇马': 'Real Madrid',
    '巴萨': 'Barcelona', '马体': 'Atletico Madrid',
    '斑马军团': 'Juventus', '老妇人': 'Juventus',
    '红魔': 'Manchester United', '蓝月亮': 'Manchester City',
    '枪手': 'Arsenal', '蓝军': 'Chelsea',
    '红军': 'Liverpool', '白百合': 'Tottenham',
    '大黄蜂': 'Borussia Dortmund', '南大王': 'Bayern Munich',
    '药厂': 'Bayer Leverkusen', '矿工': 'Shakhtar Donetsk',
    '老鹰': 'Crystal Palace', '铁锤帮': 'West Ham United',
    '喜鹊': 'Newcastle United', '狐狸城': 'Leicester City',
    '太妃糖': 'Everton', '圣徒': 'Southampton',
    '鹦鹉': 'Watford', '天鹅海': 'Swansea City',
    '灯笼裤': 'West Bromwich Albion', '陶工': 'Stoke City',
}

# ── EN→CN直接映射 (小联赛/欧战俱乐部, 补充team_chinese_names.json未覆盖的) ──
_EN_CN_DIRECT = {
    # 欧协联/欧联资格赛
    'Qarabag': '卡拉巴赫', 'Vestri': '韦斯特里', 'Dila Gori': '迪拉戈里',
    'Alashkert': '阿拉什克特', 'Yelimay Semey': '叶利迈塞梅',
    'Kalju': '卡柳', 'Hegelmann': '黑格尔曼', 'Paide': '派德',
    'S. Tiraspol': '蒂拉斯波尔', 'Aluminij': '铝业', 'Dyn. Kyiv': '基辅迪纳摩',
    'U. Cluj': '克卢日大学', 'Velez Mostar': '莫斯塔尔维莱兹',
    'Milsami': '米尔萨米', 'Marsaxlokk': '马尔萨什洛卡', 'Pyunik': '皮尤尼克',
    'Din. Minsk': '明斯克迪纳摩', 'Sileks': '西莱克斯',
    'Europa FC': '欧罗巴FC', 'CSKA Sofia': 'CSKA索菲亚',
    'Vojvodina': '伏伊伏丁那', 'Vllaznia': '弗拉兹尼亚', 'Malisheva': '马利舍瓦',
    'Glentoran': '格伦托兰', 'RFS': '里加FC', 'Penybont': '佩尼邦',
    'FC Santa Coloma': '圣科洛马FC', 'Petrovac': '彼得罗瓦茨',
    'Hamrun': '哈姆伦', 'Dinamo Tirana': '地拉那迪纳摩', 'FC Astana': '阿斯塔纳FC',
    'FK Sarajevo': '萨拉热窝', 'Stjarnan': '斯塔尔南',
    'Differdange': '迪弗丹日', 'Egnatia': '埃格纳蒂亚',
    'Caernarfon': '卡那封', 'Connahs Q.': '康纳斯码头',
    'Mondorf': '蒙多夫', 'FC Ballkani': '巴尔卡尼FC',
    'Atletic Escaldes': '阿特莱蒂克埃斯卡尔德斯',
    'St Josephs': '圣约瑟夫', 'Shkendija': '什肯迪亚',
    'Mornar Bar': '莫纳尔', 'Levski Sofia': '列夫斯基索菲亚',
    'Borac Banja Luka': '博拉茨', 'Sabah Baku': '萨巴赫',
    'UNA Strassen': '乌纳斯特拉森', 'AF Elbasani': '爱尔巴桑',
    'Zira': '齐拉', 'Torpedo Kutaisi': '库塔伊西鱼雷',
    'Iberia 1999': '伊比利亚1999', 'Petrocub': '彼得罗库布',
    'Zilina': '日利纳', 'Univ. Craiova': '克拉约瓦大学',
    'ML Vitebsk': '维捷布斯克',
    # 欧冠/欧联资格赛 (7月8日场次)
    'Kauno Zalgiris': '考纳斯扎尔吉里斯', 'Drita': '德里塔',
    'Inter Escaldes': '埃斯卡尔德斯国际', 'Ararat-Armenia': '阿拉拉特亚美尼亚',
    'Floriana': '弗洛里亚纳', 'Tre Fiori': '特雷菲奥里',
    'Larne': '拉恩', 'Bissen': '比森',
    'Vikingur Reykjavik': '雷克雅未克维京人', 'Gyor': '杰尔',
    'Kairat Almaty': '阿拉木图凯拉特', 'Sutjeska': '苏特耶斯卡',
    'Vardar': '瓦尔达尔', 'KuPS': '库奥皮奥',
    'Rafioreta': '拉菲奥里塔', 'Borisov': '鲍里索夫',
    'Shamrock Rovers': '沙姆洛克流浪', 'Lincoln Red Imps': '林肯红魔',
    'Sabail': '萨巴赫', 'Floriana': '弗洛里亚纳',
    # 巴西/南美
    'Ponte Preta': '庞特普雷塔', 'Criciuma': '克里西乌马',
    'Guayaquil City': '瓜亚基尔城', 'Ind. del Valle': '山谷独立',
    'Leones del Norte': '北方雄狮', 'Manta': '曼塔',
    'Sport Recife': '累西腓体育', 'Botafogo SP': '博塔弗戈SP',
    'Sao Bernardo': '圣贝尔纳多', 'Juventude': '尤文图德',
    'Vila Nova': '维拉诺瓦', 'Operario': '奥瓦里奥',
    # 芬兰/北欧
    'JaPS': '雅普斯', 'Jippo': '吉波', 'KaPa': '卡帕',
    'Klubi 04': '克卢比04', 'PK-35': 'PK-35', 'SJK Akatemia': 'SJK学院',
    'Tromsø': '特罗姆瑟', 'Vålerenga': '瓦勒伦加',
    'Odd': '奥德', 'Haugesund': '海于格松',
    # 韩国
    'Bucheon FC 1995': '富川FC1995', 'Hwaseong': '华城', 'Pohang': '浦项',
    'Ulsan HD': '蔚山HD',
    # 中国
    'Beijing Guoan': '北京国安', 'Chongqing Tonglianglong': '重庆铜梁龙',
    'Henan Songshan Longmen': '河南嵩山龙门', 'Qingdao West Coast': '青岛西海岸',
    'Shandong Taishan': '山东泰山', 'Wuhan Three Towns': '武汉三镇',
    'Yunnan Yukun': '云南玉昆',
    # 其他
    'TNS': '新圣徒', 'Decic': '德契奇',
}

# ── EN→CN反向映射 (从_CN_EN_EXTRA自动生成 + 直接映射) ──
_EN_CN_EXTRA = {v.lower(): k for k, v in _CN_EN_EXTRA.items() if not any(ord(c) > 127 for c in v)}
_EN_CN_EXTRA.update({k.lower(): v for k, v in _EN_CN_DIRECT.items()})


class NameService:
    """统一名称服务 — 单例模式"""

    _instance = None
    _cn_to_en: Dict[str, str] = {}
    _en_to_cn: Dict[str, str] = {}
    _loaded = False

    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = None):
        self._db_path = db_path
        if not self._loaded:
            self._load_all()
            self._loaded = True

    # ── 规范化 ─────────────────────────────────────────

    @staticmethod
    def normalize(name: str) -> str:
        """队名规范化: 去变音→小写→去后缀→国家别名

        替代: sync_service._norm_team, validate._norm_team,
              oddsfe_event_sync._norm_name, football_data_wc_sync._norm_name,
              build_team_id_mappings._norm, collect._strip_suffix
        """
        n = (name or '').strip().lower()
        # Unicode NFKD分解 + 去组合字符
        n = unicodedata.normalize('NFKD', n)
        n = ''.join(c for c in n if not unicodedata.combining(c))
        # 特殊字符替换
        n = ''.join(_SPECIAL_CHARS.get(c, c) for c in n)
        # 后缀剥离
        changed = True
        while changed:
            changed = False
            for sfx in _SUFFIXES:
                if n.endswith(sfx):
                    n = n[:-len(sfx)]
                    changed = True
        n = n.strip()
        # 国家别名
        n = _COUNTRY_ALIASES.get(n, n)
        return n

    @staticmethod
    def normalize_alpha(name: str) -> str:
        """纯字母数字规范化 (用于oddsfe匹配等场景)"""
        n = NameService.normalize(name)
        return re.sub(r'[^a-z0-9]', '', n)

    # ── CN↔EN查找 ──────────────────────────────────────

    def to_cn(self, name_en: str) -> Optional[str]:
        """英文名→中文名, 多级查找, 含自动学习"""
        if not name_en:
            return None
        # 1. 内存映射 (JSON + 额外 + 直接映射)
        key = name_en.strip()
        key_lower = key.lower()
        if key in self._en_to_cn:
            return self._en_to_cn[key]
        if key_lower in self._en_to_cn:
            return self._en_to_cn[key_lower]
        # 2. 规范化后查找
        norm = self.normalize(key)
        if norm in self._en_to_cn:
            return self._en_to_cn[norm]
        norm_alpha = self.normalize_alpha(key)
        if norm_alpha and norm_alpha in self._en_to_cn:
            return self._en_to_cn[norm_alpha]
        # 3. DB查找 (精确+规范化)
        if self._db_path:
            cn = self._db_lookup_en_to_cn(key)
            if cn:
                return cn
        # 4. 模糊匹配
        cn = self._fuzzy_to_cn(key)
        if cn:
            return cn
        # 5. DB深度模糊匹配 (normalize_alpha比较)
        if self._db_path:
            cn = self._db_deep_lookup_en_to_cn(key, norm_alpha)
            if cn:
                # 自动学习: 找到了就记住
                self.learn(cn, key, 'auto_db_match')
                return cn
        return None

    def to_en(self, name_cn: str) -> Optional[str]:
        """中文名→英文名, 多级查找"""
        if not name_cn:
            return None
        key = name_cn.strip()
        if key in self._cn_to_en:
            return self._cn_to_en[key]
        # DB查找
        if self._db_path:
            en = self._db_lookup_cn_to_en(key)
            if en:
                return en
        return None

    def is_chinese(self, name: str) -> bool:
        """判断名称是否包含中文"""
        return any(ord(c) > 0x4E00 and ord(c) < 0x9FFF for c in (name or ''))

    # ── 自动学习 ────────────────────────────────────────

    def learn(self, name_cn: str, name_en: str, source: str = 'auto') -> bool:
        """学习新的CN↔EN映射并持久化

        写入: team_chinese_names.json + teams.name_cn + team_name_mapping
        """
        if not name_cn or not name_en:
            return False
        name_cn = name_cn = name_cn.strip()
        name_en = name_en.strip()
        # 已存在则跳过
        if self._cn_to_en.get(name_cn) == name_en:
            return False
        # 更新内存
        self._cn_to_en[name_cn] = name_en
        self._en_to_cn[name_en] = name_cn
        self._en_to_cn[name_en.lower()] = name_cn
        # 持久化到JSON
        self._save_to_json(name_en, name_cn)
        # 持久化到DB
        if self._db_path:
            self._save_to_db(name_cn, name_en, source)
        logger.info('NameService.learn: %s ↔ %s (from %s)', name_cn, name_en, source)
        return True

    def learn_from_match(self, home_cn: str, away_cn: str, home_en: str, away_en: str,
                         source: str = 'match') -> int:
        """从一场比赛学习CN↔EN映射, 返回学习数量"""
        count = 0
        if home_cn and home_en and self.is_chinese(home_cn) and not self.is_chinese(home_en):
            if self.learn(home_cn, home_en, source):
                count += 1
        if away_cn and away_en and self.is_chinese(away_cn) and not self.is_chinese(away_en):
            if self.learn(away_cn, away_en, source):
                count += 1
        return count

    # ── 批量同步 ────────────────────────────────────────

    def sync_lottery_matches(self, db_path: str = None) -> int:
        """扫描lottery_matches中英文名的比赛, 尝试翻译

        策略:
        1. team_chinese_names.json → 更新
        2. teams表name_cn → 更新
        3. 内置映射 → 更新
        4. 模糊匹配 → 学习
        """
        db = db_path or self._db_path
        if not db:
            return 0
        import sqlite3
        conn = sqlite3.connect(db, timeout=15)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        updated = 0
        # 找出英文名的比赛
        c.execute("""
            SELECT lottery_match_id, home_team_cn, away_team_cn
            FROM lottery_matches
            WHERE home_team_cn IS NOT NULL
        """)
        rows = c.fetchall()

        for row in rows:
            mid = row['lottery_match_id']
            h_cn = row['home_team_cn'] or ''
            a_cn = row['away_team_cn'] or ''

            # 主队: 英文名需要翻译
            if h_cn and not self.is_chinese(h_cn):
                cn = self.to_cn(h_cn)
                if cn:
                    c.execute("UPDATE lottery_matches SET home_team_cn = ? WHERE lottery_match_id = ?",
                              (cn, mid))
                    updated += 1
                    self.learn(cn, h_cn, 'lottery_sync')

            # 客队: 英文名需要翻译
            if a_cn and not self.is_chinese(a_cn):
                cn = self.to_cn(a_cn)
                if cn:
                    c.execute("UPDATE lottery_matches SET away_team_cn = ? WHERE lottery_match_id = ?",
                              (cn, mid))
                    updated += 1
                    self.learn(cn, a_cn, 'lottery_sync')

        conn.commit()
        conn.close()
        logger.info('NameService.sync_lottery_matches: updated %d names', updated)
        return updated

    # ── 内部方法 ────────────────────────────────────────

    def _load_all(self):
        """加载所有映射源"""
        # 1. team_chinese_names.json (EN→CN)
        self._load_json()
        # 2. 额外映射
        self._en_to_cn.update(_EN_CN_EXTRA)
        self._cn_to_en.update(_CN_EN_EXTRA)
        # 3. 直接映射 (小联赛俱乐部)
        self._en_to_cn.update({k: v for k, v in _EN_CN_DIRECT.items()})
        self._cn_to_en.update({v: k for k, v in _EN_CN_DIRECT.items()})
        # 4. DB映射
        if self._db_path:
            self._load_from_db()

    def _load_json(self):
        """加载team_chinese_names.json"""
        try:
            if os.path.exists(_CN_EN_JSON):
                with open(_CN_EN_JSON, encoding='utf-8') as f:
                    en_to_cn = json.load(f)
                self._en_to_cn.update(en_to_cn)
                # 反转: CN→EN
                for en, cn in en_to_cn.items():
                    if cn and en:
                        self._cn_to_en[cn] = en
        except Exception as e:
            logger.warning('NameService: failed to load %s: %s', _CN_EN_JSON, e)

    def _load_from_db(self):
        """从DB加载teams.name_cn和team_name_mapping — 不覆盖已有映射"""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            c = conn.cursor()
            # teams表 — 只填充不存在的映射, 不覆盖
            c.execute("SELECT name_en, name_cn FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''")
            for en, cn in c.fetchall():
                if en and cn and self.is_chinese(cn):
                    # 不覆盖已有映射 (JSON/硬编码优先)
                    if en not in self._en_to_cn:
                        self._en_to_cn[en] = cn
                        self._en_to_cn[en.lower()] = cn
                    if cn not in self._cn_to_en:
                        self._cn_to_en[cn] = en
            # team_name_mapping表
            c.execute("""
                SELECT tnm.lottery_name, t.name_en, t.name_cn
                FROM team_name_mapping tnm
                JOIN teams t ON tnm.team_id = t.team_id
                WHERE t.name_cn IS NOT NULL AND t.name_cn != ''
            """)
            for lottery_name, name_en, name_cn in c.fetchall():
                if lottery_name and name_cn and self.is_chinese(name_cn):
                    if lottery_name not in self._cn_to_en:
                        self._cn_to_en[lottery_name] = name_en
                    if lottery_name not in self._en_to_cn:
                        self._en_to_cn[lottery_name] = name_cn
            conn.close()
        except Exception as e:
            logger.warning('NameService: failed to load from DB: %s', e)

    def _db_lookup_en_to_cn(self, name_en: str) -> Optional[str]:
        """DB查找: EN→CN"""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            c = conn.cursor()
            # 精确匹配
            c.execute("SELECT name_cn FROM teams WHERE name_en = ? AND name_cn IS NOT NULL AND name_cn != ''",
                      (name_en,))
            row = c.fetchone()
            if row and self.is_chinese(row[0]):
                conn.close()
                return row[0]
            # 规范化匹配
            norm = self.normalize(name_en)
            c.execute("SELECT name_en, name_cn FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''")
            for en, cn in c.fetchall():
                if self.normalize(en) == norm and self.is_chinese(cn):
                    conn.close()
                    return cn
            conn.close()
        except Exception:
            pass
        return None

    def _db_lookup_cn_to_en(self, name_cn: str) -> Optional[str]:
        """DB查找: CN→EN"""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            c = conn.cursor()
            c.execute("SELECT name_en FROM teams WHERE name_cn = ?", (name_cn,))
            row = c.fetchone()
            conn.close()
            if row:
                return row[0]
        except Exception:
            pass
        return None

    def _fuzzy_to_cn(self, name_en: str) -> Optional[str]:
        """模糊匹配: EN→CN"""
        if not name_en or len(name_en) < 3:
            return None
        norm = self.normalize(name_en)
        best_score = 0.0
        best_cn = None
        for en_key, cn_val in self._en_to_cn.items():
            if not self.is_chinese(cn_val):
                continue
            en_norm = self.normalize(en_key)
            if en_norm == norm:
                return cn_val
            score = SequenceMatcher(None, norm, en_norm).ratio()
            if score > best_score and score >= 0.80:
                best_score = score
                best_cn = cn_val
        return best_cn

    def _db_deep_lookup_en_to_cn(self, name_en: str, norm_alpha: str) -> Optional[str]:
        """DB深度模糊匹配: normalize_alpha比较teams表的name_en

        策略: 将teams表所有name_en做normalize_alpha, 与输入比较
        匹配到后返回对应的name_cn(如果有), 否则返回None
        """
        if not norm_alpha or len(norm_alpha) < 3:
            return None
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            c = conn.cursor()
            c.execute("SELECT name_en, name_cn FROM teams WHERE name_cn IS NOT NULL AND name_cn != ''")
            best_score = 0.0
            best_cn = None
            for en, cn in c.fetchall():
                if not self.is_chinese(cn):
                    continue
                db_alpha = self.normalize_alpha(en)
                if db_alpha == norm_alpha:
                    conn.close()
                    return cn
                # 模糊匹配
                score = SequenceMatcher(None, norm_alpha, db_alpha).ratio()
                if score > best_score and score >= 0.85:
                    best_score = score
                    best_cn = cn
            conn.close()
            return best_cn
        except Exception:
            return None

    def _save_to_json(self, name_en: str, name_cn: str):
        """持久化到team_chinese_names.json"""
        try:
            dirname = os.path.dirname(_CN_EN_JSON)
            if not os.path.exists(dirname):
                os.makedirs(dirname, exist_ok=True)
            data = {}
            if os.path.exists(_CN_EN_JSON):
                with open(_CN_EN_JSON, encoding='utf-8') as f:
                    data = json.load(f)
            data[name_en] = name_cn
            with open(_CN_EN_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning('NameService: failed to save JSON: %s', e)

    def _save_to_db(self, name_cn: str, name_en: str, source: str = 'auto'):
        """持久化到DB: teams.name_cn + team_name_mapping"""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            c = conn.cursor()
            # 更新teams.name_cn
            c.execute("UPDATE teams SET name_cn = ? WHERE name_en = ? AND (name_cn IS NULL OR name_cn = '')",
                      (name_cn, name_en))
            # 写入team_name_mapping
            c.execute("SELECT team_id FROM teams WHERE name_en = ?", (name_en,))
            row = c.fetchone()
            if row:
                c.execute("""
                    INSERT OR IGNORE INTO team_name_mapping (lottery_name, team_id, match_method)
                    VALUES (?, ?, ?)
                """, (name_cn, row[0], source))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning('NameService: failed to save to DB: %s', e)

    @classmethod
    def reset(cls):
        """重置单例 (测试用)"""
        cls._instance = None
        cls._cn_to_en = {}
        cls._en_to_cn = {}
        cls._loaded = False
