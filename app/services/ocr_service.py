import time
import os
import logging
from pathlib import Path
from typing import Any
from paddleocr import PaddleOCR
from PIL import Image
import pdf2image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_ocr_instances: dict[str, PaddleOCR] = {}


def get_ocr_engine(lang: str = "en") -> PaddleOCR:
    if lang not in _ocr_instances:
        _ocr_instances[lang] = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    return _ocr_instances[lang]


def _process_image(image: Image.Image, lang: str) -> dict[str, Any]:
    ocr = get_ocr_engine(lang)
    result = ocr.ocr(image, cls=True)

    words = []
    lines = []

    if result and result[0]:
        for line in result[0]:
            bbox, (text, confidence) = line
            words.append({
                "text": text,
                "confidence": round(float(confidence), 4),
                "bbox": bbox,
            })
            lines.append(text)

    return {
        "words": words,
        "text": " ".join(lines),
        "confidence": round(sum(w["confidence"] for w in words) / len(words), 4) if words else 0.0,
    }


def run_ocr(file_path: str, lang: str = "en") -> dict[str, Any]:
    """Run OCR on an image or PDF. Returns structured result with timing."""
    start = time.time()
    ext = Path(file_path).suffix.lower().lstrip(".")
    pages_result = []

    if ext == "pdf":
        images = pdf2image.convert_from_path(file_path, dpi=200)
        for i, image in enumerate(images, start=1):
            page_data = _process_image(image, lang)
            pages_result.append({"page": i, **page_data})
    else:
        image = Image.open(file_path)
        page_data = _process_image(image, lang)
        pages_result.append({"page": 1, **page_data})

    full_text = "\n\n".join(p["text"] for p in pages_result)
    all_confidences = [w["confidence"] for p in pages_result for w in p["words"]]
    avg_confidence = round(sum(all_confidences) / len(all_confidences), 4) if all_confidences else 0.0

    elapsed_ms = int((time.time() - start) * 1000)

    return {
        "pages": pages_result,
        "extracted_text": full_text,
        "confidence_score": avg_confidence,
        "page_count": len(pages_result),
        "processing_time_ms": elapsed_ms,
    }
