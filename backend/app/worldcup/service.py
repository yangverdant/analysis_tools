import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.time_utils import BEIJING_TZ

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_MATCHES_PATH = PROJECT_ROOT / "data" / "world_cup" / "wc_2026_matches.json"
THIRD_PLACE_TABLE_PATH = PROJECT_ROOT / "data" / "world_cup" / "wc_2026_third_place_table.wiki"
API_CONFIG_PATH = PROJECT_ROOT / "config" / "api_config.json"
GROUP_KEYS = list("ABCDEFGHIJKL")
THIRD_PLACE_ASSIGNMENT_COLUMNS = ["1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L"]
THIRD_PLACE_WINNER_MATCH = {
    "1A": 79,
    "1B": 85,
    "1D": 81,
    "1E": 74,
    "1G": 82,
    "1I": 77,
    "1K": 87,
    "1L": 80,
}

TEAM_CN_BY_TLA = {
    "ALG": "\u963f\u5c14\u53ca\u5229\u4e9a",
    "ARG": "\u963f\u6839\u5ef7",
    "AUS": "\u6fb3\u5927\u5229\u4e9a",
    "AUT": "\u5965\u5730\u5229",
    "BEL": "\u6bd4\u5229\u65f6",
    "BIH": "\u6ce2\u9ed1",
    "BRA": "\u5df4\u897f",
    "CAN": "\u52a0\u62ff\u5927",
    "CIV": "\u79d1\u7279\u8fea\u74e6",
    "COD": "\u521a\u679c\uff08\u91d1\uff09",
    "COL": "\u54e5\u4f26\u6bd4\u4e9a",
    "CPV": "\u4f5b\u5f97\u89d2",
    "CRO": "\u514b\u7f57\u5730\u4e9a",
    "CUW": "\u5e93\u62c9\u7d22",
    "CZE": "\u6377\u514b",
    "ECU": "\u5384\u74dc\u591a\u5c14",
    "EGY": "\u57c3\u53ca",
    "ENG": "\u82f1\u683c\u5170",
    "ESP": "\u897f\u73ed\u7259",
    "FRA": "\u6cd5\u56fd",
    "GER": "\u5fb7\u56fd",
    "GHA": "\u52a0\u7eb3",
    "HAI": "\u6d77\u5730",
    "IRN": "\u4f0a\u6717",
    "IRQ": "\u4f0a\u62c9\u514b",
    "JOR": "\u7ea6\u65e6",
    "JPN": "\u65e5\u672c",
    "KOR": "\u97e9\u56fd",
    "KSA": "\u6c99\u7279\u963f\u62c9\u4f2f",
    "MAR": "\u6469\u6d1b\u54e5",
    "MEX": "\u58a8\u897f\u54e5",
    "NED": "\u8377\u5170",
    "NOR": "\u632a\u5a01",
    "NZL": "\u65b0\u897f\u5170",
    "PAN": "\u5df4\u62ff\u9a6c",
    "PAR": "\u5df4\u62c9\u572d",
    "POR": "\u8461\u8404\u7259",
    "QAT": "\u5361\u5854\u5c14",
    "RSA": "\u5357\u975e",
    "SCO": "\u82cf\u683c\u5170",
    "SEN": "\u585e\u5185\u52a0\u5c14",
    "SUI": "\u745e\u58eb",
    "SWE": "\u745e\u5178",
    "TUN": "\u7a81\u5c3c\u65af",
    "TUR": "\u571f\u8033\u5176",
    "URY": "\u4e4c\u62c9\u572d",
    "URU": "\u4e4c\u62c9\u572d",
    "USA": "\u7f8e\u56fd",
    "UZB": "\u4e4c\u5179\u522b\u514b\u65af\u5766",
}
TEAM_CN_BY_NAME = {
    "Bosnia-H.": "\u6ce2\u9ed1",
    "Bosnia-Herzegovina": "\u6ce2\u9ed1",
    "Cape Verde": "\u4f5b\u5f97\u89d2",
    "Cape Verde Islands": "\u4f5b\u5f97\u89d2",
    "Congo DR": "\u521a\u679c\uff08\u91d1\uff09",
    "Curacao": "\u5e93\u62c9\u7d22",
    "Cura\u00e7ao": "\u5e93\u62c9\u7d22",
    "Czechia": "\u6377\u514b",
    "DR Congo": "\u521a\u679c\uff08\u91d1\uff09",
    "Ivory Coast": "\u79d1\u7279\u8fea\u74e6",
    "Korea Republic": "\u97e9\u56fd",
    "New Zealand": "\u65b0\u897f\u5170",
    "Saudi Arabia": "\u6c99\u7279\u963f\u62c9\u4f2f",
    "South Africa": "\u5357\u975e",
    "South Korea": "\u97e9\u56fd",
    "USA": "\u7f8e\u56fd",
    "United States": "\u7f8e\u56fd",
}

RULES: Dict[str, Any] = {
    "competition_code": "WC",
    "name": "FIFA World Cup 2026",
    "hosts": ["Canada", "Mexico", "United States"],
    "teams_count": 48,
    "group_count": 12,
    "group_size": 4,
    "group_stage_matches_per_team": 3,
    "points": {"win": 3, "draw": 1, "loss": 0},
    "advancement": {"direct_from_each_group": 2, "best_third_place": 8, "knockout_teams": 32},
    "knockout": {
        "rounds": ["round_of_32", "round_of_16", "quarterfinals", "semifinals", "third_place", "final"],
        "draw_resolution": "extra_time_then_penalties",
    },
    "group_ranking_order": [
        "points", "goal_difference", "goals_for", "head_to_head_points",
        "head_to_head_goal_difference", "head_to_head_goals_for", "fair_play_points", "drawing_of_lots",
    ],
    "third_place_ranking_order": ["points", "goal_difference", "goals_for", "fair_play_points", "drawing_of_lots"],
    "round_of_32_assignment": {
        "tree": "fixed_before_tournament",
        "third_place_team_names": "dynamic_from_current_or_final_group_table",
        "third_place_slots": "fixed_by_assignment_table_after_the_eight_qualified_third_place_groups_are_known",
    },
    "analysis_impacts": [
        "Third-place qualification changes draw and goal-difference incentives.",
        "Last group matches need same-group simultaneous-match context.",
        "Four points can be close to safe; three points may require margin chasing.",
        "Tie-breakers beyond goals need official fair-play/head-to-head data.",
    ],
}

BRACKET = [
    (73, "round_of_32", "2026-06-28", "Inglewood", "Runner-up Group A", "Runner-up Group B"),
    (74, "round_of_32", "2026-06-29", "Foxborough", "Winner Group E", "3rd Group A/B/C/D/F"),
    (75, "round_of_32", "2026-06-29", "Guadalupe", "Winner Group F", "Runner-up Group C"),
    (76, "round_of_32", "2026-06-29", "Houston", "Winner Group C", "Runner-up Group F"),
    (77, "round_of_32", "2026-06-30", "East Rutherford", "Winner Group I", "3rd Group C/D/F/G/H"),
    (78, "round_of_32", "2026-06-30", "Arlington", "Runner-up Group E", "Runner-up Group I"),
    (79, "round_of_32", "2026-06-30", "Mexico City", "Winner Group A", "3rd Group C/E/F/H/I"),
    (80, "round_of_32", "2026-07-01", "Atlanta", "Winner Group L", "3rd Group E/H/I/J/K"),
    (81, "round_of_32", "2026-07-01", "Santa Clara", "Winner Group D", "3rd Group B/E/F/I/J"),
    (82, "round_of_32", "2026-07-01", "Seattle", "Winner Group G", "3rd Group A/E/H/I/J"),
    (83, "round_of_32", "2026-07-02", "Toronto", "Runner-up Group K", "Runner-up Group L"),
    (84, "round_of_32", "2026-07-02", "Inglewood", "Winner Group H", "Runner-up Group J"),
    (85, "round_of_32", "2026-07-02", "Vancouver", "Winner Group B", "3rd Group E/F/G/I/J"),
    (86, "round_of_32", "2026-07-03", "Miami Gardens", "Winner Group J", "Runner-up Group H"),
    (87, "round_of_32", "2026-07-03", "Kansas City", "Winner Group K", "3rd Group D/E/I/J/L"),
    (88, "round_of_32", "2026-07-03", "Arlington", "Runner-up Group D", "Runner-up Group G"),
    (89, "round_of_16", "2026-07-04", "Philadelphia", "Winner Match 74", "Winner Match 77"),
    (90, "round_of_16", "2026-07-04", "Houston", "Winner Match 73", "Winner Match 75"),
    (91, "round_of_16", "2026-07-05", "East Rutherford", "Winner Match 76", "Winner Match 78"),
    (92, "round_of_16", "2026-07-05", "Mexico City", "Winner Match 79", "Winner Match 80"),
    (93, "round_of_16", "2026-07-06", "Arlington", "Winner Match 83", "Winner Match 84"),
    (94, "round_of_16", "2026-07-06", "Seattle", "Winner Match 81", "Winner Match 82"),
    (95, "round_of_16", "2026-07-07", "Atlanta", "Winner Match 86", "Winner Match 88"),
    (96, "round_of_16", "2026-07-07", "Vancouver", "Winner Match 85", "Winner Match 87"),
    (97, "quarterfinals", "2026-07-09", "Foxborough", "Winner Match 89", "Winner Match 90"),
    (98, "quarterfinals", "2026-07-10", "Inglewood", "Winner Match 93", "Winner Match 94"),
    (99, "quarterfinals", "2026-07-11", "Miami Gardens", "Winner Match 91", "Winner Match 92"),
    (100, "quarterfinals", "2026-07-11", "Kansas City", "Winner Match 95", "Winner Match 96"),
    (101, "semifinals", "2026-07-14", "Arlington", "Winner Match 97", "Winner Match 98"),
    (102, "semifinals", "2026-07-15", "Atlanta", "Winner Match 99", "Winner Match 100"),
    (103, "third_place", "2026-07-18", "Miami Gardens", "Loser Match 101", "Loser Match 102"),
    (104, "final", "2026-07-19", "East Rutherford", "Winner Match 101", "Winner Match 102"),
]


class WorldCupContextService:
    _third_place_assignment_cache: Optional[Dict[str, Dict[str, str]]] = None

    def get_context(self, live: bool = True, include_matches: bool = False) -> Dict[str, Any]:
        matches, data_status = self._load_matches(live)
        groups = self._groups(matches)
        third_place_table = self._third_table(groups)
        knockout = self._knockout(matches, groups, third_place_table)
        context = {
            "tournament": {
                "name": RULES["name"],
                "season": 2026,
                "start_date": "2026-06-11",
                "end_date": "2026-07-19",
                "hosts": RULES["hosts"],
            },
            "rules": RULES,
            "data_status": data_status,
            "matches_summary": self._summary(matches),
            "groups": groups,
            "third_place_table": third_place_table,
            "knockout": knockout,
            "sources": [
                {"name": "football-data.org", "type": "api", "status": "primary_when_live_enabled"},
                {"name": "FIFA World Cup 2026 Regulations", "type": "official_rule_reference", "status": "manual_structured_reference"},
                {"name": str(LOCAL_MATCHES_PATH.relative_to(PROJECT_ROOT)), "type": "local_file", "status": "fallback"},
                {"name": str(THIRD_PLACE_TABLE_PATH.relative_to(PROJECT_ROOT)), "type": "fixed_rule_table", "status": "round_of_32_third_place_assignment"},
            ],
        }
        if include_matches:
            context["matches"] = matches
        return context

    def get_rules(self) -> Dict[str, Any]:
        return {"rules": RULES, "round_of_32_slots": self._slot_dicts(BRACKET[:16])}

    def get_groups(self, live: bool = True) -> Dict[str, Any]:
        context = self.get_context(live=live)
        return {"data_status": context["data_status"], "groups": context["groups"], "third_place_table": context["third_place_table"]}

    def get_knockout(self, live: bool = True) -> Dict[str, Any]:
        context = self.get_context(live=live)
        return {"data_status": context["data_status"], "third_place_table": context["third_place_table"], "knockout": context["knockout"]}

    def get_match_context(self, match_id: str, live: bool = True) -> Dict[str, Any]:
        context = self.get_context(live=live, include_matches=True)
        match = next((m for m in context["matches"] if str(m.get("match_id")) == str(match_id)), None)
        if not match:
            raise KeyError(match_id)
        group = self._group_key(match.get("group"))
        return self._single_match_context(context, match, group)

    def get_match_context_by_teams(
        self,
        home_team: str,
        away_team: str,
        match_date: Optional[str] = None,
        live: bool = True,
    ) -> Dict[str, Any]:
        """Find a World Cup match by team names and return analysis-ready context.

        The lottery feed uses Beijing dates while football-data.org fixtures are UTC,
        so date is only a ranking signal. Team-pair matching is authoritative.
        """
        context = self.get_context(live=live, include_matches=True)
        home_key = self._norm_name(home_team)
        away_key = self._norm_name(away_team)
        if not home_key or not away_key:
            raise KeyError("missing_team")

        candidates: List[Tuple[int, Dict[str, Any], bool]] = []
        for match in context["matches"]:
            match_home = match.get("home_team") or {}
            match_away = match.get("away_team") or {}
            home_aliases = self._team_aliases(match_home)
            away_aliases = self._team_aliases(match_away)
            same_order = home_key in home_aliases and away_key in away_aliases
            reverse_order = home_key in away_aliases and away_key in home_aliases
            if not same_order and not reverse_order:
                continue
            score = 100 if same_order else 85
            score += self._date_match_score(match.get("date"), match_date)
            if match.get("stage") == "GROUP_STAGE":
                score += 5
            candidates.append((score, match, reverse_order))

        if not candidates:
            raise KeyError(f"{home_team} vs {away_team}")

        candidates.sort(key=lambda item: item[0], reverse=True)
        _, best_match, reverse_order = candidates[0]
        group = self._group_key(best_match.get("group"))
        payload = self._single_match_context(context, best_match, group)
        payload["matched_by"] = {
            "method": "team_pair",
            "input_home_team": home_team,
            "input_away_team": away_team,
            "input_match_date": match_date,
            "reverse_order": reverse_order,
        }
        return payload

    def _single_match_context(self, context: Dict[str, Any], match: Dict[str, Any], group_key: Optional[str]) -> Dict[str, Any]:
        group = context["groups"].get(group_key) if group_key else None
        standings = (group or {}).get("standings") or []
        home_row = self._standing_for_team(standings, match.get("home_team") or {})
        away_row = self._standing_for_team(standings, match.get("away_team") or {})
        third_rows = context["third_place_table"].get("rows", [])
        cutline = next((row for row in third_rows if row.get("third_rank") == context["third_place_table"].get("advancing_count", 8)), None)

        return {
            "match": match,
            "rules": context["rules"],
            "data_status": context["data_status"],
            "group": self._group_compact(group),
            "teams": {
                "home": home_row,
                "away": away_row,
            },
            "group_stage_context": {
                "group": group_key,
                "matchday": match.get("matchday"),
                "stage": match.get("stage"),
                "group_matches_finished": (group or {}).get("matches_finished", 0),
                "group_matches_total": (group or {}).get("matches_total", 0),
                "remaining_fixtures": self._remaining_group_fixtures(group, match),
                "same_matchday_fixtures": self._same_matchday_fixtures(group, match),
                "finished_fixtures": self._finished_group_fixtures(group, match),
            },
            "third_place_context": {
                "status": context["third_place_table"].get("status"),
                "advancing_count": context["third_place_table"].get("advancing_count", 8),
                "current_cutline": cutline,
                "home_third_rank": self._third_rank_for_team(third_rows, match.get("home_team") or {}),
                "away_third_rank": self._third_rank_for_team(third_rows, match.get("away_team") or {}),
            },
            "knockout_path_context": {
                "status": context["knockout"].get("status"),
                "potential_round_of_32_slots": self._potential_slots_for_group(group_key, context["knockout"]),
                "third_place_assignment": context["knockout"].get("third_place_assignment"),
            },
            "pressure": {
                "home": self._pressure_profile(home_row, match),
                "away": self._pressure_profile(away_row, match),
                "notes": self._pressure_notes(home_row, away_row, match),
            },
        }

    def _group_compact(self, group: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not group:
            return None
        return {
            "group": group.get("group"),
            "name_cn": group.get("name_cn"),
            "status": group.get("status"),
            "matches_total": group.get("matches_total"),
            "matches_finished": group.get("matches_finished"),
            "standings": group.get("standings", []),
        }

    def _remaining_group_fixtures(self, group: Optional[Dict[str, Any]], current_match: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not group:
            return []
        fixtures = []
        current_id = str(current_match.get("match_id") or "")
        current_day = current_match.get("matchday")
        for fixture in group.get("fixtures") or []:
            if str(fixture.get("match_id") or "") == current_id:
                continue
            if self._is_finished(fixture):
                continue
            if current_day and fixture.get("matchday") and fixture.get("matchday") < current_day:
                continue
            fixtures.append(self._fixture_compact(fixture))
        return fixtures

    def _same_matchday_fixtures(self, group: Optional[Dict[str, Any]], current_match: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not group or not current_match.get("matchday"):
            return []
        current_id = str(current_match.get("match_id") or "")
        rows = []
        for fixture in group.get("fixtures") or []:
            if str(fixture.get("match_id") or "") == current_id:
                continue
            if fixture.get("matchday") == current_match.get("matchday"):
                rows.append(self._fixture_compact(fixture))
        return rows

    def _finished_group_fixtures(self, group: Optional[Dict[str, Any]], current_match: Dict[str, Any]) -> List[Dict[str, Any]]:
        """本组已完赛比赛(含比分) — 倒序, 最近完成的在前"""
        if not group:
            return []
        current_id = str(current_match.get("match_id") or "")
        rows = []
        for fixture in group.get("fixtures") or []:
            if str(fixture.get("match_id") or "") == current_id:
                continue
            if self._is_finished(fixture):
                rows.append(self._fixture_compact(fixture))
        # 倒序: 最近完赛的在前(按date+time)
        rows.sort(key=lambda f: (f.get("date") or "", f.get("time") or ""), reverse=True)
        return rows

    def _fixture_compact(self, match: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "match_id": match.get("match_id"),
            "date": match.get("date"),
            "time": match.get("time"),
            "matchday": match.get("matchday"),
            "status": match.get("status"),
            "home_team_cn": self._display_team_name(match.get("home_team")),
            "away_team_cn": self._display_team_name(match.get("away_team")),
            "home_team": (match.get("home_team") or {}).get("name"),
            "away_team": (match.get("away_team") or {}).get("name"),
            "score": match.get("score"),
        }

    def _standing_for_team(self, standings: List[Dict[str, Any]], team: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        team_aliases = self._team_aliases(team)
        for row in standings:
            row_aliases = self._team_aliases({
                "id": row.get("team_id"),
                "name": row.get("team_full_name") or row.get("team_name"),
                "short_name": row.get("team_name"),
                "name_cn": row.get("team_name_cn"),
                "tla": row.get("tla"),
            })
            if team_aliases & row_aliases:
                return row
        return None

    def _third_rank_for_team(self, third_rows: List[Dict[str, Any]], team: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        team_aliases = self._team_aliases(team)
        for row in third_rows:
            row_aliases = self._team_aliases({
                "id": row.get("team_id"),
                "name": row.get("team_full_name") or row.get("team_name"),
                "short_name": row.get("team_name"),
                "name_cn": row.get("team_name_cn"),
                "tla": row.get("tla"),
            })
            if team_aliases & row_aliases:
                return {
                    "third_rank": row.get("third_rank"),
                    "qualification": row.get("qualification"),
                    "points": row.get("points"),
                    "goal_diff": row.get("goal_diff"),
                    "goals_for": row.get("goals_for"),
                }
        return None

    def _potential_slots_for_group(self, group_key: Optional[str], knockout: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not group_key:
            return []
        slots = []
        for item in knockout.get("round_of_32_slots", []):
            slot_pairs = [
                ("team1_slot", "team2_slot", "team2_slot_label", "team2_resolution"),
                ("team2_slot", "team1_slot", "team1_slot_label", "team1_resolution"),
            ]
            for own_key, opp_key, opp_label_key, opp_resolution_key in slot_pairs:
                own_slot = item.get(own_key) or ""
                finish_position = self._slot_finish_position(own_slot, group_key)
                if not finish_position:
                    continue
                slots.append({
                    "finish_position": finish_position,
                    "match_number": item.get("match_number"),
                    "date": item.get("date"),
                    "city": item.get("city"),
                    "own_slot": own_slot,
                    "own_slot_label": self._slot_label_cn(own_slot),
                    "opponent_slot": item.get(opp_key),
                    "opponent_slot_label": item.get(opp_label_key),
                    "opponent_resolution": item.get(opp_resolution_key),
                })
        slots.sort(key=lambda row: (row["finish_position"], row["match_number"] or 999))
        return slots

    def _slot_finish_position(self, slot: str, group_key: str) -> Optional[int]:
        if slot == f"Winner Group {group_key}":
            return 1
        if slot == f"Runner-up Group {group_key}":
            return 2
        if slot.startswith("3rd Group "):
            candidates = [item for item in slot.replace("3rd Group ", "").split("/") if item]
            if group_key in candidates:
                return 3
        return None

    def _pressure_profile(self, row: Optional[Dict[str, Any]], match: Dict[str, Any]) -> Dict[str, Any]:
        if not row:
            return {"level": "unknown", "reason": "missing_standing"}
        played = int(row.get("played") or 0)
        points = int(row.get("points") or 0)
        remaining_before = max(3 - played, 0)
        max_points = points + remaining_before * 3
        matchday = int(match.get("matchday") or 0)
        if matchday <= 1:
            level = "medium"
            reason = "opening_round_positioning"
        elif matchday == 2:
            if points >= 3:
                level = "medium"
                reason = "win_can_push_direct_qualification"
            elif points <= 1:
                level = "high"
                reason = "needs_points_before_final_round"
            else:
                level = "medium"
                reason = "group_shape_still_open"
        else:
            if points >= 4:
                level = "medium"
                reason = "protect_or_improve_draw_position"
            elif points == 3:
                level = "high"
                reason = "third_place_and_goal_difference_pressure"
            else:
                level = "very_high"
                reason = "must_win_or_chase_margin"
        return {
            "level": level,
            "reason": reason,
            "points": points,
            "played": played,
            "max_points_before_match": max_points,
            "current_position": row.get("position"),
            "current_qualification": row.get("qualification"),
        }

    def _pressure_notes(self, home_row: Optional[Dict[str, Any]], away_row: Optional[Dict[str, Any]], match: Dict[str, Any]) -> List[str]:
        matchday = match.get("matchday")
        notes = [f"世界杯小组赛第{matchday or '?'}轮，3场后即进入淘汰赛。"]
        if matchday == 2:
            notes.append("第二轮会明显影响第三轮策略：领先队可能控风险，低分队需要抢分。")
        if matchday == 3:
            notes.append("第三轮需要同时关注同组另一场、净胜球、进球数和第三名池排名。")
        if home_row and away_row:
            notes.append(
                f"当前积分：{home_row.get('team_name_cn') or home_row.get('team_name')} {home_row.get('points')}分，"
                f"{away_row.get('team_name_cn') or away_row.get('team_name')} {away_row.get('points')}分。"
            )
        return notes

    def _team_aliases(self, team: Dict[str, Any]) -> set:
        aliases = set()
        for key in ("id", "tla", "name", "short_name", "name_cn", "team_name", "team_name_cn", "team_full_name"):
            value = team.get(key)
            norm = self._norm_name(value)
            if norm:
                aliases.add(norm)
        for key in (team.get("name"), team.get("short_name"), team.get("team_name"), team.get("team_full_name")):
            if key and key in TEAM_CN_BY_NAME:
                aliases.add(self._norm_name(TEAM_CN_BY_NAME[key]))
        return aliases

    def _norm_name(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip().lower()
        text = text.replace("（", "(").replace("）", ")")
        text = text.replace("ré", "re").replace("ç", "c")
        text = re.sub(r"[\s\.\-_'/()]+", "", text)
        return text

    def _date_match_score(self, source_date: Optional[str], target_date: Optional[str]) -> int:
        if not source_date or not target_date:
            return 0
        if source_date[:10] == str(target_date)[:10]:
            return 12
        try:
            left = datetime.strptime(source_date[:10], "%Y-%m-%d").date()
            right = datetime.strptime(str(target_date)[:10], "%Y-%m-%d").date()
            delta = abs((left - right).days)
            if delta == 1:
                return 7
            if delta == 2:
                return 3
        except Exception:
            return 0
        return 0

    def _load_matches(self, live: bool) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        warnings: List[str] = []
        if live:
            try:
                matches = self._fetch_api_matches()
                if matches:
                    return matches, {"source": "football-data.org", "mode": "live_api", "retrieved_at": self._now(), "warnings": warnings}
            except Exception as exc:
                warnings.append(f"live API unavailable: {exc}")
        return self._local_matches(), {"source": "local_file", "mode": "offline_fallback", "path": str(LOCAL_MATCHES_PATH.relative_to(PROJECT_ROOT)), "retrieved_at": self._now(), "warnings": warnings}

    def _fetch_api_matches(self) -> List[Dict[str, Any]]:
        import requests

        token = self._token()
        if not token:
            raise RuntimeError("FOOTBALL_DATA_ORG_TOKEN is not configured")
        session = requests.Session()
        session.trust_env = False
        session.headers.update({"X-Auth-Token": token, "User-Agent": "FootballTools/1.0"})
        response = session.get("https://api.football-data.org/v4/competitions/WC/matches", params={"season": 2026}, timeout=20)
        if response.status_code != 200:
            raise RuntimeError(f"football-data.org HTTP {response.status_code}")
        return [self._api_match(item) for item in response.json().get("matches", [])]

    def _token(self) -> Optional[str]:
        env = os.environ.get("FOOTBALL_DATA_ORG_TOKEN") or os.environ.get("FOOTBALL_DATA_TOKEN")
        if env:
            return env
        try:
            config = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            source = config.get("apis", {}).get("football_data_org", {})
            return source.get("api_token") or source.get("api_key")
        except Exception:
            return None

    def _local_matches(self) -> List[Dict[str, Any]]:
        if not LOCAL_MATCHES_PATH.exists():
            return []
        data = json.loads(LOCAL_MATCHES_PATH.read_text(encoding="utf-8"))
        return [self._local_match(item) for item in data]

    def _api_match(self, item: Dict[str, Any]) -> Dict[str, Any]:
        score = item.get("score") or {}
        full_time = score.get("fullTime") or {}
        half_time = score.get("halfTime") or {}
        utc_date = item.get("utcDate") or ""
        time_payload = self._utc_datetime_payload(utc_date)
        return {
            "match_id": str(item.get("id") or ""),
            "source": "football-data.org",
            "stage": item.get("stage"),
            "group": item.get("group"),
            "matchday": item.get("matchday"),
            "status": item.get("status"),
            "utc_date": utc_date,
            **time_payload,
            "last_updated": item.get("lastUpdated"),
            "home_team": self._team(item.get("homeTeam") or {}),
            "away_team": self._team(item.get("awayTeam") or {}),
            "score": {"winner": score.get("winner"), "duration": score.get("duration"), "home_ft": full_time.get("home"), "away_ft": full_time.get("away"), "home_ht": half_time.get("home"), "away_ht": half_time.get("away")},
            "venue": None,
        }

    def _local_match(self, item: Dict[str, Any]) -> Dict[str, Any]:
        source = item.get("source") or "local_file"
        raw_date = item.get("date") or item.get("match_date")
        raw_time = item.get("time") or item.get("match_time")
        if source == "football_data_org":
            time_payload = self._utc_datetime_payload(None, raw_date, raw_time)
        else:
            time_payload = self._source_datetime_payload(raw_date, raw_time)
        return {
            "match_id": str(item.get("match_id") or ""),
            "source": source,
            "stage": item.get("stage"),
            "group": item.get("group"),
            "matchday": item.get("matchday"),
            "status": item.get("status"),
            "utc_date": time_payload.get("utc_date"),
            **time_payload,
            "last_updated": None,
            "home_team": self._local_team(item, "home"),
            "away_team": self._local_team(item, "away"),
            "score": {"winner": item.get("result"), "duration": "REGULAR", "home_ft": self._to_int(item.get("home_score_ft")), "away_ft": self._to_int(item.get("away_score_ft")), "home_ht": self._to_int(item.get("home_score_ht")), "away_ht": self._to_int(item.get("away_score_ht"))},
            "venue": item.get("venue") or item.get("stadium"),
        }

    def _utc_datetime_payload(
        self,
        utc_text: Optional[str],
        date_text: Optional[str] = None,
        time_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return display time in Beijing while preserving source UTC fields."""
        parsed: Optional[datetime] = None
        try:
            if utc_text:
                iso_text = str(utc_text).replace("Z", "+00:00")
                parsed = datetime.fromisoformat(iso_text)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            elif date_text and time_text:
                parsed = datetime.strptime(f"{date_text} {str(time_text)[:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except Exception:
            parsed = None

        if not parsed:
            return self._source_datetime_payload(date_text, time_text)

        utc_dt = parsed.astimezone(timezone.utc)
        bj_dt = utc_dt.astimezone(BEIJING_TZ)
        return {
            "source_date": utc_dt.strftime("%Y-%m-%d"),
            "source_time": utc_dt.strftime("%H:%M"),
            "source_timezone": "UTC",
            "utc_date": utc_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "date": bj_dt.strftime("%Y-%m-%d"),
            "time": bj_dt.strftime("%H:%M"),
            "beijing_time": bj_dt.strftime("%Y-%m-%d %H:%M:00"),
            "display_timezone": "Asia/Shanghai",
            "time_basis": "utc_converted_to_beijing",
        }

    def _source_datetime_payload(self, date_text: Optional[str], time_text: Optional[str]) -> Dict[str, Any]:
        time_value = str(time_text)[:5] if time_text else None
        return {
            "source_date": date_text,
            "source_time": time_value,
            "source_timezone": "source_local",
            "date": date_text,
            "time": time_value,
            "beijing_time": f"{date_text} {time_value}:00" if date_text and time_value else None,
            "display_timezone": "source_local",
            "time_basis": "source_local",
        }

    def _local_team(self, item: Dict[str, Any], side: str) -> Dict[str, Any]:
        name = item.get(f"{side}_team")
        return self._team({
            "id": item.get(f"{side}_team_id"),
            "name": name,
            "shortName": name,
            "tla": item.get(f"{side}_team_tla"),
            "crest": item.get(f"{side}_team_crest"),
        })

    def _team(self, team: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"id": self._nullable_str(team.get("id")), "name": team.get("name"), "short_name": team.get("shortName") or team.get("short_name"), "tla": team.get("tla"), "crest": team.get("crest")}
        payload["name_cn"] = self._team_cn(payload)
        return payload

    def _groups(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for match in matches:
            if match.get("stage") == "GROUP_STAGE" and match.get("group"):
                grouped[self._group_key(match.get("group"))].append(match)
        result = {}
        for group_key in GROUP_KEYS:
            fixtures = sorted(grouped.get(group_key, []), key=lambda m: ((m.get("date") or ""), (m.get("time") or "")))
            finished = sum(1 for item in fixtures if self._is_finished(item))
            result[group_key] = {
                "group": group_key,
                "name": f"{group_key}\u7ec4",
                "name_en": f"Group {group_key}",
                "name_cn": f"{group_key}\u7ec4",
                "matches_total": len(fixtures),
                "matches_finished": finished,
                "status": "final" if fixtures and finished == len(fixtures) else "live_projection",
                "standings": self._table(group_key, fixtures),
                "fixtures": fixtures,
            }
        return result

    def _table(self, group_key: str, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        teams: Dict[str, Dict[str, Any]] = {}
        order = 0
        for match in fixtures:
            for side in ("home_team", "away_team"):
                team = match.get(side) or {}
                team_id = team.get("id") or team.get("name")
                if not team_id or not team.get("name"):
                    continue
                if team_id not in teams:
                    order += 1
                    teams[team_id] = self._blank_team(team, group_key, order)
            if not self._is_finished(match):
                continue
            home = match.get("home_team") or {}
            away = match.get("away_team") or {}
            home_id = home.get("id") or home.get("name")
            away_id = away.get("id") or away.get("name")
            score = match.get("score") or {}
            if home_id not in teams or away_id not in teams or score.get("home_ft") is None or score.get("away_ft") is None:
                continue
            self._apply_result(teams[home_id], int(score["home_ft"]), int(score["away_ft"]))
            self._apply_result(teams[away_id], int(score["away_ft"]), int(score["home_ft"]))
        rows = list(teams.values())
        if rows and all(int(row.get("played") or 0) == 0 for row in rows):
            rows.sort(key=lambda row: row.get("seed_order") or 99)
            for index, row in enumerate(rows, start=1):
                row["position"] = index
                row["qualification"] = "not_started"
            return rows
        rows.sort(key=lambda row: (-row["points"], -row["goal_diff"], -row["goals_for"], row["goals_against"], row["team_name"]))
        for index, row in enumerate(rows, start=1):
            row["position"] = index
            row["qualification"] = "direct_round_of_32" if index <= 2 else "third_place_pool" if index == 3 else "outside_current_cut"
        return rows

    def _blank_team(self, team: Dict[str, Any], group_key: str, order: int) -> Dict[str, Any]:
        return {
            "group": group_key,
            "team_id": team.get("id"),
            "team_name": team.get("short_name") or team.get("name"),
            "team_name_cn": team.get("name_cn") or self._team_cn(team),
            "team_full_name": team.get("name"),
            "tla": team.get("tla"),
            "crest": team.get("crest"),
            "seed_order": order,
            "position": None,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_diff": 0,
            "points": 0,
            "form": [],
            "qualification": "unknown",
        }

    def _apply_result(self, row: Dict[str, Any], goals_for: int, goals_against: int) -> None:
        row["played"] += 1
        row["goals_for"] += goals_for
        row["goals_against"] += goals_against
        row["goal_diff"] = row["goals_for"] - row["goals_against"]
        if goals_for > goals_against:
            row["won"] += 1
            row["points"] += 3
            row["form"].append("W")
        elif goals_for == goals_against:
            row["drawn"] += 1
            row["points"] += 1
            row["form"].append("D")
        else:
            row["lost"] += 1
            row["form"].append("L")

    def _third_table(self, groups: Dict[str, Any]) -> Dict[str, Any]:
        rows = []
        for group in groups.values():
            standings = group.get("standings") or []
            if len(standings) >= 3:
                row = dict(standings[2])
                row["source_group_status"] = group.get("status")
                rows.append(row)
        rows.sort(key=lambda row: (-row["points"], -row["goal_diff"], -row["goals_for"], row["goals_against"], row["team_name"]))
        all_not_started = bool(rows) and all(int(row.get("played") or 0) == 0 for row in rows)
        for index, row in enumerate(rows, start=1):
            row["third_rank"] = index
            if all_not_started:
                row["qualification"] = "third_place_unresolved"
            else:
                row["qualification"] = "best_third_advancing" if index <= 8 else "third_place_outside_cut"
        return {
            "status": (
                "not_started_projection"
                if all_not_started
                else "final" if rows and all(item.get("source_group_status") == "final" for item in rows)
                else "live_projection"
            ),
            "advancing_count": 8,
            "ranking_order": RULES["third_place_ranking_order"],
            "rows": rows,
            "note": "Round-of-32 third-place assignment depends on Annex C combinations once the eight groups are known.",
        }

    def _knockout(self, matches: List[Dict[str, Any]], groups: Dict[str, Any], third_table: Dict[str, Any]) -> Dict[str, Any]:
        slots = []
        by_stage: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        by_number: Dict[int, Dict[str, Any]] = {}
        self._populate_group_name_cache(groups)
        match_lookup = self._knockout_match_lookup(matches)
        third_place_assignment = self._third_place_assignment(third_table)
        for number, stage, date_text, city, team1_slot, team2_slot in BRACKET:
            item = self._bracket_item(
                number,
                stage,
                date_text,
                city,
                team1_slot,
                team2_slot,
                groups,
                third_table,
                third_place_assignment,
                match_lookup.get(number),
            )
            slots.append(item)
            by_stage[stage].append(item)
            by_number[number] = item
        self._apply_progressed_teams(by_number)
        return {
            "status": "conditional_until_group_stage_complete",
            "round_of_32_slots": by_stage.get("round_of_32", []),
            "bracket_by_stage": dict(by_stage),
            "bracket_graph": self._bracket_graph(by_number),
            "slots": slots,
            "third_place_assignment": third_place_assignment,
        }

    def _knockout_match_lookup(self, matches: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        stage_map = {
            "round_of_32": {"round_of_32", "LAST_32"},
            "round_of_16": {"round_of_16", "LAST_16"},
            "quarterfinals": {"quarterfinals", "QUARTER_FINALS"},
            "semifinals": {"semifinals", "SEMI_FINALS"},
            "third_place": {"third_place", "THIRD_PLACE"},
            "final": {"final", "FINAL"},
        }
        lookup: Dict[int, Dict[str, Any]] = {}
        for bracket_stage, source_stages in stage_map.items():
            bracket_entries = [(number, team1_slot, team2_slot) for number, stage, *_ , team1_slot, team2_slot in BRACKET if stage == bracket_stage]
            source_matches = [match for match in matches if match.get("stage") in source_stages]
            unmatched_sources = list(source_matches)
            for number, team1_slot, team2_slot in bracket_entries:
                best_match = None
                best_score = -1
                for match in unmatched_sources:
                    score = self._match_bracket_score(match, team1_slot, team2_slot)
                    if score > best_score:
                        best_score = score
                        best_match = match
                if best_match and best_score >= 1:
                    lookup[number] = best_match
                    unmatched_sources.remove(best_match)
            # Fallback: remaining matches by position — but only if match has finished (has a result)
            # Unfinished placeholder matches from API often have wrong team assignments
            remaining_numbers = sorted([number for number, stage, *_ in BRACKET if stage == bracket_stage and number not in lookup])
            remaining_numbers.sort()
            remaining_sources = sorted(unmatched_sources, key=lambda match: (match.get("date") or "", match.get("time") or "", str(match.get("match_id") or "")))
            for number, match in zip(remaining_numbers, remaining_sources):
                score = match.get("score") or {}
                has_result = score.get("home_ft") is not None and score.get("away_ft") is not None
                if has_result:
                    lookup[number] = match
        return lookup

    def _match_bracket_score(self, match: Dict[str, Any], team1_slot: str, team2_slot: str) -> int:
        """Score how well an API match fits a bracket slot by team name matching."""
        score = 0
        home = match.get("home_team") or {}
        away = match.get("away_team") or {}
        for slot, team in [(team1_slot, home), (team2_slot, away)]:
            if not team:
                continue
            team_name = self._norm_name(team.get("name") or team.get("short_name") or team.get("tla") or "")
            if not team_name:
                continue
            slot_groups = self._slot_groups(slot)
            if not slot_groups:
                continue
            for group_key in slot_groups:
                group_teams = self._group_team_names(group_key)
                if team_name in group_teams:
                    score += 2
                    break
                for gt in group_teams:
                    if team_name in gt or gt in team_name:
                        score += 1
                        break
        return score

    def _populate_group_name_cache(self, groups: Dict[str, Any]) -> None:
        self._group_name_cache = {}
        for group_key, group in groups.items():
            names = []
            for team in (group.get("standings") or []):
                for field in ("team_name_cn", "name_cn", "team_name", "name", "short_name", "tla", "team_full_name"):
                    val = team.get(field)
                    if val:
                        names.append(self._norm_name(val))
            self._group_name_cache[group_key] = names

    def _slot_groups(self, slot: str) -> List[str]:
        """Extract group keys from a slot string like 'Winner Group E' or '3rd Group A/B/C/D/F'."""
        if not slot:
            return []
        import re
        if slot.startswith("Winner Group ") or slot.startswith("Runner-up Group "):
            return [slot.split()[-1]]
        if slot.startswith("3rd Group "):
            return [g for g in slot.replace("3rd Group ", "").split("/") if g]
        return []

    def _group_team_names(self, group_key: str) -> List[str]:
        """Get normalized team names for a group from cached group data."""
        return getattr(self, '_group_name_cache', {}).get(group_key, [])

    def _bracket_item(
        self,
        number: int,
        stage: str,
        date_text: str,
        city: str,
        team1_slot: str,
        team2_slot: str,
        groups: Dict[str, Any],
        third_table: Dict[str, Any],
        third_place_assignment: Dict[str, Any],
        api_match: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        team1_resolution = self._resolve_slot(team1_slot, groups, third_table, third_place_assignment, number)
        team2_resolution = self._resolve_slot(team2_slot, groups, third_table, third_place_assignment, number)
        if api_match:
            api_score = api_match.get("score") or {}
            api_finished = api_score.get("home_ft") is not None
            team1_resolution = self._with_api_team(api_match.get("home_team"), team1_resolution, force=api_finished)
            team2_resolution = self._with_api_team(api_match.get("away_team"), team2_resolution, force=api_finished)
        return {
            "match_number": number,
            "match_id": (api_match or {}).get("match_id"),
            "stage": stage,
            "date": (api_match or {}).get("date") or date_text,
            "time": (api_match or {}).get("time"),
            "status": (api_match or {}).get("status"),
            "city": city,
            "score": (api_match or {}).get("score"),
            "team1_slot": team1_slot,
            "team2_slot": team2_slot,
            "team1_slot_label": self._slot_label_cn(team1_slot),
            "team2_slot_label": self._slot_label_cn(team2_slot),
            "team1_resolution": team1_resolution,
            "team2_resolution": team2_resolution,
            "participants": [
                self._participant(team1_slot, team1_resolution),
                self._participant(team2_slot, team2_resolution),
            ],
            "feeds_from": self._winner_match_refs(team1_slot, team2_slot),
            "loser_feeds_from": self._loser_match_refs(team1_slot, team2_slot),
        }

    def _with_api_team(self, api_team: Optional[Dict[str, Any]], fallback: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        if not force and fallback.get("status") in ("official_match_team", "resolved_from_previous_match_result", "locked_group_position"):
            return fallback
        if not self._has_team_name(api_team):
            return fallback
        result = dict(fallback)
        result["team"] = api_team
        result["status"] = "official_match_team"
        return result

    def _has_team_name(self, team: Optional[Dict[str, Any]]) -> bool:
        if not team:
            return False
        return bool(team.get("team_name_cn") or team.get("name_cn") or team.get("team_name") or team.get("name") or team.get("team_full_name"))

    def _participant(self, slot: str, resolution: Dict[str, Any]) -> Dict[str, Any]:
        team = resolution.get("team")
        display_name = self._display_team_name(team) if team else self._slot_label_cn(slot)
        return {
            "slot": slot,
            "slot_label": self._slot_label_cn(slot),
            "display_name": display_name,
            "team": team,
            "status": resolution.get("status"),
            "candidate_groups": resolution.get("candidate_groups", []),
            "currently_advancing_candidates": resolution.get("currently_advancing_candidates", []),
            "candidate_rows": resolution.get("candidate_rows", []),
            "currently_advancing_candidate_rows": resolution.get("currently_advancing_candidate_rows", []),
            "assigned_group": resolution.get("assigned_group"),
            "assignment_key": resolution.get("assignment_key"),
            "assignment_source": resolution.get("assignment_source"),
            "resolved": bool(team),
        }

    def _apply_progressed_teams(self, by_number: Dict[int, Dict[str, Any]]) -> None:
        for _ in range(4):
            changed = False
            for item in by_number.values():
                for participant in item.get("participants", []):
                    if participant.get("resolved"):
                        continue
                    team = self._team_from_progress_slot(participant.get("slot"), by_number)
                    if not team:
                        continue
                    participant["team"] = team
                    participant["display_name"] = self._display_team_name(team)
                    participant["status"] = "resolved_from_previous_match_result"
                    participant["resolved"] = True
                    changed = True
            if not changed:
                break

    def _team_from_progress_slot(self, slot: Optional[str], by_number: Dict[int, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not slot:
            return None
        if slot.startswith("Winner Match "):
            return self._result_team(by_number.get(self._match_ref(slot)), "winner")
        if slot.startswith("Loser Match "):
            return self._result_team(by_number.get(self._match_ref(slot)), "loser")
        return None

    def _result_team(self, item: Optional[Dict[str, Any]], side: str) -> Optional[Dict[str, Any]]:
        if not item:
            return None
        participants = item.get("participants") or []
        if len(participants) < 2 or not all(participant.get("team") for participant in participants[:2]):
            return None
        score = item.get("score") or {}
        winner = score.get("winner")
        if winner == "HOME_TEAM":
            winner_index = 0
        elif winner == "AWAY_TEAM":
            winner_index = 1
        elif score.get("home_ft") is not None and score.get("away_ft") is not None and score.get("home_ft") != score.get("away_ft"):
            winner_index = 0 if score.get("home_ft") > score.get("away_ft") else 1
        else:
            return None
        index = winner_index if side == "winner" else 1 - winner_index
        return participants[index].get("team")

    def _bracket_graph(self, by_number: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        final = by_number.get(104)
        final_roots = self._winner_match_refs(final.get("team1_slot"), final.get("team2_slot")) if final else []
        left_root = final_roots[0] if len(final_roots) > 0 else 101
        right_root = final_roots[1] if len(final_roots) > 1 else 102
        return {
            "source": "official_round_of_32_slot_map_with_current_table_projection",
            "left": self._bracket_side("left", left_root, by_number),
            "right": self._bracket_side("right", right_root, by_number),
            "final": self._graph_node(final) if final else None,
            "third_place": self._graph_node(by_number.get(103)) if by_number.get(103) else None,
        }

    def _bracket_side(self, side: str, root_number: int, by_number: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        tree = self._bracket_tree(root_number, by_number)
        leaves = self._tree_leaves(tree)
        leaf_rows = {number: index * 2 + 1 for index, number in enumerate(leaves)}
        self._assign_tree_rows(tree, leaf_rows)
        tree_nodes: List[Dict[str, Any]] = []
        self._flatten_tree(tree, tree_nodes)
        max_depth = max((node.get("depth", 0) for node in tree_nodes), default=0)
        nodes = []
        for tree_node in tree_nodes:
            item = by_number.get(tree_node["match_number"])
            if not item:
                continue
            node = self._graph_node(item)
            node["depth"] = tree_node["depth"]
            node["row"] = tree_node["row"]
            node["column"] = tree_node["depth"] + 1 if side == "left" else max_depth - tree_node["depth"] + 1
            node["children"] = [child["match_number"] for child in tree_node.get("children", [])]
            nodes.append(node)
        columns = []
        for column in range(1, max_depth + 2):
            column_nodes = [node for node in nodes if node.get("column") == column]
            columns.append({"column": column, "nodes": sorted(column_nodes, key=lambda node: node.get("row", 0))})
        return {"root_match": root_number, "max_depth": max_depth, "rows": 16, "columns": columns, "nodes": nodes}

    def _bracket_tree(self, match_number: int, by_number: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        item = by_number.get(match_number) or {}
        children = [self._bracket_tree(number, by_number) for number in item.get("feeds_from", [])]
        depth = max((child["depth"] + 1 for child in children), default=0)
        return {"match_number": match_number, "children": children, "depth": depth, "row": None}

    def _tree_leaves(self, tree: Dict[str, Any]) -> List[int]:
        children = tree.get("children") or []
        if not children:
            return [tree["match_number"]]
        leaves: List[int] = []
        for child in children:
            leaves.extend(self._tree_leaves(child))
        return leaves

    def _assign_tree_rows(self, tree: Dict[str, Any], leaf_rows: Dict[int, int]) -> float:
        children = tree.get("children") or []
        if not children:
            tree["row"] = leaf_rows.get(tree["match_number"], 1)
            return tree["row"]
        child_rows = [self._assign_tree_rows(child, leaf_rows) for child in children]
        row = sum(child_rows) / len(child_rows)
        tree["row"] = int(row) if float(row).is_integer() else row
        return tree["row"]

    def _flatten_tree(self, tree: Dict[str, Any], nodes: List[Dict[str, Any]]) -> None:
        for child in tree.get("children") or []:
            self._flatten_tree(child, nodes)
        nodes.append(tree)

    _CITY_CN = {
        "Inglewood": "英格尔伍德", "Foxborough": "福克斯堡", "Guadalupe": "瓜达卢佩",
        "Houston": "休斯顿", "East Rutherford": "东拉瑟福德", "Arlington": "阿灵顿",
        "Mexico City": "墨西哥城", "Atlanta": "亚特兰大", "Santa Clara": "圣克拉拉",
        "Seattle": "西雅图", "Toronto": "多伦多", "Vancouver": "温哥华",
        "Miami Gardens": "迈阿密花园", "Kansas City": "堪萨斯城",
        "Philadelphia": "费城", "Foxborough": "福克斯堡",
    }

    def _graph_node(self, item: Dict[str, Any]) -> Dict[str, Any]:
        city_en = item.get("city")
        city_cn = self._CITY_CN.get(city_en, city_en)
        return {
            "match_number": item.get("match_number"),
            "match_id": item.get("match_id"),
            "stage": item.get("stage"),
            "date": item.get("date"),
            "time": item.get("time"),
            "status": item.get("status"),
            "city": city_cn,
            "score": item.get("score"),
            "participants": item.get("participants", []),
            "feeds_from": item.get("feeds_from", []),
            "loser_feeds_from": item.get("loser_feeds_from", []),
        }

    def _winner_match_refs(self, *slots: str) -> List[int]:
        return self._match_refs("Winner Match ", *slots)

    def _loser_match_refs(self, *slots: str) -> List[int]:
        return self._match_refs("Loser Match ", *slots)

    def _match_ref(self, slot: str) -> Optional[int]:
        refs = self._match_refs("Winner Match ", slot) or self._match_refs("Loser Match ", slot)
        return refs[0] if refs else None

    def _match_refs(self, prefix: str, *slots: str) -> List[int]:
        refs = []
        for slot in slots:
            if isinstance(slot, str) and slot.startswith(prefix):
                try:
                    refs.append(int(slot.replace(prefix, "")))
                except ValueError:
                    pass
        return refs

    def _slot_label_cn(self, slot: str) -> str:
        if not slot:
            return "待定"
        if slot.startswith("Winner Group "):
            return f"{slot[-1]}\u7ec4\u7b2c\u4e00"
        if slot.startswith("Runner-up Group "):
            return f"{slot[-1]}\u7ec4\u7b2c\u4e8c"
        if slot.startswith("3rd Group "):
            groups = slot.replace("3rd Group ", "")
            return f"\u6700\u4f73\u7b2c\u4e09\uff08{groups}\u7ec4\uff09"
        if slot.startswith("Winner Match "):
            return f"M{slot.replace('Winner Match ', '')}\u80dc\u8005"
        if slot.startswith("Loser Match "):
            return f"M{slot.replace('Loser Match ', '')}\u8d1f\u8005"
        return slot

    def _display_team_name(self, team: Optional[Dict[str, Any]]) -> str:
        if not team:
            return ""
        return team.get("team_name_cn") or team.get("name_cn") or team.get("team_name") or team.get("name") or team.get("team_full_name") or ""

    def _third_place_assignment(self, third_table: Dict[str, Any]) -> Dict[str, Any]:
        advancing_rows = [
            row for row in third_table.get("rows", [])
            if row.get("qualification") == "best_third_advancing" and row.get("group") in GROUP_KEYS
        ]
        qualified_groups = [self._third_place_assignment_input(row) for row in advancing_rows[:8]]
        rule_basis = {
            "tree": "fixed_before_tournament",
            "qualified_third_place_groups": "dynamic_from_group_table",
            "slot_assignment": "fixed_495_combination_table",
            "team_names": "dynamic_from_current_or_final_standings",
        }
        if len(advancing_rows) < 8:
            return {
                "status": "insufficient_third_place_rows",
                "assignment_key": None,
                "winner_assignments": {},
                "match_assignments": {},
                "qualified_groups": qualified_groups,
                "rule_basis": rule_basis,
                "note": "Needs eight current best third-place groups before a round-of-32 assignment can be projected.",
            }

        assignment_key = "".join(sorted(str(row.get("group")) for row in advancing_rows[:8]))
        table = self._third_place_assignment_table()
        winner_assignments = table.get(assignment_key)
        if not winner_assignments:
            return {
                "status": "assignment_table_missing_combination",
                "assignment_key": assignment_key,
                "winner_assignments": {},
                "match_assignments": {},
                "qualified_groups": qualified_groups,
                "rule_basis": rule_basis,
                "note": "Current third-place group combination was not found in the local 2026 assignment table.",
            }

        match_assignments = {
            THIRD_PLACE_WINNER_MATCH[winner_slot]: group
            for winner_slot, group in winner_assignments.items()
            if winner_slot in THIRD_PLACE_WINNER_MATCH
        }
        table_status = "final" if third_table.get("status") == "final" else "live_projection"
        return {
            "status": table_status,
            "assignment_key": assignment_key,
            "winner_assignments": winner_assignments,
            "match_assignments": match_assignments,
            "qualified_groups": qualified_groups,
            "rule_basis": rule_basis,
            "source": str(THIRD_PLACE_TABLE_PATH.relative_to(PROJECT_ROOT)),
            "note": "Projected from the current top-eight third-place groups and the 2026 round-of-32 third-place assignment table.",
        }

    def _third_place_assignment_input(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "group": row.get("group"),
            "third_rank": row.get("third_rank"),
            "team_id": row.get("team_id"),
            "team_name": row.get("team_name"),
            "team_name_cn": row.get("team_name_cn"),
            "team_full_name": row.get("team_full_name"),
            "tla": row.get("tla"),
            "played": row.get("played"),
            "points": row.get("points"),
            "goal_diff": row.get("goal_diff"),
            "goals_for": row.get("goals_for"),
            "qualification": row.get("qualification"),
        }

    def _third_place_assignment_table(self) -> Dict[str, Dict[str, str]]:
        if self._third_place_assignment_cache is not None:
            return self._third_place_assignment_cache
        table: Dict[str, Dict[str, str]] = {}
        if not THIRD_PLACE_TABLE_PATH.exists():
            self._third_place_assignment_cache = table
            return table

        text = THIRD_PLACE_TABLE_PATH.read_text(encoding="utf-8")
        for block in text.split("|-"):
            if '! scope="row"' not in block:
                continue
            groups: List[str] = []
            assignments: List[str] = []
            for line in block.splitlines():
                line = line.strip()
                if not line.startswith("|") or "rowspan" in line:
                    continue
                for cell in line[1:].split("||"):
                    cell = cell.strip()
                    groups.extend(re.findall(r"'''([A-L])'''", cell))
                    match = re.fullmatch(r"3([A-L])", cell)
                    if match:
                        assignments.append(match.group(1))
            if len(groups) == 8 and len(assignments) >= 8:
                key = "".join(sorted(groups))
                table[key] = dict(zip(THIRD_PLACE_ASSIGNMENT_COLUMNS, assignments[-8:]))

        self._third_place_assignment_cache = table
        return table

    def _resolve_slot(
        self,
        slot: str,
        groups: Dict[str, Any],
        third_table: Dict[str, Any],
        third_place_assignment: Dict[str, Any],
        match_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        if slot.startswith("Winner Group "):
            return self._group_position(groups, slot[-1], 1)
        if slot.startswith("Runner-up Group "):
            return self._group_position(groups, slot[-1], 2)
        if slot.startswith("3rd Group "):
            candidates = [item for item in slot.replace("3rd Group ", "").split("/") if item]
            rows_by_group = {item.get("group"): item for item in third_table.get("rows", [])}
            candidate_rows = [rows_by_group[group] for group in candidates if group in rows_by_group]
            advancing_rows = [
                row for row in candidate_rows
                if row.get("qualification") == "best_third_advancing"
            ]
            assigned_group = (third_place_assignment.get("match_assignments") or {}).get(match_number)
            assigned_row = rows_by_group.get(assigned_group) if assigned_group in candidates else None
            status = "conditional_third_place_slot"
            team = None
            if assigned_row:
                status = (
                    "final_third_place_assignment"
                    if third_place_assignment.get("status") == "final"
                    else "projected_third_place_assignment"
                )
                team = assigned_row
            return {
                "status": status,
                "candidate_groups": candidates,
                "currently_advancing_candidates": [row.get("group") for row in advancing_rows],
                "candidate_rows": candidate_rows,
                "currently_advancing_candidate_rows": advancing_rows,
                "assigned_group": assigned_group,
                "assignment_key": third_place_assignment.get("assignment_key"),
                "assignment_source": third_place_assignment.get("source"),
                "team": team,
            }
        return {"status": "depends_on_previous_match", "team": None}

    def _group_position(self, groups: Dict[str, Any], group_key: str, position: int) -> Dict[str, Any]:
        group = groups.get(group_key, {})
        if not group or int(group.get("matches_finished") or 0) == 0:
            return {"status": "unresolved_group_not_started", "team": None}
        standings = group.get("standings") or []
        team = next((item for item in standings if item.get("position") == position), None)
        if not team:
            return {"status": "missing", "team": None}
        if group.get("status") == "final":
            return {"status": "locked_group_position", "team": team}
        return {"status": "projected_from_current_table", "team": team}

    def _summary(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        finished = sum(1 for match in matches if self._is_finished(match))
        return {"total": len(matches), "finished": finished, "remaining": max(len(matches) - finished, 0), "by_stage": dict(Counter(match.get("stage") or "unknown" for match in matches))}

    def _slot_dicts(self, slots: List[Tuple[int, str, str, str, str, str]]) -> List[Dict[str, Any]]:
        return [{"match_number": n, "stage": s, "date": d, "city": c, "team1_slot": t1, "team2_slot": t2} for n, s, d, c, t1, t2 in slots]

    def _group_key(self, group: Optional[str]) -> Optional[str]:
        if not group:
            return None
        text = str(group).upper().replace("GROUP_", "").replace("GROUP ", "")
        return text[-1] if text and text[-1] in GROUP_KEYS else text

    def _is_finished(self, match: Dict[str, Any]) -> bool:
        score = match.get("score") or {}
        return str(match.get("status") or "").upper() in {"FINISHED", "AWARDED"} and score.get("home_ft") is not None and score.get("away_ft") is not None

    def _to_int(self, value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _nullable_str(self, value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return str(value)

    def _team_cn(self, team: Dict[str, Any]) -> Optional[str]:
        tla = team.get("tla")
        if tla and tla in TEAM_CN_BY_TLA:
            return TEAM_CN_BY_TLA[tla]
        for key in (team.get("short_name"), team.get("name")):
            if key and key in TEAM_CN_BY_NAME:
                return TEAM_CN_BY_NAME[key]
        return None

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
