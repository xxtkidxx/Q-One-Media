# vendor/ — code bên thứ ba

Code lấy từ dự án mã nguồn mở, **không sửa trực tiếp**. Cần đổi hành vi thì bọc adapter trong `src/` — để còn so được với upstream khi họ sửa lỗi.

## Quy tắc

Mỗi thư mục con **phải** có `ORIGIN.md` ghi đúng năm thứ:

```markdown
# ORIGIN
- Repo:    https://github.com/<owner>/<repo>
- Commit:  <SHA đầy đủ>
- Ngày lấy: YYYY-MM-DD
- License: Apache-2.0 | MIT | ...
- File đã lấy:
  - path/to/file.py
- Đã sửa: (không có) | mô tả từng chỗ
```

Đây vừa là nghĩa vụ license (Apache-2.0 yêu cầu giữ thông báo bản quyền và ghi nhận thay đổi), vừa là cách duy nhất để sau này biết mình đang lệch bao nhiêu so với upstream.

## Dự kiến vendor (G1.1)

| Thư mục | Nguồn | License | Lấy gì |
|---|---|---|---|
| `videolingo/` | `Huanshere/VideoLingo` | Apache-2.0 | `core/_1_ytdlp.py`, `core/_2_asr.py`, `core/asr_backend/demucs_vl.py`, `core/_3_*`, `core/_4_*`, `core/_5_*`–`_7_*`, `core/_8_*`–`_12_*`, `core/tts_backend/custom_tts.py` |
| `easel/` | `ZJU-REAL/Easel` | Apache-2.0 | `skills/shared/scripts/reframe.py`, `audio_mix.py`, `subtitle_ops.py`, `intro_outro.py` |

Các script Easel **độc lập hoàn toàn** — chỉ dùng thư viện chuẩn Python và gọi ffmpeg qua subprocess, không import chéo. Copy từng file là chạy được.

## Không vendor

- Tầng publish của Easel — nền tảng Trung Quốc, lại dùng browser automation.
- Framework OpenClaw — thêm phụ thuộc không cần thiết.
- VoiceStudio — AGPL-3.0. Dùng VoxCPM2 trực tiếp (cài qua pip trong worker image), không vendor.
