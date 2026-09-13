"""Hàng đợi việc — phân loại lỗi và số lần thử."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.errors import InvalidTransition, InvariantViolation
from src.domain.scheduling.entities import (
    PRIORITY_NORMAL,
    PRIORITY_URGENT,
    Job,
    JobStatus,
    JobTask,
)

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)


def test_vong_doi_thanh_cong():
    job = Job(task=JobTask.DOWNLOAD, item_id=1, id=1)
    job.claim(worker="worker-1", at=NOW)
    assert job.status is JobStatus.RUNNING
    assert job.attempts == 1
    job.succeed(at=NOW + timedelta(seconds=30))
    assert job.status is JobStatus.DONE
    assert job.locked_by is None


def test_loi_retry_duoc_thi_xep_lai_hang_doi():
    job = Job(task=JobTask.DOWNLOAD, item_id=1, id=1, max_attempts=3)
    job.claim(worker="w1", at=NOW)
    job.fail(error="mạng timeout", at=NOW, retryable=True)
    assert job.status is JobStatus.PENDING
    assert job.attempts_left == 2
    assert job.locked_by is None  # nhả khoá để worker khác lấy được


def test_loi_khong_retry_duoc_thi_dung_luon():
    """License, input sai, cấu hình sai: thử lại chỉ tốn thời gian và nhiễu log."""
    job = Job(task=JobTask.DOWNLOAD, item_id=1, id=1)
    job.claim(worker="w1", at=NOW)
    job.fail(error="nguồn chưa approved", at=NOW, retryable=False)
    assert job.status is JobStatus.FAILED
    assert job.attempts_left == 2  # còn lượt nhưng không dùng — cố ý


def test_het_luot_thu_thi_that_bai_han():
    job = Job(task=JobTask.TRANSCRIBE, item_id=1, id=1, max_attempts=2)
    for _ in range(2):
        job.claim(worker="w1", at=NOW)
        job.fail(error="oom", at=NOW, retryable=True)
    assert job.status is JobStatus.FAILED
    assert job.attempts == 2


def test_worker_phai_co_ten_de_lan_lai_duoc_khi_treo():
    job = Job(task=JobTask.RENDER, item_id=1, id=1)
    with pytest.raises(InvariantViolation):
        job.claim(worker="  ", at=NOW)


def test_done_la_trang_thai_cuoi():
    job = Job(task=JobTask.MIX, item_id=1, id=1)
    job.claim(worker="w1", at=NOW)
    job.succeed(at=NOW)
    with pytest.raises(InvalidTransition):
        job.claim(worker="w1", at=NOW)


def test_uu_tien_khan_nho_hon_uu_tien_thuong():
    """Số nhỏ = làm trước. Douyin phải khẩn vì URL CDN hết hạn vài giờ."""
    assert PRIORITY_URGENT < PRIORITY_NORMAL
