"""Test endpoint citizen xem chi tiết hồ sơ của chính mình (/form/user/detail).

Theo style suite hiện tại: mock biên DB, gọi thẳng builder/handler (không dựng Postgres/HTTP).
Trọng tâm: authz (chủ hồ sơ / 403 / 404 / superuser), map trạng thái hiển thị, evidences dùng
ẢNH GỐC, và response KHÔNG lộ field duyệt nội bộ.
"""
from __future__ import annotations

from datetime import datetime, date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.api.v1.routes.form as form_routes
from app.api.v1.routes.form import _build_user_form_detail, get_user_form_detail
from app.models.form import FormStatus
from app.schemas.form import UserFormDetailResponse


# --- helpers --------------------------------------------------------------

class _Result:
    def __init__(self, scalar=None, scalars_list=None):
        self._scalar = scalar
        self._scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self._scalars_list
        return m


def _builder_db(tamtru=None, evidences=None):
    """DB giả cho _build_user_form_detail: db.get→None (bỏ org/form_type),
    db.execute lần lượt trả tamtru rồi evidences."""
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.execute = AsyncMock(side_effect=[_Result(scalar=tamtru), _Result(scalars_list=evidences)])
    return db


def _make_form(submit_by, status=FormStatus.submitted):
    return SimpleNamespace(
        id=uuid4(),
        org_id=None,
        form_type_id=None,
        submit_by=submit_by,
        status=status,
        notification_on="email@x.com",
        created_at=datetime(2026, 6, 1, 10, 0, 0),
        updated_at=datetime(2026, 6, 2, 10, 0, 0),
    )


def _evidence(path_url, warped_img):
    return SimpleNamespace(path_url=path_url, warped_img=warped_img)


def _full_tamtru():
    return SimpleNamespace(
        id=uuid4(), case="A", type="t", submit_type="online",
        location_register="123 Đường ABC", registered_user_cccd="079...",
        registered_user_name="Nguyen Van A", registered_user_birth=date(1990, 1, 1),
        registered_user_gender="Nam", registered_user_phone="0900000000",
        registered_user_mail="a@x.com", register_content="noi dung",
    )


# --- builder: phạm vi dữ liệu & mapping -----------------------------------

@pytest.mark.parametrize("db_status,expected", [
    (FormStatus.draft, "draft"),
    (FormStatus.returned, "returned"),
    (FormStatus.submitted, "submitted"),
    (FormStatus.under_review, "submitted"),
])
async def test_status_mapped_to_display(db_status, expected):
    form = _make_form(uuid4(), status=db_status)
    res = await _build_user_form_detail(form, _builder_db())
    assert res.status == expected


async def test_evidences_use_original_upload_not_warped(monkeypatch):
    # presign = identity để assert deterministic là path GỐC được dùng (không phải warped_img).
    monkeypatch.setattr(form_routes, "_presign_path", lambda p: p)
    evs = [
        _evidence("uploads/CT01_abc.jpg", "uploads/CT01_warped.jpg"),
        _evidence("uploads/RESIDENCE_PROOF_x.jpg", None),
    ]
    res = await _build_user_form_detail(_make_form(uuid4()), _builder_db(evidences=evs))
    assert res.evidences.warped_img == "uploads/CT01_abc.jpg"          # ảnh gốc, KHÔNG phải _warped
    assert res.evidences.residence_proof == "uploads/RESIDENCE_PROOF_x.jpg"


async def test_sumited_content_populated_when_tamtru_exists():
    res = await _build_user_form_detail(_make_form(uuid4()), _builder_db(tamtru=_full_tamtru()))
    assert res.sumited_content is not None
    assert res.sumited_content.registered_user_name == "Nguyen Van A"


async def test_response_excludes_internal_review_fields():
    res = await _build_user_form_detail(_make_form(uuid4()), _builder_db())
    dumped = res.model_dump()
    for leaked in ("validated_results", "result_history", "db_value",
                   "confirmed_by_email", "review_note", "is_gate_rejected"):
        assert leaked not in dumped


# --- handler: authz -------------------------------------------------------

async def test_handler_404_when_form_missing():
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    with pytest.raises(HTTPException) as exc:
        await get_user_form_detail(uuid4(), current_user=user, db=db)
    assert exc.value.status_code == 404


async def test_handler_403_when_not_owner():
    form = _make_form(submit_by=uuid4())
    db = MagicMock()
    db.get = AsyncMock(return_value=form)
    other = SimpleNamespace(id=uuid4(), is_superuser=False)
    with pytest.raises(HTTPException) as exc:
        await get_user_form_detail(form.id, current_user=other, db=db)
    assert exc.value.status_code == 403


async def test_handler_200_for_owner():
    owner_id = uuid4()
    form = _make_form(submit_by=owner_id)
    db = MagicMock()
    db.get = AsyncMock(return_value=form)
    db.execute = AsyncMock(side_effect=[_Result(scalar=None), _Result(scalars_list=[])])
    owner = SimpleNamespace(id=owner_id, is_superuser=False)
    res = await get_user_form_detail(form.id, current_user=owner, db=db)
    assert isinstance(res, UserFormDetailResponse)
    assert res.id == form.id


async def test_handler_200_for_superuser_on_others_form():
    form = _make_form(submit_by=uuid4())
    db = MagicMock()
    db.get = AsyncMock(return_value=form)
    db.execute = AsyncMock(side_effect=[_Result(scalar=None), _Result(scalars_list=[])])
    admin = SimpleNamespace(id=uuid4(), is_superuser=True)
    res = await get_user_form_detail(form.id, current_user=admin, db=db)
    assert isinstance(res, UserFormDetailResponse)
