from functools import lru_cache

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.agents.agent1.pipeline import Agent1DocumentProcessingPipeline
from app.core.config import get_settings
from app.core.security import AuthenticatedUser, require_hardcoded_user
from app.schemas.agent1 import ProcessDocumentResponse
from app.services.chunk_service import TextChunker
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import FaissVectorStore

router = APIRouter(prefix='/agent1', tags=['Agent 1 - Document Processing'])


@lru_cache
def get_agent1_pipeline() -> Agent1DocumentProcessingPipeline:
    settings = get_settings()

    chunker = TextChunker(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    embedding_service = EmbeddingService(model_name=settings.bge_model_name)
    vector_store = FaissVectorStore(
        index_path=settings.faiss_index_path,
        metadata_path=settings.faiss_metadata_path,
    )

    return Agent1DocumentProcessingPipeline(
        chunker=chunker,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )


@router.post('/process', response_model=ProcessDocumentResponse)
async def process_document(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(require_hardcoded_user),
    pipeline: Agent1DocumentProcessingPipeline = Depends(get_agent1_pipeline),
) -> ProcessDocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Missing file name')

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only PDF files are supported')

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded PDF is empty')

    try:
        return pipeline.process_document(
            report_name=file.filename,
            pdf_bytes=pdf_bytes,
            user_id=user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Processing failed: {exc}',
        ) from exc
