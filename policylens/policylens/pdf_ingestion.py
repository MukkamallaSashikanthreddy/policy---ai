from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import pymupdf


class PDFIngestionError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


def clean_text(text: str) -> str:
    """Normalize PDF text while retaining paragraph boundaries and clause wording."""
    text = text.replace("\u00ad", "")
    text = text.replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)  # rejoin PDF line-wrap hyphenation
    text = re.sub(r"[\t\u00a0 ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_pages(file_bytes: bytes) -> tuple[list[PageText], int]:
    if not file_bytes or not file_bytes.startswith(b"%PDF"):
        raise PDFIngestionError("The uploaded file is not a valid PDF.")
    try:
        pdf = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:  # PyMuPDF has multiple low-level PDF exceptions
        raise PDFIngestionError(f"Could not open this PDF: {exc}") from exc

    pages: list[PageText] = []
    page_count = pdf.page_count
    try:
        if pdf.is_encrypted:
            raise PDFIngestionError("Password-protected PDFs are not supported. Remove the password and retry.")
        for index, page in enumerate(pdf):
            text = clean_text(page.get_text("text", sort=True))
            if text:
                pages.append(PageText(page_number=index + 1, text=text))
    finally:
        pdf.close()

    if not pages:
        raise PDFIngestionError(
            "No selectable text was found. This may be a scanned/image-only PDF; OCR is not enabled in this version."
        )
    return pages, page_count


def sha256_bytes(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()
