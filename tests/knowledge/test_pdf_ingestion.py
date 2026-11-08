from __future__ import annotations

import base64

import pytest
from pypdf import PdfWriter

from strongstart_api.features.knowledge.ingestion import TextIngestionError
from strongstart_api.features.knowledge.pdf_ingestion import BoundedPdfParser
from tests.knowledge.pdf_fixture import make_text_pdf


def _parser(**overrides: int) -> BoundedPdfParser:
    return BoundedPdfParser(
        max_bytes=overrides.get("max_bytes", 10_000),
        max_pages=overrides.get("max_pages", 5),
        max_chars=overrides.get("max_chars", 1_000),
    )


def test_pdf_parser_preserves_page_number_and_text() -> None:
    content = make_text_pdf("Exact evidence 120 children")
    decoded = _parser().decode(base64.b64encode(content).decode("ascii"))
    extraction = _parser().extract(decoded)
    assert extraction.page_count == 1
    assert extraction.pages[0].page_number == 1
    assert extraction.pages[0].text.strip() == "Exact evidence 120 children"
    assert extraction.warnings == []


@pytest.mark.parametrize(
    ("encoded", "message"),
    [
        ("not base64!", "strict standard base64"),
        (base64.b64encode(b"MZ executable").decode("ascii"), "PDF signature"),
    ],
)
def test_pdf_parser_rejects_invalid_transport_or_signature(encoded: str, message: str) -> None:
    with pytest.raises(TextIngestionError, match=message):
        _parser().decode(encoded)


def test_pdf_parser_rejects_oversize_before_parsing() -> None:
    encoded = base64.b64encode(make_text_pdf()).decode("ascii")
    with pytest.raises(TextIngestionError, match="byte limit"):
        _parser(max_bytes=100).decode(encoded)


def test_pdf_without_extractable_text_requires_ocr() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    from io import BytesIO

    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(TextIngestionError, match="OCR is required"):
        _parser().extract(buffer.getvalue())
