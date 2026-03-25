import io
import re

import fitz  # PyMuPDF
import docx
import markdown


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    extractors = {
        "pdf": _extract_pdf,
        "docx": _extract_docx,
        "md": _extract_markdown,
        "txt": _extract_text,
    }
    extractor = extractors.get(ext)
    if not extractor:
        raise ValueError(f"Unsupported file type: {ext}")
    return extractor(file_bytes)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            original_end = end
            max_scan = 50
            while end < len(text) and text[end] != " " and (end - original_end) < max_scan:
                end += 1
            if text[end] != " " if end < len(text) else False:
                end = original_end
        chunks.append(text[start:end].strip())
        start = end - overlap
        if start > 0:
            original_start = start
            max_scan = 50
            while start < len(text) and text[start] != " " and (start - original_start) < max_scan:
                start += 1
            if text[start] != " " if start < len(text) else False:
                start = original_start
    return [c for c in chunks if c]


def _extract_pdf(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    return "".join(page.get_text() for page in doc)


def _extract_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _extract_markdown(data: bytes) -> str:
    html = markdown.markdown(data.decode("utf-8"))
    return re.sub(r"<[^>]+>", "", html).strip()


def _extract_text(data: bytes) -> str:
    return data.decode("utf-8")
