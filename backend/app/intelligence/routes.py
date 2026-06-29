from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from .schemas import (
    ArtifactCreate,
    GenerateJobsResponse,
    IntelligenceJobCreate,
    JobListResponse,
    PackageResponse,
    ReviewCreate,
)
from .service import IntelligenceService, requirement_templates

router = APIRouter(prefix="/api/v1/intelligence", tags=["Match Intelligence"])


def _service() -> IntelligenceService:
    return IntelligenceService()


def _run_logged_task(
    date: Optional[str],
    include_external: bool,
    collectors: Optional[List[str]],
    network: bool,
    force: bool,
    trigger_source: str,
) -> None:
    IntelligenceService().run_daily_logged(
        match_date=date,
        include_external=include_external,
        collectors=collectors,
        network=network,
        force=force,
        trigger_source=trigger_source,
    )


def _backfill_finished_task(
    start_date: Optional[str],
    end_date: Optional[str],
    include_external: bool,
    collectors: Optional[List[str]],
    network: bool,
    force: bool,
    play_type: str,
    limit: int,
    trigger_source: str,
) -> None:
    IntelligenceService().backfill_finished_logged(
        start_date=start_date,
        end_date=end_date,
        include_external=include_external,
        collectors=collectors,
        network=network,
        force=force,
        play_type=play_type,
        limit=limit,
        trigger_source=trigger_source,
    )


def _fill_gaps_task(
    start_date: Optional[str],
    end_date: Optional[str],
    collectors: Optional[List[str]],
    network: bool,
    force: bool,
    include_optional: bool,
    include_builtin: bool,
    limit: int,
    trigger_source: str,
) -> None:
    IntelligenceService().fill_gaps_logged(
        start_date=start_date,
        end_date=end_date,
        collectors=collectors,
        network=network,
        force=force,
        include_optional=include_optional,
        include_builtin=include_builtin,
        limit=limit,
        trigger_source=trigger_source,
    )


@router.get("/health")
async def health():
    return {"status": "ok", "module": "match_intelligence"}


@router.get("/source-health")
async def source_health():
    """Return source health status mapped to intelligence requirement keys."""
    from .external_collectors import _source_health_map, _source_health_detail, _collectors_for_gaps
    from .source_channels import channels_for_requirement
    import sqlite3
    from pathlib import Path

    db_path = Path(__file__).resolve().parents[3] / "data" / "football_v2.db"
    if not db_path.exists():
        return {"sources": {}, "requirements": {}}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        health_map = _source_health_map(conn)
        health_detail = _source_health_detail(conn)
    finally:
        conn.close()

    name_to_source = {
        "news_aggregator": "zhibo8",
        "apifootball_match_detail": "apifootball",
        "api_sports_injuries": "api_sports",
        "bifen188_lineups": "bifen188",
        "weather_fetcher": "wttr_in",
        "fifa_ranking_fetcher": "fifa_ranking",
    }

    # Map requirement keys to their channel health
    req_health = {}
    for key in ["injuries_suspensions", "team_news", "expected_lineup", "weather",
                "base_info", "odds_1x2", "market_movement", "recent_form",
                "fifa_ranking", "tournament_context"]:
        channels = channels_for_requirement(key, enabled_only=True)
        req_health[key] = []
        for ch in channels:
            source_name = name_to_source.get(ch.get("name"))
            detail = health_detail.get(source_name, {}) if source_name else {}
            req_health[key].append({
                "channel": ch.get("name"),
                "kind": ch.get("kind"),
                "priority": ch.get("priority"),
                "health_source": source_name,
                "health_status": detail.get("status", "unknown"),
                "last_success": detail.get("last_success"),
                "last_failure": detail.get("last_failure"),
                "success_rate": detail.get("success_rate"),
                "failure_count": detail.get("failure_count"),
                "next_action": detail.get("next_action", "none"),
            })

    return {"sources": health_map, "sources_detail": health_detail, "requirements": req_health}


@router.get("/requirements/{analysis_view}")
async def get_requirement_templates(analysis_view: str):
    return {"analysis_view": analysis_view, "data": [item.model_dump() for item in requirement_templates(analysis_view)]}


@router.post("/jobs")
async def create_job(payload: IntelligenceJobCreate):
    try:
        return _service().create_job(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/generate", response_model=GenerateJobsResponse)
async def generate_jobs(
    date: Optional[str] = Query(None, description="Target date YYYY-MM-DD; defaults to today."),
    source: str = Query("lottery", description="Initial source: lottery."),
):
    try:
        return _service().generate_jobs_for_date(match_date=date, source=source)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run-daily")
async def run_daily(
    date: Optional[str] = Query(None, description="Target date YYYY-MM-DD; defaults to today."),
    include_external: bool = Query(False, description="Also run external collectors after builtin collection."),
    collectors: Optional[List[str]] = Query(None, description="Optional external collector keys."),
    network: bool = Query(True, description="Allow network calls when include_external=true."),
    force: bool = Query(False, description="Recollect even if artifacts already exist."),
):
    try:
        return _service().run_daily(
            match_date=date,
            include_external=include_external,
            collectors=collectors,
            network=network,
            force=force,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/runs")
async def start_run(
    background_tasks: BackgroundTasks,
    date: Optional[str] = Query(None, description="Target date YYYY-MM-DD; defaults to today."),
    include_external: bool = Query(False, description="Also run external collectors after builtin collection."),
    collectors: Optional[List[str]] = Query(None, description="Optional external collector keys."),
    network: bool = Query(True, description="Allow network calls when include_external=true."),
    force: bool = Query(False, description="Recollect even if artifacts already exist."),
    background: bool = Query(True, description="Run in FastAPI background task."),
):
    if background:
        background_tasks.add_task(
            _run_logged_task,
            date,
            include_external,
            collectors,
            network,
            force,
            "manual_background",
        )
        return {"status": "scheduled", "background": True}
    try:
        return _service().run_daily_logged(
            match_date=date,
            include_external=include_external,
            collectors=collectors,
            network=network,
            force=force,
            trigger_source="manual",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/backfill-finished")
async def backfill_finished(
    background_tasks: BackgroundTasks,
    start_date: Optional[str] = Query(None, description="Backfill start date YYYY-MM-DD; defaults to 60 days before end_date."),
    end_date: Optional[str] = Query(None, description="Backfill end date YYYY-MM-DD; defaults to today."),
    include_external: bool = Query(True, description="Also run local/source fallback collectors after builtin collection."),
    collectors: Optional[List[str]] = Query(
        None,
        description="Collector keys; defaults to team_news, injuries_suspensions, expected_lineup.",
    ),
    network: bool = Query(False, description="Allow network calls. Default false for historical backfills."),
    force: bool = Query(False, description="Recollect even if artifacts already exist."),
    play_type: str = Query("spf", description="Play type to auto-review, default SPF."),
    limit: int = Query(200, ge=1, le=1000, description="Maximum finished lottery matches to backfill."),
    background: bool = Query(False, description="Run in FastAPI background task."),
):
    if background:
        background_tasks.add_task(
            _backfill_finished_task,
            start_date,
            end_date,
            include_external,
            collectors,
            network,
            force,
            play_type,
            limit,
            "manual_backfill_background",
        )
        return {"status": "scheduled", "background": True}
    try:
        return _service().backfill_finished_logged(
            start_date=start_date,
            end_date=end_date,
            include_external=include_external,
            collectors=collectors,
            network=network,
            force=force,
            play_type=play_type,
            limit=limit,
            trigger_source="manual_backfill",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/gaps/plan")
async def plan_gap_fill(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD; defaults to yesterday."),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD; defaults to tomorrow."),
    collectors: Optional[List[str]] = Query(
        None,
        description="External collector keys: weather, team_news, injuries_suspensions, expected_lineup.",
    ),
    include_optional: bool = Query(True, description="Include optional gaps like weather/news/lineup."),
    include_builtin: bool = Query(True, description="Also include builtin gaps such as odds/context/data_quality."),
    force: bool = Query(False, description="Plan retries even when retry windows have not elapsed."),
    limit: int = Query(20, ge=1, le=200),
):
    try:
        return _service().plan_gap_fill(
            start_date=start_date,
            end_date=end_date,
            collectors=collectors,
            include_optional=include_optional,
            include_builtin=include_builtin,
            force=force,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/gaps/unified")
async def unified_gap_report(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD; defaults to yesterday."),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD; defaults to tomorrow."),
    limit: int = Query(20, ge=1, le=200),
):
    """Unified gap objects matching P0-3 spec: severity, candidate/selected/skipped channels, next_action."""
    try:
        return _service().unified_gap_report(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/gaps/fill")
async def fill_gaps(
    background_tasks: BackgroundTasks,
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD; defaults to yesterday."),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD; defaults to tomorrow."),
    collectors: Optional[List[str]] = Query(
        None,
        description="External collector keys: weather, team_news, injuries_suspensions, expected_lineup.",
    ),
    network: bool = Query(True, description="Allow network collectors."),
    force: bool = Query(False, description="Retry fallback/failed gaps immediately."),
    include_optional: bool = Query(True, description="Include optional gaps like weather/news/lineup."),
    include_builtin: bool = Query(True, description="Also collect builtin gaps before external collectors."),
    limit: int = Query(8, ge=1, le=50),
    background: bool = Query(True, description="Run in FastAPI background task."),
):
    if background:
        background_tasks.add_task(
            _fill_gaps_task,
            start_date,
            end_date,
            collectors,
            network,
            force,
            include_optional,
            include_builtin,
            limit,
            "manual_gap_fill_background",
        )
        return {"status": "scheduled", "background": True}
    try:
        return _service().fill_gaps_logged(
            start_date=start_date,
            end_date=end_date,
            collectors=collectors,
            network=network,
            force=force,
            include_optional=include_optional,
            include_builtin=include_builtin,
            limit=limit,
            trigger_source="manual_gap_fill",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs")
async def list_runs(limit: int = Query(50, ge=1, le=200)):
    try:
        return _service().list_runs(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    try:
        return _service().get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/reviews")
async def list_reviews(
    job_id: Optional[str] = Query(None, description="Filter by intelligence job id."),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        return _service().list_reviews(job_id=job_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/reviews/auto")
async def auto_review_for_date(
    date: Optional[str] = Query(None, description="Target match date YYYY-MM-DD."),
    play_type: str = Query("spf", description="Play type to review, default SPF."),
):
    try:
        return _service().auto_review_for_date(match_date=date, play_type=play_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/reviews/{review_id}")
async def get_review(review_id: str):
    try:
        return _service().get_review(review_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="review not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/training-samples")
async def list_training_samples(
    limit: int = Query(200, ge=1, le=500),
    only_settled: bool = Query(True, description="Only include reviews with actual results."),
    attribution: Optional[str] = Query(None, description="Filter by attribution level."),
    include_raw_package: bool = Query(False, description="Include the raw intelligence package JSON."),
):
    try:
        return _service().list_training_samples(
            limit=limit,
            only_settled=only_settled,
            attribution=attribution,
            include_raw_package=include_raw_package,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/training-summary")
async def training_summary(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD."),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD."),
    limit: int = Query(10000, ge=1, le=50000),
):
    try:
        return _service().training_summary(start_date=start_date, end_date=end_date, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/training-samples/export")
async def export_training_samples(
    limit: int = Query(10000, ge=1, le=50000),
    only_settled: bool = Query(True, description="Only include reviews with actual results."),
    attribution: Optional[str] = Query(None, description="Filter by attribution level."),
    include_raw_package: bool = Query(False, description="Include the raw intelligence package JSON."),
):
    try:
        return _service().export_training_samples(
            limit=limit,
            only_settled=only_settled,
            attribution=attribution,
            include_raw_package=include_raw_package,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    date: Optional[str] = Query(None, description="Filter by match date YYYY-MM-DD."),
    status: Optional[str] = Query(None, description="Filter by intelligence job status."),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        return _service().list_jobs(match_date=date, status=status, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    try:
        return _service().get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/artifacts")
async def add_artifact(job_id: str, payload: ArtifactCreate):
    try:
        return _service().add_artifact(job_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/reviews")
async def add_review(job_id: str, payload: ReviewCreate):
    try:
        return _service().add_review(job_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/reviews/auto")
async def auto_review_job(
    job_id: str,
    play_type: str = Query("spf", description="Play type to review, default SPF."),
):
    try:
        return _service().auto_review_job(job_id, play_type=play_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/link-match")
async def link_match(job_id: str):
    try:
        return _service().link_match(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/collect/builtin")
async def collect_builtin(
    job_id: str,
    force: bool = Query(False, description="Recollect even if a requirement already has an artifact."),
):
    try:
        return _service().collect_builtin(job_id, force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/collect/external")
async def collect_external(
    job_id: str,
    collectors: Optional[List[str]] = Query(
        None,
        description="Collector keys: weather, team_news, injuries_suspensions, expected_lineup.",
    ),
    network: bool = Query(True, description="Allow network calls to external sources."),
    force: bool = Query(False, description="Recollect even if a requirement already has an artifact."),
):
    try:
        return _service().collect_external(job_id, collectors=collectors, network=network, force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/package")
async def get_package(job_id: str):
    try:
        return _service().get_package(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/package", response_model=PackageResponse)
async def build_package(job_id: str):
    try:
        return _service().build_package(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
