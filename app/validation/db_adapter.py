from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.citizen import Citizen
from app.models.form import Form, FormResultStatus, TamtruForm
from app.models.organization import Organization

from . import groups
from . import field_rules as FR
from .decision import PASS, REVIEW, ERROR, Verdict
from .text_match import digits_only, norm_distance

_STATUS_MAP = {PASS: FormResultStatus.valid, REVIEW: FormResultStatus.need_review, ERROR: FormResultStatus.invalid}

def verdict_to_status(status_str: str) -> FormResultStatus:
    return _STATUS_MAP.get(status_str, FormResultStatus.need_review)


def _fmt_date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _enum_val(v) -> str:
    return getattr(v, "value", v) or ""


def _citizen_record(c: Citizen) -> dict:
    return {
        "ho_ten": c.ho_chu_dem_va_ten or "",
        "ngay_sinh": _fmt_date(c.ngay_sinh),
        "gioi_tinh": _enum_val(c.gioi_tinh),
        "so_dien_thoai": c.so_dien_thoai or "",
        "email": c.email or "",
    }


class DbCsdl:

    def __init__(self, citizens: dict, authorities: list):
        self.citizens = citizens
        self.authorities = authorities

    def lookup_citizen(self, cccd: str):
        return self.citizens.get(digits_only(cccd))

    # tìm tên cơ quan trong DB gần nhất với giá trị OCR đọc được.
    # OCR thường đọc thêm ", Thành phố ..." → dùng prefix distance để xử lý.
    def lookup_authority(self, name: str):
        if not self.authorities:
            return None, 1.0
        def _dist(a: str) -> float:
            d_full = norm_distance(name, a)
            # Nếu OCR dài hơn, thử so phần đầu cùng độ dài tên cơ quan
            if len(name) > len(a):
                d_prefix = norm_distance(name[:len(a)], a)
                return min(d_full, d_prefix)
            return d_full
        best = min(self.authorities, key=_dist)
        return best, _dist(best)


# GT fetchers (mỗi nhóm tự lấy GT)


async def _fetch_authorities(db: AsyncSession, form_db_id: UUID | None) -> list[str]:
    if form_db_id is None:
        return []
    org_name = (await db.execute(
        select(Organization.name).join(Form, Form.org_id == Organization.id).where(Form.id == form_db_id)
    )).scalar_one_or_none()
    return [f"Công an {org_name.strip()}"] if org_name else []


async def _fetch_citizen_record(db: AsyncSession, form_db_id: UUID | None) -> dict:
    if form_db_id is None:
        return {}
    cccd = (await db.execute(
        select(TamtruForm.registered_user_cccd).where(TamtruForm.form_id == form_db_id)
    )).scalar_one_or_none()
    if not cccd:
        return {}
    c = (await db.execute(
        select(Citizen).where(Citizen.so_dinh_danh == cccd)
    )).scalar_one_or_none()
    return {c.so_dinh_danh: _citizen_record(c)} if c else {}


async def _fetch_register_content(db: AsyncSession, form_db_id: UUID | None) -> dict:
    if form_db_id is None:
        return {}
    rc = (await db.execute(
        select(TamtruForm.register_content).where(TamtruForm.form_id == form_db_id)
    )).scalar_one_or_none()
    return rc or {}


# Group validators (lấy GT + validate)

async def validate_co_quan_thuc_hien(db: AsyncSession, ocr: dict, form_db_id: UUID | None) -> dict[str, Verdict]:
    gt = DbCsdl({}, await _fetch_authorities(db, form_db_id))
    return groups.validate_co_quan(ocr, gt)


async def validate_thong_tin_ho_thay_doi(db: AsyncSession, ocr: dict, form_db_id: UUID) -> dict[str, Verdict]:
    gt = DbCsdl(await _fetch_citizen_record(db, form_db_id), [])
    verdicts = groups.validate_ho_thay_doi(ocr, gt)
    return verdicts


async def validate_thong_tin_de_nghi(db: AsyncSession, ocr: dict, form_db_id: UUID | None) -> dict[str, Verdict]:
    register_content = await _fetch_register_content(db, form_db_id)
    return groups.validate_de_nghi(ocr, register_content)


# Orchestrator: dispatch theo submit_type

async def compute_field_statuses(
    db: AsyncSession, ocr_fields: dict, form_db_id: UUID | None = None,
) -> dict[str, Verdict]:
    """Trả về dict[field_name → Verdict] để caller lấy status + suggestion + reason."""
    verdicts: dict[str, Verdict] = {}
    verdicts.update(await validate_co_quan_thuc_hien(db, ocr_fields, form_db_id))
    verdicts.update(await validate_thong_tin_ho_thay_doi(db, ocr_fields, form_db_id))
    verdicts.update(await validate_thong_tin_de_nghi(db, ocr_fields, form_db_id))
    verdicts.update(groups.validate_thanh_vien(ocr_fields))

    # Khi CCCD người đăng ký là ERROR → tham chiếu OCR-to-OCR không đáng tin,
    # hạ so_dinh_danh_ca_nhan_cua_chu_ho xuống REVIEW thay vì giữ PASS vô nghĩa.
    cccd_v = verdicts.get(FR.KEY_CCCD_NGUOI_DK)
    if cccd_v is not None and cccd_v.status == ERROR:
        chu_ho_v = verdicts.get(FR.KEY_CCCD_CHU_HO)
        if chu_ho_v is not None and chu_ho_v.status == PASS:
            verdicts[FR.KEY_CCCD_CHU_HO] = Verdict(
                REVIEW,
                "CCCD người đăng ký không hợp lệ — không thể dùng làm tham chiếu cho chủ hộ",
                None, None, None, chu_ho_v.ocr_value,
            )
    return verdicts
