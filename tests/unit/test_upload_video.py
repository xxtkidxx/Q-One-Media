"""Nạp file vẫn phải đi qua license gate của nguồn đã chọn."""

from datetime import UTC, datetime

import pytest

from src.application.use_cases.upload_video import register_uploaded_video
from src.domain.errors import SourceNotApproved
from src.domain.production.value_objects import AspectRatio, ItemStage, MediaAsset
from src.domain.scheduling.entities import JobTask
from tests.fakes import FakeClock, FakeUnitOfWork
from tests.unit.test_submit_url import approve, declare


def _register(uow, clock):
    return register_uploaded_video(
        source_id=1,
        upload_id="abc123",
        original_filename="demo.mp4",
        asset=MediaAsset("source/uploads/abc123.mp4"),
        duration_sec=61,
        aspect_ratio=AspectRatio(16, 9),
        uow=uow,
        clock=clock,
        actor="quan.nguyen",
    )


def test_upload_nguon_da_duyet_di_thang_sang_tach_audio():
    uow = FakeUnitOfWork()
    clock = FakeClock(datetime(2026, 9, 14, tzinfo=UTC))
    declare(uow)
    approve(uow, clock, 1)

    item = _register(uow, clock)

    assert item.stage is ItemStage.DOWNLOADED
    assert item.source_id == 1
    assert item.path_source == MediaAsset("source/uploads/abc123.mp4")
    assert uow.jobs.all()[0].task is JobTask.SEPARATE
    assert "video_uploaded" in uow.audit.actions()


def test_upload_nguon_chua_duyet_bi_license_gate_chan():
    uow = FakeUnitOfWork()
    clock = FakeClock(datetime(2026, 9, 14, tzinfo=UTC))
    declare(uow)

    with pytest.raises(SourceNotApproved):
        _register(uow, clock)

    assert not uow.items.count_by_stage()
    assert not uow.jobs.all()
