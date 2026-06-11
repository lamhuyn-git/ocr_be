from __future__ import annotations
import os
import time
import logging
from pathlib import Path
from typing import Any

import cv2

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

os.environ.setdefault("OCR_MODEL_VERSION", settings.ocr_model_version)

def _imports():
    from app.pipeline.alignment import align_form
    from app.pipeline.config_detection import load_config, apply_quality_overrides
    from app.pipeline.ocr.field_extractor import extract_fields
    return align_form, load_config, apply_quality_overrides, extract_fields


TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "configs" / "templates"


def save_template_config(form_id: str, version: str, yaml_bytes: bytes) -> str:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{form_id}_v{version}.yaml"
    dest = TEMPLATES_DIR / filename
    dest.write_bytes(yaml_bytes)
    return str(dest)


def validate_template_yaml(yaml_bytes: bytes) -> dict:
    import yaml
    import tempfile

    _, load_config, _, _ = _imports()

    # ghi file input ra file tạm
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
        tmp.write(yaml_bytes)
        tmp_path = tmp.name

    try:
        config = load_config(tmp_path)
    finally:
        os.unlink(tmp_path)

    return config


# Main pipeline ở background

def run_form_pipeline(image_path: str, config_path: str) -> dict[str, Any]:
    align_form, load_config, apply_quality_overrides, extract_fields = _imports()

    start = time.time()

    # Bước 1: đọc ảnh
    logger.info("[PIPELINE] 1/4 đọc ảnh: %s", image_path)
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image at path: {image_path}")

    # Bước 2: căn chỉnh (align) ảnh về khung chuẩn
    logger.info("[PIPELINE] 2/4 align ảnh ...")
    warped, align_meta = align_form(img)
    quality = align_meta.get("quality", "good")  # chống lỗi khi align_meta lỡ không có key "quality"
    logger.info("[PIPELINE] align xong: method=%s quality=%s inliers=%s",
                align_meta.get("method"), quality, align_meta.get("n_inliers"))

    # Bước 3: nạp config template
    logger.info("[PIPELINE] 3/4 load config: %s", config_path)
    config = load_config(config_path)
    # config = apply_quality_overrides(config, quality)  # Chưa dùng đến, để dành cho sau khi có nhiều tier hơn và cần override config theo tier.

    # Bước 4: trích xuất field (chuẩn hoá per-field đã chạy trong extract_fields theo config)
    logger.info("[PIPELINE] 4/4 extract fields ...")
    raw_fields = extract_fields(warped, config)
    logger.info("[PIPELINE] extract xong: %d field", len(raw_fields))

    # Average confidence over non-empty text fields
    confidences = [
        v["confidence"]
        for v in raw_fields.values()
        if isinstance(v, dict)
        and not v.get("empty", True)
        and "confidence" in v
    ]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info("Form pipeline done in %dms, confidence=%.3f", elapsed_ms, avg_confidence)

    return {
        "extracted_fields":   raw_fields,
        "confidence_score":   avg_confidence,
        "alignment_method":   align_meta.get("method"),
        "alignment_quality":  quality,
        "alignment_meta":     align_meta,
        "processing_time_ms": elapsed_ms,
    }
