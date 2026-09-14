"""Dây nối giữa các bước của worker.

Nhóm test này ra đời vì hai lỗi thật tìm được khi kiểm bảng handler bằng tay:
một ``JobTask`` không có handler (job sẽ treo vĩnh viễn), và ``handle_render``
gọi ``mark_rendered()`` từ ``aligned`` — một chuyển trạng thái mà máy trạng thái
không cho phép, nên bước render **chưa từng chạy được**.

Cả hai đều không cần GPU để bắt.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.errors import InvalidTransition
from src.domain.production.value_objects import ItemStage
from src.domain.scheduling.entities import Job, JobTask
from src.interfaces.worker.handlers import (
    HANDLERS,
    NEXT_TASK,
    REQUIRED_STAGE,
    enqueue_next,
)
from src.interfaces.worker.main import _mark_item_failed
from tests.fakes import FakeUnitOfWork
from tests.unit.test_item_lifecycle import item_at_review

NOW = datetime(2026, 9, 14, 10, 0, tzinfo=UTC)


# ---------------- Bảng handler phải khớp enum ----------------


def test_moi_job_task_deu_co_handler():
    """Một JobTask không có handler nghĩa là một job treo vĩnh viễn trong hàng đợi,
    và job pending mãi mãi khó phát hiện hơn job failed có thông báo."""
    missing = [str(t) for t in JobTask if t not in HANDLERS]
    assert missing == []


def test_moi_handler_deu_khai_trang_thai_bat_buoc():
    """Thiếu REQUIRED_STAGE là để một job lạc hậu kéo item đi sai đường."""
    missing = [str(t) for t in HANDLERS if t not in REQUIRED_STAGE]
    assert missing == []


def test_moi_handler_deu_co_muc_trong_bang_day_noi():
    missing = [str(t) for t in HANDLERS if t not in NEXT_TASK]
    assert missing == []


# ---------------- Dây đứt ở đúng hai gate của người ----------------


def test_day_dut_sau_transcribe_va_sau_render():
    """Đây là hai gate người. Nếu dây tự nối qua được thì gate mất tác dụng."""
    breaks = {t for t, nxt in NEXT_TASK.items() if nxt is None}
    assert JobTask.TRANSCRIBE in breaks
    assert JobTask.RENDER in breaks


def test_khong_xep_buoc_sau_khi_day_dut():
    uow = FakeUnitOfWork()
    enqueue_next(Job(task=JobTask.TRANSCRIBE, item_id=1, id=1), uow, item_id=1)
    assert uow.jobs.all() == []


def test_job_khong_retry_duoc_day_item_sang_failed_thay_vi_hien_stage_cu():
    uow = FakeUnitOfWork()
    item, _ = item_at_review()
    item.stage = ItemStage.TRANSCRIPT_APPROVED
    uow.items.add(item)
    job = Job(task=JobTask.PICK_SEGMENT, item_id=item.id, id=9)

    _mark_item_failed(job, uow, "LlmRejected: thiếu ANTHROPIC_API_KEY")

    saved = uow.items.get(item.id)
    assert saved is not None
    assert saved.stage is ItemStage.FAILED
    assert "ANTHROPIC_API_KEY" in (saved.stage_error or "")


def test_xep_dung_buoc_tiep_theo_va_giu_uu_tien():
    """Giữ ưu tiên: một item Douyin phải khẩn suốt chuỗi, không chỉ ở bước tải."""
    uow = FakeUnitOfWork()
    enqueue_next(Job(task=JobTask.DOWNLOAD, item_id=7, id=1, priority=10), uow, item_id=7)
    jobs = uow.jobs.all()
    assert len(jobs) == 1
    assert jobs[0].task is JobTask.SEPARATE
    assert jobs[0].item_id == 7
    assert jobs[0].priority == 10


def test_chuoi_tu_download_den_render_khong_dut_giua():
    """Đi hết chuỗi tự động: download → … → render, không thiếu mắt nào."""
    task = JobTask.DOWNLOAD
    seen = [task]
    while (nxt := NEXT_TASK[task]) is not None:
        task = nxt
        seen.append(task)
        assert len(seen) < 20, "vòng lặp trong bảng dây nối"
    assert seen == [
        JobTask.DOWNLOAD,
        JobTask.SEPARATE,
        JobTask.TRANSCRIBE,
    ]

    # Nhánh sau gate soát transcript
    task = JobTask.PICK_SEGMENT
    seen = [task]
    while (nxt := NEXT_TASK[task]) is not None:
        task = nxt
        seen.append(task)
    assert seen == [
        JobTask.PICK_SEGMENT,
        JobTask.WRITE_SCRIPT,
        JobTask.SYNTHESIZE,
        JobTask.ALIGN,
        JobTask.RENDER,
    ]


# ---------------- Trạng thái bắt buộc khớp dòng chảy ----------------


def test_trang_thai_bat_buoc_cua_render_gom_aligned():
    """``handle_render`` chạy ngay sau ``align``, nên phải nhận item ở ``aligned``."""
    assert ItemStage.ALIGNED in REQUIRED_STAGE[JobTask.RENDER]


def test_publish_chi_chay_voi_item_da_duyet():
    assert REQUIRED_STAGE[JobTask.PUBLISH] == (ItemStage.APPROVED,)


def test_render_phai_di_qua_mixed_truoc_khi_rendered():
    """Lỗi thật đã sửa: máy trạng thái không cho nhảy aligned → rendered.

    Nếu ai đó bỏ ``mark_mixed()`` khỏi ``handle_render`` thì test này đỏ, và bước
    render sẽ không chạy được — đúng như nó từng không chạy được.
    """
    from src.domain.production.value_objects import MediaAsset

    # Dựng lại một item đang ở aligned
    item2, _ = item_at_review()
    item2.stage = ItemStage.ALIGNED
    with pytest.raises(InvalidTransition):
        item2.mark_rendered(path=MediaAsset("output/x/final.mp4"))

    item3, _ = item_at_review()
    item3.stage = ItemStage.ALIGNED
    item3.mark_mixed()
    item3.mark_rendered(path=MediaAsset("output/x/final.mp4"))
    assert item3.stage is ItemStage.RENDERED
