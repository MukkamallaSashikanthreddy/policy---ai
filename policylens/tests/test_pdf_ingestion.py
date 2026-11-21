import pymupdf
import pytest

from policylens.pdf_ingestion import PDFIngestionError, clean_text, extract_pdf_pages


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    raw = doc.tobytes()
    doc.close()
    return raw


def test_extracts_text_and_page_numbers():
    pages, count = extract_pdf_pages(make_pdf("Policy covers accidental damage."))
    assert count == 1
    assert pages[0].page_number == 1
    assert "accidental damage" in pages[0].text


def test_rejects_non_pdf():
    with pytest.raises(PDFIngestionError):
        extract_pdf_pages(b"not a PDF")


def test_clean_text_normalizes_pdf_line_wraps():
    assert clean_text("insur-\nance\n\n policy") == "insurance\n\npolicy"
