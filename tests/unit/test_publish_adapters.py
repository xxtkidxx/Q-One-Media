"""Adapter publish — phần không cần token thật.

Kiểm ba thứ quan trọng: mô tả video có ghi nguồn và nhãn AI, phân loại lỗi đúng
(retry được hay không), và registry bỏ qua nền tảng chưa cấu hình thay vì nổ.
"""

from __future__ import annotations

import pytest

from src.domain.publishing.value_objects import PublishPlatform, VideoMetadata
from src.domain.sourcing.entities import Source
from src.domain.sourcing.value_objects import (
    LicenseEvidence,
    LicenseScope,
    LicenseType,
    Platform,
    SourceKind,
    SourceUrl,
)
from src.infrastructure.publish.facebook import FacebookReelsPublisher
from src.infrastructure.publish.facebook import PublishFailed as FbFailed
from src.infrastructure.publish.facebook import PublishRejected as FbRejected
from src.infrastructure.publish.registry import build_publishers
from src.infrastructure.publish.youtube import YouTubePublisher
from src.shared.config import (
    LLMSettings,
    PublishSettings,
    Settings,
    TTSSettings,
)
from tests.unit.test_license_gate import NOW

PUB_SCOPE = LicenseScope(may_republish=True, may_commercial_use=True)


def clearance(*, attribution: str | None = None):
    src = Source(
        platform=Platform.YOUTUBE,
        kind=SourceKind.SINGLE_URL,
        url=SourceUrl("https://www.youtube.com/watch?v=a"),
        id=1,
    )
    src.approve(
        by="q",
        evidence=LicenseEvidence(
            license_type=LicenseType.CC_BY if attribution else LicenseType.OWN,
            evidence_ref="ref",
            attribution_text=attribution,
        ),
        scope=PUB_SCOPE,
        at=NOW,
    )
    return src.clear_for_publish(NOW)


META = VideoMetadata(title="Cpk nói gì", description="Phân tích của NMI.", tags=("spc", "cpk"))


# ---------------- Mô tả video ----------------


def test_mo_ta_youtube_co_ghi_nguon_va_nhan_ai():
    """Cả hai là yêu cầu bắt buộc: ghi nguồn là nghĩa vụ license CC BY, nhãn AI là
    yêu cầu công bố của nền tảng. Đặt trong adapter để không đường nào bỏ qua."""
    text = YouTubePublisher._build_description(
        META, clearance(attribution="Nguồn: Vendor GmbH (CC BY 4.0)")
    )
    assert "Phân tích của NMI." in text
    assert "Nguồn: Vendor GmbH" in text
    assert "AI" in text


def test_mo_ta_khong_co_ghi_nguon_thi_khong_chen_dong_rong():
    text = YouTubePublisher._build_description(META, clearance())
    assert "\n\n\n" not in text


def test_mo_ta_tat_nhan_ai_khi_khong_dung_giong_may():
    meta = VideoMetadata(title="x", description="y", ai_generated_voice=False)
    assert "AI" not in YouTubePublisher._build_description(meta, clearance())


def test_mo_ta_youtube_bi_cat_theo_gioi_han():
    meta = VideoMetadata(title="x", description="y" * 6000)
    assert len(YouTubePublisher._build_description(meta, clearance())) <= 5000


def test_mo_ta_facebook_them_hashtag_tu_tag():
    text = FacebookReelsPublisher._build_description(META, clearance())
    assert "#spc" in text and "#cpk" in text


# ---------------- Phân loại lỗi Facebook ----------------


@pytest.mark.parametrize(
    "status,body",
    [(429, "{}"), (500, "{}"), (400, '{"error":{"code":4}}'), (400, '{"error":{"code":32}}')],
)
def test_loi_tam_thoi_cua_facebook_thi_retry_duoc(status, body):
    assert isinstance(FacebookReelsPublisher._classify(status, body), FbFailed)


@pytest.mark.parametrize(
    "status,body",
    [(401, "{}"), (403, "{}"), (400, '{"error":{"code":190}}'), (400, '{"error":{"code":200}}')],
)
def test_loi_cau_hinh_cua_facebook_thi_khong_retry(status, body):
    """Token hết hạn và thiếu quyền: thử lại vô nghĩa, chỉ làm nhiễu log."""
    exc = FacebookReelsPublisher._classify(status, body)
    assert isinstance(exc, FbRejected)
    assert exc.retryable is False


def test_thong_bao_thieu_quyen_chi_ro_can_kiem_gi():
    msg = str(FacebookReelsPublisher._classify(403, "{}"))
    assert "pages_manage_posts" in msg
    assert "App Review" in msg


def test_thieu_page_id_thi_tu_choi_ngay_khi_dung():
    with pytest.raises(FbRejected):
        FacebookReelsPublisher(page_id="", page_access_token="x")


# ---------------- Registry ----------------


def _settings(**publish_kw) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql://x/y",
        media_root=__import__("pathlib").Path("/data/media"),
        model_cache=__import__("pathlib").Path("/models"),
        log_level="INFO",
        worker_concurrency=1,
        gpu_count=0,
        llm=LLMSettings(api_key=""),
        tts=TTSSettings(),
        publish=PublishSettings(**publish_kw),
    )


def test_chua_cau_hinh_nen_tang_nao_thi_tra_ve_rong_khong_no():
    """Nền tảng chưa bật là tình trạng bình thường — hệ thống phải chạy được."""
    assert build_publishers(_settings()) == {}


def test_chi_cau_hinh_youtube_thi_chi_co_youtube():
    pubs = build_publishers(
        _settings(youtube_client_secret_file="/s.json", youtube_token_file="/t.json")
    )
    assert set(pubs) == {PublishPlatform.YOUTUBE}


def test_cau_hinh_ca_hai_thi_co_ca_hai():
    pubs = build_publishers(
        _settings(
            youtube_client_secret_file="/s.json",
            youtube_token_file="/t.json",
            fb_page_id="123",
            fb_page_access_token="tok",
        )
    )
    assert set(pubs) == {PublishPlatform.YOUTUBE, PublishPlatform.FACEBOOK}


def test_tiktok_khong_co_adapter():
    """Client chưa audit bị khoá ở SELF_ONLY, tối đa 5 user/24h — tự động hoá
    không đem lại gì. Chỉ làm nếu dữ liệu G5 chứng minh đáng làm (G7.1)."""
    pubs = build_publishers(
        _settings(
            youtube_client_secret_file="/s.json",
            youtube_token_file="/t.json",
            fb_page_id="1",
            fb_page_access_token="t",
        )
    )
    assert PublishPlatform.TIKTOK not in pubs


# ---------------- Mặc định an toàn ----------------


def test_mac_dinh_dang_o_che_do_khong_cong_khai():
    """Video đã qua người duyệt nội dung, nhưng bước cho công khai nên là hành
    động có ý thức của người vận hành, không phải mặc định của code."""
    yt = YouTubePublisher(
        client_secret_file=__import__("pathlib").Path("/s.json"),
        token_file=__import__("pathlib").Path("/t.json"),
    )
    assert yt._privacy == "private"

    fb = FacebookReelsPublisher(page_id="1", page_access_token="t")
    assert fb._publish_immediately is False
