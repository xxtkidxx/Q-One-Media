# PLAN.md — Kế hoạch và hiện trạng

**Cập nhật:** 13/09/2026 · **Đặc tả:** `docs/phuong-an-cuoi-cung.md` · **Hướng dẫn agent:** `AGENTS.md`

> File này là **nguồn duy nhất về trạng thái**. Mọi agent đọc file này trước khi làm, và cập nhật nó sau khi làm. Đừng viết báo cáo riêng.

---

## 1. Hiện trạng — một dòng

**Lõi đã chạy thật: license gate + hộp thư URL + hàng đợi việc, trên Postgres trong Docker. Các bước media (ASR, TTS, render, publish) chưa có. Vẫn chờ G0 kiểm chứng khả thi và các quyết định đầu vào của người dùng.**

| | |
|---|---|
| Mốc hiện tại | **G2 + GW xong về code** · G0 vẫn mở và giờ đã thành đường găng |
| Tiến độ tổng | ~75% code Giai đoạn 1; các bước cần GPU/credential chưa chạy thật |
| Chặn lớn nhất | Cần nhập URL nguồn thật và bằng chứng giấy phép sẵn có vào `sources` để chạy bước tải thật |
| Đã kiểm chứng | **226 unit + 43 integration + 8 GPU** test xanh, ruff sạch; **`make smoke` ra video 9:16 thật có phụ đề tiếng Việt, phát được trong `/review`**; 77 thuật ngữ đã nạp vào `glossary`; **image worker chạy được model thật trên GPU** (Python 3.11 bản chính thức, torch 2.6+cu124, ctranslate2 4.8.2 khớp cuDNN 9) |
| Việc tiếp theo | **Chỉ còn chờ bạn**: `GEMINI_API_KEY` (free tier được) cho hai bước LLM (chọn đoạn, viết kịch bản) và URL nguồn có quyền để test bước tải thật. Mọi thứ khác trong chuỗi đã chạy được với model thật |

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

Mục tiêu: trả lời **tải được từ đâu · giấy phép sẵn có áp dụng cho nguồn nào · giọng nào dùng được**.

- [ ] **G0.2** Đối chiếu giấy phép/hợp đồng sẵn có với từng chủ nguồn, ghi phạm vi quyền và bằng chứng vào `sources`
- [~] **G0.3** YouTube đã chạy trên hai video thật. Mới nhất: CQE Academy `H6St9mCKWuA`, probe đúng `channel_id=UCTpQaKtfp1LIPKXHX0q0u7g`, 956 giây, 1920×1080; source #6 được duyệt theo xác nhận giấy phép của người dùng và yt-dlp tải thành công 35,6 MB. Ownership gate cũng từ chối đúng khi URL này bị thử dưới nguồn Blender (#1). **Chưa có URL source approved cho Douyin/Bilibili/Facebook nên chưa test ba nền tảng đó**
- [~] **G0.4** Pipeline video CQE Academy thật đã chạy hết đến gate `human_review` (item #7): license gate → tải → Demucs GPU → Whisper `large-v3` GPU → người soát transcript → LLM chọn đoạn/viết kịch bản → VoxCPM2 → align → render đều xanh. Đoạn chọn 302–372 giây; output `output/item-00000007/final.mp4`. Transcript nhận đúng nhiều thuật ngữ nhưng có lỗi Cp/Cpk/Pp/Ppk và lặp câu phút 8–11; còn người nghe duyệt chất lượng thành phẩm
- [~] **G0.5** VoxCPM2 sinh giọng Việt thật trên RTX 3070 với câu kỹ thuật; test xanh, VRAM đỉnh 6,15 GB và còn rảnh 5,43/8,0 GB sau khi nhả model. Mẫu nghe: `data/dev/media/output/g0-voice-test/voxcpm2-technical-vi.wav`. **Chưa blind test được với FPT.AI/Viettel vì chưa có credential và cần người nghe chấm**
- [ ] **G0.6** Clone thử giọng một kỹ sư NMI bằng VoxCPM2
- [~] **G0.7** `make speech-rate` đo tự động. **Đo được 3,54 âm tiết/giây** với edge-tts — các nguồn trên mạng ghi 5,28–6, lệch ~40%. Còn phải đo lại với VoxCPM2
- [x] **G0.8** Be Vietnam Pro **đạt** với chuỗi đủ dấu, kiểm bằng libass thật. `make fonts` tải font, `check_font_covers_vietnamese()` kiểm tự động
- [x] **G0.9** `reframe.py` chế độ `blur` chạy với ffmpeg thật (integration test) — 16:9 → 9:16 không cắt hình
- [x] **G0.10** GPU chạy trong Docker: **RTX 3070, 8 GB VRAM**, driver 595.97. Đã đo thật (`make measure-load`): Demucs 0,54 GB · Whisper `large-v3` float16 ~3,5 GB · **VoxCPM2 5,12 GB**. Cộng lại vượt 8 GB nên **không thể cùng ở trên card** — chạy tuần tự và nhả VRAM sau mỗi model (`src/shared/gpu.py`, D54). Nạp lại tốn 17,5 s (Whisper) và 31,9 s (VoxCPM2)
- [x] **G0.11** Đúng **2 giọng** tiếng Việt: `vi-VN-HoaiMyNeural` (nữ), `vi-VN-NamMinhNeural` (nam). Đã thành engine `edge` **chỉ cho dev**

### G1 — Làm tay có công cụ (tuần 2–3)

- [x] **G1.1** Đổi khung hình và trộn audio **viết lại thành module của dự án** (`src/infrastructure/media/reframe.py`, `ffmpeg.mix_voice_over_background`), thuật toán tham khảo Easel (Apache-2.0) — khai trong `docs/THIRD_PARTY_NOTICES.md`. **Không lấy gì từ VideoLingo** — xem D23
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
- [x] **G2.7** Prompt + kiểm đầu ra + handler xong; có registry chọn `gemini|anthropic`; gọi API thật thành công và chọn đoạn item #7
- [x] **G2.8** Prompt + ngân sách âm tiết xong; chỉ gửi transcript trong đoạn đã chọn; `gemini-3.5-flash-lite` viết kịch bản item #7 thành công, glossary đã nạp 77 thuật ngữ
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
- [x] **GW.6** Đăng nhập bằng session ký, tài khoản DB và RBAC 4 vai trò (`viewer`, `reviewer`, `editor`, `admin`); `/healthz`+`/readyz` luôn mở. Dev có sẵn bốn tài khoản để chọn ngay tại Login; production bootstrap admin từ `WEB_USER`/`WEB_PASSWORD` và bắt buộc `WEB_SESSION_SECRET`
- [x] **GW.7** Hợp nhất thao tác theo nguồn: mặc định hiện tất cả, lọc trạng thái, tìm kiếm, phân trang, popup thêm nguồn/video, lịch sử audit và tiến trình item ngay trong `/sources`
- [x] **GW.8** Người dùng chọn thủ công một hoặc nhiều khoảng thời gian; mỗi khoảng tạo một item con/pipeline độc lập. Ghi nguồn là tùy chọn, nhưng giấy phép bắt buộc attribution luôn được ưu tiên
- [x] **GW.9** Làm lại dashboard hiện đại theo KPI/trạng thái/việc cần xử lý; bỏ hộp nạp URL trùng chức năng với trang Nguồn
- [x] **GW.10** Nạp video là upload file thật (MP4/MOV/MKV/WebM), chọn nguồn đã duyệt, kiểm tra hình+tiếng bằng ffprobe rồi vào thẳng bước tách audio; nút hiện trực tiếp trên từng dòng nguồn. Mỗi item luôn có khối review đoạn và transcript theo timestamp
- [x] **GW.11** Form duyệt nguồn giải thích rõ người duyệt/license/bằng chứng/ghi nguồn và có nút gợi ý: tự điền quyền + attribution khi suy ra an toàn (`cc-by`, `own`), không tự cấp quyền hay bịa bằng chứng cho hợp đồng/media kit/stock
- [x] **GW.12** Rút gọn duyệt nguồn: bằng chứng và chuỗi ghi nguồn là phần bổ sung tùy chọn; bỏ trống thì lưu xác nhận nội bộ, riêng CC BY tự sinh attribution từ tên + URL nguồn
- [x] **GW.13** Thêm nguồn không tự tải. Mỗi nguồn `single-url` đã duyệt và chưa có item hiện nút “Start tải video” riêng; người dùng chủ động bắt đầu, hệ thống chống tạo trùng. Rút empty-state còn “Chưa có video”
- [x] **GW.14** Trạng thái item realtime bằng polling snapshot 3 giây: badge, thanh tiến trình và lỗi cập nhật không cần F5; tự reload khi tới gate cần người thao tác và giữ nguồn đang mở
- [x] **GW.15** Mã hiển thị theo nguồn: clip `#nguồn-số_clip` (ví dụ `#7-1`, `#7-2`), video cha có clip ghi `#7-gốc`. Progress ghi rõ `Bước x/15 · y% · tên bước` và cập nhật realtime
- [x] **GW.16** Tách trình biên tập transcript thành trang độc lập `/review/{item_id}`: video nguồn đồng bộ dòng phụ đề theo thời gian, sửa start/end/text, thêm/xóa/phát từng dòng và lưu/duyệt ngay tại trang. Hai mốc thời gian nằm cùng hàng trong cột gọn; nút phát dạng icon ở cuối dòng để dành tối đa chiều ngang cho phụ đề. Trang nguồn chỉ còn nút mở editor; trang review vẫn giữ gate duyệt video thành phẩm.
- [x] **GW.17** Chuẩn hóa phản hồi thao tác web thành toast nổi, tự đóng sau 6 giây và có nút đóng; lỗi nghiệp vụ cũng hiển thị theo cùng kiểu. Khi timestamp ASR cuối vượt thời lượng metadata không quá 5 giây, tự giới hạn về mép video thay vì chặn duyệt (item #8 thực tế lệch 375 so với 373 giây).

- [x] **GW.25** Thêm engine **VieNeu-TTS** (Apache-2.0 cả weights, base và codec — kiểm trên model card 15/09/2026; model card cho phép dùng thương mại): **20 giọng dựng sẵn** đủ Bắc/Trung/Nam, nam và nữ, chạy được trên CPU nên không tranh VRAM với Whisper/VoxCPM2. Cần `pip install vieneu` trong image worker; chưa cài thì giọng vẫn hiện kèm lý do. **ElevenLabs bị loại ở bản free**: không có quyền thương mại và bắt ghi công — đúng loại vấn đề đã loại OmniVoice và model gióng của WhisperX
- [x] **GW.24** **Chọn giọng theo từng video** ở cả tạo clip (GĐ1) và Studio (GĐ2): danh mục `infrastructure/tts/catalog.py` gom ba engine, id dạng `engine:tên` lưu vào `items.voice_id` (migration 0004). VoxCPM2 nhận giọng clone bằng cách thả file mẫu vào `media/voices/` (kèm `.txt` lời đọc thì sát hơn); 9 giọng FPT.AI và 2 giọng edge hiện sẵn kèm lý do khi chưa dùng được. Giọng hỏng thì rơi về mặc định chứ không dừng video
- [x] **GW.23** Tách hai lối nạp video: nút **“Nạp video”** ở đầu trang nguồn khai báo **một nguồn mới** (URL gốc + giấy phép + phạm vi quyền) rồi nạp file trong một màn hình, còn **“Upload file”** trên từng dòng chỉ nạp thêm video vào nguồn đã duyệt (`POST /sources/{id}/uploads`). License gate không nới: vẫn `declare_source` → `approve_source` → `register_uploaded_video`, và lỗi giữa chừng thì xoá file vừa ghi. Chi tiết nguồn xếp dọc: video và clip → hồ sơ pháp lý → lịch sử hoạt động rẽ nhánh giống trang review
- [x] **GW.22** Quan hệ **một video gốc → nhiều clip con** nói rõ trên UI (tiêu đề, dòng mô tả, link hai chiều). Mọi trạng thái hiển thị bằng **nhãn tiếng Việt**, mã enum chỉ còn làm class CSS — gồm cả dashboard và snapshot polling. Bỏ tab “Duyệt thành phẩm”: tab “Clip đã tạo” liệt kê từng clip kèm trạng thái, % và **nút việc kế tiếp**; bấm vào dòng mở popup có video, kịch bản tiếng Việt và nút thực hiện đúng bước đó (duyệt/viết lại/từ chối, hoặc **xuất bản** qua use case `queue_publish` — kill-switch `PUBLISH_ENABLED` vẫn chặn). Lịch sử hoạt động rẽ nhánh nguồn → video gốc → từng clip. Bỏ % ở video gốc vì con số đó không mô tả tiến độ thật của gì cả
- [x] **GW.21** Sơ đồ workflow 15 bước là **tham chiếu chung**, không tô theo trạng thái item đang mở (video gốc dừng ở bước 6 rồi clip con đi tiếp — tô theo item nào cũng ra bức tranh sai). Trạng thái thật chỉ nằm ở badge + thanh tiến trình. Trang nguồn chỉ liệt kê **video gốc**, clip con gộp thành thống kê theo trạng thái ngay trên dòng đó và cập nhật realtime; `?open_source=N` mở sẵn đúng nguồn
- [x] **GW.20** Trang review chia tab (Transcript · Tạo clip · Clip đã tạo · Duyệt thành phẩm · Lịch sử · Nguồn & quyền) với dải **workflow 15 bước** ở đầu trang: mỗi bước hiện % tích luỹ của chính nó và đánh dấu xong/đang làm/chưa tới, cập nhật realtime cùng thanh tiến trình. Tab mở sẵn theo việc đang cần làm; tab đang xem nằm trong hash nên F5 không nhảy về đầu
- [x] **GW.19** Lỗi nghiệp vụ của các form trên trang review quay về đúng `/review/{id}` dưới dạng toast đỏ. Không còn trần 10–180 giây: chỉ cảnh báo ngoài khuyến cáo short-form 45–75 giây; người dùng được chọn bất kỳ độ dài dương nào trong phạm vi video gốc
- [x] **GW.18** Gom mọi thao tác của một video về `/review/{id}`: thanh tiến trình + trạng thái realtime, form chọn đoạn tạo clip, transcript, duyệt thành phẩm và **lịch sử hoạt động** (audit của item, item cha và nguồn). `/sources` rút còn danh sách nguồn/item với tiến trình và nút “Mở trang review”; duyệt transcript xong thì về thẳng trang review để chọn đoạn

- [x] **GW.43** Chuẩn hóa quản lý video Studio: `/studio` là danh sách quản lý, mỗi video có trang biên tập/theo dõi riêng `/studio/{id}`; lúc tạo nhận video hoặc tập ảnh tùy chọn và vẫn cho để trống. Danh tính tạo/biên tập/duyệt/xuất bản ở toàn bộ web lấy từ session đăng nhập, không tin trường `actor` từ form. Tách `items.output_aspect_ratio` khỏi tỷ lệ media nguồn và cho chọn giữ nguyên, 9:16 hoặc 16:9 ở cả clip GĐ1 và Studio; renderer/composer xuất đúng khung đã chọn.
- [x] **GW.44** Form “Video mới” tại `/studio` không còn bị polling đóng: Studio vẫn cập nhật tiến trình realtime nhưng không reload toàn trang khi item đổi sang gate cần thao tác; reload chỉ áp dụng cho Nguồn/Review là nơi cần nạp form mới từ server.
- [x] **GW.45** Bộ chọn giọng trong form “Video mới” của Studio dùng cùng cơ chế nghe thử với màn tạo clip: chỉ bật nút khi catalog có file preview, phát qua endpoint `/voices/{engine}/{name}/preview`, và đổi giọng thì dừng/xóa bản nghe thử cũ.
- [x] **GW.46** Xác minh item Studio #14 lưu đúng `output_aspect_ratio=16:9` nhưng worker dev chạy lâu còn giữ handler cũ nên compose rơi về 9:16. Đã restart worker, dựng lại riêng #14 thành 1920×1080 và thêm test ffmpeg thật khóa hành vi composer theo tỷ lệ đầu ra.
- [x] **GW.47** Làm rõ vòng đời Studio sau khi dựng: trang chi tiết phân biệt “thành phẩm đã dựng/chờ duyệt” với “đã xuất bản”, cho nghe audio TTS và chỉnh timing từng dòng phụ đề, rồi “Lưu timing & dựng lại thành phẩm”. Dựng lại đưa item từ `human_review` về `aligned` và enqueue `compose`; item đã approved/published/rejected khóa sửa cảnh, video published không được ghi đè mà phải tạo phiên bản mới.
- [x] **GW.48** **Series trong Studio** (D60): một khuôn sản xuất cho loạt video TikTok cùng chuyên đề — tên, pillar (gõ tự do), mẫu hook có chỗ trống `[..]`, thuật ngữ giữ nguyên tiếng Anh, độ dài 25–45 giây, khung 9:16, giọng, preset phụ đề, lịch đăng. Entity `domain/authoring/series.py` từ chối cấu hình sai; bảng `series` + `items.series_id` (migration 0007). Nhập danh sách đề tài (≤ 10/lần) → mỗi đề tài một bản nháp ở `scripted`, **chưa lồng tiếng** tới khi người bấm “Đưa vào sản xuất”. Đề bài gửi model ép cấu trúc mốc giây (hook 3s · đặt khung · thân · chốt · CTA 4s) kèm trần âm tiết từng phần, hook xoay vòng tất định và ghi vào audit. **Giới hạn đã biết:** output model vẫn là lời bình liền mạch nên chưa kiểm được kịch bản có đúng mốc; preset phụ đề mới lưu/hiển thị, bộ dựng chưa đọc; lịch đăng chỉ để theo dõi, không tự đăng.

**Không làm:** CMS, trang phân tích engagement.

### G3 — Publish YouTube (tuần 5–7)

- [!] **G3.1** GCP project + OAuth consent + credential — **việc của bạn**, agent không tạo tài khoản Google được. Xong thì đặt `YOUTUBE_CLIENT_SECRET_FILE` + `YOUTUBE_TOKEN_FILE` rồi chạy `python scripts/youtube_authorize.py`
- [x] **G3.2** `src/infrastructure/publish/` — registry bỏ qua nền tảng chưa cấu hình
- [x] **G3.3** Adapter YouTube xong về code (resumable upload, mặc định `private`, mô tả có ghi nguồn + nhãn AI, phân loại lỗi retry/không). Chạy thật **chờ G3.1**
- [!] **G3.4** Video công khai đầu tiên — chờ G3.1

### G4 — Facebook (tuần 7–9)

- [!] **G4.1** Page + Business Manager + app — **việc của bạn**. Xong thì đặt `FB_PAGE_ID` + `FB_PAGE_ACCESS_TOKEN`
- [!] **G4.2** Thử ngoại lệ App Review cho app nội bộ; nếu không thì nộp review
- [x] **G4.3** Adapter Facebook Reels xong về code (3 pha start/upload/finish, mặc định không publish ngay). Chạy thật **chờ G4.1**

### G5 — Đánh giá GĐ1 (tuần 9–11)

- [ ] **G5.1** Số liệu engagement theo nền tảng và dạng nội dung
- [ ] **G5.2** Nguồn có bền không? Nền tảng nguồn nào tốt nhất?
- [ ] **G5.3** Công duyệt thực tế so với ước tính 13–22 giờ/tháng
- [ ] **G5.4** Quyết định: mở rộng GĐ1 hay sang GĐ2

### G6 — Giai đoạn 2 · Studio (xong về code)

Không crawl bài của ai: người dùng nhập đề bài, hệ thống viết kịch bản. Xem D.1
của đặc tả — vấn đề pháp lý biến mất thay vì phải quản lý.

- [x] **G6.1** Trang `/studio`: nhập đề bài + thời lượng + tên người tạo; nguồn nội bộ `own` tạo một lần rồi dùng lại
- [x] **G6.2** `PromptScriptWriter` — LLM viết kịch bản tiếng Việt từ đề bài, cùng ngân sách âm tiết và glossary của GĐ1; prompt cấm bịa số liệu/tên khách hàng
- [x] **G6.3** `Item.from_prompt` vào thẳng `scripted` rồi dùng lại nguyên chuỗi lồng tiếng → gióng phụ đề → duyệt → publish
- [x] **G6.4** Kịch bản hình bốn lớp (`domain/authoring/visuals.py`): ảnh/video người dùng đưa vào → kho có license → biểu đồ từ số liệu nhập tay → AI **chỉ** cho bối cảnh; không có gì thì thẻ thương hiệu, không bịa hình
- [x] **G6.5** Biểu đồ cột dựng bằng ffmpeg từ số liệu người dùng gõ (`Nhãn = số`), mỗi cột cao đúng theo con số
- [x] **G6.6** **Bỏ Remotion** — dựng bằng ffmpeg (`infrastructure/media/compose.py`), xem D.2: tránh cả Company License lẫn việc kéo Node/npm vào stack
- [x] **G6.7** Dùng lại tầng publish, giọng, glossary, gate duyệt của GĐ1 — không nhân bản một dòng nào
- [ ] **G6.8** Chạy thật một video Studio đầu-cuối trên GPU (cần `TTS_SYLLABLES_PER_SEC` và worker chạy)

### G7 — Tuỳ chọn (tuần 15+)

- [x] **G7.1** Adapter TikTok Content Posting API (`infrastructure/publish/tiktok.py`): init → upload theo chunk → fetch status, hỏi `creator_info` để lấy mức hiển thị hợp lệ thay vì đoán. Mặc định `SELF_ONLY` vì client chưa audit chỉ đăng được riêng tư; hạn mức thì retry, còn lỗi audit/token thì không. **Chờ `TIKTOK_ACCESS_TOKEN`** để chạy thật
- [ ] **G7.2** Bản tiếng Anh *(nội dung song ngữ đã có, chỉ tốn TTS)*
- [ ] **G7.3** LinkedIn

---

## 4. Hai việc làm ngay, không cần chờ nhau

1. **G0.4 + G0.5 — Chạy pipeline + VoxCPM2 trên một video thật.** Trả lời cùng lúc: chất lượng dịch thuật ngữ, chất lượng giọng Việt, pipeline có chạy trên máy bạn không.
2. **G0.3 — Test yt-dlp trên URL thật từng nền tảng đã có giấy phép.** Douyin dễ vỡ nhất; biết ở tuần 1 chứ không phải tuần 6.

---

## 5. Còn cần bạn quyết

Agent: làm hết phần **không** phụ thuộc các câu này. Đừng dừng chờ.

| # | Câu hỏi | Chặn việc gì |
|---|---|---|
| Q1 | **5–10 URL nguồn thật thuộc phạm vi giấy phép sẵn có**, kèm chủ nguồn và bằng chứng/phạm vi quyền | G0.2, G0.3, G1.2 |
| Q2 | **Có GPU ≥8 GB VRAM không?** | G0.10, mô hình chi phí |
| Q3 | **Tỷ lệ nguồn tiếng Trung vs Anh?** Có ai đọc được tiếng Trung? | Volume mục tiêu, G1.4 |
| Q4 | **Ai duyệt, bao nhiêu giờ/tuần?** | Volume mục tiêu |
| Q5 | **Giọng:** clone kỹ sư NMI hay giọng tổng hợp? Nam/nữ, vùng miền? | G0.5, G0.6 |
| Q6 | **Có giữ TikTok trong phạm vi?** | G7.1 |
| Q7 | **Có làm bản tiếng Anh?** | G7.2 |

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
| D27 | Session login + tài khoản DB thay Basic Auth; production bắt buộc secret ký cookie và bootstrap admin | Cần logout, nhiều người dùng, phân quyền và audit danh tính; Basic Auth không đáp ứng được | 14/09 |
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
| D55 | **Bỏ hẳn khái niệm `vendor/`** — code mượn từ dự án mở được viết lại thành module của chính dự án | Quy tắc cũ ("sao nguyên byte, không được sửa, chỉ bọc adapter") nghe thì an toàn nhưng vừa trả giá thật: graph trộn audio của Easel thiếu `aformat` trước `sidechaincompress` nên đổ ngay khi bật ducking, mà luật cấm sửa lại đẩy chỗ chữa ra xa chỗ hỏng. Thêm nữa, adapter phải gọi script qua `subprocess`, nên lỗi về dưới dạng **tiếng Trung trên stderr** — không phân loại được retry được hay không, đúng thứ hàng đợi việc cần. Nay: đọc upstream, hiểu thuật toán, **viết lại** trong `src/` và sửa tự do. Nghĩa vụ Apache-2.0 chuyển sang `docs/THIRD_PARTY_NOTICES.md` — ghi lấy gì, đưa vào đâu, **sửa những gì**, kèm toàn văn license. Bỏ luôn `subtitle_ops.py` (569 dòng chưa hề dùng) |
| D56 | **Giả định NMI đã có giấy phép nguồn; không thực hiện hoạt động gửi thư xin phép** | Giấy phép sẵn có không tự mở quyền cho mọi URL: vẫn phải đối chiếu đúng chủ nguồn, lưu bằng chứng và khai rõ quyền sửa audio/phụ đề/tái xuất bản/thương mại trong `sources`. License gate và ownership gate giữ nguyên |
| D57 | **Registry LLM hỗ trợ `gemini|openai|anthropic`**; Gemini free tier vẫn là mặc định | Cả ba dùng cùng hợp đồng JSON Schema. OpenAI API cần `OPENAI_API_KEY`; ChatGPT Plus không bao gồm API và được tính phí riêng theo tài liệu chính thức |
| D58 | Mọi thao tác biên tập tập trung tại `/sources`; JavaScript nội tuyến tối thiểu chỉ dùng cho popup, mở chi tiết và thêm dòng chọn clip | Thay D25 theo yêu cầu UX mới; vẫn server-rendered, không SPA và không phụ thuộc CDN. Một video có thể sinh nhiều item con; cờ ghi nguồn tùy chọn không được phép ghi đè nghĩa vụ attribution của license |
| D59 | “Nạp video” trên web là upload file từ máy, không phải dán URL | File gốc được giữ dưới `media/source/uploads`, vẫn phải chọn nguồn approved và qua license gate; sau ffprobe, item bắt đầu ở `downloaded` và xếp job `separate`. API nhận URL cũ được giữ cho tích hợp tự động, nhưng không còn xuất hiện trong UI |
| D60 | **Series là bảng DB riêng**, video con trỏ về bằng `items.series_id`; bản nháp dừng ở `scripted` | Series sở hữu video con và sẽ mang thêm lịch/thống kê, giống `sources`↔`items` — lưu file JSON thì không có transaction, không cùng bản sao lưu, và phải mượn `script_sources` làm khoá liên kết. Ràng buộc 25–45s/9:16/pillar/hook nằm ở entity, không có CHECK song song (D20). Bản nháp chưa lồng tiếng vì kênh kỹ thuật cần kỹ sư đọc kịch bản trước khi tốn công dựng. Pillar gõ tự do vì sẽ có lộ trình cho sản phẩm khác | 16/09 |

---

## 7. Rủi ro đang theo dõi

| Rủi ro | Mức | Trạng thái |
|---|---|---|
| Nhập sai phạm vi giấy phép sẵn có cho nguồn video | **Cao** | License gate vẫn bắt buộc; đối chiếu từng chủ nguồn và lưu bằng chứng ở G0.2 |
| Giọng Việt VoxCPM2 chưa đạt | Trung bình | Chờ G0.5. Dự phòng: FPT.AI qua cùng interface |
| Transcript nguồn tiếng Trung sai nhiều (~12,8% CER) | Trung bình | Chờ Q3 — cần người đọc được tiếng Trung |
| Công người duyệt không kham được | Trung bình | Chờ Q4 |
| Không có GPU | Trung bình | Chờ Q2 |
| Remotion company license (GĐ2) | Thấp | Chưa cần tới G6.6 |
| **License model AI** — dễ lọt model NonCommercial vào đường sản xuất | **Cao** | Đã bắt 2 ca: OmniVoice (CC-BY-NC) và model gióng của WhisperX (cc-by-nc-4.0). Quy tắc: **kiểm license weights trên HF model card trước khi thêm bất kỳ model nào**, không tin license của code |

---

## 8. Nhật ký

| Ngày | Việc |
|---|---|
| 16/09/2026 | GW.48: Series trong Studio — entity + migration 0007 + use case `author_series` (tạo, sinh bản nháp hàng loạt, đưa vào sản xuất) + trang `/studio/series/new` và `/studio/series/{id}` không JavaScript. Sửa kèm: URL item Studio thêm hậu tố ngẫu nhiên vì sinh hàng loạt trong cùng giây đụng ràng buộc duy nhất. 45 unit `test_series` (0,90 s) + 17 unit `test_authoring` + 4 integration Studio (chạy qua migration 0007) xanh, ruff sạch; render thử hai trang Series không có `<script>` mới. **Chưa chạy `make migrate` trên DB dev** |
| 15/09/2026 | Dọn tài liệu: chuyển `README.md`, `THIRD_PARTY_NOTICES.md` và `lo-trinh-tiktok-smart-factory.md` (lộ trình nội dung kênh TikTok) vào `docs/`. Ở gốc chỉ còn file của agent: `AGENTS.md`, `CLAUDE.md`, `PLAN.md`. Đã sửa link tương đối trong README và các chỗ trỏ tới notices (AGENTS.md, PLAN.md, docstring `reframe.py`/`ffmpeg.py`) |
| 15/09/2026 | GW.47: #14 thực tế ở `human_review`, chưa có publication. Bổ sung audio giọng, editor timing phụ đề và nút lưu+dựng lại; khóa ghi đè phiên bản đã xuất bản. 17 unit authoring + 37 web integration xanh, Ruff sạch. |
| 15/09/2026 | GW.46: sửa thực tế video Studio #14 “NMIT giới thiệu”: DB đã lưu 16:9 nhưng worker cũ không truyền lựa chọn sang composer. Restart worker và dựng lại output đạt 1920×1080; log compose nay ghi aspect. 14 media integration xanh, Ruff sạch. |
| 15/09/2026 | GW.45: thêm nút “Nghe thử” và audio player vào bộ chọn giọng khi tạo video Studio, dùng lại catalog/endpoint/component của tạo clip. 37 web integration xanh, Ruff sạch. |
| 15/09/2026 | GW.44: sửa polling `/studio` reload trang khi một item đổi sang gate cần thao tác, làm dialog “Video mới” vừa mở đã đóng. Studio nay chỉ cập nhật trạng thái tại chỗ. 37 web integration xanh, Ruff sạch. |
| 15/09/2026 | GW.43: làm lại Studio thành danh sách + trang chi tiết chuyên nghiệp, nhận video/tập ảnh ngay khi tạo hoặc bổ sung sau; thống nhất actor theo tài khoản session; thêm migration 0006 và ba lựa chọn khung đầu ra giữ nguyên/9:16/16:9 cho cả GĐ1/GĐ2. 48 unit, 36 web integration và 13 media integration xanh; Ruff sạch. Trình duyệt tích hợp không có instance khả dụng nên QA hình ảnh trực tiếp chưa chạy. |
| 13/09/2026 | Khảo sát công nghệ, quét nmi.vn, đánh giá 20 dự án OSS, chốt stack, dựng khung Docker + schema + AGENTS.md, dọn 13 file `.whl` và 5 tài liệu trung gian |
| 13/09/2026 | Code lõi: domain 4 bounded context → application use case → infrastructure Postgres → FastAPI + worker. 4 commit. Bịt lỗ xác minh chủ sở hữu trong license gate. 112 unit + 12 integration test xanh. Sửa 4 bug do test bắt được (xem nhật ký commit) |
| 14/09/2026 | Alembic thành nguồn duy nhất của schema · vendor Easel · tầng media (ffmpeg + ASS + render) · TTS + ngân sách âm tiết · ASR/Demucs/alignment · LLM chọn đoạn + viết kịch bản · publish YouTube/Facebook · mặt tiền web nội bộ · nối dây worker. 191 unit + 43 integration test |
| 14/09/2026 | Viết nốt 4 script vận hành (`fetch_models`, `fetch_fonts`, `measure_speech_rate`, `youtube_authorize`) · G0.8 + G0.11 xong bằng kiểm chứng thật · engine `edge` cho phép chạy toàn chuỗi **không cần GPU** · đo được tốc độ đọc 3,54 âm tiết/giây |
| 14/09/2026 | G1.3: tái lập `research/nmi-scan/` bằng script (tham chiếu treo trong tài liệu — thư mục chưa từng tồn tại), rút 77 thuật ngữ từ corpus thật và nạp vào bảng `glossary` |
| 14/09/2026 | `make smoke` chạy toàn chuỗi không cần GPU → video 9:16 thật có phụ đề tiếng Việt, phát được trong trang duyệt. Ba bug thật lộ ra khi chạy (xem nhật ký commit) |
| 14/09/2026 | Chốt D56: giả định NMI đã có giấy phép nguồn; phần việc pháp lý chuyển thành đối chiếu và nhập bằng chứng/phạm vi quyền cho từng chủ nguồn. License gate không đổi |
| 14/09/2026 | G0.3/G0.4 chạy thật trên YouTube Blender Official: probe ownership + CC Attribution, tải video 110 giây, Demucs và Whisper GPU đến gate soát transcript (item #5). G0.5 sinh mẫu VoxCPM2 thật; còn thiếu URL approved Douyin/Bilibili/Facebook, credential FPT/Viettel, API key LLM và đánh giá của người nghe |
| 14/09/2026 | Sửa state machine job cho phép `running → cancelled`: worker cần chuyển trạng thái này khi đã claim một job cũ nhưng item không còn ở stage phù hợp. `tests/unit/test_job_queue.py`: 8 test xanh |
| 14/09/2026 | Thêm source #6 cho video CQE Academy `H6St9mCKWuA` theo xác nhận giấy phép của người dùng; scope gồm dịch, sửa audio, phụ đề, tái xuất bản và thương mại, có attribution. Item #7 tải 35,6 MB, Demucs + Whisper GPU xanh và dừng đúng ở gate soát transcript; phát hiện lỗi ASR ở Cp/Cpk/Pp/Ppk và đoạn lặp phút 8–11 |
| 14/09/2026 | Sửa UX trang soát transcript: mỗi item hiện source ID + tên nguồn; nút nói rõ đây là xác nhận đạt/chuyển bước; redirect sau duyệt có banner thành công và link dashboard. Item #5 được xác định là video Blender showcase từ lần test trước. `tests/integration/test_web_ui.py`: 19 test xanh |
| 14/09/2026 | Sửa lỗi item đã duyệt transcript vẫn quay lại hàng chờ khi `pick_segment` lỗi: thêm stage `transcript_approved` + migration 0002; job không retry được nay đẩy item sang `failed` và giữ lỗi để dashboard hiển thị. Migration sửa dữ liệu #5/#7 thành `failed: thiếu ANTHROPIC_API_KEY`. Test: 34 item lifecycle, 11 worker chain, 19 web UI đều xanh |
| 14/09/2026 | Thêm Gemini REST adapter + registry `gemini|anthropic`; Gemini free tier thành mặc định, dùng JSON Schema chung với Claude. Lần gọi thật cho biết 2.5 Flash không còn cấp cho tài khoản mới nên đổi sang `gemini-3.6-flash` theo chính phản hồi API. Cập nhật compose và env mẫu. 17 test adapter LLM + 11 test worker chain xanh, Ruff sạch |
| 14/09/2026 | Chạy tiếp item #7: Gemini 3.6/3.5 Flash bị 503; Gemma 4 chọn được đoạn nhưng JSON viết kịch bản không ổn định; `gemini-3.5-flash-lite` chạy ổn và thành mặc định. Sửa bug bước viết gửi cả transcript 16 phút thay vì chỉ đoạn 70 giây. VoxCPM2 + align + render xong, item vào `human_review`. Kiểm tra Zen live: model free trả `MissingSessionID`, chỉ được dùng trong ứng dụng OpenCode nên không tích hợp vào pipeline |
| 14/09/2026 | Thiết kế lại `/` và `/sources`: KPI/biểu đồ, lọc + tìm kiếm + phân trang, popup thêm nguồn/video, tiến trình + transcript + duyệt + audit tại một trang. Thêm migration 0003 và luồng chọn nhiều khoảng để một video sinh nhiều clip độc lập; attribution là tùy chọn trừ license bắt buộc. 21 web integration + 45 unit hồi quy xanh, Ruff sạch |
| 14/09/2026 | Đổi “Nạp video” từ nhập URL thành upload file thật; chọn nguồn approved, ffprobe kiểm tra media, giữ file gốc và xếp thẳng job tách audio. Đưa nút upload ra từng dòng nguồn và thêm khối “Review chọn đoạn” luôn hiện, gồm đoạn đã chọn/trạng thái chờ và transcript có timestamp. 22 web integration + 2 unit upload xanh, Ruff sạch |
| 14/09/2026 | Làm rõ form duyệt nguồn bằng nhãn tiếng Việt, mô tả trường bắt buộc và nút “Gợi ý điền”. Preset chỉ tự cấp các quyền suy ra được cho CC BY/nội dung sở hữu; bằng chứng và quyền trong giấy phép riêng vẫn phải do người duyệt xác nhận. 22 web integration xanh |
| 14/09/2026 | Đơn giản hóa form theo yêu cầu: chuyển bằng chứng/chuỗi ghi nguồn vào mục bổ sung không bắt buộc. Khi trống, web ghi xác nhận giấy phép nội bộ; CC BY tự sinh attribution để renderer vẫn tuân thủ điều kiện giấy phép. 22 web integration xanh |
| 14/09/2026 | Đổi luồng URL sang chủ động: thêm nguồn chỉ lưu hồ sơ; sau khi duyệt, mỗi nguồn video có nút Start tải riêng và chỉ khi bấm mới enqueue download. Empty-state rút còn “Chưa có video”. 23 web integration xanh, Ruff sạch |
| 14/09/2026 | Thêm endpoint snapshot `/item-status` và polling 3 giây trên trang nguồn. Badge stage, progress và lỗi đổi trực tiếp; tới transcript review/chọn đoạn/human review thì tự reload để hiện form mới, khôi phục nguồn đang mở. 23 web integration xanh, Ruff sạch |
| 15/09/2026 | GW.30: bỏ tiền tố `/web` khỏi toàn bộ giao diện: dashboard `/`, nguồn `/sources`, review `/review/{id}`, Studio `/studio`. REST API chuyển sang `/api/sources` và `/api/items` để tránh xung đột; URL `/web/*` cũ redirect 308 sang URL mới. 33 web integration xanh, Ruff sạch; kiểm tra thật HTML/API/redirect đều đúng. |
| 15/09/2026 | GW.31: hoàn thiện nghe thử cho VoxCPM2 mặc định và 2 giọng Edge dev tại màn chọn clip. Script cache sinh đủ WAV/MP3; kiểm tra thật ba endpoint đều HTTP 200, thời lượng lần lượt 4,32 / 4,78 / 4,51 giây. 15 unit catalog xanh, Ruff sạch. |
| 15/09/2026 | GW.32: sửa lỗi JavaScript trên `/sources`: regex nhận diện `/review/{id}` bị escape thừa làm trình duyệt báo `Invalid regular expression flags`. HTML thực tế đã render `/^\/review\/\d+$/`; Node kiểm tra cú pháp và khớp `/review/8` thành công, web integration không lỗi. |
| 15/09/2026 | GW.33: bỏ trần 10–180 giây cho clip/Studio, giữ 45–75 giây như khuyến cáo; thêm OpenAI structured-output vào registry Gemini/OpenAI/Claude; thay Basic Auth bằng session login, 4 vai trò, quản lý tài khoản, audit login/logout và giao diện Q One màu `#10c572`/ink `#1a2330`. Migration `0005_user_accounts`; 69 unit + 35 web integration xanh, Ruff sạch. |
| 15/09/2026 | GW.34: chuẩn hóa UI theo template Q One Assistant: dùng nguyên hệ token light/dark, lưu lựa chọn `qone.portal.theme`, theo theme hệ thống lần đầu, nút đổi sáng/tối trên topbar, logo tương phản theo theme và menu người dùng bằng avatar + dropdown. Đã xác minh 36 integration test web xanh và bản chạy thật `/`/logo dark trả HTTP 200. |
| 15/09/2026 | GW.35: sửa HTTP 500 khi tạo thêm clip cho video đã có clip: chỉ số/URL clip mới nối tiếp giá trị lớn nhất hiện có thay vì luôn quay lại 1. Đồng thời đổi logo bằng `src` theo theme thay cho CSS `content`, bảo đảm chữ Q ONE tương phản đúng ở cả light/dark. 36 web integration xanh, Ruff sạch. |
| 15/09/2026 | GW.36: chuẩn hóa toàn bộ lớp trình bày web theo component/tokens Q One Assistant bằng `qone-ui.css`: app bar, typography, spacing, card/KPI, form, button, tab, badge, bảng, workflow, transcript editor, modal/toast/history và responsive light/dark. Khôi phục thao tác tại `/sources`: item đủ điều kiện có nút `Chọn đoạn tạo clip` đi thẳng tới `/review/{id}#clip` và không bị sự kiện dòng nguồn giữ lại. 36 web integration xanh; CSS hợp lệ, asset và link item #8 đã kiểm tra trên server thật. |
| 15/09/2026 | GW.37: snapshot realtime `/item-status` nay ghép stage với job mới nhất, phân biệt `chờ xử lý`/`đang xử lý`/`xử lý lỗi`, hiển thị bước đang chạy và ghi rõ `% đã hoàn tất` thay vì suy diễn job chỉ từ stage. Khôi phục job #33 của clip #7-2 sau khi worker cũ còn giữ validation 180 giây trong bộ nhớ; viết kịch bản đã xong và TTS đang chạy. 36 web integration xanh, Ruff sạch. |
| 15/09/2026 | GW.38: sửa fill thanh progress không hiện do `<span>` inline: fill nay là block cao 100%, width clamp 0–100%, có màu vàng/chờ, xanh dương/đang chạy, xanh lá/hoàn tất, đỏ/lỗi và thuộc tính ARIA progressbar. 36 web integration xanh; JS/CSS syntax hợp lệ. |
| 15/09/2026 | GW.39: workflow 15 bước tô theo item đang mở (xanh lá đã xong, xanh dương hiện tại, trung tính chờ, đỏ lỗi), căn số/tên/% cùng hàng và đổi layout responsive 5/3/2 cột để không còn kéo ngang. 36 web integration xanh, Ruff sạch, CSS syntax hợp lệ. |
| 15/09/2026 | GW.40: mở rộng VoxCPM2 từ 1 lên 21 lựa chọn dùng ngay: giọng mặc định + clone từ đủ 20 mẫu VieNeu đã cache, kèm transcript chuẩn và metadata nam/nữ, Bắc/Trung/Nam; mọi lựa chọn có nghe thử. Sinh lại mẫu Minh Đức bị integration test cũ xóa nhầm và sửa test để khôi phục dữ liệu runtime. 16 unit catalog + 36 web integration xanh, Ruff sạch; trang thật xác nhận 21/21 VoxCPM2 có preview. |
| 15/09/2026 | GW.41: workflow trên desktop hiển thị đủ 15 bước trong một hàng, chia đều `minmax(0,1fr)`, nội dung ô xếp dọc và không có overflow ngang; tablet/mobile vẫn chuyển 3/2 cột để dễ đọc. 36 web integration xanh, CSS syntax hợp lệ. |
| 15/09/2026 | GW.42: chẩn đoán clip #7-2: đoạn chọn thực tế 372 giây nhưng Gemini rút còn kịch bản 720 ký tự, VieNeu đọc 38,53 giây và renderer lấy audio làm mốc nên cắt output. Renderer nay giữ đúng thời lượng đoạn, cắt background đúng mốc và đệm im lặng nếu voice ngắn; prompt video dài có ngưỡng tối thiểu + một lần mở rộng bản nháp; trả về viết lại nay enqueue job thật. 21 unit LLM, 14 publish-flow và 13 media integration xanh, Ruff sạch. Chạy lại thật bị chặn đúng vì Gemini Flash Lite chỉ sinh 483–735/1.316 âm tiết; chưa render đè output cũ. |
| 15/09/2026 | GW.29: thêm nút nghe thử cạnh danh sách giọng ở bước chọn clip; endpoint chỉ phục vụ đúng file catalog, không mở thư mục media. Cache đủ 20 mẫu VieNeu bằng worker; kiểm tra thật review #8 có 20 URL preview, mẫu Minh Đức HTTP 200/399.404 byte. Thêm `make voice-previews` để tái tạo cache. 14 unit catalog + integration chọn giọng xanh, Ruff sạch. |
| 15/09/2026 | GW.28: tách bố cục chi tiết nguồn đúng hai vùng: video/clip và hồ sơ pháp lý nằm nối tiếp ở cột chính; chỉ lịch sử phân nhánh nằm ở cột phụ sticky. |
| 15/09/2026 | GW.27: sửa catalog VieNeu bị kiểm tra nhầm package trong API thay vì worker nên 20 giọng luôn disabled. Rebuild/recreate worker, import `vieneu` thành công; smoke thật giọng Minh Đức sinh WAV 2,8 giây/268.844 byte; 14 unit catalog + web integration chọn giọng xanh. |
| 15/09/2026 | GW.26: lịch sử trên chi tiết nguồn trở lại cột bên phải; chia cây nguồn → video gốc → từng clip con, mỗi nhánh là khối thu gọn và sự kiện mới nhất đứng trước. |
| 15/09/2026 | GW.25: thêm 20 giọng VieNeu-TTS (Apache-2.0, thương mại được, chạy CPU) vào danh mục; ghi nghĩa vụ license vào THIRD_PARTY_NOTICES. Kiểm điều khoản: ElevenLabs free KHÔNG có quyền thương mại, Azure F0 cũng không cho giọng neural dựng sẵn; Google Cloud TTS free 1M ký tự/tháng (WaveNet) thì được — để dành khi mở GCP cho YouTube G3.1. 14 unit catalog xanh |
| 15/09/2026 | GW.24: chọn giọng đọc theo từng video ở cả clip và Studio; danh mục ba engine (VoxCPM2 clone từ `media/voices/`, 9 giọng FPT.AI theo tài liệu — **chưa xác minh bằng tài khoản thật**, 2 giọng edge chỉ dev). Thêm `items.voice_id` + migration 0004; worker dựng engine theo giọng của item. 10 unit catalog + 35 web integration xanh |
| 15/09/2026 | G6 Studio: trang `/studio` nhập đề bài → LLM viết kịch bản → item vào thẳng `scripted` rồi dùng lại chuỗi GĐ1; kịch bản hình bốn lớp + biểu đồ từ số liệu nhập tay; bộ dựng `compose.py` bằng ffmpeg (bỏ Remotion); adapter sinh ảnh tuỳ chọn. G7.1: adapter TikTok. G3.3/G4.3 xác nhận xong về code, chỉ chờ credential. 15 unit authoring + 34 web integration xanh, Ruff sạch |
| 15/09/2026 | GW.23: “Nạp video” tạo nguồn mới kèm khai giấy phép trong cùng form; nạp vào nguồn có sẵn chuyển sang endpoint riêng của nút Upload file. Trang chi tiết nguồn xếp dọc và lịch sử rẽ nhánh theo clip. 30 web integration xanh, Ruff sạch |
| 15/09/2026 | GW.22: nhãn trạng thái tiếng Việt toàn bộ mặt tiền; tab “Clip đã tạo” có nút việc kế tiếp + popup video/kịch bản/hành động; thêm use case `queue_publish` cho nút Xuất bản; lịch sử rẽ nhánh theo clip; bỏ tab duyệt thành phẩm và bỏ % ở video gốc. 28 web integration + 16 publish flow xanh, Ruff sạch |
| 15/09/2026 | GW.21: workflow thành sơ đồ tham chiếu trung tính; trang nguồn gộp clip con thành thống kê trên dòng video gốc (snapshot polling nay trả `parent_item_id` để gộp lại phía trình duyệt) và `?open_source=` mở sẵn nguồn. 27 web integration xanh, Ruff sạch |
| 15/09/2026 | GW.20: chia trang review thành 6 tab và vẽ workflow 15 bước kèm % từng bước ở đầu trang; panel mặc định render sẵn từ server nên không phụ thuộc JS, polling cập nhật cả dải workflow. 27 web integration xanh, Ruff sạch |
| 15/09/2026 | GW.19: mọi lỗi form của trang review trả về chính trang đó bằng toast (trước đây nhảy sang `/items/8/clips` — trang cụt). Form chọn đoạn hiện biên 10–180s lấy thẳng từ domain và độ dài đoạn cập nhật khi gõ; tạo clip xong ở lại review, thêm bảng clip con có tiến trình realtime. 26 web integration xanh, Ruff sạch |
| 14/09/2026 | GW.18: đẩy chọn đoạn, tiến trình realtime và lịch sử hoạt động vào `/review/{id}`; trang nguồn chỉ còn danh sách + nút mở review, bỏ đọc transcript từng item khi render danh sách. Polling 3 giây chạy cả ở trang review và không reload khi đang sửa dở transcript. 25 web integration xanh, Ruff sạch |
| 14/09/2026 | Đổi mã item toàn cục khó đọc sang mã theo nguồn/clip (`#7-1`, `#7-2`, `#7-gốc`). Thanh trạng thái hiện rõ số bước trên 15, phần trăm tổng pipeline và tên tiếng Việt; snapshot realtime trả đủ step/percent/label. 23 web integration xanh, Ruff sạch |
