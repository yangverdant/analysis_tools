"""Collection channel registry for intelligence requirements.

This file intentionally describes both canonical services and older tested
scripts. The automation layer can use it to explain why a gap exists and which
collector should be tried before a match is analyzed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class SourceChannel:
    name: str
    requirement_keys: tuple[str, ...]
    kind: str
    command: str
    evidence_tables: tuple[str, ...]
    priority: int
    network: bool = True
    enabled: bool = True
    notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


SOURCE_CHANNELS: tuple[SourceChannel, ...] = (
    SourceChannel(
        name="sporttery_lottery_sync",
        requirement_keys=("base_info", "odds_1x2", "market_movement"),
        kind="canonical_service",
        command="scripts/sporttery_realtime_sync.py --start {date} --days 1 --date-timeout 45 --no-bridge-oddsfe",
        evidence_tables=("lottery_matches", "lottery_odds"),
        priority=10,
        notes="Official Sporttery schedule and SP/RQSPF odds. Fast daily entry point.",
    ),
    SourceChannel(
        name="oddsfe_event_detail",
        requirement_keys=("base_info", "odds_1x2", "market_movement"),
        kind="canonical_service",
        command="scripts/sync_oddsfe_event_details.py --from {date_from} --to {date_to} --apply",
        evidence_tables=("source_artifacts", "lottery_results", "lottery_matches"),
        priority=12,
        notes="Event detail, score, half-time score and raw event evidence.",
    ),
    SourceChannel(
        name="oddsfe_ou_line",
        requirement_keys=("market_movement", "goal_tempo_profile", "data_quality"),
        kind="canonical_service",
        command="scripts/sync_oddsfe_ou_lines.py --from {date_from} --to {date_to} --apply --fetch-live",
        evidence_tables=("oddsfe_matches", "source_artifacts"),
        priority=14,
        notes="Real O/U line source for total-goals analysis.",
    ),
    SourceChannel(
        name="team_match_facts",
        requirement_keys=("recent_form", "goal_tempo_profile", "home_away_profile", "major_tournament_experience"),
        kind="local_builder",
        command="scripts/build_team_match_facts.py --from {date_from} --to {date_to} --apply",
        evidence_tables=("team_match_facts", "lottery_results", "matches"),
        priority=18,
        network=False,
        notes="Settled match facts used for attack/defense, BTTS, totals and half-time tempo.",
    ),
    SourceChannel(
        name="national_teams_multi_channel",
        requirement_keys=("fifa_ranking", "elo_rating", "recent_form", "major_tournament_experience"),
        kind="legacy_script",
        command="scripts/sync_national_teams_multi_channel.py",
        evidence_tables=("teams", "matches", "team_match_facts"),
        priority=28,
        notes="Older national-team mapping/history consolidation script.",
    ),
    SourceChannel(
        name="fifa_ranking_fetcher",
        requirement_keys=("fifa_ranking",),
        kind="fetcher",
        command="fetchers/fifa_ranking/get_ranking.py",
        evidence_tables=("teams", "source_artifacts"),
        priority=30,
        notes="FIFA ranking fetcher or local ranking import path.",
    ),
    SourceChannel(
        name="news_aggregator",
        requirement_keys=("team_news", "injuries_suspensions"),
        kind="canonical_script",
        command="scripts/collect_news_aggregator.py",
        evidence_tables=("team_news", "intelligence_artifacts"),
        priority=34,
        notes="Aggregates zhibo8/dongqiudi/hupu style news when network is enabled.",
    ),
    SourceChannel(
        name="apifootball_match_detail",
        requirement_keys=("expected_lineup", "injuries_suspensions"),
        kind="fetcher",
        command="fetchers/apifootball/get_data.py",
        evidence_tables=("intelligence_artifacts", "match_lineups", "player_status"),
        priority=36,
        notes="API-Football detail/lineup path when external match ids are mapped.",
    ),
    SourceChannel(
        name="espn_match_summary",
        requirement_keys=("expected_lineup", "injuries_suspensions"),
        kind="fetcher",
        command="fetchers/espn/get_lineups.py",
        evidence_tables=("intelligence_artifacts",),
        priority=35,
        notes="ESPN free API: post-match lineups (starters+subs+formation) + league injuries. No auth needed.",
    ),
    SourceChannel(
        name="football_data_org_squad",
        requirement_keys=("expected_lineup",),
        kind="fetcher",
        command="fetchers/football_data_org/get_matches.py teams/{fd_team_id}",
        evidence_tables=("teams", "intelligence_artifacts"),
        priority=37,
        notes="World Cup squad/roster baseline. It is not a confirmed or expected starting XI.",
    ),
    SourceChannel(
        name="api_sports_injuries",
        requirement_keys=("injuries_suspensions", "expected_lineup"),
        kind="fetcher",
        command="fetchers/api_sports/get_data.py",
        evidence_tables=("intelligence_artifacts", "player_status", "match_lineups"),
        priority=38,
        notes="API-Sports/RapidAPI injuries and fixture detail when team ids are mapped.",
    ),
    SourceChannel(
        name="bifen188_lineups",
        requirement_keys=("expected_lineup",),
        kind="fetcher",
        command="fetchers/bifen188/get_lineups.py",
        evidence_tables=("intelligence_artifacts", "match_lineups"),
        priority=40,
        enabled=False,
        notes="DISABLED: site is a blank shell (404 iframe). Do not attempt collection.",
    ),
    SourceChannel(
        name="legacy_team_news_crawler",
        requirement_keys=("team_news", "injuries_suspensions"),
        kind="legacy_script",
        command="backend/scripts/team_news_crawler.py",
        evidence_tables=("team_news", "player_status"),
        priority=44,
        notes="Previously tested team-news crawler; should be wrapped before heavy use.",
    ),
    SourceChannel(
        name="legacy_prematch_crawler",
        requirement_keys=("team_news", "injuries_suspensions", "expected_lineup"),
        kind="legacy_script",
        command="backend/scripts/prematch_crawler.py",
        evidence_tables=("team_news", "player_status", "match_lineups"),
        priority=48,
        notes="Previously tested prematch crawler for lineups and absences.",
    ),
    SourceChannel(
        name="weather_fetcher",
        requirement_keys=("weather", "travel_fatigue"),
        kind="fetcher",
        command="fetchers/weather/get_weather.py",
        evidence_tables=("intelligence_artifacts",),
        priority=55,
        notes="Weather by venue/city; optional unless weather is extreme.",
    ),
    SourceChannel(
        name="worldcup_context_service",
        requirement_keys=("tournament_context", "standings_context"),
        kind="canonical_service",
        command="backend/app/worldcup/service.py",
        evidence_tables=("matches", "lottery_matches", "intelligence_artifacts"),
        priority=20,
        network=False,
        notes="World Cup group standings, third-place pool and knockout slot context.",
    ),
)


def channels_for_requirement(requirement_key: str, *, enabled_only: bool = True) -> List[Dict[str, object]]:
    key = str(requirement_key or "").strip()
    matches = [
        channel
        for channel in SOURCE_CHANNELS
        if key in channel.requirement_keys and (channel.enabled or not enabled_only)
    ]
    return [channel.to_dict() for channel in sorted(matches, key=lambda item: item.priority)]


def preferred_source_names(requirement_key: str) -> List[str]:
    return [str(item["name"]) for item in channels_for_requirement(requirement_key)]


def channel_plan_for_requirements(requirement_keys: Iterable[str]) -> Dict[str, List[Dict[str, object]]]:
    return {
        str(key): channels_for_requirement(str(key))
        for key in requirement_keys
        if str(key or "").strip()
    }
