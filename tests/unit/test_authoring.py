"""Giai đoạn 2 — video dựng từ đề bài của người dùng.

Không có license gate ở đây vì không dùng tác phẩm của ai; thứ thay thế là trách
nhiệm có tên. Test này giữ đúng hai điều: **phải có tên người tạo**, và phần sau
của pipeline (lồng tiếng → phụ đề → duyệt → publish) dùng lại nguyên vẹn.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.application.use_cases.author_video import (
    add_shot,
    create_video_from_prompt,
    load_visual_plan,
    remove_shot,
    resolve_generated_shots,
    save_visual_plan,
)
from src.domain.authoring.visuals import Shot, ShotKind, VisualPlan, default_plan
from src.domain.errors import InvariantViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage, MediaAsset
from src.domain.scheduling.entities import JobTask
from src.domain.sourcing.value_objects import SourceUrl
from tests.fakes import FakeClock, FakeUnitOfWork

NOW = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
RATE = 3.54  # âm tiết/giây, đo thật ở G0.7


class FakePromptWriter:
    def __init__(self, script: str = "Cpk nói gì, và Cpk không nói gì.") -> None:
        self.script = script
        self.calls: list[dict] = []

    def write_from_prompt(self, *, brief, title, max_syllables, glossary):
        self.calls.append(
            {"brief": brief, "title": title, "budget": max_syllables, "glossary": glossary}
        )
        return self.script


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def _create(uow, clock, tmp_path: Path, **over):
    kwargs = {
        "brief": "Giải thích Cpk cho quản lý nhà máy, 60 giây, giọng thẳng thắn.",
        "title": "Cpk trong 60 giây",
        "target_sec": 60.0,
        "author": "quan.nguyen",
        "writer": FakePromptWriter(),
        "speech_rate": RATE,
        "glossary": {"Cpk": ""},
        "media_root": tmp_path,
        "uow": uow,
        "clock": clock,
    }
    kwargs.update(over)
    return create_video_from_prompt(**kwargs)


# ---------------- Đường chính ----------------


def test_de_bai_cua_nguoi_dung_thanh_item_da_co_kich_ban(uow, clock, tmp_path):
    writer = FakePromptWriter()
    result = _create(uow, clock, tmp_path, writer=writer)

    assert result.item.stage is ItemStage.SCRIPTED
    assert result.item.script_vi == writer.script
    assert result.item.path_source is None  # không dùng thước phim của ai
    # Ngân sách âm tiết tính y như Giai đoạn 1, không có công thức thứ hai.
    assert result.max_syllables == writer.calls[0]["budget"] > 0
    assert writer.calls[0]["glossary"] == {"Cpk": ""}
    # Bước kế tiếp là lồng tiếng — không qua tải/nhận dạng/chọn đoạn.
    assert [job.task for job in uow.jobs.all()] == [JobTask.SYNTHESIZE]


def test_vet_tac_gia_di_vao_item_va_audit(uow, clock, tmp_path):
    result = _create(uow, clock, tmp_path, author="  thu.ha  ")
    assert result.item.script_sources == ("prompt:thu.ha",)
    assert "authored_from_prompt" in uow.audit.actions()


def test_thieu_ten_nguoi_tao_thi_tu_choi(uow, clock, tmp_path):
    with pytest.raises(InvariantViolation):
        _create(uow, clock, tmp_path, author="   ")


def test_thoi_luong_ngoai_bien_thi_tu_choi(uow, clock, tmp_path):
    with pytest.raises(InvariantViolation):
        _create(uow, clock, tmp_path, target_sec=600)


def test_chua_do_toc_do_doc_thi_khong_lap_duoc_ngan_sach(uow, clock, tmp_path):
    from src.application.use_cases.synthesize_voice import SpeechRateUnknown

    with pytest.raises(SpeechRateUnknown):
        _create(uow, clock, tmp_path, speech_rate=None)


def test_nguon_studio_tao_mot_lan_roi_dung_lai(uow, clock, tmp_path):
    first = _create(uow, clock, tmp_path)
    second = _create(uow, clock, tmp_path)
    assert first.item.source_id == second.item.source_id
    source = uow.sources.get(first.item.source_id)
    assert source.status.value == "approved"
    assert source.evidence.license_type.value == "own"


# ---------------- Kịch bản hình ----------------


def test_chua_dua_hinh_thi_dung_the_thuong_hieu_khong_bia_anh(uow, clock, tmp_path):
    result = _create(uow, clock, tmp_path)
    plan = load_visual_plan(tmp_path, result.item.id)
    assert plan is not None
    assert {shot.kind for shot in plan.shots} == {ShotKind.BRAND_CARD}


def test_them_canh_that_thi_thay_the_the_giu_cho(uow, clock, tmp_path):
    result = _create(uow, clock, tmp_path)
    plan = add_shot(
        result.item.id,
        shot=Shot(
            kind=ShotKind.UPLOAD, seconds=5, asset="source/uploads/a.png", caption="Dây chuyền"
        ),
        media_root=tmp_path,
        uow=uow,
        actor="quan.nguyen",
    )
    assert [shot.kind for shot in plan.shots] == [ShotKind.UPLOAD]
    assert "visual_shot_added" in uow.audit.actions()

    plan = add_shot(
        result.item.id,
        shot=Shot(kind=ShotKind.CHART, seconds=6, caption="Cpk theo tháng",
                  data=(("T1", 1.1), ("T2", 1.33))),
        media_root=tmp_path,
        uow=uow,
        actor="quan.nguyen",
    )
    assert len(plan.shots) == 2


def test_bieu_do_khong_co_so_lieu_thi_tu_choi():
    """Biểu đồ không số liệu là hình trang trí mang dáng vẻ bằng chứng."""
    with pytest.raises(InvariantViolation):
        Shot(kind=ShotKind.CHART, seconds=5, caption="Cpk")


def test_canh_ai_phai_co_prompt():
    with pytest.raises(InvariantViolation):
        Shot(kind=ShotKind.GENERATED, seconds=5)


def test_xoa_canh_cuoi_thi_quay_ve_the_thuong_hieu(uow, clock, tmp_path):
    result = _create(uow, clock, tmp_path)
    add_shot(
        result.item.id,
        shot=Shot(kind=ShotKind.UPLOAD, seconds=5, asset="a.png"),
        media_root=tmp_path, uow=uow, actor="q",
    )
    plan = remove_shot(result.item.id, index=0, media_root=tmp_path, uow=uow, actor="q")
    assert plan.shots and all(shot.kind is ShotKind.BRAND_CARD for shot in plan.shots)


def test_khong_co_nha_cung_cap_anh_thi_canh_ai_roi_ve_the_thuong_hieu(uow, clock, tmp_path):
    """Thiếu API key sinh ảnh không được làm dừng cả dây chuyền."""
    from src.infrastructure.visuals.registry import NullImageGenerator

    result = _create(uow, clock, tmp_path)
    save_visual_plan(
        tmp_path,
        result.item.id,
        VisualPlan((Shot(kind=ShotKind.GENERATED, seconds=6, prompt="nhà máy ban đêm"),)),
    )
    plan = resolve_generated_shots(
        result.item.id, generator=NullImageGenerator(), media_root=tmp_path, uow=uow
    )
    assert [shot.kind for shot in plan.shots] == [ShotKind.BRAND_CARD]
    assert plan.ready
    assert "visual_generation_fallback" in uow.audit.actions()


def test_sinh_anh_thanh_cong_thi_canh_dung_dung_file(uow, clock, tmp_path):
    class Generator:
        def generate(self, *, prompt, out_dir, name):
            return f"{out_dir}/{name}.png"

    result = _create(uow, clock, tmp_path)
    save_visual_plan(
        tmp_path,
        result.item.id,
        VisualPlan((Shot(kind=ShotKind.GENERATED, seconds=6, prompt="nhà máy ban đêm"),)),
    )
    plan = resolve_generated_shots(
        result.item.id, generator=Generator(), media_root=tmp_path, uow=uow
    )
    assert plan.shots[0].kind is ShotKind.GENERATED
    assert plan.shots[0].asset and plan.shots[0].asset.endswith("shot-0.png")


def test_hinh_co_gian_theo_do_dai_giong_doc():
    """Giọng quyết định độ dài; hình phủ theo, nếu không cảnh cuối cắt giữa câu."""
    plan = default_plan(title="Cpk", target_sec=30)
    fitted = plan.fitted_to(48.0)
    assert fitted.total_sec == pytest.approx(48.0, abs=0.6)


# ---------------- Dùng lại phần sau của pipeline ----------------


def test_item_giai_doan_2_di_tiep_den_gate_duyet_nhu_giai_doan_1():
    item = Item.from_prompt(
        url=SourceUrl("https://nmi.vn/qone/studio#1"),
        source_id=1,
        script_vi="MES làm gì trong nhà máy.",
        title="MES 45 giây",
        target_sec=45.0,
        author="quan.nguyen",
    )
    item.mark_voiced()
    item.mark_aligned()
    item.mark_mixed()
    item.mark_rendered(path=MediaAsset("output/item-00000010/final.mp4"))
    item.send_to_human_review()
    assert item.stage is ItemStage.HUMAN_REVIEW
