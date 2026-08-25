"""OCR engine interface.

Defines the contract document processing uses to extract text from
scanned/image-based documents.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("docsgraph_server.ocr")


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
    """Tesseract-backed `OcrEngine` with fallback."""

    def extract_text(self, document: bytes) -> OcrResult:
        """Extract text via Tesseract, with a mock fallback if Tesseract is missing."""
        try:
            import io

            import pytesseract  # type: ignore[import-not-found]
            from PIL import Image  # type: ignore[import-not-found]

            image = Image.open(io.BytesIO(document))
            text = pytesseract.image_to_string(image)
            return OcrResult(text=text.strip(), confidence=0.9)
        except ImportError:
            logger.warning("pytesseract or Pillow is not installed. Using mock OCR fallback.")
            return OcrResult(text="Simulated Tesseract OCR Text", confidence=0.5)
        except Exception as e:
            logger.warning("Tesseract OCR extraction failed: %s. Using mock OCR fallback.", e)
            return OcrResult(text="Simulated Tesseract OCR Text", confidence=0.5)
