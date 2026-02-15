from io import BytesIO
from dataclasses import dataclass

from pypdf import PdfReader


class PDFExtractionError(Exception):
    pass


@dataclass(slots=True)
class PDFPageText:
    page_number: int
    text: str


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    pages, total_pages = extract_page_texts_from_pdf(pdf_bytes)
    combined_text = '\n'.join(page.text for page in pages).strip()
    return combined_text, total_pages


def extract_page_texts_from_pdf(pdf_bytes: bytes) -> tuple[list[PDFPageText], int]:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as exc:
        raise PDFExtractionError('Could not parse PDF document.') from exc

    page_texts: list[PDFPageText] = []
    for page_index, page in enumerate(reader.pages):
        page_text = (page.extract_text() or '').strip()
        page_texts.append(PDFPageText(page_number=page_index + 1, text=page_text))

    return page_texts, len(reader.pages)
