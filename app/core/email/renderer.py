from __future__ import annotations
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings

settings = get_settings()

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_otp_email(otp: str, expire_minutes: int) -> tuple[str, str]:
    ctx = {
        "otp": otp,
        "expire_minutes": expire_minutes,
        "app_name": settings.app_name,
        "brand_logo_url": settings.brand_logo_url,
        "brand_color": settings.brand_color,
        "support_email": settings.support_email,
    }
    html = _env.get_template("otp_reset.html").render(**ctx)
    text = (
        f"{settings.app_name} - Dat lai mat khau\n\n"
        f"Ma xac thuc cua ban: {otp}\n"
        f"Ma co hieu luc trong {expire_minutes} phut va chi dung mot lan.\n\n"
        f"Neu ban khong yeu cau, vui long bo qua email nay."
    )
    return html, text
