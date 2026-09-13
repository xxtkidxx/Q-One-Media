# PLAN.md — Kế hoạch và hiện trạng

**Cập nhật:** 13/09/2026 · **Đặc tả:** `docs/phuong-an-cuoi-cung.md` · **Hướng dẫn agent:** `AGENTS.md`

> File này là **nguồn duy nhất về trạng thái**. Mọi agent đọc file này trước khi làm, và cập nhật nó sau khi làm. Đừng viết báo cáo riêng.

---

## 1. Hiện trạng — một dòng

**Khung dự án đã dựng (Docker, schema DB, hướng dẫn agent). Chưa có code chạy được. Đang ở G0: chờ kiểm chứng khả thi và 5 quyết định của người dùng.**

| | |
|---|---|
| Mốc hiện tại | **G0 — Kiểm chứng khả thi** |
| Tiến độ tổng | ~5% (khung + đặc tả xong, code chưa) |
| Chặn lớn nhất | Chưa biết **có đủ nguồn video có license** hay không |
| Việc tiếp theo | Ba việc ở mục 4, làm song song được |

---

## 2. Đã xong

- [x] Khảo sát công nghệ 7 khâu pipeline, xác minh từ nguồn gốc
- [x] Quét nmi.vn (SPA không SSR) — lấy được taxonomy, corpus song ngữ, brand kit
- [x] Đánh giá 20 dự án mã nguồn mở theo star / license / độ sống
- [x] Chốt stack: VideoLingo + VoxCPM2 + script Easel + publish tự viết
- [x] Xác minh VoxCPM2 Apache-2.0 và có tiếng Việt (HF model card)
- [x] Xác minh ràng buộc API: YouTube quota, Facebook Reels, TikTok audit
- [x] Gộp mọi khảo sát vào một đặc tả `docs/phuong-an-cuoi-cung.md`
- [x] Dọn 13 file `.whl` lẫn vào repo và 5 tài liệu trung gian
- [x] `AGENTS.md` + `CLAUDE.md` — quy tắc token, không subagent, kỷ luật test
- [x] Docker: base + dev + prod tách rõ, state bind mount vào `./data/`
- [x] Schema DB: `sources`, `items`, `publications`, `jobs`, `glossary`, `audit_log`
- [x] Makefile, `.gitignore`, `.env.*.example`

---

## 3. Bảng việc theo mốc

Ký hiệu: `[ ]` chưa làm · `[~]` đang làm · `[x]` xong · `[!]` bị chặn

### G0 — Kiểm chứng khả thi (tuần 1)

Mục tiêu: trả lời **tải được từ đâu · nguồn nào có phép · giọng nào dùng được**.

- [ ] **G0.1** Gửi thư xin phép 3–5 hãng thiết bị *(không cần kỹ sư — ROI cao nhất)*
- [ ] **G0.2** Đọc điều khoản media kit của 3–5 hãng, ghi vào `sources`
- [ ] **G0.3** Test `yt-dlp` trên URL thật **từng nền tảng** — Douyin dễ vỡ nhất
- [ ] **G0.4** Dựng VideoLingo, chạy 1 video với `target_language: 'Tiếng Việt'`
- [ ] **G0.5** Blind test giọng: VoxCPM2 vs FPT.AI vs Viettel bằng thuật ngữ SPC/MSA thật
- [ ] **G0.6** Clone thử giọng một kỹ sư NMI bằng VoxCPM2
- [ ] **G0.7** Đo tốc độ đọc thật của giọng đã chọn (âm tiết/giây) → ngân sách kịch bản
- [ ] **G0.8** Test glyph tiếng Việt: render chuỗi đủ dấu, soi mắt *(bẫy libass, F2.2)*
- [ ] **G0.9** Test `reframe.py` chế độ `blur` trên 1 video công nghiệp 16:9
- [ ] **G0.10** Xác nhận GPU khả dụng trong Docker (`nvidia-smi` trong worker)
- [ ] **G0.11** Kiểm `edge-tts --list-voices | grep vi-VN`

### G1 — Làm tay có công cụ (tuần 2–3)

- [ ] **G1.1** Vendor code: VideoLingo + script Easel vào `vendor/` kèm `ORIGIN.md`
- [ ] **G1.2** Làm 5 video bằng tay, **mỗi nền tảng ít nhất 1**
- [ ] **G1.3** Rút glossary EN↔VI và ZH↔VI từ corpus `research/nmi-scan/` → bảng `glossary`
- [ ] **G1.4** Ghi lại thời gian thật mỗi video theo nền tảng và ngôn ngữ nguồn
- [ ] **G1.5** Chốt style phụ đề ASS (font đã test glyph, palette `#081120`)

### G2 — Tự động hoá pipeline lõi (tuần 3–6)

- [ ] **G2.1** `src/shared/` — config, paths, logging
- [ ] **G2.2** `src/db/` — model SQLAlchemy + alembic từ schema đã có
- [ ] **G2.3** `src/api/` — hộp thư URL, CRUD `sources`, **license gate**
- [ ] **G2.4** `src/ingest/` — yt-dlp wrapper + **nhánh Douyin tải đồng bộ**
- [ ] **G2.5** Job queue trên Postgres (`FOR UPDATE SKIP LOCKED`)
- [ ] **G2.6** Worker: ASR (WhisperX) + Demucs
- [ ] **G2.7** Chọn đoạn bằng LLM (prompt tiêu chí kỹ thuật, không phải "điểm cười")
- [ ] **G2.8** Viết kịch bản Việt + glossary + **ngân sách âm tiết theo cảnh**
- [ ] **G2.9** `src/tts/` — adapter VoxCPM2, interface cho phép đổi sang FPT.AI
- [ ] **G2.10** Forced alignment: kịch bản đã biết ↔ audio TTS
- [ ] **G2.11** Trộn audio: Demucs + sidechain duck + `loudnorm`
- [ ] **G2.12** Reframe **có điều kiện** (bỏ qua nếu nguồn đã 9:16)
- [ ] **G2.13** Render: burn ASS + intro/outro + thẻ ghi nguồn
- [ ] **G2.14** Gate duyệt của người + UI tối giản
- [ ] **G2.15** Workflow n8n nối các bước

### G3 — Publish YouTube (tuần 5–7)

- [ ] **G3.1** GCP project + OAuth consent + credential
- [ ] **G3.2** `src/publish/` — interface `publish(video, metadata, platform)`
- [ ] **G3.3** Adapter YouTube Data API (`videos.insert`, 100/ngày)
- [ ] **G3.4** Video công khai đầu tiên

### G4 — Facebook (tuần 7–9)

- [ ] **G4.1** Page + Business Manager + app
- [ ] **G4.2** Thử ngoại lệ App Review cho app nội bộ; nếu không thì nộp review
- [ ] **G4.3** Adapter Graph API cho Reels

### G5 — Đánh giá GĐ1 (tuần 9–11)

- [ ] **G5.1** Số liệu engagement theo nền tảng và dạng nội dung
- [ ] **G5.2** Nguồn có bền không? Nền tảng nguồn nào tốt nhất?
- [ ] **G5.3** Công duyệt thực tế so với ước tính 13–22 giờ/tháng
- [ ] **G5.4** Quyết định: mở rộng GĐ1 hay sang GĐ2

### G6 — Giai đoạn 2 (tuần 11–15)

- [ ] **G6.1** Crawler text cho website đã khai báo (`content_type='article'`)
- [ ] **G6.2** Lọc relevance theo taxonomy nmi.vn
- [ ] **G6.3** **Prompt đa nguồn (3–5 bài) + lưu vết nguồn** *(ràng buộc pháp lý, D.1)*
- [ ] **G6.4** Thư viện ảnh phân lớp: ảnh NMI → stock → AI chỉ cho bối cảnh
- [ ] **G6.5** Render biểu đồ và bảng so sánh từ số liệu thật
- [ ] **G6.6** Template Remotion đúng brand *(xác minh license trước)*
- [ ] **G6.7** Dùng lại tầng publish, giọng, glossary của GĐ1

### G7 — Tuỳ chọn (tuần 15+)

- [ ] **G7.1** TikTok — chỉ nếu dữ liệu G5 chứng minh đáng làm
- [ ] **G7.2** Bản tiếng Anh *(nội dung song ngữ đã có, chỉ tốn TTS)*
- [ ] **G7.3** LinkedIn

---

## 4. Ba việc làm ngay, không cần chờ nhau

1. **G0.1 — Gửi thư xin phép 3–5 hãng.** Không cần kỹ sư. Nếu một hãng đồng ý, rủi ro pháp lý GĐ1 chuyển thành quy trình tuân thủ bình thường.
2. **G0.4 + G0.5 — Dựng VideoLingo + VoxCPM2, chạy một video thật.** Nửa ngày, trả lời cùng lúc: chất lượng dịch thuật ngữ, chất lượng giọng Việt, pipeline có chạy trên máy bạn không.
3. **G0.3 — Test yt-dlp trên URL thật từng nền tảng.** Douyin dễ vỡ nhất; biết ở tuần 1 chứ không phải tuần 6.

---

## 5. Còn cần bạn quyết

Agent: làm hết phần **không** phụ thuộc các câu này. Đừng dừng chờ.

| # | Câu hỏi | Chặn việc gì |
|---|---|---|
| Q1 | **NMI là đại lý/NPP của hãng nào?** Hợp đồng có gồm **quyền sửa audio** không? | G0.2, toàn bộ license gate |
| Q2 | **Có GPU ≥8 GB VRAM không?** | G0.10, mô hình chi phí |
| Q3 | **5–10 URL nguồn thật** | G0.3, G1.2 |
| Q4 | **Tỷ lệ nguồn tiếng Trung vs Anh?** Có ai đọc được tiếng Trung? | Volume mục tiêu, G1.4 |
| Q5 | **Ai duyệt, bao nhiêu giờ/tuần?** | Volume mục tiêu |
| Q6 | **Giọng:** clone kỹ sư NMI hay giọng tổng hợp? Nam/nữ, vùng miền? | G0.5, G0.6 |
| Q7 | **Có giữ TikTok trong phạm vi?** | G7.1 |
| Q8 | **Có làm bản tiếng Anh?** | G7.2 |

---

## 6. Quyết định đã chốt (decision log)

| # | Quyết định | Lý do | Ngày |
|---|---|---|---|
| D1 | Giai đoạn 1 là luồng video tái sử dụng; Giai đoạn 2 là text→video | Yêu cầu của NMI | 13/09 |
| D2 | GĐ1 làm **cả lồng tiếng và phụ đề** | Yêu cầu của NMI; tăng mức biến đổi → tốt cho chính sách nền tảng | 13/09 |
| D3 | nmi.vn **không** phải nguồn nội dung — là glossary, taxonomy, brand kit | Website của chính NMI | 13/09 |
| D4 | Nguồn đa nền tảng qua **hộp thư URL**, không xây crawler từng nền tảng | Douyin/TikTok/FB không có API công khai và chống scraper | 13/09 |
| D5 | **VideoLingo** làm xương sống | Đã có yt-dlp + Demucs + WhisperX; Apache-2.0 | 13/09 |
| D6 | **VoxCPM2** làm TTS, gọi trực tiếp (không qua VoiceStudio) | Apache-2.0 + có tiếng Việt + clone; tránh AGPL của VoiceStudio | 13/09 |
| D7 | Engine mặc định VoiceStudio (OmniVoice) **bị loại** | Weights CC-BY-NC → không dùng thương mại | 13/09 |
| D8 | Loại mọi GPL/AGPL khỏi đường sản xuất | NMI là doanh nghiệp thương mại | 13/09 |
| D9 | Reframe mặc định **`blur`**, không phải crop | Video công nghiệp: toàn khung mang thông tin | 13/09 |
| D10 | Timing phụ đề bằng **forced alignment**, không ASR lại | Chữ đã biết → không thể sai | 13/09 |
| D11 | Giữ tiếng máy (Demucs bỏ stem giọng, giữ ambience) | Tiếng máy làm video đáng tin với khán giả kỹ thuật |13/09 |
| D12 | Job queue trên **Postgres**, không thêm Redis | Ít thành phần hơn; `FOR UPDATE SKIP LOCKED` là đủ | 13/09 |
| D13 | `data/models/` **dùng chung** dev/prod | Model là artifact bất biến, không phải state; ~10 GB | 13/09 |
| D14 | TikTok ưu tiên thấp nhất | Khán giả là quản lý nhà máy (YouTube/Facebook); TikTok API khắt khe nhất | 13/09 |

---

## 7. Rủi ro đang theo dõi

| Rủi ro | Mức | Trạng thái |
|---|---|---|
| Không đủ nguồn video có license | **Cao** | Đang chờ G0.1, G0.2 |
| Giọng Việt VoxCPM2 chưa đạt | Trung bình | Chờ G0.5. Dự phòng: FPT.AI qua cùng interface |
| Transcript nguồn tiếng Trung sai nhiều (~12,8% CER) | Trung bình | Chờ Q4 — cần người đọc được tiếng Trung |
| Công người duyệt không kham được | Trung bình | Chờ Q5 |
| Không có GPU | Trung bình | Chờ Q2 |
| Remotion company license (GĐ2) | Thấp | Chưa cần tới G6.6 |

---

## 8. Nhật ký

| Ngày | Việc |
|---|---|
| 13/09/2026 | Khảo sát công nghệ, quét nmi.vn, đánh giá 20 dự án OSS, chốt stack, dựng khung Docker + schema + AGENTS.md, dọn 13 file `.whl` và 5 tài liệu trung gian |
