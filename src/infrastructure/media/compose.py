"""Dựng video Giai đoạn 2 từ kịch bản hình — **chỉ bằng ffmpeg**.

Vì sao không phải Remotion như đặc tả ghi (mục ⑧): hai lý do độc lập, cùng chặn.
*License* — Remotion miễn phí cho cá nhân và công ty nhỏ, còn doanh nghiệp phải
mua Company License; đây là dự án thương mại của NMI, nên nó là một khoản chi và
một ràng buộc pháp lý cho thứ ta chưa cần. *Hạ tầng* — Remotion kéo Node + npm +
một image nữa vào một stack đã cố tình không có npm (D21/D25), để đổi lấy khả
năng làm hoạt hoạ mà short kỹ thuật gần như không dùng.

Thứ thật sự cần là: ảnh/video đứng yên nối nhau, thẻ chữ đúng brand, biểu đồ từ
số liệu thật, phụ đề, giọng đọc. ffmpeg làm đủ, và nó đã là phụ thuộc cứng của
Giai đoạn 1 — không thêm một mắt xích nào có thể hỏng.

Brand: nền `#081120`, chữ trắng, font Be Vietnam Pro đã kiểm glyph tiếng Việt (G0.8).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.domain.authoring.visuals import Shot, ShotKind, VisualPlan
from src.domain.production.value_objects import PORTRAIT_9_16, AspectRatio
from src.infrastructure.media import ffmpeg
from src.shared.logging import get_logger

log = get_logger(__name__)

WIDTH, HEIGHT = 1080, 1920
BRAND_BG = "0x081120"
BRAND_ACCENT = "0x15AABF"
BRAND_TEXT = "white"
FPS = 30


class ComposeFailed(RuntimeError):
    retryable = False


@dataclass(frozen=True, slots=True)
class ComposeRequest:
    plan: VisualPlan
    voice_audio: Path
    subtitle_cues: list[tuple[float, float, str]]
    work_dir: Path
    output: Path
    media_root: Path
    music_bed: Path | None = None
    font_name: str = "Be Vietnam Pro"
    font_file: Path | None = None
    output_aspect: AspectRatio | None = PORTRAIT_9_16


def _escape_text(value: str) -> str:
    """Escape cho drawtext: dấu hai chấm, nháy đơn, gạch chéo và phần trăm."""
    out = value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return out.replace("%", "\\%").replace(",", "\\,")


def _wrap(text: str, width: int = 22) -> str:
    """Xuống dòng thủ công: drawtext không tự ngắt dòng."""
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width and current:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "\n".join(lines[:6])


class FfmpegComposer:
    """Kịch bản hình → một file mp4 9:16 có giọng và phụ đề."""

    def compose(self, req: ComposeRequest) -> Path:
        req.work_dir.mkdir(parents=True, exist_ok=True)
        req.output.parent.mkdir(parents=True, exist_ok=True)

        voice_sec = ffmpeg.probe(req.voice_audio).duration_sec
        if voice_sec <= 0:
            raise ComposeFailed("file giọng đọc rỗng — không có gì để dựng hình theo")
        # Giọng quyết định độ dài, hình phủ theo. Ngược lại thì cảnh cuối cắt giữa câu.
        plan = req.plan.fitted_to(voice_sec)

        clips = [
            self._render_shot(shot, index, req)
            for index, shot in enumerate(plan.shots)
        ]
        silent = self._concat(clips, req.work_dir / "visual.mp4")
        with_audio = ffmpeg.mux(silent, req.voice_audio, req.work_dir / "muxed.mp4")

        ass_path = req.work_dir / "subs.ass"
        ass_path.write_text(
            ffmpeg.build_ass(list(req.subtitle_cues), font_name=req.font_name),
            encoding="utf-8",
        )
        subbed = ffmpeg.burn_subtitles(
            with_audio, ass_path, req.work_dir / "subbed.mp4", strict_glyphs=True
        )
        final = ffmpeg.normalize_loudness(subbed, req.output)
        log.info(
            "compose.done",
            output=str(final),
            shots=len(plan.shots),
            sec=voice_sec,
            aspect=str(req.output_aspect or PORTRAIT_9_16),
        )
        return final

    @staticmethod
    def _size(req: ComposeRequest) -> tuple[int, int]:
        ratio = req.output_aspect or PORTRAIT_9_16
        return (1920, 1080) if str(ratio) == "16:9" else (WIDTH, HEIGHT)

    # ---------------- Từng cảnh ----------------

    def _render_shot(self, shot: Shot, index: int, req: ComposeRequest) -> Path:
        dest = req.work_dir / f"shot-{index:02d}.mp4"
        if shot.kind in (ShotKind.UPLOAD, ShotKind.STOCK, ShotKind.GENERATED) and shot.asset:
            return self._from_asset(shot, req.media_root / shot.asset, dest, req)
        if shot.kind is ShotKind.CHART:
            return self._chart(shot, dest, req)
        return self._brand_card(shot, dest, req)

    def _drawtext(
        self, req: ComposeRequest, text: str, *, y: str, size: int, color: str = BRAND_TEXT
    ) -> str:
        font = (
            f"fontfile='{req.font_file.as_posix()}'"
            if req.font_file
            else f"font='{req.font_name}'"
        )
        return (
            f"drawtext={font}:text='{_escape_text(text)}':fontcolor={color}:fontsize={size}"
            f":x=(w-text_w)/2:y={y}:line_spacing=12:borderw=0"
        )

    def _from_asset(self, shot: Shot, path: Path, dest: Path, req: ComposeRequest) -> Path:
        """Ảnh hoặc video người dùng đưa vào → khung 9:16, nền mờ, không cắt hình.

        Cùng lý lẽ với D9 của Giai đoạn 1: video công nghiệp thì toàn khung mang
        thông tin, cắt là mất dữ kiện. Nền mờ giữ nguyên hình gốc.
        """
        if not path.exists():
            log.warning("compose.asset.missing", path=str(path))
            return self._brand_card(shot, dest, req)
        info = ffmpeg.probe(path)
        is_image = not info.has_video or info.duration_sec <= 0
        width, height = self._size(req)
        chain = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=40:2,setsar=1[bg];"
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p"
        )
        if shot.caption:
            chain += "," + self._drawtext(req, _wrap(shot.caption), y="h*0.80", size=52)
        args = ["-y"]
        if is_image:
            args += ["-loop", "1", "-t", f"{shot.seconds:.2f}", "-i", str(path)]
        else:
            args += ["-stream_loop", "-1", "-t", f"{shot.seconds:.2f}", "-i", str(path)]
        args += ["-filter_complex", chain, "-an", "-r", str(FPS)]
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dest)]
        ffmpeg.run(args)
        return dest

    def _brand_card(self, shot: Shot, dest: Path, req: ComposeRequest) -> Path:
        """Thẻ nền thương hiệu + chữ. Không có hình thật thì **không giả vờ có**."""
        chain = "[0:v]format=yuv420p"
        caption = shot.caption or ""
        if caption:
            chain += "," + self._drawtext(req, _wrap(caption, 18), y="(h-text_h)/2", size=76)
        chain += (
            f",drawbox=x=(w-360)/2:y=h*0.72:w=360:h=6:color={BRAND_ACCENT}@1:t=fill"
        )
        width, height = self._size(req)
        ffmpeg.run(
            [
                "-y", "-f", "lavfi",
                "-i", f"color=c={BRAND_BG}:s={width}x{height}:r={FPS}:d={shot.seconds:.2f}",
                "-filter_complex", chain, "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dest),
            ]
        )
        return dest

    def _chart(self, shot: Shot, dest: Path, req: ComposeRequest) -> Path:
        """Biểu đồ cột dựng từ **số liệu thật** người dùng nhập.

        Vẽ bằng ``drawbox``/``drawtext`` chứ không nhờ model sinh ảnh biểu đồ: một
        biểu đồ do AI vẽ trông rất thuyết phục và hoàn toàn bịa, còn ở đây mỗi cột
        cao đúng theo con số được đưa vào.
        """
        data = list(shot.data)
        top = max(value for _, value in data) or 1.0
        count = len(data)
        width, height = self._size(req)
        margin, base_y, chart_h = 110, int(height * 0.62), int(height * 0.34)
        slot = (width - 2 * margin) / count
        bar_w = int(slot * 0.55)

        chain = "[0:v]format=yuv420p"
        caption = _wrap(shot.caption or "Số liệu", 20)
        chain += "," + self._drawtext(req, caption, y="h*0.10", size=64)
        for index, (label, value) in enumerate(data):
            height = max(6, int(chart_h * (value / top)))
            x = int(margin + slot * index + (slot - bar_w) / 2)
            y = base_y - height
            chain += (
                f",drawbox=x={x}:y={y}:w={bar_w}:h={height}:color={BRAND_ACCENT}@1:t=fill"
            )
            chain += (
                f",drawtext=text='{_escape_text(f'{value:g}')}':fontcolor=white:fontsize=40"
                f":x={x}+{bar_w}/2-text_w/2:y={y - 56}"
            )
            chain += (
                f",drawtext=text='{_escape_text(label[:14])}':fontcolor=white@0.75:fontsize=36"
                f":x={x}+{bar_w}/2-text_w/2:y={base_y + 24}"
            )
        chain += f",drawbox=x={margin}:y={base_y}:w={width - 2 * margin}:h=4:color=white@0.5:t=fill"

        ffmpeg.run(
            [
                "-y", "-f", "lavfi",
                "-i", f"color=c={BRAND_BG}:s={width}x{height}:r={FPS}:d={shot.seconds:.2f}",
                "-filter_complex", chain, "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dest),
            ]
        )
        return dest

    def _concat(self, clips: list[Path], dest: Path) -> Path:
        if not clips:
            raise ComposeFailed("không có cảnh nào để nối")
        listing = dest.with_suffix(".txt")
        listing.write_text(
            "\n".join(f"file '{clip.as_posix()}'" for clip in clips), encoding="utf-8"
        )
        try:
            ffmpeg.run(
                ["-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
                 "-pix_fmt", "yuv420p", str(dest)]
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - ffmpeg thật
            raise ComposeFailed(f"nối cảnh thất bại: {exc}") from exc
        return dest
