from __future__ import annotations
from .decision import (PASS, REVIEW, ERROR, Verdict, decide_match, not_found, validate_number_format)
from . import field_rules as FR
from .text_match import digits_only
from .thresholds import LIST_MATCH_DIST_MAX


FIELD_THANH_VIEN = "thanh_vien_cung_thay_doi"


GROUP_FIELDS = {
    "co_quan_thuc_hien": [FR.FIELD_CO_QUAN],
    "thong_tin_ho_thay_doi": [FR.KEY_CCCD_NGUOI_DK, *FR.CITIZEN_COMPARE],
    "thong_tin_de_nghi": [FR.FIELD_NOI_DUNG, "ho_chu_dem_va_ten_chu_ho", FR.KEY_CCCD_CHU_HO],
    "thanh_vien_cung_thay_doi": [FIELD_THANH_VIEN],
}


def _txt(ocr_fields, name):
    f = ocr_fields.get(name) or {}
    return (f.get("text", "") if isinstance(f, dict) else str(f)), \
           (f.get("confidence") if isinstance(f, dict) else None)


# Validate Cơ quan thực hiện
def validate_co_quan(ocr_fields, gt) -> dict[str, Verdict]:
    # Lấy text và conf từ extracted "kinh_gui"
    text, conf = _txt(ocr_fields, FR.FIELD_CO_QUAN)

    # Tìm tên cơ quan trong DB gần nhất với giá trị OCR đọc được
    best, distance = gt.lookup_authority(text)

    if best is None or distance > LIST_MATCH_DIST_MAX:
        v = not_found(text, "bảng cơ quan")
    else:
        v = decide_match(text, best, conf=conf, distance=distance)
    return {FR.FIELD_CO_QUAN: v}


# Validate Thông tin hộ thay đổi (người đăng ký, Mục 1-6)
def validate_ho_thay_doi(ocr_fields, gt) -> dict[str, Verdict]:
    val_resuls: dict[str, Verdict] = {}

    # Lấy kết quả trích xuất của so_dinh_danh_ca_nhan
    cccd_text, _ = _txt(ocr_fields, FR.KEY_CCCD_NGUOI_DK)

    # Kiểm tra CCCD trích xuất có đúng format 12 số không
    fmt = validate_number_format(cccd_text, "cccd")
    if fmt is not None:
        val_resuls[FR.KEY_CCCD_NGUOI_DK] = fmt    # sai format thì dừng luôn
        # Đánh dấu các field phụ thuộc là REVIEW (không thể đối chiếu khi CCCD sai)
        for fname in FR.CITIZEN_COMPARE:
            ftext, _ = _txt(ocr_fields, fname)
            val_resuls[fname] = Verdict(REVIEW, "CCCD không hợp lệ — không thể đối chiếu thông tin", None, None, None, ftext)
    else:
        citizen_gt = gt.lookup_citizen(cccd_text)    # Đúng format thì dô lục coi có key là CCCD không
        if citizen_gt:
            val_resuls[FR.KEY_CCCD_NGUOI_DK] = Verdict(PASS, "CCCD có tồn tại trong CSDL",None, 0.0, cccd_text, cccd_text)
            # Dò tiếp các field ho_ten", "ngay_sinh", "gioi_tinh", "so_dien_thoai", "email"
            for fname, dbkey in FR.CITIZEN_COMPARE.items():
                ftext, fconf = _txt(ocr_fields, fname)
                kind = FR.NUMBER_KIND.get(fname)
                if kind:
                    bad = validate_number_format(ftext, kind)
                    if bad is not None:
                        val_resuls[fname] = bad
                        continue
                # đối chiếu OCR vs CSDL
                val_resuls[fname] = decide_match(ftext, citizen_gt.get(dbkey, ""), fconf, soft=(fname in FR.SOFT_FIELDS))
        else:
            val_resuls[FR.KEY_CCCD_NGUOI_DK] = not_found(cccd_text, "CCCD như trên CT01")
            # Đánh dấu các field phụ thuộc là REVIEW (không tìm thấy citizen để đối chiếu)
            for fname in FR.CITIZEN_COMPARE:
                ftext, _ = _txt(ocr_fields, fname)
                val_resuls[fname] = Verdict(REVIEW, "CCCD không tìm thấy trong CSDL — không thể đối chiếu thông tin", None, None, None, ftext)
    return val_resuls


# Validate Thông tin đề nghị
def validate_de_nghi(ocr_fields, register_content) -> dict[str, Verdict]:
    val_resuls: dict[str, Verdict] = {}

    # check địa chỉ OCR (noi_dung_de_nghi) vs địa chỉ khai online (register_content: 1 chuỗi).
    nd_text, nd_conf = _txt(ocr_fields, FR.FIELD_NOI_DUNG)
    gt_addr = str(register_content or "").strip()
    if not gt_addr:
        val_resuls[FR.FIELD_NOI_DUNG] = Verdict(REVIEW, "không có địa chỉ khai online để đối chiếu",None, None, None, nd_text)
    else:
        # Địa chỉ gõ tay → lệch coi như cần soát (soft), không đánh invalid cứng.
        val_resuls[FR.FIELD_NOI_DUNG] = decide_match(nd_text, gt_addr, nd_conf, soft=True)

    # 2) Người đăng ký có phải chủ hộ không: so tên + CCCD người ĐK với chủ hộ (đều từ OCR).
    ten_dk, _ = _txt(ocr_fields, "ho_chu_dem_va_ten")
    ten_ch, ten_ch_conf = _txt(ocr_fields, "ho_chu_dem_va_ten_chu_ho")
    cccd_dk, _ = _txt(ocr_fields, FR.KEY_CCCD_NGUOI_DK)
    cccd_ch, cccd_ch_conf = _txt(ocr_fields, FR.KEY_CCCD_CHU_HO)

    # tên chủ hộ == tên người ĐK ? (khác nhau → cần soát, không invalid cứng)
    val_resuls["ho_chu_dem_va_ten_chu_ho"] = decide_match(ten_ch, ten_dk, ten_ch_conf, soft=True)

    # CCCD chủ hộ: đúng format trước, rồi == CCCD người ĐK ?
    bad = validate_number_format(cccd_ch, "cccd")
    if bad is not None:
        val_resuls[FR.KEY_CCCD_CHU_HO] = bad
    elif validate_number_format(cccd_dk, "cccd") is not None:
        val_resuls[FR.KEY_CCCD_CHU_HO] = Verdict(REVIEW, "CCCD người đăng ký sai định dạng — chưa so được với chủ hộ",
                                                 None, None, None, cccd_ch)
    else:
        val_resuls[FR.KEY_CCCD_CHU_HO] = decide_match(digits_only(cccd_ch), digits_only(cccd_dk),
                                                      cccd_ch_conf, soft=True)

    # Mối quan hệ với chủ hộ: bắt buộc phải là "chủ hộ"
    qh_text, qh_conf = _txt(ocr_fields, FR.FIELD_QUAN_HE_CHU_HO)
    if qh_text:
        val_resuls[FR.FIELD_QUAN_HE_CHU_HO] = decide_match(
            qh_text, FR.EXPECTED_QUAN_HE_CHU_HO, qh_conf,
        )
    return val_resuls


# Thành viên cùng thay đổi (tạm để need_review)
def validate_thanh_vien(ocr_fields) -> dict[str, Verdict]:
    if FIELD_THANH_VIEN not in ocr_fields:
        return {}
    text, _ = _txt(ocr_fields, FIELD_THANH_VIEN)
    return {FIELD_THANH_VIEN: Verdict(REVIEW, "thành viên cùng thay đổi — cán bộ tự soát",
                                      None, None, None, text)}
