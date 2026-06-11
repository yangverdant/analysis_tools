"""
实体映射器 - 数据转换核心

功能:
1. 字段映射: 不同数据源字段 → 系统标准字段
2. 值转换: 数据类型转换、格式标准化
3. 实体关联: 体彩名称 → 系统team_id
4. 数据合并: 多源数据合并
"""

from typing import Dict, Any, List, Optional
import sqlite3
import json
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class EntityMapper:
    """
    实体映射器

    解决问题:
    - API-Football返回 homeTeam.name
    - Sportmonks返回 home_team.name
    - 体彩官网返回 主队名称
    → 统一映射为系统标准字段 home_team_name
    """

    # 字段映射配置
    FIELD_MAPPINGS = {
        # API-Football 数据源
        'api_football': {
            'fixture.id': 'match_id',
            'fixture.date': 'match_date',
            'fixture.time': 'match_time',
            'fixture.status.short': 'status',
            'league.id': 'league_id',
            'league.name': 'league_name',
            'teams.home.id': 'home_team_id',
            'teams.home.name': 'home_team_name',
            'teams.away.id': 'away_team_id',
            'teams.away.name': 'away_team_name',
            'goals.home': 'home_goals',
            'goals.away': 'away_goals',
            'score.halftime.home': 'home_goals_ht',
            'score.halftime.away': 'away_goals_ht',
        },

        # Sportmonks 数据源
        'sportmonks': {
            'id': 'match_id',
            'starting_at': 'match_datetime',
            'result_info': 'result_info',
            'league_id': 'league_id',
            'season_id': 'season_id',
            'scores.localteam_score': 'home_goals',
            'scores.visitorteam_score': 'away_goals',
        },

        # 体彩官网数据源
        'lottery': {
            'matchId': 'lottery_match_id',
            'matchNum': 'match_num',
            'homeTeam': 'home_team_cn',
            'awayTeam': 'away_team_cn',
            'leagueName': 'league_name_cn',
            'matchDate': 'match_date',
            'matchTime': 'match_time',
            'beijingTime': 'beijing_time',
            'sellStatus': 'sell_status',
            'sellEndTime': 'sell_end_time',
            'handicapLine': 'handicap_line',
            'spfOdds': 'spf_odds',
            'bfOdds': 'bf_odds',
            'bqcOdds': 'bqc_odds',
            'rqspfOdds': 'rqspf_odds',
        },

        # FBref 数据源
        'fbref': {
            'match_id': 'match_id',
            'date': 'match_date',
            'home_team': 'home_team_name',
            'away_team': 'away_team_name',
            'home_goals': 'home_goals',
            'away_goals': 'away_goals',
            'home_xg': 'home_xg',
            'away_xg': 'away_xg',
        }
    }

    # 值转换器
    VALUE_CONVERTERS = {
        'match_date': lambda v: v[:10] if v else None,
        'match_time': lambda v: v[11:16] if v and len(v) > 11 else v,
        'sell_status': lambda v: {'on': 'selling', 'off': 'stopped'}.get(v, v),
        'home_goals': lambda v: int(v) if v is not None else None,
        'away_goals': lambda v: int(v) if v is not None else None,
    }

    def __init__(self, db_path: str, config: Dict = None):
        self.db_path = db_path
        self.config = config or {}

        # 球队名称映射缓存
        self._team_name_cache: Dict[str, int] = {}
        self._team_id_cache: Dict[int, Dict] = {}
        self._load_team_mappings()

    def map_to_standard(
        self,
        source_name: str,
        raw_data: Dict,
        extra_mappings: Dict = None
    ) -> Dict[str, Any]:
        """
        将任意数据源的数据转换为系统标准格式

        Args:
            source_name: 数据源名称
            raw_data: 原始数据
            extra_mappings: 额外的字段映射

        Returns:
            标准化后的数据
        """
        mapping = self.FIELD_MAPPINGS.get(source_name, {})
        if extra_mappings:
            mapping = {**mapping, **extra_mappings}

        result = {}

        for source_path, target_field in mapping.items():
            # 特殊处理
            if target_field.startswith('_') and target_field.endswith('_special'):
                special_result = self._handle_special_mapping(
                    source_name, source_path, raw_data
                )
                result.update(special_result)
                continue

            # 获取值
            value = self._get_nested_value(raw_data, source_path)

            if value is not None:
                # 值转换
                if target_field in self.VALUE_CONVERTERS:
                    value = self.VALUE_CONVERTERS[target_field](value)

                result[target_field] = value

        # 添加数据源标识
        result['_source'] = source_name

        return result

    def map_lottery_to_system(
        self,
        lottery_match: Dict,
        team_mapping: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """
        体彩比赛数据 → 系统比赛数据

        包含球队名称映射
        """
        # 基础字段映射
        result = self.map_to_standard('lottery', lottery_match)

        # 球队名称映射
        home_team_cn = result.get('home_team_cn')
        away_team_cn = result.get('away_team_cn')

        if team_mapping:
            result['home_team_id'] = team_mapping.get(home_team_cn)
            result['away_team_id'] = team_mapping.get(away_team_cn)
        else:
            result['home_team_id'] = self._team_name_cache.get(home_team_cn)
            result['away_team_id'] = self._team_name_cache.get(away_team_cn)

        return result

    def get_team_id(self, lottery_name: str) -> Optional[int]:
        """
        体彩名称 → 系统team_id

        支持多种匹配方式:
        1. 精确匹配
        2. 模糊匹配
        """
        # 精确匹配
        if lottery_name in self._team_name_cache:
            return self._team_name_cache[lottery_name]

        # 模糊匹配
        return self._fuzzy_match_team(lottery_name)

    def get_team_info(self, team_id: int) -> Optional[Dict]:
        """获取球队信息"""
        return self._team_id_cache.get(team_id)

    def register_team_mapping(
        self,
        lottery_name: str,
        team_id: int,
        method: str = 'manual'
    ) -> bool:
        """
        注册新的球队映射

        Args:
            lottery_name: 体彩名称
            team_id: 系统team_id
            method: 匹配方法 (exact/fuzzy/manual)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO team_name_mapping
                (lottery_name, team_id, match_confidence, match_method, updated_at)
                VALUES (?, ?, 1.0, ?, CURRENT_TIMESTAMP)
            """, (lottery_name, team_id, method))

            conn.commit()

            # 更新缓存
            self._team_name_cache[lottery_name] = team_id

            logger.info(f"Registered team mapping: {lottery_name} -> {team_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register team mapping: {e}")
            return False
        finally:
            conn.close()

    def _load_team_mappings(self):
        """加载球队名称映射"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 从映射表加载
            cursor.execute("""
                SELECT lottery_name, team_id FROM team_name_mapping
            """)

            for row in cursor.fetchall():
                self._team_name_cache[row[0]] = row[1]

            # 从teams表加载中文名
            cursor.execute("""
                SELECT team_id, name_en, name_cn, short_name FROM teams
            """)

            for row in cursor.fetchall():
                team_id = row[0]
                self._team_id_cache[team_id] = {
                    'name_en': row[1],
                    'name_cn': row[2],
                    'short_name': row[3]
                }

                # 中文名也加入缓存
                if row[2]:
                    self._team_name_cache[row[2]] = team_id

            logger.info(f"Loaded {len(self._team_name_cache)} team mappings")

        except Exception as e:
            logger.error(f"Failed to load team mappings: {e}")
        finally:
            conn.close()

    def _fuzzy_match_team(self, lottery_name: str) -> Optional[int]:
        """模糊匹配球队"""
        best_match = None
        best_score = 0

        for cached_name, team_id in self._team_name_cache.items():
            # 计算相似度
            score = SequenceMatcher(None, lottery_name, cached_name).ratio()

            if score > best_score and score > 0.8:  # 阈值
                best_score = score
                best_match = team_id

        if best_match:
            logger.info(f"Fuzzy matched '{lottery_name}' to team_id={best_match} (score={best_score:.2f})")

        return best_match

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """获取嵌套字段值"""
        keys = path.split('.')
        value = data

        for key in keys:
            if value is None:
                return None

            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(value):
                    value = value[idx]
                else:
                    return None
            else:
                return None

        return value

    def _handle_special_mapping(
        self,
        source_name: str,
        path: str,
        data: Dict
    ) -> Dict:
        """处理特殊映射逻辑"""
        result = {}

        if source_name == 'sportmonks' and path == 'participants':
            participants = data.get('participants', [])
            for p in participants:
                if p.get('meta', {}).get('location') == 'home':
                    result['home_team_id'] = p.get('id')
                    result['home_team_name'] = p.get('name')
                elif p.get('meta', {}).get('location') == 'away':
                    result['away_team_id'] = p.get('id')
                    result['away_team_name'] = p.get('name')

        return result

    def merge_multi_source(
        self,
        sources_data: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """
        合并多数据源数据

        策略:
        1. 按数据源优先级填充
        2. 冲突时保留最完整的值
        """
        merged = {}
        filled_fields = set()

        # 按优先级顺序
        source_priority = self.config.get('source_priority', [
            'api_football', 'sportmonks', 'fbref', 'lottery'
        ])

        for source_name in source_priority:
            if source_name not in sources_data:
                continue

            data = sources_data[source_name]
            if isinstance(data, dict):
                standardized = self.map_to_standard(source_name, data)

                for field, value in standardized.items():
                    if field not in filled_fields and value is not None:
                        merged[field] = value
                        filled_fields.add(field)

        return merged

    def list_unmapped_teams(self) -> List[str]:
        """列出未映射的球队名称"""
        # 这里可以查询 lottery_matches 表中未映射的球队
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT DISTINCT home_team_cn FROM lottery_matches
                WHERE home_team_id IS NULL
                UNION
                SELECT DISTINCT away_team_cn FROM lottery_matches
                WHERE away_team_id IS NULL
            """)

            return [row[0] for row in cursor.fetchall() if row[0]]

        finally:
            conn.close()

    def get_mapping_stats(self) -> Dict:
        """获取映射统计"""
        return {
            'total_mappings': len(self._team_name_cache),
            'teams_loaded': len(self._team_id_cache)
        }