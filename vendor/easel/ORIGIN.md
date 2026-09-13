# ORIGIN

- Repo:     https://github.com/ZJU-REAL/Easel
- Commit:   16f068e4a5c147712d01ae6601765e42edaaf6e8
- Ngày lấy: 2026-09-13
- License:  Apache-2.0 (bản đầy đủ trong `LICENSE` cùng thư mục)
- File đã lấy:
  - `skills/shared/scripts/reframe.py`       → `reframe.py`
  - `skills/shared/scripts/audio_mix.py`     → `audio_mix.py`
  - `skills/shared/scripts/subtitle_ops.py`  → `subtitle_ops.py`
- Đã sửa: **(không có)** — giữ nguyên từng byte để còn so được với upstream.

## Vì sao lấy được từng file rời

Ba script này **độc lập hoàn toàn**: chỉ dùng thư viện chuẩn Python và gọi
`ffmpeg`/`ffprobe` qua `subprocess`, không import chéo sang phần còn lại của
Easel. Copy một file là chạy được.

## Cách dùng trong dự án này

Không import trực tiếp từ code. Gọi qua adapter ở
`src/infrastructure/media/easel.py` — lý do: `AGENTS.md` cấm sửa `vendor/`, nên
mọi khác biệt về tham số và xử lý lỗi phải nằm ở adapter để còn nâng cấp
upstream được.

## Bẫy đã biết

`audio_mix.py --bgm-volume` là **hệ số tuyến tính**, không phải dB. Mặc định
`0.25` ≈ −12 dB, còn đặc tả F2.4 cần nền ở −18…−22 dB → adapter truyền
`0.08`–`0.13`. Để mặc định thì tiếng máy to hơn dự kiến khoảng 10 dB.

Trợ giúp dòng lệnh của cả ba script bằng tiếng Trung — không ảnh hưởng chạy,
nhưng đọc `argparse` trong source thay vì dựa vào `--help`.
