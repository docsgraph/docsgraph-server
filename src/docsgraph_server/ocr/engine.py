"""OCR engine interface.

Defines the contract document processing uses to extract text from
scanned/image-based documents. Tesseract is the intended first backend;
`TesseractOcrEngine` below is a placeholder pending that implementation.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OcrResult:
    """Result of running OCR over a document."""

    text: str
    confidence: float


class OcrEngine(Protocol):
    """Interface implemented by OCR backends."""

    def extract_text(self, document: bytes) -> OcrResult:
        """Extract text (and a confidence score) from a document's raw bytes."""
        ...


class TesseractOcrEngine:
    """Tesseract-backed `OcrEngine`. Not yet implemented."""

    def extract_text(self, document: bytes) -> OcrResult:
        """Extract text via Tesseract."""
        raise NotImplementedError("Tesseract OCR backend is not yet implemented")
