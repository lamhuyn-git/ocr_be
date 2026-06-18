import re
import unicodedata

from rapidfuzz.distance import Levenshtein


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", (s or "")).strip()


def fold(s: str) -> str:
    """Chuẩn hoá để SO SÁNH: NFC + lower + bỏ dấu câu (giữ dấu tiếng Việt) + gộp khoảng trắng."""
    s = nfc(s).lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)   # bỏ dấu câu, giữ chữ/số/dấu tiếng Việt
    return " ".join(s.split())

# Tính bằng Levenshtein
def norm_distance(a: str, b: str) -> float:
    a, b = fold(a), fold(b)
    if not a and not b:
        return 0.0
    denom = max(len(a), len(b)) or 1
    return Levenshtein.distance(a, b) / denom


def digits_only(s: str) -> str:
    return re.sub(r"\D", "", s or "")
