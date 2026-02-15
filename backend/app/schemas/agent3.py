from pydantic import BaseModel, Field

from app.schemas.agent2 import Agent2ChatResponse


class Agent3ScoreDomainRequest(BaseModel):
    report_name: str
    agent2_result: Agent2ChatResponse


class DomainScoreResult(BaseModel):
    report_name: str
    domain: str
    domain_score: float
    threshold: float
    passes_threshold: bool
    risk_level: str
    coverage_score: float
    best_practice_match_ratio: float
    risk_indicator_match_ratio: float
    missing_area_ratio: float
    loops_run: int
    matched_best_practices: list[str] = Field(default_factory=list)
    matched_risk_indicators: list[str] = Field(default_factory=list)
    updated_at: str


class Agent3FinalReport(BaseModel):
    report_name: str
    generated_at: str
    total_domains_scored: int
    aggregate_score: float
    average_threshold: float
    domains_meeting_threshold: int
    domains_below_threshold: int
    overall_status: str
    domain_results: list[DomainScoreResult] = Field(default_factory=list)
