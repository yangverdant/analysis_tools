from fastapi import APIRouter, HTTPException, Query

from .service import WorldCupContextService


router = APIRouter(prefix="/api/v1/world-cup/2026", tags=["World Cup 2026"])


def _service() -> WorldCupContextService:
    return WorldCupContextService()


@router.get("/health")
async def health():
    return {"status": "ok", "module": "world_cup_2026"}


@router.get("/context")
async def get_context(
    live: bool = Query(True, description="Use live football-data.org when available."),
    include_matches: bool = Query(False, description="Include all normalized fixtures/results."),
):
    try:
        return _service().get_context(live=live, include_matches=include_matches)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/rules")
async def get_rules():
    return _service().get_rules()


@router.get("/groups")
async def get_groups(live: bool = Query(True, description="Use live football-data.org when available.")):
    try:
        return _service().get_groups(live=live)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/knockout")
async def get_knockout(live: bool = Query(True, description="Use live football-data.org when available.")):
    try:
        return _service().get_knockout(live=live)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/matches")
async def get_matches(live: bool = Query(True, description="Use live football-data.org when available.")):
    try:
        context = _service().get_context(live=live, include_matches=True)
        return {"data_status": context["data_status"], "matches_summary": context["matches_summary"], "matches": context["matches"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/match/{match_id}/context")
async def get_match_context(match_id: str, live: bool = Query(True, description="Use live football-data.org when available.")):
    try:
        return _service().get_match_context(match_id=match_id, live=live)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="World Cup match not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/match-context")
async def get_match_context_by_teams(
    home_team: str = Query(..., description="Home team name, Chinese or English."),
    away_team: str = Query(..., description="Away team name, Chinese or English."),
    match_date: str = Query(None, description="Optional match date. Used as a soft ranking signal."),
    live: bool = Query(True, description="Use live football-data.org when available."),
):
    try:
        return _service().get_match_context_by_teams(
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            live=live,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="World Cup match not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
