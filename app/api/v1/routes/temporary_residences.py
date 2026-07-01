from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_staff, get_user_ward_ids
from app.database import get_db
from app.models.residence import TemporaryResidence, TempResidenceStatus
from app.models.citizen import Citizen
from app.models.form import Form as FormModel
from app.models.user import User
from app.schemas.residence import (
    TemporaryResidenceListItem,
    TemporaryResidenceListResponse,
)

router = APIRouter(prefix="/temporary-residences", tags=["TemporaryResidence"])


@router.get(
    "",
    response_model=TemporaryResidenceListResponse,
    summary="List granted temporary residences (scoped by ward)",
)
async def list_temporary_residences(
    org_id: UUID | None = None,
    status_filter: TempResidenceStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, description="Tìm theo CCCD / họ tên / SĐT người tạm trú"),
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    conditions = []

    # Scope theo quyền: superadmin xem mọi phường (có thể lọc thêm org_id);
    # staff chỉ xem các phường mình là thành viên.
    if not current_user.is_superuser:
        ward_ids = await get_user_ward_ids(current_user, db)
        if not ward_ids:
            return TemporaryResidenceListResponse(items=[], total=0)
        conditions.append(TemporaryResidence.org_id.in_(ward_ids))

    if org_id is not None:
        conditions.append(TemporaryResidence.org_id == org_id)
    if status_filter is not None:
        conditions.append(TemporaryResidence.status == status_filter)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conditions.append(
            or_(
                Citizen.so_dinh_danh.ilike(like),
                Citizen.ho_chu_dem_va_ten.ilike(like),
                Citizen.so_dien_thoai.ilike(like),
            )
        )

    # Bản ghi tạm trú + thông tin người tạm trú (citizen) + cán bộ tiếp nhận
    # (form.reviewer). Tất cả join là LEFT JOIN vì các FK đều có thể NULL.
    data_stmt = (
        select(
            TemporaryResidence,
            Citizen.so_dinh_danh,
            Citizen.ho_chu_dem_va_ten,
            Citizen.so_dien_thoai,
            Citizen.so_dinh_danh_chu_ho,
            User.full_name,
        )
        .select_from(TemporaryResidence)
        .outerjoin(Citizen, Citizen.id == TemporaryResidence.citizen_id)
        .outerjoin(FormModel, FormModel.id == TemporaryResidence.form_id)
        .outerjoin(User, User.id == FormModel.reviewer_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(TemporaryResidence)
        .outerjoin(Citizen, Citizen.id == TemporaryResidence.citizen_id)
    )
    if conditions:
        data_stmt = data_stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    data_stmt = (
        data_stmt.order_by(TemporaryResidence.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = (await db.execute(data_stmt)).all()
    total = (await db.execute(count_stmt)).scalar_one()

    items = [
        TemporaryResidenceListItem(
            id=tr.id,
            citizen_cccd=cccd,
            citizen_name=name,
            phone=phone,
            chu_ho_cccd=chu_ho,
            dia_chi=tr.dia_chi,
            tu_ngay=tr.tu_ngay,
            den_ngay=tr.den_ngay,
            reviewer_name=reviewer_name,
            form_id=tr.form_id,
            status=tr.status,
            created_at=tr.created_at,
        )
        for tr, cccd, name, phone, chu_ho, reviewer_name in rows
    ]
    return TemporaryResidenceListResponse(items=items, total=total)
