"""
Form extraction service.
Wraps the ocr_project pipeline:
  image → align → load_config → extract_fields → validate → structured result
"""
from __future__ import annotations
import sys
import os
import time
import logging
from pathlib import Path
from typing import Any

import cv2

logger = logging.getLogger(__name__)

# ── Inject ocr_project into Python path ──────────────────────────────────────
_OCR_PROJECT = Path("/Users/macm2/Documents/trulem/ocr_project")
_OCR_SRC     = _OCR_PROJECT / "src"
_OCR_CONFIGS = _OCR_PROJECT / "configs"

for _p in [str(_OCR_PROJECT), str(_OCR_SRC)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Lazy imports — heavy models are loaded on first call, not at import time
def _imports():
    from alignment import align_form
    from config_detection import load_config, apply_quality_overrides
    from ocr.field_extractor import extract_fields
    from validator.validator import CLEAN_FUNCTIONS
    return align_form, load_config, apply_quality_overrides, extract_fields, CLEAN_FUNCTIONS


# ── Template config helpers ───────────────────────────────────────────────────

TEMPLATES_DIR = _OCR_CONFIGS / "templates"
SCHEMA_DIR    = _OCR_CONFIGS / "schema"


def save_template_config(form_id: str, version: str, yaml_bytes: bytes) -> str:
    """Save uploaded YAML to configs/templates/. Returns absolute path."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{form_id}_v{version}.yaml"
    dest = TEMPLATES_DIR / filename
    dest.write_bytes(yaml_bytes)
    return str(dest)


def validate_template_yaml(yaml_bytes: bytes) -> dict:
    """
    Parse + validate the YAML against the JSON schema.
    Returns parsed config dict, raises ValueError on failure.
    """
    import yaml
    import tempfile

    _, load_config, _, _, _ = _imports()

    # Write to temp file so load_config can read it (it expects a path)
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
        tmp.write(yaml_bytes)
        tmp_path = tmp.name

    try:
        config = load_config(tmp_path)
    finally:
        os.unlink(tmp_path)

    return config


# ── Field validation ──────────────────────────────────────────────────────────

def _apply_validators(raw_fields: dict, clean_functions: dict) -> dict:
    """
    Run field-specific cleaners from validator.py on each extracted field.
    Table fields (list) are passed through unchanged.
    """
    validated: dict[str, Any] = {}
    for field_name, result in raw_fields.items():
        if isinstance(result, list):
            # Table field — keep as-is
            validated[field_name] = result
            continue

        if not isinstance(result, dict):
            validated[field_name] = result
            continue

        raw_text = result.get("text", "")
        cleaner  = clean_functions.get(field_name)

        if cleaner and raw_text:
            try:
                cleaned = cleaner(raw_text)
            except Exception as exc:
                logger.warning("Validator error on field %s: %s", field_name, exc)
                cleaned = raw_text
        else:
            cleaned = raw_text

        validated[field_name] = {**result, "validated": cleaned}

    return validated


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_form_pipeline(image_path: str, config_path: str) -> dict[str, Any]:
    """
    Full synchronous pipeline (run inside a thread executor to avoid blocking).

    Steps:
      1. Read image with OpenCV
      2. align_form  → canonical 1654×2339, quality tier, alignment meta
      3. load_config + apply_quality_overrides (pads ROI by quality)
      4. extract_fields  → per-field OCR results
      5. validate fields → cleaned text values

    Returns a result dict ready to persist to the DB.
    """
    align_form, load_config, apply_quality_overrides, extract_fields, CLEAN_FUNCTIONS = _imports()

    start = time.time()

    # 1. Read image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image at path: {image_path}")

    # 2. Align
    warped, align_meta = align_form(img)
    quality = align_meta.get("quality", "good")
    logger.info("Alignment done: method=%s quality=%s inliers=%s",
                align_meta.get("method"), quality, align_meta.get("n_inliers"))

    # 3. Load field config
    config = load_config(config_path)
    config = apply_quality_overrides(config, quality)

    # 4. Extract fields
    raw_fields = extract_fields(warped, config)

    # 5. Validate
    validated_fields = _apply_validators(raw_fields, CLEAN_FUNCTIONS)

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
        "validated_fields":   validated_fields,
        "confidence_score":   avg_confidence,
        "alignment_method":   align_meta.get("method"),
        "alignment_quality":  quality,
        "alignment_meta":     align_meta,
        "processing_time_ms": elapsed_ms,
    }
