from __future__ import annotations

import enum
from dataclasses import dataclass


class ErrorLayer(str, enum.Enum):
    pre_extract = "pre_extract"   # Lỗi thuộc về cổng tiền trích xuất (trước OCR): thông tin người thay đổi cư trú trong đơn online khác với CSDL và địa chỉ mới không thuộc phường
    same_person = "same_person"   # Lỗi thuộc về tầng 1: thông tin trong CT01 != thông tin trong đơn online
    field_match = "field_match"   # Lỗi thuộc tầng 2:  lỗi khi đối chiếu từng field được trích xuất vs CSDL
    system      = "system"        # Lỗi hệ thống: liên quan đến vòng đời (pipeline, quá hạn)


class Severity(str, enum.Enum):
    hard = "hard"   # chặn cổng (gate_rejected) hoặc field invalid
    soft = "soft"   # cảnh báo / cần soát (need_review)
    info = "info"   # pass / thông tin


class ErrorCode(str, enum.Enum):
    # pre_extract
    registered_user_missing   = "registered_user_missing"
    registered_user_not_found = "registered_user_not_found"
    registered_user_name      = "registered_user_name"
    registered_user_birth     = "registered_user_birth"
    registered_user_gender    = "registered_user_gender"
    registered_user_phone     = "registered_user_phone"
    registered_user_mail      = "registered_user_mail"
    location_not_in_ward      = "location_not_in_ward"
    # same_person
    ct01_cccd_mismatch        = "ct01_cccd_mismatch"
    ct01_person_unverified    = "ct01_person_unverified"
    # field_match
    low_confidence            = "low_confidence"
    minor_diff                = "minor_diff"
    mismatch                  = "mismatch"
    not_found_in_db           = "not_found_in_db"
    cccd_format               = "cccd_format"
    phone_format              = "phone_format"
    date_format               = "date_format"
    cccd_invalid_cant_compare = "cccd_invalid_cant_compare"
    cccd_notfound_cant_compare = "cccd_notfound_cant_compare"
    no_online_address         = "no_online_address"
    cccd_dk_bad_cant_compare_chuho = "cccd_dk_bad_cant_compare_chuho"
    chuho_ref_invalid         = "chuho_ref_invalid"
    thanh_vien_manual         = "thanh_vien_manual"
    match_ok                  = "match_ok"
    registrant_found          = "registrant_found"
    # system
    pipeline_failed           = "pipeline_failed"
    overdue                   = "overdue"


@dataclass(frozen=True)
class ExtractionError:
    code: ErrorCode
    layer: ErrorLayer
    severity: Severity
    scope: str          # "form" | "field"
    message: str        # thông điệp hiển thị cho cán bộ
    note: str = ""      # mô tả điều kiện kích hoạt


_ERRORS: list[ExtractionError] = [

    ExtractionError(ErrorCode.registered_user_missing, ErrorLayer.pre_extract, Severity.hard, "form", "Chưa khai số định danh người thay đổi cư trú. Vui lòng kiểm tra lại thông tin điền trên đơn đăng ký tạm trú online.", "tamtru.registered_user_cccd trống"),
    ExtractionError(ErrorCode.registered_user_not_found, ErrorLayer.pre_extract, Severity.hard, "form", "Người/Hộ yêu cầu thay đổi cư trú không có trong CSDL (CCCD khai online không tồn tại trong bảng thông tin người dân).", "CCCD khai online không tồn tại trong bảng citizens"),
    ExtractionError(ErrorCode.registered_user_name, ErrorLayer.pre_extract, Severity.hard, "form", "Họ tên người đăng ký trong đơn online không khớp CSDL", "distance(tên online, CSDL) > NAME_MATCH_DIST_MAX"),
    ExtractionError(ErrorCode.registered_user_birth, ErrorLayer.pre_extract, Severity.hard, "form", "Ngày sinh người đăng ký trong đơn online không khớp CSDL", "ngày sinh online ≠ CSDL"),
    ExtractionError(ErrorCode.registered_user_gender, ErrorLayer.pre_extract, Severity.hard, "form", "Giới tính người đăng ký không khớp CSDL", "giới tính online ≠ CSDL"),
    ExtractionError(ErrorCode.registered_user_phone, ErrorLayer.pre_extract, Severity.soft, "form", "Số điện thoại người đăng ký trong đơn online không khớp CSDL", "Trường soft nên KHÔNG chặn, chỉ ghi chú (có thể đã đổi hợp lệ)"),
    ExtractionError(ErrorCode.registered_user_mail, ErrorLayer.pre_extract, Severity.soft, "form", "Email người đăng ký trong đơn online không khớp CSDL", "Trường soft nên KHÔNG chặn, chỉ ghi chú"),
    ExtractionError(ErrorCode.location_not_in_ward, ErrorLayer.pre_extract, Severity.hard, "form", "Địa chỉ đăng ký trong đơn online không thuộc phường tiếp nhận", "location_register không khớp (fuzzy) địa chỉ nào của phường"),

    ExtractionError(ErrorCode.ct01_cccd_mismatch, ErrorLayer.same_person, Severity.hard, "form", "Thông tin người khai trong CT01 và người trong tờ khai online là KHÔNG cùng một người. Vui lòng xem lại. ", "OCR CCCD đủ 12 số nhưng ≠ registered_user_cccd"),
    ExtractionError(ErrorCode.ct01_person_unverified, ErrorLayer.same_person, Severity.hard, "form", "Thông tin người khai trong CT01 và người trong tờ khai online là KHÔNG cùng một người. Vui lòng xem lại", "OCR CCCD không đủ 12 số và họ tên cũng không khớp"),

    ExtractionError(ErrorCode.low_confidence, ErrorLayer.field_match, Severity.soft, "field", "Hệ thống không chắc về kết quả", "confidence OCR < OCR_CONF_MIN (0.80)"),
    ExtractionError(ErrorCode.minor_diff, ErrorLayer.field_match, Severity.soft, "field", "Có sự chênh lệch nhỏ so với CSDL", "0 < distance ≤ NEAR_DIST_MAX (0.22)"),
    ExtractionError(ErrorCode.mismatch, ErrorLayer.field_match, Severity.hard, "field", "đọc rõ nhưng khác CSDL", "distance > NEAR_DIST_MAX — field cứng → invalid; field mềm → need_review"),
    ExtractionError(ErrorCode.not_found_in_db, ErrorLayer.field_match, Severity.hard, "field", "không tìm thấy trong CSDL ({what})", "lookup thất bại (vd cơ quan, CCCD như trên CT01)"),
    ExtractionError(ErrorCode.cccd_format, ErrorLayer.field_match, Severity.hard, "field", "CCCD phải 12 chữ số (đọc {n})", "so_dinh_dan_ca_nhan / ..._chu_ho sai định dạng"),
    ExtractionError(ErrorCode.phone_format, ErrorLayer.field_match, Severity.hard, "field", "số điện thoại không hợp lệ ({n} chữ số)", "so_dien_thoai_lien_he ngoài 9–11 chữ số"),
    ExtractionError(ErrorCode.date_format, ErrorLayer.field_match, Severity.hard, "field", "ngày tháng không hợp lệ", "ngay_thang_nam_sinh không parse được"),
    ExtractionError(ErrorCode.cccd_invalid_cant_compare, ErrorLayer.field_match, Severity.soft, "field", "CCCD không hợp lệ — không thể đối chiếu thông tin", "field phụ thuộc khi CCCD người ĐK sai format"),
    ExtractionError(ErrorCode.cccd_notfound_cant_compare, ErrorLayer.field_match, Severity.soft, "field", "CCCD không tìm thấy trong CSDL — không thể đối chiếu thông tin", "field phụ thuộc khi không thấy citizen"),
    ExtractionError(ErrorCode.no_online_address, ErrorLayer.field_match, Severity.soft, "field", "không có địa chỉ khai online để đối chiếu", "register_content trống (noi_dung_de_nghi)"),
    ExtractionError(ErrorCode.cccd_dk_bad_cant_compare_chuho, ErrorLayer.field_match, Severity.soft, "field", "CCCD người đăng ký sai định dạng — chưa so được với chủ hộ", "so_dinh_dan_ca_nhan_cua_chu_ho"),
    ExtractionError(ErrorCode.chuho_ref_invalid, ErrorLayer.field_match, Severity.soft, "field", "CCCD người đăng ký không hợp lệ — không thể dùng làm tham chiếu cho chủ hộ", "hạ cccd_chu_ho từ PASS→REVIEW khi CCCD người ĐK là ERROR"),
    ExtractionError(ErrorCode.thanh_vien_manual, ErrorLayer.field_match, Severity.soft, "field", "thành viên cùng thay đổi — cán bộ tự soát", "thanh_vien_cung_thay_doi luôn need_review"),
    ExtractionError(ErrorCode.match_ok, ErrorLayer.field_match, Severity.info, "field", "khớp với CSDL", "distance = 0"),
    ExtractionError(ErrorCode.registrant_found, ErrorLayer.field_match, Severity.info, "field", "CCCD có tồn tại trong CSDL", "CCCD người ĐK tìm thấy trong CSDL"),

    ExtractionError(ErrorCode.pipeline_failed, ErrorLayer.system, Severity.hard, "form", "Lỗi trích xuất OCR", "run_form_pipeline ném exception → status=failed"),
    ExtractionError(ErrorCode.overdue, ErrorLayer.system, Severity.soft, "form", "Hồ sơ quá hạn xử lý", "quá overdue_days chưa xử lý → status=overdue"),
]

# code → ExtractionError (tra cứu nhanh). Key là ErrorCode (str-enum) — tra bằng str vẫn được.
EXTRACTION_ERROR_CATALOG: dict[ErrorCode, ExtractionError] = {e.code: e for e in _ERRORS}


def get_error(code: str) -> ExtractionError | None:
    return EXTRACTION_ERROR_CATALOG.get(code)


def errors_by_layer(layer: ErrorLayer) -> list[ExtractionError]:
    return [e for e in _ERRORS if e.layer == layer]
