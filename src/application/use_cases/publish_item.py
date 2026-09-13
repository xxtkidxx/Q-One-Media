"""Đăng một item lên một hoặc nhiều nền tảng.

Tầng này quyết định *có đăng hay không* và *ghi lại kết quả*; việc gọi API nền
tảng nằm ở adapter sau interface ``VideoPublisher``. Nhờ tách vậy mà chính sách
(watermark, gate duyệt, hạn mức) test được mà không cần token thật.

Nền tảng chưa bật là **tình trạng bình thường**, không phải lỗi — mỗi nền tảng
một lịch duyệt app riêng, và hệ thống phải chạy được khi mới có YouTube.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.application.ports import Clock, UnitOfWork, VideoPublisher
from src.domain.errors import DomainError, LicenseViolation
from src.domain.production.entities import Item
from src.domain.production.value_objects import ItemStage
from src.domain.publishing import policy
from src.domain.publishing.entities import Publication
from src.domain.publishing.value_objects import PublishPlatform, PublishStatus, VideoMetadata


class PublishDisabled(DomainError):
    """Kill-switch ``PUBLISH_ENABLED=false``. Chỉ chặn thêm, không bao giờ mở thêm."""


class ItemNotFound(DomainError):
    pass


class QuotaExhausted(DomainError):
    retryable = True  # mai là hết — xếp lại chứ không bỏ


@dataclass(frozen=True, slots=True)
class PublishOutcome:
    platform: PublishPlatform
    status: PublishStatus
    remote_url: str | None = None
    reason: str | None = None


def publish_item(
    item_id: int,
    *,
    metadata: VideoMetadata,
    publishers: dict[PublishPlatform, VideoPublisher],
    media_root: Path,
    uow: UnitOfWork,
    clock: Clock,
    enabled: bool,
    actor: str = "system",
) -> list[PublishOutcome]:
    if not enabled:
        raise PublishDisabled("PUBLISH_ENABLED=false — không đăng gì")

    outcomes: list[PublishOutcome] = []

    with uow:
        item = uow.items.get(item_id)
        if item is None:
            raise ItemNotFound(f"không có item #{item_id}")
        source = uow.sources.get(item.source_id)
        if source is None:
            raise ItemNotFound(f"item #{item_id} trỏ tới nguồn #{item.source_id} không tồn tại")

        for platform, publisher in publishers.items():
            pub = uow.publications.get_for(item_id, platform) or uow.publications.add(
                Publication(item_id=item_id, platform=platform)
            )
            if pub.status is PublishStatus.PUBLISHED:
                outcomes.append(
                    PublishOutcome(platform, PublishStatus.PUBLISHED, pub.remote_url, "đã đăng")
                )
                continue
            if pub.status is PublishStatus.FAILED:
                pub.requeue()

            try:
                clearance = source.clear_for_publish(clock.now())
            except LicenseViolation as exc:
                pub.skip(str(exc))
                uow.publications.update(pub)
                outcomes.append(PublishOutcome(platform, PublishStatus.SKIPPED, None, str(exc)))
                continue

            decision = policy.decide(item=item, platform=platform, clearance=clearance)
            if not decision.allowed:
                assert decision.reason is not None
                pub.skip(decision.reason)
                uow.publications.update(pub)
                outcomes.append(
                    PublishOutcome(platform, PublishStatus.SKIPPED, None, decision.reason)
                )
                continue

            quota = platform.daily_upload_quota
            if quota is not None and uow.publications.count_published_today(platform) >= quota:
                raise QuotaExhausted(f"{platform}: đã dùng hết {quota} lượt đăng hôm nay")

            assert item.path_output is not None
            pub.start_upload()
            uow.publications.update(pub)
            try:
                result = publisher.publish(
                    video=media_root / item.path_output.relative_path,
                    metadata=metadata.with_attribution(clearance.attribution_text),
                    clearance=clearance,
                )
            except Exception as exc:  # noqa: BLE001 — lỗi adapter nền tảng rất đa dạng
                # Bắt rộng ở đúng một chỗ này là có chủ ý: SDK ba nền tảng ném
                # ba họ exception khác nhau, và một nền tảng lỗi không được làm
                # đổ các nền tảng còn lại. Lỗi được ghi nguyên văn, không nuốt.
                pub.fail(f"{type(exc).__name__}: {exc}")
                uow.publications.update(pub)
                outcomes.append(PublishOutcome(platform, PublishStatus.FAILED, None, str(exc)))
                continue

            pub.mark_published(
                remote_id=result.remote_id, remote_url=result.remote_url, at=clock.now()
            )
            uow.publications.update(pub)
            uow.audit.record(
                entity="publication",
                entity_id=pub.id or 0,
                action="published",
                actor=actor,
                detail={"platform": str(platform), "remote_id": result.remote_id},
            )
            outcomes.append(
                PublishOutcome(platform, PublishStatus.PUBLISHED, result.remote_url)
            )

        _advance_item_if_published(item, uow, actor)
        uow.commit()

    return outcomes


def _advance_item_if_published(item: Item, uow: UnitOfWork, actor: str) -> None:
    """Item sang ``published`` khi có **ít nhất một** nền tảng đăng được.

    Không đòi tất cả nền tảng thành công: Facebook đang chờ App Review không
    nên giữ item lại mãi khi YouTube đã đăng xong.
    """
    assert item.id is not None
    if item.stage is not ItemStage.APPROVED:
        # Gọi lại publish_item trên một item đã đăng là bình thường (thêm nền
        # tảng mới, đăng lại nền tảng từng lỗi) — không đổi trạng thái item nữa.
        return
    pubs = uow.publications.list_for_item(item.id)
    if any(p.status is PublishStatus.PUBLISHED for p in pubs):
        item.mark_published()
        uow.items.update(item)
        uow.audit.record(entity="item", entity_id=item.id, action="published", actor=actor)
