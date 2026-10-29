"""PDF validation, extraction, and page-aware chunking."""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO
import fitz

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PAGES = 500

@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str

@dataclass(frozen=True)
class Document:
    name: str
    pages: list[PageText]
    total_pages: int
    characters: int

@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    page_number: int
    source: str

def validate_pdf(data: bytes, name: str) -> None:
    if not name.lower().endswith('.pdf'):
        raise ValueError('Please upload a PDF file.')
    if not data:
        raise ValueError('The uploaded file is empty.')
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f'The file is too large. Maximum size is {MAX_FILE_BYTES // (1024 * 1024)} MB.')

def extract_document(file_or_bytes: BinaryIO | bytes, name: str) -> Document:
    data = file_or_bytes if isinstance(file_or_bytes, bytes) else file_or_bytes.read()
    validate_pdf(data, name)
    try:
        pdf = fitz.open(stream=BytesIO(data), filetype='pdf')
    except Exception as exc:
        raise ValueError('This PDF is corrupted, encrypted, or unsupported.') from exc
    try:
        if pdf.needs_pass:
            raise ValueError('This PDF is password-protected. Please upload an unlocked copy.')
        if len(pdf) == 0:
            raise ValueError('The PDF has no pages.')
        if len(pdf) > MAX_PAGES:
            raise ValueError(f'The PDF has too many pages. Maximum is {MAX_PAGES} pages.')
        pages = [PageText(i + 1, page.get_text('text').strip()) for i, page in enumerate(pdf)]
    finally:
        pdf.close()
    characters = sum(len(p.text) for p in pages)
    if characters == 0:
        raise ValueError('No selectable text was found. This may be a scanned PDF; run OCR first and try again.')
    return Document(name=name, pages=pages, total_pages=len(pages), characters=characters)

def chunk_document(document: Document, chunk_size: int = 1100, overlap: int = 180) -> list[Chunk]:
    if chunk_size <= overlap:
        raise ValueError('chunk_size must be greater than overlap')
    chunks: list[Chunk] = []
    for page in document.pages:
        words = page.text.split()
        if not words:
            continue
        start = 0
        index = 0
        while start < len(words):
            current, count, cursor = [], 0, start
            while cursor < len(words) and (count + len(words[cursor]) + 1 <= chunk_size or not current):
                current.append(words[cursor]); count += len(words[cursor]) + 1; cursor += 1
            text = ' '.join(current).strip()
            chunks.append(Chunk(f'p{page.page_number}-c{index}', text, page.page_number, document.name))
            if cursor >= len(words):
                break
            start += max(1, cursor - start - max(1, overlap // 6)); index += 1
    return chunks
