# PLAN.md — Kế hoạch và hiện trạng

**Cập nhật:** 13/09/2026 · **Đặc tả:** `docs/phuong-an-cuoi-cung.md` · **Hướng dẫn agent:** `AGENTS.md`

> File này là **nguồn duy nhất về trạng thái**. Mọi agent đọc file này trước khi làm, và cập nhật nó sau khi làm. Đừng viết báo cáo riêng.

---

## 1. Hiện trạng — một dòng

**Lõi đã chạy thật: license gate + hộp thư URL + hàng đợi việc, trên Postgres trong Docker. Các bước media (ASR, TTS, render, publish) chưa có. Vẫn chờ G0 kiểm chứng khả thi và 5 quyết định của người dùng.**

| | |
|---|---|
| Mốc hiện tại | **G2 + GW xong về code** · G0 vẫn mở và giờ đã thành đường găng |
| Tiến độ tổng | ~75% code Giai đoạn 1; các bước cần GPU/credential chưa chạy thật |
| Chặn lớn nhất | Chưa biết **có đủ nguồn video có license** hay không |
| Đã kiểm chứng | **226 unit + 43 integration + 8 GPU** test xanh, ruff sạch; **`make smoke` ra video 9:16 thật có phụ đề tiếng Việt, phát được trong `/web/review`**; 77 thuật ngữ đã nạp vào `glossary`; **image worker chạy được model thật trên GPU** (Python 3.11 bản chính thức, torch 2.6+cu124, ctranslate2 4.8.2 khớp cuDNN 9) |
| Việc tiếp theo | **Chỉ còn chờ bạn**: `ANTHROPIC_API_KEY` cho hai bước LLM (chọn đoạn, viết kịch bản) và URL nguồn có quyền để test bước tải thật. Mọi thứ khác trong chuỗi đã chạy được với model thật |

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
- [x] **Tầng domain** (Clean Architecture + DDD): 4 bounded context, thuần stdlib
- [x] **License gate là kiểu dữ liệu** — clearance chỉ `Source` cấp được, không đi vòng được
- [x] **Bịt lỗ xác minh chủ sở hữu** — duyệt một kênh không mở quyền cho cả nền tảng
- [x] **Tầng application**: use case khai báo/duyệt nguồn, hộp thư URL, tải, duyệt nội dung, publish
- [x] **Tầng infrastructure**: ORM + mapper + repository + UoW trên Postgres; adapter yt-dlp
- [x] **FastAPI** `/sources` `/items` `/healthz` `/readyz` + worker vòng lặp hàng đợi
- [x] Kiểm chứng thật: API boot, `/readyz` 200, vòng đời license gate đầu-cuối qua HTTP, CHECK constraint chặn cả `UPDATE` tay

---

## 3. Bảng việc theo mốc

Ký hiệu: `[ ]` chưa làm · `[~]` đang làm · `[x]` xong · `[!]` bị chặn

### G0 — Kiểm chứng khả thi (tuần 1)

Mục tiêu: trả lời **tải được từ đâu · nguồn nào có phép · giọng nào dùng được**.

- [ ] **G0.1** Gửi thư xin phép 3–5 hãng thiết bị *(không cần kỹ sư — ROI cao nhất)*
- [ ] **G0.2** Đọc điều khoản media kit của 3–5 hãng, ghi vào `sources`
- [~] **G0.3** `YtDlpProbe` chạy đúng trên URL YouTube thật (channel_id, duration, kích thước). **Chỉ đọc metadata công khai, không tải nội dung** — license gate cấm, và đó đúng là bước bảo vệ quyền. Còn phải test Douyin/Bilibili/Facebook
- [x] **G0.4** Không dùng VideoLingo nữa (D23). **`make smoke` chạy toàn chuỗi ra video thật trên GPU**: Demucs tách stem thật, gióng phụ đề bằng word timestamp của `large-v3` (khớp 0,95), reframe blur 1280×720 → 720×1280, trộn có ducking ở −20 dB, burn phụ đề Be Vietnam Pro, `loudnorm`. Còn giả đúng hai chỗ: bước tải (dùng `lavfi`) và hai bước LLM — cả hai chờ `ANTHROPIC_API_KEY` và URL nguồn có quyền
- [ ] **G0.5** Blind test giọng: VoxCPM2 vs FPT.AI vs Viettel bằng thuật ngữ SPC/MSA thật
- [ ] **G0.6** Clone thử giọng một kỹ sư NMI bằng VoxCPM2
- [~] **G0.7** `make speech-rate` đo tự động. **Đo được 3,54 âm tiết/giây** với edge-tts — các nguồn trên mạng ghi 5,28–6, lệch ~40%. Còn phải đo lại với VoxCPM2
- [x] **G0.8** Be Vietnam Pro **đạt** với chuỗi đủ dấu, kiểm bằng libass thật. `make fonts` tải font, `check_font_covers_vietnamese()` kiểm tự động
- [x] **G0.9** `reframe.py` chế độ `blur` chạy với ffmpeg thật (integration test) — 16:9 → 9:16 không cắt hình
- [x] **G0.10** GPU chạy trong Docker: **RTX 3070, 8 GB VRAM**, driver 595.97. Đã đo thật (`make measure-load`): Demucs 0,54 GB · Whisper `large-v3` float16 ~3,5 GB · **VoxCPM2 5,12 GB**. Cộng lại vượt 8 GB nên **không thể cùng ở trên card** — chạy tuần tự và nhả VRAM sau mỗi model (`src/shared/gpu.py`, D54). Nạp lại tốn 17,5 s (Whisper) và 31,9 s (VoxCPM2)
- [x] **G0.11** Đúng **2 giọng** tiếng Việt: `vi-VN-HoaiMyNeural` (nữ), `vi-VN-NamMinhNeural` (nam). Đã thành engine `edge` **chỉ cho dev**

### G1 — Làm tay có công cụ (tuần 2–3)

- [x] **G1.1** Đổi khung hình và trộn audio **viết lại thành module của dự án** (`src/infrastructure/media/reframe.py`, `ffmpeg.mix_voice_over_background`), thuật toán tham khảo Easel (Apache-2.0) — khai trong `THIRD_PARTY_NOTICES.md`. **Không lấy gì từ VideoLingo** — xem D23
- [ ] **G1.2** Làm 5 video bằng tay, **mỗi nền tảng ít nhất 1**
- [~] **G1.3** `make corpus` + `make glossary-load`. **77 thuật ngữ EN đã nạp** từ corpus thật (PLC 107×, MES 63×, SPC 42×, Gage R&R 22×, Cpk 15×, OPC UA 14×) — tất cả là *giữ nguyên tiếng Anh*. Còn thiếu: cặp có bản tiếng Việt, và chiều ZH↔VI
- [ ] **G1.4** Ghi lại thời gian thật mỗi video theo nền tảng và ngôn ngữ nguồn
- [ ] **G1.5** Chốt style phụ đề ASS (font đã test glyph, palette `#081120`)

### G2 — Tự động hoá pipeline lõi (tuần 3–6)

- [x] **G2.1** `src/shared/` — config, paths, logging
- [x] **G2.2** `src/infrastructure/db/` — ORM + mapper + repository + UoW + **Alembic là nguồn sự thật duy nhất của schema** (baseline idempotent, `make migrate`). Test tích hợp chạy trên DB `<db>_test` riêng nên không xoá dữ liệu dev
- [x] **G2.3** `src/interfaces/api/` — hộp thư URL, CRUD `sources`, **license gate** + xác minh chủ sở hữu
- [~] **G2.4** `src/infrastructure/ingest/ytdlp.py` — wrapper + probe metadata xong; ưu tiên khẩn cho Douyin xong. **Chưa test trên URL Douyin thật** (G0.3)
- [x] **G2.5** Job queue trên Postgres (`FOR UPDATE SKIP LOCKED`) + thu hồi việc của worker đã chết
- [x] **G2.6** Adapter + handler worker xong, **đã chạy với model thật trên GPU**: Demucs tách stem, Whisper `large-v3` nhận dạng, gióng phụ đề, VoxCPM2 sinh giọng — cả bốn tuần tự trên một card 8 GB, canh bằng `make test-gpu`
- [~] **G2.7** Prompt + kiểm đầu ra + handler xong; **chưa gọi API thật**
- [~] **G2.8** Prompt + ngân sách âm tiết xong; glossary chờ G1.3
- [x] **G2.9** VoxCPM2 + FPT.AI sau cùng port xong. **VoxCPM2 đã sinh giọng tiếng Việt thật trên GPU** (`openbmb/VoxCPM2`, sample rate 48 kHz đọc từ model chứ không đoán). Còn lại là blind test chọn giọng (G0.5) — việc đánh giá, không phải việc code
- [x] **G2.10** `align_known_text()` + gộp dòng phụ đề, **đã chạy với model thật trên GPU**. Không dùng model gióng của WhisperX: `nguyenvulebinh/wav2vec2-base-vi` là `cc-by-nc-4.0` (không thương mại được) và lại thiếu CTC head nên timing vô nghĩa mà không báo lỗi (D49). Thay bằng word timestamp của `large-v3` — **chữ trong phụ đề vẫn là chữ mình viết**, Whisper chỉ cấp thời gian. Bỏ WhisperX hoàn toàn (D53)
- [x] **G2.11** Trộn audio qua Easel `audio_mix` (nền −20 dB) + `loudnorm`
- [x] **G2.12** Reframe có điều kiện, chế độ `blur` — test với ffmpeg thật
- [x] **G2.13** Render: cắt → reframe → trộn → burn ASS + thẻ ghi nguồn → `loudnorm`. Test với ffmpeg thật
- [x] **G2.14** Hai gate người: soát transcript và duyệt thành phẩm. Dây nối worker **cố tình đứt** ở đúng hai chỗ đó
- [!] **G2.15** Workflow n8n — **không còn cần** cho dòng chảy chính: worker tự nối bước qua hàng đợi. Giữ n8n cho thông báo và trigger định kỳ (xem D29)

### GW — Mặt tiền web nội bộ (xen vào giữa G2 và G3)

Vì sao cần, không phải cho đẹp: **gate duyệt của người là bắt buộc ở Giai đoạn 1** và tốn 20–35 phút/video (nguồn en) hoặc 35–55 phút (nguồn zh). Người duyệt là quản lý nội dung/chất lượng, không phải dev — không thể bắt họ bấm `POST /items/12/approve` trong Swagger. **Mọi video đều đi qua đúng cửa đó**, nên cửa đó phải dùng được.

Quyết định kỹ thuật: **Jinja2 + HTMX server-rendered**, không SPA — xem D21. Sống ở `src/interfaces/web/`, dùng lại đúng use case đã có, **không thêm một dòng nghiệp vụ nào**.

- [x] **GW.1** Trang khai báo + duyệt nguồn — dùng được ngay hôm nay
- [x] **GW.2** Trang soát transcript ngoại ngữ (bước ⑥)
- [x] **GW.3** Trang duyệt video: phát video, đọc kịch bản, approve / reject / trả về viết lại
- [x] **GW.4** Dashboard: item theo từng bước + công duyệt tồn + hộp thư URL
- [x] **GW.5** Phục vụ `media/output` chỉ đọc; `source/` và `work/` không ra HTTP
- [x] **GW.6** Basic auth (`WEB_USER`/`WEB_PASSWORD`), **bắt buộc ở prod**; `/healthz`+`/readyz` luôn mở

**Không làm:** CMS, quản lý người dùng/phân quyền, trang phân tích engagement. 2–5 người nội bộ.

### G3 — Publish YouTube (tuần 5–7)

- [ ] **G3.1** GCP project + OAuth consent + credential
- [x] **G3.2** `src/infrastructure/publish/` — registry bỏ qua nền tảng chưa cấu hình
- [~] **G3.3** Adapter YouTube (resumable upload, mặc định `private`); **chờ credential G3.1**
- [ ] **G3.4** Video công khai đầu tiên

### G4 — Facebook (tuần 7–9)

- [ ] **G4.1** Page + Business Manager + app
- [ ] **G4.2** Thử ngoại lệ App Review cho app nội bộ; nếu không thì nộp review
- [~] **G4.3** Adapter Facebook Reels (3 pha start/upload/finish); **chờ Page + token G4.1**

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
| D15 | **Clean Architecture + DDD**, `domain/` thuần stdlib | Quy tắc license test được trong < 1s, không DB/GPU/token; đổi hạ tầng không sửa nghiệp vụ | 13/09 |
| D16 | **License gate là kiểu dữ liệu** (clearance), không phải câu `if` | Câu `if` bị quên hoặc bị đường code mới đi vòng; clearance thì trình kiểm tra kiểu bắt lỗi ngay | 13/09 |
| D17 | **Bỏ `REQUIRE_LICENSE_APPROVAL` / `REQUIRE_HUMAN_REVIEW` khỏi env** | Một cờ có thể đặt `false` *chính là* đường tắt mà quy tắc nghiệp vụ cấm. Giữ `PUBLISH_ENABLED` vì nó chỉ chặn thêm | 13/09 |
| D18 | Thêm `sources.external_owner_id`, bắt buộc với nguồn dạng bao | Khớp theo host nghĩa là duyệt một kênh YouTube mở cửa cho mọi URL youtube.com — lỗ thật, và nó đi qua im lặng | 13/09 |
| D19 | **Không vendor `core/_1_ytdlp.py`** của VideoLingo, tự viết adapter | Upstream chạy `pip install --upgrade yt-dlp` mỗi lần tải, ghi vào `output/` toàn cục, và gắn cứng `config.yaml` | 13/09 |
| D20 | Mapper viết tay, không để ORM map thẳng vào entity | Value object phải kiểm bất biến **cả khi** dữ liệu đến từ DB — một dòng hỏng nổ lúc đọc, không lẳng lặng qua gate | 13/09 |
| D21 | Mặt tiền web là **Jinja2 + HTMX server-rendered**, không React/Vue | 2–5 người dùng nội bộ. SPA đòi npm + một Dockerfile + một container nữa mà không mua được gì; phần khó nhất là phát video, HTML thuần làm tốt nhất | 13/09 |
| D22 | Theo dõi pipeline/retry/thông báo dùng **n8n**, không tự viết | n8n đã trong stack và có UI sẵn. Tự viết lại là trùng việc | 13/09 |
| D23 | **Không vendor gì từ VideoLingo**, gọi `whisperx`/`demucs` trực tiếp | Bề mặt dùng lại được thật ra nhỏ: prompt của họ là *dịch từng câu*, còn GĐ1 *viết lại*; phần Demucs/WhisperX chỉ là ~50 dòng keo quanh thư viện đã pin sẵn | 13/09 |
| D24 | Alembic là nguồn duy nhất của schema, `init/` chỉ còn schema n8n | Hai bản DDL song song chắc chắn lệch nhau; lệch ở `sources` là lệch ở kiểm soát pháp lý | 13/09 |
| D25 | Mặt tiền web **không có JavaScript nào** (form POST + redirect), bỏ cả HTMX | Kế hoạch ghi "Jinja2 + HTMX" nhưng khi viết thì form đủ. Trang chạy được khi nhà máy không có internet ra ngoài — giá trị thật cho công cụ on-prem | 14/09 |
| D26 | Chỉ mount `media/output` ra HTTP, không mount cả `MEDIA_ROOT` | `source/` chứa video gốc của người khác, `work/` chứa file trung gian — không có lý do gì để chúng ra được HTTP | 14/09 |
| D27 | `WEB_USER`/`WEB_PASSWORD` **bắt buộc ở prod**, chặn ngay khi đọc config | Không tin vào việc bind `127.0.0.1`: một lần thêm reverse proxy là trang duyệt nội dung thành công khai, và không ai nhận ra | 14/09 |
| D28 | Chọn đoạn: **tự lấy đề xuất đầu của LLM**, lưu cả danh sách kèm lý do | Sơ đồ ghi "LLM đề xuất → người chọn", nhưng GĐ1 đã có hai gate người; gate thứ ba đẩy công duyệt vượt xa mức 13–22 giờ/tháng đã ước lượng. Người duyệt cuối vẫn trả về được |
| D29 | Worker **tự nối bước** qua hàng đợi; n8n không nằm trên dòng chảy chính | Mỗi bước xếp việc tiếp theo nên tự retry được và worker chết giữa đường không mất chuỗi. n8n giữ lại cho thông báo và trigger định kỳ, không phải để nối bước |
| D30 | Không có `JobTask.MIX` / `JobTask.REFRAME` riêng | Hai việc đó nằm trong `render`: tách ra thì mỗi bước phải encode lại một lần nữa. Và một `JobTask` không có handler là mời một job treo vĩnh viễn |
| D31 | Thêm engine TTS `edge` **chỉ cho dev**, chặn ở prod bằng hai lớp | Cho chạy toàn chuỗi không cần GPU. Nhưng `edge-tts` là client *không chính thức* của dịch vụ Microsoft Edge nên điều khoản thương mại không rõ — dự án đã bỏ OmniVoice vì đúng loại vấn đề đó (CC-BY-NC), giữ một chuẩn thì phải giữ cả ở đây |
| D32 | `edge-tts` **không pin phiên bản cứng** (`>=7.2.8`) | Bản 7.0.2 bị HTTP 403 ở handshake trong khi 7.2.8 chạy được: client không chính thức phải chạy theo thay đổi của Microsoft. Đây cũng là lý do kỹ thuật để không dùng ở production |
| D33 | Font tải bằng script, **không commit `.ttf`** | Be Vietnam Pro license OFL nên tải lại lúc nào cũng được; tải trong Dockerfile thì build phụ thuộc mạng và không lặp lại được |
| D34 | Glossary: **`term_vi` để trống nghĩa là "giữ nguyên tiếng Anh"** | Corpus nmi.vn cho thấy NMI viết Cpk, MES, OPC UA, PLC nguyên dạng trong câu tiếng Việt vì người trong ngành gọi vậy. Dịch chúng ra làm nội dung *khó* đọc hơn với đúng nhóm cần đọc |
| D35 | Thuật ngữ rút tự động là **ứng viên cần người duyệt**, không nạp thẳng | Một thuật ngữ dịch sai đi vào **mọi** video sau đó. Script ghi ra TSV, người điền `term_vi`, rồi `make glossary-load` |
| D36 | `research/nmi-scan/` tái lập bằng script, **không commit bundle `.js`** | Tên file chứa hash nội dung nên đổi mỗi lần nmi.vn build lại — commit vào repo là commit một thứ hết hạn |
| D37 | Mọi biến container cần phải khai trong `x-common-env` của compose | `--env-file` chỉ thay biến trong *chính file compose*, không tự truyền vào container. Thiếu một dòng là code đọc ra `None` và một guard nổ giữa đường — đã xảy ra với `TTS_SYLLABLES_PER_SEC` |
| D38 | **Chỉ hai file compose**, mỗi file chạy độc lập — bỏ file base | Ba file với override lồng nhau khó đọc và khó đoán: phải ghép trong đầu mới biết một service thật ra chạy với cấu hình gì. Giá phải trả là lặp phần `x-env` giữa hai file; đổi lại mỗi file đọc một lượt là hiểu hết |
| D39 | Hardcode `dev`/`prod` trong đường dẫn thay vì `${APP_ENV}` | File đã tên là dev thì `${APP_ENV}` chỉ là một lớp gián tiếp không thêm thông tin, và là một chỗ nữa để đặt sai |
| D40 | Pin **`voxcpm==2.0.3`**, và chỉ định model **`openbmb/VoxCPM2`** tường minh | `voxcpm==0.5.0` trong `docker/worker/requirements.txt` **không tồn tại** — số đó do tôi đặt sai, lẫn tên model (VoxCPM-0.5B) thành số phiên bản package. Đặc tả ghi đúng `openbmb/VoxCPM2`. Đã xác minh lại hôm nay: repo Apache-2.0 37.149★, model card `license: apache-2.0` và có `vi` trong 30 ngôn ngữ. Và `VoxCPM-0.5B` chỉ có `en`/`zh`, **không có tiếng Việt**; chỉ `VoxCPM2` có `vi`. Để thư viện tự chọn là rủi ro nạp đúng model không dùng được |
| D41 | Worker bootstrap pip cho **đúng Python 3.11** bằng `get-pip.py` | Ubuntu 22.04 có `python3` = 3.10; gói `python3-pip` cài pip cho 3.10, nên mọi thư viện vào 3.10 rồi symlink `python` sang 3.11 và 3.11 không thấy gì. Build vẫn báo thành công. Code cần 3.11 thật (`StrEnum`, `datetime.UTC`). Đã thêm bước kiểm ngay trong Dockerfile |
| D42 | Python 3.11 của worker lấy từ **deadsnakes PPA**, không từ repo Ubuntu | `apt-cache policy python3.11` trên jammy-updates chỉ có **3.11.0~rc1** — một release candidate, không có bản ổn định nào trong repo distro. Base CUDA 12.4 lại chỉ có bản Ubuntu 22.04 (nvidia không publish 12.4 cho 24.04) nên không thoát được bằng cách đổi base mà không kéo theo đổi cả CUDA và torch. Dockerfile có bước kiểm chặn `'rc' in sys.version` |
| D43 | **torch >= 2.6** là yêu cầu cứng của worker, không phải chọn bản mới cho vui | WhisperX gióng `vi` bằng `nguyenvulebinh/wav2vec2-base-vi`, model phát hành dạng `.bin` chứ không phải safetensors. `transformers` 5.x từ chối `torch.load` khi torch < 2.6 (CVE-2025-32434). Với torch 2.5.1, `load_align_model('vi')` ném ValueError → **mất cơ chế timing phụ đề của F2.5**. Dockerfile có bước kiểm chặn |
| D44 | Test tích hợp chạy trên **DB riêng `<db>_test`**, tự tạo và tự migrate | Test `TRUNCATE ... CASCADE` để mỗi test có schema sạch. Chạy trên DB dev thì `make test-int` xoá sạch nguồn đã khai, item đang chờ duyệt và vết audit — đã xảy ra thật, một lần chạy test làm mất item demo đang mở trong trang duyệt. Dùng alembic chứ không `create_all()` để test chạy trên đúng schema production có (gồm CHECK và index một phần) |
| D45 | Worker image cần **`build-essential` như phụ thuộc lúc chạy** | VoxCPM2 dùng `torch.compile` (backend inductor); inductor sinh mã C++ rồi gọi compiler ngay trong lần suy luận đầu. Thiếu gcc thì nạp model ném `BackendCompilerFailed … Failed to find C compiler` — lỗi trông như lỗi model, thực ra thiếu gói hệ thống |
| D46 | Đọc `sample_rate` từ `model.tts_model`, **không dùng giá trị mặc định** | Lớp công khai `VoxCPM` bọc `tts_model` và không expose `sample_rate`. Mặc định 16000 là sai âm thầm theo cách tệ nhất: WAV sai tần số → audio phát sai tốc độ → độ dài đo sai → **ngân sách âm tiết sai theo**, và không ai truy ra được từ đâu |
| D47 | `load_denoiser=False` và `normalize=False` khi gọi VoxCPM2 | Denoiser là model riêng chỉ để làm sạch audio mẫu — trên card 8 GB thì mỗi GB đều đáng, và giọng mẫu nên được thu sạch từ đầu. Bộ chuẩn hoá văn bản của VoxCPM làm cho tiếng Trung/Anh, đưa tiếng Việt vào thì rủi ro đọc sai số; prompt viết kịch bản đã yêu cầu viết số thành chữ |
| D48 | Cho phép **tường minh** các class omegaconf cho `torch.load`, không tắt `weights_only` | torch 2.6 đổi mặc định `torch.load` sang `weights_only=True` — đúng về bảo mật, nhưng checkpoint VAD của pyannote (WhisperX dùng để cắt đoạn có tiếng) chứa object omegaconf đã pickle nên bị từ chối. Chọn allowlist đúng class cần thay vì `weights_only=False` cho mọi lần load. Rủi ro còn lại chấp nhận được vì model đến từ **id repo đã pin** và cache local; nếu về sau cho người dùng trỏ tới checkpoint của họ thì phải xem lại |
| D49 | **Không dùng forced alignment của WhisperX**; gióng bằng word timestamp của Whisper | Hai lý do độc lập. *License:* model `vi` duy nhất WhisperX trỏ tới là `nguyenvulebinh/wav2vec2-base-vi` — `cc-by-nc-4.0`, không dùng thương mại được; cả họ MMS của Meta cũng `cc-by-nc-4.0`, nên mọi model gióng tiếng Việt sẵn có đều NonCommercial. *Kỹ thuật:* model đó có tag `pretraining`, **không có CTC head** (`lm_head` khởi tạo ngẫu nhiên) → timing vô nghĩa mà không báo lỗi. Đường mới dùng `Systran/faster-whisper-large-v3` (MIT) + weights `openai/whisper-large-v3` (Apache-2.0); **chữ vẫn là chữ mình viết**, Whisper chỉ cấp thời gian |
| D50 | Xoá hẳn `align_known_text` khỏi `whisperx.py` thay vì để lại | Để hai đường tồn tại là mời người khác gọi nhầm vào đường NonCommercial |
| D51 | `del model` tường minh trước `_free_vram()` | Đo trên RTX 3070: khi large-v3 float16 chạy, VRAM rảnh về **0,00/8,0 GB**. CTranslate2 cấp bộ nhớ **ngoài** allocator của PyTorch nên `empty_cache()` một mình không nhả được gì. Trên card 8 GB, chạy tuần tự là **bắt buộc**, không phải thực hành tốt |
| D52 | Pin **`ctranslate2==4.8.2`** (>= 4.5), không để faster-whisper tự chọn | Bản 4.4.0 link với **cuDNN 8**, còn base image CUDA 12.4 và torch 2.6 đều mang **cuDNN 9** — không có cuDNN 8 ở đâu. CTranslate2 không nạp được `libcudnn_ops_infer.so.8` và **ABORT cứng cả tiến trình** (`Fatal Python error: Aborted`), không ném exception nên không handler nào bắt được. Nghĩa là **đường ASR trên GPU chưa từng chạy được một lần** — chỉ lộ ra khi chạy test GPU thật |
| D53 | **Bỏ WhisperX hoàn toàn**, dùng `faster-whisper` trực tiếp | `whisperx 3.3.1` khoá `ctranslate2<4.5` (cuDNN 8) nên không chạy được trên base cuDNN 9; `whisperx 3.8.6` cho phép ctranslate2 mới nhưng đòi `torch~=2.8`, tức một lần di trú nữa cho thứ **ta không còn cần**: phần giá trị nhất của nó là forced alignment, đã bị thay vì license (D49). Phần còn lại — gom batch và VAD — `faster-whisper` có sẵn. Kết quả: **một** đường ASR duy nhất cho cả nhận dạng lời nguồn và mốc thời gian phụ đề |
| D54 | **Không model nào được giữ trên card qua ranh giới lời gọi** — nạp trong hàm, nhả trong `finally` | Đảo lại thiết kế cũ của `voxcpm.py` (giữ model ở biến module-level cho suốt vòng đời tiến trình). Đo bằng `make measure-load` trên RTX 3070: VoxCPM2 giữ **5,12 GB** làm VRAM rảnh về **0,00/8,0 GB** — việc kế tiếp không nạp nổi Whisper (~3,5 GB). Lý do giữ model là để tránh 120,9 s nạp, nhưng nạp **lại** chỉ mất **31,9 s**: 89 s chênh là biên dịch kernel, trả một lần mỗi tiến trình. Đổi 32 s mỗi việc để không bao giờ `CUDA out of memory` là đổi đáng, nhất là khi mỗi video còn qua 20–35 phút người soát. Hàm nhả chuyển về `src/shared/gpu.py` để ba adapter dùng chung thay vì ba bản copy |
| D55 | **Bỏ hẳn khái niệm `vendor/`** — code mượn từ dự án mở được viết lại thành module của chính dự án | Quy tắc cũ ("sao nguyên byte, không được sửa, chỉ bọc adapter") nghe thì an toàn nhưng vừa trả giá thật: graph trộn audio của Easel thiếu `aformat` trước `sidechaincompress` nên đổ ngay khi bật ducking, mà luật cấm sửa lại đẩy chỗ chữa ra xa chỗ hỏng. Thêm nữa, adapter phải gọi script qua `subprocess`, nên lỗi về dưới dạng **tiếng Trung trên stderr** — không phân loại được retry được hay không, đúng thứ hàng đợi việc cần. Nay: đọc upstream, hiểu thuật toán, **viết lại** trong `src/` và sửa tự do. Nghĩa vụ Apache-2.0 chuyển sang `THIRD_PARTY_NOTICES.md` — ghi lấy gì, đưa vào đâu, **sửa những gì**, kèm toàn văn license. Bỏ luôn `subtitle_ops.py` (569 dòng chưa hề dùng) |

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
| **License model AI** — dễ lọt model NonCommercial vào đường sản xuất | **Cao** | Đã bắt 2 ca: OmniVoice (CC-BY-NC) và model gióng của WhisperX (cc-by-nc-4.0). Quy tắc: **kiểm license weights trên HF model card trước khi thêm bất kỳ model nào**, không tin license của code |

---

## 8. Nhật ký

| Ngày | Việc |
|---|---|
| 13/09/2026 | Khảo sát công nghệ, quét nmi.vn, đánh giá 20 dự án OSS, chốt stack, dựng khung Docker + schema + AGENTS.md, dọn 13 file `.whl` và 5 tài liệu trung gian |
| 13/09/2026 | Code lõi: domain 4 bounded context → application use case → infrastructure Postgres → FastAPI + worker. 4 commit. Bịt lỗ xác minh chủ sở hữu trong license gate. 112 unit + 12 integration test xanh. Sửa 4 bug do test bắt được (xem nhật ký commit) |
| 14/09/2026 | Alembic thành nguồn duy nhất của schema · vendor Easel · tầng media (ffmpeg + ASS + render) · TTS + ngân sách âm tiết · ASR/Demucs/alignment · LLM chọn đoạn + viết kịch bản · publish YouTube/Facebook · mặt tiền web nội bộ · nối dây worker. 191 unit + 43 integration test |
| 14/09/2026 | Viết nốt 4 script vận hành (`fetch_models`, `fetch_fonts`, `measure_speech_rate`, `youtube_authorize`) · G0.8 + G0.11 xong bằng kiểm chứng thật · engine `edge` cho phép chạy toàn chuỗi **không cần GPU** · đo được tốc độ đọc 3,54 âm tiết/giây |
| 14/09/2026 | G1.3: tái lập `research/nmi-scan/` bằng script (tham chiếu treo trong tài liệu — thư mục chưa từng tồn tại), rút 77 thuật ngữ từ corpus thật và nạp vào bảng `glossary` |
| 14/09/2026 | `make smoke` chạy toàn chuỗi không cần GPU → video 9:16 thật có phụ đề tiếng Việt, phát được trong trang duyệt. Ba bug thật lộ ra khi chạy (xem nhật ký commit) |
