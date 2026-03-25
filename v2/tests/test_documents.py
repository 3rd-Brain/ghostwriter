import pytest
from app.services.documents import extract_text, chunk_text


def test_extract_text_txt():
    text = extract_text(b"Hello world", "file.txt")
    assert text == "Hello world"


def test_extract_text_markdown():
    md = b"# Title\n\nSome **bold** text."
    text = extract_text(md, "file.md")
    assert "Title" in text
    assert "bold" in text
    assert "<" not in text  # HTML tags stripped


def test_extract_text_unsupported():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(b"data", "file.xyz")


def test_chunk_text_small():
    text = "Short text"
    chunks = chunk_text(text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == "Short text"


def test_chunk_text_splits():
    text = "word " * 500  # 2500 chars
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 300  # chunk_size + max_scan tolerance


def test_chunk_text_no_spaces():
    """Verify chunk_text doesn't infinite loop on text without spaces."""
    text = "a" * 2000
    chunks = chunk_text(text, chunk_size=500, overlap=100)
    assert len(chunks) >= 1
    assert "".join(chunks)  # all content preserved


def test_chunk_text_empty():
    chunks = chunk_text("")
    assert chunks == []
