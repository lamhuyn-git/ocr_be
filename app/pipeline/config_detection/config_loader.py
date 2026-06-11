import copy
import json
import os
from typing import Optional

import yaml
from jsonschema import Draft7Validator

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))                
_CONFIGS_DIR = os.path.join(os.path.dirname(_THIS_DIR), "configs")     
_SCHEMA_PATH = os.path.join(_CONFIGS_DIR, "schema", "ct01_config.schema.json")


class ConfigError(Exception):
    """Ném ra khi config sai schema hoặc sai ngữ nghĩa."""


def _load_schema() -> dict:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise ConfigError(f"Config không tồn tại: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML không parse được ({path}): {e}") from e

    if not isinstance(config, dict):
        raise ConfigError(
            f"Config phải là mapping (dict), nhận: {type(config).__name__}"
        )

    validator = Draft7Validator(_load_schema())
    errors = sorted(validator.iter_errors(config), key=lambda e: e.path)
    if errors:
        # Gom TẤT CẢ lỗi lại, mỗi lỗi 1 dòng + chỉ rõ field nào
        messages = []
        for e in errors:
            location = ".".join(str(p) for p in e.path) or "<root>"
            messages.append(f"  - [{location}] {e.message}")
        raise ConfigError(f"Config sai schema ({path}):\n" + "\n".join(messages))

    # Bước 5: kiểm tra ngữ nghĩa mà schema không bắt được
    _check_semantics(config, path)
    return config


def _check_semantics(config: dict, path: str) -> None:
    """
    Kiểm tra ROI không tràn ra ngoài ảnh: x + w <= 1 và y + h <= 1.
    (1e-9 là dung sai nhỏ để bỏ qua sai số làm tròn số thực.)
    """
    for name, field in config["fields"].items():
        roi = field["roi_norm"]

        if roi["x"] + roi["w"] > 1.0 + 1e-9:
            raise ConfigError(
                f"Config {path}: field '{name}' ROI tràn biên phải "
                f"(x={roi['x']} + w={roi['w']} = {roi['x'] + roi['w']:.3f} > 1)."
            )

        if roi["y"] + roi["h"] > 1.0 + 1e-9:
            raise ConfigError(
                f"Config {path}: field '{name}' ROI tràn biên dưới "
                f"(y={roi['y']} + h={roi['h']} = {roi['y'] + roi['h']:.3f} > 1)."
            )


def apply_quality_overrides(config: dict, quality: Optional[str]) -> dict:
    # TODO(tạm): tắt nhân padding theo quality để calibrate lại ROI 53/2025.
    #   Đang dùng padding gốc trong config, không scale theo quality.
    #   Bật lại bằng cách bỏ `return config` dưới đây + uncomment khối bên dưới.
    return config

    # if quality is None:
    #     return config

    # overrides = config.get("quality_overrides", {})

    # if quality not in overrides:
    #     return config

    # rule = overrides[quality]

    # if "padding_scale" not in rule:
    #     return config

    # scale = rule["padding_scale"]

    # new_config = copy.deepcopy(config)

    # for field in new_config["fields"].values():
    #     old_x = field.get("padding_x", 0)
    #     old_y = field.get("padding_y", 0)
    #     field["padding_x"] = int(round(old_x * scale))
    #     field["padding_y"] = int(round(old_y * scale))

    # return new_config
