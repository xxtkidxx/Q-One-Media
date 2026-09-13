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

## Chữ ký đã xác minh (đọc trực tiếp source, 13/09/2026)

Ghi lại để lần sau không phải đọc lại upstream.

### VideoLingo `core/tts_backend/custom_tts.py`

```python
def custom_tts(text: str, save_path: str) -> None
```

Đúng hai tham số, không trả về gì, tự tạo thư mục cha. Adapter VoxCPM2 (G2.9) cắm vào đây là đủ
— nhưng **đừng giữ nguyên `try/except Exception` rồi `print`** như bản gốc: nó nuốt lỗi và trả về
bình thường, nên pipeline sẽ đi tiếp với file audio rỗng.

### VideoLingo `core/asr_backend/demucs_vl.py`

Dùng `htdemucs`, `shifts=1`, `overlap=0.25`. Ghi ra hai file: stem giọng và **tổng các stem còn
lại** làm nền. Đúng thứ cần cho F2.4 (bỏ giọng, giữ tiếng máy). Đường dẫn là hằng số cấp module
(`_VOCAL_AUDIO_FILE`…) nên phải chạy trong thư mục riêng của từng item.

### Easel `skills/shared/scripts/reframe.py`

```
-i IN -o OUT --ratio 9:16 [--mode blur|crop|smart] [--size WxH]
[--focus-x 0.5] [--focus-y 0.5] [--blur-sigma 25]
```

Mặc định `--mode blur` — trùng với D9, không cần truyền. Chỉ dùng stdlib + gọi ffmpeg qua
subprocess, không import chéo trong repo Easel → copy một file là chạy.

### Easel `skills/shared/scripts/audio_mix.py`

```
--voice VOICE [--voice-volume 1.0] --bgm BGM [--bgm-volume 0.25]
[--bgm-loop-off] [--no-duck] [--sfx F --sfx-at S]... [--duration N] -o OUT
```

Tự bật sidechain ducking khi có cả `--voice` và `--bgm` (tắt bằng `--no-duck`). Độ dài đầu ra
theo `--voice`.

**Lưu ý về đơn vị:** `--bgm-volume` là hệ số **tuyến tính**, không phải dB. Mặc định `0.25`
≈ −12 dB, còn đặc tả F2.4 cần nền ở −18…−22 dB → truyền khoảng **`0.08`–`0.13`**. Để mặc định
thì tiếng máy to hơn dự kiến ~10 dB.

Trợ giúp dòng lệnh của cả hai script bằng tiếng Trung — không ảnh hưởng chạy, nhưng đừng dựa vào
`--help` khi viết adapter, đọc `argparse` trong source.
