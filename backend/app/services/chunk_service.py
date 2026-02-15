from dataclasses import dataclass

from app.services.pdf_service import PDFPageText


@dataclass(slots=True)
class TextChunk:
    chunk_id: int
    text: str
    page_number: int | None = None


class TextChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        if chunk_overlap >= chunk_size:
            raise ValueError('chunk_overlap must be smaller than chunk_size')

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> list[TextChunk]:
        words = text.split()
        if not words:
            return []

        chunks: list[TextChunk] = []
        step = self.chunk_size - self.chunk_overlap

        idx = 0
        chunk_id = 0
        while idx < len(words):
            window = words[idx : idx + self.chunk_size]
            chunks.append(TextChunk(chunk_id=chunk_id, text=' '.join(window)))
            idx += step
            chunk_id += 1

        return chunks

    def chunk_page_texts(self, pages: list[PDFPageText]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        chunk_id = 0
        step = self.chunk_size - self.chunk_overlap

        for page in pages:
            words = page.text.split()
            if not words:
                continue

            idx = 0
            while idx < len(words):
                window = words[idx : idx + self.chunk_size]
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        text=' '.join(window),
                        page_number=page.page_number,
                    )
                )
                idx += step
                chunk_id += 1

        return chunks
