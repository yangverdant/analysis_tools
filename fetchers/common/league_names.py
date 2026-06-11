"""
联赛名称标准化与ID跨源映射

功能:
1. 任何源的联赛名/ID → 标准英文名 (normalize_league_name)
2. 标准英文名 → 某数据源的ID (league_to_source_id)
3. 某数据源的ID → 标准英文名 (source_id_to_league)
4. 联赛别名列表 (get_league_aliases)

数据来源: common/data/league_aliases.json + data/linkage/league_chinese_names.json

使用示例:
    from fetchers.common.league_names import normalize_league_name

    normalize_league_name("英超")       # → "Premier League"
    normalize_league_name("PL")        # → "Premier League"
    normalize_league_name("soccer_epl") # → "Premier League"

    league_to_source_id("Premier League", "apifootball")  # → 152
    source_id_to_league("PL", "football_data_org")        # → "Premier League"
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== 数据加载 ====================

_leagues_data = None
_name_to_standard: Dict[str, str] = {}
_standard_to_info: Dict[str, Dict] = {}
_source_to_id_league: Dict[str, Dict] = {}  # source → {id_value: standard_name}

_DATA_DIR = Path(__file__).parent / "data"
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_leagues_data() -> dict:
    path = _DATA_DIR / "league_aliases.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_chinese_leagues() -> Dict[str, str]:
    path = _PROJECT_ROOT / "data" / "linkage" / "league_chinese_names.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_index():
    global _leagues_data, _name_to_standard, _standard_to_info, _source_to_id_league

    if _name_to_standard:
        return

    _leagues_data = _load_leagues_data()

    SOURCES = ["apifootball", "football_data_org", "the_odds_api", "sportmonks",
               "openligadb", "okooo", "scores365", "thesportsdb", "fbref",
               "understat", "football_data_uk", "flashlive"]

    for source in SOURCES:
        _source_to_id_league[source] = {}

    for standard_name, info in _leagues_data.items():
        if standard_name.startswith("_"):
            continue
        if not isinstance(info, dict):
            continue

        # 标准名自身
        _name_to_standard[standard_name.lower()] = standard_name
        _standard_to_info[standard_name] = info

        # 中文名
        cn = info.get("cn")
        if cn:
            _name_to_standard[cn.lower()] = standard_name

        # 中文别名
        for alias in info.get("cn_aliases", []):
            _name_to_standard[alias.lower()] = standard_name

        # 英文别名
        for alias in info.get("en_aliases", []):
            _name_to_standard[alias.lower()] = standard_name

        # 各数据源ID → 标准名
        for source in SOURCES:
            source_id = info.get(source)
            if source_id is not None:
                _source_to_id_league[source][str(source_id).lower()] = standard_name

    # 补充 chinese league names 的反向映射
    chinese = _load_chinese_leagues()
    for en_name, cn_name in chinese.items():
        cn_key = cn_name.lower()
        if cn_key not in _name_to_standard:
            # 尝试先标准化英文名
            en_standard = _name_to_standard.get(en_name.lower(), en_name)
            _name_to_standard[cn_key] = en_standard

    logger.debug(f"联赛索引构建完成: {len(_name_to_standard)} 个名字 → {len(_standard_to_info)} 个标准联赛")


# ==================== 公开接口 ====================

def normalize_league_name(name) -> str:
    """任何源的联赛名/ID → 标准英文名

    支持输入: 中文名、英文别名、数据源ID(int/str)、数据源key

    Examples:
        normalize_league_name("英超")        → "Premier League"
        normalize_league_name("PL")         → "Premier League"
        normalize_league_name("soccer_epl") → "Premier League"
        normalize_league_name(152)          → "Premier League" (apifootball ID)
    """
    if not name:
        return str(name) if name else ""

    _build_index()

    # 字符串精确匹配
    key = str(name).strip().lower()
    if key in _name_to_standard:
        return _name_to_standard[key]

    # 尝试在所有数据源ID中查找
    for source, id_map in _source_to_id_league.items():
        if key in id_map:
            return id_map[key]

    # 无法标准化，返回原名
    return str(name)


def league_to_source_id(league_name: str, source: str) -> Optional[str]:
    """标准联赛名 → 某数据源的ID

    Examples:
        league_to_source_id("Premier League", "apifootball")  → "152"
        league_to_source_id("Premier League", "football_data_org") → "PL"
        league_to_source_id("Premier League", "the_odds_api") → "soccer_epl"
    """
    _build_index()

    standard = normalize_league_name(league_name)
    info = _standard_to_info.get(standard)
    if info:
        val = info.get(source)
        return str(val) if val is not None else None
    return None


def source_id_to_league(source_id, source: str) -> Optional[str]:
    """某数据源的ID → 标准联赛名

    Examples:
        source_id_to_league(152, "apifootball")  → "Premier League"
        source_id_to_league("PL", "football_data_org") → "Premier League"
        source_id_to_league("bl1", "openligadb") → "Bundesliga"
    """
    _build_index()

    key = str(source_id).lower()
    id_map = _source_to_id_league.get(source, {})
    if key in id_map:
        return id_map[key]
    return None


def get_league_aliases(name: str) -> List[str]:
    """标准联赛名 → 所有别名列表

    Examples:
        get_league_aliases("Premier League")
        → ["Premier League", "英超", "EPL", "English Premier League", ...]
    """
    _build_index()

    standard = normalize_league_name(name)
    info = _standard_to_info.get(standard)
    if not info:
        return [standard]

    result = [standard]
    if info.get("cn"):
        result.append(info["cn"])
    result.extend(info.get("cn_aliases", []))
    result.extend(info.get("en_aliases", []))
    return result


def get_league_info(name: str) -> Optional[Dict]:
    """获取联赛完整信息"""
    _build_index()
    standard = normalize_league_name(name)
    return _standard_to_info.get(standard)


def get_all_standard_leagues() -> List[str]:
    """获取所有标准联赛名列表"""
    _build_index()
    return sorted(_standard_to_info.keys())


def get_stats() -> Dict:
    _build_index()
    return {
        "total_names": len(_name_to_standard),
        "total_leagues": len(_standard_to_info),
        "sources_with_ids": {s: len(ids) for s, ids in _source_to_id_league.items() if ids},
    }


if __name__ == "__main__":
    tests = [
        ("英超", "Premier League"),
        ("PL", "Premier League"),
        ("soccer_epl", "Premier League"),
        ("EPL", "Premier League"),
        ("西甲", "La Liga"),
        ("德甲", "Bundesliga"),
        ("意甲", "Serie A"),
        ("法甲", "Ligue 1"),
        ("英冠", "Championship"),
        ("荷甲", "Eredivisie"),
        ("葡超", "Primeira Liga"),
        ("欧冠", "Champions League"),
        ("欧联", "Europa League"),
        ("日职联", "J1 League"),
        ("K联赛", "K1 League"),
        ("bl1", "Bundesliga"),
        ("BL1", "Bundesliga"),
        (152, "Premier League"),
        ("E0", "Premier League"),
    ]

    print("=== 联赛名标准化测试 ===")
    passed = 0
    for input_name, expected in tests:
        result = normalize_league_name(input_name)
        ok = "OK" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        print(f"  {ok} normalize_league_name({input_name!r}) -> {result!r} (expect: {expected!r})")

    print(f"\n通过: {passed}/{len(tests)}")

    # ID映射测试
    print("\n=== ID映射测试 ===")
    id_tests = [
        ("Premier League", "apifootball", "152"),
        ("Premier League", "football_data_org", "PL"),
        ("Premier League", "the_odds_api", "soccer_epl"),
        ("Bundesliga", "openligadb", "bl1"),
        ("Bundesliga", "football_data_uk", "D1"),
    ]
    for league, source, expected in id_tests:
        result = league_to_source_id(league, source)
        ok = "OK" if result == expected else "FAIL"
        print(f"  {ok} league_to_source_id({league!r}, {source!r}) -> {result!r} (expect: {expected!r})")

    print(f"\n索引统计: {get_stats()}")