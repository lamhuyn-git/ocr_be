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


def render_form_returned_email(outcome_label: str, ward_name: str | None,
                               note: str | None, form_code: str) -> tuple[str, str]:
    ctx = {
        "outcome_label": outcome_label,
        "ward_name": ward_name,
        "note": note,
        "form_code": form_code,
        "app_name": settings.app_name,
        "brand_logo_url": settings.brand_logo_url,
        "brand_color": settings.brand_color,
        "support_email": settings.support_email,
    }
    html = _env.get_template("form_returned.html").render(**ctx)
    text = (
        f"{settings.app_name} - Ket qua ho so {form_code}\n\n"
        f"Ket qua: {outcome_label}\n"
        + (f"Ghi chu: {note}\n" if note else "")
        + (f"Vui long den {ward_name} de nhan ket qua.\n" if ward_name else "")
    )
    return html, text
