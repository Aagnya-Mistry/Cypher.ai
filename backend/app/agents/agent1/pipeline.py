from app.schemas.agent1 import EmbeddingPreview, ProcessDocumentResponse
from app.services.chunk_service import TextChunk, TextChunker
from app.services.embedding_service import EmbeddingService
from app.services.pdf_service import PDFExtractionError, extract_page_texts_from_pdf
from app.services.vector_store_service import FaissVectorStore


class Agent1DocumentProcessingPipeline:
    def __init__(
        self,
        chunker: TextChunker,
        embedding_service: EmbeddingService,
        vector_store: FaissVectorStore,
    ):
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def process_document(self, report_name: str, pdf_bytes: bytes, user_id: str) -> ProcessDocumentResponse:
        try:
            pages, total_pages = extract_page_texts_from_pdf(pdf_bytes)
        except PDFExtractionError as exc:
            raise ValueError(str(exc)) from exc

        pages_with_text = len([page for page in pages if page.text.strip()])
        if pages_with_text == 0:
            raise ValueError('No text could be extracted from the PDF.')

        chunks = self.chunker.chunk_page_texts(pages)
        if not chunks:
            raise ValueError('No chunks were generated from the extracted text.')

        embeddings = self.embedding_service.embed_texts([chunk.text for chunk in chunks])

        metadata = [
            {
                'user_id': user_id,
                'report_name': report_name,
                'chunk_id': chunk.chunk_id,
                'page_number': chunk.page_number,
                'text': chunk.text,
            }
            for chunk in chunks
        ]
        add_result = self.vector_store.add_embeddings(embeddings, metadata)

        return ProcessDocumentResponse(
            report_name=report_name,
            total_pages=total_pages,
            pages_with_text=pages_with_text,
            total_chunks=len(chunks),
            embedding_dimension=int(embeddings.shape[1]),
            stored_vector_count=add_result.total_vectors,
            embedding_preview=self._build_preview(chunks, embeddings),
        )

    def _build_preview(self, chunks: list[TextChunk], embeddings) -> list[EmbeddingPreview]:
        preview: list[EmbeddingPreview] = []
        max_preview = min(3, len(chunks))

        for idx in range(max_preview):
            chunk = chunks[idx]
            preview.append(
                EmbeddingPreview(
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    text_preview=chunk.text[:180],
                    vector=embeddings[idx].tolist(),
                )
            )

        return preview
