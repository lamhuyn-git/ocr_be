# Phase 01 — Backend: mở rộng `/auth/me` trả ward assignment

**Priority:** High · **Status:** ⬜ Pending · **Repo:** `/Users/macm2/Documents/trulem/ocr_be`

## Mục tiêu
`GET /api/v1/auth/me` trả thêm object `ward` cho ward_officer (suy ra phường + tỉnh).
Citizen / super_admin → `ward = null`.

## Key insights (từ scout)
- Không có cột `role` trên `User`; officer = có `OrganizationMember`. (`app/core/deps.py:18-22,61-65`)
- Chuỗi quan hệ: `OrganizationMember.org_id` → `Organization` → `Organization.province_id` → `Province.name`.
  (`app/models/organization.py:14-42`, `app/models/province.py`)
- `me()` đã tính `role` qua `get_user_role`. (`app/api/v1/routes/auth.py:139-143`)
- `UserResponse` ở `app/schemas/user.py:7-17` (đã có `role: str | None`).
- `Organization.province` relationship `lazy="noload"` → phải join/load tường minh, không lazy-load async được.

## Implementation steps

### 1. Schema — `app/schemas/user.py`
Thêm trước `UserResponse`:
```python
class WardAssignment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    org_id: UUID
    ward_name: str
    province_id: UUID | None = None
    province_name: str | None = None
```
Thêm field vào `UserResponse`:
```python
    ward: WardAssignment | None = None
```
(đảm bảo import `UUID`, `BaseModel`, `ConfigDict` đã có)

### 2. Helper — `app/core/deps.py`
Thêm import: `from app.models.organization import Organization` (đã có `OrganizationMember, OrgRole`),
`from app.models.province import Province`.
```python
# Phường primary của officer (membership sớm nhất) + tên tỉnh, dùng prefill form.
async def get_user_primary_ward(user: User, db: AsyncSession):
    row = (
        await db.execute(
            select(Organization, Province.name)
            .join(OrganizationMember, OrganizationMember.org_id == Organization.id)
            .outerjoin(Province, Province.id == Organization.province_id)
            .where(OrganizationMember.user_id == user.id)
            .order_by(OrganizationMember.created_at)
            .limit(1)
        )
    ).first()
    if not row:
        return None
    org, province_name = row
    return {
        "org_id": org.id,
        "ward_name": org.name,
        "province_id": org.province_id,
        "province_name": province_name,
    }
```

### 3. Route — `app/api/v1/routes/auth.py` (`me`, dòng 139-143)
```python
    resp = UserResponse.model_validate(current_user)
    resp.role = await get_user_role(current_user, db)
    if resp.role == "ward_officer":
        ward = await get_user_primary_ward(current_user, db)
        if ward:
            resp.ward = WardAssignment(**ward)
    return resp
```
Cập nhật import: `from app.schemas.user import UserResponse, WardAssignment` và
`from app.core.deps import get_current_user, get_user_role, get_user_primary_ward`.

## Files
- Modify: `app/schemas/user.py`, `app/core/deps.py`, `app/api/v1/routes/auth.py`
- Create: none · Delete: none · Migration: none (read-only feature)

## Todo
- [ ] Thêm `WardAssignment` + field `ward` vào schema
- [ ] Thêm `get_user_primary_ward` vào deps
- [ ] Set `resp.ward` trong `me()`
- [ ] Chạy server kiểm tra import / compile (`python -c "import app.main"`)

## Success criteria
- `GET /auth/me` với token officer → JSON có `ward: {org_id, ward_name, province_id, province_name}`.
- Token citizen / super_admin → `ward: null`.
- Không lỗi async lazy-load (`MissingGreenlet`).

## Security / risk
- Endpoint đã yêu cầu `get_current_user`. Chỉ lộ phường của chính user → an toàn.
- Officer nhiều phường: lấy phường sớm nhất; ghi nhận giới hạn ở `plan.md`.

## Next
→ Phase 02 dùng field `ward` để prefill + khóa FE.
