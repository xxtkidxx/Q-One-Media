"""Ngân sách âm tiết (F2.3) — nhóm test giữ cho video không nghe như máy đọc."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.application.use_cases.synthesize_voice import (
    ScriptMissing,
    SpeechRateUnknown,
    synthesize_voice,
)
from src.domain.errors import ScopeNotGranted
from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage, MediaAsset, Segment
from src.domain.sourcing.clearance import DubbingClearance
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    LicenseEvidence,
    LicenseScope,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)
from src.infrastructure.tts.voxcpm import count_syllables
from tests.fakes import FakeClock, FakeUnitOfWork

NOW = datetime(2026, 9, 14, 10, 0, tzinfo=UTC)
MEDIA_ROOT = Path("/data/media")

DUB_SCOPE = LicenseScope(may_translate=True, may_modify_audio=True, may_subtitle=True)


class StubSynthesizer:
    """Sinh giọng giả, độ dài audio do test quyết định."""

    def __init__(self, *, rate: float | None, audio_sec: float = 50.0) -> None:
        self._rate = rate
        self.audio_sec = audio_sec
        self.calls: list[tuple[str, DubbingClearance]] = []

    def measured_rate(self) -> float | None:
        return self._rate

    def synthesize(self, *, text, dest, clearance, voice_ref=None) -> Path:
        self.calls.append((text, clearance))
        return dest


class StubProbe:
    def __init__(self, synth: StubSynthesizer) -> None:
        self._synth = synth

    def duration_sec(self, path: Path) -> float:
        return self._synth.audio_sec


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def scripted_item(uow, *, script: str, window_sec: float = 60.0, scope=DUB_SCOPE) -> Item:
    source = uow.sources.add(
        Source(
            platform=Platform.YOUTUBE,
            kind=SourceKind.SINGLE_URL,
            url=SourceUrl("https://www.youtube.com/watch?v=a"),
        )
    )
    source.approve(
        by="q",
        evidence=LicenseEvidence(
            license_type=LicenseType.VENDOR_MEDIAKIT, evidence_ref="https://v/terms"
        ),
        scope=scope,
        at=NOW,
    )
    uow.sources.update(source)

    item = uow.items.add(
        Item.accept(
            url=SourceUrl("https://www.youtube.com/watch?v=a"),
            clearance=source.clear_for_download(NOW),
        )
    )
    item.mark_downloaded(path=MediaAsset("source/a.mp4"), duration_sec=600)
    item.mark_separated()
    item.mark_transcribed()
    item.send_transcript_to_review()
    item.pick_segment(Segment(0.0, window_sec))
    if scope.may_modify_audio:
        item.attach_script(script_vi=script, clearance=source.clear_for_dubbing(NOW))
    else:
        # Kịch bản gắn bằng scope đủ quyền, rồi thu quyền lại — mô phỏng license
        # hết hiệu lực giữa đường, chuyện có thật khi media kit đổi điều khoản.
        item.attach_script(script_vi=script, clearance=_force_clearance(source))
        source.scope = scope
        uow.sources.update(source)
    uow.items.update(item)
    return item


def _force_clearance(source: Source) -> DubbingClearance:
    saved = source.scope
    source.scope = DUB_SCOPE
    try:
        return source.clear_for_dubbing(NOW)
    finally:
        source.scope = saved


def run(uow, clock, item_id, synth):
    return synthesize_voice(
        item_id,
        synthesizer=synth,
        probe=StubProbe(synth),
        count_syllables=count_syllables,
        media_root=MEDIA_ROOT,
        uow=uow,
        clock=clock,
    )


# ---------------- Đếm âm tiết ----------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hệ thống kiểm soát quá trình", 6),
        ("Cpk", 1),
        ("Gage R và R", 4),
        ("", 0),
        ("   ", 0),
    ],
)
def test_dem_am_tiet_tinh_tieng_khong_tinh_tu(text, expected):
    """Tiếng Việt viết rời từng âm tiết, nên đếm 'tiếng' sát thực tế hơn đếm từ."""
    assert count_syllables(text) == expected


def test_chu_so_duoc_tinh_theo_so_am_tiet_doc_ra():
    """Nội dung công nghiệp dày số, và số nở ra khi đọc.

    "biến tần 380V ba pha" đọc là "biến tần ba trăm tám mươi vôn ba pha" = 9 âm
    tiết. Đếm chữ số là 1 thì ra 5 — thiếu gần một nửa, đúng ở loại nội dung dự
    án này làm nhiều nhất.
    """
    assert count_syllables("biến tần 380V ba pha") == 10  # ước lượng thiên về cao
    assert count_syllables("IP67") == 4
    assert count_syllables("Cpk 1.33") == 6


def test_dem_thieu_la_huong_sai_nguy_hiem_hon_dem_thua():
    """Với một ngân sách: đếm thừa làm kịch bản ngắn hơn cần (vô hại), đếm thiếu
    để kịch bản tràn khung đi qua (có hại). Hệ số chữ số phải >= 1."""
    assert count_syllables("380") >= 3


# ---------------- Chưa đo tốc độ đọc thì từ chối ----------------


def test_chua_do_toc_do_doc_thi_tu_choi_chu_khong_doan(uow, clock):
    """Một ngân sách sai còn tệ hơn không có ngân sách: nó làm mọi cảnh lệch đều nhau."""
    item = scripted_item(uow, script="Cpk chỉ nói về độ lệch trong nhóm mẫu.")
    synth = StubSynthesizer(rate=None)
    with pytest.raises(SpeechRateUnknown) as exc:
        run(uow, clock, item.id, synth)
    assert "G0.7" in str(exc.value)
    assert synth.calls == []  # không tốn một giây GPU nào


# ---------------- Chặn trước khi sinh ----------------


def test_kich_ban_qua_dai_thi_khong_sinh_giong_va_tra_ve_viet_lai(uow, clock):
    """Bắt được ở bước đếm thì không tốn GPU."""
    script = " ".join(["âm"] * 400)  # 400 âm tiết cho khung 60s ở 5.5/s = quá
    item = scripted_item(uow, script=script, window_sec=60.0)
    synth = StubSynthesizer(rate=5.5)

    out = run(uow, clock, item.id, synth)

    assert out.voiced is False
    assert out.syllables == 400
    assert out.max_syllables == 330
    assert synth.calls == []
    assert uow.items.get(item.id).stage is ItemStage.SEGMENT_PICKED
    assert "viết ngắn lại" in (out.reason or "")
    assert "script_over_budget" in uow.audit.actions()


# ---------------- Chặn sau khi sinh ----------------


def test_audio_that_dai_qua_nguong_5_phan_tram_thi_viet_lai(uow, clock):
    """Nội dung nhiều số liệu đọc chậm hơn văn xuôi — đếm đúng vẫn có thể tràn."""
    item = scripted_item(uow, script=" ".join(["âm"] * 300), window_sec=60.0)
    synth = StubSynthesizer(rate=5.5, audio_sec=68.0)  # vượt 13%

    out = run(uow, clock, item.id, synth)

    assert out.voiced is False
    assert out.audio_sec == 68.0
    assert len(synth.calls) == 1  # đã sinh rồi mới biết
    assert uow.items.get(item.id).stage is ItemStage.SEGMENT_PICKED
    assert "13%" in (out.reason or "")
    assert "không tăng tốc độ đọc" in (out.reason or "")
    assert "audio_over_budget" in uow.audit.actions()


def test_trong_nguong_5_phan_tram_thi_chap_nhan(uow, clock):
    item = scripted_item(uow, script=" ".join(["âm"] * 300), window_sec=60.0)
    synth = StubSynthesizer(rate=5.5, audio_sec=62.0)  # vượt 3.3%, trong ngưỡng

    out = run(uow, clock, item.id, synth)

    assert out.voiced is True
    saved = uow.items.get(item.id)
    assert saved.stage is ItemStage.VOICED
    assert saved.path_work.relative_path.endswith("voice_vi.wav")
    assert "voiced" in uow.audit.actions()


def test_duong_dan_luu_la_tuong_doi_khong_tuyet_doi(uow, clock):
    item = scripted_item(uow, script=" ".join(["âm"] * 100), window_sec=60.0)
    out = run(uow, clock, item.id, StubSynthesizer(rate=5.5, audio_sec=20.0))
    path = out.item.path_work.relative_path
    assert path == "work/item-00000002/voice_vi.wav"
    assert not path.startswith("/")


# ---------------- License gate vẫn chặn ở bước này ----------------


def test_mat_quyen_sua_audio_giua_duong_thi_khong_long_tieng(uow, clock):
    """LicenseViolation cố ý KHÔNG bị bắt trong use case — job phải dừng hẳn."""
    item = scripted_item(
        uow,
        script="ngắn",
        scope=LicenseScope(may_translate=True, may_subtitle=True),  # thiếu modify_audio
    )
    synth = StubSynthesizer(rate=5.5)
    with pytest.raises(ScopeNotGranted):
        run(uow, clock, item.id, synth)
    assert synth.calls == []


# ---------------- Đầu vào thiếu ----------------


def test_thieu_kich_ban_thi_bao_loi_ro(uow, clock):
    source = uow.sources.add(
        Source(
            platform=Platform.YOUTUBE,
            kind=SourceKind.SINGLE_URL,
            url=SourceUrl("https://www.youtube.com/watch?v=b"),
        )
    )
    source.approve(
        by="q",
        evidence=LicenseEvidence(license_type=LicenseType.OWN, evidence_ref="nội bộ"),
        scope=DUB_SCOPE,
        at=NOW,
    )
    uow.sources.update(source)
    item = uow.items.add(
        Item.accept(
            url=SourceUrl("https://www.youtube.com/watch?v=b"),
            clearance=source.clear_for_download(NOW),
        )
    )
    with pytest.raises(ScriptMissing):
        run(uow, clock, item.id, StubSynthesizer(rate=5.5))
