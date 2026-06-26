# Phase 02 — Frontend: prefill + khóa 2 select cho ward_officer

**Priority:** High · **Status:** ⬜ Pending · **Repo:** `/Users/macm2/Documents/trulem/ocr_fe`
**Depends on:** Phase 01 (field `ward` trong `/auth/me`).

## Mục tiêu
Officer mở form → Tỉnh/Thành phố + Phường set sẵn theo phụ trách, **disable** cả 2; Agency
hiển thị `Công an {wardName}`. Citizen → giữ nguyên hành vi chọn tay.

## Key insights (từ scout)
- `fetchCurrentUser` map trực tiếp `/auth/me` → `AuthUser`. (`src/features/auth/services/auth-api.ts:21-31`)
- `AuthUser.role` union `"user"|"admin"|"ward_admin"` KHÔNG khớp giá trị BE → **gate theo `user.ward`, không theo role**.
- Form state: `province`, `ward`, `wards`, `agency` khởi tạo rỗng. (`src/pages/form.tsx:48-52`)
- `fetchWards(provinceId)` nạp options phường; value select cần options đã load mới hiển thị. (`form-api.ts:19-25`)
- `AgencySection` 2 `<Select>`; ward đã có `disabled={!province}`. (`agency-section.tsx:40-60`)

## Implementation steps

### 1. Type — `src/features/auth/types.ts`
```typescript
export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: "user" | "admin" | "ward_admin";
  ward?: {
    orgId: string;
    wardName: string;
    provinceId: string | null;
    provinceName: string | null;
  };
};
```

### 2. Map response — `src/features/auth/services/auth-api.ts` (`fetchCurrentUser`)
```typescript
  return {
    id: data.id,
    role: data.role,
    name: data.full_name,
    email: data.email,
    ward: data.ward
      ? {
          orgId: data.ward.org_id,
          wardName: data.ward.ward_name,
          provinceId: data.ward.province_id,
          provinceName: data.ward.province_name,
        }
      : undefined,
  };
```

### 3. Prefill — `src/pages/form.tsx`
Thêm useEffect (sau khi `provinces` fetch, ~dòng 112). Chỉ chạy 1 lần khi có `user.ward`:
```typescript
useEffect(() => {
  const w = user?.ward;
  if (!w?.provinceId) return;
  setProvince(w.provinceId);
  setWardsLoading(true);
  fetchWards(w.provinceId)
    .then((opts) => {
      setWards(opts);
      setWard(w.orgId);
      setAgency(`Công an ${w.wardName}`);
    })
    .finally(() => setWardsLoading(false));
}, [user?.ward?.orgId]);
```
Truyền prop khóa vào `AgencySection`:
```typescript
<AgencySection ... locked={!!user?.ward} />
```

### 4. Khóa select — `src/features/residence-form/components/agency-section.tsx`
Thêm `locked?: boolean` vào Props; áp dụng:
```typescript
// Tỉnh/Thành phố
<Select ... onChange={onProvinceChange} disabled={locked} ... />
// Xã/Phường
<Select ... onChange={onWardChange} disabled={!province || locked} ... />
```

## Files
- Modify: `src/features/auth/types.ts`, `src/features/auth/services/auth-api.ts`,
  `src/pages/form.tsx`, `src/features/residence-form/components/agency-section.tsx`
- Create / Delete: none

## Todo
- [ ] Thêm `ward?` vào `AuthUser`
- [ ] Map `data.ward` trong `fetchCurrentUser`
- [ ] useEffect prefill province/ward/agency trong `form.tsx`
- [ ] Truyền + áp `locked` vào 2 select `AgencySection`
- [ ] `npm run build` / typecheck pass

## Success criteria
- Officer: 2 field hiển thị TP + phường đúng, disable; Agency = `Công an {phường}`; submit gửi `org_id` đúng.
- Citizen: hành vi chọn tay không đổi.
- Reload trang vẫn giữ prefill (lấy lại từ `/auth/me`).

## Risk
- Race: nếu `provinces` chưa load, value Tỉnh vẫn set được (Select hiển thị theo options tỉnh — fetchProvinces on mount đảm bảo có). Kiểm tra options tỉnh chứa `provinceId`.
- Đảm bảo useEffect không override khi citizen (guard `if (!w) return`).
