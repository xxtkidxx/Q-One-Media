# Phương án cuối cùng — Giai đoạn 1 và Giai đoạn 2

**Ngày:** 13/09/2026 · **Tài liệu này tổng hợp toàn bộ khảo sát và là bản chốt để triển khai.**

Tài liệu này là **bản duy nhất** để triển khai. Các tài liệu khảo sát trung gian đã được gộp vào đây và xoá bỏ.

---

## Phần A — Khảo sát VoiceStudio

`debpalash/VoiceStudio` · **25.814★ · 3.197 fork · AGPL-3.0 · cập nhật 11/09/2026 · tạo 09/04/2026** `[first-party — GitHub API]`

### A.1. Nó là gì

Bản thay ElevenLabs chạy hoàn toàn local: voice cloning, voice design, video dubbing, STT, audiobook. Gom **16 engine TTS** và **11 engine STT** sau một giao diện thống nhất, kèm **REST API tương thích OpenAI** (`/v1/audio/speech`, `/v1/audio/transcriptions`), WebSocket streaming, MCP server.

Yêu cầu: RAM 8 GB tối thiểu / 16 GB+ khuyến nghị; GPU tuỳ chọn nhưng VRAM 4 GB tối thiểu / 8 GB+ khuyến nghị. Có bản Windows, macOS ARM, Linux, Docker.

### A.2. Hai rào cản license — và cách đi qua

**Rào cản 1: engine mặc định không dùng thương mại được.** Engine mặc định (OmniVoice của k2-fsa) có **code Apache-2.0 nhưng weights CC-BY-NC** `[first-party — README VoiceStudio, bảng engine]`. FAQ của họ nói thẳng: *"VoiceStudio's application license does not restrict generated audio, but it does not grant rights under a model's separate terms. The default OmniVoice repository labels its pretrained weights CC-BY-NC... Review the selected model terms before commercial use."*

Video marketing của NMI là mục đích thương mại → **không dùng được engine mặc định.**

**Rào cản 2: AGPL-3.0 — nhưng hẹp hơn tôi lo ban đầu.** Nguyên văn phần License: *"You may run it, modify it, and use it internally. ... If you **modify** VoiceStudio and provide that **modified version as a network service**, AGPL requires you to offer the corresponding source."*

Tức nghĩa vụ mở nguồn chỉ kích hoạt khi **vừa sửa vừa cung cấp bản sửa như dịch vụ mạng**. Chạy bản gốc không sửa, nội bộ → không vướng. Họ cũng bán **commercial license** cho nhúng vào sản phẩm đóng (VoiceStudio@palash.dev) — nhưng license đó *không* cấp lại quyền với model của bên thứ ba.

### A.3. Lối đi: đổi engine sang VoxCPM2

Bảng engine của VoiceStudio có nhiều lựa chọn Apache-2.0/MIT. Lọc theo ba tiêu chí (license thương mại được + có tiếng Việt + có voice cloning):

| Engine | Ngôn ngữ | Clone | Instruct | License | Tiếng Việt |
|---|---|:---:|:---:|---|:---:|
| **VoxCPM2** | 30 | ✅ | ✅ | **Apache-2.0** | **✅ Có** |
| MOSS-TTS-v1.5 | 31 | ✅ | ❌ | Apache-2.0 | Chưa xác minh |
| dots.tts | 24 | ✅ | ❌ | Apache-2.0 | Chưa xác minh |
| MOSS-TTS-Nano | 20 | ✅ | ❌ | Apache-2.0 | Chưa xác minh |
| CosyVoice 3 | 9 + 18 phương ngữ TQ | ✅ | ✅ | Apache-2.0 | Khó — 9 ngôn ngữ, tối ưu tiếng Trung |
| GPT-SoVITS | 5 | ✅ | ❌ | MIT | Khó — 5 ngôn ngữ |
| Sherpa-ONNX | 20+ | ❌ | ❌ | Apache-2.0 | Không clone được |
| ~~OmniVoice (mặc định)~~ | 600+ | ✅ | ✅ | **CC-BY-NC weights** | ⛔ Không thương mại |
| ~~IndexTTS 2.5~~ | 5 | ✅ | ❌ | Bilibili license | Không có VI |
| ~~Supertonic 3~~ | 31 | ❌ | ❌ | OpenRAIL-M (có ràng buộc sử dụng) | Không clone |

**VoxCPM2 là câu trả lời.** Đã xác minh trực tiếp trên Hugging Face model card `openbmb/VoxCPM2`: `license: apache-2.0`, và `vi` nằm trong danh sách ngôn ngữ `[first-party — HF model card]`. Repo gốc `OpenBMB/VoxCPM`: **37.028★, Apache-2.0, cập nhật 02/09/2026** `[first-party]`. Có cả voice cloning **và** voice design (sinh giọng từ mô tả bằng chữ).

### A.4. Kết luận về VoiceStudio: dùng VoxCPM2, không nhất thiết dùng VoiceStudio

Đây là điểm quan trọng nhất của phần A. **VoxCPM2 là repo độc lập 37k★** — dùng trực tiếp được, không cần VoiceStudio. Nếu thứ bạn cần chỉ là một engine TTS tiếng Việt có clone chạy on-prem, thì gọi VoxCPM2 trực tiếp **tránh được hoàn toàn AGPL** và bỏ được một lớp cài đặt nặng.

VoiceStudio chỉ đáng thêm vào nếu bạn muốn ba thứ nó cộng thêm:

| VoiceStudio cho thêm | Có đáng với NMI? |
|---|---|
| REST API tương thích OpenAI cho 16 engine sau một endpoint | Đáng, nếu muốn đổi engine không sửa code |
| Voice design UI + quản lý thư viện giọng | Đáng ở giai đoạn chọn giọng (G0), ít đáng khi đã chốt |
| 11 engine STT gồm WhisperX + diarization | **Không cần** — VideoLingo đã có WhisperX |

**Khuyến nghị:** dùng **VoxCPM2 trực tiếp** trong pipeline sản xuất. Cài **VoiceStudio riêng trên một máy để thử nghiệm và thiết kế giọng ở G0** — nó là công cụ tốt để so sánh nhanh nhiều engine và clone thử giọng, và ở mục đích nội bộ không sửa đổi thì AGPL không vướng. Sau khi chốt được giọng thì sản xuất gọi VoxCPM2 trực tiếp.

### A.5. Một điểm hợp thương hiệu, không chỉ hợp kỹ thuật

Q One được bán bằng đúng một lời hứa: *"Triển khai tại chỗ, dữ liệu ở lại trong nhà máy."*

Dùng **giọng AI chạy on-prem, clone từ giọng thật của một kỹ sư NMI, model Apache-2.0** là nhất quán với chính lời hứa đó — và là thứ có thể nói ra được trong nội dung. Ngược lại, gửi kịch bản lên API của một nhà cung cấp nước ngoài để lấy giọng đọc thì hơi trái với thông điệp bạn đang bán. Đây không phải lập luận kỹ thuật, nhưng với B2B kỹ thuật thì sự nhất quán này có giá.

---

## Phần B — Bộ thành phần đã chốt

Tổng hợp toàn bộ khảo sát. **Mọi thành phần đều Apache-2.0, MIT, BSD hoặc Unlicense — không có GPL/AGPL nào trong đường sản xuất.**

| Khâu | Chọn | Star | License | Vì sao |
|---|---|---:|---|---|
| Điều phối | **n8n** self-host | — | Sustainable Use | Control plane; unlimited executions; UI cho người non-tech |
| Hộp thư URL + license registry | **Tự viết** (Postgres) | — | — | Không có sẵn ở đâu; là kiểm soát pháp lý cốt lõi |
| Tải video đa nền tảng | **yt-dlp** qua VideoLingo `_1_ytdlp.py` | 190.797 | Unlicense | 1.510+ site |
| Tách giọng khỏi tiếng máy | **Demucs** qua VideoLingo `demucs_vl.py` | 3.203 | MIT | Giữ tiếng máy — quan trọng với video công nghiệp |
| ASR + forced alignment | **WhisperX** qua VideoLingo `_2_asr.py` | 24.017 | BSD-2 | Timestamp cấp từ ±50ms |
| Chọn đoạn | **Claude Sonnet 5** + prompt riêng | — | — | Tiêu chí kỹ thuật, không phải "điểm cười" |
| Ngắt câu + tóm tắt + dịch/viết | **VideoLingo `_3_*` `_4_*`** | 18.433 | Apache-2.0 | Có bước tóm tắt toàn video trước khi dịch |
| Phụ đề + burn | **VideoLingo `_5_*` `_6_*` `_7_*`** | 18.433 | Apache-2.0 | |
| **TTS / lồng tiếng** | **VoxCPM2** cắm qua `custom_tts.py` | 37.028 | **Apache-2.0** | Có tiếng Việt, có clone + voice design, on-prem |
| Thiết kế & thử giọng (chỉ G0) | **VoiceStudio** | 25.814 | AGPL-3.0 | Chỉ dùng nội bộ, không sửa, không vào đường sản xuất |
| Ghép lồng tiếng vào video | **VideoLingo `_8_*`→`_12_*`** | 18.433 | Apache-2.0 | |
| Trộn audio + ducking | **Easel `audio_mix.py`** + ffmpeg `sidechaincompress`, `loudnorm` | 1.002 | Apache-2.0 | Script độc lập, chỉ stdlib |
| Reframe 9:16 | **Easel `reframe.py`** chế độ `blur` | 1.002 | Apache-2.0 | Không mất nội dung — đúng cho video thiết bị |
| **Publish** | **Tự viết** — YouTube Data API + Facebook Graph API | — | — | Postiz là AGPL; hai nền tảng thì tự viết rẻ hơn |
| Sinh ảnh (GĐ2) | **Imagen 4 Fast** hoặc **Seedream** + thư viện ảnh NMI | — | API | Chỉ cho ảnh bối cảnh, không cho ảnh kỹ thuật |
| Render template brand (GĐ2) | **Remotion** | — | Thương mại nếu >3 người | Brand riêng; xác minh điều khoản trước |

### B.1. Những gì đã loại và vì sao

| Loại | Lý do |
|---|---|
| `krillinai/OpenCreator` (11.381★) | **Không có license** → mặc định giữ toàn bộ bản quyền, không có quyền dùng |
| `calesthio/OpenMontage` (58.176★) | AGPL-3.0 + không tải video + không publish + mô hình agentic không phù hợp sản xuất lô |
| `gitroomhq/postiz-app` (35.753★) | AGPL-3.0, là web app nên điều khoản network gần như chắc áp dụng |
| `jianchang512/pyvideotrans` (18.995★) | GPL-3.0 + không có tải video. Giữ làm nguồn đối chiếu |
| `WEIFENG2333/VideoCaptioner` (15.976★) | GPL-3.0. Nhưng **giữ để tham khảo** cách hiệu đính phụ đề bằng LLM — hữu ích cho nguồn tiếng Trung 12,8% CER |
| OmniVoice (engine mặc định VoiceStudio) | Weights CC-BY-NC → không thương mại |
| `RayVentura/ShortGPT`, `ClipsAI/clipsai`, `Kedreamix/Linly-Dubbing` | Bỏ hoang 18–20 tháng |
| Framework OpenClaw của Easel | Thêm phụ thuộc không cần; bus factor 1; tài liệu tiếng Trung |
| MoneyPrinterTurbo (123.071★) | Đúng GĐ2 chứ không phải GĐ1 — đánh giá lại khi tới G7 |

---

## Phần C — Kiến trúc Giai đoạn 1

**Đầu vào:** video từ nguồn nước ngoài (YouTube, Douyin, Bilibili, Facebook, TikTok, site hãng) do NMI khai báo.
**Đầu ra:** short video tiếng Việt có **lồng tiếng + phụ đề**, đăng YouTube và Facebook.

```
① NẠP NGUỒN ─ hộp thư URL (chính) + RSS kênh YouTube + API Bilibili
       │      [tự viết]
       ▼
② LICENSE GATE ─ sources.status == approved ? → nếu không: DỪNG
       │         scope phải gồm quyền SỬA AUDIO (lồng tiếng cần quyền này)
       ▼          [tự viết]
③ TẢI ─ yt-dlp   ⚠ Douyin: tải đồng bộ ngay (URL CDN hết hạn vài giờ)
       │          [VideoLingo _1_ytdlp]
       ▼
④ TÁCH AUDIO ─ Demucs: bỏ stem giọng, GIỮ stem tiếng máy
       │        [VideoLingo demucs_vl]
       ▼
⑤ ASR nguồn ─ WhisperX large-v3, language theo sources.audio_lang
       │       en ~93–95% | zh ~12,8% CER → cần soát kỹ hơn
       ▼       [VideoLingo _2_asr]
⑥ NGƯỜI SOÁT TRANSCRIPT ─ bắt buộc, nhất là nguồn zh
       ▼
⑦ CHỌN ĐOẠN ─ LLM đề xuất 2–3 cửa sổ 45–75s + lý do → người chọn
       │        tiêu chí: có số liệu kiểm chứng được, giải thích nguyên nhân,
       │        có thiết bị/màn hình thật; TRÁNH talking-head
       ▼       [Claude Sonnet 5, prompt riêng]
⑧ VIẾT KỊCH BẢN VIỆT ─ KHÔNG dịch từng chữ. Tóm tắt ngữ cảnh → viết lại
       │                 + phân tích NMI + bối cảnh VN. Ngân sách âm tiết/cảnh.
       ▼                [VideoLingo _3_* _4_* + glossary EN↔VI và ZH↔VI]
       ├──────────────────────────┐
       ▼                          ▼
⑨ TTS VoxCPM2              ⑪ CẮT + REFRAME 9:16
   giọng clone NMI             blur mode; BỎ QUA nếu nguồn đã 9:16
   [custom_tts.py ~20 dòng]    [Easel reframe.py]
       │                          │
       ▼                          │
⑩ FORCED ALIGN ─ kịch bản ĐÃ BIẾT ↔ audio TTS → timing phụ đề
   không thể sai chữ                │
   [WhisperX]                       │
       │                            │
       ▼                            │
⑫ TRỘN AUDIO ─ giọng Việt + nền tiếng máy (−18…−22 dB) + sidechain duck + loudnorm
       │        [Easel audio_mix.py + ffmpeg]
       ▼                            │
       └────────────┬───────────────┘
                    ▼
⑬ RENDER ─ burn phụ đề ASS (font đã test glyph U+1Exx) + intro/outro
       │    + thẻ ghi nguồn + GIỮ watermark gốc + nhãn AI
       ▼   [VideoLingo _5_→_7_, _8_→_12_]
⑭ NGƯỜI DUYỆT ─ bắt buộc. 20–35 phút nguồn en / 35–55 phút nguồn zh
       ▼
⑮ PUBLISH ─ publish(video, metadata, platform)
            YouTube Data API (100 upload/ngày) → Facebook Page Graph API
            TikTok: ưu tiên thấp nhất; KHÔNG đăng nếu nguồn có watermark dán cứng
            [tự viết]
```

### C.1. Những gì phải tự viết ở Giai đoạn 1

Chỉ còn bốn thứ — phần còn lại là ghép thành phần có sẵn:

1. **Hộp thư URL + bảng `sources`/`items` + license gate** — 3–4 ngày
2. **Tầng publish** YouTube + Facebook sau interface thống nhất — 5–8 ngày *(chưa tính chờ App Review)*
3. **Cắm VoxCPM2 vào `custom_tts.py`** + glossary hai chiều — 2–3 ngày
4. **Glue n8n** nối các bước, gate duyệt, thông báo — 3–4 ngày

Cộng việc tích hợp và test: **~2–3 tuần dev**.

---

## Phần D — Kiến trúc Giai đoạn 2

**Đầu vào:** bài viết từ các trang nước ngoài do NMI khai báo.
**Đầu ra:** short video từ nội dung viết mới, không dùng thước phim của ai.

```
① NẠP NGUỒN ─ DÙNG LẠI bảng sources, content_type='article'
       ▼      + crawler text (RSS / fetch trang)
② LỌC RELEVANCE ─ theo taxonomy nmi.vn: SPC, MSA, MES, historian,
       │           AI vision, kết nối máy, 6 ngành mục tiêu
       ▼
③ GOM NHIỀU NGUỒN CÙNG CHỦ ĐỀ ─ 3–5 bài, KHÔNG phải 1 bài
       │   ⚠ Đây là yêu cầu pháp lý, không phải tuỳ chọn — xem D.1
       ▼
④ VIẾT KỊCH BẢN GỐC ─ tổng hợp dữ kiện → viết bằng góc nhìn NMI
       │                lưu vết nguồn đã đọc cho từng kịch bản
       ▼               [Claude Sonnet 5 / Opus 5 cho bài khó + glossary]
       ├──────────────────────┬──────────────────────┐
       ▼                      ▼                      ▼
⑤ TTS VoxCPM2          ⑥ HÌNH ẢNH phân lớp    ⑦ BIỂU ĐỒ / BẢNG SO SÁNH
   CÙNG GIỌNG GĐ1        L1 ảnh NMI thật         render từ số liệu thật
   [dùng lại]            L2 stock có license      — dạng nội dung mạnh nhất
                         L3 AI chỉ cho bối cảnh     cho khán giả kỹ thuật
       │                      │                      │
       └──────────────────────┴──────────────────────┘
                         ▼
⑧ RENDER ─ template Remotion đúng brand (#081120, Inter/IBM Plex Mono,
       │    bám theo qone-30s-stable.mp4) + phụ đề + nhạc nền
       ▼
⑨ NGƯỜI DUYỆT ─ nhẹ hơn GĐ1 vì không phải soát transcript ngoại ngữ
       ▼
⑩ PUBLISH ─ DÙNG LẠI tầng publish của GĐ1
```

### D.1. Giai đoạn 2 rủi ro pháp lý thấp hơn — và cách giữ nó như vậy

**Bản quyền bảo hộ cách diễn đạt, không bảo hộ dữ kiện.** Giai đoạn 1 dùng chính thước phim được bảo hộ nên buộc phải có license. Giai đoạn 2 có thể đọc nhiều bài để hiểu dữ kiện rồi **viết** nội dung của riêng NMI — dữ kiện *"Cpk dùng độ lệch chuẩn trong nhóm mẫu"* không thuộc về ai.

Hai điều kiện kỹ thuật để giữ vị thế đó, phải đưa vào thiết kế chứ không để tuỳ người dùng:

- **Prompt phải nhận 3–5 nguồn cùng lúc.** Một nguồn duy nhất gần như chắc chắn cho ra bản diễn giải sát nguyên văn; nhiều nguồn buộc phải tổng hợp. Đây là ràng buộc nên kiểm tự động: pipeline từ chối chạy nếu chỉ có 1 nguồn cho một chủ đề.
- **Lưu vết nguồn cho từng kịch bản** — bài nào đã đọc để viết ra nó. Vừa để kiểm chứng thông tin kỹ thuật, vừa là bằng chứng quy trình.

Ranh giới: **viết** thì an toàn, **dịch** thì không. Đó là khác biệt về bản chất, không phải mức độ.

### D.2. Thứ Giai đoạn 2 thừa hưởng từ Giai đoạn 1

| Thành phần | Trạng thái khi vào GĐ2 |
|---|---|
| Hệ quản lý nguồn + license registry | Xong, chỉ thêm `content_type='article'` |
| Glossary EN↔VI và ZH↔VI | Xong, dùng ngay |
| Giọng VoxCPM2 đã clone và hiệu chỉnh | Xong — khoản thu hồi lớn nhất |
| Tầng publish | Xong |
| Brand kit: style phụ đề ASS, `loudnorm`, font đã test glyph | Xong |
| Bộ lọc relevance theo taxonomy nmi.vn | Xong |

**Ước lượng: ~60% công việc Giai đoạn 2 đã được xây ở Giai đoạn 1.** Phần mới: crawler text, prompt viết kịch bản gốc, sinh ảnh, template Remotion.

---

## Phần E — Chi phí

### E.1. Vận hành, 20–30 video/tháng

| Hạng mục | GĐ1 | GĐ2 |
|---|---|---|
| VPS chạy n8n + Postgres | $10–15 | $10–15 |
| LLM (chọn đoạn + kịch bản) | ~$0,50 | ~$1–2 (kịch bản dài hơn, nhiều nguồn) |
| TTS | **$0** — VoxCPM2 local | **$0** |
| ASR + Demucs + reframe + render | $0 — local | $0 |
| Sinh ảnh | — | $5–10 |
| Remotion license (nếu >3 người) | — | ~$100 `[cần xác minh remotion.pro]` |
| API publish | $0 | $0 |
| **Tổng** | **$11–16/tháng** | **$16–130/tháng** |

Toàn bộ thành phần mã nguồn mở đều miễn phí và cho dùng thương mại. Khoản duy nhất có thể phát sinh đáng kể là Remotion license ở GĐ2 — và có thể hoãn bằng cách render bằng ffmpeg ở giai đoạn đầu.

### E.2. Ràng buộc thật không phải tiền

| Ràng buộc | Số |
|---|---|
| **Giờ người duyệt GĐ1** | 20–35 phút/video nguồn tiếng Anh · **35–55 phút nguồn tiếng Trung** → 13–22 giờ/tháng ở 30 video |
| **GPU** | Bắt buộc thực tế: WhisperX large-v3 + Demucs + VoxCPM2 + reframe. VRAM 8 GB+ |
| **Nguồn có license** | Câu hỏi sinh tử của GĐ1 — trả lời ở G0 |
| **Thời gian duyệt app** | Facebook App Review ~20 ngày; TikTok audit 2–6 tuần |

### E.3. Công triển khai

| | Trước khảo sát | Sau khảo sát |
|---|---|---|
| Giai đoạn 1 | 4–6 tuần | **~2–3 tuần** |
| Giai đoạn 2 | — | **~3–4 tuần** (hưởng 60% từ GĐ1) |

---

## Phần F — Lộ trình chốt

| Mốc | Tuần | Nội dung | Câu hỏi nó trả lời |
|---|---|---|---|
| **G0** Kiểm chứng khả thi | 1 | Test yt-dlp trên URL thật **từng nền tảng** (Douyin dễ vỡ nhất) · đọc điều khoản media kit 3–5 hãng · gửi thư xin phép · **cài VoiceStudio, blind test VoxCPM2 vs FPT.AI vs Viettel bằng thuật ngữ SPC/MSA thật** · clone thử giọng một kỹ sư NMI · đo tốc độ đọc thật · test glyph U+1Exx · dựng VideoLingo chạy 1 video với `target_language: 'Tiếng Việt'` · xác nhận GPU | **Tải được từ đâu? Nguồn nào có phép? Giọng nào dùng được?** |
| **G1** Làm tay có công cụ | 2–3 | 5 video, **mỗi nền tảng ít nhất 1** · rút glossary EN↔VI + ZH↔VI từ corpus song ngữ nmi.vn · audio dùng ducking đơn giản | Mỗi video tốn bao nhiêu phút người, vướng ở đâu |
| **G2** Tự động hoá GĐ1 | 3–6 | Hộp thư URL + `sources`/`items` + license gate · n8n glue · cắm VoxCPM2 · Demucs · reframe có điều kiện · gate duyệt | Pipeline chạy end-to-end cả nguồn 16:9 và 9:16 |
| **G3** Publish YouTube | 5–7 | GCP + OAuth + Data API sau `publish()` | Video công khai đầu tiên, số liệu thật |
| **G4** Facebook | 7–9 | Page + Business Manager + Graph API (thử ngoại lệ App Review cho app nội bộ) | Kênh nào hiệu quả hơn |
| **G5** Đánh giá GĐ1 | 9–11 | Nguồn bền không? Engagement? Công duyệt chịu được? Nền tảng nguồn nào tốt nhất? | Mở rộng GĐ1 hay sang GĐ2 |
| **G6** Giai đoạn 2 | 11–15 | Crawler text · prompt đa nguồn + lưu vết · sinh ảnh phân lớp · template Remotion · dùng lại toàn bộ hạ tầng GĐ1 | Video nội dung gốc đầu tiên |
| **G7** Tuỳ chọn | 15+ | TikTok (nếu dữ liệu chứng minh đáng) · bản tiếng Anh (nội dung song ngữ đã có, chỉ tốn TTS) · LinkedIn | |

**G0 không được rút gọn.** Nó trả lời ba câu mà không đoán thay được, và nếu cả ba đều xấu thì thứ tự hai giai đoạn nên đảo lại — vì Giai đoạn 2 cần ít giấy phép hơn.

---

## Phần F2 — Chi tiết kỹ thuật bắt buộc biết khi triển khai

Đây là những cái bẫy đã xác minh. Mỗi cái đều là **chế độ thất bại im lặng** — pipeline chạy xong, không báo lỗi, kết quả sai.

### F2.1. Ma trận nền tảng nguồn

| Nền tảng | Khung | Reframe? | Audio | Watermark cứng | Khám phá |
|---|---|:---:|---|:---:|---|
| **YouTube** | 16:9 | Có | EN/JA/DE | Không | RSS theo kênh (miễn phí) + `search.list` có `videoLicense=creativeCommon` |
| **Bilibili** | 16:9 | Có | ZH | Thường không | API công khai, **bắt buộc WBI signature từ 05/2025** |
| **Douyin** | **9:16 sẵn** | **Bỏ qua** | ZH | **Có** | Không có API → chỉ URL thủ công |
| **TikTok** | 9:16 | Bỏ qua | Nhiều | **Có** | Không → URL thủ công |
| **Facebook** | Nhiều | Tuỳ | Nhiều | Không | Kém, thường chặn sau login → URL thủ công |
| **Vimeo / site hãng** | 16:9 | Có | EN | Không | RSS nếu có |

Bốn hệ quả:
1. **Kiến trúc là "hộp thư URL", không phải crawler đa nền tảng.** yt-dlp phủ 1.510+ site nên tải là bài toán đã giải; khám phá thì mỗi nền tảng một kiểu và phần lớn không có API. Đừng xây scraper cho nền tảng đang chặn — sẽ giòn và ngốn hết công bảo trì.
2. **Douyin: URL CDN hết hạn sau vài giờ** → phải tải **đồng bộ ngay lúc nạp URL**, không xếp hàng. Nhánh riêng, dễ bỏ sót, biểu hiện thành "một số video tự nhiên tải lỗi".
3. **Nguồn có watermark cứng thì đừng đăng lên TikTok** — TikTok xếp video mang logo nền tảng khác vào nội dung không nguyên bản. Giữ watermark (nó cũng là attribution); Douyin → TikTok là tổ hợp tệ nhất.
4. **Nguồn 9:16 bỏ qua hẳn reframe** — bước tốn compute nhất. Nhánh điều kiện theo `platform`.

### F2.2. Bẫy glyph tiếng Việt trong libass — phải test trước

Nhiều font thiếu glyph dải Unicode **U+1Exx** (ậ ả ằ ầ ấ ể ệ ỉ ồ ớ ộ ủ ự). Khi burn phụ đề, libass báo *"Glyph not found"* rồi **âm thầm thay font khác** — video render xong, không lỗi, nhưng chữ có dấu nặng và dấu ngã bị sai font hoặc hiện ô vuông.

Bắt buộc:
1. Chọn font có bộ tiếng Việt đầy đủ (Be Vietnam Pro thiết kế riêng cho tiếng Việt; Inter và IBM Plex Sans đang dùng trên nmi.vn cũng hỗ trợ — tự kiểm chứng).
2. Test bằng chuỗi đủ dấu, render ra ảnh và **soi mắt**:
   `ẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ`
3. Bật log libass trong CI và **fail build nếu có cảnh báo glyph**.

### F2.3. Ngân sách âm tiết — ràng buộc cứng của lồng tiếng

Tiếng Việt nói ra thường **dài hơn** tiếng Anh cùng nội dung, nên dịch trực tiếp gần như luôn tràn khung thời gian. Các nguồn ghi tốc độ tiếng Việt 5,28–6 âm tiết/giây `[blog — số liệu không thống nhất, chỉ để định hướng]`.

**Đừng lập kế hoạch theo con số đó.** Cách đúng: **tự đo giọng VoxCPM2 đã chọn** — đọc một đoạn 200 âm tiết, bấm thời gian, suy ra tốc độ thật ở đúng tốc độ cài đặt. Sau đó đưa vào prompt dưới dạng **ngân sách âm tiết cho từng cảnh**, không phải cho cả video (kịch bản phải khớp ranh giới cảnh).

Kiểm tra tự động: nếu TTS render dài hơn khung cho phép quá 5%, **trả kịch bản về cho LLM viết ngắn lại** — đừng tăng speed để nhồi cho vừa, giọng nhanh bất thường là dấu hiệu video máy làm.

### F2.4. Trộn audio — giữ tiếng máy

Video công nghiệp có tiếng máy chạy, tiếng bíp HMI — âm thanh **mang thông tin** và làm video đáng tin. Xoá sạch audio gốc thì video nghe như slideshow.

Quy trình: Demucs tách stem giọng → **bỏ stem giọng** → giữ stem còn lại làm nền ở **−18 đến −22 dB** → lồng giọng Việt lên → **sidechain ducking**.

Cấu hình ffmpeg được ghi nhận: `[1:a][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[duck]` `[blog]`. Xử lý sự cố: nền "pump" nghe rõ → tăng `release` hoặc giảm `ratio`; ducking trễ hơn giọng → giảm `attack`.

Chuẩn hoá độ to bằng `loudnorm` (mốc phổ biến cho nền tảng xã hội khoảng −14 LUFS `[chưa xác minh — kiểm tài liệu từng nền tảng]`). Bỏ bước này thì video to nhỏ thất thường giữa các bài.

### F2.5. Timing phụ đề — forced alignment, không phải ASR

Bạn **đã biết chính xác chữ tiếng Việt** (chính kịch bản viết ra). Đừng chạy ASR trên audio TTS vừa tạo để lấy phụ đề — đó là tự tạo lỗi nhận dạng từ một văn bản đã hoàn hảo.

Cách đúng: đưa **kịch bản đã biết + audio TTS** vào WhisperX forced alignment → timestamp cấp từ. Chữ không thể sai vì chữ là đầu vào.

Phụ đề vì vậy **trùng nội dung với lời lồng tiếng** — có chủ ý. Hai văn bản Việt khác nhau (tai nghe một bản, mắt đọc bản khác) làm người xem rất mệt; trùng nhau thì hai kênh củng cố nhau, và phục vụ đúng thực tế phần lớn người xem short-form để tắt tiếng.

### F2.6. Reframe: dùng `blur`, không dùng crop

Với video công nghiệp, **toàn bộ khung hình đều mang thông tin**. Cắt hai bên để "theo dõi đối tượng" chính là làm mất thứ người xem cần thấy.

| Chế độ | Khi nào |
|---|---|
| **`blur`** | **Mặc định** cho nguồn 16:9 công nghiệp — máy móc, dây chuyền, HMI, screen recording |
| `crop` | Chủ thể rõ và muốn kín màn hình; cần `--focus-x` nếu chủ thể lệch |
| `smart` / face-pan | Chỉ khi nội dung là người nói — mà tiêu chí chọn đoạn đã chủ động tránh loại này |

### F2.7. Ràng buộc API publish đã xác minh

| Nền tảng | Ràng buộc |
|---|---|
| **YouTube** | `videos.insert` có **bucket quota riêng: 1 unit/lần, tối đa 100 lần/ngày**. Con số "1.600 units mỗi upload" đã lạc hậu. Các write khác (update/rate/delete) 50 units trong pool 10.000/ngày |
| **Facebook** | Reels **chỉ lên Page**, không lên profile. Cần `pages_show_list` + `pages_read_engagement` + `pages_manage_posts`. **Ngoại lệ đáng dùng: không cần App Review nếu app chỉ được dùng bởi người có role trên chính app đó** |
| **TikTok** | Client chưa audit: khoá ở `SELF_ONLY`, **tối đa 5 user/24h**, ~15 bài/ngày/creator chia chung mọi API client. Bắt buộc UX: user phải **chủ động chọn** privacy, không set default |

### F2.8. Chất lượng ASR theo ngôn ngữ nguồn

| Nguồn | Độ chính xác | Công duyệt/video |
|---|---|---|
| Tiếng Anh sạch | ~93–95% độ chính xác từ `[blog]` | 20–35 phút |
| **Tiếng Trung** | **~12,8% CER** (Common Voice) `[blog]` — khoảng 1/8 ký tự sai | **35–55 phút** |

Có thể truyền `initial_prompt` chứa thuật ngữ để cải thiện, nhưng cùng nguồn cảnh báo việc đó **tăng nguy cơ hallucination** — dùng thận trọng và luôn soát. Nếu người duyệt là nguồn lực khan, **ưu tiên nguồn tiếng Anh** dù nguồn Trung dồi dào hơn.

---

## Phần G — Rủi ro và điểm cần quyết

### G.1. Bốn rủi ro lớn nhất

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| **Không đủ nguồn video có license** | **Cao** | G0 đo trước. Nếu xấu → đảo sang GĐ2 trước |
| **Chất lượng giọng Việt của VoxCPM2 chưa đạt** | Trung bình | Blind test ở G0. Dự phòng: FPT.AI qua cùng `custom_tts.py` — đổi engine không đổi kiến trúc |
| **Chất lượng transcript nguồn tiếng Trung** | Trung bình | Người duyệt phải đọc được tiếng Trung; nếu không có thì hoãn nhóm nguồn này |
| **Công người duyệt không kham được** | Trung bình | Giảm volume mục tiêu; ưu tiên nguồn tiếng Anh (công duyệt bằng nửa) |

### G.2. Còn cần bạn quyết

1. **NMI là đại lý/nhà phân phối của hãng nào?** — câu hỏi giá trị nhất. Nếu có, kiểm tra hợp đồng **có bao gồm quyền sửa audio** không (lồng tiếng cần quyền đó, và nó không suy ra từ quyền "dùng lại").
2. **Có máy GPU ≥8 GB VRAM không?** Quyết định toàn bộ mô hình chi phí.
3. **5–10 URL nguồn thật** — để đánh giá tỷ lệ b-roll/talking-head, watermark, và khả năng tải.
4. **Tỷ lệ nguồn tiếng Trung so với tiếng Anh**, và **có ai đọc được tiếng Trung không?**
5. **Ai duyệt, bao nhiêu giờ/tuần?**
6. **Giọng đọc:** clone giọng thật của một kỹ sư NMI (tôi nghiêng về phương án này — xem A.5), hay dùng giọng tổng hợp? Nam/nữ, vùng miền nào?
7. **Có giữ TikTok trong phạm vi không?**
8. **Có làm bản tiếng Anh không?** Nội dung song ngữ đã có, chỉ tốn thêm TTS — cách nhân đôi sản lượng rẻ nhất.

---

## Phần H — Ba việc làm đầu tiên

Theo đúng thứ tự, tất cả nằm trong tuần G0 và không cần chờ nhau:

1. **Gửi email xin phép 3–5 hãng thiết bị** — không cần kỹ sư, ROI cao nhất trong cả dự án. Nếu một hãng đồng ý, rủi ro pháp lý GĐ1 chuyển thành quy trình tuân thủ bình thường.
2. **Dựng VideoLingo + VoxCPM2, chạy một video thật** với `target_language: 'Tiếng Việt'`. Nửa ngày, và nó trả lời cùng lúc: chất lượng dịch thuật ngữ kỹ thuật, chất lượng giọng Việt, và pipeline có chạy trên máy bạn không.
3. **Test tải bằng yt-dlp trên URL thật của từng nền tảng** bạn định dùng. Douyin là chỗ dễ vỡ nhất; nếu nền tảng bạn trông cậy nhất không tải ổn định thì phải biết ở tuần 1, không phải tuần 6.

---

## Ghi chú về mức xác minh

**Đã xác minh trực tiếp từ nguồn gốc:** toàn bộ số star, license, ngày cập nhật (GitHub REST API, 13/09/2026) · license và danh sách ngôn ngữ VoxCPM2 (HF model card `openbmb/VoxCPM2`: `license: apache-2.0`, có `vi`) · bảng engine và điều khoản license của VoiceStudio (README) · cấu trúc pipeline và `config.yaml` của VideoLingo · độ độc lập của các script Easel (đọc phần import) · quota YouTube Data API · giới hạn TikTok Content Posting API · quyền Facebook Reels · chính sách monetization YouTube · giá ElevenLabs và FPT.AI · nội dung nmi.vn (bundle production).

**Chưa xác minh, cần kiểm ở G0:** tên giọng tiếng Việt của edge-tts · **chất lượng thực tế giọng Việt của VoxCPM2** (đây là ẩn số quan trọng nhất còn lại) · chất lượng bản dịch thuật ngữ SPC/MSA của VideoLingo · điều khoản Remotion company license · tiếng Việt trong MOSS-TTS-v1.5 / dots.tts / MOSS-TTS-Nano (các phương án dự phòng cho VoxCPM2).
