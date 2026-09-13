"""Hộp thư URL — cửa vào chính của Giai đoạn 1, và là nơi license gate chạy thật.

Người dán một URL video. Hệ thống tự tìm nguồn cha đã khai báo, rồi:

- không có nguồn cha  → từ chối, và nói rõ phải khai báo nguồn trước
- nguồn cha chưa có quyền → tạo item ``license_blocked`` (vẫn lưu, để thấy nhu
  cầu thật và biết nên đi xin phép hãng nào trước)
- nguồn cha có quyền → tạo item ``inbox`` + xếp việc tải

Một chi tiết dễ bỏ sót nhưng làm vỡ cả luồng: URL Douyin hết hạn sau vài giờ,
nên việc tải phải được xếp ở mức **khẩn**, không đứng chung hàng đợi thường.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports import Clock, UnitOfWork
from src.domain.errors import DomainError, LicenseViolation, OwnershipMismatch
from src.domain.production.entities import Item
from src.domain.scheduling.entities import (
    PRIORITY_NORMAL,
    PRIORITY_URGENT,
    Job,
    JobTask,
)
from src.domain.sourcing.value_objects import SourceUrl


class SourceNotDeclared(DomainError):
    """URL không thuộc nguồn nào đã khai báo.

    Cố tình không tự tạo nguồn: khai báo nguồn là hành vi có trách nhiệm pháp lý,
    phải do người làm, không để hệ thống suy ra.
    """


class ItemAlreadyExists(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitUrlResult:
    item: Item
    accepted: bool
    job_id: int | None
    reason: str | None = None


def submit_url(
    raw_url: str,
    *,
    uow: UnitOfWork,
    clock: Clock,
    actor: str,
) -> SubmitUrlResult:
    url = SourceUrl(raw_url)
    now = clock.now()

    with uow:
        existing = uow.items.get_by_url(url)
        if existing is not None:
            raise ItemAlreadyExists(
                f"URL này đã có item #{existing.id} ở trạng thái {existing.stage}"
            )

        source = uow.sources.find_owning(url)
        if source is None:
            raise SourceNotDeclared(
                f"chưa khai báo nguồn nào bao trùm {url.host} — "
                "khai báo nguồn và duyệt license trước khi nạp URL"
            )
        assert source.id is not None

        # Xin clearance. Từ chối vì license là kết quả bình thường của nghiệp vụ
        # ở đây, không phải sự cố — nên bắt đúng nhóm LicenseViolation và ghi lại.
        try:
            clearance = source.clear_for_download(now)
            # Chặn sớm nếu nguồn dạng bao mà chưa khai id chủ kênh: không có cách
            # xác minh thì việc tải chắc chắn sẽ bị từ chối ở bước sau, nên nói
            # ngay tại đây thay vì để người dùng chờ một job rồi mới thấy lỗi.
            if not source.ownership_is_verifiable:
                raise OwnershipMismatch(
                    f"nguồn #{source.id} ({source.url.host}) dạng {source.kind} chưa khai "
                    "external_owner_id — bổ sung id chủ kênh rồi nạp lại URL"
                )
        except LicenseViolation as exc:
            item = uow.items.add(Item.blocked(url=url, source_id=source.id, reason=str(exc)))
            assert item.id is not None
            uow.audit.record(
                entity="item",
                entity_id=item.id,
                action="license_blocked",
                actor=actor,
                detail={"url": raw_url, "source_id": source.id, "reason": str(exc)},
            )
            uow.commit()
            return SubmitUrlResult(item=item, accepted=False, job_id=None, reason=str(exc))

        item = uow.items.add(Item.accept(url=url, clearance=clearance))
        assert item.id is not None

        job = uow.jobs.enqueue(
            Job(
                task=JobTask.DOWNLOAD,
                item_id=item.id,
                priority=PRIORITY_URGENT if clearance.url_expires_fast else PRIORITY_NORMAL,
                payload={"url": raw_url, "platform": clearance.platform},
            )
        )
        uow.audit.record(
            entity="item",
            entity_id=item.id,
            action="accepted",
            actor=actor,
            detail={
                "url": raw_url,
                "source_id": source.id,
                "urgent": clearance.url_expires_fast,
            },
        )
        uow.commit()

    return SubmitUrlResult(item=item, accepted=True, job_id=job.id)
