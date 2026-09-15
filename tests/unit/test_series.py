"""Series ở Studio — khuôn sản xuất cho một loạt video ngắn cùng chuyên đề.

Giữ ba điều: Series sai cấu hình bị **domain** từ chối; mọi bản nháp sinh từ Series
mang đúng pillar, mẫu hook và thuật ngữ của nó; bản nháp dừng trước lồng tiếng cho
tới khi người bấm đưa vào sản xuất.
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

import pytest

from src.application.use_cases.author_series import (
    MAX_TOPICS_PER_BATCH,
    SeriesNotFound,
    create_series,
    draft_from_series,
    start_series_video,
)
from src.domain.authoring.series import PostingCadence, Series, SubtitlePreset
from src.domain.errors import InvariantViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import (
    PORTRAIT_9_16,
    AspectRatio,
    ItemStage,
    SpeechRate,
    SyllableBudget,
)
from src.domain.scheduling.entities import JobTask
from src.domain.sourcing.value_objects import SourceUrl
from src.infrastructure.db import mappers
from tests.fakes import FakeClock, FakeUnitOfWork

NOW = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)
RATE = 3.54  # âm tiết/giây, đo thật ở G0.7
HOOKS = (
    "[Biểu đồ/chỉ số] báo [trạng thái], mà [thực tế ngược lại]. Ai sai?",
    "[A] và [B] khác nhau đúng một chỗ: [chỗ khác].",
    "Trước khi tin [con số], hỏi một câu: [câu hỏi kiểm tra].",
)
TERMS = ("MES", "SPC", "OEE", "Cpk")


def _series(**over) -> Series:
    kwargs = {
        "name": "SPC không nói dối",
        "pillar": "Giải-Thích",
        "hook_templates": HOOKS,
        "target_sec": 35.0,
        "kept_terms": TERMS,
    }
    kwargs.update(over)
    return Series(**kwargs)


class FakePromptWriter:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[dict] = []

    def write_from_prompt(self, *, brief, title, max_syllables, glossary):
        if title == self.fail_on:
            raise RuntimeError("model quá tải")
        self.calls.append(
            {"brief": brief, "title": title, "budget": max_syllables, "glossary": glossary}
        )
        return f"Kịch bản cho {title}."


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def _create(uow, **over) -> Series:
    kwargs = {
        "name": "SPC không nói dối",
        "pillar": "Giải-Thích",
        "hook_templates": list(HOOKS),
        "target_sec": 35.0,
        "kept_terms": list(TERMS),
        "output_aspect_ratio": PORTRAIT_9_16,
        "voice_id": "vieneu:minh-duc",
        "subtitle": SubtitlePreset(),
        "cadence": PostingCadence(weekdays=(0, 2, 4), time_of_day="11:45"),
        "uow": uow,
        "actor": "quan.nguyen",
    }
    kwargs.update(over)
    return create_series(**kwargs)


def _draft(uow, clock, tmp_path, series_id, topics, writer=None):
    return draft_from_series(
        series_id,
        topics=topics,
        author="quan.nguyen",
        writer=writer or FakePromptWriter(),
        speech_rate=RATE,
        glossary={"Cpk": "", "downtime": "thời gian dừng máy"},
        media_root=tmp_path,
        uow=uow,
        clock=clock,
    )


# ---------------- Domain từ chối cấu hình sai ----------------


def test_series_hop_le_chuan_hoa_hook_va_thuat_ngu():
    series = _series(
        name="  SPC không nói dối ",
        hook_templates=(HOOKS[0], "   ", f"  {HOOKS[1]} "),
        kept_terms=("MES", " SPC ", "spc", ""),
    )
    assert series.name == "SPC không nói dối"
    assert series.hook_templates == (HOOKS[0], HOOKS[1])
    assert series.kept_terms == ("MES", "SPC")
    assert series.output_aspect_ratio == PORTRAIT_9_16
    assert series.language == "vi"


@pytest.mark.parametrize("pillar", ["", "   "])
def test_thieu_pillar_thi_tu_choi(pillar):
    with pytest.raises(InvariantViolation, match="pillar"):
        _series(pillar=pillar)


def test_thieu_ten_thi_tu_choi():
    with pytest.raises(InvariantViolation):
        _series(name=" ")


@pytest.mark.parametrize("target_sec", [10.0, 24.9, 45.1, 60.0])
def test_do_dai_ngoai_25_45_giay_thi_tu_choi(target_sec):
    with pytest.raises(InvariantViolation, match="25–45"):
        _series(target_sec=target_sec)


@pytest.mark.parametrize("target_sec", [25.0, 45.0])
def test_bien_25_va_45_giay_duoc_chap_nhan(target_sec):
    assert _series(target_sec=target_sec).target_sec == target_sec


@pytest.mark.parametrize("ratio", ["16:9", "1:1", "4:5"])
def test_khung_khac_9_16_thi_tu_choi(ratio):
    with pytest.raises(InvariantViolation, match="9:16"):
        _series(output_aspect_ratio=AspectRatio.parse(ratio))


def test_ngon_ngu_khac_tieng_viet_thi_tu_choi():
    with pytest.raises(InvariantViolation):
        _series(language="en")


def test_khong_co_mau_hook_thi_tu_choi():
    with pytest.raises(InvariantViolation):
        _series(hook_templates=("  ",))


def test_mau_hook_khong_co_cho_trong_thi_tu_choi():
    """Không có chỗ trống thì mọi video mở đầu y hệt nhau."""
    with pytest.raises(InvariantViolation, match="chỗ trống"):
        _series(hook_templates=("Biểu đồ báo đỏ mà hàng vẫn đạt. Ai sai?",))


@pytest.mark.parametrize(
    ("weekdays", "time_of_day"),
    [((), "11:45"), ((7,), "11:45"), ((1, 1), "11:45"), ((0,), "25:00"), ((0,), "9h")],
)
def test_lich_dang_sai_thi_tu_choi(weekdays, time_of_day):
    with pytest.raises(InvariantViolation):
        PostingCadence(weekdays=weekdays, time_of_day=time_of_day)


def test_lich_dang_hien_thi_theo_thu_tu_ngay():
    assert PostingCadence(weekdays=(4, 0, 2), time_of_day="11:45").label == "T2, T4, T6 · 11:45"


@pytest.mark.parametrize(("font_size", "max_chars"), [(20, 42), (54, 80)])
def test_preset_phu_de_ngoai_khoang_thi_tu_choi(font_size, max_chars):
    with pytest.raises(InvariantViolation):
        SubtitlePreset(font_size=font_size, max_chars_per_line=max_chars)


# ---------------- Hook, mốc giây, thuật ngữ ----------------


def test_hook_xoay_vong_tat_dinh():
    series = _series()
    assert [series.hook_for(n) for n in range(4)] == [HOOKS[0], HOOKS[1], HOOKS[2], HOOKS[0]]


@pytest.mark.parametrize("target_sec", [25.0, 35.0, 45.0])
def test_moc_giay_lien_mach_tu_0_toi_het_video(target_sec):
    beats = _series(target_sec=target_sec).beats()
    assert [beat.label for beat in beats] == ["Hook", "Đặt khung", "Thân", "Chốt", "CTA"]
    assert (beats[0].start_sec, beats[0].end_sec) == (0.0, 3.0)
    assert beats[-1].end_sec == target_sec
    assert beats[-1].duration_sec == 4.0
    for before, after in pairwise(beats):
        assert before.end_sec == after.start_sec
    caps = sum(
        SyllableBudget(window_sec=beat.duration_sec, rate=SpeechRate(RATE)).max_syllables
        for beat in beats
    )
    assert caps <= SyllableBudget(window_sec=target_sec, rate=SpeechRate(RATE)).max_syllables


def test_de_bai_ep_cau_truc_moc_giay_hook_va_thuat_ngu():
    brief = _series().brief_for("Cpk và Ppk", position=1, speech_rate=RATE)
    assert "Pillar: Giải-Thích" in brief
    assert "Đề tài của video này: Cpk và Ppk" in brief
    assert HOOKS[1] in brief and HOOKS[0] not in brief
    for mark in ("0–3s · Hook", "3–8.6s · Đặt khung", "8.6–25.4s · Thân", "31–35s · CTA"):
        assert mark in brief
    assert "tối đa 10 âm tiết" in brief  # 3 giây × 3,54 âm tiết/giây
    assert "Giữ nguyên tiếng Anh, không dịch, không phiên âm: MES, SPC, OEE, Cpk" in brief


def test_de_tai_rong_thi_tu_choi():
    with pytest.raises(InvariantViolation):
        _series().brief_for("  ", position=0, speech_rate=RATE)


def test_thuat_ngu_cua_series_thang_glossary_chung():
    merged = _series().glossary_over({"cpk": "chỉ số năng lực", "downtime": "thời gian dừng máy"})
    assert merged == {
        "downtime": "thời gian dừng máy",
        "MES": "MES",
        "SPC": "SPC",
        "OEE": "OEE",
        "Cpk": "Cpk",
    }


# ---------------- Use case ----------------


def test_tao_series_luu_va_ghi_audit(uow):
    series = _create(uow)
    assert series.id is not None
    assert uow.series.get(series.id) is series
    assert "series_created" in uow.audit.actions()
    assert uow.commits == 1


def test_cau_hinh_sai_bi_domain_chan_truoc_khi_luu(uow):
    with pytest.raises(InvariantViolation):
        _create(uow, output_aspect_ratio=AspectRatio.parse("16:9"))
    assert uow.series.list_all() == []


def test_ba_de_tai_thanh_ba_ban_nhap_mang_dung_rang_buoc_series(uow, clock, tmp_path):
    series = _create(uow)
    writer = FakePromptWriter()
    topics = ["Cpk và Ppk", "OEE vượt 100%", "Gage R&R trước Cpk"]

    outcome = _draft(uow, clock, tmp_path, series.id, topics, writer)

    assert outcome.failed == ()
    assert [item.title_original for item in outcome.created] == topics
    for index, (item, call) in enumerate(zip(outcome.created, writer.calls, strict=True)):
        assert item.series_id == series.id
        assert item.stage is ItemStage.SCRIPTED
        assert item.duration_sec == 35
        assert item.output_aspect_ratio == PORTRAIT_9_16
        assert item.voice_id == "vieneu:minh-duc"
        assert "Pillar: Giải-Thích" in call["brief"]
        assert HOOKS[index] in call["brief"]
        assert {term: term for term in TERMS}.items() <= call["glossary"].items()
        assert "cpk" not in {key.casefold() for key in call["glossary"] if key != "Cpk"}
    drafts = [e for e in uow.audit.entries if e["action"] == "series_draft_created"]
    assert [e["detail"]["hook"] for e in drafts] == list(HOOKS)
    # Bản nháp chưa được lồng tiếng: người phải đọc kịch bản trước.
    assert uow.jobs.all() == []


def test_lan_sinh_sau_xoay_hook_tiep_tu_video_con_cuoi(uow, clock, tmp_path):
    series = _create(uow)
    _draft(uow, clock, tmp_path, series.id, ["Cpk và Ppk", "OEE vượt 100%"])
    writer = FakePromptWriter()
    _draft(uow, clock, tmp_path, series.id, ["Gage R&R", "MES và ERP"], writer)
    assert HOOKS[2] in writer.calls[0]["brief"]
    assert HOOKS[0] in writer.calls[1]["brief"]


def test_de_tai_trung_va_dong_trong_bi_bo(uow, clock, tmp_path):
    series = _create(uow)
    outcome = _draft(uow, clock, tmp_path, series.id, ["Cpk", " ", "Cpk ", "OEE"])
    assert [item.title_original for item in outcome.created] == ["Cpk", "OEE"]


def test_qua_tran_de_tai_thi_tu_choi_truoc_khi_goi_model(uow, clock, tmp_path):
    series = _create(uow)
    writer = FakePromptWriter()
    topics = [f"Đề tài {n}" for n in range(MAX_TOPICS_PER_BATCH + 1)]
    with pytest.raises(InvariantViolation):
        _draft(uow, clock, tmp_path, series.id, topics, writer)
    assert writer.calls == []


def test_khong_co_de_tai_thi_tu_choi(uow, clock, tmp_path):
    series = _create(uow)
    with pytest.raises(InvariantViolation):
        _draft(uow, clock, tmp_path, series.id, ["", "  "])


def test_series_khong_ton_tai(uow, clock, tmp_path):
    with pytest.raises(SeriesNotFound):
        _draft(uow, clock, tmp_path, 999, ["Cpk"])


def test_mot_de_tai_loi_khong_keo_do_cac_de_tai_con_lai(uow, clock, tmp_path):
    series = _create(uow)
    writer = FakePromptWriter(fail_on="OEE vượt 100%")
    outcome = _draft(uow, clock, tmp_path, series.id, ["Cpk", "OEE vượt 100%", "MES"], writer)
    assert [item.title_original for item in outcome.created] == ["Cpk", "MES"]
    assert outcome.failed == (("OEE vượt 100%", "model quá tải"),)
    # Đề tài lỗi không chiếm vị trí hook: video tạo được vẫn xoay liền mạch.
    assert HOOKS[1] in writer.calls[1]["brief"]


def test_dua_ban_nhap_vao_san_xuat_xep_viec_long_tieng(uow, clock, tmp_path):
    series = _create(uow)
    item = _draft(uow, clock, tmp_path, series.id, ["Cpk"]).created[0]

    start_series_video(item.id, series_id=series.id, uow=uow, actor="quan.nguyen")

    assert [(job.task, job.item_id) for job in uow.jobs.all()] == [(JobTask.SYNTHESIZE, item.id)]
    assert "series_production_started" in uow.audit.actions()


def test_khong_dua_video_cua_series_khac_vao_san_xuat(uow, clock, tmp_path):
    from src.application.use_cases.author_video import ItemNotFound

    series = _create(uow)
    item = _draft(uow, clock, tmp_path, series.id, ["Cpk"]).created[0]
    with pytest.raises(ItemNotFound):
        start_series_video(item.id, series_id=series.id + 100, uow=uow, actor="q")


def test_chi_ban_nhap_scripted_moi_dua_vao_san_xuat(uow, clock, tmp_path):
    series = _create(uow)
    item = _draft(uow, clock, tmp_path, series.id, ["Cpk"]).created[0]
    item.mark_voiced()
    with pytest.raises(InvariantViolation):
        start_series_video(item.id, series_id=series.id, uow=uow, actor="q")


# ---------------- Mapper: không mất dữ liệu im lặng ----------------


def test_mapper_series_giu_nguyen_moi_truong():
    series = _series(
        voice_id="vieneu:minh-duc",
        subtitle=SubtitlePreset(font_size=60, max_chars_per_line=30),
        cadence=PostingCadence(weekdays=(0, 2, 4), time_of_day="11:45"),
    )
    row = mappers.series_to_row(series)
    row.id = 7
    back = mappers.series_to_domain(row)
    assert back.id == 7
    for name in (
        "name", "pillar", "hook_templates", "target_sec", "kept_terms",
        "output_aspect_ratio", "language", "voice_id", "subtitle", "cadence",
    ):
        assert getattr(back, name) == getattr(series, name), name


def test_mapper_item_giu_series_id():
    item = Item.from_prompt(
        url=SourceUrl("https://nmi.vn/qone/studio#1"),
        source_id=1,
        script_vi="MES làm gì trong nhà máy.",
        title="MES",
        target_sec=35.0,
        author="quan.nguyen",
        series_id=3,
    )
    row = mappers.item_to_row(item)
    row.id = 11
    assert mappers.item_to_domain(row).series_id == 3
