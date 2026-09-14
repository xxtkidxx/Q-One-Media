"""Demucs, Whisper và VoxCPM2 chạy với GPU và model thật.

Đánh dấu ``gpu`` nên ``make test`` và ``make test-int`` đều bỏ qua. Chạy bằng:

    make test-gpu

Nhóm test này tồn tại vì một ràng buộc cụ thể của máy đang dùng: **RTX 3070 có
8 GB VRAM**. Đo thật bằng ``make measure-load``:

| Model | Giữ trên card | Nạp lại (cache ấm) |
|---|---|---|
| Demucs `htdemucs` | 0,54 GB | — |
| Whisper `large-v3` float16 | ~3,5 GB | 17,5 s |
| VoxCPM2 | **5,12 GB** | 31,9 s |

Cộng lại vượt 8 GB, nên chúng **không thể cùng ở trên card**. Thiết kế là chạy tuần
tự và nhả VRAM sau mỗi model; nếu ai bỏ lệnh nhả đi thì test ở đây đỏ ngay bằng một
con số VRAM, chứ không đỏ ba tuần sau bằng một job chết lúc 2 giờ sáng.

Mỗi test in VRAM đỉnh để so được giữa các lần chạy.
"""

from __future__ import annotations

import shutil
from itertools import pairwise
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

    Dùng giọng thật chứ không dùng sine wave: Demucs và Whisper xử lý tiếng nói
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


# ---------------- Whisper: nhận dạng ----------------


def test_whisper_nhan_dang_tieng_viet(speech_audio):
    """Máy **đoán** chữ ở bước này, nên có tỷ lệ sai — vì thế GĐ1 bắt buộc có người soát."""
    from src.infrastructure.asr.whisper import transcribe

    result = transcribe(speech_audio, language="vi")
    assert result.language == "vi"
    assert len(result.text) > 20
    assert result.segments
    # Không assert chính xác từng chữ: đó là điều test không nên làm với ASR.
    # Chỉ kiểm nó ra tiếng Việt có dấu, không ra chuỗi rỗng hay tiếng Anh.
    assert any(c in result.text for c in "ăâđêôơưáàảãạ")


def test_whisper_truyen_language_tuong_minh(speech_audio):
    """Ép ngôn ngữ là có chủ ý: nội dung kỹ thuật đầy thuật ngữ Anh nên nhận tự
    động có thể ra sai ngôn ngữ, và khi đó transcript vô dụng mà không báo lỗi."""
    from src.infrastructure.asr.whisper import transcribe

    assert transcribe(speech_audio, language="vi").language == "vi"


# ---------------- Gióng kịch bản đã biết (Whisper word timestamp) ----------------


def test_forced_alignment_giu_nguyen_chu_da_biet(speech_audio):
    """Điểm cốt lõi của F2.5: chữ là **đầu vào** nên không thể sai chữ.

    Chỉ timing mới cần đo. Đây là lý do không ASR lại audio TTS.
    """
    from src.infrastructure.asr.align import align_known_text
    from src.infrastructure.asr.whisper import group_words_into_cues

    known = (
        "Biểu đồ kiểm soát cho thấy trung bình quá trình trôi dần theo ca. "
        "Cpk một phẩy ba ba vẫn có thể cho ra hàng lỗi."
    )
    words = align_known_text(speech_audio, known, language="vi")
    assert words, "aligner không trả về từ nào"
    assert all(w.end >= w.start for w in words)
    # Timestamp phải tăng dần: lệch thứ tự là phụ đề nhảy ngược
    assert all(b.start >= a.start for a, b in pairwise(words))

    cues = group_words_into_cues(words)
    assert cues
    joined = " ".join(text for _, _, text in cues).lower()
    # Chữ trong phụ đề phải là chữ mình đưa vào, không phải chữ máy đoán
    assert "kiểm soát" in joined
    assert "cpk" in joined


def test_alignment_nam_trong_do_dai_audio(speech_audio):
    from src.infrastructure.asr.align import align_known_text
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

    torch = _torch()
    out = VoxCpmSynthesizer().synthesize(
        text="Biểu đồ kiểm soát cho thấy quá trình đang trôi.",
        dest=tmp_path / "voxcpm.wav",
        clearance=source.clear_for_dubbing(now),
    )
    assert out.exists() and out.stat().st_size > 1000
    assert ffmpeg.probe(out).duration_sec > 0.5

    # Model này chiếm 5,12 GB — giữ lại là VRAM rảnh về 0,00/8,0 GB và việc sau
    # không nạp nổi Whisper. Adapter phải nhả ngay trong ``finally``, và đây là
    # chỗ bắt nếu ai bỏ hai dòng đó đi.
    held = torch.cuda.memory_allocated() / 1024**3
    assert held < 1.0, f"VoxCPM2 còn giữ {held:.2f} GB sau khi sinh giọng"


# ---------------- Ba model tuần tự trên cùng một card 8 GB ----------------


def test_bon_buoc_gpu_chay_tuan_tu_khong_het_vram(speech_audio, tmp_path):
    """Đây là test quan trọng nhất của file này.

    Một job thật đi qua Demucs → Whisper → gióng → VoxCPM2, **trên cùng một card
    8 GB**. Cộng dồn nhu cầu của chúng là ~9 GB nên chúng không thể cùng ở trên
    card; cả chuỗi chỉ chạy được nếu mỗi bước nhả VRAM khi xong.

    Test này đã bắt được một lỗi thật: ``voxcpm.py`` từng giữ model ở biến
    module-level cho suốt vòng đời tiến trình — đo ra VRAM rảnh **0,00/8,0 GB**,
    nên việc kế tiếp không nạp nổi Whisper. Đó là loại lỗi không đỏ ở unit test và
    chỉ lộ ra bằng một job chết lúc 2 giờ sáng, nên nó phải được canh ở đây.
    """
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
    from src.infrastructure.asr.align import align_known_text
    from src.infrastructure.asr.demucs import separate
    from src.infrastructure.asr.whisper import transcribe
    from src.infrastructure.tts.voxcpm import VoxCpmSynthesizer

    torch = _torch()

    def held() -> float:
        return torch.cuda.memory_allocated() / 1024**3

    stems = separate(speech_audio, tmp_path / "stems")
    after_demucs = held()

    result = transcribe(stems.vocals, language="vi")
    after_asr = held()

    words = align_known_text(stems.vocals, result.text or "Biểu đồ kiểm soát.", language="vi")
    after_align = held()

    now = datetime.now(UTC)
    source = Source(
        platform=Platform.WEB,
        kind=SourceKind.SINGLE_URL,
        url=SourceUrl("https://nmi.vn/test-tuan-tu"),
        id=0,
    )
    source.approve(
        by="test",
        evidence=LicenseEvidence(license_type=LicenseType.OWN, evidence_ref="nội bộ"),
        scope=LicenseScope(may_translate=True, may_modify_audio=True, may_subtitle=True),
        at=now,
    )
    # VoxCPM2 là model nặng nhất (5,12 GB) và đứng CUỐI chuỗi — nó chỉ nạp được nếu
    # ba bước trên đã nhả sạch. Khởi tạo adapter không chứng minh gì (nạp là lười),
    # nên ở đây phải sinh giọng thật.
    voiced = VoxCpmSynthesizer().synthesize(
        text="Quá trình đang trôi theo ca.",
        dest=tmp_path / "voiced.wav",
        clearance=source.clear_for_dubbing(now),
    )
    after_tts = held()

    print(
        f"\n    VRAM đang giữ sau mỗi bước: demucs {after_demucs:.2f} GB · "
        f"asr {after_asr:.2f} GB · gióng {after_align:.2f} GB · tts {after_tts:.2f} GB"
    )
    # Ngưỡng 1,0 GB là rộng rãi so với model nhỏ nhất trong chuỗi (Demucs 0,54 GB):
    # vượt nó nghĩa là có model còn nằm trên card, không phải nhiễu đo.
    for step, value in (
        ("demucs", after_demucs),
        ("asr", after_asr),
        ("gióng", after_align),
        ("tts", after_tts),
    ):
        assert value < 1.0, f"{step} không nhả VRAM: còn giữ {value:.2f} GB"

    assert words
    assert stems.background.exists()
    assert voiced.exists() and voiced.stat().st_size > 1000
