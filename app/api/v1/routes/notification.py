from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationListResponse, MarkReadRequest

router = APIRouter(prefix="/notifications", tags=["Notification"])


async def _count_unread(db: AsyncSession, user_id) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
    ).scalar() or 0


@router.get("", response_model=NotificationListResponse, summary="List my notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Notification).where(Notification.recipient_user_id == current_user.id)
    if unread_only:
        base = base.where(Notification.is_read.is_(False))

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0

    unread = await _count_unread(db, current_user.id)

    rows = (
        await db.execute(
            base.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "items": rows,
        "total": total,
        "unread": unread,
        "page": page,
        "page_size": page_size,
    }


@router.get("/unread-count", summary="Count my unread notifications")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"unread": await _count_unread(db, current_user.id)}


@router.post("/mark-read", summary="Mark my notifications as read")
async def mark_read(
    body: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = update(Notification).where(Notification.recipient_user_id == current_user.id)
    if not body.all:
        if not body.ids:
            return {"updated": 0}
        stmt = stmt.where(Notification.id.in_(body.ids))
    stmt = stmt.values(is_read=True)

    result = await db.execute(stmt)
    await db.flush()
    return {"updated": result.rowcount or 0}
