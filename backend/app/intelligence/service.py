import hashlib
import json
import re
import unicodedata
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .schemas import (
    AnalysisView,
    ArtifactCreate,
    CompetitionType,
    IntelligenceJobCreate,
    JobStatus,
    RequirementStatus,
    RequirementTemplate,
    ReviewCreate,
)
from .external_collectors import run_external_collectors
from .source_channels import channel_plan_for_requirements
from .storage import get_connection, init_schema


WORLD_CUP_TERMS = ("world cup", "世界杯", "fifa world cup")
NATIONAL_TERMS = (
    "national",
    "international",
    "friendlies",
    "friendly",
    "nations league",
    "world cup qualification",
    "euro qualification",
    "国家",
    "国际",
    "友谊",
    "世预",
    "欧国联",
    "亚洲杯",
    "欧洲杯",
)

EXTERNAL_GAP_COLLECTORS = ("injuries_suspensions", "team_news", "expected_lineup", "weather")
BUILTIN_GAP_COLLECTORS = {
    "base_info",
    "odds_1x2",
    "market_movement",
    "recent_form",
    "goal_tempo_profile",
    "elo_rating",
    "fifa_ranking",
    "standings_context",
    "tournament_context",
    "travel_fatigue",
    "major_tournament_experience",
    "home_away_profile",
    "data_quality",
}
GAP_KEY_PRIORITY = {
    "injuries_suspensions": 110,
    "odds_1x2": 105,
    "data_quality": 95,
    "recent_form": 90,
    "goal_tempo_profile": 89,
    "tournament_context": 88,
    "standings_context": 84,
    "elo_rating": 82,
    "fifa_ranking": 80,
    "market_movement": 76,
    "travel_fatigue": 74,
    "expected_lineup": 72,
    "major_tournament_experience": 70,
    "team_news": 68,
    "weather": 60,
    "home_away_profile": 58,
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _safe_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def detect_context(league_name: Optional[str]) -> Tuple[str, str]:
    text = (league_name or "").lower()
    if any(term in text for term in WORLD_CUP_TERMS):
        return CompetitionType.world_cup.value, AnalysisView.world_cup.value
    if any(term in text for term in NATIONAL_TERMS):
        return CompetitionType.national_team.value, AnalysisView.national_team.value
    if "cup" in text or "杯" in text:
        return CompetitionType.cup.value, AnalysisView.cup.value
    if text:
        return CompetitionType.league.value, AnalysisView.league.value
    return CompetitionType.unknown.value, AnalysisView.generic.value


def requirement_templates(view: str) -> List[RequirementTemplate]:
    common = [
        RequirementTemplate(
            key="base_info",
            category="base",
            preferred_sources=["football_v2", "lottery_matches"],
            fallback_policy="manual_review",
            description="Canonical match, team, league, kickoff and source ids.",
        ),
        RequirementTemplate(
            key="odds_1x2",
            category="odds",
            preferred_sources=["oddsfe", "sporttery", "the_odds_api", "football_data_csv"],
            fallback_policy="fallback_to_no_odds_analysis",
            description="Opening/latest 1X2 odds and market implied probabilities.",
        ),
        RequirementTemplate(
            key="market_movement",
            category="odds",
            required=False,
            preferred_sources=["oddsfe", "sporttery"],
            fallback_policy="mark_low_confidence",
            description="Odds movement and abnormal market signals.",
        ),
        RequirementTemplate(
            key="recent_form",
            category="team_strength",
            preferred_sources=["football_v2", "apifootball", "sofascore"],
            fallback_policy="use_historical_matches",
            description="Recent form adjusted by opponent quality.",
        ),
        RequirementTemplate(
            key="goal_tempo_profile",
            category="goal_model",
            preferred_sources=["team_match_facts", "lottery_results", "matches"],
            fallback_policy="build_team_match_facts",
            description="Attack, defense, both-teams-score, total-goals and half-time tempo profile from settled pre-match facts.",
        ),
        RequirementTemplate(
            key="team_news",
            category="news",
            required=False,
            preferred_sources=["dongqiudi", "hupu", "news_aggregator", "official"],
            fallback_policy="mark_missing",
            description="Team news, coach comments and information gaps.",
        ),
        RequirementTemplate(
            key="injuries_suspensions",
            category="squad",
            preferred_sources=["apifootball", "sportmonks", "news", "manual"],
            fallback_policy="fallback_to_news_scan",
            description="Injuries, suspensions, doubtful and unavailable players.",
        ),
        RequirementTemplate(
            key="expected_lineup",
            category="squad",
            required=False,
            preferred_sources=["apifootball", "sportmonks", "365scores", "news"],
            fallback_policy="use_probable_lineup_or_unknown",
            description="Expected starting XI and formation.",
        ),
        RequirementTemplate(
            key="weather",
            category="environment",
            required=False,
            preferred_sources=["openweathermap", "venue_city", "historical_weather"],
            fallback_policy="city_then_climate_average",
            description="Weather, temperature, rain, wind and pitch impact.",
        ),
        RequirementTemplate(
            key="data_quality",
            category="quality",
            preferred_sources=["system"],
            fallback_policy="always_compute",
            description="Missing fields, source confidence, stale data and warnings.",
        ),
    ]

    national = [
        RequirementTemplate(
            key="fifa_ranking",
            category="team_strength",
            preferred_sources=["football_v2", "fifa_ranking_csv"],
            fallback_policy="use_elo_only",
            description="FIFA ranking and ranking trend for national teams.",
        ),
        RequirementTemplate(
            key="elo_rating",
            category="team_strength",
            preferred_sources=["football_v2", "elo_history"],
            fallback_policy="compute_from_recent_results",
            description="Elo strength and expected result baseline.",
        ),
        RequirementTemplate(
            key="tournament_context",
            category="motivation",
            preferred_sources=["standings", "world_cup_rules", "manual"],
            fallback_policy="manual_review",
            description="Group points, qualification pressure, goal difference and rotation incentive.",
        ),
        RequirementTemplate(
            key="travel_fatigue",
            category="environment",
            required=False,
            preferred_sources=["venue", "schedule", "team_base"],
            fallback_policy="mark_low_confidence",
            description="Travel, rest days, climate adaptation and neutral venue effect.",
        ),
        RequirementTemplate(
            key="major_tournament_experience",
            category="team_strength",
            required=False,
            preferred_sources=["world_cup_history", "national_teams_history"],
            fallback_policy="mark_missing",
            description="World Cup or major tournament experience.",
        ),
    ]

    league = [
        RequirementTemplate(
            key="standings_context",
            category="motivation",
            preferred_sources=["football_v2", "apifootball"],
            fallback_policy="manual_review",
            description="Title, relegation, continental qualification and six-pointer context.",
        ),
        RequirementTemplate(
            key="home_away_profile",
            category="team_strength",
            preferred_sources=["football_v2"],
            fallback_policy="use_recent_form",
            description="Home and away performance split.",
        ),
        RequirementTemplate(
            key="schedule_congestion",
            category="fatigue",
            required=False,
            preferred_sources=["football_v2", "fixture_api"],
            fallback_policy="compute_from_matches",
            description="Rest days, travel and rotation risk.",
        ),
    ]

    if view in (AnalysisView.world_cup.value, AnalysisView.national_team.value):
        return common + national
    if view in (AnalysisView.league.value, AnalysisView.cup.value):
        return common + league
    return common


class IntelligenceService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _connect(self):
        conn = get_connection(self.db_path)
        init_schema(conn)
        return conn

    def create_job(self, payload: IntelligenceJobCreate) -> Dict[str, Any]:
        competition_type = payload.competition_type.value if payload.competition_type else None
        analysis_view = payload.analysis_view.value if payload.analysis_view else None
        if not competition_type or not analysis_view:
            detected_type, detected_view = detect_context(payload.league_name)
            competition_type = competition_type or detected_type
            analysis_view = analysis_view or detected_view

        job_id = self._make_job_id(payload)
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intelligence_jobs (
                    job_id, match_id, lottery_match_id, home_team_id, away_team_id, match_date, match_time,
                    league_name, home_team, away_team, competition_type,
                    analysis_view, status, priority, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    match_id=excluded.match_id,
                    lottery_match_id=excluded.lottery_match_id,
                    home_team_id=excluded.home_team_id,
                    away_team_id=excluded.away_team_id,
                    match_date=excluded.match_date,
                    match_time=excluded.match_time,
                    league_name=excluded.league_name,
                    home_team=excluded.home_team,
                    away_team=excluded.away_team,
                    competition_type=excluded.competition_type,
                    analysis_view=excluded.analysis_view,
                    priority=excluded.priority,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (
                    job_id,
                    payload.match_id,
                    payload.lottery_match_id,
                    payload.home_team_id,
                    payload.away_team_id,
                    payload.match_date,
                    payload.match_time,
                    payload.league_name,
                    payload.home_team,
                    payload.away_team,
                    competition_type,
                    analysis_view,
                    JobStatus.pending.value,
                    payload.priority,
                    payload.source,
                    now,
                    now,
                ),
            )
            self._ensure_requirements(conn, job_id, analysis_view)
            conn.commit()
            return self.get_job(job_id, conn=conn)

    def generate_jobs_for_date(self, match_date: Optional[str] = None, source: str = "lottery") -> Dict[str, Any]:
        target_date = match_date or date.today().isoformat()
        created = 0
        updated = 0
        jobs: List[Dict[str, Any]] = []
        with self._connect() as conn:
            rows = self._load_lottery_matches(conn, target_date) if source == "lottery" else []
            existing_ids = {row["job_id"] for row in conn.execute("SELECT job_id FROM intelligence_jobs")}
            for row in rows:
                payload = IntelligenceJobCreate(
                    match_id=row.get("match_id"),
                    lottery_match_id=row.get("lottery_match_id"),
                    home_team_id=row.get("home_team_id"),
                    away_team_id=row.get("away_team_id"),
                    match_date=row.get("match_date"),
                    match_time=row.get("beijing_time") or row.get("match_time"),
                    league_name=row.get("league_name_cn"),
                    home_team=row.get("home_team_cn"),
                    away_team=row.get("away_team_cn"),
                    source="auto_lottery",
                )
                job = self.create_job(payload)
                if job["job_id"] in existing_ids:
                    updated += 1
                else:
                    created += 1
                jobs.append(job)
        return {"created": created, "updated": updated, "skipped": 0, "jobs": jobs}

    def generate_jobs_for_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate intelligence_jobs for all dates in range.

        Ensures rows exist in intelligence_jobs for the target date range so
        that fill_gaps can find candidates. Without this, the automation
        pipeline detects "collect_intelligence" gaps but fill_gaps returns
        zero candidates because no jobs exist to fill.
        """
        from datetime import date, timedelta
        start = date.fromisoformat(start_date) if start_date else date.today()
        end = date.fromisoformat(end_date) if end_date else date.today() + timedelta(days=2)
        total_created = 0
        total_updated = 0
        d = start
        while d <= end:
            result = self.generate_jobs_for_date(match_date=d.isoformat())
            total_created += result.get("created", 0)
            total_updated += result.get("updated", 0)
            d += timedelta(days=1)
        return {"created": total_created, "updated": total_updated, "dates": (end - start).days + 1}

    def run_daily(
        self,
        match_date: Optional[str] = None,
        include_external: bool = False,
        collectors: Optional[List[str]] = None,
        network: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        generated = self.generate_jobs_for_date(match_date=match_date)
        results = []
        for job in generated["jobs"]:
            job_id = job["job_id"]
            builtin = self.collect_builtin(job_id, force=force)
            external = None
            if include_external:
                external = self.collect_external(job_id, collectors=collectors, network=network, force=force)
            package_result = (external or builtin)["package"]
            summary = package_result["package"]["summary"]
            results.append(
                {
                    "job_id": job_id,
                    "match": f"{job.get('home_team')} vs {job.get('away_team')}",
                    "builtin_collected": len(builtin["collected"]),
                    "builtin_missing": len(builtin["missing"]),
                    "builtin_unhandled": len(builtin["unhandled"]),
                    "external_collected": len(external["collected"]) if external else 0,
                    "required_total": summary.get("required_total", 0),
                    "required_collected": summary.get("required_collected", 0),
                    "required_fallback": summary.get("required_fallback", 0),
                    "required_missing": len(summary.get("missing_required", [])),
                    "coverage": summary.get("completeness", 0),
                    "completeness": summary.get("completeness", 0),
                    "strict_coverage": summary.get("strict_completeness", 0),
                    "average_confidence": summary.get("average_confidence", 0),
                    "status": (external or builtin)["job"]["status"],
                }
            )
        return {"generated": generated, "results": results}

    def run_daily_logged(
        self,
        match_date: Optional[str] = None,
        include_external: bool = False,
        collectors: Optional[List[str]] = None,
        network: bool = True,
        force: bool = False,
        trigger_source: str = "manual",
    ) -> Dict[str, Any]:
        run_id = "run:" + uuid.uuid4().hex
        target_date = match_date or date.today().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intelligence_runs (
                    run_id, run_date, trigger_source, include_external,
                    collectors_json, network, force, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running')
                """,
                (
                    run_id,
                    target_date,
                    trigger_source,
                    1 if include_external else 0,
                    _json(collectors or []),
                    1 if network else 0,
                    1 if force else 0,
                ),
            )
            conn.commit()
        try:
            summary = self.run_daily(
                match_date=target_date,
                include_external=include_external,
                collectors=collectors,
                network=network,
                force=force,
            )
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE intelligence_runs
                    SET status = 'completed',
                        finished_at = CURRENT_TIMESTAMP,
                        summary_json = ?
                    WHERE run_id = ?
                    """,
                    (_json(summary), run_id),
                )
                conn.commit()
            return {"run_id": run_id, "status": "completed", "summary": summary}
        except Exception as exc:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE intelligence_runs
                    SET status = 'failed',
                        finished_at = CURRENT_TIMESTAMP,
                        error = ?
                    WHERE run_id = ?
                    """,
                    (str(exc), run_id),
                )
                conn.commit()
            raise

    def backfill_finished(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_external: bool = True,
        collectors: Optional[List[str]] = None,
        network: bool = False,
        force: bool = False,
        play_type: str = "spf",
        limit: int = 200,
    ) -> Dict[str, Any]:
        end = end_date or date.today().isoformat()
        start = start_date or (date.fromisoformat(end) - timedelta(days=60)).isoformat()
        selected_collectors = collectors or ["team_news", "injuries_suspensions", "expected_lineup"]
        rows = self._load_finished_lottery_matches(start, end, play_type=play_type, limit=limit)
        existing_ids = self._existing_job_ids()
        generated = {"created": 0, "updated": 0, "skipped": 0, "jobs": []}
        results = []
        dates = sorted({row.get("match_date") for row in rows if row.get("match_date")})
        for row in rows:
            payload = IntelligenceJobCreate(
                match_id=row.get("match_id"),
                lottery_match_id=row.get("lottery_match_id"),
                home_team_id=row.get("home_team_id"),
                away_team_id=row.get("away_team_id"),
                match_date=row.get("match_date"),
                match_time=row.get("beijing_time") or row.get("match_time"),
                league_name=row.get("league_name_cn"),
                home_team=row.get("home_team_cn"),
                away_team=row.get("away_team_cn"),
                source="backfill_finished",
            )
            job = self.create_job(payload)
            if job["job_id"] in existing_ids:
                generated["updated"] += 1
            else:
                generated["created"] += 1
                existing_ids.add(job["job_id"])
            generated["jobs"].append(job)

            builtin = self.collect_builtin(job["job_id"], force=force)
            external = None
            if include_external:
                external = self.collect_external(
                    job["job_id"],
                    collectors=selected_collectors,
                    network=network,
                    force=force,
                )
            review = self.auto_review_job(job["job_id"], play_type=play_type)
            package_result = (external or builtin)["package"]
            summary = package_result["package"]["summary"]
            results.append(
                {
                    "job_id": job["job_id"],
                    "lottery_match_id": job.get("lottery_match_id"),
                    "match_date": job.get("match_date"),
                    "match": f"{job.get('home_team')} vs {job.get('away_team')}",
                    "status": review["job"]["status"],
                    "coverage": summary.get("completeness", 0),
                    "strict_coverage": summary.get("strict_completeness", 0),
                    "review": {
                        "review_id": review["review"]["review_id"],
                        "actual_result": review["review"].get("actual_result"),
                        "predicted_result": review["review"].get("predicted_result"),
                        "is_correct": review["review"].get("is_correct"),
                        "attribution": review["review"].get("attribution"),
                    },
                }
            )
        return {
            "range": {"start_date": start, "end_date": end},
            "dates": dates,
            "source_rows": len(rows),
            "generated": generated,
            "results": results,
        }

    def backfill_finished_logged(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_external: bool = True,
        collectors: Optional[List[str]] = None,
        network: bool = False,
        force: bool = False,
        play_type: str = "spf",
        limit: int = 200,
        trigger_source: str = "manual_backfill_finished",
    ) -> Dict[str, Any]:
        run_id = "run:" + uuid.uuid4().hex
        range_label = f"{start_date or ''}..{end_date or ''}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intelligence_runs (
                    run_id, run_date, trigger_source, include_external,
                    collectors_json, network, force, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running')
                """,
                (
                    run_id,
                    range_label,
                    trigger_source,
                    1 if include_external else 0,
                    _json(collectors or ["team_news", "injuries_suspensions", "expected_lineup"]),
                    1 if network else 0,
                    1 if force else 0,
                ),
            )
            conn.commit()
        try:
            summary = self.backfill_finished(
                start_date=start_date,
                end_date=end_date,
                include_external=include_external,
                collectors=collectors,
                network=network,
                force=force,
                play_type=play_type,
                limit=limit,
            )
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE intelligence_runs
                    SET status = 'completed',
                        finished_at = CURRENT_TIMESTAMP,
                        summary_json = ?
                    WHERE run_id = ?
                    """,
                    (_json(summary), run_id),
                )
                conn.commit()
            return {"run_id": run_id, "status": "completed", "summary": summary}
        except Exception as exc:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE intelligence_runs
                    SET status = 'failed',
                        finished_at = CURRENT_TIMESTAMP,
                        error = ?
                    WHERE run_id = ?
                    """,
                    (str(exc), run_id),
                )
                conn.commit()
            raise

    def plan_gap_fill(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        collectors: Optional[List[str]] = None,
        include_optional: bool = True,
        include_builtin: bool = True,
        retry_fallback: bool = True,
        force: bool = False,
        limit: int = 20,
        failed_retry_minutes: int = 180,
        fallback_retry_minutes: int = 360,
    ) -> Dict[str, Any]:
        today = date.today()
        start = start_date or (today - timedelta(days=1)).isoformat()
        end = end_date or (today + timedelta(days=1)).isoformat()
        external_keys = set(collectors or EXTERNAL_GAP_COLLECTORS)
        watched_keys = set(external_keys)
        if include_builtin:
            watched_keys.update(BUILTIN_GAP_COLLECTORS)

        with self._connect() as conn:
            self._ensure_requirements_for_range(conn, start, end)
            rows = conn.execute(
                f"""
                SELECT j.job_id, j.lottery_match_id, j.match_id, j.match_date, j.match_time,
                       j.league_name, j.home_team, j.away_team, j.competition_type,
                       j.analysis_view, j.priority AS job_priority, j.status AS job_status,
                       r.key, r.category, r.required, r.status AS requirement_status,
                       r.confidence, r.updated_at
                FROM intelligence_jobs j
                JOIN intelligence_requirements r ON r.job_id = j.job_id
                WHERE j.match_date BETWEEN ? AND ?
                  AND r.key IN ({",".join("?" for _ in watched_keys)})
                ORDER BY j.match_date ASC, j.priority ASC, j.match_time ASC
                """,
                [start, end, *sorted(watched_keys)],
            ).fetchall()

        jobs: Dict[str, Dict[str, Any]] = {}
        # SQLite CURRENT_TIMESTAMP is UTC; compare in UTC so retry windows do
        # not see freshly updated requirements as eight hours old on +08 hosts.
        now = datetime.utcnow()
        for row in rows:
            item = dict(row)
            status = item.get("requirement_status")
            key = item.get("key")
            confidence = _safe_float(item.get("confidence"), 0.0)
            updated_at = _safe_datetime(item.get("updated_at"))
            age_minutes = (now - updated_at).total_seconds() / 60 if updated_at else 999999
            required = bool(item.get("required"))
            if not include_optional and not required:
                continue

            should_fill = False
            reason = ""
            if force and status != RequirementStatus.collected.value:
                should_fill = True
                reason = "force_retry"
            elif status in (RequirementStatus.missing.value, RequirementStatus.stale.value):
                should_fill = True
                reason = status
            elif status == RequirementStatus.failed.value and age_minutes >= failed_retry_minutes:
                should_fill = True
                reason = "failed_retry"
            elif (
                retry_fallback
                and status == RequirementStatus.fallback_used.value
                and key in external_keys
                and age_minutes >= fallback_retry_minutes
                and confidence < (0.58 if required else 0.45)
            ):
                should_fill = True
                reason = "low_confidence_fallback"

            if not should_fill:
                continue

            match_date = _safe_date(item.get("match_date"))
            day_gap = (match_date - today).days if match_date else 99
            date_score = 0
            if day_gap == 0:
                date_score = 55
            elif day_gap == 1:
                date_score = 50
            elif day_gap == -1:
                date_score = 42
            elif 2 <= day_gap <= 3:
                date_score = 32
            elif -7 <= day_gap < -1:
                date_score = 18
            else:
                date_score = 8
            status_score = {
                RequirementStatus.missing.value: 35,
                RequirementStatus.failed.value: 28,
                RequirementStatus.stale.value: 32,
                RequirementStatus.fallback_used.value: 18,
            }.get(status, 0)
            context_text = f"{item.get('league_name') or ''} {item.get('competition_type') or ''} {item.get('analysis_view') or ''}".lower()
            context_bonus = 24 if ("世界杯" in context_text or "world_cup" in context_text or "world cup" in context_text) else 0
            score = (
                GAP_KEY_PRIORITY.get(key, 40)
                + status_score
                + date_score
                + (28 if required else 6)
                + context_bonus
                + max(0, 12 - int(_safe_float(item.get("job_priority"), 5)))
                - int(confidence * 10)
            )

            job = jobs.setdefault(
                item["job_id"],
                {
                    "job_id": item["job_id"],
                    "lottery_match_id": item.get("lottery_match_id"),
                    "match_id": item.get("match_id"),
                    "match_date": item.get("match_date"),
                    "match_time": item.get("match_time"),
                    "league_name": item.get("league_name"),
                    "home_team": item.get("home_team"),
                    "away_team": item.get("away_team"),
                    "competition_type": item.get("competition_type"),
                    "analysis_view": item.get("analysis_view"),
                    "score": 0,
                    "external_collectors": [],
                    "builtin_requirements": [],
                    "gaps": [],
                },
            )
            gap = {
                "key": key,
                "status": status,
                "required": required,
                "confidence": confidence,
                "reason": reason,
                "age_minutes": round(age_minutes, 1) if age_minutes < 999999 else None,
                "score": score,
            }
            job["gaps"].append(gap)
            if key in external_keys and key not in job["external_collectors"]:
                job["external_collectors"].append(key)
            if key in BUILTIN_GAP_COLLECTORS and key not in job["builtin_requirements"]:
                job["builtin_requirements"].append(key)
            job["score"] += score

        candidates = sorted(jobs.values(), key=lambda item: item["score"], reverse=True)
        for candidate in candidates:
            gap_keys = [gap.get("key") for gap in candidate.get("gaps", []) if gap.get("key")]
            candidate["channel_plan"] = channel_plan_for_requirements(gap_keys)
        return {
            "range": {"start_date": start, "end_date": end},
            "collectors": sorted(external_keys),
            "include_builtin": include_builtin,
            "total_candidates": len(candidates),
            "data": candidates[:limit],
        }

    def unified_gap_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Produce unified gap objects matching P0-3 spec.

        Each gap object has: lottery_match_id, requirement_key, severity,
        reason, candidate_channels, selected_channels, skipped_channels, next_action.
        """
        plan = self.plan_gap_fill(
            start_date=start_date,
            end_date=end_date,
            include_optional=False,
            limit=limit,
        )
        gaps = []
        for candidate in plan.get("data", []):
            match_id = candidate.get("lottery_match_id") or candidate.get("match_id")
            channel_plan = candidate.get("channel_plan", {})
            for gap in candidate.get("gaps", []):
                key = gap.get("key")
                score = gap.get("score", 0)
                severity = "high" if score >= 3 else ("medium" if score >= 1 else "low")

                candidate_channels = []
                selected_channels = []
                skipped_channels = []
                if key in channel_plan:
                    for ch in channel_plan[key]:
                        candidate_channels.append(ch.get("name", ""))
                        if ch.get("enabled", True):
                            selected_channels.append(ch.get("name", ""))
                        else:
                            skipped_channels.append({
                                "name": ch.get("name", ""),
                                "reason": "disabled_or_error",
                            })

                next_action = "collect" if selected_channels else (
                    "wait_for_source_recovery" if candidate_channels and not selected_channels else "skip"
                )

                gaps.append({
                    "lottery_match_id": match_id,
                    "requirement_key": key,
                    "severity": severity,
                    "reason": gap.get("reason", ""),
                    "candidate_channels": candidate_channels,
                    "selected_channels": selected_channels,
                    "skipped_channels": skipped_channels,
                    "next_action": next_action,
                })
        return gaps

    def _ensure_requirements_for_range(self, conn, start: str, end: str) -> int:
        """Bring existing jobs up to the current requirement template.

        This matters when the evidence contract evolves. Existing upcoming jobs
        must receive new requirements such as goal_tempo_profile, otherwise the
        gap filler never knows the match still lacks that evidence.
        """
        ensured = 0
        rows = conn.execute(
            """
            SELECT job_id, analysis_view
            FROM intelligence_jobs
            WHERE match_date BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchall()
        for row in rows:
            self._ensure_requirements(conn, row["job_id"], row["analysis_view"])
            self._update_job_status(conn, row["job_id"])
            ensured += 1
        if ensured:
            conn.commit()
        return ensured

    def fill_gaps(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        collectors: Optional[List[str]] = None,
        network: bool = True,
        force: bool = False,
        include_optional: bool = True,
        include_builtin: bool = True,
        limit: int = 8,
        failed_retry_minutes: int = 180,
        fallback_retry_minutes: int = 360,
    ) -> Dict[str, Any]:
        plan = self.plan_gap_fill(
            start_date=start_date,
            end_date=end_date,
            collectors=collectors,
            include_optional=include_optional,
            include_builtin=include_builtin,
            retry_fallback=True,
            force=force,
            limit=limit,
            failed_retry_minutes=failed_retry_minutes,
            fallback_retry_minutes=fallback_retry_minutes,
        )
        results = []
        for candidate in plan["data"][:limit]:
            job_id = candidate["job_id"]
            result: Dict[str, Any] = {
                "job_id": job_id,
                "lottery_match_id": candidate.get("lottery_match_id"),
                "match_date": candidate.get("match_date"),
                "match": f"{candidate.get('home_team')} vs {candidate.get('away_team')}",
                "target_external": candidate.get("external_collectors", []),
                "target_builtin": candidate.get("builtin_requirements", []),
                "gaps": candidate.get("gaps", []),
                "channel_plan": candidate.get("channel_plan", {}),
            }
            try:
                if candidate.get("builtin_requirements"):
                    builtin = self.collect_builtin(job_id, force=False)
                    collected_builtin = {
                        item.get("requirement_key")
                        for item in builtin.get("collected", [])
                        if item.get("requirement_key")
                    }
                    unresolved_builtin = [
                        key for key in candidate.get("builtin_requirements", [])
                        if key not in collected_builtin
                    ]
                    if unresolved_builtin:
                        with self._connect() as conn:
                            for key in unresolved_builtin:
                                artifact = ArtifactCreate(
                                    requirement_key=key,
                                    source="intelligence_builtin_gap_fill",
                                    payload={
                                        "collector_status": "no_artifact",
                                        "reason": "Builtin collector returned no usable artifact during prioritized gap fill.",
                                        "trigger": "fill_gaps",
                                    },
                                    confidence=0.0,
                                    status=RequirementStatus.failed,
                                )
                                self._save_artifact(conn, "artifact:" + uuid.uuid4().hex, job_id, artifact)
                            self._update_job_status(conn, job_id)
                            conn.commit()
                    result["builtin"] = {
                        "collected": builtin.get("collected", []),
                        "missing": builtin.get("missing", []),
                        "skipped": builtin.get("skipped", []),
                        "marked_failed": unresolved_builtin,
                    }
                if candidate.get("external_collectors"):
                    gap_keys = [g.get("key") for g in candidate.get("gaps", []) if g.get("key")]
                    external = self.collect_external(
                        job_id,
                        collectors=candidate["external_collectors"],
                        network=network,
                        force=True,
                        gap_keys=gap_keys,
                    )
                    result["external"] = {
                        "collected": external.get("collected", []),
                        "skipped": external.get("skipped", []),
                    }
                package = self.build_package(job_id)
                summary = package.get("package", {}).get("summary", {})
                result["after"] = {
                    "completeness": summary.get("completeness"),
                    "strict_completeness": summary.get("strict_completeness"),
                    "average_confidence": summary.get("average_confidence"),
                    "missing_required": summary.get("missing_required", []),
                }
                result["status"] = "completed"
            except Exception as exc:
                result["status"] = "failed"
                result["error"] = str(exc)
            results.append(result)
        return {
            "range": plan["range"],
            "planned_candidates": plan["total_candidates"],
            "processed": len(results),
            "network": network,
            "force": force,
            "collectors": plan["collectors"],
            "results": results,
        }

    def fill_gaps_logged(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        collectors: Optional[List[str]] = None,
        network: bool = True,
        force: bool = False,
        include_optional: bool = True,
        include_builtin: bool = True,
        limit: int = 8,
        failed_retry_minutes: int = 180,
        fallback_retry_minutes: int = 360,
        trigger_source: str = "manual_gap_fill",
    ) -> Dict[str, Any]:
        run_id = "run:" + uuid.uuid4().hex
        range_label = f"{start_date or ''}..{end_date or ''}"
        selected_collectors = collectors or list(EXTERNAL_GAP_COLLECTORS)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intelligence_runs (
                    run_id, run_date, trigger_source, include_external,
                    collectors_json, network, force, status
                ) VALUES (?, ?, ?, 1, ?, ?, ?, 'running')
                """,
                (
                    run_id,
                    range_label,
                    trigger_source,
                    _json(selected_collectors),
                    1 if network else 0,
                    1 if force else 0,
                ),
            )
            conn.commit()
        try:
            # Ensure intelligence_jobs exist for the target date range before
            # trying to fill gaps. Without this, fill_gaps finds zero candidates
            # because it only queries existing jobs — and nothing in the automation
            # pipeline creates those rows (generate_jobs_for_date was only reachable
            # via HTTP API).
            generated = self.generate_jobs_for_date_range(
                start_date=start_date, end_date=end_date,
            )
            summary = self.fill_gaps(
                start_date=start_date,
                end_date=end_date,
                collectors=selected_collectors,
                network=network,
                force=force,
                include_optional=include_optional,
                include_builtin=include_builtin,
                limit=limit,
                failed_retry_minutes=failed_retry_minutes,
                fallback_retry_minutes=fallback_retry_minutes,
            )
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE intelligence_runs
                    SET status = 'completed',
                        finished_at = CURRENT_TIMESTAMP,
                        summary_json = ?
                    WHERE run_id = ?
                    """,
                    (_json(summary), run_id),
                )
                conn.commit()
            return {"run_id": run_id, "status": "completed", "summary": summary}
        except Exception as exc:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE intelligence_runs
                    SET status = 'failed',
                        finished_at = CURRENT_TIMESTAMP,
                        error = ?
                    WHERE run_id = ?
                    """,
                    (str(exc), run_id),
                )
                conn.commit()
            raise

    def list_runs(self, limit: int = 50) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = []
            for row in conn.execute(
                """
                SELECT * FROM intelligence_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ):
                item = dict(row)
                item["collectors"] = _loads(item.pop("collectors_json", "[]"), [])
                item["summary"] = _loads(item.pop("summary_json", "{}"), {})
                rows.append(item)
            return {"data": rows, "total": len(rows)}

    def get_run(self, run_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM intelligence_runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            item = dict(row)
            item["collectors"] = _loads(item.pop("collectors_json", "[]"), [])
            item["summary"] = _loads(item.pop("summary_json", "{}"), {})
            return item

    def list_reviews(self, job_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        clauses = []
        params: List[Any] = []
        if job_id:
            clauses.append("job_id = ?")
            params.append(job_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            rows = []
            for row in conn.execute(
                f"""
                SELECT * FROM intelligence_reviews
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ):
                rows.append(self._review_from_row(row))
            total = conn.execute(f"SELECT COUNT(*) FROM intelligence_reviews {where}", params[:-1]).fetchone()[0]
            return {"data": rows, "total": total}

    def list_training_samples(
        self,
        limit: int = 200,
        only_settled: bool = True,
        attribution: Optional[str] = None,
        include_raw_package: bool = False,
    ) -> Dict[str, Any]:
        clauses = []
        params: List[Any] = []
        if only_settled:
            clauses.append("r.actual_result IS NOT NULL")
        if attribution:
            clauses.append("r.attribution = ?")
            params.append(attribution)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            samples = []
            rows = conn.execute(
                f"""
                SELECT r.*, j.match_date, j.match_time, j.league_name, j.home_team, j.away_team,
                       j.competition_type, j.analysis_view, p.package_json
                FROM intelligence_reviews r
                JOIN intelligence_jobs j ON j.job_id = r.job_id
                LEFT JOIN intelligence_packages p ON p.job_id = r.job_id
                {where}
                ORDER BY j.match_date DESC, r.created_at DESC
                LIMIT ?
                """,
                params,
            )
            for row in rows:
                samples.append(self._training_sample_from_row(row, include_raw_package=include_raw_package))
            total = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM intelligence_reviews r
                JOIN intelligence_jobs j ON j.job_id = r.job_id
                {where}
                """,
                params[:-1],
            ).fetchone()[0]
            return {"data": samples, "total": total}

    def training_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10000,
    ) -> Dict[str, Any]:
        clauses = ["r.actual_result IS NOT NULL"]
        params: List[Any] = []
        if start_date:
            clauses.append("j.match_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("j.match_date <= ?")
            params.append(end_date)
        where = " WHERE " + " AND ".join(clauses)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT r.*, j.match_date, j.match_time, j.league_name, j.home_team, j.away_team,
                       j.competition_type, j.analysis_view, p.package_json
                FROM intelligence_reviews r
                JOIN intelligence_jobs j ON j.job_id = r.job_id
                LEFT JOIN intelligence_packages p ON p.job_id = r.job_id
                {where}
                ORDER BY j.match_date DESC, r.created_at DESC
                LIMIT ?
                """,
                params,
            )
            samples = [self._training_sample_from_row(row) for row in rows]
        total = len(samples)
        correct = sum(1 for item in samples if item.get("is_correct") is True)
        wrong = sum(1 for item in samples if item.get("is_correct") is False)
        return {
            "range": {"start_date": start_date, "end_date": end_date},
            "total": total,
            "correct": correct,
            "wrong": wrong,
            "accuracy": round(correct / total * 100, 1) if total else 0,
            "by_attribution": self._group_training_samples(samples, "attribution"),
            "by_date": self._group_training_samples(samples, "match_date"),
            "by_analysis_view": self._group_training_samples(samples, "analysis_view"),
            "by_strict_coverage": self._coverage_buckets(samples),
            "requirement_risk": self._requirement_risk(samples),
            "wrong_cases": self._wrong_case_digest(samples, limit=20),
        }

    def export_training_samples(
        self,
        limit: int = 10000,
        only_settled: bool = True,
        attribution: Optional[str] = None,
        include_raw_package: bool = False,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        samples = self.list_training_samples(
            limit=limit,
            only_settled=only_settled,
            attribution=attribution,
            include_raw_package=include_raw_package,
        )["data"]
        project_root = Path(__file__).resolve().parents[3]
        export_dir = Path(output_dir) if output_dir else project_root / "data" / "intelligence_exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        suffix = attribution or ("settled" if only_settled else "all")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = export_dir / f"training_samples_{suffix}_{timestamp}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for sample in samples:
                f.write(_json(sample) + "\n")
        return {
            "path": str(path),
            "format": "jsonl",
            "count": len(samples),
            "only_settled": only_settled,
            "attribution": attribution,
            "include_raw_package": include_raw_package,
        }

    def get_review(self, review_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM intelligence_reviews WHERE review_id = ?", (review_id,)).fetchone()
            if not row:
                raise KeyError(review_id)
            return self._review_from_row(row)

    def add_review(self, job_id: str, payload: ReviewCreate) -> Dict[str, Any]:
        review_id = payload.result.get("review_id") or "review:" + uuid.uuid4().hex
        with self._connect() as conn:
            job = self.get_job(job_id, conn=conn)
            result = dict(payload.result)
            attribution = dict(payload.attribution)
            self._save_review(conn, review_id, job, result, attribution, payload.source)
            if result.get("actual_result") is not None or result.get("is_correct") is not None:
                conn.execute(
                    "UPDATE intelligence_jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    (JobStatus.validated.value, job_id),
                )
            conn.commit()
            return {"review": self.get_review(review_id), "job": self.get_job(job_id, conn=conn)}

    def auto_review_job(self, job_id: str, play_type: str = "spf") -> Dict[str, Any]:
        with self._connect() as conn:
            job = self.get_job(job_id, conn=conn)
            package = self.build_package(job_id)["package"]
            result = self._build_auto_review_result(conn, job, package, play_type)
            attribution = self._build_auto_attribution(job, package, result)
            review_id = f"review:{job_id}:{play_type}"
            self._save_review(conn, review_id, job, result, attribution, "auto_lottery_validation")
            if result.get("actual_result") is not None:
                conn.execute(
                    "UPDATE intelligence_jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    (JobStatus.validated.value, job_id),
                )
            conn.commit()
            return {"review": self.get_review(review_id), "job": self.get_job(job_id, conn=conn)}

    def auto_review_for_date(self, match_date: Optional[str] = None, play_type: str = "spf") -> Dict[str, Any]:
        jobs = self.list_jobs(match_date=match_date, limit=500)["data"]
        reviewed = []
        pending = []
        failed = []
        for job in jobs:
            try:
                result = self.auto_review_job(job["job_id"], play_type=play_type)
                review = result["review"]
                if review["result"].get("actual_result") is None:
                    pending.append(review)
                else:
                    reviewed.append(review)
            except Exception as exc:
                failed.append({"job_id": job["job_id"], "reason": str(exc)})
        return {
            "reviewed": reviewed,
            "pending": pending,
            "failed": failed,
            "skipped": [{"job_id": item["job_id"], "reason": "missing actual result"} for item in pending] + failed,
            "total_jobs": len(jobs),
        }

    def list_jobs(self, match_date: Optional[str] = None, status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        clauses: List[str] = []
        params: List[Any] = []
        if match_date:
            clauses.append("j.match_date = ?")
            params.append(match_date)
        if status:
            clauses.append("j.status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"""
            SELECT j.*,
                   p.completeness AS package_completeness,
                   p.missing_required_json,
                   p.package_json
            FROM intelligence_jobs j
            LEFT JOIN intelligence_packages p ON p.job_id = j.job_id
            {where}
            ORDER BY j.match_date DESC, j.priority ASC, j.created_at DESC
            LIMIT ?
        """
        params.append(limit)
        with self._connect() as conn:
            rows = []
            for row in conn.execute(sql, params):
                item = dict(row)
                package = _loads(item.pop("package_json", "{}"), {})
                package_summary = package.get("summary", {}) if isinstance(package, dict) else {}
                missing_required = package_summary.get("missing_required")
                if missing_required is None:
                    missing_required = _loads(item.pop("missing_required_json", "[]"), [])
                else:
                    item.pop("missing_required_json", None)
                item["package_summary"] = package_summary
                item["package_completeness"] = item.get("package_completeness") or package_summary.get("completeness")
                item["strict_completeness"] = package_summary.get("strict_completeness")
                item["average_confidence"] = package_summary.get("average_confidence")
                item["missing_required"] = missing_required or []
                rows.append(item)
            total = conn.execute(f"SELECT COUNT(*) FROM intelligence_jobs j {where}", params[:-1]).fetchone()[0]
            return {"data": rows, "total": total}

    def get_job(self, job_id: str, conn=None) -> Dict[str, Any]:
        close_conn = False
        if conn is None:
            conn = self._connect()
            close_conn = True
        try:
            row = conn.execute("SELECT * FROM intelligence_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            job = dict(row)
            requirements = []
            for req in conn.execute(
                "SELECT * FROM intelligence_requirements WHERE job_id = ? ORDER BY required DESC, category, key",
                (job_id,),
            ):
                item = dict(req)
                item["preferred_sources"] = _loads(item.get("preferred_sources"), [])
                requirements.append(item)
            job["requirements"] = requirements
            job["summary"] = self._summarize_requirements(requirements)
            return job
        finally:
            if close_conn:
                conn.close()

    def add_artifact(self, job_id: str, artifact: ArtifactCreate) -> Dict[str, Any]:
        artifact_id = "artifact:" + uuid.uuid4().hex
        with self._connect() as conn:
            self._save_artifact(conn, artifact_id, job_id, artifact)
            self._update_job_status(conn, job_id)
            conn.commit()
            return {"artifact_id": artifact_id, "job": self.get_job(job_id, conn=conn)}

    def collect_builtin(self, job_id: str, force: bool = False) -> Dict[str, Any]:
        collectors = {
            "base_info": self._collect_base_info,
            "odds_1x2": self._collect_odds_1x2,
            "market_movement": self._collect_market_movement,
            "recent_form": self._collect_recent_form,
            "goal_tempo_profile": self._collect_goal_tempo_profile,
            "elo_rating": self._collect_elo_rating,
            "fifa_ranking": self._collect_fifa_ranking,
            "standings_context": self._collect_standings_context,
            "tournament_context": self._collect_tournament_context,
            "travel_fatigue": self._collect_travel_fatigue,
            "major_tournament_experience": self._collect_major_tournament_experience,
            "home_away_profile": self._collect_home_away_profile,
            "data_quality": self._collect_data_quality,
        }
        collected = []
        skipped = []
        missing = []
        with self._connect() as conn:
            self._link_match_if_possible(conn, job_id)
            job = self.get_job(job_id, conn=conn)
            for req in job["requirements"]:
                key = req["key"]
                if not force and req.get("status") in ("collected", "fallback_used"):
                    skipped.append(key)
                    continue
                collector = collectors.get(key)
                if not collector:
                    missing.append(key)
                    continue
                result = collector(conn, job)
                if not result:
                    missing.append(key)
                    continue
                payload, source, confidence, status = result
                artifact = ArtifactCreate(
                    requirement_key=key,
                    source=source,
                    payload=payload,
                    confidence=confidence,
                    status=RequirementStatus(status),
                )
                artifact_id = "artifact:" + uuid.uuid4().hex
                self._save_artifact(conn, artifact_id, job_id, artifact)
                collected.append({"requirement_key": key, "artifact_id": artifact_id, "source": source})
            self._update_job_status(conn, job_id)
            conn.commit()
            job = self.get_job(job_id, conn=conn)
        package = self.build_package(job_id)
        return {
            "job_id": job_id,
            "collected": collected,
            "skipped": skipped,
            "missing": missing,
            "unhandled": missing,
            "job": job,
            "package": package,
        }

    def link_match(self, job_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            result = self._link_match_if_possible(conn, job_id)
            conn.commit()
            return {"job_id": job_id, "linked": result, "job": self.get_job(job_id, conn=conn)}

    def collect_external(
        self,
        job_id: str,
        collectors: Optional[List[str]] = None,
        network: bool = True,
        force: bool = False,
        gap_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        collected = []
        skipped = []
        with self._connect() as conn:
            job = self.get_job(job_id, conn=conn)
            current = {req["key"]: req for req in job["requirements"]}
            artifacts = run_external_collectors(
                conn, job, selected=collectors, network=network, gap_keys=gap_keys
            )
            for artifact in artifacts:
                req = current.get(artifact.requirement_key)
                if req and not force and req.get("status") in ("collected", "fallback_used"):
                    skipped.append(artifact.requirement_key)
                    continue
                artifact_id = "artifact:" + uuid.uuid4().hex
                self._save_artifact(conn, artifact_id, job_id, artifact)
                collected.append(
                    {
                        "requirement_key": artifact.requirement_key,
                        "artifact_id": artifact_id,
                        "source": artifact.source,
                        "status": artifact.status.value,
                        "confidence": artifact.confidence,
                    }
                )
            self._update_job_status(conn, job_id)
            conn.commit()
            job = self.get_job(job_id, conn=conn)
        package = self.build_package(job_id)
        return {"job_id": job_id, "collected": collected, "skipped": skipped, "job": job, "package": package}

    def build_package(self, job_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            job = self.get_job(job_id, conn=conn)
            artifacts: Dict[str, Dict[str, Any]] = {}
            artifact_history: Dict[str, List[Dict[str, Any]]] = {}
            for row in conn.execute(
                "SELECT * FROM intelligence_artifacts WHERE job_id = ? ORDER BY captured_at DESC, artifact_id DESC",
                (job_id,),
            ):
                item = {
                    "source": row["source"],
                    "confidence": row["confidence"],
                    "captured_at": row["captured_at"],
                    "payload": _loads(row["payload_json"], {}),
                }
                key = row["requirement_key"]
                artifacts.setdefault(key, item)
                artifact_history.setdefault(key, []).append(item)
            summary = job["summary"]
            package = {
                "job": {k: v for k, v in job.items() if k not in ("requirements", "summary")},
                "requirements": job["requirements"],
                "artifacts": artifacts,
                "artifact_history": artifact_history,
                "summary": summary,
                "analysis_view": job["analysis_view"],
                "next_actions": self._next_actions(job["requirements"]),
            }
            package_id = "package:" + job_id
            conn.execute(
                """
                INSERT INTO intelligence_packages (
                    package_id, job_id, package_json, completeness, missing_required_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(job_id) DO UPDATE SET
                    package_json=excluded.package_json,
                    completeness=excluded.completeness,
                    missing_required_json=excluded.missing_required_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (package_id, job_id, _json(package), summary["completeness"], _json(summary["missing_required"])),
            )
            conn.commit()
            return {
                "job_id": job_id,
                "completeness": summary["completeness"],
                "strict_completeness": summary["strict_completeness"],
                "missing_required": summary["missing_required"],
                "package": package,
            }

    def get_package(self, job_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            job = self.get_job(job_id, conn=conn)
            row = conn.execute(
                "SELECT * FROM intelligence_packages WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                summary = job["summary"]
                return {
                    "job_id": job_id,
                    "exists": False,
                    "completeness": summary.get("completeness", 0),
                    "strict_completeness": summary.get("strict_completeness", 0),
                    "missing_required": summary.get("missing_required", []),
                    "package": {
                        "job": {k: v for k, v in job.items() if k not in ("requirements", "summary")},
                        "requirements": job["requirements"],
                        "artifacts": {},
                        "artifact_history": {},
                        "summary": summary,
                        "analysis_view": job["analysis_view"],
                        "next_actions": self._next_actions(job["requirements"]),
                    },
                }
            package = _loads(row["package_json"], {})
            summary = package.get("summary", {}) if isinstance(package, dict) else {}
            missing_required = summary.get("missing_required")
            if missing_required is None:
                missing_required = _loads(row["missing_required_json"], [])
            return {
                "job_id": job_id,
                "exists": True,
                "completeness": row["completeness"],
                "strict_completeness": summary.get("strict_completeness", 0),
                "missing_required": missing_required or [],
                "updated_at": row["updated_at"],
                "package": package,
            }

    def _review_from_row(self, row) -> Dict[str, Any]:
        item = dict(row)
        item["result"] = _loads(item.pop("result_json", "{}"), {})
        item["attribution_detail"] = _loads(item.pop("attribution_json", "{}"), {})
        item["is_correct"] = None if item.get("is_correct") is None else bool(item.get("is_correct"))
        return item

    def _training_sample_from_row(self, row, include_raw_package: bool = False) -> Dict[str, Any]:
        item = self._review_from_row(row)
        package = _loads(item.pop("package_json", "{}"), {})
        requirements = package.get("requirements", []) if isinstance(package, dict) else []
        artifacts = package.get("artifacts", {}) if isinstance(package, dict) else {}
        summary = package.get("summary", {}) if isinstance(package, dict) else {}
        sample = {
            "review_id": item.get("review_id"),
            "job_id": item.get("job_id"),
            "lottery_match_id": item.get("lottery_match_id"),
            "match_date": item.get("match_date"),
            "match_time": item.get("match_time"),
            "league_name": item.get("league_name"),
            "home_team": item.get("home_team"),
            "away_team": item.get("away_team"),
            "analysis_view": item.get("analysis_view"),
            "competition_type": item.get("competition_type"),
            "play_type": item.get("play_type"),
            "predicted_result": item.get("predicted_result"),
            "actual_result": item.get("actual_result"),
            "is_correct": item.get("is_correct"),
            "attribution": item.get("attribution"),
            "confidence": item.get("confidence"),
            "source": item.get("source"),
            "package_summary": summary,
            "requirement_status": {req.get("key"): req.get("status") for req in requirements if req.get("key")},
            "requirement_confidence": {req.get("key"): req.get("confidence") for req in requirements if req.get("key")},
            "artifact_sources": {key: artifact.get("source") for key, artifact in artifacts.items()},
            "artifact_confidence": {key: artifact.get("confidence") for key, artifact in artifacts.items()},
            "evidence_flags": {
                "has_weather": "weather" in artifacts,
                "has_news": "team_news" in artifacts,
                "has_injuries": "injuries_suspensions" in artifacts,
                "has_lineup": "expected_lineup" in artifacts,
                "has_tournament_context": "tournament_context" in artifacts,
            },
            "review": {
                "result": item.get("result"),
                "attribution_detail": item.get("attribution_detail"),
            },
        }
        if include_raw_package:
            sample["raw_package"] = package
        return sample

    def _group_training_samples(self, samples: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        for sample in samples:
            value = sample.get(key) or "unknown"
            bucket = groups.setdefault(str(value), {"key": value, "total": 0, "correct": 0, "wrong": 0})
            bucket["total"] += 1
            if sample.get("is_correct") is True:
                bucket["correct"] += 1
            elif sample.get("is_correct") is False:
                bucket["wrong"] += 1
        result = []
        for bucket in groups.values():
            total = bucket["total"]
            bucket["accuracy"] = round(bucket["correct"] / total * 100, 1) if total else 0
            result.append(bucket)
        return sorted(result, key=lambda item: (-item["total"], str(item["key"])))

    def _coverage_buckets(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets = {
            "0-49": {"key": "0-49", "total": 0, "correct": 0, "wrong": 0},
            "50-69": {"key": "50-69", "total": 0, "correct": 0, "wrong": 0},
            "70-84": {"key": "70-84", "total": 0, "correct": 0, "wrong": 0},
            "85-100": {"key": "85-100", "total": 0, "correct": 0, "wrong": 0},
        }
        for sample in samples:
            strict = float((sample.get("package_summary") or {}).get("strict_completeness") or 0)
            if strict < 50:
                key = "0-49"
            elif strict < 70:
                key = "50-69"
            elif strict < 85:
                key = "70-84"
            else:
                key = "85-100"
            buckets[key]["total"] += 1
            if sample.get("is_correct") is True:
                buckets[key]["correct"] += 1
            elif sample.get("is_correct") is False:
                buckets[key]["wrong"] += 1
        result = []
        for bucket in buckets.values():
            total = bucket["total"]
            bucket["accuracy"] = round(bucket["correct"] / total * 100, 1) if total else 0
            result.append(bucket)
        return result

    def _requirement_risk(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        risks: Dict[str, Dict[str, Any]] = {}
        for sample in samples:
            statuses = sample.get("requirement_status") or {}
            confidences = sample.get("requirement_confidence") or {}
            for key, status in statuses.items():
                is_risky = status in ("missing", "fallback_used")
                confidence = confidences.get(key)
                if confidence is not None:
                    try:
                        is_risky = is_risky or float(confidence) < 0.45
                    except Exception:
                        pass
                if not is_risky:
                    continue
                bucket = risks.setdefault(key, {"requirement_key": key, "total": 0, "correct": 0, "wrong": 0})
                bucket["total"] += 1
                if sample.get("is_correct") is True:
                    bucket["correct"] += 1
                elif sample.get("is_correct") is False:
                    bucket["wrong"] += 1
        result = []
        for bucket in risks.values():
            total = bucket["total"]
            bucket["wrong_rate"] = round(bucket["wrong"] / total * 100, 1) if total else 0
            result.append(bucket)
        return sorted(result, key=lambda item: (-item["wrong"], -item["total"], item["requirement_key"]))

    def _wrong_case_digest(self, samples: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
        wrong_cases = [sample for sample in samples if sample.get("is_correct") is False]
        digest = []
        for sample in wrong_cases[:limit]:
            digest.append(
                {
                    "review_id": sample.get("review_id"),
                    "job_id": sample.get("job_id"),
                    "match_date": sample.get("match_date"),
                    "match": f"{sample.get('home_team')} vs {sample.get('away_team')}",
                    "league_name": sample.get("league_name"),
                    "predicted_result": sample.get("predicted_result"),
                    "actual_result": sample.get("actual_result"),
                    "attribution": sample.get("attribution"),
                    "strict_completeness": (sample.get("package_summary") or {}).get("strict_completeness"),
                    "low_confidence_requirements": [
                        key
                        for key, value in (sample.get("requirement_confidence") or {}).items()
                        if value is not None and float(value) < 0.45
                    ],
                }
            )
        return digest

    def _save_review(
        self,
        conn,
        review_id: str,
        job: Dict[str, Any],
        result: Dict[str, Any],
        attribution: Dict[str, Any],
        source: str,
    ) -> None:
        is_correct = result.get("is_correct")
        if isinstance(is_correct, bool):
            is_correct = 1 if is_correct else 0
        elif is_correct is not None:
            is_correct = int(is_correct)
        conn.execute(
            """
            INSERT OR REPLACE INTO intelligence_reviews (
                review_id, job_id, lottery_match_id, play_type,
                predicted_result, actual_result, is_correct, attribution,
                confidence, source, result_json, attribution_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                review_id,
                job["job_id"],
                result.get("lottery_match_id") or job.get("lottery_match_id"),
                result.get("play_type"),
                result.get("predicted_result"),
                result.get("actual_result"),
                is_correct,
                attribution.get("level") or result.get("attribution"),
                result.get("predicted_prob") or attribution.get("confidence"),
                source,
                _json(result),
                _json(attribution),
            ),
        )

    def _build_auto_review_result(
        self,
        conn,
        job: Dict[str, Any],
        package: Dict[str, Any],
        play_type: str,
    ) -> Dict[str, Any]:
        lottery_match_id = job.get("lottery_match_id")
        validation = self._latest_lottery_validation(conn, lottery_match_id, play_type)
        match_result = self._latest_lottery_result(conn, lottery_match_id, job.get("match_id"))
        prediction = self._latest_lottery_prediction(conn, lottery_match_id, play_type)
        report = self._latest_lottery_report(conn, lottery_match_id)

        predicted_result = (
            validation.get("predicted_result")
            or prediction.get("recommendation")
            or self._prediction_from_report(report, play_type)
        )
        actual_result = validation.get("actual_result") or match_result.get(f"{play_type}_result")
        predicted_result = self._normalize_spf_result(predicted_result) if play_type == "spf" else predicted_result
        actual_result = self._normalize_spf_result(actual_result) if play_type == "spf" else actual_result
        is_correct = validation.get("is_correct")
        if is_correct is None and predicted_result is not None and actual_result is not None:
            is_correct = predicted_result == actual_result
        elif is_correct is not None:
            is_correct = bool(is_correct)

        return {
            "job_id": job["job_id"],
            "lottery_match_id": lottery_match_id,
            "match_id": job.get("match_id"),
            "play_type": play_type,
            "predicted_result": predicted_result,
            "actual_result": actual_result,
            "is_correct": is_correct,
            "predicted_prob": validation.get("predicted_prob") or prediction.get("confidence"),
            "brier_score": validation.get("brier_score"),
            "validated_at": validation.get("validated_at"),
            "package_summary": package.get("summary", {}),
            "validation": validation,
            "match_result": match_result,
            "prediction": self._trim_prediction(prediction),
            "report": self._summarize_report(report),
        }

    def _build_auto_attribution(
        self,
        job: Dict[str, Any],
        package: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        summary = package.get("summary", {})
        requirements = package.get("requirements", [])
        missing_required = summary.get("missing_required", [])
        fallback_required = [req["key"] for req in requirements if req.get("required") and req.get("status") == "fallback_used"]
        low_confidence = [
            req["key"]
            for req in requirements
            if req.get("confidence") is not None and float(req.get("confidence")) < 0.45
        ]
        if result.get("actual_result") is None:
            level = "pending_result"
            detail = "Actual result is not available yet, so this job cannot be judged."
            actionable = False
        elif result.get("predicted_result") is None:
            level = "missing_prediction"
            detail = "No usable prediction was found in lottery_validation, lottery_predictions or analysis reports."
            actionable = True
        elif result.get("is_correct") is True:
            level = "correct"
            detail = "Prediction matched the actual result."
            actionable = False
        elif missing_required:
            level = "missing_required_evidence"
            detail = "Required evidence was missing at analysis time."
            actionable = True
        elif summary.get("strict_completeness", 100) < 80:
            level = "low_strict_data_coverage"
            detail = "The job was analyzable through fallback evidence, but authoritative coverage was low."
            actionable = True
        elif fallback_required:
            level = "fallback_evidence_risk"
            detail = "The wrong prediction depended on one or more required fallback artifacts."
            actionable = True
        elif "market_movement" in [req["key"] for req in requirements if req.get("status") == "missing"]:
            level = "missing_market_movement"
            detail = "Market movement was missing, so odds drift and late information gaps were not available."
            actionable = True
        else:
            level = "model_judgement_error"
            detail = "Core evidence was present, so this should be reviewed as model weighting or interpretation error."
            actionable = True
        return {
            "level": level,
            "detail": detail,
            "actionable": actionable,
            "confidence": self._attribution_confidence(level, summary),
            "evidence": {
                "job_id": job["job_id"],
                "play_type": result.get("play_type"),
                "predicted_result": result.get("predicted_result"),
                "actual_result": result.get("actual_result"),
                "is_correct": result.get("is_correct"),
                "package_summary": summary,
                "missing_required": missing_required,
                "fallback_required": fallback_required,
                "low_confidence_requirements": low_confidence,
            },
        }

    def _attribution_confidence(self, level: str, summary: Dict[str, Any]) -> float:
        if level in ("pending_result", "missing_prediction"):
            return 0.9
        if level == "correct":
            return 0.85
        if level == "low_strict_data_coverage":
            return 0.75
        if level == "fallback_evidence_risk":
            return 0.68
        if level == "missing_market_movement":
            return 0.6
        base = float(summary.get("average_confidence", 0.5) or 0.5)
        return round(min(max(base, 0.45), 0.8), 2)

    def _latest_lottery_validation(self, conn, lottery_match_id: Optional[str], play_type: str) -> Dict[str, Any]:
        if not lottery_match_id or not self._table_exists(conn, "lottery_validation"):
            return {}
        row = conn.execute(
            """
            SELECT *
            FROM lottery_validation
            WHERE lottery_match_id = ? AND play_type = ?
            ORDER BY validated_at DESC, validation_id DESC
            LIMIT 1
            """,
            (lottery_match_id, play_type),
        ).fetchone()
        return dict(row) if row else {}

    def _latest_lottery_result(self, conn, lottery_match_id: Optional[str], match_id: Optional[str]) -> Dict[str, Any]:
        if not self._table_exists(conn, "lottery_results"):
            return {}
        row = None
        if lottery_match_id:
            row = conn.execute(
                "SELECT * FROM lottery_results WHERE lottery_match_id = ? ORDER BY created_at DESC, result_id DESC LIMIT 1",
                (lottery_match_id,),
            ).fetchone()
        if not row and match_id:
            row = conn.execute(
                "SELECT * FROM lottery_results WHERE match_id = ? ORDER BY created_at DESC, result_id DESC LIMIT 1",
                (match_id,),
            ).fetchone()
        return dict(row) if row else {}

    def _latest_lottery_prediction(self, conn, lottery_match_id: Optional[str], play_type: str) -> Dict[str, Any]:
        if not lottery_match_id or not self._table_exists(conn, "lottery_predictions"):
            return {}
        row = conn.execute(
            """
            SELECT *
            FROM lottery_predictions
            WHERE lottery_match_id = ? AND play_type = ?
            ORDER BY created_at DESC, prediction_id DESC
            LIMIT 1
            """,
            (lottery_match_id, play_type),
        ).fetchone()
        if not row:
            return {}
        item = dict(row)
        item["predictions"] = _loads(item.get("predictions"), {})
        item["features"] = _loads(item.pop("features_json", "{}"), {})
        item["weights"] = _loads(item.pop("weights_json", "{}"), {})
        item["value_bets"] = _loads(item.get("value_bets"), item.get("value_bets"))
        return item

    def _latest_lottery_report(self, conn, lottery_match_id: Optional[str]) -> Dict[str, Any]:
        if not lottery_match_id or not self._table_exists(conn, "lottery_analysis_reports"):
            return {}
        row = conn.execute(
            """
            SELECT report_id, lottery_match_id, match_id, report_type, report_data, created_at
            FROM lottery_analysis_reports
            WHERE lottery_match_id = ? AND report_type IN ('prediction', 'full')
            ORDER BY CASE WHEN report_type = 'prediction' THEN 0 ELSE 1 END, created_at DESC, report_id DESC
            LIMIT 1
            """,
            (lottery_match_id,),
        ).fetchone()
        if not row:
            return {}
        item = dict(row)
        item["report_data"] = _loads(item.get("report_data"), {})
        return item

    def _prediction_from_report(self, report: Dict[str, Any], play_type: str) -> Optional[str]:
        data = report.get("report_data") or {}
        final = data.get("final_prediction") or {}
        if isinstance(final, dict):
            predicted = final.get("predicted_result") or final.get("recommendation")
            if predicted:
                return predicted
        play_predictions = data.get("play_predictions") or {}
        play = play_predictions.get(play_type) or {}
        if isinstance(play, dict):
            predicted = play.get("recommendation") or play.get("predicted_result")
            if predicted:
                return predicted
        analyses = data.get("analyses") or {}
        analysis = analyses.get(play_type) or {}
        if isinstance(analysis, dict):
            return analysis.get("recommendation") or analysis.get("predicted_result")
        return None

    def _normalize_spf_result(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        mapping = {
            "3": "3",
            "1": "1",
            "0": "0",
            "home_win": "3",
            "home": "3",
            "h": "3",
            "主胜": "3",
            "胜": "3",
            "draw": "1",
            "d": "1",
            "平": "1",
            "平局": "1",
            "away_win": "0",
            "away": "0",
            "a": "0",
            "客胜": "0",
            "负": "0",
        }
        return mapping.get(text.lower(), mapping.get(text, text if text in ("3", "1", "0") else None))

    def _trim_prediction(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        if not prediction:
            return {}
        return {
            "prediction_id": prediction.get("prediction_id"),
            "recommendation": prediction.get("recommendation"),
            "confidence": prediction.get("confidence"),
            "confidence_level": prediction.get("confidence_level"),
            "predictions": prediction.get("predictions"),
            "model_version": prediction.get("model_version"),
            "created_at": prediction.get("created_at"),
        }

    def _summarize_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        if not report:
            return {}
        data = report.get("report_data") or {}
        return {
            "report_id": report.get("report_id"),
            "report_type": report.get("report_type"),
            "created_at": report.get("created_at"),
            "final_prediction": data.get("final_prediction"),
            "summary": data.get("summary"),
            "play_prediction_keys": sorted((data.get("play_predictions") or {}).keys()),
            "analysis_keys": sorted((data.get("analyses") or {}).keys()),
            "feature_keys": sorted((data.get("features") or {}).keys()),
        }

    def _save_artifact(self, conn, artifact_id: str, job_id: str, artifact: ArtifactCreate) -> None:
        conn.execute(
            """
            INSERT INTO intelligence_artifacts (
                artifact_id, job_id, requirement_key, source, payload_json, confidence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, job_id, artifact.requirement_key, artifact.source, _json(artifact.payload), artifact.confidence),
        )
        conn.execute(
            """
            UPDATE intelligence_requirements
            SET status = ?, artifact_id = ?, confidence = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? AND key = ?
            """,
            (artifact.status.value, artifact_id, artifact.confidence, job_id, artifact.requirement_key),
        )

    def _collect_base_info(self, conn, job: Dict[str, Any]):
        home_team = self._load_team(conn, job.get("home_team_id"))
        away_team = self._load_team(conn, job.get("away_team_id"))
        linked_match = self._load_match(conn, job.get("match_id"))
        payload = {
            "match": {
                "job_id": job["job_id"],
                "match_id": job.get("match_id"),
                "lottery_match_id": job.get("lottery_match_id"),
                "match_date": job.get("match_date"),
                "match_time": job.get("match_time"),
                "league_name": job.get("league_name"),
                "competition_type": job.get("competition_type"),
                "analysis_view": job.get("analysis_view"),
                "linked_match": linked_match,
            },
            "home_team": home_team or {"team_id": job.get("home_team_id"), "name": job.get("home_team")},
            "away_team": away_team or {"team_id": job.get("away_team_id"), "name": job.get("away_team")},
        }
        return payload, "football_v2", 0.95, RequirementStatus.collected.value

    def _link_match_if_possible(self, conn, job_id: str) -> Optional[Dict[str, Any]]:
        job = conn.execute("SELECT * FROM intelligence_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not job:
            raise KeyError(job_id)
        if job["match_id"]:
            existing = self._load_match(conn, job["match_id"])
            if existing:
                return {"already_linked": True, "match_id": job["match_id"]}
        home_id = job["home_team_id"]
        away_id = job["away_team_id"]
        match_date = job["match_date"]
        if not home_id or not away_id or not match_date:
            return None
        candidates = [
            dict(row)
            for row in conn.execute(
                """
                SELECT match_id, match_date, match_time, status, source, league_id,
                       home_team_id, away_team_id, venue_city, venue
                FROM matches
                WHERE home_team_id = ?
                  AND away_team_id = ?
                  AND match_date BETWEEN date(?, '-1 day') AND date(?, '+1 day')
                """,
                (home_id, away_id, match_date, match_date),
            )
        ]
        if not candidates:
            return None
        best = sorted(candidates, key=lambda item: self._match_link_score(job, item), reverse=True)[0]
        conn.execute(
            "UPDATE intelligence_jobs SET match_id = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (best["match_id"], job_id),
        )
        return {"match_id": best["match_id"], "candidate_count": len(candidates), "score": self._match_link_score(job, best)}

    def _match_link_score(self, job, candidate: Dict[str, Any]) -> int:
        score = 0
        match_id = str(candidate.get("match_id") or "").lower()
        source = str(candidate.get("source") or "").lower()
        status = str(candidate.get("status") or "").lower()
        view = str(job["analysis_view"] or "").lower()
        if candidate.get("match_date") == job["match_date"]:
            score += 20
        else:
            score += 10
        if view in ("world_cup", "national_team"):
            if "world_cup" in match_id or match_id.startswith("wc_"):
                score += 60
            if "friendly" in match_id or "friendly" in source:
                score -= 30
        if status in ("scheduled", "not started"):
            score += 10
        if candidate.get("match_time"):
            score += 5
        return score

    def _collect_odds_1x2(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "lottery_odds"):
            return None
        def load_rows(play_type: str) -> List[Dict[str, Any]]:
            if job.get("lottery_match_id"):
                rows_by_lottery = [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT play_type, snapshot_type, odds_data, opening_odds, latest_odds,
                               odds_movement, update_time, created_at
                        FROM lottery_odds
                        WHERE lottery_match_id = ? AND play_type = ?
                        ORDER BY created_at DESC
                        """,
                        (job["lottery_match_id"], play_type),
                    )
                ]
                if rows_by_lottery:
                    return rows_by_lottery
            if job.get("match_id"):
                return [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT play_type, snapshot_type, odds_data, opening_odds, latest_odds,
                               odds_movement, update_time, created_at
                        FROM lottery_odds
                        WHERE match_id = ? AND play_type = ?
                        ORDER BY created_at DESC
                        """,
                        (job["match_id"], play_type),
                    )
                ]
            return []

        rows = []
        rows = load_rows("spf")
        mode = "spf"
        source = "lottery_odds"
        confidence = 0.85
        status = RequirementStatus.collected.value
        if not rows:
            rows = load_rows("rqspf")
            mode = "rqspf_fallback_no_spf"
            source = "lottery_odds_rqspf_fallback"
            confidence = 0.62
            status = RequirementStatus.fallback_used.value
        if not rows:
            return None
        for row in rows:
            for key in ("odds_data", "opening_odds", "latest_odds", "odds_movement"):
                row[key] = _loads(row.get(key), row.get(key))
        return {
            "mode": mode,
            "rows": rows,
            "notes": [
                "SPF odds are preferred for 1x2 evidence.",
                "RQSPF fallback is marked lower confidence and must not be treated as plain 1x2 odds.",
            ] if mode != "spf" else [],
        }, source, confidence, status

    def _collect_market_movement(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "lottery_odds"):
            return None
        rows = self._load_lottery_odds_rows(conn, job)
        if not rows:
            return None
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("play_type") or "unknown"), []).append(row)

        play_summaries = []
        significant_movements = []
        comparable_count = 0
        raw_movement_count = 0
        for play_type, play_rows in grouped.items():
            snapshots = self._extract_odds_snapshots(play_rows)
            comparison = self._compare_odds_maps(
                play_type,
                snapshots.get("opening"),
                snapshots.get("latest"),
            )
            parsed_raw_movements = []
            for row in play_rows:
                raw = _loads(row.get("odds_movement"), row.get("odds_movement"))
                if raw:
                    parsed_raw_movements.append(raw)
            raw_movement_count += len(parsed_raw_movements)
            if comparison.get("comparable"):
                comparable_count += 1
                significant_movements.extend(
                    {**item, "play_type": play_type}
                    for item in comparison.get("significant", [])
                )
            play_summaries.append(
                {
                    "play_type": play_type,
                    "snapshots_seen": len(play_rows),
                    "snapshot_types": sorted({str(row.get("snapshot_type") or "unknown") for row in play_rows}),
                    "opening_source": snapshots.get("opening_source"),
                    "latest_source": snapshots.get("latest_source"),
                    "comparison": comparison,
                    "raw_odds_movement": parsed_raw_movements[:5],
                }
            )

        significant_movements = sorted(
            significant_movements,
            key=lambda item: abs(_safe_float(item.get("probability_delta")) or _safe_float(item.get("odds_pct_delta"))),
            reverse=True,
        )[:20]
        payload = {
            "has_movement": bool(significant_movements or raw_movement_count),
            "has_comparable_snapshots": comparable_count > 0,
            "thresholds": {
                "odds_pct_delta": 0.03,
                "implied_probability_delta": 0.02,
            },
            "source_rows": len(rows),
            "play_types": sorted(grouped.keys()),
            "significant_movements": significant_movements,
            "play_summaries": play_summaries,
            "notes": [
                "Movement is computed from real opening/latest lottery_odds snapshots when explicit odds_movement is absent.",
                "For spf/rqspf, implied probabilities are normalized within 3/1/0 outcomes.",
            ],
        }
        if comparable_count:
            confidence = 0.76 if significant_movements else 0.68
            return payload, "lottery_odds", confidence, RequirementStatus.collected.value
        payload["gaps"] = ["Only one usable odds snapshot was available; market direction cannot be compared."]
        return payload, "lottery_odds", 0.45, RequirementStatus.fallback_used.value

    def _collect_travel_fatigue(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "matches"):
            return None
        match_context = self._load_match(conn, job.get("match_id")) or {}
        kickoff = self._match_kickoff_datetime(job, match_context)
        if not kickoff:
            return None
        home = self._team_travel_snapshot(conn, job.get("home_team_id"), kickoff, match_context)
        away = self._team_travel_snapshot(conn, job.get("away_team_id"), kickoff, match_context)
        gaps = []
        if not match_context:
            gaps.append("match context not linked in matches table")
        if not match_context.get("venue_city") and not match_context.get("venue"):
            gaps.append("current venue/city missing; travel distance is not estimated")
        for side, snapshot in (("home", home), ("away", away)):
            if not snapshot.get("previous_match"):
                gaps.append(f"{side} previous finished match missing")
        payload = {
            "current_match": {
                "match_id": match_context.get("match_id") or job.get("match_id"),
                "kickoff": kickoff.isoformat(timespec="minutes"),
                "venue": match_context.get("venue"),
                "venue_city": match_context.get("venue_city"),
                "neutral": bool(match_context.get("neutral")) if match_context.get("neutral") is not None else None,
            },
            "home": home,
            "away": away,
            "comparison": {
                "rest_hours_delta_home_minus_away": self._rest_delta(home, away),
                "short_rest_side": self._short_rest_side(home, away),
            },
            "gaps": gaps,
            "notes": [
                "Rest and schedule pressure are computed from real matches table dates.",
                "No travel distance is invented when coordinates or verified city chain are missing.",
            ],
        }
        previous_count = int(bool(home.get("previous_match"))) + int(bool(away.get("previous_match")))
        confidence = 0.48 + previous_count * 0.1
        if match_context:
            confidence += 0.08
        if match_context.get("venue_city"):
            confidence += 0.05
        confidence = min(round(confidence, 2), 0.74)
        status = RequirementStatus.collected.value if previous_count else RequirementStatus.fallback_used.value
        return payload, "football_v2.matches", confidence, status

    def _collect_major_tournament_experience(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "matches"):
            return None
        before_date = (job.get("match_date") or date.today().isoformat())[:10]
        home_team = self._load_team(conn, job.get("home_team_id")) or {}
        away_team = self._load_team(conn, job.get("away_team_id")) or {}
        home_aliases = self._team_aliases(home_team, job.get("home_team"))
        away_aliases = self._team_aliases(away_team, job.get("away_team"))
        home = self._team_major_tournament_snapshot(
            conn,
            job.get("home_team_id"),
            before_date,
            home_aliases,
        )
        away = self._team_major_tournament_snapshot(
            conn,
            job.get("away_team_id"),
            before_date,
            away_aliases,
        )
        total_major = home.get("db", {}).get("major_matches", 0) + away.get("db", {}).get("major_matches", 0)
        json_validated = home.get("history_json", {}).get("validated_records", 0) + away.get("history_json", {}).get("validated_records", 0)
        payload = {
            "before_date": before_date,
            "home": home,
            "away": away,
            "comparison": {
                "major_matches_delta_home_minus_away": home.get("db", {}).get("major_matches", 0) - away.get("db", {}).get("major_matches", 0),
                "world_cup_matches_delta_home_minus_away": home.get("db", {}).get("world_cup_matches", 0) - away.get("db", {}).get("world_cup_matches", 0),
                "knockout_matches_delta_home_minus_away": home.get("db", {}).get("knockout_matches", 0) - away.get("db", {}).get("knockout_matches", 0),
            },
            "notes": [
                "Primary counts use finished rows in matches before this match date.",
                "national_teams_history JSON is only used after team-name validation because some files are known to be mis-mapped.",
            ],
        }
        if total_major:
            return payload, "football_v2.matches", 0.72, RequirementStatus.collected.value
        if json_validated:
            return payload, "national_teams_history.validated", 0.6, RequirementStatus.collected.value
        payload["gaps"] = ["No validated finished major-tournament history was found for either team before this match."]
        return payload, "football_v2.matches", 0.42, RequirementStatus.fallback_used.value

    def _collect_recent_form(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "matches"):
            return None
        home_id = job.get("home_team_id")
        away_id = job.get("away_team_id")
        if not home_id or not away_id:
            return None
        match_date = job.get("match_date") or date.today().isoformat()
        payload = {
            "home": self._team_form(conn, home_id, match_date),
            "away": self._team_form(conn, away_id, match_date),
        }
        if not payload["home"]["matches"] and not payload["away"]["matches"]:
            return None
        return payload, "football_v2.matches", 0.75, RequirementStatus.collected.value

    def _collect_goal_tempo_profile(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "team_match_facts"):
            return {
                "gaps": ["team_match_facts table is missing; run scripts/build_team_match_facts.py --apply first."],
                "build_hint": "python scripts/build_team_match_facts.py --from 1900-01-01 --to <yesterday> --apply",
            }, "team_match_facts", 0.0, RequirementStatus.failed.value

        before_date = (job.get("match_date") or date.today().isoformat())[:10]
        home = self._team_goal_tempo_profile(conn, job.get("home_team_id"), before_date)
        away = self._team_goal_tempo_profile(conn, job.get("away_team_id"), before_date)
        home_signal = self._expected_goal_signal(home, away)
        away_signal = self._expected_goal_signal(away, home)
        total_signal = None
        if home_signal is not None and away_signal is not None:
            total_signal = round(home_signal + away_signal, 3)

        min_sample = min(home.get("sample_size", 0), away.get("sample_size", 0))
        half_samples = min(home.get("half_time_sample", 0), away.get("half_time_sample", 0))
        gaps = []
        if home.get("sample_size", 0) < 4:
            gaps.append(f"home goal/tempo sample too small: {home.get('sample_size', 0)}")
        if away.get("sample_size", 0) < 4:
            gaps.append(f"away goal/tempo sample too small: {away.get('sample_size', 0)}")
        if half_samples < 4:
            gaps.append(f"half-time tempo sample too small: {half_samples}")

        payload = {
            "before_date": before_date,
            "home": home,
            "away": away,
            "matchup_signal": {
                "home_expected_goal_signal": home_signal,
                "away_expected_goal_signal": away_signal,
                "total_goal_signal": total_signal,
                "both_teams_score_signal": self._both_teams_score_signal(home, away),
                "low_total_signal": self._low_total_signal(home, away),
                "high_total_signal": self._high_total_signal(home, away),
                "half_time_low_tempo_signal": self._half_time_low_tempo_signal(home, away),
            },
            "gaps": gaps,
            "notes": [
                "Only settled facts before kickoff are used; no post-match leakage.",
                "This profile is a factual input for score, O/U, handicap margin and half/full-time reasoning.",
            ],
        }
        if min_sample >= 8 and half_samples >= 6:
            confidence = 0.78
            status = RequirementStatus.collected.value
        elif min_sample >= 4:
            confidence = 0.62 if half_samples >= 3 else 0.55
            status = RequirementStatus.collected.value
        elif min_sample > 0:
            confidence = 0.38
            status = RequirementStatus.fallback_used.value
        else:
            confidence = 0.0
            status = RequirementStatus.failed.value
        return payload, "team_match_facts", confidence, status

    def _team_goal_tempo_profile(self, conn, team_id: Optional[int], before_date: str, limit: int = 12) -> Dict[str, Any]:
        if not team_id:
            return {"sample_size": 0, "matches": [], "gaps": ["missing team_id"]}
        rows = conn.execute(
            """
            SELECT source_name, source_match_id, team_name, opponent_name, league_name_cn,
                   match_date, is_home, goals_for, goals_against,
                   goals_ht_for, goals_ht_against, total_goals, ht_total_goals, result_code
            FROM team_match_facts
            WHERE team_id = ?
              AND date(match_date) < date(?)
              AND goals_for IS NOT NULL
              AND goals_against IS NOT NULL
            ORDER BY date(match_date) DESC, source_match_id DESC
            LIMIT ?
            """,
            (str(team_id), before_date, limit),
        ).fetchall()
        return self._summarize_goal_tempo_rows([dict(row) for row in rows])

    def _summarize_goal_tempo_rows(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        sample = len(rows)
        if not sample:
            return {"sample_size": 0, "matches": []}

        def avg(values: List[float]) -> Optional[float]:
            values = [float(v) for v in values if v is not None]
            return round(sum(values) / len(values), 3) if values else None

        goals_for = [_safe_float(row.get("goals_for"), None) for row in rows]
        goals_against = [_safe_float(row.get("goals_against"), None) for row in rows]
        total_goals = [_safe_float(row.get("total_goals"), None) for row in rows]
        ht_for = [_safe_float(row.get("goals_ht_for"), None) for row in rows if row.get("goals_ht_for") is not None]
        ht_against = [_safe_float(row.get("goals_ht_against"), None) for row in rows if row.get("goals_ht_against") is not None]
        ht_total = [_safe_float(row.get("ht_total_goals"), None) for row in rows if row.get("ht_total_goals") is not None]
        half_sample = len(ht_total)
        wins = sum(1 for row in rows if row.get("result_code") == "W")
        draws = sum(1 for row in rows if row.get("result_code") == "D")
        losses = sum(1 for row in rows if row.get("result_code") == "L")

        profile = {
            "sample_size": sample,
            "half_time_sample": half_sample,
            "avg_goals_for": avg(goals_for),
            "avg_goals_against": avg(goals_against),
            "avg_total_goals": avg(total_goals),
            "score_rate": round(sum(1 for v in goals_for if v and v > 0) / sample, 3),
            "concede_rate": round(sum(1 for v in goals_against if v and v > 0) / sample, 3),
            "clean_sheet_rate": round(sum(1 for v in goals_against if v == 0) / sample, 3),
            "blank_rate": round(sum(1 for v in goals_for if v == 0) / sample, 3),
            "both_teams_score_rate": round(
                sum(1 for gf, ga in zip(goals_for, goals_against) if gf and ga and gf > 0 and ga > 0) / sample,
                3,
            ),
            "high_total_rate": round(sum(1 for v in total_goals if v is not None and v >= 3) / sample, 3),
            "low_total_rate": round(sum(1 for v in total_goals if v is not None and v <= 2) / sample, 3),
            "win_rate": round(wins / sample, 3),
            "draw_rate": round(draws / sample, 3),
            "loss_rate": round(losses / sample, 3),
            "half_avg_for": avg(ht_for),
            "half_avg_against": avg(ht_against),
            "half_avg_total": avg(ht_total),
            "half_score_rate": round(sum(1 for v in ht_for if v and v > 0) / half_sample, 3) if half_sample else None,
            "half_concede_rate": round(sum(1 for v in ht_against if v and v > 0) / half_sample, 3) if half_sample else None,
            "half_under_1_5_rate": round(sum(1 for v in ht_total if v is not None and v <= 1) / half_sample, 3) if half_sample else None,
            "matches": [
                {
                    "date": row.get("match_date"),
                    "opponent": row.get("opponent_name"),
                    "score": f"{row.get('goals_for')}:{row.get('goals_against')}",
                    "half": (
                        f"{row.get('goals_ht_for')}:{row.get('goals_ht_against')}"
                        if row.get("goals_ht_for") is not None and row.get("goals_ht_against") is not None
                        else None
                    ),
                    "source": row.get("source_name"),
                    "league": row.get("league_name_cn"),
                }
                for row in rows[:8]
            ],
        }
        return profile

    def _expected_goal_signal(self, team: Dict[str, Any], opponent: Dict[str, Any]) -> Optional[float]:
        attack = _safe_float(team.get("avg_goals_for"), None)
        opponent_defense = _safe_float(opponent.get("avg_goals_against"), None)
        if attack is None and opponent_defense is None:
            return None
        if attack is None:
            return round(float(opponent_defense), 3)
        if opponent_defense is None:
            return round(float(attack), 3)
        return round((float(attack) * 0.58) + (float(opponent_defense) * 0.42), 3)

    def _both_teams_score_signal(self, home: Dict[str, Any], away: Dict[str, Any]) -> Optional[float]:
        values = [
            _safe_float(home.get("score_rate"), None),
            _safe_float(home.get("concede_rate"), None),
            _safe_float(away.get("score_rate"), None),
            _safe_float(away.get("concede_rate"), None),
        ]
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    def _low_total_signal(self, home: Dict[str, Any], away: Dict[str, Any]) -> Optional[float]:
        values = [_safe_float(home.get("low_total_rate"), None), _safe_float(away.get("low_total_rate"), None)]
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    def _high_total_signal(self, home: Dict[str, Any], away: Dict[str, Any]) -> Optional[float]:
        values = [_safe_float(home.get("high_total_rate"), None), _safe_float(away.get("high_total_rate"), None)]
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    def _half_time_low_tempo_signal(self, home: Dict[str, Any], away: Dict[str, Any]) -> Optional[float]:
        values = [_safe_float(home.get("half_under_1_5_rate"), None), _safe_float(away.get("half_under_1_5_rate"), None)]
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    def _collect_elo_rating(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "elo_ratings"):
            return None
        payload = {
            "home": self._single_row(conn, "SELECT * FROM elo_ratings WHERE team_id = ?", (job.get("home_team_id"),)),
            "away": self._single_row(conn, "SELECT * FROM elo_ratings WHERE team_id = ?", (job.get("away_team_id"),)),
        }
        if not payload["home"] and not payload["away"]:
            return None
        return payload, "elo_ratings", 0.8, RequirementStatus.collected.value

    def _collect_fifa_ranking(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "fifa_rankings"):
            return None
        payload = {
            "home": self._latest_fifa(conn, job.get("home_team_id")),
            "away": self._latest_fifa(conn, job.get("away_team_id")),
        }
        if not payload["home"] and not payload["away"]:
            return None
        return payload, "fifa_rankings", 0.75, RequirementStatus.collected.value

    def _collect_standings_context(self, conn, job: Dict[str, Any]):
        if not self._table_exists(conn, "standings"):
            return None
        payload = {
            "home": self._latest_standing(conn, job.get("home_team_id")),
            "away": self._latest_standing(conn, job.get("away_team_id")),
        }
        if not payload["home"] and not payload["away"]:
            return None
        return payload, "standings", 0.7, RequirementStatus.collected.value

    def _collect_tournament_context(self, conn, job: Dict[str, Any]):
        standings = self._collect_standings_context(conn, job)
        linked_match = self._load_match(conn, job.get("match_id"))
        match_context = linked_match or {}
        league = self._load_league(conn, match_context.get("league_id"))
        season = self._load_season(conn, match_context.get("season_id"))
        rules = self._load_league_rule(conn, match_context.get("league_id"))
        actual_match_date = match_context.get("match_date") or job.get("match_date") or date.today().isoformat()
        home_context = self._team_tournament_snapshot(
            conn,
            job.get("home_team_id"),
            actual_match_date,
            match_context.get("league_id"),
            match_context.get("season_id"),
        )
        away_context = self._team_tournament_snapshot(
            conn,
            job.get("away_team_id"),
            actual_match_date,
            match_context.get("league_id"),
            match_context.get("season_id"),
        )
        related_matches = self._related_lottery_matches(conn, job)
        world_cup_context = None
        world_cup_context_error = None
        league_text = " ".join(str(item or "") for item in [
            job.get("league_name"),
            league.get("league_code") if league else None,
            league.get("name_en") if league else None,
            league.get("name_cn") if league else None,
        ]).lower()
        is_world_cup = (
            "world_cup" in league_text
            or "world cup" in league_text
            or "fifa world cup" in league_text
            or "\u4e16\u754c\u676f" in league_text
        )
        if is_world_cup:
            try:
                try:
                    from backend.app.worldcup.service import WorldCupContextService
                except ImportError:
                    from app.worldcup.service import WorldCupContextService

                service = WorldCupContextService()
                try:
                    world_cup_context = service.get_match_context_by_teams(
                        home_team=job.get("home_team"),
                        away_team=job.get("away_team"),
                        match_date=job.get("match_time") or job.get("match_date"),
                        live=True,
                    )
                    world_cup_context["context_freshness"] = "live"
                except Exception as live_exc:
                    world_cup_context = service.get_match_context_by_teams(
                        home_team=job.get("home_team"),
                        away_team=job.get("away_team"),
                        match_date=job.get("match_time") or job.get("match_date"),
                        live=False,
                    )
                    world_cup_context["context_freshness"] = "offline_fallback"
                    world_cup_context["live_error"] = str(live_exc)
            except Exception as exc:
                world_cup_context_error = str(exc)
        has_world_cup_group_context = bool(world_cup_context and world_cup_context.get("group"))
        has_world_cup_context = bool(world_cup_context and (world_cup_context.get("match") or has_world_cup_group_context))
        gaps = []
        if not linked_match:
            gaps.append("job is not linked to matches table")
        if not match_context.get("group_name") and not has_world_cup_group_context:
            gaps.append("group_name missing; group qualification pressure cannot be computed exactly")
        if not standings and not has_world_cup_group_context:
            gaps.append("standings missing; using schedule/history fallback")
        if world_cup_context_error:
            gaps.append(f"world cup context unavailable: {world_cup_context_error}")
        inferred_stage = self._infer_tournament_stage(job, match_context, home_context, away_context)
        payload = {
            "analysis_view": job.get("analysis_view"),
            "league_name": job.get("league_name"),
            "competition": {
                "league": league,
                "season": season,
                "rules": rules,
                "match": match_context,
                "inferred_stage": inferred_stage,
            },
            "world_cup_context": world_cup_context,
            "standings": standings[0] if standings else None,
            "same_series_matches": related_matches,
            "home_context": home_context,
            "away_context": away_context,
            "gaps": gaps,
            "manual_review_needed": bool(gaps),
            "notes": [
                "World Cup/national-team context uses competition rules, same-series schedule, current-tournament prior matches and recent national-team form.",
                "For World Cup matches, live group standings and knockout-path context are preferred when available.",
            ],
        }
        status = RequirementStatus.collected.value if (standings or has_world_cup_context) else RequirementStatus.fallback_used.value
        if has_world_cup_group_context:
            confidence = 0.78 if world_cup_context.get("context_freshness") == "live" else 0.7
        else:
            confidence = 0.74 if standings else 0.58
        if not linked_match:
            confidence -= 0.08
        if not related_matches:
            confidence -= 0.04
        confidence = max(round(confidence, 2), 0.35)
        return payload, "intelligence_builtin", confidence, status

    def _infer_tournament_stage(
        self,
        job: Dict[str, Any],
        match_context: Dict[str, Any],
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        round_num = match_context.get("round_num")
        stage_type = match_context.get("stage_type")
        round_stage = match_context.get("round_stage")
        group_name = match_context.get("group_name")
        home_prior = home_context.get("current_competition", {}).get("played", 0) or 0
        away_prior = away_context.get("current_competition", {}).get("played", 0) or 0
        if stage_type or round_stage:
            label = stage_type or round_stage
        elif group_name or round_num in (1, 2, 3):
            label = "group_stage"
        elif str(job.get("analysis_view")) in ("world_cup", "national_team"):
            label = "national_team_tournament"
        else:
            label = "unknown"
        pressure = []
        if home_prior == 0 and away_prior == 0:
            pressure.append("opening_match_uncertainty")
            pressure.append("avoid_loss_priority")
        elif max(home_prior, away_prior) <= 2:
            pressure.append("group_points_and_goal_difference")
        else:
            pressure.append("knockout_or_late_group_context_requires_manual_check")
        if not group_name:
            pressure.append("missing_group_mapping")
        return {
            "label": label,
            "round_num": round_num,
            "round_stage": round_stage,
            "group_name": group_name,
            "home_prior_current_competition_matches": home_prior,
            "away_prior_current_competition_matches": away_prior,
            "pressure_factors": pressure,
        }

    def _collect_home_away_profile(self, conn, job: Dict[str, Any]):
        form = self._collect_recent_form(conn, job)
        if not form:
            return None
        payload = {
            "home_recent": form[0]["home"],
            "away_recent": form[0]["away"],
            "note": "Derived from recent matches until a dedicated home/away model is wired in.",
        }
        return payload, "football_v2.matches", 0.6, RequirementStatus.fallback_used.value

    def _collect_data_quality(self, conn, job: Dict[str, Any]):
        warnings = []
        if not job.get("home_team_id") or not job.get("away_team_id"):
            warnings.append("missing canonical team ids")
        if not job.get("match_date"):
            warnings.append("missing match date")
        if not job.get("match_time"):
            warnings.append("missing match time")
        if not self._collect_odds_1x2(conn, job):
            warnings.append("missing 1x2 odds artifact")
        payload = {
            "warnings": warnings,
            "has_team_ids": bool(job.get("home_team_id") and job.get("away_team_id")),
            "has_kickoff": bool(job.get("match_date") and job.get("match_time")),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "collection_channel_plan": channel_plan_for_requirements(
                [
                    "odds_1x2",
                    "market_movement",
                    "recent_form",
                    "goal_tempo_profile",
                    "injuries_suspensions",
                    "expected_lineup",
                    "team_news",
                    "weather",
                    "tournament_context",
                ]
            ),
        }
        confidence = 0.9 if not warnings else 0.65
        return payload, "intelligence_builtin", confidence, RequirementStatus.collected.value

    def _load_lottery_odds_rows(self, conn, job: Dict[str, Any]) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []
        if job.get("lottery_match_id"):
            conditions.append("lottery_match_id = ?")
            params.append(job.get("lottery_match_id"))
        if job.get("match_id"):
            conditions.append("match_id = ?")
            params.append(job.get("match_id"))
        if not conditions:
            return []
        rows = conn.execute(
            f"""
            SELECT play_type, snapshot_type, odds_data, opening_odds, latest_odds,
                   odds_movement, update_time, created_at
            FROM lottery_odds
            WHERE {" OR ".join(conditions)}
            ORDER BY play_type, COALESCE(created_at, update_time), snapshot_type
            """,
            params,
        )
        return [dict(row) for row in rows]

    def _extract_odds_snapshots(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        opening_candidates = []
        latest_candidates = []
        ordered = sorted(rows, key=lambda row: str(row.get("created_at") or row.get("update_time") or ""))
        for row in ordered:
            snapshot_type = str(row.get("snapshot_type") or "").lower()
            row_ref = {
                "snapshot_type": row.get("snapshot_type"),
                "created_at": row.get("created_at"),
                "update_time": row.get("update_time"),
            }
            opening_odds = self._parse_odds_map(row.get("opening_odds"))
            latest_odds = self._parse_odds_map(row.get("latest_odds"))
            odds_data = self._parse_odds_map(row.get("odds_data"))
            if opening_odds:
                opening_candidates.append((opening_odds, {**row_ref, "field": "opening_odds"}))
            if latest_odds:
                latest_candidates.append((latest_odds, {**row_ref, "field": "latest_odds"}))
            if odds_data and snapshot_type == "opening":
                opening_candidates.append((odds_data, {**row_ref, "field": "odds_data"}))
            if odds_data and snapshot_type in ("latest", "current", "closing"):
                latest_candidates.append((odds_data, {**row_ref, "field": "odds_data"}))
            if odds_data:
                opening_candidates.append((odds_data, {**row_ref, "field": "odds_data_earliest"}))
                latest_candidates.append((odds_data, {**row_ref, "field": "odds_data_latest"}))
        opening = opening_candidates[0] if opening_candidates else (None, None)
        latest = latest_candidates[-1] if latest_candidates else (None, None)
        return {
            "opening": opening[0],
            "opening_source": opening[1],
            "latest": latest[0],
            "latest_source": latest[1],
        }

    def _parse_odds_map(self, value: Any) -> Dict[str, float]:
        raw = _loads(value, value)
        if not isinstance(raw, dict):
            return {}
        parsed = {}
        for key, item in raw.items():
            try:
                odd = float(item)
            except (TypeError, ValueError):
                continue
            if odd > 1:
                parsed[str(key)] = round(odd, 4)
        return parsed

    def _compare_odds_maps(
        self,
        play_type: str,
        opening: Optional[Dict[str, float]],
        latest: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        if not opening or not latest:
            return {"comparable": False, "reason": "opening or latest odds missing", "movements": [], "significant": []}
        common = sorted(set(opening.keys()) & set(latest.keys()))
        if not common:
            return {"comparable": False, "reason": "opening/latest odds have no common keys", "movements": [], "significant": []}

        play = str(play_type or "").lower()
        normalized_probabilities = play in ("spf", "rqspf") and {"3", "1", "0"}.issubset(set(common))
        opening_prob = self._implied_probability_share(opening, common) if normalized_probabilities else {}
        latest_prob = self._implied_probability_share(latest, common) if normalized_probabilities else {}
        movements = []
        significant = []
        for key in common:
            open_odd = opening[key]
            latest_odd = latest[key]
            odds_delta = latest_odd - open_odd
            odds_pct_delta = odds_delta / open_odd if open_odd else 0
            prob_delta = None
            if key in opening_prob and key in latest_prob:
                prob_delta = latest_prob[key] - opening_prob[key]
            is_significant = abs(odds_pct_delta) >= 0.03 or (prob_delta is not None and abs(prob_delta) >= 0.02)
            movement = {
                "key": key,
                "label": self._odds_key_label(play, key),
                "opening": open_odd,
                "latest": latest_odd,
                "odds_delta": round(odds_delta, 4),
                "odds_pct_delta": round(odds_pct_delta, 4),
                "opening_probability": round(opening_prob[key], 4) if key in opening_prob else None,
                "latest_probability": round(latest_prob[key], 4) if key in latest_prob else None,
                "probability_delta": round(prob_delta, 4) if prob_delta is not None else None,
                "direction": "odds_down_probability_up" if odds_delta < 0 else ("odds_up_probability_down" if odds_delta > 0 else "flat"),
                "significant": is_significant,
            }
            movements.append(movement)
            if is_significant:
                significant.append(movement)
        if play not in ("spf", "rqspf"):
            movements = sorted(movements, key=lambda item: abs(item["odds_pct_delta"]), reverse=True)[:12]
        significant = sorted(
            significant,
            key=lambda item: max(abs(_safe_float(item.get("odds_pct_delta"))), abs(_safe_float(item.get("probability_delta")))),
            reverse=True,
        )[:12]
        return {
            "comparable": True,
            "normalized_probabilities": normalized_probabilities,
            "movement_count": len(movements),
            "significant_count": len(significant),
            "movements": movements,
            "significant": significant,
        }

    def _implied_probability_share(self, odds: Dict[str, float], keys: List[str]) -> Dict[str, float]:
        inverse = {key: (1 / odds[key]) for key in keys if odds.get(key)}
        total = sum(inverse.values())
        if not total:
            return {}
        return {key: value / total for key, value in inverse.items()}

    def _odds_key_label(self, play_type: str, key: str) -> str:
        if play_type == "rqspf":
            return {"3": "让胜", "1": "让平", "0": "让负"}.get(key, key)
        if play_type == "spf":
            return {"3": "主胜", "1": "平", "0": "客胜"}.get(key, key)
        return key

    def _match_kickoff_datetime(self, job: Dict[str, Any], match_context: Dict[str, Any]) -> Optional[datetime]:
        for value in (match_context.get("match_time"), job.get("match_time")):
            parsed = _safe_datetime(value)
            if parsed:
                return parsed
        date_text = match_context.get("match_date") or job.get("match_date")
        time_text = match_context.get("match_time") or job.get("match_time") or "00:00"
        if not date_text:
            return None
        if " " in str(time_text):
            parsed = _safe_datetime(time_text)
            if parsed:
                return parsed
        return _safe_datetime(f"{str(date_text)[:10]} {str(time_text)[:5]}")

    def _team_travel_snapshot(
        self,
        conn,
        team_id: Optional[int],
        kickoff: datetime,
        match_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not team_id:
            return {"team_id": None, "gaps": ["team_id missing"]}
        current_match_id = match_context.get("match_id")
        date_text = kickoff.date().isoformat()
        time_text = kickoff.strftime("%H:%M:%S")
        select_sql = """
            SELECT m.match_id, m.match_date, m.match_time, m.league_id, m.season_id,
                   l.name_en AS league_name_en, l.name_cn AS league_name_cn,
                   m.home_team_id, m.away_team_id, m.home_goals, m.away_goals,
                   m.venue, m.venue_city, m.neutral, m.status, m.source
            FROM matches m
            LEFT JOIN leagues l ON l.league_id = m.league_id
        """
        previous = conn.execute(
            select_sql
            + """
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
              AND (? IS NULL OR m.match_id != ?)
              AND m.home_goals IS NOT NULL
              AND m.away_goals IS NOT NULL
              AND (m.match_date < ? OR (m.match_date = ? AND COALESCE(m.match_time, '00:00:00') < ?))
            ORDER BY m.match_date DESC, COALESCE(m.match_time, '00:00:00') DESC
            LIMIT 1
            """,
            (team_id, team_id, current_match_id, current_match_id, date_text, date_text, time_text),
        ).fetchone()
        next_match = conn.execute(
            select_sql
            + """
            WHERE (m.home_team_id = ? OR m.away_team_id = ?)
              AND (? IS NULL OR m.match_id != ?)
              AND (m.match_date > ? OR (m.match_date = ? AND COALESCE(m.match_time, '23:59:59') > ?))
            ORDER BY
              CASE WHEN m.league_id = ? AND m.season_id = ? THEN 0 ELSE 1 END,
              m.match_date,
              COALESCE(m.match_time, '23:59:59')
            LIMIT 1
            """,
            (
                team_id,
                team_id,
                current_match_id,
                current_match_id,
                date_text,
                date_text,
                time_text,
                match_context.get("league_id"),
                match_context.get("season_id"),
            ),
        ).fetchone()
        previous_item = self._schedule_match_item(dict(previous), team_id) if previous else None
        next_item = self._schedule_match_item(dict(next_match), team_id) if next_match else None
        rest_hours = None
        if previous_item and previous_item.get("kickoff"):
            previous_dt = _safe_datetime(previous_item["kickoff"])
            if previous_dt:
                rest_hours = round((kickoff - previous_dt).total_seconds() / 3600, 1)
        venue_city_changed = None
        if previous_item and previous_item.get("venue_city") and match_context.get("venue_city"):
            venue_city_changed = self._normalize_name(previous_item.get("venue_city")) != self._normalize_name(match_context.get("venue_city"))
        return {
            "team_id": team_id,
            "previous_match": previous_item,
            "next_match": next_item,
            "rest_hours": rest_hours,
            "rest_days": round(rest_hours / 24, 1) if rest_hours is not None else None,
            "rest_band": self._rest_band(rest_hours),
            "quick_turnaround": rest_hours is not None and rest_hours < 96,
            "venue_city_changed": venue_city_changed,
            "gaps": [] if previous_item else ["previous finished match missing"],
        }

    def _schedule_match_item(self, row: Dict[str, Any], team_id: int) -> Dict[str, Any]:
        is_home = row.get("home_team_id") == team_id
        goals_for = row.get("home_goals") if is_home else row.get("away_goals")
        goals_against = row.get("away_goals") if is_home else row.get("home_goals")
        kickoff = self._match_kickoff_datetime(
            {"match_date": row.get("match_date"), "match_time": row.get("match_time")},
            row,
        )
        return {
            "match_id": row.get("match_id"),
            "kickoff": kickoff.isoformat(timespec="minutes") if kickoff else None,
            "league_name": row.get("league_name_cn") or row.get("league_name_en"),
            "is_home": is_home,
            "opponent_team_id": row.get("away_team_id") if is_home else row.get("home_team_id"),
            "goals_for": goals_for,
            "goals_against": goals_against,
            "venue": row.get("venue"),
            "venue_city": row.get("venue_city"),
            "neutral": bool(row.get("neutral")) if row.get("neutral") is not None else None,
            "status": row.get("status"),
            "source": row.get("source"),
        }

    def _rest_band(self, rest_hours: Optional[float]) -> Optional[str]:
        if rest_hours is None:
            return None
        if rest_hours < 72:
            return "very_short"
        if rest_hours < 96:
            return "short"
        if rest_hours < 168:
            return "normal"
        return "long"

    def _rest_delta(self, home: Dict[str, Any], away: Dict[str, Any]) -> Optional[float]:
        if home.get("rest_hours") is None or away.get("rest_hours") is None:
            return None
        return round(home["rest_hours"] - away["rest_hours"], 1)

    def _short_rest_side(self, home: Dict[str, Any], away: Dict[str, Any]) -> Optional[str]:
        home_short = home.get("quick_turnaround")
        away_short = away.get("quick_turnaround")
        if home_short and away_short:
            return "both"
        if home_short:
            return "home"
        if away_short:
            return "away"
        return None

    def _team_aliases(self, team: Dict[str, Any], display_name: Optional[str] = None) -> List[str]:
        aliases = []
        for key in (
            "name_en",
            "name_cn",
            "sporttery_name_en",
            "sporttery_name_cn",
            "oddsfe_name_en",
            "oddsfe_name_cn",
            "apifootball_name_en",
            "apifootball_name_cn",
            "fifa_code",
        ):
            value = team.get(key)
            if value:
                aliases.append(str(value))
        if display_name:
            aliases.append(str(display_name))
        normalized = []
        seen = set()
        for alias in aliases:
            cleaned = alias.strip()
            key = self._normalize_name(cleaned)
            if cleaned and key and key not in seen:
                normalized.append(cleaned)
                seen.add(key)
        return normalized

    def _normalize_name(self, value: Any) -> str:
        if value is None:
            return ""
        text = "".join(
            ch for ch in unicodedata.normalize("NFKD", str(value))
            if not unicodedata.combining(ch)
        )
        text = text.lower().replace("&", " and ")
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text).strip()

    def _team_major_tournament_snapshot(
        self,
        conn,
        team_id: Optional[int],
        before_date: str,
        aliases: List[str],
    ) -> Dict[str, Any]:
        if not team_id:
            return {"team_id": None, "aliases": aliases, "gaps": ["team_id missing"]}
        db_snapshot = self._db_major_tournament_snapshot(conn, team_id, before_date)
        json_snapshot = self._json_major_tournament_snapshot(team_id, before_date, aliases)
        return {
            "team_id": team_id,
            "aliases": aliases[:10],
            "db": db_snapshot,
            "history_json": json_snapshot,
        }

    def _db_major_tournament_snapshot(self, conn, team_id: int, before_date: str) -> Dict[str, Any]:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT m.match_id, m.match_date, m.match_time, m.round_stage, m.stage_type,
                       m.home_team_id, m.away_team_id, m.home_goals, m.away_goals,
                       l.league_id, l.league_code, l.name_en AS league_name_en,
                       l.name_cn AS league_name_cn, l.participant_type, l.is_international
                FROM matches m
                LEFT JOIN leagues l ON l.league_id = m.league_id
                WHERE (m.home_team_id = ? OR m.away_team_id = ?)
                  AND m.match_date < ?
                  AND m.home_goals IS NOT NULL
                  AND m.away_goals IS NOT NULL
                ORDER BY m.match_date DESC, COALESCE(m.match_time, '23:59:59') DESC
                LIMIT 800
                """,
                (team_id, team_id, before_date),
            )
        ]
        summary = {
            "source_rows_checked": len(rows),
            "major_matches": 0,
            "world_cup_matches": 0,
            "continental_major_matches": 0,
            "qualifier_matches": 0,
            "competitive_international_matches": 0,
            "knockout_matches": 0,
            "samples": [],
        }
        for row in rows:
            classification = self._classify_competition(row)
            if not classification.get("countable"):
                continue
            if classification.get("is_qualifier"):
                summary["qualifier_matches"] += 1
            if classification.get("competitive_international"):
                summary["competitive_international_matches"] += 1
            if classification.get("is_major"):
                summary["major_matches"] += 1
                if classification.get("family") == "world_cup":
                    summary["world_cup_matches"] += 1
                else:
                    summary["continental_major_matches"] += 1
                if self._is_knockout_stage(row):
                    summary["knockout_matches"] += 1
                if len(summary["samples"]) < 8:
                    summary["samples"].append(
                        {
                            "match_id": row.get("match_id"),
                            "match_date": row.get("match_date"),
                            "league_name": row.get("league_name_cn") or row.get("league_name_en"),
                            "family": classification.get("family"),
                            "stage": row.get("round_stage") or row.get("stage_type"),
                            "home_team_id": row.get("home_team_id"),
                            "away_team_id": row.get("away_team_id"),
                            "score": f"{row.get('home_goals')}-{row.get('away_goals')}",
                        }
                    )
        return summary

    def _json_major_tournament_snapshot(self, team_id: int, before_date: str, aliases: List[str]) -> Dict[str, Any]:
        files = self._history_candidate_files(team_id, aliases)
        summary = {
            "candidate_files": [path.name for path in files],
            "validated_records": 0,
            "major_matches": 0,
            "world_cup_matches": 0,
            "knockout_matches": 0,
            "samples": [],
            "warnings": [],
        }
        if not files:
            summary["warnings"].append("no candidate national_teams_history file")
            return summary
        alias_norms = {self._normalize_name(alias) for alias in aliases if len(self._normalize_name(alias)) >= 2}
        for path in files[:6]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                summary["warnings"].append(f"{path.name}: read failed: {exc}")
                continue
            if not isinstance(data, list):
                summary["warnings"].append(f"{path.name}: unexpected json shape")
                continue
            validated_in_file = 0
            for record in data:
                if not isinstance(record, dict):
                    continue
                home_name = self._normalize_name(record.get("match_hometeam_name"))
                away_name = self._normalize_name(record.get("match_awayteam_name"))
                if not self._json_record_matches_alias(home_name, away_name, alias_norms):
                    continue
                validated_in_file += 1
                match_date = str(record.get("match_date") or "")[:10]
                if match_date and match_date >= before_date:
                    continue
                classification = self._classify_competition(
                    {
                        "league_name_en": record.get("league_name"),
                        "league_name_cn": "",
                        "league_code": "",
                        "participant_type": "national",
                        "is_international": 1,
                    }
                )
                summary["validated_records"] += 1
                if not classification.get("is_major"):
                    continue
                summary["major_matches"] += 1
                if classification.get("family") == "world_cup":
                    summary["world_cup_matches"] += 1
                if self._is_knockout_stage(
                    {
                        "round_stage": record.get("match_round"),
                        "stage_type": record.get("stage_name"),
                    }
                ):
                    summary["knockout_matches"] += 1
                if len(summary["samples"]) < 8:
                    summary["samples"].append(
                        {
                            "match_id": record.get("match_id"),
                            "match_date": match_date,
                            "league_name": record.get("league_name"),
                            "stage": record.get("stage_name") or record.get("match_round"),
                            "home": record.get("match_hometeam_name"),
                            "away": record.get("match_awayteam_name"),
                            "score": f"{record.get('match_hometeam_score')}-{record.get('match_awayteam_score')}",
                            "file": path.name,
                        }
                    )
            if validated_in_file == 0:
                summary["warnings"].append(f"{path.name}: no team-name validated records; ignored as evidence")
        return summary

    def _history_candidate_files(self, team_id: int, aliases: List[str]) -> List[Path]:
        history_dir = Path(__file__).resolve().parents[3] / "national_teams_history"
        if not history_dir.exists():
            return []
        alias_norms = {self._normalize_name(alias) for alias in aliases if alias}
        candidates = []
        for path in history_dir.glob("*.json"):
            stem = path.stem
            stem_without_id = re.sub(r"^\d+_", "", stem).replace("_", " ")
            stem_norm = self._normalize_name(stem_without_id)
            starts_with_id = stem.startswith(f"{team_id}_")
            alias_hit = any(
                alias_norm and (
                    alias_norm == stem_norm
                    or alias_norm in stem_norm
                    or stem_norm in alias_norm
                )
                for alias_norm in alias_norms
            )
            if starts_with_id or alias_hit:
                candidates.append(path)
        return sorted(candidates, key=lambda path: (not path.stem.startswith(f"{team_id}_"), path.name))

    def _json_record_matches_alias(self, home_name: str, away_name: str, alias_norms: set) -> bool:
        for alias in alias_norms:
            if len(alias) < 2:
                continue
            if alias in (home_name, away_name):
                return True
            if len(alias) >= 4 and (alias in home_name or alias in away_name):
                return True
        return False

    def _classify_competition(self, row: Dict[str, Any]) -> Dict[str, Any]:
        text = self._normalize_name(
            " ".join(
                str(row.get(key) or "")
                for key in ("league_code", "league_name_en", "league_name_cn")
            )
        )
        participant_type = self._normalize_name(row.get("participant_type"))
        is_club = participant_type == "club"
        is_qualifier = any(term in text for term in ("qualifier", "qualification", "prelim", "预选", "资格"))
        if is_club or "club world cup" in text or "世俱杯" in text:
            return {"countable": False}
        family = None
        is_major = False
        if "world cup" in text or "世界杯" in text:
            family = "world_cup"
            is_major = not is_qualifier and not any(term in text for term in ("u17", "u20", "women", "女足"))
        elif "uefa european championship" in text or text == "euro" or "欧洲杯" in text:
            family = "euro"
            is_major = not is_qualifier and "u21" not in text and "u19" not in text and "u17" not in text
        elif "copa america" in text or "美洲杯" in text:
            family = "copa_america"
            is_major = not is_qualifier
        elif "africa cup" in text or "afcon" in text or "非洲杯" in text:
            family = "africa_cup"
            is_major = not is_qualifier and "u20" not in text and "u17" not in text
        elif "asian cup" in text or "亚洲杯" in text:
            family = "asian_cup"
            is_major = not is_qualifier and "u23" not in text and "u20" not in text and "u17" not in text
        elif "gold cup" in text or "金杯" in text:
            family = "gold_cup"
            is_major = not is_qualifier
        elif "nations league" in text or "欧国联" in text:
            family = "nations_league"
        competitive = bool(is_major or is_qualifier or family == "nations_league")
        return {
            "countable": competitive,
            "family": family,
            "is_major": is_major,
            "is_qualifier": is_qualifier,
            "competitive_international": competitive,
        }

    def _is_knockout_stage(self, row: Dict[str, Any]) -> bool:
        text = self._normalize_name(
            " ".join(str(row.get(key) or "") for key in ("round_stage", "stage_type", "stage", "match_round"))
        )
        if not text or "group" in text or "qualification" in text or "qualifier" in text:
            return False
        return any(
            term in text
            for term in (
                "final",
                "semi",
                "quarter",
                "round of 16",
                "round 16",
                "knockout",
                "third place",
                "三四名",
                "决赛",
                "半决赛",
                "四分之一",
                "八分之一",
            )
        )

    def _table_exists(self, conn, table: str) -> bool:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone()
        return row is not None

    def _table_columns(self, conn, table: str) -> set:
        try:
            return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
        except Exception:
            return set()

    def _select_existing_columns(self, conn, table: str, columns: List[str]) -> str:
        existing = self._table_columns(conn, table)
        parts = []
        for column in columns:
            if column in existing:
                parts.append(column)
            else:
                parts.append(f"NULL AS {column}")
        return ", ".join(parts)

    def _single_row(self, conn, sql: str, params: Tuple[Any, ...]) -> Optional[Dict[str, Any]]:
        if any(value is None for value in params):
            return None
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _load_team(self, conn, team_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if not team_id or not self._table_exists(conn, "teams"):
            return None
        select_cols = self._select_existing_columns(conn, "teams", [
            "team_id",
            "name_en",
            "name_cn",
            "sporttery_name_cn",
            "sporttery_name_en",
            "oddsfe_name_cn",
            "oddsfe_name_en",
            "country",
            "country_cn",
            "team_type",
            "fifa_code",
            "apifootball_name_cn",
            "apifootball_name_en",
            "apifootball_team_id",
        ])
        return self._single_row(
            conn,
            f"SELECT {select_cols} FROM teams WHERE team_id = ?",
            (team_id,),
        )

    def _load_match(self, conn, match_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not match_id or not self._table_exists(conn, "matches"):
            return None
        return self._single_row(
            conn,
            """
            SELECT match_id, match_date, match_time, league_id, season_id,
                   round_num, round_stage, stage_type, group_name,
                   home_team_id, away_team_id, venue, venue_city, neutral,
                   home_goals, away_goals, status, source, match_code
            FROM matches
            WHERE match_id = ?
            """,
            (match_id,),
        )

    def _load_league(self, conn, league_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if league_id is None or not self._table_exists(conn, "leagues"):
            return None
        select_cols = self._select_existing_columns(conn, "leagues", [
            "league_id",
            "league_code",
            "name_en",
            "name_cn",
            "competition_type",
            "participant_type",
            "format_type",
            "tier",
            "is_international",
            "oddsfe_tournament_id",
            "sporttery_name",
            "apifootball_id",
        ])
        return self._single_row(
            conn,
            f"SELECT {select_cols} FROM leagues WHERE league_id = ?",
            (league_id,),
        )

    def _load_season(self, conn, season_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if season_id is None or not self._table_exists(conn, "seasons"):
            return None
        return self._single_row(
            conn,
            """
            SELECT season_id, league_id, season_name, year, start_date, end_date, status
            FROM seasons
            WHERE season_id = ?
            """,
            (season_id,),
        )

    def _load_league_rule(self, conn, league_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if league_id is None or not self._table_exists(conn, "league_rules"):
            return None
        row = self._single_row(
            conn,
            """
            SELECT league_id, league_code, season, teams_count, matches_per_team,
                   format_type, points_for_win, draw_resolution, rules_json, updated_at
            FROM league_rules
            WHERE league_id = ?
            ORDER BY CASE WHEN season IS NULL THEN 1 ELSE 0 END, updated_at DESC
            LIMIT 1
            """,
            (league_id,),
        )
        if row and row.get("rules_json"):
            row["rules"] = _loads(row.get("rules_json"), {})
        return row

    def _related_lottery_matches(self, conn, job: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        if not self._table_exists(conn, "lottery_matches") or not job.get("match_date"):
            return []
        params: List[Any] = [job.get("match_date")]
        league_filter = ""
        if job.get("league_name"):
            league_filter = " AND league_name_cn = ?"
            params.append(job.get("league_name"))
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT lottery_match_id, match_id, league_name_cn, home_team_cn, away_team_cn,
                   match_date, match_time, beijing_time, sell_status
            FROM lottery_matches
            WHERE match_date = ?
            {league_filter}
            ORDER BY COALESCE(beijing_time, match_time), lottery_match_id
            LIMIT ?
            """,
            params,
        )
        return [dict(row) for row in rows]

    def _team_tournament_snapshot(
        self,
        conn,
        team_id: Optional[int],
        match_date: str,
        league_id: Optional[int],
        season_id: Optional[int],
    ) -> Dict[str, Any]:
        if not team_id:
            return {"team_id": None, "gaps": ["team_id missing"]}
        recent_form = self._team_form(conn, team_id, match_date, limit=6) if self._table_exists(conn, "matches") else {}
        return {
            "team_id": team_id,
            "current_competition": self._team_competition_form(conn, team_id, match_date, league_id, season_id),
            "future_competition_matches": self._future_team_matches(conn, team_id, match_date, league_id, season_id),
            "recent_national_form": recent_form.get("summary", {}),
            "recent_national_matches": recent_form.get("matches", []),
        }

    def _team_competition_form(
        self,
        conn,
        team_id: int,
        before_date: str,
        league_id: Optional[int],
        season_id: Optional[int],
        limit: int = 10,
    ) -> Dict[str, Any]:
        if league_id is None or season_id is None or not self._table_exists(conn, "matches"):
            return {"played": 0, "matches": [], "gaps": ["league_id or season_id missing"]}
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT match_id, match_date, home_team_id, away_team_id, home_goals, away_goals,
                       round_num, round_stage, group_name, status
                FROM matches
                WHERE league_id = ?
                  AND season_id = ?
                  AND match_date < ?
                  AND (home_team_id = ? OR away_team_id = ?)
                  AND home_goals IS NOT NULL
                  AND away_goals IS NOT NULL
                ORDER BY match_date DESC
                LIMIT ?
                """,
                (league_id, season_id, before_date, team_id, team_id, limit),
            )
        ]
        summary = {"played": 0, "wins": 0, "draws": 0, "losses": 0, "goals_for": 0, "goals_against": 0, "points": 0}
        matches = []
        for row in rows:
            is_home = row["home_team_id"] == team_id
            goals_for = row["home_goals"] if is_home else row["away_goals"]
            goals_against = row["away_goals"] if is_home else row["home_goals"]
            if goals_for > goals_against:
                outcome = "W"
                summary["wins"] += 1
                summary["points"] += 3
            elif goals_for == goals_against:
                outcome = "D"
                summary["draws"] += 1
                summary["points"] += 1
            else:
                outcome = "L"
                summary["losses"] += 1
            summary["played"] += 1
            summary["goals_for"] += goals_for
            summary["goals_against"] += goals_against
            matches.append(
                {
                    "match_id": row["match_id"],
                    "match_date": row["match_date"],
                    "is_home": is_home,
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "outcome": outcome,
                    "round_num": row.get("round_num"),
                    "round_stage": row.get("round_stage"),
                    "group_name": row.get("group_name"),
                }
            )
        summary["goal_diff"] = summary["goals_for"] - summary["goals_against"]
        return {**summary, "matches": matches}

    def _future_team_matches(
        self,
        conn,
        team_id: int,
        after_date: str,
        league_id: Optional[int],
        season_id: Optional[int],
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        if league_id is None or season_id is None or not self._table_exists(conn, "matches"):
            return []
        rows = conn.execute(
            """
            SELECT match_id, match_date, match_time, home_team_id, away_team_id,
                   round_num, round_stage, group_name, status
            FROM matches
            WHERE league_id = ?
              AND season_id = ?
              AND match_date > ?
              AND (home_team_id = ? OR away_team_id = ?)
            ORDER BY match_date, match_time
            LIMIT ?
            """,
            (league_id, season_id, after_date, team_id, team_id, limit),
        )
        return [dict(row) for row in rows]

    def _latest_fifa(self, conn, team_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if not team_id:
            return None
        return self._single_row(
            conn,
            """
            SELECT rank_date, team_id, rank, points, previous_rank, movement, confederation
            FROM fifa_rankings
            WHERE team_id = ?
            ORDER BY rank_date DESC
            LIMIT 1
            """,
            (team_id,),
        )

    def _latest_standing(self, conn, team_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if not team_id:
            return None
        return self._single_row(
            conn,
            """
            SELECT season_id, league_id, team_id, position, played, won, drawn, lost,
                   goals_for, goals_against, goal_diff, points, form, updated_at
            FROM standings
            WHERE team_id = ?
            ORDER BY updated_at DESC, season_id DESC
            LIMIT 1
            """,
            (team_id,),
        )

    def _team_form(self, conn, team_id: int, before_date: str, limit: int = 10) -> Dict[str, Any]:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT match_id, match_date, home_team_id, away_team_id, home_goals, away_goals,
                       result, status, league_id, season_id
                FROM matches
                WHERE match_date < ?
                  AND (home_team_id = ? OR away_team_id = ?)
                  AND home_goals IS NOT NULL
                  AND away_goals IS NOT NULL
                ORDER BY match_date DESC
                LIMIT ?
                """,
                (before_date, team_id, team_id, limit),
            )
        ]
        summary = {"wins": 0, "draws": 0, "losses": 0, "goals_for": 0, "goals_against": 0}
        normalized = []
        for row in rows:
            is_home = row["home_team_id"] == team_id
            goals_for = row["home_goals"] if is_home else row["away_goals"]
            goals_against = row["away_goals"] if is_home else row["home_goals"]
            if goals_for > goals_against:
                outcome = "W"
                summary["wins"] += 1
            elif goals_for == goals_against:
                outcome = "D"
                summary["draws"] += 1
            else:
                outcome = "L"
                summary["losses"] += 1
            summary["goals_for"] += goals_for
            summary["goals_against"] += goals_against
            normalized.append(
                {
                    "match_id": row["match_id"],
                    "match_date": row["match_date"],
                    "is_home": is_home,
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "outcome": outcome,
                    "league_id": row.get("league_id"),
                    "season_id": row.get("season_id"),
                }
            )
        played = len(normalized)
        summary["played"] = played
        summary["points"] = summary["wins"] * 3 + summary["draws"]
        summary["points_per_match"] = round(summary["points"] / played, 2) if played else None
        return {"team_id": team_id, "summary": summary, "matches": normalized}

    def _make_job_id(self, payload: IntelligenceJobCreate) -> str:
        if payload.lottery_match_id:
            return "lottery:" + payload.lottery_match_id
        if payload.match_id is not None:
            return "match:" + str(payload.match_id)
        raw = "|".join(
            [
                payload.match_date or "",
                payload.league_name or "",
                payload.home_team or "",
                payload.away_team or "",
            ]
        )
        if raw.strip("|"):
            return "manual:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return "manual:" + uuid.uuid4().hex

    def _ensure_requirements(self, conn, job_id: str, view: str) -> None:
        for tmpl in requirement_templates(view):
            requirement_id = f"{job_id}:{tmpl.key}"
            conn.execute(
                """
                INSERT INTO intelligence_requirements (
                    requirement_id, job_id, key, category, required, status,
                    preferred_sources, fallback_policy, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, key) DO UPDATE SET
                    category=excluded.category,
                    required=excluded.required,
                    preferred_sources=excluded.preferred_sources,
                    fallback_policy=excluded.fallback_policy,
                    description=excluded.description,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    requirement_id,
                    job_id,
                    tmpl.key,
                    tmpl.category,
                    1 if tmpl.required else 0,
                    RequirementStatus.missing.value,
                    _json(tmpl.preferred_sources),
                    tmpl.fallback_policy,
                    tmpl.description,
                ),
            )

    def _existing_job_ids(self) -> set:
        with self._connect() as conn:
            return {row["job_id"] for row in conn.execute("SELECT job_id FROM intelligence_jobs")}

    def _load_lottery_matches(self, conn, match_date: str) -> Iterable[Dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT lottery_match_id, match_id, match_date, match_time, beijing_time,
                   league_name_cn, home_team_cn, away_team_cn, home_team_id, away_team_id
            FROM lottery_matches
            WHERE match_date = ?
            ORDER BY COALESCE(beijing_time, match_time), lottery_match_id
            """,
            (match_date,),
        )
        return [dict(row) for row in rows]

    def _load_finished_lottery_matches(
        self,
        start_date: str,
        end_date: str,
        play_type: str = "spf",
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT
                       lm.lottery_match_id, lm.match_id, lm.match_date, lm.match_time, lm.beijing_time,
                       lm.league_name_cn, lm.home_team_cn, lm.away_team_cn,
                       lm.home_team_id, lm.away_team_id,
                       CASE WHEN lr.lottery_match_id IS NOT NULL THEN 1 ELSE 0 END as has_result,
                       CASE WHEN lv.lottery_match_id IS NOT NULL THEN 1 ELSE 0 END as has_validation
                FROM lottery_matches lm
                LEFT JOIN lottery_results lr ON lr.lottery_match_id = lm.lottery_match_id
                LEFT JOIN lottery_validation lv
                  ON lv.lottery_match_id = lm.lottery_match_id
                 AND lv.play_type = ?
                WHERE lm.match_date BETWEEN ? AND ?
                  AND (lr.lottery_match_id IS NOT NULL OR lv.lottery_match_id IS NOT NULL)
                ORDER BY lm.match_date, COALESCE(lm.beijing_time, lm.match_time), lm.lottery_match_id
                LIMIT ?
                """,
                (play_type, start_date, end_date, limit),
            )
            return [dict(row) for row in rows]

    def _summarize_requirements(self, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        required = [r for r in requirements if r.get("required")]
        collected_required = [r for r in required if r.get("status") == "collected"]
        fallback_required = [r for r in required if r.get("status") == "fallback_used"]
        missing_required = [r["key"] for r in required if r.get("status") not in ("collected", "fallback_used")]
        completeness = round(((len(collected_required) + len(fallback_required)) / len(required)) * 100, 1) if required else 100.0
        strict_completeness = round((len(collected_required) / len(required)) * 100, 1) if required else 100.0
        confidences = [float(r["confidence"]) for r in required if r.get("confidence") is not None]
        average_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
        return {
            "required_total": len(required),
            "required_collected": len(collected_required),
            "required_fallback": len(fallback_required),
            "required_missing_count": len(missing_required),
            "missing_required": missing_required,
            "completeness": completeness,
            "strict_completeness": strict_completeness,
            "average_confidence": average_confidence,
        }

    def _update_job_status(self, conn, job_id: str) -> None:
        reqs = [dict(row) for row in conn.execute("SELECT * FROM intelligence_requirements WHERE job_id = ?", (job_id,))]
        summary = self._summarize_requirements(reqs)
        status = JobStatus.ready_to_analyze.value if not summary["missing_required"] else JobStatus.partial.value
        conn.execute(
            "UPDATE intelligence_jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
            (status, job_id),
        )

    def _next_actions(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        actions = []
        for req in requirements:
            if req.get("status") in ("collected", "fallback_used"):
                continue
            actions.append(
                {
                    "requirement_key": req["key"],
                    "category": req["category"],
                    "required": bool(req["required"]),
                    "try_sources": req.get("preferred_sources", []),
                    "fallback_policy": req.get("fallback_policy"),
                }
            )
        return actions
