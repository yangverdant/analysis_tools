import re
import contextlib
import hashlib
import io
import json
import sqlite3
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional
import time

from .schemas import ArtifactCreate, RequirementStatus

# Lineup confidence tiers — maps confidence score to descriptive tier
LINEUP_CONFIDENCE_TIERS = [
    (0.90, "official_lineup", "官方确认首发"),
    (0.75, "confirmed_lineup", "已确认阵容"),
    (0.60, "expected_lineup", "预计首发"),
    (0.38, "squad_only", "仅大名单"),
    (0.25, "news_inferred", "新闻推断"),
    (0.00, "builtin_fallback", "无阵容数据"),
]

def _lineup_tier(confidence: float) -> tuple:
    """Return (tier_name, tier_label) for a lineup confidence score."""
    for threshold, name, label in LINEUP_CONFIDENCE_TIERS:
        if confidence >= threshold:
            return name, label
    return "builtin_fallback", "无阵容数据"

_NEWS_CACHE: Optional[List[Dict[str, Any]]] = None
_LEGACY_TEAM_NEWS_CACHE: Dict[str, Dict[str, Any]] = {}
_LEGACY_LINEUP_CACHE: Dict[str, Any] = {"captured_at": 0.0, "items": [], "errors": []}
_FOOTBALL_DATA_TEAM_CACHE: Dict[str, Dict[str, Any]] = {}
_FOOTBALL_DATA_TEAM_FETCH_COUNT = 0
LEGACY_CACHE_TTL_SECONDS = 15 * 60
FOOTBALL_DATA_TEAM_FETCH_LIMIT = 8

INJURY_NEWS_TYPES = {"injury", "suspension", "return"}
INJURY_TITLE_RE = re.compile(
    r"(injur|suspend|doubt|unavailable|return|"
    r"\u4f24|\u505c\u8d5b|\u7ea2\u724c|\u7981\u8d5b|\u590d\u51fa|\u7f3a\u9635|\u4f24\u75c5)",
    re.IGNORECASE,
)


def _source_health_map(conn) -> Dict[str, str]:
    """Read data_source_health and return {source_name: status} for enabled channels."""
    return {name: info['status'] for name, info in _source_health_detail(conn).items()}


def _source_health_detail(conn) -> Dict[str, Dict]:
    """Read data_source_health and return rich detail per source."""
    from .source_channels import SOURCE_CHANNELS
    channel_sources = set()
    for ch in SOURCE_CHANNELS:
        if not ch.enabled:
            continue
        name_map = {
            "news_aggregator": "zhibo8",
            "apifootball_match_detail": "apifootball",
            "api_sports_injuries": "api_sports",
            "bifen188_lineups": "bifen188",
            "espn_match_summary": "espn_api",
            "football_data_org_squad": "football_data_org",
            "weather_fetcher": "wttr_in",
            "fifa_ranking_fetcher": "fifa_ranking",
        }
        mapped = name_map.get(ch.name)
        if mapped:
            channel_sources.add(mapped)
    if not channel_sources:
        return {}
    try:
        rows = conn.execute(
            """SELECT source_name, status, last_success, last_failure,
                      success_rate, failure_count, updated_at
               FROM data_source_health WHERE source_name IN ({})""".format(
                ",".join("?" for _ in channel_sources)
            ),
            list(channel_sources),
        ).fetchall()
        result = {}
        for row in rows:
            name = row["source_name"]
            status = row["status"] or "unknown"
            next_action = "none"
            if status == "error":
                next_action = "repair_or_downgrade"
            elif status == "degraded":
                next_action = "monitor"
            result[name] = {
                'status': status,
                'last_success': row["last_success"],
                'last_failure': row["last_failure"],
                'success_rate': row["success_rate"],
                'failure_count': row["failure_count"],
                'updated_at': row["updated_at"],
                'next_action': next_action,
            }
        return result
    except Exception:
        return {}


def _collectors_for_gaps(
    gap_keys: Iterable[str],
    health_map: Dict[str, str],
    network: bool = True,
) -> List[str]:
    """Determine which external collectors to run based on gap keys and source health.

    Uses source_channels registry to find available channels for each gap,
    then maps to the external collectors that implement them.
    Skips channels whose health source is in error state.
    """
    from .source_channels import channels_for_requirement

    # Map channel names to external collector keys
    channel_to_collector = {
        "news_aggregator": "team_news",
        "apifootball_match_detail": "expected_lineup",
        "api_sports_injuries": "injuries_suspensions",
        "bifen188_lineups": "expected_lineup",
        "weather_fetcher": "weather",
    }

    # Map channel names to health source names
    channel_to_health = {
        "news_aggregator": "zhibo8",
        "apifootball_match_detail": "apifootball",
        "api_sports_injuries": "api_sports",
        "bifen188_lineups": "bifen188",
        "weather_fetcher": "wttr_in",
    }

    collectors = set()
    for key in gap_keys:
        channels = channels_for_requirement(key, enabled_only=True)
        for ch in channels:
            ch_name = ch.get("name", "")
            collector = channel_to_collector.get(ch_name)
            if not collector:
                continue
            # Check if channel needs network and network is disabled
            if ch.get("network", True) and not network:
                continue
            # Check source health — skip if error
            health_source = channel_to_health.get(ch_name)
            if health_source and health_map.get(health_source) == "error":
                continue
            collectors.add(collector)

    return sorted(collectors)


def run_external_collectors(
    conn,
    job: Dict[str, Any],
    selected: Optional[Iterable[str]] = None,
    network: bool = True,
    *,
    gap_keys: Optional[Iterable[str]] = None,
) -> List[ArtifactCreate]:
    selected_set = {item.strip() for item in selected} if selected else None
    registry = {
        "weather": collect_weather,
        "team_news": collect_team_news,
        "injuries_suspensions": collect_injuries,
        "expected_lineup": collect_expected_lineup,
    }

    # If gap_keys provided, use channel-driven selection
    if gap_keys and not selected:
        health_map = _source_health_map(conn)
        selected_set = set(_collectors_for_gaps(gap_keys, health_map, network))

    artifacts: List[ArtifactCreate] = []
    for key, func in registry.items():
        if selected_set and key not in selected_set:
            continue
        artifacts.append(func(conn, job, network=network))
    return artifacts


def collect_weather(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    old_rf = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        return _collect_weather_impl(conn, job, network)
    finally:
        conn.row_factory = old_rf


def _collect_weather_impl(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    city = _match_city(conn, job) or _team_city(conn, job.get("home_team_id"))
    if not city:
        return _failed("weather", "weather_fallback", "No venue city or team city available for weather lookup.")
    if not network:
        return _failed("weather", "weather_fallback", "Network disabled; weather collector did not call wttr.in.")
    try:
        from fetchers.weather.get_weather import assess_weather_impact, get_match_weather

        weather = get_match_weather(city, date=job.get("match_date"), home_team=job.get("home_team"))
        if not weather:
            return _failed("weather", "wttr.in", f"Weather source returned no data for city={city}.")
        impact = assess_weather_impact(weather)
        return ArtifactCreate(
            requirement_key="weather",
            source="wttr.in",
            payload={"city_used": city, "weather": weather, "impact": impact},
            confidence=0.72,
            status=RequirementStatus.collected,
        )
    except Exception as exc:
        return _failed("weather", "wttr.in", str(exc))


def collect_team_news(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    old_rf = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        return _collect_team_news_impl(conn, job, network)
    finally:
        conn.row_factory = old_rf


def _collect_team_news_impl(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    names = _team_name_tokens(conn, job)
    local_items = _local_team_news(conn, job, days=30)
    news_items: List[Dict[str, Any]] = []
    legacy_items: List[Dict[str, Any]] = []
    errors = []
    if network:
        news_items, errors = _fetch_news_once()
        legacy_items, legacy_errors = _fetch_legacy_team_news(names)
        errors.extend(legacy_errors)
    else:
        errors.append({"source": "news_collectors", "error": "Network disabled; only local team_news was checked."})
    matched = _dedupe_news(local_items + _filter_news(news_items, names) + legacy_items)
    status = RequirementStatus.collected if matched else RequirementStatus.fallback_used
    confidence = 0.72 if matched else 0.35
    return ArtifactCreate(
        requirement_key="team_news",
        source="local_team_news+news_collectors",
        payload={
            "team_tokens": sorted(names),
            "matched": matched[:30],
            "local_matched": local_items[:30],
            "legacy_matched": legacy_items[:30],
            "general_sample": news_items[:10],
            "total_fetched": len(news_items),
            "legacy_total_fetched": len(legacy_items),
            "errors": errors,
        },
        confidence=confidence,
        status=status,
    )


def _fetch_news_once() -> tuple:
    global _NEWS_CACHE
    if _NEWS_CACHE is not None:
        return _NEWS_CACHE, []
    news_items: List[Dict[str, Any]] = []
    errors = []
    for source_name, getter_name in [
        ("zhibo8", "fetchers.news.get_news:get_zhibo8_news"),
        ("dongqiudi", "fetchers.dongqiudi.get_news:get_news"),
        ("hupu", "fetchers.hupu.get_news:get_news"),
    ]:
        try:
            module_name, func_name = getter_name.split(":")
            module = __import__(module_name, fromlist=[func_name])
            getter = getattr(module, func_name)
            for item in getter(limit=30):
                item = dict(item)
                item.setdefault("source", source_name)
                news_items.append(item)
        except Exception as exc:
            errors.append({"source": source_name, "error": str(exc)})
    _NEWS_CACHE = news_items
    return news_items, errors


def _run_with_timeout(func, timeout_seconds: float, source: str):
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func)
    try:
        return future.result(timeout=timeout_seconds), None
    except TimeoutError:
        return None, {"source": source, "error": f"timeout after {timeout_seconds:g}s"}
    except Exception as exc:
        return None, {"source": source, "error": str(exc)}
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _cache_fresh(captured_at: Any) -> bool:
    try:
        return (time.time() - float(captured_at or 0)) <= LEGACY_CACHE_TTL_SECONDS
    except Exception:
        return False


def _fetch_legacy_team_news(tokens: set) -> tuple:
    """Read-only wrapper around the older team-news crawler.

    The legacy crawler knows a few useful Chinese sources, but its save methods
    target older schemas. Keep it as a probe and convert hits into artifacts.
    """
    news_items: List[Dict[str, Any]] = []
    errors = []
    usable_tokens = [token for token in sorted(tokens, key=len, reverse=True) if token and len(token) >= 2][:6]
    if not usable_tokens:
        return news_items, errors
    try:
        from backend.scripts.team_news_crawler import TeamNewsCrawler

        crawler = TeamNewsCrawler(":memory:")
        for token in usable_tokens:
            try:
                cached = _LEGACY_TEAM_NEWS_CACHE.get(token)
                if cached and _cache_fresh(cached.get("captured_at")):
                    fetched = cached.get("items") or []
                    cache_hit = True
                else:
                    def fetch_token():
                        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                            return crawler.crawl_zhibo8_team_news(token) or []

                    fetched, error = _run_with_timeout(fetch_token, 8.0, "legacy_team_news_crawler")
                    if error:
                        error["token"] = token
                        errors.append(error)
                        fetched = []
                    _LEGACY_TEAM_NEWS_CACHE[token] = {
                        "captured_at": time.time(),
                        "items": fetched,
                    }
                    cache_hit = False
                for item in fetched[:8]:
                    title = item.get("title") or item.get("news_title") or ""
                    if not title:
                        continue
                    news_items.append(
                        {
                            "title": title,
                            "url": item.get("url") or item.get("source_url") or "",
                            "date": item.get("date") or item.get("news_date") or "",
                            "source": f"legacy_team_news_crawler:{item.get('source') or 'zhibo8'}",
                            "matched_token": token,
                            "collector_mode": "readonly_probe",
                            "cache_hit": cache_hit,
                        }
                    )
            except Exception as exc:
                errors.append({"source": "legacy_team_news_crawler", "token": token, "error": str(exc)})
    except Exception as exc:
        errors.append({"source": "legacy_team_news_crawler", "error": str(exc)})
    return _dedupe_news(news_items), errors


def collect_injuries(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    old_rf = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        return _collect_injuries_impl(conn, job, network)
    finally:
        conn.row_factory = old_rf


def _collect_injuries_impl(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    ids = _api_sports_team_ids(conn, job)
    apifootball_ids = _apifootball_team_ids(conn, job)
    live_injury_news = _live_injury_news(conn, job, network=network)
    payload = {
        "api_sports": {"home": [], "away": [], "team_ids_used": ids, "errors": []},
        "external_ids": {
            "api_sports": ids,
            "apifootball": apifootball_ids,
        },
        "local_player_status": _local_player_status(conn, job),
        "local_injury_news": _local_injury_news(conn, job, days=30),
        "live_injury_news": live_injury_news,
        "gaps": [],
    }
    if network and any(ids.values()):
        try:
            from fetchers.api_sports.get_data import get_injuries

            if ids.get("home"):
                payload["api_sports"]["home"] = get_injuries(team=ids["home"])
            else:
                payload["gaps"].append("missing home apifootball/api-sports team id")
            if ids.get("away"):
                payload["api_sports"]["away"] = get_injuries(team=ids["away"])
            else:
                payload["gaps"].append("missing away apifootball/api-sports team id")
        except Exception as exc:
            payload["api_sports"]["errors"].append(str(exc))
    elif not network:
        payload["gaps"].append("network disabled; api-sports injury collector skipped")
    else:
        payload["gaps"].append("no api-sports team ids are mapped for this match")
        if any(apifootball_ids.values()):
            payload["gaps"].append("apifootball ids are available but are not reused for api-sports injuries")

    api_hit = bool(payload["api_sports"]["home"] or payload["api_sports"]["away"])

    # ESPN injuries — free API, works during active season
    espn_hit = False
    if network:
        try:
            espn_injuries = _fetch_espn_injuries(job)
            payload["espn"] = espn_injuries
            espn_hit = bool(espn_injuries and (espn_injuries.get("home") or espn_injuries.get("away")))
        except Exception as exc:
            payload["espn"] = {"error": str(exc)}

    local_hit = _has_local_absence_evidence(
        payload["local_player_status"],
        payload["local_injury_news"],
        payload["live_injury_news"],
    )
    payload["summary"] = _injury_summary(payload, api_hit, local_hit)
    if api_hit:
        status = RequirementStatus.collected
        confidence = 0.78
    elif espn_hit:
        status = RequirementStatus.collected
        confidence = 0.70
    elif local_hit:
        status = RequirementStatus.fallback_used
        confidence = 0.55
    else:
        status = RequirementStatus.fallback_used
        confidence = 0.28
    return ArtifactCreate(
        requirement_key="injuries_suspensions",
        source="api_sports+espn+local_status+local_news",
        payload=payload,
        confidence=confidence,
        status=status,
    )


def collect_expected_lineup(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    old_rf = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        return _collect_expected_lineup_impl(conn, job, network)
    finally:
        conn.row_factory = old_rf


def _collect_expected_lineup_impl(conn, job: Dict[str, Any], network: bool = True) -> ArtifactCreate:
    confirmed = _local_match_lineup(conn, job.get("match_id"))
    if confirmed:
        tier_name, tier_label = _lineup_tier(0.85)
        return ArtifactCreate(
            requirement_key="expected_lineup",
            source="match_lineups",
            payload={"mode": "confirmed_or_imported_lineup", "lineup": confirmed, "lineup_confidence_tier": tier_name, "lineup_confidence_label": tier_label},
            confidence=0.85,
            status=RequirementStatus.collected,
        )

    external_match_id = _external_match_id(conn, job)
    errors = []
    if network and external_match_id:
        try:
            from fetchers.apifootball.get_data import get_match_detail

            detail = get_match_detail(str(external_match_id))
            lineup = detail.get("lineup") if detail else None
            if lineup:
                tier_name, tier_label = _lineup_tier(0.72)
                return ArtifactCreate(
                    requirement_key="expected_lineup",
                    source="apifootball",
                    payload={"external_match_id": external_match_id, "lineup": lineup, "raw_match_detail": detail, "lineup_confidence_tier": tier_name, "lineup_confidence_label": tier_label},
                    confidence=0.72,
                    status=RequirementStatus.collected,
                )
            errors.append(f"No lineup returned for external_match_id={external_match_id}.")
        except Exception as exc:
            errors.append(str(exc))
    elif not network:
        errors.append("Network disabled; apifootball lineup collector skipped.")
    else:
        errors.append("No external API match id mapped; lineup requires match-level external id.")

    # ESPN match summary API — provides lineups for completed matches (free, no auth)
    espn_lineup = None
    if network:
        espn_lineup = _fetch_espn_match_lineup(conn, job)
        if espn_lineup and espn_lineup.get("has_lineup"):
            tier_name, tier_label = _lineup_tier(0.82)
            return ArtifactCreate(
                requirement_key="expected_lineup",
                source="espn_match_summary",
                payload={
                    "mode": "espn_post_match_lineup",
                    "lineup": espn_lineup,
                    "lineup_confidence_tier": tier_name,
                    "lineup_confidence_label": tier_label,
                    "gaps": errors + ["ESPN provides post-match lineups only; not pre-match predictions"],
                },
                confidence=0.82,
                status=RequirementStatus.collected,
            )
        if espn_lineup and espn_lineup.get("error"):
            errors.append(f"ESPN lineup: {espn_lineup['error']}")

    legacy_lineup = None
    if network:
        legacy_lineup = _fetch_legacy_expected_lineup(job)
        if legacy_lineup and legacy_lineup.get("matched"):
            tier_name, tier_label = _lineup_tier(0.58)
            return ArtifactCreate(
                requirement_key="expected_lineup",
                source="legacy_prematch_crawler_readonly",
                payload={
                    "mode": "readonly_legacy_lineup_probe",
                    "lineup": legacy_lineup,
                    "gaps": errors,
                    "lineup_confidence_tier": tier_name,
                    "lineup_confidence_label": tier_label,
                },
                confidence=0.58,
                status=RequirementStatus.fallback_used,
            )
        if legacy_lineup and legacy_lineup.get("errors"):
            errors.extend(legacy_lineup.get("errors") or [])

    football_data_squad = _fetch_football_data_squad_context(conn, job, network=network)
    projection = _recent_lineup_projection(conn, job)
    has_projection = bool(
        projection.get("home", {}).get("latest_starting_xi")
        or projection.get("away", {}).get("latest_starting_xi")
    )
    has_football_data_squad = bool(
        (football_data_squad.get("home") or {}).get("squad")
        or (football_data_squad.get("away") or {}).get("squad")
    )
    if has_football_data_squad:
        confidence = 0.52 if has_projection else 0.42
        tier_name, tier_label = _lineup_tier(confidence)
        return ArtifactCreate(
            requirement_key="expected_lineup",
            source="football_data_org_squad+recent_match_lineups_fallback",
            payload={
                "mode": "squad_baseline_not_expected_xi",
                "football_data_squad": football_data_squad,
                "projection": projection,
                "legacy_lineup_probe": legacy_lineup,
                "lineup_confidence_tier": tier_name,
                "lineup_confidence_label": tier_label,
                "gaps": errors
                + [
                    "football-data.org squad is a roster baseline, not confirmed or expected starting XI",
                ],
            },
            confidence=confidence,
            status=RequirementStatus.fallback_used,
        )
    confidence = 0.48 if has_projection else 0.22
    tier_name, tier_label = _lineup_tier(confidence)
    return ArtifactCreate(
        requirement_key="expected_lineup",
        source="recent_match_lineups_fallback",
        payload={
            "mode": "recent_lineup_projection" if has_projection else "lineup_missing",
            "projection": projection,
            "football_data_squad": football_data_squad,
            "legacy_lineup_probe": legacy_lineup,
            "lineup_confidence_tier": tier_name,
            "lineup_confidence_label": tier_label,
            "gaps": errors,
        },
        confidence=confidence,
        status=RequirementStatus.fallback_used,
    )


def _fetch_legacy_expected_lineup(job: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "matched": False,
        "source": "legacy_prematch_crawler",
        "collector_mode": "readonly_probe",
        "home_lineup": [],
        "away_lineup": [],
        "raw_match": None,
        "sample_count": 0,
        "errors": [],
    }
    home = str(job.get("home_team") or "").strip()
    away = str(job.get("away_team") or "").strip()
    if not home or not away:
        result["errors"].append({"source": "legacy_prematch_crawler", "error": "home/away team name missing"})
        return result
    try:
        from backend.scripts.prematch_crawler import PreMatchCrawler

        if _cache_fresh(_LEGACY_LINEUP_CACHE.get("captured_at")):
            lineups = _LEGACY_LINEUP_CACHE.get("items") or []
            result["cache_hit"] = True
        else:
            crawler = PreMatchCrawler(":memory:")

            def fetch_lineups():
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    return crawler.crawl_188bifen_lineups() or []

            lineups, error = _run_with_timeout(fetch_lineups, 18.0, "legacy_prematch_crawler")
            if error:
                result["errors"].append(error)
                lineups = []
            _LEGACY_LINEUP_CACHE["captured_at"] = time.time()
            _LEGACY_LINEUP_CACHE["items"] = lineups
            _LEGACY_LINEUP_CACHE["errors"] = list(result["errors"])
            result["cache_hit"] = False
        result["sample_count"] = len(lineups)
        for item in lineups[:80]:
            item_home = str(item.get("home_team") or "").strip()
            item_away = str(item.get("away_team") or "").strip()
            if _team_name_match(home, item_home) and _team_name_match(away, item_away):
                result.update(
                    {
                        "matched": True,
                        "home_lineup": item.get("home_lineup") or [],
                        "away_lineup": item.get("away_lineup") or [],
                        "raw_match": item,
                    }
                )
                break
    except Exception as exc:
        result["errors"].append({"source": "legacy_prematch_crawler", "error": str(exc)})
    return result


_ESPN_LINEUP_CACHE: Dict[str, Any] = {}


def _fetch_espn_match_lineup(conn, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetch match lineup from ESPN summary API.

    Works for completed matches (returns full starting XI + subs + formation).
    Returns empty rosters for scheduled matches (ESPN doesn't predict lineups).
    Also persists lineup to match_lineups table for future projections.
    """
    home_team = str(job.get("home_team") or "").strip()
    away_team = str(job.get("away_team") or "").strip()
    if not home_team or not away_team:
        return None

    # Check cache
    cache_key = f"{home_team}_vs_{away_team}"
    if cache_key in _ESPN_LINEUP_CACHE:
        cached = _ESPN_LINEUP_CACHE[cache_key]
        if time.time() - cached.get("_ts", 0) < 600:
            return {k: v for k, v in cached.items() if k != "_ts"}

    # Determine ESPN league code from match league
    league = str(job.get("league") or "").strip()
    from fetchers.espn.get_lineups import resolve_league_code, get_league_scoreboard, get_match_lineup

    espn_league = resolve_league_code(league)

    result = {"home": {}, "away": {}, "has_lineup": False, "source": "espn_api"}

    # Strategy: search for the match in the league scoreboard, then get its lineup
    leagues_to_search = [espn_league] if espn_league else []
    # Add common leagues as fallback
    if espn_league != "eng.1":
        leagues_to_search.append("eng.1")

    for lg_code in leagues_to_search:
        if not lg_code:
            continue
        try:
            sb = get_league_scoreboard(lg_code)
            events = sb.get("events", [])
            for ev in events:
                ev_home = ev.get("home_team", "")
                ev_away = ev.get("away_team", "")
                if _team_name_match(home_team, ev_home) and _team_name_match(away_team, ev_away):
                    eid = ev.get("event_id")
                    if eid:
                        lineup = get_match_lineup(str(eid), lg_code)
                        result.update(lineup)
                        result["espn_event_id"] = eid
                        result["espn_league"] = lg_code
                        # Persist to match_lineups for future projections
                        if lineup.get("has_lineup"):
                            _persist_espn_lineup(conn, job, lineup)
                        # Cache result
                        result["_ts"] = time.time()
                        _ESPN_LINEUP_CACHE[cache_key] = dict(result)
                        return {k: v for k, v in result.items() if k != "_ts"}
        except Exception as exc:
            result["error"] = str(exc)
            continue
        break  # Found in first league, stop searching

    return result if result.get("error") else None


def _persist_espn_lineup(conn, job: Dict[str, Any], lineup: Dict[str, Any]) -> None:
    """Write ESPN lineup data to match_lineups table for future projections."""
    match_id = job.get("match_id")
    if not match_id or not _table_exists(conn, "match_lineups"):
        return
    try:
        # Check if lineup already exists for this match
        existing = conn.execute(
            "SELECT COUNT(*) FROM match_lineups WHERE match_id = ?",
            (str(match_id),),
        ).fetchone()[0]
        if existing > 0:
            return  # Already have lineup data

        for side in ("home", "away"):
            side_data = lineup.get(side, {})
            team_type = side
            team_name = side_data.get("team_name", "")
            formation = side_data.get("formation", "")
            if isinstance(formation, dict):
                formation = str(formation)

            for p in side_data.get("starters", []):
                conn.execute(
                    """INSERT OR IGNORE INTO match_lineups
                       (match_id, team_type, player_key, player_name, player_number,
                        position, is_starter, formation, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'espn_api')""",
                    (str(match_id), team_type, p.get("name", ""), p.get("name", ""),
                     p.get("jersey"), p.get("position", ""), 1, formation),
                )
            for p in side_data.get("subs", []):
                conn.execute(
                    """INSERT OR IGNORE INTO match_lineups
                       (match_id, team_type, player_key, player_name, player_number,
                        position, is_starter, formation, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'espn_api')""",
                    (str(match_id), team_type, p.get("name", ""), p.get("name", ""),
                     p.get("jersey"), p.get("position", ""), 0, formation),
                )
        conn.commit()
    except Exception:
        pass  # Best-effort persistence


_ESPN_INJURY_CACHE: Dict[str, Any] = {}


def _fetch_espn_injuries(job: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch injury data from ESPN API (free, no auth).

    Works during active season. Returns empty lists during off-season.
    """
    league = str(job.get("league") or "").strip()
    from fetchers.espn.get_lineups import resolve_league_code, get_league_injuries

    espn_league = resolve_league_code(league)
    if not espn_league:
        return {"home": [], "away": [], "error": f"cannot resolve ESPN league for '{league}'"}

    # Cache by league (injury list is per-league, refreshed infrequently)
    cache_key = espn_league
    if cache_key in _ESPN_INJURY_CACHE:
        cached = _ESPN_INJURY_CACHE[cache_key]
        if time.time() - cached.get("_ts", 0) < 1800:  # 30-min cache
            return {k: v for k, v in cached.items() if k != "_ts"}

    result = {"home": [], "away": [], "league_code": espn_league, "source": "espn_api"}
    try:
        data = get_league_injuries(espn_league)
        all_injuries = data.get("injuries", [])
        # Split by home/away team
        home_team = str(job.get("home_team") or "").strip()
        away_team = str(job.get("away_team") or "").strip()
        for inj in all_injuries:
            team_name = inj.get("team_name", "")
            if _team_name_match(home_team, team_name):
                result["home"].append(inj)
            elif _team_name_match(away_team, team_name):
                result["away"].append(inj)
    except Exception as exc:
        result["error"] = str(exc)

    result["_ts"] = time.time()
    _ESPN_INJURY_CACHE[cache_key] = dict(result)
    return {k: v for k, v in result.items() if k != "_ts"}


def _fetch_football_data_squad_context(conn, job: Dict[str, Any], network: bool = True) -> Dict[str, Any]:
    historical = _latest_football_data_squad_from_intel(conn, str(job.get("job_id") or ""))
    if historical:
        historical["cache_source"] = "intelligence_artifacts"
        _persist_football_data_squad_context(conn, historical)
        return historical

    result = {
        "source": "football-data.org",
        "mode": "squad_baseline_not_expected_xi",
        "home": {},
        "away": {},
        "team_ids_used": _football_data_team_ids(conn, job),
        "errors": [],
        "gaps": [],
    }
    ids = result["team_ids_used"]
    if not network:
        result["gaps"].append("network disabled; football-data.org squad lookup skipped")
        return result
    if not any(ids.values()):
        result["gaps"].append("no football-data.org team ids are mapped for this match")
        return result
    for side in ("home", "away"):
        fd_id = ids.get(side)
        if not fd_id:
            result["gaps"].append(f"missing {side} football-data.org team id")
            continue
        detail = _fetch_football_data_team_detail(conn, str(fd_id))
        if detail.get("error"):
            result["errors"].append({"side": side, "team_id": fd_id, "error": detail.get("error")})
        if detail.get("fetch_limited"):
            result["gaps"].append(detail.get("error") or "football-data.org team detail fetch limit reached")
        result[side] = {
            "team_id": detail.get("team_id") or str(fd_id),
            "name": detail.get("name"),
            "short_name": detail.get("short_name"),
            "country": detail.get("country"),
            "squad_count": len(detail.get("squad") or []),
            "squad": detail.get("squad") or [],
            "note": "Roster baseline only; not a confirmed lineup.",
        }
    return result


def _persist_football_data_squad_context(conn, squad_context: Dict[str, Any]) -> None:
    for side in ("home", "away"):
        detail = dict((squad_context.get(side) or {}))
        team_id = detail.get("team_id")
        if not team_id or not detail.get("squad"):
            continue
        detail.setdefault("source", "football-data.org")
        _record_source_artifact(
            conn,
            source_name="football_data_org",
            source_type="api",
            entity_type="team",
            entity_id=str(team_id),
            payload=detail,
            confidence=0.86,
        )


def _latest_football_data_squad_from_intel(conn, job_id: str) -> Optional[Dict[str, Any]]:
    if not job_id or not _table_exists(conn, "intelligence_artifacts"):
        return None
    try:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM intelligence_artifacts
            WHERE job_id = ?
              AND requirement_key = 'expected_lineup'
              AND source LIKE 'football_data_org_squad%'
            ORDER BY rowid DESC
            LIMIT 5
            """,
            (job_id,),
        ).fetchall()
    except Exception:
        return None
    for row in rows:
        try:
            payload = json.loads(_row_value(row, "payload_json", 0) or "{}")
        except Exception:
            continue
        squad_context = payload.get("football_data_squad") if isinstance(payload, dict) else None
        if not isinstance(squad_context, dict):
            continue
        if (
            (squad_context.get("home") or {}).get("squad")
            or (squad_context.get("away") or {}).get("squad")
        ):
            return squad_context
    return None


def _fetch_football_data_team_detail(conn, team_id: str) -> Dict[str, Any]:
    global _FOOTBALL_DATA_TEAM_FETCH_COUNT
    cached = _FOOTBALL_DATA_TEAM_CACHE.get(team_id)
    if cached:
        return cached
    cached_artifact = _latest_source_artifact_payload(conn, "football_data_org", "team", team_id)
    if cached_artifact and isinstance(cached_artifact, dict):
        cached_artifact["cache_source"] = "source_artifacts"
        _FOOTBALL_DATA_TEAM_CACHE[team_id] = cached_artifact
        return cached_artifact
    if _FOOTBALL_DATA_TEAM_FETCH_COUNT >= FOOTBALL_DATA_TEAM_FETCH_LIMIT:
        return {
            "team_id": team_id,
            "squad": [],
            "fetch_limited": True,
            "error": f"football-data.org team detail fetch limit reached ({FOOTBALL_DATA_TEAM_FETCH_LIMIT})",
        }
    _FOOTBALL_DATA_TEAM_FETCH_COUNT += 1

    def fetch_detail():
        from fetchers.football_data_org.get_matches import get_team_detail

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return get_team_detail(team_id) or {}

    detail, error = _run_with_timeout(fetch_detail, 14.0, "football_data_org_team_detail")
    if error:
        detail = {"team_id": team_id, "squad": [], "error": error.get("error") or str(error)}
    elif not detail:
        detail = {"team_id": team_id, "squad": [], "error": "football-data.org returned empty team detail"}
    if detail and not detail.get("error"):
        _record_source_artifact(
            conn,
            source_name="football_data_org",
            source_type="api",
            entity_type="team",
            entity_id=team_id,
            payload=detail,
            confidence=0.86,
        )
    _FOOTBALL_DATA_TEAM_CACHE[team_id] = detail
    return detail


def _latest_source_artifact_payload(
    conn,
    source_name: str,
    entity_type: str,
    entity_id: str,
) -> Optional[Dict[str, Any]]:
    if not _table_exists(conn, "source_artifacts"):
        return None
    try:
        row = conn.execute(
            """
            SELECT payload_json
            FROM source_artifacts
            WHERE source_name = ?
              AND entity_type = ?
              AND entity_id = ?
            ORDER BY captured_at DESC
            LIMIT 1
            """,
            (source_name, entity_type, str(entity_id)),
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        payload = json.loads(_row_value(row, "payload_json", 0) or "{}")
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _record_source_artifact(
    conn,
    *,
    source_name: str,
    source_type: str,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any],
    confidence: float,
) -> None:
    if not _table_exists(conn, "source_artifacts"):
        return
    try:
        payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        raw_id = f"{source_name}|{entity_type}|{entity_id}|{payload_hash}"
        artifact_id = "art_" + hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:32]
        conn.execute(
            """
            INSERT OR IGNORE INTO source_artifacts
            (artifact_id, source_name, source_type, entity_type, entity_id,
             payload_json, payload_hash, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                source_name,
                source_type,
                entity_type,
                str(entity_id),
                payload_json,
                payload_hash,
                confidence,
            ),
        )
    except Exception:
        return


def _team_name_match(expected: str, observed: str) -> bool:
    a = re.sub(r"\s+", "", str(expected or "").lower())
    b = re.sub(r"\s+", "", str(observed or "").lower())
    if not a or not b:
        return False
    return a in b or b in a


def _failed(key: str, source: str, reason: str) -> ArtifactCreate:
    return ArtifactCreate(
        requirement_key=key,
        source=source,
        payload={"error": reason, "collector_status": "failed"},
        confidence=0.0,
        status=RequirementStatus.failed,
    )


def _table_exists(conn, table: str) -> bool:
    try:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone()
    except Exception:
        return False
    return row is not None


def _row_dict(row) -> Dict[str, Any]:
    if not row:
        return {}
    try:
        return dict(row)
    except (TypeError, ValueError):
        return {}


def _since(match_date: Optional[str], days: int) -> str:
    try:
        base = date.fromisoformat(str(match_date)[:10]) if match_date else date.today()
    except Exception:
        base = date.today()
    return (base - timedelta(days=days)).isoformat()


def _match_city(conn, job: Dict[str, Any]) -> Optional[str]:
    match_id = job.get("match_id")
    if not match_id:
        return None
    try:
        row = conn.execute("SELECT venue_city, venue FROM matches WHERE match_id = ?", (match_id,)).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return row["venue_city"] or row["venue"]


def _team_city(conn, team_id: Optional[int]) -> Optional[str]:
    if not team_id:
        return None
    try:
        row = conn.execute("SELECT city, country, country_cn FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return row["city"] or row["country"] or row["country_cn"]


def _table_columns(conn, table: str) -> set:
    try:
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
    except Exception:
        return set()


def _team_name_tokens(conn, job: Dict[str, Any]) -> set:
    tokens = {job.get("home_team") or "", job.get("away_team") or ""}
    team_columns = _table_columns(conn, "teams")
    name_columns = [
        col for col in (
            "name_en",
            "name_cn",
            "sporttery_name_cn",
            "oddsfe_name_cn",
            "apifootball_name_cn",
            "apifootball_name_en",
            "name_cn_aliases",
        )
        if col in team_columns
    ]
    for team_id in (job.get("home_team_id"), job.get("away_team_id")):
        if not team_id or not name_columns:
            continue
        try:
            row = conn.execute(
                f"SELECT {', '.join(name_columns)} FROM teams WHERE team_id = ?",
                (team_id,),
            ).fetchone()
        except Exception:
            row = None
        if row:
            for value in dict(row).values():
                if not value:
                    continue
                if isinstance(value, str):
                    tokens.update(part.strip() for part in re.split(r"[,/|;\uff0c\u3001]", value) if part.strip())
    return {token for token in tokens if token and len(token) >= 2}


def _filter_news(items: List[Dict[str, Any]], tokens: set) -> List[Dict[str, Any]]:
    matched = []
    for item in items:
        title = item.get("title", "") or ""
        if any(token in title for token in tokens):
            matched.append(item)
    return matched


def _dedupe_news(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        key = item.get("url") or item.get("source_url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _local_team_news(conn, job: Dict[str, Any], days: int = 30, injury_only: bool = False) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    team_ids = [value for value in (job.get("home_team_id"), job.get("away_team_id")) if value]
    if not team_ids:
        return items
    since = _since(job.get("match_date"), days)
    placeholders = ",".join("?" for _ in team_ids)
    if _table_exists(conn, "team_news"):
        try:
            rows = conn.execute(
                f"""
                SELECT news_id, team_id, title, content, news_type, category, impact_level,
                       impact_type, affected_players, news_date, source, source_url, verified
                FROM team_news
                WHERE team_id IN ({placeholders})
                  AND (news_date IS NULL OR news_date >= ?)
                ORDER BY news_date DESC, impact_level DESC
                LIMIT 80
                """,
                (*team_ids, since),
            ).fetchall()
            for row in rows:
                item = _row_dict(row)
                item["source_table"] = "team_news"
                if not injury_only or _is_injury_news(item):
                    items.append(item)
        except Exception as exc:
            items.append({"source_table": "team_news", "error": str(exc)})
    if _table_exists(conn, "team_news_relation") and _table_exists(conn, "news_aggregated"):
        try:
            rows = conn.execute(
                f"""
                SELECT n.id as news_id, r.team_id, n.title, n.content, n.summary,
                       n.news_type, n.sentiment, n.impact_level, n.mentioned_players,
                       n.published_at as news_date, n.source, n.url as source_url
                FROM news_aggregated n
                JOIN team_news_relation r ON r.news_id = n.id
                WHERE r.team_id IN ({placeholders})
                  AND (n.published_at IS NULL OR substr(n.published_at, 1, 10) >= ?)
                ORDER BY n.published_at DESC, n.impact_level DESC
                LIMIT 80
                """,
                (*team_ids, since),
            ).fetchall()
            for row in rows:
                item = _row_dict(row)
                item["source_table"] = "news_aggregated"
                if not injury_only or _is_injury_news(item):
                    items.append(item)
        except Exception as exc:
            items.append({"source_table": "news_aggregated", "error": str(exc)})
    return _dedupe_news(items)


def _local_injury_news(conn, job: Dict[str, Any], days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
    by_team: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for item in _local_team_news(conn, job, days=days, injury_only=True):
        team_id = item.get("team_id")
        if team_id:
            by_team[int(team_id)].append(item)
    return {
        "home": by_team.get(int(job["home_team_id"]), [])[:30] if job.get("home_team_id") else [],
        "away": by_team.get(int(job["away_team_id"]), [])[:30] if job.get("away_team_id") else [],
    }


def _live_injury_news(conn, job: Dict[str, Any], network: bool = True) -> Dict[str, Any]:
    result = {"home": [], "away": [], "total_fetched": 0, "legacy_total_fetched": 0, "errors": []}
    if not network:
        result["errors"].append("network disabled; live injury-news probe skipped")
        return result
    try:
        news_items, errors = _fetch_news_once()
        result["errors"].extend(errors or [])
    except Exception as exc:
        news_items = []
        result["errors"].append({"source": "news_collectors", "error": str(exc)})
    result["total_fetched"] = len(news_items)

    side_tokens = {
        "home": _single_team_name_tokens(conn, job.get("home_team_id"), job.get("home_team")),
        "away": _single_team_name_tokens(conn, job.get("away_team_id"), job.get("away_team")),
    }
    all_tokens = set().union(*side_tokens.values())
    legacy_items: List[Dict[str, Any]] = []
    if all_tokens:
        try:
            legacy_items, legacy_errors = _fetch_legacy_team_news(all_tokens)
            result["errors"].extend(legacy_errors or [])
        except Exception as exc:
            legacy_items = []
            result["errors"].append({"source": "legacy_team_news_crawler", "error": str(exc)})
    result["legacy_total_fetched"] = len(legacy_items)

    for side, tokens in side_tokens.items():
        if not tokens:
            continue
        matched = []
        for item in news_items + legacy_items:
            if not _is_injury_news(item):
                continue
            text = f"{item.get('title') or ''} {item.get('content') or item.get('summary') or ''}"
            text_lower = text.lower()
            if any(str(token).lower() in text_lower for token in tokens):
                enriched = dict(item)
                enriched.setdefault("collector_mode", "live_injury_news_probe")
                matched.append(enriched)
        result[side] = _dedupe_news(matched)[:20]
    return result


def _is_injury_news(item: Dict[str, Any]) -> bool:
    news_type = str(item.get("news_type") or item.get("category") or "").lower()
    if news_type in INJURY_NEWS_TYPES:
        return True
    title = str(item.get("title") or "")
    content = str(item.get("content") or item.get("summary") or "")
    return bool(INJURY_TITLE_RE.search(title) or INJURY_TITLE_RE.search(content))


def _local_player_status(conn, job: Dict[str, Any]) -> Dict[str, Any]:
    result = {"home": [], "away": [], "summary": {"home": {}, "away": {}}, "errors": []}
    if not _table_exists(conn, "player_status"):
        result["errors"].append("player_status table missing")
        return result
    for side, team_id, team_cn in [
        ("home", job.get("home_team_id"), job.get("home_team_cn")),
        ("away", job.get("away_team_id"), job.get("away_team_cn")),
    ]:
        if not team_id and not team_cn:
            result["errors"].append(f"{side} team_id and team_cn both missing")
            continue
        try:
            resolved_id = _resolve_team_id_for_player_status(conn, team_id, team_cn)
            if not resolved_id:
                result["errors"].append(f"{side}: no player_status data found (team_id={team_id}, cn={team_cn})")
                continue
            result["summary"][side] = _player_status_summary(conn, resolved_id)
            rows = conn.execute(
                """
                SELECT ps.status_id, ps.player_id,
                       COALESCE(p.name_cn, p.name_en, p.full_name, CAST(ps.player_id AS TEXT)) as player_name,
                       ps.status, ps.status_detail, ps.injury_type, ps.injury_severity,
                       ps.expected_return, ps.suspension_reason, ps.suspension_matches,
                       ps.appearance_probability, ps.team_impact_score, ps.replacement_quality,
                       ps.source, ps.updated_at
                FROM player_status ps
                LEFT JOIN players p ON p.player_id = ps.player_id
                WHERE ps.team_id = ?
                  AND lower(COALESCE(ps.status, '')) NOT IN ('available', 'fit', 'active')
                ORDER BY COALESCE(ps.team_impact_score, 0) DESC, ps.updated_at DESC
                LIMIT 30
                """,
                (resolved_id,),
            ).fetchall()
            result[side] = [_row_dict(row) for row in rows]
        except Exception as exc:
            result["errors"].append(f"{side}: {exc}")
    return result


def _resolve_team_id_for_player_status(conn, team_id, team_cn: Optional[str] = None) -> Optional[int]:
    """Resolve a team_id that works with the player_status table.

    player_status uses api-football-style IDs (1,2,3...) which differ from
    the internal IDs used in lottery_matches. This function tries:
    1. Direct match on team_id
    2. Lookup via teams.name_cn → teams.team_id
    """
    # Try direct match first
    if team_id:
        row = conn.execute(
            "SELECT 1 FROM player_status WHERE team_id = ? LIMIT 1",
            (int(team_id),),
        ).fetchone()
        if row:
            return int(team_id)

    # Fallback: resolve via teams table name_cn match
    if team_cn and _table_exists(conn, "teams"):
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name_cn = ? LIMIT 1",
            (team_cn,),
        ).fetchone()
        if row:
            resolved = int(row[0])
            # Verify this team_id has player_status data
            check = conn.execute(
                "SELECT 1 FROM player_status WHERE team_id = ? LIMIT 1",
                (resolved,),
            ).fetchone()
            if check:
                return resolved

    return None


def _player_status_summary(conn, team_id: int) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN lower(COALESCE(status, '')) = 'available' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN lower(COALESCE(status, '')) = 'injured' THEN 1 ELSE 0 END) as injured,
            SUM(CASE WHEN lower(COALESCE(status, '')) = 'suspended' THEN 1 ELSE 0 END) as suspended,
            SUM(CASE WHEN lower(COALESCE(status, '')) NOT IN ('available', 'fit', 'active') THEN 1 ELSE 0 END) as unavailable,
            SUM(CASE WHEN lower(COALESCE(status, '')) NOT IN ('available', 'fit', 'active')
                       AND COALESCE(team_impact_score, 0) >= 0.5 THEN 1 ELSE 0 END) as key_absent,
            MAX(updated_at) as latest_update
        FROM player_status
        WHERE team_id = ?
        """,
        (team_id,),
    ).fetchone()
    return _row_dict(row)


def _has_local_absence_evidence(
    player_status: Dict[str, Any],
    injury_news: Dict[str, List[Dict[str, Any]]],
    live_injury_news: Optional[Dict[str, Any]] = None,
) -> bool:
    live_injury_news = live_injury_news or {}
    return bool(
        player_status.get("home")
        or player_status.get("away")
        or injury_news.get("home")
        or injury_news.get("away")
        or live_injury_news.get("home")
        or live_injury_news.get("away")
    )


def _injury_summary(payload: Dict[str, Any], api_hit: bool, local_hit: bool) -> Dict[str, Any]:
    local_status = payload.get("local_player_status", {})
    local_news = payload.get("local_injury_news", {})
    live_news = payload.get("live_injury_news", {})
    return {
        "mode": "api_confirmed" if api_hit else "local_fallback" if local_hit else "no_confirmed_absence_found",
        "api_home_count": len(payload.get("api_sports", {}).get("home", [])),
        "api_away_count": len(payload.get("api_sports", {}).get("away", [])),
        "local_home_absent": len(local_status.get("home", [])),
        "local_away_absent": len(local_status.get("away", [])),
        "local_home_news": len(local_news.get("home", [])),
        "local_away_news": len(local_news.get("away", [])),
        "live_home_news": len(live_news.get("home", [])),
        "live_away_news": len(live_news.get("away", [])),
        "confidence_note": "Low confidence means the collector checked available local sources but still lacks authoritative squad data.",
    }


def _single_team_name_tokens(conn, team_id: Optional[int], fallback_name: Optional[str] = None) -> set:
    tokens = {fallback_name or ""}
    team_columns = _table_columns(conn, "teams")
    name_columns = [
        col for col in (
            "name_en",
            "name_cn",
            "sporttery_name_cn",
            "oddsfe_name_cn",
            "oddsfe_name_en",
            "apifootball_name_cn",
            "apifootball_name_en",
            "name_cn_aliases",
        )
        if col in team_columns
    ]
    if team_id and name_columns:
        try:
            row = conn.execute(f"SELECT {', '.join(name_columns)} FROM teams WHERE team_id = ?", (team_id,)).fetchone()
        except Exception:
            row = None
        if row:
            for value in _row_dict(row).values():
                if not value:
                    continue
                if isinstance(value, str):
                    tokens.update(part.strip() for part in re.split(r"[,/|;\uff0c\u3001]", value) if part.strip())
    return {token for token in tokens if token and len(token) >= 2}


def _api_sports_team_ids(conn, job: Dict[str, Any]) -> Dict[str, Optional[int]]:
    return _source_team_ids(conn, job, ("api_sports", "api-football-v1"))


def _apifootball_team_ids(conn, job: Dict[str, Any]) -> Dict[str, Optional[int]]:
    return _source_team_ids(conn, job, ("apifootball", "api-football"))


def _football_data_team_ids(conn, job: Dict[str, Any]) -> Dict[str, Optional[int]]:
    return {
        "home": _team_column_id(conn, job.get("home_team_id"), "fd_team_id"),
        "away": _team_column_id(conn, job.get("away_team_id"), "fd_team_id"),
    }


def _team_column_id(conn, team_id: Optional[int], column: str) -> Optional[int]:
    if not team_id or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", column or ""):
        return None
    try:
        if column not in _table_columns(conn, "teams"):
            return None
        row = conn.execute(f"SELECT {column} FROM teams WHERE team_id = ?", (team_id,)).fetchone()
        return _safe_int(_row_value(row, column, 0))
    except Exception:
        return None


def _source_team_ids(conn, job: Dict[str, Any], source_names: Iterable[str]) -> Dict[str, Optional[int]]:
    return {
        "home": _team_source_id(conn, job.get("home_team_id"), source_names),
        "away": _team_source_id(conn, job.get("away_team_id"), source_names),
    }


def _team_source_id(conn, team_id: Optional[int], source_names: Iterable[str]) -> Optional[int]:
    if not team_id:
        return None
    normalized_sources = {str(item).strip().lower() for item in source_names if str(item).strip()}
    if not normalized_sources:
        return None

    # APIFootball predates the generic source mapping table in this project.
    # Keep this DB column as a compatibility read path, but only for APIFootball.
    if normalized_sources.intersection({"apifootball", "api-football"}):
        try:
            if "apifootball_team_id" in _table_columns(conn, "teams"):
                row = conn.execute("SELECT apifootball_team_id FROM teams WHERE team_id = ?", (team_id,)).fetchone()
                value = _row_value(row, "apifootball_team_id", 0)
                parsed = _safe_int(value)
                if parsed is not None:
                    return parsed
        except Exception:
            pass

    if not _table_exists(conn, "source_entity_mappings"):
        return None
    placeholders = ",".join("?" for _ in normalized_sources)
    try:
        row = conn.execute(
            f"""
            SELECT source_entity_id
            FROM source_entity_mappings
            WHERE entity_type = 'team'
              AND CAST(canonical_id AS TEXT) = CAST(? AS TEXT)
              AND lower(source_name) IN ({placeholders})
              AND COALESCE(status, 'active') = 'active'
            ORDER BY confidence DESC, updated_at DESC
            LIMIT 1
            """,
            (team_id, *sorted(normalized_sources)),
        ).fetchone()
    except Exception:
        return None
    return _safe_int(_row_value(row, "source_entity_id", 0))


def _row_value(row, key: str, index: int = 0) -> Any:
    if not row:
        return None
    try:
        return row[key]
    except Exception:
        try:
            return row[index]
        except Exception:
            return None


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _external_match_id(conn, job: Dict[str, Any]) -> Optional[str]:
    match_id = job.get("match_id")
    if not match_id:
        return None
    try:
        row = conn.execute("SELECT match_code, source FROM matches WHERE match_id = ?", (match_id,)).fetchone()
    except Exception:
        return None
    if not row:
        return None
    source = (row["source"] or "").lower()
    code = row["match_code"]
    if code and any(marker in source for marker in ("apifootball", "api-football", "api_sports")):
        return str(code)
    return None


def _local_match_lineup(conn, match_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not match_id or not _table_exists(conn, "match_lineups"):
        return None
    try:
        rows = conn.execute(
            """
            SELECT match_id, team_type, player_key, player_name, player_number, position, is_starter
            FROM match_lineups
            WHERE match_id = ?
            ORDER BY team_type, is_starter DESC, CAST(position AS INTEGER), player_number
            """,
            (str(match_id),),
        ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    grouped = {"home": [], "away": []}
    for row in rows:
        item = _row_dict(row)
        side = item.pop("team_type", None)
        if side in grouped:
            grouped[side].append(item)
    return grouped


def _recent_lineup_projection(conn, job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "home": _recent_team_lineup(conn, job.get("home_team_id"), job.get("match_date")),
        "away": _recent_team_lineup(conn, job.get("away_team_id"), job.get("match_date")),
    }


def _recent_team_lineup(conn, team_id: Optional[int], match_date: Optional[str], limit_matches: int = 5) -> Dict[str, Any]:
    empty = {"latest_starting_xi": [], "frequent_starters": [], "sample_matches": [], "gaps": []}
    if not team_id:
        empty["gaps"].append("team_id missing")
        return empty
    if not _table_exists(conn, "match_lineups") or not _table_exists(conn, "matches"):
        empty["gaps"].append("match_lineups or matches table missing")
        return empty
    before_date = str(match_date or date.today().isoformat())[:10]
    try:
        rows = conn.execute(
            """
            SELECT ml.match_id, ml.team_type, ml.player_key, ml.player_name, ml.player_number,
                   ml.position, ml.is_starter, m.match_date
            FROM match_lineups ml
            JOIN matches m ON CAST(m.match_id AS TEXT) = CAST(ml.match_id AS TEXT)
            WHERE m.match_date < ?
              AND (
                    (m.home_team_id = ? AND ml.team_type = 'home')
                 OR (m.away_team_id = ? AND ml.team_type = 'away')
              )
            ORDER BY m.match_date DESC, ml.match_id, ml.is_starter DESC, CAST(ml.position AS INTEGER)
            LIMIT 300
            """,
            (before_date, team_id, team_id),
        ).fetchall()
    except Exception as exc:
        empty["gaps"].append(str(exc))
        return empty
    by_match: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    match_dates = {}
    for row in rows:
        item = _row_dict(row)
        match_id = str(item.get("match_id"))
        if len(by_match) >= limit_matches and match_id not in by_match:
            continue
        match_dates[match_id] = item.get("match_date")
        by_match[match_id].append(item)
    if not by_match:
        empty["gaps"].append("no historical lineups found before match date")
        return empty
    sample_matches = []
    starter_counter: Counter = Counter()
    latest_starting_xi: List[Dict[str, Any]] = []
    for index, (match_id, players) in enumerate(by_match.items()):
        starters = [_lineup_player(item) for item in players if item.get("is_starter")]
        starters = [player for player in starters if player.get("player_name")]
        if index == 0:
            latest_starting_xi = starters[:11]
        for player in starters:
            starter_counter[player["player_name"]] += 1
        sample_matches.append({"match_id": match_id, "match_date": match_dates.get(match_id), "starter_count": len(starters)})
    frequent = [
        {"player_name": name, "starts_in_sample": count}
        for name, count in starter_counter.most_common(16)
    ]
    return {
        "latest_starting_xi": latest_starting_xi,
        "frequent_starters": frequent,
        "sample_matches": sample_matches,
        "projection_note": "Fallback uses recent imported lineups; it is not a confirmed starting XI.",
    }


def _lineup_player(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "player_key": item.get("player_key"),
        "player_name": item.get("player_name"),
        "player_number": item.get("player_number"),
        "position": item.get("position"),
    }
