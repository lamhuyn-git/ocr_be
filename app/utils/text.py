"""Generic, stateless text helpers (no DB)."""
import re
import unicodedata


def slugify(name: str) -> str:
    """Vietnamese-aware slug: bỏ dấu, đ→d, lowercase, nối bằng '-'."""
    s = name.strip().lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s
