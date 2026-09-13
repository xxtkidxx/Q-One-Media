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

## Đã vendor

| Thư mục | Nguồn | License | Trạng thái |
|---|---|---|---|
| `easel/` | `ZJU-REAL/Easel` @ `16f068e4` | Apache-2.0 | ✅ `reframe.py`, `audio_mix.py`, `subtitle_ops.py` + `LICENSE` + `ORIGIN.md` |

## Không vendor VideoLingo — quyết định đã đổi (D23)

Kế hoạch ban đầu là vendor `core/_1_ytdlp.py` … `core/_12_dub_to_vid.py`. Sau khi
đọc source thì **không vendor gì từ VideoLingo**, vì bề mặt thật sự dùng lại được
nhỏ hơn nhiều so với tưởng:

- **Bước tải** (`_1_ytdlp.py`): ba vấn đề chặn — `pip install --upgrade` mỗi lần
  tải, thư mục `output/` toàn cục, gắn cứng `config.yaml`. Đã tự viết
  `src/infrastructure/ingest/ytdlp.py`.
- **Prompt dịch** (`_3_*`, `_4_*`): VideoLingo dịch **từng câu sát nghĩa**. Giai
  đoạn 1 của dự án này **không dịch mà viết lại** (đặc tả mục C bước ⑧) — bài toán
  khác, nên prompt của họ không dùng được.
- **Tách phụ đề theo ngữ nghĩa**: có giá trị, nhưng phụ đề ở đây sinh từ forced
  alignment của **chính kịch bản mình viết** (F2.5), không phải từ câu dịch.
- **Demucs và WhisperX** (`demucs_vl.py`, `_2_asr.py`): chỉ là ~50 dòng keo quanh
  API của `demucs` và `whisperx` — hai thư viện đã pin trong
  `docker/worker/requirements.txt`. Gọi thư viện trực tiếp sạch hơn là vendor keo
  rồi bọc adapter quanh keo.

Tham số nào mượn ý từ VideoLingo (ví dụ `htdemucs` với `shifts=1, overlap=0.25`,
và cách cộng các stem không phải giọng làm nền) được **ghi nguồn trong docstring**
của adapter tương ứng. Đó là ý tưởng, không phải code — không sinh nghĩa vụ
license, nhưng ghi nguồn vẫn là việc nên làm.

## Không vendor

- Tầng publish của Easel — nền tảng Trung Quốc, lại dùng browser automation.
- Framework OpenClaw — thêm phụ thuộc không cần thiết.
- VoiceStudio — AGPL-3.0. Dùng VoxCPM2 trực tiếp (cài qua pip trong worker image).

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
