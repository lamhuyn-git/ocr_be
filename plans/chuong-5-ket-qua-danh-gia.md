# CHƯƠNG 5. KẾT QUẢ VÀ ĐÁNH GIÁ

> Toàn bộ số liệu trong chương được trích xuất từ kết quả đánh giá định lượng của
> mô hình nhận dạng `paddle_v9` (đường dẫn `debug_output/output_final/paddle_v9/eval_results.json`)
> và mô hình đối chứng `trocr` (`debug_output/output_final/trocr/eval_results.json`).
> Hai mô hình được đánh giá trên **cùng một tập kiểm thử** gồm **264 mẫu trường dữ liệu**,
> trích từ **24 biểu mẫu** Tờ khai thay đổi thông tin cư trú (mẫu CT01 theo Thông tư
> 53/2025/TT-BCA), mỗi phiếu gồm 11 trường thông tin được đánh giá.

---

## 5.1. Kết quả đánh giá tổng thể

### 5.1.1. Tập dữ liệu kiểm thử

Để phản ánh sát điều kiện sử dụng thực tế (vừa quét máy, vừa chụp bằng điện thoại,
chất lượng ảnh cao/thấp; vừa chữ in, vừa chữ viết tay), tập kiểm thử được tổ chức theo
**năm điều kiện thu nhận ảnh** như Bảng 5.1.

**Bảng 5.1.** Cấu trúc tập kiểm thử theo điều kiện thu nhận ảnh

| Điều kiện ảnh | Loại chữ | Cách thu nhận | Số phiếu | Số mẫu trường |
|---------------|---------|----------------|:--------:|:-------------:|
| `hand_phone_good` | Viết tay | Chụp điện thoại, chất lượng tốt | 6 | 66 |
| `hand_phone_low`  | Viết tay | Chụp điện thoại, chất lượng thấp | 2 | 22 |
| `hand_scan`       | Viết tay | Quét máy (scan) | 6 | 66 |
| `print_phone_good`| In ấn   | Chụp điện thoại, chất lượng tốt | 5 | 55 |
| `print_scan`      | In ấn   | Quét máy (scan) | 5 | 55 |
| **Tổng** | | | **24** | **264** |

Việc phân tách theo điều kiện ảnh cho phép đánh giá **độ bền vững (*robustness*)** của
hệ thống trước các nguồn nhiễu khác nhau (nền giấy, độ nghiêng, độ mờ, ánh sáng khi
chụp điện thoại), thay vì chỉ đánh giá trên ảnh quét lý tưởng.

### 5.1.2. Phương pháp và độ đo đánh giá

Nghiên cứu sử dụng bốn độ đo tiêu chuẩn trong nhận dạng văn bản, tính ở mức từng trường
dữ liệu giữa kết quả nhận dạng (*prediction*) và nhãn chuẩn (*ground truth*):

| Độ đo | Định nghĩa | Ý nghĩa |
|-------|-----------|---------|
| **CER** (*Character Error Rate*) | Khoảng cách Levenshtein ở mức **ký tự** chia độ dài chuỗi chuẩn | Tỷ lệ lỗi ký tự; càng thấp càng tốt |
| **WER** (*Word Error Rate*) | Khoảng cách Levenshtein ở mức **từ** chia số từ chuỗi chuẩn | Tỷ lệ lỗi từ; càng thấp càng tốt |
| **NED** (*Normalized Edit Distance similarity*) | $1 - \dfrac{\text{Levenshtein}}{\max(\lvert gt\rvert,\lvert pred\rvert)}$ | Độ tương đồng chuẩn hóa; càng cao càng tốt |
| **EM** (*Exact Match*) | Tỷ lệ trường nhận dạng **trùng khớp tuyệt đối** với nhãn chuẩn | Độ chính xác mức trường; càng cao càng tốt |

Trước khi tính độ đo, cả hai chuỗi được chuẩn hóa thống nhất (loại bỏ dấu phẩy thừa,
đưa về chữ thường) để so sánh công bằng giữa hai mô hình. Mỗi độ đo báo cáo kèm **giá
trị trung bình** và **độ lệch chuẩn** nhằm phản ánh mức độ phân tán của lỗi.

### 5.1.3. Kết quả tổng thể của mô hình PaddleOCR v9

**Bảng 5.2.** Kết quả đánh giá tổng thể của mô hình PaddleOCR v9 (264 mẫu)

| Độ đo | Trung bình | Độ lệch chuẩn |
|-------|:----------:|:-------------:|
| CER ↓ | **0,0686** (6,86%) | — |
| WER ↓ | 0,2249 (22,49%) | — |
| NED ↑ | **0,9329** (93,29%) | — |
| EM ↑  | **0,6250** (62,50%) | — |

Trên toàn bộ 264 mẫu thuộc 5 điều kiện ảnh, mô hình đạt **CER trung bình 6,86%** (độ
chính xác ký tự ≈ 93%), **NED 93,29%** và **EM 62,50%**. Kết quả này khẳng định hệ
thống duy trì chất lượng nhận dạng tốt và ổn định **ngay cả khi mở rộng tập kiểm thử
sang ảnh chụp điện thoại và ảnh chất lượng thấp** — vốn khó hơn nhiều so với ảnh quét.

Như đã quan sát, khoảng cách giữa CER thấp (6,86%) và EM trung bình (62,50%) là đặc
trưng của tiếng Việt: chỉ cần sai một dấu thanh hay dấu mũ (ví dụ "Mẫn" → "Măn") là
trường bị tính sai tuyệt đối dù sai số ký tự rất nhỏ.

### 5.1.4. Kết quả theo điều kiện ảnh

**Bảng 5.3.** Kết quả phân tách theo từng điều kiện thu nhận ảnh

| Điều kiện ảnh | Số mẫu | CER ↓ | WER ↓ | NED ↑ | EM ↑ |
|---------------|:------:|:-----:|:-----:|:-----:|:----:|
| `print_phone_good` | 55 | **0,0306** | 0,1283 | **0,9695** | 0,6909 |
| `print_scan`       | 55 | 0,0544 | 0,1401 | 0,9461 | **0,7091** |
| `hand_scan`        | 66 | 0,0713 | 0,3155 | 0,9307 | 0,5303 |
| `hand_phone_good`  | 66 | 0,0982 | 0,2896 | 0,9044 | 0,5758 |
| `hand_phone_low`   | 22 | 0,1024 | 0,2123 | 0,9005 | 0,6818 |

Để dễ so sánh, Bảng 5.4 gộp về hai nhóm thô theo loại chữ:

**Bảng 5.4.** Kết quả theo loại chữ (gộp)

| Nhóm | Số mẫu | CER ↓ | WER ↓ | NED ↑ | EM ↑ |
|------|:------:|:-----:|:-----:|:-----:|:----:|
| Chữ in (*print*)   | 110 | **0,0425** (4,25%) | 0,1342 | 0,9578 | **0,7000** |
| Chữ viết tay (*hand*) | 154 | 0,0873 (8,73%) | 0,2896 | 0,9151 | 0,5714 |

Các nhận xét quan trọng:

**(a) Loại chữ là yếu tố ảnh hưởng mạnh nhất.** Chữ in đạt CER 4,25% và EM 70,00%, tốt
hơn rõ rệt chữ viết tay (CER 8,73%, EM 57,14%). Điều này phù hợp với bản chất bài toán:
chữ viết tay có biến thể nét lớn, đặc biệt ở các trường số và dấu thanh.

**(b) Với chữ in, ảnh chụp điện thoại chất lượng tốt không hề kém ảnh quét — thậm chí
tốt hơn.** `print_phone_good` đạt CER 3,06% (thấp nhất toàn tập), nhỉnh hơn `print_scan`
(5,44%). Nguyên nhân là ảnh điện thoại độ phân giải cao, tương phản tốt, trong khi một
số ảnh quét bị nhiễu nền. Đây là kết quả tích cực cho khả năng triển khai thực tế (người
dùng chỉ cần chụp ảnh phiếu in).

**(c) Với chữ viết tay, ảnh quét vẫn cho kết quả tốt nhất.** `hand_scan` đạt CER 7,13%,
trong khi ảnh chụp điện thoại tăng lỗi ký tự (`hand_phone_good` 9,82%, `hand_phone_low`
10,24%) do nghiêng, mờ và biến dạng phối cảnh khiến nét chữ tay vốn đã khó càng khó hơn.

**(d) Hệ thống suy giảm có kiểm soát (*graceful degradation*) ở ảnh chất lượng thấp.**
Dù `hand_phone_low` có CER cao nhất (10,24%), NED vẫn đạt 90,05% — nội dung về cơ bản
vẫn đọc hiểu được. *Lưu ý:* điều kiện này chỉ có 2 phiếu (22 mẫu) nên các con số mang
tính tham khảo, độ tin cậy thống kê thấp.

### 5.1.5. Kết quả chi tiết theo từng trường thông tin

**Bảng 5.5.** Kết quả đánh giá theo từng trường (PaddleOCR v9, 24 mẫu/trường, sắp theo CER tăng dần)

| Trường thông tin | CER ↓ | WER ↓ | NED ↑ | EM ↑ |
|------------------|:-----:|:-----:|:-----:|:----:|
| Mối quan hệ với chủ hộ | **0,0000** | 0,0000 | 1,0000 | **1,0000** |
| Số điện thoại liên hệ | 0,0042 | 0,0417 | 0,9958 | 0,9583 |
| Kính gửi | 0,0194 | 0,0811 | 0,9808 | 0,4583 |
| Số định danh cá nhân của chủ hộ | 0,0486 | 0,3333 | 0,9519 | 0,6667 |
| Họ, chữ đệm và tên chủ hộ | 0,0506 | 0,2118 | 0,9501 | 0,5417 |
| Email | 0,0734 | 0,5000 | 0,9284 | 0,5000 |
| Họ, chữ đệm và tên | 0,0781 | 0,3090 | 0,9238 | 0,4583 |
| Giới tính | 0,0833 | 0,0833 | 0,9167 | 0,9167 |
| Số định danh cá nhân | 0,1250 | 0,2917 | 0,8761 | 0,7083 |
| Nội dung đề nghị | 0,1350 | 0,2882 | 0,8758 | **0,0000** |
| Ngày, tháng, năm sinh | 0,1375 | 0,3333 | 0,8625 | 0,6667 |

Các quy luật rút ra:

**(a) Trường có cấu trúc cố định, ngắn gọn đạt kết quả tốt nhất.** "Mối quan hệ với chủ
hộ" đạt tuyệt đối (CER 0%, EM 100%); "Số điện thoại liên hệ" gần như tuyệt đối (CER
0,42%, EM 95,83%); "Giới tính" đạt EM 91,67%. Đây là các trường miền giá trị hẹp.

**(b) Trường số nhiều chữ số nhạy cảm với nhiễu ảnh.** "Số định danh cá nhân" (CER
12,50%) và "Ngày, tháng, năm sinh" (CER 13,75%) có CER cao hơn hẳn phần còn lại. Khi mở
rộng sang ảnh chụp điện thoại và viết tay, các chữ số dễ bị nhầm (`1`↔`L`, `0`↔`O`, mất/
thừa ký tự `/`), kéo CER tăng so với khi chỉ đánh giá trên ảnh quét.

**(c) Trường "Nội dung đề nghị" có EM = 0% dù CER chỉ 13,50%.** Đây là trường văn bản
dài nhất (địa chỉ đầy đủ, >90 ký tự); xác suất sai ít nhất một ký tự gần như chắc chắn
nên không mẫu nào khớp tuyệt đối. NED vẫn đạt 87,58% — đọc hiểu và hiệu chỉnh được.

**(d) WER cao bất thường ở trường định danh liền mạch.** Email có WER 50,00% dù CER chỉ
7,34%: vì email tính như một "từ" duy nhất, sai một ký tự là cả từ sai. WER do đó không
phản ánh đúng chất lượng nhận dạng với loại trường này.

---

## 5.2. So sánh kết quả đánh giá với mô hình TrOCR

### 5.2.1. Bối cảnh so sánh

Để khẳng định lựa chọn kiến trúc, nghiên cứu đối chứng PaddleOCR v9 với **TrOCR**
(*Transformer-based OCR*, encoder thị giác + decoder ngôn ngữ) đã tinh chỉnh trên dữ
liệu tiếng Việt (`trocr_vi`). Hai mô hình được đánh giá trên **cùng 264 mẫu**, **cùng độ
đo** và **cùng quy trình chuẩn hóa**, bảo đảm công bằng. Để xử lý văn bản nhiều dòng,
TrOCR đọc theo từng dòng do PaddleOCR phát hiện rồi ghép lại.

### 5.2.2. So sánh tổng thể

**Bảng 5.6.** So sánh kết quả tổng thể PaddleOCR v9 và TrOCR (264 mẫu)

| Độ đo | PaddleOCR v9 | TrOCR | Chênh lệch |
|-------|:-----------:|:-----:|:----------:|
| CER ↓ | **0,0686** | 0,0963 | −0,0277 (giảm ~28,8% tương đối) |
| WER ↓ | **0,2249** | 0,3480 | −0,1231 |
| NED ↑ | **0,9329** | 0,9055 | +0,0274 |
| EM ↑  | **0,6250** | 0,4811 | +0,1439 |

PaddleOCR v9 **vượt trội trên cả bốn độ đo**: tỷ lệ lỗi ký tự thấp hơn 2,77 điểm phần
trăm (giảm ~28,8% tương đối), tỷ lệ lỗi từ thấp hơn 12,31 điểm phần trăm, độ tương đồng
NED cao hơn 2,74 điểm, và đặc biệt độ chính xác mức trường (EM) cao hơn **14,39 điểm
phần trăm**. Đây là cơ sở định lượng vững chắc cho việc chọn PaddleOCR làm mô hình nhận
dạng chính của hệ thống.

### 5.2.3. So sánh theo loại chữ

**Bảng 5.7.** So sánh theo loại chữ

| Nhóm | Mô hình | CER ↓ | WER ↓ | NED ↑ | EM ↑ |
|------|---------|:-----:|:-----:|:-----:|:----:|
| Viết tay | PaddleOCR v9 | **0,0873** | **0,2896** | **0,9151** | **0,5714** |
|          | TrOCR        | 0,1182 | 0,3986 | 0,8837 | 0,4416 |
| In ấn   | PaddleOCR v9 | **0,0425** | **0,1342** | **0,9578** | **0,7000** |
|          | TrOCR        | 0,0657 | 0,2773 | 0,9361 | 0,5364 |

PaddleOCR dẫn trước ở **cả hai loại chữ và mọi độ đo**. Khoảng cách lớn nhất ở **chữ
viết tay** (CER 8,73% so với 11,82% — TrOCR cao hơn ~35% tương đối; EM 57,14% so với
44,16%), cho thấy PaddleOCR sau tinh chỉnh xử lý chữ viết tay tiếng Việt ổn định hơn
hẳn. Với chữ in, khoảng cách CER thu hẹp nhưng PaddleOCR vẫn vượt rõ ở WER và EM.

### 5.2.4. So sánh theo từng trường thông tin

**Bảng 5.8.** So sánh CER theo từng trường (PaddleOCR v9 vs TrOCR)

| Trường thông tin | CER Paddle ↓ | CER TrOCR ↓ | Mô hình tốt hơn |
|------------------|:-----------:|:-----------:|:---------------:|
| Mối quan hệ với chủ hộ | 0,0000 | 0,0000 | Hòa |
| Số điện thoại liên hệ | **0,0042** | 0,0708 | Paddle |
| Kính gửi | **0,0194** | 0,0759 | Paddle |
| Số định danh cá nhân của chủ hộ | **0,0486** | 0,1007 | Paddle |
| Họ, chữ đệm và tên chủ hộ | **0,0506** | 0,1480 | Paddle |
| Email | **0,0734** | 0,1061 | Paddle |
| Họ, chữ đệm và tên | **0,0781** | 0,1434 | Paddle |
| Giới tính | 0,0833 | **0,0139** | TrOCR |
| Số định danh cá nhân | 0,1250 | **0,0694** | TrOCR |
| Nội dung đề nghị | **0,1350** | 0,2561 | Paddle |
| Ngày, tháng, năm sinh | 0,1375 | **0,0750** | TrOCR |

Phân tích định tính:

- **PaddleOCR thắng ở 7/11 trường** (1 trường hòa), đặc biệt áp đảo ở các trường chữ
  (họ tên, kính gửi, số định danh của chủ hộ) và **trường văn bản dài "Nội dung đề
  nghị"** (CER 13,50% so với 25,61% — chỉ bằng khoảng một nửa lỗi của TrOCR). Lý do là
  TrOCR nhận dạng theo dòng đơn nên xử lý văn bản dài, nhiều dòng kém ổn định hơn.
- **TrOCR thắng ở 3 trường**: "Giới tính", "Số định danh cá nhân" và "Ngày tháng năm
  sinh". Đây đều là **trường ngắn/trường số**, nơi mô hình decoder ngôn ngữ của TrOCR
  xử lý chuỗi chữ số khá tốt và không phụ thuộc khâu phát hiện vùng. Đây là gợi ý hữu
  ích cho hướng kết hợp (xem Mục 5.4).

**Kết luận Mục 5.2:** Trên tổng thể và trên đa số trường, PaddleOCR v9 vượt trội TrOCR,
đặc biệt với chữ viết tay và văn bản dài. TrOCR chỉ có lợi thế cục bộ ở một vài trường
số ngắn. Kết quả này xác nhận quyết định kỹ thuật của đề tài là phù hợp.

---

## 5.3. Kết quả đạt được

Tổng hợp từ thực nghiệm ở Mục 5.1 và 5.2, đề tài đạt được những kết quả chính sau:

1. **Xây dựng hoàn chỉnh hệ thống OCR trích xuất thông tin biểu mẫu hành chính** theo
   kiến trúc hai tầng: phát hiện vùng văn bản (PP-OCRv5 detection) và nhận dạng được
   tinh chỉnh trên dữ liệu tiếng Việt, kết hợp căn chỉnh ảnh (*alignment*), cắt vùng
   theo cấu hình trường và chuẩn hóa hậu kỳ.

2. **Đạt độ chính xác cao và bền vững trên nhiều điều kiện ảnh**: CER tổng thể 6,86%,
   NED 93,29%, EM 62,50% trên 264 mẫu thuộc 5 điều kiện (quét máy và chụp điện thoại,
   chất lượng cao và thấp). Đặc biệt, với **chữ in chụp điện thoại** hệ thống đạt CER
   chỉ 3,06% — chứng minh khả năng triển khai thực tế không cần thiết bị quét chuyên dụng.

3. **Nhận dạng chính xác các trường nghiệp vụ then chốt**: "Mối quan hệ với chủ hộ" đạt
   EM 100%; "Số điện thoại liên hệ" EM 95,83%; "Giới tính" EM 91,67%, đáp ứng yêu cầu
   trích xuất tự động phục vụ nghiệp vụ.

4. **Chứng minh bằng thực nghiệm tính ưu việt của giải pháp**: qua đối chứng công bằng
   với TrOCR trên cùng tập dữ liệu, PaddleOCR v9 tốt hơn trên cả bốn độ đo (giảm ~28,8%
   lỗi ký tự tương đối, tăng 14,39 điểm phần trăm EM).

5. **Thiết lập quy trình đánh giá định lượng chuẩn hóa, đa cấp độ**: bộ độ đo (CER, WER,
   NED, EM) tính ở bốn cấp — tổng thể, theo điều kiện ảnh, theo loại chữ và theo từng
   trường — cho phép phân tích sâu điểm mạnh/yếu và làm nền tảng cho các vòng cải tiến.

6. **Xây dựng được tập dữ liệu đào tạo mô hình quy mô lớn, đa nguồn.** Tập huấn luyện
   gồm khoảng **65.000 ảnh dòng/từ tiếng Việt**, kết hợp bốn nguồn bổ trợ lẫn nhau:

   | Nguồn dữ liệu | Loại | Số lượng (xấp xỉ) | Vai trò |
   |---------------|------|:-----------------:|---------|
   | HuggingFace Vietnamese OCR (`hf_viet_ocr`) | Ảnh chữ in/đa dạng | 60.247 | Nền lớn, học đặc trưng tiếng Việt tổng quát |
   | VNOnDB (chữ viết tay) | Viết tay | 1.144 (train 690 / val 196 / test 258) | Tăng năng lực nhận dạng chữ viết tay |
   | Dữ liệu tổng hợp (`synth`, `synth_v2`) | Sinh tự động | 3.600 | Bổ sung mẫu giàu **dấu hỏi/ngã/nặng hiếm** (ẩ, ử, ữ, ẫ, ợ, ệ…) mà mô hình hay nhầm |
   | Biểu mẫu thật (`real_forms`) | Viết tay + in, quét + chụp | ≈ 446 | Thu hẹp khoảng cách miền (*domain gap*) với dữ liệu thực tế của đơn CT01 |

   Đóng góp đáng chú ý là **bộ sinh dữ liệu tổng hợp có chủ đích** (mô-đun
   `vietnamese_rare_tone_corpus`): chủ động sinh các chuỗi tiếng Việt giàu ký tự dấu
   hiếm — vốn xuất hiện thưa trong các tập công khai — nhằm trực tiếp khắc phục lỗi nhầm
   dấu thanh, một trong những nguyên nhân chính làm giảm EM (xem Mục 5.4). Việc phối hợp
   dữ liệu in, viết tay, tổng hợp và biểu mẫu thật theo nhiều điều kiện thu nhận (quét
   máy, chụp điện thoại chất lượng cao/thấp) là yếu tố then chốt giúp mô hình đạt độ bền
   vững như trình bày ở Mục 5.1.4.

7. **Mô phỏng được tính ứng dụng của OCR trong trích xuất thông tin và hỗ trợ kiểm tra
   (*validation*) văn bản hành chính công — cụ thể là đơn CT01.** Ngoài việc nhận dạng,
   hệ thống còn được tích hợp mô-đun ra quyết định kiểm tra tính hợp lệ của thông tin
   trích xuất bằng cách **đối chiếu kết quả OCR với dữ liệu chuẩn trong cơ sở dữ liệu**.
   Cơ chế quyết định dựa trên hai trục — **độ tin cậy nhận dạng** (*confidence*) và
   **khoảng cách văn bản** giữa giá trị OCR và giá trị thật — phân loại mỗi trường vào
   một trong ba trạng thái:

   | Trạng thái | Điều kiện | Ý nghĩa nghiệp vụ |
   |-----------|-----------|-------------------|
   | **PASS** (hợp lệ) | Khoảng cách = 0 và độ tin cậy cao | Tự động chấp nhận |
   | **REVIEW** (cần xem lại) | Độ tin cậy thấp, hoặc lệch nhỏ (nghi do OCR), hoặc trường "mềm" lệch lớn | Đưa vào luồng kiểm duyệt thủ công, kèm gợi ý giá trị từ CSDL |
   | **ERROR** (không hợp lệ) | Trường "cứng" lệch lớn với độ tin cậy cao, sai định dạng, hoặc không tìm thấy | Cảnh báo dữ liệu không khớp |

   Thiết kế này thể hiện đúng tinh thần **con người trong vòng lặp** (*human-in-the-loop*):
   tự động hóa các trường chắc chắn (PASS), chỉ chuyển cho người xử lý các trường rủi ro
   (REVIEW/ERROR), qua đó **giảm khối lượng nhập liệu thủ công mà vẫn kiểm soát được sai
   sót** — minh chứng cho khả năng ứng dụng thực tế của OCR trong nghiệp vụ quản lý cư
   trú và xử lý văn bản hành chính công.

---

# KẾT LUẬN

> *Phần này tương ứng với các mục được liệt kê 5.1–5.3 (lần thứ hai) trong dàn ý gốc;
> để bảo đảm tính nhất quán về đánh số, các mục được đánh lại là 5.4, 5.5, 5.6.*

## 5.4. Hạn chế và hướng cải thiện

**(1) Lỗi dấu thanh và dấu phụ tiếng Việt.** Khoảng cách giữa CER thấp (6,86%) và EM
(62,50%) cho thấy nhiều lỗi đến từ sai dấu thanh/dấu mũ (ví dụ "Mẫn" → "Măn", "Trọng" →
"Trong"). *Hướng cải thiện:* bổ sung dữ liệu huấn luyện giàu biến thể dấu và tích hợp
mô-đun hậu xử lý dựa trên từ điển/mô hình ngôn ngữ tiếng Việt để hiệu chỉnh dấu.

**(2) Nhận dạng trường số viết tay/ảnh chụp còn yếu.** "Số định danh cá nhân" (CER
12,50%) và "Ngày tháng năm sinh" (CER 13,75%) là các trường lỗi cao nhất, do nhầm cặp
ký tự dễ lẫn và mất/thừa ký tự khi ảnh bị nghiêng, mờ. *Hướng cải thiện:* dùng bộ nhận
dạng chữ số chuyên biệt và áp ràng buộc định dạng (số định danh đúng 12 chữ số, ngày
sinh `dd/mm/yyyy`); đáng chú ý TrOCR làm tốt hơn ở nhóm này → có thể kết hợp.

**(3) Chữ viết tay chụp điện thoại nhạy với nhiễu phối cảnh.** CER nhóm `hand_phone`
(~10%) cao hơn `hand_scan` (7,13%). *Hướng cải thiện:* tăng cường tiền xử lý (khử mờ,
hiệu chỉnh phối cảnh, tăng tương phản) và bổ sung dữ liệu chụp điện thoại khi huấn luyện.

**(4) Độ đo WER chưa phù hợp với trường định danh liền mạch** (email WER 50% dù CER
7,34%). *Hướng cải thiện:* với trường định danh, ưu tiên CER/NED và kiểm tra định dạng
thay vì WER.

**(5) Quy mô và phân bố tập kiểm thử chưa cân đối** (24 phiếu; riêng `hand_phone_low`
chỉ 2 phiếu/22 mẫu). *Hướng cải thiện:* mở rộng số phiếu, đa dạng người viết và điều
kiện ảnh, cân bằng số mẫu giữa các điều kiện để tăng độ tin cậy thống kê.

## 5.5. Đóng góp của đề tài

- **Về thực tiễn:** xây dựng giải pháp số hóa tự động biểu mẫu hành chính (Tờ khai thay
  đổi thông tin cư trú CT01/TT53) hỗ trợ cả chữ in và chữ viết tay tiếng Việt, hoạt động
  tốt cả với ảnh chụp điện thoại — phù hợp triển khai cho người dùng phổ thông.

- **Về kỹ thuật:** tinh chỉnh thành công mô hình nhận dạng tiếng Việt trên miền dữ liệu
  đặc thù, đạt độ chính xác cao và bền vững trên nhiều điều kiện ảnh; xây dựng pipeline
  hoàn chỉnh từ căn chỉnh ảnh, cắt vùng đến chuẩn hóa hậu kỳ.

- **Về phương pháp:** thiết lập khung đánh giá định lượng đa độ đo, đa cấp độ (tổng thể
  / điều kiện ảnh / loại chữ / từng trường) và đối chứng công bằng với TrOCR, cung cấp
  cơ sở khoa học cho việc lựa chọn và cải tiến mô hình.

## 5.6. Hướng phát triển trong tương lai

1. **Tích hợp hậu xử lý ngôn ngữ:** kết hợp mô hình ngôn ngữ tiếng Việt và từ điển
   chuyên ngành (địa danh, họ tên) để tự động hiệu chỉnh dấu thanh và lỗi chính tả, trực
   tiếp nâng EM.

2. **Cơ chế lai (*hybrid*) ở mức trường:** định tuyến từng trường tới mô hình mạnh nhất
   cho trường đó (ví dụ dùng TrOCR cho các trường số như "Số định danh", "Ngày sinh"),
   tận dụng ưu điểm của cả hai kiến trúc đã khảo sát.

3. **Ràng buộc theo định dạng nghiệp vụ:** kiểm tra hợp lệ (số định danh 12 chữ số, định
   dạng ngày sinh, email) ngay trong pipeline để tự sửa và cảnh báo trường nghi ngờ.

4. **Tăng cường tiền xử lý ảnh điện thoại:** khử mờ, hiệu chỉnh phối cảnh, cân bằng sáng
   để thu hẹp khoảng cách giữa ảnh chụp và ảnh quét cho chữ viết tay.

5. **Tối ưu triển khai:** đóng gói hệ thống thành dịch vụ (API) kèm cơ chế đánh giá độ
   tin cậy (*confidence*) và đưa các trường rủi ro cao vào luồng kiểm duyệt thủ công
   (*human-in-the-loop*).
