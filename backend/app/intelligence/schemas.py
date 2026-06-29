from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    pending = "pending"
    collecting = "collecting"
    partial = "partial"
    ready_to_analyze = "ready_to_analyze"
    analyzing = "analyzing"
    analyzed = "analyzed"
    validated = "validated"
    failed = "failed"


class RequirementStatus(str, Enum):
    missing = "missing"
    collecting = "collecting"
    collected = "collected"
    fallback_used = "fallback_used"
    failed = "failed"
    stale = "stale"


class CompetitionType(str, Enum):
    world_cup = "world_cup"
    national_team = "national_team"
    league = "league"
    cup = "cup"
    unknown = "unknown"


class AnalysisView(str, Enum):
    world_cup = "world_cup"
    national_team = "national_team"
    league = "league"
    cup = "cup"
    generic = "generic"


class RequirementTemplate(BaseModel):
    key: str
    category: str
    required: bool = True
    preferred_sources: List[str] = Field(default_factory=list)
    fallback_policy: str = "mark_missing"
    description: str = ""


class IntelligenceJobCreate(BaseModel):
    match_id: Optional[str] = None
    lottery_match_id: Optional[str] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    match_date: Optional[str] = None
    match_time: Optional[str] = None
    league_name: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    source: str = "manual"
    competition_type: Optional[CompetitionType] = None
    analysis_view: Optional[AnalysisView] = None
    priority: int = 5

    @field_validator("match_id", mode="before")
    @classmethod
    def coerce_match_id(cls, value):
        if value is None:
            return None
        return str(value)


class ArtifactCreate(BaseModel):
    requirement_key: str
    source: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5
    status: RequirementStatus = RequirementStatus.collected


class ReviewCreate(BaseModel):
    result: Dict[str, Any] = Field(default_factory=dict)
    attribution: Dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"


class JobListResponse(BaseModel):
    data: List[Dict[str, Any]]
    total: int


class GenerateJobsResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    jobs: List[Dict[str, Any]]


class PackageResponse(BaseModel):
    job_id: str
    completeness: float
    strict_completeness: float = 0
    missing_required: List[str]
    package: Dict[str, Any]
