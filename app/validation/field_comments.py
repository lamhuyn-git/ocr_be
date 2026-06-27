from __future__ import annotations

from app.services.extraction_error_catalog import ErrorCode

# Message riêng theo từng trường × từng tình huống (ErrorCode), nội dung theo tài liệu nghiệp vụ.
# Khoá ngoài: label trường (xem field_rules.py). Khoá trong: ErrorCode.
# Tra không thấy -> comment_for() trả None -> nơi gọi fallback về verdict.reason chung.
_LOW_CONF = "Hệ thống không chắc về kết quả trích xuất"

FIELD_COMMENTS: dict[str, dict[ErrorCode, str]] = {
    # Cơ quan tiếp nhận
    "kinh_gui": {
        ErrorCode.not_found_in_db: "Không có thông tin cơ quan tiếp nhận trong CSDL",
        ErrorCode.match_ok: "Cơ quan tiếp nhận khớp với đơn đăng ký",
        ErrorCode.minor_diff: "Cơ quan tiếp nhận lệch nhẹ so với đơn đăng ký online",
        ErrorCode.mismatch: "Cơ quan tiếp nhận không khớp với đơn đăng ký online",
        ErrorCode.low_confidence: _LOW_CONF,
    },
    # CCCD người đăng ký
    "so_dinh_dan_ca_nhan": {
        ErrorCode.cccd_format: "Thông tin điền sai định dạng (phải đủ 12 số)",
        ErrorCode.registrant_found: "CCCD hợp lệ",
        ErrorCode.not_found_in_db: "CCCD không có trong cơ sở thông tin",
        ErrorCode.low_confidence: _LOW_CONF,
    },
    # Họ chữ đệm và tên người đăng ký
    "ho_chu_dem_va_ten": {
        ErrorCode.match_ok: "Họ chữ đệm và tên trong đơn CT01 khớp với thông tin điền online",
        ErrorCode.minor_diff: "Họ chữ đệm và tên trong đơn CT01 lệch nhẹ so với thông tin điền online",
        ErrorCode.mismatch: "Họ chữ đệm và tên trong đơn CT01 khác so với thông tin điền online",
        ErrorCode.low_confidence: _LOW_CONF,
        ErrorCode.cccd_invalid_cant_compare: "Chưa đối chiếu được vì CCCD không hợp lệ",
        ErrorCode.cccd_notfound_cant_compare: "Chưa đối chiếu được vì không tìm thấy CCCD trong CSDL",
    },
    # Ngày tháng năm sinh
    "ngay_thang_nam_sinh": {
        ErrorCode.date_format: "Ngày tháng năm sinh trong đơn CT01 bị sai định dạng ngày",
        ErrorCode.match_ok: "Ngày tháng năm sinh trong đơn CT01 khớp với thông tin điền online",
        ErrorCode.minor_diff: "Ngày tháng năm sinh trong đơn CT01 lệch nhẹ so với thông tin điền online",
        ErrorCode.mismatch: "Ngày tháng năm sinh trong đơn CT01 khác so với thông tin điền online",
        ErrorCode.low_confidence: _LOW_CONF,
        ErrorCode.cccd_invalid_cant_compare: "Chưa đối chiếu được vì CCCD không hợp lệ",
        ErrorCode.cccd_notfound_cant_compare: "Chưa đối chiếu được vì không tìm thấy CCCD trong CSDL",
    },
    # Giới tính
    "gioi_tinh": {
        ErrorCode.match_ok: "Giới tính trong đơn CT01 khớp với thông tin điền online",
        ErrorCode.minor_diff: "Giới tính trong đơn CT01 lệch nhẹ so với thông tin điền online",
        ErrorCode.mismatch: "Giới tính trong đơn CT01 khác so với thông tin điền online",
        ErrorCode.low_confidence: _LOW_CONF,
        ErrorCode.cccd_invalid_cant_compare: "Chưa đối chiếu được vì CCCD không hợp lệ",
        ErrorCode.cccd_notfound_cant_compare: "Chưa đối chiếu được vì không tìm thấy CCCD trong CSDL",
    },
    # Số điện thoại liên hệ (field mềm)
    "so_dien_thoai_lien_he": {
        ErrorCode.phone_format: "Số điện thoại trong đơn CT01 sai định dạng",
        ErrorCode.match_ok: "Số điện thoại trong đơn CT01 khớp với thông tin điền online",
        ErrorCode.minor_diff: "Số điện thoại trong đơn CT01 lệch nhẹ so với thông tin điền online",
        ErrorCode.mismatch: "Số điện thoại trong đơn CT01 khác so với thông tin điền online",
        ErrorCode.low_confidence: _LOW_CONF,
        ErrorCode.cccd_invalid_cant_compare: "Chưa đối chiếu được vì CCCD không hợp lệ",
        ErrorCode.cccd_notfound_cant_compare: "Chưa đối chiếu được vì không tìm thấy CCCD trong CSDL",
    },
    # Email (field mềm)
    "email": {
        ErrorCode.match_ok: "Email khớp với thông tin điền online",
        ErrorCode.minor_diff: "Email lệch nhẹ so với thông tin điền online (có thể đã đổi)",
        ErrorCode.mismatch: "Email khác so với thông tin điền online (có thể đã đổi)",
        ErrorCode.low_confidence: _LOW_CONF,
        ErrorCode.cccd_invalid_cant_compare: "Chưa đối chiếu được vì CCCD không hợp lệ",
        ErrorCode.cccd_notfound_cant_compare: "Chưa đối chiếu được vì không tìm thấy CCCD trong CSDL",
    },
    # Họ chữ đệm và tên chủ hộ
    "ho_chu_dem_va_ten_chu_ho": {
        ErrorCode.match_ok: "Họ chữ đệm và tên chủ hộ khớp với người ĐK",
        ErrorCode.minor_diff: "Họ chữ đệm và tên chủ hộ lệch nhẹ so với người ĐK",
        ErrorCode.mismatch: "Họ chữ đệm và tên chủ hộ khác so với người ĐK",
        ErrorCode.low_confidence: _LOW_CONF,
    },
    # CCCD chủ hộ
    "so_dinh_dan_ca_nhan_cua_chu_ho": {
        ErrorCode.cccd_format: "CCCD chủ hộ sai định dạng (phải đủ 12 số)",
        ErrorCode.cccd_dk_bad_cant_compare_chuho: "Chưa so sánh được vì CCCD người đăng ký sai định dạng",
        ErrorCode.match_ok: "CCCD chủ hộ khớp với người ĐK",
        ErrorCode.minor_diff: "CCCD chủ hộ lệch nhẹ so với người ĐK",
        ErrorCode.mismatch: "CCCD chủ hộ khác so với người ĐK",
        ErrorCode.low_confidence: _LOW_CONF,
    },
    # Mối quan hệ với chủ hộ (phải là "chủ hộ")
    "moi_quan_he_voi_chu_ho": {
        ErrorCode.match_ok: "Mối quan hệ với chủ hộ hợp lệ",
        ErrorCode.minor_diff: "Mối quan hệ với chủ hộ không hợp lệ (phải là chủ hộ)",
        ErrorCode.mismatch: "Mối quan hệ với chủ hộ không hợp lệ (phải là chủ hộ)",
        ErrorCode.low_confidence: _LOW_CONF,
    },
    # Nội dung đề nghị (chứa địa chỉ đăng ký)
    "noi_dung_de_nghi": {
        ErrorCode.no_online_address: "Địa chỉ đề nghị tạm trú không có thông tin để đối chiếu",
        ErrorCode.match_ok: "Địa chỉ đề nghị tạm trú khớp với thông tin được điền online",
        ErrorCode.minor_diff: "Địa chỉ đề nghị tạm trú lệch nhẹ so với thông tin được điền online",
        ErrorCode.mismatch: "Địa chỉ đề nghị tạm trú khác so với thông tin được điền online",
        ErrorCode.low_confidence: _LOW_CONF,
    },
    # Thành viên cùng thay đổi
    "thanh_vien_cung_thay_doi": {
        ErrorCode.thanh_vien_manual: "Cán bộ tự soát",
    },
}


def comment_for(field_label: str, code) -> str | None:
    """Trả message riêng cho (trường, tình huống). Không có -> None để nơi gọi fallback."""
    if not field_label or code is None:
        return None
    return FIELD_COMMENTS.get(field_label, {}).get(code)
