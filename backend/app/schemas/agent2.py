from pydantic import BaseModel, Field


class DomainOption(BaseModel):
    key: str
    label: str


class Agent2DomainListResponse(BaseModel):
    domains: list[DomainOption]


class Agent2ChatRequest(BaseModel):
    domain: str
    top_k: int = Field(default=5, ge=1, le=20)
    report_name: str | None = None
    max_loops: int | None = Field(default=None, ge=1, le=6)


class RetrievedChunk(BaseModel):
    vector_id: int
    score: float
    text_preview: str


class StructuredAnswer(BaseModel):
    best_practices_found: list[str] = Field(default_factory=list)
    risk_indicators_found: list[str] = Field(default_factory=list)
    coverage_complete: bool = False
    missing_areas: list[str] = Field(default_factory=list)
    summary: str = ''


class Agent2LoopMessage(BaseModel):
    loop_number: int
    control_query: str
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    llm_answer: StructuredAnswer


class Agent2ChatResponse(BaseModel):
    domain: str
    loops_run: int
    coverage_complete: bool
    final_coverage_score: float
    threshold: float
    conversation: list[Agent2LoopMessage] = Field(default_factory=list)
