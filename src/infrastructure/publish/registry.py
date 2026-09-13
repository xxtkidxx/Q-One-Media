"""Dựng tập publisher theo cấu hình.

Nền tảng **chưa bật là tình trạng bình thường**, không phải lỗi. Mỗi nền tảng có
lịch duyệt app riêng: YouTube đi được ngay, Facebook phải qua App Review (hoặc
lọt ngoại lệ app nội bộ), TikTok cần audit. Hệ thống phải chạy được khi mới có
một nền tảng — nên hàm này chỉ trả về những nền tảng **đã đủ cấu hình**, im lặng
bỏ qua phần còn lại.
"""

from __future__ import annotations

from pathlib import Path

from src.application.ports import VideoPublisher
from src.domain.publishing.value_objects import PublishPlatform
from src.shared.config import Settings
from src.shared.logging import get_logger

log = get_logger(__name__)


def build_publishers(settings: Settings) -> dict[PublishPlatform, VideoPublisher]:
    publishers: dict[PublishPlatform, VideoPublisher] = {}

    yt = settings.publish
    if yt.youtube_client_secret_file and yt.youtube_token_file:
        from src.infrastructure.publish.youtube import YouTubePublisher

        publishers[PublishPlatform.YOUTUBE] = YouTubePublisher(
            client_secret_file=Path(yt.youtube_client_secret_file),
            token_file=Path(yt.youtube_token_file),
        )
    else:
        log.info("publish.youtube.disabled", reason="chưa có credential OAuth (G3.1)")

    if yt.fb_page_id and yt.fb_page_access_token:
        from src.infrastructure.publish.facebook import FacebookReelsPublisher

        publishers[PublishPlatform.FACEBOOK] = FacebookReelsPublisher(
            page_id=yt.fb_page_id, page_access_token=yt.fb_page_access_token
        )
    else:
        log.info("publish.facebook.disabled", reason="chưa có Page ID / token (G4.1)")

    # TikTok cố tình không có adapter: client chưa audit bị khoá ở SELF_ONLY và
    # tối đa 5 user/24h, nên tự động hoá không đem lại gì. Xem G7.1 — chỉ làm nếu
    # dữ liệu G5 chứng minh đáng làm.
    return publishers
