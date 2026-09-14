"""Đo tốc độ đọc thật của giọng đang dùng → giá trị cho ``TTS_SYLLABLES_PER_SEC``.

Chạy trong container:

    docker compose ... run --rm worker python scripts/measure_speech_rate.py
    docker compose ... run --rm api    python scripts/measure_speech_rate.py   # engine edge

Đây là G0.7 ở dạng chạy được. Đặc tả F2.3 yêu cầu **tự đo** thay vì lấy con số
trên mạng, và số liệu đo ngày 14/09/2026 cho thấy lý do rất cụ thể:

===================================== =====================
Các nguồn trên mạng ghi               5,28–6 âm tiết/giây
Đo thật (edge-tts, giọng vi-VN)       **3,52 âm tiết/giây**
===================================== =====================

Chênh gần 40%. Lấy 5,5 thì ngân sách âm tiết rộng hơn thực tế khoảng 56%, nghĩa
là **mọi cảnh đều tràn khung** — và tràn đều nhau nên không ai thấy nguyên nhân.

Hai lý do khiến số đo thấp hơn, và cả hai đều là lý do để dùng số đo chứ không
dùng số trên mạng:

1. Số trên mạng thường là *tốc độ phát âm* thuần, không tính khoảng lặng. Còn
   ngân sách của ta phải tính cả khoảng lặng ở dấu câu, vì audio thật có chúng.
2. Phải đo bằng **đúng hàm đếm âm tiết** mà ngân sách dùng
   (``count_syllables``). Hàm đó đếm "Cpk" là 1 dù đọc ra là ba tiếng, nên nếu
   đo bằng cách đếm khác thì hai con số không ghép được với nhau.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Đoạn mẫu dùng đúng loại nội dung dự án này làm: thuật ngữ SPC/MSA, số liệu đọc
# thành lời, câu dài vừa phải. Đo bằng văn bản khác thì ra số khác.
SAMPLE = (
    "Cpk chỉ nói về độ lệch trong nhóm mẫu. Nó không nói gì về độ trôi giữa các lô. "
    "Một dây chuyền có Cpk một phẩy ba ba vẫn có thể cho ra hàng lỗi nếu trung bình "
    "quá trình trôi dần theo ca. Biểu đồ kiểm soát mới cho thấy điều đó, và bộ quy tắc "
    "Nelson bắt được xu hướng trước khi có điểm vượt giới hạn. Gage R và R dưới mười "
    "phần trăm thì hệ đo chấp nhận được, nhưng con số đó chưa nói gì về độ phân giải."
)


def main() -> int:
    from datetime import UTC, datetime

    from src.domain.sourcing.entities import Source
    from src.domain.sourcing.value_objects import (
        LicenseEvidence,
        LicenseScope,
        LicenseType,
        Platform,
        SourceKind,
        SourceUrl,
    )
    from src.infrastructure.media import ffmpeg
    from src.infrastructure.tts.registry import build_synthesizer
    from src.infrastructure.tts.voxcpm import count_syllables
    from src.shared.config import get_settings

    settings = get_settings()
    synth = build_synthesizer(settings)
    engine = settings.tts.engine

    # Nguồn giả đã approved: TTS đòi DubbingClearance theo thiết kế, và clearance
    # chỉ Source cấp được. Dùng license 'own' vì đây là văn bản của chính NMI.
    now = datetime.now(UTC)
    source = Source(
        platform=Platform.WEB,
        kind=SourceKind.SINGLE_URL,
        url=SourceUrl("https://nmi.vn/do-toc-do-doc"),
        id=0,
    )
    source.approve(
        by="scripts/measure_speech_rate.py",
        evidence=LicenseEvidence(license_type=LicenseType.OWN, evidence_ref="văn bản nội bộ"),
        scope=LicenseScope(may_translate=True, may_modify_audio=True, may_subtitle=True),
        at=now,
    )
    clearance = source.clear_for_dubbing(now)

    syllables = count_syllables(SAMPLE)
    out_dir = Path(os.environ.get("MEDIA_ROOT", "/data/media")) / "work" / "speech-rate"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Engine: {engine}")
    print(f"Đoạn mẫu: {len(SAMPLE)} ký tự, {syllables} âm tiết (theo count_syllables)")
    print()

    audio = synth.synthesize(
        text=SAMPLE, dest=out_dir / f"sample-{engine}.wav", clearance=clearance
    )
    duration = ffmpeg.probe(audio).duration_sec
    if duration <= 0:
        print("Audio dài 0 giây — TTS không sinh được gì.")
        return 1

    rate = syllables / duration
    print(f"Audio: {duration:.2f}s  ({audio})")
    print(f"Tốc độ đọc: {rate:.2f} âm tiết/giây")
    print()
    print("Đặt vào .env:")
    print(f"  TTS_SYLLABLES_PER_SEC={rate:.2f}")
    print()
    print("Nghe lại file audio trước khi tin con số: nếu giọng nghe nhanh bất thường")
    print("thì vấn đề ở cấu hình TTS, không phải ở ngân sách.")
    print()
    print(f"Với khung 60 giây, ngân sách sẽ là {int(60 * rate)} âm tiết.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
