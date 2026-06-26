# Plan: Mặc định Tỉnh/Thành phố + Phường cho ward_officer

## Mục tiêu
Khi user đăng nhập là **ward_officer**, 2 field trong "Cơ quan thực hiện" của form đăng ký
cư trú phải được set sẵn và **khóa (read-only)**:
- **Tỉnh/Thành phố** = tỉnh của phường mà officer phụ trách (suy ra từ `Organization.province_id`).
- **Phường/Xã** = phường officer phụ trách (`OrganizationMember.org_id`).

## Quyết định đã chốt (user)
1. 2 field **khóa/disable** (read-only) khi là ward_officer.
2. Tỉnh **suy ra** từ phường officer (không hardcode HCM).
3. Phạm vi: **Backend + Frontend**.

## Cách tiếp cận (chốt)
- **Không tạo endpoint mới.** Mở rộng `GET /api/v1/auth/me` để trả thêm object `ward`
  (officer mới có, citizen/null). Tiết kiệm 1 round-trip, role đã tính sẵn ở đây.
- Frontend gate việc khóa field theo **sự hiện diện của `user.ward`**, KHÔNG dựa vào chuỗi
  `role` (union `role` ở FE hiện không khớp giá trị BE — tránh fragile).
- Phường "primary" = membership sớm nhất (`order_by created_at limit 1`) nếu officer thuộc nhiều phường.

## Phases
| # | Phase | Status | File |
|---|-------|--------|------|
| 1 | Backend: mở rộng `/auth/me` trả ward assignment | ✅ Done | [phase-01-backend-ward-assignment.md](phase-01-backend-ward-assignment.md) |
| 2 | Frontend: prefill + khóa 2 select | ✅ Done | [phase-02-frontend-prefill-lock.md](phase-02-frontend-prefill-lock.md) |

## Dependencies
- Phase 2 phụ thuộc Phase 1 (cần field `ward` trong response `/auth/me`).
- Repos: backend `/Users/macm2/Documents/trulem/ocr_be`, frontend `/Users/macm2/Documents/trulem/ocr_fe`.

## Files chính sẽ chạm
**Backend**
- `app/schemas/user.py` — thêm `WardAssignment` + field `ward` trong `UserResponse`.
- `app/core/deps.py` — helper `get_user_primary_ward(user, db)`.
- `app/api/v1/routes/auth.py` — set `resp.ward` trong `me()`.

**Frontend**
- `src/features/auth/types.ts` — thêm `ward?` vào `AuthUser`.
- `src/features/auth/services/auth-api.ts` — map `data.ward`.
- `src/pages/form.tsx` — useEffect prefill từ `user.ward`; truyền `locked`.
- `src/features/residence-form/components/agency-section.tsx` — prop `locked`, disable 2 select.

## Out of scope
- Backend enforcement bắt buộc `org_id` của officer khi submit (FE đã khóa; có thể bổ sung sau nếu cần chống bypass API).
- Hỗ trợ officer chọn giữa nhiều phường (lấy phường primary).
