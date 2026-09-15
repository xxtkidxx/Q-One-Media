"""Tầng media chạy với ffmpeg thật.

Tự bỏ qua nếu không có ffmpeg, nên cùng một file chạy được trong container dev
(có ffmpeg) và bỏ qua ở nơi không có — không cần marker riêng.

Video dùng để test được sinh bằng `lavfi` ngay trong test: không cần fixture
nhị phân trong repo, và mỗi lần chạy là một điều kiện đã biết chính xác.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.infrastructure.media import ffmpeg
from src.infrastructure.media.ffmpeg import (
    VIETNAMESE_GLYPH_PROBE,
    GlyphMissing,
    build_ass,
)
from src.infrastructure.media.reframe import reframe

pytestmark = pytest.mark.integration

FFMPEG_MISSING = shutil.which("ffmpeg") is None
skip_no_ffmpeg = pytest.mark.skipif(FFMPEG_MISSING, reason="không có ffmpeg ở môi trường này")


@pytest.fixture(scope="module")
def landscape_video(tmp_path_factory) -> Path:
    """Video 16:9, 6 giây, có tiếng — giả lập nguồn công nghiệp."""
    if FFMPEG_MISSING:
        pytest.skip("không có ffmpeg")
    out = tmp_path_factory.mktemp("media") / "source_16x9.mp4"
    ffmpeg.run(
        [
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=6",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out),
        ]
    )
    return out


@pytest.fixture(scope="module")
def portrait_video(tmp_path_factory) -> Path:
    if FFMPEG_MISSING:
        pytest.skip("không có ffmpeg")
    out = tmp_path_factory.mktemp("media") / "source_9x16.mp4"
    ffmpeg.run(
        [
            "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=25:duration=3",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(out),
        ]
    )
    return out


# ---------------- probe ----------------


@skip_no_ffmpeg
def test_probe_doc_dung_kich_thuoc_va_do_dai(landscape_video):
    info = ffmpeg.probe(landscape_video)
    assert (info.width, info.height) == (1280, 720)
    assert info.duration_sec == pytest.approx(6.0, abs=0.3)
    assert info.has_audio is True
    assert info.has_video is True
    assert info.aspect == pytest.approx(16 / 9, abs=0.01)


@skip_no_ffmpeg
def test_probe_nhan_ra_video_khong_co_tieng(portrait_video):
    assert ffmpeg.probe(portrait_video).has_audio is False


@skip_no_ffmpeg
def test_probe_file_khong_ton_tai_thi_bao_loi_khong_retry(tmp_path):
    with pytest.raises(ffmpeg.FfmpegFailed) as exc:
        ffmpeg.probe(tmp_path / "khong-co.mp4")
    assert exc.value.retryable is False


# ---------------- cắt đoạn ----------------


@skip_no_ffmpeg
def test_cat_doan_dung_diem_khong_lech_theo_keyframe(landscape_video, tmp_path):
    """Lý do re-encode chứ không ``-c copy``: copy chỉ cắt ở keyframe.

    Với short video 45–75s thì lệch vài giây là phá luôn đoạn đã chọn.
    """
    out = ffmpeg.cut(landscape_video, tmp_path / "cut.mp4", start_sec=1.5, end_sec=4.0)
    assert ffmpeg.probe(out).duration_sec == pytest.approx(2.5, abs=0.2)


@skip_no_ffmpeg
def test_rut_audio_mono_16k(landscape_video, tmp_path):
    out = ffmpeg.extract_audio(landscape_video, tmp_path / "audio.wav")
    info = ffmpeg.probe(out)
    assert info.has_audio and not info.has_video
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels", "-of", "csv=p=0", str(out)],
        capture_output=True, check=False, text=True,
    )
    assert probe.stdout.strip().startswith("16000,1")


# ---------------- Phụ đề: bẫy glyph F2.2 ----------------


@skip_no_ffmpeg
def test_burn_phu_de_tieng_viet_voi_font_co_du_glyph(portrait_video, tmp_path):
    """DejaVu Sans phủ dải U+1Exx — đây là ca ĐẠT."""
    ass = tmp_path / "sub.ass"
    ass.write_text(
        build_ass([(0.0, 2.0, "Cpk chỉ nói về độ lệch trong nhóm mẫu")],
                  font_name="DejaVu Sans"),
        encoding="utf-8",
    )
    out = ffmpeg.burn_subtitles(portrait_video, ass, tmp_path / "subbed.mp4")
    assert out.exists() and out.stat().st_size > 0
    assert ffmpeg.probe(out).height == 1920


@skip_no_ffmpeg
def test_font_khong_ton_tai_thi_bao_thieu_glyph_chu_khong_im_lang(portrait_video, tmp_path):
    """Đây là điểm cốt lõi của F2.2.

    Mặc định libass chỉ **cảnh báo** rồi âm thầm thay font khác: video render
    thành công, không mã lỗi, nhưng chữ tiếng Việt sai font — và không ai phát
    hiện tới khi video đã lên sóng. ``strict_glyphs=True`` biến nó thành lỗi.
    """
    ass = tmp_path / "sub.ass"
    ass.write_text(
        build_ass([(0.0, 2.0, VIETNAMESE_GLYPH_PROBE)], font_name="Font Khong Ton Tai 12345"),
        encoding="utf-8",
    )
    with pytest.raises(GlyphMissing):
        ffmpeg.burn_subtitles(portrait_video, ass, tmp_path / "bad.mp4", strict_glyphs=True)

    # Tắt strict thì vẫn render ra file — chứng minh mặc định của libass là im lặng
    out = ffmpeg.burn_subtitles(
        portrait_video, ass, tmp_path / "silent.mp4", strict_glyphs=False
    )
    assert out.exists()


@skip_no_ffmpeg
def test_kiem_font_phu_tieng_viet():
    """Bản tự động của G0.8. Không thay việc soi mắt, nhưng bắt được ca tệ nhất."""
    assert ffmpeg.check_font_covers_vietnamese("DejaVu Sans") == []
    assert ffmpeg.check_font_covers_vietnamese("Font Khong Ton Tai 12345") != []


# ---------------- Chuẩn hoá độ to ----------------


@skip_no_ffmpeg
def test_loudnorm_chay_va_giu_hinh(landscape_video, tmp_path):
    out = ffmpeg.normalize_loudness(landscape_video, tmp_path / "norm.mp4")
    info = ffmpeg.probe(out)
    assert info.has_video and info.has_audio
    assert (info.width, info.height) == (1280, 720)


# ---------------- Đổi khung hình ----------------


@skip_no_ffmpeg
def test_reframe_blur_dua_16_9_ve_9_16_khong_cat_hinh(landscape_video, tmp_path):
    """Chế độ ``blur`` giữ nguyên toàn bộ khung gốc, chỉ thêm nền mờ hai đầu.

    Đúng thứ cần cho video công nghiệp: toàn khung mang thông tin (F2.6).
    """
    out = reframe(landscape_video, tmp_path / "vertical.mp4", ratio="9:16")
    info = ffmpeg.probe(out)
    assert info.aspect == pytest.approx(9 / 16, abs=0.01)
    assert info.duration_sec == pytest.approx(6.0, abs=0.4)


# ---------------- Toàn chuỗi render ----------------


@skip_no_ffmpeg
def test_render_toan_chuoi_ra_video_doc_co_phu_de(landscape_video, tmp_path):
    """Cắt → reframe blur → trộn audio → burn phụ đề → loudnorm, bằng ffmpeg thật."""
    from src.infrastructure.media.renderer import FfmpegRenderer, RenderRequest

    voice = tmp_path / "voice.wav"
    bg = tmp_path / "bg.wav"
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=2", str(voice)])
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=90:duration=6", str(bg)])

    out = FfmpegRenderer().render(
        RenderRequest(
            source_video=landscape_video,
            voice_audio=voice,
            background_audio=bg,
            subtitle_cues=[
                (0.0, 2.0, "Cpk thấp vì máy trôi."),
                (2.0, 3.8, "Không phải vì dung sai."),
            ],
            start_sec=1.0,
            end_sec=5.0,
            work_dir=tmp_path / "work",
            output=tmp_path / "final.mp4",
            attribution_text="Nguồn: Vendor GmbH (CC BY 4.0)",
            font_name="DejaVu Sans",
        )
    )

    info = ffmpeg.probe(out)
    assert info.aspect == pytest.approx(9 / 16, abs=0.01)
    assert info.has_audio and info.has_video
    assert info.duration_sec == pytest.approx(4.0, abs=0.4)
    assert out.stat().st_size > 0


@skip_no_ffmpeg
def test_render_bo_qua_reframe_khi_nguon_da_doc(portrait_video, tmp_path):
    """Tiết kiệm một lần encode và tránh giảm chất lượng vô ích (G2.12)."""
    from src.domain.production.value_objects import AspectRatio
    from src.infrastructure.media.renderer import FfmpegRenderer, RenderRequest

    voice = tmp_path / "voice.wav"
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=2", str(voice)])

    out = FfmpegRenderer().render(
        RenderRequest(
            source_video=portrait_video,
            voice_audio=voice,
            background_audio=None,  # không có nền dùng được
            subtitle_cues=[(0.0, 1.5, "Đã dọc sẵn")],
            start_sec=0.0,
            end_sec=2.0,
            work_dir=tmp_path / "w2",
            output=tmp_path / "final2.mp4",
            source_aspect=AspectRatio(1080, 1920),
            font_name="DejaVu Sans",
        )
    )
    assert not (tmp_path / "w2" / "framed.mp4").exists()  # không hề reframe
    assert ffmpeg.probe(out).aspect == pytest.approx(9 / 16, abs=0.01)


@skip_no_ffmpeg
def test_render_dung_lai_khi_font_thieu_dau_tieng_viet(portrait_video, tmp_path):
    """Không để video render xong với chữ sai font (F2.2)."""
    from src.infrastructure.media.renderer import FfmpegRenderer, RenderRequest

    voice = tmp_path / "v.wav"
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=2", str(voice)])

    with pytest.raises(GlyphMissing):
        FfmpegRenderer().render(
            RenderRequest(
                source_video=portrait_video,
                voice_audio=voice,
                background_audio=None,
                subtitle_cues=[(0.0, 1.5, VIETNAMESE_GLYPH_PROBE)],
                start_sec=0.0,
                end_sec=2.0,
                work_dir=tmp_path / "w3",
                output=tmp_path / "final3.mp4",
                font_name="Font Khong Ton Tai 999",
            )
        )


@skip_no_ffmpeg
def test_studio_compose_ton_trong_lua_chon_ngang_16_9(tmp_path):
    from src.domain.authoring.visuals import Shot, ShotKind, VisualPlan
    from src.domain.production.value_objects import AspectRatio
    from src.infrastructure.media.compose import ComposeRequest, FfmpegComposer

    voice = tmp_path / "voice.wav"
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=2", str(voice)])
    output = FfmpegComposer().compose(
        ComposeRequest(
            plan=VisualPlan((Shot(kind=ShotKind.BRAND_CARD, seconds=2, caption="NMIT"),)),
            voice_audio=voice,
            subtitle_cues=[],
            work_dir=tmp_path / "compose-16x9",
            output=tmp_path / "studio-16x9.mp4",
            media_root=tmp_path,
            output_aspect=AspectRatio(16, 9),
            font_name="DejaVu Sans",
        )
    )
    info = ffmpeg.probe(output)
    assert (info.width, info.height) == (1920, 1080)
