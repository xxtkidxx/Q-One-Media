"""Demucs, WhisperX và VoxCPM2 chạy với GPU và model thật.

Đánh dấu ``gpu`` nên ``make test`` và ``make test-int`` đều bỏ qua. Chạy bằng:

    make test-gpu

Nhóm test này tồn tại vì một ràng buộc cụ thể của máy đang dùng: **RTX 3070 có
8 GB VRAM**, mà WhisperX large-v3 float16 (~4,7 GB) + Demucs (~2 GB) + VoxCPM2
(~5 GB) **không thể cùng ở trên card**. Thiết kế chạy tuần tự và gọi
``_free_vram()`` sau mỗi model; nếu ai đó bỏ lệnh nhả VRAM đi thì test ở đây đỏ
bằng ``CUDA out of memory``, chứ không đỏ bằng một video xấu ba tuần sau.

Mỗi test in VRAM đỉnh để so được giữa các lần chạy.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.gpu]


def _torch():
    torch = pytest.importorskip("torch", reason="chỉ có trong image worker")
    if not torch.cuda.is_available():
        pytest.skip("không thấy CUDA — chạy trong container worker có GPU")
    return torch


@pytest.fixture(autouse=True)
def clean_vram():
    """Nhả VRAM trước và sau mỗi test, rồi báo mức đỉnh.

    Không có bước này thì một test rò VRAM sẽ làm test sau đỏ, và lỗi trông như
    của test sau.
    """
    torch = _torch()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    yield
    peak = torch.cuda.max_memory_allocated() / 1024**3
    free, total = torch.cuda.mem_get_info()
    print(
        f"\n    VRAM đỉnh {peak:.2f} GB · còn rảnh {free / 1024**3:.2f}/"
        f"{total / 1024**3:.1f} GB"
    )
    torch.cuda.empty_cache()


@pytest.fixture(scope="module")
def speech_audio(tmp_path_factory) -> Path:
    """Audio tiếng Việt thật để làm đầu vào — sinh bằng edge-tts.

    Dùng giọng thật chứ không dùng sine wave: Demucs và WhisperX xử lý tiếng nói
    khác hẳn xử lý âm thuần, nên test bằng sine chỉ chứng minh code chạy, không
    chứng minh nó làm đúng việc.
    """
    if shutil.which("ffmpeg") is None:
        pytest.skip("không có ffmpeg")
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
    from src.infrastructure.tts.edge import EdgeTtsSynthesizer

    now = datetime.now(UTC)
    source = Source(
        platform=Platform.WEB,
        kind=SourceKind.SINGLE_URL,
        url=SourceUrl("https://nmi.vn/test-gpu"),
        id=0,
    )
    source.approve(
        by="test",
        evidence=LicenseEvidence(license_type=LicenseType.OWN, evidence_ref="nội bộ"),
        scope=LicenseScope(may_translate=True, may_modify_audio=True, may_subtitle=True),
        at=now,
    )
    out = tmp_path_factory.mktemp("gpu") / "speech.wav"
    return EdgeTtsSynthesizer().synthesize(
        text=(
            "Biểu đồ kiểm soát cho thấy trung bình quá trình trôi dần theo ca. "
            "Cpk một phẩy ba ba vẫn có thể cho ra hàng lỗi."
        ),
        dest=out,
        clearance=source.clear_for_dubbing(now),
    )


# ---------------- Demucs ----------------


def test_demucs_tach_hai_stem_tren_gpu(speech_audio, tmp_path):
    """Bỏ stem giọng, giữ phần còn lại làm nền tiếng máy (F2.4)."""
    from src.infrastructure.asr.demucs import separate

    stems = separate(speech_audio, tmp_path / "stems")
    assert stems.vocals.exists() and stems.vocals.stat().st_size > 0
    assert stems.background.exists() and stems.background.stat().st_size > 0

    from src.infrastructure.media import ffmpeg

    src_len = ffmpeg.probe(speech_audio).duration_sec
    assert ffmpeg.probe(stems.vocals).duration_sec == pytest.approx(src_len, abs=0.5)


def test_demucs_chay_lai_thi_dung_lai_ket_qua_cu(speech_audio, tmp_path):
    """Tách lại một file đã tách là tốn GPU vô ích."""
    from src.infrastructure.asr.demucs import separate

    work = tmp_path / "stems"
    first = separate(speech_audio, work)
    mtime = first.vocals.stat().st_mtime
    second = separate(speech_audio, work)
    assert second.vocals.stat().st_mtime == mtime


# ---------------- WhisperX: nhận dạng ----------------


def test_whisperx_nhan_dang_tieng_viet(speech_audio):
    """Máy **đoán** chữ ở bước này, nên có tỷ lệ sai — vì thế GĐ1 bắt buộc có người soát."""
    from src.infrastructure.asr.whisperx import transcribe

    result = transcribe(speech_audio, language="vi")
    assert result.language == "vi"
    assert len(result.text) > 20
    assert result.segments
    # Không assert chính xác từng chữ: đó là điều test không nên làm với ASR.
    # Chỉ kiểm nó ra tiếng Việt có dấu, không ra chuỗi rỗng hay tiếng Anh.
    assert any(c in result.text for c in "ăâđêôơưáàảãạ")


def test_whisperx_truyen_language_tuong_minh(speech_audio):
    """Ép ngôn ngữ là có chủ ý: nội dung kỹ thuật đầy thuật ngữ Anh nên nhận tự
    động có thể ra sai ngôn ngữ, và khi đó transcript vô dụng mà không báo lỗi."""
    from src.infrastructure.asr.whisperx import transcribe

    assert transcribe(speech_audio, language="vi").language == "vi"


# ---------------- WhisperX: forced alignment ----------------


def test_forced_alignment_giu_nguyen_chu_da_biet(speech_audio):
    """Điểm cốt lõi của F2.5: chữ là **đầu vào** nên không thể sai chữ.

    Chỉ timing mới cần đo. Đây là lý do không ASR lại audio TTS.
    """
    from src.infrastructure.asr.whisperx import align_known_text, group_words_into_cues

    known = (
        "Biểu đồ kiểm soát cho thấy trung bình quá trình trôi dần theo ca. "
        "Cpk một phẩy ba ba vẫn có thể cho ra hàng lỗi."
    )
    words = align_known_text(speech_audio, known, language="vi")
    assert words, "aligner không trả về từ nào"
    assert all(w.end >= w.start for w in words)
    # Timestamp phải tăng dần: lệch thứ tự là phụ đề nhảy ngược
    assert all(b.start >= a.start for a, b in zip(words, words[1:], strict=False))

    cues = group_words_into_cues(words)
    assert cues
    joined = " ".join(text for _, _, text in cues).lower()
    # Chữ trong phụ đề phải là chữ mình đưa vào, không phải chữ máy đoán
    assert "kiểm soát" in joined
    assert "cpk" in joined


def test_alignment_nam_trong_do_dai_audio(speech_audio):
    from src.infrastructure.asr.whisperx import align_known_text
    from src.infrastructure.media import ffmpeg

    duration = ffmpeg.probe(speech_audio).duration_sec
    words = align_known_text(speech_audio, "Biểu đồ kiểm soát.", language="vi")
    assert all(0 <= w.start <= duration + 0.5 for w in words)


# ---------------- VoxCPM2 ----------------


def test_voxcpm2_sinh_giong_tieng_viet(tmp_path):
    """Model **openbmb/VoxCPM2**, không phải VoxCPM-0.5B (bản đó không có `vi`)."""
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
    from src.infrastructure.tts.voxcpm import DEFAULT_MODEL_ID, VoxCpmSynthesizer

    assert DEFAULT_MODEL_ID == "openbmb/VoxCPM2"

    now = datetime.now(UTC)
    source = Source(
        platform=Platform.WEB,
        kind=SourceKind.SINGLE_URL,
        url=SourceUrl("https://nmi.vn/test-voxcpm"),
        id=0,
    )
    source.approve(
        by="test",
        evidence=LicenseEvidence(license_type=LicenseType.OWN, evidence_ref="nội bộ"),
        scope=LicenseScope(may_translate=True, may_modify_audio=True, may_subtitle=True),
        at=now,
    )

    out = VoxCpmSynthesizer().synthesize(
        text="Biểu đồ kiểm soát cho thấy quá trình đang trôi.",
        dest=tmp_path / "voxcpm.wav",
        clearance=source.clear_for_dubbing(now),
    )
    assert out.exists() and out.stat().st_size > 1000
    assert ffmpeg.probe(out).duration_sec > 0.5


# ---------------- Ba model tuần tự trên cùng một card 8 GB ----------------


def test_ba_model_chay_tuan_tu_khong_het_vram(speech_audio, tmp_path):
    """Đây là test quan trọng nhất của file này.

    Một job thật đi qua Demucs → WhisperX → VoxCPM2. Trên card 8 GB, ba model
    cùng ở trên GPU là ``CUDA out of memory``. Test này chạy đúng chuỗi đó; nếu
    ai bỏ ``_free_vram()`` thì nó đỏ ở đây, không đỏ ba tuần sau bằng một job
    thất bại lúc 2 giờ sáng.
    """
    from src.infrastructure.asr.demucs import separate
    from src.infrastructure.asr.whisperx import align_known_text, transcribe
    from src.infrastructure.tts.voxcpm import VoxCpmSynthesizer

    torch = _torch()

    stems = separate(speech_audio, tmp_path / "stems")
    after_demucs = torch.cuda.memory_allocated() / 1024**3

    result = transcribe(stems.vocals, language="vi")
    after_asr = torch.cuda.memory_allocated() / 1024**3

    words = align_known_text(stems.vocals, result.text or "Biểu đồ kiểm soát.", language="vi")
    after_align = torch.cuda.memory_allocated() / 1024**3

    print(
        f"\n    VRAM đang giữ sau mỗi bước: demucs {after_demucs:.2f} GB · "
        f"asr {after_asr:.2f} GB · align {after_align:.2f} GB"
    )
    # Mỗi model phải nhả gần hết sau khi xong. Ngưỡng 1,5 GB là rộng rãi — vượt
    # nghĩa là có model còn nằm trên card.
    assert after_align < 1.5, "VRAM không được nhả giữa các bước"
    assert words

    # VoxCPM2 là model nặng nhất; nó phải nạp được sau cả hai bước trên
    _ = VoxCpmSynthesizer()
    assert stems.background.exists()
