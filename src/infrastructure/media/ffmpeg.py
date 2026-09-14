"""Lớp bọc ``ffmpeg`` / ``ffprobe``.

Gọi qua ``subprocess`` thay vì dùng thư viện Python bọc ffmpeg, vì filtergraph
phức tạp thì cú pháp ffmpeg gốc là thứ duy nhất có tài liệu và tra được. Đổi lại
phải tự xử lý lỗi — làm ở đây một lần, phân loại rõ retry được hay không.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.shared.logging import get_logger

log = get_logger(__name__)

# Mốc phổ biến cho nền tảng xã hội. Đặc tả ghi rõ đây là số [chưa xác minh] —
# kiểm tài liệu từng nền tảng trước khi coi là chuẩn.
TARGET_LUFS = -14.0
TARGET_TRUE_PEAK = -1.5

# Chuỗi đủ dấu tiếng Việt để test glyph (đặc tả F2.2). Nhiều font thiếu dải U+1Exx.
# Cách libass báo lỗi đã được kiểm bằng thực nghiệm — xem find_font_problems():
# thiếu font thì nó KHÔNG báo "Glyph not found", chỉ ghi một dòng fontselect ở
# mức info rồi âm thầm thay font khác.
VIETNAMESE_GLYPH_PROBE = (
    "ẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ"
    "ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
    "đĐăĂâÂêÊôÔơƠưƯ"
)


class FfmpegNotFound(RuntimeError):
    retryable = False


class FfmpegFailed(RuntimeError):
    """ffmpeg trả mã lỗi. Gần như luôn là input sai hoặc filtergraph sai."""

    retryable = False

    def __init__(self, cmd: list[str], stderr: str) -> None:
        self.cmd = cmd
        self.stderr = stderr
        # Giữ đuôi stderr: ffmpeg in lỗi thật ở cuối, phần đầu là banner phiên bản
        tail = "\n".join(stderr.strip().splitlines()[-12:])
        super().__init__(f"ffmpeg thất bại:\n{tail}")


class GlyphMissing(RuntimeError):
    """Font thiếu glyph tiếng Việt. Không retry — phải đổi font."""

    retryable = False


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise FfmpegNotFound(
            f"không tìm thấy {binary} — chạy trong container worker, không chạy trên host"
        )
    return path


def run(args: list[str], *, capture_stderr: bool = True) -> str:
    """Chạy ffmpeg. Trả về stderr (nơi ffmpeg in mọi thông tin, kể cả khi thành công)."""
    cmd = [_require("ffmpeg"), "-hide_banner", "-nostdin", "-y", *args]
    proc = subprocess.run(
        cmd,
        capture_output=capture_stderr,
        check=False,  # tự kiểm returncode để phân loại lỗi
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise FfmpegFailed(cmd, proc.stderr or "")
    return proc.stderr or ""


@dataclass(frozen=True, slots=True)
class MediaInfo:
    duration_sec: float
    width: int | None
    height: int | None
    has_audio: bool
    has_video: bool

    @property
    def aspect(self) -> float | None:
        if not self.width or not self.height:
            return None
        return self.width / self.height


def probe(path: Path) -> MediaInfo:
    cmd = [
        _require("ffprobe"),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(
        cmd, capture_output=True, check=False, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode != 0:
        raise FfmpegFailed(cmd, proc.stderr or "")
    data = json.loads(proc.stdout)

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(data.get("format", {}).get("duration") or 0.0)
    if duration == 0.0 and video is not None:
        duration = float(video.get("duration") or 0.0)

    return MediaInfo(
        duration_sec=duration,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
        has_audio=audio is not None,
        has_video=video is not None,
    )


def extract_audio(video: Path, dest: Path, *, sample_rate: int = 16000) -> Path:
    """Rút audio mono 16 kHz — đúng thứ Whisper và Demucs cần.

    16 kHz mono không phải để tiết kiệm chỗ: Whisper resample về đúng mức này ở
    bên trong, nên đưa sẵn thì bỏ được một lần chuyển đổi và kết quả giống nhau.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["-i", str(video), "-vn", "-ac", "1", "-ar", str(sample_rate), str(dest)])
    return dest


def cut(source: Path, dest: Path, *, start_sec: float, end_sec: float) -> Path:
    """Cắt một đoạn. Re-encode chứ không copy stream.

    ``-c copy`` chỉ cắt được ở keyframe nên điểm cắt lệch tới vài giây — với
    short video 45–75s thì lệch đó phá luôn đoạn đã chọn.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "-ss", f"{start_sec:.3f}",
            "-to", f"{end_sec:.3f}",
            "-i", str(source),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(dest),
        ]
    )
    return dest


def normalize_loudness(source: Path, dest: Path, *, lufs: float = TARGET_LUFS) -> Path:
    """Chuẩn hoá độ to. Bỏ bước này thì video to nhỏ thất thường giữa các bài."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "-i", str(source),
            "-af", f"loudnorm=I={lufs}:TP={TARGET_TRUE_PEAK}:LRA=11",
            "-c:v", "copy",
            str(dest),
        ]
    )
    return dest


def mux(video: Path, audio: Path, dest: Path) -> Path:
    """Ghép hình của file này với tiếng của file kia, lấy độ dài theo stream ngắn hơn."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "-i", str(video),
            "-i", str(audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(dest),
        ]
    )
    return dest


# Nền tiếng máy ở −20 dB: giữa khoảng −18…−22 dB của đặc tả F2.4.
BACKGROUND_DB = -20.0

# Sidechain ducking: nền tụt xuống khi có tiếng nói, trả lại khi ngừng. Ngưỡng và
# thời hằng lấy theo mặc định của Easel (đã nghe được với nội dung công nghiệp);
# `release` dài hơn `attack` nhiều lần là có ý — nền dâng lại nhanh quá thì nghe
# như đang "thở".
DUCK_THRESHOLD = 0.03
DUCK_RATIO = 8
DUCK_ATTACK_MS = 20
DUCK_RELEASE_MS = 300

# Chốt định dạng giữa chừng filtergraph. Đây **không** phải dòng thừa: `aresample`
# đổi được tần số nhưng không chốt channel layout, và `sidechaincompress` của
# ffmpeg 4.4 không tự thương lượng được format qua `asplit` — nó đổ bằng
# "No channel layout for input 1" / "could not choose their formats" rồi hỏng cả
# lần chạy. Đã dựng lại lỗi này với mọi tổ hợp đầu vào (mono/stereo, wav/flac,
# layout khai báo đầy đủ) — chỉ `aformat` ngay trước sidechain mới chữa được, nên
# nguyên nhân nằm ở graph chứ không nằm ở file.
_AFORMAT = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"

# Nền tắt dần ở cuối để không bị cắt cụt. Trần 1,5 s, và không dài quá 1/4 video
# vì với clip ngắn thì fade dài nghe như lỗi.
_FADE_MAX_SEC = 1.5


def mix_voice_over_background(
    voice: Path,
    background: Path,
    dest: Path,
    *,
    background_db: float = BACKGROUND_DB,
    voice_db: float = 0.0,
    duck: bool = True,
) -> Path:
    """Lồng giọng Việt lên nền tiếng máy, có sidechain ducking.

    ``background`` là stem **không phải giọng** do Demucs tách ra — tiếng máy chạy,
    tiếng bíp HMI. Giữ lại vì âm thanh đó *mang thông tin* và làm video đáng tin với
    khán giả kỹ thuật; xoá sạch thì video nghe như slideshow (F2.4).

    Độ dài đầu ra theo ``voice`` — đúng thứ cần, vì giọng Việt là trục thời gian của
    video thành phẩm.

    Graph ở đây viết lại từ ``skills/shared/scripts/audio_mix.py`` của **Easel**
    (Apache-2.0 — xem ``THIRD_PARTY_NOTICES.md``), **có sửa một lỗi**: bản gốc thiếu
    ``aformat`` trước ``sidechaincompress`` nên đổ ngay khi bật ducking với đầu vào
    của dự án này (giọng mono 24 kHz từ TTS + nền stereo 44,1 kHz từ Demucs). Hai
    khác biệt nữa so với bản gốc:

    * âm lượng nhận thẳng **dB** (``volume=-20dB``) thay vì hệ số tuyến tính — bản
      gốc nhận hệ số, và mặc định ``0.25`` của nó ≈ −12 dB, to hơn mức F2.4 yêu cầu
      khoảng 10 dB. Nhận dB thì không còn chỗ cho nhầm đơn vị;
    * độ dài lấy theo giọng bằng ``duration=first``, không phải tự tính rồi ``-t``.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    voice_len = probe(voice).duration_sec
    fade = min(_FADE_MAX_SEC, voice_len / 4) if voice_len > 0 else 0.0

    # Giọng: chốt format NGAY, vì nhánh này vừa đi ra bản trộn vừa làm tín hiệu
    # điều khiển sidechain — hai nhánh phải cùng định dạng.
    graph = [
        f"[0:a]volume={voice_db}dB,aresample=44100,{_AFORMAT}[voice]",
        f"[1:a]volume={background_db}dB,aresample=44100,{_AFORMAT}[bg0]",
    ]
    if duck:
        graph += [
            "[voice]asplit=2[voice_out][voice_sc]",
            f"[bg0][voice_sc]sidechaincompress=threshold={DUCK_THRESHOLD}"
            f":ratio={DUCK_RATIO}:attack={DUCK_ATTACK_MS}:release={DUCK_RELEASE_MS}[bg]",
        ]
        voice_label = "[voice_out]"
    else:
        graph.append("[bg0]anull[bg]")
        voice_label = "[voice]"

    # duration=first: đầu vào đầu tiên là giọng, nên nền bị cắt theo giọng chứ không
    # kéo dài video ra. normalize=0: amix mặc định chia đều biên độ cho số nhánh, tức
    # tự ý hạ giọng 6 dB — mà mức của hai nhánh đã đặt bằng dB ở trên rồi.
    graph.append(
        f"{voice_label}[bg]amix=inputs=2:duration=first:normalize=0"
        ":dropout_transition=0[mixed]"
    )
    if fade > 0:
        graph.append(
            f"[mixed]afade=t=out:st={max(0.0, voice_len - fade):.3f}:d={fade:.3f}[out]"
        )
    else:
        graph.append("[mixed]anull[out]")

    log.info(
        "ffmpeg.mix",
        voice_sec=round(voice_len, 2),
        background_db=background_db,
        duck=duck,
    )
    run(
        [
            "-i", str(voice),
            "-i", str(background),
            "-filter_complex", ";".join(graph),
            "-map", "[out]",
            "-c:a", "pcm_s16le",
            str(dest),
        ]
    )
    return dest


def _escape_filter_path(path: Path) -> str:
    """``:`` và ``\\`` là ký tự cú pháp của filtergraph, phải escape."""
    return str(path).replace("\\", "/").replace(":", r"\:")


def _ass_filter(ass_file: Path, fonts_dir: Path | None) -> str:
    vf = f"ass='{_escape_filter_path(ass_file)}'"
    if fonts_dir is not None:
        vf += f":fontsdir='{_escape_filter_path(fonts_dir)}'"
    return vf


# libass ghi dòng này ở mức info mỗi khi nó chọn font. Dạng thật:
#   fontselect: (Be Vietnam Pro, 700, 0) -> /p/BeVietnamPro-Bold.ttf, 0, BeVietnamPro-Bold
_FONTSELECT_RE = re.compile(
    r"fontselect:\s*\((?P<want>[^,]+),\s*\d+,\s*\d+\)"
    r"\s*->\s*(?P<path>[^,]+),\s*\d+,\s*(?P<got>.+?)\s*$"
)


def _norm_family(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_font_problems(stderr: str) -> list[str]:
    """Bóc hai loại sự cố font từ stderr của libass.

    Chạy thật mới biết libass hành xử **khác** điều thường được nói:

    1. **Thiếu font** không hề sinh ``Glyph not found``. Nó chỉ ghi một dòng
       ``fontselect: (Font X, ...) -> /path/DejaVuSans-Bold.ttf`` ở mức *info*
       rồi lặng lẽ thay font. ffmpeg trả mã 0, video render xong, chữ sai kiểu —
       đúng chế độ thất bại mà đặc tả F2.2 cảnh báo, nhưng dấu hiệu nằm ở dòng
       ``fontselect``, không phải ở cảnh báo glyph.
    2. ``Glyph not found`` chỉ xuất hiện khi font **đã chọn được** lại thiếu đúng
       ký tự cần — ví dụ font Latin cơ bản gặp dải U+1Exx của tiếng Việt.

    Vì vậy phải soi cả hai. Bỏ (1) thì mọi lần đặt sai tên font đều đi qua im lặng.
    """
    problems: list[str] = []
    for line in stderr.splitlines():
        if "Glyph" in line and "not found" in line:
            problems.append(f"thiếu glyph: {line.strip()}")
            continue
        m = _FONTSELECT_RE.search(line)
        if m is None:
            continue
        want, got = m.group("want").strip(), m.group("got").strip()
        if not _norm_family(got).startswith(_norm_family(want)):
            problems.append(
                f"font bị thay: yêu cầu {want!r} nhưng libass dùng {got!r} "
                f"({m.group('path').strip()})"
            )
    return problems


def burn_subtitles(
    video: Path,
    ass_file: Path,
    dest: Path,
    *,
    fonts_dir: Path | None = None,
    strict_glyphs: bool = True,
) -> Path:
    """Burn phụ đề ASS vào hình.

    ``strict_glyphs=True`` biến sự cố font của libass thành lỗi — xem
    ``find_font_problems`` để biết vì sao cần kiểm hai loại dấu hiệu, không chỉ một.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    stderr = run(
        [
            # Bắt buộc: dòng fontselect của libass chỉ hiện ở mức info. Quiet hơn
            # là mất luôn khả năng phát hiện font bị thay.
            "-loglevel", "info",
            "-i", str(video),
            "-vf", _ass_filter(ass_file, fonts_dir),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(dest),
        ]
    )
    problems = find_font_problems(stderr)
    if problems and strict_glyphs:
        raise GlyphMissing(
            "Phụ đề có sự cố font — đổi font (Be Vietnam Pro / Inter / "
            "IBM Plex Sans) hoặc sửa tên font trong style rồi render lại.\n"
            + "\n".join(problems[:5])
        )
    if problems:
        log.warning("subtitle.font.problem", count=len(problems), sample=problems[:3])
    return dest


def check_font_covers_vietnamese(font_name: str, *, fonts_dir: Path | None = None) -> list[str]:
    """Render chuỗi đủ dấu rồi soi stderr. Trả về danh sách sự cố (rỗng = đạt).

    Đây là bản tự động của G0.8. **Không thay thế việc soi mắt**: libass có thể
    chọn được một font *có* glyph nhưng sai kiểu chữ so với brand, và chuyện đó
    chỉ mắt người thấy.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        ass = tmpdir / "probe.ass"
        ass.write_text(
            build_ass([(0.0, 3.0, VIETNAMESE_GLYPH_PROBE)], font_name=font_name, font_size=48),
            encoding="utf-8",
        )
        stderr = run(
            [
                "-loglevel", "info",
                "-f", "lavfi",
                "-i", "color=c=black:s=1080x1920:d=3",
                "-vf", _ass_filter(ass, fonts_dir),
                "-frames:v", "75",
                str(tmpdir / "probe.mp4"),
            ]
        )
    return find_font_problems(stderr)


# ---------------- ASS ----------------

# Brand NMI: navy #081120. ASS dùng &HBBGGRR (ngược thứ tự so với hex web).
ASS_PRIMARY = "&H00FFFFFF"  # chữ trắng
ASS_OUTLINE = "&H00201108"  # viền navy #081120 đảo byte
ASS_BACK = "&H80000000"     # bóng đen 50% alpha


def _ass_timestamp(seconds: float) -> str:
    """ASS dùng centisecond và giờ một chữ số: H:MM:SS.cc"""
    if seconds < 0:
        seconds = 0.0
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(
    cues: list[tuple[float, float, str]],
    *,
    font_name: str = "Be Vietnam Pro",
    font_size: int = 54,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    margin_v: int = 260,
) -> str:
    """Sinh file ASS từ danh sách (bắt đầu, kết thúc, chữ).

    ``margin_v`` lớn (260) có lý do cụ thể: giao diện của TikTok/Reels/Shorts che
    khoảng 15–20% đáy màn hình bằng caption, nút và tên kênh. Phụ đề đặt sát đáy
    theo mặc định sẽ bị chính app che mất.
    """
    header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{ASS_PRIMARY},{ASS_PRIMARY},{ASS_OUTLINE},{ASS_BACK},-1,0,0,0,100,100,0,0,1,4,2,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for start, end, text in cues:
        safe = text.replace("\n", r"\N").replace("{", "(").replace("}", ")").strip()
        if not safe:
            continue
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Default,,0,0,0,,{safe}"
        )
    return header + "\n".join(lines) + "\n"
