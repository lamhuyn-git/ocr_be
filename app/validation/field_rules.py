GROUPS = {
    1: "Cơ quan thực hiện",
    2: "Thông tin người đăng ký",
    3: "Thông tin đăng ký tạm trú",
}

CITIZEN_COMPARE = {
    "ho_chu_dem_va_ten": "ho_ten",
    "ngay_thang_nam_sinh": "ngay_sinh",
    "gioi_tinh": "gioi_tinh",
    "so_dien_thoai_lien_he": "so_dien_thoai",   # soft
    "email": "email",                            # soft
}

# Field "mềm" — mâu thuẫn → REVIEW (không ERROR), vì người dân có thể đã đổi.
SOFT_FIELDS = {"so_dien_thoai_lien_he", "email"}

# Field SỐ — validate format cứng trước khi đối chiếu.
NUMBER_KIND = {
    "so_dinh_dan_ca_nhan": "cccd",
    "so_dinh_dan_ca_nhan_cua_chu_ho": "cccd",
    "so_dien_thoai_lien_he": "phone",
    "ngay_thang_nam_sinh": "date",
}

KEY_CCCD_NGUOI_DK = "so_dinh_dan_ca_nhan"
KEY_CCCD_CHU_HO = "so_dinh_dan_ca_nhan_cua_chu_ho"
FIELD_CO_QUAN = "kinh_gui"               # "Công an Phường X" → bảng cơ quan
FIELD_NOI_DUNG = "noi_dung_de_nghi"      # chứa địa chỉ đăng ký
FIELD_QUAN_HE_CHU_HO = "moi_quan_he_voi_chu_ho"   # phải là "chủ hộ"
EXPECTED_QUAN_HE_CHU_HO = "chủ hộ"
