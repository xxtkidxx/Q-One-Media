"""Đưa video về khung dọc 9:16.

Thuật toán *blur fill* và *focus crop* ở đây viết lại từ ``skills/shared/scripts/
reframe.py`` của **Easel** (https://github.com/ZJU-REAL/Easel, Apache-2.0, commit
``16f068e4a5c147712d01ae6601765e42edaaf6e8``). Xem ``docs/THIRD_PARTY_NOTICES.md``.

Viết lại chứ không gọi lại script gốc, vì ba lý do đo được:

1. Script gốc là CLI: mỗi lần đổi khung là một tiến trình Python mới chỉ để ghép một
   chuỗi filtergraph rồi gọi ffmpeg. Ở đây ghép thẳng và gọi ffmpeg một lần.
2. Lỗi của nó đi ra ``stderr`` bằng **tiếng Trung** kèm ``sys.exit`` — không phân
   loại được retry được hay không, mà đó chính là thứ hàng đợi việc cần biết.
3. Nó dò khuôn mặt bằng ``cv2`` cho chế độ ``smart``. Nội dung của dự án này là dây
   chuyền, HMI, screen recording — hiếm khi có mặt người, nên phần đó là một phụ
   thuộc nặng đổi lấy gần như không gì.

**Mặc định là ``blur``, không phải ``crop``** — với video công nghiệp thì *toàn bộ
khung hình mang thông tin*: máy móc, dây chuyền, đồng hồ, màn hình HMI. Cắt hai bên
để "bám đối tượng" chính là cắt mất thứ người xem cần thấy (đặc tả F2.6).
"""

from __future__ import annotations

from pathlib import Path

from src.domain.production.value_objects import ReframeMode
from src.infrastructure.media import ffmpeg
from src.shared.logging import get_logger

log = get_logger(__name__)

# Độ mờ của nền. 25 là mức của Easel: đủ để nền không tranh sự chú ý với khung
# chính, chưa tới mức thành một mảng màu phẳng.
DEFAULT_BLUR_SIGMA = 25

# Tỷ lệ cho phép. Danh sách đóng chứ không nhận chuỗi tuỳ ý: sai tỷ lệ thì video
# vẫn render ra bình thường, chỉ là sai khung — loại lỗi không ai thấy cho tới
# khi đăng.
SUPPORTED_RATIOS = ("9:16", "16:9", "1:1", "4:5")


class ReframeFailed(RuntimeError):
    retryable = False


def _even(value: float) -> int:
    """Làm tròn về số chẵn — H.264 với ``yuv420p`` yêu cầu cả hai chiều chẵn."""
    return round(value / 2) * 2


def output_size(ratio: str, source_w: int, source_h: int) -> tuple[int, int]:
    """Kích thước đích: giữ nguyên cạnh dài của nguồn, suy ra cạnh kia theo tỷ lệ.

    Giữ cạnh dài nghĩa là **không phóng to** — phóng to video nguồn chỉ làm file
    nặng hơn mà không thêm một chi tiết nào.
    """
    if ratio not in SUPPORTED_RATIOS:
        raise ReframeFailed(f"tỷ lệ {ratio!r} không nằm trong {SUPPORTED_RATIOS}")
    rw, rh = (int(x) for x in ratio.split(":"))
    long_edge = max(source_w, source_h)
    if rw < rh:  # khung dọc
        out_h, out_w = long_edge, long_edge * rw / rh
    else:
        out_w, out_h = long_edge, long_edge * rh / rw
    return _even(out_w), _even(out_h)


def _vf_blur(out_w: int, out_h: int, sigma: int) -> str:
    """Nền là chính khung hình đó, phóng to cho đầy rồi làm mờ; khung gốc đặt giữa.

    Nhờ vậy không có dải đen hai bên mà cũng không mất một pixel nào của bản gốc.
    """
    return (
        "split=2[bg][fg];"
        f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h},gblur=sigma={sigma}[bgb];"
        f"[fg]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


def _vf_crop(
    out_w: int, out_h: int, source_w: int, source_h: int, focus_x: float, focus_y: float
) -> str:
    """Cắt đúng tỷ lệ quanh một điểm tiêu. **Có mất phần rìa** — xem docstring đầu file."""
    scale = max(out_w / source_w, out_h / source_h)
    crop_w = _even(min(source_w, out_w / scale))
    crop_h = _even(min(source_h, out_h / scale))
    # Kẹp trong khung để điểm tiêu sát mép không đẩy vùng cắt ra ngoài ảnh.
    x = f"max(0\\,min(iw-{crop_w}\\,iw*{focus_x:.4f}-{crop_w}/2))"
    y = f"max(0\\,min(ih-{crop_h}\\,ih*{focus_y:.4f}-{crop_h}/2))"
    return f"crop={crop_w}:{crop_h}:{x}:{y},scale={out_w}:{out_h},setsar=1"


def reframe(
    source: Path,
    dest: Path,
    *,
    ratio: str = "9:16",
    mode: ReframeMode = ReframeMode.BLUR,
    blur_sigma: int = DEFAULT_BLUR_SIGMA,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> Path:
    """Đưa video về tỷ lệ đích. Trả về ``dest``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    info = ffmpeg.probe(source)
    if not info.width or not info.height:
        raise ReframeFailed(f"{source} không có stream hình để đổi khung")

    out_w, out_h = output_size(ratio, info.width, info.height)

    if mode is ReframeMode.BLUR:
        vf = _vf_blur(out_w, out_h, blur_sigma)
    elif mode is ReframeMode.CROP:
        vf = _vf_crop(out_w, out_h, info.width, info.height, focus_x, focus_y)
    else:
        # SMART cần dò khuôn mặt; chưa hiện thực vì nội dung dự án hiếm có mặt
        # người. Nói thẳng ra thay vì lặng lẽ rơi về blur — rơi ngầm thì người gọi
        # tưởng đã được bám đối tượng.
        raise ReframeFailed(
            f"chế độ {mode} chưa hiện thực — dùng {ReframeMode.BLUR} hoặc {ReframeMode.CROP}"
        )

    log.info(
        "reframe.start",
        mode=str(mode),
        source=f"{info.width}x{info.height}",
        dest=f"{out_w}x{out_h}",
        ratio=ratio,
    )
    args = [
        "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-preset", "medium",
    ]
    # Giữ nguyên tiếng nếu có: bước này chỉ đổi khung hình, đụng vào audio là
    # encode thừa một lần. Không có tiếng thì nói rõ ``-an``, vì ffmpeg gặp
    # ``-c:a copy`` mà không có stream audio sẽ báo lỗi.
    args += ["-c:a", "copy"] if info.has_audio else ["-an"]
    args.append(str(dest))
    ffmpeg.run(args)
    return dest
