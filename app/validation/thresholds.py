# Confidence tối thiểu để tin kết quả OCR; dưới mức này → need_review (đọc chưa chắc).
OCR_CONF_MIN = 0.80

# Distance tối đa vẫn coi là "lệch nhỏ" (nghi nhiễu OCR) → need_review thay vì error.
NEAR_DIST_MAX = 0.22

# Distance tối đa coi như KHỚP khi dò trong một danh sách (tên cơ quan, địa chỉ phường).
LIST_MATCH_DIST_MAX = 0.45

# Distance tối đa coi như khớp họ tên người đăng ký (chặt hơn vì so 1-1, không phải dò danh sách).
NAME_MATCH_DIST_MAX = 0.20
