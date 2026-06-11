"""
球队名称标准化与别名匹配

功能:
1. 任何数据源的队名 → 标准英文名 (normalize_team_name)
2. 标准英文名 → 所有别名 (get_team_aliases)
3. 任意队名 → 主场城市 (team_to_city)
4. 模糊匹配 (find_team)

数据来源: common/data/team_aliases.json + data/linkage/ 映射文件

使用示例:
    from fetchers.common.team_names import normalize_team_name, get_team_aliases

    normalize_team_name("枪手")       # → "Arsenal"
    normalize_team_name("Man City")   # → "Manchester City"
    normalize_team_name("拜仁")       # → "Bayern Munich"

    get_team_aliases("Arsenal")
    # → ["Arsenal", "Ars", "Arsenal FC", "阿森纳", "枪手", "兵工厂", "娜娜"]
"""

import json
import logging
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ==================== 数据加载 ====================

_aliases_data = None          # team_aliases.json 原始数据
_name_to_standard: Dict[str, str] = {}   # 任何名字 → 标准英文名
_standard_to_info: Dict[str, Dict] = {}  # 标准英文名 → 完整信息
_standard_to_all_names: Dict[str, List[str]] = {}  # 标准英文名 → 所有名字列表

_DATA_DIR = Path(__file__).parent / "data"
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_aliases_data() -> dict:
    """加载 team_aliases.json"""
    path = _DATA_DIR / "team_aliases.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_linkage_mapping() -> Dict[str, str]:
    """加载 data/linkage/team_name_mapping.json (2900+条目)"""
    path = _PROJECT_ROOT / "data" / "linkage" / "team_name_mapping.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if k != v}


def _load_short_mapping() -> Dict[str, str]:
    """加载 data/09_other_data/team_name_mapping.json (缩写→全称)"""
    path = _PROJECT_ROOT / "data" / "09_other_data" / "team_name_mapping.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if k != v}


def _load_chinese_names() -> Dict[str, str]:
    """加载 data/linkage/team_chinese_names.json (英→中)"""
    path = _PROJECT_ROOT / "data" / "linkage" / "team_chinese_names.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_index():
    """构建查找索引: 任何名字 → 标准英文名"""
    global _aliases_data, _name_to_standard, _standard_to_info, _standard_to_all_names

    if _name_to_standard:
        return

    _aliases_data = _load_aliases_data()

    # 1. 从 team_aliases.json 构建索引
    for league_name, teams in _aliases_data.items():
        if league_name.startswith("_"):
            continue
        if not isinstance(teams, dict):
            continue

        for standard_name, info in teams.items():
            if standard_name.startswith("_"):
                continue
            if not isinstance(info, dict):
                continue

            # 处理 _merge_to (重复条目合并)
            if "_merge_to" in info:
                continue
            if "_ref" in info:
                continue

            # 标准名自身
            _name_to_standard[standard_name.lower()] = standard_name
            _standard_to_info[standard_name] = info

            # 收集所有名字
            all_names = [standard_name]

            # 中文名
            cn = info.get("cn")
            if cn:
                _name_to_standard[cn.lower()] = standard_name
                all_names.append(cn)

            # 德文名
            de = info.get("de")
            if de:
                _name_to_standard[de.lower()] = standard_name
                all_names.append(de)

            # 英文别名
            for alias in info.get("en_aliases", []):
                _name_to_standard[alias.lower()] = standard_name
                all_names.append(alias)

            # 中文别名/昵称
            for alias in info.get("cn_aliases", []):
                _name_to_standard[alias.lower()] = standard_name
                all_names.append(alias)

            _standard_to_all_names[standard_name] = all_names

    # 2. 补充 linkage/team_name_mapping.json (覆盖更多球队)
    linkage = _load_linkage_mapping()
    for alias, canonical in linkage.items():
        key = alias.lower()
        if key not in _name_to_standard:
            _name_to_standard[key] = canonical
            # 反向: 如果canonical是已知的标准名，补充alias到all_names
            if canonical in _standard_to_all_names:
                if alias not in _standard_to_all_names[canonical]:
                    _standard_to_all_names[canonical].append(alias)

    # 3. 补充 09_other_data/team_name_mapping.json
    short = _load_short_mapping()
    for alias, canonical in short.items():
        key = alias.lower()
        if key not in _name_to_standard:
            _name_to_standard[key] = canonical
            if canonical in _standard_to_all_names:
                if alias not in _standard_to_all_names[canonical]:
                    _standard_to_all_names[canonical].append(alias)

    # 4. 补充 team_chinese_names.json 的反向映射 (中→英)
    chinese = _load_chinese_names()
    for en_name, cn_name in chinese.items():
        cn_key = cn_name.lower()
        # 直接建立中文→英文映射（不论英文名是否已知标准名）
        # 这修复了国家队映射缺失: "日本"→"Japan", "巴西"→"Brazil"
        if cn_key not in _name_to_standard:
            _name_to_standard[cn_key] = en_name
        # 如果英文名是已知标准名，补充别名
        if en_name in _standard_to_info:
            if cn_name not in _standard_to_all_names.get(en_name, []):
                _standard_to_all_names.setdefault(en_name, [en_name]).append(cn_name)
        elif en_name.lower() in _name_to_standard:
            standard = _name_to_standard[en_name.lower()]
            if cn_key not in _name_to_standard:
                _name_to_standard[cn_key] = standard

    # 5. 体彩中文别名(体彩用的简称/全称与team_chinese_names.json不同)
    _LOTTERY_CN_ALIASES = {
        '曼彻斯特城': 'Manchester City', '托特纳姆热刺': 'Tottenham Hotspur',
        '比利亚雷': 'Villarreal', '布伦特': 'Brentford',
        '沙特阿拉伯': 'Saudi Arabia', '刚果(金)': 'DR Congo',
        '斯托克港': 'Stockport County', '清水鼓动': 'Shimizu S-Pulse',
        '西雅图海湾人': 'Seattle Sounders', '费城联合': 'Philadelphia Union',
        '曼彻斯特联': 'Manchester United', '纽卡斯尔联': 'Newcastle United',
        '阿斯顿维拉': 'Aston Villa', '布莱克本流浪者': 'Blackburn Rovers',
        '西布朗维奇': 'West Bromwich Albion', '谢菲尔德联': 'Sheffield United',
    }
    for cn_alias, en_standard in _LOTTERY_CN_ALIASES.items():
        key = cn_alias.lower()
        if key not in _name_to_standard:
            _name_to_standard[key] = en_standard

    # 6. oddsfe队名变体 → 标准名(oddsfe用简称/缩写与标准名不同)
    _ODDSFE_ALIASES = {
        'Congo DR': 'DR Congo', 'Congo Dr': 'DR Congo',
        'Korea Republic': 'South Korea', 'Korea Rep.': 'South Korea',
        'USA': 'United States', 'USMNT': 'United States',
        'Ivory Coast': 'Cote d\'Ivoire', 'Côte d\'Ivoire': 'Cote d\'Ivoire',
        'Bosnia-Herzegovina': 'Bosnia and Herzegovina', 'Bosnia Herz': 'Bosnia and Herzegovina',
        'N. Ireland': 'Northern Ireland', 'North Ireland': 'Northern Ireland',
        'Macedonia': 'North Macedonia', 'Macedonia FYR': 'North Macedonia',
        'China PR': 'China', 'Chinese Taipei': 'China Taipei',
        'Turkiye': 'Turkey', 'Türkiye': 'Turkey',
        'Curacao': 'Curaçao', 'Curaçao': 'Curacao',
        'St. Kitts and Nevis': 'St Kitts and Nevis',
        'Trinidad and Tobago': 'Trinidad and Tobago',
        'Nottingham': 'Nottingham Forest',
        'Wolves': 'Wolverhampton', 'Wolverhampton Wanderers': 'Wolverhampton',
        'Leeds': 'Leeds United',
        'Spurs': 'Tottenham Hotspur', 'Tottenham': 'Tottenham Hotspur',
        'West Ham': 'West Ham United',
        'Brighton': 'Brighton and Hove Albion',
        'Atl. Madrid': 'Atletico Madrid', 'Athletic Madrid': 'Atletico Madrid',
        'Man Utd': 'Manchester United', 'Manchester Utd': 'Manchester United',
        'Man City': 'Manchester City',
        'Newcastle': 'Newcastle United',
    }
    for alias, standard in _ODDSFE_ALIASES.items():
        key = alias.lower()
        if key not in _name_to_standard:
            _name_to_standard[key] = standard

    logger.debug(f"球队索引构建完成: {len(_name_to_standard)} 个名字 → {len(_standard_to_info)} 个标准名")


# ==================== 公开接口 ====================

def normalize_team_name(name: str) -> str:
    """任何源的队名 → 标准英文名

    Examples:
        normalize_team_name("枪手")       → "Arsenal"
        normalize_team_name("Man City")   → "Manchester City"
        normalize_team_name("拜仁")       → "Bayern Munich"
        normalize_team_name("BVB")        → "Borussia Dortmund"
        normalize_team_name("PSG")        → "Paris Saint-Germain"
        normalize_team_name("蓝月亮")     → "Manchester City"
    """
    if not name:
        return name

    _build_index()

    # 精确匹配
    key = name.strip().lower()
    if key in _name_to_standard:
        return _name_to_standard[key]

    # 去除括号后缀 (如 "Bayern Munich (GER)")
    stripped = key
    if " (" in stripped:
        stripped = stripped[:stripped.index(" (")]
    if stripped != key and stripped in _name_to_standard:
        return _name_to_standard[stripped]

    # 去除 "FC", "CF", "SC" 等后缀再试
    for suffix in [" fc", " cf", " sc", " ac", " afc", " bsc", " vfl", " vfb"]:
        if key.endswith(suffix):
            trimmed = key[:-len(suffix)]
            if trimmed in _name_to_standard:
                return _name_to_standard[trimmed]

    # 无法标准化，返回原名
    return name


def get_team_aliases(name: str) -> List[str]:
    """标准名 → 所有别名列表 (含中文、缩写、昵称)

    Examples:
        get_team_aliases("Arsenal")
        → ["Arsenal", "Ars", "Arsenal FC", "阿森纳", "枪手", "兵工厂", "娜娜"]
    """
    _build_index()

    standard = normalize_team_name(name)
    return _standard_to_all_names.get(standard, [standard])


def get_team_info(name: str) -> Optional[Dict]:
    """获取球队完整信息

    # Returns:
    #     {"cn": "阿森纳", "de": null, "en_aliases": [...], "cn_aliases": [...], "city": "London", "stadium": "Emirates Stadium"}
    #     或 None
    """
    _build_index()

    standard = normalize_team_name(name)
    return _standard_to_info.get(standard)


def team_to_city(name: str) -> Optional[str]:
    """球队名 → 主场城市(英文)

    Examples:
        team_to_city("Arsenal")    → "London"
        team_to_city("拜仁")       → "Munich"
        team_to_city("巴萨")       → "Barcelona"
    """
    info = get_team_info(name)
    if info:
        return info.get("city")
    return None


def team_to_stadium(name: str) -> Optional[str]:
    """球队名 → 主场球场名

    Examples:
        team_to_stadium("Arsenal")  → "Emirates Stadium"
        team_to_stadium("拜仁")     → "Allianz Arena"
        team_to_stadium("巴萨")     → "Camp Nou"
    """
    info = get_team_info(name)
    if info:
        return info.get("stadium")
    return None


def find_team(query: str, threshold: float = 0.75) -> Optional[Tuple[str, float]]:
    """模糊查找球队

    Args:
        query: 任意球队名
        threshold: 匹配阈值 (0-1)

    Returns:
        (标准英文名, 匹配分数) 或 None
    """
    _build_index()

    # 先精确匹配
    standard = normalize_team_name(query)
    if standard != query:
        return (standard, 1.0)

    # 模糊匹配: 对所有已知名字计算相似度
    best_score = 0.0
    best_standard = None
    query_lower = query.lower()

    for known_name, standard_name in _name_to_standard.items():
        if len(query_lower) < 2 or len(known_name) < 2:
            continue
        score = SequenceMatcher(None, query_lower, known_name).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_standard = standard_name

    if best_standard:
        return (best_standard, best_score)
    return None


def is_same_team(name1: str, name2: str) -> bool:
    """判断两个队名是否指同一支球队

    Examples:
        is_same_team("枪手", "Arsenal")     → True
        is_same_team("Man City", "曼城")    → True
        is_same_team("Barca", "巴塞罗那")   → True
    """
    s1 = normalize_team_name(name1)
    s2 = normalize_team_name(name2)
    if s1 == s2:
        return True
    # 如果标准化后不同，尝试模糊匹配
    if s1 != name1 and s2 != name2:
        return s1 == s2
    return False


def get_all_standard_names() -> List[str]:
    """获取所有标准英文名列表"""
    _build_index()
    return sorted(_standard_to_info.keys())


def get_stats() -> Dict:
    """获取索引统计信息"""
    _build_index()
    return {
        "total_names": len(_name_to_standard),
        "total_teams": len(_standard_to_info),
        "teams_with_city": sum(1 for v in _standard_to_info.values() if v.get("city")),
        "teams_with_cn": sum(1 for v in _standard_to_info.values() if v.get("cn")),
        "teams_with_de": sum(1 for v in _standard_to_info.values() if v.get("de")),
    }


if __name__ == "__main__":
    # 测试
    tests = [
        ("枪手", "Arsenal"),
        ("Man City", "Manchester City"),
        ("拜仁", "Bayern Munich"),
        ("BVB", "Borussia Dortmund"),
        ("PSG", "Paris Saint-Germain"),
        ("蓝月亮", "Manchester City"),
        ("皇马", "Real Madrid"),
        ("巴萨", "FC Barcelona"),
        ("老妇人", "Juventus"),
        ("药厂", "Bayer Leverkusen"),
        ("大黄蜂", "Borussia Dortmund"),
        ("红军", "Liverpool"),
        ("红魔", "Manchester United"),
        ("铁锤帮", "West Ham United"),
        ("喜鹊", "Newcastle United"),
        ("矿工", "Shakhtar Donetsk"),
        ("门兴", "Borussia Monchengladbach"),
        ("狼堡", "VfL Wolfsburg"),
        ("紫百合", "Fiorentina"),
        ("黄色潜水艇", "Villarreal"),
    ]

    print("=== 队名标准化测试 ===")
    passed = 0
    for input_name, expected in tests:
        result = normalize_team_name(input_name)
        ok = "OK" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        print(f"  {ok} normalize_team_name(\"{input_name}\") → \"{result}\" (期望: \"{expected}\")")

    print(f"\n通过: {passed}/{len(tests)}")
    print(f"\n索引统计: {get_stats()}")
