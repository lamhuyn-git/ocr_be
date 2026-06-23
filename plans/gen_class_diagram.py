#!/usr/bin/env python3
"""Sinh sơ đồ lớp (UML class diagram) chuẩn học thuật cho backend OCR.

Nguyên tắc áp dụng (tham khảo viblo class-diagram):
 - Lớp = 3 ngăn: tên / thuộc tính (visibility + name: Type) / phương thức (lược bỏ ở lớp entity).
 - Bỏ cột khóa ngoại (FK) khỏi danh sách thuộc tính -> thay bằng đường quan hệ + multiplicity.
 - Composition (thoi đặc ◆): con bị xóa theo cha (ondelete=CASCADE / delete-orphan).
 - Aggregation (thoi rỗng ◇): con sống độc lập (ondelete=SET NULL).
 - Association: tham chiếu điều hướng còn lại, có vai trò (role) + multiplicity.
 - Enum biểu diễn bằng «enumeration».
"""
import math

OUT = "/Users/macm2/Documents/trulem/ocr_project/assets/diagrams/class-diagram-uml-backend.svg"

PURPLE = "#2A165A"

# ---- Định nghĩa lớp: (key, title, x, y, width, [(name, type)]) ----
CLASSES = {
    "Province": ("Province", 40, 60, 215, [
        ("id", "UUID"), ("name", "String"), ("slug", "String"),
        ("created_at", "DateTime"), ("updated_at", "DateTime")]),
    "OrgAddress": ("OrgAddress", 40, 200, 215, [
        ("id", "UUID"), ("dia_chi", "String"), ("is_active", "Boolean"),
        ("created_at", "DateTime"), ("updated_at", "DateTime")]),
    "OrganizationMember": ("OrganizationMember", 40, 345, 215, [
        ("id", "UUID"), ("role", "OrgRole"), ("created_at", "DateTime")]),
    "RefreshToken": ("RefreshToken", 40, 470, 215, [
        ("id", "UUID"), ("token_hash", "String"), ("expires_at", "DateTime"),
        ("is_revoked", "Boolean"), ("created_at", "DateTime")]),
    "PasswordResetOTP": ("PasswordResetOTP", 40, 620, 215, [
        ("id", "UUID"), ("otp_hash", "String"), ("expires_at", "DateTime"),
        ("attempts", "Integer"), ("is_used", "Boolean"), ("created_at", "DateTime")]),
    "CitizenRelation": ("CitizenRelation", 40, 900, 215, [
        ("id", "UUID"), ("relation_type", "RelationType"),
        ("note", "String"), ("created_at", "DateTime")]),
    "Organization": ("Organization", 560, 60, 215, [
        ("id", "UUID"), ("name", "String"), ("slug", "String"),
        ("org_type", "String"), ("created_at", "DateTime"), ("updated_at", "DateTime")]),
    "User": ("User", 560, 270, 215, [
        ("id", "UUID"), ("national_id", "String"), ("email", "String"),
        ("hashed_password", "String"), ("google_sub", "String"),
        ("full_name", "String"), ("is_active", "Boolean"),
        ("is_superuser", "Boolean"), ("created_at", "DateTime"), ("updated_at", "DateTime")]),
    "Citizen": ("Citizen", 560, 620, 215, [
        ("id", "UUID"), ("so_dinh_danh", "String"), ("ho_chu_dem_va_ten", "String"),
        ("ten_goi_khac", "String"), ("ngay_sinh", "Date"), ("gioi_tinh", "Gender"),
        ("noi_sinh", "String"), ("noi_dang_ky_khai_sinh", "String"),
        ("que_quan", "String"), ("dan_toc", "String"), ("ton_giao", "String"),
        ("quoc_tich", "String"), ("nhom_mau", "String"), ("noi_thuong_tru", "String"),
        ("noi_tam_tru", "String"), ("noi_o_hien_tai", "String"),
        ("tinh_trang_cu_tru", "ResidenceStatus"), ("ma_ho", "String"),
        ("quan_he_voi_chu_ho", "String"), ("so_dinh_danh_chu_ho", "String"),
        ("tinh_trang_hon_nhan", "MaritalStatus"), ("nghe_nghiep", "String"),
        ("tinh_trang_song", "LifeStatus"), ("ngay_mat", "Date"),
        ("so_dien_thoai", "String"), ("email", "String"), ("is_active", "Boolean"),
        ("created_at", "DateTime"), ("updated_at", "DateTime")]),
    "FormType": ("FormType", 1075, 60, 215, [
        ("id", "UUID"), ("type_name", "String"), ("created_at", "DateTime")]),
    "FormTemplate": ("FormTemplate", 1075, 200, 215, [
        ("id", "UUID"), ("name", "String"), ("version", "String"),
        ("config_path", "String"), ("field_schema", "JSONB"),
        ("is_active", "Boolean"), ("created_at", "DateTime"), ("updated_at", "DateTime")]),
    "Form": ("Form", 1075, 430, 215, [
        ("id", "UUID"), ("status", "FormStatus"), ("notification_on", "String"),
        ("review_note", "Text"), ("created_at", "DateTime"), ("updated_at", "DateTime")]),
    "TamtruForm": ("TamtruForm", 1075, 620, 215, [
        ("id", "UUID"), ("case", "String"), ("type", "String"),
        ("submit_type", "String"), ("location_register", "String"),
        ("registered_user_cccd", "String"), ("registered_user_name", "String"),
        ("registered_user_birth", "Date"), ("registered_user_gender", "String"),
        ("registered_user_phone", "String"), ("registered_user_mail", "String"),
        ("register_content", "Text"), ("created_at", "DateTime")]),
    "Evidence": ("Evidence", 1075, 900, 215, [
        ("id", "UUID"), ("path_url", "String"), ("warped_img", "String"),
        ("created_at", "DateTime")]),
    "FormResult": ("FormResult", 1075, 1040, 215, [
        ("id", "UUID"), ("label", "String"), ("raw_value", "Text"),
        ("suggested_value", "Text"), ("final_value", "Text"), ("note", "Text"),
        ("status", "FormResultStatus"), ("position", "JSONB"), ("created_at", "DateTime")]),
    "TemporaryResidence": ("TemporaryResidence", 1075, 1280, 215, [
        ("id", "UUID"), ("dia_chi", "String"), ("tu_ngay", "Date"),
        ("den_ngay", "Date"), ("status", "TempResidenceStatus"),
        ("created_at", "DateTime"), ("updated_at", "DateTime")]),
}

HDR = 26
ROW = 15

def box_geom(key):
    _, x, y, w, attrs = CLASSES[key]
    h = HDR + len(attrs) * ROW + 8
    return x, y, w, h

def render_class(key):
    title = CLASSES[key][0]
    attrs = CLASSES[key][4]
    x, y, w, h = box_geom(key)
    s = []
    s.append(f'<rect class="tbox" x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>')
    s.append(f'<rect class="thd" x="{x}" y="{y}" width="{w}" height="{HDR}" rx="3"/>')
    s.append(f'<rect class="thd" x="{x}" y="{y+HDR-6}" width="{w}" height="6"/>')
    cx = x + w / 2
    s.append(f'<text class="st" x="{cx}" y="{y+11}">&#171;entity&#187;</text>')
    s.append(f'<text class="tt" x="{cx}" y="{y+22}">{title}</text>')
    ay = y + HDR + 12
    for name, typ in attrs:
        pk = ' font-weight="bold"' if name == "id" else ''
        s.append(f'<text class="ff" x="{x+8}" y="{ay}"><tspan class="vis">+</tspan> '
                 f'<tspan{pk}>{name}</tspan>: <tspan class="typ">{typ}</tspan></text>')
        ay += ROW
    return "".join(s)

# ---- Markers ----
def diamond(px, py, dx, dy, filled):
    """Thoi đặt tại đầu 'cha', dx,dy = hướng đoạn đầu (rời khỏi hộp cha)."""
    L = 9
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    pxp, pyp = -uy, ux  # vuông góc
    half = 6
    cx, cy = px + ux * L, py + uy * L
    far_x, far_y = px + ux * 2 * L, py + uy * 2 * L
    pts = [(px, py), (cx + pxp * half, cy + pyp * half),
           (far_x, far_y), (cx - pxp * half, cy - pyp * half)]
    p = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    fill = PURPLE if filled else "#ffffff"
    return f'<polygon points="{p}" fill="{fill}" stroke="{PURPLE}" stroke-width="1.2"/>'

def arrow(px, py, dx, dy):
    """Mũi tên hở (navigability) tại đầu 'con', dx,dy = hướng đoạn cuối tới hộp con."""
    L = 11
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    pxp, pyp = -uy, ux
    bx, by = px - ux * L, py - uy * L
    a = (bx + pxp * 5, by + pyp * 5)
    b = (bx - pxp * 5, by - pyp * 5)
    return (f'<polyline points="{a[0]:.1f},{a[1]:.1f} {px:.1f},{py:.1f} '
            f'{b[0]:.1f},{b[1]:.1f}" fill="none" stroke="{PURPLE}" stroke-width="1.1"/>')

# ---- Edges ----
# kind: comp | agg | assoc ; pts = polyline (đầu = phía cha/aggregate)
# m0 = multiplicity tại đầu pts[0], m1 = tại đầu pts[-1]; role optional; navi: vẽ mũi tên ở đầu con (pts[-1])
EDGES = [
    # whole/aggregate ở pts[0]
    ("agg",   [(255,122),(560,122)], "1", "*", "", False),                       # Province ◇ Organization
    ("comp",  [(560,150),(420,150),(420,254),(255,254)], "1", "*", "", False),   # Organization ◆ OrgAddress
    ("comp",  [(560,165),(395,165),(395,375),(255,375)], "1", "*", "", False),   # Organization ◆ OrganizationMember
    ("assoc", [(255,400),(490,400),(490,408),(560,408)], "*", "1", "", True),    # OrganizationMember -> User
    ("comp",  [(560,420),(360,420),(360,524),(255,524)], "1", "*", "", False),   # User ◆ RefreshToken
    ("comp",  [(560,440),(335,440),(335,682),(255,682)], "1", "*", "", False),   # User ◆ PasswordResetOTP
    ("assoc", [(667,454),(667,620)], "1", "0..1", "", True),                     # User -> Citizen (1:1)
    ("comp",  [(560,900),(420,900),(420,940),(255,940)], "1", "*", "", False),   # Citizen ◆ CitizenRelation
    ("assoc", [(255,965),(440,965),(440,1010),(560,1010)], "*", "1", "related", True),  # CitizenRelation -> Citizen
    ("comp",  [(775,1050),(905,1050),(905,1315),(1075,1315)], "1", "*", "", False),     # Citizen ◆ TemporaryResidence
    ("agg",   [(775,135),(1025,135),(1025,1300),(1075,1300)], "0..1", "*", "", False),  # Organization ◇ TemporaryResidence
    ("agg",   [(775,160),(965,160),(965,465),(1075,465)], "0..1", "*", "", False),      # Organization ◇ Form
    ("assoc", [(1075,485),(945,485),(945,345),(775,345)], "*", "1", "submit_by", True), # Form -> User
    ("assoc", [(1075,285),(885,285),(885,320),(775,320)], "*", "0..1", "created_by", True),   # FormTemplate -> User
    ("assoc", [(1075,1110),(855,1110),(855,400),(775,400)], "*", "0..1", "confirmed_by", True),  # FormResult -> User
    ("comp",  [(1182,139),(1182,200)], "1", "*", "", False),                     # FormType ◆ FormTemplate
    ("agg",   [(1290,99),(1335,99),(1335,470),(1290,470)], "0..1", "*", "", False),     # FormType ◇ Form
    ("comp",  [(1182,554),(1182,620)], "1", "0..1", "", False),                  # Form ◆ TamtruForm
    ("comp",  [(1290,515),(1355,515),(1355,947),(1290,947)], "1", "*", "", False),      # Form ◆ Evidence
    ("comp",  [(1290,535),(1375,535),(1375,1124),(1290,1124)], "1", "*", "", False),    # Form ◆ FormResult
    ("agg",   [(1290,545),(1395,545),(1395,1360),(1290,1360)], "0..1", "*", "", False), # Form ◇ TemporaryResidence
]

def render_edge(kind, pts, m0, m1, role, navi):
    s = []
    path = "M" + " L".join(f"{x},{y}" for x, y in pts)
    s.append(f'<path class="rel" d="{path}"/>')
    # marker tại đầu cha (pts[0]), hướng = pts[0]->pts[1]
    x0, y0 = pts[0]; x1, y1 = pts[1]
    dx, dy = x1 - x0, y1 - y0
    if kind == "comp":
        s.append(diamond(x0, y0, dx, dy, True))
    elif kind == "agg":
        s.append(diamond(x0, y0, dx, dy, False))
    # mũi tên tại đầu con (pts[-1])
    if navi:
        xn, yn = pts[-1]; xp, yp = pts[-2]
        s.append(arrow(xn, yn, xn - xp, yn - yp))
    # multiplicity
    def near(p, q, m, anchor):
        if not m:
            return ""
        ddx, ddy = q[0]-p[0], q[1]-p[1]
        n = math.hypot(ddx, ddy) or 1
        ux, uy = ddx/n, ddy/n
        tx = p[0] + ux*20 - uy*8
        ty = p[1] + uy*20 + ux*8 + 3
        return f'<text class="ml" x="{tx:.0f}" y="{ty:.0f}" text-anchor="{anchor}">{m}</text>'
    s.append(near(pts[0], pts[1], m0, "middle"))
    s.append(near(pts[-1], pts[-2], m1, "middle"))
    if role:
        mx = (pts[-1][0] + pts[-2][0]) / 2
        my = (pts[-1][1] + pts[-2][1]) / 2 - 4
        s.append(f'<text class="role" x="{mx:.0f}" y="{my:.0f}" text-anchor="middle">&#171;{role}&#187;</text>')
    return "".join(s)

# ---- Enumerations ----
ENUMS = [
    ("FormStatus", ["draft","submitted","processing","extracted","under_review",
                    "reviewed","valid","invalid","returned","require_adjust",
                    "failed","overdue","gate_rejected"]),
    ("FormResultStatus", ["valid","need_review","invalid"]),
    ("ResidenceStatus", ["thuong_tru","tam_tru","tam_vang","khong_xac_dinh"]),
    ("RelationType", ["cha","me","vo_chong","con","chu_ho","anh_chi_em","khac"]),
    ("TempResidenceStatus", ["active","expired","cancelled"]),
    ("Gender", ["male","female"]),
    ("MaritalStatus", ["single","married"]),
    ("LifeStatus", ["alive","dead","missing"]),
    ("OrgRole", ["ward_officer"]),
]

def render_enums(x0, y0):
    s = [f'<text class="band" x="{x0}" y="{y0-12}">B&#7843;ng li&#7879;t k&#234; ki&#7875;u (enumeration)</text>']
    col_w, gap = 270, 18
    x, y = x0, y0
    per_row = 5
    row_h = 0
    for i, (name, lits) in enumerate(ENUMS):
        h = HDR + len(lits) * 13 + 8
        row_h = max(row_h, h)
        s.append(f'<rect class="ebox" x="{x}" y="{y}" width="{col_w}" height="{h}" rx="3"/>')
        s.append(f'<rect class="thd" x="{x}" y="{y}" width="{col_w}" height="{HDR}" rx="3"/>')
        s.append(f'<rect class="thd" x="{x}" y="{y+HDR-6}" width="{col_w}" height="6"/>')
        cx = x + col_w/2
        s.append(f'<text class="st" x="{cx}" y="{y+11}">&#171;enumeration&#187;</text>')
        s.append(f'<text class="tt" x="{cx}" y="{y+22}">{name}</text>')
        ly = y + HDR + 11
        for lit in lits:
            s.append(f'<text class="ef" x="{x+8}" y="{ly}">{lit}</text>')
            ly += 13
        if (i + 1) % per_row == 0:
            x = x0; y += row_h + gap; row_h = 0
        else:
            x += col_w + gap
    return "".join(s)

# ---- Build SVG ----
W, H = 1500, 2120
parts = [
    f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
    f'font-family="\'Times New Roman\', Times, serif">',
    '<title>So do lop (UML class diagram) - backend OCR tam tru</title>',
    f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>',
    f'''<style>
    .tbox {{ fill:#ffffff; stroke:{PURPLE}; stroke-width:1.2; }}
    .ebox {{ fill:#ffffff; stroke:{PURPLE}; stroke-width:1; }}
    .thd  {{ fill:{PURPLE}; }}
    .st   {{ fill:#d9cff2; font-size:8.5px; font-style:italic; text-anchor:middle; }}
    .tt   {{ fill:#ffffff; font-size:12.5px; font-weight:bold; text-anchor:middle; }}
    .ff   {{ fill:#1f1f1f; font-size:10.5px; }}
    .vis  {{ fill:{PURPLE}; font-weight:bold; }}
    .typ  {{ fill:#0b6b4f; }}
    .ef   {{ fill:#1f1f1f; font-size:9px; }}
    .rel  {{ stroke:{PURPLE}; stroke-width:1.1; fill:none; }}
    .ml   {{ fill:#1f1f1f; font-size:10.5px; font-weight:bold; }}
    .role {{ fill:#b23b00; font-size:9.5px; font-style:italic; }}
    .band {{ fill:{PURPLE}; font-size:13px; font-weight:bold; }}
    .cap  {{ fill:#1f1f1f; font-size:15px; font-style:italic; text-anchor:middle; }}
    </style>''',
]
# vẽ đường trước, hộp sau (hộp đè lên điểm cuối cho gọn)
for e in EDGES:
    parts.append(render_edge(*e))
for k in CLASSES:
    parts.append(render_class(k))
parts.append(render_enums(40, 1500))
parts.append(f'<text class="cap" x="{W/2}" y="{H-25}">H&#236;nh 4.x: S&#417; &#273;&#7891; l&#7899;p '
             f'(UML class diagram) &#8212; t&#7847;ng nghi&#7879;p v&#7909; backend. '
             f'&#9670; composition, &#9671; aggregation, &#8212;&#9657; association.</text>')
parts.append('</svg>')

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))
print("written", OUT)
