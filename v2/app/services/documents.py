import io

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
            while end < len(text) and text[end] != " ":
                end += 1
        chunks.append(text[start:end].strip())
        start = end - overlap
        if start > 0:
            while start < len(text) and text[start] != " ":
                start += 1
    return [c for c in chunks if c]


def _extract_pdf(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    return "".join(page.get_text() for page in doc)


def _extract_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _extract_markdown(data: bytes) -> str:
    html = markdown.markdown(data.decode("utf-8"))
    return html.replace("<p>", "").replace("</p>", "\n")


def _extract_text(data: bytes) -> str:
    return data.decode("utf-8")
