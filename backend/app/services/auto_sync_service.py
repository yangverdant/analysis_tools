"""
自动数据同步服务
统一管理所有数据补充管道，支持手动触发和定时调度
"""
import sqlite3
import json
import os
import logging
import asyncio
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "football_v2.db"
LINKAGE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "linkage"


class AutoSyncService:
    """自动数据补充服务"""

    def __init__(self):
        self._conn = None
        self.results = {}

    @property
    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(DB_PATH))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _execute(self, sql, params=None):
        return self.conn.execute(sql, params or ())

    # ========== 1. 国家中文名同步 ==========
    def sync_country_chinese_names(self) -> dict:
        """从linkage文件同步国家中文名到数据库"""
        result = {"total": 0, "updated": 0, "errors": []}

        mapping_file = LINKAGE_DIR / "country_chinese_name.json"
        if not mapping_file.exists():
            result["errors"].append("country_chinese_name.json 不存在")
            return result

        with open(mapping_file, "r", encoding="utf-8") as f:
            country_map = json.load(f)

        # 同步到 leagues 表的 country_cn 列
        for en_name, cn_name in country_map.items():
            result["total"] += 1
            try:
                cur = self._execute(
                    "UPDATE leagues SET country_cn = ? WHERE country = ? AND (country_cn IS NULL OR country_cn = '')",
                    (cn_name, en_name),
                )
                result["updated"] += cur.rowcount
            except Exception as e:
                result["errors"].append(f"更新 {en_name}: {e}")

        self.conn.commit()
        logger.info(f"国家中文名同步完成: {result['updated']}/{result['total']}")
        return result

    # ========== 2. 联赛规则自动补充 ==========
    def sync_league_rules(self) -> dict:
        """自动补充联赛规则：先从已有数据推断，再用AI补充"""
        result = {"total": 0, "filled": 0, "errors": []}

        # 找出没有规则或规则不完整的联赛
        rows = self._execute("""
            SELECT l.league_id, l.name_en, l.name_cn, l.country, l.competition_type, l.tier
            FROM leagues l
            LEFT JOIN league_rules r ON l.league_id = r.league_id
            WHERE r.league_id IS NULL
              AND l.competition_type = 'league'
        """).fetchall()

        result["total"] = len(rows)

        for row in rows:
            try:
                # 根据已知联赛特征推断规则
                rules = self._infer_league_rules(dict(row))
                if rules:
                    self._insert_league_rules(rules)
                    result["filled"] += 1
            except Exception as e:
                result["errors"].append(f"联赛 {row['league_id']}: {e}")

        self.conn.commit()
        logger.info(f"联赛规则补充完成: {result['filled']}/{result['total']}")
        return result

    def _infer_league_rules(self, league: dict) -> dict | None:
        """根据联赛特征推断规则（基于tier和国家）"""
        country = league.get("country", "")
        tier = league.get("tier", 99)
        league_id = league.get("league_id")

        # 从当前赛季比赛数据推断球队数量
        teams_count = self._get_teams_count(league_id)

        # 已知联赛规则映射（覆盖主要联赛）
        known_rules = {
            # 英超
            "England_1": {"teams_count": 20, "champions_league_spots": 4, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 38},
            # 英冠
            "England_2": {"teams_count": 24, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 46},
            # 英甲
            "England_3": {"teams_count": 24, "relegation_spots": 4, "promotion_spots": 3, "matches_per_team": 46},
            # 英乙
            "England_4": {"teams_count": 24, "relegation_spots": 2, "promotion_spots": 4, "matches_per_team": 46},
            # 西甲
            "Spain_1": {"teams_count": 20, "champions_league_spots": 4, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 38},
            # 西乙
            "Spain_2": {"teams_count": 22, "relegation_spots": 4, "promotion_spots": 3, "matches_per_team": 42},
            # 德甲
            "Germany_1": {"teams_count": 18, "champions_league_spots": 4, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 34},
            # 德乙
            "Germany_2": {"teams_count": 18, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 34},
            # 意甲
            "Italy_1": {"teams_count": 20, "champions_league_spots": 4, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 38},
            # 意乙
            "Italy_2": {"teams_count": 20, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 38},
            # 法甲
            "France_1": {"teams_count": 18, "champions_league_spots": 3, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 34},
            # 法乙
            "France_2": {"teams_count": 18, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 34},
            # 荷甲
            "Netherlands_1": {"teams_count": 18, "champions_league_spots": 2, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 34},
            # 葡超
            "Portugal_1": {"teams_count": 18, "champions_league_spots": 2, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 34},
            # 比甲
            "Belgium_1": {"teams_count": 16, "champions_league_spots": 2, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 30},
            # 奥超
            "Austria_1": {"teams_count": 12, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 22},
            # 奥乙
            "Austria_2": {"teams_count": 16, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # 瑞士超
            "Switzerland_1": {"teams_count": 12, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 22},
            # 土超
            "Turkey_1": {"teams_count": 20, "champions_league_spots": 2, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 38},
            # 希超
            "Greece_1": {"teams_count": 14, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 26},
            # 俄超
            "Russia_1": {"teams_count": 16, "champions_league_spots": 1, "europa_league_spots": 2, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # 苏超
            "Scotland_1": {"teams_count": 12, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 22},
            # 丹麦超
            "Denmark_1": {"teams_count": 12, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 22},
            # 瑞典超
            "Sweden_1": {"teams_count": 16, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # 挪超
            "Norway_1": {"teams_count": 16, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # 芬超
            "Finland_1": {"teams_count": 12, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 0, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 22},
            # 波兰超
            "Poland_1": {"teams_count": 18, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 34},
            # 捷甲
            "Czech Republic_1": {"teams_count": 16, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # 克甲
            "Croatia_1": {"teams_count": 10, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 18},
            # 匈甲
            "Hungary_1": {"teams_count": 12, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 22},
            # 罗甲
            "Romania_1": {"teams_count": 16, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # 巴甲
            "Brazil_1": {"teams_count": 20, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 4, "promotion_spots": 4, "matches_per_team": 38},
            # 阿甲
            "Argentina_1": {"teams_count": 28, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 27},
            # 中超
            "China_1": {"teams_count": 16, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # J联赛
            "Japan_1": {"teams_count": 20, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 3, "promotion_spots": 3, "matches_per_team": 38},
            # K联赛
            "South Korea_1": {"teams_count": 12, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 22},
            # 沙特联
            "Saudi Arabia_1": {"teams_count": 18, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 34},
            # 澳超
            "Australia_1": {"teams_count": 13, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 0, "promotion_spots": 0, "matches_per_team": 24},
            # 墨超
            "Mexico_1": {"teams_count": 18, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 34},
            # 美职联
            "USA_1": {"teams_count": 30, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 0, "promotion_spots": 0, "matches_per_team": 34},
            # 埃及超
            "Egypt_1": {"teams_count": 18, "champions_league_spots": 0, "europa_league_spots": 0, "conference_league_spots": 0, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 34},
            # 乌超
            "Ukraine_1": {"teams_count": 16, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 1, "relegation_spots": 2, "promotion_spots": 2, "matches_per_team": 30},
            # 斯洛伐克超
            "Slovakia_1": {"teams_count": 12, "champions_league_spots": 1, "europa_league_spots": 1, "conference_league_spots": 0, "relegation_spots": 1, "promotion_spots": 1, "matches_per_team": 22},
        }

        # 查找匹配的规则
        key = f"{country}_{tier}"
        rules_data = known_rules.get(key)

        if not rules_data:
            # 通用推断：基于tier和球队数
            rules_data = self._generic_rules(tier, teams_count)
            if not rules_data:
                return None

        # 用实际球队数覆盖（如果有）
        if teams_count and teams_count > 0:
            rules_data["teams_count"] = teams_count
            if "matches_per_team" not in rules_data:
                rules_data["matches_per_team"] = (teams_count - 1) * 2

        rules_data["league_id"] = league_id
        return rules_data

    def _get_teams_count(self, league_id: int) -> int | None:
        """从当前赛季积分榜推断球队数量"""
        row = self._execute("""
            SELECT COUNT(DISTINCT CASE WHEN m.home_goals IS NOT NULL THEN m.home_team_id END) as cnt
            FROM matches m
            LEFT JOIN seasons s ON m.season_id = s.season_id
            WHERE m.league_id = ?
            ORDER BY s.season_name DESC
            LIMIT 1
        """, (league_id,)).fetchone()
        if row and row["cnt"] and row["cnt"] > 0:
            return row["cnt"]

        # 备选：从teams表查
        row2 = self._execute("""
            SELECT COUNT(*) as cnt FROM teams WHERE league_id = ?
        """, (league_id,)).fetchone()
        if row2 and row2["cnt"] and row2["cnt"] > 0:
            return row2["cnt"]
        return None

    def _generic_rules(self, tier: int, teams_count: int | None) -> dict | None:
        """基于tier的通用规则推断"""
        if tier == 1:
            return {
                "teams_count": teams_count or 18,
                "champions_league_spots": 2 if teams_count and teams_count <= 16 else 4,
                "europa_league_spots": 2,
                "conference_league_spots": 1,
                "relegation_spots": 2 if teams_count and teams_count <= 16 else 3,
                "promotion_spots": 2 if teams_count and teams_count <= 16 else 3,
            }
        elif tier == 2:
            return {
                "teams_count": teams_count or 18,
                "relegation_spots": 2,
                "promotion_spots": 2,
            }
        elif tier == 3:
            return {
                "teams_count": teams_count or 20,
                "relegation_spots": 2,
                "promotion_spots": 2,
            }
        else:
            if teams_count and teams_count > 0:
                return {"teams_count": teams_count}
            return None

    def _insert_league_rules(self, rules: dict):
        """插入联赛规则到数据库"""
        columns = ["league_id", "teams_count", "matches_per_team",
                    "champions_league_spots", "europa_league_spots",
                    "conference_league_spots", "promotion_spots", "relegation_spots"]
        values = [rules.get(c) for c in columns]
        placeholders = ",".join(["?"] * len(columns))
        col_str = ",".join(columns)
        self._execute(
            f"INSERT OR REPLACE INTO league_rules ({col_str}) VALUES ({placeholders})",
            values,
        )

    # ========== 3. 球员中文名AI翻译 ==========
    async def sync_player_chinese_names(self, limit: int = 200) -> dict:
        """用DeepSeek AI翻译球员中文名"""
        result = {"total": 0, "translated": 0, "errors": []}

        players = self._execute("""
            SELECT p.player_id, p.name_en
            FROM players p
            WHERE (p.name_cn IS NULL OR p.name_cn = '')
            LIMIT ?
        """, (limit,)).fetchall()

        if not players:
            return result

        result["total"] = len(players)
        config = self._load_api_config()
        deepseek_key = config.get("deepseek", {}).get("api_key", "")

        if not deepseek_key:
            result["errors"].append("DeepSeek API key 未配置，请在 api_config.json 中添加")
            return result

        # 批量翻译（每批50人）
        batch_size = 50
        for i in range(0, len(players), batch_size):
            batch = [dict(p) for p in players[i:i + batch_size]]
            try:
                translations = await self._translate_players_batch(batch, deepseek_key)
                for player_id, cn_name in translations.items():
                    if cn_name:
                        self._execute(
                            "UPDATE players SET name_cn = ? WHERE player_id = ?",
                            (cn_name, player_id),
                        )
                        result["translated"] += 1
                self.conn.commit()
            except Exception as e:
                result["errors"].append(f"批次 {i // batch_size}: {e}")

        logger.info(f"球员中文名翻译完成: {result['translated']}/{result['total']}")
        return result

    async def _translate_players_batch(self, players: list, api_key: str) -> dict:
        """调用DeepSeek AI翻译一批球员名"""
        import httpx

        player_list = "\n".join([
            f"{p['player_id']}: {p['name_en']} ({p.get('team_name', '')})"
            for p in players
        ])

        prompt = f"""请将以下足球运动员的名字翻译为中文。只返回JSON格式 {{"player_id": "中文名"}}，不要其他内容。

{player_list}

注意：
- 如果是已经约定俗成的中文译名（如 Haaland -> 哈兰德），使用约定译名
- 否则按中文体育翻译惯例音译
- 只返回JSON，不要任何解释"""

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            # 提取JSON
            import re
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            # 尝试完整解析
            return json.loads(content)

    # ========== 4. 联赛中文名AI翻译 ==========
    async def sync_league_chinese_names(self, limit: int = 200) -> dict:
        """用DeepSeek AI翻译联赛中文名"""
        result = {"total": 0, "translated": 0, "errors": []}

        leagues = self._execute("""
            SELECT league_id, name_en, country
            FROM leagues
            WHERE (name_cn IS NULL OR name_cn = '')
            LIMIT ?
        """, (limit,)).fetchall()

        if not leagues:
            return result

        result["total"] = len(leagues)
        config = self._load_api_config()
        deepseek_key = config.get("deepseek", {}).get("api_key", "")

        if not deepseek_key:
            result["errors"].append("DeepSeek API key 未配置")
            return result

        batch = [dict(l) for l in leagues]
        try:
            translations = await self._translate_leagues_batch(batch, deepseek_key)
            for league_id, cn_name in translations.items():
                if cn_name:
                    self._execute(
                        "UPDATE leagues SET name_cn = ? WHERE league_id = ?",
                        (cn_name, league_id),
                    )
                    result["translated"] += 1
            self.conn.commit()
        except Exception as e:
            result["errors"].append(str(e))

        logger.info(f"联赛中文名翻译完成: {result['translated']}/{result['total']}")
        return result

    async def _translate_leagues_batch(self, leagues: list, api_key: str) -> dict:
        """调用DeepSeek AI翻译一批联赛名"""
        import httpx

        league_list = "\n".join([
            f"{l['league_id']}: {l['name_en']} ({l.get('country', '')})"
            for l in leagues
        ])

        prompt = f"""请将以下足球联赛的名字翻译为中文。只返回JSON格式 {{"league_id": "中文名"}}，不要其他内容。

{league_list}

注意：使用约定俗成的中文译名（如 Premier League -> 英超，La Liga -> 西甲）。只返回JSON。"""

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(content)

    # ========== 5. 比赛season_id修复 ==========
    def fix_match_season_ids(self) -> dict:
        """修复比赛的season_id关联"""
        result = {"total": 0, "fixed": 0, "errors": []}

        # 找出缺少season_id的比赛
        orphan_matches = self._execute("""
            SELECT m.match_id, m.league_id, m.match_date, m.season_id
            FROM matches m
            WHERE m.season_id IS NULL
            LIMIT 10000
        """).fetchall()

        result["total"] = len(orphan_matches)
        if not orphan_matches:
            return result

        # 获取所有赛季映射
        seasons = self._execute("""
            SELECT season_id, league_id, season_name, start_date, end_date
            FROM seasons
        """).fetchall()

        # 按league_id分组
        league_seasons = {}
        for s in seasons:
            lid = s["league_id"]
            if lid not in league_seasons:
                league_seasons[lid] = []
            league_seasons[lid].append(dict(s))

        for match in orphan_matches:
            try:
                season_id = self._match_season(dict(match), league_seasons)
                if season_id:
                    self._execute(
                        "UPDATE matches SET season_id = ? WHERE match_id = ?",
                        (season_id, match["match_id"]),
                    )
                    result["fixed"] += 1
            except Exception as e:
                result["errors"].append(f"match {match['match_id']}: {e}")

        self.conn.commit()
        logger.info(f"season_id修复完成: {result['fixed']}/{result['total']}")
        return result

    def _match_season(self, match: dict, league_seasons: dict) -> int | None:
        """为比赛匹配season_id"""
        lid = match["league_id"]
        if lid not in league_seasons:
            return None

        match_date = match.get("match_date")
        if not match_date:
            return None

        for season in league_seasons[lid]:
            # 方式1：按日期范围匹配
            start = season.get("start_date")
            end = season.get("end_date")
            if start and end and match_date >= start and match_date <= end:
                return season["season_id"]

            # 方式2：按赛季名推断（如 "2024-25" -> 2024年8月~2025年5月）
            sn = season.get("season_name", "")
            if "-" in sn and len(sn.split("-")) == 2:
                parts = sn.split("-")
                try:
                    year1 = int(parts[0])
                    year2_prefix = parts[1]
                    year2 = int(str(year1)[:2] + year2_prefix) if len(year2_prefix) == 2 else int(year2_prefix)
                    # 赛季通常8月开始，5月结束
                    import datetime
                    season_start = datetime.date(year1, 8, 1)
                    season_end = datetime.date(year2, 6, 30)
                    md = datetime.date.fromisoformat(str(match_date)[:10]) if match_date else None
                    if md and season_start <= md <= season_end:
                        return season["season_id"]
                except (ValueError, TypeError):
                    continue

        return None

    # ========== 6. 已完成比赛结果同步 ==========
    async def sync_finished_match_results(self, league_id: int = None) -> dict:
        """从API同步已完成比赛的结果和比分"""
        result = {"total": 0, "updated": 0, "errors": []}

        # 找出缺少结果的比赛（已过去但无比分）
        if league_id:
            matches = self._execute("""
                SELECT m.match_id, m.league_id, m.match_date, m.home_team_id, m.away_team_id,
                       ht.name_en as home_team, at.name_en as away_team,
                       m.sb_match_id, m.source
                FROM matches m
                LEFT JOIN teams ht ON m.home_team_id = ht.team_id
                LEFT JOIN teams at ON m.away_team_id = at.team_id
                WHERE m.league_id = ?
                  AND m.home_goals IS NULL
                  AND m.match_date < date('now')
                ORDER BY m.match_date DESC
                LIMIT 500
            """, (league_id,)).fetchall()
        else:
            matches = self._execute("""
                SELECT m.match_id, m.league_id, m.match_date, m.home_team_id, m.away_team_id,
                       ht.name_en as home_team, at.name_en as away_team,
                       m.sb_match_id, m.source
                FROM matches m
                LEFT JOIN teams ht ON m.home_team_id = ht.team_id
                LEFT JOIN teams at ON m.away_team_id = at.team_id
                WHERE m.home_goals IS NULL
                  AND m.match_date < date('now')
                ORDER BY m.match_date DESC
                LIMIT 500
            """).fetchall()

        result["total"] = len(matches)
        if not matches:
            return result

        # 尝试从API获取结果
        config = self._load_api_config()
        api_football_key = config.get("api_football", {}).get("api_key", "")

        if not api_football_key:
            result["errors"].append("API-Football key 未配置")
            return result

        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            # 按日期分组查询
            from collections import defaultdict
            by_date = defaultdict(list)
            for m in matches:
                by_date[str(m["match_date"])[:10]].append(dict(m))

            for date_str, date_matches in by_date.items():
                try:
                    resp = await client.get(
                        "https://v3.football.api-sports.io/fixtures",
                        headers={"x-apisports-key": api_football_key},
                        params={"date": date_str, "timezone": "Europe/London"},
                    )
                    resp.raise_for_status()
                    fixtures = resp.json().get("response", [])

                    for fixture in fixtures:
                        fi = fixture.get("fixture", {})
                        goals = fixture.get("goals", {})
                        teams = fixture.get("teams", {})

                        if goals.get("home") is None:
                            continue

                        api_id = fi.get("id")
                        home_team = teams.get("home", {}).get("name", "")
                        away_team = teams.get("away", {}).get("name", "")

                        # 匹配到我们的比赛
                        for m in date_matches:
                            matched = False
                            if api_id and m.get("sb_match_id") == str(api_id):
                                matched = True
                            elif home_team and m.get("home_team") and (
                                m["home_team"] == home_team or
                                m["home_team"].replace(" FC", "") == home_team.replace(" FC", "")
                            ):
                                matched = True

                            if matched:
                                self._execute("""
                                    UPDATE matches
                                    SET home_goals = ?, away_goals = ?,
                                        home_odds = ?, draw_odds = ?, away_odds = ?
                                    WHERE match_id = ?
                                """, (
                                    goals["home"], goals["away"],
                                    None, None, None,
                                    m["match_id"],
                                ))
                                result["updated"] += 1
                                break

                except Exception as e:
                    result["errors"].append(f"日期 {date_str}: {e}")

                await asyncio.sleep(1)  # API rate limit

        self.conn.commit()
        logger.info(f"比赛结果同步完成: {result['updated']}/{result['total']}")
        return result

    # ========== 7. 球队中文名同步 ==========
    def sync_team_chinese_names(self) -> dict:
        """从linkage文件同步球队中文名"""
        result = {"total": 0, "updated": 0, "errors": []}

        mapping_file = LINKAGE_DIR / "team_chinese_names.json"
        if not mapping_file.exists():
            result["errors"].append("team_chinese_names.json 不存在")
            return result

        with open(mapping_file, "r", encoding="utf-8") as f:
            team_map = json.load(f)

        for en_name, cn_name in team_map.items():
            result["total"] += 1
            try:
                cur = self._execute(
                    "UPDATE teams SET name_cn = ? WHERE name_en = ? AND (name_cn IS NULL OR name_cn = '')",
                    (cn_name, en_name),
                )
                result["updated"] += cur.rowcount
            except Exception as e:
                result["errors"].append(f"更新 {en_name}: {e}")

        self.conn.commit()
        logger.info(f"球队中文名同步完成: {result['updated']}/{result['total']}")
        return result

    # ========== 8. 非AI翻译管道（Sportmonks + TheSportsDB） ==========

    async def sync_team_cn_from_api(self, limit: int = 500) -> dict:
        """从Sportmonks/TheSportsDB API获取球队中文名（非AI）"""
        import aiohttp
        result = {"total": 0, "updated": 0, "errors": []}
        config = self._load_api_config()

        # 1. 尝试Sportmonks（有中文name字段）
        sm_cfg = config.get("sportmonks", {})
        sm_token = sm_cfg.get("api_token", "")
        if sm_token:
            rows = self._execute("""
                SELECT team_id, name_en FROM teams
                WHERE (name_cn IS NULL OR name_cn = '') AND name_en IS NOT NULL
                LIMIT ?
            """, (limit,)).fetchall()
            result["total"] = len(rows)

            async with aiohttp.ClientSession() as session:
                for row in rows:
                    try:
                        # Sportmonks search by name
                        url = f"https://api.sportmonks.com/v3/football/teams/search/{row['name_en']}"
                        params = {"api_token": sm_token, "select": "id,name,short_code,image_path"}
                        async with session.get(url, params=params) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get("data") and len(data["data"]) > 0:
                                    team = data["data"][0]
                                    # Sportmonks may have translated name in different locale
                                    cn_name = team.get("name_cn") or team.get("name")
                                    if cn_name and cn_name != row["name_en"]:
                                        self._execute(
                                            "UPDATE teams SET name_cn = ? WHERE team_id = ?",
                                            (cn_name, row["team_id"]),
                                        )
                                        result["updated"] += 1
                        await asyncio.sleep(2)  # rate limit
                    except Exception as e:
                        result["errors"].append(f"Sportmonks {row['name_en']}: {e}")

            self.conn.commit()

        # 2. 尝试TheSportsDB（免费，有strTeamAlternate字段）
        tsdb_cfg = config.get("thesportsdb", {})
        tsdb_url = tsdb_cfg.get("base_url", "https://www.thesportsdb.com/api/v1/json/3")
        if result["updated"] < limit:
            remaining = limit - result["updated"]
            rows = self._execute("""
                SELECT team_id, name_en FROM teams
                WHERE (name_cn IS NULL OR name_cn = '') AND name_en IS NOT NULL
                LIMIT ?
            """, (remaining,)).fetchall()
            result["total"] += len(rows)

            async with aiohttp.ClientSession() as session:
                for row in rows:
                    try:
                        url = f"{tsdb_url}/searchteams.php?t={row['name_en']}"
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                teams = data.get("teams") or []
                                if teams:
                                    team = teams[0]
                                    # TheSportsDB strTeamAlternate sometimes has Chinese
                                    alt = team.get("strTeamAlternate", "")
                                    if alt and any('一' <= c <= '鿿' for c in alt):
                                        self._execute(
                                            "UPDATE teams SET name_cn = ? WHERE team_id = ?",
                                            (alt, row["team_id"]),
                                        )
                                        result["updated"] += 1
                        await asyncio.sleep(1)
                    except Exception as e:
                        result["errors"].append(f"TheSportsDB {row['name_en']}: {e}")

            self.conn.commit()

        logger.info(f"API球队中文名同步: {result['updated']}/{result['total']}")
        return result

    async def sync_league_cn_from_api(self, limit: int = 200) -> dict:
        """从Sportmonks/TheSportsDB API获取联赛中文名（非AI）"""
        import aiohttp
        result = {"total": 0, "updated":  0, "errors": []}
        config = self._load_api_config()

        # TheSportsDB联赛搜索
        tsdb_url = config.get("thesportsdb", {}).get("base_url", "https://www.thesportsdb.com/api/v1/json/3")
        rows = self._execute("""
            SELECT league_id, name_en FROM leagues
            WHERE (name_cn IS NULL OR name_cn = '') AND name_en IS NOT NULL
            LIMIT ?
        """, (limit,)).fetchall()
        result["total"] = len(rows)

        async with aiohttp.ClientSession() as session:
            for row in rows:
                try:
                    url = f"{tsdb_url}/searchteams.php?t={row['name_en']}"
                    # Try league search instead
                    url = f"{tsdb_url}/allleagues.php"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            leagues = data.get("leagues") or []
                            for lg in leagues:
                                if lg.get("strLeague") == row["name_en"]:
                                    alt = lg.get("strLeagueAlternate", "")
                                    if alt and any('一' <= c <= '鿿' for c in alt):
                                        self._execute(
                                            "UPDATE leagues SET name_cn = ? WHERE league_id = ?",
                                            (alt, row["league_id"]),
                                        )
                                        result["updated"] += 1
                                    break
                    await asyncio.sleep(1)
                except Exception as e:
                    result["errors"].append(f"TheSportsDB {row['name_en']}: {e}")

        self.conn.commit()
        logger.info(f"API联赛中文名同步: {result['updated']}/{result['total']}")
        return result

    # ========== 工具方法 ==========
    def _load_api_config(self) -> dict:
        config_path = Path(__file__).parent.parent.parent.parent / "api_config.json"
        if not config_path.exists():
            return {}
        with open(config_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        # 将嵌套结构映射到代码期望的扁平格式
        apis = raw.get("apis", {})
        config = {}
        for src_name, api_cfg in apis.items():
            key = api_cfg.get("api_key") or api_cfg.get("api_token") or ""
            base_url = api_cfg.get("base_url", "")
            # 映射key名称到代码使用的格式
            dest_name = src_name
            if src_name == "apifootball":
                dest_name = "api_football"
            config[dest_name] = {
                "api_key": key,
                "base_url": base_url,
                "api_token": key,
            }
        # 保留rapidapi（顶层）
        if "rapidapi" in raw:
            config["rapidapi"] = raw["rapidapi"]
        return config

    def get_data_gaps(self) -> dict:
        """检测数据缺口"""
        gaps = {}

        # 缺少规则的联赛
        no_rules = self._execute("""
            SELECT COUNT(*) as cnt FROM leagues l
            LEFT JOIN league_rules r ON l.league_id = r.league_id
            WHERE r.league_id IS NULL AND l.competition_type = 'league'
        """).fetchone()["cnt"]
        gaps["missing_league_rules"] = no_rules

        # 缺少中文名的球员
        no_cn_players = self._execute("""
            SELECT COUNT(*) as cnt FROM players
            WHERE name_cn IS NULL OR name_cn = ''
        """).fetchone()["cnt"]
        gaps["missing_player_cn"] = no_cn_players

        # 缺少中文名的球队
        no_cn_teams = self._execute("""
            SELECT COUNT(*) as cnt FROM teams
            WHERE name_cn IS NULL OR name_cn = ''
        """).fetchone()["cnt"]
        gaps["missing_team_cn"] = no_cn_teams

        # 缺少中文名的国家
        no_cn_countries = self._execute("""
            SELECT COUNT(*) as cnt FROM leagues
            WHERE country_cn IS NULL OR country_cn = ''
        """).fetchone()["cnt"]
        gaps["missing_country_cn"] = no_cn_countries

        # 缺少结果的已结束比赛
        no_result = self._execute("""
            SELECT COUNT(*) as cnt FROM matches
            WHERE home_goals IS NULL AND match_date < date('now')
        """).fetchone()["cnt"]
        gaps["missing_match_scores"] = no_result

        # 缺少中文名的联赛
        no_cn_leagues = self._execute("""
            SELECT COUNT(*) as cnt FROM leagues
            WHERE name_cn IS NULL OR name_cn = ''
        """).fetchone()["cnt"]
        gaps["missing_league_cn"] = no_cn_leagues

        return gaps

    async def run_full_sync(self) -> dict:
        """执行完整数据补充流程"""
        overall = {"started_at": datetime.now().isoformat(), "steps": {}}

        # 1. 国家中文名
        overall["steps"]["country_cn"] = self.sync_country_chinese_names()

        # 2. 球队中文名
        overall["steps"]["team_cn"] = self.sync_team_chinese_names()

        # 3. 联赛规则
        overall["steps"]["league_rules"] = self.sync_league_rules()

        # 4. 联赛中文名
        overall["steps"]["league_cn"] = await self.sync_league_chinese_names()

        # 5. 球员中文名
        overall["steps"]["player_cn"] = await self.sync_player_chinese_names()

        # 6. season_id修复
        overall["steps"]["season_id_fix"] = self.fix_match_season_ids()

        # 7. 比赛结果同步
        overall["steps"]["match_results"] = await self.sync_finished_match_results()

        overall["completed_at"] = datetime.now().isoformat()
        overall["gaps_after"] = self.get_data_gaps()

        return overall
