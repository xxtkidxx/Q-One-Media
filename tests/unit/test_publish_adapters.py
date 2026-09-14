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


def test_tiktok_chi_bat_khi_co_token():
    """G7.1: có adapter, nhưng chưa có token thì im lặng bỏ qua như mọi nền tảng."""
    pubs = build_publishers(
        _settings(
            youtube_client_secret_file="/s.json",
            youtube_token_file="/t.json",
            fb_page_id="1",
            fb_page_access_token="t",
        )
    )
    assert PublishPlatform.TIKTOK not in pubs

    with_token = build_publishers(_settings(tiktok_access_token="tok"))
    assert set(with_token) == {PublishPlatform.TIKTOK}


# ---------------- TikTok (G7.1) ----------------


def test_tiktok_mac_dinh_self_only_va_khong_doan_quyen_hien_thi():
    """Client chưa audit chỉ đăng được riêng tư; đoán sai mức là hỏng cả lần đăng."""
    from src.infrastructure.publish.tiktok import TikTokPublisher

    tt = TikTokPublisher(access_token="tok")
    assert tt._privacy_level == "SELF_ONLY"


def _tiktok_with_options(monkeypatch, options, **kw):
    from src.infrastructure.publish import tiktok as tiktok_mod

    monkeypatch.setattr(
        tiktok_mod.TikTokPublisher,
        "_get",
        lambda self, client, url: {"data": {"privacy_level_options": options}},
    )
    return tiktok_mod.TikTokPublisher(access_token="tok", **kw)


def test_tiktok_ton_trong_muc_da_cau_hinh_khi_tai_khoan_duoc_phep(monkeypatch):
    tt = _tiktok_with_options(
        monkeypatch, ["PUBLIC_TO_EVERYONE", "SELF_ONLY"], privacy_level="PUBLIC_TO_EVERYONE"
    )
    assert tt._pick_privacy(client=None) == "PUBLIC_TO_EVERYONE"


@pytest.mark.parametrize(
    "options,expected",
    [
        (["PUBLIC_TO_EVERYONE", "SELF_ONLY"], "SELF_ONLY"),
        (["FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"], "FOLLOWER_OF_CREATOR"),
    ],
)
def test_tiktok_muc_cau_hinh_khong_duoc_phep_thi_ha_ve_kin_nhat(options, expected, monkeypatch):
    """Hạ về mức kín nhất, không leo lên công khai — sai hướng này là sự cố thật."""
    tt = _tiktok_with_options(monkeypatch, options, privacy_level="MUTUAL_FOLLOW_FRIENDS")
    assert tt._pick_privacy(client=None) == expected


def test_tiktok_khong_co_muc_nao_thi_bao_loi_chi_ro_can_kiem_gi(monkeypatch):
    from src.infrastructure.publish.tiktok import PublishRejected

    tt = _tiktok_with_options(monkeypatch, [])
    with pytest.raises(PublishRejected) as exc:
        tt._pick_privacy(client=None)
    assert "audit" in str(exc.value)


@pytest.mark.parametrize(
    "status,body",
    [(429, "rate_limit_exceeded"), (500, "server"), (400, "spam_risk_too_many_posts")],
)
def test_loi_han_muc_tiktok_thi_retry_duoc(status, body):
    from src.infrastructure.publish.tiktok import TikTokPublisher

    assert TikTokPublisher._classify(status, body).retryable is True


@pytest.mark.parametrize(
    "status,body",
    [(403, "unaudited_client_can_only_post_to_private_accounts"), (401, "access_token_invalid")],
)
def test_loi_audit_va_token_tiktok_thi_khong_retry(status, body):
    from src.infrastructure.publish.tiktok import TikTokPublisher

    error = TikTokPublisher._classify(status, body)
    assert error.retryable is False


def test_tiktok_gop_tieu_de_ghi_nguon_va_hashtag_vao_mot_o_chu():
    """TikTok chỉ có một ô chữ — ghi nguồn phải nằm trong đó, không mất đi."""
    from src.infrastructure.publish.tiktok import MAX_TITLE, TikTokPublisher

    title = TikTokPublisher._build_title(
        META, clearance(attribution="Nguồn: Vendor GmbH — CC BY 4.0")
    )
    assert title.startswith("Cpk nói gì")
    assert "Nguồn: Vendor GmbH" in title
    assert "#spc" in title
    assert len(title) <= MAX_TITLE


def test_tiktok_het_cho_thi_cat_hashtag_chu_khong_cat_ghi_nguon():
    from src.infrastructure.publish.tiktok import MAX_TITLE, TikTokPublisher

    long_credit = "Nguồn: " + "Vendor GmbH · " * 200
    title = TikTokPublisher._build_title(META, clearance(attribution=long_credit))
    assert len(title) <= MAX_TITLE
    assert "Nguồn: Vendor GmbH" in title
    assert "#spc" not in title


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
