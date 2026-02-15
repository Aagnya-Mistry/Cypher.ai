from pydantic import BaseModel, Field


class EmbeddingPreview(BaseModel):
    chunk_id: int
    page_number: int | None = None
    text_preview: str
    vector: list[float]


class ProcessDocumentResponse(BaseModel):
    report_name: str
    total_pages: int
    pages_with_text: int
    total_chunks: int
    embedding_dimension: int
    stored_vector_count: int
    embedding_preview: list[EmbeddingPreview] = Field(default_factory=list)
