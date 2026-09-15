# Lộ trình TikTok — Smart Factory Việt Nam

**Lập:** 15/09/2026 · **Bắt đầu:** thứ Tư 16/09/2026 · **Mục tiêu:** 10.000 follow là người trong ngành sản xuất

---

## Mục lục

1. [Định vị](#p1)
2. [Content pillar](#p2)
3. [Công thức video](#p3)
4. [Lộ trình 4 giai đoạn](#p4)
5. [40 ý tưởng video](#p5)
6. [Chuẩn sản xuất](#p6)
7. [Đăng tải](#p7)
8. [Bảng đo](#p8)
9. [Chuyển đổi](#p9)
10. [Rủi ro](#p10)

---

### Cách đọc tài liệu này

- **Ba loại nhãn** dùng xuyên suốt:
  - **[thực hành phổ biến]**: cách nhiều kênh đang làm. Không có nghĩa là đã được chứng minh hiệu quả.
  - **[giả định cần tự A/B test]**: con số hoặc lựa chọn tôi tự đặt làm điểm xuất phát. Đo xong thì sửa.
  - **[chưa kiểm chứng]**: tôi không chắc về nền tảng hoặc con số đó. Kiểm lại trong app hoặc trang chính sách của TikTok trước khi dựa vào.
- **Mọi mục tiêu follow và ngưỡng đạt/không đạt trong tài liệu là do tôi tự đặt.** Tôi không có benchmark đáng tin nào cho kênh B2B kỹ thuật tiếng Việt trên TikTok, nên không có con số nào ở đây là "chuẩn ngành".
- **Con số duy nhất đã đo thật:** tốc độ đọc TTS là **3,54 âm tiết/giây**, đo bằng `make speech-rate` với edge-tts (PLAN.md G0.7). Khi đổi sang giọng sản xuất thì phải đo lại.

### Giả định đầu vào (sai cái nào thì sửa phần liên quan)

| # | Giả định | Nếu sai thì sửa ở |
|---|---|---|
| A1 | Kênh đứng tên NMI, nói với tư cách "kỹ sư của một đơn vị làm phần mềm/giải pháp nhà máy" | Phần 1, 9 |
| A2 | Có **ít nhất 1 kỹ sư QA/sản xuất** duyệt kỹ thuật mỗi kịch bản, khoảng 15–20 phút/kịch bản | Phần 4, 10 |
| A3 | Được quay b-roll tại **ít nhất 1 xưởng** (xưởng/line demo của mình, hoặc xưởng đối tác có văn bản đồng ý) | Phần 6 |
| A4 | Không bắt buộc lộ mặt. Giọng là TTS (VieNeu-TTS) hoặc giọng clone của kỹ sư có đồng ý bằng văn bản (VoxCPM2) | Phần 6, 10 |
| A5 | Adapter TikTok của công cụ chưa qua audit nên API chỉ đăng được `SELF_ONLY` (PLAN.md G7.1). **Video công khai phải đăng tay trong app** | Phần 7, 10 |

---

<a id="p1"></a>

## 1. ĐỊNH VỊ

### Câu định vị

> **Kênh này giải thích SPC, OEE, MES, IoT và camera kiểm tra bằng đúng tình huống đang xảy ra trên xưởng Việt Nam — mỗi video trả lời một câu hỏi mà kỹ sư và quản đốc gặp trong ca làm, trong dưới 45 giây, không bán hàng.**

### 3 chân dung khán giả

| | **P1 — Kỹ sư QA/QC/sản xuất** | **P2 — Quản đốc, trưởng xưởng, quản lý nhà máy** | **P3 — Chủ doanh nghiệp sản xuất vừa và nhỏ** |
|---|---|---|---|
| Hay gặp ở | Nhà máy FDI, công ty vendor cấp 1–2 cho ô tô/điện tử/nhựa/cơ khí | Xưởng 50–500 người, chịu áp lực sản lượng theo ca | Công ty gia đình, xưởng gia công, đang nghe nói nhiều về "chuyển đổi số" |
| **Đang bực mình chuyện gì** | Khách audit hỏi Cpk mà không giải thích được tại sao Cpk khác Ppk · Biểu đồ SPC làm để nộp, không ai đọc · Thước đo chưa làm MSA mà vẫn phải báo cáo năng lực · Camera AOI loại nhầm hàng tốt, bị sản xuất trách | Sổ ghi dừng máy không khớp sản lượng thực · Báo cáo OEE đẹp mà không đủ hàng giao · Công nhân ghi số cho xong · Họp giao ca cãi nhau vì mỗi người một số | Đã mất tiền cho phần mềm không ai dùng · Không biết bắt đầu từ đâu và tốn bao nhiêu · Khách lớn đòi truy xuất nguồn gốc/dữ liệu chất lượng mới cho làm vendor · Sợ bị nhà cung cấp "vẽ" |
| **Đang tìm cái gì** | Cách tính và cách đọc đúng để giải trình với khách/cấp trên · Mẹo dùng được ngay trên Excel/Minitab | Cách biết máy nào đang mất giờ, mất ở đâu · Cách bắt dữ liệu mà không đẩy thêm việc cho công nhân | Lộ trình từng bước, làm nhỏ trước · Câu hỏi để kiểm tra nhà cung cấp · Ví dụ doanh nghiệp cùng quy mô |
| Họ lưu/chia sẻ video khi | Video giải thích đúng thứ họ sắp phải trình bày | Video nói trúng chuyện họ vừa họp | Video giúp họ đỡ bị lừa khi mua |
| Tỉ trọng nội dung nhắm tới [giả định cần tự A/B test] | 45% | 35% | 20% |

**Vì sao P1 đi trước:** kỹ sư là người tìm kiếm thuật ngữ (Cpk, X-bar, OEE), lưu video và gửi cho sếp. Lấy được P1 trước thì có đường đi tới P2 và P3. Làm ngược lại, nói chuyện "chuyển đổi số" với chủ doanh nghiệp ngay từ đầu, thì dễ rơi vào nội dung chung chung, và nhóm đó cũng ít khi tìm kiếm trên TikTok [chưa kiểm chứng].

### 3 thứ kênh này KHÔNG làm

1. **Không làm tin tức và xu hướng công nghệ.** Không "Top 5 xu hướng Công nghiệp 4.0", không đưa tin robot của hãng nước ngoài. Loại video này không trả lời câu hỏi nào của người đứng máy, và làm lệch khán giả sang người xem vãng lai.
2. **Không bán hàng trá hình.** Không có video nào mà thông điệp thật là "mua phần mềm của chúng tôi" nhưng đội lốt video giáo dục. Chỉ nhắc sản phẩm theo đúng luật ở [Phần 9](#p9).
3. **Không làm giật gân "AI thay công nhân", "nhà máy không người", hay chê bai công nhân/doanh nghiệp Việt.** Người trong ngành bỏ qua ngay, còn bình luận thì kéo tới nhóm tranh cãi ngoài ngành.

---

<a id="p2"></a>

## 2. CONTENT PILLAR

| # | Tên trụ | Mục đích | Tỉ lệ GĐ1 | Tỉ lệ GĐ2 | Tỉ lệ GĐ3 | Tiêu đề mẫu |
|---|---|---|---|---|---|---|
| 1 | **Giải-Thích** | Mỗi video làm rõ **một** khái niệm hay bị hiểu sai (SPC, MSA, MES, FMEA, vision). Đây là nền để người xem tin kênh và nhận ra kênh qua thuật ngữ | 40% | 25% | 20% | "Vì sao biểu đồ X-bar báo ngoài kiểm soát mà sản phẩm vẫn đạt" |
| 2 | **Tính-Tay** | Cách tính và các lỗi tính: Cpk/Ppk, OEE, takt, MTTR. Loại video người xem **lưu lại** để dùng | 30% | 25% | 20% | "OEE ra 104%? Máy không giỏi lên, cycle time chuẩn của anh chị sai" |
| 3 | **Mổ-Xẻ** | Tình huống trên xưởng (tổng hợp, ẩn danh): triệu chứng → nguyên nhân → cách kiểm tra. Cho P2 thấy chuyện của chính họ | 20% | 25% | 25% | "Camera AI loại nhầm hàng tốt cả ca — lỗi nằm ở cái đèn" |
| 4 | **Số-Hoá-Thực-Tế** | Bắt đầu chuyển đổi số với doanh nghiệp vừa và nhỏ: làm gì trước, hỏi nhà cung cấp gì, máy cũ bắt dữ liệu thế nào. Cầu nối sang P3 và sang kinh doanh | 10% | 15% | 20% | "Máy cũ không có cổng dữ liệu: bắt tín hiệu chạy/dừng không cần đụng PLC" |
| 5 | **Hỏi-Đáp** | Trả lời bình luận bằng video, phản biện hiểu lầm, sửa lỗi của chính kênh. Cho người xem thấy có người thật đang nghe mình | 0% (chưa có bình luận) | 10% | 15% | "Trả lời anh Tuấn: xưởng 20 người có cần MES không?" |

**Luật chia tỉ lệ:** 5 video/tuần thì 1 video ≈ 20%. Làm tròn theo tuần, không cần đúng tuyệt đối. Hai video liên tiếp không được cùng trụ, trừ khi là series nối phần.

---

<a id="p3"></a>

## 3. CÔNG THỨC VIDEO

### Ngân sách lời đọc

Tính theo **3,54 âm tiết/giây** (đo với edge-tts; **đo lại bằng `make speech-rate` với giọng đã chốt ở GĐ0**):

| Độ dài | Âm tiết tối đa | Dùng cho |
|---|---|---|
| 25 giây | ~88 | Hook + 1 ý + chốt: định nghĩa, phân biệt A/B |
| 35 giây | ~124 | **Mặc định**: hook + 2 ý + chốt + CTA |
| 45 giây | ~159 | Mổ-Xẻ, Tính-Tay có ví dụ số |

Công cụ viết kịch bản đã có ngân sách âm tiết (PLAN.md G2.8, G6.2). Nhập độ dài theo bảng trên, không nhập số chữ.

### Cấu trúc theo mốc giây (bản 35–42 giây)

| Mốc | Phần | Lời đọc | Hình | Luật |
|---|---|---|---|---|
| **0–3s** | **Hook** | ≤ 10 âm tiết. Một câu hỏi hoặc mâu thuẫn **có thuật ngữ** | Hình khớp đúng lời: biểu đồ có điểm đỏ, con số sai, máy đang dừng. Chữ lớn trên màn hình lặp lại hook | Không chào, không "xin chào các bạn", không logo intro. Thuật ngữ phải xuất hiện trong 3 giây đầu để lọc đúng người |
| **3–8s** | **Đặt khung** | 1 câu: vì sao chuyện này hay xảy ra/hay bị hiểu sai | Cảnh xưởng hoặc sơ đồ đơn giản | Hứa trước người xem sẽ biết gì |
| **8–30s** | **Thân** | 2 ý, tối đa 3. Mỗi ý = 1 câu khẳng định + 1 ví dụ cụ thể | Mỗi ý có 1 hình riêng. Công thức/biểu đồ giữ trên màn hình đủ lâu để đọc | Không liệt kê quá 3 ý. Nhiều hơn thì tách thành series |
| **30–38s** | **Chốt** | 1 câu mang về xưởng áp dụng được | Chữ chốt lớn, nền tối thương hiệu | Câu chốt phải là **hành động kiểm tra**, không phải khẩu hiệu |
| **38–42s** | **CTA** | 1 câu, chọn **đúng một** trong 3 kiểu bên dưới | Giữ khung chốt | Không "nhớ like, share, follow" cùng lúc |

**3 kiểu CTA được phép:**
- **Lưu:** "Lưu lại, lần sau khách hỏi Cpk thì mở ra." Dùng cho Tính-Tay.
- **Bình luận có nội dung:** "Xưởng anh chị đang kẻ đường nào lên biểu đồ? Ghi vào bình luận." Dùng cho Giải-Thích và Mổ-Xẻ. Câu hỏi phải để người trong ngành trả lời được, người ngoài ngành không trả lời được.
- **Nối phần:** "Phần 2: khi nào phải tính lại giới hạn kiểm soát." Chỉ dùng khi phần 2 **đã render xong**.

### Kịch bản mẫu điền sẵn (ý tưởng #1, ~40 giây)

| Mốc | Lời đọc | Hình |
|---|---|---|
| 0–3s | "Biểu đồ X-bar báo đỏ, mà hàng vẫn đạt spec. Ai sai?" | Biểu đồ X-bar có một điểm vượt UCL, chữ "ĐẠT SPEC" bên cạnh |
| 3–8s | "Không ai sai. Hai đường đó đến từ hai chỗ khác nhau." | Hai đường UCL và USL cùng hiện trên biểu đồ, hai màu |
| 8–30s | "Spec do khách đặt: hàng phải nằm trong khoảng này. Còn UCL, LCL tính từ chính dữ liệu quá trình: bình thường nó chỉ dao động trong khoảng này. Điểm vượt UCL nghĩa là quá trình vừa đổi — dao mòn, lô vật liệu mới, người đứng máy khác." | Tô vùng spec → tô vùng giới hạn kiểm soát → 3 icon nguyên nhân |
| 30–38s | "Điểm đỏ không phải lệnh loại hàng. Nó là lệnh đi tìm nguyên nhân, trước khi ra hàng lỗi." | Chữ chốt |
| 38–42s | "Xưởng anh chị đang kẻ đường nào lên biểu đồ? Ghi vào bình luận." | Giữ khung |

Số liệu trên biểu đồ là **số minh hoạ**, phải ghi "số minh hoạ" ở góc hình (xem [Phần 6](#p6)).

### 8 mẫu hook điền chỗ trống

| # | Mẫu | Ví dụ đã điền | Hợp trụ |
|---|---|---|---|
| H1 | "[Biểu đồ/chỉ số] báo [trạng thái], mà [thực tế ngược lại]. Ai sai?" | "Biểu đồ X-bar báo đỏ, mà hàng vẫn đạt spec. Ai sai?" | Giải-Thích |
| H2 | "[Chỉ số] ra [con số vô lý]? [Máy/người] không [giỏi/tệ] đi — [thứ gì] của anh chị sai." | "OEE ra 104%? Máy không giỏi lên — cycle time chuẩn của anh chị sai." | Tính-Tay |
| H3 | "[A] và [B] khác nhau đúng một chỗ: [chỗ khác]." | "Cpk và Ppk khác nhau đúng một chỗ: sigma lấy từ đâu." | Tính-Tay |
| H4 | "Trước khi tin [con số], hỏi một câu: [câu hỏi kiểm tra]." | "Trước khi tin Cpk, hỏi một câu: cái thước đã làm Gage R&R chưa?" | Giải-Thích |
| H5 | "[Thiết bị/hệ thống] [triệu chứng] liên tục? Kiểm tra [yếu tố] trước khi đổ cho [thứ hay bị đổ lỗi]." | "Camera báo lỗi giả liên tục? Kiểm tra ánh sáng trước khi đổ cho model." | Mổ-Xẻ |
| H6 | "Sổ [ghi chép] của xưởng thường thiếu đúng một loại [dữ liệu] — và [chỉ số] ảo từ đó." | "Sổ ghi dừng máy thường thiếu đúng một loại dừng — và OEE ảo từ đó." | Mổ-Xẻ |
| H7 | "Trước khi ký [MES/camera AI/IoT], hỏi nhà cung cấp: [câu hỏi cụ thể]?" | "Trước khi ký MES, hỏi nhà cung cấp: máy cũ đưa dữ liệu vào bằng cách nào?" | Số-Hoá |
| H8 | "Kỹ sư mới hay [làm sai điều gì]. Làm vậy thì [hậu quả cụ thể trên xưởng]." | "Kỹ sư mới hay lấy mẫu rải cả ca vào một nhóm con. Làm vậy thì biểu đồ luôn xanh." | Tính-Tay |

**Luật hook:** hook chỉ được hứa điều mà thân video trả lời trọn trong video đó. Không dùng "sốc", "không ai nói cho bạn", "99% kỹ sư không biết". Loại câu này bị người trong ngành coi là rẻ tiền, và con số 99% là bịa.

---

<a id="p4"></a>

## 4. LỘ TRÌNH 4 GIAI ĐOẠN

### Thứ tự ưu tiên — vì sao làm theo trình tự này

1. **GĐ0 chốt những thứ không được đổi giữa chừng:** giọng, bảng thuật ngữ, khuôn hình, kho b-roll. Đổi giọng ở tuần 6 là 30 video cũ nghe như của kênh khác.
2. **GĐ1 xây thư viện nền SPC, OEE và vision.** Đây là các video mà video tuần 5–12 sẽ trỏ về ("xem video Cpk/Ppk trước"). Không có nền thì series và video trả lời bình luận ở GĐ2 không có gì để nối.
3. **GĐ2 chỉ làm được khi đã có bình luận chuyên môn,** vì trụ Hỏi-Đáp sống bằng bình luận. Nên GĐ1 phải cố tình dùng CTA hỏi chuyên môn để gom nguyên liệu cho GĐ2.
4. **GĐ3 mới được nhắc sản phẩm.** Lúc đó kênh đã có đủ video giá trị và đủ lượng người biết mình để một video có nhắc sản phẩm không làm hỏng lòng tin.
5. **Luôn giữ hàng chờ ≥ 5 video đã duyệt và render xong.** Sản xuất không phải nút thắt, **người duyệt kỹ thuật** mới là nút thắt (A2). Có hàng chờ thì ốm một tuần vẫn không đứt nhịp.

### "Tuần đạt" là gì (dùng cho mọi giai đoạn)

Một tuần **đạt** khi thoả **cả 3** điều kiện [giả định cần tự A/B test]:
1. Đăng đủ số video theo kế hoạch của giai đoạn.
2. Có ≥ 1 video đạt ngưỡng "Đạt" ở [Phần 8](#p8).
3. Follow mới trong tuần ≥ mục tiêu tuần của giai đoạn **hoặc** số bình luận chuyên môn trong tuần ≥ mục tiêu tuần.

Điều kiện 3 cho phép "hoặc" là có chủ ý: ở kênh ngách hẹp, tín hiệu đúng người thường xuất hiện trước khi follow tăng [chưa kiểm chứng]. Không muốn khai tử một hướng đúng chỉ vì follow chậm.

---

### GIAI ĐOẠN 0 — Thiết lập (thứ Tư 16/09 → Chủ nhật 20/09)

| | |
|---|---|
| **Mục tiêu follow** | 0. Chưa đăng công khai |
| **Số video/tuần** | 0 công khai; 6 video render xong nằm trong hàng chờ |
| **Format ưu tiên** | Giải-Thích và Tính-Tay 35 giây, giọng + biểu đồ tự dựng + b-roll xưởng |

**Việc phải làm:**

**Thứ Tư 16/09**
- [ ] Chốt tên hiển thị + handle. Handle chứa từ khoá người trong ngành gõ (ví dụ `nmi.smartfactory`), không dùng tên lóng.
- [ ] Chuyển tài khoản sang **Tài khoản doanh nghiệp** trong Cài đặt → Tài khoản. Lý do: có phân tích và bắt dùng nhạc thương mại có quyền. Điều kiện và tính năng cụ thể [chưa kiểm chứng — kiểm lại trong app].
- [ ] Viết bio tạm theo mẫu ở [Phần 9](#p9). Ảnh đại diện là logo NMI trên nền tối, đọc được ở cỡ nhỏ.
- [ ] Rà **77 thuật ngữ đã nạp trong `glossary`** (PLAN.md G1.3). Đối chiếu với bảng ở [Phần 6](#p6) và thêm các cặp dịch còn thiếu (subgroup → nhóm con, rework → hàng sửa lại…). Nạp bằng `make glossary-load`.

**Thứ Năm 17/09**
- [ ] Nghe thử **20 giọng VieNeu-TTS** và mẫu VoxCPM2 trên cùng một đoạn 40 âm tiết có đủ "Cpk, X-bar, OEE, Gage R&R, UCL".
- [ ] Chọn 3 giọng. Cho **3 người trong ngành** (không phải người làm kênh) nghe mù, chấm 2 câu: "nghe có giống kỹ sư không?" và "có đọc sai thuật ngữ nào không?". Chốt **1 giọng chính**.
- [ ] Nếu clone giọng kỹ sư: lấy **văn bản đồng ý cho phép dùng giọng** trước khi thu mẫu.
- [ ] Chạy `make speech-rate` với giọng đã chốt. Ghi con số mới vào dòng đầu [Phần 3](#p3) và `TTS_SYLLABLES_PER_SEC`.

**Thứ Sáu 18/09**
- [ ] Quay **60 clip b-roll, mỗi clip 5–10 giây** tại xưởng (A3), theo danh sách: máy CNC/ép chạy và dừng, đèn tháp, thước cặp/panme đang đo, HMI (che tên sản phẩm), bàn QC, camera kiểm tra, dây chuyền lắp, giấy ghi sổ tay, kho. Quay dọc 9:16 và ngang 16:9 mỗi loại.
- [ ] Nhập b-roll vào nguồn nội bộ `own` của công cụ, ghi rõ xưởng nào và văn bản đồng ý nào vào hồ sơ nguồn.
- [ ] Viết **12 kịch bản** cho ý tưởng #1–#12 ở [Phần 5](#p5), dùng Studio với đề bài + độ dài 35 giây.

**Thứ Bảy 19/09**
- [ ] Kỹ sư QA duyệt kỹ thuật 12 kịch bản. Sửa và ghi mọi lỗi thuật ngữ vào danh sách "lỗi đã gặp" để cập nhật prompt.
- [ ] Render **6 video** đầu. Xem **trên điện thoại thật, trong app TikTok ở chế độ nháp/riêng tư**. Kiểm tra phụ đề có bị nút bên phải và caption che không.
- [ ] Dựng 3 khuôn cố định: khung chốt (nền `#081120`), nhãn "số minh hoạ", ảnh bìa có tiêu đề.

**Chủ nhật 20/09**
- [ ] Render xong 3 video ghim (xem [Phần 9](#p9)): "Kênh này dành cho ai", #1, #3.
- [ ] Tạo sheet theo dõi với đúng các cột của bảng ở [Phần 8](#p8).
- [ ] Lập danh sách **20 tài khoản TikTok/YouTube Shorts trong và gần ngách** (Việt và nước ngoài) để xem họ trả lời bình luận thế nào. **Không** lấy hình hay kịch bản của họ.
- [ ] Viết thêm kịch bản #13–#16 để hàng chờ tuần 1 có đủ 10 video.

**ĐIỀU KIỆN MỞ KHOÁ sang GĐ1 (phải đủ tất cả):**
- Giọng chính đã chốt và đo lại tốc độ đọc.
- ≥ 10 kịch bản đã qua duyệt kỹ thuật; ≥ 6 video render xong, đã xem trên điện thoại.
- 3 video ghim đã render.
- Sheet theo dõi đã có.

**Nếu 3 tuần liền không đạt:** GĐ0 không được kéo quá 1 tuần. Nếu tới Chủ nhật 27/09 vẫn chưa đủ điều kiện:
- Chưa có người duyệt kỹ thuật → **dừng việc làm kênh** cho tới khi có người duyệt, không đăng video chưa duyệt (xem Rủi ro R2).
- Chưa quay được b-roll → bắt đầu GĐ1 với hình **chỉ gồm biểu đồ tự dựng + sơ đồ**, chọn các ý tưởng không cần cảnh xưởng (#2, #3, #4, #5, #7, #14, #15).
- Chưa chốt được giọng → chọn giọng được 3 người nghe chấm cao nhất và đi tiếp. Không chờ giọng hoàn hảo.

---

### GIAI ĐOẠN 1 — Thư viện nền (tuần 1–4: 21/09 → 18/10)

| | |
|---|---|
| **Mục tiêu follow** | 500 vào Chủ nhật 18/10 [giả định cần tự A/B test] · mục tiêu tuần: +125 follow **hoặc** ≥ 5 bình luận chuyên môn |
| **Số video/tuần** | **5** (thứ Hai → thứ Sáu) [giả định cần tự A/B test] |
| **Format ưu tiên** | Giải-Thích và Tính-Tay 30–35 giây · 1 khái niệm/video · hook H1–H4 · CTA bình luận chuyên môn hoặc Lưu |

**Nhịp tuần cố định (lặp 4 tuần):**

| Ngày | Việc |
|---|---|
| Thứ Hai sáng | Điền sheet của tuần trước. Đánh dấu video Đạt/Flop/Bùng nổ theo [Phần 8](#p8). Chọn 5 ý tưởng cho tuần sau |
| Thứ Hai chiều | Viết 5 kịch bản cho **tuần sau** trong Studio |
| Thứ Ba | Kỹ sư QA duyệt 5 kịch bản. Sửa xong trong ngày |
| Thứ Tư | Render 5 video, xem trên điện thoại, đặt ảnh bìa |
| Hằng ngày (T2–T6) | Đăng tay 1 video theo khung giờ đang thử ([Phần 7](#p7)). Trả lời mọi bình luận chuyên môn trong ngày theo luật ở [Phần 9](#p9) |
| Thứ Sáu | Chép các câu hỏi trong bình luận vào tab "nguyên liệu Hỏi-Đáp" của sheet |

**Việc riêng từng tuần:**
- **Tuần 1 (21–27/09):** đăng video "Kênh này dành cho ai" vào thứ Hai và ghim. Tiếp theo đăng #1, #2, #3, #10. Thử khung giờ A cả tuần.
- **Tuần 2 (28/09–04/10):** đăng #4, #5, #6, #7, #8. Thử khung giờ B. Viết xong kịch bản #17–#21 cho GĐ2 để có hàng chờ.
- **Tuần 3 (05–11/10):** đăng #9, #11, #12, #13, #14. Thử khung giờ C. Làm bản thử **2 hook khác nhau cho cùng một chủ đề** (#14 và bản hook khác đăng ở tuần 4) để so sánh.
- **Tuần 4 (12–18/10):** đăng #15, #16 và 3 video làm lại từ các chủ đề Đạt tốt nhất (góc mới, không đăng lại file cũ). Chốt khung giờ tốt nhất. Viết tổng kết GĐ1 một trang: trụ nào, hook nào, độ dài nào thắng.

**ĐIỀU KIỆN MỞ KHOÁ sang GĐ2 (phải đủ tất cả)** [giả định cần tự A/B test]:
- ≥ 20 video đã đăng công khai.
- ≥ 300 follow.
- ≥ 15 bình luận chuyên môn cộng dồn (câu hỏi hoặc phản biện có thuật ngữ, theo định nghĩa ở [Phần 8](#p8)).
- Phân loại tay 50 bình luận gần nhất: ≥ 50% là người trong ngành.
- Có ≥ 5 câu hỏi trong tab "nguyên liệu Hỏi-Đáp".

**Nếu 3 tuần liền không đạt:** mỗi tuần tiếp theo chỉ đổi **một biến**, giữ nguyên các biến còn lại:
1. **Tuần chẩn đoán A — Hook:** mở biểu đồ giữ chân khán giả (retention) của 10 video gần nhất. Nếu phần lớn rơi trước giây 3: viết lại hook cho 5 video tuần tới theo mẫu H2 và H5 (mâu thuẫn và triệu chứng), hình giây 0 phải là con số hoặc biểu đồ lỗi.
2. **Tuần chẩn đoán B — Độ dài:** nếu rơi đều ở giữa video: cắt xuống 25 giây, 1 ý/video.
3. **Tuần chẩn đoán C — Chủ đề:** nếu giữ chân ổn mà không ai follow: chuyển tỉ lệ sang Mổ-Xẻ 40%, vì tình huống xưởng dễ khiến người xem nhận ra "chuyện của mình" hơn định nghĩa [giả định cần tự A/B test].
4. Sau 3 tuần chẩn đoán vẫn không đạt: xem kỹ khán giả (R1). Nếu > 50% bình luận là vãng lai thì vấn đề nằm ở hook/hình quá rộng, không nằm ở chủ đề. Siết lại luật "thuật ngữ trong 3 giây đầu".

**Không làm khi không đạt:** không đổi giọng, không đổi ngách, không chuyển sang nội dung giải trí.

---

### GIAI ĐOẠN 2 — Series và đối thoại (tuần 5–8: 19/10 → 15/11)

| | |
|---|---|
| **Mục tiêu follow** | 3.000 vào Chủ nhật 15/11 [giả định cần tự A/B test] · mục tiêu tuần: +600 follow **hoặc** ≥ 15 bình luận chuyên môn |
| **Số video/tuần** | **5–6**: 4 video thường + 1–2 video Hỏi-Đáp trả lời bình luận [giả định cần tự A/B test] |
| **Format ưu tiên** | Series 3 phần có tên (ví dụ "Cpk không nói dối", "OEE không ảo") · video trả lời bình luận · Mổ-Xẻ 40–45 giây |

**Việc phải làm:**
- [ ] **Thứ Hai 19/10:** chọn **2 series** từ các chủ đề Đạt tốt nhất GĐ1. Đặt tên series và hashtag series riêng. Viết đủ **6 kịch bản** (2 series × 3 phần) trước thứ Tư 21/10.
- [ ] **Mỗi tuần:** làm **1–2 video trả lời bình luận** bằng tính năng trả lời bình luận bằng video, lấy từ tab "nguyên liệu Hỏi-Đáp". Nêu tên người hỏi nếu tài khoản công khai. Không nêu tên nhà máy của họ.
- [ ] **Trước thứ Sáu 30/10:** làm **1 tài liệu tải về miễn phí, không gắn sản phẩm**: file Excel tính Cp/Cpk/Pp/Ppk có biểu đồ X-bar/R, **hoặc** file Excel tính OEE theo ca. Kỹ sư QA kiểm công thức với 1 bộ dữ liệu đã biết kết quả. Đặt trên website NMI, **chưa** có form thu thông tin.
- [ ] **Tuần 6 (26/10–01/11):** làm video giới thiệu file tải về theo góc "cách dùng", không phải "tải ngay". Ghim thay video thứ 3.
- [ ] **Tuần 7 (02–08/11):** thử **1 video có kỹ sư thật xuất hiện** (3 giây mở đầu hoặc cả video) để so với video chỉ có giọng. Đồng ý hình ảnh bằng văn bản.
- [ ] **Tuần 8 (09–15/11):** viết kịch bản #31–#40, dựng hàng chờ 10 video cho GĐ3. Viết tổng kết GĐ2 một trang.
- [ ] **Hằng tuần:** cập nhật danh sách "lỗi kỹ thuật bị người xem chỉ ra". Lỗi nào đúng thì làm video đính chính trong 72 giờ (xem R2).

**ĐIỀU KIỆN MỞ KHOÁ sang GĐ3 (phải đủ tất cả)** [giả định cần tự A/B test]:
- ≥ 3.000 follow.
- ≥ 40 video đã đăng, trong đó ≥ 6 video thuộc series đã hoàn thành.
- Trung vị tỉ lệ (lưu + chia sẻ)/view của 10 video gần nhất **≥** trung vị của 10 video cuối GĐ1.
- Phân loại tay 50 bình luận gần nhất: ≥ 55% người trong ngành.
- Có ≥ 5 tin nhắn/bình luận hỏi dạng "xưởng tôi làm việc này thế nào" hoặc "dùng công cụ gì". Đây là tín hiệu cho phép bắt đầu chuyển đổi.

**Nếu 3 tuần liền không đạt:**
1. Bỏ series nào có **phần 2 và phần 3 dưới 50% view của phần 1**, vì người xem không đi theo series. Quay về video lẻ cho chủ đề đó.
2. Nếu Hỏi-Đáp kém: dừng Hỏi-Đáp 2 tuần, dồn tỉ lệ sang trụ đang Đạt nhiều nhất.
3. Nếu follow đứng nhưng bình luận chuyên môn vẫn tăng: **đi tiếp, không đổi hướng**. Hạ mục tiêu follow của GĐ2 xuống 2.000 và giữ nguyên các điều kiện còn lại.
4. Nếu cả follow lẫn bình luận đều đứng: quay lại nhịp GĐ1 trong 2 tuần với 5 video Tính-Tay và Mổ-Xẻ thuộc chủ đề đã Đạt, rồi đánh giá lại.

---

### GIAI ĐOẠN 3 — Uy tín và chuyển đổi (tuần 9–12+: từ 16/11)

| | |
|---|---|
| **Mục tiêu follow** | 10.000. Mốc giữa: 6.000 vào 13/12 [giả định cần tự A/B test]. "+" nghĩa là **có thể cần hơn 12 tuần**. Tôi không có dữ liệu chắc chắn nào về tốc độ tăng của kênh ngách này |
| **Số video/tuần** | **5**: 3 video thường + 1 Hỏi-Đáp + 1 video "Đọc biểu đồ của anh chị" |
| **Format ưu tiên** | Mổ-Xẻ và Số-Hoá 40–45 giây · video phân tích dữ liệu người xem gửi (ẩn danh) · hướng dẫn cho người mua · tối đa 1/10 video được nhắc sản phẩm |

**Việc phải làm:**
- [ ] **Thứ Hai 16/11:** mở series **"Đọc biểu đồ của anh chị"**. Đăng video kêu gọi người xem gửi biểu đồ SPC/OEE **đã xoá tên công ty, tên sản phẩm, số lô**. Viết quy định nhận bài 5 dòng: không nhận dữ liệu còn tên, không phân tích dữ liệu của khách hàng NMI mà chưa có đồng ý.
- [ ] **Trước thứ Sáu 20/11:** gắn form thu email/số điện thoại + vai trò + quy mô xưởng vào file tải về. Mỗi dòng lead ghi video nguồn.
- [ ] **Trước thứ Sáu 27/11:** viết quy trình bàn giao lead cho kinh doanh ([Phần 9](#p9)) và thống nhất với người phụ trách kinh doanh.
- [ ] **Tuần 10–11:** làm 2 video hướng dẫn người mua (#23 và #33): "hỏi nhà cung cấp gì", "chi phí một điểm IoT gồm những dòng nào". Chỉ nêu cấu phần, **không** báo giá.
- [ ] **Từ tuần 11:** được làm **1 video có nhắc sản phẩm trên mỗi 10 video**, theo đúng luật ở [Phần 9](#p9).
- [ ] **Hằng tuần:** đổi video ghim thứ 3 thành video Đạt tốt nhất trong 4 tuần gần nhất.
- [ ] **Nếu tài khoản đủ điều kiện LIVE** [chưa kiểm chứng điều kiện hiện hành]: thử 1 buổi LIVE 30 phút "Hỏi đáp SPC" vào tuần 12, có kỹ sư QA trực.
- [ ] **Thứ Hai 14/12:** viết tổng kết 12 tuần. Quyết định có dùng lại video sang YouTube Shorts/Facebook Reels hay không (công cụ đã có adapter, PLAN.md G3, G4).

**ĐIỀU KIỆN "HOÀN THÀNH" (thay cho mở khoá):**
- ≥ 10.000 follow.
- Phân loại tay 50 bình luận gần nhất: ≥ 60% người trong ngành.
- Lead từ TikTok có ghi video nguồn, và ≥ 1 lead đã được kinh doanh xác nhận là doanh nghiệp sản xuất có nhu cầu thật.

**Nếu 3 tuần liền không đạt:**
1. Nếu follow tăng mà tỉ lệ người trong ngành **giảm** dưới 50%: dừng ngay các chủ đề gây tranh cãi rộng (#31 và các video kiểu "AI thay QC"), quay lại Tính-Tay (R1).
2. Nếu video nhắc sản phẩm làm bình luận xấu đi (xem R6): dừng nhắc sản phẩm 4 tuần.
3. Nếu follow đứng quanh một mức: kéo dài GĐ3, **không** mở rộng ngách. Tăng Hỏi-Đáp lên 2 video/tuần, vì trả lời người thật là loại nội dung khó có kênh nào sao chép.
4. Nếu lead = 0 sau 4 tuần có form: sửa file tải về. Có thể nó giải quyết vấn đề chưa đủ sát, hoặc form hỏi quá nhiều. Rút form còn 3 trường.

---

<a id="p5"></a>

## 5. 40 Ý TƯỞNG VIDEO

Mọi con số trong video là **số minh hoạ**, trừ các hướng dẫn chuẩn có dẫn tên (AIAG MSA, AIAG-VDA FMEA, ISA-95, Western Electric). Tình huống Mổ-Xẻ là **tình huống tổng hợp**, không phải một khách hàng cụ thể.

| STT | Tiêu đề | Hook 1 câu | Góc kể trong 30 giây | Pillar | Giai đoạn |
|---|---|---|---|---|---|
| 1 | Vì sao X-bar báo ngoài kiểm soát mà sản phẩm vẫn đạt spec | "Biểu đồ X-bar báo đỏ, mà hàng vẫn đạt spec. Ai sai?" | Giới hạn spec do khách đặt, giới hạn kiểm soát tính từ dữ liệu quá trình. Điểm vượt UCL nghĩa là quá trình vừa đổi, cần tìm nguyên nhân trước khi ra hàng lỗi | Giải-Thích | 1 |
| 2 | Đừng kẻ đường spec lên biểu đồ kiểm soát | "Kẻ đường spec lên biểu đồ SPC là cách nhanh nhất để SPC mất tác dụng." | Dùng spec làm giới hạn thì chỉ báo khi đã ra hàng lỗi. SPC có mặt để báo **trước** đó. Hai biểu đồ cạnh nhau, cùng dữ liệu | Giải-Thích | 1 |
| 3 | Cpk và Ppk khác nhau ở đúng một chỗ | "Cpk và Ppk khác nhau đúng một chỗ: sigma lấy từ đâu." | Cpk dùng sigma trong nhóm con (R̄/d₂). Ppk dùng độ lệch chuẩn của toàn bộ dữ liệu. Ppk thấp hơn Cpk nhiều nghĩa là quá trình trôi giữa các nhóm con: giữa ca, giữa lô | Tính-Tay | 1 |
| 4 | Cp cao mà Cpk thấp: quá trình tốt nhưng lệch tâm | "Cp 2,0 mà Cpk 0,9 — máy tốt hay máy tệ?" | Cp không nhìn vị trí trung bình, Cpk có nhìn. Khoảng cách giữa hai số cho biết lệch tâm bao nhiêu. Chỉnh tâm thường dễ hơn giảm biến động | Tính-Tay | 1 |
| 5 | OEE vượt 100%: cycle time chuẩn đặt sai | "OEE ra 104%? Máy không giỏi lên — cycle time chuẩn của anh chị sai." | Performance = sản lượng × cycle time lý tưởng ÷ thời gian chạy. Lấy cycle time "trung bình thực tế" hoặc số cũ làm chuẩn thì Performance vượt 100% và che mất tổn thất tốc độ | Tính-Tay | 1 |
| 6 | Dừng máy dưới 5 phút không ai ghi — OEE ảo từ đó | "Sổ ghi dừng máy thường thiếu đúng một loại dừng." | Dừng ngắn (kẹt phôi, chờ vật tư) không được ghi tay, nên Availability đẹp mà Performance thấp không giải thích được. Chỉ bắt được bằng tín hiệu chạy/dừng lấy từ máy | Mổ-Xẻ | 1 |
| 7 | Hàng sửa lại có tính là hàng tốt trong OEE không? | "Sửa xong đạt rồi thì tính là hàng tốt chứ?" | Quality trong OEE tính hàng đạt **ngay lần đầu**. Tính hàng sửa lại là hàng tốt thì che mất thời gian và chi phí sửa, cũng như nguyên nhân gốc | Tính-Tay | 1 |
| 8 | Gage R&R: thước đo sai trước khi hàng sai | "Trước khi tin Cpk, hỏi một câu: cái thước đã làm Gage R&R chưa?" | Biến động của hệ đo lớn thì biểu đồ đang vẽ nhiễu của thước. Hướng dẫn AIAG MSA: %GRR < 10% chấp nhận, 10–30% tuỳ ứng dụng, > 30% không chấp nhận | Giải-Thích | 1 |
| 9 | 8 điểm liên tiếp một phía đường tâm: chưa vượt giới hạn vẫn phải xem | "Không điểm nào vượt UCL, mà vẫn phải dừng xem máy." | Quy tắc Western Electric: 8 điểm liên tiếp cùng một phía đường tâm (bộ quy tắc Nelson dùng 9). Quá trình đã dịch tâm: dao mòn, lô vật liệu mới | Giải-Thích | 1 |
| 10 | MES và ERP khác nhau ở tầng nào | "ERP biết đơn giao ngày nào. MES biết máy số 3 đang làm gì lúc này." | ISA-95: ERP ở tầng 4 (kế hoạch, tính theo ngày/tuần), MES ở tầng 3 (điều hành theo ca/giờ). Khoảng trống giữa hai tầng là chỗ Excel đang sống | Giải-Thích | 1 |
| 11 | Camera AI báo lỗi giả cả ca: lỗi nằm ở cái đèn | "Camera báo lỗi giả liên tục? Kiểm tra ánh sáng trước khi đổ cho model." | Bề mặt kim loại bóng dưới đèn thường tạo điểm chói, model đọc thành vết. Đổi đèn trước (dome/khuếch tán cho bề mặt cong bóng, coaxial cho bề mặt phẳng phản quang), rồi mới gán nhãn thêm | Mổ-Xẻ | 1 |
| 12 | Loại nhầm và lọt lỗi: camera kiểm tra phải chọn đánh đổi | "Camera bắt được 100% lỗi rất dễ — cứ loại hết hàng là xong." | Hạ ngưỡng thì loại nhầm hàng tốt, nâng ngưỡng thì lọt lỗi. Chọn ngưỡng theo chi phí lọt lỗi ra khách so với chi phí loại nhầm, không chọn theo "độ chính xác" chung chung | Giải-Thích | 1 |
| 13 | Máy cũ không có cổng dữ liệu: bắt chạy/dừng không cần đụng PLC | "Máy 20 năm tuổi vẫn gửi được trạng thái chạy/dừng." | Kẹp cảm biến dòng lên dây nguồn motor hoặc lấy tín hiệu đèn tháp. Không can thiệp PLC. Giới hạn: chỉ biết chạy/dừng, chưa biết sản lượng hay lý do dừng | Số-Hoá-Thực-Tế | 1 |
| 14 | Nhóm con 5 mẫu: lấy liên tiếp hay rải cả ca? | "Lấy mẫu rải cả ca vào một nhóm con thì biểu đồ luôn xanh." | Nguyên tắc nhóm con hợp lý: lấy liên tiếp để biến động trong nhóm nhỏ. Rải cả ca thì biến động giữa giờ bị nhét vào trong nhóm, giới hạn nở rộng, biểu đồ không bao giờ báo | Tính-Tay | 1 |
| 15 | Pareto lỗi: đếm theo số lượng hay theo tiền? | "Lỗi nhiều nhất chưa chắc là lỗi đáng sửa nhất." | Cùng một dữ liệu, xếp theo số lần và xếp theo chi phí (phế phẩm + sửa + khiếu nại) cho hai top khác nhau. Chọn trục trước khi họp | Tính-Tay | 1 |
| 16 | Kênh này dành cho ai | "Nếu anh chị đang đứng trong xưởng, kênh này làm cho anh chị." | Dành cho kỹ sư QA, quản đốc, chủ xưởng. Có 3 loại video: giải thích, tính tay, mổ xẻ. Lịch đăng. Không bán hàng. Video ghim số 1 | Hỏi-Đáp | 1 |
| 17 | Dữ liệu độ phẳng mà tính Cpk như chiều dài | "Độ phẳng không bao giờ âm — sao lại tính Cpk như chiều dài?" | Đặc tính chặn dưới ở 0 (độ phẳng, độ đảo) thường lệch phải. Công thức Cpk theo phân phối chuẩn cho số sai. Xem histogram trước, dùng phương pháp cho phân phối không chuẩn | Tính-Tay | 2 |
| 18 | Khi nào phải tính lại giới hạn kiểm soát | "Tính lại UCL mỗi tuần là cách làm biểu đồ mù." | Chỉ tính lại sau thay đổi có chủ đích đã xác nhận (khuôn mới, quy trình mới). Tính lại liên tục thì giới hạn chạy theo sự trôi của quá trình | Giải-Thích | 2 |
| 19 | FMEA: vẫn nhân S×O×D ra RPN? | "Hai rủi ro cùng RPN 120 — một cái có thể làm khách bị thương." | RPN giống nhau che mất mức nghiêm trọng. Sổ tay AIAG-VDA FMEA (2019) chuyển sang Action Priority, ưu tiên Severity trước | Giải-Thích | 2 |
| 20 | 5 Why dừng ở "công nhân bất cẩn" là chưa xong | "Câu trả lời là 'do con người' thì mới hỏi được 2 Why." | Hỏi tiếp: quy trình nào cho phép lắp sai? Ví dụ chi tiết lắp ngược → đồ gá chống sai (poka-yoke), không phải đào tạo lại | Mổ-Xẻ | 2 |
| 21 | OPC UA hay MQTT: câu hỏi sai | "OPC UA hay MQTT? Nhiều xưởng dùng cả hai, ở hai chỗ khác nhau." | OPC UA có mô hình thông tin mô tả dữ liệu máy. MQTT là giao thức truyền nhẹ qua broker, bản thân không có mô hình dữ liệu (Sparkplug B bổ sung phần này). Thường dùng OPC UA gần máy, MQTT lên hệ thống | Giải-Thích | 2 |
| 22 | Takt time và cycle time: một cái do khách, một cái do máy | "Máy chạy nhanh hơn takt vẫn có thể là lãng phí." | Takt = thời gian sẵn có ÷ nhu cầu. Cycle time lớn hơn takt thì phải tăng ca hoặc cải tiến. Nhỏ hơn nhiều thì tồn kho giữa công đoạn | Tính-Tay | 2 |
| 23 | Trước khi ký MES, hỏi nhà cung cấp 3 câu | "Trước khi ký MES, hỏi: máy cũ đưa dữ liệu vào bằng cách nào?" | 3 câu: máy không có cổng dữ liệu thì làm sao · mất mạng thì ai nhập và nhập lại thế nào · ngừng dùng thì xuất dữ liệu ra định dạng gì | Số-Hoá-Thực-Tế | 2 |
| 24 | Số hoá bắt đầu từ 1 máy nút cổ chai, không phải cả xưởng | "Gắn cảm biến cả xưởng một lúc là cách nhanh nhất để có dashboard không ai mở." | Tìm công đoạn nút cổ chai, đo OEE đúng máy đó 4 tuần, giảm được một loại tổn thất rồi mới mở rộng. Dữ liệu phải có người chịu trách nhiệm hành động | Số-Hoá-Thực-Tế | 2 |
| 25 | Camera cần độ phân giải bao nhiêu để thấy vết xước 0,1 mm | "Camera 5MP có thấy được vết xước 0,1 mm không? Tính 10 giây là biết." | Trường nhìn ÷ số pixel = mm/pixel. Vết lỗi cần phủ vài pixel (quy tắc kinh nghiệm, tuỳ thuật toán). Ví dụ minh hoạ: trường nhìn 100 mm, muốn 3 pixel trên 0,1 mm thì cần khoảng 3.000 pixel theo chiều đó | Tính-Tay | 2 |
| 26 | Xưởng gần như không có mẫu lỗi thì huấn luyện AI kiểm tra kiểu gì | "Hàng lỗi hiếm quá, không đủ ảnh để dạy AI?" | Phát hiện bất thường học từ hàng tốt và báo cái gì khác thường. Đổi lại khó phân loại loại lỗi, và phải kiểm soát chặt ánh sáng và vị trí | Giải-Thích | 2 |
| 27 | Trả lời bình luận: xưởng 20 người có cần MES không? | "Xưởng 20 người có cần MES không? Câu trả lời thật: chưa chắc." | Dấu hiệu cần: nhiều mã hàng, khách đòi truy xuất nguồn gốc, số liệu giao ca không khớp. Trước đó: ghi chép có cấu trúc + bảng tính dùng chung | Hỏi-Đáp | 2 |
| 28 | Cpk đẹp lúc duyệt mẫu, hàng loạt vẫn bị khách trả | "Báo cáo năng lực đạt, ba tháng sau khách trả hàng." | Nghiên cứu năng lực chạy ngắn: một ca, một lô vật liệu, một người đứng máy. Hàng loạt có biến động giữa ca/lô, nên Ppk dài hạn mới gần thực tế | Mổ-Xẻ | 2 |
| 29 | MTTR tính từ lúc máy dừng hay lúc thợ tới? | "Hai xưởng cùng MTTR 30 phút có thể đang đo hai thứ khác nhau." | Định nghĩa điểm bắt đầu (máy dừng/báo sửa/thợ tới) và điểm kết thúc (sửa xong/chạy lại/ra hàng đạt) làm số khác nhau. Chốt định nghĩa trước khi so sánh | Tính-Tay | 2 |
| 30 | Biểu đồ p khi cỡ mẫu mỗi ngày khác nhau | "Tỉ lệ lỗi hôm nay vượt đường đỏ — hay đường đỏ vẽ sai?" | Giới hạn của biểu đồ p phụ thuộc cỡ mẫu n. Ngày kiểm ít thì giới hạn rộng hơn. Dùng một đường cố định thì báo sai ngày ít mẫu, bỏ sót ngày nhiều mẫu | Tính-Tay | 2 |
| 31 | Camera có thay được người QC không — việc gì làm tốt, việc gì không | "Camera không mệt. Nhưng có loại lỗi nó không bao giờ thấy." | Làm tốt: lỗi lặp lại, vị trí cố định, ánh sáng kiểm soát được. Làm kém: lỗi mới chưa từng gặp, đánh giá cảm quan có tranh cãi. Người QC chuyển sang xử lý ngoại lệ và cải tiến | Hỏi-Đáp | 3 |
| 32 | Dashboard đẹp mà không ai mở | "Dự án số hoá xong, dashboard đẹp — ba tháng sau không ai mở." | Tình huống tổng hợp: không ai được giao hành động theo chỉ số, cảnh báo gửi cho quá nhiều người, chỉ số không gắn với họp giao ca. Sửa quy trình trước khi sửa giao diện | Mổ-Xẻ | 3 |
| 33 | Một điểm đo IoT tốn tiền ở những dòng nào | "Báo giá cảm biến rẻ — rồi hoá đơn đến từ những dòng khác." | Cấu phần: cảm biến, bộ thu thập/gateway, đi dây và lắp đặt, mạng, phần mềm, người đọc và xử lý dữ liệu. Không báo giá, chỉ liệt kê để hỏi đủ | Số-Hoá-Thực-Tế | 3 |
| 34 | Truy xuất nguồn gốc: từ mã lô đến từng sản phẩm cần gì | "Khách hỏi con hàng này làm máy nào, ca nào — trả lời mất bao lâu?" | Ba mức: theo lô, theo ca/máy, theo từng sản phẩm. Mỗi mức cần thêm: ghi mã ở đâu, quét ở công đoạn nào, gắn với dữ liệu quá trình ra sao | Số-Hoá-Thực-Tế | 3 |
| 35 | SPC trên Excel đến lúc nào thì vỡ | "Excel làm SPC được. Đến một lúc nó bắt đầu nói dối." | Dấu hiệu: nhiều người sửa cùng file, công thức bị ghi đè, dữ liệu nhập trễ cả ca, không ai xem kịp lúc. Trước khi đổi công cụ, hỏi: ai hành động khi có điểm đỏ? | Số-Hoá-Thực-Tế | 3 |
| 36 | Đọc biểu đồ của anh chị #1 | "Một kỹ sư gửi biểu đồ này và hỏi: quá trình có ổn không?" | Biểu đồ người xem gửi (đã xoá thông tin nhận diện): đọc theo thứ tự điểm vượt giới hạn → chuỗi → xu hướng → chia nhóm con. Kết luận + 1 việc cần kiểm tra | Hỏi-Đáp | 3 |
| 37 | Sau khi đổi khuôn: tách những sản phẩm đầu thành nhóm riêng | "Mỗi lần đổi khuôn là biểu đồ nhảy — mà không ai ghi lại." | Sản phẩm ngay sau đổi khuôn/đổi mã hàng có đặc tính khác lúc ổn định. Đánh dấu sự kiện đổi khuôn trên biểu đồ, không trộn chung vào giới hạn | Mổ-Xẻ | 3 |
| 38 | SMED: tách việc trong và việc ngoài khi đổi khuôn | "Đổi khuôn mất lâu phần lớn không phải vì tháo lắp." | Việc ngoài (chuẩn bị dụng cụ, gia nhiệt, lấy khuôn) chuyển ra trước khi dừng máy. Việc trong mới làm lúc dừng. Quay video một lần đổi khuôn rồi phân loại từng thao tác | Giải-Thích | 3 |
| 39 | Cảnh báo IoT: ai nhận, trong bao lâu | "Cảm biến báo, điện thoại rung — rồi không ai làm gì." | Mỗi cảnh báo cần: một người nhận chính, thời hạn phản hồi, việc cụ thể phải làm, và người nhận tiếp khi quá hạn. Cảnh báo không có người nhận thì nên tắt | Số-Hoá-Thực-Tế | 3 |
| 40 | Kỹ sư trả lời bình luận bằng dữ liệu line demo | "Anh Hùng hỏi OEE tính theo ca hay theo ngày — mở dữ liệu thật ra xem." | Kỹ sư mở dữ liệu line demo của mình (không phải dữ liệu khách), tính cùng một OEE theo ca và theo ngày, chỉ ra con số theo ngày che mất ca kém | Hỏi-Đáp | 3 |

Tên người trong #27, #40 là ví dụ. Khi làm thật, dùng đúng tên tài khoản người hỏi, và chỉ khi tài khoản đó công khai.

---

<a id="p6"></a>

## 6. CHUẨN SẢN XUẤT

### 6.1 Quy ước thuật ngữ

Nguyên tắc theo glossary của công cụ (PLAN.md D34): người trong ngành nói tiếng Anh thì giữ tiếng Anh. Dịch những từ đó ra làm video **khó** hiểu hơn với đúng nhóm cần xem.

**Giữ nguyên tiếng Anh (viết và đọc nguyên dạng):**

| Nhóm | Thuật ngữ |
|---|---|
| Hệ thống | MES, ERP, SCADA, PLC, HMI, IoT, OPC UA, MQTT, API, dashboard |
| Chất lượng | SPC, Cp, Cpk, Pp, Ppk, MSA, Gage R&R, FMEA, PPAP, AOI, UCL, LCL, X-bar, R chart, spec, CAPA, 8D |
| Hiệu suất | OEE, KPI, takt time, cycle time, MTBF, MTTR, SMED |
| Lean | Kaizen, 5S, poka-yoke, Kanban |

**Dịch (lần đầu trong video ghi kèm tiếng Anh trong ngoặc ở phụ đề, các lần sau chỉ tiếng Việt):**

| Tiếng Anh | Dùng | Không dùng |
|---|---|---|
| control chart | biểu đồ kiểm soát | "đồ thị điều khiển" |
| control limit / spec limit | giới hạn kiểm soát / giới hạn spec | "giới hạn kỹ thuật" và "giới hạn kiểm soát" dùng lẫn lộn |
| out of control | ngoài kiểm soát | "mất kiểm soát" (nghe như sự cố) |
| process capability | năng lực quá trình | "khả năng xử lý" |
| subgroup | nhóm con | "nhóm mẫu phụ" |
| downtime / micro-stop | thời gian dừng máy / dừng ngắn | "thời gian chết" |
| scrap / rework | phế phẩm / hàng sửa lại | "hàng hư" |
| yield / first pass yield | tỉ lệ đạt / tỉ lệ đạt ngay lần đầu | |
| changeover | đổi khuôn / đổi mã hàng | |
| root cause | nguyên nhân gốc | "căn nguyên" |
| false reject / escape | loại nhầm / lọt lỗi | "dương tính giả" (sai ngữ cảnh xưởng) |
| sensor / gateway | cảm biến / gateway | |
| traceability | truy xuất nguồn gốc | |
| inspection | kiểm tra | "thanh tra" |

**Quy ước đọc số:** dấu thập phân đọc là "phẩy" và viết "1,33". Phần trăm đọc đủ "phần trăm". Đơn vị đọc đủ: "mi-li-mét", không đọc "em em".

**Kiểm tra phát âm TTS:** mỗi thuật ngữ mới xuất hiện lần đầu phải nghe lại. **Không viết phiên âm vào kịch bản** (ví dụ "xê-pê-ka"), vì phụ đề lấy nguyên chữ của kịch bản (PLAN.md G2.10). Engine đọc sai thì ghi vào danh sách lỗi phát âm và đổi cách đặt câu, hoặc đổi giọng từ GĐ0.

### 6.2 Giọng đọc

- **1 giọng chính cho toàn kênh**, chốt ở GĐ0. Chỉ thêm giọng thứ hai cho một series riêng có tên, không trộn tuỳ ý.
- Xưng **"mình"**, gọi người xem **"anh chị"**. Không xưng "ad", không gọi "các bạn ơi".
- Giọng điềm tĩnh, như kỹ sư đang giải thích cho đồng nghiệp ở bàn QC. Không nhấn kiểu quảng cáo, không cảm thán.
- Không "xin chào", không "hôm nay mình sẽ nói về". Vào thẳng hook.
- Giọng clone của người thật: **phải có văn bản đồng ý**, và người đó được xem trước video đầu tiên dùng giọng mình.
- Nhạc nền nhỏ hơn giọng rõ rệt (công cụ đang trộn nền ở −20 dB, PLAN.md G2.11). Khi có cảnh xưởng thật thì giữ tiếng máy (PLAN.md D11).

### 6.3 Phụ đề

- **Luôn có**, burn cứng vào video, font Be Vietnam Pro (đã kiểm đủ dấu tiếng Việt, PLAN.md G0.8).
- Tối đa **2 dòng**, mỗi dòng khoảng **7 từ** [giả định cần tự A/B test].
- Tô màu **thuật ngữ và con số** (1 màu nhấn thống nhất). Không tô cả câu.
- Đặt phụ đề ở **khoảng giữa đến 2/3 chiều cao màn hình**, tránh dải dưới cùng (caption, tên tài khoản) và cột nút bên phải. Kích thước vùng an toàn chính xác [chưa kiểm chứng]. **Luật bắt buộc:** xem mọi video trên điện thoại trong app trước khi đăng.
- Phụ đề phải khớp lời đọc từng chữ. Không viết tắt trên phụ đề khi lời đọc nói đủ.
- Chữ trên màn hình của hook (0–3s) to hơn phụ đề và đặt cao hơn.

### 6.4 Nhịp cắt

- Đổi hình mỗi **2–4 giây** [thực hành phổ biến]. Ngoại lệ: biểu đồ hoặc công thức đang được giải thích thì **giữ đến khi lời đọc về nó kết thúc**.
- Không cắt ngang giữa một công thức.
- Hình khớp lời **đúng từng giây**: nói "đèn tháp" thì hình là đèn tháp.
- Không dùng hiệu ứng chuyển cảnh xoay/zoom mạnh. Cắt thẳng hoặc mờ dần ngắn.
- Không có intro logo. Logo nhỏ ở khung chốt hoặc góc hình là đủ.

### 6.5 Nguồn hình b-roll an toàn bản quyền

Dùng đúng thứ tự 4 lớp hình của công cụ (PLAN.md G6.4):

| Ưu tiên | Nguồn | Điều kiện |
|---|---|---|
| 1 | **Quay tại xưởng/line demo của mình** | Che tên sản phẩm của khách trên HMI, bao bì, bản vẽ. Người xuất hiện rõ mặt phải đồng ý |
| 2 | **Quay tại xưởng đối tác** | Có **văn bản đồng ý** ghi phạm vi dùng (TikTok, mạng xã hội, thời hạn). Che logo khách, mã sản phẩm, số lô, bảng tiến độ |
| 3 | **Biểu đồ và sơ đồ tự dựng** | Công cụ dựng biểu đồ cột từ số nhập tay (G6.5). Góc hình ghi "số minh hoạ". Biểu đồ SPC/OEE vẽ từ số giả lập, không lấy từ báo cáo của khách |
| 4 | **Kho stock có license thương mại** | Lưu bằng chứng license vào hồ sơ nguồn của công cụ (license gate). Ghi nguồn nếu license bắt buộc |
| 5 | **Ảnh AI** | Chỉ làm **bối cảnh** (ví dụ nền nhà xưởng mờ). **Không** dùng để minh hoạ lỗi sản phẩm, thiết bị cụ thể, biểu đồ hay màn hình phần mềm |

**Không bao giờ dùng:** video của hãng thiết bị (Siemens, Keyence, Cognex…) cắt từ YouTube · video TikTok/Reels của kênh khác · ảnh tìm trên Google · ảnh chụp màn hình phần mềm của đối thủ · ảnh có mặt công nhân mà không có đồng ý.

### 6.6 5 lỗi làm video kỹ thuật bị người trong ngành đánh giá là nghiệp dư

| # | Lỗi | Ví dụ | Cách chặn trong quy trình |
|---|---|---|---|
| 1 | **Dùng sai hoặc lẫn thuật ngữ** | Nói Cpk khi đang mô tả Ppk · coi giới hạn spec là giới hạn kiểm soát · gọi MES là "phần mềm quản lý kho" | Kỹ sư QA duyệt mọi kịch bản. Danh sách "lỗi đã gặp" đưa vào prompt |
| 2 | **Hình không khớp nghề** | Nói về máy ép nhựa mà chiếu máy CNC · robot hình người kiểu phim để minh hoạ "tự động hoá" · ảnh AI có màn hình chữ vô nghĩa | Luật 6.5: ảnh AI chỉ làm bối cảnh. Người duyệt xem video có hình, không chỉ đọc kịch bản |
| 3 | **Số liệu tròn trịa không nguồn** | "Tăng 30% năng suất", "giảm 50% lỗi" | Cấm con số hiệu quả không có nguồn (prompt Studio đã cấm bịa số, G6.2). Số trên biểu đồ ghi "số minh hoạ" |
| 4 | **Vi phạm an toàn trong hình** | Người không đeo bảo hộ · tay gần máy đang chạy · cửa an toàn mở khi máy chạy · đứng dưới tải | Checklist quay b-roll: kiểm tra đồ bảo hộ, cửa an toàn trước khi bấm quay. Loại mọi clip vi phạm, kể cả khi đẹp |
| 5 | **Giọng và nhịp kiểu quảng cáo** | Hook "sốc", "99% kỹ sư không biết" · nhạc sôi động đè giọng · kết bằng "liên hệ ngay" | Luật hook ở [Phần 3](#p3). Nhạc nền −20 dB. CTA chỉ 1 trong 3 kiểu đã quy định |

---

<a id="p7"></a>

## 7. ĐĂNG TẢI

### 7.1 Caption

| Khuyến nghị | Nhãn |
|---|---|
| Dòng 1 lặp lại **câu hỏi của hook** bằng từ người trong ngành hay gõ tìm kiếm (ví dụ "Cpk và Ppk khác nhau thế nào?") | [thực hành phổ biến] |
| Cụ thể caption, chữ trên màn hình và lời đọc được TikTok đưa vào tìm kiếm tới mức nào | [chưa kiểm chứng] |
| Dòng 2 (tuỳ chọn): 1 câu bổ sung không có trong video, ví dụ "Công thức ở giây 12" | [giả định cần tự A/B test] |
| Caption ngắn 1–2 dòng, không nhồi từ khoá | [thực hành phổ biến] |
| Không đặt link, số điện thoại, tên sản phẩm trong caption ở GĐ1–GĐ2 | Luật riêng của kênh (xem [Phần 9](#p9)) |

### 7.2 Hashtag

| Khuyến nghị | Nhãn |
|---|---|
| 3–5 hashtag/video | [thực hành phổ biến] |
| Cơ cấu: 1–2 hashtag ngách rộng (`#smartfactory` `#sanxuat`) + 2–3 hashtag thuật ngữ (`#SPC` `#OEE` `#Cpk`) + 1 hashtag series riêng của kênh khi có series | [giả định cần tự A/B test] |
| Mức ảnh hưởng của hashtag lên phân phối | [chưa kiểm chứng] |
| Không dùng hashtag xu hướng ngoài ngách (`#xuhuong` `#fyp`) để kéo view | Luật riêng của kênh: kéo sai người xem (R1) |

### 7.3 Âm thanh nền

| Khuyến nghị | Nhãn |
|---|---|
| Tài khoản doanh nghiệp chỉ dùng nhạc trong thư viện nhạc thương mại của TikTok | [chưa kiểm chứng — kiểm lại chính sách hiện hành trong app] |
| Giọng là chính, nhạc nền rất nhỏ hoặc không có. Có cảnh xưởng thì giữ tiếng máy | [giả định cần tự A/B test] |
| Âm thanh đang xu hướng giúp tăng phân phối | [chưa kiểm chứng] — **không dựa vào**, vì nhạc xu hướng hợp giải trí, không hợp giọng kỹ thuật |
| **Bật nhãn "nội dung do AI tạo"** cho mọi video dùng giọng TTS/giọng clone hoặc ảnh AI | [chưa kiểm chứng cách áp dụng cho giọng TTS] — mặc định **luôn bật**. Nói rõ trong video "Kênh này dành cho ai" rằng giọng đọc là AI, còn nội dung do kỹ sư viết và duyệt |

### 7.4 Khung giờ đăng

| Khuyến nghị | Nhãn |
|---|---|
| Thử 3 khung, mỗi khung 1 tuần ở GĐ1: **A = 11:45–12:15** (nghỉ trưa ca hành chính) · **B = 17:30–18:30** (tan ca) · **C = 20:30–21:30** (buổi tối) | [giả định cần tự A/B test] |
| Nhà máy chạy 3 ca thì giờ rảnh của người xem rải khắp ngày, nên không có khung đúng cho mọi người | [giả định cần tự A/B test] |
| Từ tuần 5: đọc tab khán giả/thời gian hoạt động của người theo dõi trong TikTok Studio, chuyển sang khung có nhiều người theo dõi hoạt động nhất | [thực hành phổ biến]; điều kiện hiện dữ liệu này [chưa kiểm chứng] |
| So sánh khung giờ bằng **trung vị view 72 giờ** của các video cùng trụ, không so từng video | Quy tắc đo riêng của kênh |

### 7.5 Tần suất

| Khuyến nghị | Nhãn |
|---|---|
| GĐ1: 5 video/tuần, thứ Hai → thứ Sáu | [giả định cần tự A/B test] |
| GĐ2: 5–6 video/tuần · GĐ3: 5 video/tuần | [giả định cần tự A/B test] |
| Đều đặn quan trọng hơn số lượng. Không đăng dồn 3 video/ngày rồi nghỉ 1 tuần | [thực hành phổ biến] |
| Không xoá video flop rồi đăng lại **cùng file** | [thực hành phổ biến]; hệ quả với phân phối [chưa kiểm chứng]. Làm lại thì đổi hook, góc kể, hình |
| Trả lời bình luận trong vài giờ đầu sau khi đăng | [thực hành phổ biến]; tác động lên phân phối [chưa kiểm chứng]. Làm vì người hỏi xứng đáng được trả lời |

### 7.6 Cách đăng

- **GĐ1–GĐ3: đăng tay trong app TikTok.** Adapter API của công cụ chưa qua audit nên chỉ đăng được `SELF_ONLY` (PLAN.md G7.1).
- Có thể dùng API đẩy bản riêng tư lên để xem trước trên điện thoại. Chuyển một video riêng tư sang công khai có bị phân phối khác so với đăng công khai từ đầu hay không thì [chưa kiểm chứng], nên **video công khai vẫn đăng mới bằng tay**.
- Mỗi lần đăng: đặt ảnh bìa có tiêu đề (để lưới hồ sơ đọc như một thư viện, [thực hành phổ biến]) · caption + hashtag · bật nhãn AI · kiểm tra quyền bình luận đang mở.

---

<a id="p8"></a>

## 8. BẢNG ĐO

### 8.1 Định nghĩa dùng trong bảng

- **Mốc đo:** mọi số liệu video lấy ở **72 giờ** và **7 ngày** sau khi đăng. So video với video ở **cùng mốc**.
- **M (trung vị kênh):** trung vị của **10 video gần nhất** ở cùng mốc. Chưa đủ 10 video thì dùng các ngưỡng "trước 10 video".
- **Bình luận chuyên môn:** bình luận có ít nhất một trong ba thứ: câu hỏi kỹ thuật, phản biện có thuật ngữ, hoặc mô tả tình huống ở xưởng của họ. "Hay quá", emoji, tag bạn bè thì không tính.
- **Người trong ngành (phân loại tay):** bình luận hoặc hồ sơ cho thấy làm sản xuất/QA/kỹ thuật/quản lý xưởng. Không rõ thì xếp "không rõ", không tính là trong ngành.
- Tên chỉ số trong TikTok Studio (thời gian xem trung bình, tỉ lệ xem hết, follow mới theo video, nguồn lưu lượng) có thể khác theo phiên bản app [chưa kiểm chứng]. Dùng chỉ số gần nghĩa nhất và ghi rõ tên đã dùng vào sheet.
- **Mọi ngưỡng dưới đây là [giả định cần tự A/B test]**, không phải benchmark ngành.

### 8.2 Chỉ số theo dõi hằng tuần (điền mỗi sáng thứ Hai)

| # | Chỉ số | Lấy ở đâu | Tuần ĐẠT | Tuần BÁO ĐỘNG | Ghi chú |
|---|---|---|---|---|---|
| W1 | Follow cuối tuần | Hồ sơ / TikTok Studio | Theo mục tiêu giai đoạn ([Phần 4](#p4)) | Giảm so với tuần trước | |
| W2 | Follow mới trong tuần | TikTok Studio | ≥ mục tiêu tuần của giai đoạn | < 50% mục tiêu tuần | |
| W3 | Số video đã đăng / kế hoạch | Sheet | = kế hoạch | Thiếu ≥ 2 video | Thiếu video là lỗi vận hành, sửa hàng chờ |
| W4 | Số video còn trong hàng chờ (đã duyệt + render) | Công cụ Studio | ≥ 5 | ≤ 2 | Báo động thì thứ Hai dồn viết + duyệt |
| W5 | Trung vị view 72 giờ các video trong tuần | TikTok Studio | ≥ M | < 0,5 × M | |
| W6 | Trung vị tỉ lệ xem hết | TikTok Studio | ≥ M | < 0,7 × M | Giảm kéo dài → xem lại hook và độ dài |
| W7 | Trung vị (lưu + chia sẻ) ÷ view | TikTok Studio | ≥ M | < 0,5 × M | Chỉ số gần nhất với "người trong ngành thấy có ích" |
| W8 | Số bình luận chuyên môn trong tuần | Đếm tay | ≥ mục tiêu tuần của giai đoạn | 0 | |
| W9 | % người trong ngành trong 50 bình luận gần nhất | Phân loại tay | ≥ ngưỡng giai đoạn (50% / 55% / 60%) | < 40% | Dưới 40% → xử lý R1 ngay |
| W10 | % khán giả ở Việt Nam | TikTok Studio → khán giả | Tăng hoặc giữ | Giảm 2 tuần liền | Khán giả nước ngoài không mua phần mềm tiếng Việt |
| W11 | Tỉ trọng view từ tìm kiếm + hồ sơ | TikTok Studio → nguồn lưu lượng | Tăng hoặc giữ | Giảm 3 tuần liền | Tăng nghĩa là có người chủ động tìm kênh [giả định] |
| W12 | Số lỗi kỹ thuật người xem chỉ ra **và đúng** | Đếm tay | 0 | ≥ 2 trong tuần | Mỗi lỗi đúng → video đính chính trong 72 giờ (R2) |
| W13 | Câu hỏi mới vào tab "nguyên liệu Hỏi-Đáp" | Sheet | ≥ 3 (từ GĐ2) | 0 trong 2 tuần | |
| W14 | Lead có ghi video nguồn (từ GĐ3) | Form + sheet | ≥ 1 | 0 trong 4 tuần | 0 trong 4 tuần → sửa file tải về/form |

### 8.3 Ngưỡng đạt/không đạt của từng video

| Mức | Điều kiện (đo ở 72 giờ) | Việc phải làm |
|---|---|---|
| **Trước 10 video** | Không chấm ĐẠT/FLOP theo view. Chỉ kiểm: (a) không có lỗi kỹ thuật bị chỉ ra đúng, (b) biểu đồ giữ chân khán giả không rơi phần lớn trước giây 3 | Ghi nhận xét hook vào sheet. Chưa đổi gì |
| **ĐẠT** | Đủ **2 trong 3**: view ≥ M · tỉ lệ xem hết ≥ M · (lưu + chia sẻ)/view ≥ M. **Và** ≥ 1 bình luận chuyên môn | Ghi hook, trụ, độ dài vào tab "công thức thắng". Đưa chủ đề vào danh sách làm phần 2/series |
| **TRUNG BÌNH** | Đạt 1 trong 3 chỉ số | Không làm gì riêng. Tính vào M |
| **FLOP** | View < 0,5 × M **và** tỉ lệ xem hết < M | Chạy **quy trình flop** bên dưới |
| **BÙNG NỔ** | View ≥ 3 × M **hoặc** follow mới từ video ≥ 3 × trung vị follow mới/video | Chạy **quy trình bùng nổ** bên dưới |

### 8.4 Quy trình khi một video FLOP

1. **Không xoá video** [thực hành phổ biến]. Để đó, nó vẫn là một mục trong thư viện.
2. Trong **24 giờ**: mở biểu đồ giữ chân khán giả, ghi video rơi ở đâu:

| Rơi ở | Chẩn đoán | Sửa ở video sau cùng chủ đề |
|---|---|---|
| 0–3 giây | Hook không trúng hoặc hình giây 0 không khớp | Viết lại hook theo mẫu khác (H2/H5), giây 0 phải là con số hoặc biểu đồ lỗi |
| 3–10 giây | Phần đặt khung dài dòng | Cắt phần đặt khung còn 1 câu |
| Giữa thân | Quá nhiều ý hoặc hình đứng quá lâu | Còn 1–2 ý, đổi hình mỗi 2–4 giây |
| Gần cuối | Chốt yếu, CTA dài | Chốt bằng 1 hành động kiểm tra, CTA 1 câu |
| Không rơi rõ chỗ nào nhưng view thấp | Chủ đề hẹp hoặc tiêu đề/ảnh bìa không rõ | Giữ chủ đề, đổi góc: từ định nghĩa sang tình huống Mổ-Xẻ |

3. Ghi chẩn đoán vào sheet. **Không kết luận từ 1 video.** Chỉ đổi công thức khi ≥ 3 video cùng kiểu flop theo cùng một cách.
4. Chủ đề vẫn quan trọng với khán giả (có trong danh sách 40 hoặc có người hỏi) thì làm lại **sau ≥ 2 tuần** với hook + góc kể mới. Không đăng lại file cũ.

### 8.5 Quy trình khi một video BÙNG NỔ

1. **Trong 2 giờ:** kiểm tra bình luận. Người trong ngành chiếm đa số, hay người xem vãng lai/tranh cãi ngoài ngành?
   - **Đa số vãng lai:** trả lời lịch sự vài bình luận, **không** làm tiếp chủ đề đó, ghi lại hook nào kéo sai người (R1).
   - **Đa số trong ngành:** làm tiếp các bước dưới.
2. **Trong 24 giờ:**
   - Trả lời **10 bình luận chuyên môn** có nhiều lượt thích nhất.
   - Có bình luận chỉ lỗi đúng: ghim phản hồi thừa nhận lỗi và lên lịch video đính chính.
   - Ghim video nếu nó đúng ngách (thay video ghim thứ 3).
3. **Trong 48 giờ:** viết + duyệt + render **2 video nối tiếp**: 1 video "phần 2" đi sâu hơn, 1 video trả lời bình luận hay nhất. Đăng trong **3 ngày** tiếp theo, chen trước hàng chờ.
4. **Trong 7 ngày:** kiểm tra follow mới từ video bùng nổ có ở lại không (follow cuối tuần sau vẫn tăng hay giảm). Ghi vào tab "công thức thắng": hook, trụ, độ dài, khung giờ, hình giây 0.
5. **Không làm:** không chèn nhắc sản phẩm vào bình luận hay video nối tiếp, không đổi nhịp đăng sang chạy theo chủ đề đó quá 3 video.

---

<a id="p9"></a>

## 9. CHUYỂN ĐỔI

### 9.1 Nguyên tắc

- **Phễu:** video → bình luận/lưu → follow → tải file hữu ích → để lại thông tin → kinh doanh gọi tư vấn. Không có bước nào đi thẳng từ video sang "mua".
- **Việc của kênh là tạo cuộc trò chuyện chuyên môn.** Việc bán là của kinh doanh, bắt đầu sau khi người xem tự để lại thông tin.

### 9.2 Bio

**GĐ0–GĐ2** (giới hạn ký tự của bio [chưa kiểm chứng], giữ ngắn):

```
Kỹ sư NMI giải thích SPC · OEE · MES bằng tình huống xưởng thật
Video mới T2–T6 · Giọng đọc AI, nội dung kỹ sư viết & duyệt
```

**GĐ3** (khi đã có file tải về và gắn được link):

```
Kỹ sư NMI giải thích SPC · OEE · MES bằng tình huống xưởng thật
Tải file Excel tính Cpk/OEE miễn phí ↓
```

- Điều kiện gắn link website trong bio (loại tài khoản, số follow) [chưa kiểm chứng — kiểm lại trong app ở GĐ0]. Chưa gắn được thì ghi "Tìm 'NMI' trên Google" thay link, **không** lách bằng cách viết link trong ảnh hay trong caption.
- Không ghi số điện thoại hay "nhận tư vấn" trong bio ở GĐ1–GĐ2.

### 9.3 Video ghim

Ghim tối đa 3 video [thực hành phổ biến; kiểm lại giới hạn trong app].

| Vị trí | GĐ1 | GĐ2 | GĐ3 |
|---|---|---|---|
| Ghim 1 | #16 "Kênh này dành cho ai" | Giữ | Làm lại bản mới: có nhắc file tải về |
| Ghim 2 | #1 X-bar đỏ mà hàng đạt | Video Đạt tốt nhất Tính-Tay | Giữ |
| Ghim 3 | #3 Cpk vs Ppk | Video giới thiệu file tải về (tuần 6) | Video Đạt tốt nhất trong 4 tuần gần nhất, đổi mỗi thứ Hai |

### 9.4 Cách trả lời bình luận

| Loại bình luận | Trả lời thế nào | Mẫu |
|---|---|---|
| **Câu hỏi kỹ thuật ngắn** | Trả lời thẳng trong bình luận, ≤ 3 câu. Hay thì chép vào "nguyên liệu Hỏi-Đáp" | "Được anh ạ, với dữ liệu lệch phải như độ phẳng thì Cpk tính theo phân phối chuẩn sẽ sai. Mình làm riêng một video phần này tuần sau." |
| **Câu hỏi kỹ thuật dài/phụ thuộc bối cảnh** | Hỏi lại 1 câu làm rõ, rồi làm video trả lời bình luận | "Chị cho mình hỏi thêm: nhóm con đang lấy mấy mẫu, lấy liên tiếp hay rải trong ca?" |
| **Phản biện đúng** (kênh sai) | Thừa nhận ngay, ghim phản hồi, làm video đính chính trong 72 giờ. Cảm ơn bằng tên | "Anh nói đúng, mình nói nhầm Cpk thành Ppk ở giây 15. Mình ghim lại và sẽ làm video sửa. Cảm ơn anh." |
| **Phản biện sai hoặc khác trường phái** | Lịch sự, dẫn tên chuẩn (AIAG MSA, ISA-95…), không tranh thắng thua | "Nhiều xưởng làm theo cách anh nói. Theo hướng dẫn AIAG MSA thì… Hai cách khác nhau ở chỗ…" |
| **Hỏi "dùng phần mềm gì"** — GĐ1–GĐ2 | Trả lời trung lập: Excel/Minitab làm được gì trước. Không nêu tên sản phẩm của mình | "Giai đoạn đầu Excel làm được, miễn nhóm con lấy đúng. Khi nào nhiều line thì mới cần công cụ chuyên." |
| **Hỏi "dùng phần mềm gì"** — GĐ3 | Trả lời trung lập như trên + 1 câu: "NMI có làm phần này, anh chị cần thì nhắn tin mình gửi thông tin." Không dán link dưới bình luận của người khác | |
| **Mô tả sự cố ở xưởng của họ** | Trả lời hướng kiểm tra. **Không** phán nguyên nhân khi chưa có dữ liệu | "Mô tả vậy thì mình sẽ kiểm tra ánh sáng và vị trí phôi trước. Chưa xem dữ liệu thì mình chưa dám kết luận." |
| **Chê giọng AI** | Thừa nhận, nói rõ nội dung do kỹ sư viết và duyệt. Đếm số lượng cho R3 | "Đúng là giọng AI anh ạ. Nội dung do kỹ sư QA bên mình viết và duyệt từng câu." |
| **Gửi dữ liệu/ảnh có tên công ty** | Nhắc xoá thông tin nhận diện, không phân tích công khai bản còn tên | "Anh xoá tên công ty và mã sản phẩm rồi gửi lại giúp mình, mình mới đưa lên video được." |
| **Công kích, spam, chính trị, ngoài ngách** | Không trả lời. Ẩn/xoá nếu xúc phạm | — |

**Nhịp trả lời:** mọi bình luận chuyên môn được trả lời **trong ngày**. Mỗi tuần, người phụ trách kênh dành 20 phút vào sáng thứ Hai và 15 phút mỗi chiều T2–T6.

### 9.5 Thời điểm ĐƯỢC nhắc sản phẩm

Chỉ khi **đủ tất cả** các điều kiện sau:
- Đã vào GĐ3 **và** từ tuần 11 trở đi.
- Không quá **1 video có nhắc sản phẩm trên mỗi 10 video**.
- Video vẫn có giá trị trọn vẹn nếu cắt phần nhắc sản phẩm đi.

Các dạng được phép:
1. **So sánh trung lập:** "Việc này làm bằng Excel thế nào — bằng phần mềm chuyên thì khác chỗ nào — NMI đang làm theo cách nào." Tên sản phẩm chỉ ở phần cuối, ≤ 5 giây.
2. **Hậu trường:** "Bên mình xây màn hình SPC này, vì sao đặt quy tắc Western Electric lên đầu." Nói về quyết định kỹ thuật, không nói giá hay khuyến mãi.
3. **Trả lời trực tiếp** khi người xem hỏi đích danh "NMI có làm X không".
4. **Trong tin nhắn riêng**, khi người xem đã chủ động nhắn.

### 9.6 Thời điểm TUYỆT ĐỐI KHÔNG nhắc sản phẩm

- Trong **40 video đầu tiên** và suốt GĐ1–GĐ2.
- Trong video **Mổ-Xẻ sự cố** và video **đính chính lỗi** của kênh.
- Trong phản hồi cho bình luận **phàn nàn, chê bai**, hoặc bình luận về **đối thủ**.
- Trong video **"Đọc biểu đồ của anh chị"**: người gửi dữ liệu không gửi để bị bán hàng.
- Khi **chưa trả lời xong** câu hỏi kỹ thuật của người xem.
- Trong video/bình luận nói về **tai nạn lao động hoặc an toàn**.
- Bằng cách **chê sản phẩm đối thủ** — bất cứ lúc nào.
- Trong **video nối tiếp một video bùng nổ** (xem [8.5](#p8)).

### 9.7 Bàn giao lead cho kinh doanh (từ GĐ3)

| Bước | Việc | Ai | Hạn |
|---|---|---|---|
| 1 | Người xem điền form khi tải file (3 trường: tên, số điện thoại/email, vai trò + quy mô xưởng) | Người xem | — |
| 2 | Ghi lead vào sheet kèm **video nguồn** | Người phụ trách kênh | Trong ngày |
| 3 | Lọc: có xưởng sản xuất thật + vai trò kỹ sư trở lên hoặc chủ doanh nghiệp + có vấn đề cụ thể | Người phụ trách kênh | Trong 2 ngày |
| 4 | Kinh doanh nhắn/gọi, mở đầu bằng **chủ đề của video nguồn**, không mở bằng bảng giá | Kinh doanh | Trong 3 ngày làm việc |
| 5 | Ghi kết quả (có nhu cầu / chưa / không phù hợp) về sheet | Kinh doanh | Sau cuộc gọi |
| 6 | Mỗi thứ Hai: đếm lead theo trụ và theo video, đưa vào tổng kết | Người phụ trách kênh | Thứ Hai |

---

<a id="p10"></a>

## 10. RỦI RO

| # | Rủi ro | Dấu hiệu nhận biết sớm | Cách xử lý |
|---|---|---|---|
| **R1** | **Khán giả lệch sang người xem vãng lai.** Follow tăng nhưng không phải người trong ngành, lead = 0, và thuật toán tiếp tục đẩy video tới sai người | W9 (% người trong ngành) < 40% · bình luận kiểu "không hiểu gì", tag bạn bè, emoji · W10 (% khán giả VN) giảm · một video bùng nổ nhờ chủ đề tranh cãi rộng | Dừng ngay các hook/chủ đề rộng đã kéo sai người (đã ghi ở 8.5). 2 tuần tiếp theo chỉ làm Tính-Tay và Giải-Thích có thuật ngữ trong 3 giây đầu. Không dùng hashtag rộng. Chấp nhận view giảm |
| **R2** | **Sai kỹ thuật bị chỉ trích công khai.** Trong ngách hẹp, một lỗi Cpk/OEE bị một kỹ sư có tiếng chỉ ra có thể làm mất lòng tin cả kênh | W12 ≥ 1 · bình luận "sai rồi" nhận nhiều lượt thích · có người stitch/duet để chỉ lỗi | **Phòng:** không đăng kịch bản chưa qua kỹ sư QA duyệt, không ngoại lệ. **Khi xảy ra:** trong 24 giờ ghim phản hồi thừa nhận; trong 72 giờ đăng video đính chính nêu rõ sai ở đâu và cảm ơn người chỉ ra; thêm lỗi vào danh sách "lỗi đã gặp" trong prompt. **Không** xoá video gốc để giấu lỗi — thêm dòng đính chính vào caption |
| **R3** | **Giọng AI và hình AI làm mất tin cậy.** Người trong ngành coi kênh là "máy sản xuất nội dung", không phải kỹ sư | Bình luận chê giọng AI > 10% số bình luận trong 2 tuần [giả định cần tự A/B test] · tỉ lệ xem hết của video giọng AI thấp hơn video có kỹ sư thật (thử ở tuần 7) · bị hỏi "có người thật không" | Nói rõ ngay từ video ghim 1 rằng giọng là AI, nội dung do kỹ sư viết/duyệt. Luôn bật nhãn AI. Tăng tỉ lệ cảnh xưởng thật (lớp 1–2), giảm ảnh AI. Kết quả tuần 7 cho thấy video có kỹ sư thật Đạt rõ hơn thì chuyển 1–2 video/tuần sang kỹ sư xuất hiện hoặc giọng clone có đồng ý |
| **R4** | **Cạn ý tưởng và lặp lại chính mình.** Công cụ sản xuất nhanh nên dễ ra 10 video Cpk na ná nhau | Nhiều video liền nhau cùng khái niệm · hàng chờ W4 toàn chủ đề đã làm · bình luận "video này nói rồi" · M giảm dần 3 tuần liền mà không có flop rõ | Giữ **tab "nguyên liệu Hỏi-Đáp"** làm nguồn ý tưởng chính từ GĐ2. Mỗi tháng người phụ trách ngồi 1 giờ với kỹ sư QA/kỹ sư triển khai, chép **10 câu hỏi khách hàng thật hay hỏi** (ẩn danh). Luật: một khái niệm chỉ được làm lại nếu có **góc kể mới** (tình huống, lỗi tính, phản biện) |
| **R5** | **Lộ dữ liệu khách hàng hoặc vi phạm an toàn trong hình.** Mất khách thật, rủi ro pháp lý, và bị người trong ngành đánh giá không chuyên nghiệp | Có tên sản phẩm/logo/mã lô/bảng tiến độ trong b-roll · công nhân không đồ bảo hộ trong khung hình · khách/đối tác nhắn hỏi "sao có hình xưởng tôi" · người xem gửi dữ liệu còn tên công ty | **Phòng:** checklist quay (6.5, 6.6 lỗi 4) và văn bản đồng ý lưu trong hồ sơ nguồn trước khi dùng. Người duyệt xem **video thành phẩm**, không chỉ kịch bản. **Khi xảy ra:** chuyển video sang riêng tư ngay, báo đối tác/khách trong ngày, dựng lại bản đã che rồi mới đăng lại |
| **R6** | **Đứt nhịp vận hành:** người duyệt kỹ thuật bận/nghỉ, đăng tay bị quên, hoặc nhắc sản phẩm quá sớm làm hỏng lòng tin | W4 (hàng chờ) ≤ 2 · W3 thiếu video 2 tuần liền · kịch bản chờ duyệt > 3 ngày · sau video nhắc sản phẩm có bình luận "quảng cáo à", hoặc W7 của video đó < 0,5 × M | Luôn giữ hàng chờ ≥ 5 video. Đào tạo **người duyệt thứ hai** trước tuần 5 (kỹ sư QA thứ hai hoặc kỹ sư triển khai) để có người thay khi người chính vắng. Đặt lịch nhắc đăng trên điện thoại người phụ trách theo khung giờ đang dùng. Video nhắc sản phẩm bị chê → dừng nhắc sản phẩm 4 tuần (GĐ3 mục "3 tuần không đạt"). Nếu TikTok cấp audit cho client API, chuyển sang đăng lịch qua công cụ, nhưng **vẫn** giữ gate duyệt của người |

---

*Hết tài liệu. Cập nhật file này sau tổng kết cuối GĐ1 (thứ Hai 19/10), GĐ2 (thứ Hai 16/11), và tuần 12 (thứ Hai 14/12): sửa các ngưỡng [giả định cần tự A/B test] bằng số đo thật của kênh.*
