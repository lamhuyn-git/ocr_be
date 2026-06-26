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


# Tiền tố cấp hành chính (sau fold, giữ dấu): dùng để cắt hậu tố địa chỉ.
_ADMIN_PREFIXES = ("phường", "xã", "đặc khu", "thành phố", "tỉnh", "quận", "huyện")


def street_part(addr: str) -> str:
    """Giữ phần phân biệt 'số nhà + tên đường', bỏ hậu tố hành chính
    (phường/xã/quận/thành phố/tỉnh). Hậu tố này luôn trùng trong cùng một phường
    nên nếu so cả chuỗi sẽ làm loãng fuzzy match, khiến đường khác vẫn bị coi là khớp."""
    kept: list[str] = []
    for seg in (addr or "").split(","):
        seg = seg.strip()
        if not seg:
            continue
        if any(fold(seg).startswith(p) for p in _ADMIN_PREFIXES):
            break  # gặp đoạn cấp hành chính -> dừng, phần còn lại là phố/số nhà đã giữ
        kept.append(seg)
    return ", ".join(kept) if kept else (addr or "")
