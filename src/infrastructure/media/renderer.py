"""Dựng video thành phẩm: cắt → reframe → trộn audio → burn phụ đề.

Chuỗi ffmpeg sống ở đây, không ở tầng application, vì thứ tự các bước là quyết
định **kỹ thuật** (cái nào re-encode, cái nào copy được) chứ không phải quyết định
nghiệp vụ. Tầng application chỉ cần biết "dựng xong, file ở đây".

Thứ tự có lý do, và đổi thứ tự là tự tạo lỗi:

1. **Cắt trước** — mọi bước sau chỉ làm trên đoạn đã chọn, không làm trên cả video
   gốc dài 10 phút.
2. **Reframe trước khi burn phụ đề** — burn trước thì chữ bị kéo giãn theo khung
   mới hoặc rơi vào vùng nền mờ.
3. **Trộn audio song song với xử lý hình** rồi mux — hai nhánh không phụ thuộc nhau.
4. **Burn phụ đề cuối cùng** — sau bước này khung hình đã cố định, và libass chỉ
   nói đúng về font khi kích thước đã là kích thước thật.
5. **loudnorm cuối** — chuẩn hoá trên audio đã trộn xong, không phải trên từng stem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.domain.production.value_objects import PORTRAIT_9_16, AspectRatio, ReframeMode
from src.infrastructure.media import ffmpeg
from src.infrastructure.media.reframe import reframe as reframe_video
from src.shared.logging import get_logger

log = get_logger(__name__)

# Thẻ ghi nguồn hiện ở đầu video. Là nghĩa vụ license với CC BY, và là cách giữ
# credit gốc mà quy tắc nghiệp vụ yêu cầu.
CREDIT_CARD_SEC = 2.5


@dataclass(frozen=True, slots=True)
class RenderRequest:
    source_video: Path
    voice_audio: Path
    background_audio: Path | None
    subtitle_cues: list[tuple[float, float, str]]
    start_sec: float
    end_sec: float
    work_dir: Path
    output: Path
    source_aspect: AspectRatio | None = None
    output_aspect: AspectRatio | None = PORTRAIT_9_16
    attribution_text: str | None = None
    font_name: str = "Be Vietnam Pro"
    fonts_dir: Path | None = None


class RenderFailed(RuntimeError):
    retryable = False


class FfmpegRenderer:
    """Hiện thực cụ thể. Chỉ dùng ffmpeg."""

    def render(self, req: RenderRequest) -> Path:
        req.work_dir.mkdir(parents=True, exist_ok=True)
        req.output.parent.mkdir(parents=True, exist_ok=True)

        # 1. Cắt đoạn đã chọn
        clip = ffmpeg.cut(
            req.source_video,
            req.work_dir / "clip.mp4",
            start_sec=req.start_sec,
            end_sec=req.end_sec,
        )

        # 2. Reframe CÓ ĐIỀU KIỆN — nguồn đã 9:16 thì bỏ qua, tiết kiệm một lần
        #    encode và tránh giảm chất lượng vô ích.
        aspect = req.source_aspect or self._probe_aspect(clip)
        target = req.output_aspect
        if target is None or (aspect is not None and not aspect.needs_reframe_to(target)):
            log.info("render.reframe.skipped", aspect=str(aspect))
            framed = clip
        else:
            framed = reframe_video(
                clip, req.work_dir / "framed.mp4", ratio=str(target), mode=ReframeMode.BLUR
            )

        # 3. Trộn audio: giọng Việt lên nền tiếng máy
        target_sec = req.end_sec - req.start_sec
        if req.background_audio is not None and req.background_audio.exists():
            mixed_audio = ffmpeg.mix_voice_over_background(
                req.voice_audio,
                req.background_audio,
                req.work_dir / "mixed.wav",
                target_sec=target_sec,
                background_start_sec=req.start_sec,
            )
        else:
            # Nguồn không có nền dùng được (video im lặng, hoặc Demucs không tách
            # ra gì). Dùng giọng trần — nói rõ trong log vì video sẽ nghe khô hơn.
            log.warning("render.background.missing", reason="dùng giọng trần")
            mixed_audio = ffmpeg.pad_audio(
                req.voice_audio, req.work_dir / "voice-padded.wav", target_sec=target_sec
            )

        # 4. Ghép hình đã reframe với audio đã trộn
        muxed = ffmpeg.mux(framed, mixed_audio, req.work_dir / "muxed.mp4")

        # 5. Burn phụ đề ASS — strict glyph: font thiếu dấu tiếng Việt thì DỪNG,
        #    không để video render xong với chữ sai font (F2.2)
        cues = list(req.subtitle_cues)
        if req.attribution_text:
            # Thẻ ghi nguồn đặt ở đầu, đẩy các cue khác ra sau nó
            cues = [(0.0, CREDIT_CARD_SEC, req.attribution_text)] + [
                (s + CREDIT_CARD_SEC, e + CREDIT_CARD_SEC, t) for s, e, t in cues
            ]
        ass_path = req.work_dir / "subs.ass"
        ass_path.write_text(
            ffmpeg.build_ass(cues, font_name=req.font_name), encoding="utf-8"
        )
        subbed = ffmpeg.burn_subtitles(
            muxed,
            ass_path,
            req.work_dir / "subbed.mp4",
            fonts_dir=req.fonts_dir,
            strict_glyphs=True,
        )

        # 6. Chuẩn hoá độ to trên audio đã trộn xong
        final = ffmpeg.normalize_loudness(subbed, req.output)
        log.info("render.done", output=str(final), bytes=final.stat().st_size)
        return final

    @staticmethod
    def _probe_aspect(path: Path) -> AspectRatio | None:
        info = ffmpeg.probe(path)
        if not info.width or not info.height:
            return None
        return AspectRatio.from_size(info.width, info.height)
