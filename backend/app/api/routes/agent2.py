from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.agent2.pipeline import Agent2RagReasoningPipeline
from app.core.config import get_settings
from app.core.security import AuthenticatedUser, require_hardcoded_user
from app.schemas.agent2 import Agent2ChatRequest, Agent2ChatResponse, Agent2DomainListResponse, DomainOption
from app.services.embedding_service import EmbeddingService
from app.services.groq_service import GroqService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.vector_store_service import FaissVectorStore

router = APIRouter(prefix='/agent2', tags=['Agent 2 - RAG + LLM Reasoning'])


@lru_cache
def get_knowledge_base_service() -> KnowledgeBaseService:
    settings = get_settings()
    return KnowledgeBaseService(knowledge_base_path=settings.knowledge_base_path)


@lru_cache
def get_agent2_pipeline() -> Agent2RagReasoningPipeline:
    settings = get_settings()
    if not settings.groq_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='GROQ_API_KEY is not configured in backend/.env',
        )

    return Agent2RagReasoningPipeline(
        knowledge_base=KnowledgeBaseService(knowledge_base_path=settings.knowledge_base_path),
        embedding_service=EmbeddingService(model_name=settings.bge_model_name),
        vector_store=FaissVectorStore(
            index_path=settings.faiss_index_path,
            metadata_path=settings.faiss_metadata_path,
        ),
        llm_service=GroqService(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout_seconds=settings.groq_timeout_seconds,
            max_retries=settings.groq_max_retries,
            requests_per_minute=settings.groq_requests_per_minute,
        ),
        max_loops=settings.agent2_max_loops,
    )


@router.get('/domains', response_model=Agent2DomainListResponse)
def list_domains(
    user: AuthenticatedUser = Depends(require_hardcoded_user),
    kb_service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> Agent2DomainListResponse:
    domains = kb_service.list_domains()
    return Agent2DomainListResponse(
        domains=[
            DomainOption(
                key=domain,
                label=domain.replace('_', ' ').title(),
            )
            for domain in domains
        ]
    )


@router.post('/chat', response_model=Agent2ChatResponse)
def run_agent2_chat(
    payload: Agent2ChatRequest,
    user: AuthenticatedUser = Depends(require_hardcoded_user),
    pipeline: Agent2RagReasoningPipeline = Depends(get_agent2_pipeline),
) -> Agent2ChatResponse:
    try:
        return pipeline.run(
            user_id=user.username,
            domain=payload.domain,
            top_k=payload.top_k,
            report_name=payload.report_name,
            max_loops_override=payload.max_loops,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Agent 2 execution failed: {exc}',
        ) from exc
