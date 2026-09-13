"""Adapter cho script Easel đã vendor.

Gọi qua ``subprocess`` chứ không import, vì `vendor/` không được sửa và ba script
đó là CLI đúng nghĩa (có `argparse`, `main()`, `sys.exit`). Bọc ở đây để:

- đổi đơn vị âm lượng từ dB sang hệ số tuyến tính mà script chờ đợi;
- áp mặc định của dự án (`blur`, nền −20 dB) thay vì mặc định của upstream;
- phân loại lỗi thành retry được / không.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.domain.production.value_objects import ReframeMode
from src.shared.logging import get_logger

log = get_logger(__name__)

VENDOR_EASEL = Path(__file__).resolve().parents[3] / "vendor" / "easel"

# Nền tiếng máy ở −20 dB: giữa khoảng −18…−22 dB của đặc tả F2.4.
DEFAULT_BACKGROUND_DB = -20.0


class EaselFailed(RuntimeError):
    retryable = False

    def __init__(self, script: str, stderr: str) -> None:
        tail = "\n".join(stderr.strip().splitlines()[-10:])
        super().__init__(f"{script} thất bại:\n{tail}")


def db_to_linear(db: float) -> float:
    """Đổi dB sang hệ số tuyến tính.

    Cần thiết vì `audio_mix.py --bgm-volume` nhận **hệ số tuyến tính**, không phải
    dB — mặc định `0.25` của upstream ≈ −12 dB, to hơn mức đặc tả yêu cầu khoảng
    8–10 dB. Đây đúng là loại sai số không ai nghe ra là *sai*, chỉ thấy "nền hơi
    to", nên phải tính chứ không ước lượng.
    """
    return round(10 ** (db / 20), 4)


def _run(script: str, subcommand: str, args: list[str]) -> None:
    """Gọi script Easel.

    ``subcommand`` là bắt buộc: cả ba script dùng ``add_subparsers`` nên
    ``reframe.py -i a.mp4`` bị từ chối, phải là ``reframe.py reframe -i a.mp4``.
    Chi tiết dễ bỏ sót khi chỉ đọc danh sách ``add_argument``.
    """
    path = VENDOR_EASEL / script
    if not path.exists():
        raise EaselFailed(script, f"chưa vendor {path} — xem vendor/easel/ORIGIN.md")
    cmd = [sys.executable, str(path), subcommand, *args]
    log.info("easel.run", script=script, subcommand=subcommand, args=args)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise EaselFailed(script, (proc.stderr or "") + (proc.stdout or ""))


def reframe(
    source: Path,
    dest: Path,
    *,
    ratio: str = "9:16",
    mode: ReframeMode = ReframeMode.BLUR,
    blur_sigma: int = 25,
    focus_x: float = 0.5,
) -> Path:
    """Đưa video về tỷ lệ dọc.

    Mặc định ``blur`` chứ không ``crop``: với video công nghiệp thì **toàn bộ
    khung hình mang thông tin** — máy móc, dây chuyền, HMI, screen recording. Cắt
    hai bên để "theo dõi đối tượng" chính là làm mất thứ người xem cần thấy (F2.6).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "-i", str(source),
        "-o", str(dest),
        "--ratio", ratio,
        "--mode", str(mode),
    ]
    if mode is ReframeMode.BLUR:
        args += ["--blur-sigma", str(blur_sigma)]
    if mode is ReframeMode.CROP:
        args += ["--focus-x", str(focus_x)]
    _run("reframe.py", "reframe", args)
    return dest


def mix_voice_over_background(
    voice: Path,
    background: Path,
    dest: Path,
    *,
    background_db: float = DEFAULT_BACKGROUND_DB,
    voice_volume: float = 1.0,
    duck: bool = True,
) -> Path:
    """Lồng giọng Việt lên nền tiếng máy, có sidechain ducking.

    ``background`` là stem **không phải giọng** do Demucs tách ra — tiếng máy
    chạy, tiếng bíp HMI. Giữ lại vì âm thanh đó *mang thông tin* và làm video
    đáng tin với khán giả kỹ thuật; xoá sạch thì video nghe như slideshow (F2.4).

    Độ dài đầu ra theo ``voice`` — đúng thứ cần, vì giọng Việt là trục thời gian
    của video thành phẩm.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "--voice", str(voice),
        "--voice-volume", str(voice_volume),
        "--bgm", str(background),
        "--bgm-volume", str(db_to_linear(background_db)),
        "--bgm-loop-off",  # nền là tiếng máy của chính video, lặp lại sẽ nghe giả
        "-o", str(dest),
    ]
    if not duck:
        args.append("--no-duck")
    _run("audio_mix.py", "mix", args)
    return dest
